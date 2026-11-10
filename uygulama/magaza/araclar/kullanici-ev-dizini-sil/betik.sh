: "${PSY_P_kullanici:?kullanici parametresi gerekli}"
HEDEF="$PSY_P_kullanici"
if [ "$HEDEF" = "root" ] || [ "$HEDEF" = "pardus" ] || [ "$HEDEF" = "hp" ] || [ "$HEDEF" = "ogrenci" ]; then
  echo "HATA: $HEDEF korumalı sistem hesabıdır, silinemez!" >&2
  exit 1
fi
if id "$HEDEF" &>/dev/null; then
  if [ "${PSY_P_yedek_al:-0}" = "1" ] && [ -d "/home/$HEDEF" ]; then
    mkdir -p /var/lib/pardus-sinif-yonetimi/karantina 2>/dev/null || true
    tar -czf "/var/lib/pardus-sinif-yonetimi/karantina/silinen_${HEDEF}_$(date +%s).tar.gz" -C /home "$HEDEF" 2>/dev/null || true
    echo "::psy:bilgi=Ev dizini karantinaya yedeklendi."
  fi
  pkill -KILL -u "$HEDEF" 2>/dev/null || true
  userdel -r "$HEDEF"
  echo "::psy:degisti=/home/$HEDEF"
  echo "OK: $HEDEF kullanıcısı ve ev dizini sistemden silindi."
else
  echo "ATLANDI: $HEDEF adlı kullanıcı sistemde bulunamadı."
fi
