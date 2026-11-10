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
               isler, kesif, komutlar, paketler, profil, secim, sinif_araclari, sistem_yedek,
               tekillestirme, temizlik, veritabani, veyon, yedekler, yonetim)
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
    # Ek Yetki 2: SSH Komut Gönder & Komut Mağazası
    if yol.startswith(("/api/komutlar", "/api/magaza")):
        if not _yetki_var_mi(ogr, "komut_gonder"):
            return "SSH Komut ve Mağaza işlemleri için ek yetki veya Admin Öğretmen hesabı gereklidir"
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
    if yol.startswith("/api/sistem-yedek"):
        return "Sistem yedeği alma ve geri yükleme işlemleri yalnızca Admin Öğretmen tarafından yapılabilir"
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
    yonetim_kullanici: str | None = "pardus"
    yonetim_parola: str | None = None


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
    odev_koru: bool = True
    haric_klasor: str | None = None


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
    hostname: str | None = None
    grup: str | None = None
    baglanti_hesabi: str | None = None
    korunan: bool = False


class CihazDuzenleIstek(BaseModel):
    ip: str | None = None
    port: int | None = None
    etiket: str | None = None
    hostname: str | None = None
    grup: str | None = None
    baglanti_hesabi: str | None = None
    korunan: bool | None = None


class IceAktarIstek(BaseModel):
    icerik: str = Field(max_length=2_000_000)
    laboratuvar: str | None = None


class CikarIstek(OnayliIstek):
    anahtari_kaldir: bool = False


class YonetimHesaplariIstek(BaseModel):
    hesaplar: list[dict]


class TestBaglantiIstek(BaseModel):
    ip: str
    kullanici: str = "pardus"
    parola: str = ""
    port: int = 22


class ParolaDegistirIstek(OnayliIstek):
    cihazlar: list[str]
    kullanici: str = "pardus"
    yeni_parola: str


class AyarIstek(BaseModel):
    saklama_adedi: int = Field(ge=1, le=30)


class DuvarGorselIstek(BaseModel):
    icerik_b64: str
    uzanti: str  # ".png" veya ".jpg"
    ad: str | None = None


class DuvarGaleriSecIstek(BaseModel):
    id: str


class GorunumIstek(OnayliIstek):
    secenekler: dict


class GucIstek(OnayliIstek):
    eylem: str  # 'yeniden_baslat' / 'kapat'


class PaketIstek(OnayliIstek):
    plan_is_id: str | None = None


class RepoAraIstek(BaseModel):
    sorgu: str
    cihaz: str | None = None


class RepoKuruluListeleIstek(BaseModel):
    cihaz: str | None = None
    tum_paketler: bool = False


class RepoKurIstek(OnayliIstek):
    paketler: list[str]
    guncelle: bool = True


class RepoKaldirIstek(OnayliIstek):
    paketler: list[str]
    artiklari_temizle: bool = False


class VeyonPlanIstek(CihazListesiIstek):
    kip: str = "ikisi"               # 'kur' | 'yapilandir' | 'ikisi'
    uzman: dict | None = None


class VeyonUygulaIstek(OnayliIstek):
    kip: str = "ikisi"
    plan_is_id: str | None = None
    anahtar_uyarisi_onay: bool = False   # öğretmen PC hazırlık sorunlarına rağmen devam
    uzman: dict | None = None


class VeyonPaketSecIstek(BaseModel):
    sha: str


class UykuIstek(OnayliIstek):
    islem: str = "onizle"            # 'onizle' | 'uygula' | 'kaldir'
    ekran_dk: int = 0


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
    otomatik_ac: bool = False
    hosts_ip: str | None = None
    hosts_ad: str | None = None
    klasor: str = "Odevler"


class MasaustuDosyaIstek(CihazListesiIstek):
    dosya_adi: str
    icerik_b64: str
    klasor: str = "Odevler"


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


class AracCalistirIstek(CihazListesiIstek):
    arac_id: str
    parametreler: dict = Field(default_factory=dict)


class AracSabitleIstek(BaseModel):
    arac_id: str
    sabitle: bool = True


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
    if istek.yonetim_kullanici and istek.yonetim_kullanici.strip():
        veritabani.yonetim_hesaplari_kaydet([{
            "kullanici": istek.yonetim_kullanici.strip(),
            "parola": istek.yonetim_parola or "",
            "oncelik": 1
        }])
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
                                       istek.baglanti_hesabi, istek.korunan, istek.hostname)
    except envanter.EnvanterHatasi as hata:
        raise HTTPException(422, str(hata))
    return {"id": cihaz_id}


@uygulama.patch("/api/cihazlar/{cihaz_id}", dependencies=[korumali])
async def cihaz_duzenle(cihaz_id: str, istek: CihazDuzenleIstek):
    if isler.aktif_is_var_mi():
        raise HTTPException(409, "Devam eden bir iş var; önce bitmesini bekleyin")
    try:
        return await asyncio.to_thread(envanter.cihaz_duzenle, cihaz_id, istek.model_dump(exclude_unset=True))
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
    yonetim_listesi = ayarlar.yonetim_hesap_adlari()
    parolalar = {h: p for h, p in istek.parolalar.items()
                 if (h in yonetim_listesi or h in ayarlar.YONETIM_HESAPLARI) and p}
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
    yonetim_listesi = ayarlar.yonetim_hesap_adlari()
    if any(k not in yonetim_listesi and k not in ayarlar.YONETIM_HESAPLARI for k in istek.korunacaklar.values()):
        raise HTTPException(422, f"Korunacak hesap tanımlı yönetim hesaplarından biri olmalı ({', '.join(yonetim_listesi)})")
    return _is_baslat(
        "tekillestirme", {"korunacaklar": istek.korunacaklar}, list(istek.korunacaklar),
        lambda is_id, iptal: tekillestirme.uygula_isi(is_id, istek.korunacaklar, iptal))


# ---- Yönetim Hesapları & Toplu Parola Yönetimi ----

@uygulama.get("/api/yonetim/hesaplar", dependencies=[korumali])
async def yonetim_hesaplari_al():
    return veritabani.yonetim_hesaplari_al()


@uygulama.post("/api/yonetim/hesaplar", dependencies=[korumali])
async def yonetim_hesaplari_kaydet(istek: YonetimHesaplariIstek):
    ogr = guvenlik.aktif_ogretmen()
    if ogr and ogr.get("rol") != "admin":
        raise HTTPException(403, "Yönetim hesaplarını değiştirme yetkisi yalnızca Admin Öğretmen'e aittir.")
    return veritabani.yonetim_hesaplari_kaydet(istek.hesaplar)


@uygulama.post("/api/yonetim/test_baglanti", dependencies=[korumali])
async def yonetim_test_baglanti(istek: TestBaglantiIstek):
    ip = istek.ip.strip()
    kullanici = istek.kullanici.strip()
    parola = istek.parola
    port = istek.port or 22
    if not ip:
        raise HTTPException(422, "IP adresi gereklidir")

    def _test():
        try:
            kimlik = ssh_araclari.host_kimligi_topla(ip, port)
        except Exception as e:
            return {"basarili": False, "ssh": False, "sudo": False, "mesaj": f"Host anahtarı okunamadı / SSH kapalı: {e}"}

        try:
            istemci = ssh_araclari.parola_ile_baglan(ip, port, kullanici, parola, kimlik["tip"], kimlik["b64"])
        except Exception as e:
            return {"basarili": False, "ssh": False, "sudo": False, "mesaj": f"SSH giriş hatası: {e}"}

        try:
            sudo_durum = ssh_araclari.sudo_dogrula(istemci, parola)
            parolasiz = sudo_durum == "parolasiz"
            sudo_ok = sudo_durum in ("parolasiz", "parola_gerekli")
            istemci.close()
            if sudo_ok:
                sudo_not = " (Parolasız Sudo aktif)" if parolasiz else " (Parolalı Sudo başarılı)"
                return {"basarili": True, "ssh": True, "sudo": True, "parolasiz": parolasiz,
                        "mesaj": f"'{kullanici}' ile SSH ve Sudo yetkisi doğrulandı{sudo_not}"}
            else:
                return {"basarili": False, "ssh": True, "sudo": False,
                        "mesaj": f"'{kullanici}' ile SSH başarılı ancak Sudo yetkisi yok!"}
        except Exception as e:
            try:
                istemci.close()
            except Exception:
                pass
            return {"basarili": False, "ssh": True, "sudo": False, "mesaj": f"Sudo deneme hatası: {e}"}

    return await asyncio.to_thread(_test)


@uygulama.post("/api/yonetim/parola_degistir", dependencies=[korumali])
async def yonetim_parola_degistir(istek: ParolaDegistirIstek):
    _onay_gerekli(istek.onay, "Parola değiştirme için onay gereklidir")
    ogr = guvenlik.aktif_ogretmen()
    if ogr and ogr.get("rol") != "admin":
        raise HTTPException(403, "Yönetici parolasını değiştirme yetkisi yalnızca Admin Öğretmen'e aittir.")
    if len(istek.yeni_parola) < 4:
        raise HTTPException(422, "Yeni parola en az 4 karakter olmalıdır.")

    def _is_yurut(is_id, iptal):
        sinir = asyncio.Semaphore(4)

        async def _tek(cid):
            if iptal.is_set():
                return
            cihaz = veritabani.cihaz(cid)
            if not cihaz:
                return
            ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
            try:
                istemci = yonetim.baglan(cihaz)
            except Exception as e:
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — Bağlanılamadı: {e}")
                return
            try:
                girdi = f"{istek.kullanici}:{istek.yeni_parola}\n"
                rc, stdout, stderr = ssh_araclari.sudo_komut(istemci, ["chpasswd"], girdi=girdi, zaman=15)
                if rc == 0:
                    veritabani.hedef_guncelle(is_id, ip, "basarili", "parola", f"{ad} — '{istek.kullanici}' parolası güncellendi")
                else:
                    veritabani.hedef_guncelle(is_id, ip, "basarisiz", "parola", f"{ad} — chpasswd hatası: {stderr}")
            except Exception as e:
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "hata", f"{ad} — {e}")
            finally:
                istemci.close()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(*(_tek(c) for c in istek.cihazlar)))

    return _is_baslat(
        "parola_degistir", {"kullanici": istek.kullanici, "hedef_sayisi": len(istek.cihazlar)},
        istek.cihazlar,
        lambda is_id, iptal: asyncio.to_thread(_is_yurut, is_id, iptal)
    )


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
    haric = [istek.haric_klasor] if istek.haric_klasor else None
    return _is_baslat(
        "temizlik_onizleme", {"alanlar": istek.alanlar, "istisna_sayisi": len(istek.istisnalar), "odev_koru": istek.odev_koru},
        istek.cihazlar, lambda is_id, iptal: temizlik.temizlik_isi(is_id, plan, "onizleme", iptal, odev_koru=istek.odev_koru, haric_adlar=haric))


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
    haric = [istek.haric_klasor] if istek.haric_klasor else None
    yanit = _is_baslat(
        "temizlik", {"alanlar": istek.alanlar, "istisna_sayisi": len(istek.istisnalar), "odev_koru": istek.odev_koru},
        istek.cihazlar, lambda is_id, iptal: temizlik.temizlik_isi(is_id, plan, "temizle", iptal, odev_koru=istek.odev_koru, haric_adlar=haric))
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


@uygulama.get("/api/paketler/repo/katalog", dependencies=[korumali])
async def repo_katalog():
    return paketler.repo_katalog()


@uygulama.post("/api/paketler/repo/ara", dependencies=[korumali])
async def repo_ara(istek: RepoAraIstek):
    try:
        return await asyncio.to_thread(paketler.repo_ara, istek.sorgu, istek.cihaz)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/paketler/repo/kurulu-listele", dependencies=[korumali])
async def repo_kurulu_listele(istek: RepoKuruluListeleIstek):
    try:
        return await asyncio.to_thread(paketler.kurulu_listele, istek.cihaz, istek.tum_paketler)
    except ValueError as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/paketler/repo/kur", dependencies=[korumali])
async def repo_kur(istek: RepoKurIstek):
    _onay_gerekli(istek.onay, "Depodan paket kurulumu onaylanmalıdır")
    try:
        temiz_paketler = paketler.paket_listesi_dogrula(istek.paketler, kaldirma_mi=False)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    uygun_cihazlar, _ = secim.hedefleri_ayir(istek.cihazlar, "paket")
    hedefler = [c["id"] for c in uygun_cihazlar]
    if not hedefler:
        raise HTTPException(422, "Seçimde paket kurulumuna uygun bilgisayar yok")
    return _is_baslat(
        "repo_kur", {"paketler": temiz_paketler, "guncelle": istek.guncelle}, hedefler,
        lambda is_id, iptal: paketler.repo_kur_isi(is_id, temiz_paketler, istek.guncelle, hedefler, iptal))


@uygulama.post("/api/paketler/repo/kaldir", dependencies=[korumali])
async def repo_kaldir(istek: RepoKaldirIstek):
    _onay_gerekli(istek.onay, "Uygulama kaldırma işlemi onaylanmalıdır")
    try:
        temiz_paketler = paketler.paket_listesi_dogrula(istek.paketler, kaldirma_mi=True)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    uygun_cihazlar, _ = secim.hedefleri_ayir(istek.cihazlar, "paket")
    hedefler = [c["id"] for c in uygun_cihazlar]
    if not hedefler:
        raise HTTPException(422, "Seçimde işlem yapmaya uygun bilgisayar yok")
    return _is_baslat(
        "repo_kaldir", {"paketler": temiz_paketler, "artiklari_temizle": istek.artiklari_temizle}, hedefler,
        lambda is_id, iptal: paketler.repo_kaldir_isi(is_id, temiz_paketler, istek.artiklari_temizle, hedefler, iptal))


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
    _onay_gerekli(istek.onay, "Kurulum onaylanmalıdır")
    paket = paketler.paket_bilgisi(sha)
    if not paket:
        raise HTTPException(404, "Paket bulunamadı")
    if istek.plan_is_id:
        uygun = set(paketler.onaylanabilir_hedefler(istek.plan_is_id, sha))
        hedefler = [c for c in istek.cihazlar if c in uygun]
        if not hedefler:
            raise HTTPException(422, "Onaylanan planda kurulabilir bilgisayar yok")
    else:
        uygun_cihazlar, _ = secim.hedefleri_ayir(istek.cihazlar, "paket")
        hedefler = [c["id"] for c in uygun_cihazlar]
        if not hedefler:
            raise HTTPException(422, "Seçimde kuruluma uygun bilgisayar yok")
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
                      lambda is_id, iptal: veyon.plan_isi(is_id, istek.cihazlar, istek.kip, iptal, istek.uzman))


@uygulama.post("/api/veyon/uygula", dependencies=[korumali])
async def veyon_uygula(istek: VeyonUygulaIstek):
    _onay_gerekli(istek.onay, "Veyon işlemi onaylanmalıdır")
    parametre = _veyon_on_kosul(_veyon_kip(istek.kip))
    if istek.plan_is_id:
        uygun = set(veyon.onaylanabilir_hedefler(istek.plan_is_id, istek.kip))
        hedefler = [c for c in istek.cihazlar if c in uygun]
        if not hedefler:
            raise HTTPException(422, "Onaylanan planda uygulanabilir bilgisayar yok")
    else:
        uygun_cihazlar, _ = secim.hedefleri_ayir(istek.cihazlar, "veyon")
        hedefler = [c["id"] for c in uygun_cihazlar]
        if not hedefler:
            raise HTTPException(422, "Seçimde Veyon işlemine uygun bilgisayar yok")
    if istek.kip in ("yapilandir", "ikisi") and not istek.anahtar_uyarisi_onay:
        hazirlik = await asyncio.to_thread(veyon.ogretmen_hazirligi)
        if hazirlik["sorunlar"]:
            raise HTTPException(422, "Öğretmen PC hazırlık denetiminde sorun var: "
                                + " | ".join(hazirlik["sorunlar"])
                                + " — yine de devam etmek için onay penceresindeki kutuyu işaretleyin")
    return _is_baslat("veyon_uygula", {**parametre, "plan_is_id": istek.plan_is_id}, hedefler,
                      lambda is_id, iptal: veyon.uygula_isi(is_id, hedefler, istek.kip, iptal, istek.uzman))


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
    return gorunum.galeri_listele()


@uygulama.post("/api/duvar-kagidi/gorsel", dependencies=[korumali])
async def duvar_gorsel_yukle(istek: DuvarGorselIstek):
    if istek.uzanti not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(422, "Yalnızca .png / .jpg kabul edilir")
    try:
        galeri = gorunum.galeri_ekle(istek.icerik_b64, istek.uzanti, istek.ad)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    bayt = (galeri.get("gorsel") or {}).get("bayt", 0)
    return {"tamam": True, "bayt": bayt, "galeri": galeri, **galeri}


@uygulama.post("/api/duvar-kagidi/galeri/sec", dependencies=[korumali])
async def duvar_galeri_sec(istek: DuvarGaleriSecIstek):
    try:
        galeri = gorunum.galeri_sec(istek.id)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return {"tamam": True, "galeri": galeri, **galeri}


@uygulama.delete("/api/duvar-kagidi/galeri/{oge_id}", dependencies=[korumali])
async def duvar_galeri_sil(oge_id: str):
    try:
        galeri = gorunum.galeri_sil(oge_id)
    except ValueError as hata:
        raise HTTPException(422, str(hata))
    return {"tamam": True, "silindi": True, "galeri": galeri, **galeri}


@uygulama.get("/api/duvar-kagidi/galeri/{oge_id}/indir", dependencies=[korumali])
async def duvar_galeri_indir(oge_id: str):
    yol = gorunum.galeri_dosya_yolu(oge_id)
    if not yol:
        raise HTTPException(404, "Duvar kağıdı bulunamadı")
    media = "image/jpeg" if yol.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return FileResponse(yol, media_type=media)


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
    ek_param = {
        "baslik": istek.baslik,
        "url": istek.url,
        "otomatik_ac": istek.otomatik_ac,
        "klasor": istek.klasor or "Odevler",
    }
    if istek.hosts_ip:
        ek_param["hosts_ip"] = istek.hosts_ip
    if istek.hosts_ad:
        ek_param["hosts_ad"] = istek.hosts_ad
    return _is_baslat(
        "sinif_masaustu_url", {"baslik": istek.baslik, "url": istek.url, "otomatik_ac": istek.otomatik_ac, "klasor": istek.klasor}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "masaustu_url", ek_param, iptal))


@uygulama.post("/api/sinif/masaustu-dosya", dependencies=[korumali])
async def sinif_masaustu_dosya(istek: MasaustuDosyaIstek):
    return _is_baslat(
        "sinif_masaustu_dosya", {"dosya_adi": istek.dosya_adi, "klasor": istek.klasor}, istek.cihazlar,
        lambda is_id, iptal: sinif_araclari.sinif_isi(
            is_id, istek.cihazlar, "masaustu_dosya",
            {"dosya_adi": istek.dosya_adi, "icerik_b64": istek.icerik_b64, "klasor": istek.klasor or "Odevler"}, iptal))


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


# ---- Komut Mağazası API ----

@uygulama.get("/api/magaza/katalog", dependencies=[korumali])
async def magaza_katalog_uc():
    return komutlar.resmi_magaza_katalogu()


@uygulama.post("/api/magaza/guncelle", dependencies=[korumali])
async def magaza_guncelle_uc():
    return await komutlar.magaza_katalogu_guncelle()


@uygulama.get("/api/magaza/sabitler", dependencies=[korumali])
async def magaza_sabitler_uc():
    return komutlar.sabit_araclari_al()


@uygulama.post("/api/magaza/sabitle", dependencies=[korumali])
async def magaza_sabitle_uc(istek: AracSabitleIstek):
    mevcut = komutlar.sabit_araclari_al()
    if istek.sabitle:
        if istek.arac_id not in mevcut:
            mevcut.append(istek.arac_id)
    else:
        mevcut = [x for x in mevcut if x != istek.arac_id]
    komutlar.sabit_arac_kaydet(mevcut)
    return {"sabitler": mevcut}


@uygulama.post("/api/magaza/calistir", dependencies=[korumali])
async def magaza_arac_calistir_uc(istek: AracCalistirIstek):
    arac = komutlar.magaza_araci_getir(istek.arac_id)
    if not arac:
        raise HTTPException(404, "Mağaza aracı bulunamadı")
    try:
        uretilmis_komut = komutlar.arac_komutu_uret(arac, istek.parametreler)
    except (komutlar.KomutHatasi, ValueError) as hata:
        raise HTTPException(422, str(hata))

    is_adi = f"Mağaza: {arac.get('ad', istek.arac_id)}"
    return _is_baslat(
        "ssh_komut",
        {"ad": is_adi, "arac_id": istek.arac_id, "sudo": arac.get("sudo", True)},
        istek.cihazlar,
        lambda is_id, iptal: komutlar.komut_isi(
            is_id, istek.cihazlar, uretilmis_komut, arac.get("sudo", True), is_adi, iptal),
    )


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


class SistemYedekOlusturIstek(BaseModel):
    aciklama: str = ""
    deb_dahil: bool = True
    odev_teslimleri_dahil: bool = True
    yerel_paketler_dahil: bool = False


class SistemYedekDosyaAdiIstek(BaseModel):
    dosya_adi: str
    onay: bool = False


@uygulama.get("/api/sistem-yedek", dependencies=[korumali])
async def sistem_yedek_durumu():
    sistem, yedekler = await asyncio.gather(
        asyncio.to_thread(sistem_yedek.sistem_ozeti),
        asyncio.to_thread(sistem_yedek.yedek_listele),
    )
    return {"sistem": sistem, "yedekler": yedekler}


@uygulama.post("/api/sistem-yedek/olustur", dependencies=[korumali])
async def sistem_yedek_olustur_uc(istek: SistemYedekOlusturIstek):
    try:
        yedek = await asyncio.to_thread(
            sistem_yedek.yedek_olustur,
            aciklama=istek.aciklama,
            deb_dahil=istek.deb_dahil,
            odev_teslimleri_dahil=istek.odev_teslimleri_dahil,
            yerel_paketler_dahil=istek.yerel_paketler_dahil,
        )
        return {
            "tamam": True,
            "yedek": yedek,
            "yedekler": await asyncio.to_thread(sistem_yedek.yedek_listele),
            "sistem": await asyncio.to_thread(sistem_yedek.sistem_ozeti),
        }
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.get("/api/sistem-yedek/{dosya_adi}/indir", dependencies=[korumali])
async def sistem_yedek_indir_uc(dosya_adi: str):
    try:
        yol = sistem_yedek.yedek_yolu(dosya_adi)
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(404, str(hata))
    return FileResponse(
        yol,
        media_type="application/gzip",
        filename=yol.name,
        headers={"Content-Security-Policy": "sandbox"},
    )


@uygulama.delete("/api/sistem-yedek/{dosya_adi}", dependencies=[korumali])
async def sistem_yedek_sil_uc(dosya_adi: str):
    try:
        sistem_yedek.yedek_sil(dosya_adi)
        return {"tamam": True, "yedekler": await asyncio.to_thread(sistem_yedek.yedek_listele)}
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(404, str(hata))


@uygulama.post("/api/sistem-yedek/incele", dependencies=[korumali])
async def sistem_yedek_incele_uc(istek: Request):
    icerik_turu = (istek.headers.get("content-type") or "").lower()
    try:
        if "application/json" in icerik_turu:
            veri_json = await istek.json()
            yol = sistem_yedek.yedek_yolu(veri_json.get("dosya_adi", ""))
            return await asyncio.to_thread(sistem_yedek.yedek_incele, yol, True)
        govde = await istek.body()
        if not govde:
            raise HTTPException(422, "İncelenecek yedek dosyası boş")
        return await asyncio.to_thread(sistem_yedek.yedek_incele, govde, True)
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(422, str(hata))


@uygulama.post("/api/sistem-yedek/geri-yukle", dependencies=[korumali])
async def sistem_yedek_geri_yukle_uc(istek: Request):
    ogr = guvenlik.aktif_ogretmen(istek)
    k_adi = (ogr or {}).get("kullanici_adi") or "admin"
    icerik_turu = (istek.headers.get("content-type") or "").lower()
    try:
        if "application/json" in icerik_turu:
            veri_json = await istek.json()
            _onay_gerekli(bool(veri_json.get("onay")), "Yedekten geri yükleme için onay gereklidir")
            yol = sistem_yedek.yedek_yolu(veri_json.get("dosya_adi", ""))
            sonuc = await asyncio.to_thread(sistem_yedek.yedek_geri_yukle, yol, True)
        else:
            _onay_gerekli(istek.headers.get("x-onay") == "1", "Yedekten geri yükleme için onay gereklidir")
            govde = await istek.body()
            if not govde:
                raise HTTPException(422, "Geri yüklenecek yedek dosyası boş")
            sonuc = await asyncio.to_thread(sistem_yedek.yedek_geri_yukle, govde, True)
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(422, str(hata))

    cerez = guvenlik.oturum_ac(k_adi)
    sonuc["csrf"] = guvenlik.csrf_uret(cerez)
    sonuc["okul"] = veritabani.okul_bilgisi()
    sonuc["yedekler"] = await asyncio.to_thread(sistem_yedek.yedek_listele)
    yanit = JSONResponse(content=sonuc)
    yanit.set_cookie("psy_oturum", cerez, httponly=True, samesite="strict",
                     max_age=ayarlar.OTURUM_SURESI_SN)
    return yanit


@uygulama.post("/api/sistem-yedek/deb-yukle", dependencies=[korumali])
async def sistem_yedek_deb_yukle_uc(istek: Request):
    from urllib.parse import unquote
    dosya_adi = unquote(istek.headers.get("x-dosya-adi", "pardus-sinif-yonetimi.deb"))
    govde = await istek.body()
    try:
        bilgi = await asyncio.to_thread(sistem_yedek.deb_onbellege_yukle, dosya_adi, govde)
        return {"tamam": True, "deb": bilgi, "sistem": await asyncio.to_thread(sistem_yedek.sistem_ozeti)}
    except sistem_yedek.SistemYedekHatasi as hata:
        raise HTTPException(422, str(hata))


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
