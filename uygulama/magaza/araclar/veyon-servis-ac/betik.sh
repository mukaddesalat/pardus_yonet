if systemctl is-active --quiet veyon && pgrep -x veyon-service >/dev/null; then
  echo '::psy:bilgi=Veyon servisi zaten aktif ve çalışıyor.'
  echo 'OK: Veyon servisi ve arka plan süreçleri çalışıyor (aktif).'
else
  echo '::psy:bilgi=Veyon servisi kapalı; yeniden ayağa kaldırılıyor...'
  systemctl unmask veyon 2>/dev/null || true
  systemctl enable veyon 2>/dev/null || true
  systemctl restart veyon 2>/dev/null || systemctl restart veyon-service 2>/dev/null || true
  sleep 1
  if systemctl is-active --quiet veyon || systemctl is-active --quiet veyon-service; then
    echo '::psy:sonuc=ok'
    echo 'BAŞARILI: Veyon servisi ayağa kaldırıldı ve aktif duruma getirildi.'
  else
    echo 'HATA: Veyon servisi başlatılamadı!'
    systemctl status veyon --no-pager -n 5 2>/dev/null || true
    exit 1
  fi
fi