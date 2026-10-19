"""Debian paketi (.deb) yapısal doğrulama ve control alanlarını okuma.

Uzantıya güvenilmez: dosya `ar` arşivi olmalı, ilk üye "debian-binary" = "2.0",
ardından control.tar.* ve data.tar.* gelmelidir. control dosyası saf Python ile
(gz/xz/sıkıştırmasız) okunur; zstd gibi desteklenmeyen sıkıştırmada sistemdeki
`dpkg-deb` kullanılır (Pardus'ta vardır).
"""

import io
import lzma
import re
import shutil
import subprocess
import tarfile
import zlib

AR_IMZA = b"!<arch>\n"
PAKET_DESENI = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")
SURUM_DESENI = re.compile(r"^(\d+:)?[A-Za-z0-9.+~-]+$")
MIMARILER = {"amd64", "i386", "arm64", "armhf", "all"}
ALANLAR = ("Package", "Version", "Architecture", "Maintainer", "Installed-Size", "Depends",
           "Pre-Depends", "Recommends", "Conflicts", "Breaks", "Replaces", "Provides",
           "Essential", "Priority", "Section", "Description")


class PaketHatasi(ValueError):
    """Öğretmene olduğu gibi gösterilir."""


def _ar_uyeleri(f):
    """(ad, veri_başlangıcı, boyut) üreteci; yalnız başlıkları okur."""
    f.seek(0)
    if f.read(8) != AR_IMZA:
        raise PaketHatasi("Dosya bir Debian paketi değil (ar imzası yok)")
    while True:
        baslik = f.read(60)
        if not baslik:
            return
        if len(baslik) < 60 or baslik[58:60] != b"`\n":
            raise PaketHatasi("Bozuk paket: ar üye başlığı geçersiz")
        ad = baslik[:16].decode("ascii", "replace").strip().rstrip("/")
        try:
            boyut = int(baslik[48:58].decode("ascii").strip())
        except ValueError:
            raise PaketHatasi("Bozuk paket: üye boyutu okunamadı")
        bas = f.tell()
        yield ad, bas, boyut
        f.seek(bas + boyut + (boyut % 2))


def _control_ac(ad: str, veri: bytes) -> bytes:
    if ad == "control.tar.gz":
        return zlib.decompress(veri, 16 + zlib.MAX_WBITS)
    if ad == "control.tar.xz":
        return lzma.decompress(veri)
    if ad == "control.tar":
        return veri
    raise NotImplementedError(ad)


def control_ayristir(metin: str) -> dict:
    """RFC822 benzeri control dosyası; devam satırları birleştirilir."""
    alanlar, son = {}, None
    for satir in metin.splitlines():
        if satir.startswith((" ", "\t")) and son:
            alanlar[son] += "\n" + satir.strip()
        elif ":" in satir:
            ad, deger = satir.split(":", 1)
            son = ad.strip()
            alanlar[son] = deger.strip()
    return alanlar


def incele(yol: str) -> dict:
    """Paketi doğrular ve özet döndürür. Geçersizse PaketHatasi."""
    with open(yol, "rb") as f:
        uyeler = list(_ar_uyeleri(f))
        adlar = [u[0] for u in uyeler]
        if len(uyeler) < 3 or adlar[0] != "debian-binary":
            raise PaketHatasi("Bozuk paket: ilk üye debian-binary değil")
        if not adlar[1].startswith("control.tar") or not any(a.startswith("data.tar") for a in adlar[2:]):
            raise PaketHatasi("Bozuk paket: control.tar / data.tar üyeleri eksik")
        _, bas, boyut = uyeler[0]
        f.seek(bas)
        if f.read(boyut).strip() != b"2.0":
            raise PaketHatasi("Desteklenmeyen paket biçimi (debian-binary 2.0 değil)")
        ad, bas, boyut = uyeler[1]
        f.seek(bas)
        ham = f.read(boyut)

    kontrol_metni = None
    try:
        tar_verisi = _control_ac(ad, ham)
        with tarfile.open(fileobj=io.BytesIO(tar_verisi)) as tf:
            for uye in tf.getmembers():
                if uye.name.lstrip("./") == "control" and uye.isfile():
                    kontrol_metni = tf.extractfile(uye).read().decode("utf-8", "replace")
                    break
    except NotImplementedError:
        kontrol_metni = _dpkg_deb_ile(yol)
    except (OSError, EOFError, lzma.LZMAError, zlib.error, tarfile.TarError):
        raise PaketHatasi("Bozuk paket: control arşivi açılamadı")
    if not kontrol_metni:
        raise PaketHatasi("Bozuk paket: control dosyası yok")

    alanlar = control_ayristir(kontrol_metni)
    paket, surum, mimari = (alanlar.get("Package", ""), alanlar.get("Version", ""),
                            alanlar.get("Architecture", ""))
    if not PAKET_DESENI.match(paket):
        raise PaketHatasi("Geçersiz paket adı")
    if not SURUM_DESENI.match(surum):
        raise PaketHatasi("Geçersiz paket sürümü")
    if mimari not in MIMARILER:
        raise PaketHatasi(f"Desteklenmeyen mimari: {mimari or '?'}")
    try:
        kurulu_kb = int(alanlar.get("Installed-Size", "0") or 0)
    except ValueError:
        kurulu_kb = 0
    return {"paket": paket, "surum": surum, "mimari": mimari, "kurulu_kb": kurulu_kb,
            "kontrol": {a: alanlar[a] for a in ALANLAR if a in alanlar},
            "uyeler": adlar}


def _dpkg_deb_ile(yol: str) -> str | None:
    if not shutil.which("dpkg-deb"):
        raise PaketHatasi("Bu paketin sıkıştırma biçimi okunamadı ve dpkg-deb bulunamadı")
    r = subprocess.run(["dpkg-deb", "-f", yol], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise PaketHatasi("dpkg-deb paketi okuyamadı: " + r.stderr.strip()[-200:])
    return r.stdout
