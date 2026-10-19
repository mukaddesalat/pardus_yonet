"""Uygulama genel ayarları ve sabitleri.

Karar kaydına göre (istem §0): tek laboratuvar ~20-30 PC, sabit `ogrenci`
profili, yönetim bağlantısı `pardus`/`hp` hesaplarından biriyle yapılır (karar 21:
her bilgisayarda yalnız biri kalır). Günlük işler parolasız sudo ile çalışır
(karar 22); parola yalnız ilk hazırlıkta bir kez alınır.
"""

import os
from pathlib import Path

# Kalıcı veri dizini: kurulu pakette /var/lib/pardus-sinif-yonetimi (systemd
# servisi PSY_VERI_DIZINI ile verir), geliştirmede ./veri
VERI_DIZINI = Path(os.environ.get("PSY_VERI_DIZINI", "veri")).resolve()

# Sunucu
DINLEME_ADRESI = os.environ.get("PSY_ADRES", "127.0.0.1")
DINLEME_PORTU = int(os.environ.get("PSY_PORT", "8080"))

# Hesap modeli (karar 4, 21)
PROFIL_HESABI = "ogrenci"
YONETIM_HESAPLARI = ("pardus", "hp")   # tekilleştirme adayları; önerilen: ilki
VARSAYILAN_HESAP_ADAYLARI = list(YONETIM_HESAPLARI)

# Parolasız sudo (karar 22): yönetim hesabına root eşdeğeri yetki verir
SUDOERS_DOSYASI = "/etc/sudoers.d/pardus-sinif-yonetimi"

# Keşif sınırları (karar 7 ve istem §5)
EN_FAZLA_HEDEF = 256           # tek taramada genişletilebilecek adres sayısı
TARAMA_PARALELLIGI = 32        # TCP port kontrolü paralelliği
DOGRULAMA_PARALELLIGI = 8      # SSH kimlik doğrulama paralelliği
TCP_ZAMAN_ASIMI = 1.5          # saniye
SSH_ZAMAN_ASIMI = 10           # saniye
KOMUT_ZAMAN_ASIMI = 20         # saniye

# Deneme bütçesi: hesap+cihaz başına toplam parola denemesi (istem §5.4).
# Kurumun kilitleme eşiği bilinmediği için ihtiyatlı tutulur; yeniden tarama
# bütçeyi sıfırlamaz (veritabanında saklanır).
DENEME_BUTCESI = 3
DENEME_BEKLEME = 1.0           # aynı hedefe iki deneme arası saniye

# Oturum
OTURUM_SURESI_SN = 8 * 3600    # arayüz oturumu 8 saat

# Yerel .deb dağıtımı (karar 24)
EN_BUYUK_PAKET = 1024 * 1048576   # 1 GiB
PAKET_PARALELLIGI = 4

# Veyon (karar 28): yalnız öğretmenin yüklediği .deb kurulur; public key PEM olarak yüklenir
VEYON_PORT = 11100                 # Veyon sunucusu (bağlantı doğrulaması için RFB karşılaması okunur)
VEYON_ANAHTAR_VARSAYILAN = "teacher"
EN_BUYUK_ANAHTAR = 65536           # public key dosyası üst sınırı (bayt)

VERSIYON = "0.7.0"
UYGULAMA_ADI = "Lab Kaptanı"   # görünen ad; paket adı pardus-sinif-yonetimi kalır


def veri_yollari() -> dict:
    """Kalıcı dizin altındaki standart yollar."""
    return {
        "veritabani": VERI_DIZINI / "envanter.db",
        "anahtar_dizini": VERI_DIZINI / "anahtar",
        "ozel_anahtar": VERI_DIZINI / "anahtar" / "uygulama_ed25519",
        "acik_anahtar": VERI_DIZINI / "anahtar" / "uygulama_ed25519.pub",
        "kurulum_kodu": VERI_DIZINI / "kurulum_kodu",
        "log_dizini": VERI_DIZINI / "log",
        "paket_dizini": VERI_DIZINI / "paketler",
        "veyon_dizini": VERI_DIZINI / "veyon",
    }
