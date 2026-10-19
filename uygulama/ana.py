"""FastAPI uygulaması: Türkçe yerel web arayüzü ve API uçları.

Yalnızca loopback'e yayınlanır; her istekte Origin/Host kontrolü yapılır.
Yönetim uçları oturum + CSRF gerektirir (istem §7). Günlük işlerde uzak sudo
parolası istenmez (karar 22); parola yalnız M1-S2/M1-S3 hazırlığında bir kez alınır.
Uygulama giriş parolası ile uzak bilgisayarların sudo parolası ayrı şeylerdir.
"""

import asyncio
import contextvars
import csv
import io
import logging
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import (ag, anahtar, ayarlar, debpaket, envanter, gorunum, guc, guc_ayar, guvenlik, hazirlik,
               isler, kesif, komutlar, paketler, profil, secim, sinif_araclari, tekillestirme,
               temizlik, veritabani, veyon, yedekler, yonetim)
from .odev import ortak as odev_ortak
from .odev import vt as odev_vt
from .odev.yonetim_api import yonlendirici as odev_yonlendirici

log = logging.getLogger("psy")
ARAYUZ_DIZINI = Path(__file__).parent / "arayuz"
_aktif_ogretmen_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("_aktif_ogretmen_ctx", default=None)


@asynccontextmanager
async def yasam_dongusu(_uygulama: FastAPI):
    veritabani.ac()
    veritabani.yarim_isleri_isaretle()
    anahtar.anahtar_uret_veya_yukle()
    odev_vt.ac()
    if not guvenlik.kurulum_tamam_mi():
        kod = guvenlik.kurulum_kodu_uret()
        log.warning("İlk kurulum bekleniyor. Kurulum kodu: %s "
                    "(dosya: %s)", kod, ayarlar.veri_yollari()["kurulum_kodu"])
    yield


uygulama = FastAPI(title="Pardus Sınıf Yönetimi", docs_url=None, redoc_url=None,
                   openapi_url=None, lifespan=yasam_dongusu)


def _yetki_var_mi(ogr: dict | None, anahtar_adi: str) -> bool:
    if not ogr:
        return False
    if ogr.get("rol") == "admin":
        return True
    yetkiler = ogr.get("yetkiler") or []
    if isinstance(yetkiler, dict):
        return bool(yetkiler.get(anahtar_adi))
    return anahtar_adi in yetkiler


def _yol_yetki_hata_mesaji(yol: str, metod: str, ogr: dict | None) -> str | None:
    """Standart öğretmen için rol ve ek yetki sınırlarını denetler."""
    if not ogr or ogr.get("rol") == "admin":
        return None
    # Ek Yetki 1: .deb Paket Kurulumu & Görünüm
    if yol.startswith(("/api/paketler", "/api/gorunum", "/api/duvar-kagidi")):
        if not _yetki_var_mi(ogr, "paket_gorunum"):
            return "Paket kurulumu ve görünüm ayarları için ek yetki veya Admin Öğretmen hesabı gereklidir"
    # Ek Yetki 2: SSH Komut Gönder
    if yol.startswith("/api/komutlar"):
        if not _yetki_var_mi(ogr, "komut_gonder"):
            return "SSH Komut Gönderme menüsü için ek yetki veya Admin Öğretmen hesabı gereklidir"
    # Yalnız Admin Öğretmen uçları
    admin_on_ekleri = ("/api/hazirlik", "/api/tekillestirme", "/api/kesif")
    if yol.startswith(admin_on_ekleri):
        return "Bu kurulum işlemi yalnızca Admin Öğretmen tarafından yapılabilir"
    if yol.startswith("/api/veyon") and metod != "GET":
        return "Veyon kurulum ve anahtar işlemleri yalnızca Admin Öğretmen tarafından yapılabilir"
    if (yol == "/api/cihazlar" and metod == "POST") or yol.startswith(("/api/cihazlar/ice-aktar", "/api/cihazlar/cikar")) or (
            yol.startswith("/api/cihazlar/") and metod == "PATCH"):
        return "Envantere bilgisayar ekleme/çıkarma yalnızca Admin Öğretmen tarafından yapılabilir"
    if yol.startswith(("/api/ogretmenler", "/api/okul", "/api/ayarlar")) and metod != "GET":
        return "Sistem, okul ve öğretmen ayarları yalnızca Admin Öğretmen tarafından değiştirilebilir"
    return None


def _yol_yetki_kontrol(istek_veya_yol: Request | str, metod_veya_ogr: str | dict | None = None,
                       ogr_ucuncu: dict | None = None) -> JSONResponse | None:
    if isinstance(istek_veya_yol, str):
        mesaj = _yol_yetki_hata_mesaji(istek_veya_yol, str(metod_veya_ogr or "GET"), ogr_ucuncu)
        if mesaj:
            raise HTTPException(status_code=403, detail=mesaj)
        return None
    ogr = metod_veya_ogr if isinstance(metod_veya_ogr, dict) else None
    mesaj = _yol_yetki_hata_mesaji(istek_veya_yol.url.path, istek_veya_yol.method, ogr)
    if mesaj:
        return JSONResponse(status_code=403, content={"detail": mesaj})
    return None


@uygulama.middleware("http")
async def yerel_kontrol(istek: Request, devam):
    if not guvenlik.yerel_istek_mi(istek):
        return JSONResponse(status_code=403,
                            content={"detail": "Yalnızca yerel erişime izin verilir"})
    ogr = guvenlik.oturum_ogretmeni(istek.cookies.get("psy_oturum"))
    token = _aktif_ogretmen_ctx.set(ogr)
    try:
        engel = _yol_yetki_kontrol(istek, ogr)
        if engel is not None:
            return engel
        yanit = await devam(istek)
    finally:
        _aktif_ogretmen_ctx.reset(token)
    yanit.headers["X-Content-Type-Options"] = "nosniff"
    yanit.headers["Referrer-Policy"] = "no-referrer"
    # Arayüz dosyaları her açılışta yeniden doğrulanır (ETag): paket güncellemesinden
    # sonra tarayıcı eski betiği önbellekten çalıştırmaz.
    yanit.headers.setdefault("Cache-Control", "no-cache")
    # İndirme uçları kendi (daha sıkı, "sandbox") politikasını koyar; ezilmez.
    yanit.headers.setdefault("Content-Security-Policy",
                             "default-src 'self'; img-src 'self' data:; style-src 'self'")
    return yanit


# ---- istek gövdeleri ----

class KurulumIstek(BaseModel):
    kod: str
    parola: str = Field(min_length=8)
    kullanici_adi: str = "admin"
    ad_soyad: str = "Mukaddes ALAT"
    brans: str = "Bilişim Teknolojileri"
    okul_adi: str | None = None


class GirisIstek(BaseModel):
    parola: str
    kullanici_adi: str | None = None


class CihazListesiIstek(BaseModel):
    cihazlar: list[str]


class SecimOzetIstek(BaseModel):
    cihazlar: list[str]
    islem: str
    canli: bool = True


class OnayliIstek(CihazListesiIstek):
    onay: bool = False


class KesifIstek(BaseModel):
    aralik: str
    haric: list[str] = []
    port: int = 22


class BulunanEkleIstek(BaseModel):
    bulunanlar: list[str]            # "ip:port"
    laboratuvar: str | None = None


class HazirlikIstek(CihazListesiIstek):
    # Yalnız bu işin belleğinde yaşar; veritabanına/loglara yazılmaz.
    parolalar: dict[str, str] = {}   # {"pardus": "...", "hp": "..."}
    ogrenci_olustur: bool = True


class TekillestirmeIstek(BaseModel):
    korunacaklar: dict[str, str]     # cihaz_id -> "pardus" | "hp"
    onay: bool = False


class TemizlikIstek(CihazListesiIstek):
    kapsam: str = "alanlar"                  # 'alanlar' | 'ayarlar' | 'tam'
    alanlar: list[str] = []                  # tüm seçili bilgisayarlar için genel seçim
    istisnalar: dict[str, list[str]] = {}    # cihaz_id -> alanlar; yalnızca bu temizlik için
    oturumlari_kapat: bool = False
    onay: bool = False


class YedekListeIstek(BaseModel):
    cihaz: str


class GeriYukleIstek(BaseModel):
    cihaz: str
    tur: str
    ad: str
    zorla_kapat: bool = False
    onay: bool = False


class CihazEkleIstek(BaseModel):
    ip: str
    port: int = 22
    etiket: str | None = None
    grup: str | None = None
    baglanti_hesabi: str | None = None
    korunan: bool = False


class CihazDuzenleIstek(BaseModel):
    etiket: str | None = None
    grup: str | None = None
    baglanti_hesabi: str | None = None
    korunan: bool | None = None


class IceAktarIstek(BaseModel):
    icerik: str = Field(max_length=2_000_000)
    laboratuvar: str | None = None


class CikarIstek(OnayliIstek):
    anahtari_kaldir: bool = False


class AyarIstek(BaseModel):
    saklama_adedi: int = Field(ge=1, le=30)


class DuvarGorselIstek(BaseModel):
    icerik_b64: str
    uzanti: str  # ".png" veya ".jpg"


class GorunumIstek(OnayliIstek):
    secenekler: dict


class GucIstek(OnayliIstek):
    eylem: str  # 'yeniden_baslat' / 'kapat'


class PaketIstek(OnayliIstek):
    plan_is_id: str | None = None


class VeyonPlanIstek(CihazListesiIstek):
    kip: str = "ikisi"               # 'kur' | 'yapilandir' | 'ikisi'


class VeyonUygulaIstek(OnayliIstek):
    kip: str = "ikisi"
    plan_is_id: str | None = None
    anahtar_uyarisi_onay: bool = False   # öğretmen PC hazırlık sorunlarına rağmen devam


class VeyonPaketSecIstek(BaseModel):
    sha: str


class UykuIstek(OnayliIstek):
    islem: str = "onizle"            # 'onizle' | 'uygula' | 'kaldir'
    ekran_dk: int = 10


class KapatmaPlanIstek(OnayliIstek):
    tur: str                         # 'tek' (bir kez) | 'surekli' (her hafta)
    saat: str                        # SS:DD
    tarih: str | None = None         # YYYY-AA-GG (tek)
    gunler: list[str] = []           # Mon..Sun (surekli)
    uyari_dk: int = 5
    aciklama: str = ""


class KapatmaSilIstek(OnayliIstek):
    idler: list[str] | None = None   # None: seçililerdeki tüm planlar


class EkranKilitIstek(CihazListesiIstek):
    kilitle: bool = True
    mesaj: str = "Lütfen öğretmeninizi dinleyin (Bana Bakın modu aktif)."


class DuyuruIstek(CihazListesiIstek):
    baslik: str = "Öğretmen Duyurusu"
    mesaj: str


class InternetIstek(CihazListesiIstek):
    kisitla: bool = True


class MasaustuUrlIstek(CihazListesiIstek):
    baslik: str
    url: str


class MasaustuDosyaIstek(CihazListesiIstek):
    dosya_adi: str
    icerik_b64: str


class KomutKaydetIstek(BaseModel):
    ad: str
    komut: str
    kategori: str = "Genel"
    aciklama: str = ""
    sudo: bool = True


class KomutCalistirIstek(CihazListesiIstek):
    ad: str = "Bash Komutu"
    komut: str
    sudo: bool = True


class HostsEkleIstek(CihazListesiIstek):
    ip: str
    alan_adi: str


class OkulBilgiIstek(BaseModel):
    ad: str
    alt_baslik: str | None = None
    logo_b64: str | None = None


class OgretmenEkleIstek(BaseModel):
    kullanici_adi: str
    ad_soyad: str
    parola: str = Field(min_length=8)
    rol: str = "standart"
    brans: str = "Bilişim Teknolojileri"
    yetkiler: list[str] = []


class OgretmenGuncelleIstek(BaseModel):
    ad_soyad: str | None = None
    rol: str | None = None
    brans: str | None = None
    yetkiler: list[str] | None = None
    parola: str | None = None


# ---- kimliksiz uçlar ----

@uygulama.get("/api/saglik")
async def saglik():
    return {"durum": "ok", "versiyon": ayarlar.VERSIYON}


@uygulama.get("/api/oturum")
async def oturum_bilgisi(istek: Request):
    cerez = istek.cookies.get("psy_oturum")
    ogr = guvenlik.oturum_ogretmeni(cerez)
    girisli = ogr is not None
    okul = veritabani.okul_bilgisi()
    ogretmen_adaylari = [
        {"kullanici_adi": o["kullanici_adi"], "ad_soyad": o["ad_soyad"],
         "brans": o["brans"], "rol": o["rol"]}
        for o in veritabani.ogretmenler() if o.get("aktif", True)
    ]
    return {
        "kurulum_tamam": guvenlik.kurulum_tamam_mi(),
        "girisli": girisli,
        "csrf": guvenlik.csrf_uret(cerez) if girisli and cerez else None,
        "versiyon": ayarlar.VERSIYON,
        "ogretmen": ogr,
        "okul": okul,
        "ogretmen_listesi": ogretmen_adaylari,
        "ogretmenler_ozet": ogretmen_adaylari,
    }


@uygulama.post("/api/kurulum")
async def kurulum(istek: KurulumIstek):
    if guvenlik.kurulum_tamam_mi():
        raise HTTPException(409, "Kurulum zaten tamamlandı")
    if not guvenlik.kurulum_kodu_dogru_mu(istek.kod):
        raise HTTPException(403, "Kurulum kodu hatalı")
    if istek.okul_adi and istek.okul_adi.strip():
        veritabani.okul_kaydet(istek.okul_adi.strip())
    ogr = guvenlik.parola_belirle(
        istek.parola, kullanici_adi=istek.kullanici_adi,
        ad_soyad=istek.ad_soyad, brans=istek.brans)
    guvenlik.kurulum_kodu_sil()
    return _girisli_yanit(ogr)


@uygulama.post("/api/giris")
async def giris(istek: GirisIstek):
    if not guvenlik.kurulum_tamam_mi():
        raise HTTPException(409, "Önce ilk kurulum tamamlanmalı")
    ogr = guvenlik.ogretmen_dogrula(istek.kullanici_adi, istek.parola)
    if not ogr:
        raise HTTPException(401, "Kullanıcı adı veya parola hatalı")
    return _girisli_yanit(ogr)


def _girisli_yanit(ogr: dict | None = None) -> JSONResponse:
    k_adi = (ogr or {}).get("kullanici_adi") or "admin"
    cerez = guvenlik.oturum_ac(k_adi)
    yanit = JSONResponse({
        "girisli": True,
        "csrf": guvenlik.csrf_uret(cerez),
        "ogretmen": ogr or guvenlik.oturum_ogretmeni(cerez),
    })
    yanit.set_cookie("psy_oturum", cerez, httponly=True, samesite="strict",
                     max_age=ayarlar.OTURUM_SURESI_SN)
    return yanit


@uygulama.post("/api/cikis")
async def cikis():
    yanit = JSONResponse({"girisli": False})
    yanit.delete_cookie("psy_oturum")
    return yanit


# ---- ortak yardımcılar ----

korumali = Depends(guvenlik.oturum_gerekli)


def _is_baslat(tip: str, parametreler: dict, cihaz_idler: list[str], coro_fabrikasi):
    """İşi başlatır. Hedef listesi ve işlemi başlatan öğretmen iş kaydına yazılır:
    sonradan değişen seçim çalışan işi etkilemez (karar 25)."""
    if isler.aktif_is_var_mi():
        raise HTTPException(409, "Devam eden bir iş var; önce bitmesini bekleyin")
    if not cihaz_idler:
        raise HTTPException(422, "Hedef bilgisayar yok")
    cihaz_idler = list(dict.fromkeys(cihaz_idler))
    ipler, hedef_ozeti = [], []
    for cid in cihaz_idler:
        c = veritabani.cihaz(cid)
        if c:
            ipler.append(c["ip"])
            hedef_ozeti.append({"id": cid, "ad": veritabani.cihaz_adi(c), "ip": c["ip"]})
    if not ipler:
        raise HTTPException(422, "Seçili bilgisayarlar envanterde bulunamadı")
    ogr = _aktif_ogretmen_ctx.get() or guvenlik.aktif_ogretmen()
    is_id = veritabani.is_olustur(tip, {**parametreler, "hedefler": hedef_ozeti}, ipler, ogretmen=ogr)
    isler.baslat(is_id, tip, lambda iptal: coro_fabrikasi(is_id, iptal))
    return {"is_id": is_id, "hedef_sayisi": len(ipler)}


def _onay_gerekli(onay: bool, metin: str = "Bu işlem için açık onay gereklidir"):
    if not onay:
        raise HTTPException(422, metin)


@uygulama.get("/api/ozet", dependencies=[korumali])
async def ozet():
    cihazlar = veritabani.cihazlar()
    bos, _ = _ogretmen_disk()
    return {
        "cihaz_sayisi": len(cihazlar),
        "hazir": sum(1 for c in cihazlar if c["sudo_durumu"] == "parolasiz" and c["anahtar_durumu"] == "ok"),
        "korunan": sum(1 for c in cihazlar if c["korunan"]),
        "anahtar_hazir": anahtar.anahtar_var_mi(),
        "aktif_is": isler.aktif_is_var_mi(),
        "ogretmen_bos": bos,
        "versiyon": ayarlar.VERSIYON,
    }


def _ogretmen_disk():
    try:
        kullanim = shutil.disk_usage(ayarlar.VERI_DIZINI)
        return kullanim.free, kullanim.total
    except OSError:
        return None, None


# ---- M1-S1 Bilgisayarlar ----

@uygulama.get("/api/cihazlar", dependencies=[korumali])
async def cihaz_listesi():
    paket = veyon.secili_paket()
    hedef = paket["surum"] if paket else None
    return [secim.gorunum(c, hedef) for c in veritabani.cihazlar()]


@uygulama.post("/api/secim/ozet", dependencies=[korumali])
async def secim_ozeti(istek: SecimOzetIstek):
    if istek.islem not in secim.ISLEMLER:
        raise HTTPException(422, "Bilinmeyen işlem")
    return await secim.ozet(istek.cihazlar, istek.islem, istek.canli)


@uygulama.post("/api/erisim", dependencies=[korumali])
async def erisim(istek: CihazListesiIstek):
    return await secim.erisim_dene(istek.cihazlar)


@uygulama.post("/api/cihazlar", dependencies=[korumali])
async def cihaz_ekle(istek: CihazEkleIstek):
    """Yalnız kayıt oluşturur: bağlantı, hesap değişikliği veya kurulum başlatmaz."""
    try:
        cihaz_id = envanter.cihaz_ekle(istek.ip, istek.port, istek.etiket, istek.grup,
                                       istek.baglanti_hesabi, istek.korunan)
    except envanter.EnvanterHatasi as hata:
        raise HTTPException(422, str(hata))
    return {"id": cihaz_id}


@uygulama.patch("/api/cihazlar/{cihaz_id}", dependencies=[korumali])
async def cihaz_duzenle(cihaz_id: str, istek: CihazDuzenleIstek):
    if isler.aktif_is_var_mi():
        raise HTTPException(409, "Devam eden bir iş var; önce bitmesini bekleyin")
    try:
        return envanter.cihaz_duzenle(cihaz_id, istek.model_dump(exclude_unset=True))
    except envanter.EnvanterHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/cihazlar/ice-aktar/onizle", dependencies=[korumali])
async def ice_aktar_onizle(istek: IceAktarIstek):
    try:
        return envanter.ice_aktar_onizle(istek.icerik, istek.laboratuvar)
    except envanter.EnvanterHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/cihazlar/ice-aktar", dependencies=[korumali])
async def ice_aktar(istek: IceAktarIstek):
    try:
        return envanter.ice_aktar(istek.icerik, istek.laboratuvar)
    except envanter.EnvanterHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/cihazlar/cikar", dependencies=[korumali])
async def cihaz_cikar(istek: CikarIstek):
    _onay_gerekli(istek.onay, "Envanterden çıkarmak için onay gereklidir")
    if isler.aktif_is_var_mi():
        raise HTTPException(409, "Devam eden bir iş var; önce bitmesini bekleyin")
    if istek.anahtari_kaldir:
        return _is_baslat(
            "envanterden_cikar", {}, istek.cihazlar,
            lambda is_id, iptal: envanter.cikar_isi(is_id, istek.cihazlar, iptal))
    silinen = 0
    for cihaz_id in istek.cihazlar:
        if veritabani.cihaz(cihaz_id):
            veritabani.cihaz_sil(cihaz_id)
            silinen += 1
    return {"silinen": silinen}


@uygulama.post("/api/durum-kontrol", dependencies=[korumali])
async def durum_kontrol(istek: CihazListesiIstek):
    return _is_baslat("durum", {}, istek.cihazlar,
                      lambda is_id, iptal: yonetim.durum_isi(is_id, istek.cihazlar, iptal))


@uygulama.get("/api/envanter/ansible", dependencies=[korumali])
async def ansible_envanter():
    """Parolasız Ansible envanteri dışa aktarımı (istem §2, karar 12)."""
    return PlainTextResponse(envanter.ansible_envanteri(),
                             headers={"Content-Disposition": 'attachment; filename="envanter.ini"'})


# ---- M1-S2 SSH ve Hesap Hazırlığı ----

@uygulama.post("/api/hazirlik/kimlik-oku", dependencies=[korumali])
async def kimlik_oku(istek: CihazListesiIstek):
    return _is_baslat("kimlik_oku", {}, istek.cihazlar,
                      lambda is_id, iptal: hazirlik.kimlik_oku_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/hazirlik/kimlik-onayla", dependencies=[korumali])
async def kimlik_onayla(istek: CihazListesiIstek):
    return hazirlik.kimlikleri_onayla(istek.cihazlar)


@uygulama.post("/api/hazirlik/baslat", dependencies=[korumali])
async def hazirlik_baslat(istek: HazirlikIstek):
    parolalar = {h: p for h, p in istek.parolalar.items()
                 if h in ayarlar.YONETIM_HESAPLARI and p}
    # Parolalar iş parametrelerine YAZILMAZ; yalnızca bellekte taşınır.
    return _is_baslat(
        "hazirlik", {"hesaplar": sorted(parolalar), "ogrenci_olustur": istek.ogrenci_olustur},
        istek.cihazlar,
        lambda is_id, iptal: hazirlik.hazirlik_isi(is_id, istek.cihazlar, parolalar,
                                                   istek.ogrenci_olustur, iptal))


@uygulama.post("/api/tekillestirme/onizle", dependencies=[korumali])
async def tekillestirme_onizle(istek: CihazListesiIstek):
    return _is_baslat("tekillestirme_onizleme", {}, istek.cihazlar,
                      lambda is_id, iptal: tekillestirme.onizleme_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/tekillestirme/uygula", dependencies=[korumali])
async def tekillestirme_uygula(istek: TekillestirmeIstek):
    _onay_gerekli(istek.onay, "Hesap silme için açık onay gereklidir")
    if any(k not in ayarlar.YONETIM_HESAPLARI for k in istek.korunacaklar.values()):
        raise HTTPException(422, "Korunacak hesap pardus veya hp olmalı")
    return _is_baslat(
        "tekillestirme", {"korunacaklar": istek.korunacaklar}, list(istek.korunacaklar),
        lambda is_id, iptal: tekillestirme.uygula_isi(is_id, istek.korunacaklar, iptal))


# ---- M1-S3 Ağda Bul ----

@uygulama.get("/api/kesif/ag", dependencies=[korumali])
async def kesif_ag():
    return await asyncio.to_thread(ag.varsayilan_ag)


@uygulama.post("/api/kesif/tara", dependencies=[korumali])
async def kesif_baslat(istek: KesifIstek):
    if isler.aktif_is_var_mi():
        raise HTTPException(409, "Devam eden bir iş var; önce bitmesini bekleyin")
    try:
        adresler = kesif.aralik_genislet(istek.aralik, istek.haric)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    if not adresler:
        raise HTTPException(422, "Kapsamda adres yok")
    is_id = veritabani.is_olustur(
        "kesif", {"aralik": istek.aralik, "adres_sayisi": len(adresler)}, adresler)
    isler.baslat(is_id, "kesif",
                 lambda iptal: kesif.kesif_isi(is_id, adresler, istek.port, iptal))
    return {"is_id": is_id, "hedef_sayisi": len(adresler)}


@uygulama.get("/api/kesif/bulunanlar", dependencies=[korumali])
async def kesif_bulunanlar():
    return kesif.bulunanlar()


@uygulama.post("/api/kesif/ekle", dependencies=[korumali])
async def kesif_ekle(istek: BulunanEkleIstek):
    eklenen = kesif.envantere_ekle(istek.bulunanlar, istek.laboratuvar)
    return {"eklenen": eklenen}


@uygulama.post("/api/kesif/temizle", dependencies=[korumali])
async def kesif_temizle():
    kesif.bulunanlari_temizle()
    return {"tamam": True}


# ---- M2-S1 Profil Temizliği ----

@uygulama.get("/api/temizlik/alanlar", dependencies=[korumali])
async def temizlik_alanlari():
    bos, toplam = _ogretmen_disk()
    return {"katalog": temizlik.katalog(), "genel": temizlik.genel_alanlar(),
            "kapsamlar": profil.KAPSAMLAR, "saklama": veritabani.saklama_adedi(),
            "ogretmen_bos": bos, "ogretmen_toplam": toplam}


def _temizlik_plani(istek: TemizlikIstek) -> dict[str, list[str]]:
    try:
        return temizlik.plan_olustur(istek.cihazlar, istek.alanlar, istek.istisnalar)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/temizlik/onizle", dependencies=[korumali])
async def temizlik_onizle(istek: TemizlikIstek):
    if istek.kapsam == "tam":
        ogr = guvenlik.aktif_ogretmen()
        if ogr and ogr.get("rol") != "admin":
            raise HTTPException(403, "Ev dizininin tamamını sıfırlama yalnızca Admin Öğretmen yetkisindedir.")
    if istek.kapsam in ("ayarlar", "tam"):
        return _is_baslat(
            "sifirlama_onizleme", {"kapsam": istek.kapsam}, istek.cihazlar,
            lambda is_id, iptal: temizlik.sifirlama_olcum_isi(is_id, istek.cihazlar,
                                                              istek.kapsam, iptal))
    if istek.kapsam != "alanlar":
        raise HTTPException(422, "Bilinmeyen kapsam")
    plan = _temizlik_plani(istek)
    return _is_baslat(
        "temizlik_onizleme", {"alanlar": istek.alanlar, "istisna_sayisi": len(istek.istisnalar)},
        istek.cihazlar, lambda is_id, iptal: temizlik.temizlik_isi(is_id, plan, "onizleme", iptal))


@uygulama.post("/api/temizlik/uygula", dependencies=[korumali])
async def temizlik_uygula(istek: TemizlikIstek):
    _onay_gerekli(istek.onay, "Önizlemeden sonra onay gereklidir")
    if istek.kapsam == "tam":
        ogr = guvenlik.aktif_ogretmen()
        if ogr and ogr.get("rol") != "admin":
            raise HTTPException(403, "Ev dizininin tamamını sıfırlama yalnızca Admin Öğretmen yetkisindedir.")
    if istek.kapsam in ("ayarlar", "tam"):
        return _is_baslat(
            "profil_sifirla", {"kapsam": istek.kapsam, "oturumlari_kapat": istek.oturumlari_kapat},
            istek.cihazlar,
            lambda is_id, iptal: profil.profil_sifirla_isi(is_id, istek.cihazlar, istek.kapsam,
                                                           istek.oturumlari_kapat, iptal))
    plan = _temizlik_plani(istek)
    yanit = _is_baslat(
        "temizlik", {"alanlar": istek.alanlar, "istisna_sayisi": len(istek.istisnalar)},
        istek.cihazlar, lambda is_id, iptal: temizlik.temizlik_isi(is_id, plan, "temizle", iptal))
    # Genel seçim bir sonraki temizlik için hatırlanır; istisnalar kaydedilmez.
    temizlik.genel_alanlari_kaydet(istek.alanlar)
    return yanit


@uygulama.post("/api/oturum-kapat", dependencies=[korumali])
async def oturum_kapat(istek: OnayliIstek):
    _onay_gerekli(istek.onay, "Oturum kapatma için açık onay gereklidir")
    return _is_baslat("oturum_kapat", {}, istek.cihazlar,
                      lambda is_id, iptal: profil.oturum_kapat_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/yedek", dependencies=[korumali])
async def yedek_al(istek: CihazListesiIstek):
    return _is_baslat("yedek", {}, istek.cihazlar,
                      lambda is_id, iptal: profil.yedek_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/yedekler/listele", dependencies=[korumali])
async def yedek_listele(istek: YedekListeIstek):
    try:
        return await asyncio.to_thread(yedekler.listele, istek.cihaz)
    except yedekler.YedekHatasi as hata:
        raise HTTPException(409, str(hata))


@uygulama.post("/api/yedekler/geri-yukle", dependencies=[korumali])
async def geri_yukle(istek: GeriYukleIstek):
    _onay_gerekli(istek.onay, "Geri yükleme için açık onay gereklidir")
    try:
        yedekler.istegi_dogrula(istek.tur, istek.ad)
    except yedekler.YedekHatasi as hata:
        raise HTTPException(422, str(hata))
    if not veritabani.cihaz(istek.cihaz):
        raise HTTPException(404, "Bilgisayar bulunamadı")
    return _is_baslat(
        "geri_yukle", {"tur": istek.tur, "ad": istek.ad, "zorla_kapat": istek.zorla_kapat},
        [istek.cihaz],
        lambda is_id, iptal: yedekler.geri_yukle_isi(is_id, istek.cihaz, istek.tur, istek.ad,
                                                     istek.zorla_kapat, iptal))


# ---- M2-S2 Paket Kurulumu ----

def _paket_turu(tur: str) -> str:
    if tur not in ("genel", "veyon"):
        raise HTTPException(422, "Paket türü 'genel' veya 'veyon' olmalı")
    return tur


@uygulama.get("/api/paketler", dependencies=[korumali])
async def paket_listesi(tur: str = "genel"):
    """M2-S2 genel paketleri, M1-S4 Veyon paketlerini görür; listeler ayrıdır."""
    return paketler.paketler(_paket_turu(tur))


@uygulama.post("/api/paketler", dependencies=[korumali])
async def paket_yukle(istek: Request):
    """Gövde: ham .deb baytları. Ad: X-Dosya-Adi (URL kodlu). Tür: X-Paket-Turu (genel/veyon).
    Yol parametresi yoktur."""
    from urllib.parse import unquote
    uzunluk = int(istek.headers.get("content-length") or 0)
    if uzunluk > ayarlar.EN_BUYUK_PAKET:
        raise HTTPException(413, "Paket 1 GB sınırını aşıyor")
    tur = _paket_turu(istek.headers.get("x-paket-turu", "genel"))
    try:
        return await paketler.yukle(istek.stream(), unquote(istek.headers.get("x-dosya-adi", "")), tur)
    except debpaket.PaketHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.delete("/api/paketler/{sha}", dependencies=[korumali])
async def paket_sil(sha: str):
    if not paketler.paket_sil(sha):
        raise HTTPException(404, "Paket bulunamadı")
    return {"tamam": True}


@uygulama.post("/api/paketler/{sha}/plan", dependencies=[korumali])
async def paket_plan(sha: str, istek: CihazListesiIstek):
    paket = paketler.paket_bilgisi(sha)
    if not paket:
        raise HTTPException(404, "Paket bulunamadı")
    return _is_baslat(
        "paket_plan", {"sha256": sha, "paket": paket["paket"], "surum": paket["surum"]},
        istek.cihazlar, lambda is_id, iptal: paketler.plan_isi(is_id, sha, istek.cihazlar, iptal))


@uygulama.post("/api/paketler/{sha}/kur", dependencies=[korumali])
async def paket_kur(sha: str, istek: PaketIstek):
    _onay_gerekli(istek.onay, "Kurulum planı onaylanmalıdır")
    paket = paketler.paket_bilgisi(sha)
    if not paket:
        raise HTTPException(404, "Paket bulunamadı")
    uygun = set(paketler.onaylanabilir_hedefler(istek.plan_is_id or "", sha))
    hedefler = [c for c in istek.cihazlar if c in uygun]
    if not hedefler:
        raise HTTPException(422, "Onaylanan planda kurulabilir bilgisayar yok; önce planı hazırlayın")
    return _is_baslat(
        "paket_kur", {"sha256": sha, "paket": paket["paket"], "surum": paket["surum"],
                      "plan_is_id": istek.plan_is_id}, hedefler,
        lambda is_id, iptal: paketler.kur_isi(is_id, sha, hedefler, iptal))


# ---- M1-S4 Veyon Ayarları ----

@uygulama.get("/api/veyon", dependencies=[korumali])
async def veyon_ozeti():
    return veyon.ozet()


@uygulama.post("/api/veyon/paket-sec", dependencies=[korumali])
async def veyon_paket_sec(istek: VeyonPaketSecIstek):
    try:
        return veyon.paket_sec(istek.sha)
    except veyon.VeyonHatasi as hata:
        raise HTTPException(404, str(hata))


@uygulama.get("/api/veyon/hazirlik", dependencies=[korumali])
async def veyon_hazirlik():
    """Öğretmen PC tarafı (salt okunur): private key var mı, kim okuyabilir, yöntem anahtar mı. Ağa çıkmaz."""
    return await asyncio.to_thread(veyon.ogretmen_hazirligi)


@uygulama.post("/api/veyon/anahtar", dependencies=[korumali])
async def veyon_anahtar_yukle(istek: Request):
    """Gövde: public key dosyası (PEM/DER, ≤ 64 KB). Başlıklar: X-Dosya-Adi, X-Anahtar-Adi, X-Onay."""
    from urllib.parse import unquote
    if int(istek.headers.get("content-length") or 0) > ayarlar.EN_BUYUK_ANAHTAR:
        raise HTTPException(413, "Dosya 64 KB sınırını aşıyor; bu bir public key dosyası olamaz")
    veri = await istek.body()
    try:
        return veyon.anahtar_kaydet(unquote(istek.headers.get("x-anahtar-adi", "")).strip(),
                                    unquote(istek.headers.get("x-dosya-adi", "")), veri,
                                    istek.headers.get("x-onay") == "1")
    except veyon.OnayGerekli as hata:
        return JSONResponse(status_code=409, content={"detail": str(hata), "onay_gerekli": True,
                                                      "mevcut": hata.mevcut})
    except veyon.VeyonHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.delete("/api/veyon/anahtar", dependencies=[korumali])
async def veyon_anahtar_sil():
    return {"silindi": veyon.anahtar_sil(), "not": "Öğrenci bilgisayarlarındaki anahtarlar değişmedi"}


def _veyon_kip(kip: str) -> str:
    if kip not in veyon.KIPLER:
        raise HTTPException(422, "Geçersiz işlem; kur, yapilandir veya ikisi olmalı")
    return kip


def _veyon_on_kosul(kip: str) -> dict:
    paket = veyon.secili_paket()
    anahtar = veyon.anahtar_bilgisi()
    if kip in ("kur", "ikisi") and not paket:
        raise HTTPException(422, "Önce Veyon .deb paketini yükleyin ve kurulacak paketi seçin (M1-S4-B1 / B2)")
    if kip in ("yapilandir", "ikisi") and not anahtar:
        raise HTTPException(422, "Önce Veyon public key dosyasını yükleyin (M1-S4-B4)")
    return {"kip": kip, "sha256": paket["sha256"] if paket else None,
            "surum": paket["surum"] if paket else None,
            "anahtar": {"ad": anahtar["ad"], "cift_kimligi": anahtar["cift_kimligi"]} if anahtar else None}


@uygulama.post("/api/veyon/surumler", dependencies=[korumali])
async def veyon_surumler(istek: CihazListesiIstek):
    """Bilinen envanter kayıtlarını sorgular; ağ taraması yapmaz."""
    return _is_baslat("veyon_surum", {}, istek.cihazlar,
                      lambda is_id, iptal: veyon.surum_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/veyon/plan", dependencies=[korumali])
async def veyon_plan(istek: VeyonPlanIstek):
    parametre = _veyon_on_kosul(_veyon_kip(istek.kip))
    return _is_baslat("veyon_plan", parametre, istek.cihazlar,
                      lambda is_id, iptal: veyon.plan_isi(is_id, istek.cihazlar, istek.kip, iptal))


@uygulama.post("/api/veyon/uygula", dependencies=[korumali])
async def veyon_uygula(istek: VeyonUygulaIstek):
    _onay_gerekli(istek.onay, "Veyon planı onaylanmalıdır")
    parametre = _veyon_on_kosul(_veyon_kip(istek.kip))
    uygun = set(veyon.onaylanabilir_hedefler(istek.plan_is_id or "", istek.kip))
    hedefler = [c for c in istek.cihazlar if c in uygun]
    if not hedefler:
        raise HTTPException(422, "Onaylanan planda uygulanabilir bilgisayar yok; önce planı hazırlayın")
    if istek.kip in ("yapilandir", "ikisi") and not istek.anahtar_uyarisi_onay:
        hazirlik = await asyncio.to_thread(veyon.ogretmen_hazirligi)
        if hazirlik["sorunlar"]:
            raise HTTPException(422, "Öğretmen PC hazırlık denetiminde sorun var: "
                                + " | ".join(hazirlik["sorunlar"])
                                + " — yine de devam etmek için onay penceresindeki kutuyu işaretleyin")
    return _is_baslat("veyon_uygula", {**parametre, "plan_is_id": istek.plan_is_id}, hedefler,
                      lambda is_id, iptal: veyon.uygula_isi(is_id, hedefler, istek.kip, iptal))


@uygulama.post("/api/veyon/dogrula", dependencies=[korumali])
async def veyon_dogrula(istek: CihazListesiIstek):
    return _is_baslat("veyon_dogrula", {}, istek.cihazlar,
                      lambda is_id, iptal: veyon.dogrula_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/veyon/geri-al", dependencies=[korumali])
async def veyon_geri_al(istek: OnayliIstek):
    _onay_gerekli(istek.onay, "Önceki Veyon ayarlarına dönüş onaylanmalıdır")
    return _is_baslat("veyon_geri_al", {}, istek.cihazlar,
                      lambda is_id, iptal: veyon.geri_al_isi(is_id, istek.cihazlar, iptal))


# ---- M2-S3 Görünüm ve Giriş ----

@uygulama.get("/api/gorunum", dependencies=[korumali])
async def gorunum_bilgisi():
    return {"gorsel": gorunum.gorsel_bilgi()}


@uygulama.post("/api/duvar-kagidi/gorsel", dependencies=[korumali])
async def duvar_gorsel_yukle(istek: DuvarGorselIstek):
    if istek.uzanti not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(422, "Yalnızca .png / .jpg kabul edilir")
    try:
        bayt = gorunum.gorsel_kaydet(istek.icerik_b64, istek.uzanti)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return {"tamam": True, "bayt": bayt}


def _gorunum_secenekleri(istek: GorunumIstek) -> dict:
    try:
        return gorunum.secenekleri_dogrula(istek.secenekler)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/gorunum/onizle", dependencies=[korumali])
async def gorunum_onizle(istek: GorunumIstek):
    secenekler = _gorunum_secenekleri(istek)
    return _is_baslat("gorunum_onizleme", {"secenekler": secenekler}, istek.cihazlar,
                      lambda is_id, iptal: gorunum.gorunum_isi(is_id, istek.cihazlar, secenekler,
                                                               "onizle", iptal))


@uygulama.post("/api/gorunum/uygula", dependencies=[korumali])
async def gorunum_uygula(istek: GorunumIstek):
    _onay_gerekli(istek.onay)
    secenekler = _gorunum_secenekleri(istek)
    return _is_baslat("gorunum", {"secenekler": secenekler}, istek.cihazlar,
                      lambda is_id, iptal: gorunum.gorunum_isi(is_id, istek.cihazlar, secenekler,
                                                               "uygula", iptal))


# ---- M2-S4 Güç ----

@uygulama.post("/api/guc", dependencies=[korumali])
async def guc_islemi(istek: GucIstek):
    if istek.eylem not in ("yeniden_baslat", "kapat"):
        raise HTTPException(422, "Geçersiz eylem")
    _onay_gerekli(istek.onay, "Kaydedilmemiş çalışmalar kaybolabilir; onay gereklidir")
    return _is_baslat("guc_" + istek.eylem, {"eylem": istek.eylem}, istek.cihazlar,
                      lambda is_id, iptal: guc.guc_isi(is_id, istek.cihazlar, istek.eylem, iptal))


@uygulama.post("/api/guc/uyku", dependencies=[korumali])
async def guc_uyku(istek: UykuIstek):
    """Uyku/ekran koruyucu ayarı: önizle (salt okunur) / uygula / varsayılana dön."""
    if istek.islem not in ("onizle", "uygula", "kaldir"):
        raise HTTPException(422, "Geçersiz işlem")
    if istek.ekran_dk not in guc_ayar.EKRAN_SURELERI:
        raise HTTPException(422, "Geçersiz ekran koruyucu süresi")
    if istek.islem != "onizle":
        _onay_gerekli(istek.onay)
    tip = {"onizle": "uyku_onizleme", "uygula": "uyku_ayari", "kaldir": "uyku_varsayilan"}[istek.islem]
    return _is_baslat(tip, {"islem": istek.islem, "ekran_dk": istek.ekran_dk}, istek.cihazlar,
                      lambda is_id, iptal: guc_ayar.uyku_isi(is_id, istek.cihazlar, istek.islem,
                                                             istek.ekran_dk, iptal))


# ---- M2-S5 Zamanlı Kapatma ----

@uygulama.post("/api/kapatma/oku", dependencies=[korumali])
async def kapatma_oku(istek: CihazListesiIstek):
    return _is_baslat("kapatma_oku", {}, istek.cihazlar,
                      lambda is_id, iptal: guc_ayar.oku_isi(is_id, istek.cihazlar, iptal))


@uygulama.post("/api/kapatma/ekle", dependencies=[korumali])
async def kapatma_ekle(istek: KapatmaPlanIstek):
    _onay_gerekli(istek.onay, "Zamanlı kapatma planı onaylanmalıdır")
    try:
        plan = guc_ayar.plan_olustur(istek.tur, istek.saat, istek.tarih, istek.gunler, istek.uyari_dk,
                                     istek.aciklama)
    except guc_ayar.GucHatasi as hata:
        raise HTTPException(422, str(hata))
    return _is_baslat("kapatma_ekle", {"plan": plan}, istek.cihazlar,
                      lambda is_id, iptal: guc_ayar.ekle_isi(is_id, istek.cihazlar, plan, iptal))


@uygulama.post("/api/kapatma/sil", dependencies=[korumali])
async def kapatma_sil(istek: KapatmaSilIstek):
    _onay_gerekli(istek.onay)
    idler = "hepsi" if not istek.idler else [i for i in istek.idler if re.match(r"^[a-z0-9]{4,16}$", i)]
    return _is_baslat("kapatma_sil", {"idler": idler}, istek.cihazlar,
                      lambda is_id, iptal: guc_ayar.sil_isi(is_id, istek.cihazlar, idler, iptal))


@uygulama.post("/api/kapatma/iptal", dependencies=[korumali])
async def kapatma_iptal(istek: OnayliIstek):
    _onay_gerekli(istek.onay)
    return _is_baslat("kapatma_iptal", {}, istek.cihazlar,
                      lambda is_id, iptal: guc_ayar.iptal_isi(is_id, istek.cihazlar, iptal))


# ---- M1-S1 / M3-S1 Sınıf Hızlı Araçlar ----

@uygulama.post("/api/sinif/ekran-kilit", dependencies=[korumali])
async def sinif_ekran_kilit(istek: EkranKilitIstek):
    tip = "sinif_ekran_kilitle" if istek.kilitle else "sinif_ekran_ac"
    return _is_baslat(
        tip, {"kilitle": istek.kilitle, "mesaj": istek.mesaj}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "ekran_kilit",
            {"kilitle": istek.kilitle, "mesaj": istek.mesaj}, iptal))


@uygulama.post("/api/sinif/duyuru", dependencies=[korumali])
async def sinif_duyuru(istek: DuyuruIstek):
    return _is_baslat(
        "sinif_duyuru", {"baslik": istek.baslik, "mesaj": istek.mesaj}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "duyuru",
            {"baslik": istek.baslik, "mesaj": istek.mesaj}, iptal))


@uygulama.post("/api/sinif/internet", dependencies=[korumali])
async def sinif_internet(istek: InternetIstek):
    tip = "sinif_internet_kisitla" if istek.kisitla else "sinif_internet_ac"
    return _is_baslat(
        tip, {"kisitla": istek.kisitla}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "internet", {"kisitla": istek.kisitla}, iptal))


@uygulama.post("/api/sinif/masaustu-url", dependencies=[korumali])
async def sinif_masaustu_url(istek: MasaustuUrlIstek):
    return _is_baslat(
        "sinif_masaustu_url", {"baslik": istek.baslik, "url": istek.url}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "masaustu_url",
            {"baslik": istek.baslik, "url": istek.url}, iptal))


@uygulama.post("/api/sinif/masaustu-dosya", dependencies=[korumali])
async def sinif_masaustu_dosya(istek: MasaustuDosyaIstek):
    return _is_baslat(
        "sinif_masaustu_dosya", {"dosya_adi": istek.dosya_adi}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "masaustu_dosya",
            {"dosya_adi": istek.dosya_adi, "icerik_b64": istek.icerik_b64}, iptal))


# ---- M2-S6 Komut Gönder (SSH Komut Merkezi) ----

@uygulama.get("/api/komutlar", dependencies=[korumali])
async def komut_listesi():
    return veritabani.kayitli_komutlar()


@uygulama.post("/api/komutlar", dependencies=[korumali])
async def komut_kaydet(istek: KomutKaydetIstek):
    try:
        komutlar.komut_dogrula(istek.komut)
        ogr = guvenlik.aktif_ogretmen() or {}
        return veritabani.komut_ekle(
            ad=istek.ad, komut=istek.komut, kategori=istek.kategori,
            aciklama=istek.aciklama, sudo=istek.sudo,
            olusturan=ogr.get("kullanici_adi", "admin"))
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.delete("/api/komutlar/{komut_id}", dependencies=[korumali])
async def komut_sil_uc(komut_id: str):
    try:
        if not veritabani.komut_sil(komut_id):
            raise HTTPException(404, "Komut bulunamadı")
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return {"tamam": True}


@uygulama.post("/api/komutlar/calistir", dependencies=[korumali])
async def komut_calistir_uc(istek: KomutCalistirIstek):
    try:
        temiz = komutlar.komut_dogrula(istek.komut)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return _is_baslat(
        "ssh_komut", {"ad": istek.ad or "Bash Komutu", "komut": temiz, "sudo": istek.sudo},
        istek.cihazlar,
        lambda is_id, iptal: komutlar.komut_isi(
            is_id, istek.cihazlar, temiz, istek.sudo, istek.ad or "Bash Komutu", iptal))


@uygulama.post("/api/komutlar/hosts-ekle", dependencies=[korumali])
async def komut_hosts_ekle_uc(istek: HostsEkleIstek):
    try:
        ip, alan_adi = komutlar.hosts_dogrula(istek.ip, istek.alan_adi)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return _is_baslat(
        "hosts_ekle", {"ip": ip, "alan_adi": alan_adi}, istek.cihazlar,
        lambda is_id, iptal: komutlar.hosts_ekle_isi(is_id, istek.cihazlar, ip, alan_adi, iptal))


# ---- M4-S1 İşlem Geçmişi ----

@uygulama.get("/api/isler", dependencies=[korumali])
async def is_listesi():
    return [dict(s) for s in veritabani.sorgula(
        "SELECT id, tip, durum, baslangic, bitis, ozet, "
        "ogretmen_kullanici, ogretmen_ad, ogretmen_rol FROM is_kaydi "
        "ORDER BY baslangic DESC LIMIT 100")]


@uygulama.get("/api/isler/{is_id}", dependencies=[korumali])
async def is_detay(is_id: str):
    kayit = veritabani.is_durumu(is_id)
    if not kayit:
        raise HTTPException(404, "İş bulunamadı")
    return kayit


@uygulama.get("/api/isler/{is_id}/csv", dependencies=[korumali])
async def is_csv(is_id: str):
    """Hassas bilgi içermeyen sonuç dışa aktarımı (istem §10)."""
    kayit = veritabani.is_durumu(is_id)
    if not kayit:
        raise HTTPException(404, "İş bulunamadı")
    tampon = io.StringIO()
    yazici = csv.writer(tampon, delimiter=";")
    yazici.writerow(["İşlem", "Öğretmen", "Hedef", "Sonuç", "Aşama", "Mesaj", "Zaman"])
    ogr_etiket = kayit.get("ogretmen_ad") or kayit.get("ogretmen_kullanici") or "-"
    for h in kayit["hedefler"]:
        yazici.writerow([kayit["tip"], ogr_etiket, h["hedef"], h["durum"], h["asama"] or "",
                         h["mesaj"] or "", h["zaman"] or ""])
    return Response("﻿" + tampon.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="islem-{is_id}.csv"'})


@uygulama.post("/api/isler/{is_id}/iptal", dependencies=[korumali])
async def is_iptal(is_id: str):
    if not isler.iptal_iste(is_id):
        raise HTTPException(409, "İş çalışmıyor veya zaten bitti")
    return {"tamam": True,
            "not": "İptal, güvenli noktada durdurur; başlamış adımları geri almaz"}


# ---- M5-S1 Ayarlar & M5-S2 Okul / Öğretmen Yönetimi ----

@uygulama.get("/api/ayarlar", dependencies=[korumali])
async def ayarlari_oku():
    return {"saklama_adedi": veritabani.saklama_adedi(), "versiyon": ayarlar.VERSIYON,
            "odev_dizini": str(odev_ortak.ODEV_DIZINI), "okul": veritabani.okul_bilgisi()}


@uygulama.post("/api/ayarlar", dependencies=[korumali])
async def ayarlari_yaz(istek: AyarIstek):
    veritabani.ayar_yaz("saklama_adedi", str(istek.saklama_adedi))
    return {"saklama_adedi": istek.saklama_adedi}


@uygulama.get("/api/okul")
async def okul_oku():
    return veritabani.okul_bilgisi()


@uygulama.post("/api/okul", dependencies=[korumali])
async def okul_yaz(istek: OkulBilgiIstek):
    return veritabani.okul_kaydet(istek.ad, istek.alt_baslik, istek.logo_b64)


@uygulama.get("/api/ogretmenler", dependencies=[korumali])
async def ogretmen_listesi_uc():
    return veritabani.ogretmenler()


@uygulama.post("/api/ogretmenler", dependencies=[korumali])
async def ogretmen_ekle_uc(istek: OgretmenEkleIstek):
    try:
        ozet = guvenlik.bcrypt_ozet(istek.parola)
        return veritabani.ogretmen_ekle(
            kullanici_adi=istek.kullanici_adi, ad_soyad=istek.ad_soyad,
            parola_ozeti=ozet, rol=istek.rol, brans=istek.brans, yetkiler=istek.yetkiler)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.patch("/api/ogretmenler/{ogretmen_id}", dependencies=[korumali])
async def ogretmen_guncelle_uc(ogretmen_id: str, istek: OgretmenGuncelleIstek):
    try:
        ozet = guvenlik.bcrypt_ozet(istek.parola) if istek.parola else None
        return veritabani.ogretmen_guncelle(
            ogretmen_id, ad_soyad=istek.ad_soyad, rol=istek.rol,
            brans=istek.brans, yetkiler=istek.yetkiler, parola_ozeti=ozet)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.delete("/api/ogretmenler/{ogretmen_id}", dependencies=[korumali])
async def ogretmen_sil_uc(ogretmen_id: str):
    try:
        if not veritabani.ogretmen_sil(ogretmen_id):
            raise HTTPException(404, "Öğretmen bulunamadı")
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return {"tamam": True}


# ---- ödev teslim (öğretmen tarafı; öğrenci portalı ayrı süreçtir) ----

uygulama.include_router(odev_yonlendirici, dependencies=[korumali])


# ---- arayüz ----

@uygulama.get("/")
async def anasayfa():
    return FileResponse(ARAYUZ_DIZINI / "index.html")


uygulama.mount("/statik", StaticFiles(directory=ARAYUZ_DIZINI), name="statik")


def calistir():
    import uvicorn
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(uygulama, host=ayarlar.DINLEME_ADRESI, port=ayarlar.DINLEME_PORTU,
                access_log=False)


if __name__ == "__main__":
    calistir()
