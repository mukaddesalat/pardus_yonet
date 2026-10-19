"""M1-S4 Veyon Ayarları: Veyon paketini ve public key'i yükleme, seçili bilgisayarlara
Veyon kurma/güncelleme, anahtar dosyasıyla yapılandırma, bağlantı doğrulama ve geri
alma (karar 28). Öğretmen Veyon Configurator kullanmaz.

- Veyon yalnız öğretmenin bu sayfaya yüklediği .deb'den kurulur; paket deposundan
  Veyon kurulmaz (bağımlılıklar apt ile çözülür). Paket metadata ile doğrulanır
  (Package: veyon); dosya adında "veyon" geçmesi yetmez.
- Aynı sürüm kuruluysa yeniden kurulmaz; daha yeni yüklenen paket güncelleme yapar;
  eski pakete düşürme yapılmaz. Debian'ın parçalı veyon-* paketleri tek paketin yerine
  geçer (yalnız bu Veyon ailesinin kaldırılmasına izin verilir).
- Public key PEM olarak yüklenir ve öğretmen PC'de saklanır; PRIVATE key hiçbir zaman
  istenmez, aktarılmaz ve günlüğe yazılmaz. Öğretmen PC'de yalnız private key
  dosyasının VARLIĞI ve erişim grubu (stat) denetlenir; eşleşme, aynı adlı yerel
  public key ile DER karşılaştırmasıyla yapılır.
- SSH anahtarı kurulum/bakım erişimi; Veyon anahtarı sınıf yönetimi bağlantısı içindir.
- Yapılandırmadan önce hedefteki Veyon ayarları ve anahtarları yedeklenir; "Önceki
  ayarları geri yükle" bu yedeği geri koyar (paket kaldırılmaz).
"""

import asyncio
import glob
import hashlib
import json
import os
import re
import socket
import subprocess
from pathlib import Path

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from . import ayarlar, debpaket, paketler, secim, ssh_araclari, uzak, veritabani, yonetim

try:  # yalnız Linux'ta var; Windows geliştirme ortamında öğretmen denetimi kısıtlı çalışır
    import grp
    import pwd
except ImportError:
    grp = pwd = None

PAKET_ADI = "veyon"
PAKET_AILESI = ("veyon", "veyon-service", "veyon-master", "veyon-configurator", "veyon-plugins",
                "libveyon-core")
ESDEGER_PAKETLER = ("veyon-service",)      # kurulu sürüm karşılaştırması için
ANAHTAR_ADI_DESENI = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,31}$")
VEYON_YOK_MESAJI = ("Bu bilgisayarda Veyon kurulu değil. Bu sayfadaki Veyon paketi alanından "
                    "uygun .deb dosyasını yükleyerek kurulumu başlatabilirsiniz.")
OGRETMEN_KONF = "/etc/xdg/Veyon Solutions/Veyon.conf"
OGRETMEN_ANAHTAR_KOK = "/etc/veyon/keys"
KIPLER = {"kur": "Veyon kur/güncelle", "yapilandir": "Veyon'u yapılandır", "ikisi": "Kur ve yapılandır"}
PAKET_SECIM_AYARI = "veyon_paket_sha"


class VeyonHatasi(ValueError):
    """Öğretmene olduğu gibi gösterilir."""


class OnayGerekli(VeyonHatasi):
    def __init__(self, mesaj: str, mevcut: dict):
        super().__init__(mesaj)
        self.mevcut = mevcut


# ---------------------------------------------------------------- paket doğrulama

def _saglananlar(kontrol: dict) -> set[str]:
    return {p.strip().split()[0] for p in (kontrol.get("Provides") or "").split(",") if p.strip()}


def veyon_paketi_mi(bilgi: dict) -> bool:
    """Veyon ailesinden bir paket mi? (genel M2-S2 yüklemesinde reddetmek için)"""
    kontrol = bilgi.get("kontrol") or {}
    return bilgi["paket"] in PAKET_AILESI or bool(_saglananlar(kontrol) & set(PAKET_AILESI))


def paket_dogrula(bilgi: dict) -> None:
    """Desteklenen Veyon paketi: tek parça 'veyon' (veyon.io / Pardus contrib). Metadata denetlenir."""
    kontrol = bilgi.get("kontrol") or {}
    if bilgi["paket"] != PAKET_ADI:
        if veyon_paketi_mi(bilgi):
            raise debpaket.PaketHatasi(
                f"'{bilgi['paket']}' Debian'ın parçalı Veyon paketlerinden biri; tek başına kurulmaz. "
                "veyon.io'dan veya Pardus deposundan tek parça 'veyon' paketini "
                "(veyon_<sürüm>_amd64.deb) indirip yükleyin.")
        raise debpaket.PaketHatasi(
            f"Bu dosya Veyon paketi değil (paket adı: {bilgi['paket']}). Veyon sayfası yalnız 'veyon' "
            "paketini kabul eder; başka uygulamalar M2-S2 Paket Kurulumu'ndan kurulur.")
    if "veyon-service" not in _saglananlar(kontrol) and "veyon" not in (kontrol.get("Description") or "").lower():
        raise debpaket.PaketHatasi("Paket adı 'veyon' ama içerik Veyon'a benzemiyor (Provides/Description "
                                   "eksik). Dosyayı güvenilir kaynaktan yeniden indirin.")


# ---------------------------------------------------------------- public key

def qt_ozet(veri: bytes) -> str:
    """Veyon'un gösterdiği PAIR ID: Qt5 qHash(QByteArray(DER)) → 8 onaltılık hane (lab'da doğrulandı)."""
    h = 0
    for b in veri:
        h = (31 * h + b) & 0xFFFFFFFF
    return "%08x" % h


def anahtar_incele(veri: bytes) -> dict:
    """Yalnız RSA public key (PEM veya DER) kabul eder; private/SSH/geçersiz dosyayı reddeder."""
    if len(veri) > ayarlar.EN_BUYUK_ANAHTAR:
        raise VeyonHatasi("Dosya 64 KB sınırını aşıyor; bu bir public key dosyası olamaz")
    metin = veri.decode("utf-8", "replace")
    if "PRIVATE KEY" in metin.upper():
        raise VeyonHatasi("Bu bir PRIVATE (özel) anahtar! Özel anahtar hiçbir zaman yüklenmez; bu uygulama "
                          "onu saklamadı. Yalnız Veyon PUBLIC key dosyasını (…_public_key.pem) seçin; özel "
                          "anahtar öğretmen bilgisayarında kalmalıdır.")
    if metin.lstrip().startswith(("ssh-rsa", "ssh-ed25519", "ecdsa-sha2-", "ssh-dss", "sk-ssh-", "sk-ecdsa")):
        raise VeyonHatasi("Bu bir SSH public key; Veyon anahtarı değil. Veyon public key'i PEM biçimindedir "
                          "(-----BEGIN PUBLIC KEY-----). SSH anahtarı bakım erişimi için M1-S2'de kullanılır.")
    anahtar = None
    for yukle in (serialization.load_pem_public_key, serialization.load_der_public_key):
        try:
            anahtar = yukle(veri)
            break
        except (ValueError, TypeError, UnsupportedAlgorithm):
            continue
    if anahtar is None:
        raise VeyonHatasi("Geçerli bir Veyon public key değil ('BEGIN PUBLIC KEY' veya 'BEGIN RSA PUBLIC KEY' "
                          "PEM bekleniyor). Veyon Configurator → Kimlik doğrulama anahtarları → Dışa aktar, "
                          "ya da: veyon-cli authkeys export <ad>/public dosya.pem")
    if not isinstance(anahtar, rsa.RSAPublicKey):
        raise VeyonHatasi(f"Veyon RSA anahtarı kullanır; bu anahtar {type(anahtar).__name__} türünde.")
    der = anahtar.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    pem = anahtar.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return {"parmak_izi": hashlib.sha256(der).hexdigest(), "cift_kimligi": qt_ozet(der),
            "bit": anahtar.key_size, "pem": pem.decode("ascii")}


def _dizin() -> Path:
    d = ayarlar.veri_yollari()["veyon_dizini"]
    d.mkdir(parents=True, exist_ok=True)
    try:
        # Veyon anahtar dizini (yalnızca sahibi tarafından erişilebilir)
        os.chmod(d, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    except OSError:
        pass
    return d


def anahtar_bilgisi() -> dict | None:
    d = _dizin()
    try:
        bilgi = json.loads((d / "anahtar.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not (d / "acik_anahtar.pem").exists():
        return None
    return bilgi


def anahtar_pem() -> str | None:
    try:
        return (_dizin() / "acik_anahtar.pem").read_text(encoding="ascii")
    except OSError:
        return None


def anahtar_kaydet(ad: str, dosya_adi: str, veri: bytes, onay: bool = False) -> dict:
    """Aynı adla FARKLI anahtar geliyorsa mevcut anahtar yedeklenir ve açık onay istenir."""
    if not ANAHTAR_ADI_DESENI.match(ad or ""):
        raise VeyonHatasi("Anahtar adı harfle başlamalı, yalnız harf ve rakam içermeli (ör. teacher). "
                          "Öğretmen PC'deki private key ile aynı ad olmalıdır.")
    bilgi = anahtar_incele(veri)
    mevcut = anahtar_bilgisi()
    d = _dizin()
    farkli = bool(mevcut and mevcut["parmak_izi"] != bilgi["parmak_izi"])
    if farkli:
        if not onay:
            raise OnayGerekli(
                f"Uygulamada kayıtlı '{mevcut['ad']}' anahtarından ([{mevcut['cift_kimligi']}]) farklı bir "
                f"anahtar yüklüyorsunuz ([{bilgi['cift_kimligi']}]). Onaylarsanız mevcut anahtar yedeklenir ve "
                "değiştirilir; öğrenci bilgisayarları yeniden yapılandırılana kadar eski anahtarla çalışır.",
                mevcut)
        yedek = d / "yedek"
        yedek.mkdir(exist_ok=True)
        eski = anahtar_pem()
        if eski:
            zaman = veritabani.simdi().replace(":", "").replace("-", "")[:15]
            (yedek / f"{mevcut['ad']}-{mevcut['cift_kimligi']}-{zaman}.pem").write_text(eski, encoding="ascii")
    kayit = {"ad": ad, "dosya_adi": os.path.basename(dosya_adi or "public_key.pem")[:120],
             "parmak_izi": bilgi["parmak_izi"], "cift_kimligi": bilgi["cift_kimligi"], "bit": bilgi["bit"],
             "zaman": veritabani.simdi(),
             "onceki": ({"ad": mevcut["ad"], "cift_kimligi": mevcut["cift_kimligi"], "zaman": mevcut["zaman"]}
                        if farkli else (mevcut or {}).get("onceki"))}
    pem_yolu = d / "acik_anahtar.pem"
    pem_yolu.write_text(bilgi["pem"], encoding="ascii")
    (d / "anahtar.json").write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
    for yol in (pem_yolu, d / "anahtar.json"):
        try:
            os.chmod(yol, 0o600)
        except OSError:
            pass
    return kayit


def anahtar_sil() -> bool:
    d = _dizin()
    vardi = False
    for ad in ("acik_anahtar.pem", "anahtar.json"):
        yol = d / ad
        if yol.exists():
            yol.unlink()
            vardi = True
    return vardi


# ---------------------------------------------------------------- öğretmen PC hazırlığı (salt okunur)

def _dpkg_surum(paket: str) -> str | None:
    try:
        r = subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Version}", paket],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or "\t" not in r.stdout:
        return None
    durum, surum = r.stdout.split("\t", 1)
    return surum.strip() if durum.strip() == "ii" else None


def _ini_oku(yol: str) -> dict | None:
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


def _okuyabilenler(st) -> list[str]:
    """Dosyayı grup izniyle okuyabilen normal (uid ≥ 1000) hesaplar."""
    if not st.st_mode & 0o040 or grp is None or not hasattr(grp, "getgrgid"):
        return []
    try:
        uyeler = set(grp.getgrgid(st.st_gid).gr_mem)
    except KeyError:
        uyeler = set()
    uyeler |= {p.pw_name for p in pwd.getpwall() if p.pw_gid == st.st_gid and p.pw_uid >= 1000}
    return sorted(u for u in uyeler if u != "root")


def ogretmen_hazirligi() -> dict:
    """Öğretmen PC'de Veyon Master tarafı: private key var mı, kim okuyabilir, yöntem anahtar mı."""
    bilgi = anahtar_bilgisi()
    sonuc = {"anahtar": bilgi, "veyon": None, "yerel_anahtarlar": [], "eslesen": None,
             "ozel_anahtar": None, "yontem": None, "sorunlar": [], "uyarilar": [], "komutlar": []}
    for paket in ("veyon", "veyon-master"):
        surum = _dpkg_surum(paket)
        if surum:
            sonuc["veyon"] = {"paket": paket, "surum": surum}
            break
    for yol in sorted(glob.glob(OGRETMEN_ANAHTAR_KOK + "/public/*/key")):
        ad = os.path.basename(os.path.dirname(yol))
        try:
            with open(yol, "rb") as f:
                yerel = anahtar_incele(f.read(ayarlar.EN_BUYUK_ANAHTAR + 1))
        except (OSError, VeyonHatasi):
            sonuc["yerel_anahtarlar"].append({"ad": ad, "hata": "okunamadı"})
            continue
        sonuc["yerel_anahtarlar"].append({"ad": ad, "cift_kimligi": yerel["cift_kimligi"], "bit": yerel["bit"]})
        if bilgi and yerel["parmak_izi"] == bilgi["parmak_izi"]:
            sonuc["eslesen"] = ad
    if not bilgi:
        sonuc["sorunlar"].append("Henüz Veyon public key yüklenmedi (M1-S4-B4).")
    else:
        ad = bilgi["ad"]
        yol = f"{OGRETMEN_ANAHTAR_KOK}/private/{ad}/key"
        try:
            st = os.stat(yol)
        except FileNotFoundError:
            sonuc["ozel_anahtar"] = {"var": False, "yol": yol}
            metin = (f"Öğretmen PC'de '{ad}' adlı private key yok ({yol}). Veyon Master bu anahtarla bağlanamaz. "
                     "Anahtar adını private key'in adıyla aynı yapın veya Veyon Configurator ile anahtar çifti "
                     "oluşturup public key'i dışa aktarın.")
            if sonuc["veyon"]:
                sonuc["sorunlar"].append(metin)
            else:
                sonuc["uyarilar"].append(metin + " (Bu bilgisayarda Veyon kurulu görünmüyor; Master başka "
                                                 "bilgisayardaysa denetimi orada yapın.)")
        except PermissionError:
            sonuc["ozel_anahtar"] = {"var": None, "yol": yol}
            sonuc["uyarilar"].append(f"Private key dizini okunamadı ({yol}); varlığı denetlenemedi.")
        else:
            try:
                grup = grp.getgrgid(st.st_gid).gr_name
            except (KeyError, AttributeError):
                grup = str(st.st_gid)
            okuyanlar = _okuyabilenler(st)
            sonuc["ozel_anahtar"] = {"var": True, "yol": yol, "grup": grup, "izin": "%04o" % (st.st_mode & 0o7777),
                                     "okuyabilenler": okuyanlar, "herkes_okur": bool(st.st_mode & 0o004),
                                     "not": "içeriği bu uygulama tarafından okunmaz"}
            if sonuc["ozel_anahtar"]["herkes_okur"]:
                sonuc["uyarilar"].append("Private key herkes tarafından okunabilir; erişimi öğretmen hesabıyla "
                                         f"sınırlayın: sudo veyon-cli authkeys setaccessgroup {ad}/private "
                                         "<öğretmen-hesabı>")
            elif not okuyanlar:
                sonuc["sorunlar"].append(f"Private key ({yol}) yalnız root okuyabiliyor (grup: {grup}); Veyon "
                                         "Master'ı çalıştıran öğretmen hesabı okuyamaz.")
                sonuc["komutlar"].append(f"sudo veyon-cli authkeys setaccessgroup {ad}/private <öğretmen-hesabı>")
        if sonuc["eslesen"] and sonuc["eslesen"] != ad:
            sonuc["sorunlar"].append(f"Yüklenen public key öğretmen PC'de '{sonuc['eslesen']}' adıyla kayıtlı; "
                                     f"anahtar adı '{ad}' yerine '{sonuc['eslesen']}' olmalı.")
        elif sonuc["eslesen"] is None and sonuc["yerel_anahtarlar"]:
            sonuc["uyarilar"].append(
                "Yüklenen public key, öğretmen PC'deki Veyon anahtarlarının hiçbiriyle aynı değil (yerel: "
                + ", ".join(f"{k['ad']} [{k.get('cift_kimligi', '?')}]" for k in sonuc["yerel_anahtarlar"])
                + "). Veyon Master bu bilgisayardaysa anahtarla bağlanamaz; Master başka bilgisayardaysa bu normaldir.")
        elif sonuc["eslesen"] is None and sonuc["veyon"]:
            sonuc["uyarilar"].append("Öğretmen PC'de hiç Veyon public key yok; anahtar çifti Veyon Configurator "
                                     "ile oluşturulmuş olmalıdır.")
    ini = _ini_oku(OGRETMEN_KONF) or {}
    yontem = ini.get("Authentication", {}).get("Method")
    sonuc["yontem"] = int(yontem) if yontem and yontem.isdigit() else None
    if sonuc["veyon"] and sonuc["yontem"] != 1:
        sonuc["sorunlar"].append("Öğretmen PC'deki Veyon kimlik doğrulama yöntemi 'anahtar dosyası' değil; "
                                 "Veyon Master anahtarla bağlanamaz.")
        sonuc["komutlar"].append("sudo veyon-cli config set Authentication/Method 1")
    if not sonuc["veyon"]:
        sonuc["uyarilar"].append("Bu bilgisayarda Veyon Master kurulu görünmüyor (veyon / veyon-master paketi yok).")
    sonuc["hazir"] = not sonuc["sorunlar"]
    return sonuc


# ---------------------------------------------------------------- paket seçimi

def secili_paket() -> dict | None:
    sha = veritabani.ayar_oku(PAKET_SECIM_AYARI)
    p = paketler.paket_bilgisi(sha) if sha else None
    if p and p.get("tur") == "veyon":
        return p
    liste = paketler.paketler("veyon")
    return liste[0] if len(liste) == 1 else None


def paket_sec(sha: str) -> dict:
    p = paketler.paket_bilgisi(sha)
    if not p or p.get("tur") != "veyon":
        raise VeyonHatasi("Veyon paketi bulunamadı")
    veritabani.ayar_yaz(PAKET_SECIM_AYARI, sha)
    return p


def paket_silindi(sha: str) -> None:
    if veritabani.ayar_oku(PAKET_SECIM_AYARI) == sha:
        veritabani.ayar_yaz(PAKET_SECIM_AYARI, "")


def ozet() -> dict:
    secili = secili_paket()
    return {"paketler": paketler.paketler("veyon"), "secili_sha": secili["sha256"] if secili else None,
            "anahtar": anahtar_bilgisi(), "anahtar_adi_varsayilan": ayarlar.VEYON_ANAHTAR_VARSAYILAN,
            "veyon_yok_mesaji": VEYON_YOK_MESAJI, "kipler": KIPLER}


# ---------------------------------------------------------------- envanter alanları

def envanter_alanlari(v: dict) -> dict:
    """Uzak durum çıktısından envanter sütunları (M1-S1 durum kontrolü ve buradaki işler kullanır)."""
    sv = v.get("servis") or {}
    anahtarlar = v.get("anahtarlar") or {}
    bilgi = anahtar_bilgisi()
    eslesme = None
    if bilgi:
        mevcut = anahtarlar.get(bilgi["ad"]) or {}
        eslesme = "yok" if not mevcut else "eslesiyor" if mevcut.get("parmak_izi") == bilgi["parmak_izi"] else "farkli"
    return {
        "veyon_surum": v.get("surum"),
        "veyon_durumu": v.get("durum") or "okunamadi",
        "veyon_yapilandirma": {
            "paket": v.get("paket"), "parcali": bool(v.get("parcali")), "neden": v.get("neden"),
            "servis": {"etkin": sv.get("etkin"), "calisiyor": sv.get("calisiyor"), "port": sv.get("port_dinliyor")},
            "yontem": v.get("yontem"),
            "anahtarlar": {ad: b.get("cift_kimligi") for ad, b in anahtarlar.items()},
            "anahtar_adi": bilgi["ad"] if bilgi else None, "eslesme": eslesme,
        },
        "veyon_kontrol": veritabani.simdi(),
    }


YONTEM_ADI = {1: "anahtar dosyası", 0: "oturum parolası", None: "ayarlanmamış"}


def _ozet_metni(v: dict) -> str:
    a = envanter_alanlari(v)
    y = a["veyon_yapilandirma"]
    if a["veyon_durumu"] == "kurulu":
        kurulum = f"Veyon {a['veyon_surum']} kurulu" + (" (parçalı Debian paketi)" if y["parcali"] else "")
    elif a["veyon_durumu"] == "kurulu_degil":
        kurulum = "Veyon kurulu değil"
    elif a["veyon_durumu"] == "hatali":
        kurulum = "Veyon kurulumu hatalı veya yarım (%s)" % (y.get("neden") or a["veyon_surum"])
    else:
        kurulum = "Veyon sürümü okunamadı"
    sv = y["servis"]
    servis = ("servis çalışıyor" if sv["calisiyor"] else "servis kapalı") if a["veyon_durumu"] == "kurulu" else None
    anahtar = None
    if y["anahtar_adi"]:
        anahtar = {"eslesiyor": f"anahtar '{y['anahtar_adi']}' eşleşiyor", "farkli": f"anahtar '{y['anahtar_adi']}' FARKLI",
                   "yok": f"anahtar '{y['anahtar_adi']}' yok"}[y["eslesme"]]
    yontem = f"yöntem: {YONTEM_ADI.get(y['yontem'], y['yontem'])}" if a["veyon_durumu"] == "kurulu" else None
    return "; ".join(p for p in (kurulum, servis, anahtar, yontem) if p)


def _yapilandirma_metni(ogeler: dict) -> str:
    a, y, s = ogeler.get("anahtar", {}), ogeler.get("yontem", {}), ogeler.get("servis", {})
    ad = a.get("ad", "?")
    metin = {
        "anahtar": {"zaten": f"anahtar '{ad}' zaten aynı", "eklenecek": f"anahtar '{ad}' eklenecek",
                    "degistirilecek": f"anahtar '{ad}' DEĞİŞTİRİLECEK (mevcut [{a.get('mevcut_kimlik')}] yedeklenir)",
                    "uygulandi": f"anahtar '{ad}' kuruldu ve geri okunarak doğrulandı",
                    "hata": f"anahtar HATASI: {a.get('neden')}"},
        "yontem": {"zaten": "yöntem zaten anahtar dosyası", "ayarlanacak": "yöntem → anahtar dosyası",
                   "uygulandi": "yöntem anahtar dosyası yapıldı", "hata": f"yöntem HATASI: {y.get('neden')}"},
        "servis": {"zaten": "servis zaten çalışıyor", "etkinlestirilecek": "servis etkinleştirilip başlatılacak",
                   "uygulandi": "servis etkin ve çalışıyor", "hata": f"servis HATASI: {s.get('neden')}"},
    }
    return ", ".join(metin[k].get(o.get("durum"), f"{k}: {o.get('durum')}") for k, o in
                     (("anahtar", a), ("yontem", y), ("servis", s)) if o)


# ---------------------------------------------------------------- işler

def _veyon_betik(istemci, parametre: dict, zaman: int = 120) -> dict:
    try:
        return ssh_araclari.sudo_betik(istemci, uzak.betik("veyon"), parametre, zaman=zaman)
    except ssh_araclari.SudoHatasi:
        if parametre.get("kip") in ("durum", "dogrula"):     # salt okunur kipler root istemez
            return ssh_araclari.betik(istemci, uzak.betik("veyon"), parametre, zaman=zaman)
        raise


def _anahtar_parametre() -> dict:
    bilgi = anahtar_bilgisi()
    return {"anahtar_adi": bilgi["ad"], "parmak_izi": bilgi["parmak_izi"]} if bilgi else {}


def _paket_parametresi(paket: dict, kip: str) -> dict:
    return {**paketler._parametre(paket, kip), "kaldirma_izni": list(PAKET_AILESI),
            "esdeger_paketler": list(ESDEGER_PAKETLER)}


def _yalniz_dusurme(plan: dict) -> bool:
    """Engel yalnız "daha yeni sürüm kurulu" ise kurulum atlanır, yapılandırma sürer (düşürme yapılmaz)."""
    engeller = plan.get("engeller") or []
    return plan.get("durum") == "engellendi" and bool(engeller) and all(e.startswith("sürüm düşürme") for e in engeller)


def _dusurme_neden(plan: dict) -> str:
    return (f"daha yeni Veyon kurulu ({plan.get('kurulu_surum')}); seçili paket daha eski — sürüm düşürülmez, "
            "kurulum atlanır")


def _durumu_yaz(cihaz: dict, v: dict) -> dict:
    alanlar = envanter_alanlari(v)
    veritabani.cihaz_guncelle(cihaz["id"], erisim=1, erisim_zamani=veritabani.simdi(), **alanlar)
    return alanlar


async def _is(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event, tek, *ek,
              islem: str = "veyon") -> None:
    sinir = asyncio.Semaphore(ayarlar.PAKET_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz:
            return
        ad = veritabani.cihaz_adi(cihaz)
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "iptal", f"{ad} — kullanıcı iptal etti",
                                      {"cihaz_id": cid, "ad": ad})
            return
        neden = secim.uygunluk(cihaz, islem)
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam", f"{ad} — {neden}",
                                      {"cihaz_id": cid, "ad": ad, "durum": "kapsam_disi", "neden": neden})
            return
        async with sinir:
            await asyncio.to_thread(tek, is_id, cihaz, *ek)

    await asyncio.gather(*(_tek(c) for c in dict.fromkeys(cihaz_idler)))


def _baglan(is_id: str, cihaz: dict, veri: dict):
    ip, ad = cihaz["ip"], veri["ad"]
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        return yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}",
                                  {**veri, "durum": "hata"})
        return None


async def surum_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    """"Sürümleri yenile": yalnız bilinen envanter kayıtları sorgulanır; ağ taraması yapılmaz."""
    await _is(is_id, cihaz_idler, iptal, _surum_oku, islem="veyon_oku")


def _surum_oku(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    istemci = _baglan(is_id, cihaz, veri)
    if not istemci:
        return
    try:
        v = _veyon_betik(istemci, {"kip": "durum", **_anahtar_parametre()}, 60)
        if "hata" in v:
            raise RuntimeError(v["hata"])
        _durumu_yaz(cihaz, v)
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam", f"{ad} — {_ozet_metni(v)}", {**veri, "veyon": v})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "durum", f"{ad} — {hata}", {**veri, "durum": "hata"})
    finally:
        istemci.close()


async def plan_isi(is_id: str, cihaz_idler: list[str], kip: str, iptal: asyncio.Event) -> None:
    """Önizleme: kurulacak sürüm ve uygulanacak ayarlar; hiçbir şey değişmez (paket aktarımı hariç)."""
    await _is(is_id, cihaz_idler, iptal, _plan, kip, secili_paket(), anahtar_bilgisi())


def _plan(is_id: str, cihaz: dict, kip: str, paket: dict | None, anahtar: dict | None) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "kip": kip}
    istemci = _baglan(is_id, cihaz, veri)
    if not istemci:
        return
    try:
        v = _veyon_betik(istemci, {"kip": "durum", **_anahtar_parametre()}, 60)
        if "hata" in v:
            raise RuntimeError(v["hata"])
        _durumu_yaz(cihaz, v)
        veri["veyon"] = v
        parcalar, engel = [], False
        if kip in ("kur", "ikisi"):
            if not paket:
                raise RuntimeError("Kurulacak Veyon paketi seçilmedi (M1-S4-B1 / M1-S4-B2)")
            veritabani.hedef_guncelle(is_id, ip, "calisiyor", "aktarim", f"{ad} — paket aktarılıyor", veri)
            paketler._aktar(istemci, paket)
            plan = ssh_araclari.sudo_betik(istemci, uzak.betik("paket"), _paket_parametresi(paket, "plan"), zaman=400)
            if "hata" in plan:
                raise RuntimeError(plan["hata"])
            if _yalniz_dusurme(plan):
                plan = {**plan, "durum": "atlanacak", "neden": _dusurme_neden(plan), "engeller": []}
            veri["kurulum"] = plan
            d = plan["durum"]
            if d == "kurulacak":
                parcalar.append(f"kurulum: veyon {paket['surum']} kurulacak")
            elif d == "guncellenecek":
                parcalar.append(f"kurulum: güncellenecek ({plan.get('kurulu_paket')} {plan.get('kurulu_surum')} → "
                                f"veyon {paket['surum']}" + ("; eski parçalı paketler yerine geçer"
                                                            if plan.get("yerine_gececek") else "") + ")")
            elif d == "atlanacak":
                parcalar.append("kurulum: " + (plan.get("neden") or "aynı sürüm; atlanacak"))
            else:
                engel = True
                parcalar.append("kurulum ENGELLENDİ: " + "; ".join(plan.get("engeller") or []))
            for u in plan.get("uyarilar") or []:
                if "yerine" not in u:
                    parcalar.append(u)
        if kip in ("yapilandir", "ikisi"):
            if not anahtar:
                raise RuntimeError("Veyon public key yüklenmedi (M1-S4-B4)")
            if kip == "yapilandir" and v["durum"] != "kurulu":
                neden = VEYON_YOK_MESAJI if v["durum"] == "kurulu_degil" else \
                    f"Veyon kurulumu {('hatalı veya yarım' if v['durum'] == 'hatali' else 'okunamadı')}; önce kurulumu düzeltin"
                veri["yapilandirma"] = {"durum": "engellendi", "neden": neden}
                engel = True
                parcalar.append("yapılandırma: " + neden)
            else:
                y = _veyon_betik(istemci, {"kip": "yapilandir", "anahtar_adi": anahtar["ad"],
                                           "anahtar_pem": anahtar_pem(), "parmak_izi": anahtar["parmak_izi"],
                                           "uygula": False}, 120)
                if "hata" in y:
                    raise RuntimeError(y["hata"])
                veri["yapilandirma"] = y
                parcalar.append("yapılandırma: " + _yapilandirma_metni(y["ogeler"])
                                + (" (kurulumdan sonra)" if y.get("veyon_yok") else ""))
                parcalar += y.get("uyarilar") or []
        veri["durum"] = "engellendi" if engel else "hazir"
        veritabani.hedef_guncelle(is_id, ip, "basarisiz" if engel else "basarili", "plan",
                                  f"{ad} — " + "; ".join(parcalar), veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", {**veri, "durum": "hata"})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "plan", f"{ad} — {hata}", {**veri, "durum": "hata"})
    finally:
        istemci.close()


def onaylanabilir_hedefler(plan_is_id: str, kip: str) -> list[str]:
    kayit = veritabani.is_durumu(plan_is_id)
    if not kayit or kayit["tip"] != "veyon_plan" or kayit["parametreler"].get("kip") != kip:
        return []
    return [h["veri"]["cihaz_id"] for h in kayit["hedefler"]
            if h.get("veri") and h["veri"].get("durum") == "hazir"]


async def uygula_isi(is_id: str, cihaz_idler: list[str], kip: str, iptal: asyncio.Event) -> None:
    await _is(is_id, cihaz_idler, iptal, _uygula, kip, secili_paket(), anahtar_bilgisi())


def _uygula(is_id: str, cihaz: dict, kip: str, paket: dict | None, anahtar: dict | None) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "kip": kip}
    istemci = _baglan(is_id, cihaz, veri)
    if not istemci:
        return
    try:
        adimlar = []
        if kip in ("kur", "ikisi"):
            if not paket:
                raise RuntimeError("Kurulacak Veyon paketi seçilmedi")
            paketler._aktar(istemci, paket)
            veritabani.hedef_guncelle(is_id, ip, "calisiyor", "kurulum", f"{ad} — veyon {paket['surum']} kuruluyor", veri)
            sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("paket"), _paket_parametresi(paket, "kur"), zaman=2000)
            if "hata" in sonuc:
                raise RuntimeError(sonuc["hata"])
            veri["kurulum"] = sonuc
            if _yalniz_dusurme(sonuc):
                adimlar.append("kurulum atlandı: " + _dusurme_neden(sonuc))
            elif sonuc.get("durum") == "atlanacak":
                adimlar.append("kurulum atlandı: " + (sonuc.get("neden") or "aynı sürüm zaten kurulu"))
            elif sonuc.get("kuruldu"):
                adimlar.append(f"kuruldu ve doğrulandı: veyon {sonuc['kurulu_surum']}")
            else:
                if sonuc.get("durum") == "engellendi":
                    mesaj = "kurulmadı: " + "; ".join(sonuc.get("engeller") or [])
                else:
                    son = " | ".join((sonuc.get("kayit") or [])[-3:])
                    mesaj = f"kurulum başarısız (apt rc={sonuc.get('rc')}): {son}"
                v = _veyon_betik(istemci, {"kip": "durum", **_anahtar_parametre()}, 60)
                if "hata" not in v:
                    _durumu_yaz(cihaz, v)
                veri["durum"] = "hata"
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kurulum",
                                          f"{ad} — {mesaj}; yapılandırmaya geçilmedi", veri)
                return
        if kip in ("yapilandir", "ikisi"):
            if not anahtar:
                raise RuntimeError("Veyon public key yüklenmedi")
            veritabani.hedef_guncelle(is_id, ip, "calisiyor", "yapilandirma", f"{ad} — Veyon yapılandırılıyor", veri)
            y = _veyon_betik(istemci, {"kip": "yapilandir", "anahtar_adi": anahtar["ad"], "anahtar_pem": anahtar_pem(),
                                       "parmak_izi": anahtar["parmak_izi"], "uygula": True}, 300)
            if y.get("hata") == "veyon_yok":
                raise RuntimeError(VEYON_YOK_MESAJI)
            if "hata" in y:
                raise RuntimeError(y["hata"])
            veri["yapilandirma"] = y
            adimlar.append("yapılandırma: " + _yapilandirma_metni(y["ogeler"])
                           + f" (önceki ayarlar yedeklendi: {y['yedek']['ad']})")
            if y.get("hata_var"):
                _durumu_yaz(cihaz, y["durum"])
                veri["durum"] = "hata"
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "yapilandirma", f"{ad} — " + "; ".join(adimlar), veri)
                return
        v = _veyon_betik(istemci, {"kip": "durum", **_anahtar_parametre()}, 60)
        if "hata" in v:
            raise RuntimeError(v["hata"])
        _durumu_yaz(cihaz, v)
        veri["veyon"] = v
        veri["durum"] = "tamam"
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                  f"{ad} — " + "; ".join(adimlar) + f" | {_ozet_metni(v)}", veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", {**veri, "durum": "hata"})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "uygulama", f"{ad} — {hata}", {**veri, "durum": "hata"})
    finally:
        istemci.close()


def rfb_karsilama(ip: str, port: int = ayarlar.VEYON_PORT, zaman: float = 3.0) -> str | None:
    """Veyon sunucusuna TCP bağlanıp RFB karşılamasını okur (kimlik bilgisi gönderilmez)."""
    try:
        with socket.create_connection((ip, port), timeout=zaman) as s:
            s.settimeout(zaman)
            veri = s.recv(12)
    except OSError:
        return None
    return veri.decode("ascii", "replace").strip("\x00\r\n ") if veri.startswith(b"RFB ") else None


async def dogrula_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    await _is(is_id, cihaz_idler, iptal, _dogrula, islem="veyon_oku")


def _dogrula(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    istemci = _baglan(is_id, cihaz, veri)
    if not istemci:
        return
    try:
        d = _veyon_betik(istemci, {"kip": "dogrula", **_anahtar_parametre()}, 60)
        if "hata" in d:
            raise RuntimeError(d["hata"])
        _durumu_yaz(cihaz, d["durum"])
        rfb = rfb_karsilama(ip)
        denetimler = list(d["denetimler"]) + [["rfb", bool(rfb),
                                              f"öğretmen PC'den Veyon sunucusu yanıt verdi ({rfb})" if rfb
                                              else f"öğretmen PC'den {ayarlar.VEYON_PORT} portuna bağlanılamadı"]]
        tamam = all(ok for _, ok, _ in denetimler)
        veri.update(veyon=d["durum"], denetimler=denetimler, tamam=tamam, durum="tamam" if tamam else "hata")
        mesaj = f"{ad} — " + "; ".join(("✓ " if ok else "✗ ") + m for _, ok, m in denetimler)
        mesaj += " | Anahtarla gerçek oturum yalnız Veyon Master'da denenebilir (private key bu uygulamada yok)"
        veritabani.hedef_guncelle(is_id, ip, "basarili" if tamam else "basarisiz", "dogrulama", mesaj, veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "dogrulama", f"{ad} — {hata}", {**veri, "durum": "hata"})
    finally:
        istemci.close()


async def geri_al_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    await _is(is_id, cihaz_idler, iptal, _geri_al)


def _geri_al(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    istemci = _baglan(is_id, cihaz, veri)
    if not istemci:
        return
    try:
        g = _veyon_betik(istemci, {"kip": "geri_al", **_anahtar_parametre()}, 180)
        if "hata" in g:
            raise RuntimeError(g["hata"])
        _durumu_yaz(cihaz, g["durum"])
        veri.update(geri_alma=g, veyon=g["durum"], durum="tamam")
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                  f"{ad} — yedek {g['yedek']} geri alındı: " + "; ".join(g["adimlar"])
                                  + f" | {_ozet_metni(g['durum'])}", veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", {**veri, "durum": "hata"})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "geri_alma", f"{ad} — {hata}", {**veri, "durum": "hata"})
    finally:
        istemci.close()
