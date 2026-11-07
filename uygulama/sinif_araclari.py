"""Sınıf Masası hızlı işlemleri ve masaüstü dosya/bağlantı dağıtımı (M1-S1 / M3-S1).

Öğrenci bilgisayarlarında `uzak/sinif.py` betiğini parolasız sudo ile çalıştırır:
- Ekran kilitleme ("Bana Bakın" modu) ve kilit açma
- Sınıfa masaüstü duyurusu / mesaj gönderme
- İnternet kısıtlama (yalnız yerel ağ açık) ve serbest bırakma
- Öğrenci masaüstüne (`/home/ogrenci/Masaüstü`) web kısayolu veya dosya gönderme
"""

import asyncio
import base64
import secrets
import shlex

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
        parametre_gonder = {
            **parametre,
            "cihaz_hostname": cihaz.get("hostname") or "",
            "cihaz_etiket": cihaz.get("etiket") or "",
        }
        zaman_asimi = 30
        gecici_yol = None
        if parametre_gonder.get("kip") == "masaustu_dosya" and parametre_gonder.get("icerik_b64"):
            try:
                ham_veri = base64.b64decode(parametre_gonder.get("icerik_b64") or "", validate=True)
            except Exception:
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "uygulama",
                                          f"{ad} — Dosya verisi çözümlenemedi", {**veri, "ulasildi": True})
                return
            kb = max(1, len(ham_veri) // 1024)
            veritabani.hedef_guncelle(is_id, ip, "calisiyor", "aktarim",
                                      f"{ad} — dosya aktarılıyor ({kb} KB)", veri)
            gecici_yol = f"/tmp/psy-dosya-{secrets.token_hex(8)}"
            aktarildi = False
            if hasattr(istemci, "open_sftp"):
                try:
                    sftp = istemci.open_sftp()
                    try:
                        with sftp.file(gecici_yol, "wb") as f:
                            f.write(ham_veri)
                        aktarildi = True
                    finally:
                        sftp.close()
                except Exception:
                    aktarildi = False
            if not aktarildi and hasattr(istemci, "exec_command"):
                try:
                    kod_k, _, _ = ssh_araclari.komut(
                        istemci, f"cat > {shlex.quote(gecici_yol)}", girdi=ham_veri, zaman=120
                    )
                    aktarildi = kod_k == 0
                except Exception:
                    aktarildi = False
            if aktarildi:
                parametre_gonder = {k: v for k, v in parametre_gonder.items() if k != "icerik_b64"}
                parametre_gonder["gecici_yol"] = gecici_yol
                zaman_asimi = 120
        try:
            sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("sinif"), parametre_gonder, zaman=zaman_asimi)
        finally:
            if gecici_yol and hasattr(istemci, "exec_command"):
                try:
                    ssh_araclari.komut(istemci, f"rm -f {shlex.quote(gecici_yol)}", zaman=5)
                except Exception:
                    pass
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
