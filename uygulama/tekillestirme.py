"""hp / pardus yönetim hesabı tekilleştirme (karar 21).

Hedef: her öğrenci bilgisayarında hp veya pardus'tan yalnız biri kalsın.
- Yalnız biri varsa ona dokunulmaz (sırf isim birliği için hesap açılmaz).
- İkisi varsa öğretmen korunacak olanı seçer (öneri: pardus).
- Silinecek hesabın kapsamı önce gösterilir ve ev dizini + hesap kayıtları
  öğrenci PC'de yedeklenir (karar 18: öğrenci PC'de kalır).
- Korunacak hesapla YENİ ve bağımsız bir oturumda yalnız anahtarla bağlanılıp
  `sudo -n true` doğrulanmadan diğer hesap silinmez.
- Bağlantıyı sağlayan hesap, kendi oturumundan silinmez: silme her zaman
  korunacak hesabın oturumundan yapılır.
- ogrenci, root ve sistem/servis hesapları bu işlemin dışındadır.
- Envanter (ve dolayısıyla Ansible dışa aktarımı) korunacak hesaba geçer; sshd
  AllowUsers/AllowGroups kısıtı varsa korunacak hesaba izin eklenir.
"""

import asyncio

from . import anahtar, ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim
from .ssh_araclari import _ANAHTAR_EKLE_BETIGI

VARSAYILAN_KORUNACAK = "pardus"


async def onizleme_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or iptal.is_set():
            return
        neden = secim.uygunluk(cihaz, "tekillestirme")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}",
                                      {"cihaz_id": cid, "ad": veritabani.cihaz_adi(cihaz)})
            return
        async with sinir:
            await asyncio.to_thread(_onizle, is_id, cihaz)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _onizle(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "baglanti": cihaz["baglanti_hesabi"]}
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — bağlanılamadı: {hata}", veri)
        return
    try:
        sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("hesap"),
                                        {"kip": "kapsam", "hesaplar": list(ayarlar.YONETIM_HESAPLARI)},
                                        zaman=180)
        if "hata" in sonuc:
            raise RuntimeError(sonuc["hata"])
        hesaplar = sonuc["hesaplar"]
        var_olan = [h for h in ayarlar.YONETIM_HESAPLARI if hesaplar.get(h)]
        veritabani.cihaz_guncelle(cihaz["id"], yonetim_hesaplari=var_olan)
        veri["hesaplar"] = hesaplar
        if len(var_olan) < 2:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "tamam",
                                      f"{ad} — yalnız {', '.join(var_olan) or 'hiçbiri'} var; "
                                      f"tekilleştirme gerekmez", veri)
            return
        oneri = VARSAYILAN_KORUNACAK if VARSAYILAN_KORUNACAK in var_olan else var_olan[0]
        veri["oneri"] = oneri
        uyarilar = [f"{h}: açık oturum" for h in var_olan if hesaplar[h]["oturum"]]
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — iki yönetim hesabı var ({', '.join(var_olan)}); öneri: {oneri} korunsun"
            + (f" | UYARI: {'; '.join(uyarilar)}" if uyarilar else ""), veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kapsam", f"{ad} — {hata}", veri)
    finally:
        istemci.close()


async def uygula_isi(is_id: str, korunacaklar: dict[str, str], iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(2)
    acik_satir = anahtar.acik_anahtar_satiri()

    async def _tek(cid: str, korunacak: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or iptal.is_set():
            return
        neden = secim.uygunluk(cihaz, "tekillestirme")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(_uygula, is_id, cihaz, korunacak, acik_satir)

    await asyncio.gather(*(_tek(c, k) for c, k in korunacaklar.items()))


class _Dur(Exception):
    def __init__(self, asama, mesaj):
        super().__init__(mesaj)
        self.asama = asama


def _uygula(is_id: str, cihaz: dict, korunacak: str, acik_satir: str) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    silinecek = next(h for h in ayarlar.YONETIM_HESAPLARI if h != korunacak)
    baglanti = cihaz["baglanti_hesabi"]
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "korunacak": korunacak, "silinecek": silinecek,
            "adimlar": []}

    def adim(asama, metin):
        veri["adimlar"].append(metin)
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", asama, f"{ad} — {metin}", veri)

    istemci = test = None
    try:
        if korunacak not in ayarlar.YONETIM_HESAPLARI:
            raise _Dur("secim", "korunacak hesap pardus veya hp olmalı")
        istemci = yonetim.baglan(cihaz)
        kapsam = ssh_araclari.sudo_betik(istemci, uzak.betik("hesap"),
                                         {"kip": "kapsam", "hesaplar": [korunacak, silinecek]},
                                         zaman=180)
        if "hata" in kapsam:
            raise _Dur("kapsam", kapsam["hata"])
        hesaplar = kapsam["hesaplar"]
        if not hesaplar.get(korunacak):
            raise _Dur("kapsam", f"korunacak hesap ({korunacak}) bu bilgisayarda yok")
        if not hesaplar.get(silinecek):
            veritabani.cihaz_guncelle(cihaz["id"], yonetim_hesaplari=[korunacak])
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "tamam",
                                      f"{ad} — {silinecek} zaten yok; işlem gerekmedi", veri)
            return
        if hesaplar[silinecek]["oturum"]:
            raise _Dur("oturum", f"{silinecek} hesabında açık oturum var; hiçbir şey silinmedi")
        adim("kapsam", f"{silinecek}: ev dizini {hesaplar[silinecek]['ev_bayt'] // 1048576} MB, "
                       f"{hesaplar[silinecek]['anahtar_sayisi']} yetkili anahtar"
                       + (", cron işi var" if hesaplar[silinecek]["cron"] else ""))

        # 1) korunacak hesabı hazırla (bağlantı silinecek hesapla kuruluysa)
        if baglanti != korunacak:
            rc, cikti, hata = ssh_araclari.sudo_komut(
                istemci, ["runuser", "-u", korunacak, "--", "python3", "-c", _ANAHTAR_EKLE_BETIGI],
                girdi=acik_satir + "\n", zaman=60)
            sonuc = (cikti or hata).strip()
            if rc != 0 or sonuc not in ("EKLENDI", "ZATEN_VAR"):
                raise _Dur("anahtar", f"{korunacak} hesabına anahtar eklenemedi: {sonuc}")
            adim("anahtar", f"uygulama anahtarı {korunacak} hesabına "
                            f"{'eklendi' if sonuc == 'EKLENDI' else 'zaten vardı'}")
        s = ssh_araclari.sudo_betik(istemci, uzak.betik("hazirlik"),
                                    {"kip": "sudoers", "ekle": [korunacak]}, zaman=60)
        if "hata" in s:
            raise _Dur("sudo", f"{korunacak} için parolasız sudo yazılamadı: {s['hata']}")
        s = ssh_araclari.sudo_betik(istemci, uzak.betik("hazirlik"),
                                    {"kip": "sshd_izin", "hesap": korunacak}, zaman=60)
        if "hata" in s:
            raise _Dur("sshd", s["hata"])
        if s.get("durum") == "eklendi":
            adim("sshd", "SSH erişim kuralı güncellendi: " + ", ".join(s["satirlar"]))
        istemci.close()
        istemci = None

        # 2) bağımsız doğrulama: yalnız anahtar, yeni oturum, sudo -n
        adim("test", f"{korunacak} hesabıyla yeni oturumda doğrulanıyor")
        try:
            test = yonetim.baglan(dict(cihaz, baglanti_hesabi=korunacak))
        except Exception as hata:
            raise _Dur("test", f"{korunacak} hesabıyla anahtarlı bağlantı kurulamadı ({hata}); "
                               f"{silinecek} silinmedi")
        rc, kim, _ = ssh_araclari.komut(test, ["whoami"])
        if rc != 0 or kim.strip() != korunacak or not ssh_araclari.parolasiz_sudo_var_mi(test):
            raise _Dur("test", f"{korunacak} hesabında anahtar/parolasız sudo doğrulanamadı; "
                               f"{silinecek} silinmedi")
        veritabani.cihaz_guncelle(cihaz["id"], baglanti_hesabi=korunacak, anahtar_durumu="ok",
                                  sudo_durumu="parolasiz", durum="Yönetilebilir")
        adim("test", f"{korunacak}: anahtar ✓, sudo -n ✓ — envanter bu hesaba geçti")

        # 3) yedek (öğrenci PC'de) ve silme — korunacak hesabın oturumundan
        y = ssh_araclari.sudo_betik(test, uzak.betik("hesap"), {"kip": "yedekle", "hesap": silinecek},
                                    zaman=1800)
        if "hata" in y:
            raise _Dur("yedek", f"{silinecek} yedeklenemedi ({y['hata']}); silinmedi")
        veri["yedek"] = {"arsiv": y["arsiv"], "sha256": y["sha256"], "bayt": y["bayt"]}
        adim("yedek", f"{silinecek} yedeklendi ve doğrulandı: {y['arsiv']}")
        blob = acik_satir.split()[1]
        s = ssh_araclari.sudo_betik(test, uzak.betik("hesap"),
                                    {"kip": "sil", "hesap": silinecek, "korunan": korunacak,
                                     "anahtar": blob, "arsiv": y["arsiv"], "sha256": y["sha256"]},
                                    zaman=600)
        if "hata" in s:
            raise _Dur("sil", s["hata"])
        if not ssh_araclari.parolasiz_sudo_var_mi(test):
            raise _Dur("sil", f"{silinecek} silindi ancak son kontrolde sudo -n başarısız; "
                              f"elle kontrol edin")
        veritabani.cihaz_guncelle(cihaz["id"], yonetim_hesaplari=[korunacak],
                                  son_kontrol=veritabani.simdi())
        try:  # giriş ekranı gizleme vb. alanlar artık korunan hesaba göre okunur
            durum, _ = yonetim.durum_topla(test)
            yonetim.durum_kaydet(veritabani.cihaz(cihaz["id"]), durum, True)
        except Exception:
            pass  # asıl iş bitti; durum M1-S1'den yeniden okunabilir
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — {silinecek} silindi, {korunacak} korundu (yedek öğrenci PC'de: "
            f"{y['arsiv']}); Ansible envanteri {korunacak} hesabını kullanır", veri)
    except _Dur as hata:
        veri["hata"] = str(hata)
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", hata.asama, f"{ad} — {hata}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "hata", f"{ad} — {hata}", veri)
    finally:
        for i in (istemci, test):
            if i is not None:
                i.close()
