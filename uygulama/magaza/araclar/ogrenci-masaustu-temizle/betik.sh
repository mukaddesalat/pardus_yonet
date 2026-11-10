rm -rf /home/ogrenci/İndirilenler/* /home/ogrenci/Downloads/* 2>/dev/null || true
find /home/ogrenci/Masaüstü -mindepth 1 ! -name '*.desktop' -delete 2>/dev/null || true
if [ "${PSY_P_copu_bosalt:-0}" = "1" ]; then
  rm -rf /home/ogrenci/.local/share/Trash/* 2>/dev/null || true
fi
echo '::psy:degisti=/home/ogrenci/Masaüstü'
echo 'OK: Öğrenci masaüstü ve indirilenler temizlendi.'
