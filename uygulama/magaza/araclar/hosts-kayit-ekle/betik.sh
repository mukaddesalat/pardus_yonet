: "${PSY_P_ip:?ip parametresi gerekli}"
: "${PSY_P_alan_adi:?alan_adi parametresi gerekli}"
AD_KACIS=$(printf "%s" "$PSY_P_alan_adi" | sed "s/\./\\./g")
if grep -qE "(^|[[:space:]])${AD_KACIS}([[:space:]]|$)" /etc/hosts; then
  sed -i "s/.*[[:space:]]${AD_KACIS}.*/$PSY_P_ip\t$PSY_P_alan_adi/" /etc/hosts
  echo "::psy:degisti=/etc/hosts"
  echo "OK: /etc/hosts içindeki $PSY_P_alan_adi kaydı $PSY_P_ip olarak güncellendi."
else
  printf "\n%s\t%s\n" "$PSY_P_ip" "$PSY_P_alan_adi" >> /etc/hosts
  echo "::psy:degisti=/etc/hosts"
  echo "OK: /etc/hosts dosyasına $PSY_P_ip -> $PSY_P_alan_adi kaydı eklendi."
fi
grep "$PSY_P_alan_adi" /etc/hosts
