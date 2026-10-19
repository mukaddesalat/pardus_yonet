"""M2-S3 Görünüm ve Giriş: ortak Windows 10 benzeri Pardus görünümü, standart
duvar kâğıdı, ekran kilidi, öğrenci otomatik girişi ve yönetim hesabını giriş
ekranında gizleme (karar 14, 23).

Asıl iş öğrenci PC'de uzak/gorunum.py betiğindedir: düzen tanımı hedefteki Pardus
Karşılayıcı dosyasından okunur ve her anahtar kurulu şemaya göre denetlenir.
Önizleme salt okunurdur; açık öğrenci oturumu varsa öğretmen önizlemede bunu
görür (kilitli ayarlar açık oturumda hemen değişebilir) — sessiz değişiklik yoktur.
XFCE bilgisayarlarda görünüm uygulanmaz; GNOME geçişi ayrı plan ve onay ister.
"""

import asyncio
import base64

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

GORSEL_YOLU = ayarlar.VERI_DIZINI / "duvar_kagidi"
SECENEKLER = ("duzen", "duvar", "ekran_kilidi", "otomatik_giris", "gizle")


def secenekleri_dogrula(secenekler: dict) -> dict:
    temiz = {}
    for ad in SECENEKLER:
        deger = secenekler.get(ad)
        if deger in (None, "", False):
            continue
        if deger not in ("uygula", "kaldir"):
            raise ValueError(f"Geçersiz seçenek değeri: {ad}={deger!r}")
        temiz[ad] = deger
    if not temiz:
        raise ValueError("En az bir görünüm/giriş seçeneği işaretleyin")
    temiz["kilit"] = bool(secenekler.get("kilit", True))
    if temiz.get("duvar") == "uygula" and gorsel_bilgi() is None:
        raise ValueError("Önce duvar kâğıdı görselini yükleyin")
    return temiz


def gorsel_kaydet(icerik_b64: str, uzanti: str) -> int:
    veri = base64.b64decode(icerik_b64)
    if len(veri) > 20 * 1048576:
        raise ValueError("Görsel 20 MB sınırını aşıyor")
    if not (veri.startswith(b"\x89PNG") or veri.startswith(b"\xff\xd8\xff")):
        raise ValueError("Yalnızca PNG veya JPEG kabul edilir")
    GORSEL_YOLU.mkdir(parents=True, exist_ok=True)
    for eski in GORSEL_YOLU.glob("duvar.*"):
        eski.unlink()
    (GORSEL_YOLU / f"duvar{uzanti}").write_bytes(veri)
    return len(veri)


def gorsel_bilgi() -> dict | None:
    for dosya in GORSEL_YOLU.glob("duvar.*") if GORSEL_YOLU.exists() else []:
        return {"ad": dosya.name, "bayt": dosya.stat().st_size}
    return None


async def gorunum_isi(is_id: str, cihaz_idler: list[str], secenekler: dict, kip: str,
                      iptal: asyncio.Event) -> None:
    """kip: 'onizle' (salt okunur) veya 'uygula'."""
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or iptal.is_set():
            return
        neden = secim.uygunluk(cihaz, "gorunum")  # XFCE/korunan/hazır olmayan: atlanır
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}",
                                      {"cihaz_id": cid, "ad": veritabani.cihaz_adi(cihaz)})
            return
        async with sinir:
            await asyncio.to_thread(_calistir, is_id, cihaz, secenekler, kip)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


OGE_ADLARI = {"duzen": "Windows 10 benzeri düzen", "duvar": "Duvar kâğıdı",
              "ekran_kilidi": "Ekran kilidi kapalı", "otomatik_giris": "Öğrenci otomatik girişi",
              "gizle": "Yönetim hesabını gizle"}
DURUM_ADLARI = {"uygulanacak": "uygulanacak", "kaldirilacak": "kaldırılacak", "zaten": "zaten öyle",
                "zaten_yok": "zaten yok", "uygulandi": "uygulandı", "kaldirildi": "kaldırıldı",
                "desteklenmiyor": "desteklenmiyor", "hata": "HATA"}


def _calistir(is_id: str, cihaz: dict, secenekler: dict, kip: str) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", kip, f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}")
        return
    try:
        parametre = {"kip": kip, "secenekler": secenekler, "profil": ayarlar.PROFIL_HESABI,
                     "yonetim_hesabi": cihaz["baglanti_hesabi"]}
        if kip == "uygula" and secenekler.get("duvar") == "uygula":
            yerel = next(GORSEL_YOLU.glob("duvar.*"))
            rc, klasor, _ = ssh_araclari.komut(istemci, ["mktemp", "-d", "/tmp/psy-duvar-XXXXXXXX"])
            gecici = f"{klasor.strip()}/duvar{yerel.suffix}"
            sftp = istemci.open_sftp()
            try:
                sftp.put(str(yerel), gecici)
            finally:
                sftp.close()
            parametre.update(duvar_gecici=gecici, duvar_uzanti=yerel.suffix)
        sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("gorunum"), parametre, zaman=180)
        if "hata" in sonuc:
            raise RuntimeError(sonuc["hata"])
        veri.update(sonuc)
        parcalar, hata_var = [], False
        for oge, bilgi in sonuc["ogeler"].items():
            metin = f"{OGE_ADLARI.get(oge, oge)}: {DURUM_ADLARI.get(bilgi['durum'], bilgi['durum'])}"
            if bilgi.get("ayrinti"):
                metin += f" ({bilgi['ayrinti']})"
            if bilgi.get("karsilayici"):
                metin += f"; Pardus Karşılayıcı: {bilgi['karsilayici']}"
            if bilgi.get("atlanan"):
                metin += f" [{len(bilgi['atlanan'])} anahtar kurulu şemada olmadığı için atlandı]"
            parcalar.append(metin)
            hata_var |= bilgi["durum"] == "hata"
        if sonuc["ortam"].get("ogrenci_oturumu"):
            parcalar.append("UYARI: öğrenci oturumu açık — kilitli ayarlar bu oturumda hemen "
                            "değişebilir; düzenin tamamı sonraki girişte görünür")
        if kip == "uygula":
            yeni = {}
            if "duzen" in sonuc["ogeler"] and sonuc["ogeler"]["duzen"]["durum"] in ("uygulandi", "kaldirildi"):
                yeni["gorunum_durumu"] = "uygulandi" if secenekler["duzen"] == "uygula" else "yok"
            gz = sonuc["ogeler"].get("gizle")
            if gz and gz.get("mevcut"):
                m = gz["mevcut"]
                yeni["gizleme_durumu"] = ("gizli" if m["sistem_hesabi"] and m["listede"] is False else
                                          "yapilandirildi" if m["sistem_hesabi"] else "gorunur")
            og = sonuc["ogeler"].get("otomatik_giris")
            if og and og.get("mevcut"):
                yeni["otomatik_giris"] = og["mevcut"].get("hesap") or "kapali"
            if yeni:
                veritabani.cihaz_guncelle(cihaz["id"], son_kontrol=veritabani.simdi(), **yeni)
        veritabani.hedef_guncelle(is_id, ip, "basarisiz" if hata_var else "basarili", "tamam",
                                  f"{ad} — " + "; ".join(parcalar), veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", kip, f"{ad} — {hata}", veri)
    finally:
        istemci.close()
