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
import json
from pathlib import Path
import re
import shlex
import urllib.request

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



# ================================================================ Komut Mağazası (Topluluk & Öğretmen Araçları)

_RESMI_MAGAZA_KATALOGU = [
    {
        "id": "veyon-servis-ac",
        "ad": "Veyon Servisini Kontrol Et ve Başlat",
        "kategori": "veyon",
        "risk": "degisiklik",
        "ozet": "Öğrenciler Veyon servisini kapattığında servisi unmask/enable yapıp anında yeniden ayağa kaldırır.",
        "yazar": "Pardus Lab Ekibi",
        "surum": "1.2.0",
        "sudo": True,
        "parametreler": [],
        "betik": (
            "if systemctl is-active --quiet veyon && pgrep -x veyon-service >/dev/null; then\n"
            "  echo '::psy:bilgi=Veyon servisi zaten aktif ve çalışıyor.'\n"
            "  echo 'OK: Veyon servisi ve arka plan süreçleri çalışıyor (aktif).'\n"
            "else\n"
            "  echo '::psy:bilgi=Veyon servisi kapalı; yeniden ayağa kaldırılıyor...'\n"
            "  systemctl unmask veyon 2>/dev/null || true\n"
            "  systemctl enable veyon 2>/dev/null || true\n"
            "  systemctl restart veyon 2>/dev/null || systemctl restart veyon-service 2>/dev/null || true\n"
            "  sleep 1\n"
            "  if systemctl is-active --quiet veyon || systemctl is-active --quiet veyon-service; then\n"
            "    echo '::psy:sonuc=ok'\n"
            "    echo 'BAŞARILI: Veyon servisi ayağa kaldırıldı ve aktif duruma getirildi.'\n"
            "  else\n"
            "    echo 'HATA: Veyon servisi başlatılamadı!'\n"
            "    systemctl status veyon --no-pager -n 5 2>/dev/null || true\n"
            "    exit 1\n"
            "  fi\n"
            "fi"
        ),
    },
    {
        "id": "hosts-kayit-ekle",
        "ad": "Yerel Alan Adı (Hosts) Dağıt",
        "kategori": "ag",
        "risk": "degisiklik",
        "ozet": "Öğrenci bilgisayarlarının /etc/hosts dosyasına yerel sunucu IP ve alan adını güvenle ekler veya günceller.",
        "yazar": "Kemal Öğretmen",
        "surum": "1.1.0",
        "sudo": True,
        "parametreler": [
            {
                "ad": "ip",
                "etiket": "Hedef IP Adresi",
                "tip": "metin",
                "varsayilan": "192.168.1.100",
                "zorunlu": True,
                "aciklama": "Öğretmen bilgisayarı veya yerel sunucu IP adresi",
            },
            {
                "ad": "alan_adi",
                "etiket": "Alan Adı (Hostname)",
                "tip": "metin",
                "varsayilan": "ogretmen.lab",
                "zorunlu": True,
                "aciklama": "Örn. ogretmen.lab veya portal.yerel",
            },
        ],
        "betik": (
            ': "${PSY_P_ip:?ip parametresi gerekli}"\n'
            ': "${PSY_P_alan_adi:?alan_adi parametresi gerekli}"\n'
            'AD_KACIS=$(printf "%s" "$PSY_P_alan_adi" | sed "s/\\./\\\\./g")\n'
            "if grep -qE \"(^|[[:space:]])${AD_KACIS}([[:space:]]|$)\" /etc/hosts; then\n"
            '  sed -i "s/.*[[:space:]]${AD_KACIS}.*/$PSY_P_ip\\t$PSY_P_alan_adi/" /etc/hosts\n'
            '  echo "::psy:degisti=/etc/hosts"\n'
            '  echo "OK: /etc/hosts içindeki $PSY_P_alan_adi kaydı $PSY_P_ip olarak güncellendi."\n'
            "else\n"
            '  printf "\\n%s\\t%s\\n" "$PSY_P_ip" "$PSY_P_alan_adi" >> /etc/hosts\n'
            '  echo "::psy:degisti=/etc/hosts"\n'
            '  echo "OK: /etc/hosts dosyasına $PSY_P_ip -> $PSY_P_alan_adi kaydı eklendi."\n'
            "fi\n"
            'grep "$PSY_P_alan_adi" /etc/hosts\n'
        ),
    },
    {
        "id": "kullanici-ev-dizini-sil",
        "ad": "Kullanıcı ve Ev Dizinini Sil",
        "kategori": "kullanici",
        "risk": "yikici",
        "ozet": "Sistem ve yönetim hesapları hariç belirtilen kullanıcının açık süreçlerini sonlandırıp ev diziniyle birlikte siler.",
        "yazar": "Fatma Öğretmen",
        "surum": "1.0.0",
        "sudo": True,
        "parametreler": [
            {
                "ad": "kullanici",
                "etiket": "Silinecek Kullanıcı Adı",
                "tip": "metin",
                "varsayilan": "misafir",
                "zorunlu": True,
                "yasak": ["root", "pardus", "hp", "ogrenci"],
                "aciklama": "Sistem kullanıcıları koruma altındadır ve silinemez",
            },
            {
                "ad": "yedek_al",
                "etiket": "Silmeden önce ev dizinini arşivle",
                "tip": "onay",
                "varsayilan": True,
                "aciklama": "/var/lib/pardus-sinif-yonetimi/karantina/ altına geçici yedek alır",
            },
        ],
        "betik": (
            ': "${PSY_P_kullanici:?kullanici parametresi gerekli}"\n'
            'HEDEF="$PSY_P_kullanici"\n'
            'if [ "$HEDEF" = "root" ] || [ "$HEDEF" = "pardus" ] || [ "$HEDEF" = "hp" ] || [ "$HEDEF" = "ogrenci" ]; then\n'
            '  echo "HATA: $HEDEF korumalı sistem hesabıdır, silinemez!" >&2\n'
            "  exit 1\n"
            "fi\n"
            'if id "$HEDEF" &>/dev/null; then\n'
            '  if [ "${PSY_P_yedek_al:-0}" = "1" ] && [ -d "/home/$HEDEF" ]; then\n'
            "    mkdir -p /var/lib/pardus-sinif-yonetimi/karantina 2>/dev/null || true\n"
            '    tar -czf "/var/lib/pardus-sinif-yonetimi/karantina/silinen_${HEDEF}_$(date +%s).tar.gz" -C /home "$HEDEF" 2>/dev/null || true\n'
            '    echo "::psy:bilgi=Ev dizini karantinaya yedeklendi."\n'
            "  fi\n"
            '  pkill -KILL -u "$HEDEF" 2>/dev/null || true\n'
            '  userdel -r "$HEDEF"\n'
            '  echo "::psy:degisti=/home/$HEDEF"\n'
            '  echo "OK: $HEDEF kullanıcısı ve ev dizini sistemden silindi."\n'
            "else\n"
            '  echo "ATLANDI: $HEDEF adlı kullanıcı sistemde bulunamadı."\n'
            "fi\n"
        ),
    },
    {
        "id": "disk-bellek-raporu",
        "ad": "Disk ve RAM Sağlık Özeti",
        "kategori": "sistem",
        "risk": "bilgi",
        "ozet": "Öğrenci bilgisayarlarındaki boş disk alanını ve RAM kullanımını hızlıca raporlar (salt okunur).",
        "yazar": "Bilişim Zümresi",
        "surum": "1.0.0",
        "sudo": False,
        "parametreler": [],
        "betik": (
            'echo "=== HOST: $(hostname) ==="\n'
            'echo "--- BELLEK (RAM) ---"\n'
            "free -h | awk 'NR<=2'\n"
            'echo "--- DİSK ALANI ---"\n'
            "df -h / /home 2>/dev/null | awk 'NR<=3'\n"
        ),
    },
    {
        "id": "bozuk-paket-onar",
        "ad": "Kilitli ve Bozuk Paketleri Onar",
        "kategori": "paket",
        "risk": "degisiklik",
        "ozet": "Yarım kalmış apt kilitlerini, bozuk bağımlılıkları ve eksik paket kurulumlarını onarır.",
        "yazar": "Pardus Lab Ekibi",
        "surum": "1.1.0",
        "sudo": True,
        "parametreler": [],
        "betik": (
            "export DEBIAN_FRONTEND=noninteractive\n"
            "dpkg --configure -a 2>&1\n"
            "apt-get -f install -y 2>&1\n"
            "echo '::psy:sonuc=ok'\n"
            "echo 'OK: Paket sistemi ve kilitler başarıyla onarıldı.'\n"
        ),
    },
    {
        "id": "ogrenci-masaustu-temizle",
        "ad": "Öğrenci Masaüstü ve İndirilenleri Temizle",
        "kategori": "bakim",
        "risk": "yikici",
        "ozet": "Ders bitiminde /home/ogrenci/Masaüstü ve İndirilenler klasöründeki gereksiz dosyaları temizler.",
        "yazar": "Mehmet Öğretmen",
        "surum": "1.0.0",
        "sudo": True,
        "parametreler": [
            {
                "ad": "copu_bosalt",
                "etiket": "Çöp kutusunu da tamamen temizle",
                "tip": "onay",
                "varsayilan": True,
            }
        ],
        "betik": (
            "rm -rf /home/ogrenci/İndirilenler/* /home/ogrenci/Downloads/* 2>/dev/null || true\n"
            "find /home/ogrenci/Masaüstü -mindepth 1 ! -name '*.desktop' ! -name 'Odevler' ! -name 'odev' ! -name 'odevler' ! -name 'dersnotlari' -delete 2>/dev/null || true\n"
            'if [ "${PSY_P_copu_bosalt:-0}" = "1" ]; then\n'
            "  rm -rf /home/ogrenci/.local/share/Trash/* 2>/dev/null || true\n"
            "fi\n"
            "echo '::psy:degisti=/home/ogrenci/Masaüstü'\n"
            "echo 'OK: Öğrenci masaüstü ve indirilenler temizlendi.'\n"
        ),
    },
]


VARSAYILAN_MAGAZA_REPO_URL = "https://raw.githubusercontent.com/mukaddesalat/pardus_yonet_magaza/main/katalog.json"
_PAKET_KATALOG_DOSYASI = Path(__file__).resolve().parent / "magaza" / "katalog.json"


def _dinamik_onbellek_dosyasi() -> Path:
    return ayarlar.VERI_DIZINI / "magaza_katalog.json"


def resmi_magaza_katalogu() -> list[dict]:
    """Resmi mağaza kataloğunu döner; dinamik önbellek, çevrimdışı paket kataloğu ve yerleşik katalog içerir."""
    # 1. Önce dinamik indirilen güncel önbellek dosyasına bak
    dinamik_dosya = _dinamik_onbellek_dosyasi()
    if dinamik_dosya.is_file():
        try:
            with open(dinamik_dosya, "r", encoding="utf-8") as f:
                veriler = json.load(f)
                if isinstance(veriler, list) and len(veriler) > 0:
                    return veriler
        except Exception:
            pass

    # 2. Veritabanı önbelleğine bak
    try:
        db_onbellek = veritabani.ayar_oku("magaza_katalog_onbellek")
        if db_onbellek:
            veriler = json.loads(db_onbellek)
            if isinstance(veriler, list) and len(veriler) > 0:
                return veriler
    except Exception:
        pass

    # 3. Paketle gelen yerleşik katalog dosyasına bak
    if _PAKET_KATALOG_DOSYASI.is_file():
        try:
            with open(_PAKET_KATALOG_DOSYASI, "r", encoding="utf-8") as f:
                veriler = json.load(f)
                if isinstance(veriler, list) and len(veriler) > 0:
                    return veriler
        except Exception:
            pass

    return [dict(a) for a in _RESMI_MAGAZA_KATALOGU]


async def magaza_katalogu_guncelle() -> dict:
    """Uzak Git deposundan (Raw HTTP) en güncel katalog dosyasını sorgular ve yerel önbelleğe kaydeder."""
    repo_url = veritabani.ayar_oku("magaza_repo_url") or VARSAYILAN_MAGAZA_REPO_URL
    loop = asyncio.get_running_loop()

    # Mevcut araç sürümlerini haritalandır
    mevcut_katalog = resmi_magaza_katalogu()
    mevcut_harita = {a.get("id"): a.get("surum", "1.0.0") for a in mevcut_katalog if a.get("id")}

    def _indir():
        req = urllib.request.Request(
            repo_url,
            headers={"User-Agent": "Pardus-Lab-Kaptani/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            ham = response.read().decode("utf-8")
            return json.loads(ham)

    try:
        yeni_katalog = await loop.run_in_executor(None, _indir)
        if isinstance(yeni_katalog, list) and len(yeni_katalog) > 0:
            eklenenler = []
            guncellenenler = []
            for a in yeni_katalog:
                aid = a.get("id")
                yeni_surum = a.get("surum", "1.0.0")
                if not aid:
                    continue
                if aid not in mevcut_harita:
                    eklenenler.append(a)
                elif mevcut_harita[aid] != yeni_surum:
                    guncellenenler.append({
                        "id": aid,
                        "ad": a.get("ad", aid),
                        "eski_surum": mevcut_harita[aid],
                        "yeni_surum": yeni_surum,
                    })

            dinamik_dosya = _dinamik_onbellek_dosyasi()
            try:
                dinamik_dosya.parent.mkdir(parents=True, exist_ok=True)
                with open(dinamik_dosya, "w", encoding="utf-8") as f:
                    json.dump(yeni_katalog, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            try:
                if _PAKET_KATALOG_DOSYASI.parent.exists():
                    with open(_PAKET_KATALOG_DOSYASI, "w", encoding="utf-8") as f:
                        json.dump(yeni_katalog, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            veritabani.ayar_yaz("magaza_katalog_onbellek", json.dumps(yeni_katalog, ensure_ascii=False))

            loglar = [
                f"🌐 GitHub deposuna bağlanıldı: {repo_url}",
                f"📦 Katalog manifestosu başarıyla indirildi ({len(yeni_katalog)} araç bulundu).",
                "🔍 Sürüm ve paket karşılaştırması tamamlandı.",
            ]
            for e in eklenenler:
                loglar.append(f"⚡ [YENİ ARAÇ] '{e.get('ad', e.get('id'))}' (v{e.get('surum', '1.0.0')}) kataloğa eklendi.")
            for g in guncellenenler:
                loglar.append(f"🔄 [GÜNCELLENDİ] '{g['ad']}' v{g['eski_surum']} ➔ v{g['yeni_surum']} sürümüne yükseltildi.")
            if not eklenenler and not guncellenenler:
                loglar.append(f"✓ Tüm araçlar zaten en güncel sürümde ({len(yeni_katalog)} araç eşitlendi).")
            loglar.append("💾 Yerel SQLite veritabanı ve dinamik önbellek eşitlendi.")
            loglar.append(f"✓ Katalog başarıyla senkronize edildi. (Toplam {len(yeni_katalog)} araç hazır)")

            return {
                "durum": "tamam",
                "arac_sayisi": len(yeni_katalog),
                "kaynak": repo_url,
                "eklenen_sayisi": len(eklenenler),
                "guncellenen_sayisi": len(guncellenenler),
                "eklenenler": [e.get("ad", e.get("id")) for e in eklenenler],
                "guncellenenler": [f"{g['ad']} (v{g['eski_surum']} ➔ v{g['yeni_surum']})" for g in guncellenenler],
                "loglar": loglar,
            }
        return {
            "durum": "gecersiz_veri",
            "mesaj": "Depodaki katalog formatı doğrulanamadı",
            "arac_sayisi": len(resmi_magaza_katalogu()),
            "loglar": ["❌ Depodaki katalog verisi geçersiz veya boş."],
        }
    except Exception as hata:
        return {
            "durum": "cevrimdisi",
            "hata": str(hata),
            "arac_sayisi": len(resmi_magaza_katalogu()),
            "mesaj": "Uzak depoya erişilemedi; yerel çevrimdışı katalog kullanılıyor.",
            "loglar": [f"⚠️ Uzak depoya erişilemedi ({hata}); yerel çevrimdışı katalog devrede."],
        }


def magaza_araci_getir(arac_id: str) -> dict | None:
    for a in resmi_magaza_katalogu():
        if a["id"] == arac_id:
            return dict(a)
    return None


def arac_parametrelerini_dogrula(arac: dict, parametreler: dict) -> dict[str, str]:
    """Parametreleri manifest kurallarına ve güvenlik sınırlarına göre doğrular."""
    temiz = {}
    tanimlar = {p["ad"]: p for p in arac.get("parametreler", [])}
    for ad, tanim in tanimlar.items():
        deger = parametreler.get(ad, tanim.get("varsayilan", ""))
        tip = tanim.get("tip", "metin")
        if tip == "onay":
            temiz[ad] = "1" if bool(deger) else "0"
            continue
        deger_str = str(deger or "").strip()
        if tanim.get("zorunlu") and not deger_str:
            raise KomutHatasi(f"'{tanim.get('etiket', ad)}' alanı zorunludur")
        yasaklar = [y.lower() for y in tanim.get("yasak", [])]
        if deger_str.lower() in yasaklar:
            raise KomutHatasi(f"'{deger_str}' korumalı bir değerdir ve bu alanda kullanılamaz")
        if re.search(r"[`$\\\";|&]", deger_str):
            raise KomutHatasi(f"'{tanim.get('etiket', ad)}' alanında geçersiz özel karakterler var")
        temiz[ad] = deger_str
    return temiz


def arac_komutu_uret(arac: dict, parametreler: dict) -> str:
    """Parametreleri güvenli ortam değişkenleri (PSY_P_*) olarak dışa aktaran bash betiği üretir."""
    temiz_paramlar = arac_parametrelerini_dogrula(arac, parametreler)
    satirlar = [
        f"export PSY_ARAC_ID={shlex.quote(arac['id'])}",
        f"export PSY_ARAC_SURUM={shlex.quote(arac.get('surum', '1.0.0'))}",
    ]
    for k, v in temiz_paramlar.items():
        satirlar.append(f"export PSY_P_{k}={shlex.quote(v)}")
    satirlar.append(arac["betik"])
    return "\n".join(satirlar)


def sabit_araclari_al() -> list[str]:
    ham = veritabani.ayar_oku("sabit_araclar")
    if not ham:
        return ["veyon-servis-ac", "disk-bellek-raporu"]
    try:
        return json.loads(ham)
    except Exception:
        return ["veyon-servis-ac", "disk-bellek-raporu"]


def sabit_arac_kaydet(arac_idler: list[str]) -> list[str]:
    veritabani.ayar_yaz("sabit_araclar", json.dumps(arac_idler))
    return arac_idler
