"""Uzak SSH Komut Gönderme Merkezi (M2-S6).

Yalnızca Admin Öğretmen veya 'komut_gonder' ek yetkisi verilmiş öğretmenler
tarafından kullanılabilir. Korunan cihazlar (EBA/ETAP) ve öğretmen PC her zaman
kapsam dışıdır. Her bilgisayardan dönen stdout, stderr ve çıkış kodu (rc)
canlı olarak iş hedeflerine kaydedilir; bitişte:
"X bilgisayara gönderildi · Y bilgisayara ulaşılamadı · Z başarılı · W hata alındı"
özeti üretilir.
"""

import asyncio
import ipaddress
import re

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

EN_BUYUK_CIKTI = 16384  # hedef başına kaydedilecek en fazla çıktı (bayt/karakter)

# Sistem bütünlüğünü tamamen yok edebilecek kalıplara karşı emniyet kilidi
_YASAKLI_KALIPLAR = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--no-preserve-root)\s+/\s*$"), "Güvenlik kilidi: Kök dizini (/) silme komutu engellendi"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "Güvenlik kilidi: Fork bombası kalıbı engellendi"),
    (re.compile(r"\bmkfs(\.[a-z0-9]+)?\s+/dev/"), "Güvenlik kilidi: Disk biçimlendirme (mkfs) komutu engellendi"),
    (re.compile(r"\bdd\s+.*of=/dev/(sd[a-z]|nvme\d+n\d+|vd[a-z])\b"), "Güvenlik kilidi: Ham diske doğrudan yazma (dd) komutu engellendi"),
]


class KomutHatasi(ValueError):
    """Geçersiz veya güvenlik kilidine takılan komut."""


def komutu_dogrula(komut: str) -> str:
    temiz = (komut or "").strip()
    if not temiz:
        raise KomutHatasi("Çalıştırılacak komut boş olamaz")
    if len(temiz) > 4000:
        raise KomutHatasi("Komut 4000 karakter sınırını aşıyor")
    for desen, mesaj in _YASAKLI_KALIPLAR:
        if desen.search(temiz):
            raise KomutHatasi(mesaj)
    return temiz


komut_dogrula = komutu_dogrula


def hosts_dogrula(ip: str, ad: str) -> tuple[str, str]:
    """Verilen IPv4 adresi ve alan adını doğrular."""
    ip_temiz = (ip or "").strip()
    ad_temiz = (ad or "").strip().lower()
    try:
        ipaddress.IPv4Address(ip_temiz)
    except ValueError:
        raise KomutHatasi("Geçersiz IPv4 adresi (örn. 192.168.23.142)")
    if not re.match(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$", ad_temiz):
        raise KomutHatasi("Geçersiz alan adı (örn. abc.local)")
    return ip_temiz, ad_temiz


def hosts_komutu_uret(ip: str, ad: str) -> tuple[str, str, str]:
    """Verilen IP ve alan adı için güvenli /etc/hosts ekleme/güncelleme komutu üretir."""
    ip_temiz, ad_temiz = hosts_dogrula(ip, ad)
    ad_kacis = ad_temiz.replace(".", "\\.")
    komut = (
        f"grep -qE '(^|[[:space:]]){ad_kacis}([[:space:]]|$)' /etc/hosts "
        f"&& sed -i 's/.*[[:space:]]{ad_kacis}.*/{ip_temiz}\\t{ad_temiz}/' /etc/hosts "
        f"|| printf '\\n{ip_temiz}\\t{ad_temiz}\\n' >> /etc/hosts && grep '{ad_temiz}' /etc/hosts"
    )
    return ip_temiz, ad_temiz, komut


async def komut_isi(is_id: str, cihaz_idler: list[str], komut_metni: str,
                    sudo_gerekli: bool = True, baslik_veya_zaman: str | int = 60,
                    iptal: asyncio.Event | None = None) -> None:
    if iptal is None:
        iptal = asyncio.Event()
    zaman_asimi = baslik_veya_zaman if isinstance(baslik_veya_zaman, int) else 60
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    sayac = {"gonderilen": len(cihaz_idler), "ulasilamadi": 0, "basarili": 0, "hatali": 0}

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip = cihaz["ip"]
        ad = veritabani.cihaz_adi(cihaz)
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "komut")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam", f"{ad} — {neden}")
            return
        async with sinir:
            durum_turu = await asyncio.to_thread(
                _komut_calistir_tek, is_id, cihaz, komut_metni, sudo_gerekli, zaman_asimi
            )
            if durum_turu in sayac:
                sayac[durum_turu] += 1

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))
    ozet_metin = (
        f"{sayac['gonderilen']} bilgisayara gönderildi · "
        f"{sayac['ulasilamadi']} bilgisayara ulaşılamadı · "
        f"{sayac['basarili']} başarılı · "
        f"{sayac['hatali']} hata alındı"
    )
    veritabani.is_bitir(is_id, "iptal" if iptal.is_set() else "tamamlandi", ozet_metin)


def _komut_calistir_tek(is_id: str, cihaz: dict, komut_metni: str,
                        sudo_gerekli: bool, zaman_asimi: int) -> str:
    ip = cihaz["ip"]
    ad = veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "ip": ip, "komut": komut_metni}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "ulasilamadi",
            f"{ad} — ulaşılamadı ({hata})",
            {**veri, "ulasildi": False, "rc": None, "stdout": "", "stderr": f"SSH bağlantısı kurulamadı: {hata}"},
        )
        return "ulasilamadi"
    try:
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "calisiyor", f"{ad} — komut çalıştırılıyor", veri)
        argv = ["bash", "-c", komut_metni]
        if sudo_gerekli:
            rc, cikti, hata = ssh_araclari.sudo_komut(istemci, argv, zaman=zaman_asimi)
        else:
            rc, cikti, hata = ssh_araclari.komut(istemci, argv, zaman=zaman_asimi)
        stdout_kisa = (cikti or "").strip()[:EN_BUYUK_CIKTI]
        stderr_kisa = (hata or "").strip()[:EN_BUYUK_CIKTI]
        ilk_satir = (stdout_kisa or stderr_kisa or ("OK (çıktı yok)" if rc == 0 else f"Çıkış kodu: {rc}")).splitlines()[0][:140]
        hedef_veri = {
            **veri,
            "ulasildi": True,
            "rc": rc,
            "stdout": stdout_kisa,
            "stderr": stderr_kisa,
        }
        if rc == 0:
            veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam", f"{ad} — [rc=0] {ilk_satir}", hedef_veri)
            return "basarili"
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", f"rc={rc}", f"{ad} — [rc={rc}] {ilk_satir}", hedef_veri)
        return "hatali"
    except Exception as hata:
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "hata", f"{ad} — {hata}",
            {**veri, "ulasildi": True, "rc": -1, "stdout": "", "stderr": str(hata)},
        )
        return "hatali"
    finally:
        istemci.close()


async def hosts_ekle_isi(is_id: str, cihaz_idler: list[str], ip_adresi: str,
                         alan_adi: str, iptal: asyncio.Event | None = None) -> None:
    """uzak/sinif.py içindeki atomik hosts_ekle kipini kullanarak /etc/hosts kaydı ekler."""
    if iptal is None:
        iptal = asyncio.Event()
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    sayac = {"gonderilen": len(cihaz_idler), "ulasilamadi": 0, "basarili": 0, "hatali": 0}

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip = cihaz["ip"]
        ad = veritabani.cihaz_adi(cihaz)
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "komut")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam", f"{ad} — {neden}")
            return
        async with sinir:
            durum_turu = await asyncio.to_thread(_hosts_tek, is_id, cihaz, ip_adresi, alan_adi)
            if durum_turu in sayac:
                sayac[durum_turu] += 1

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))
    ozet_metin = (
        f"{sayac['gonderilen']} bilgisayara gönderildi · "
        f"{sayac['ulasilamadi']} bilgisayara ulaşılamadı · "
        f"{sayac['basarili']} başarılı · "
        f"{sayac['hatali']} hata alındı"
    )
    veritabani.is_bitir(is_id, "iptal" if iptal.is_set() else "tamamlandi", ozet_metin)


def _hosts_tek(is_id: str, cihaz: dict, ip_adresi: str, alan_adi: str) -> str:
    ip = cihaz["ip"]
    ad = veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "ip": ip, "komut": f"/etc/hosts: {ip_adresi}\t{alan_adi}"}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "ulasilamadi", f"{ad} — ulaşılamadı ({hata})",
            {**veri, "ulasildi": False, "rc": None, "stdout": "", "stderr": f"SSH bağlantısı kurulamadı: {hata}"},
        )
        return "ulasilamadi"
    try:
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("sinif"), {"kip": "hosts_ekle", "ip": ip_adresi, "ad": alan_adi}, zaman=20
        )
        if "hata" in sonuc:
            veritabani.hedef_guncelle(
                is_id, ip, "basarisiz", "hata", f"{ad} — {sonuc['hata']}",
                {**veri, "ulasildi": True, "rc": 1, "stdout": "", "stderr": sonuc["hata"]},
            )
            return "hatali"
        mesaj = sonuc.get("mesaj") or f"{ip_adresi} -> {alan_adi} eklendi"
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam", f"{ad} — [rc=0] {mesaj}",
            {**veri, "ulasildi": True, "rc": 0, "stdout": f"{ip_adresi}\t{alan_adi}\n({mesaj})", "stderr": ""},
        )
        return "basarili"
    except Exception as hata:
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "hata", f"{ad} — {hata}",
            {**veri, "ulasildi": True, "rc": 1, "stdout": "", "stderr": str(hata)},
        )
        return "hatali"
    finally:
        istemci.close()
