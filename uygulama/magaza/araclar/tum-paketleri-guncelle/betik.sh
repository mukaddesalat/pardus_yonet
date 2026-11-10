#!/usr/bin/env bash
set -euo pipefail

# Debian / Pardus otomatik güncelleme kilitlerini ve sessiz modu ayarla
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

echo "[*] APT depo paket listeleri güncelleniyor (apt-get update)..."
apt-get update

echo "[*] Sistem ve tüm paketler en yeni sürüme yükseltiliyor (apt-get full-upgrade)..."
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" full-upgrade

PARAM_AUTOREMOVE="${PARAM_AUTOREMOVE:-true}"
if [ "$PARAM_AUTOREMOVE" = "true" ] || [ "$PARAM_AUTOREMOVE" = "1" ]; then
  echo "[*] Artık gerekmeyen eski paketler ve eski çekirdekler temizleniyor (autoremove --purge)..."
  apt-get -y autoremove --purge 2>/dev/null || true
fi

PARAM_CLEAN="${PARAM_CLEAN:-true}"
if [ "$PARAM_CLEAN" = "true" ] || [ "$PARAM_CLEAN" = "1" ]; then
  echo "[*] İndirilen .deb paket arşivi temizleniyor (clean)..."
  apt-get clean 2>/dev/null || true
fi

echo "[✓] Tüm sistem ve paket güncellemeleri başarıyla tamamlandı."
