pkill -f chromium 2>/dev/null || true
pkill -f firefox 2>/dev/null || true
rm -rf /home/ogrenci/.cache/chromium/Default/* 2>/dev/null || true
rm -rf /home/ogrenci/.cache/mozilla/firefox/* 2>/dev/null || true
echo '::psy:sonuc=ok'
echo 'OK: Tarayıcı önbelleği ve açık oturumlar güvenle temizlendi.'
