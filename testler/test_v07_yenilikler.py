"""0.7.0: Okul kimliği ve logosu, çoklu öğretmen & RBAC yetkileri,
sınıf hızlı araçları (ekran kilidi, duyuru, internet kısıtlama, masaüstüne dağıtım)
ve M2-S6 SSH Komut Gönder (/etc/hosts ve bash komut merkezi) testleri."""

import base64
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from uygulama import ana, envanter, guvenlik, komutlar, sinif_araclari, veritabani
from uygulama.uzak import sinif as uzak_sinif


def _hazir_cihaz(ip: str, etiket: str):
    cid = envanter.cihaz_ekle(ip, 22, etiket, "Bilişim-1", "pardus", False)
    veritabani.cihaz_guncelle(
        cid,
        parmak_izi="SHA256:test",
        parmak_izi_onay=1,
        anahtar_durumu="ok",
        sudo_durumu="parolasiz",
        profil_var=1,
        masaustu="GNOME",
        baglanti_hesabi="pardus",
    )
    return veritabani.cihaz(cid)


class TestOkulKimligiVeOgretmenRBAC:
    def setup_method(self):
        veritabani.calistir("DELETE FROM ogretmen")
        veritabani.calistir("DELETE FROM ayar WHERE anahtar LIKE 'okul_%' OR anahtar='giris_parolasi'")

    def test_okul_bilgisi_kaydet_ve_oku(self):
        varsayilan = veritabani.okul_bilgisi()
        assert varsayilan["ad"]
        yeni = veritabani.okul_kaydet(
            "Cumhuriyet Fen Lisesi",
            "Pardus Bilişim Laboratuvarı",
            "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=",
        )
        assert yeni["ad"] == "Cumhuriyet Fen Lisesi"
        assert yeni["alt_baslik"] == "Pardus Bilişim Laboratuvarı"
        assert yeni["logo_b64"].startswith("data:image/svg+xml;base64,")

    def test_eski_parola_gocu_admin_olusturur(self):
        ozet = guvenlik.bcrypt_ozet("deneme1234")
        veritabani.ayar_yaz("giris_parolasi", ozet)
        guvenlik.eski_parola_gocu()
        admin = veritabani.ogretmen_bul("admin")
        assert admin is not None
        assert admin["rol"] == "admin"
        dogrulanan = guvenlik.ogretmen_dogrula("admin", "deneme1234")
        assert dogrulanan is not None
        assert dogrulanan["kullanici_adi"] == "admin"

    def test_ogretmen_ekle_guncelle_sil_ve_son_admin_korumasi(self):
        admin_ozet = guvenlik.bcrypt_ozet("admin12345")
        admin = veritabani.ogretmen_ekle("admin", "Mukaddes ALAT", admin_ozet, rol="admin")
        std_ozet = guvenlik.bcrypt_ozet("ogretmen123")
        std = veritabani.ogretmen_ekle(
            "zeynep.demir",
            "Zeynep Demir",
            std_ozet,
            rol="standart",
            brans="Bilişim",
            yetkiler=["komut_gonder"],
        )
        assert std["rol"] == "standart"
        assert "komut_gonder" in std["yetkiler"]

        # Tek admin silinemez ve standart role düşürülemez
        with pytest.raises(ValueError, match="Son Admin"):
            veritabani.ogretmen_sil(admin["id"])
        with pytest.raises(ValueError, match="Son Admin"):
            veritabani.ogretmen_guncelle(admin["id"], rol="standart")

        # Standart öğretmen güncellenebilir ve silinebilir
        guncel = veritabani.ogretmen_guncelle(
            std["id"], ad_soyad="Zeynep Demir Yılmaz", yetkiler=["paket_gorunum", "komut_gonder"]
        )
        assert guncel["ad_soyad"] == "Zeynep Demir Yılmaz"
        assert set(guncel["yetkiler"]) == {"paket_gorunum", "komut_gonder"}
        assert veritabani.ogretmen_sil(std["id"]) is True

    def test_rbac_yol_yetki_kontrolu(self):
        admin = {
            "id": "1",
            "kullanici_adi": "admin",
            "ad_soyad": "Admin",
            "rol": "admin",
            "yetkiler": [],
        }
        std_temel = {
            "id": "2",
            "kullanici_adi": "std",
            "ad_soyad": "Standart",
            "rol": "standart",
            "yetkiler": [],
        }
        std_komut = {
            "id": "3",
            "kullanici_adi": "std2",
            "ad_soyad": "Komut Yetkili",
            "rol": "standart",
            "yetkiler": ["komut_gonder", "paket_gorunum"],
        }

        # Admin her yola erişir
        ana._yol_yetki_kontrol("/api/ayarlar", "POST", admin)
        ana._yol_yetki_kontrol("/api/komutlar/calistir", "POST", admin)
        ana._yol_yetki_kontrol("/api/ogretmenler", "POST", admin)

        # Standart öğretmen sınıf, temizlik, güç ve ödev yollarına erişir
        ana._yol_yetki_kontrol("/api/sinif/ekran-kilit", "POST", std_temel)
        ana._yol_yetki_kontrol("/api/temizlik/onizle", "POST", std_temel)
        ana._yol_yetki_kontrol("/api/guc", "POST", std_temel)
        ana._yol_yetki_kontrol("/api/odev/odevler", "GET", std_temel)

        # Standart öğretmen yüksek etkili sistem ayarlarına erişemez
        for yasak_yol in ["/api/hazirlik/baslat", "/api/veyon/uygula", "/api/ayarlar", "/api/ogretmenler"]:
            with pytest.raises(HTTPException) as exc:
                ana._yol_yetki_kontrol(yasak_yol, "POST", std_temel)
            assert exc.value.status_code == 403

        # İsteğe bağlı yetkiler: temel standart öğretmende kapalı, yetkili standart öğretmende açık
        with pytest.raises(HTTPException) as exc:
            ana._yol_yetki_kontrol("/api/komutlar/calistir", "POST", std_temel)
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as exc:
            ana._yol_yetki_kontrol("/api/paketler", "GET", std_temel)
        assert exc.value.status_code == 403

        ana._yol_yetki_kontrol("/api/komutlar/calistir", "POST", std_komut)
        ana._yol_yetki_kontrol("/api/paketler", "GET", std_komut)


class TestKomutGonderVeHosts:
    def test_yerlesik_komutlar_yuklu(self):
        liste = veritabani.kayitli_komutlar()
        idler = {k["id"] for k in liste}
        assert "k_hosts" in idler
        assert "k_userdel" in idler
        hosts_komut = veritabani.komut_getir("k_hosts")
        assert "192.168.23.142" in hosts_komut["komut"]
        assert "abc.local" in hosts_komut["komut"]
        userdel_komut = veritabani.komut_getir("k_userdel")
        assert "userdel -r abc" in userdel_komut["komut"]

    def test_tehlikeli_komut_engellenir(self):
        with pytest.raises(ValueError, match="Güvenlik"):
            komutlar.komut_dogrula("rm -rf /")
        with pytest.raises(ValueError, match="Güvenlik"):
            komutlar.komut_dogrula("mkfs.ext4 /dev/sda1")

    def test_hosts_dogrulama_ve_idempotent_yazim(self):
        ip, ad = komutlar.hosts_dogrula("192.168.23.142", "abc.local")
        assert ip == "192.168.23.142"
        assert ad == "abc.local"
        with pytest.raises(ValueError):
            komutlar.hosts_dogrula("999.999.1.1", "abc.local")

        with tempfile.TemporaryDirectory() as tmp:
            hosts_yolu = Path(tmp) / "hosts"
            hosts_yolu.write_text("127.0.0.1\tlocalhost\n192.168.1.10\teski.local\n", encoding="utf-8")
            with patch.object(uzak_sinif, "HOSTS_YOLU", hosts_yolu):
                sonuc1 = uzak_sinif.hosts_ekle("192.168.23.142", "abc.local")
                assert sonuc1["tamam"] is True
                icerik1 = hosts_yolu.read_text(encoding="utf-8")
                assert "192.168.23.142\tabc.local" in icerik1

                # Aynı alan adı farklı IP ile güncellenince çift kayıt oluşmaz
                sonuc2 = uzak_sinif.hosts_ekle("192.168.23.200", "abc.local")
                assert sonuc2["degisti"] is True
                icerik2 = hosts_yolu.read_text(encoding="utf-8")
                assert icerik2.count("abc.local") == 1
                assert "192.168.23.200\tabc.local" in icerik2

    def test_komut_isi_ozet_sayaclari(self):
        import asyncio

        c1 = _hazir_cihaz("192.168.10.101", "LAB01")
        c2 = _hazir_cihaz("192.168.10.102", "LAB02")
        c3 = _hazir_cihaz("192.168.10.103", "LAB03")
        is_id = veritabani.is_olustur(
            "ssh_komut",
            {"ad": "userdel abc", "komut": "userdel -r abc", "sudo": True},
            [c1["ip"], c2["ip"], c3["ip"]],
            ogretmen={"kullanici_adi": "admin", "ad_soyad": "Mukaddes ALAT", "rol": "admin"},
        )

        class SahteIstemci:
            def __init__(self, ip):
                self.ip = ip

            def close(self):
                pass

        def sahte_baglan(cihaz):
            if cihaz["ip"] == "192.168.10.103":
                raise RuntimeError("SSH zaman aşımı")
            return SahteIstemci(cihaz["ip"])

        def sahte_sudo_komut(istemci, argv, zaman=60):
            if istemci.ip == "192.168.10.101":
                return 0, "abc kullanicisi silindi", ""
            return 1, "", "userdel: user 'abc' does not exist"

        with patch("uygulama.komutlar.yonetim.baglan", side_effect=sahte_baglan), \
             patch("uygulama.komutlar.ssh_araclari.sudo_komut", side_effect=sahte_sudo_komut):
            asyncio.run(
                komutlar.komut_isi(is_id, [c1["id"], c2["id"], c3["id"]], "userdel -r abc", True, "userdel abc")
            )

        kayit = veritabani.is_durumu(is_id)
        assert kayit["durum"] == "tamamlandi"
        assert kayit["ogretmen_ad"] == "Mukaddes ALAT"
        assert "3 bilgisayara gönderildi" in kayit["ozet"]
        assert "1 bilgisayara ulaşılamadı" in kayit["ozet"]
        assert "1 başarılı" in kayit["ozet"]
        assert "1 hata alındı" in kayit["ozet"]


class TestSinifHizliAraclar:
    def test_masaustu_url_ve_dosya_dagitimi(self):
        with tempfile.TemporaryDirectory() as tmp:
            masaustu = Path(tmp) / "Masaüstü"
            sahte_kullanici = MagicMock(pw_name="ogrenci", pw_uid=1000, pw_gid=1000, pw_dir=tmp)
            with patch.object(uzak_sinif, "_masaustu_dizini", return_value=masaustu), \
                 patch.object(uzak_sinif, "_ogrenci_bilgi", return_value=sahte_kullanici), \
                 patch.object(uzak_sinif, "_kullanici_bildir"), \
                 patch.object(uzak_sinif, "_ogrenci_sahip_yap"):
                r_url = uzak_sinif.masaustu_url("Pardus Kılavuzu", "https://pardus.org.tr")
                assert r_url["tamam"] is True
                dosyalar = list(masaustu.glob("*.desktop"))
                assert len(dosyalar) == 1
                assert "https://pardus.org.tr" in dosyalar[0].read_text(encoding="utf-8")

                b64 = base64.b64encode("Merhaba Sınıf".encode("utf-8")).decode("ascii")
                r_dosya = uzak_sinif.masaustu_dosya("calisma_notu.txt", b64)
                assert r_dosya["tamam"] is True
                hedef = masaustu / "calisma_notu.txt"
                assert hedef.exists()
                assert hedef.read_text(encoding="utf-8") == "Merhaba Sınıf"
