#!/usr/bin/env bash
# Lab Kaptanı — Güncellenebilir Paket Sayacı ve Raporu
set -e

ONBELLEK="${PSY_P_onbellek_guncelle:-hayir}"
DETAY="${PSY_P_detay_goster:-ayrintili}"

HOSTNAME_VAL=$(hostname 2>/dev/null || cat /etc/hostname 2>/dev/null || echo "Bilinmiyor")
IP_VAL=$(hostname -I 2>/dev/null | awk '{print $1}')

echo "=================================================="
echo "  PARDUS PAKET GÜNCELLEME SAYACI VE ANALİZİ"
echo "  Bilgisayar: $HOSTNAME_VAL ($IP_VAL)"
echo "  Tarih: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================================="

if [ "$ONBELLEK" = "evet" ]; then
    echo -e "\n[*] Paket depoları kontrol ediliyor (apt-get update)..."
    if [ "$(id -u)" -eq 0 ] || sudo -n true 2>/dev/null; then
        sudo -n apt-get update -qq || echo "[!] Uyarı: apt-get update kısmi hata verdi, devam ediliyor."
    else
        echo "[!] Sudo yetkisi bulunamadı, mevcut önbellek ile devam ediliyor."
    fi
fi

# Debian/Pardus simülasyon çıktısını al
SIM_OUT=$(LC_ALL=C apt-get -s dist-upgrade 2>/dev/null || true)

# Yükseltilecek toplam paket sayısı
UPG_COUNT=$(echo "$SIM_OUT" | grep -E "^[0-9]+ upgraded" | awk '{print $1}')
[ -z "$UPG_COUNT" ] && UPG_COUNT=0

# Güvenlik güncellemeleri
SEC_COUNT=$(echo "$SIM_OUT" | grep "^Inst " | grep -Ei "(security|debian-security|pardus-security|-updates)" | wc -l || echo 0)

# Çekirdek (Kernel) güncellemeleri
KERNEL_UPG=$(echo "$SIM_OUT" | grep "^Inst linux-image" | wc -l || echo 0)

echo ""
echo "::psy:bilgi=Güncelleme analizi tamamlandı: $UPG_COUNT paket güncellenebilir."

if [ "$UPG_COUNT" -eq 0 ]; then
    echo "  Durum                          : [GÜNCEL] Sistem günceldir."
    echo "  Toplam Güncellenebilir Paket   : 0"
    echo "  Güvenlik Güncellemesi          : 0"
    echo "=================================================="
    echo "::psy:sonuc=guncel"
    exit 0
fi

echo "  Durum                          : [GÜNCELLEME GEREKLİ]"
echo "  Toplam Güncellenebilir Paket   : $UPG_COUNT"
echo "  Güvenlik Güncellemesi          : $SEC_COUNT"
if [ "$KERNEL_UPG" -gt 0 ]; then
    echo "  Çekirdek (Kernel) Güncellemesi : VAR ($KERNEL_UPG adet yeni çekirdek paketi)"
else
    echo "  Çekirdek (Kernel) Güncellemesi : Yok"
fi
echo "=================================================="

if [ "$DETAY" = "ayrintili" ]; then
    echo ""
    echo "Güncellenecek Paketlerin Listesi:"
    echo "--------------------------------------------------"
    echo "$SIM_OUT" | grep "^Inst " | while read -r line; do
        PKG=$(echo "$line" | awk '{print $2}')
        NEW_VER=$(echo "$line" | sed -n 's/.*(\(.*\) .*/\1/p' | awk '{print $1}')
        IS_SEC=$(echo "$line" | grep -Ei "(security|debian-security|-updates)" >/dev/null && echo "[GÜVENLİK]" || echo "")
        printf "  %-32s -> %-20s %s\n" "$PKG" "$NEW_VER" "$IS_SEC"
    done
    echo "--------------------------------------------------"
fi

echo ""
echo "Öneri:"
if [ "$SEC_COUNT" -gt 0 ]; then
    echo "  [DİKKAT] $SEC_COUNT adet güvenlik güncellemesi mevcut! En kısa sürede güncellemeniz önerilir."
fi
echo "  Toplu güncellemek için: Lab Kaptanı 'Yazılım Merkezi' veya 'Serbest Uçbirim' üzerinden 'sudo apt-get upgrade -y' komutunu verebilirsiniz."
echo "=================================================="

