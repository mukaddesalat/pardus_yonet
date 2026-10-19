"""Ödev Teslim modülü: kurallar, kodlar, sınıf listesi ve teslim yaşam döngüsü."""

import asyncio
import io
import json
import zipfile
from datetime import timedelta

import pytest

from uygulama.odev import kod, kurallar, odevler, ortak, siniflar, teslim, vt


def _akis(*parcalar: bytes):
    async def uret():
        for p in parcalar:
            yield p
    return uret()


def _yaz(ogrenci, teslim_id, sira, veri: bytes):
    return asyncio.run(teslim.dosya_yaz(ogrenci, teslim_id, sira,
                                        _akis(veri[:3], veri[3:]), len(veri)))


@pytest.fixture()
def sinif():
    """Her test için ayrı sınıf, iki öğrenci ve açık bir ödev."""
    ad = "T-" + vt.yeni_kimlik()[:6]
    sinif_id = siniflar.sinif_bul_veya_olustur(ad)
    a = siniflar.ogrenci_ekle(sinif_id, "12", "Ayşe Yılmaz")
    b = siniflar.ogrenci_ekle(sinif_id, "7", "Mehmet Öz")
    kodlar = {k["id"]: k["kod"] for k in siniflar.kod_uret([a, b])}
    odev_id = odevler.olustur({"baslik": "Proje 1", "sinif_id": sinif_id,
                               "turler": ["belge", "arsiv", "kod"], "en_fazla_dosya": 5,
                               "en_fazla_mb": 1})
    odevler.durum_degistir(odev_id, "ac")
    ogr = lambda i: vt.tek("SELECT id, sinif_id FROM ogrenci WHERE id=?", (i,))  # noqa: E731
    return {"sinif_id": sinif_id, "a": ogr(a), "b": ogr(b), "odev_id": odev_id, "kodlar": kodlar}


class TestKurallar:
    @pytest.mark.parametrize("yol", ["/etc/passwd", "../x.py", "a/../../b.txt", "C:/x.txt",
                                     "a\x00b.txt", "", "a/b:c.txt"])
    def test_tehlikeli_yollar(self, yol):
        with pytest.raises(kurallar.KuralHatasi):
            kurallar.yol_dogrula(yol)

    def test_yol_normallesir(self):
        assert kurallar.yol_dogrula("proje\\src/./main.py") == "proje/src/main.py"

    def test_liste_butun_olarak_reddedilir(self):
        odev = {"en_fazla_dosya": 5, "en_fazla_bayt": 100, "klasor_izni": 1}
        izinli = {"pdf", "py"}
        with pytest.raises(kurallar.KuralHatasi):  # bir dosya bile uymazsa hepsi reddedilir
            kurallar.liste_dogrula([{"yol": "a.pdf", "boyut": 1}, {"yol": "b.exe", "boyut": 1}],
                                   odev, izinli)
        with pytest.raises(kurallar.KuralHatasi):  # büyük/küçük harf çakışması
            kurallar.liste_dogrula([{"yol": "A.py", "boyut": 1}, {"yol": "a.PY", "boyut": 1}],
                                   odev, izinli)
        with pytest.raises(kurallar.KuralHatasi):  # dosya ile klasör aynı adda
            kurallar.liste_dogrula([{"yol": "x.py", "boyut": 1}, {"yol": "x.py/y.py", "boyut": 1}],
                                   odev, izinli)
        with pytest.raises(kurallar.KuralHatasi):  # toplam boyut
            kurallar.liste_dogrula([{"yol": "a.pdf", "boyut": 101}], odev, izinli)
        with pytest.raises(kurallar.KuralHatasi):  # klasör izni yok
            kurallar.liste_dogrula([{"yol": "d/a.pdf", "boyut": 1}],
                                   {**odev, "klasor_izni": 0}, izinli)

    def test_icerik_imzasi(self):
        assert kurallar.icerik_uyusuyor_mu("pdf", b"%PDF-1.7 ...", 10)
        assert not kurallar.icerik_uyusuyor_mu("pdf", b"<html><script>", 10)
        assert kurallar.icerik_uyusuyor_mu("docx", b"PK\x03\x04....", 10)
        assert not kurallar.icerik_uyusuyor_mu("py", b"\x7fELF\x00\x00", 10)
        assert kurallar.icerik_uyusuyor_mu("py", b"print('merhaba')", 10)
        assert not kurallar.icerik_uyusuyor_mu("zip", b"", 0)


class TestKod:
    def test_bicim_ve_dogrulama(self):
        k = kod.uret()
        assert len(k) == 9 and k[4] == "-"
        assert all(ch in kod.ALFABE for ch in k.replace("-", ""))
        kayit = kod.ozet(k)
        assert k not in kayit
        assert kod.dogru_mu(k.lower().replace("-", " "), kayit)
        assert not kod.dogru_mu("AAAA-AAAA", kayit)
        assert not kod.dogru_mu(k, None)


class TestSinifListesi:
    def test_csv_ice_aktarma_ve_disari_aktarma(self):
        veri = "sınıf;öğrenci numarası;ad soyad\n10-B;5;Çağrı Şen\n10-B;6;Işıl Gök\n10-B;x y;Hatalı\n"
        sonuc = siniflar.ice_aktar(veri.encode("cp1254"))
        assert sonuc["eklenen"] == 2 and len(sonuc["hatalar"]) == 1
        sinif_id = vt.tek("SELECT id FROM sinif WHERE ad='10-B'")["id"]
        ids = [o["id"] for o in siniflar.ogrenciler(sinif_id)]
        siniflar.kod_uret(ids)
        csv_metni = siniflar.disari_aktar(sinif_id)
        assert "Çağrı Şen" in csv_metni and "$" not in csv_metni   # kod özeti yok
        # yeniden içe aktarma adı günceller, kodu korur
        siniflar.ice_aktar("10-B,5,Çağrı Şenol\n".encode())
        ogr = vt.tek("SELECT ad_soyad, kod_ozeti FROM ogrenci WHERE sinif_id=? AND numara='5'",
                     (sinif_id,))
        assert ogr["ad_soyad"] == "Çağrı Şenol" and ogr["kod_ozeti"]


class TestTeslim:
    def test_tam_akis_surumler_ve_idempotentlik(self, sinif):
        a, odev_id = sinif["a"], sinif["odev_id"]
        bas = teslim.baslat(a, odev_id, [{"yol": "proje/main.py", "boyut": 11},
                                         {"yol": "rapor.pdf", "boyut": 9}], "10.0.0.5")
        tid = bas["teslim_id"]
        with pytest.raises(teslim.TeslimHatasi):   # eksik dosyayla teslim alınmaz
            teslim.tamamla(a, tid)
        _yaz(a, tid, 1, b"print('hi')")
        _yaz(a, tid, 2, b"%PDF-1.7\n")
        m1 = teslim.tamamla(a, tid)
        assert m1["surum"] == 1 and m1["dosya_sayisi"] == 2
        assert teslim.tamamla(a, tid) == m1          # ağ tekrarı ikinci teslim üretmez
        assert (ortak.yollar()["teslimler"] / odev_id / tid / "0001").read_bytes() == b"print('hi')"
        bas2 = teslim.baslat(a, odev_id, [{"yol": "rapor.pdf", "boyut": 9}], "10.0.0.5")
        _yaz(a, bas2["teslim_id"], 1, b"%PDF-2.0\n")
        assert teslim.tamamla(a, bas2["teslim_id"])["surum"] == 2   # bilinçli yeni sürüm

    def test_baska_ogrenci_erisemez(self, sinif):
        bas = teslim.baslat(sinif["a"], sinif["odev_id"], [{"yol": "a.txt", "boyut": 1}], "")
        for islev in (lambda: teslim.durum(sinif["b"], bas["teslim_id"]),
                      lambda: teslim.tamamla(sinif["b"], bas["teslim_id"]),
                      lambda: _yaz(sinif["b"], bas["teslim_id"], 1, b"x")):
            with pytest.raises(teslim.TeslimHatasi) as hata:
                islev()
            assert hata.value.kod == 404

    def test_icerik_uyusmazligi_ve_boyut(self, sinif):
        a = sinif["a"]
        bas = teslim.baslat(a, sinif["odev_id"], [{"yol": "odev.pdf", "boyut": 20}], "")
        with pytest.raises(teslim.TeslimHatasi) as hata:
            _yaz(a, bas["teslim_id"], 1, b"<script>alert(1)</sc")   # 20 bayt HTML
        assert hata.value.kod == 415
        # bu dosya listesiyle gönderim tamamlanamaz: hemen "yükleme hatası" sayılır
        assert teslim.durum(a, bas["teslim_id"])["durum"] == "yarim"
        assert not (ortak.yollar()["gecici"] / bas["teslim_id"]).exists()
        bas2 = teslim.baslat(a, sinif["odev_id"], [{"yol": "odev.pdf", "boyut": 20}], "")
        with pytest.raises(teslim.TeslimHatasi) as hata:
            _yaz(a, bas2["teslim_id"], 1, b"%PDF-" + b"x" * 30)      # bildirilenden büyük
        assert hata.value.kod == 400
        assert teslim.durum(a, bas2["teslim_id"])["durum"] == "yarim"

    def test_kapatilinca_yarim_aktarim_teslim_sayilmaz(self, sinif):
        a = sinif["a"]
        bas = teslim.baslat(a, sinif["odev_id"], [{"yol": "a.txt", "boyut": 1}], "")
        _yaz(a, bas["teslim_id"], 1, b"x")
        odevler.durum_degistir(sinif["odev_id"], "kapat")
        with pytest.raises(teslim.TeslimHatasi):
            teslim.tamamla(a, bas["teslim_id"])
        assert teslim.durum(a, bas["teslim_id"])["durum"] == "yarim"

    def test_sure_ve_gec_teslim(self, sinif):
        a, odev_id = sinif["a"], sinif["odev_id"]
        gecmis = (ortak.simdi() - timedelta(minutes=5)).isoformat(timespec="seconds")
        vt.calistir("UPDATE odev SET son_tarih=?, gec_teslim=0 WHERE id=?", (gecmis, odev_id))
        with pytest.raises(teslim.TeslimHatasi) as hata:
            teslim.baslat(a, odev_id, [{"yol": "a.txt", "boyut": 1}], "")
        assert "süresi doldu" in hata.value.mesaj
        vt.calistir("UPDATE odev SET gec_teslim=1 WHERE id=?", (odev_id,))
        bas = teslim.baslat(a, odev_id, [{"yol": "a.txt", "boyut": 1}], "")
        _yaz(a, bas["teslim_id"], 1, b"x")
        assert teslim.tamamla(a, bas["teslim_id"])["gec"] is True

    def test_servis_yeniden_baslayinca_yarim_kalanlar(self, sinif):
        a = sinif["a"]
        bas = teslim.baslat(a, sinif["odev_id"], [{"yol": "a.txt", "boyut": 1}], "")
        _yaz(a, bas["teslim_id"], 1, b"x")
        # tamamla, klasörü taşıdıktan sonra kesilmiş gibi: kayıtsız kalıcı klasör
        sahte = ortak.yollar()["teslimler"] / sinif["odev_id"] / "kayitsiz"
        sahte.mkdir(parents=True)
        teslim.onar(acilista=True)
        assert teslim.durum(a, bas["teslim_id"])["durum"] == "yarim"
        assert not sahte.exists()
        with pytest.raises(teslim.TeslimHatasi):
            teslim.tamamla(a, bas["teslim_id"])

    def test_takip_sinif_listesine_dayanir_ve_zip(self, sinif):
        a, odev_id = sinif["a"], sinif["odev_id"]
        for icerik in (b"%PDF-1\n", b"%PDF-2\n"):
            bas = teslim.baslat(a, odev_id, [{"yol": "belge/rapor.pdf", "boyut": 7}], "")
            _yaz(a, bas["teslim_id"], 1, icerik)
            teslim.tamamla(a, bas["teslim_id"])
        detay = odevler.detay(odev_id)
        assert detay["ozet"]["toplam"] == 2 and detay["ozet"]["teslim_eden"] == 1
        assert not detay["ozet"]["tamami_teslim_etti"]
        durumlar = {s["numara"]: s["durum"] for s in detay["ogrenciler"]}
        assert durumlar == {"12": "alindi", "7": "etmedi"}

        ad, girdiler = odevler.zip_girdileri(odev_id, None, tum_surumler=False)
        veri = b"".join(odevler.zip_akisi(girdiler))
        with zipfile.ZipFile(io.BytesIO(veri)) as zf:
            adlar = zf.namelist()
            assert len(adlar) == 1 and adlar[0].endswith("12 Ayşe Yılmaz/Teslim 2/belge/rapor.pdf")
            assert zf.read(adlar[0]) == b"%PDF-2\n"
        _, tum = odevler.zip_girdileri(odev_id, None, tum_surumler=True)
        assert {g[1].split("/")[2] for g in tum} == {"Teslim 1", "Teslim 2"}

    def test_yeni_gonderim_oncekini_gecersiz_kilar(self, sinif):
        a = sinif["a"]
        eski = teslim.baslat(a, sinif["odev_id"], [{"yol": "a.txt", "boyut": 1}], "")
        teslim.baslat(a, sinif["odev_id"], [{"yol": "b.txt", "boyut": 1}], "")
        assert teslim.durum(a, eski["teslim_id"])["durum"] == "yarim"


def test_arsivlenmeyen_odev_silinemez(sinif):
    with pytest.raises(odevler.OdevHatasi):
        odevler.sil(sinif["odev_id"])
    odevler.durum_degistir(sinif["odev_id"], "kapat")
    odevler.durum_degistir(sinif["odev_id"], "arsivle")
    odevler.sil(sinif["odev_id"])
    assert vt.tek("SELECT 1 FROM odev WHERE id=?", (sinif["odev_id"],)) is None


def test_ogrenci_yalniz_kendi_sinifinin_acik_odevlerini_gorur(sinif):
    diger = siniflar.sinif_bul_veya_olustur("D-" + vt.yeni_kimlik()[:6])
    gizli = odevler.olustur({"baslik": "Başka sınıf", "sinif_id": diger, "turler": ["belge"]})
    odevler.durum_degistir(gizli, "ac")
    taslak = odevler.olustur({"baslik": "Taslak", "sinif_id": sinif["sinif_id"],
                              "turler": ["belge"]})
    gorunen = {o["id"] for o in teslim.ogrenci_odevleri(sinif["a"])}
    assert sinif["odev_id"] in gorunen and gizli not in gorunen and taslak not in gorunen
    with pytest.raises(teslim.TeslimHatasi):
        teslim.baslat(sinif["a"], gizli, [{"yol": "a.pdf", "boyut": 5}], "")
    assert json.loads(vt.tek("SELECT turler FROM odev WHERE id=?", (gizli,))["turler"]) == ["belge"]
