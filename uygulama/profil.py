"""Kullanıcı yedekleme, öğrenci oturumunu kapatma ve profil sıfırlama.

Akış (istem §9): oturum uyarısı -> (seçilirse) oturum kapatma + kapanma
doğrulaması -> doğrulanmış yedek -> profil sıfırlama -> /etc/skel'den standart
başlangıç dosyaları. Yedekler öğrenci PC'de /var/lib/pardus-sinif-yonetimi/yedek/
altındadır (karar 13, 18); yerel yedek disk arızasına karşı koruma sağlamaz.
Yedeği alan, ölçen, listeleyen ve geri yükleyen uzak betik uzak/yedek.py'dir.

Sıfırlama kapsamı (karar 26):
- "ayarlar": ev dizinindeki gizli girdiler (tarayıcı verileri DAHİL); Belgeler,
  Masaüstü ve diğer görünür klasörler korunur.
- "tam": ev dizininin TAMAMI (Belgeler, Masaüstü, İndirilenler ve tarayıcı
  verileri dahil).
Günlük işlerde sudo parolası sorulmaz (karar 22).
"""

import asyncio

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

KAPSAMLAR = {
    "ayarlar": "Profil ayarları (gizli dosyalar; tarayıcı verileri DAHİL, Belgeler ve "
               "görünür klasörler korunur)",
    "tam": "Ev dizininin TAMAMI (Belgeler, Masaüstü, İndirilenler ve tarayıcı verileri DAHİL)",
}

# ---- uzak betikler (root ile çalışır; JSON tek satır döndürür) ----

_OTURUM_KAPAT_BETIGI = r'''
import json, os, pwd, subprocess, sys, time

p = json.loads(sys.argv[1])
hesap = p["hesap"]
KORUNAN = {"root"} | {x.pw_name for x in pwd.getpwall() if x.pw_uid < 1000}
if hesap in KORUNAN or hesap == p.get("baglanti_hesabi") or hesap in ("pardus", "hp"):
    print(json.dumps({"hata": f"'{hesap}' oturumu bu işlemle kapatılamaz (istem §9.10)"}))
    sys.exit(0)
try:
    uid = pwd.getpwnam(hesap).pw_uid
except KeyError:
    print(json.dumps({"hata": f"'{hesap}' hesabı yok"})); sys.exit(0)

def aktif():
    ls = subprocess.run(["loginctl", "list-sessions", "--no-legend"],
                        capture_output=True, text=True).stdout
    oturum_var = any(len(s.split()) >= 3 and s.split()[2] == hesap for s in ls.splitlines())
    proses = subprocess.run(["pgrep", "-u", hesap], capture_output=True).returncode == 0
    return oturum_var, proses

oturum_var, proses = aktif()
if not oturum_var and not proses:
    print(json.dumps({"durum": "zaten_kapali"})); sys.exit(0)

subprocess.run(["loginctl", "terminate-user", hesap], capture_output=True)
kapandi = False
for _ in range(15):
    time.sleep(1)
    oturum_var, proses = aktif()
    if not oturum_var and not proses:
        kapandi = True; break
if not kapandi and proses:
    subprocess.run(["pkill", "-KILL", "-u", hesap], capture_output=True)
    time.sleep(2)
    oturum_var, proses = aktif()
    kapandi = not oturum_var and not proses

# kullanıcı mount'ları (gvfs vb.) sonlanmış mı (istem §9.9)
kalan_mount = os.path.ismount(f"/run/user/{uid}")
print(json.dumps({"durum": "kapandi" if kapandi else "kapatilamadi",
                  "kalan_mount": kalan_mount}))
'''

_SIFIRLA_BETIGI = r'''
import hashlib, json, os, pwd, shutil, subprocess, sys

p = json.loads(sys.argv[1])
hesap, arsiv, ozet, kapsam = p["hesap"], p["arsiv"], p["sha256"], p.get("kapsam", "ayarlar")
if kapsam not in ("ayarlar", "tam"):
    print(json.dumps({"hata": "bilinmeyen kapsam"})); sys.exit(0)
try:
    kayit = pwd.getpwnam(hesap)
except KeyError:
    print(json.dumps({"hata": f"'{hesap}' hesabı yok"})); sys.exit(0)
ev = os.path.realpath(kayit.pw_dir)
if not os.path.isdir(ev) or ev in ("/", "/home", "/root"):
    print(json.dumps({"hata": f"güvensiz ev dizini: {ev}"})); sys.exit(0)

# son güvenlik kontrolleri: oturum/proses kalmadığından emin ol (istem §9.9)
ls = subprocess.run(["loginctl", "list-sessions", "--no-legend"],
                    capture_output=True, text=True).stdout
if any(len(s.split()) >= 3 and s.split()[2] == hesap for s in ls.splitlines()) or \
   subprocess.run(["pgrep", "-u", hesap], capture_output=True).returncode == 0:
    print(json.dumps({"hata": "hesap hâlâ aktif; sıfırlama yapılmadı"})); sys.exit(0)

# doğrulanmış yedek zorunlu (istem §9.11): arşiv var mı ve sha256 tutuyor mu
if not os.path.isfile(arsiv):
    print(json.dumps({"hata": "yedek arşivi bulunamadı; sıfırlama yapılmadı"})); sys.exit(0)
sha = hashlib.sha256()
with open(arsiv, "rb") as f:
    for parca in iter(lambda: f.read(1048576), b""):
        sha.update(parca)
if sha.hexdigest() != ozet:
    print(json.dumps({"hata": "yedek sağlaması tutmuyor; sıfırlama yapılmadı"})); sys.exit(0)

def bos():
    sv = os.statvfs(ev)
    return sv.f_bavail * sv.f_frsize

bos_once = bos()
ev_dev = os.stat(ev).st_dev
silinen = hatali = 0
for girdi in list(os.scandir(ev)):
    if kapsam == "ayarlar" and not girdi.name.startswith("."):
        continue
    try:
        if girdi.is_dir(follow_symlinks=False):
            if os.stat(girdi.path, follow_symlinks=False).st_dev != ev_dev:
                hatali += 1  # bağlama noktası: dokunulmaz
                continue
            shutil.rmtree(girdi.path)
        else:
            os.unlink(girdi.path)
        silinen += 1
    except OSError:
        hatali += 1

# standart başlangıç dosyaları (/etc/skel): öğrencinin kendi yetkisine sahip olarak
skel = 0
if os.path.isdir("/etc/skel"):
    for kok, klasorler, dosyalar in os.walk("/etc/skel"):
        goreli = os.path.relpath(kok, "/etc/skel")
        hedef_kok = ev if goreli == "." else os.path.join(ev, goreli)
        for ad in klasorler:
            h = os.path.join(hedef_kok, ad)
            if not os.path.lexists(h):
                os.mkdir(h, 0o755)
                os.lchown(h, kayit.pw_uid, kayit.pw_gid)
        for ad in dosyalar:
            k, h = os.path.join(kok, ad), os.path.join(hedef_kok, ad)
            if os.path.lexists(h) or os.path.islink(k):
                continue
            # düzen merkezden kilitliyse Pardus Karşılayıcı öğrenci girişinde açılmasın
            if ad == "tr.org.pardus.pardus-gnome-greeter.desktop" and \
                    os.path.exists("/var/lib/pardus-sinif-yonetimi/karsilayici-kapali"):
                continue
            shutil.copy2(k, h)
            os.lchown(h, kayit.pw_uid, kayit.pw_gid)
            skel += 1

print(json.dumps({"silinen": silinen, "hatali": hatali, "skel": skel, "kapsam": kapsam,
                  "bos_once": bos_once, "bos_sonra": bos()}))
'''


# ---- ortak adımlar (geri yükleme de kullanır) ----

def hazirlik_kontrol(is_id: str, cihaz: dict) -> bool:
    neden = secim.uygunluk(cihaz, "temizlik")
    if neden:
        veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                  f"{veritabani.cihaz_adi(cihaz)} — {neden}",
                                  {"cihaz_id": cihaz["id"], "ad": veritabani.cihaz_adi(cihaz)})
        return False
    return True


def baglan(cihaz: dict):
    return yonetim.baglan(cihaz)


def yedek_betigi(istemci) -> dict:
    """Doğrulanmış profil yedeği alır; saklama sınırını aşan eskileri budar."""
    return ssh_araclari.sudo_betik(
        istemci, uzak.betik("yedek"),
        {"mod": "yedekle", "hesap": ayarlar.PROFIL_HESABI,
         "saklama": veritabani.saklama_adedi()}, zaman=900)


def oturum_kapat(istemci, cihaz: dict) -> dict:
    return ssh_araclari.sudo_betik(
        istemci, _OTURUM_KAPAT_BETIGI,
        {"hesap": ayarlar.PROFIL_HESABI, "baglanti_hesabi": cihaz["baglanti_hesabi"]}, zaman=60)


def oturum_kapisi(is_id: str, istemci, cihaz: dict, zorla_kapat: bool, islem: str) -> bool:
    """Açık öğrenci oturumunu ele alır (istem §9.5–9.9).

    Oturum yoksa True. Açıksa ve oturum kapatma onaylanmadıysa hedefi "bekliyor"
    olarak işaretler; onaylandıysa kapatır ve süreç/mount'ların bittiğini doğrular.
    """
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    if ayarlar.PROFIL_HESABI not in ssh_araclari.aktif_oturumlar(istemci):
        return True
    if not zorla_kapat:
        veritabani.hedef_guncelle(
            is_id, ip, "atlandi", "oturum",
            f"{ad} — {ayarlar.PROFIL_HESABI} oturumu açık; oturum kapatma "
            f"onaylanmadığı için durum: {islem} bekliyor")
        return False
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "oturum",
                              f"{ad} — oturum kapatma onaylandı; kapatılıyor")
    sonuc = oturum_kapat(istemci, cihaz)
    if sonuc.get("hata") or sonuc.get("durum") == "kapatilamadi":
        neden = f": {sonuc['hata']}" if sonuc.get("hata") else ""
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "oturum",
            f"{ad} — oturum kapatılamadı{neden}; {islem.lower()} bu bilgisayarda başlatılmadı")
        return False
    if sonuc.get("kalan_mount"):
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "oturum",
            f"{ad} — oturum kapandı ancak kullanıcı mount'u sonlanmadı; "
            f"güvenlik gereği {islem.lower()} yapılmadı")
        return False
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "oturum",
                              f"{ad} — oturum kapandı; süreçler doğrulandı")
    return True


# ---- işler ----

async def _her_cihaz(cihaz_idler, iptal, paralellik, islev, islem="temizlik"):
    sinir = asyncio.Semaphore(paralellik)

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz or iptal.is_set():
            return
        neden = secim.uygunluk(cihaz, islem)
        if neden:
            veritabani.hedef_guncelle(islev.is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(islev, cihaz)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


class _Is:
    """İş kimliğini taşıyan çağrılabilir (asyncio.to_thread ile kullanılır)."""

    def __init__(self, is_id, fonksiyon, *argumanlar):
        self.is_id, self.fonksiyon, self.argumanlar = is_id, fonksiyon, argumanlar

    def __call__(self, cihaz):
        return self.fonksiyon(self.is_id, cihaz, *self.argumanlar)


async def oturum_kapat_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    await _her_cihaz(cihaz_idler, iptal, 8, _Is(is_id, _oturum_kapat), "oturum")


def _oturum_kapat(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    try:
        istemci = baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}")
        return
    try:
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "oturum", f"{ad} — kapatılıyor", veri)
        sonuc = oturum_kapat(istemci, cihaz)
        if sonuc.get("durum") == "zaten_kapali":
            veritabani.cihaz_guncelle(cihaz["id"], ogrenci_oturumu=0)
            veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                      f"{ad} — öğrenci oturumu zaten kapalıydı", veri)
        elif sonuc.get("durum") == "kapandi" and not sonuc.get("kalan_mount"):
            veritabani.cihaz_guncelle(cihaz["id"], ogrenci_oturumu=0)
            veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                      f"{ad} — öğrenci oturumu kapatıldı; süreçler doğrulandı", veri)
        else:
            neden = sonuc.get("hata") or ("kullanıcı mount'u kaldı" if sonuc.get("kalan_mount")
                                          else "kapatılamadı")
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "oturum", f"{ad} — {neden}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "oturum", f"{ad} — {hata}", veri)
    finally:
        istemci.close()


async def yedek_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    # yedekleme yükü için sınırlı paralellik (istem §11)
    await _her_cihaz(cihaz_idler, iptal, 4, _Is(is_id, _yedek_al))


def _yedek_al(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "yedek",
                              f"{ad} — {ayarlar.PROFIL_HESABI} profili yedekleniyor")
    try:
        istemci = baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — bağlantı kurulamadı: {hata}")
        return
    try:
        sonuc = yedek_betigi(istemci)
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "yedek", f"{ad} — {sonuc['hata']}")
            return
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — yedek doğrulandı: {sonuc['ad']} "
            f"({sonuc['bayt'] // 1048576} MB, {sonuc['kayit']} kayıt). "
            f"Yerel yedek disk arızasına karşı koruma sağlamaz.",
            {"cihaz_id": cihaz["id"], "ad": ad, "yedek": sonuc})
    except (RuntimeError, ssh_araclari.SudoHatasi) as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "yedek", f"{ad} — {hata}")
    finally:
        istemci.close()


async def profil_sifirla_isi(is_id: str, cihaz_idler: list[str], kapsam: str,
                             zorla_kapat: bool, iptal: asyncio.Event) -> None:
    """Tam akış: oturum kontrolü -> (onaylıysa) kapat -> yedek -> sıfırla -> skel."""
    await _her_cihaz(cihaz_idler, iptal, 2, _Is(is_id, _sifirla, kapsam, zorla_kapat))


def _sifirla(is_id: str, cihaz: dict, kapsam: str, zorla_kapat: bool) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "kapsam": kapsam}
    try:
        istemci = baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — bağlantı kurulamadı: {hata}")
        return
    try:
        if not oturum_kapisi(is_id, istemci, cihaz, zorla_kapat, "Profil sıfırlama"):
            return
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "yedek",
                                  f"{ad} — sıfırlama öncesi yedek alınıyor", veri)
        yedek = yedek_betigi(istemci)
        if "hata" in yedek:
            veritabani.hedef_guncelle(
                is_id, ip, "basarisiz", "yedek",
                f"{ad} — yedek başarısız ({yedek['hata']}); sıfırlama YAPILMADI", veri)
            return
        veri["yedek"] = yedek
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "sifirla",
                                  f"{ad} — yedek doğrulandı; profil sıfırlanıyor", veri)
        sonuc = ssh_araclari.sudo_betik(
            istemci, _SIFIRLA_BETIGI,
            {"hesap": ayarlar.PROFIL_HESABI, "arsiv": yedek["arsiv"],
             "sha256": yedek["sha256"], "kapsam": kapsam}, zaman=300)
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sifirla", f"{ad} — {sonuc['hata']}", veri)
            return
        veri["sonuc"] = sonuc
        veri["gerceklesen"] = sonuc["bos_sonra"] - sonuc["bos_once"]
        hatali = f", {sonuc['hatali']} öğe silinemedi" if sonuc.get("hatali") else ""
        kapsam_metni = ("ayarlar sıfırlandı (Belgeler ve görünür klasörler korundu)" if kapsam == "ayarlar"
                        else "ev dizininin tamamı sıfırlandı")
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — {kapsam_metni}: {sonuc['silinen']} öğe silindi{hatali}; "
            f"standart başlangıç dosyaları kondu; yedek: {yedek['ad']} "
            f"(M2-S1 “Yedekten dön” ile geri dönülebilir)", veri)
        veritabani.cihaz_guncelle(cihaz["id"], son_kontrol=veritabani.simdi(), ogrenci_oturumu=0)
    except (RuntimeError, ssh_araclari.SudoHatasi) as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sifirla", f"{ad} — {hata}", veri)
    finally:
        istemci.close()
