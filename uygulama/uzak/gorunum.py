"""Uzak betik — ortak görünüm ve giriş ekranı (öğrenci PC'de root).

Kaynaklar HAYALİ DEĞİL, hedef makinenin kendisidir (karar 23):
- Windows 10 benzeri düzen, Pardus Karşılayıcı'nın (pardus-gnome-greeter) kendi
  tanım dosyasındaki "10" düzeninden okunur. Her anahtar, kurulu GSettings
  şemasında var mı ve türü uyuyor mu diye denetlenir; uymayan anahtar yazılmaz,
  raporlanır.
- Tema ve simge teması, makinenin kendi varsayılanlarından (şema + Pardus
  override) okunup sabitlenir.
- Ayarlar dconf sistem veritabanına (/etc/dconf/db/local.d/) varsayılan olarak
  yazılır ve istenirse kilitlenir; öğrencinin kendi ayarı kilitli anahtarı ezemez.

Kipler (argv[1], JSON):
  {"kip": "onizle" | "uygula", "yonetim_hesabi": "pardus", "profil": "ogrenci",
   "secenekler": {"duzen": "uygula"|"kaldir", "duvar": "uygula"|"kaldir",
                  "kilit": true, "ekran_kilidi": "uygula"|"kaldir",
                  "otomatik_giris": "uygula"|"kaldir", "gizle": "uygula"|"kaldir"},
   "duvar_gecici": "/tmp/...", "duvar_uzanti": ".png"}
Çıktı: tek satır JSON {"ogeler": {ad: {"durum", "ayrinti", ...}}, ...}
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

try:
    import pwd
except ImportError:  # Windows test ortamı
    pwd = None

ORTAM = dict(os.environ, LC_ALL="C", LANG="C", GSETTINGS_BACKEND="memory")
KOK = "/var/lib/pardus-sinif-yonetimi"
AYAR_YEDEK = KOK + "/ayar-yedekleri"
KARSILAYICI = "/usr/share/pardus/pardus-gnome-greeter/data/layout_config.json"
DUZEN_ADI = "10"
DB = "/etc/dconf/db/local.d"
# dconf aynı anahtar birden çok dosyadaysa alfabetik olarak SONRAKİ dosyayı kullanır;
# Pardus EDU kendi varsayılanlarını 30-edu-gnome'a yazar. Bizim dosyalarımız onu
# geçmeli: 9x öneki (lab01'de doğrulandı).
DUVAR_DOSYASI = DB + "/91-pardus-sinif-duvar"
DUZEN_DOSYASI = DB + "/92-pardus-sinif-gorunum"
KILIT_DOSYASI = DB + "/93-pardus-sinif-ekran-kilidi"
DUVAR_KILIT = DB + "/locks/pardus-sinif-duvar"
DUZEN_KILIT = DB + "/locks/pardus-sinif-gorunum"
KILIT_KILIT = DB + "/locks/pardus-sinif-ekran-kilidi"
ESKI_DOSYALAR = (DB + "/01-pardus-sinif-duvar", DB + "/02-pardus-sinif-gorunum",
                 DB + "/03-pardus-sinif-ekran-kilidi")  # 0.3.x adları
DUVAR_DIZINI = "/usr/share/backgrounds/pardus-sinif"
GDM_AYAR = "/etc/gdm3/daemon.conf"
AS_DIZINI = "/var/lib/AccountsService/users"
HESAP_DESENI = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

EKRAN_KILIDI = [  # (yol, GVariant metni)
    ("/org/gnome/desktop/screensaver/lock-enabled", "false"),
    ("/org/gnome/desktop/lockdown/disable-lock-screen", "true"),
    ("/org/gnome/desktop/screensaver/ubuntu-lock-on-suspend", "false"),
]


def calistir(argv, zaman=30, ortam=None):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ortam or ORTAM)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as hata:
        return 127, "", str(hata)


# ------------------------------------------------------------------ şema denetimi

_sema_dizini = {}


def _sema_dizini_bul(sema):
    if sema in _sema_dizini:
        return _sema_dizini[sema]
    dizin = False
    if calistir(["gsettings", "list-keys", sema])[0] == 0:
        dizin = None  # sistem şema dizininde
    else:
        for xml in glob.glob("/usr/share/gnome-shell/extensions/*/schemas/%s.gschema.xml" % sema):
            dizin = os.path.dirname(xml)
            break
    _sema_dizini[sema] = dizin
    return dizin


def anahtar_turu(yol):
    """'/org/gnome/x/y/anahtar' -> ('type b' | "enum\\n'A'..." | None, şema)."""
    parca = yol.strip("/").split("/")
    sema, anahtar = ".".join(parca[:-1]), parca[-1]
    dizin = _sema_dizini_bul(sema)
    if dizin is False:
        return None, sema
    argv = ["gsettings"] + (["--schemadir", dizin] if dizin else []) + ["range", sema, anahtar]
    rc, cikti, _ = calistir(argv)
    return (cikti.strip() if rc == 0 else None), sema


def deger_uyar_mi(tur, metin):
    """GVariant metni anahtar türüne uyuyor mu (gi varsa onunla, yoksa temel kurallarla)."""
    if tur.startswith("enum"):
        izinli = [s.strip() for s in tur.splitlines()[1:]]
        return metin in izinli
    kod = tur.split(" ", 1)[1] if tur.startswith("type ") else None
    if kod is None:
        return True  # aralık/bayrak türleri: Karşılayıcı'nın değeri kabul edilir
    try:
        from gi.repository import GLib  # type: ignore
        GLib.Variant.parse(GLib.VariantType.new(kod), metin, None, None)
        return True
    except ImportError:
        pass
    except Exception:
        return False
    if kod == "b":
        return metin in ("true", "false")
    if kod in ("i", "u", "x", "t", "n", "q", "y"):
        return re.fullmatch(r"-?\d+", metin) is not None
    if kod == "d":
        return re.fullmatch(r"-?\d+(\.\d+)?", metin) is not None
    if kod == "s":
        return len(metin) >= 2 and metin[0] == metin[-1] == "'"
    if kod.startswith("a"):
        return metin.startswith("[") or metin.startswith("{") or metin.startswith("@")
    return True


def gv_dize(metin):
    return "'" + metin.replace("\\", "\\\\").replace("'", "\\'") + "'"


def varsayilan(sema, anahtar):
    """Makinenin kendi varsayılanı (şema + dağıtım override'ları; kullanıcı ayarı değil)."""
    rc, cikti, _ = calistir(["gsettings", "get", sema, anahtar])
    return cikti.strip() if rc == 0 else None


# ------------------------------------------------------------------ düzen (Windows 10 benzeri)

# Görev çubuğu / uygulama menüsü / rıhtım işlevi gören bilinen eklentiler. Bilgisayarda
# Karşılayıcı düzeninden farklı bir menü kurulmuş ve etkin olabilir (proje sahibi notu):
# "10" düzeninde bulunmayanlar kapatılır ki iki menü / iki görev çubuğu oluşmasın.
MENU_PANEL_EKLENTILERI = {
    "arcmenu@arcmenu.com": "ArcMenu (uygulama menüsü)",
    "dash-to-panel@jderose9.github.com": "Dash to Panel (görev çubuğu)",
    "dash-to-dock@micxgx.gmail.com": "Dash to Dock (rıhtım)",
    "ubuntu-dock@ubuntu.com": "Ubuntu Dock (rıhtım)",
    "apps-menu@gnome-shell-extensions.gcampax.github.com": "Uygulamalar menüsü (GNOME Klasik)",
    "window-list@gnome-shell-extensions.gcampax.github.com": "Pencere listesi (alt çubuk)",
    "start-overlay-in-application-view@Hex_cz": "Açılışta uygulama görünümü",
    "gnomenu@panacier.gmail.com": "Gno-Menu",
    "zorin-menu@zorinos.com": "Zorin menüsü",
    "tint2-dock": "tint2",
}
SISTEM_EKLENTI_DIZINI = "/usr/share/gnome-shell/extensions"
KARSILAYICI_OTOBASLAT = ".config/autostart/tr.org.pardus.pardus-gnome-greeter.desktop"
KARSILAYICI_ISARET = KOK + "/karsilayici-kapali"  # profil sıfırlama skel'den geri koymasın


def karsilayici_otobaslat(profil, kapat):
    """Karşılayıcı her profilin ilk girişinde /etc/skel'den gelen dosyayla açılır ve
    düzen değiştirmeyi önerir. Düzen merkezden kilitlendiğinde öğrenci girişinde
    açılmaz: dosya kaldırılır ve sıfırlamada geri konmaz (işaret dosyası)."""
    if not kapat:
        try:
            os.unlink(KARSILAYICI_ISARET)
        except FileNotFoundError:
            pass
        return "öğrenci girişinde açılması serbest (sonraki profil sıfırlamada geri gelir)"
    os.makedirs(KOK, mode=0o700, exist_ok=True)
    with open(KARSILAYICI_ISARET, "w") as f:
        f.write("Pardus Sinif Yonetimi: duzen merkezden kilitli\n")
    try:
        ev = os.path.realpath(pwd.getpwnam(profil).pw_dir)
    except KeyError:
        return "kapatıldı (öğrenci hesabı yok)"
    yol = os.path.join(ev, KARSILAYICI_OTOBASLAT)
    if os.path.lexists(yol) and not os.path.islink(yol) \
            and os.path.realpath(yol).startswith(ev + os.sep):
        os.unlink(yol)
        return "öğrenci girişinde açılmayacak (otomatik başlatma kaldırıldı)"
    return "öğrenci girişinde açılmayacak"


def kullanici_dconf_oku(profil, yol):
    """Öğrencinin ETKİN değeri (kendi ayarı + sistem varsayılanı); oturum veri yolu gerekmez."""
    rc, cikti, _ = calistir(["runuser", "-u", profil, "--", "dconf", "read", yol])
    return cikti.strip() if rc == 0 and cikti.strip() else None


def eklenti_durumu(profil):
    """Kurulu ve etkin menü/panel eklentileri; Karşılayıcı'da seçili düzen."""
    kurulu = set(os.listdir(SISTEM_EKLENTI_DIZINI)) if os.path.isdir(SISTEM_EKLENTI_DIZINI) else set()
    try:
        yerel = os.path.join(pwd.getpwnam(profil).pw_dir, ".local/share/gnome-shell/extensions")
        ogrencinin = set(os.listdir(yerel)) if os.path.isdir(yerel) else set()
    except (KeyError, OSError):
        ogrencinin = set()
    etkin_metin = kullanici_dconf_oku(profil, "/org/gnome/shell/enabled-extensions") \
        or varsayilan("org.gnome.shell", "enabled-extensions") or ""
    etkin = re.findall(r"'([^']+)'", etkin_metin)
    duzen = kullanici_dconf_oku(profil, "/org/pardus/pardus-gnome-greeter/layout-name") \
        or varsayilan("org.pardus.pardus-gnome-greeter", "layout-name")
    return {
        "karsilayici_duzeni": duzen.strip("'") if duzen else None,
        "kurulu_menu": sorted(e for e in kurulu | ogrencinin if e in MENU_PANEL_EKLENTILERI),
        "etkin_menu": [e for e in etkin if e in MENU_PANEL_EKLENTILERI],
        "ogrencinin_kurdugu": sorted(ogrencinin),
    }


def duzen_plani(profil="ogrenci"):
    """Karşılayıcı'nın "10" düzeninden (yol -> değer) planı ve atlananları çıkarır."""
    if not os.path.isfile(KARSILAYICI):
        return None, "Pardus Karşılayıcı düzen tanımı yok (%s)" % KARSILAYICI
    with open(KARSILAYICI, encoding="utf-8") as f:
        tanim = json.load(f).get(DUZEN_ADI)
    if not tanim:
        return None, "Karşılayıcı tanımında '%s' düzeni yok" % DUZEN_ADI

    gerekli = tanim.get("enable", [])
    eksik = [e for e in gerekli if not os.path.isdir(os.path.join(SISTEM_EKLENTI_DIZINI, e))]
    durum = eklenti_durumu(profil)
    if eksik:
        return None, ("düzen için gerekli eklenti kurulu değil: %s (bu bilgisayarda kurulu menü/panel "
                      "eklentileri: %s). Eksik paketi M2-S2 ile kurabilirsiniz."
                      % (", ".join(MENU_PANEL_EKLENTILERI.get(e, e) for e in eksik),
                         ", ".join(MENU_PANEL_EKLENTILERI.get(e, e) for e in durum["kurulu_menu"]) or "yok"))

    ayarlar, atlanan = {}, []
    for conf in tanim.get("config", []):
        yol = conf["path"]
        metin = "'%s'" % conf["value"] if conf.get("type") == "string" else str(conf["value"])
        tur, sema = anahtar_turu(yol)
        if tur is None:
            atlanan.append({"anahtar": yol, "neden": "kurulu şemada yok"})
        elif not deger_uyar_mi(tur, metin):
            atlanan.append({"anahtar": yol, "neden": "değer türü uymuyor (%s)" % tur.splitlines()[0]})
        else:
            ayarlar[yol] = metin

    # Eklenti listesi: makinenin kendi varsayılanı + düzenin aç/kapat listesi
    temel = varsayilan("org.gnome.shell", "enabled-extensions") or "@as []"
    etkin = re.findall(r"'([^']+)'", temel)
    for e in tanim.get("enable", []):
        if e not in etkin:
            etkin.append(e)
    kapali = list(tanim.get("disable", []))
    # Düzende olmayan başka bir menü / görev çubuğu / rıhtım kuruluysa kapatılır
    for e in durum["kurulu_menu"] + durum["etkin_menu"]:
        if e not in gerekli and e not in kapali:
            kapali.append(e)
    etkin = [e for e in etkin if e not in kapali]
    ayarlar["/org/gnome/shell/enabled-extensions"] = "[" + ", ".join(gv_dize(e) for e in etkin) + "]"
    ayarlar["/org/gnome/shell/disabled-extensions"] = "[" + ", ".join(gv_dize(e) for e in kapali) + "]"
    ayarlar["/org/gnome/shell/disable-user-extensions"] = "false"
    if anahtar_turu("/org/pardus/pardus-gnome-greeter/layout-name")[0]:
        ayarlar["/org/pardus/pardus-gnome-greeter/layout-name"] = gv_dize(DUZEN_ADI)
    for anahtar in ("gtk-theme", "icon-theme"):
        deger = varsayilan("org.gnome.desktop.interface", anahtar)
        if deger:
            ayarlar["/org/gnome/desktop/interface/" + anahtar] = deger
    return {"ayarlar": ayarlar, "atlanan": atlanan, "eklentiler": etkin, "kapatilacak": kapali,
            "mevcut": durum}, None


def anahtar_dosyasi_yaz(dosya, kilit_dosyasi, ayarlar, kilitle):
    bolumler = {}
    for yol, metin in ayarlar.items():
        klasor, anahtar = yol.strip("/").rsplit("/", 1)
        bolumler.setdefault(klasor, []).append("%s=%s" % (anahtar, metin))
    govde = "# Pardus Sınıf Yönetimi tarafından yazıldı; elle değiştirmeyin.\n"
    for klasor, satirlar in bolumler.items():
        govde += "\n[%s]\n%s\n" % (klasor, "\n".join(satirlar))
    os.makedirs(DB + "/locks", exist_ok=True)
    _atomik_yaz(dosya, govde, 0o644)
    if kilitle:
        _atomik_yaz(kilit_dosyasi, "".join(yol + "\n" for yol in ayarlar), 0o644)
    else:
        _sil(kilit_dosyasi)


def _atomik_yaz(yol, icerik, izin):
    gecici = yol + ".psy-yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(icerik)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(gecici, izin)
    os.replace(gecici, yol)


def _sil(yol):
    try:
        os.unlink(yol)
        return True
    except FileNotFoundError:
        return False


def dconf_profili_hazirla():
    os.makedirs("/etc/dconf/profile", exist_ok=True)
    yol = "/etc/dconf/profile/user"
    mevcut = ""
    if os.path.exists(yol):
        with open(yol, encoding="utf-8") as f:
            mevcut = f.read()
    if "system-db:local" not in mevcut:
        _atomik_yaz(yol, "user-db:user\nsystem-db:local\n" if not mevcut.strip()
                    else mevcut.rstrip() + "\nsystem-db:local\n", 0o644)


def dconf_guncelle():
    rc, _, hata = calistir(["dconf", "update"])
    return None if rc == 0 else "dconf update başarısız: " + hata.strip()[-200:]


def sistem_db_oku(yol):
    """Derlenmiş sistem veritabanından okur (kullanıcı ayarı karışmaz)."""
    fd, profil = tempfile.mkstemp(prefix="psy-dconf-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write("system-db:local\n")
        rc, cikti, _ = calistir(["dconf", "read", yol], ortam=dict(ORTAM, DCONF_PROFILE=profil))
        return cikti.strip() if rc == 0 else None
    finally:
        os.unlink(profil)


def ayni_deger(a, b):
    a, b = a.replace(" ", ""), b.replace(" ", "")
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9  # dconf ondalığı 0.84999999999999998 diye yazar
    except ValueError:
        return False


def _dogrula(ayarlar, ornek_sayisi=3):
    """Yazılan anahtarları derlenmiş sistem veritabanından okuyup karşılaştırır."""
    uyusmayan = []
    for yol in list(ayarlar)[:ornek_sayisi]:
        okunan = sistem_db_oku(yol)
        if okunan is None or not ayni_deger(okunan, ayarlar[yol]):
            uyusmayan.append(yol)
    return uyusmayan


# ------------------------------------------------------------------ GDM ve AccountsService

def ini_oku(yol):
    sonuc, bolum = {}, None
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            for satir in f:
                satir = satir.strip()
                if not satir or satir[0] in "#;":
                    continue
                if satir.startswith("[") and satir.endswith("]"):
                    bolum = satir[1:-1].strip()
                    sonuc.setdefault(bolum, {})
                elif "=" in satir and bolum is not None:
                    ad, deger = satir.split("=", 1)
                    sonuc[bolum][ad.strip()] = deger.strip()
    except OSError:
        return None
    return sonuc


def ini_ayarla(metin, bolum, degerler):
    """INI metninde bir bölümdeki anahtarları ayarlar/siler (değer None = sil).

    Yorumlar ve diğer satırlar korunur; bölüm yoksa sona eklenir.
    """
    satirlar = metin.splitlines()
    cikti, icinde, eklendi = [], False, False
    for satir in satirlar:
        kirp = satir.strip()
        if kirp.startswith("[") and kirp.endswith("]"):
            if icinde and not eklendi:
                cikti += ["%s=%s" % (a, d) for a, d in degerler.items() if d is not None]
                eklendi = True
            icinde = kirp[1:-1].strip() == bolum
            cikti.append(satir)
            if icinde:
                cikti += ["%s=%s" % (a, d) for a, d in degerler.items() if d is not None]
                eklendi = True
            continue
        if icinde and "=" in kirp and not kirp.startswith(("#", ";")) \
                and kirp.split("=", 1)[0].strip() in degerler:
            continue  # eski değer atılır (yenisi bölüm başına yazıldı)
        cikti.append(satir)
    if not eklendi:
        yeni = ["%s=%s" % (a, d) for a, d in degerler.items() if d is not None]
        if yeni:
            cikti += ["", "[%s]" % bolum] + yeni
    return "\n".join(cikti) + "\n"


def ayar_yedekle(yol):
    """Değiştirilen sistem dosyasının ilk hâlini bir kez saklar."""
    if not os.path.exists(yol):
        return None
    os.makedirs(AYAR_YEDEK, mode=0o700, exist_ok=True)
    hedef = os.path.join(AYAR_YEDEK, os.path.basename(yol) + ".ilk")
    if not os.path.exists(hedef):
        with open(yol, "rb") as kaynak, open(hedef, "wb") as f:
            f.write(kaynak.read())
        os.chmod(hedef, 0o600)
    return hedef


def otomatik_giris_durumu():
    daemon = (ini_oku(GDM_AYAR) or {}).get("daemon", {})
    etkin = daemon.get("AutomaticLoginEnable", "").lower() == "true"
    return {"etkin": etkin, "hesap": daemon.get("AutomaticLogin") if etkin else None}


def otomatik_giris_yaz(profil, ac):
    metin = ""
    if os.path.exists(GDM_AYAR):
        with open(GDM_AYAR, encoding="utf-8") as f:
            metin = f.read()
    ayar_yedekle(GDM_AYAR)
    degerler = ({"AutomaticLoginEnable": "true", "AutomaticLogin": profil} if ac
                else {"AutomaticLoginEnable": "false", "AutomaticLogin": None})
    os.makedirs(os.path.dirname(GDM_AYAR), exist_ok=True)
    _atomik_yaz(GDM_AYAR, ini_ayarla(metin, "daemon", degerler), 0o644)


def _busctl(*argv):
    rc, cikti, _ = calistir(["busctl", "--json=short", "call", "org.freedesktop.Accounts",
                             "/org/freedesktop/Accounts", "org.freedesktop.Accounts"] + list(argv))
    if rc != 0:
        return None
    try:
        return json.loads(cikti)["data"]
    except (ValueError, KeyError):
        return None


def listede_mi(hesap):
    """AccountsService'in giriş ekranına verdiği kullanıcı listesinde mi? (None: bilinmiyor)"""
    liste = _busctl("ListCachedUsers")
    yol = _busctl("FindUserByName", "s", hesap)
    if liste is None or yol is None:
        return None
    return yol[0] in set(liste[0])


def gizleme_durumu(hesap):
    kullanici = (ini_oku(os.path.join(AS_DIZINI, hesap)) or {}).get("User", {})
    return {"sistem_hesabi": kullanici.get("SystemAccount", "").lower() == "true",
            "listede": listede_mi(hesap)}


def gizleme_yaz(hesap, gizle):
    yol = os.path.join(AS_DIZINI, hesap)
    metin = ""
    if os.path.isfile(yol) and not os.path.islink(yol):
        with open(yol, encoding="utf-8", errors="replace") as f:
            metin = f.read()
    os.makedirs(AS_DIZINI, mode=0o700, exist_ok=True)
    _atomik_yaz(yol, ini_ayarla(metin, "User", {"SystemAccount": "true" if gizle else "false"}), 0o600)
    # accounts-daemon kullanıcı dosyalarını açılışta okur; listeyi tazelemek için
    # yeniden başlatılır (açık masaüstü oturumu kapanmaz).
    listede = listede_mi(hesap)
    if listede is not None and listede == gizle:
        calistir(["systemctl", "try-restart", "accounts-daemon.service"])
        for _ in range(10):
            time.sleep(0.5)
            listede = listede_mi(hesap)
            if listede is not None:
                break
    return listede


# ------------------------------------------------------------------ ana akış

def ortam_bilgisi(profil):
    gnome = os.access("/usr/bin/gnome-shell", os.X_OK)
    xfce = os.access("/usr/bin/xfce4-session", os.X_OK)
    dm_yolu = "/etc/systemd/system/display-manager.service"
    dm = None
    if os.path.exists(dm_yolu):
        dm = os.path.basename(os.path.realpath(dm_yolu)).replace(".service", "")
        dm = "gdm3" if dm in ("gdm", "gdm3") else dm
    rc, cikti, _ = calistir(["loginctl", "list-sessions", "--no-legend"])
    oturum = rc == 0 and any(len(s.split()) >= 3 and s.split()[2] == profil for s in cikti.splitlines())
    return {"masaustu": "GNOME" if gnome else ("XFCE" if xfce else None),
            "giris_yoneticisi": dm, "ogrenci_oturumu": oturum}


def calistir_betik(p):
    kip = p["kip"]
    uygula = kip == "uygula"
    s = p.get("secenekler", {})
    kilitle = bool(s.get("kilit", True))
    profil = p.get("profil", "ogrenci")
    yonetim = p.get("yonetim_hesabi", "")
    if not HESAP_DESENI.match(profil) or not HESAP_DESENI.match(yonetim or "x"):
        return {"hata": "geçersiz hesap adı"}
    ortam = ortam_bilgisi(profil)
    gnome = ortam["masaustu"] == "GNOME"
    gdm = ortam["giris_yoneticisi"] == "gdm3"
    ogeler = {}
    dconf_degisti = False
    dogrulanacak = {}  # öğe -> {yol: değer}

    def desteklenmiyor_masaustu():
        if ortam["masaustu"] == "XFCE":
            return "XFCE: GNOME geçişi ayrı plan ve onay gerektirir; görünüm uygulanmadı"
        return "masaüstü GNOME değil (%s)" % (ortam["masaustu"] or "bilinmiyor")

    if uygula and gnome and any(s.get(k) for k in ("duzen", "duvar", "ekran_kilidi")):
        dconf_profili_hazirla()
        for eski in ESKI_DOSYALAR:  # eski önekli dosyalar EDU varsayılanlarına yeniliyordu
            if os.path.exists(eski):
                if eski.endswith("duvar") and not os.path.exists(DUVAR_DOSYASI):
                    os.replace(eski, DUVAR_DOSYASI)
                else:
                    os.unlink(eski)
                dconf_degisti = True

    # --- Windows 10 benzeri düzen
    if s.get("duzen"):
        if not gnome:
            ogeler["duzen"] = {"durum": "desteklenmiyor", "ayrinti": desteklenmiyor_masaustu()}
        elif s["duzen"] == "kaldir":
            if uygula:
                degisti = _sil(DUZEN_DOSYASI) | _sil(DUZEN_KILIT)
                dconf_degisti |= degisti
                ogeler["duzen"] = {"durum": "kaldirildi" if degisti else "zaten_yok",
                                   "karsilayici": karsilayici_otobaslat(profil, False)}
            else:
                ogeler["duzen"] = {"durum": "kaldirilacak" if os.path.exists(DUZEN_DOSYASI) else "zaten_yok"}
        else:
            plan, hata = duzen_plani(profil)
            if plan is None:
                ogeler["duzen"] = {"durum": "desteklenmiyor", "ayrinti": hata}
            else:
                mevcut = plan["mevcut"]
                farkli = [MENU_PANEL_EKLENTILERI[e] for e in mevcut["etkin_menu"]
                          if e in plan["kapatilacak"]]
                oge = {"durum": "uygulanacak", "anahtar_sayisi": len(plan["ayarlar"]),
                       "atlanan": plan["atlanan"], "eklentiler": plan["eklentiler"],
                       "mevcut": mevcut, "kapatilacak_menu": farkli,
                       "ayrinti": ("Karşılayıcı'da seçili düzen: %s; şu an etkin menü/panel: %s%s"
                                   % (mevcut["karsilayici_duzeni"] or "bilinmiyor",
                                      ", ".join(MENU_PANEL_EKLENTILERI[e] for e in mevcut["etkin_menu"]) or "yok",
                                      ("; kapatılacak farklı menü: " + ", ".join(farkli)) if farkli else "")),
                       "kaynak": "%s → \"%s\" düzeni" % (KARSILAYICI, DUZEN_ADI), "kilit": kilitle}
                oge["karsilayici"] = ("öğrenci girişinde açılmayacak" if kilitle
                                      else "öğrenci girişinde açılabilir (kilit yok)")
                if uygula:
                    anahtar_dosyasi_yaz(DUZEN_DOSYASI, DUZEN_KILIT, plan["ayarlar"], kilitle)
                    dconf_degisti = True
                    dogrulanacak["duzen"] = plan["ayarlar"]
                    oge["karsilayici"] = karsilayici_otobaslat(profil, kilitle)
                    oge["durum"] = "uygulandi"
                ogeler["duzen"] = oge

    # --- ekran kilidi kapalı
    if s.get("ekran_kilidi"):
        if not gnome:
            ogeler["ekran_kilidi"] = {"durum": "desteklenmiyor", "ayrinti": desteklenmiyor_masaustu()}
        elif s["ekran_kilidi"] == "kaldir":
            degisti = uygula and (_sil(KILIT_DOSYASI) | _sil(KILIT_KILIT))
            dconf_degisti |= bool(degisti)
            ogeler["ekran_kilidi"] = {"durum": ("kaldirildi" if degisti else "zaten_yok") if uygula
                                      else "kaldirilacak"}
        else:
            gecerli, atlanan = {}, []
            for yol, metin in EKRAN_KILIDI:
                tur, _ = anahtar_turu(yol)
                if tur and deger_uyar_mi(tur, metin):
                    gecerli[yol] = metin
                else:
                    atlanan.append({"anahtar": yol, "neden": "kurulu şemada yok"})
            oge = {"durum": "uygulanacak", "anahtarlar": list(gecerli), "atlanan": atlanan}
            if uygula:
                anahtar_dosyasi_yaz(KILIT_DOSYASI, KILIT_KILIT, gecerli, True)
                dconf_degisti = True
                dogrulanacak["ekran_kilidi"] = gecerli
                oge["durum"] = "uygulandi"
            ogeler["ekran_kilidi"] = oge

    # --- standart duvar kâğıdı
    if s.get("duvar"):
        if not gnome:
            ogeler["duvar"] = {"durum": "desteklenmiyor", "ayrinti": desteklenmiyor_masaustu()}
        elif s["duvar"] == "kaldir":
            degisti = uygula and (_sil(DUVAR_DOSYASI) | _sil(DUVAR_KILIT))
            dconf_degisti |= bool(degisti)
            ogeler["duvar"] = {"durum": ("kaldirildi" if degisti else "zaten_yok") if uygula
                               else "kaldirilacak"}
        else:
            kose = p.get("duvar_kose") or s.get("duvar_kose") or "sag_ust"
            numara, tam_host = hostname_numarasi_cikar(p.get("cihaz_hostname") or "", p.get("cihaz_etiket") or "")
            kose_metin = {"sag_ust": "sağ üst", "sol_ust": "sol üst"}.get(kose)
            oge = {
                "durum": "uygulanacak",
                "kilit": kilitle,
                "ayrinti": (f"köşede '{numara}' ({tam_host}, {kose_metin}) yazılacak"
                            if kose_metin else "köşe etiketi yok"),
            }
            if uygula:
                hata, ayarlar, etiket_bilgi = _duvar_uygula(
                    p.get("duvar_gecici", ""), p.get("duvar_uzanti", ""), kilitle,
                    kose=kose, numara=numara, tam_host=tam_host
                )
                if hata:
                    oge = {"durum": "hata", "ayrinti": hata}
                else:
                    dconf_degisti = True
                    dogrulanacak["duvar"] = ayarlar
                    oge["durum"] = "uygulandi"
                    if etiket_bilgi:
                        oge["ayrinti"] = etiket_bilgi
            ogeler["duvar"] = oge

    if uygula and dconf_degisti:
        hata = dconf_guncelle()
        if hata:
            for ad in ("duzen", "ekran_kilidi", "duvar"):
                if ogeler.get(ad, {}).get("durum") == "uygulandi":
                    ogeler[ad] = {"durum": "hata", "ayrinti": hata}
        else:
            for ad, ayarlar in dogrulanacak.items():
                uyusmayan = _dogrula(ayarlar, len(ayarlar))
                if not uyusmayan:
                    ogeler[ad]["dogrulama"] = ("derlenmiş sistem veritabanından okundu; %d anahtar "
                                               "yazılanla aynı" % len(ayarlar))
                else:
                    ogeler[ad]["durum"] = "hata"
                    ogeler[ad]["dogrulama"] = ("yazıldı ama başka bir dconf dosyası şu anahtarları "
                                               "eziyor: " + ", ".join(uyusmayan))

    # --- öğrenci otomatik girişi
    if s.get("otomatik_giris"):
        mevcut = otomatik_giris_durumu() if gdm else None
        if not gdm:
            ogeler["otomatik_giris"] = {"durum": "desteklenmiyor",
                                        "ayrinti": "giriş yöneticisi %s; yalnız GDM destekleniyor"
                                                   % (ortam["giris_yoneticisi"] or "bilinmiyor")}
        else:
            ac = s["otomatik_giris"] == "uygula"
            try:
                pwd.getpwnam(profil)
                hesap_var = True
            except KeyError:
                hesap_var = False
            if ac and not hesap_var:
                ogeler["otomatik_giris"] = {"durum": "hata", "ayrinti": "'%s' hesabı yok" % profil}
            elif (ac and mevcut["etkin"] and mevcut["hesap"] == profil) or (not ac and not mevcut["etkin"]):
                ogeler["otomatik_giris"] = {"durum": "zaten", "mevcut": mevcut}
            else:
                oge = {"durum": "uygulanacak" if ac else "kaldirilacak", "mevcut": mevcut}
                if uygula:
                    otomatik_giris_yaz(profil, ac)
                    yeni = otomatik_giris_durumu()
                    dogru = yeni["etkin"] == ac and (not ac or yeni["hesap"] == profil)
                    oge = {"durum": "uygulandi" if dogru else "hata", "mevcut": yeni,
                           "dogrulama": "GDM ayar dosyası yeniden okundu; bir sonraki açılışta "
                                        "veya giriş ekranı yeniden başladığında etkinleşir"}
                ogeler["otomatik_giris"] = oge

    # --- yönetim hesabını giriş ekranında gizle
    if s.get("gizle"):
        try:
            pwd.getpwnam(yonetim)
            var = True
        except KeyError:
            var = False
        if not gdm:
            ogeler["gizle"] = {"durum": "desteklenmiyor",
                               "ayrinti": "giriş yöneticisi %s; yalnız GDM destekleniyor"
                                          % (ortam["giris_yoneticisi"] or "bilinmiyor")}
        elif not var:
            ogeler["gizle"] = {"durum": "hata", "ayrinti": "'%s' hesabı yok" % yonetim}
        else:
            gizle = s["gizle"] == "uygula"
            mevcut = gizleme_durumu(yonetim)
            if mevcut["sistem_hesabi"] == gizle and mevcut["listede"] is not None \
                    and mevcut["listede"] != gizle:
                ogeler["gizle"] = {"durum": "zaten", "mevcut": mevcut}
            else:
                oge = {"durum": "uygulanacak" if gizle else "kaldirilacak", "mevcut": mevcut,
                       "yontem": "AccountsService SystemAccount=%s (%s/%s)"
                                 % ("true" if gizle else "false", AS_DIZINI, yonetim)}
                if uygula:
                    listede = gizleme_yaz(yonetim, gizle)
                    son = gizleme_durumu(yonetim)
                    if listede is None:
                        oge.update(durum="uygulandi", mevcut=son,
                                   dogrulama="ayar yazıldı; AccountsService listesi okunamadı — doğrulanmadı")
                    elif listede != gizle:
                        oge.update(durum="uygulandi", mevcut=son,
                                   dogrulama=("AccountsService listesinde yok" if gizle else
                                              "AccountsService listesinde") +
                                             "; gerçek giriş ekranında görsel doğrulama yapılmadı")
                    else:
                        oge.update(durum="hata", mevcut=son,
                                   dogrulama="ayar yazıldı ama liste değişmedi")
                ogeler["gizle"] = oge

    return {"ortam": ortam, "ogeler": ogeler}


def hostname_numarasi_cikar(cihaz_hostname="", cihaz_etiket=""):
    sistem_ad = ""
    try:
        sistem_ad = os.uname().nodename
    except AttributeError:
        pass
    tam_host = (cihaz_hostname or "").strip() or (sistem_ad or "").strip() or (cihaz_etiket or "").strip() or "PC"
    rakamlar = re.findall(r"\d+", tam_host) or re.findall(r"\d+", cihaz_etiket or "")
    numara = (rakamlar[-1].zfill(2) if len(rakamlar[-1]) == 1 else rakamlar[-1]) if rakamlar else tam_host.upper()[:8]
    return numara, tam_host


def _yuvarlak_kutu(ctx, x, y, w, h, r):
    import math
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _duvar_kose_etiketi_yaz(kaynak_yol, hedef_png_yol, numara, tam_host, kose):
    """Pardus GNOME'da kurulu GdkPixbuf+Cairo (veya PIL yedek) ile duvar kağıdının sağ/sol üst köşesine
    uzaktan okunabilir estetik bilgisayar numarası ve hostname rozeti işler."""
    if kose not in ("sag_ust", "sol_ust"):
        return False
    # 1. Yöntem: GdkPixbuf + Cairo (GNOME masaüstünde yerleşik)
    try:
        import cairo
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, GdkPixbuf

        pixbuf = GdkPixbuf.Pixbuf.new_from_file(kaynak_yol)
        w, h = pixbuf.get_width(), pixbuf.get_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        ctx = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
        ctx.paint()

        no_boy = max(42, int(h * 0.088))
        alt_boy = max(14, int(h * 0.022))

        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(no_boy)
        xb, yb, no_w, no_h, _, _ = ctx.text_extents(numara)

        ctx.set_font_size(alt_boy)
        xb2, yb2, alt_w, alt_h, _, _ = ctx.text_extents(tam_host)

        pad_x = max(24, int(w * 0.018))
        pad_y = max(16, int(h * 0.016))
        ic_bosluk = max(8, int(h * 0.010))
        kutu_w = int(max(no_w, alt_w) + pad_x * 2)
        kutu_h = int(no_h + alt_h + pad_y * 2 + ic_bosluk)

        kenar_x = max(28, int(w * 0.032))
        kenar_y = max(42, int(h * 0.055))  # GNOME üst panelin altında kalması için güvenli boşluk
        kutu_x = (w - kutu_w - kenar_x) if kose == "sag_ust" else kenar_x
        kutu_y = kenar_y
        yaricap = max(14, int(min(kutu_w, kutu_h) * 0.18))

        # Gölge
        _yuvarlak_kutu(ctx, kutu_x + 4, kutu_y + 6, kutu_w, kutu_h, yaricap)
        ctx.set_source_rgba(0, 0, 0, 0.45)
        ctx.fill()

        # Koyu lacivert yarı saydam zemin (#0F172A)
        _yuvarlak_kutu(ctx, kutu_x, kutu_y, kutu_w, kutu_h, yaricap)
        ctx.set_source_rgba(15 / 255.0, 23 / 255.0, 42 / 255.0, 0.88)
        ctx.fill_preserve()

        # Parlak gök mavisi çerçeve (#38BDF8)
        ctx.set_line_width(max(2.5, h * 0.003))
        ctx.set_source_rgba(56 / 255.0, 189 / 255.0, 248 / 255.0, 0.95)
        ctx.stroke()

        # Büyük numara metni
        ctx.set_font_size(no_boy)
        ctx.set_source_rgba(56 / 255.0, 189 / 255.0, 248 / 255.0, 1.0)
        no_x = kutu_x + (kutu_w - no_w) / 2 - xb
        no_y = kutu_y + pad_y - yb
        ctx.move_to(no_x, no_y)
        ctx.show_text(numara)

        # Altında hostname metni
        ctx.set_font_size(alt_boy)
        ctx.set_source_rgba(226 / 255.0, 232 / 255.0, 240 / 255.0, 0.95)
        alt_x = kutu_x + (kutu_w - alt_w) / 2 - xb2
        alt_y = kutu_y + pad_y + no_h + ic_bosluk - yb2
        ctx.move_to(alt_x, alt_y)
        ctx.show_text(tam_host)

        surface.write_to_png(hedef_png_yol)
        return os.path.isfile(hedef_png_yol)
    except Exception:
        pass

    # 2. Yedek Yöntem: PIL / Pillow
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.open(kaynak_yol).convert("RGBA")
        w, h = im.size
        katman = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ciz = ImageDraw.Draw(katman)
        no_boy = max(42, int(h * 0.085))
        alt_boy = max(14, int(h * 0.022))
        try:
            f_no = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", no_boy)
            f_alt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", alt_boy)
        except Exception:
            f_no = ImageFont.load_default()
            f_alt = ImageFont.load_default()
        b_no = ciz.textbbox((0, 0), numara, font=f_no)
        b_alt = ciz.textbbox((0, 0), tam_host, font=f_alt)
        no_w, no_h = b_no[2] - b_no[0], b_no[3] - b_no[1]
        alt_w, alt_h = b_alt[2] - b_alt[0], b_alt[3] - b_alt[1]
        pad_x, pad_y = max(24, int(w * 0.018)), max(16, int(h * 0.016))
        kutu_w = max(no_w, alt_w) + pad_x * 2
        kutu_h = no_h + alt_h + pad_y * 2 + 10
        kenar_x, kenar_y = max(28, int(w * 0.032)), max(42, int(h * 0.055))
        x0 = (w - kutu_w - kenar_x) if kose == "sag_ust" else kenar_x
        y0 = kenar_y
        ciz.rounded_rectangle([x0, y0, x0 + kutu_w, y0 + kutu_h], radius=18,
                              fill=(15, 23, 42, 225), outline=(56, 189, 248, 245), width=3)
        ciz.text((x0 + (kutu_w - no_w) // 2, y0 + pad_y - b_no[1]), numara, font=f_no, fill=(56, 189, 248, 255))
        ciz.text((x0 + (kutu_w - alt_w) // 2, y0 + pad_y + no_h + 10 - b_alt[1]), tam_host, font=f_alt, fill=(226, 232, 240, 245))
        sonuc = Image.alpha_composite(im, katman).convert("RGB")
        sonuc.save(hedef_png_yol, "PNG")
        return os.path.isfile(hedef_png_yol)
    except Exception:
        return False


def _duvar_uygula(gecici, uzanti, kilitle, kose="sag_ust", numara="", tam_host=""):
    if uzanti not in (".png", ".jpg", ".jpeg"):
        return "geçersiz görsel uzantısı", None, None
    if not gecici.startswith("/tmp/") or not os.path.isfile(gecici) or os.path.islink(gecici):
        return "yüklenen görsel bulunamadı", None, None
    if os.path.getsize(gecici) > 20 * 1048576:
        return "görsel 20 MB sınırını aşıyor", None, None
    with open(gecici, "rb") as f:
        bas = f.read(8)
    if not (bas.startswith(b"\x89PNG") or bas.startswith(b"\xff\xd8\xff")):
        return "yalnızca PNG veya JPEG kabul edilir", None, None
    os.makedirs(DUVAR_DIZINI, mode=0o755, exist_ok=True)
    for eski in glob.glob(DUVAR_DIZINI + "/duvar.*"):
        os.unlink(eski)
    if not numara or not tam_host:
        numara, tam_host = hostname_numarasi_cikar()
    etiket_bilgi = None
    hedef_png = os.path.join(DUVAR_DIZINI, "duvar.png")
    if kose in ("sag_ust", "sol_ust") and _duvar_kose_etiketi_yaz(gecici, hedef_png + ".yeni", numara, tam_host, kose):
        os.chmod(hedef_png + ".yeni", 0o644)
        os.replace(hedef_png + ".yeni", hedef_png)
        hedef = hedef_png
        kose_ad = "sağ üst" if kose == "sag_ust" else "sol üst"
        etiket_bilgi = f"köşe numarası işlendi: '{numara}' ({tam_host}, {kose_ad})"
    else:
        hedef = os.path.join(DUVAR_DIZINI, "duvar" + uzanti)
        with open(gecici, "rb") as kaynak, open(hedef + ".yeni", "wb") as f:
            f.write(kaynak.read())
        os.chmod(hedef + ".yeni", 0o644)
        os.replace(hedef + ".yeni", hedef)
        if kose == "yok":
            etiket_bilgi = "köşe etiketsiz uygulandı"
    os.unlink(gecici)
    if os.path.basename(os.path.dirname(gecici)).startswith("psy-duvar-"):
        try:
            os.rmdir(os.path.dirname(gecici))
        except OSError:
            pass
    ayarlar = {
        "/org/gnome/desktop/background/picture-uri": gv_dize("file://" + hedef),
        "/org/gnome/desktop/background/picture-uri-dark": gv_dize("file://" + hedef),
        "/org/gnome/desktop/background/picture-options": "'zoom'",
    }
    anahtar_dosyasi_yaz(DUVAR_DOSYASI, DUVAR_KILIT, ayarlar, kilitle)
    return None, ayarlar, etiket_bilgi


def ana():
    try:
        p = json.loads(sys.argv[1])
        if os.geteuid() != 0:
            sonuc = {"hata": "root yetkisi gerekli"}
        else:
            sonuc = calistir_betik(p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
