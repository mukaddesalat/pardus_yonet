export DEBIAN_FRONTEND=noninteractive
dpkg --configure -a 2>&1
apt-get -f install -y 2>&1
echo '::psy:sonuc=ok'
echo 'OK: Paket sistemi ve kilitler başarıyla onarıldı.'
