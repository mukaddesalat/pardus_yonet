"""0.6.0: M2-S4 uyku ayarı ve M2-S5 zamanlı kapatma — takvim üretimi, birim dosyaları, dconf
içeriği ve envanter alanı (saf işlevler; gerçek bilgisayar gerektirmez)."""

import re
from datetime import datetime

import pytest

from uygulama import ana, guc_ayar, secim
from uygulama.uzak import durum as uzak_durum
from uygulama.uzak import guc_ayar as uzak_guc

from test_v04 import HAZIR, _cihaz  # noqa: E402

SIMDI = datetime(2026, 10, 4, 21, 0)


@pytest.mark.parametrize("gunler,beklenen", [
    (["Mon", "Tue", "Wed", "Thu", "Fri"], "Pzt–Cum"),
    (["Mon", "Wed", "Fri"], "Pzt, Çar, Cum"),
    (["Sat", "Sun"], "Cmt, Paz"),
    (["Mon", "Tue", "Wed", "Fri", "Sat", "Sun"], "Pzt–Çar, Cum–Paz"),
    (list(guc_ayar.GUNLER), "Her gün"),
])
def test_gun_etiketi(gunler, beklenen):
    assert guc_ayar._gun_etiketi(gunler) == beklenen


class TestTakvim:
    def test_her_hafta(self):
        takvim, etiket = guc_ayar.takvim_olustur("surekli", "17:30", gunler=["Fri", "Mon", "Tue", "Wed", "Thu"])
        assert takvim == "Mon,Tue,Wed,Thu,Fri *-*-* 17:30:00"     # gün sırası düzeltilir
        assert etiket == "Pzt–Cum 17:30 (her hafta)"
        assert guc_ayar.takvim_olustur("surekli", "08:05", gunler=list(guc_ayar.GUNLER))[0] == "*-*-* 08:05:00"

    def test_bir_kez(self):
        takvim, etiket = guc_ayar.takvim_olustur("tek", "12:00", tarih="2026-10-05", simdi=SIMDI)
        assert (takvim, etiket) == ("2026-10-05 12:00:00", "05.10.2026 12:00 (bir kez)")

    @pytest.mark.parametrize("args,parca", [
        (("tek", "12:00", "2026-10-04"), "Geçmiş"),
        (("tek", "25:00", "2026-10-05"), "Saat"),
        (("tek", "12:00", None), "Tarih"),
        (("surekli", "12:00", None, []), "gün"),
        (("hergun", "12:00"), "Plan türü"),
        (("surekli", "12:00", None, ["Mon; rm -rf /"]), "gün"),   # bilinmeyen gün atılır
    ])
    def test_hatalar(self, args, parca):
        with pytest.raises(guc_ayar.GucHatasi, match=parca):
            guc_ayar.takvim_olustur(*args, simdi=SIMDI)

    def test_plan_olustur(self):
        p = guc_ayar.plan_olustur("surekli", "17:30", None, ["Mon"], 5, "Gün sonu\nkapatma")
        assert len(p["id"]) == 6 and p["id"].isalnum()
        assert p["aciklama"] == "Gün sonu kapatma"            # kontrol karakteri temizlenir
        assert uzak_guc.ID_DESENI.match(p["id"]) and uzak_guc.TAKVIM_DESENI.match(p["takvim"])
        with pytest.raises(guc_ayar.GucHatasi):
            guc_ayar.plan_olustur("surekli", "17:30", None, ["Mon"], 7)   # izinli uyarı süresi değil


class TestUzakGuc:
    def test_dconf_icerigi(self):
        metin = uzak_guc.dconf_icerik(uzak_guc.oturum_anahtarlari(10))
        assert "[org/gnome/settings-daemon/plugins/power]" in metin
        assert "sleep-inactive-ac-type='nothing'" in metin and "sleep-inactive-ac-timeout=0" in metin
        assert "[org/gnome/desktop/session]\nidle-delay=uint32 600" in metin
        assert "idle-delay=uint32 0" in uzak_guc.dconf_icerik(uzak_guc.oturum_anahtarlari(0))

    def test_birim_dosyalari(self):
        servis, zamanlayici = uzak_guc.birim_icerikleri({"id": "a1b2c3", "tur": "tek", "uyari_dk": 5,
                                                        "takvim": "2026-10-05 12:00:00", "etiket": "x"})
        assert "ExecStart=/usr/local/sbin/pardus-sinif-kapat 5 a1b2c3 tek" in servis
        assert "OnCalendar=2026-10-05 12:00:00" in zamanlayici
        assert "Persistent=false" in zamanlayici          # kapalıyken kaçan kapatma açılışta uygulanmaz
        assert zamanlayici.startswith("# psy: {")

    def test_yardimci_betik_guvenli(self):
        icerik = uzak_guc.YARDIMCI_ICERIK
        assert 'case "$ID" in' in icerik and 'case "$DK" in' in icerik
        assert "rm -f \"/etc/systemd/system/pardus-sinif-kapat-$ID.timer\"" in icerik

    def test_uyari_suresi_gecici_zamanlayicida(self):
        # Lab bulgusu: "shutdown +N" son 5 dk'da /run/nologin oluşturur → root dışı SSH kapanır ve
        # uygulama iptal edemez. Uyarı süresi geçici systemd zamanlayıcısıyla beklenmeli.
        icerik = uzak_guc.YARDIMCI_ICERIK
        komutlar = [s for s in icerik.splitlines() if not s.lstrip().startswith("#")]
        assert not any(re.search(r"(^|[\s/])shutdown\s", s) for s in komutlar)   # simge adı system-shutdown serbest
        assert 'systemd-run --quiet --unit="$BEKLEYEN"' in icerik and '--on-active="${DK}min"' in icerik
        assert "BEKLEYEN=%s\n" % uzak_guc.BEKLEYEN_BIRIM in icerik
        assert "> %s\n" % uzak_guc.BEKLEYEN_SAAT in icerik
        assert icerik.index('is-active --quiet "$BEKLEYEN.timer"') < icerik.index("bildir()")  # çift sayaç yok

    def test_yardimci_bildirim_gdbus_once(self):
        # Pardus'ta notify-send kurulu gelmez (lab'da doğrulandı); gdbus öncelikli, notify-send yedek
        icerik = uzak_guc.YARDIMCI_ICERIK
        assert icerik.index("command -v gdbus") < icerik.index("command -v notify-send")
        assert "org.freedesktop.Notifications.Notify" in icerik and "<byte 2>" in icerik

    def test_uyari_bildirim_kimlikleri(self, tmp_path, monkeypatch):
        # İptal bildirimi ekrandaki kritik uyarının yerine geçer (kimlikler yardımcıdan okunur)
        assert ">> %s" % uzak_guc.BEKLEYEN_BILDIRIM in uzak_guc.YARDIMCI_ICERIK   # yardımcı aynı dosyaya yazar
        dosya = tmp_path / "bildirim"
        monkeypatch.setattr(uzak_guc, "BEKLEYEN_BILDIRIM", str(dosya))
        assert uzak_guc.uyari_bildirimleri() == {}
        dosya.write_text("ogrenci 7\nbozuk satir x\nDebian-gdm 3\n")
        assert uzak_guc.uyari_bildirimleri() == {"ogrenci": "7", "Debian-gdm": "3"}

    def test_yardimci_guncelle(self, tmp_path, monkeypatch):
        # Uygulama güncellenince hedefteki eski yardımcı (ör. shutdown +N kullanan) yenilenmeli
        birimler, yardimci = tmp_path / "system", tmp_path / "pardus-sinif-kapat"
        birimler.mkdir()
        monkeypatch.setattr(uzak_guc, "BIRIM_KOK", str(birimler))
        monkeypatch.setattr(uzak_guc, "YARDIMCI", str(yardimci))
        monkeypatch.setattr(uzak_guc.os, "geteuid", lambda: 0, raising=False)
        yardimci.write_text("eski: shutdown -h +5\n")
        assert uzak_guc.yardimci_guncelle() is False               # plan yok: dokunulmaz
        (birimler / "pardus-sinif-kapat-a1b2c3.timer").write_text("[Timer]\n")
        assert uzak_guc.yardimci_guncelle() is True
        assert yardimci.read_text(encoding="utf-8") == uzak_guc.YARDIMCI_ICERIK
        assert uzak_guc.yardimci_guncelle() is False               # zaten güncel

    def test_gdm_profili_icerigi(self):
        # Debian 12 / Pardus 23.5 paket profili (lab'da okundu): system-db:gdm yok
        paket = ["user-db:user", "file-db:/var/lib/gdm3/greeter-dconf-defaults"]
        satirlar = uzak_guc.gdm_profili_icerik(paket).splitlines()
        assert satirlar[0] == uzak_guc.GDM_PROFIL_IMZA            # kaldırırken tanınır
        assert satirlar[1:] == ["user-db:user", "system-db:gdm", "file-db:/var/lib/gdm3/greeter-dconf-defaults"]

    def test_gdm_profili_hazirla(self, tmp_path, monkeypatch):
        etc, paket = tmp_path / "etc-gdm", tmp_path / "usr-gdm"
        monkeypatch.setattr(uzak_guc, "GDM_PROFIL", str(etc))
        monkeypatch.setattr(uzak_guc, "GDM_PROFIL_PAKET", str(paket))
        assert uzak_guc.gdm_profili_hazirla() == (False, False, None)        # GDM yok: dokunulmaz
        paket.write_text("user-db:user\nfile-db:/var/lib/gdm3/greeter-dconf-defaults\n")
        assert uzak_guc.gdm_profili_hazirla() == (True, True, None)          # /etc kopyası oluşturulur
        assert "system-db:gdm" in etc.read_text() and uzak_guc.gdm_profili_var()
        assert uzak_guc.gdm_profili_hazirla() == (True, False, None)         # ikinci kez: zaten hazır
        etc.write_text("user-db:user\n")                                     # başkasının profili
        hazir, bizim, notu = uzak_guc.gdm_profili_hazirla()
        assert (hazir, bizim) == (False, False) and "değiştirilmedi" in notu
        assert etc.read_text() == "user-db:user\n"

    def test_uyku_dogrulama_karsilastirma(self):
        assert uzak_guc.ayni("uint32 600", "uint32 600") and uzak_guc.ayni("600", "uint32 600")
        assert not uzak_guc.ayni(None, "0") and not uzak_guc.ayni("'suspend'", "'nothing'")

    def test_durum_betiginde_guc_bolumu(self):
        assert callable(uzak_durum.guc_durumu)
        assert uzak_durum.UYKU_HEDEFLERI == uzak_guc.UYKU_HEDEFLERI


def test_envanter_alani_ve_uygunluk():
    d = {"uyku": {"kapali": True, "ekran_dk": 10}, "bekleyen": False,
         "planlar": [{"id": "a1b2c3", "etiket": "Pzt–Cum 17:30 (her hafta)", "tur": "surekli", "uyari_dk": 5,
                      "sonraki": "Mon 2026-10-05 17:30:00 +03", "etkin": True}]}
    a = guc_ayar.envanter_alani(d)["guc_durumu"]
    assert a["uyku_kapali"] is True and a["ekran_dk"] == 10 and a["planlar"][0]["id"] == "a1b2c3"
    assert "uyku KAPALI" in guc_ayar._ozet(d) and "1 kapatma planı" in guc_ayar._ozet(d)
    c = _cihaz("10.41.0.1", **HAZIR)
    from uygulama import veritabani
    veritabani.cihaz_guncelle(c["id"], **guc_ayar.envanter_alani(d))
    c = veritabani.cihaz(c["id"])
    assert c["guc_durumu"]["planlar"][0]["etiket"].startswith("Pzt")      # JSON geri okunur
    assert secim.uygunluk(c, "guc") is None


def test_api_uclari_kayitli():
    yollar = {getattr(r, "path", None) for r in ana.uygulama.routes}
    for yol in ("/api/guc/uyku", "/api/kapatma/oku", "/api/kapatma/ekle", "/api/kapatma/sil", "/api/kapatma/iptal"):
        assert yol in yollar, yol
