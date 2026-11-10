echo "[*] Açık harici tarayıcı süreçleri sonlandırılıyor..."
for proc in firefox firefox-esr chrome brave opera msedge vivaldi-bin epiphany midori falkon; do
  pkill -x "$proc" 2>/dev/null || true
done

echo "[*] Chromium kurulu mu denetleniyor..."
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  echo "[*] Chromium bulunamadı; Pardus deposundan kuruluyor..."
  echo "::psy:bilgi=Chromium ve Türkçe dil paketi kuruluyor..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq 2>&1 || true
  apt-get install -y --no-install-recommends chromium chromium-l10n 2>&1
fi

CHROMIUM_BIN=$(command -v chromium 2>/dev/null || command -v chromium-browser 2>/dev/null || true)
if [ -z "$CHROMIUM_BIN" ]; then
  echo "HATA: Chromium sistemi bulunamadı veya kurulamadı!" >&2
  exit 1
fi
echo "[+] Chromium hazır: $CHROMIUM_BIN"

echo "[*] Kurulu harici tarayıcılar taranıyor..."
POTANSIYEL=(
  "firefox" "firefox-esr" "google-chrome-stable" "google-chrome-beta"
  "google-chrome-unstable" "brave-browser" "brave-keyring" "microsoft-edge-stable"
  "microsoft-edge-beta" "microsoft-edge-dev" "opera-stable" "opera-beta"
  "opera-developer" "vivaldi-stable" "epiphany-browser" "midori" "falkon" "konqueror"
)

KALDIRILACAK=()
for pkg in "${POTANSIYEL[@]}"; do
  if dpkg -s "$pkg" 2>/dev/null | grep -q "Status: install ok installed"; then
    KALDIRILACAK+=("$pkg")
  fi
done

while IFS= read -r lpkg; do
  [ -n "$lpkg" ] && KALDIRILACAK+=("$lpkg")
done < <(dpkg-query -W -f='${Package} ${Status}\n' 'firefox*' 2>/dev/null | grep "install ok installed" | awk '{print $1}')

if [ ${#KALDIRILACAK[@]} -gt 0 ]; then
  KALDIR_LISTE=$(printf "%s\n" "${KALDIRILACAK[@]}" | sort -u | tr '\n' ' ')
  echo "[*] Tespit edilen harici tarayıcılar kaldırılıyor: $KALDIR_LISTE"
  echo "::psy:bilgi=Kaldırılıyor: $KALDIR_LISTE"
  export DEBIAN_FRONTEND=noninteractive
  apt-get purge -y $KALDIR_LISTE 2>&1 || apt-get remove -y $KALDIR_LISTE 2>&1
  echo "::psy:degisti=paketler"
else
  echo "[+] Kurulu harici APT tarayıcısı bulunamadı."
fi

if command -v flatpak >/dev/null 2>&1; then
  for flat in org.mozilla.firefox com.google.Chrome com.brave.Browser com.microsoft.Edge com.opera.Opera tv.falkon.Falkon; do
    if flatpak list --app 2>/dev/null | grep -q "$flat"; then
      echo "[*] Flatpak tarayıcısı kaldırılıyor: $flat"
      flatpak uninstall -y --noninteractive "$flat" 2>/dev/null || true
    fi
  done
fi

if command -v snap >/dev/null 2>&1; then
  for sn in firefox brave edge opera; do
    if snap list "$sn" 2>/dev/null | grep -q "^$sn "; then
      echo "[*] Snap tarayıcısı kaldırılıyor: $sn"
      snap remove "$sn" 2>/dev/null || true
    fi
  done
fi

echo "[*] Chromium varsayılan sistem tarayıcısı olarak yapılandırılıyor..."
update-alternatives --set x-www-browser "$CHROMIUM_BIN" 2>/dev/null || true
update-alternatives --set gnome-www-browser "$CHROMIUM_BIN" 2>/dev/null || true

DESKTOP_FILE=""
for f in /usr/share/applications/chromium.desktop /usr/share/applications/chromium-browser.desktop; do
  if [ -f "$f" ]; then
    DESKTOP_FILE=$(basename "$f")
    break
  fi
done
[ -z "$DESKTOP_FILE" ] && DESKTOP_FILE="chromium.desktop"

mkdir -p /etc/xdg
MIME_FILE="/etc/xdg/mimeapps.list"
touch "$MIME_FILE"
if ! grep -q "^\[Default Applications\]" "$MIME_FILE" 2>/dev/null; then
  printf "[Default Applications]\n" >> "$MIME_FILE"
fi

MIME_TIPLERI=(
  "text/html"
  "text/xml"
  "application/xhtml+xml"
  "x-scheme-handler/http"
  "x-scheme-handler/https"
  "x-scheme-handler/about"
  "x-scheme-handler/unknown"
)

for m in "${MIME_TIPLERI[@]}"; do
  if grep -q "^$m=" "$MIME_FILE" 2>/dev/null; then
    sed -i "s|^$m=.*|$m=$DESKTOP_FILE;|" "$MIME_FILE"
  else
    sed -i "/^\[Default Applications\]/a $m=$DESKTOP_FILE;" "$MIME_FILE"
  fi
done

mkdir -p /etc/skel/.config
cp -f "$MIME_FILE" /etc/skel/.config/mimeapps.list 2>/dev/null || true

for UDIR in /home/*; do
  [ -d "$UDIR" ] || continue
  U_NAME=$(basename "$UDIR")
  mkdir -p "$UDIR/.config"
  cp -f "$MIME_FILE" "$UDIR/.config/mimeapps.list" 2>/dev/null || true
  chown "$U_NAME:$U_NAME" "$UDIR/.config" "$UDIR/.config/mimeapps.list" 2>/dev/null || true
done

if [ "${PSY_P_artiklari_temizle:-1}" = "1" ]; then
  echo "[*] Harici tarayıcı profil artıkları ve önbellekleri temizleniyor..."
  for UDIR in /home/*; do
    [ -d "$UDIR" ] || continue
    rm -rf "$UDIR/.mozilla" "$UDIR/.cache/mozilla" 2>/dev/null || true
    rm -rf "$UDIR/.config/google-chrome" "$UDIR/.cache/google-chrome" 2>/dev/null || true
    rm -rf "$UDIR/.config/BraveSoftware" "$UDIR/.cache/BraveSoftware" 2>/dev/null || true
    rm -rf "$UDIR/.config/microsoft-edge" "$UDIR/.cache/microsoft-edge" 2>/dev/null || true
    rm -rf "$UDIR/.config/opera" "$UDIR/.cache/opera" 2>/dev/null || true
    rm -rf "$UDIR/.config/vivaldi" "$UDIR/.cache/vivaldi" 2>/dev/null || true
  done
  echo "::psy:degisti=tarayici_profilleri"
fi

for UDIR in /home/*; do
  [ -d "$UDIR" ] || continue
  for ddir in "$UDIR/Masaüstü" "$UDIR/Desktop"; do
    if [ -d "$ddir" ]; then
      rm -f "$ddir"/*firefox*.desktop "$ddir"/*chrome*.desktop "$ddir"/*brave*.desktop \
            "$ddir"/*edge*.desktop "$ddir"/*opera*.desktop "$ddir"/*vivaldi*.desktop 2>/dev/null || true
    fi
  done
done

if [ "${PSY_P_masaustu_kisayol:-1}" = "1" ]; then
  echo "[*] Masaüstüne Chromium kısayolu yerleştiriliyor..."
  SRC_DESKTOP="/usr/share/applications/$DESKTOP_FILE"
  if [ -f "$SRC_DESKTOP" ]; then
    for UDIR in /home/*; do
      [ -d "$UDIR" ] || continue
      U_NAME=$(basename "$UDIR")
      for ddir in "$UDIR/Masaüstü" "$UDIR/Desktop"; do
        if [ -d "$ddir" ]; then
          cp -f "$SRC_DESKTOP" "$ddir/$DESKTOP_FILE"
          chmod 755 "$ddir/$DESKTOP_FILE" 2>/dev/null || true
          chown "$U_NAME:$U_NAME" "$ddir/$DESKTOP_FILE" 2>/dev/null || true
        fi
      done
    done
    echo "::psy:degisti=/home/ogrenci/Masaüstü"
  fi
fi

echo "::psy:sonuc=ok"
echo "BAŞARILI: Harici tarayıcılar temizlendi; Chromium varsayılan yapıldı."
