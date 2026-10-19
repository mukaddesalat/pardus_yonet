"""Sınıf Masası hızlı işlemleri ve masaüstü dosya/bağlantı dağıtımı (M1-S1 / M3-S1).

Öğrenci bilgisayarlarında `uzak/sinif.py` betiğini parolasız sudo ile çalıştırır:
- Ekran kilitleme ("Bana Bakın" modu) ve kilit açma
- Sınıfa masaüstü duyurusu / mesaj gönderme
- İnternet kısıtlama (yalnız yerel ağ açık) ve serbest bırakma
- Öğrenci masaüstüne (`/home/ogrenci/Masaüstü`) web kısayolu veya dosya gönderme
"""

import asyncio

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim


async def sinif_isi(is_id: str, cihaz_idler: list[str], kip_veya_parametre: str | dict,
                    parametre_veya_iptal: dict | asyncio.Event | None = None,
                    iptal: asyncio.Event | None = None) -> None:
    if isinstance(kip_veya_parametre, str):
        ek = dict(parametre_veya_iptal) if isinstance(parametre_veya_iptal, dict) else {}
        if kip_veya_parametre == "ekran_kilit" and "eylem" not in ek and "kilitle" in ek:
            ek["eylem"] = "kilitle" if ek["kilitle"] else "ac"
        if kip_veya_parametre == "internet" and "eylem" not in ek and "kisitla" in ek:
            ek["eylem"] = "kisitla" if ek["kisitla"] else "ac"
        parametre = {"kip": kip_veya_parametre, **ek}
    else:
        parametre = dict(kip_veya_parametre)
        if isinstance(parametre_veya_iptal, asyncio.Event):
            iptal = parametre_veya_iptal
    if iptal is None:
        iptal = asyncio.Event()
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip = cihaz["ip"]
        ad = veritabani.cihaz_adi(cihaz)
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "sinif")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam", f"{ad} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(_calistir_tek, is_id, cihaz, parametre)

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))


def _calistir_tek(is_id: str, cihaz: dict, parametre: dict) -> None:
    ip = cihaz["ip"]
    ad = veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "ip": ip}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — ulaşılamadı ({hata})", {**veri, "ulasildi": False})
        return
    try:
        sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("sinif"), parametre, zaman=30)
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "uygulama",
                                      f"{ad} — {sonuc['hata']}", {**veri, "ulasildi": True, "sonuc": sonuc})
        else:
            mesaj = sonuc.get("mesaj") or "Tamamlandı"
            veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                      f"{ad} — {mesaj}", {**veri, "ulasildi": True, "sonuc": sonuc})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "uygulama",
                                  f"{ad} — {hata}", {**veri, "ulasildi": True})
    finally:
        istemci.close()
