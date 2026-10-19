"""Salt okunur durum kontrolü (istem §8) ve envanter alanlarının güncellenmesi.

Durum, öğrenci PC'de tek bir uzak betikle (uzak/durum.py) toplanır. Betik
parolasız sudo ile root olarak çalışır; sudo yoksa aynı betik bağlantı hesabının
yetkisiyle çalışır ve root gerektiren alanlar "ölçülemedi" kalır. Hiçbir ayar
değiştirilmez. Anahtarı kurulmamış bilgisayarda yalnız erişim ve sunucu kimliği
(kimlik bilgisi göndermeden) denetlenir.
"""

import asyncio
import logging

from . import anahtar, ayarlar, secim, ssh_araclari, uzak, veritabani

log = logging.getLogger("psy.yonetim")


def baglan(cihaz: dict):
    """Uygulama anahtarıyla (parola geri dönüşü olmadan) bağlanır."""
    return ssh_araclari.anahtar_ile_baglan(
        cihaz["ip"], cihaz["ssh_port"], cihaz["baglanti_hesabi"],
        anahtar.ozel_anahtar_yolu(), cihaz["anahtar_tipi"], cihaz["anahtar_b64"])


def durum_topla(istemci) -> tuple[dict, bool]:
    """(durum, parolasız_sudo_var_mı). Sudo yoksa kısmi durum döner."""
    parametre = {"profil": ayarlar.PROFIL_HESABI, "yonetim": list(ayarlar.YONETIM_HESAPLARI)}
    try:
        sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("durum"), parametre, zaman=60)
        return sonuc, True
    except ssh_araclari.SudoHatasi:
        return ssh_araclari.betik(istemci, uzak.betik("durum"), parametre, zaman=60), False


def _gizleme(sonuc: dict, hesap: str | None) -> str | None:
    if sonuc.get("giris_yoneticisi") not in (None, "gdm3"):
        return "desteklenmiyor"
    bilgi = (sonuc.get("gizleme") or {}).get(hesap or "")
    if not bilgi:
        return None  # ölçülemedi (root yok) veya hesap yok
    if bilgi["sistem_hesabi"] and bilgi["listede"] is False:
        return "gizli"
    if bilgi["sistem_hesabi"]:
        return "yapilandirildi"  # ayar var, liste doğrulanamadı
    return "gorunur"


def durum_kaydet(cihaz: dict, sonuc: dict, sudo_var: bool) -> dict:
    """Uzak durum sonucunu envantere yazar; güncellenen alanları döndürür."""
    if "hata" in sonuc:
        raise RuntimeError(sonuc["hata"])
    os_bilgi = sonuc.get("os") or {}
    hesaplar = [h for h, v in (sonuc.get("yonetim_hesaplari") or {}).items() if v]
    otomatik = sonuc.get("otomatik_giris") or {}
    alanlar = {
        "hostname": sonuc.get("hostname"),
        "pardus_surum": (f"Pardus {os_bilgi['VERSION_ID']}"
                         if os_bilgi.get("ID") == "pardus" and os_bilgi.get("VERSION_ID")
                         else os_bilgi.get("PRETTY_NAME") or ""),
        "masaustu": sonuc.get("masaustu") or "bilinmiyor",
        "giris_yoneticisi": sonuc.get("giris_yoneticisi"),
        "profil_var": 1 if sonuc.get("profil") else 0,
        "ogrenci_oturumu": 1 if sonuc.get("ogrenci_oturumu") else 0,
        "ogrenci_sudo": 1 if sonuc.get("profil_sudo") else 0,
        "disk_bos": (sonuc.get("disk") or {}).get("ev_bos"),
        "gorunum_durumu": "uygulandi" if (sonuc.get("gorunum") or {}).get("duzen") else "yok",
        "otomatik_giris": (otomatik.get("hesap") or "kapali") if otomatik.get("destekli")
                          else "desteklenmiyor",
        "erisim": 1, "erisim_zamani": veritabani.simdi(),
        "son_kontrol": veritabani.simdi(),
    }
    if sudo_var:
        # hesap listesi ve gizleme yalnız root ile güvenilir okunur
        alanlar["yonetim_hesaplari"] = hesaplar
        alanlar["gizleme_durumu"] = _gizleme(sonuc, cihaz.get("baglanti_hesabi"))
        alanlar["sudo_durumu"] = "parolasiz"
    else:
        alanlar["sudo_durumu"] = "parola_gerekli"
    if os_bilgi.get("ID") != "pardus":
        alanlar["durum"] = "Pardus değil — yönetilemez"
    elif sudo_var:
        alanlar["durum"] = "Yönetilebilir"
    else:
        alanlar["durum"] = "Parolasız sudo gerekli"
    if sonuc.get("etap") and not cihaz.get("korunan"):
        # EBA/ETAP izi bulunan cihaz korunur; öğretmen isterse elle kaldırabilir
        alanlar["korunan"] = 1
        alanlar["korunan_neden"] = "Otomatik: " + sonuc["etap"]
    if sonuc.get("veyon"):
        from . import veyon  # döngüsel içe aktarma
        alanlar.update(veyon.envanter_alanlari(sonuc["veyon"]))  # M1-S1 ve M1-S4 aynı veriyi görür
    if sonuc.get("guc"):
        from . import guc_ayar  # döngüsel içe aktarma
        alanlar.update(guc_ayar.envanter_alani(sonuc["guc"]))
    veritabani.cihaz_guncelle(cihaz["id"], **alanlar)
    return alanlar


async def durum_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip = cihaz["ip"]
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "durum")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam", neden)
            return
        async with sinir:
            await asyncio.to_thread(_durum_oku, is_id, cihaz)

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))


def _durum_oku(is_id: str, cihaz: dict) -> None:
    ip, port = cihaz["ip"], cihaz["ssh_port"]
    ad = veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)

    if cihaz["anahtar_durumu"] != "ok":
        # Anahtar yok: kimlik bilgisi göndermeden yalnız erişim ve sunucu kimliği
        try:
            kimlik = ssh_araclari.host_kimligi_topla(ip, port)
        except Exception as hata:
            veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi(),
                                      durum="SSH erişilemiyor", son_kontrol=veritabani.simdi())
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                      f"{ad} — SSH erişilemiyor ({hata})")
            return
        degisti = cihaz["parmak_izi"] and kimlik["parmak_izi"] != cihaz["parmak_izi"]
        veritabani.cihaz_guncelle(cihaz["id"], erisim=1, erisim_zamani=veritabani.simdi(),
                                  son_kontrol=veritabani.simdi())
        mesaj = (f"{ad} — erişilebilir; SSH anahtarı kurulu değil (M1-S2)" if not degisti else
                 f"{ad} — UYARI: sunucu kimliği kayıtlıdan farklı! ({kimlik['parmak_izi']})")
        veritabani.hedef_guncelle(is_id, ip, "basarisiz" if degisti else "basarili", "tamam",
                                  mesaj, {**veri, "anahtar": False})
        return

    try:
        istemci = baglan(cihaz)
    except ssh_araclari.SunucuKimligiHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kimlik", f"{ad} — {hata}")
        return
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi(),
                                  durum="SSH erişilemiyor", son_kontrol=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — anahtarlı bağlantı kurulamadı: {hata}")
        return
    try:
        sonuc, sudo_var = durum_topla(istemci)
        alanlar = durum_kaydet(cihaz, sonuc, sudo_var)
        uyarilar = []
        if alanlar.get("ogrenci_oturumu"):
            uyarilar.append(f"{ayarlar.PROFIL_HESABI} oturumu açık")
        if not alanlar.get("profil_var"):
            uyarilar.append(f"'{ayarlar.PROFIL_HESABI}' hesabı yok")
        if not sudo_var:
            uyarilar.append("parolasız sudo yok (M1-S2)")
        if len(alanlar.get("yonetim_hesaplari") or []) > 1:
            uyarilar.append("hp ve pardus birlikte var (tekilleştirme)")
        if alanlar.get("korunan"):
            uyarilar.append("EBA/ETAP izi — korunan cihaz yapıldı")
        mesaj = f"{ad} — {alanlar['pardus_surum'] or '?'}, {alanlar['masaustu']}"
        if uyarilar:
            mesaj += " | UYARI: " + "; ".join(uyarilar)
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam", mesaj,
                                  {**veri, "durum": sonuc, "sudo": sudo_var})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "durum", f"{ad} — {hata}")
    finally:
        istemci.close()
