#!/usr/bin/env python3
"""Pardus Sınıf Yönetimi — .deb paketi üretir.

Saf Python ile çalışır (Windows, Linux veya macOS); dpkg-deb gerekmez.

    python paketleme/deb_yap.py                   # cikti/pardus-sinif-yonetimi_<sürüm>_amd64.deb
    python paketleme/deb_yap.py --kilit-guncelle  # requirements.txt değişince tekerlek kilidini yeniler

Paket; gömülü Python'u (python-build-standalone), sabitlenmiş kütüphaneleri ve
uygulamayı içerir. Hedef bilgisayarda yalnızca `sudo dpkg -i <paket>.deb` gerekir;
kurulum sırasında internetten hiçbir şey indirilmez.

İnternet yalnızca derleme makinesinde, ilk derlemede gerekir. İndirilenler
paketleme/onbellek/ altında tutulur ve her dosya sabit sha256 ile doğrulanır:
gömülü Python bu dosyadaki PYTHON sözlüğüyle, tekerlekler tekerlek_kilidi.txt ile.
"""

import argparse
import hashlib
import io
import math
import re
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
PAKETLEME = KOK / "paketleme"
ONBELLEK = PAKETLEME / "onbellek"
TEKERLEKLER = ONBELLEK / "tekerlekler"
KILIT = PAKETLEME / "tekerlek_kilidi.txt"
CIKTI = KOK / "cikti"

PAKET = "pardus-sinif-yonetimi"
OPT = f"opt/{PAKET}"
PY_SURUM = "3.12"
PYTHON = {
    "ad": "cpython-3.12.14+20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
    "url": ("https://github.com/astral-sh/python-build-standalone/releases/download/20260901/"
            "cpython-3.12.14%2B20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"),
    "sha256": "72748da13197c1fb161e3afeef20a6a385ff24f2165e6e2758e47008e7faba4c",
}
# Tekerlek seçimi: Linux x86_64, glibc >= 2.28 (Pardus 21+), CPython 3.12
PIP_PLATFORM = ["--only-binary=:all:", "--python-version", PY_SURUM, "--implementation", "cp",
                "--abi", "cp312", "--abi", "abi3",
                "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux_2_17_x86_64",
                "--platform", "manylinux2014_x86_64"]

# Gömülü Python'dan yalnızca yorumlayıcı ve standart kütüphane alınır; libpython,
# tcl/tk, pip ve derleme başlıkları çalışma için gerekmez (yorumlayıcı statik bağlı).
PY_BIN = {"python/bin/python", "python/bin/python3", "python/bin/python3.12"}
PY_LIB = f"python/lib/python{PY_SURUM}/"
PY_HARIC = tuple(PY_LIB + d for d in (
    "idlelib/", "tkinter/", "turtledemo/", "ensurepip/", "lib2to3/", "test/",
    f"config-{PY_SURUM}-x86_64-linux-gnu/", "site-packages/", "lib-dynload/_tkinter"))
SITE = f"{OPT}/python/lib/python{PY_SURUM}/site-packages"

# Depodan pakete: kaynak -> (hedef, izin)
SISTEM_DOSYALARI = {
    "paketleme/dosyalar/pardus-sinif-yonetimi.service":
        (f"lib/systemd/system/{PAKET}.service", 0o644),
    "paketleme/dosyalar/pardus-sinif-odev.service":
        ("lib/systemd/system/pardus-sinif-odev.service", 0o644),
    "paketleme/dosyalar/pardus-sinif-yonetimi": (f"usr/bin/{PAKET}", 0o755),
    "paketleme/dosyalar/kurulum-kodu": (f"usr/lib/{PAKET}/kurulum-kodu", 0o755),
    "paketleme/dosyalar/tr.org.pardus.sinif-yonetimi.policy":
        ("usr/share/polkit-1/actions/tr.org.pardus.sinif-yonetimi.policy", 0o644),
    "paketleme/dosyalar/pardus-sinif-yonetimi.desktop":
        (f"usr/share/applications/{PAKET}.desktop", 0o644),
    "paketleme/dosyalar/pardus-sinif-yonetimi.svg":
        (f"usr/share/icons/hicolor/scalable/apps/{PAKET}.svg", 0o644),
    "README.md": (f"usr/share/doc/{PAKET}/README.md", 0o644),
    "belgeler/kullanim_kilavuzu.md": (f"usr/share/doc/{PAKET}/kullanim_kilavuzu.md", 0o644),
    "belgeler/yonetici_kilavuzu.md": (f"usr/share/doc/{PAKET}/yonetici_kilavuzu.md", 0o644),
    "belgeler/odev_kilavuzu.md": (f"usr/share/doc/{PAKET}/odev_kilavuzu.md", 0o644),
    "belgeler/ornek_sinif_listesi.csv": (f"usr/share/doc/{PAKET}/ornek_sinif_listesi.csv", 0o644),
    "DESIGN.md": (f"usr/share/doc/{PAKET}/DESIGN.md", 0o644),
    "arayuz-onizleme.html": (f"usr/share/doc/{PAKET}/arayuz-onizleme.html", 0o644),
}
BAKIM_BETIKLERI = ("postinst", "prerm", "postrm")


def bilgi(metin: str) -> None:
    print(f"== {metin}", flush=True)


def dur(metin: str) -> None:
    print(f"HATA: {metin}", file=sys.stderr)
    sys.exit(1)


def sha256(yol: Path) -> str:
    ozet = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def lf(veri: bytes) -> bytes:
    """Depodaki metin dosyaları Windows'ta CRLF'ye dönmüş olabilir; paket LF ister."""
    return veri.replace(b"\r\n", b"\n")


# ---------------------------------------------------------------- indirmeler

def gomulu_python() -> Path:
    yol = ONBELLEK / PYTHON["ad"]
    if not yol.exists() or sha256(yol) != PYTHON["sha256"]:
        bilgi(f"Gömülü Python indiriliyor: {PYTHON['ad']}")
        url = PYTHON["url"]
        if not url.startswith("https://github.com/astral-sh/"):
            dur("Güvensiz indirme adresi: Python arşivi yalnızca resmi kaynaktan indirilebilir")
        with urllib.request.urlopen(url, timeout=120) as yanit, open(gecici, "wb") as f:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            while parca := yanit.read(1 << 20):
                f.write(parca)
        if sha256(gecici) != PYTHON["sha256"]:
            gecici.unlink()
            dur("gömülü Python arşivinin sha256 değeri tutmuyor; indirme bozuk veya değiştirilmiş")
        gecici.replace(yol)
    return yol


def tekerlek_indir(hedef: Path) -> None:
    hedef.mkdir(parents=True, exist_ok=True)
    komut = [sys.executable, "-m", "pip", "download", "--quiet", "--disable-pip-version-check",
             "--no-deps", "-r", str(PAKETLEME / "requirements.txt"), "-d", str(hedef), *PIP_PLATFORM]
    if subprocess.run(komut).returncode != 0:
        dur("tekerlekler indirilemedi (internet bağlantısını kontrol edin)")


def kilidi_oku() -> dict[str, str]:
    kilit = {}
    for satir in KILIT.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if satir and not satir.startswith("#"):
            ozet, ad = satir.split()
            kilit[ad] = ozet
    return kilit


def kilit_guncelle() -> None:
    bilgi("Tekerlekler indiriliyor ve kilit yeniden üretiliyor")
    tekerlek_indir(TEKERLEKLER)
    istenen = {}
    for satir in (PAKETLEME / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in satir and not satir.lstrip().startswith("#"):
            ad, surum = satir.strip().split("==")
            istenen[re.sub(r"[-_.]+", "_", ad.lower())] = surum
    satirlar = ["# requirements.txt'deki her paketin Linux tekerleği ve sha256 özeti.",
                "# Üretmek için: python paketleme/deb_yap.py --kilit-guncelle"]
    for yol in sorted(TEKERLEKLER.glob("*.whl")):
        ad, surum = yol.name.split("-")[:2]
        if istenen.get(ad.lower()) == surum:
            satirlar.append(f"{sha256(yol)}  {yol.name}")
    if len(satirlar) - 2 != len(istenen):
        dur("her paket için tam bir tekerlek bulunamadı; requirements.txt'yi kontrol edin")
    KILIT.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    bilgi(f"Kilit yazıldı: {KILIT.relative_to(KOK)} ({len(satirlar) - 2} tekerlek)")


def tekerlekler() -> list[Path]:
    if not KILIT.exists():
        dur("tekerlek_kilidi.txt yok; önce: python paketleme/deb_yap.py --kilit-guncelle")
    kilit = kilidi_oku()
    eksik = [ad for ad, ozet in kilit.items()
             if not (TEKERLEKLER / ad).exists() or sha256(TEKERLEKLER / ad) != ozet]
    if eksik:
        bilgi(f"{len(eksik)} tekerlek indiriliyor")
        tekerlek_indir(TEKERLEKLER)
    for ad, ozet in kilit.items():
        yol = TEKERLEKLER / ad
        if not yol.exists():
            dur(f"kilitteki tekerlek indirilemedi: {ad}")
        if sha256(yol) != ozet:
            dur(f"tekerlek sha256 tutmuyor: {ad}")
    return [TEKERLEKLER / ad for ad in kilit]


# ---------------------------------------------------------------- paket ağacı

class Agac:
    """Paket içeriği: yol -> ('dosya', izin, veri) | ('bag', 0o777, hedef)."""

    def __init__(self):
        self.girdiler: dict[str, tuple] = {}

    def dosya(self, yol: str, veri: bytes, izin: int = 0o644) -> None:
        self.girdiler[yol] = ("dosya", izin, veri)

    def bag(self, yol: str, hedef: str) -> None:
        self.girdiler[yol] = ("bag", 0o777, hedef)

    def dizinler(self) -> set[str]:
        sonuc = set()
        for yol in self.girdiler:
            parcalar = yol.split("/")[:-1]
            for i in range(1, len(parcalar) + 1):
                sonuc.add("/".join(parcalar[:i]))
        return sonuc

    def boyut(self) -> int:
        return sum(len(g[2]) for g in self.girdiler.values() if g[0] == "dosya")


def python_ekle(agac: Agac, arsiv: Path) -> None:
    with tarfile.open(arsiv) as tf:
        for uye in tf:
            ad = uye.name
            # Bayt kodunu postinst üretir, prerm siler; paket __pycache__ sahiplenmez.
            if uye.isdir() or "/__pycache__/" in ad:
                continue
            if ad.startswith("python/bin/"):
                if ad not in PY_BIN:
                    continue
            elif not ad.startswith(PY_LIB) or ad.startswith(PY_HARIC):
                continue
            hedef = f"{OPT}/{ad}"
            if uye.issym():
                agac.bag(hedef, uye.linkname)
            elif uye.isfile():
                agac.dosya(hedef, tf.extractfile(uye).read(), uye.mode & 0o755)
            else:
                dur(f"gömülü Python arşivinde beklenmeyen girdi türü: {ad}")


def tekerlek_ekle(agac: Agac, yol: Path) -> None:
    with zipfile.ZipFile(yol) as zf:
        for bilgi_ in zf.infolist():
            if bilgi_.is_dir() or "__pycache__" in bilgi_.filename:
                continue
            parcalar = bilgi_.filename.split("/")
            if ".." in parcalar or bilgi_.filename.startswith("/"):
                dur(f"tekerlekte güvensiz yol: {yol.name}: {bilgi_.filename}")
            if parcalar[0].endswith(".data"):
                if len(parcalar) < 3 or parcalar[1] not in ("purelib", "platlib"):
                    continue  # betikler/başlıklar gerekmez
                parcalar = parcalar[2:]
            agac.dosya(f"{SITE}/{'/'.join(parcalar)}", zf.read(bilgi_), 0o644)


def uygulama_ekle(agac: Agac) -> None:
    for yol in sorted((KOK / "uygulama").rglob("*")):
        if not yol.is_file() or "__pycache__" in yol.parts or yol.suffix == ".pyc":
            continue
        goreli = yol.relative_to(KOK).as_posix()
        veri = yol.read_bytes()
        if yol.suffix in (".py", ".html", ".js", ".css", ".md", ".txt", ".svg"):
            veri = lf(veri)
        agac.dosya(f"{OPT}/{goreli}", veri, 0o644)
    for kaynak, (hedef, izin) in SISTEM_DOSYALARI.items():
        agac.dosya(hedef, lf((KOK / kaynak).read_bytes()), izin)


# ---------------------------------------------------------------- arşivler

def _tar_bilgisi(ad: str, zaman: int) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(ad)
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = "root"
    ti.mtime = zaman
    return ti


def tar_xz(girdiler: list[tuple], zaman: int) -> bytes:
    """girdiler: (yol, tür, izin, veri) — 'dizin' / 'dosya' / 'bag'. Sıra korunur."""
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:xz", format=tarfile.GNU_FORMAT, preset=6) as tf:
        kok = _tar_bilgisi("./", zaman)
        kok.type, kok.mode = tarfile.DIRTYPE, 0o755
        tf.addfile(kok)
        for yol, tur, izin, veri in girdiler:
            ti = _tar_bilgisi(f"./{yol}", zaman)
            ti.mode = izin
            if tur == "dizin":
                ti.type = tarfile.DIRTYPE
                tf.addfile(ti)
            elif tur == "bag":
                ti.type, ti.linkname = tarfile.SYMTYPE, veri
                tf.addfile(ti)
            else:
                ti.size = len(veri)
                tf.addfile(ti, io.BytesIO(veri))
    return tampon.getvalue()


def ar_yaz(yol: Path, uyeler: list[tuple[str, bytes]], zaman: int) -> None:
    with open(yol, "wb") as f:
        f.write(b"!<arch>\n")
        for ad, veri in uyeler:
            baslik = f"{ad:<16}{zaman:<12}{0:<6}{0:<6}{'100644':<8}{len(veri):<10}`\n"
            assert len(baslik) == 60
            f.write(baslik.encode("ascii"))
            f.write(veri)
            if len(veri) % 2:
                f.write(b"\n")


def ar_oku(yol: Path) -> dict[str, bytes]:
    veri = yol.read_bytes()
    if not veri.startswith(b"!<arch>\n"):
        dur("üretilen dosya ar arşivi değil")
    uyeler, konum = {}, 8
    while konum < len(veri):
        baslik = veri[konum:konum + 60]
        ad, boyut = baslik[:16].decode().strip(), int(baslik[48:58])
        uyeler[ad] = veri[konum + 60:konum + 60 + boyut]
        konum += 60 + boyut + (boyut % 2)
    return uyeler


# ---------------------------------------------------------------- ana akış

def surum() -> str:
    metin = (KOK / "uygulama" / "ayarlar.py").read_text(encoding="utf-8")
    return re.search(r'^VERSIYON = "([^"]+)"', metin, re.M).group(1)


def git(*argumanlar: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(KOK), *argumanlar], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def paket_yap() -> Path:
    zaman = int(git("log", "-1", "--format=%ct") or time.time())
    agac = Agac()
    bilgi("Gömülü Python hazırlanıyor")
    python_ekle(agac, gomulu_python())
    bilgi("Kütüphaneler hazırlanıyor")
    for yol in tekerlekler():
        tekerlek_ekle(agac, yol)
    bilgi("Uygulama ve sistem dosyaları ekleniyor")
    uygulama_ekle(agac)

    girdiler = [(d, "dizin", 0o755, None) for d in agac.dizinler()]
    girdiler += [(y, tur, izin, veri) for y, (tur, izin, veri) in agac.girdiler.items()]
    girdiler.sort(key=lambda g: g[0])

    # Debian dpkg md5sums standardı (kriptografik amaçlı değildir)
    md5 = "".join(f"{hashlib.md5(veri, usedforsecurity=False).hexdigest()}  {yol}\n"
                  for yol, tur, _, veri in girdiler if tur == "dosya")
    ad, eposta = git("config", "user.name"), git("config", "user.email")
    bakimci = f"{ad or 'Pardus Sinif Yonetimi'} <{eposta or 'root@localhost'}>"
    kontrol = "\n".join([
        f"Package: {PAKET}",
        f"Version: {surum()}",
        "Architecture: amd64",
        f"Maintainer: {bakimci}",
        f"Installed-Size: {math.ceil(agac.boyut() / 1024)}",
        "Depends: libc6 (>= 2.28), systemd, passwd",
        "Recommends: xdg-utils, pkexec | policykit-1, zenity",
        "Section: admin",
        "Priority: optional",
        "Description: Pardus okul laboratuvarları için merkezi yönetim",
        " Öğretmen bilgisayarından öğrenci bilgisayarlarını SSH anahtarıyla yöneten",
        " Türkçe web arayüzü: ağ keşfi, envanter, ders sonu temizliği, yedekleme ve",
        " yedekten dönüş, duvar kâğıdı, yeniden başlatma/kapatma. Öğrencilerin",
        " tarayıcıdan ödev yüklediği yerel Ödev Teslim portalını içerir.",
        " .",
        " Kendi Python çalışma ortamını içerir; kurulum için internet gerekmez.",
    ]) + "\n"
    kontrol_girdileri = [("control", "dosya", 0o644, kontrol.encode("utf-8")),
                         ("md5sums", "dosya", 0o644, md5.encode("utf-8"))]
    for betik in BAKIM_BETIKLERI:
        veri = lf((PAKETLEME / "debian" / betik).read_bytes())
        kontrol_girdileri.append((betik, "dosya", 0o755, veri))

    bilgi("Arşivler sıkıştırılıyor (bir iki dakika sürebilir)")
    control_tar = tar_xz(kontrol_girdileri, zaman)
    data_tar = tar_xz(girdiler, zaman)

    CIKTI.mkdir(exist_ok=True)
    deb = CIKTI / f"{PAKET}_{surum()}_amd64.deb"
    ar_yaz(deb, [("debian-binary", b"2.0\n"), ("control.tar.xz", control_tar),
                 ("data.tar.xz", data_tar)], zaman)
    dogrula(deb)
    ozet = sha256(deb)
    (deb.parent / (deb.name + ".sha256")).write_text(f"{ozet}  {deb.name}\n", encoding="ascii")
    bilgi(f"Paket hazır: {deb.relative_to(KOK)} ({deb.stat().st_size / 1048576:.1f} MB)")
    print(f"   sha256: {ozet}")
    print(f"   Kurulum (öğretmen bilgisayarında):  sudo dpkg -i {deb.name}")
    return deb


def dogrula(deb: Path) -> None:
    """Üretilen paketi geri okuyup temel yapıyı denetler."""
    uyeler = ar_oku(deb)
    if list(uyeler) != ["debian-binary", "control.tar.xz", "data.tar.xz"]:
        dur(f"ar üyeleri beklenmedik: {list(uyeler)}")
    with tarfile.open(fileobj=io.BytesIO(uyeler["control.tar.xz"])) as tf:
        adlar = set(tf.getnames())
        for gerekli in ("./control", "./md5sums", *(f"./{b}" for b in BAKIM_BETIKLERI)):
            if gerekli not in adlar:
                dur(f"control.tar içinde {gerekli} yok")
        for b in BAKIM_BETIKLERI:
            if b"\r" in tf.extractfile(f"./{b}").read():
                dur(f"{b} CRLF içeriyor")
    with tarfile.open(fileobj=io.BytesIO(uyeler["data.tar.xz"])) as tf:
        adlar = {u.name: u for u in tf.getmembers()}
    for gerekli in (f"./{OPT}/python/bin/python3.12", f"./{OPT}/uygulama/ana.py",
                    f"./{OPT}/uygulama/odev/portal.py", f"./{OPT}/uygulama/odev/arayuz/portal.js",
                    "./lib/systemd/system/pardus-sinif-odev.service",
                    f"./{OPT}/uygulama/uzak/yedek.py", f"./{OPT}/uygulama/uzak/hazirlik.py",
                    f"./{OPT}/uygulama/uzak/gorunum.py", f"./{OPT}/uygulama/uzak/paket.py",
                    f"./{OPT}/uygulama/uzak/veyon.py", f"./{OPT}/uygulama/veyon.py",
                    f"./{OPT}/uygulama/arayuz/veyon.js", f"./{OPT}/uygulama/arayuz/guc.js",
                    f"./{OPT}/uygulama/uzak/guc_ayar.py", f"./{OPT}/uygulama/guc_ayar.py",
                    f"./{OPT}/uygulama/uzak/sinif.py", f"./{OPT}/uygulama/sinif_araclari.py",
                    f"./{OPT}/uygulama/komutlar.py",
                    f"./{OPT}/uygulama/arayuz/referans.js", f"./{OPT}/uygulama/arayuz/belirtecler.css",
                    f"./{SITE}/fastapi/__init__.py",
                    f"./{SITE}/paramiko/__init__.py", f"./usr/bin/{PAKET}",
                    f"./lib/systemd/system/{PAKET}.service"):
        if gerekli not in adlar:
            dur(f"data.tar içinde {gerekli} yok")
    if not adlar[f"./usr/bin/{PAKET}"].mode & 0o111:
        dur("başlatıcı çalıştırılabilir değil")
    if any(u.uid or u.gid for u in adlar.values()):
        dur("root dışı sahiplik bulundu")


def main() -> None:
    for akis in (sys.stdout, sys.stderr):  # Windows konsolu (cp1252) Türkçe harfte çökmesin
        akis.reconfigure(encoding="utf-8", errors="replace")
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--kilit-guncelle", action="store_true",
                             help="requirements.txt'e göre tekerlek kilidini yeniden üret")
    argumanlar = ayristirici.parse_args()
    if argumanlar.kilit_guncelle:
        kilit_guncelle()
        return
    paket_yap()


if __name__ == "__main__":
    main()
