"""Yönetim Uygulaması (Lab Kaptanı) Tam Sistem Yedekleme, Taşıma ve Geri Yükleme Modülü.

Bu modül; öğretmen bilgisayarındaki yönetim uygulamasını başka bir bilgisayara
eksiksiz taşımak veya düzenli aralıklarla tam yedek almak için tasarlanmıştır.

Yedek Arşivi (.tar.gz) İçeriği (`pardus-sinif-yonetimi-yedek/`):
- `manifest.json`   : Sürüm, zaman, okul/cihaz/öğretmen sayıları ve tüm dosyaların SHA-256 özetleri
- `yedekten-kur.sh` : Sıfırdan Pardus kurulu yeni bir bilgisayarda tek komutla `.deb` paketini
                      kuran, tüm veritabanlarını/SSH anahtarlarını geri yükleyen ve servisleri başlatan betik
- `BENIOKU.txt`     : Hem terminalden (`yedekten-kur.sh`) hem de web arayüzünden (`M5-S1`) geri yükleme kılavuzu
- `paket/`          : `pardus-sinif-yonetimi_<sürüm>_amd64.deb` ve `.sha256` kurulum paketi
- `veri/`           : `envanter.db` (SQLite Online Backup), `anahtar/` (Ed25519 SSH çifti),
                      `veyon/` (Veyon .deb ve public key), `duvar_kagidi/` (galeri), `paketler/`
- `odev/`           : `odev.db` (sınıflar, öğrenci kodları, ödevler) ve `teslimler/`
- `sistem/`         : `/etc/pardus-sinif-yonetimi/ortam` (port ve ağ yapılandırması)
"""

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import socket
import sqlite3
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import ayarlar, veritabani
from .odev import ortak as odev_ortak
from .odev import vt as odev_vt

KOK_DIZIN = Path(__file__).resolve().parent.parent
ARSIV_KOK = "pardus-sinif-yonetimi-yedek"
FORMAT_ADI = "pardus-sinif-yonetimi-yedek"
FORMAT_SURUMU = 1
DOSYA_DESENI = re.compile(r"^pardus-sinif-yonetimi-yedek_[A-Za-z0-9._-]+\.tar\.gz$")
EN_BUYUK_ARSIV = 1536 * 1048576  # 1.5 GiB üst sınır


class SistemYedekHatasi(Exception):
    """Yedekleme veya geri yükleme sırasında oluşan kullanıcıya gösterilebilir hata."""


def yedek_dizini() -> Path:
    d = ayarlar.veri_yollari()["sistem_yedek_dizini"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _onbellek_dizini() -> Path:
    d = yedek_dizini() / "onbellek"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256_bytes(veri: bytes) -> str:
    return hashlib.sha256(veri).hexdigest()


def _sha256_dosya(yol: Path) -> str:
    ozet = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1048576), b""):
            ozet.update(parca)
    return ozet.hexdigest()


# ------------------------------------------------------------------ .deb paketi bulma / üretme

def _kurulu_sistemden_deb_uret(hedef_deb: Path) -> Path | None:
    """Kurulu Linux sisteminde (/opt/pardus-sinif-yonetimi) mevcut dosyalardan .deb paketini yeniden üretir."""
    opt_kok = Path("/opt/pardus-sinif-yonetimi")
    dpkg_info = Path("/var/lib/dpkg/info")
    if not opt_kok.is_dir() or not (opt_kok / "uygulama" / "ana.py").is_file():
        return None
    try:
        zaman = int(time.time())
        girdiler: list[tuple[str, str, int, bytes | str | None]] = []
        dizinler: set[str] = set()

        def dizin_ekle(goreli: str) -> None:
            parcalar = goreli.strip("/").split("/")[:-1]
            for i in range(1, len(parcalar) + 1):
                dizinler.add("/".join(parcalar[:i]))

        def dosya_ekle(kaynak: Path, hedef_yol: str, varsayilan_izin: int = 0o644) -> None:
            if not kaynak.exists() and not kaynak.is_symlink():
                return
            dizin_ekle(hedef_yol)
            if kaynak.is_symlink():
                girdiler.append((hedef_yol, "bag", 0o777, os.readlink(kaynak)))
            elif kaynak.is_file():
                st = kaynak.stat()
                izin = (st.st_mode & 0o755) or varsayilan_izin
                girdiler.append((hedef_yol, "dosya", izin, kaynak.read_bytes()))

        for yol in sorted(opt_kok.rglob("*")):
            if "__pycache__" in yol.parts or yol.suffix == ".pyc":
                continue
            if yol.is_dir() and not yol.is_symlink():
                continue
            goreli = "opt/pardus-sinif-yonetimi/" + yol.relative_to(opt_kok).as_posix()
            dosya_ekle(yol, goreli)

        sistem_yollari = [
            ("lib/systemd/system/pardus-sinif-yonetimi.service", 0o644),
            ("lib/systemd/system/pardus-sinif-odev.service", 0o644),
            ("usr/bin/pardus-sinif-yonetimi", 0o755),
            ("usr/lib/pardus-sinif-yonetimi/kurulum-kodu", 0o755),
            ("usr/share/polkit-1/actions/tr.org.pardus.sinif-yonetimi.policy", 0o644),
            ("usr/share/applications/pardus-sinif-yonetimi.desktop", 0o644),
            ("usr/share/icons/hicolor/scalable/apps/pardus-sinif-yonetimi.svg", 0o644),
        ]
        for goreli, izin in sistem_yollari:
            dosya_ekle(Path("/") / goreli, goreli, izin)

        doc_kok = Path("/usr/share/doc/pardus-sinif-yonetimi")
        if doc_kok.is_dir():
            for yol in sorted(doc_kok.rglob("*")):
                if yol.is_file():
                    goreli = "usr/share/doc/pardus-sinif-yonetimi/" + yol.relative_to(doc_kok).as_posix()
                    dosya_ekle(yol, goreli, 0o644)

        tum_girdiler = [(d, "dizin", 0o755, None) for d in sorted(dizinler)]
        tum_girdiler.extend(sorted(girdiler, key=lambda x: x[0]))

        toplam_boyut = sum(len(v) for _, t, _, v in tum_girdiler if t == "dosya" and isinstance(v, bytes))
        md5_satirlari = "".join(
            f"{hashlib.md5(v, usedforsecurity=False).hexdigest()}  {y}\n"
            for y, t, _, v in tum_girdiler if t == "dosya" and isinstance(v, bytes)
        )
        kontrol = (
            "Package: pardus-sinif-yonetimi\n"
            f"Version: {ayarlar.VERSIYON}\n"
            "Architecture: amd64\n"
            "Maintainer: Pardus Sinif Yonetimi <root@localhost>\n"
            f"Installed-Size: {math.ceil(toplam_boyut / 1024)}\n"
            "Depends: libc6 (>= 2.28), systemd, passwd\n"
            "Recommends: xdg-utils, pkexec | policykit-1, zenity\n"
            "Section: admin\n"
            "Priority: optional\n"
            "Description: Pardus okul laboratuvarlari icin merkezi yonetim\n"
        )
        kontrol_girdileri: list[tuple[str, str, int, bytes | str | None]] = [
            ("control", "dosya", 0o644, kontrol.encode("utf-8")),
            ("md5sums", "dosya", 0o644, md5_satirlari.encode("utf-8")),
        ]
        for betik in ("postinst", "prerm", "postrm"):
            b_yol = dpkg_info / f"pardus-sinif-yonetimi.{betik}"
            if not b_yol.is_file():
                b_yol = KOK_DIZIN / "paketleme" / "debian" / betik
            if b_yol.is_file():
                kontrol_girdileri.append((betik, "dosya", 0o755, b_yol.read_bytes().replace(b"\r\n", b"\n")))

        def _tar_xz_uret(liste: list[tuple]) -> bytes:
            tampon = io.BytesIO()
            with tarfile.open(fileobj=tampon, mode="w:xz", format=tarfile.GNU_FORMAT, preset=3) as tf:
                kok = tarfile.TarInfo("./")
                kok.type, kok.mode, kok.uid, kok.gid, kok.uname, kok.gname, kok.mtime = (
                    tarfile.DIRTYPE, 0o755, 0, 0, "root", "root", zaman
                )
                tf.addfile(kok)
                for y, tur, iz, veri in liste:
                    ti = tarfile.TarInfo(f"./{y}")
                    ti.mode, ti.uid, ti.gid, ti.uname, ti.gname, ti.mtime = iz, 0, 0, "root", "root", zaman
                    if tur == "dizin":
                        ti.type = tarfile.DIRTYPE
                        tf.addfile(ti)
                    elif tur == "bag":
                        ti.type, ti.linkname = tarfile.SYMTYPE, str(veri)
                        tf.addfile(ti)
                    elif isinstance(veri, bytes):
                        ti.size = len(veri)
                        tf.addfile(ti, io.BytesIO(veri))
            return tampon.getvalue()

        control_tar = _tar_xz_uret(kontrol_girdileri)
        data_tar = _tar_xz_uret(tum_girdiler)

        hedef_deb.parent.mkdir(parents=True, exist_ok=True)
        gecici = hedef_deb.with_suffix(".deb.gecici")
        with open(gecici, "wb") as f:
            f.write(b"!<arch>\n")
            for ad, veri in [("debian-binary", b"2.0\n"), ("control.tar.xz", control_tar), ("data.tar.xz", data_tar)]:
                baslik = f"{ad:<16}{zaman:<12}{0:<6}{0:<6}{'100644':<8}{len(veri):<10}`\n"
                f.write(baslik.encode("ascii"))
                f.write(veri)
                if len(veri) % 2:
                    f.write(b"\n")
        gecici.replace(hedef_deb)
        return hedef_deb
    except Exception:
        return None


def deb_paketi_bul(uret: bool = False) -> Path | None:
    """Mevcut uygulama sürümüne ait .deb kurulum paketini bulur veya gerekirse üretir."""
    hedef_ad = f"pardus-sinif-yonetimi_{ayarlar.VERSIYON}_amd64.deb"
    adaylar = [
        _onbellek_dizini() / hedef_ad,
        KOK_DIZIN / "cikti" / hedef_ad,
        Path("/var/cache/pardus-sinif-yonetimi") / hedef_ad,
        Path("/var/cache/apt/archives") / hedef_ad,
    ]
    for aday in adaylar:
        if aday.is_file() and aday.stat().st_size > 1024 * 1024:
            return aday

    # cikti/ veya onbellek/ altındaki en güncel pardus-sinif-yonetimi_*.deb
    for klasor in (_onbellek_dizini(), KOK_DIZIN / "cikti"):
        if klasor.is_dir():
            debler = sorted(klasor.glob("pardus-sinif-yonetimi_*_amd64.deb"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
            if debler and debler[0].stat().st_size > 1024 * 1024:
                return debler[0]

    if not uret:
        return None

    hedef_onbellek = _onbellek_dizini() / hedef_ad
    # 1) Kurulu Linux sisteminden (/opt/pardus-sinif-yonetimi) yeniden paketle
    uretilen = _kurulu_sistemden_deb_uret(hedef_onbellek)
    if uretilen and uretilen.is_file():
        return uretilen

    # 2) Geliştirme ortamında paketleme/deb_yap.py mevcutsa çalıştır
    deb_yap_yolu = KOK_DIZIN / "paketleme" / "deb_yap.py"
    if deb_yap_yolu.is_file() and (KOK_DIZIN / "paketleme" / "onbellek").is_dir():
        try:
            from paketleme import deb_yap  # type: ignore
            yol = deb_yap.paket_yap()
            if yol and Path(yol).is_file():
                return Path(yol)
        except Exception:
            pass
    return None


def deb_onbellege_yukle(dosya_adi: str, icerik: bytes) -> dict:
    """Yöneticinin dışarıdan yüklediği uygulama .deb paketini yedekleme önbelleğine kaydeder."""
    temiz_ad = os.path.basename(dosya_adi or "")
    if not temiz_ad.endswith(".deb") or not temiz_ad.startswith("pardus-sinif-yonetimi"):
        raise SistemYedekHatasi("Yalnızca 'pardus-sinif-yonetimi_*.deb' kurulum paketi yüklenebilir")
    if len(icerik) < 1024 * 1024 or not icerik.startswith(b"!<arch>\n"):
        raise SistemYedekHatasi("Geçerli bir Debian (.deb) arşivi değil")
    hedef = _onbellek_dizini() / f"pardus-sinif-yonetimi_{ayarlar.VERSIYON}_amd64.deb"
    gecici = hedef.with_suffix(".deb.gecici")
    gecici.write_bytes(icerik)
    gecici.replace(hedef)
    ozet = _sha256_bytes(icerik)
    (hedef.parent / (hedef.name + ".sha256")).write_text(f"{ozet}  {hedef.name}\n", encoding="ascii")
    return {
        "dosya_adi": hedef.name,
        "boyut": len(icerik),
        "sha256": ozet,
    }


# ------------------------------------------------------------------ Kurulum Betiği ve Kılavuz Üretimi

def _yedekten_kur_betigi_uret(manifest: dict) -> str:
    """Sıfırdan Pardus bilgisayarda uygulamayı kuran ve yedeği geri yükleyen bash betiği."""
    ozet = manifest.get("ozet") or {}
    okul = ozet.get("okul_adi") or "Lab Kaptanı"
    surum = manifest.get("uygulama_surumu") or ayarlar.VERSIYON
    tarih = manifest.get("olusturma_zamani") or ""
    return f"""#!/usr/bin/env bash
# ==============================================================================
# Lab Kaptanı (Pardus Sınıf Yönetimi) — Yedekten Otomatik Kurulum ve Taşıma Betiği
# Yedek Sürümü : v{surum}
# Yedek Tarihi : {tarih}
# Okul / Birim : {okul}
# ==============================================================================
set -euo pipefail

BETIK_DIZINI="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$BETIK_DIZINI"

if [ "$(id -u)" -ne 0 ]; then
    echo "== Yönetici (root) yetkisi gerekiyor, sudo ile yeniden başlatılıyor..."
    exec sudo bash "$0" "$@"
fi

echo "================================================================"
echo " Lab Kaptanı (Pardus Sınıf Yönetimi) — Yedekten Taşıma ve Kurulum"
echo " Okul   : {okul}"
echo " Sürüm  : v{surum}"
echo "================================================================"
echo

# 1) Bütünlük doğrulaması (manifest.json)
if [ ! -f "$BETIK_DIZINI/manifest.json" ] || [ ! -f "$BETIK_DIZINI/veri/envanter.db" ]; then
    echo "HATA: Yedek klasörü eksik veya bozuk (manifest.json / veri/envanter.db bulunamadı)." >&2
    exit 1
fi

# 2) Uygulama .deb paketi kurulumu (paket/ altında varsa veya sistemde kurulu değilse)
DEB_DOSYA="$(find "$BETIK_DIZINI/paket" -maxdepth 1 -name 'pardus-sinif-yonetimi_*.deb' 2>/dev/null | head -n 1 || true)"
if [ -n "$DEB_DOSYA" ] && [ -f "$DEB_DOSYA" ]; then
    echo "== [1/5] Uygulama paketi kuruluyor: $(basename "$DEB_DOSYA")"
    DEBIAN_FRONTEND=noninteractive dpkg -i "$DEB_DOSYA" || DEBIAN_FRONTEND=noninteractive apt-get install -f -y
else
    if [ ! -d "/opt/pardus-sinif-yonetimi" ]; then
        echo "UYARI: Yedek içinde .deb paketi bulunamadı ve sistemde uygulama kurulu değil." >&2
        echo "Lütfen önce 'sudo dpkg -i pardus-sinif-yonetimi_{surum}_amd64.deb' komutunu çalıştırın," >&2
        echo "ardından bu betiği tekrar çalıştırın." >&2
        exit 1
    fi
    echo "== [1/5] Sistemde kurulu Pardus Sınıf Yönetimi bulundu."
fi

UYG="pardus-sinif-yonetimi"
KULLANICI="pardus-sinif"
ODEV_KULLANICI="pardus-odev"
VERI="/var/lib/$UYG"
ODEV_VERI="/var/lib/pardus-sinif-odev"
AYAR="/etc/$UYG"
PY="/opt/$UYG/python/bin/python3"

# 3) Servisleri güvenli şekilde durdur
echo "== [2/5] Servisler durduruluyor..."
if [ -d /run/systemd/system ]; then
    systemctl stop "$UYG.service" pardus-sinif-odev.service 2>/dev/null || true
fi

# 4) Hedef makinede mevcut veri varsa güvenlik yedeği al
ZAMAN_DAMGASI="$(date +%Y%m%d_%H%M%S)"
if [ -f "$VERI/envanter.db" ]; then
    ONCEKI_YEDEK="$VERI/sistem_yedekleri/tasima_oncesi_$ZAMAN_DAMGASI"
    mkdir -p "$ONCEKI_YEDEK"
    cp -a "$VERI/envanter.db" "$ONCEKI_YEDEK/" 2>/dev/null || true
    [ -d "$VERI/anahtar" ] && cp -a "$VERI/anahtar" "$ONCEKI_YEDEK/" 2>/dev/null || true
    echo "   Mevcut veritabanı koruma altına alındı: $ONCEKI_YEDEK"
fi

# 5) Yönetim verilerini, SSH anahtarlarını, Veyon ve Galeri dosyalarını geri yükle
echo "== [3/5] Envanter, SSH anahtarları, Veyon ve galeri ayarları geri yükleniyor..."
install -d -m 0700 -o "$KULLANICI" -g "$KULLANICI" "$VERI"
rm -f "$VERI/envanter.db-wal" "$VERI/envanter.db-shm"
cp -a "$BETIK_DIZINI/veri/." "$VERI/"

if [ -d "$VERI/anahtar" ]; then
    chmod 0700 "$VERI/anahtar"
    [ -f "$VERI/anahtar/uygulama_ed25519" ] && chmod 0600 "$VERI/anahtar/uygulama_ed25519"
    [ -f "$VERI/anahtar/uygulama_ed25519.pub" ] && chmod 0644 "$VERI/anahtar/uygulama_ed25519.pub"
fi
[ -f "$VERI/kurulum_kodu" ] && chmod 0600 "$VERI/kurulum_kodu"
chown -R "$KULLANICI:$KULLANICI" "$VERI"

# 6) Öğrenci sınıf listeleri ve ödev portalı verilerini geri yükle
echo "== [4/5] Öğrenci sınıfları ve ödev teslim veritabanı geri yükleniyor..."
if [ -d "$BETIK_DIZINI/odev" ]; then
    install -d -m 2770 -o "$ODEV_KULLANICI" -g "$ODEV_KULLANICI" "$ODEV_VERI"
    rm -f "$ODEV_VERI/odev.db-wal" "$ODEV_VERI/odev.db-shm"
    cp -a "$BETIK_DIZINI/odev/." "$ODEV_VERI/"
    chown -R "$ODEV_KULLANICI:$ODEV_KULLANICI" "$ODEV_VERI"
    chmod 2770 "$ODEV_VERI"
fi

if [ -f "$BETIK_DIZINI/sistem/ortam" ] && [ ! -f "$AYAR/ortam" ]; then
    install -d -m 0755 "$AYAR"
    cp -a "$BETIK_DIZINI/sistem/ortam" "$AYAR/ortam"
    chmod 0644 "$AYAR/ortam"
fi

# 7) Veritabanı şema doğrulaması ve servisleri yeniden başlatma
echo "== [5/5] Servisler başlatılıyor..."
if [ -x "$PY" ]; then
    runuser -u "$KULLANICI" -- env PSY_VERI_DIZINI="$VERI" PYTHONPATH="/opt/$UYG" \\
        "$PY" -c "from uygulama import veritabani; veritabani.ac()" >/dev/null 2>&1 || true
fi

if [ -d /run/systemd/system ]; then
    systemctl daemon-reload
    systemctl enable "$UYG.service" pardus-sinif-odev.service >/dev/null 2>&1 || true
    systemctl restart pardus-sinif-odev.service || true
    systemctl restart "$UYG.service"
fi

echo
echo "================================================================"
echo " TAMAMLANDI: Yönetim uygulaması ve tüm verileriniz geri yüklendi!"
echo " - Envanterdeki tüm öğrenci bilgisayarları ve SSH anahtarları hazır."
echo " - Öğrenci bilgisayarlarında yeniden kurulum/şifre girme GEREKMEZ."
echo " - Uygulamayı masaüstündeki 'Pardus Sınıf Yönetimi' simgesinden açabilirsiniz."
echo "================================================================"
""".replace("\r\n", "\n")


def _benioku_metni_uret(manifest: dict) -> str:
    ozet = manifest.get("ozet") or {}
    return f"""================================================================================
LAB KAPTANI (PARDUS SINIF YÖNETİMİ) — TAM SİSTEM YEDEĞİ VE TAŞIMA PAKETİ
================================================================================

Yedek Tarihi     : {manifest.get("olusturma_zamani", "")}
Uygulama Sürümü  : v{manifest.get("uygulama_surumu", ayarlar.VERSIYON)}
Okul / Birim     : {ozet.get("okul_adi", "")}
Kayıtlı Cihazlar : {ozet.get("cihaz_sayisi", 0)} bilgisayar
Öğretmen Hesabı  : {ozet.get("ogretmen_sayisi", 0)} öğretmen
Sınıf / Öğrenci  : {ozet.get("sinif_sayisi", 0)} sınıf, {ozet.get("ogrenci_sayisi", 0)} öğrenci
SSH Anahtar Çifti: {"Mevcut (Öğrenci PC'lere yeniden şifre girmeden bağlanır)" if ozet.get("ssh_anahtari_var") else "Yok"}

--------------------------------------------------------------------------------
YÖNTEM 1: SIFIRDAN PARDUS KURULU YENİ BİLGİSAYARA TEK KOMUTLA KURULUM (ÖNERİLEN)
--------------------------------------------------------------------------------
Yeni öğretmen bilgisayarında bu arşivi klasöre çıkarın ve terminalde şu komutu
çalıştırın:

    tar -xzf pardus-sinif-yonetimi-yedek_*.tar.gz
    cd pardus-sinif-yonetimi-yedek
    sudo bash yedekten-kur.sh

Bu betik;
1. Paket klasöründeki .deb kurulum paketini otomatik kurar (internet gerekmez),
2. Envanteri, öğretmen hesaplarını, SSH özel/açık anahtarlarını, Veyon paket/anahtarını,
   duvar kâğıdı galerisini ve öğrenci ödev veritabanını geri yükler,
3. Servisleri başlatır. Öğrenci bilgisayarlarında hiçbir işlem yapmanıza gerek kalmaz!

--------------------------------------------------------------------------------
YÖNTEM 2: YÖNETİM PANELİ (WEB ARAYÜZÜ) ÜZERİNDEN GERİ YÜKLEME
--------------------------------------------------------------------------------
Uygulama bilgisayarda zaten kuruluysa:
1. Lab Kaptanı yönetim panelini açın.
2. Sol menüden "Okul ve Sistem Ayarları -> Sistem ve Saklama Ayarları (M5-S1)"
   sayfasına gidin.
3. "Yedekten Geri Yükle" bölümünden `.tar.gz` yedek dosyasını seçip
   "Yedeği Doğrula ve Geri Yükle" düğmesine tıklayın.
================================================================================
""".replace("\r\n", "\n")


# ------------------------------------------------------------------ Mevcut Sistem Özeti

def sistem_ozeti() -> dict:
    """Mevcut yönetim uygulamasının yedeklenecek bileşenlerinin canlı özetini döndürür."""
    y = ayarlar.veri_yollari()
    okul = veritabani.okul_bilgisi()
    cihazlar = veritabani.cihazlar()
    ogretmenler = veritabani.ogretmenler()

    sinif_sayisi = ogrenci_sayisi = teslim_sayisi = 0
    try:
        sinif_sayisi = int(odev_vt.tek("SELECT COUNT(*) AS n FROM sinif")["n"])
        ogrenci_sayisi = int(odev_vt.tek("SELECT COUNT(*) AS n FROM ogrenci")["n"])
        teslim_sayisi = int(odev_vt.tek("SELECT COUNT(*) AS n FROM teslim WHERE durum='tamamlandi'")["n"])
    except Exception:
        pass

    veyon_dizin = y["veyon_dizini"]
    veyon_anahtari_var = (veyon_dizin / "public_key.pem").is_file()
    veyon_paketi_var = any(veyon_dizin.glob("*.deb")) if veyon_dizin.is_dir() else False

    galeri_dizin = ayarlar.VERI_DIZINI / "duvar_kagidi" / "galeri"
    galeri_sayisi = len([p for p in galeri_dizin.iterdir() if p.is_file()]) if galeri_dizin.is_dir() else 0

    paket_dizin = y["paket_dizini"]
    yerel_paket_sayisi = len(list(paket_dizin.glob("*.deb"))) if paket_dizin.is_dir() else 0
    yerel_paket_boyut = sum(p.stat().st_size for p in paket_dizin.glob("*.deb")) if paket_dizin.is_dir() else 0

    teslim_dizin = odev_ortak.yollar()["teslimler"]
    teslim_boyut = 0
    if teslim_dizin.is_dir():
        for p in teslim_dizin.rglob("*"):
            if p.is_file():
                teslim_boyut += p.stat().st_size

    deb_yol = deb_paketi_bul(uret=False)
    deb_boyut = deb_yol.stat().st_size if deb_yol else 0
    deb_uretilebilir = deb_yol is not None or Path("/opt/pardus-sinif-yonetimi/uygulama/ana.py").is_file() or (
        (KOK_DIZIN / "paketleme" / "deb_yap.py").is_file()
    )

    return {
        "uygulama_surumu": ayarlar.VERSIYON,
        "okul_adi": okul.get("ad", ""),
        "cihaz_sayisi": len(cihazlar),
        "ogretmen_sayisi": len(ogretmenler),
        "sinif_sayisi": sinif_sayisi,
        "ogrenci_sayisi": ogrenci_sayisi,
        "teslim_sayisi": teslim_sayisi,
        "teslim_boyut": teslim_boyut,
        "ssh_anahtari_var": y["ozel_anahtar"].is_file() and y["acik_anahtar"].is_file(),
        "veyon_anahtari_var": veyon_anahtari_var,
        "veyon_paketi_var": veyon_paketi_var,
        "galeri_gorsel_sayisi": galeri_sayisi,
        "yerel_paket_sayisi": yerel_paket_sayisi,
        "yerel_paket_boyut": yerel_paket_boyut,
        "deb_hazir": deb_yol is not None,
        "deb_uretilebilir": deb_uretilebilir,
        "deb_paketi": deb_yol.name if deb_yol else f"pardus-sinif-yonetimi_{ayarlar.VERSIYON}_amd64.deb",
        "deb_boyut": deb_boyut,
    }


# ------------------------------------------------------------------ Yedek Oluşturma

def _sqlite_yedek_al(kaynak_baglanti: sqlite3.Connection, hedef_yol: Path) -> None:
    """Çalışan SQLite veritabanının Online Backup API ile tutarlı tek dosya kopyasını alır."""
    hedef_yol.parent.mkdir(parents=True, exist_ok=True)
    if hedef_yol.exists():
        hedef_yol.unlink()
    hedef_vt = sqlite3.connect(hedef_yol)
    try:
        kaynak_baglanti.backup(hedef_vt)
        hedef_vt.execute("PRAGMA journal_mode=DELETE;")
        hedef_vt.commit()
    finally:
        hedef_vt.close()


def yedek_olustur(
    aciklama: str = "",
    deb_dahil: bool = True,
    odev_teslimleri_dahil: bool = True,
    yerel_paketler_dahil: bool = False,
    on_ek: str = "",
) -> dict:
    """Tüm yönetim yapılandırmasını, veritabanlarını, anahtarları ve .deb paketini .tar.gz olarak yedekler."""
    y = ayarlar.veri_yollari()
    if not (y["ozel_anahtar"].is_file() and y["acik_anahtar"].is_file()):
        try:
            from . import anahtar
            anahtar.anahtar_uret_veya_yukle()
        except Exception:
            pass
    ozet_bilgi = sistem_ozeti()
    simdi_dt = datetime.now(timezone.utc).astimezone()
    zaman_metin = simdi_dt.strftime("%Y-%m-%d_%H-%M-%S")
    zaman_iso = simdi_dt.isoformat(timespec="seconds")
    unix_zaman = int(simdi_dt.timestamp())

    onek_str = f"{on_ek}_" if on_ek else ""
    arsiv_adi = f"pardus-sinif-yonetimi-yedek_{onek_str}{zaman_metin}_v{ayarlar.VERSIYON}.tar.gz"
    hedef_arsiv = yedek_dizini() / arsiv_adi
    if hedef_arsiv.exists():
        arsiv_adi = f"pardus-sinif-yonetimi-yedek_{onek_str}{zaman_metin}_{int(time.time() * 1000) % 1000}_v{ayarlar.VERSIYON}.tar.gz"
        hedef_arsiv = yedek_dizini() / arsiv_adi

    y = ayarlar.veri_yollari()
    dosya_kayitlari: dict[str, dict] = {}

    with tempfile.TemporaryDirectory(prefix="psy_yedek_") as gecici_str:
        gecici_kok = Path(gecici_str)
        envanter_kopya = gecici_kok / "envanter.db"
        _sqlite_yedek_al(veritabani.ac(), envanter_kopya)

        odev_kopya = gecici_kok / "odev.db"
        _sqlite_yedek_al(odev_vt.ac(), odev_kopya)

        deb_yol: Path | None = None
        if deb_dahil:
            deb_yol = deb_paketi_bul(uret=True)

        ozet_bilgi["deb_paketi"] = deb_yol.name if deb_yol else None
        ozet_bilgi["deb_dahil_edildi"] = deb_yol is not None

        gecici_tar = hedef_arsiv.with_suffix(".tar.gz.gecici")
        with gzip.open(gecici_tar, mode="wb", compresslevel=1) as gz_akis:
            with tarfile.open(fileobj=gz_akis, mode="w", format=tarfile.PAX_FORMAT) as tf:

                def _tar_dosya_ekle(kaynak_yol: Path, arsiv_ici_goreli: str, izin: int = 0o644) -> None:
                    if not kaynak_yol.is_file():
                        return
                    veri = kaynak_yol.read_bytes()
                    _tar_bellek_ekle(veri, arsiv_ici_goreli, izin)

                def _tar_bellek_ekle(veri: bytes, arsiv_ici_goreli: str, izin: int = 0o644,
                                     manifeste_ekle: bool = True) -> None:
                    tam_ad = f"{ARSIV_KOK}/{arsiv_ici_goreli.lstrip('/')}"
                    ti = tarfile.TarInfo(tam_ad)
                    ti.size = len(veri)
                    ti.mode = izin
                    ti.mtime = unix_zaman
                    ti.uid = ti.gid = 0
                    ti.uname = ti.gname = "root"
                    tf.addfile(ti, io.BytesIO(veri))
                    if manifeste_ekle:
                        dosya_kayitlari[arsiv_ici_goreli.lstrip("/")] = {
                            "sha256": _sha256_bytes(veri),
                            "boyut": len(veri),
                            "izin": izin,
                        }

                # 1) Veritabanları
                _tar_dosya_ekle(envanter_kopya, "veri/envanter.db", 0o600)
                _tar_dosya_ekle(odev_kopya, "odev/odev.db", 0o660)

                # 2) SSH Anahtarları ve Kurulum Kodu
                if y["ozel_anahtar"].is_file():
                    _tar_dosya_ekle(y["ozel_anahtar"], "veri/anahtar/uygulama_ed25519", 0o600)
                if y["acik_anahtar"].is_file():
                    _tar_dosya_ekle(y["acik_anahtar"], "veri/anahtar/uygulama_ed25519.pub", 0o644)
                if y["kurulum_kodu"].is_file():
                    _tar_dosya_ekle(y["kurulum_kodu"], "veri/kurulum_kodu", 0o600)

                # 3) Veyon (.deb, public_key.pem, veyon.json)
                if y["veyon_dizini"].is_dir():
                    for p in sorted(y["veyon_dizini"].rglob("*")):
                        if p.is_file():
                            goreli = "veri/veyon/" + p.relative_to(y["veyon_dizini"]).as_posix()
                            _tar_dosya_ekle(p, goreli, 0o644)

                # 4) Duvar Kâğıdı Galerisi ve Görseller
                duvar_dizin = ayarlar.VERI_DIZINI / "duvar_kagidi"
                if duvar_dizin.is_dir():
                    for p in sorted(duvar_dizin.rglob("*")):
                        if p.is_file():
                            goreli = "veri/duvar_kagidi/" + p.relative_to(duvar_dizin).as_posix()
                            _tar_dosya_ekle(p, goreli, 0o644)

                # 5) Yerel .deb paketleri (isteğe bağlı)
                if yerel_paketler_dahil and y["paket_dizini"].is_dir():
                    for p in sorted(y["paket_dizini"].glob("*.deb")):
                        if p.is_file():
                            _tar_dosya_ekle(p, f"veri/paketler/{p.name}", 0o644)

                # 6) Öğrenci ödev teslim dosyaları (isteğe bağlı)
                teslimler_dizin = odev_ortak.yollar()["teslimler"]
                if odev_teslimleri_dahil and teslimler_dizin.is_dir():
                    for p in sorted(teslimler_dizin.rglob("*")):
                        if p.is_file():
                            goreli = "odev/teslimler/" + p.relative_to(teslimler_dizin).as_posix()
                            _tar_dosya_ekle(p, goreli, 0o640)

                # 7) Sistem ortam yapılandırması (/etc/pardus-sinif-yonetimi/ortam)
                ortam_dosyasi = Path("/etc/pardus-sinif-yonetimi/ortam")
                if ortam_dosyasi.is_file():
                    _tar_dosya_ekle(ortam_dosyasi, "sistem/ortam", 0o644)

                # 8) Uygulamanın kendi .deb kurulum paketi
                if deb_yol and deb_yol.is_file():
                    _tar_dosya_ekle(deb_yol, f"paket/{deb_yol.name}", 0o644)
                    deb_sha = dosya_kayitlari[f"paket/{deb_yol.name}"]["sha256"]
                    _tar_bellek_ekle(
                        f"{deb_sha}  {deb_yol.name}\n".encode("ascii"),
                        f"paket/{deb_yol.name}.sha256",
                        0o644,
                    )

                # 9) Manifest, Otomatik Kurulum Betiği (yedekten-kur.sh) ve BENIOKU.txt
                manifest = {
                    "format": FORMAT_ADI,
                    "format_surumu": FORMAT_SURUMU,
                    "uygulama_surumu": ayarlar.VERSIYON,
                    "olusturma_zamani": zaman_iso,
                    "kaynak_makine": socket.gethostname(),
                    "aciklama": (aciklama or "").strip()[:200],
                    "secenekler": {
                        "deb_dahil": bool(deb_yol and deb_yol.is_file()),
                        "odev_teslimleri_dahil": bool(odev_teslimleri_dahil),
                        "yerel_paketler_dahil": bool(yerel_paketler_dahil),
                    },
                    "ozet": ozet_bilgi,
                    "dosyalar": dosya_kayitlari,
                }
                kur_betigi = _yedekten_kur_betigi_uret(manifest).encode("utf-8")
                _tar_bellek_ekle(kur_betigi, "yedekten-kur.sh", 0o755)

                benioku = _benioku_metni_uret(manifest).encode("utf-8")
                _tar_bellek_ekle(benioku, "BENIOKU.txt", 0o644)

                manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
                _tar_bellek_ekle(manifest_bytes, "manifest.json", 0o644, manifeste_ekle=False)

        gecici_tar.replace(hedef_arsiv)

    arsiv_boyut = hedef_arsiv.stat().st_size
    arsiv_sha256 = _sha256_dosya(hedef_arsiv)
    ust_veri = {
        "dosya_adi": arsiv_adi,
        "boyut": arsiv_boyut,
        "sha256": arsiv_sha256,
        "olusturma_zamani": zaman_iso,
        "uygulama_surumu": ayarlar.VERSIYON,
        "kaynak_makine": socket.gethostname(),
        "aciklama": (aciklama or "").strip()[:200],
        "secenekler": manifest["secenekler"],
        "ozet": ozet_bilgi,
    }
    meta_yol = hedef_arsiv.with_suffix(".meta.json")
    meta_yol.write_text(json.dumps(ust_veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return ust_veri


# ------------------------------------------------------------------ Listeleme, Silme ve İndirme

def _arsiv_ad_dogrula(dosya_adi: str) -> Path:
    temiz = os.path.basename(dosya_adi or "")
    if not DOSYA_DESENI.match(temiz):
        raise SistemYedekHatasi("Geçersiz yedek dosya adı")
    yol = (yedek_dizini() / temiz).resolve()
    if yol.parent != yedek_dizini().resolve() or not yol.is_file():
        raise SistemYedekHatasi("Yedek dosyası bulunamadı")
    return yol


def yedek_yolu(dosya_adi: str) -> Path:
    return _arsiv_ad_dogrula(dosya_adi)


def yedek_listele() -> list[dict]:
    """Sunucuda saklanan sistem yedeklerini en yeniden eskiye doğru listeler."""
    dizin = yedek_dizini()
    sonuc = []
    for yol in sorted(dizin.glob("pardus-sinif-yonetimi-yedek_*.tar.gz"),
                      key=lambda p: p.stat().st_mtime, reverse=True):
        meta_yol = yol.with_suffix(".meta.json")
        if meta_yol.is_file():
            try:
                meta = json.loads(meta_yol.read_text(encoding="utf-8"))
                meta["dosya_adi"] = yol.name
                meta["boyut"] = yol.stat().st_size
                sonuc.append(meta)
                continue
            except Exception:
                pass
        # Meta dosyası yoksa arşiv içindeki manifest.json'u oku
        try:
            inceleme = yedek_incele(yol, tam_sha_dogrula=False)
            sonuc.append({
                "dosya_adi": yol.name,
                "boyut": yol.stat().st_size,
                "sha256": "",
                "olusturma_zamani": inceleme.get("olusturma_zamani", ""),
                "uygulama_surumu": inceleme.get("uygulama_surumu", ""),
                "kaynak_makine": inceleme.get("kaynak_makine", ""),
                "aciklama": inceleme.get("aciklama", ""),
                "secenekler": inceleme.get("secenekler", {}),
                "ozet": inceleme.get("ozet", {}),
            })
        except Exception:
            continue
    return sonuc


def yedek_sil(dosya_adi: str) -> dict:
    yol = _arsiv_ad_dogrula(dosya_adi)
    meta_yol = yol.with_suffix(".meta.json")
    yol.unlink(missing_ok=True)
    meta_yol.unlink(missing_ok=True)
    return {"silindi": dosya_adi}


# ------------------------------------------------------------------ Yedek Doğrulama ve İnceleme

def _guvenli_goreli_yol(uye_adi: str) -> str:
    """Tar üye yolunu doğrular (TarSlip koruması) ve kök klasör önekini soyar."""
    norm = uye_adi.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    parcalar = [p for p in norm.split("/") if p]
    if not parcalar or ".." in parcalar or norm.startswith("/"):
        raise SistemYedekHatasi(f"Arşivde güvensiz dosya yolu: {uye_adi}")
    if parcalar[0] == ARSIV_KOK:
        parcalar = parcalar[1:]
    if not parcalar:
        return ""
    return "/".join(parcalar)


def yedek_incele(kaynak: Path | bytes, tam_sha_dogrula: bool = True) -> dict:
    """Yedek arşivinin yapısını, manifest.json'unu ve SHA-256 dosya bütünlüğünü doğrular."""
    if isinstance(kaynak, bytes):
        if len(kaynak) > EN_BUYUK_ARSIV:
            raise SistemYedekHatasi("Yedek arşivi izin verilen boyutu aşıyor")
        akis: io.BufferedReader | io.BytesIO = io.BytesIO(kaynak)
    else:
        if not kaynak.is_file():
            raise SistemYedekHatasi("Yedek dosyası bulunamadı")
        if kaynak.stat().st_size > EN_BUYUK_ARSIV:
            raise SistemYedekHatasi("Yedek arşivi izin verilen boyutu aşıyor")
        akis = open(kaynak, "rb")

    try:
        with tarfile.open(fileobj=akis, mode="r:gz") as tf:
            uyeler: dict[str, tarfile.TarInfo] = {}
            for uye in tf.getmembers():
                if uye.isdir():
                    continue
                if not uye.isfile():
                    raise SistemYedekHatasi(f"Arşivde desteklenmeyen girdi türü (sembolik bağ/aygıt): {uye.name}")
                goreli = _guvenli_goreli_yol(uye.name)
                if goreli:
                    uyeler[goreli] = uye

            if "manifest.json" not in uyeler:
                raise SistemYedekHatasi("Geçerli bir Lab Kaptanı yedeği değil (manifest.json bulunamadı)")
            if "veri/envanter.db" not in uyeler:
                raise SistemYedekHatasi("Yedek arşivinde 'veri/envanter.db' veritabanı bulunamadı")

            manifest_f = tf.extractfile(uyeler["manifest.json"])
            if manifest_f is None:
                raise SistemYedekHatasi("manifest.json okunamadı")
            manifest = json.loads(manifest_f.read().decode("utf-8"))

            if manifest.get("format") != FORMAT_ADI:
                raise SistemYedekHatasi("Bilinmeyen yedek formatı")

            beklenen_dosyalar = manifest.get("dosyalar") or {}
            if tam_sha_dogrula:
                for goreli_ad, bilgi in beklenen_dosyalar.items():
                    if goreli_ad not in uyeler:
                        raise SistemYedekHatasi(f"Yedek arşivinde eksik dosya: {goreli_ad}")
                    cikti_f = tf.extractfile(uyeler[goreli_ad])
                    if cikti_f is None:
                        raise SistemYedekHatasi(f"Arşivden dosya okunamadı: {goreli_ad}")
                    veri = cikti_f.read()
                    if _sha256_bytes(veri) != bilgi.get("sha256"):
                        raise SistemYedekHatasi(f"Dosya bütünlüğü bozuk (SHA-256 uyuşmuyor): {goreli_ad}")

            return {
                "gecerli": True,
                "format": manifest.get("format"),
                "format_surumu": manifest.get("format_surumu"),
                "uygulama_surumu": manifest.get("uygulama_surumu"),
                "olusturma_zamani": manifest.get("olusturma_zamani"),
                "kaynak_makine": manifest.get("kaynak_makine"),
                "aciklama": manifest.get("aciklama", ""),
                "secenekler": manifest.get("secenekler", {}),
                "ozet": manifest.get("ozet", {}),
                "dosya_sayisi": len(uyeler),
            }
    except SistemYedekHatasi:
        raise
    except (tarfile.TarError, EOFError, json.JSONDecodeError, OSError) as hata:
        raise SistemYedekHatasi(f"Yedek arşivi okunamadı veya bozuk: {hata}") from hata
    finally:
        if not isinstance(kaynak, bytes):
            akis.close()


# ------------------------------------------------------------------ Yedekten Geri Yükleme

def _sqlite_dogrula_ve_geri_yukle(yedek_db_yolu: Path, hedef_baglanti: sqlite3.Connection,
                                  beklenen_tablo: str) -> None:
    """Yedek SQLite veritabanının bütünlüğünü denetler ve canlı veritabanına atomik olarak yazar."""
    kaynak = sqlite3.connect(yedek_db_yolu)
    try:
        kontrol = kaynak.execute("PRAGMA integrity_check;").fetchone()
        if not kontrol or kontrol[0] != "ok":
            raise SistemYedekHatasi(f"Yedek veritabanı bütünlük denetiminden geçemedi ({yedek_db_yolu.name})")
        tablolar = {r[0] for r in kaynak.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if beklenen_tablo not in tablolar:
            raise SistemYedekHatasi(f"Yedek veritabanında '{beklenen_tablo}' tablosu bulunamadı")
        kaynak.backup(hedef_baglanti)
        hedef_baglanti.commit()
    finally:
        kaynak.close()


def yedek_geri_yukle(kaynak: Path | bytes, otomatik_yedek: bool = True) -> dict:
    """Doğrulanmış yedek arşivini canlı sisteme geri yükler."""
    inceleme = yedek_incele(kaynak, tam_sha_dogrula=True)

    onceki_yedek = None
    if otomatik_yedek:
        try:
            onceki_yedek = yedek_olustur(
                aciklama="Geri yükleme öncesi otomatik güvenlik yedeği",
                deb_dahil=False,
                odev_teslimleri_dahil=False,
                yerel_paketler_dahil=False,
                on_ek="geri-yukleme-oncesi",
            )["dosya_adi"]
        except Exception:
            onceki_yedek = None

    if isinstance(kaynak, bytes):
        akis: io.BufferedReader | io.BytesIO = io.BytesIO(kaynak)
    else:
        akis = open(kaynak, "rb")

    geri_yuklenen: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="psy_geri_yukle_") as gecici_str:
            gecici_kok = Path(gecici_str)
            with tarfile.open(fileobj=akis, mode="r:gz") as tf:
                for uye in tf.getmembers():
                    if not uye.isfile():
                        continue
                    goreli = _guvenli_goreli_yol(uye.name)
                    if not goreli:
                        continue
                    hedef_dosya = (gecici_kok / goreli).resolve()
                    if not str(hedef_dosya).startswith(str(gecici_kok.resolve())):
                        raise SistemYedekHatasi("Güvensiz arşiv yolu engellendi")
                    hedef_dosya.parent.mkdir(parents=True, exist_ok=True)
                    cikti_f = tf.extractfile(uye)
                    if cikti_f is not None:
                        hedef_dosya.write_bytes(cikti_f.read())

            y = ayarlar.veri_yollari()

            # 1) Envanter veritabanı (Online Backup API + Şema Göçü)
            yedek_envanter = gecici_kok / "veri" / "envanter.db"
            if not yedek_envanter.is_file():
                raise SistemYedekHatasi("Yedekte envanter.db bulunamadı")
            vt = veritabani.ac()
            with veritabani._kilit:
                _sqlite_dogrula_ve_geri_yukle(yedek_envanter, vt, "cihaz")
                veritabani._goc(vt)
                veritabani._yerlesik_komutlari_yukle(vt)
                vt.commit()
            geri_yuklenen.append("Envanter, öğretmen hesapları ve okul ayarları (envanter.db)")

            # 2) SSH Anahtar Çifti
            yedek_ozel = gecici_kok / "veri" / "anahtar" / "uygulama_ed25519"
            yedek_acik = gecici_kok / "veri" / "anahtar" / "uygulama_ed25519.pub"
            if yedek_ozel.is_file() and yedek_acik.is_file():
                y["anahtar_dizini"].mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(y["anahtar_dizini"], 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
                except OSError:
                    pass
                fd = os.open(y["ozel_anahtar"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(yedek_ozel.read_bytes())
                y["acik_anahtar"].write_bytes(yedek_acik.read_bytes())
                try:
                    os.chmod(y["acik_anahtar"], 0o644)
                except OSError:
                    pass
                geri_yuklenen.append("SSH özel ve açık anahtar çifti (uygulama_ed25519)")

            # 3) Veyon dosyaları
            yedek_veyon = gecici_kok / "veri" / "veyon"
            if yedek_veyon.is_dir():
                y["veyon_dizini"].mkdir(parents=True, exist_ok=True)
                for p in yedek_veyon.rglob("*"):
                    if p.is_file():
                        h = y["veyon_dizini"] / p.relative_to(yedek_veyon)
                        h.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, h)
                geri_yuklenen.append("Veyon paket ve açık anahtar dosyaları")

            # 4) Duvar Kâğıdı Galerisi
            yedek_duvar = gecici_kok / "veri" / "duvar_kagidi"
            if yedek_duvar.is_dir():
                hedef_duvar = ayarlar.VERI_DIZINI / "duvar_kagidi"
                hedef_duvar.mkdir(parents=True, exist_ok=True)
                for p in yedek_duvar.rglob("*"):
                    if p.is_file():
                        h = hedef_duvar / p.relative_to(yedek_duvar)
                        h.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, h)
                geri_yuklenen.append("Duvar kâğıdı galerisi ve görselleri")

            # 5) Yerel .deb paketleri
            yedek_paketler = gecici_kok / "veri" / "paketler"
            if yedek_paketler.is_dir():
                y["paket_dizini"].mkdir(parents=True, exist_ok=True)
                for p in yedek_paketler.glob("*.deb"):
                    if p.is_file():
                        shutil.copy2(p, y["paket_dizini"] / p.name)
                geri_yuklenen.append("Yüklenmiş yerel .deb paketleri")

            # 6) Ödev veritabanı ve teslim dosyaları
            yedek_odev_db = gecici_kok / "odev" / "odev.db"
            if yedek_odev_db.is_file():
                ovt = odev_vt.ac()
                with odev_vt._kilit:
                    _sqlite_dogrula_ve_geri_yukle(yedek_odev_db, ovt, "sinif")
                geri_yuklenen.append("Öğrenci sınıfları, kodları ve ödev veritabanı (odev.db)")

            yedek_teslimler = gecici_kok / "odev" / "teslimler"
            if yedek_teslimler.is_dir():
                hedef_teslimler = odev_ortak.yollar()["teslimler"]
                hedef_teslimler.mkdir(parents=True, exist_ok=True)
                for p in yedek_teslimler.rglob("*"):
                    if p.is_file():
                        h = hedef_teslimler / p.relative_to(yedek_teslimler)
                        h.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, h)
                geri_yuklenen.append("Öğrenci ödev teslim dosyaları")

            # 7) Yedek içinde uygulama .deb paketi varsa önbelleğe de kopyala
            yedek_deb_klasor = gecici_kok / "paket"
            if yedek_deb_klasor.is_dir():
                for deb_p in yedek_deb_klasor.glob("pardus-sinif-yonetimi_*.deb"):
                    if deb_p.is_file():
                        shutil.copy2(deb_p, _onbellek_dizini() / deb_p.name)

        return {
            "durum": "tamamlandi",
            "geri_yuklenen": geri_yuklenen,
            "onceki_yedek": onceki_yedek,
            "inceleme": inceleme,
            "guncel_ozet": sistem_ozeti(),
        }
    finally:
        if not isinstance(kaynak, bytes):
            akis.close()


# ------------------------------------------------------------------ Komut Satırı (CLI) Desteği

def _cli() -> None:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(
        prog="pardus-sinif-yonetimi-yedek",
        description="Lab Kaptanı (Pardus Sınıf Yönetimi) tam sistem yedekleme ve geri yükleme aracı",
    )
    alt = p.add_subparsers(dest="komut", required=True)

    p_yedek = alt.add_parser("yedekle", help="Tam sistem yedeği (.tar.gz) oluşturur")
    p_yedek.add_argument("-c", "--cikti", help="Yedeğin kopyalanacağı hedef dosya veya klasör yolu")
    p_yedek.add_argument("-a", "--aciklama", default="", help="Yedek açıklaması")
    p_yedek.add_argument("--deb-haric", action="store_true", help="Uygulama .deb paketini dahil etme")

    p_yukle = alt.add_parser("geri-yukle", help="Yedek arşivini (.tar.gz) doğrular ve sisteme geri yükler")
    p_yukle.add_argument("arsiv", help="Geri yüklenecek .tar.gz yedek dosyası")

    p_liste = alt.add_parser("listele", help="Kayıtlı yedekleri listeler")

    args = p.parse_args()
    if args.komut == "yedekle":
        sonuc = yedek_olustur(aciklama=args.aciklama, deb_dahil=not args.deb_haric)
        kaynak_yol = yedek_yolu(sonuc["dosya_adi"])
        if args.cikti:
            hedef = Path(args.cikti)
            if hedef.is_dir():
                hedef = hedef / kaynak_yol.name
            shutil.copy2(kaynak_yol, hedef)
            print(f"Yedek oluşturuldu: {hedef} ({sonuc['boyut'] / 1048576:.1f} MB)")
        else:
            print(f"Yedek oluşturuldu: {kaynak_yol} ({sonuc['boyut'] / 1048576:.1f} MB)")
    elif args.komut == "geri-yukle":
        sonuc = yedek_geri_yukle(Path(args.arsiv))
        print("Geri yükleme tamamlandı:")
        for kalem in sonuc["geri_yuklenen"]:
            print(f"  + {kalem}")
    elif args.komut == "listele":
        for y in yedek_listele():
            print(f"{y['dosya_adi']}  ({y['boyut'] / 1048576:.1f} MB)  {y.get('olusturma_zamani', '')}")


if __name__ == "__main__":
    _cli()
