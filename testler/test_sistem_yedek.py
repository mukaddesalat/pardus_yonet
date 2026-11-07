"""Yönetim uygulaması tam sistem yedekleme, taşıma (.tar.gz + .deb + yedekten-kur.sh) ve geri yükleme testleri."""

import io
import json
import tarfile
from pathlib import Path

from uygulama import ayarlar, sistem_yedek, veritabani
from uygulama.odev import vt as odev_vt


def test_tam_sistem_yedekleme_inceleme_ve_geri_yukleme():
    y = ayarlar.veri_yollari()
    veritabani.ac()
    odev_vt.ac()

    # 1) Örnek okul, bilgisayar, öğretmen, SSH anahtarı, Veyon anahtarı ve sınıf oluştur
    veritabani.okul_kaydet("Atatürk Fen Lisesi", "Bilişim Lab-1", "")
    veritabani.calistir("DELETE FROM cihaz")
    veritabani.cihaz_bul_veya_olustur("192.168.1.51", 22)
    veritabani.cihaz_bul_veya_olustur("192.168.1.52", 22)

    y["anahtar_dizini"].mkdir(parents=True, exist_ok=True)
    ozel_icerik = b"-----BEGIN OPENSSH PRIVATE KEY-----\ntest-ozel-anahtar-123\n-----END OPENSSH PRIVATE KEY-----\n"
    acik_icerik = b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest pardus-sinif-yonetimi@test\n"
    y["ozel_anahtar"].write_bytes(ozel_icerik)
    y["acik_anahtar"].write_bytes(acik_icerik)

    y["veyon_dizini"].mkdir(parents=True, exist_ok=True)
    (y["veyon_dizini"] / "public_key.pem").write_text("-----BEGIN PUBLIC KEY-----\nTEST\n-----END PUBLIC KEY-----\n", encoding="utf-8")

    odev_vt.calistir("DELETE FROM teslim_dosya")
    odev_vt.calistir("DELETE FROM teslim")
    odev_vt.calistir("DELETE FROM odev")
    odev_vt.calistir("DELETE FROM ogrenci")
    odev_vt.calistir("DELETE FROM sinif")
    odev_vt.calistir("INSERT INTO sinif(id, ad) VALUES('s1', '10-A')")
    odev_vt.calistir("INSERT INTO ogrenci(id, sinif_id, numara, ad_soyad) VALUES('o1', 's1', '101', 'Ali Yılmaz')")

    ozet = sistem_yedek.sistem_ozeti()
    assert ozet["okul_adi"] == "Atatürk Fen Lisesi"
    assert ozet["cihaz_sayisi"] == 2
    assert ozet["sinif_sayisi"] == 1
    assert ozet["ogrenci_sayisi"] == 1
    assert ozet["ssh_anahtari_var"] is True
    assert ozet["veyon_anahtari_var"] is True

    # 2) Yedek oluştur (hızlı test için deb_dahil=False ve deb_dahil=True kontrolü)
    meta = sistem_yedek.yedek_olustur(
        aciklama="Taşıma testi yedeği",
        deb_dahil=False,
        odev_teslimleri_dahil=True,
        yerel_paketler_dahil=False,
    )
    assert meta["dosya_adi"].startswith("pardus-sinif-yonetimi-yedek_")
    assert meta["boyut"] > 1000
    arsiv_yolu = sistem_yedek.yedek_yolu(meta["dosya_adi"])
    assert arsiv_yolu.is_file()

    # Arşiv içinde yedekten-kur.sh, BENIOKU.txt, manifest.json, veri/envanter.db, odev/odev.db var mı?
    with tarfile.open(arsiv_yolu, "r:gz") as tf:
        isimler = set(tf.getnames())
        assert f"{sistem_yedek.ARSIV_KOK}/manifest.json" in isimler
        assert f"{sistem_yedek.ARSIV_KOK}/yedekten-kur.sh" in isimler
        assert f"{sistem_yedek.ARSIV_KOK}/BENIOKU.txt" in isimler
        assert f"{sistem_yedek.ARSIV_KOK}/veri/envanter.db" in isimler
        assert f"{sistem_yedek.ARSIV_KOK}/veri/anahtar/uygulama_ed25519" in isimler
        assert f"{sistem_yedek.ARSIV_KOK}/odev/odev.db" in isimler
        betik = tf.extractfile(f"{sistem_yedek.ARSIV_KOK}/yedekten-kur.sh").read()
        assert b"\r\n" not in betik
        assert b"dpkg -i" in betik

    # 3) Yedeği incele ve SHA-256 bütünlüğünü doğrula
    inceleme = sistem_yedek.yedek_incele(arsiv_yolu, tam_sha_dogrula=True)
    assert inceleme["gecerli"] is True
    assert inceleme["ozet"]["okul_adi"] == "Atatürk Fen Lisesi"
    assert inceleme["ozet"]["cihaz_sayisi"] == 2

    # 4) Canlı verileri değiştir / sil (farklı bir bilgisayara kurulum simülasyonu)
    veritabani.okul_kaydet("Boş Kurulum Okulu", "Varsayılan", "")
    veritabani.calistir("DELETE FROM cihaz")
    y["ozel_anahtar"].write_bytes(b"degistirildi")
    odev_vt.calistir("DELETE FROM teslim_dosya")
    odev_vt.calistir("DELETE FROM teslim")
    odev_vt.calistir("DELETE FROM odev")
    odev_vt.calistir("DELETE FROM ogrenci")
    odev_vt.calistir("DELETE FROM sinif")
    assert len(veritabani.cihazlar()) == 0

    # 5) Yedekten geri yükle
    sonuc = sistem_yedek.yedek_geri_yukle(arsiv_yolu, otomatik_yedek=True)
    assert sonuc["durum"] == "tamamlandi"
    assert sonuc["onceki_yedek"] is not None
    assert veritabani.okul_bilgisi()["ad"] == "Atatürk Fen Lisesi"
    assert len(veritabani.cihazlar()) == 2
    assert y["ozel_anahtar"].read_bytes() == ozel_icerik
    assert int(odev_vt.tek("SELECT COUNT(*) AS n FROM ogrenci")["n"]) == 1


def test_bozuk_veya_guvensiz_arsiv_reddedilir():
    # Path traversal (TarSlip) denemesi
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as tf:
        ti = tarfile.TarInfo("../../etc/passwd")
        veri = b"root:x:0:0"
        ti.size = len(veri)
        tf.addfile(ti, io.BytesIO(veri))
    try:
        sistem_yedek.yedek_incele(tampon.getvalue())
        assert False, "Güvensiz arşiv yolu reddedilmeliydi"
    except sistem_yedek.SistemYedekHatasi as hata:
        assert "güvensiz" in str(hata).lower()

