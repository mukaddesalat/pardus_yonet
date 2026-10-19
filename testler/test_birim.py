"""Birim testleri: aralık genişletme, güvenlik ve deneme bütçesi."""

import pytest

from uygulama import ayarlar, guvenlik, veritabani
from uygulama.kesif import aralik_genislet


class TestAralikGenislet:
    def test_tek_ip(self):
        assert aralik_genislet("192.168.10.137", []) == ["192.168.10.137"]

    def test_kisa_aralik(self):
        sonuc = aralik_genislet("192.168.10.10-12", [])
        assert sonuc == ["192.168.10.10", "192.168.10.11", "192.168.10.12"]

    def test_tam_aralik(self):
        sonuc = aralik_genislet("192.168.10.10-192.168.10.11", [])
        assert sonuc == ["192.168.10.10", "192.168.10.11"]

    def test_cidr(self):
        sonuc = aralik_genislet("192.168.10.0/29", [])
        assert len(sonuc) == 6  # ağ ve yayın adresleri hariç

    def test_haric_tutma(self):
        sonuc = aralik_genislet("192.168.10.10-12", ["192.168.10.11"])
        assert "192.168.10.11" not in sonuc and len(sonuc) == 2

    def test_genis_kapsam_reddedilir(self):
        with pytest.raises(ValueError):
            aralik_genislet("10.0.0.0/16", [])

    def test_ters_aralik_reddedilir(self):
        with pytest.raises(ValueError):
            aralik_genislet("192.168.10.20-10", [])

    def test_gecersiz_girdi(self):
        with pytest.raises(ValueError):
            aralik_genislet("laboratuvar", [])

    def test_virgullu_liste(self):
        sonuc = aralik_genislet("192.168.10.1, 192.168.10.2", [])
        assert sonuc == ["192.168.10.1", "192.168.10.2"]


class TestGuvenlik:
    def test_parola_karmasi_dogrulanir(self):
        kayit = guvenlik.parola_karmasi("Deneme-Parola-2026")
        assert guvenlik.parola_dogru_mu("Deneme-Parola-2026", kayit)
        assert not guvenlik.parola_dogru_mu("yanlis", kayit)

    def test_bozuk_kayit_reddedilir(self):
        assert not guvenlik.parola_dogru_mu("x", "bozuk-kayit")

    def test_oturum_cerezi(self):
        cerez = guvenlik.oturum_ac()
        assert guvenlik.oturum_gecerli_mi(cerez)
        assert not guvenlik.oturum_gecerli_mi(cerez + "x")
        assert not guvenlik.oturum_gecerli_mi(None)

    def test_csrf(self):
        cerez = guvenlik.oturum_ac()
        belirtec = guvenlik.csrf_uret(cerez)
        assert guvenlik.csrf_dogru_mu(cerez, belirtec)
        assert not guvenlik.csrf_dogru_mu(cerez, "sahte")
        assert not guvenlik.csrf_dogru_mu(cerez, None)


class TestDenemeButcesi:
    def test_butce_azalir_ve_sifirlanmaz(self):
        ip, hesap = "10.9.9.9", "pardus"
        ilk = veritabani.butce_al(ip, hesap)
        assert ilk == ayarlar.DENEME_BUTCESI
        veritabani.butce_dus(ip, hesap)
        veritabani.butce_dus(ip, hesap)
        assert veritabani.butce_al(ip, hesap) == ilk - 2
        # yeniden "tarama" bütçeyi sıfırlamaz; yalnızca başarı sıfırlar
        assert veritabani.butce_al(ip, hesap) == ilk - 2
        veritabani.butce_sifirla(ip, hesap)
        assert veritabani.butce_al(ip, hesap) == ayarlar.DENEME_BUTCESI

    def test_butce_eksiye_dusmez(self):
        ip, hesap = "10.9.9.8", "hp"
        for _ in range(10):
            veritabani.butce_dus(ip, hesap)
        assert veritabani.butce_al(ip, hesap) == 0
