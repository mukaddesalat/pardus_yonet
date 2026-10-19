"""SSH ve hesap hazırlığı (M1-S2, M1-S3): tek seferlik yetkili hazırlık (karar 22).

Akış (bilgisayar başına):
1. Sunucu kimliği onaylı mı? Değilse hiçbir kimlik bilgisi gönderilmez.
2. Bağlantı: uygulama anahtarı çalışıyorsa onunla; yoksa öğretmenin BİR KEZ
   verdiği pardus/hp parolasıyla (hesap+cihaz başına deneme bütçesiyle). Parola
   yalnız bu işin belleğinde yaşar; veritabanına ve loglara yazılmaz.
3. sudo yapabilen hesap seçilir (hp veya pardus). Hiçbiri yoksa kullanıcı/parola
   denemesine girilmez: "yetkili hesap hazırlığı gerekiyor".
4. Uygulama anahtarı authorized_keys'e eklenir.
5. Parolasız sudo: /etc/sudoers.d/ dosyası visudo ile doğrulanarak yazılır.
6. İstenirse `ogrenci` hesabı oluşturulur (sudo verilmez).
7. YENİ ve bağımsız bir oturumda yalnız anahtarla bağlanılır; `sudo -n true`
   çalışmadan cihaz "hazır" sayılmaz.
"""

import asyncio
import time

from . import anahtar, ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim


class HazirlikHatasi(Exception):
    """Öğretmene olduğu gibi gösterilir; asama: hangi adımda durulduğu."""

    def __init__(self, asama: str, mesaj: str):
        super().__init__(mesaj)
        self.asama = asama


async def hazirlik_isi(is_id: str, cihaz_idler: list[str], parolalar: dict[str, str],
                       ogrenci_olustur: bool, iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    acik_satir = anahtar.acik_anahtar_satiri()

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip = cihaz["ip"]
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "hazirlik")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(_hazirla, is_id, cihaz, parolalar, ogrenci_olustur,
                                    acik_satir)

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))


def _parola_ile_dene(cihaz: dict, hesap: str, parola: str):
    """Deneme bütçesiyle tek parola denemesi. Dönüş: istemci veya None."""
    ip, port = cihaz["ip"], cihaz["ssh_port"]
    if veritabani.butce_al(ip, hesap) <= 0:
        raise HazirlikHatasi("dogrulama", f"{hesap}: deneme sınırı doldu (hesap kilitlenmesin "
                                          f"diye durduruldu); yönetici kılavuzuna bakın")
    veritabani.butce_dus(ip, hesap)
    try:
        istemci = ssh_araclari.parola_ile_baglan(ip, port, hesap, parola,
                                                 cihaz["anahtar_tipi"], cihaz["anahtar_b64"])
    except ssh_araclari.SunucuKimligiHatasi as hata:
        raise HazirlikHatasi("kimlik", str(hata))
    except Exception:
        time.sleep(ayarlar.DENEME_BEKLEME)
        return None
    veritabani.butce_sifirla(ip, hesap)
    return istemci


def _yetkili_baglanti(cihaz: dict, parolalar: dict[str, str], notlar: list[str]):
    """(istemci, hesap, sudo_parolası|None) — sudo yapabilen ilk hesap."""
    # 1) Anahtar zaten kuruluysa önce onu kullan
    if cihaz.get("anahtar_durumu") == "ok" and cihaz.get("baglanti_hesabi"):
        hesap = cihaz["baglanti_hesabi"]
        try:
            istemci = yonetim.baglan(cihaz)
        except ssh_araclari.SunucuKimligiHatasi as hata:
            raise HazirlikHatasi("kimlik", str(hata))
        except Exception as hata:
            notlar.append(f"{hesap}: anahtarla bağlanılamadı ({hata})")
        else:
            if ssh_araclari.parolasiz_sudo_var_mi(istemci):
                return istemci, hesap, None
            parola = parolalar.get(hesap)
            if parola and ssh_araclari.sudo_dogrula(istemci, parola) == "parola_gerekli":
                return istemci, hesap, parola
            istemci.close()
            notlar.append(f"{hesap}: parolasız sudo yok" +
                          (" ve verilen parolayla sudo çalışmadı" if parola else
                           "; bu hesabın parolasını girin"))

    # 2) Parola ile: kayıtlı hesap varsa önce o, sonra diğer yönetim hesabı
    adaylar = [h for h in ([cihaz.get("baglanti_hesabi")] + list(ayarlar.YONETIM_HESAPLARI))
               if h in ayarlar.YONETIM_HESAPLARI]
    for hesap in dict.fromkeys(adaylar):
        parola = parolalar.get(hesap)
        if not parola:
            continue
        istemci = _parola_ile_dene(cihaz, hesap, parola)
        if istemci is None:
            notlar.append(f"{hesap}: giriş yapılamadı (hesap yok veya parola yanlış)")
            continue
        sudo = ssh_araclari.sudo_dogrula(istemci, parola)
        if sudo in ("parolasiz", "parola_gerekli"):
            return istemci, hesap, (None if sudo == "parolasiz" else parola)
        istemci.close()
        notlar.append(f"{hesap}: giriş yapıldı ama sudo yetkisi yok")
    if not any(parolalar.get(h) for h in ayarlar.YONETIM_HESAPLARI):
        raise HazirlikHatasi("parola", "Parola girilmedi; pardus veya hp hesabının parolası "
                                       "bir kez gerekir")
    raise HazirlikHatasi(
        "yetki", "Yetkili hesap hazırlığı gerekiyor: sudo yapabilen pardus/hp hesabıyla "
                 "girilemedi (" + "; ".join(notlar) + "). Bilgisayarda yerel hazırlık "
                 "yapın (yönetici kılavuzu: “Yerel hazırlık”).")


def _hazirla(is_id: str, cihaz: dict, parolalar: dict[str, str], ogrenci_olustur: bool,
             acik_satir: str) -> None:
    ip = cihaz["ip"]
    ad = veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "adimlar": []}

    def adim(asama: str, metin: str):
        veri["adimlar"].append(metin)
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", asama, f"{ad} — {metin}", veri)

    istemci = None
    try:
        adim("baglanti", "yetkili hesapla bağlanılıyor")
        notlar: list[str] = []
        istemci, hesap, sudo_parola = _yetkili_baglanti(cihaz, parolalar, notlar)
        veri["hesap"] = hesap
        adim("baglanti", f"{hesap} hesabıyla bağlanıldı" +
             (" (parolasız sudo zaten var)" if sudo_parola is None else ""))

        os_bilgi = ssh_araclari.os_bilgisi(istemci)
        if os_bilgi.get("ID") != "pardus":
            veritabani.cihaz_guncelle(cihaz["id"], durum="Pardus değil — yönetilemez",
                                      pardus_surum=os_bilgi.get("PRETTY_NAME", ""),
                                      son_kontrol=veritabani.simdi())
            raise HazirlikHatasi("pardus", f"Pardus değil ({os_bilgi.get('PRETTY_NAME', '?')}); "
                                           f"hazırlık yapılmadı")

        sonuc = ssh_araclari.anahtar_ekle(istemci, acik_satir)
        if sonuc not in ("EKLENDI", "ZATEN_VAR"):
            raise HazirlikHatasi("anahtar", f"uygulama anahtarı eklenemedi: {sonuc}")
        veri["anahtar"] = "eklendi" if sonuc == "EKLENDI" else "zaten vardı"
        adim("anahtar", f"uygulama anahtarı {veri['anahtar']}")

        s = ssh_araclari.sudo_betik(istemci, uzak.betik("hazirlik"),
                                    {"kip": "sudoers", "ekle": [hesap]}, sudo_parola, zaman=60)
        if "hata" in s:
            raise HazirlikHatasi("sudo", f"parolasız sudo yazılamadı: {s['hata']}")
        veri["sudoers"] = s["durum"]
        adim("sudo", "parolasız sudo " + {"yazildi": "yapılandırıldı (visudo doğrulandı)",
                                          "zaten_var": "zaten yapılandırılmış"}.get(s["durum"], s["durum"]))

        s = ssh_araclari.sudo_betik(istemci, uzak.betik("hazirlik"),
                                    {"kip": "sshd_izin", "hesap": hesap}, sudo_parola, zaman=60)
        if "hata" in s:
            raise HazirlikHatasi("sshd", s["hata"])
        if s.get("durum") == "eklendi":
            adim("sshd", "SSH erişim kuralına hesap eklendi: " + ", ".join(s["satirlar"]))

        if ogrenci_olustur:
            s = ssh_araclari.sudo_betik(istemci, uzak.betik("hazirlik"),
                                        {"kip": "ogrenci", "hesap": ayarlar.PROFIL_HESABI},
                                        sudo_parola, zaman=60)
            if "hata" in s:
                raise HazirlikHatasi("ogrenci", f"{ayarlar.PROFIL_HESABI} hesabı: {s['hata']}")
            veri["ogrenci"] = s["durum"]
            metin = {"olusturuldu": "oluşturuldu (sudo yok, giriş ekranında parolasız)",
                     "zaten_var": "zaten vardı"}[s["durum"]]
            if s.get("yetkili_grup"):
                metin += f" — UYARI: yetkili gruplarda: {', '.join(s['yetkili_grup'])}"
            adim("ogrenci", f"{ayarlar.PROFIL_HESABI} hesabı {metin}")

        # Bağımsız doğrulama: yeni oturum, yalnız anahtar, parola geri dönüşü yok
        adim("test", "yeni oturumda yalnız anahtarla doğrulanıyor")
        taze = dict(cihaz, baglanti_hesabi=hesap)
        try:
            test = yonetim.baglan(taze)
        except Exception as hata:
            raise HazirlikHatasi("test", f"anahtarla bağımsız bağlantı kurulamadı ({hata}); "
                                         f"cihaz hazır sayılmadı")
        try:
            rc, kim, _ = ssh_araclari.komut(test, ["whoami"])
            if rc != 0 or kim.strip() != hesap:
                raise HazirlikHatasi("test", f"beklenmeyen hesap: {kim.strip()!r}")
            if not ssh_araclari.parolasiz_sudo_var_mi(test):
                veritabani.cihaz_guncelle(cihaz["id"], baglanti_hesabi=hesap, anahtar_durumu="ok",
                                          sudo_durumu="parola_gerekli",
                                          durum="Parolasız sudo gerekli")
                raise HazirlikHatasi("test", "anahtar çalışıyor ama `sudo -n` başarısız; "
                                             "parolasız sudo doğrulanamadı")
            veritabani.cihaz_guncelle(cihaz["id"], baglanti_hesabi=hesap, anahtar_durumu="ok",
                                      sudo_durumu="parolasiz", durum="Yönetilebilir")
            durum, _ = yonetim.durum_topla(test)
            alanlar = yonetim.durum_kaydet(veritabani.cihaz(cihaz["id"]), durum, True)
        finally:
            test.close()

        diger = [h for h in (alanlar.get("yonetim_hesaplari") or []) if h != hesap]
        ek = f"; ikinci yönetim hesabı da var ({', '.join(diger)}) — tekilleştirme önerilir" if diger else ""
        veri["dogrulama"] = "anahtar ✓, sudo -n ✓"
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — hazır: {hesap} hesabı, anahtar ve parolasız sudo bağımsız oturumda "
            f"doğrulandı{ek}", veri)
    except HazirlikHatasi as hata:
        veri["hata"] = str(hata)
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", hata.asama, f"{ad} — {hata}", veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "hata", f"{ad} — {hata}", veri)
    finally:
        if istemci is not None:
            istemci.close()


# ---- sunucu kimliği (kimlik bilgisi göndermeden) ----

async def kimlik_oku_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(ayarlar.TARAMA_PARALELLIGI)

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz or iptal.is_set():
            return
        async with sinir:
            await asyncio.to_thread(_kimlik_oku, is_id, cihaz)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _kimlik_oku(is_id: str, cihaz: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    try:
        kimlik = ssh_araclari.host_kimligi_topla(ip, cihaz["ssh_port"])
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — SSH erişilemiyor ({hata})")
        return
    if cihaz["parmak_izi"] == kimlik["parmak_izi"] and cihaz["parmak_izi_onay"]:
        veritabani.hedef_guncelle(is_id, ip, "basarili", "kimlik",
                                  f"{ad} — sunucu kimliği önceki onayla aynı")
        return
    degisti = bool(cihaz["parmak_izi"]) and cihaz["parmak_izi"] != kimlik["parmak_izi"]
    veritabani.cihaz_guncelle(
        cihaz["id"], anahtar_tipi=kimlik["tip"], anahtar_b64=kimlik["b64"],
        parmak_izi=kimlik["parmak_izi"], parmak_izi_onay=0, erisim=1,
        erisim_zamani=veritabani.simdi(),
        durum="Kimlik onayı gerekli (anahtar DEĞİŞMİŞ!)" if degisti else "Kimlik onayı gerekli")
    klon_isaretle(kimlik["parmak_izi"])
    veritabani.hedef_guncelle(
        is_id, ip, "basarili", "kimlik",
        f"{ad} — {'UYARI: kimlik DEĞİŞMİŞ; ' if degisti else ''}onay bekliyor: {kimlik['parmak_izi']}",
        {"cihaz_id": cihaz["id"], "parmak_izi": kimlik["parmak_izi"], "degisti": degisti})


def klon_isaretle(parmak_izi: str) -> None:
    """Aynı host anahtarı birden çok cihazda görülürse işaretle (karar 10)."""
    ayni = veritabani.sorgula("SELECT id FROM cihaz WHERE parmak_izi=?", (parmak_izi,))
    if len(ayni) > 1:
        veritabani.calistir("UPDATE cihaz SET yinelenen_kimlik=1 WHERE parmak_izi=?", (parmak_izi,))


def kimlikleri_onayla(cihaz_idler: list[str]) -> dict:
    """Öğretmenin gördüğü parmak izlerini toplu onaylar (yalnız okunmuş olanlar)."""
    onaylanan, atlanan = [], []
    for cid in dict.fromkeys(cihaz_idler):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or not cihaz["parmak_izi"]:
            atlanan.append(cid)
            continue
        if not cihaz["parmak_izi_onay"]:
            veritabani.cihaz_guncelle(cid, parmak_izi_onay=1,
                                      durum="Hazırlık gerekli" if cihaz["anahtar_durumu"] != "ok"
                                      else cihaz["durum"])
        onaylanan.append(cid)
    return {"onaylanan": len(onaylanan), "atlanan": len(atlanan)}
