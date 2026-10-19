"""Yedekler ve geri dönüş (istem §9.14).

Öğrenci verisi öğretmen PC'ye taşınmaz (proje sahibi kararı, 26 Eyl 2026): yedek
listesi her seferinde hedef bilgisayardan canlı okunur ve veritabanına yazılmaz;
iş günlüğüne yalnızca sayısal bir özet düşer. Asıl iş uzak/yedek.py betiğindedir.

İki tür kayıt geri yüklenebilir:
- "profil":   Yedek al / profil sıfırlama öncesi alınan tam profil arşivi.
- "temizlik": Ders sonu temizliğinde karantinaya taşınan dosyalar.
"""

import asyncio
import re

from . import ayarlar, profil, secim, ssh_araclari, uzak, veritabani

TURLER = ("profil", "temizlik")
_AD_DESENI = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


class YedekHatasi(Exception):
    """Kullanıcıya olduğu gibi gösterilebilecek hata."""


def _yonetilebilir_cihaz(cihaz_id: str) -> dict:
    cihaz = veritabani.cihaz(cihaz_id)
    if not cihaz:
        raise YedekHatasi("Bilgisayar bulunamadı")
    neden = secim.uygunluk(cihaz, "temizlik")
    if neden:
        raise YedekHatasi(neden)
    return cihaz


def listele(cihaz_id: str) -> dict:
    """Hedefteki yedekleri canlı okur (salt okunur)."""
    cihaz = _yonetilebilir_cihaz(cihaz_id)
    try:
        istemci = profil.baglan(cihaz)
    except Exception as hata:
        raise YedekHatasi(f"{veritabani.cihaz_adi(cihaz)} bilgisayarına bağlanılamadı: {hata}")
    try:
        try:
            sonuc = ssh_araclari.sudo_betik(
                istemci, uzak.betik("yedek"),
                {"mod": "listele", "hesap": ayarlar.PROFIL_HESABI}, zaman=60)
        except ssh_araclari.SudoHatasi as hata:
            raise YedekHatasi(str(hata))
        except RuntimeError as hata:
            raise YedekHatasi(f"Yedekler okunamadı: {hata}")
        if "hata" in sonuc:
            raise YedekHatasi(sonuc["hata"])
        sonuc["oturum_acik"] = (ayarlar.PROFIL_HESABI
                                in ssh_araclari.aktif_oturumlar(istemci))
        return sonuc
    finally:
        istemci.close()


def istegi_dogrula(tur: str, ad: str) -> None:
    if tur not in TURLER:
        raise YedekHatasi("Bilinmeyen yedek türü")
    if not _AD_DESENI.match(ad):
        raise YedekHatasi("Geçersiz yedek adı")


async def geri_yukle_isi(is_id: str, cihaz_id: str, tur: str, ad: str,
                         zorla_kapat: bool, iptal: asyncio.Event) -> None:
    cihaz = veritabani.cihaz(cihaz_id)
    if not cihaz or iptal.is_set():
        return
    if not profil.hazirlik_kontrol(is_id, cihaz):
        return
    await asyncio.to_thread(_geri_yukle, is_id, cihaz, tur, ad, zorla_kapat)


def _geri_yukle(is_id: str, cihaz: dict, tur: str, ad: str, zorla_kapat: bool) -> None:
    ip, cad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti",
                              f"{cad} — geri yükleme için bağlanılıyor")
    try:
        istemci = profil.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{cad} — bağlantı kurulamadı: {hata}")
        return
    try:
        oturum_notu = ""
        if tur == "profil":
            # Profil yedeği ayar dosyalarını da içerir; açık oturuma yazılmaz.
            if not profil.oturum_kapisi(is_id, istemci, cihaz, zorla_kapat, "Geri yükleme"):
                return
        elif ayarlar.PROFIL_HESABI in ssh_araclari.aktif_oturumlar(istemci):
            oturum_notu = (f" | Not: {ayarlar.PROFIL_HESABI} oturumu açıktı; dosyalar "
                           f"açık oturuma geri kondu")

        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "geri_yukle",
                                  f"{cad} — yedek doğrulanıyor ve geri yükleniyor")
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("yedek"),
            {"mod": "geri_yukle", "hesap": ayarlar.PROFIL_HESABI, "tur": tur, "ad": ad},
            zaman=3600)
        ozet = (f"{sonuc.get('yeni', 0)} dosya geri kondu, "
                f"{sonuc.get('ayni', 0)} dosya zaten aynıydı, "
                f"{sonuc.get('yan_yana', 0)} dosya farklı olduğu için '(yedek …)' adıyla yanına kondu")
        if sonuc.get("atlanan"):
            ozet += f", {sonuc['atlanan']} öğe atlandı"
        if sonuc.get("hatali"):
            ozet += f", {sonuc['hatali']} öğe yazılamadı"
        if "hata" in sonuc:
            ilerleme = f" ({ozet})" if any(sonuc.get(k) for k in ("yeni", "ayni", "yan_yana")) else ""
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "geri_yukle",
                                      f"{cad} — {sonuc['hata']}{ilerleme}")
            return
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                  f"{cad} — geri yükleme tamamlandı: {ozet}{oturum_notu}")
        veritabani.cihaz_guncelle(cihaz["id"], son_kontrol=veritabani.simdi())
    except (RuntimeError, ssh_araclari.SudoHatasi) as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "geri_yukle", f"{cad} — {hata}")
    finally:
        istemci.close()
