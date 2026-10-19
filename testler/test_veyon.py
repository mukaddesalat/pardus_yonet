"""0.5.0: M1-S4 Veyon — paket ve public key doğrulama, sürüm karşılaştırma, envanter
sütunu, kaldırma izni ve öğretmen PC denetimi."""

import asyncio
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from uygulama import ana, debpaket, paketler, secim, surum, veritabani, veyon
from uygulama.uzak import paket as uzak_paket
from uygulama.uzak import veyon as uzak_veyon

from test_v04 import HAZIR, _cihaz, _deb  # noqa: E402  (testler/ dizini sys.path'te)


@pytest.fixture(scope="module")
def rsa_anahtar():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(anahtar, bicim=serialization.PublicFormat.SubjectPublicKeyInfo) -> bytes:
    return anahtar.public_key().public_bytes(serialization.Encoding.PEM, bicim)


# ---------------------------------------------------------------- sürüm karşılaştırma

@pytest.mark.parametrize("a,b,beklenen", [
    ("4.7.5+repack1-1", "4.11.0.0-debian.12", -1),   # lab: parçalı Debian paketi < resmî paket
    ("4.11.0.0-debian.12", "4.10.4.0-debian.12", 1),
    ("4.11.0.0-debian.12", "4.11.0.0-debian.12", 0),
    ("1.0~rc1", "1.0", -1), ("1.0", "1.0-0", 0), ("2.0a", "2.0", 1), ("1.0+b1", "1.0", 1),
    ("1:0.1", "2.0", 1), ("1.0-1", "1.0-1.1", -1), ("1.0~", "1.0", -1), ("10", "9", 1),
])
def test_dpkg_surum_karsilastirma(a, b, beklenen):
    assert surum.karsilastir(a, b) == beklenen
    assert surum.karsilastir(b, a) == -beklenen


def test_iliski():
    assert surum.iliski(None, "4.11") == "kurulu_degil"
    assert surum.iliski("4.7.5+repack1-1", "4.11.0.0-debian.12") == "eski"
    assert surum.iliski("4.11.0.0-debian.12", "4.11.0.0-debian.12") == "ayni"
    assert surum.iliski("4.12.0.0-debian.12", "4.11.0.0-debian.12") == "yeni"


# ---------------------------------------------------------------- public key

class TestAnahtar:
    def test_rsa_public_key_kabul(self, rsa_anahtar):
        b = veyon.anahtar_incele(_pem(rsa_anahtar))
        der = rsa_anahtar.public_key().public_bytes(serialization.Encoding.DER,
                                                    serialization.PublicFormat.SubjectPublicKeyInfo)
        assert b["bit"] == 2048 and len(b["parmak_izi"]) == 64
        assert b["cift_kimligi"] == veyon.qt_ozet(der)
        assert b["pem"].startswith("-----BEGIN PUBLIC KEY-----")
        # PKCS#1 ("BEGIN RSA PUBLIC KEY") aynı anahtara normalize edilir
        pkcs1 = veyon.anahtar_incele(_pem(rsa_anahtar, serialization.PublicFormat.PKCS1))
        assert pkcs1["parmak_izi"] == b["parmak_izi"]

    def test_veyon_cift_kimligi_algoritmasi(self):
        # Qt5 qHash(QByteArray): h = 31*h + bayt (lab'da `veyon-cli authkeys list details` ile doğrulandı)
        assert veyon.qt_ozet(b"") == "00000000"
        assert veyon.qt_ozet(b"ab") == "%08x" % (31 * 97 + 98)
        assert veyon.qt_ozet(b"\xff" * 64) == uzak_veyon.qt_ozet(b"\xff" * 64)

    def test_private_key_reddedilir_ve_saklanmaz(self, rsa_anahtar):
        ozel = rsa_anahtar.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption())
        with pytest.raises(veyon.VeyonHatasi, match="PRIVATE"):
            veyon.anahtar_kaydet("teacher", "teacher_private_key.pem", ozel)
        dizin = veyon._dizin()
        for yol in dizin.rglob("*"):
            if yol.is_file():
                assert b"PRIVATE" not in yol.read_bytes()

    @pytest.mark.parametrize("icerik,parca", [
        (b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample kullanici@pc", "SSH"),
        (b"merhaba dunya", "Geçerli bir Veyon public key değil"),
        ((b"-----BEGIN " + b"OPENSSH PRIVATE " + b"KEY-----\nabc\n-----END " + b"OPENSSH PRIVATE " + b"KEY-----\n"), "PRIVATE"),
    ])
    def test_gecersiz_dosyalar(self, icerik, parca):
        with pytest.raises(veyon.VeyonHatasi, match=parca):
            veyon.anahtar_incele(icerik)

    def test_rsa_olmayan_anahtar(self):
        ed = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        with pytest.raises(veyon.VeyonHatasi, match="RSA"):
            veyon.anahtar_incele(ed)

    def test_ad_kurali(self, rsa_anahtar):
        for ad in ("", "1abc", "öğretmen", "a b", "a-b"):
            with pytest.raises(veyon.VeyonHatasi, match="Anahtar adı"):
                veyon.anahtar_kaydet(ad, "x.pem", _pem(rsa_anahtar))

    def test_ayni_adli_farkli_anahtar_onay_ve_yedek(self, rsa_anahtar):
        veyon.anahtar_sil()
        ilk = veyon.anahtar_kaydet("teacher", "teacher_public_key.pem", _pem(rsa_anahtar))
        # aynı anahtarı yeniden yüklemek onay istemez
        assert veyon.anahtar_kaydet("teacher", "kopya.pem", _pem(rsa_anahtar))["parmak_izi"] == ilk["parmak_izi"]
        yeni = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with pytest.raises(veyon.OnayGerekli):
            veyon.anahtar_kaydet("teacher", "yeni.pem", _pem(yeni))
        assert veyon.anahtar_bilgisi()["parmak_izi"] == ilk["parmak_izi"]   # onaysız değişmedi
        kayit = veyon.anahtar_kaydet("teacher", "yeni.pem", _pem(yeni), onay=True)
        assert kayit["onceki"]["cift_kimligi"] == ilk["cift_kimligi"]
        yedekler = list((veyon._dizin() / "yedek").glob("teacher-*.pem"))
        assert yedekler and yedekler[0].read_text(encoding="ascii").startswith("-----BEGIN PUBLIC KEY-----")


# ---------------------------------------------------------------- paket doğrulama ve ayrı listeler

VEYON_CONTROL = ("Package: veyon\nVersion: 4.11.0.0-debian.12\nArchitecture: amd64\nInstalled-Size: 9151\n"
                 "Provides: veyon-configurator, veyon-master, veyon-plugins, veyon-service\n"
                 "Conflicts: veyon-configurator, veyon-master, veyon-plugins, veyon-service\n"
                 "Description: Cross-platform computer control and classroom management\n")


async def _akis(veri: bytes):
    yield veri


def _yukle(veri: bytes, ad: str, tur: str):
    return asyncio.run(paketler.yukle(_akis(veri), ad, tur))


class TestVeyonPaketi:
    def test_metadata_ile_dogrulama(self):
        p = _yukle(_deb(VEYON_CONTROL), "veyon_4.11.0.0-debian.12_amd64.deb", "veyon")
        assert (p["paket"], p["surum"], p["tur"]) == ("veyon", "4.11.0.0-debian.12", "veyon")
        assert p["sha256"] in {x["sha256"] for x in paketler.paketler("veyon")}
        assert p["sha256"] not in {x["sha256"] for x in paketler.paketler("genel")}

    def test_dosya_adi_yetmez(self):
        baska = VEYON_CONTROL.replace("Package: veyon", "Package: firefox-esr").replace("Provides: ", "X-Yok: ")
        with pytest.raises(debpaket.PaketHatasi, match="Veyon paketi değil"):
            _yukle(_deb(baska), "veyon_4.11_amd64.deb", "veyon")

    def test_parcali_paket_tek_basina_reddedilir(self):
        parca = VEYON_CONTROL.replace("Package: veyon", "Package: veyon-service")
        with pytest.raises(debpaket.PaketHatasi, match="parçalı"):
            _yukle(_deb(parca), "veyon-service_4.7.5_amd64.deb", "veyon")

    def test_genel_sayfa_veyon_kabul_etmez(self):
        with pytest.raises(debpaket.PaketHatasi, match="M1-S4"):
            _yukle(_deb(VEYON_CONTROL), "veyon_4.11.0.0-debian.12_amd64.deb", "genel")

    def test_secim_ve_silme(self):
        p = _yukle(_deb(VEYON_CONTROL), "veyon_4.11.0.0-debian.12_amd64.deb", "veyon")
        veyon.paket_sec(p["sha256"])
        assert veyon.secili_paket()["sha256"] == p["sha256"]
        paketler.paket_sil(p["sha256"])
        assert veyon.secili_paket() is None


# ---------------------------------------------------------------- uzak betik: kurulum durumu ve kaldırma izni

class TestUzakVeyon:
    @pytest.mark.parametrize("pk,durum,paket", [
        ({"veyon": {"durum": "ii", "surum": "4.11.0.0-debian.12"}}, "kurulu", "veyon"),
        ({"veyon-service": {"durum": "ii", "surum": "4.7.5+repack1-1"},
          "libveyon-core": {"durum": "ii", "surum": "4.7.5+repack1-1"}}, "kurulu", "veyon-service"),
        ({"veyon": {"durum": "iU", "surum": "4.11.0.0-debian.12"}}, "hatali", "veyon"),
        ({"libveyon-core": {"durum": "ii", "surum": "4.7.5+repack1-1"}}, "hatali", "libveyon-core"),
        ({"veyon-service": {"durum": "rc", "surum": "4.7.5+repack1-1"}}, "kurulu_degil", None),
        ({}, "kurulu_degil", None),
        (None, "okunamadi", None),
    ])
    def test_surum_bilgisi(self, pk, durum, paket):
        s = uzak_veyon.surum_bilgisi(pk)
        assert (s["durum"], s["paket"]) == (durum, paket)
        if durum == "kurulu":
            assert s["surum"] == pk[paket]["surum"]   # TAM sürüm, dağıtım revizyonuyla

    def test_pem_ozet_ogretmen_tarafiyla_ayni(self, rsa_anahtar):
        b = veyon.anahtar_incele(_pem(rsa_anahtar))
        u = uzak_veyon.pem_ozet(b["pem"])
        assert (u["parmak_izi"], u["cift_kimligi"]) == (b["parmak_izi"], b["cift_kimligi"])

    def _plan(self, monkeypatch, kaldirma_izni, kaldirilacak):
        monkeypatch.setattr(uzak_paket, "os_release", lambda: {"ID": "pardus", "PRETTY_NAME": "Pardus 23"})
        monkeypatch.setattr(uzak_paket, "calistir", lambda argv, zaman=120: (0, "amd64\n" if "--print-architecture" in argv else "", ""))
        kurulu = {"veyon-service": "4.7.5+repack1-1"}
        monkeypatch.setattr(uzak_paket, "kurulu_surum", lambda ad: kurulu.get(ad))
        monkeypatch.setattr(uzak_paket, "surum_karsilastir",
                            lambda a, islec, b: {"eq": 0, "gt": 1, "lt": -1}[islec] == surum.karsilastir(a, b))
        monkeypatch.setattr(uzak_paket, "bos_alan", lambda yol: 10 ** 12)
        monkeypatch.setattr(uzak_paket, "kilit_durumu", lambda: None)
        monkeypatch.setattr(uzak_paket.os.path, "isfile", lambda yol: True)
        monkeypatch.setattr(uzak_paket, "apt_benzetim", lambda yol: {
            "yeni": [{"paket": "veyon", "surum": "4.11.0.0-debian.12"}], "guncellenecek": [],
            "kaldirilacak": kaldirilacak, "dusurulecek": [], "rc": 0, "hata": None})
        monkeypatch.setattr(uzak_paket, "indirilecekler", lambda yol: [])
        p = {"kip": "plan", "sha256": "a" * 64, "paket": "veyon", "surum": "4.11.0.0-debian.12", "mimari": "amd64",
             "kurulu_kb": 9151, "boyut": 2004828, "esdeger_paketler": ["veyon-service"]}
        if kaldirma_izni is not None:
            p["kaldirma_izni"] = kaldirma_izni
        return uzak_paket.plan(p)

    PARCALI = ["veyon-configurator", "veyon-master", "veyon-service", "libveyon-core", "veyon-plugins"]

    def test_parcali_paketlerin_yerine_gecme_izni(self, monkeypatch):
        s = self._plan(monkeypatch, list(veyon.PAKET_AILESI), self.PARCALI)
        assert s["durum"] == "guncellenecek", s["engeller"]
        assert (s["kurulu_paket"], s["kurulu_surum"]) == ("veyon-service", "4.7.5+repack1-1")
        assert s["yerine_gececek"] == self.PARCALI

    def test_izinsiz_kaldirma_engellenir(self, monkeypatch):
        s = self._plan(monkeypatch, None, self.PARCALI)
        assert s["durum"] == "engellendi" and "KALDIRACAK" in s["engeller"][0]
        s = self._plan(monkeypatch, list(veyon.PAKET_AILESI), self.PARCALI + ["nano"])
        assert s["durum"] == "engellendi" and "nano" in s["engeller"][0] and "veyon-service" not in s["engeller"][0]

    def test_yalniz_dusurme_atlanir(self):
        assert veyon._yalniz_dusurme({"durum": "engellendi", "engeller": [
            "sürüm düşürme: kurulu 4.12, paket 4.11 — izin verilmez"]})
        assert not veyon._yalniz_dusurme({"durum": "engellendi", "engeller": [
            "sürüm düşürme: kurulu 4.12, paket 4.11 — izin verilmez", "yetersiz boş alan"]})


# ---------------------------------------------------------------- envanter sütunu ve uygunluk

class TestVeyonEnvanter:
    def test_gosterim_durumlari(self):
        c = _cihaz("10.40.0.1", **HAZIR)
        assert secim.veyon_gorunumu(c, "4.11")["durum"] == "kontrol_edilmedi"
        veritabani.cihaz_guncelle(c["id"], veyon_durumu="kurulu", veyon_surum="4.7.5+repack1-1",
                                  veyon_kontrol="2026-10-01T10:00:00+00:00")
        c = veritabani.cihaz(c["id"])
        g = secim.veyon_gorunumu(c, "4.11.0.0-debian.12")
        assert (g["durum"], g["surum"], g["karsilastirma"]) == ("kurulu", "4.7.5+repack1-1", "eski")
        assert secim.veyon_gorunumu(c, None)["karsilastirma"] == "kurulu"

    def test_erisilemeyen_kurulu_degil_gosterilmez(self):
        c = _cihaz("10.40.0.2", **HAZIR)
        veritabani.cihaz_guncelle(c["id"], veyon_durumu="kurulu", veyon_surum="4.11.0.0-debian.12",
                                  veyon_kontrol="2026-10-01T10:00:00+00:00", erisim=0,
                                  erisim_zamani="2026-10-02T09:00:00+00:00")
        g = secim.veyon_gorunumu(veritabani.cihaz(c["id"]), "4.11.0.0-debian.12")
        assert g["durum"] == "erisilemiyor" and g["eski_bilgi"] and g["surum"] == "4.11.0.0-debian.12"
        assert g["karsilastirma"] == "bilinmiyor"

    def test_envanter_alanlari_m1s1_ve_m1s4_ortak(self):
        v = {"durum": "kurulu", "surum": "4.11.0.0-debian.12", "paket": "veyon",
             "servis": {"etkin": True, "calisiyor": True}, "yontem": 1, "anahtarlar": {}}
        a = veyon.envanter_alanlari(v)
        assert a["veyon_surum"] == "4.11.0.0-debian.12" and a["veyon_durumu"] == "kurulu"
        c = _cihaz("10.40.0.3", **HAZIR)
        veritabani.cihaz_guncelle(c["id"], **a)
        c = veritabani.cihaz(c["id"])
        assert c["veyon_yapilandirma"]["servis"]["calisiyor"] is True   # JSON geri okunur
        assert secim.gorunum(c, "4.11.0.0-debian.12")["veyon"]["karsilastirma"] == "ayni"

    def test_uygunluk(self):
        c = _cihaz("10.40.0.4", **{**HAZIR, "sudo_durumu": "parola_gerekli"})
        assert secim.uygunluk(c, "veyon_oku") is None           # sürüm okuma parolasız sudo istemez
        assert "Parolasız sudo" in secim.uygunluk(c, "veyon")    # kurulum/yapılandırma ister
        k = _cihaz("10.40.0.5", korunan=True, **HAZIR)
        assert "Korunan" in secim.uygunluk(k, "veyon_oku")


def test_ogretmen_hazirligi_private_key_okunmaz(tmp_path, monkeypatch, rsa_anahtar):
    veyon.anahtar_sil()
    veyon.anahtar_kaydet("teacher", "teacher_public_key.pem", _pem(rsa_anahtar))
    kok = tmp_path / "keys"
    (kok / "public" / "teacher").mkdir(parents=True)
    (kok / "public" / "teacher" / "key").write_bytes(_pem(rsa_anahtar))
    monkeypatch.setattr(veyon, "OGRETMEN_ANAHTAR_KOK", str(kok))
    monkeypatch.setattr(veyon, "OGRETMEN_KONF", str(tmp_path / "yok.conf"))
    monkeypatch.setattr(veyon, "_dpkg_surum", lambda paket: "4.11.0.0-debian.12" if paket == "veyon" else None)
    h = veyon.ogretmen_hazirligi()
    assert h["eslesen"] == "teacher"
    assert h["ozel_anahtar"]["var"] is False and any("private key yok" in s for s in h["sorunlar"])
    assert any("Authentication/Method 1" in k for k in h["komutlar"])
    # private key dosyası açılmaz: içerik okunamaz olsa da yalnız stat yapılır
    (kok / "private" / "teacher").mkdir(parents=True)
    ozel = kok / "private" / "teacher" / "key"
    ozel.write_bytes(b"GIZLI")
    acilan = []
    gercek_open = open

    def izle(yol, *a, **k):
        acilan.append(str(yol))
        return gercek_open(yol, *a, **k)
    monkeypatch.setattr("builtins.open", izle)
    h = veyon.ogretmen_hazirligi()
    assert h["ozel_anahtar"]["var"] is True
    assert not any("private" in y for y in acilan)


def test_veyon_api_uclari_kayitli():
    yollar = {getattr(r, "path", None) for r in ana.uygulama.routes}
    for yol in ("/api/veyon", "/api/veyon/paket-sec", "/api/veyon/hazirlik", "/api/veyon/anahtar",
                "/api/veyon/surumler", "/api/veyon/plan", "/api/veyon/uygula", "/api/veyon/dogrula",
                "/api/veyon/geri-al"):
        assert yol in yollar, yol
    assert os.path.basename(veyon.OGRETMEN_ANAHTAR_KOK) == "keys"
