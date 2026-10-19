"""Temizlik alan seçimi/istisna planı ve envanter düzenleme kuralları."""

import pytest

from uygulama import envanter, temizlik, veritabani


class TestTemizlikPlani:
    def test_bilinmeyen_alan_reddedilir(self):
        with pytest.raises(ValueError):
            temizlik.alanlari_dogrula(["masaustu", "/etc"])

    def test_alanlar_katalog_sirasina_girer(self):
        assert temizlik.alanlari_dogrula(["cop", "masaustu", "cop"]) == ["masaustu", "cop"]

    def test_istisna_yalnizca_o_bilgisayari_etkiler(self):
        plan = temizlik.plan_olustur(
            ["a", "b", "c"], ["masaustu", "indirilenler"], {"b": ["belgeler"]})
        assert plan == {"a": ["masaustu", "indirilenler"], "b": ["belgeler"],
                        "c": ["masaustu", "indirilenler"]}

    def test_bos_istisna_o_bilgisayarda_hicbir_sey_temizlemez(self):
        plan = temizlik.plan_olustur(["a", "b"], ["masaustu"], {"a": []})
        assert plan["a"] == [] and plan["b"] == ["masaustu"]

    def test_secili_olmayan_bilgisayara_istisna_reddedilir(self):
        with pytest.raises(ValueError):
            temizlik.plan_olustur(["a"], ["masaustu"], {"x": ["cop"]})

    def test_istisnada_bilinmeyen_alan_reddedilir(self):
        with pytest.raises(ValueError):
            temizlik.plan_olustur(["a"], ["masaustu"], {"a": ["kok_dizin"]})

    def test_genel_secim_hatirlanir(self):
        assert temizlik.genel_alanlar() == temizlik.VARSAYILAN_ALANLAR
        temizlik.genel_alanlari_kaydet(["tarayici", "masaustu"])
        assert temizlik.genel_alanlar() == ["masaustu", "tarayici"]
        temizlik.genel_alanlari_kaydet(temizlik.VARSAYILAN_ALANLAR)

    def test_uzak_betik_ayni_alanlari_tanir(self):
        from uygulama.uzak import temizlik as uzak_temizlik
        uzak_alanlar = set(uzak_temizlik.XDG_ALANLARI) | set(uzak_temizlik.SABIT_ALANLAR)
        assert uzak_alanlar == set(temizlik.ALANLAR)


class TestEnvanter:
    def test_elle_ekleme_ve_yineleme(self):
        cid = envanter.cihaz_ekle("10.20.0.5", 22, "LAB05", "Lab-2", "pardus")
        cihaz = veritabani.cihaz(cid)
        assert cihaz["etiket"] == "LAB05" and cihaz["grup"] == "Lab-2"
        assert cihaz["baglanti_hesabi"] == "pardus" and cihaz["parmak_izi_onay"] == 0
        assert veritabani.cihaz_adi(cihaz) == "LAB05"
        with pytest.raises(envanter.EnvanterHatasi):
            envanter.cihaz_ekle("10.20.0.5", 22)

    @pytest.mark.parametrize("ip", ["laboratuvar", "127.0.0.1", "0.0.0.0", "224.0.0.1"])
    def test_gecersiz_adres(self, ip):
        with pytest.raises(envanter.EnvanterHatasi):
            envanter.cihaz_ekle(ip)

    @pytest.mark.parametrize("hesap", ["root", "ogrenci", "Pardus", "a b", "x;rm -rf", "-a"])
    def test_gecersiz_hesap(self, hesap):
        with pytest.raises(envanter.EnvanterHatasi):
            envanter.hesap_dogrula(hesap)

    def test_hesap_degisince_anahtar_kurulumu_gerekir(self):
        cid = envanter.cihaz_ekle("10.20.0.6", 22, hesap="pardus")
        veritabani.cihaz_guncelle(cid, anahtar_durumu="ok", sudo_durumu="parolasiz",
                                  parmak_izi_onay=1, durum="Yönetilebilir")
        sonuc = envanter.cihaz_duzenle(cid, {"baglanti_hesabi": "hp"})
        cihaz = veritabani.cihaz(cid)
        assert sonuc["hesap_degisti"]
        assert cihaz["baglanti_hesabi"] == "hp"
        assert cihaz["anahtar_durumu"] == "gerekli" and cihaz["sudo_durumu"] is None
        assert cihaz["durum"] == "Hazırlık gerekli"

    def test_ayni_hesap_anahtari_bozmaz(self):
        cid = envanter.cihaz_ekle("10.20.0.7", 22, hesap="pardus")
        veritabani.cihaz_guncelle(cid, anahtar_durumu="ok")
        sonuc = envanter.cihaz_duzenle(cid, {"baglanti_hesabi": "pardus", "etiket": "Ö-7"})
        assert not sonuc["hesap_degisti"]
        assert veritabani.cihaz(cid)["anahtar_durumu"] == "ok"
        assert veritabani.cihaz(cid)["etiket"] == "Ö-7"

    def test_silme_deneme_butcesini_sifirlamaz(self):
        cid = envanter.cihaz_ekle("10.20.0.8", 22)
        veritabani.butce_dus("10.20.0.8", "pardus")
        kalan = veritabani.butce_al("10.20.0.8", "pardus")
        veritabani.cihaz_sil(cid)
        assert veritabani.cihaz(cid) is None
        envanter.cihaz_ekle("10.20.0.8", 22)
        assert veritabani.butce_al("10.20.0.8", "pardus") == kalan
