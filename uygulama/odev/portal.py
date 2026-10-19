"""Öğrenci teslim portalı — laboratuvar ağına açık tek bileşen (istem §2, §8).

Ayrı süreç ve ayrı sistem kullanıcısı (`pardus-odev`) ile çalışır; yalnız
`uygulama.odev` paketini içe aktarır. Yönetim uçları, SSH anahtarı, envanter
veya yönetim günlüklerine erişimi yoktur (dosya izinleri de engeller).

Güvenlik: laboratuvar alt ağı izin listesi, Host/Origin denetimi, özel başlık
(CSRF), oturum çerezi (HttpOnly, SameSite=Strict), kısa hareketsizlik süresi,
giriş deneme sınırı ve her istekte sunucu tarafı yetki denetimi.
Proje sahibi kararıyla düz HTTP kullanılır; trafik laboratuvar ağında şifresizdir.
"""

import asyncio
import ipaddress
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import kod, ortak, teslim, vt

log = logging.getLogger("psy.odev")
ARAYUZ = Path(__file__).parent / "arayuz"

OTURUM_BOSTA_SN = 15 * 60
GIRIS_HATA_SINIRI = 5          # öğrenci başına; aşılınca kilit
GIRIS_KILIT_SN = 5 * 60
IP_HATA_SINIRI = 30            # IP başına, 10 dakikalık pencerede
IP_PENCERE_SN = 10 * 60
ISTEK_SINIRI_DK = 900          # IP başına dakikadaki istek (çok dosyalı klasör yüklemeye yeter)

_oturumlar: dict[str, dict] = {}                     # belirteç -> {ogrenci_id, sinif_id, son}
_ogrenci_hata: dict[tuple, list] = {}                 # (sınıf, numara) -> [sayı, kilit_bitis]
_ip_hata: dict[str, list[float]] = {}
_ip_istek: dict[str, list] = {}                       # ip -> [pencere_bas, sayı]
_ag_onbellek: dict = {"zaman": 0.0, "aglar": [], "adlar": set()}


# ---------------------------------------------------------------- ağ ve adres denetimi

def _ayarlari_yukle() -> dict:
    if time.monotonic() - _ag_onbellek["zaman"] > 30:
        ham = vt.ayar_oku("portal_aglar") or os.environ.get("PSY_ODEV_AGLAR", "")
        try:
            liste = json.loads(ham) if ham.startswith("[") else [a for a in ham.split(",") if a]
            aglar = [ipaddress.ip_network(a.strip(), strict=False) for a in liste]
        except ValueError:
            aglar = []
        ad = (vt.ayar_oku("adres_adi") or ortak.VARSAYILAN_AD).lower()
        _ag_onbellek.update(zaman=time.monotonic(), aglar=aglar, adlar={ad, "localhost"})
    return _ag_onbellek


def istemci_izinli_mi(ip: str) -> bool:
    try:
        adres = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if adres.is_loopback:
        return True
    return any(adres in ag for ag in _ayarlari_yukle()["aglar"])


def _host_adi(host: str) -> str:
    """'ogretmen.lab:8090' -> 'ogretmen.lab'; '[::1]:80' -> '::1'."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:].split("]", 1)[0]
    return host.split(":", 1)[0] if host.count(":") == 1 else host


def host_izinli_mi(host: str) -> bool:
    """DNS yeniden bağlama saldırısına karşı yalnız tanımlı ad veya IP kabul edilir."""
    ad = _host_adi(host)
    if ad in _ayarlari_yukle()["adlar"]:
        return True
    try:
        ipaddress.ip_address(ad)
        return True
    except ValueError:
        return False


def _hiz_asildi_mi(ip: str) -> bool:
    simdi = time.monotonic()
    kayit = _ip_istek.setdefault(ip, [simdi, 0])
    if simdi - kayit[0] > 60:
        kayit[0], kayit[1] = simdi, 0
    kayit[1] += 1
    return kayit[1] > ISTEK_SINIRI_DK


# ---------------------------------------------------------------- uygulama

@asynccontextmanager
async def yasam_dongusu(_uygulama: FastAPI):
    vt.ac()
    sonuc = teslim.onar(acilista=True)
    if sonuc["yarim"]:
        log.warning("Servis yeniden başladı: %d yarım aktarım teslim sayılmadı", sonuc["yarim"])
    gorev = asyncio.create_task(_bakim())
    yield
    gorev.cancel()


async def _bakim():
    while True:
        await asyncio.sleep(300)
        try:
            await asyncio.to_thread(teslim.onar)
            simdi = time.monotonic()
            for belirtec in [b for b, o in _oturumlar.items() if simdi - o["son"] > OTURUM_BOSTA_SN]:
                _oturumlar.pop(belirtec, None)
        except Exception:
            log.exception("Bakım görevi hatası")


uygulama = FastAPI(title="Ödev Teslim", docs_url=None, redoc_url=None, openapi_url=None,
                   lifespan=yasam_dongusu)


@uygulama.middleware("http")
async def koruma(istek: Request, devam):
    ip = istek.client.host if istek.client else ""
    if not istemci_izinli_mi(ip):
        return JSONResponse({"detail": "Bu adrese yalnız laboratuvar ağından erişilebilir."},
                            status_code=403)
    if not host_izinli_mi(istek.headers.get("host", "")):
        return JSONResponse({"detail": "Geçersiz adres"}, status_code=400)
    if _hiz_asildi_mi(ip):
        return JSONResponse({"detail": "Çok fazla istek; biraz bekleyin."}, status_code=429)
    if istek.method not in ("GET", "HEAD"):
        # Çapraz site istekleri özel başlık gönderemez (CORS yok); Origin de denetlenir.
        origin = istek.headers.get("origin")
        host = istek.headers.get("host", "")
        if istek.headers.get("x-odev") != "1" or (origin and origin.split("//")[-1] != host):
            return JSONResponse({"detail": "İstek reddedildi"}, status_code=403)
    yanit = await devam(istek)
    yanit.headers["Cache-Control"] = "no-store"
    yanit.headers["X-Content-Type-Options"] = "nosniff"
    yanit.headers["Referrer-Policy"] = "no-referrer"
    yanit.headers["X-Frame-Options"] = "DENY"
    yanit.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; frame-ancestors 'none'")
    return yanit


@uygulama.exception_handler(teslim.TeslimHatasi)
async def teslim_hatasi(_istek: Request, hata: teslim.TeslimHatasi):
    return JSONResponse({"detail": hata.mesaj}, status_code=hata.kod)


# ---------------------------------------------------------------- oturum

def _ogrenci(istek: Request) -> dict:
    belirtec = istek.cookies.get("odev_oturum")
    oturum = _oturumlar.get(belirtec or "")
    if not oturum or time.monotonic() - oturum["son"] > OTURUM_BOSTA_SN:
        _oturumlar.pop(belirtec or "", None)
        raise HTTPException(401, "Oturumunuz kapandı; yeniden giriş yapın.")
    ogrenci = vt.tek("SELECT o.id, o.sinif_id, o.numara, o.ad_soyad, s.ad AS sinif "
                     "FROM ogrenci o JOIN sinif s ON s.id=o.sinif_id WHERE o.id=?",
                     (oturum["ogrenci_id"],))
    if not ogrenci:
        raise HTTPException(401, "Oturumunuz kapandı; yeniden giriş yapın.")
    oturum["son"] = time.monotonic()
    return ogrenci


class GirisIstek(BaseModel):
    sinif_id: str = Field(max_length=64)
    numara: str = Field(max_length=16)
    kod: str = Field(max_length=32)


@uygulama.get("/api/saglik")
async def saglik():
    return {"durum": "ok"}


@uygulama.get("/api/siniflar")
async def sinif_listesi():
    """Giriş ekranı için sınıf adları (yalnız kodu üretilmiş öğrencisi olanlar)."""
    return vt.sorgula("SELECT DISTINCT s.id, s.ad FROM sinif s JOIN ogrenci o "
                      "ON o.sinif_id=s.id WHERE o.kod_ozeti IS NOT NULL ORDER BY s.ad")


@uygulama.post("/api/giris")
async def giris(istek: GirisIstek, http: Request):
    ip = http.client.host if http.client else ""
    simdi = time.monotonic()
    ip_kayit = [t for t in _ip_hata.get(ip, []) if simdi - t < IP_PENCERE_SN]
    _ip_hata[ip] = ip_kayit
    if len(ip_kayit) >= IP_HATA_SINIRI:
        raise HTTPException(429, "Çok fazla hatalı deneme. Birkaç dakika sonra tekrar deneyin.")
    anahtar = (istek.sinif_id, istek.numara.strip())
    sayac = _ogrenci_hata.get(anahtar, [0, 0.0])
    if sayac[1] > simdi:
        raise HTTPException(429, "Çok fazla hatalı deneme. 5 dakika sonra tekrar deneyin "
                                 "veya öğretmeninizden yeni kod isteyin.")
    ogr = vt.tek("SELECT id, sinif_id, kod_ozeti FROM ogrenci WHERE sinif_id=? AND numara=?",
                 anahtar)
    # Numara yoksa da aynı hesaplama yapılır: yanıt süresi kaydın varlığını ele vermez.
    dogru = await asyncio.to_thread(kod.dogru_mu, istek.kod,
                                    ogr["kod_ozeti"] if ogr else kod.SAHTE_KAYIT)
    if not ogr or not ogr["kod_ozeti"] or not dogru:
        sayac[0] += 1
        if sayac[0] >= GIRIS_HATA_SINIRI:
            sayac = [0, simdi + GIRIS_KILIT_SN]
        _ogrenci_hata[anahtar] = sayac
        ip_kayit.append(simdi)
        raise HTTPException(401, "Sınıf, numara veya teslim kodu hatalı.")
    _ogrenci_hata.pop(anahtar, None)
    belirtec = secrets.token_urlsafe(32)
    _oturumlar[belirtec] = {"ogrenci_id": ogr["id"], "son": simdi}
    yanit = JSONResponse({"tamam": True})
    yanit.set_cookie("odev_oturum", belirtec, httponly=True, samesite="strict", path="/")
    return yanit


@uygulama.post("/api/cikis")
async def cikis(istek: Request):
    _oturumlar.pop(istek.cookies.get("odev_oturum") or "", None)
    yanit = JSONResponse({"tamam": True})
    yanit.delete_cookie("odev_oturum", path="/")
    return yanit


@uygulama.get("/api/ben")
async def ben(istek: Request):
    o = _ogrenci(istek)
    return {"ad_soyad": o["ad_soyad"], "sinif": o["sinif"], "numara": o["numara"],
            "bosta_sn": OTURUM_BOSTA_SN}


# ---------------------------------------------------------------- ödevler ve teslim

class BaslatIstek(BaseModel):
    odev_id: str = Field(max_length=64)
    dosyalar: list[dict] = Field(max_length=ortak.EN_FAZLA_DOSYA_SINIRI)


@uygulama.get("/api/odevler")
async def odevler(istek: Request):
    return teslim.ogrenci_odevleri(_ogrenci(istek))


@uygulama.get("/api/odevler/{odev_id}/teslimlerim")
async def teslimlerim(odev_id: str, istek: Request):
    return teslim.ogrenci_teslimleri(_ogrenci(istek), odev_id)


@uygulama.post("/api/teslim/baslat")
async def baslat(govde: BaslatIstek, istek: Request):
    ogrenci = _ogrenci(istek)
    return await asyncio.to_thread(teslim.baslat, ogrenci, govde.odev_id, govde.dosyalar,
                                   istek.client.host if istek.client else "")


@uygulama.put("/api/teslim/{teslim_id}/dosya/{sira}")
async def dosya(teslim_id: str, sira: int, istek: Request):
    ogrenci = _ogrenci(istek)
    boyut = istek.headers.get("content-length")
    return await teslim.dosya_yaz(ogrenci, teslim_id, sira, istek.stream(),
                                  int(boyut) if boyut and boyut.isdigit() else None)


@uygulama.post("/api/teslim/{teslim_id}/tamamla")
async def tamamla(teslim_id: str, istek: Request):
    return await asyncio.to_thread(teslim.tamamla, _ogrenci(istek), teslim_id)


@uygulama.post("/api/teslim/{teslim_id}/iptal")
async def iptal(teslim_id: str, istek: Request):
    await asyncio.to_thread(teslim.iptal, _ogrenci(istek), teslim_id)
    return {"tamam": True}


@uygulama.get("/api/teslim/{teslim_id}")
async def teslim_durumu(teslim_id: str, istek: Request):
    return teslim.durum(_ogrenci(istek), teslim_id)


# ---------------------------------------------------------------- arayüz

@uygulama.get("/")
async def anasayfa():
    return FileResponse(ARAYUZ / "index.html")


uygulama.mount("/statik", StaticFiles(directory=ARAYUZ), name="statik")


def calistir():
    import uvicorn
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(uygulama, host=ortak.PORTAL_ADRESI, port=ortak.PORTAL_PORTU,
                access_log=False, server_header=False, proxy_headers=False,
                limit_concurrency=300, timeout_keep_alive=30)


if __name__ == "__main__":
    calistir()
