"""Uzak geri yükleme birleştirme kuralı (uzak/yedek.py → birlestir).

Kural (proje sahibi kararı): yoksa geri koy; özet aynıysa üzerine yaz; özet
farklıysa ikisini de tut, geri geleni "(yedek <tarih>)" ekiyle yeniden adlandır.
"""

import io
import os
import sys
import tarfile

import pytest

from uygulama.uzak import yedek

ETIKET = "26.09.2026 14.30"


def _arsiv(uyeler: dict, kok="ogrenci") -> tarfile.TarFile:
    """{göreli yol: bytes | None(klasör) | ('link', hedef)} -> okunmaya hazır tar."""
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w") as tf:
        for ad, icerik in uyeler.items():
            tam = f"{kok}/{ad}" if kok else ad
            bilgi = tarfile.TarInfo(tam)
            bilgi.mtime = 1_790_000_000
            if icerik is None:
                bilgi.type, bilgi.mode = tarfile.DIRTYPE, 0o755
                tf.addfile(bilgi)
            elif isinstance(icerik, tuple):
                bilgi.type, bilgi.linkname = tarfile.SYMTYPE, icerik[1]
                tf.addfile(bilgi)
            else:
                bilgi.size, bilgi.mode = len(icerik), 0o644
                tf.addfile(bilgi, io.BytesIO(icerik))
    tampon.seek(0)
    return tarfile.open(fileobj=tampon, mode="r|")


def _oku(yol):
    with open(yol, "rb") as f:
        return f.read()


def test_yeni_dosya_geri_konur(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    sonuc = yedek.birlestir(_arsiv({"Masaüstü": None, "Masaüstü/odev.txt": b"odev"}),
                            str(ev), None, ETIKET)
    assert _oku(ev / "Masaüstü" / "odev.txt") == b"odev"
    assert sonuc["yeni"] == 1 and sonuc["yan_yana"] == 0


def test_ayni_ozet_uzerine_yazilir(tmp_path):
    ev = tmp_path / "ev"
    (ev / "Masaüstü").mkdir(parents=True)
    (ev / "Masaüstü" / "odev.txt").write_bytes(b"ayni")
    sonuc = yedek.birlestir(_arsiv({"Masaüstü": None, "Masaüstü/odev.txt": b"ayni"}),
                            str(ev), None, ETIKET)
    assert sonuc["ayni"] == 1 and sonuc["yan_yana"] == 0
    assert sorted(os.listdir(ev / "Masaüstü")) == ["odev.txt"]


def test_farkli_ozet_ikisini_de_tutar(tmp_path):
    ev = tmp_path / "ev"
    (ev / "Masaüstü").mkdir(parents=True)
    (ev / "Masaüstü" / "rapor.odt").write_bytes(b"yeni hali")
    sonuc = yedek.birlestir(_arsiv({"Masaüstü": None, "Masaüstü/rapor.odt": b"eski hali"}),
                            str(ev), None, ETIKET)
    assert sonuc["yan_yana"] == 1
    assert _oku(ev / "Masaüstü" / "rapor.odt") == b"yeni hali"  # mevcut dosyaya dokunulmaz
    assert _oku(ev / "Masaüstü" / f"rapor (yedek {ETIKET}).odt") == b"eski hali"


def test_ikinci_catismada_sira_numarasi(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    (ev / "not.txt").write_bytes(b"1")
    (ev / f"not (yedek {ETIKET}).txt").write_bytes(b"2")
    yedek.birlestir(_arsiv({"not.txt": b"3"}), str(ev), None, ETIKET)
    assert _oku(ev / f"not (yedek {ETIKET}) 2.txt") == b"3"


def test_gizli_ve_uzantisiz_dosya_adi(tmp_path):
    assert os.path.basename(yedek.yan_ad(str(tmp_path / ".bashrc"), ETIKET)) == \
        f".bashrc (yedek {ETIKET})"
    assert os.path.basename(yedek.yan_ad(str(tmp_path / "Makefile"), ETIKET)) == \
        f"Makefile (yedek {ETIKET})"


def test_klasor_yerine_dosya_varsa_klasor_yan_ada_acilir(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    (ev / "Proje").write_bytes(b"bir dosya")
    sonuc = yedek.birlestir(_arsiv({"Proje": None, "Proje/a.txt": b"a"}), str(ev), None, ETIKET)
    assert _oku(ev / "Proje") == b"bir dosya"
    assert _oku(ev / f"Proje (yedek {ETIKET})" / "a.txt") == b"a"
    assert sonuc["yeni"] == 1 and sonuc["hatali"] == 0


def test_karantina_kok_adi_atilir(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    yedek.birlestir(_arsiv({"İndirilenler": None, "İndirilenler/x.pdf": b"%PDF"}, kok="veri"),
                    str(ev), "veri", ETIKET)
    assert _oku(ev / "İndirilenler" / "x.pdf") == b"%PDF"


@pytest.mark.parametrize("kotu_ad", ["ogrenci/../../etc/passwd", "/etc/passwd",
                                     "baska/dosya.txt"])
def test_kacis_ve_yabanci_kok_atlanir(tmp_path, kotu_ad):
    ev = tmp_path / "ev"
    ev.mkdir()
    uyeler = {"ogrenci/a.txt": b"a", kotu_ad: b"kotu"}
    sonuc = yedek.birlestir(_arsiv(uyeler, kok=""), str(ev), None, ETIKET)
    assert sonuc["atlanan"] == 1 and sonuc["yeni"] == 1
    assert not (tmp_path / "etc").exists()
    assert sorted(os.listdir(ev)) == ["a.txt"]


@pytest.mark.skipif(sys.platform == "win32", reason="sembolik bağlantı yetkisi gerekir")
def test_sembolik_baglanti_yeniden_olusturulur(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    sonuc = yedek.birlestir(_arsiv({"kisayol": ("link", "Belgeler/x")}), str(ev), None, ETIKET)
    assert os.readlink(ev / "kisayol") == "Belgeler/x" and sonuc["yeni"] == 1


def test_zaman_bilgisi():
    assert yedek.zaman_bilgisi("20260926", "143005") == ("2026-09-26T14:30:05", "26.09.2026 14.30")


def test_desenler_hesaba_ozel():
    assert yedek.profil_deseni("ogrenci").match("ogrenci-20260926-143005.tar.gz")
    assert not yedek.profil_deseni("ogrenci").match("ogrenci2-20260926-143005.tar.gz")
    assert not yedek.profil_deseni("ogrenci").match("../ogrenci-20260926-143005.tar.gz")
    assert yedek.karantina_deseni("ogrenci").match("20260926-143005-ogrenci")


def test_sabit_baglanti_icerigiyle_geri_konur(tmp_path):
    """Karantinadaki sabit bağlantılı dosyanın ikinci adı da geri gelir (lab01'de bulundu)."""
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w") as tf:
        for ad, tur in (("veri", tarfile.DIRTYPE), ("veri/Masaüstü", tarfile.DIRTYPE)):
            b = tarfile.TarInfo(ad)
            b.type, b.mode = tur, 0o755
            tf.addfile(b)
        b = tarfile.TarInfo("veri/Masaüstü/buyuk.bin")
        b.size, b.mode = 5, 0o644
        tf.addfile(b, io.BytesIO(b"12345"))
        b = tarfile.TarInfo("veri/Masaüstü/bag.bin")
        b.type, b.linkname, b.mode = tarfile.LNKTYPE, "veri/Masaüstü/buyuk.bin", 0o644
        tf.addfile(b)
    tampon.seek(0)
    ev = tmp_path / "ev"
    ev.mkdir()
    sonuc = yedek.birlestir(tarfile.open(fileobj=tampon, mode="r|"), str(ev), "veri", ETIKET)
    assert _oku(ev / "Masaüstü" / "bag.bin") == b"12345"
    assert sonuc["yeni"] == 2 and sonuc["atlanan"] == 0
