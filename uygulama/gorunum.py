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
import json
import re
import secrets
import shutil
import struct
import time
import zlib
from pathlib import Path

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

GORSEL_YOLU = ayarlar.VERI_DIZINI / "duvar_kagidi"
GALERI_DIZINI = GORSEL_YOLU / "galeri"
GALERI_JSON = GORSEL_YOLU / "galeri.json"
SECENEKLER = ("duzen", "duvar", "ekran_kilidi", "otomatik_giris", "gizle")
KOSE_SECENEKLERI = ("sag_ust", "sol_ust", "yok")

HAZIR_SABLONLAR = (
    ("hazir_pardus_gece", "Pardus Gece Mavisi (Hazır)", (15, 23, 42), (30, 58, 138), (56, 189, 248)),
    ("hazir_anadolu_turkuaz", "Anadolu Turkuazı (Hazır)", (13, 59, 76), (15, 118, 110), (45, 212, 191)),
    ("hazir_bilisim_mor", "Bilişim Atölyesi (Hazır)", (30, 27, 75), (76, 29, 149), (192, 132, 252)),
)


def _png_parca(tur: bytes, veri: bytes) -> bytes:
    return struct.pack(">I", len(veri)) + tur + veri + struct.pack(">I", zlib.crc32(tur + veri) & 0xFFFFFFFF)


def _hazir_png_uret(ust: tuple[int, int, int], alt: tuple[int, int, int],
                    vurgu: tuple[int, int, int], gen: int = 1280, yuk: int = 720) -> bytes:
    """Harici kütüphane gerektirmeden pürüzsüz kurumsal degrade PNG üretir."""
    satirlar = []
    for y in range(yuk):
        t = y / max(1, yuk - 1)
        r = int(ust[0] * (1 - t) + alt[0] * t)
        g = int(ust[1] * (1 - t) + alt[1] * t)
        b = int(ust[2] * (1 - t) + alt[2] * t)
        # Alt kısımda ince modern vurgu şeridi
        if yuk - 14 <= y <= yuk - 8:
            r, g, b = vurgu
        satirlar.append(b"\x00" + bytes((r, g, b)) * gen)
    ihdr = struct.pack(">IIBBBBB", gen, yuk, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"".join(satirlar), level=1)
    return b"\x89PNG\r\n\x1a\n" + _png_parca(b"IHDR", ihdr) + _png_parca(b"IDAT", idat) + _png_parca(b"IEND", b"")


def _galeri_hazirla() -> dict:
    GALERI_DIZINI.mkdir(parents=True, exist_ok=True)
    veri = {"secili_id": None, "ogeler": []}
    if GALERI_JSON.exists():
        try:
            veri = json.loads(GALERI_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            veri = {"secili_id": None, "ogeler": []}
    mevcut_idler = {o.get("id") for o in veri.get("ogeler") or []}
    degisti = False
    for sablon_id, ad, ust, alt, vurgu in HAZIR_SABLONLAR:
        dosya = GALERI_DIZINI / f"{sablon_id}.png"
        if not dosya.exists():
            dosya.write_bytes(_hazir_png_uret(ust, alt, vurgu))
            degisti = True
        if sablon_id not in mevcut_idler:
            veri.setdefault("ogeler", []).append({
                "id": sablon_id,
                "ad": ad,
                "dosya": f"{sablon_id}.png",
                "uzanti": ".png",
                "hazir": True,
                "zaman": "Hazır Şablon",
            })
            degisti = True
    # Var olmayan dosyaları temizle
    gecerli = []
    for o in veri.get("ogeler") or []:
        yol = GALERI_DIZINI / o.get("dosya", "")
        if yol.is_file():
            gecerli.append(o)
        else:
            degisti = True
    veri["ogeler"] = gecerli
    # Eğer eski tekil duvar.* varsa ve galeride seçili bir şey yoksa ya da ilk geçişse
    mevcut_aktif = list(GORSEL_YOLU.glob("duvar.*"))
    if not veri.get("secili_id") or not any(o["id"] == veri["secili_id"] for o in gecerli):
        veri["secili_id"] = gecerli[0]["id"] if gecerli else None
        degisti = True
    if not mevcut_aktif and veri.get("secili_id"):
        secili_oge = next((o for o in gecerli if o["id"] == veri["secili_id"]), None)
        if secili_oge:
            shutil.copy2(GALERI_DIZINI / secili_oge["dosya"], GORSEL_YOLU / f"duvar{secili_oge['uzanti']}")
    if degisti:
        GALERI_JSON.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return veri


def galeri_listele() -> dict:
    veri = _galeri_hazirla()
    secili_id = veri.get("secili_id")
    ogeler = []
    for o in veri.get("ogeler") or []:
        yol = GALERI_DIZINI / o["dosya"]
        if not yol.is_file():
            continue
        ogeler.append({
            "id": o["id"],
            "ad": o["ad"],
            "baslik": o["ad"],
            "uzanti": o["uzanti"],
            "bayt": yol.stat().st_size,
            "hazir": bool(o.get("hazir")),
            "secili": o["id"] == secili_id,
            "zaman": o.get("zaman"),
            "url": f"/api/duvar-kagidi/galeri/{o['id']}/indir",
            "onizleme_url": f"/api/duvar-kagidi/galeri/{o['id']}/indir",
        })
    return {"secili_id": secili_id, "ogeler": ogeler, "gorsel": gorsel_bilgi()}


def galeri_dosya_yolu(oge_id: str) -> Path | None:
    if not re.match(r"^[A-Za-z0-9_-]{3,64}$", oge_id or ""):
        return None
    veri = _galeri_hazirla()
    oge = next((o for o in veri.get("ogeler") or [] if o["id"] == oge_id), None)
    if not oge:
        return None
    yol = GALERI_DIZINI / oge["dosya"]
    return yol if yol.is_file() else None


def galeri_sec(oge_id: str) -> dict:
    veri = _galeri_hazirla()
    oge = next((o for o in veri.get("ogeler") or [] if o["id"] == oge_id), None)
    if not oge:
        raise ValueError("Galeride böyle bir duvar kâğıdı bulunamadı")
    kaynak = GALERI_DIZINI / oge["dosya"]
    if not kaynak.is_file():
        raise ValueError("Duvar kâğıdı dosyası bulunamadı")
    for eski in GORSEL_YOLU.glob("duvar.*"):
        eski.unlink()
    shutil.copy2(kaynak, GORSEL_YOLU / f"duvar{oge['uzanti']}")
    veri["secili_id"] = oge_id
    GALERI_JSON.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return galeri_listele()


def galeri_ekle(icerik_b64: str, uzanti: str, ad: str | None = None) -> dict:
    uzanti = ".png" if (uzanti or "").lower() == ".png" else ".jpg"
    ham = base64.b64decode(icerik_b64)
    if len(ham) > 20 * 1048576:
        raise ValueError("Görsel 20 MB sınırını aşıyor")
    if not (ham.startswith(b"\x89PNG") or ham.startswith(b"\xff\xd8\xff")):
        raise ValueError("Yalnızca PNG veya JPEG kabul edilir")
    veri = _galeri_hazirla()
    yeni_id = f"galeri_{int(time.time())}_{secrets.token_hex(3)}"
    dosya_adi = f"{yeni_id}{uzanti}"
    temiz_ad = re.sub(r"[\x00-\x1f/\\]", "", (ad or "").strip())[:60] or f"Fotoğraf ({time.strftime('%d.%m %H:%M')})"
    (GALERI_DIZINI / dosya_adi).write_bytes(ham)
    veri.setdefault("ogeler", []).insert(0, {
        "id": yeni_id,
        "ad": temiz_ad,
        "dosya": dosya_adi,
        "uzanti": uzanti,
        "hazir": False,
        "zaman": time.strftime("%Y-%m-%d %H:%M"),
    })
    veri["secili_id"] = yeni_id
    GALERI_JSON.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    for eski in GORSEL_YOLU.glob("duvar.*"):
        eski.unlink()
    (GORSEL_YOLU / f"duvar{uzanti}").write_bytes(ham)
    return galeri_listele()


def galeri_sil(oge_id: str) -> dict:
    veri = _galeri_hazirla()
    oge = next((o for o in veri.get("ogeler") or [] if o["id"] == oge_id), None)
    if not oge:
        raise ValueError("Görsel bulunamadı")
    if oge.get("hazir"):
        raise ValueError("Hazır şablon görseller silinemez")
    yol = GALERI_DIZINI / oge["dosya"]
    if yol.exists():
        yol.unlink()
    veri["ogeler"] = [o for o in veri.get("ogeler") or [] if o["id"] != oge_id]
    if veri.get("secili_id") == oge_id:
        veri["secili_id"] = veri["ogeler"][0]["id"] if veri["ogeler"] else None
        if veri["secili_id"]:
            yeni_secili = veri["ogeler"][0]
            for eski in GORSEL_YOLU.glob("duvar.*"):
                eski.unlink()
            shutil.copy2(GALERI_DIZINI / yeni_secili["dosya"], GORSEL_YOLU / f"duvar{yeni_secili['uzanti']}")
    GALERI_JSON.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return galeri_listele()


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
    kose = secenekler.get("duvar_kose") or "sag_ust"
    temiz["duvar_kose"] = kose if kose in KOSE_SECENEKLERI else "sag_ust"
    if secenekler.get("duvar_id"):
        galeri_sec(str(secenekler["duvar_id"]))
        temiz["duvar_id"] = str(secenekler["duvar_id"])
    if temiz.get("duvar") == "uygula":
        if gorsel_bilgi() is None:
            _galeri_hazirla()
        if gorsel_bilgi() is None:
            raise ValueError("Önce duvar kâğıdı görselini seçin veya yükleyin")
    return temiz


def gorsel_kaydet(icerik_b64: str, uzanti: str, ad: str | None = None) -> int:
    veri = base64.b64decode(icerik_b64)
    galeri_ekle(icerik_b64, uzanti, ad=ad)
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
                     "yonetim_hesabi": cihaz["baglanti_hesabi"],
                     "cihaz_hostname": cihaz.get("hostname") or "",
                     "cihaz_etiket": cihaz.get("etiket") or "",
                     "duvar_kose": secenekler.get("duvar_kose", "sag_ust")}
        if kip == "uygula" and secenekler.get("duvar") == "uygula":
            if not list(GORSEL_YOLU.glob("duvar.*")):
                _galeri_hazirla()
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
