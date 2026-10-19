"""Arayüz güvenliği: parola, oturum çerezi, CSRF ve Origin/Host kontrolü.

Karar 3: uygulama anahtarı parolasızdır; tek etkileşimli koruma bu modüldeki
arayüz giriş parolasıdır. Bu yüzden oturum olmadan hiçbir yönetim ucu çalışmaz.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import HTTPException, Request

from . import ayarlar, veritabani

_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def _gizli_anahtar() -> bytes:
    """Çerez imzalama sırrı; ilk kullanımda üretilir ve veritabanında saklanır."""
    deger = veritabani.ayar_oku("gizli_anahtar")
    if deger is None:
        deger = secrets.token_hex(32)
        veritabani.ayar_yaz("gizli_anahtar", deger)
    return bytes.fromhex(deger)


# ---- parola ----

def parola_karmasi(parola: str) -> str:
    tuz = os.urandom(16)
    ozet = hashlib.scrypt(parola.encode(), salt=tuz, **_SCRYPT)
    return base64.b64encode(tuz).decode() + "$" + base64.b64encode(ozet).decode()


bcrypt_ozet = parola_karmasi


def parola_dogru_mu(parola: str, kayit: str) -> bool:
    try:
        tuz_b64, ozet_b64 = kayit.split("$", 1)
        tuz = base64.b64decode(tuz_b64)
        beklenen = base64.b64decode(ozet_b64)
    except Exception:
        return False
    ozet = hashlib.scrypt(parola.encode(), salt=tuz, **_SCRYPT)
    return hmac.compare_digest(ozet, beklenen)


def kurulum_tamam_mi() -> bool:
    eski_parola_gocu()
    return veritabani.ayar_oku("giris_parolasi") is not None or bool(veritabani.ogretmenler())


def eski_parola_gocu() -> None:
    """Eski sürümden kalan tekli giris_parolasi kaydını 'admin' öğretmen hesabına taşır."""
    kayit = veritabani.ayar_oku("giris_parolasi")
    if kayit and not veritabani.ogretmenler():
        veritabani.ogretmen_ekle(
            kullanici_adi="admin",
            ad_soyad="Mukaddes ALAT",
            parola_ozeti=kayit,
            rol="admin",
            brans="Bilişim Teknolojileri",
            yetkiler=["paket_gorunum", "komut_gonder"],
        )


def parola_belirle(parola: str, kullanici_adi: str = "admin",
                   ad_soyad: str = "Mukaddes ALAT",
                   brans: str = "Bilişim Teknolojileri") -> dict:
    ozet = parola_karmasi(parola)
    veritabani.ayar_yaz("giris_parolasi", ozet)
    k_adi = (kullanici_adi or "admin").strip().lower() or "admin"
    mevcut = veritabani.ogretmen_bul(k_adi, gizli_kaldir=False)
    if mevcut:
        return veritabani.ogretmen_guncelle(
            mevcut["id"], ad_soyad=ad_soyad, brans=brans, parola_ozeti=ozet, rol="admin",
            yetkiler=["paket_gorunum", "komut_gonder"])
    return veritabani.ogretmen_ekle(
        kullanici_adi=k_adi, ad_soyad=ad_soyad or "Mukaddes ALAT",
        parola_ozeti=ozet, rol="admin", brans=brans,
        yetkiler=["paket_gorunum", "komut_gonder"])


def ogretmen_dogrula(kullanici_adi: str | None, parola: str) -> dict | None:
    eski_parola_gocu()
    k_adi = (kullanici_adi or "").strip().lower()
    if k_adi:
        ogr = veritabani.ogretmen_bul(k_adi, gizli_kaldir=False)
        if ogr and ogr.get("aktif", True) and parola_dogru_mu(parola, ogr["parola_ozeti"]):
            veritabani.ogretmen_guncelle(ogr["id"], son_giris=veritabani.simdi())
            return veritabani.ogretmen_getir(ogr["id"])
        return None
    # Kullanıcı adı verilmemişse önce admin veya ilk eşleşen öğretmen, sonra eski giris_parolasi
    for satir in veritabani.sorgula("SELECT * FROM ogretmen WHERE aktif=1 ORDER BY rol ASC"):
        if parola_dogru_mu(parola, satir["parola_ozeti"]):
            veritabani.ogretmen_guncelle(satir["id"], son_giris=veritabani.simdi())
            return veritabani.ogretmen_getir(satir["id"])
    kayit = veritabani.ayar_oku("giris_parolasi")
    if kayit is not None and parola_dogru_mu(parola, kayit):
        eski_parola_gocu()
        return veritabani.ogretmen_bul("admin", gizli_kaldir=True) or {
            "id": "ogr_admin", "kullanici_adi": "admin", "ad_soyad": "Mukaddes ALAT",
            "brans": "Bilişim Teknolojileri", "rol": "admin",
            "yetkiler": ["paket_gorunum", "komut_gonder"],
        }
    return None


def giris_dogrula(parola: str, kullanici_adi: str | None = None) -> bool:
    return ogretmen_dogrula(kullanici_adi, parola) is not None


# ---- kurulum kodu ----
# İlk yönetici parolasını yalnızca yetkili yerel kullanıcı belirleyebilsin diye
# (istem §7) kurulum sırasında 0600 izinli bir dosyaya tek kullanımlık kod yazılır;
# Paket kurulumu (postinst) kodu ekrana yazar; masaüstü simgesi ilk açılışta kodu
# yönetici parolasıyla (pkexec) okuyup forma taşır.

def kurulum_kodu_uret() -> str:
    yol = ayarlar.veri_yollari()["kurulum_kodu"]
    yol.parent.mkdir(parents=True, exist_ok=True)
    kod = secrets.token_urlsafe(12)
    yol.write_text(kod, encoding="utf-8")
    try:
        os.chmod(yol, 0o600)
    except OSError:
        pass  # Windows geliştirme ortamı
    return kod


def kurulum_kodu_dogru_mu(kod: str) -> bool:
    yol = ayarlar.veri_yollari()["kurulum_kodu"]
    if not yol.exists():
        return False
    return hmac.compare_digest(yol.read_text(encoding="utf-8").strip(), kod.strip())


def kurulum_kodu_sil() -> None:
    yol = ayarlar.veri_yollari()["kurulum_kodu"]
    if yol.exists():
        yol.unlink()


# ---- oturum çerezi ----

def _imzala(veri: str) -> str:
    imza = hmac.new(_gizli_anahtar(), veri.encode(), hashlib.sha256).hexdigest()
    return f"{veri}.{imza}"


def _imza_dogru_mu(deger: str) -> str | None:
    if "." not in deger:
        return None
    veri, imza = deger.rsplit(".", 1)
    beklenen = hmac.new(_gizli_anahtar(), veri.encode(), hashlib.sha256).hexdigest()
    return veri if hmac.compare_digest(imza, beklenen) else None


def oturum_ac(kullanici_adi: str = "admin") -> str:
    son = int(time.time()) + ayarlar.OTURUM_SURESI_SN
    k_adi = (kullanici_adi or "admin").strip().lower().replace("|", "") or "admin"
    return _imzala(f"oturum|{k_adi}|{secrets.token_hex(8)}|{son}")


def oturum_gecerli_mi(cerez: str | None) -> bool:
    if not cerez:
        return False
    veri = _imza_dogru_mu(cerez)
    if not veri:
        return False
    parcalar = veri.split("|")
    if len(parcalar) not in (3, 4) or parcalar[0] != "oturum":
        return False
    try:
        return int(parcalar[-1]) > time.time()
    except ValueError:
        return False


def oturum_ogretmeni(cerez: str | None) -> dict | None:
    if not oturum_gecerli_mi(cerez):
        return None
    eski_parola_gocu()
    veri = _imza_dogru_mu(cerez) or ""
    parcalar = veri.split("|")
    k_adi = parcalar[1] if len(parcalar) == 4 else "admin"
    ogr = veritabani.ogretmen_bul(k_adi, gizli_kaldir=True)
    if ogr:
        return ogr
    # Veritabanında henüz öğretmen yoksa varsayılan admin döner
    hepsi = veritabani.ogretmenler()
    if hepsi:
        return hepsi[0]
    return {
        "id": "ogr_admin",
        "kullanici_adi": k_adi or "admin",
        "ad_soyad": "Mukaddes ALAT",
        "brans": "Bilişim Teknolojileri",
        "rol": "admin",
        "yetkiler": ["paket_gorunum", "komut_gonder"],
        "aktif": True,
    }


def csrf_uret(cerez: str) -> str:
    return hmac.new(_gizli_anahtar(), f"csrf|{cerez}".encode(), hashlib.sha256).hexdigest()


def csrf_dogru_mu(cerez: str | None, belirtec: str | None) -> bool:
    if not cerez or not belirtec:
        return False
    return hmac.compare_digest(csrf_uret(cerez), belirtec)


# ---- FastAPI bağımlılıkları ----

def oturum_gerekli(istek: Request) -> dict:
    cerez = istek.cookies.get("psy_oturum")
    ogr = oturum_ogretmeni(cerez)
    if not ogr:
        raise HTTPException(status_code=401, detail="Oturum gerekli")
    if istek.method not in ("GET", "HEAD", "OPTIONS"):
        if not csrf_dogru_mu(cerez, istek.headers.get("X-CSRF")):
            raise HTTPException(status_code=403, detail="CSRF doğrulaması başarısız")
    istek.state.ogretmen = ogr
    return ogr


def aktif_ogretmen(istek: Request | None = None) -> dict:
    if istek is not None and hasattr(istek.state, "ogretmen") and istek.state.ogretmen:
        return istek.state.ogretmen
    if istek is not None:
        ogr = oturum_ogretmeni(istek.cookies.get("psy_oturum"))
        if ogr:
            return ogr
    return {
        "id": "ogr_admin",
        "kullanici_adi": "admin",
        "ad_soyad": "Mukaddes ALAT",
        "brans": "Bilişim Teknolojileri",
        "rol": "admin",
        "yetkiler": ["paket_gorunum", "komut_gonder"],
    }


def admin_kontrol(ogretmen: dict) -> None:
    if (ogretmen or {}).get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Bu işlem için Admin Öğretmen yetkisi gereklidir")


def yetki_kontrol(ogretmen: dict, yetki_adi: str) -> None:
    if (ogretmen or {}).get("rol") == "admin":
        return
    yetkiler = (ogretmen or {}).get("yetkiler") or {}
    if not yetkiler.get(yetki_adi):
        raise HTTPException(
            status_code=403,
            detail=f"Bu işlem için '{yetki_adi}' yetkisi veya Admin Öğretmen hesabı gereklidir",
        )


def _izinli_konak_mi(konak: str, ag_acik: bool) -> bool:
    if konak in ("127.0.0.1", "localhost", "[::1]", "::1"):
        return True
    if not ag_acik:
        return False
    import ipaddress
    try:
        ip = ipaddress.ip_address(konak.strip("[]"))
        return ip.is_private or ip.is_loopback
    except ValueError:
        return konak.endswith(".lab") or konak.endswith(".local")


def yerel_istek_mi(istek: Request) -> bool:
    """Origin/Host kontrolü: varsayılan loopback; PSY_AG_ERISIMI=1 veya 0.0.0.0 dinlemede yerel ağa izin verir."""
    ag_acik = ayarlar.DINLEME_ADRESI == "0.0.0.0" or os.environ.get("PSY_AG_ERISIMI") == "1"
    host = (istek.headers.get("host") or "").split(":")[0]
    if not _izinli_konak_mi(host, ag_acik):
        return False
    origin = istek.headers.get("origin")
    if origin:
        o_host = origin.split("//")[-1].split(":")[0]
        if not _izinli_konak_mi(o_host, ag_acik):
            return False
    return True


