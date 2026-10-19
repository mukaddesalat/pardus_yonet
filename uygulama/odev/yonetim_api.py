"""Öğretmen paneli için ödev uçları (/api/odev/...).

Yalnız yerel yönetim panelinde (127.0.0.1, oturum + CSRF) bağlanır; öğrenci
portalı bu yönlendiriciyi hiç yüklemez.
"""

import asyncio
import base64
import ipaddress
import json
import os
import shutil
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import kurallar, odevler, ortak, siniflar, vt

yonlendirici = APIRouter(prefix="/api/odev")


def _indirme_basliklari(dosya_adi: str) -> dict:
    ascii_ad = dosya_adi.encode("ascii", "replace").decode().replace("?", "_").replace('"', "_")
    return {
        "Content-Disposition": (f'attachment; filename="{ascii_ad}"; '
                                f"filename*=UTF-8''{urllib.parse.quote(dosya_adi)}"),
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox",
        "Cache-Control": "no-store",
    }


def _hata(hata: Exception, kod: int = 422):
    raise HTTPException(kod, str(hata))


# ---------------------------------------------------------------- genel durum

class PortalAyarIstek(BaseModel):
    adres_adi: str = Field(min_length=1, max_length=63)
    aglar: list[str] = Field(max_length=16)


def _portal_calisiyor_mu() -> bool:
    try:
        url = f"http://127.0.0.1:{int(ortak.PORTAL_PORTU)}/api/saglik"
        with urllib.request.urlopen(url, timeout=2) as yanit:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            return yanit.status == 200
    except Exception:
        return False


def _aglar() -> list[str]:
    ham = vt.ayar_oku("portal_aglar")
    if ham:
        return json.loads(ham)
    return [a for a in os.environ.get("PSY_ODEV_AGLAR", "").split(",") if a]


@yonlendirici.get("/durum")
async def durum():
    ad = vt.ayar_oku("adres_adi") or ortak.VARSAYILAN_AD
    port = "" if ortak.PORTAL_PORTU == 80 else f":{ortak.PORTAL_PORTU}"
    kok = ortak.ODEV_DIZINI
    kok.mkdir(parents=True, exist_ok=True)
    return {"adres": f"http://{ad}{port}/", "adres_adi": ad, "port": ortak.PORTAL_PORTU,
            "portal_calisiyor": await asyncio.to_thread(_portal_calisiyor_mu),
            "bos_alan": shutil.disk_usage(kok).free, "aglar": _aglar(),
            "turler": {k: v[0] for k, v in kurallar.KATEGORILER.items()},
            "varsayilan_turler": kurallar.VARSAYILAN_KATEGORILER}


@yonlendirici.post("/ayarlar")
async def portal_ayarlari(istek: PortalAyarIstek):
    ad = istek.adres_adi.strip().lower()
    if not all(p and p.replace("-", "").isalnum() for p in ad.split(".")):
        _hata(ValueError("Geçersiz adres adı (örn. ogretmen.lab)"))
    try:
        aglar = [str(ipaddress.ip_network(a.strip(), strict=False)) for a in istek.aglar if a.strip()]
    except ValueError:
        _hata(ValueError("Geçersiz ağ (örn. 192.168.10.0/24)"))
    if not aglar:
        _hata(ValueError("En az bir laboratuvar ağı girin"))
    vt.ayar_yaz("adres_adi", ad)
    vt.ayar_yaz("portal_aglar", json.dumps(aglar))
    return {"adres_adi": ad, "aglar": aglar, "not": "Portal ayarları 30 saniye içinde uygular."}


# ---------------------------------------------------------------- sınıflar ve öğrenciler

class SinifIstek(BaseModel):
    ad: str


class OgrenciIstek(BaseModel):
    numara: str
    ad_soyad: str


class OgrenciDuzenleIstek(BaseModel):
    ad_soyad: str


class IceAktarIstek(BaseModel):
    icerik_b64: str = Field(max_length=4 * 1024 * 1024)


class KodIstek(BaseModel):
    ogrenci_idler: list[str] = []
    sinif_id: str | None = None
    sadece_kodsuz: bool = False


@yonlendirici.get("/siniflar")
async def sinif_listesi():
    return siniflar.siniflar()


@yonlendirici.post("/siniflar")
async def sinif_ekle(istek: SinifIstek):
    try:
        return {"id": siniflar.sinif_bul_veya_olustur(istek.ad)}
    except siniflar.SinifHatasi as hata:
        _hata(hata)


@yonlendirici.delete("/siniflar/{sinif_id}")
async def sinif_sil(sinif_id: str):
    try:
        siniflar.sinif_sil(sinif_id)
    except siniflar.SinifHatasi as hata:
        _hata(hata, 409)
    return {"tamam": True}


@yonlendirici.get("/siniflar/{sinif_id}/ogrenciler")
async def ogrenci_listesi(sinif_id: str):
    return siniflar.ogrenciler(sinif_id)


@yonlendirici.post("/siniflar/{sinif_id}/ogrenciler")
async def ogrenci_ekle(sinif_id: str, istek: OgrenciIstek):
    try:
        return {"id": siniflar.ogrenci_ekle(sinif_id, istek.numara, istek.ad_soyad)}
    except siniflar.SinifHatasi as hata:
        _hata(hata)


@yonlendirici.patch("/ogrenciler/{ogrenci_id}")
async def ogrenci_duzenle(ogrenci_id: str, istek: OgrenciDuzenleIstek):
    try:
        siniflar.ogrenci_duzenle(ogrenci_id, istek.ad_soyad)
    except siniflar.SinifHatasi as hata:
        _hata(hata)
    return {"tamam": True}


@yonlendirici.delete("/ogrenciler/{ogrenci_id}")
async def ogrenci_sil(ogrenci_id: str):
    try:
        siniflar.ogrenci_sil(ogrenci_id)
    except siniflar.SinifHatasi as hata:
        _hata(hata, 409)
    return {"tamam": True}


@yonlendirici.post("/ice-aktar")
async def ice_aktar(istek: IceAktarIstek):
    try:
        veri = base64.b64decode(istek.icerik_b64, validate=True)
    except ValueError:
        _hata(ValueError("Dosya okunamadı"))
    return await asyncio.to_thread(siniflar.ice_aktar, veri)


@yonlendirici.get("/siniflar/{sinif_id}/csv")
async def sinif_csv(sinif_id: str):
    try:
        metin = siniflar.disari_aktar(sinif_id)
    except siniflar.SinifHatasi as hata:
        _hata(hata, 404)
    ad = vt.tek("SELECT ad FROM sinif WHERE id=?", (sinif_id,))["ad"]
    return PlainTextResponse(metin, media_type="text/csv; charset=utf-8",
                             headers=_indirme_basliklari(f"{odevler.guvenli_ad(ad)} sınıf listesi.csv"))


@yonlendirici.post("/kod-uret")
async def kod_uret(istek: KodIstek):
    """Kodlar yalnız bu yanıtta döner; sunucuda düz metin olarak tutulmaz."""
    idler = list(istek.ogrenci_idler)
    if istek.sinif_id:
        idler += [o["id"] for o in siniflar.ogrenciler(istek.sinif_id)
                  if not (istek.sadece_kodsuz and o["kodu_var"])]
    if not idler:
        _hata(ValueError("Kod üretilecek öğrenci yok"))
    return await asyncio.to_thread(siniflar.kod_uret, idler)


# ---------------------------------------------------------------- ödevler

class OdevIstek(BaseModel):
    baslik: str
    sinif_id: str
    yonerge: str = ""
    son_tarih: str | None = None     # İstanbul saatiyle 'YYYY-MM-DDTHH:MM'
    gec_teslim: bool = False
    turler: list[str] = []
    ek_uzantilar: list[str] = []
    en_fazla_dosya: int = ortak.VARSAYILAN_EN_FAZLA_DOSYA
    en_fazla_mb: int = ortak.VARSAYILAN_EN_FAZLA_MB
    klasor_izni: bool = True


class DurumIstek(BaseModel):
    eylem: str


class SilIstek(BaseModel):
    onay: bool = False


@yonlendirici.get("/odevler")
async def odev_listesi():
    return odevler.liste()


@yonlendirici.post("/odevler")
async def odev_olustur(istek: OdevIstek):
    try:
        return {"id": odevler.olustur(istek.model_dump())}
    except odevler.OdevHatasi as hata:
        _hata(hata)


@yonlendirici.get("/odevler/{odev_id}")
async def odev_detay(odev_id: str):
    try:
        return odevler.detay(odev_id)
    except odevler.OdevHatasi as hata:
        _hata(hata, 404)


@yonlendirici.put("/odevler/{odev_id}")
async def odev_guncelle(odev_id: str, istek: OdevIstek):
    try:
        odevler.guncelle(odev_id, istek.model_dump())
    except odevler.OdevHatasi as hata:
        _hata(hata)
    return {"tamam": True}


@yonlendirici.post("/odevler/{odev_id}/durum")
async def odev_durum(odev_id: str, istek: DurumIstek):
    try:
        return {"durum": odevler.durum_degistir(odev_id, istek.eylem)}
    except odevler.OdevHatasi as hata:
        _hata(hata, 409)


@yonlendirici.post("/odevler/{odev_id}/sil")
async def odev_sil(odev_id: str, istek: SilIstek):
    if not istek.onay:
        _hata(ValueError("Silme için açık onay gereklidir"))
    try:
        await asyncio.to_thread(odevler.sil, odev_id)
    except odevler.OdevHatasi as hata:
        _hata(hata, 409)
    return {"tamam": True}


# ---------------------------------------------------------------- teslimler ve indirme

@yonlendirici.get("/teslimler/{teslim_id}/dosyalar")
async def teslim_dosyalari(teslim_id: str):
    try:
        return odevler.teslim_dosyalari(teslim_id)
    except odevler.OdevHatasi as hata:
        _hata(hata, 404)


@yonlendirici.get("/teslimler/{teslim_id}/dosya/{sira}")
async def dosya_indir(teslim_id: str, sira: int):
    try:
        yol, ad = odevler.tek_dosya(teslim_id, sira)
    except odevler.OdevHatasi as hata:
        _hata(hata, 404)
    # Etkin içerik asla tarayıcıda açılmaz: her zaman ek olarak ve genel türle.
    return FileResponse(yol, media_type="application/octet-stream",
                        headers=_indirme_basliklari(ad))


@yonlendirici.get("/teslimler/{teslim_id}/zip")
async def teslim_zip(teslim_id: str):
    try:
        ad, girdiler = odevler.teslim_zip_girdileri(teslim_id)
    except odevler.OdevHatasi as hata:
        _hata(hata, 404)
    return StreamingResponse(odevler.zip_akisi(girdiler), media_type="application/zip",
                             headers=_indirme_basliklari(ad))


@yonlendirici.get("/odevler/{odev_id}/zip")
async def odev_zip(odev_id: str, ogrenciler: str = "", tum_surumler: int = 0):
    secili = [o for o in ogrenciler.split(",") if o] or None
    try:
        ad, girdiler = odevler.zip_girdileri(odev_id, secili, bool(tum_surumler))
    except odevler.OdevHatasi as hata:
        _hata(hata, 404)
    return StreamingResponse(odevler.zip_akisi(girdiler), media_type="application/zip",
                             headers=_indirme_basliklari(ad))
