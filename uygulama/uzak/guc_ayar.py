"""Uzak betik — uyku/ekran koruyucu ayarı ve zamanlı kapatma (öğrenci PC'de, root).

Amaç: bilgisayar boşta kalınca UYKUYA GEÇMEZ ve KAPANMAZ (yönetim için erişilebilir kalır);
yalnız ekran kararır (ekran koruyucu). Kapanma yalnız öğretmenin planladığı zamanda olur.

Kipler (argv[1], JSON):
  {"kip": "durum"}                                   salt okunur
  {"kip": "uyku", "islem": "onizle"|"uygula"|"kaldir", "ekran_dk": 10}
      uygula: uyku hedefleri maskelenir (systemctl mask), GNOME güç ayarları dconf
      sistem veritabanına yazılıp kilitlenir (oturum ve giriş ekranı), logind boşta
      eylemi "ignore" yapılır. kaldir: yalnız bu uygulamanın yaptıkları geri alınır.
  {"kip": "kapatma_ekle", "id": "a1b2c3", "takvim": "Mon..Fri *-*-* 17:30:00", "tur": "surekli"|"tek",
   "uyari_dk": 5, "etiket": "Pzt–Cum 17:30", "aciklama": "..."}
      systemd zamanlayıcısı (cron/at benzeri). Persistent=false: kapalıyken kaçan kapatma
      açılışta UYGULANMAZ. Zamanı gelince öğrencilere uyarı gösterilir, uyarı süresi
      geçici bir zamanlayıcıyla beklenir (shutdown +N değil: son 5 dk'da SSH'yi kapatır)
      ve sonunda bilgisayar kapanır. "tek" plan çalışınca kendini siler.
  {"kip": "kapatma_sil", "idler": ["a1b2c3"] | "hepsi"}
  {"kip": "kapatma_iptal"}      uyarı süresindeki bekleyen kapatmayı iptal eder, öğrencilere bildirir
Çıktı: tek satır JSON.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

UYKU_HEDEFLERI = ("sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target",
                  "suspend-then-hibernate.target")
DCONF_YEREL = "/etc/dconf/db/local.d/94-pardus-sinif-guc"
DCONF_YEREL_KILIT = "/etc/dconf/db/local.d/locks/94-pardus-sinif-guc"
DCONF_GDM = "/etc/dconf/db/gdm.d/94-pardus-sinif-guc"
DCONF_GDM_KILIT = "/etc/dconf/db/gdm.d/locks/94-pardus-sinif-guc"
DCONF_GDM_DB = "/etc/dconf/db/gdm"
GDM_PROFIL = "/etc/dconf/profile/gdm"
# Debian/Pardus: paketin profili burada ve system-db:gdm İÇERMEZ (yalnız file-db:/var/lib/gdm3/...)
GDM_PROFIL_PAKET = "/usr/share/dconf/profile/gdm"
GDM_PROFIL_IMZA = "# Pardus Sinif Yonetimi: giris ekrani guc ayari icin system-db:gdm eklendi (M2-S4)"
LOGIND = "/etc/systemd/logind.conf.d/pardus-sinif-guc.conf"
KOK = "/var/lib/pardus-sinif-yonetimi"
DURUM_DOSYASI = KOK + "/guc.json"
BIRIM_KOK = "/etc/systemd/system"
ON_EK = "pardus-sinif-kapat-"
YARDIMCI = "/usr/local/sbin/pardus-sinif-kapat"
BEKLEYEN = "/run/systemd/shutdown/scheduled"
ID_DESENI = re.compile(r"^[a-z0-9]{4,16}$")
TAKVIM_DESENI = re.compile(r"^[A-Za-z0-9 ,.*:\-]{5,80}$")
ORTAM = dict(os.environ, LC_ALL="C", LANG="C")

GUC_ANAHTARLARI = [  # (dconf yolu, değer) — oturum ve giriş ekranı için
    ("/org/gnome/settings-daemon/plugins/power/sleep-inactive-ac-type", "'nothing'"),
    ("/org/gnome/settings-daemon/plugins/power/sleep-inactive-battery-type", "'nothing'"),
    ("/org/gnome/settings-daemon/plugins/power/sleep-inactive-ac-timeout", "0"),
    ("/org/gnome/settings-daemon/plugins/power/sleep-inactive-battery-timeout", "0"),
]
EKRAN_ANAHTARI = "/org/gnome/desktop/session/idle-delay"

LOGIND_ICERIK = """# Pardus Sinif Yonetimi: bosta uyku / askiya alma yok (yonetim icin erisilebilir kalsin)
[Login]
IdleAction=ignore
HandleSuspendKey=ignore
HandleHibernateKey=ignore
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
"""

BEKLEYEN_BIRIM = "pardus-sinif-kapatma-bekliyor"   # geçici (systemd-run) zamanlayıcı: uyarı süresi
BEKLEYEN_SAAT = "/run/pardus-sinif-kapatma"         # bekleyen kapanma saati (SS:DD); açılışta silinir
BEKLEYEN_BILDIRIM = BEKLEYEN_SAAT + ".bildirim"      # "kullanıcı bildirim_kimliği" satırları (uyarı)

YARDIMCI_ICERIK = r"""#!/bin/sh
# Pardus Sinif Yonetimi - zamanli kapatma yardimcisi (uygulama tarafindan yazilir; elle duzenlemeyin)
# Kullanim: pardus-sinif-kapat <uyari_dakika> <plan_id> <tek|surekli>
# Uyari suresi "shutdown +N" ile BEKLENMEZ: logind kapanmaya 5 dakika kala /run/nologin olusturur,
# root disi SSH girisi kapanir ve uygulama kapatmayi iptal edemez (lab'da goruldu). Bunun yerine
# gecici bir systemd zamanlayicisi kurulur; iptal = "systemctl stop pardus-sinif-kapatma-bekliyor.timer".
DK="$1"; ID="$2"; TUR="$3"
BEKLEYEN=pardus-sinif-kapatma-bekliyor
case "$DK" in ''|*[!0-9]*) DK=5 ;; esac
case "$ID" in ''|*[!a-z0-9]*) exit 2 ;; esac
if [ "$TUR" = "tek" ]; then
  # --now: calismis zamanlayici durdurulur (bu servisi etkilemez); yoksa dosyasi silinse de
  # "list-timers --all"da asili kalir
  systemctl disable --now "pardus-sinif-kapat-$ID.timer" >/dev/null 2>&1
  rm -f "/etc/systemd/system/pardus-sinif-kapat-$ID.timer" "/etc/systemd/system/pardus-sinif-kapat-$ID.service"
  systemctl daemon-reload >/dev/null 2>&1
fi
# Ayni anda ikinci bir plan tetiklenirse ilk sayac gecerli kalir
systemctl is-active --quiet "$BEKLEYEN.timer" && exit 0
if [ "$DK" -gt 0 ]; then
  SAAT=$(date -d "+$DK min" +%H:%M)
  MESAJ="Bu bilgisayar $DK dakika sonra ($SAAT) kapanacak (zamanli kapatma). Lutfen calismalarinizi kaydedin."
  GOVDE="Bu bilgisayar $DK dakika sonra ($SAAT) kapanacak. Lütfen çalışmalarınızı kaydedin."
else
  MESAJ="Bu bilgisayar simdi kapaniyor (zamanli kapatma)."
  GOVDE="Bu bilgisayar şimdi kapanıyor."
fi
# Masaüstü bildirimi: Pardus'ta notify-send (libnotify-bin) kurulu gelmez; gdbus (libglib2.0-bin) gelir.
# Bildirim kimligi saklanir: iptal edilirse "iptal edildi" bildirimi uyarinin yerine gecer
# (kritik uyari ogrenci kapatana kadar ekranda kalir).
rm -f /run/pardus-sinif-kapatma.bildirim
bildir() {
  ADR="unix:path=/run/user/$2/bus"
  if command -v gdbus >/dev/null 2>&1; then
    NID=$(runuser -u "$1" -- env DBUS_SESSION_BUS_ADDRESS="$ADR" gdbus call --session \
      --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications \
      --method org.freedesktop.Notifications.Notify "Lab Kaptanı" 0 system-shutdown \
      "Zamanlı kapatma" "$GOVDE" "[]" "{'urgency': <byte 2>}" 0 2>/dev/null \
      | sed -n 's/^(uint32 \([0-9][0-9]*\),)$/\1/p')
    [ -n "$NID" ] && echo "$1 $NID" >> /run/pardus-sinif-kapatma.bildirim
  elif command -v notify-send >/dev/null 2>&1; then
    runuser -u "$1" -- env DBUS_SESSION_BUS_ADDRESS="$ADR" \
      notify-send -u critical -i system-shutdown "Zamanlı kapatma" "$GOVDE" >/dev/null 2>&1
  fi
}
for OT in $(loginctl list-sessions --no-legend | awk '{print $1}'); do
  TIP=$(loginctl show-session "$OT" -p Type --value 2>/dev/null)
  KUL=$(loginctl show-session "$OT" -p Name --value 2>/dev/null)
  case "$TIP" in
    x11|wayland)
      KID=$(id -u "$KUL" 2>/dev/null) || continue
      [ -S "/run/user/$KID/bus" ] || continue
      bildir "$KUL" "$KID" || true ;;
  esac
done
command -v wall >/dev/null 2>&1 && timeout 10 wall "$MESAJ" >/dev/null 2>&1
if [ "$DK" -gt 0 ]; then
  echo "$SAAT" > /run/pardus-sinif-kapatma
  exec systemd-run --quiet --unit="$BEKLEYEN" --description="Pardus Sinif Yonetimi bekleyen zamanli kapatma" \
    --on-active="${DK}min" --timer-property=AccuracySec=1s /bin/systemctl poweroff
fi
exec /bin/systemctl poweroff
"""


def calistir(argv, zaman=60):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ORTAM)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "zaman aşımı"
    except OSError as hata:
        return 127, "", str(hata)


def yaz(yol, icerik, kip=0o644):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".psy-yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(icerik)
    os.chmod(gecici, kip)
    os.replace(gecici, yol)


def sil(yol):
    try:
        os.unlink(yol)
        return True
    except FileNotFoundError:
        return False


def durum_oku():
    try:
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def durum_yaz(veri):
    os.makedirs(KOK, mode=0o700, exist_ok=True)
    yaz(DURUM_DOSYASI, json.dumps(veri, ensure_ascii=False), 0o600)


# ---------------------------------------------------------------- dconf içeriği (saf işlevler)

def dconf_icerik(anahtarlar):
    """[(yol, değer)] → keyfile metni (bölümler sıralı)."""
    bolumler = {}
    for yol, deger in anahtarlar:
        bolum, ad = yol.rsplit("/", 1)
        bolumler.setdefault(bolum.strip("/"), []).append("%s=%s" % (ad, deger))
    satirlar = ["# Pardus Sinif Yonetimi: guc ayari (M2-S4)"]
    for bolum in sorted(bolumler):
        satirlar += ["", "[%s]" % bolum] + bolumler[bolum]
    return "\n".join(satirlar) + "\n"


def oturum_anahtarlari(ekran_dk):
    return GUC_ANAHTARLARI + [(EKRAN_ANAHTARI, "uint32 %d" % (max(0, int(ekran_dk)) * 60))]


def _satirlar(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return f.read().splitlines()
    except OSError:
        return None


def gdm_profili_var():
    """Etkin GDM profili (önce /etc, yoksa paketin /usr/share kopyası) system-db:gdm okuyor mu?"""
    satirlar = _satirlar(GDM_PROFIL)
    if satirlar is None:
        satirlar = _satirlar(GDM_PROFIL_PAKET) or []
    return any(s.strip() == "system-db:gdm" for s in satirlar)


def gdm_profili_icerik(paket_satirlari):
    """Paket profilinin kopyası + system-db:gdm (user-db'den hemen sonra: file-db varsayılanlarını ezer)."""
    satirlar = [s for s in paket_satirlari if s.strip()]
    yer = next((i + 1 for i, s in enumerate(satirlar) if s.strip().startswith("user-db:")), 0)
    return "\n".join([GDM_PROFIL_IMZA] + satirlar[:yer] + ["system-db:gdm"] + satirlar[yer:]) + "\n"


def gdm_profili_hazirla():
    """GDM giriş ekranının system-db:gdm okumasını sağlar. (hazir, bizim_olusturduk, not)"""
    if gdm_profili_var():
        return True, False, None
    if os.path.exists(GDM_PROFIL):  # başkasının profili: dokunulmaz
        return False, False, "giriş ekranı: %s system-db:gdm içermiyor, değiştirilmedi" % GDM_PROFIL
    paket = _satirlar(GDM_PROFIL_PAKET)
    if paket is None:
        return False, False, None  # GDM yok (başka giriş yöneticisi): uyku hedefleri maskesi yeterli
    yaz(GDM_PROFIL, gdm_profili_icerik(paket))
    return True, True, None


def dconf_oku(db, yol):
    """Derlenmiş sistem veritabanından okur (kullanıcı ayarları karışmaz)."""
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="psy-profil-") as f:
        f.write("system-db:%s\n" % db)
        profil = f.name
    try:
        r = subprocess.run(["dconf", "read", yol], capture_output=True, text=True, timeout=15,
                           env=dict(ORTAM, DCONF_PROFILE=profil))
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None
    finally:
        os.unlink(profil)


def ayni(okunan, beklenen):
    if okunan is None:
        return False
    okunan = okunan.replace("uint32 ", "")
    beklenen = beklenen.replace("uint32 ", "")
    return okunan == beklenen


# ---------------------------------------------------------------- durum

def hedef_durumlari():
    sonuc = {}
    for h in UYKU_HEDEFLERI:
        rc, cikti, _ = calistir(["systemctl", "is-enabled", h], 15)
        sonuc[h] = cikti.strip() or ("yok" if rc else "?")
    return sonuc


def ekran_dk_oku():
    try:
        with open(DCONF_YEREL, encoding="utf-8") as f:
            es = re.search(r"^idle-delay=uint32 (\d+)", f.read(), re.M)
        return int(es.group(1)) // 60 if es else None
    except OSError:
        return None


def plan_bilgisi(timer_yolu):
    meta = {}
    try:
        with open(timer_yolu, encoding="utf-8") as f:
            for satir in f:
                if satir.startswith("# psy: "):
                    meta = json.loads(satir[7:])
                elif satir.startswith("OnCalendar="):
                    meta["takvim"] = satir.split("=", 1)[1].strip()
    except (OSError, ValueError):
        pass
    ad = os.path.basename(timer_yolu)
    meta["id"] = ad[len(ON_EK):-len(".timer")]
    rc, cikti, _ = calistir(["systemctl", "show", ad, "-p", "NextElapseUSecRealtime", "-p", "ActiveState",
                             "-p", "UnitFileState"], 15)
    alan = dict(s.split("=", 1) for s in cikti.splitlines() if "=" in s)
    meta["sonraki"] = alan.get("NextElapseUSecRealtime") or None
    meta["etkin"] = alan.get("ActiveState") == "active" and alan.get("UnitFileState") == "enabled"
    return meta


def planlar():
    return [plan_bilgisi(y) for y in sorted(glob.glob(os.path.join(BIRIM_KOK, ON_EK + "*.timer")))]


def bekleyen_durumu():
    """(bizim sayaç çalışıyor mu, logind'de "shutdown +N" var mı, bekleyen kapanma saati)"""
    _, cikti, _ = calistir(["systemctl", "is-active", BEKLEYEN_BIRIM + ".timer"], 15)
    bizim = cikti.strip() == "active"
    saat = None
    if bizim:
        try:
            with open(BEKLEYEN_SAAT, encoding="utf-8") as f:
                saat = f.read().strip()[:5] or None
        except OSError:
            pass
    return bizim, os.path.exists(BEKLEYEN), saat


def yardimci_guncelle():
    """Plan varsa yardımcı betiği bu sürümün içeriğiyle yeniler; plan birimleri hep aynı yolu çağırır,
    bu yüzden uygulama güncellenince eski betik (ör. shutdown +N kullanan) yerinde kalmamalı."""
    if os.geteuid() != 0 or not glob.glob(os.path.join(BIRIM_KOK, ON_EK + "*.timer")):
        return False
    try:
        with open(YARDIMCI, encoding="utf-8") as f:
            if f.read() == YARDIMCI_ICERIK:
                return False
    except OSError:
        pass
    yaz(YARDIMCI, YARDIMCI_ICERIK, 0o755)
    return True


def durum(p=None):
    yenilendi = yardimci_guncelle() if (p or {}).get("yardimci_yenile") else False
    hedefler = hedef_durumlari()
    bizim, logind, saat = bekleyen_durumu()
    return {"uyku": {"hedefler": hedefler, "kapali": all(v == "masked" for v in hedefler.values()),
                     "dconf": os.path.exists(DCONF_YEREL), "ekran_dk": ekran_dk_oku(),
                     "logind": os.path.exists(LOGIND), "bizim": durum_oku().get("maskelenen") or []},
            "planlar": planlar(), "bekleyen": bizim or logind, "bekleyen_saat": saat,
            "yardimci_yenilendi": yenilendi, "zaman": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ---------------------------------------------------------------- uyku ayarı

def uyku(p):
    islem = p.get("islem", "onizle")
    ekran_dk = int(p.get("ekran_dk", 10))
    if islem not in ("onizle", "uygula", "kaldir") or not 0 <= ekran_dk <= 240:
        return {"hata": "geçersiz parametre"}
    once = durum()
    if islem == "onizle":
        maskelenecek = [h for h, v in once["uyku"]["hedefler"].items() if v not in ("masked", "yok")]
        gdm = gdm_profili_var() or (not os.path.exists(GDM_PROFIL) and os.path.exists(GDM_PROFIL_PAKET))
        return {"islem": "onizle", "once": once, "maskelenecek": maskelenecek,
                "gdm": gdm, "ekran_dk": ekran_dk}
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}
    adimlar, hatalar = [], []
    kayit = durum_oku()
    if islem == "uygula":
        maskelenecek = [h for h, v in once["uyku"]["hedefler"].items() if v not in ("masked", "yok")]
        if maskelenecek:
            rc, _, hata = calistir(["systemctl", "mask", *maskelenecek])
            if rc != 0:
                hatalar.append("uyku hedefleri maskelenemedi: " + hata.strip()[-200:])
        kayit["maskelenen"] = sorted(set(kayit.get("maskelenen") or []) | set(maskelenecek))
        anahtarlar = oturum_anahtarlari(ekran_dk)
        yaz(DCONF_YEREL, dconf_icerik(anahtarlar))
        yaz(DCONF_YEREL_KILIT, "\n".join(y for y, _ in anahtarlar) + "\n")
        gdm, profil_bizim, gdm_notu = gdm_profili_hazirla()
        if profil_bizim:
            kayit["gdm_profili"] = True
        if gdm_notu:
            adimlar.append(gdm_notu)
        if gdm:
            yaz(DCONF_GDM, dconf_icerik(GUC_ANAHTARLARI))
            yaz(DCONF_GDM_KILIT, "\n".join(y for y, _ in GUC_ANAHTARLARI) + "\n")
        yaz(LOGIND, LOGIND_ICERIK)
        rc, _, hata = calistir(["dconf", "update"])
        if rc != 0:
            hatalar.append("dconf update: " + hata.strip()[-200:])
        kayit["ekran_dk"] = ekran_dk
        kayit["zaman"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        durum_yaz(kayit)
        # doğrulama: geri okuma
        hedefler = hedef_durumlari()
        maskeli = [h for h, v in hedefler.items() if v == "masked"]
        eksik = [h for h, v in hedefler.items() if v not in ("masked", "yok")]
        adimlar.append("uyku/askıya alma hedefleri kapatıldı (%d/%d maskeli)" % (len(maskeli), len(hedefler)))
        if eksik:
            hatalar.append("maskelenemeyen: " + ", ".join(eksik))
        yanlis = [y for y, d in anahtarlar if not ayni(dconf_oku("local", y), d)]
        if yanlis:
            hatalar.append("oturum ayarı geri okunamadı: " + ", ".join(yanlis))
        else:
            adimlar.append("oturum: boşta uyku yok, ekran koruyucu %s (kilitli)"
                           % ("%d dk" % ekran_dk if ekran_dk else "kapalı"))
        if gdm:
            yanlis = [y for y, d in GUC_ANAHTARLARI if not ayni(dconf_oku("gdm", y), d)]
            if yanlis:
                hatalar.append("giriş ekranı ayarı geri okunamadı: " + ", ".join(yanlis))
            else:
                adimlar.append("giriş ekranı (GDM): boşta uyku yok (giriş ekranı yeniden açılınca)")
        adimlar.append("güç tuşu/kapak uyku yapmaz (logind; bir sonraki açılışta tam geçerli)")
    else:  # kaldir
        bizim = [h for h in (kayit.get("maskelenen") or []) if h in UYKU_HEDEFLERI]
        if bizim:
            rc, _, hata = calistir(["systemctl", "unmask", *bizim])
            if rc != 0:
                hatalar.append("maske kaldırılamadı: " + hata.strip()[-200:])
            adimlar.append("uyku hedefleri eski haline döndü: " + ", ".join(bizim))
        degisti = False
        for yol in (DCONF_YEREL, DCONF_YEREL_KILIT, DCONF_GDM, DCONF_GDM_KILIT):
            degisti |= sil(yol)
        if kayit.get("gdm_profili") and (_satirlar(GDM_PROFIL) or [""])[0] == GDM_PROFIL_IMZA:
            sil(GDM_PROFIL)  # yalnız bizim oluşturduğumuz profil; paket kopyası yeniden geçerli olur
            degisti = True
            gdm_d = os.path.dirname(DCONF_GDM)
            for dizin in (os.path.dirname(DCONF_GDM_KILIT), gdm_d):
                try:
                    os.rmdir(dizin)  # yalnız boşsa (başkasının dosyası varsa kalır)
                except OSError:
                    pass
            if not os.path.exists(gdm_d):
                sil(DCONF_GDM_DB)  # derlenmiş veritabanı: kaynağı ve onu okuyan profil kalmadı
        if degisti:
            calistir(["dconf", "update"])
            adimlar.append("GNOME güç ayarları varsayılana döndü")
        if sil(LOGIND):
            adimlar.append("logind ayarı kaldırıldı")
        sil(DURUM_DOSYASI)
        if not adimlar:
            adimlar.append("bu uygulamanın yaptığı bir güç ayarı yoktu")
    return {"islem": islem, "adimlar": adimlar, "hatalar": hatalar, "sonra": durum()}


# ---------------------------------------------------------------- zamanlı kapatma

def takvim_dogrula(takvim):
    """systemd-analyze ile denetler; sonraki tetiklenme zamanını döndürür (None: geçersiz/geçmiş)."""
    if not TAKVIM_DESENI.match(takvim or ""):
        return None, "takvim ifadesi geçersiz"
    rc, cikti, hata = calistir(["systemd-analyze", "calendar", takvim], 15)
    if rc != 0:
        return None, (hata or cikti).strip()[-200:] or "takvim ifadesi geçersiz"
    es = re.search(r"Next elapse:\s*(.+)", cikti)
    if not es or es.group(1).strip().lower() == "never":
        return None, "bu zaman geçmişte kalıyor (bilgisayarın saatine göre)"
    return es.group(1).strip(), None


def birim_icerikleri(p):
    meta = {"id": p["id"], "tur": p["tur"], "uyari_dk": int(p["uyari_dk"]),
            "etiket": p.get("etiket", "")[:60], "aciklama": p.get("aciklama", "")[:80],
            "olusturma": time.strftime("%Y-%m-%dT%H:%M:%S")}
    servis = ("[Unit]\nDescription=Pardus Sinif Yonetimi zamanli kapatma (%s)\n\n"
              "[Service]\nType=oneshot\nExecStart=%s %d %s %s\n"
              % (p["id"], YARDIMCI, meta["uyari_dk"], p["id"], p["tur"]))
    zamanlayici = ("# psy: %s\n[Unit]\nDescription=Pardus Sinif Yonetimi zamanli kapatma (%s)\n\n"
                   "[Timer]\nOnCalendar=%s\nPersistent=false\nAccuracySec=1s\n\n"
                   "[Install]\nWantedBy=timers.target\n"
                   % (json.dumps(meta, ensure_ascii=True), p["id"], p["takvim"]))
    return servis, zamanlayici


def kapatma_ekle(p):
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}
    if not ID_DESENI.match(p.get("id", "")) or p.get("tur") not in ("tek", "surekli"):
        return {"hata": "geçersiz plan"}
    try:
        uyari = int(p.get("uyari_dk", 5))
    except (TypeError, ValueError):
        return {"hata": "geçersiz uyarı süresi"}
    if not 0 <= uyari <= 30:
        return {"hata": "uyarı süresi 0-30 dakika olmalı"}
    sonraki, hata = takvim_dogrula(p.get("takvim"))
    if hata:
        return {"hata": hata}
    yaz(YARDIMCI, YARDIMCI_ICERIK, 0o755)
    servis, zamanlayici = birim_icerikleri({**p, "uyari_dk": uyari})
    ad = ON_EK + p["id"]
    yaz(os.path.join(BIRIM_KOK, ad + ".service"), servis)
    yaz(os.path.join(BIRIM_KOK, ad + ".timer"), zamanlayici)
    calistir(["systemctl", "daemon-reload"])
    rc, _, hata = calistir(["systemctl", "enable", "--now", ad + ".timer"])
    bilgi = plan_bilgisi(os.path.join(BIRIM_KOK, ad + ".timer"))
    if rc != 0 or not bilgi.get("etkin"):
        return {"hata": "zamanlayıcı etkinleşmedi: " + (hata.strip()[-200:] or "durum doğrulanamadı")}
    return {"eklendi": True, "plan": bilgi, "sonraki": bilgi.get("sonraki") or sonraki, "planlar": planlar()}


def kapatma_sil(p):
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}
    idler = p.get("idler")
    mevcut = [b["id"] for b in planlar()]
    hedef = mevcut if idler == "hepsi" else [i for i in (idler or []) if ID_DESENI.match(i)]
    silinen = []
    for i in hedef:
        ad = ON_EK + i
        if i not in mevcut:
            continue
        calistir(["systemctl", "disable", "--now", ad + ".timer"])
        sil(os.path.join(BIRIM_KOK, ad + ".timer"))
        sil(os.path.join(BIRIM_KOK, ad + ".service"))
        silinen.append(i)
    if silinen:
        calistir(["systemctl", "daemon-reload"])
    kalan = planlar()
    if not kalan:
        sil(YARDIMCI)
    else:
        yardimci_guncelle()
    return {"silinen": silinen, "planlar": kalan}


def uyari_bildirimleri():
    """Yardımcının gönderdiği uyarı bildirimlerinin kimlikleri: {kullanıcı: kimlik}."""
    sonuc = {}
    for satir in _satirlar(BEKLEYEN_BILDIRIM) or []:
        parca = satir.split()
        if len(parca) == 2 and parca[1].isdigit():
            sonuc[parca[0]] = parca[1]
    return sonuc


def masaustu_bildir(baslik, govde, simge="dialog-information", yerine=None):
    """Açık grafik oturumlara bildirim (yardımcı betikteki bildir() ile aynı yol). Gönderilen sayısı.
    yerine: {kullanıcı: bildirim kimliği} — o bildirimin yerine geçer (ekrandaki uyarı güncellenir)."""
    import pwd  # yalnız Linux (testler bu modülü Windows'ta da içe aktarır)
    _, cikti, _ = calistir(["loginctl", "list-sessions", "--no-legend"], 15)
    gonderilen = 0
    for satir in cikti.splitlines():
        if not satir.split():
            continue
        _, bilgi, _ = calistir(["loginctl", "show-session", satir.split()[0], "-p", "Type", "-p", "Name"], 15)
        alan = dict(s.split("=", 1) for s in bilgi.splitlines() if "=" in s)
        if alan.get("Type") not in ("x11", "wayland"):
            continue
        try:
            kid = pwd.getpwnam(alan.get("Name", "")).pw_uid
        except KeyError:
            continue
        veri_yolu = "/run/user/%d/bus" % kid
        if not os.path.exists(veri_yolu):
            continue
        on = ["runuser", "-u", alan["Name"], "--", "env", "LC_ALL=C.UTF-8",
              "DBUS_SESSION_BUS_ADDRESS=unix:path=" + veri_yolu]
        if shutil.which("gdbus"):
            argv = on + ["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                         "--object-path", "/org/freedesktop/Notifications",
                         "--method", "org.freedesktop.Notifications.Notify", "Lab Kaptanı",
                         (yerine or {}).get(alan["Name"], "0"), simge,
                         baslik, govde, "[]", "{}", "0"]
        elif shutil.which("notify-send"):
            argv = on + ["notify-send", "-i", simge, baslik, govde]
        else:
            continue
        if calistir(argv, 15)[0] == 0:
            gonderilen += 1
    return gonderilen


def kapatma_iptal(_p):
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}
    yardimci_guncelle()
    bizim, logind, _ = bekleyen_durumu()
    uyarilar = uyari_bildirimleri()
    if bizim:
        calistir(["systemctl", "stop", BEKLEYEN_BIRIM + ".timer"])
        sil(BEKLEYEN_SAAT)
        sil(BEKLEYEN_BILDIRIM)
    if logind:  # elle ya da eski sürümle verilmiş "shutdown +N"
        calistir(["shutdown", "-c", "Zamanli kapatma ogretmen tarafindan iptal edildi."])
        for _ in range(10):
            if not os.path.exists(BEKLEYEN):
                break
            time.sleep(0.3)
    vardi = bizim or logind
    hala = any(bekleyen_durumu()[:2])
    bildirilen = 0
    if vardi and not hala:
        bildirilen = masaustu_bildir("Zamanlı kapatma iptal edildi",
                                     "Bu bilgisayar kapanmayacak. Çalışmaya devam edebilirsiniz.",
                                     yerine=uyarilar)
    return {"bekleyen_vardi": vardi, "iptal_edildi": vardi and not hala, "bekleyen": hala,
            "bildirilen": bildirilen}


def ana():
    try:
        p = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        islev = {"durum": durum, "uyku": uyku, "kapatma_ekle": kapatma_ekle, "kapatma_sil": kapatma_sil,
                 "kapatma_iptal": kapatma_iptal}[p.get("kip", "durum")]
        sonuc = islev(p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
