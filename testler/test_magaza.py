"""Komut Mağazası ve Araç Çalıştırma Testleri."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from uygulama import ana, komutlar, veritabani


class TestMagazaBirim:
    def test_katalog_listesi(self):
        katalog = komutlar.resmi_magaza_katalogu()
        assert len(katalog) >= 6
        idler = {a["id"] for a in katalog}
        assert "veyon-servis-ac" in idler
        assert "hosts-kayit-ekle" in idler
        assert "kullanici-ev-dizini-sil" in idler
        assert "disk-bellek-raporu" in idler

    def test_arac_getir(self):
        arac = komutlar.magaza_araci_getir("veyon-servis-ac")
        assert arac is not None
        assert arac["kategori"] == "veyon"
        assert arac["sudo"] is True
        assert komutlar.magaza_araci_getir("olmayan-arac") is None

    def test_parametre_dogrulama_ve_yasaklar(self):
        arac = komutlar.magaza_araci_getir("kullanici-ev-dizini-sil")
        assert arac is not None

        # Geçerli parametre
        temiz = komutlar.arac_parametrelerini_dogrula(arac, {"kullanici": "deneme1"})
        assert temiz["kullanici"] == "deneme1"

        # Korumalı sistem hesabı engellenmeli
        with pytest.raises(komutlar.KomutHatasi, match="korumalı bir değerdir"):
            komutlar.arac_parametrelerini_dogrula(arac, {"kullanici": "root"})

        with pytest.raises(komutlar.KomutHatasi, match="korumalı bir değerdir"):
            komutlar.arac_parametrelerini_dogrula(arac, {"kullanici": "ogrenci"})

        # Özel karakter enjeksiyonu engellenmeli
        with pytest.raises(komutlar.KomutHatasi, match="geçersiz özel karakterler"):
            komutlar.arac_parametrelerini_dogrula(arac, {"kullanici": "ali; rm -rf /"})

    def test_komut_uretimi_guvenli_ortam_degiskenleri(self):
        arac = komutlar.magaza_araci_getir("hosts-kayit-ekle")
        uretilen = komutlar.arac_komutu_uret(arac, {"ip": "192.168.1.50", "alan_adi": "portal.yerel"})
        assert "PSY_ARAC_ID=" in uretilen and "hosts-kayit-ekle" in uretilen
        assert "PSY_P_ip=" in uretilen and "192.168.1.50" in uretilen
        assert "PSY_P_alan_adi=" in uretilen and "portal.yerel" in uretilen
        assert "sed" in uretilen

    def test_sabit_araclar_ayari(self):
        varsayilan = komutlar.sabit_araclari_al()
        assert isinstance(varsayilan, list)
        assert "veyon-servis-ac" in varsayilan

        guncel = komutlar.sabit_arac_kaydet(["veyon-servis-ac", "hosts-kayit-ekle"])
        assert komutlar.sabit_araclari_al() == ["veyon-servis-ac", "hosts-kayit-ekle"]


class TestMagazaUclari:
    def test_magaza_katalog_ve_sabitler_api(self):
        kat = asyncio.run(ana.magaza_katalog_uc())
        assert len(kat) >= 6

        sab = asyncio.run(ana.magaza_sabitler_uc())
        assert isinstance(sab, list)

        # Sabitleme ekle ve çıkar
        r_ekle = asyncio.run(ana.magaza_sabitle_uc(ana.AracSabitleIstek(arac_id="bozuk-paket-onar", sabitle=True)))
        assert "bozuk-paket-onar" in r_ekle["sabitler"]

        r_cikar = asyncio.run(ana.magaza_sabitle_uc(ana.AracSabitleIstek(arac_id="bozuk-paket-onar", sabitle=False)))
        assert "bozuk-paket-onar" not in r_cikar["sabitler"]

    def test_magaza_calistir_dogrulama(self):
        # Olmayan araç için 404
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            asyncio.run(ana.magaza_arac_calistir_uc(ana.AracCalistirIstek(cihazlar=["c1"], arac_id="yok-arac", parametreler={})))
        assert exc.value.status_code == 404

        # Korumalı kullanıcı silinmek istendiğinde 422
        with pytest.raises(HTTPException) as exc:
            asyncio.run(ana.magaza_arac_calistir_uc(ana.AracCalistirIstek(cihazlar=["c1"], arac_id="kullanici-ev-dizini-sil", parametreler={"kullanici": "root"})))
        assert exc.value.status_code == 422
