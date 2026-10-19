"""Ödevler: oluşturma, durum geçişleri, takip ve indirme (yönetim paneli tarafı; istem §3).

Durumlar: taslak -> acik <-> kapali -> arsiv. Arşivleme silme değildir; silme
yalnız arşivdeki ödev için ve açık onayla yapılır. Takip, yükleme yapanlara
değil sınıf listesine dayanır.
"""

import json
import queue
import re
import shutil
import threading
import zipfile
from pathlib import Path

from . import kurallar, ortak, siniflar, teslim, vt

DURUMLAR = {"taslak": "Taslak", "acik": "Teslime açık", "kapali": "Teslime kapalı",
            "arsiv": "Arşivlendi"}
GECISLER = {  # eylem -> (izinli kaynak durumlar, hedef)
    "ac": ({"taslak", "kapali"}, "acik"),
    "kapat": ({"acik"}, "kapali"),
    "arsivle": ({"taslak", "kapali"}, "arsiv"),
    "arsivden_cikar": ({"arsiv"}, "kapali"),
}
AKTIF_YUKLEME_SN = 15 * 60   # bu süre içinde etkinlik yoksa "yükleme sürüyor" sayılmaz


class OdevHatasi(ValueError):
    """Öğretmene olduğu gibi gösterilebilecek hata."""


# ---------------------------------------------------------------- oluşturma

def _dogrula(girdi: dict) -> dict:
    baslik = re.sub(r"\s+", " ", str(girdi.get("baslik", "")).strip())
    if not 1 <= len(baslik) <= 120:
        raise OdevHatasi("Başlık 1–120 karakter olmalı")
    sinif_id = girdi.get("sinif_id")
    if not vt.tek("SELECT 1 FROM sinif WHERE id=?", (sinif_id,)):
        raise OdevHatasi("Sınıf seçin")
    yonerge = str(girdi.get("yonerge", "")).strip()
    if len(yonerge) > 4000:
        raise OdevHatasi("Yönerge en çok 4000 karakter olabilir")
    try:
        son_tarih = ortak.yerelden_utc(girdi.get("son_tarih") or None)
    except ValueError:
        raise OdevHatasi("Geçersiz son teslim tarihi")
    turler = [t for t in girdi.get("turler", []) if t in kurallar.KATEGORILER]
    try:
        ek = kurallar.ek_uzantilari_dogrula(list(girdi.get("ek_uzantilar", [])))
    except kurallar.KuralHatasi as hata:
        raise OdevHatasi(str(hata))
    if not turler and not ek:
        raise OdevHatasi("En az bir dosya türü seçin")
    try:
        en_fazla_dosya = int(girdi.get("en_fazla_dosya", ortak.VARSAYILAN_EN_FAZLA_DOSYA))
        en_fazla_mb = int(girdi.get("en_fazla_mb", ortak.VARSAYILAN_EN_FAZLA_MB))
    except (TypeError, ValueError):
        raise OdevHatasi("Dosya sayısı ve boyut sınırı sayı olmalı")
    if not 1 <= en_fazla_dosya <= ortak.EN_FAZLA_DOSYA_SINIRI:
        raise OdevHatasi(f"Dosya sayısı 1–{ortak.EN_FAZLA_DOSYA_SINIRI} arasında olmalı")
    if not 1 <= en_fazla_mb <= ortak.EN_FAZLA_MB_SINIRI:
        raise OdevHatasi(f"Boyut sınırı 1–{ortak.EN_FAZLA_MB_SINIRI} MB arasında olmalı")
    return {"baslik": baslik, "sinif_id": sinif_id, "yonerge": yonerge, "son_tarih": son_tarih,
            "gec_teslim": int(bool(girdi.get("gec_teslim"))), "turler": json.dumps(turler),
            "ek_uzantilar": json.dumps(ek), "en_fazla_dosya": en_fazla_dosya,
            "en_fazla_bayt": en_fazla_mb * 1048576,
            "klasor_izni": int(bool(girdi.get("klasor_izni", True)))}


def olustur(girdi: dict) -> str:
    alanlar = _dogrula(girdi)
    kimlik, simdi = vt.yeni_kimlik(), ortak.simdi_iso()
    alanlar.update(id=kimlik, durum="taslak", olusturma=simdi, guncelleme=simdi)
    sutunlar = ", ".join(alanlar)
    vt.calistir(f"INSERT INTO odev({sutunlar}) VALUES({', '.join('?' * len(alanlar))})",
                tuple(alanlar.values()))
    return kimlik


def guncelle(odev_id: str, girdi: dict) -> None:
    odev = _odev(odev_id)
    if odev["durum"] == "arsiv":
        raise OdevHatasi("Arşivdeki ödev düzenlenemez; önce arşivden çıkarın")
    alanlar = _dogrula(girdi)
    if alanlar["sinif_id"] != odev["sinif_id"] and _teslim_var_mi(odev_id):
        raise OdevHatasi("Teslim alınmış ödevin sınıfı değiştirilemez")
    alanlar["guncelleme"] = ortak.simdi_iso()
    atama = ", ".join(f"{ad}=?" for ad in alanlar)
    vt.calistir(f"UPDATE odev SET {atama} WHERE id=?", (*alanlar.values(), odev_id))


def durum_degistir(odev_id: str, eylem: str) -> str:
    if eylem not in GECISLER:
        raise OdevHatasi("Geçersiz işlem")
    kaynaklar, hedef = GECISLER[eylem]
    odev = _odev(odev_id)
    if odev["durum"] not in kaynaklar:
        raise OdevHatasi(f"'{DURUMLAR[odev['durum']]}' durumundaki ödev için bu işlem yapılamaz")
    vt.calistir("UPDATE odev SET durum=?, guncelleme=? WHERE id=?",
                (hedef, ortak.simdi_iso(), odev_id))
    # Kapatılan/arşivlenen ödevde süren aktarımlar teslim sayılmaz; portal da her
    # dosyada ve tamamlamada durumu yeniden denetler.
    if hedef != "acik":
        for t in vt.sorgula("SELECT id FROM teslim WHERE odev_id=? AND durum='yukleniyor'",
                            (odev_id,)):
            vt.calistir("UPDATE teslim SET durum='yarim', hata=?, bitis=? WHERE id=? "
                        "AND durum='yukleniyor'",
                        ("öğretmen teslimleri kapattı", ortak.simdi_iso(), t["id"]))
    return hedef


def sil(odev_id: str) -> None:
    """Yalnız arşivdeki ödev; teslim dosyaları da silinir (geri alınamaz)."""
    odev = _odev(odev_id)
    if odev["durum"] != "arsiv":
        raise OdevHatasi("Yalnız arşivlenmiş ödev silinebilir")
    with vt.islem() as baglanti:
        baglanti.execute("DELETE FROM teslim_dosya WHERE teslim_id IN "
                         "(SELECT id FROM teslim WHERE odev_id=?)", (odev_id,))
        baglanti.execute("DELETE FROM teslim WHERE odev_id=?", (odev_id,))
        baglanti.execute("DELETE FROM odev WHERE id=?", (odev_id,))
    shutil.rmtree(ortak.yollar()["teslimler"] / odev_id, ignore_errors=True)


def _odev(odev_id: str) -> dict:
    odev = vt.tek("SELECT * FROM odev WHERE id=?", (odev_id,))
    if not odev:
        raise OdevHatasi("Ödev bulunamadı")
    return odev


def _teslim_var_mi(odev_id: str) -> bool:
    return bool(vt.tek("SELECT 1 FROM teslim WHERE odev_id=? AND durum='tamamlandi' LIMIT 1",
                       (odev_id,)))


# ---------------------------------------------------------------- listeleme ve takip

def liste() -> list[dict]:
    sonuc = []
    for o in vt.sorgula(
            "SELECT o.*, s.ad AS sinif, "
            "(SELECT COUNT(*) FROM ogrenci WHERE sinif_id=o.sinif_id) AS ogrenci_sayisi, "
            "(SELECT COUNT(DISTINCT ogrenci_id) FROM teslim t JOIN ogrenci g ON g.id=t.ogrenci_id "
            " WHERE t.odev_id=o.id AND t.durum='tamamlandi' AND g.sinif_id=o.sinif_id) "
            "  AS teslim_eden "
            "FROM odev o JOIN sinif s ON s.id=o.sinif_id ORDER BY o.olusturma DESC"):
        sonuc.append({"id": o["id"], "baslik": o["baslik"], "sinif": o["sinif"],
                      "durum": o["durum"], "durum_adi": DURUMLAR[o["durum"]],
                      "son_tarih": ortak.yerel_metin(o["son_tarih"]) or None,
                      "ogrenci_sayisi": o["ogrenci_sayisi"], "teslim_eden": o["teslim_eden"]})
    return sonuc


def detay(odev_id: str) -> dict:
    odev = _odev(odev_id)
    sinif = vt.tek("SELECT ad FROM sinif WHERE id=?", (odev["sinif_id"],))
    teslimler = vt.sorgula("SELECT * FROM teslim WHERE odev_id=? ORDER BY baslangic",
                           (odev_id,))
    ogrenciye_gore: dict[str, list[dict]] = {}
    for t in teslimler:
        ogrenciye_gore.setdefault(t["ogrenci_id"], []).append(t)

    aktif_sinir = ortak.simdi().timestamp() - AKTIF_YUKLEME_SN
    satirlar, sayilar = [], {"alindi": 0, "gec": 0, "etmedi": 0, "yukleniyor": 0, "hata": 0}
    for ogr in siniflar.ogrenciler(odev["sinif_id"]):
        kendi = ogrenciye_gore.get(ogr["id"], [])
        tamam = sorted((t for t in kendi if t["durum"] == "tamamlandi"),
                       key=lambda t: t["surum"], reverse=True)
        aktif = [t for t in kendi if t["durum"] == "yukleniyor"
                 and ortak.iso_oku(t["son_etkinlik"]).timestamp() >= aktif_sinir]
        son_deneme = kendi[-1] if kendi else None
        if aktif:
            durum = "yukleniyor"
        elif tamam:
            durum = "gec" if tamam[0]["gec"] else "alindi"
        elif son_deneme and son_deneme["durum"] == "yarim":
            durum = "hata"
        else:
            durum = "etmedi"
        sayilar[durum] += 1
        son = tamam[0] if tamam else None
        satirlar.append({
            "ogrenci_id": ogr["id"], "numara": ogr["numara"], "ad_soyad": ogr["ad_soyad"],
            "durum": durum,
            "son_hata": (son_deneme["hata"] if son_deneme and son_deneme["durum"] == "yarim"
                         else None),
            "son_zaman": ortak.yerel_metin(son["bitis"]) if son else None,
            "surum": son["surum"] if son else None,
            "dosya_sayisi": son["dosya_sayisi"] if son else None,
            "toplam_bayt": son["toplam_bayt"] if son else None,
            "teslimler": [{"id": t["id"], "teslim_no": teslim.teslim_no(t["id"]),
                           "surum": t["surum"], "zaman": ortak.yerel_metin(t["bitis"]),
                           "gec": bool(t["gec"]), "dosya_sayisi": t["dosya_sayisi"],
                           "toplam_bayt": t["toplam_bayt"]} for t in tamam],
        })
    teslim_eden = sayilar["alindi"] + sayilar["gec"]
    return {
        "odev": {**{k: odev[k] for k in ("id", "baslik", "yonerge", "sinif_id", "durum",
                                           "en_fazla_dosya", "klasor_izni", "gec_teslim")},
                 "sinif": sinif["ad"], "durum_adi": DURUMLAR[odev["durum"]],
                 "son_tarih": ortak.yerel_metin(odev["son_tarih"]) or None,
                 "son_tarih_giris": ortak.utcden_yerel_giris(odev["son_tarih"]),
                 "turler": json.loads(odev["turler"]),
                 "ek_uzantilar": json.loads(odev["ek_uzantilar"]),
                 "en_fazla_mb": odev["en_fazla_bayt"] // 1048576,
                 "klasor_izni": bool(odev["klasor_izni"]),
                 "gec_teslim": bool(odev["gec_teslim"])},
        "ogrenciler": satirlar,
        "ozet": {**sayilar, "toplam": len(satirlar), "teslim_eden": teslim_eden,
                 "tamami_teslim_etti": bool(satirlar) and teslim_eden == len(satirlar)},
    }


def teslim_dosyalari(teslim_id: str) -> list[dict]:
    if not vt.tek("SELECT 1 FROM teslim WHERE id=? AND durum='tamamlandi'", (teslim_id,)):
        raise OdevHatasi("Teslim bulunamadı")
    return vt.sorgula("SELECT sira, goreli_yol, boyut, sha256 FROM teslim_dosya "
                      "WHERE teslim_id=? ORDER BY sira", (teslim_id,))


# ---------------------------------------------------------------- indirme

def guvenli_ad(ad: str) -> str:
    """Windows/Linux'ta sorunsuz açılacak ZIP bileşeni."""
    ad = re.sub(r'[\x00-\x1f\x7f\\/:*?"<>|]', "_", ad).strip().rstrip(". ")
    return (ad or "_")[:120]


def _disk_yolu(t: dict, depo_adi: str) -> Path:
    return ortak.yollar()["teslimler"] / t["odev_id"] / t["id"] / depo_adi


def tek_dosya(teslim_id: str, sira: int) -> tuple[Path, str]:
    t = vt.tek("SELECT * FROM teslim WHERE id=? AND durum='tamamlandi'", (teslim_id,))
    d = vt.tek("SELECT * FROM teslim_dosya WHERE teslim_id=? AND sira=?", (teslim_id, sira))
    if not t or not d:
        raise OdevHatasi("Dosya bulunamadı")
    return _disk_yolu(t, d["depo_adi"]), d["goreli_yol"].rsplit("/", 1)[-1]


def zip_girdileri(odev_id: str, ogrenci_idler: list[str] | None,
                  tum_surumler: bool) -> tuple[str, list[tuple[Path, str]]]:
    """ZIP içeriği: <sınıf>/<numara> <ad>/Teslim <n>/<özgün göreli yol>.

    Varsayılan olarak her öğrencinin yalnız son tamamlanmış teslimi alınır.
    Öğrenci ve sürüm klasörleri aynı adlı dosyaların çakışmasını önler.
    """
    odev = _odev(odev_id)
    sinif = vt.tek("SELECT ad FROM sinif WHERE id=?", (odev["sinif_id"],))["ad"]
    ogrenciler = siniflar.ogrenciler(odev["sinif_id"])
    if ogrenci_idler:
        secili = set(ogrenci_idler)
        ogrenciler = [o for o in ogrenciler if o["id"] in secili]
    girdiler = []
    for ogr in ogrenciler:
        tamam = vt.sorgula("SELECT * FROM teslim WHERE odev_id=? AND ogrenci_id=? "
                           "AND durum='tamamlandi' ORDER BY surum DESC", (odev_id, ogr["id"]))
        for t in (tamam if tum_surumler else tamam[:1]):
            kok = (f"{guvenli_ad(sinif)}/{guvenli_ad(ogr['numara'] + ' ' + ogr['ad_soyad'])}/"
                   f"Teslim {t['surum']}{' (geç)' if t['gec'] else ''}")
            for d in vt.sorgula("SELECT * FROM teslim_dosya WHERE teslim_id=? ORDER BY sira",
                                (t["id"],)):
                ic_yol = "/".join(guvenli_ad(p) for p in d["goreli_yol"].split("/"))
                girdiler.append((_disk_yolu(t, d["depo_adi"]), f"{kok}/{ic_yol}"))
    if not girdiler:
        raise OdevHatasi("İndirilecek tamamlanmış teslim yok")
    return f"{guvenli_ad(odev['baslik'])} - {guvenli_ad(sinif)}.zip", girdiler


def teslim_zip_girdileri(teslim_id: str) -> tuple[str, list[tuple[Path, str]]]:
    t = vt.tek("SELECT t.*, g.numara, g.ad_soyad FROM teslim t JOIN ogrenci g "
               "ON g.id=t.ogrenci_id WHERE t.id=? AND t.durum='tamamlandi'", (teslim_id,))
    if not t:
        raise OdevHatasi("Teslim bulunamadı")
    kok = guvenli_ad(f"{t['numara']} {t['ad_soyad']} - Teslim {t['surum']}")
    girdiler = [(_disk_yolu(t, d["depo_adi"]),
                 f"{kok}/" + "/".join(guvenli_ad(p) for p in d["goreli_yol"].split("/")))
                for d in vt.sorgula("SELECT * FROM teslim_dosya WHERE teslim_id=? ORDER BY sira",
                                    (teslim_id,))]
    return f"{kok}.zip", girdiler


class _KuyrukYazici:
    """zipfile'ın yazdığı baytları üreteçe aktaran, konumlanamayan çıktı."""

    def __init__(self, kuyruk: queue.Queue, durdur: threading.Event):
        self.kuyruk, self.durdur = kuyruk, durdur

    def write(self, veri) -> int:
        veri = bytes(veri)
        while not self.durdur.is_set():
            try:
                self.kuyruk.put(veri, timeout=1)
                return len(veri)
            except queue.Full:
                continue
        raise OSError("indirme iptal edildi")

    def flush(self) -> None:
        pass


def zip_akisi(girdiler: list[tuple[Path, str]]):
    """ZIP'i belleğe veya diske biriktirmeden parça parça üretir."""
    kuyruk: queue.Queue = queue.Queue(maxsize=32)
    durdur = threading.Event()

    def koy(oge) -> None:
        while not durdur.is_set():
            try:
                kuyruk.put(oge, timeout=1)
                return
            except queue.Full:
                continue

    def uret():
        try:
            with zipfile.ZipFile(_KuyrukYazici(kuyruk, durdur), "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=6) as zf:
                for yol, ad in girdiler:
                    zf.write(yol, ad)
            koy(None)
        except BaseException as hata:  # noqa: BLE001 — hata üretece taşınır
            koy(hata)

    threading.Thread(target=uret, daemon=True).start()
    try:
        while True:
            parca = kuyruk.get()
            if parca is None:
                return
            if isinstance(parca, BaseException):
                raise parca
            yield parca
    finally:
        durdur.set()
