"""0.4.0: tek envanter, hazırlık, tekilleştirme, toplu seçim, .deb dağıtımı, görünüm,
M/S/B referans kodları ve DESIGN.md belirteçleri."""

import asyncio
import io
import os
import re
import sys
import tarfile
from pathlib import Path

import pytest

from uygulama import ag, ana, debpaket, envanter, secim, veritabani
from uygulama.uzak import gorunum as uzak_gorunum
from uygulama.uzak import hazirlik as uzak_hazirlik
from uygulama.uzak import paket as uzak_paket

KOK = Path(__file__).resolve().parent.parent
ARAYUZ = KOK / "uygulama" / "arayuz"
sys.path.insert(0, str(KOK / "araclar"))
import belirtec_css  # noqa: E402


def _cihaz(ip, **alanlar):
    cid = envanter.cihaz_ekle(ip, 22, alanlar.pop("etiket", None), alanlar.pop("grup", None),
                              alanlar.pop("hesap", None), alanlar.pop("korunan", False))
    if alanlar:
        veritabani.cihaz_guncelle(cid, **alanlar)
    return veritabani.cihaz(cid)


HAZIR = dict(parmak_izi="SHA256:x", parmak_izi_onay=1, anahtar_durumu="ok",
             sudo_durumu="parolasiz", profil_var=1, masaustu="GNOME", baglanti_hesabi="pardus")


# ---------------------------------------------------------------- referans kodları

def _kayit_defteri():
    metin = (ARAYUZ / "referans.js").read_text(encoding="utf-8")
    dugmeler_bolumu = metin[metin.index("dugmeler: {"):metin.index("emekli:")]
    dugmeler = re.findall(r'^\s*"(M\d+-S\d+-B\d+(?:-\*)?)"\s*:', dugmeler_bolumu, re.M)
    emekli_bolumu = metin[metin.index("emekli:"):]
    emekli = re.findall(r'"(M\d+-S\d+-B\d+(?:-\*)?)"', emekli_bolumu)
    return dugmeler, set(emekli), metin


def _kullanilan_kodlar():
    """HTML ve JS'teki data-ui-id değerleri; `${...}` satır kimlikleri '*' olur."""
    kodlar = set()
    for dosya in [ARAYUZ / "index.html", *ARAYUZ.glob("*.js")]:
        metin = dosya.read_text(encoding="utf-8")
        for es in re.finditer(r'data-ui-id="(M\d+-S\d+(?:-B\d+)?)"', metin):
            kodlar.add(es.group(1))
        for es in re.finditer(r'[`"\'](M\d+-S\d+-B\d+)(-\$\{[^`]*)?[`"\']', metin):
            kodlar.add(es.group(1) + ("-*" if es.group(2) else ""))
    return kodlar


class TestReferansKodlari:
    def test_kodlar_benzersiz_ve_emekliyle_cakismaz(self):
        dugmeler, emekli, _ = _kayit_defteri()
        assert len(dugmeler) == len(set(dugmeler)), "aynı kod iki kez tanımlı"
        assert not (set(dugmeler) & emekli), "emekli kod yeniden kullanılmış"

    def test_arayuzdeki_her_kod_kayitli(self):
        dugmeler, emekli, _ = _kayit_defteri()
        kayitli = set(dugmeler)
        kullanilan = {k for k in _kullanilan_kodlar() if "-B" in k}
        eksik = kullanilan - kayitli
        assert not eksik, f"kayıt defterinde olmayan kodlar: {sorted(eksik)}"
        assert not (kullanilan & emekli)

    def test_her_kayitli_dugme_arayuzde_kullaniliyor(self):
        dugmeler, _, _ = _kayit_defteri()
        kullanilan = _kullanilan_kodlar()
        kullanilmayan = [k for k in dugmeler if k not in kullanilan]
        assert not kullanilmayan, f"kullanılmayan (emekliye alınmalı?) kodlar: {kullanilmayan}"

    def test_sayfalar_ve_menuler_tutarli(self):
        _, _, metin = _kayit_defteri()
        html = (ARAYUZ / "index.html").read_text(encoding="utf-8")
        sayfalar_html = set(re.findall(r'id="sayfa-(M\d+-S\d+)"', html))
        # kayıt defterindeki menü/sayfa listesi (M0 ortak araçlar hariç)
        kayit = set()
        for menu in re.finditer(r'\{ kod: "(M[1-9])".*?sayfalar: \[(.*?)\] \}', metin, re.S):
            for sayfa in re.findall(r'kod: "(S\d+)"', menu.group(2)):
                kayit.add(f"{menu.group(1)}-{sayfa}")
        assert sayfalar_html == kayit
        assert {"M1-S1", "M1-S2", "M2-S1", "M2-S2", "M2-S3", "M3-S1", "M4-S1", "M5-S1"} <= kayit
        for kod in sayfalar_html:
            m, s = kod.split("-")
            assert f'<span class="kod-cip">{m} · {s}</span>' in html, f"{kod} başlığında kod yok"

    def test_ornek_satir_kodu_bicimi(self):
        dugmeler, _, _ = _kayit_defteri()
        assert "M2-S1-B4-*" in dugmeler   # istemdeki örnek: M2-S1-B4-LAB01

    def test_onizleme_ayni_kayit_defterini_kullanir(self):
        onizleme = KOK / "arayuz-onizleme.html"
        if not onizleme.exists():
            pytest.skip("önizleme henüz üretilmedi")
        _, _, metin = _kayit_defteri()
        assert metin.strip() in onizleme.read_text(encoding="utf-8")

    def test_javascript_sozdizimi_gecerli(self):
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            pytest.skip("node kurulu değil")
        for js_dosya in sorted(ARAYUZ.glob("*.js")):
            sonuc = subprocess.run([node, "--check", str(js_dosya)], capture_output=True, text=True)
            assert sonuc.returncode == 0, f"{js_dosya.name} sözdizimi hatası: {sonuc.stderr}"



# ---------------------------------------------------------------- DESIGN.md

class TestTasarimBelirtecleri:
    def test_css_guncel(self):
        uretilen = belirtec_css.css_uret(belirtec_css.belirtecler())
        assert (ARAYUZ / "belirtecler.css").read_text(encoding="utf-8") == uretilen

    @pytest.mark.parametrize("on,arka", [
        ("on-surface", "surface"), ("on-surface", "neutral"), ("secondary", "surface"),
        ("on-primary", "primary"), ("success", "success-bg"), ("warning", "warning-bg"),
        ("error", "error-bg"), ("ref", "ref-bg"), ("demo", "demo-bg"), ("on-sidebar", "sidebar"),
    ])
    def test_wcag_aa_kontrast(self, on, arka):
        renk = belirtec_css.belirtecler()["colors"]
        assert belirtec_css.kontrast(renk[on], renk[arka]) >= 4.5

    def test_bolum_sirasi(self):
        metin = (KOK / "DESIGN.md").read_text(encoding="utf-8")
        basliklar = re.findall(r"^## (.+)$", metin, re.M)
        sira = ["Overview", "Colors", "Typography", "Layout", "Elevation & Depth", "Shapes",
                "Components", "Do's and Don'ts"]
        assert [b for b in basliklar if b in sira] == sira


# ---------------------------------------------------------------- uygunluk ve seçim

class TestUygunluk:
    def test_korunan_hic_bir_isleme_girmez(self):
        c = _cihaz("10.30.0.1", korunan=True, **HAZIR)
        for islem in ("durum", "hazirlik", "temizlik", "paket", "gorunum", "guc", "oturum"):
            assert "Korunan" in secim.uygunluk(c, islem)
        assert secim.uygunluk(c, "cikar") is None  # listeden çıkarılabilir

    def test_hazirlik_kimlik_onayi_ister(self):
        c = _cihaz("10.30.0.2")
        assert "okunmadı" in secim.uygunluk(c, "hazirlik")
        veritabani.cihaz_guncelle(c["id"], parmak_izi="SHA256:a")
        assert "onaylanmadı" in secim.uygunluk(veritabani.cihaz(c["id"]), "hazirlik")
        veritabani.cihaz_guncelle(c["id"], parmak_izi_onay=1)
        assert secim.uygunluk(veritabani.cihaz(c["id"]), "hazirlik") is None

    def test_parolasiz_sudo_olmadan_islem_yok(self):
        c = _cihaz("10.30.0.3", **{**HAZIR, "sudo_durumu": "parola_gerekli"})
        assert "Parolasız sudo" in secim.uygunluk(c, "temizlik")
        assert "Parolasız sudo" in secim.uygunluk(c, "paket")

    def test_xfce_gorunum_disi(self):
        c = _cihaz("10.30.0.4", **{**HAZIR, "masaustu": "XFCE"})
        assert "XFCE" in secim.uygunluk(c, "gorunum")
        assert secim.uygunluk(c, "paket") is None

    def test_tekillestirme_yalniz_iki_hesapta(self):
        c = _cihaz("10.30.0.5", **HAZIR)
        assert "bilinmiyor" in secim.uygunluk(c, "tekillestirme")
        veritabani.cihaz_guncelle(c["id"], yonetim_hesaplari=["pardus"])
        assert "gerekmez" in secim.uygunluk(veritabani.cihaz(c["id"]), "tekillestirme")
        veritabani.cihaz_guncelle(c["id"], yonetim_hesaplari=["pardus", "hp"])
        c = veritabani.cihaz(c["id"])
        assert secim.uygunluk(c, "tekillestirme") is None
        assert "tekilleştir" in secim.gereken_islem(c)["metin"]

    def test_gereken_islem_onceligi(self):
        c = _cihaz("10.30.0.6")
        assert secim.gereken_islem(c)["sayfa"] == "M1-S2"
        c = _cihaz("10.30.0.7", **{**HAZIR, "yonetim_hesaplari": ["pardus"], "gizleme_durumu": "gorunur",
                                   "son_kontrol": veritabani.simdi()})
        assert secim.gereken_islem(c)["sayfa"] == "M2-S3"
        veritabani.cihaz_guncelle(c["id"], gizleme_durumu="gizli")
        assert secim.gereken_islem(veritabani.cihaz(c["id"])) is None

    def test_hedef_listesi_ayrimi_ve_yineleme(self):
        a = _cihaz("10.30.0.8", **HAZIR)
        b = _cihaz("10.30.0.9", korunan=True, **HAZIR)
        uygun, disarida = secim.hedefleri_ayir([a["id"], b["id"], a["id"], "yok"], "temizlik")
        assert [c["id"] for c in uygun] == [a["id"]]
        assert {d["neden"].split(" ")[0] for d in disarida} == {"Korunan", "Envanterde"}

    def test_ogretmen_adresi_kapsam_disi(self, monkeypatch):
        monkeypatch.setattr(ag, "yerel_adresler", lambda: frozenset({"10.30.0.10"}))
        with pytest.raises(envanter.EnvanterHatasi):
            envanter.cihaz_ekle("10.30.0.10")
        veritabani.calistir("INSERT INTO cihaz(id, ip, ssh_port, durum) VALUES('ogr', '10.30.0.10', 22, 'x')")
        assert "Öğretmen" in secim.uygunluk(veritabani.cihaz("ogr"), "temizlik")


# ---------------------------------------------------------------- envanter: ekleme ve içe aktarma

class TestEnvanterIceAktarma:
    def test_ekleme_ag_baglantisi_kurmaz(self, monkeypatch):
        from uygulama import ssh_araclari

        def yasak(*a, **k):
            raise AssertionError("ekleme sırasında ağ bağlantısı kurulmamalı")
        for ad in ("host_kimligi_topla", "parola_ile_baglan", "anahtar_ile_baglan"):
            monkeypatch.setattr(ssh_araclari, ad, yasak)
        sonuc = asyncio.run(ana.cihaz_ekle(ana.CihazEkleIstek(ip="10.31.0.1", etiket="LAB09")))
        c = veritabani.cihaz(sonuc["id"])
        assert c["durum"] == "Kimlik okunmadı" and not c["parmak_izi"]

    def test_ansible_ini(self):
        metin = (
            "[bilisim_1]\n"
            "lab10 ansible_host=10.31.0.10 ansible_user=pardus\n"
            "10.31.0.11\n"
            "lab12 ansible_host=10.31.0.12 ansible_port=2222\n"
            "adi-yok-ip-yok\n"
            "\n[bilisim_1:vars]\nansible_user=hp\n"
            "[tum:children]\nbilisim_1\n"
        )
        o = envanter.ice_aktar_onizle(metin)
        assert o["bicim"] == "ansible"
        satir = {s["ip"]: s for s in o["satirlar"]}
        assert satir["10.31.0.10"]["hesap"] == "pardus" and satir["10.31.0.10"]["etiket"] == "lab10"
        assert satir["10.31.0.11"]["hesap"] == "hp" and satir["10.31.0.11"]["laboratuvar"] == "bilisim_1"
        assert satir["10.31.0.12"]["port"] == 2222
        assert satir["adi-yok-ip-yok"]["durum"] == "gecersiz"
        assert o["eklenecek"] == 3
        sonuc = envanter.ice_aktar(metin)
        assert sonuc["eklenen"] == 3
        assert envanter.ice_aktar_onizle(metin)["eklenecek"] == 0  # hepsi artık "var"

    def test_csv_baslikli_ve_yinelenen(self):
        metin = "ad;ip;hesap;laboratuvar\nLAB20;10.31.0.20;pardus;Lab-2\nLAB21;10.31.0.20;hp;Lab-2\n"
        o = envanter.ice_aktar_onizle(metin)
        assert o["bicim"] == "csv"
        assert [s["durum"] for s in o["satirlar"]] == ["eklenecek", "yinelenen"]

    def test_ansible_disa_aktarim(self):
        a = _cihaz("10.31.0.30", etiket="LAB30", grup="Bilişim-1", **{**HAZIR, "baglanti_hesabi": "hp"})
        _cihaz("10.31.0.31", etiket="ETAP", grup="Bilişim-1", korunan=True, **HAZIR)
        _cihaz("10.31.0.32", etiket="HAZIRDEGIL", grup="Bilişim-1")
        metin = envanter.ansible_envanteri()
        assert "[bilisim_1]" in metin
        assert "LAB30 ansible_host=10.31.0.30 ansible_port=22 ansible_user=hp" in metin
        assert "ETAP" not in metin and "HAZIRDEGIL" not in metin
        assert "ansible_become=true" in metin
        assert "ansible_password" not in metin and "become_pass" not in metin
        assert a["id"]


# ---------------------------------------------------------------- .deb doğrulama

def _deb(control: str, debian_binary=b"2.0\n", uyeler=None) -> bytes:
    def tar(dosyalar):
        b = io.BytesIO()
        with tarfile.open(fileobj=b, mode="w:xz") as t:
            for ad, veri in dosyalar:
                ti = tarfile.TarInfo(ad)
                ti.size = len(veri)
                t.addfile(ti, io.BytesIO(veri))
        return b.getvalue()

    def uye(ad, veri):
        bas = f"{ad:<16}{0:<12}0     0     100644  {len(veri):<10}`\n".encode()
        return bas + veri + (b"\n" if len(veri) % 2 else b"")
    parcalar = uyeler or [("debian-binary", debian_binary),
                          ("control.tar.xz", tar([("./control", control.encode())])),
                          ("data.tar.xz", tar([("./usr/share/doc/x/BENIOKU", b"x")]))]
    return b"!<arch>\n" + b"".join(uye(a, v) for a, v in parcalar)


CONTROL = "Package: psy-x\nVersion: 1:2.0-1\nArchitecture: all\nInstalled-Size: 12\nDepends: sl\nDescription: x\n y\n"


class TestDebPaketi:
    def test_gecerli_paket(self, tmp_path):
        yol = tmp_path / "x.deb"
        yol.write_bytes(_deb(CONTROL))
        b = debpaket.incele(str(yol))
        assert (b["paket"], b["surum"], b["mimari"], b["kurulu_kb"]) == ("psy-x", "1:2.0-1", "all", 12)
        assert b["kontrol"]["Depends"] == "sl" and b["kontrol"]["Description"] == "x\ny"

    @pytest.mark.parametrize("icerik,parca", [
        (b"merhaba", "ar imzası"),
        (None, "debian-binary"),
        ("sürüm", "2.0"),
        ("mimari", "mimari"),
        ("ad", "paket adı"),
    ])
    def test_yapi_reddi(self, tmp_path, icerik, parca):
        yol = tmp_path / "x.deb"
        if icerik == b"merhaba":
            yol.write_bytes(b"merhaba dunya")
        elif icerik is None:
            yol.write_bytes(_deb("", uyeler=[("data.tar.xz", b"x"), ("control.tar.xz", b"y"), ("z", b"")]))
        elif icerik == "sürüm":
            yol.write_bytes(_deb(CONTROL, debian_binary=b"3.0\n"))
        elif icerik == "mimari":
            yol.write_bytes(_deb(CONTROL.replace("Architecture: all", "Architecture: s390x")))
        else:
            yol.write_bytes(_deb(CONTROL.replace("psy-x", "Kotu_Ad")))
        with pytest.raises(debpaket.PaketHatasi) as hata:
            debpaket.incele(str(yol))
        assert parca in str(hata.value)

    def test_apt_benzetim_ayristirma(self):
        cikti = ("Inst libfoo (1.2 Debian:12/stable [amd64])\n"
                 "Inst bar [2.0] (2.1 Debian:12/stable [amd64])\n"
                 "Inst baz [3.0] (2.9 local [all])\n"
                 "Remv nano [7.2-1]\n"
                 "Conf libfoo (1.2 Debian:12/stable [amd64])\n")
        kucuk = lambda a, _islec, b: a < b  # noqa: E731
        s = uzak_paket.apt_ciktisi_ayristir(cikti, kucuk)
        assert s["yeni"] == [{"paket": "libfoo", "surum": "1.2"}]
        assert s["guncellenecek"] == [{"paket": "bar", "eski": "2.0", "yeni": "2.1"}]
        assert s["dusurulecek"] == [{"paket": "baz", "eski": "3.0", "yeni": "2.9"}]
        assert s["kaldirilacak"] == ["nano"]

    def test_yukleme_ucu_dosya_yolu_kabul_etmez(self):
        """Öğrenci portalındaki dosyalar bu akışa giremez: uç yalnız gövde alır."""
        import inspect
        imza = inspect.signature(ana.paket_yukle)
        assert list(imza.parameters) == ["istek"]
        kaynak = inspect.getsource(ana.paket_yukle)
        assert "odev" not in kaynak.lower()


# ---------------------------------------------------------------- uzak betiklerin saf işlevleri

class TestUzakBetikler:
    def test_sudoers_icerigi(self):
        metin = uzak_hazirlik.sudoers_icerigi(["pardus"])
        assert "pardus ALL=(ALL:ALL) NOPASSWD: ALL\n" in metin
        assert "root eşdeğeri" in metin
        assert "ogrenci" not in metin

    def test_sudoers_yalniz_yonetim_hesabi(self):
        assert "hata" in uzak_hazirlik.sudoers({"hesaplar": ["ogrenci"]})
        assert "hata" in uzak_hazirlik.sudoers({"hesaplar": ["root"]})

    def test_mevcut_hesaplar_ayristirma(self, tmp_path, monkeypatch):
        dosya = tmp_path / "s"
        dosya.write_text("# yorum\npardus ALL=(ALL:ALL) NOPASSWD: ALL\nhp ALL=(ALL:ALL) NOPASSWD: ALL\n",
                         encoding="utf-8")
        monkeypatch.setattr(uzak_hazirlik, "SUDOERS", str(dosya))
        assert uzak_hazirlik.mevcut_hesaplar() == ["pardus", "hp"]

    def test_ini_ayarla_yorumlari_korur(self):
        gdm = ("# GDM configuration storage\n[daemon]\n# Enabling automatic login\n"
               "#  AutomaticLoginEnable = true\nAutomaticLogin=eski\n\n[security]\n")
        yeni = uzak_gorunum.ini_ayarla(gdm, "daemon", {"AutomaticLoginEnable": "true",
                                                       "AutomaticLogin": "ogrenci"})
        assert "#  AutomaticLoginEnable = true" in yeni and "AutomaticLogin=eski" not in yeni
        assert yeni.index("AutomaticLogin=ogrenci") < yeni.index("[security]")
        bos = uzak_gorunum.ini_ayarla("", "User", {"SystemAccount": "true"})
        assert "[User]\nSystemAccount=true" in bos
        kaldir = uzak_gorunum.ini_ayarla(yeni, "daemon", {"AutomaticLoginEnable": "false",
                                                          "AutomaticLogin": None})
        assert "AutomaticLogin=" not in kaldir.replace("AutomaticLoginEnable", "")

    @pytest.mark.parametrize("tur,metin,beklenen", [
        ("type b", "true", True), ("type b", "'true'", False), ("type d", "0.85", True),
        ("type i", "48", True), ("type s", "'Windows'", True), ("type s", "Windows", False),
        ("enum\n'LEFT'\n'BOTTOM'", "'BOTTOM'", True), ("enum\n'LEFT'\n'BOTTOM'", "'TOP'", False),
        ("type as", "['a', 'b']", True),
    ])
    def test_deger_turu_denetimi(self, tur, metin, beklenen):
        assert uzak_gorunum.deger_uyar_mi(tur, metin) is beklenen

    def test_dconf_sayi_karsilastirma_ve_dize(self):
        assert uzak_gorunum.ayni_deger("0.84999999999999998", "0.85")
        assert not uzak_gorunum.ayni_deger("'a'", "'b'")
        assert uzak_gorunum.gv_dize("it's") == "'it\\'s'"

    def test_dconf_dosyalari_edu_varsayilanlarindan_sonra_gelir(self):
        """dconf'ta alfabetik olarak sonraki dosya kazanır; Pardus EDU 30-edu-gnome kullanır."""
        for yol in (uzak_gorunum.DUVAR_DOSYASI, uzak_gorunum.DUZEN_DOSYASI, uzak_gorunum.KILIT_DOSYASI):
            assert os.path.basename(yol) > "30-edu-gnome"

    @pytest.mark.skipif(not hasattr(os.stat_result, "st_blocks"), reason="st_blocks yalnız POSIX")
    def test_olcum_sabit_baglanti_ve_seyrek_dosya(self, tmp_path):
        from uygulama.uzak import temizlik as uzak_temizlik
        alan = tmp_path / "alan"
        alan.mkdir()
        (alan / "a.bin").write_bytes(os.urandom(65536))
        os.link(alan / "a.bin", alan / "a-bag.bin")
        with open(alan / "seyrek.img", "wb") as f:
            f.truncate(50 * 1048576)
        dis = tmp_path / "dis.bin"
        dis.write_bytes(os.urandom(32768))
        os.link(dis, alan / "dis-bag.bin")
        o = uzak_temizlik.Olcum()
        o.ekle(str(alan))
        s = o.sonuc()
        assert s["bayt"] == 65536 + 50 * 1048576 + 32768      # sabit bağlantı bir kez
        assert s["ayrilmis"] < 1048576                          # seyrek dosya yer kaplamaz
        assert s["serbest_kalabilir"] < s["ayrilmis"]           # dışarıda adı olan dosya sayılmaz


# ---------------------------------------------------------------- parola kalıcılığı

def test_hazirlik_parolasi_is_kaydina_yazilmaz(monkeypatch):
    from uygulama import isler

    baslayan = {}
    monkeypatch.setattr(isler, "aktif_is_var_mi", lambda tip=None: False)
    monkeypatch.setattr(isler, "baslat", lambda is_id, tip, f: baslayan.setdefault("id", is_id))
    c = _cihaz("10.32.0.1", parmak_izi="SHA256:z", parmak_izi_onay=1)
    istek = ana.HazirlikIstek(cihazlar=[c["id"]], parolalar={"pardus": "Gizli-Parola-123", "x": "y"})
    yanit = asyncio.run(ana.hazirlik_baslat(istek))
    kayit = veritabani.tek("SELECT parametreler FROM is_kaydi WHERE id=?", (yanit["is_id"],))
    assert "Gizli-Parola-123" not in kayit["parametreler"]
    assert '"hesaplar": ["pardus"]' in kayit["parametreler"]
    dump = "\n".join(veritabani.ac().iterdump())
    assert "Gizli-Parola-123" not in dump


def test_onizleme_kaynaklarla_guncel():
    """arayuz-onizleme.html gerçek arayüz dosyalarından üretilir; elle düzenlenmez."""
    import onizleme_yap
    hedef = KOK / "arayuz-onizleme.html"
    assert hedef.exists(), "python araclar/onizleme_yap.py çalıştırın"
    assert hedef.read_text(encoding="utf-8") == onizleme_yap.uret(), \
        "önizleme eski: python araclar/onizleme_yap.py çalıştırın"
    metin = hedef.read_text(encoding="utf-8")
    assert "DEMO — örnek veriler" in metin
    assert not re.search(r'(src|href)="(https?:)?//', metin), "harici kaynak olmamalı"


def test_referans_haritasi_guncel():
    import referans_haritasi
    harita = KOK / "belgeler" / "arayuz_referans_haritasi.md"
    if harita.exists():
        assert harita.read_text(encoding="utf-8") == referans_haritasi.uret(), "python araclar/referans_haritasi.py çalıştırın"
    dugmeler, _, _ = _kayit_defteri()
    menuler, ayristirilan, _ = referans_haritasi.ayristir((ARAYUZ / "referans.js").read_text(encoding="utf-8"))
    assert set(ayristirilan) == set(dugmeler)


def test_ag_bilgisi_proc_dosyalarindan():
    """Servis netlink kullanamaz; öğretmen adresleri /proc/net'ten okunur (lab öğretmen PC çıktısı)."""
    veri = Path(__file__).parent / "veri"
    yerel = ag.fib_yerel((veri / "fib_trie.txt").read_text(encoding="utf-8"))
    assert "192.168.23.136" in yerel and "127.0.0.1" in yerel
    assert ag.rota_agi((veri / "net_route.txt").read_text(encoding="utf-8"), "192.168.23.136") \
        == {"ag": "192.168.23.0/24", "arayuz": "ens33"}
