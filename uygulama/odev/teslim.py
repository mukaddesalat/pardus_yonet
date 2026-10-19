"""Teslim yaşam döngüsü (öğrenci portalı tarafı; istem §5–6).

Akış: baslat (dosya listesi bildirilir, sunucu doğrular ve teslim kimliği verir)
-> dosya_yaz (her dosya akış halinde diske; boyut + sha256 + içerik imzası)
-> tamamla (idempotent; sürüm numarası kilit altında atanır, klasör tek adımda
kalıcı alana taşınır). "Teslim alındı" yalnız tamamla başarılıysa döner.

Disk düzeni (öğrencinin gönderdiği ad veya numara asla yol olarak kullanılmaz):
    gecici/<teslim_id>/<sira>             yükleme sürerken
    teslimler/<odev_id>/<teslim_id>/<sira> tamamlanınca
"""

import asyncio
import errno
import hashlib
import json
import os
import shutil
from pathlib import Path

from . import kurallar, ortak, vt

YAZMA_PARALELLIGI = asyncio.Semaphore(12)   # 21–40 öğrenci için sınırlı eşzamanlı disk yazımı
TAMPON = 1024 * 1024


class TeslimHatasi(Exception):
    def __init__(self, mesaj: str, kod: int = 409):
        super().__init__(mesaj)
        self.mesaj, self.kod = mesaj, kod


def _gecici(teslim_id: str) -> Path:
    return ortak.yollar()["gecici"] / teslim_id


def _kalici(odev_id: str, teslim_id: str) -> Path:
    return ortak.yollar()["teslimler"] / odev_id / teslim_id


def teslim_no(teslim_id: str) -> str:
    return f"{teslim_id[:4]}-{teslim_id[4:8]}".upper()


def teslime_uygun(odev: dict) -> tuple[bool, bool, str]:
    """(kabul edilir mi, geç teslim mi, red nedeni) — sunucu saatine göre."""
    if odev["durum"] != "acik":
        return False, False, "Bu ödev teslime kapalı."
    son = ortak.iso_oku(odev["son_tarih"])
    if son and ortak.simdi() > son:
        if odev["gec_teslim"]:
            return True, True, ""
        return False, False, "Teslim süresi doldu. Öğretmeninizden yeniden açmasını isteyin."
    return True, False, ""


def _odev(ogrenci: dict, odev_id: str) -> dict:
    """Öğrencinin kendi sınıfına ait ödev; değilse varlığı da açığa vurulmaz."""
    odev = vt.tek("SELECT * FROM odev WHERE id=? AND sinif_id=?", (odev_id, ogrenci["sinif_id"]))
    if not odev or odev["durum"] in ("taslak", "arsiv"):
        raise TeslimHatasi("Ödev bulunamadı.", 404)
    return odev


def _teslim(ogrenci: dict, teslim_id: str) -> dict:
    teslim = vt.tek("SELECT * FROM teslim WHERE id=? AND ogrenci_id=?", (teslim_id, ogrenci["id"]))
    if not teslim:
        raise TeslimHatasi("Teslim bulunamadı.", 404)
    return teslim


def _yarim_yap(teslim_id: str, neden: str) -> None:
    vt.calistir("UPDATE teslim SET durum='yarim', hata=?, bitis=? "
                "WHERE id=? AND durum='yukleniyor'", (neden, ortak.simdi_iso(), teslim_id))
    shutil.rmtree(_gecici(teslim_id), ignore_errors=True)


# ---------------------------------------------------------------- öğrenci görünümü

def _izinli(odev: dict) -> set[str]:
    return kurallar.izinli_uzantilar(json.loads(odev["turler"]), json.loads(odev["ek_uzantilar"]))


def ogrenci_odevleri(ogrenci: dict) -> list[dict]:
    """Yalnız öğrencinin kendi sınıfına açık ödevler ve kendi teslim özeti."""
    sonuc = []
    for odev in vt.sorgula("SELECT * FROM odev WHERE sinif_id=? AND durum='acik' "
                           "ORDER BY COALESCE(son_tarih, '9999'), olusturma",
                           (ogrenci["sinif_id"],)):
        kabul, gec, neden = teslime_uygun(odev)
        son = vt.tek("SELECT surum, bitis, gec, dosya_sayisi, toplam_bayt FROM teslim "
                     "WHERE odev_id=? AND ogrenci_id=? AND durum='tamamlandi' "
                     "ORDER BY surum DESC LIMIT 1", (odev["id"], ogrenci["id"]))
        son_tarih = ortak.iso_oku(odev["son_tarih"])
        sonuc.append({
            "id": odev["id"], "baslik": odev["baslik"], "yonerge": odev["yonerge"],
            "son_tarih": ortak.yerel_metin(odev["son_tarih"]) or None,
            "kalan_sn": int((son_tarih - ortak.simdi()).total_seconds()) if son_tarih else None,
            "gec_teslim": bool(odev["gec_teslim"]),
            "uzantilar": sorted(_izinli(odev)),
            "en_fazla_dosya": odev["en_fazla_dosya"], "en_fazla_bayt": odev["en_fazla_bayt"],
            "klasor_izni": bool(odev["klasor_izni"]),
            "kabul": kabul, "gec_olur": gec, "red_nedeni": neden,
            "son_teslim": ({"surum": son["surum"], "zaman": ortak.yerel_metin(son["bitis"]),
                            "gec": bool(son["gec"]), "dosya_sayisi": son["dosya_sayisi"],
                            "toplam_bayt": son["toplam_bayt"]} if son else None),
        })
    return sonuc


def ogrenci_teslimleri(ogrenci: dict, odev_id: str) -> list[dict]:
    """Öğrencinin bu ödevdeki tamamlanmış teslimleri ve dosya adları (yalnız kendisi)."""
    _odev(ogrenci, odev_id)
    sonuc = []
    for t in vt.sorgula(
            "SELECT id, surum, bitis, gec, dosya_sayisi, toplam_bayt FROM teslim "
            "WHERE odev_id=? AND ogrenci_id=? AND durum='tamamlandi' ORDER BY surum DESC",
            (odev_id, ogrenci["id"])):
        dosyalar = [d["goreli_yol"] for d in vt.sorgula(
            "SELECT goreli_yol FROM teslim_dosya WHERE teslim_id=? ORDER BY sira", (t["id"],))]
        sonuc.append({"teslim_no": teslim_no(t["id"]), "surum": t["surum"],
                      "zaman": ortak.yerel_metin(t["bitis"]), "gec": bool(t["gec"]),
                      "dosya_sayisi": t["dosya_sayisi"], "toplam_bayt": t["toplam_bayt"],
                      "dosyalar": dosyalar})
    return sonuc


# ---------------------------------------------------------------- yükleme

def baslat(ogrenci: dict, odev_id: str, dosyalar: list[dict], istemci_ip: str) -> dict:
    odev = _odev(ogrenci, odev_id)
    kabul, _, neden = teslime_uygun(odev)
    if not kabul:
        raise TeslimHatasi(neden)
    try:
        liste = kurallar.liste_dogrula(dosyalar, odev, _izinli(odev))
    except kurallar.KuralHatasi as hata:
        raise TeslimHatasi(str(hata), 422)
    toplam = sum(d["boyut"] for d in liste)
    kok = ortak.yollar()["gecici"]
    kok.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(kok).free < toplam + ortak.BOS_ALAN_PAYI:
        raise TeslimHatasi("Öğretmen bilgisayarında yeterli yer yok; teslim alınamıyor. "
                           "Öğretmeninize haber verin.", 507)

    teslim_id = vt.yeni_kimlik()
    simdi = ortak.simdi_iso()
    with vt.islem() as baglanti:
        # Aynı ödevde yarım kalmış önceki gönderim yenisiyle geçersiz olur.
        eskiler = [s[0] for s in baglanti.execute(
            "SELECT id FROM teslim WHERE odev_id=? AND ogrenci_id=? AND durum='yukleniyor'",
            (odev_id, ogrenci["id"])).fetchall()]
        baglanti.execute(
            "UPDATE teslim SET durum='yarim', hata='yeni gönderim başlatıldı', bitis=? "
            "WHERE odev_id=? AND ogrenci_id=? AND durum='yukleniyor'",
            (simdi, odev_id, ogrenci["id"]))
        baglanti.execute(
            "INSERT INTO teslim(id, odev_id, ogrenci_id, durum, dosya_sayisi, toplam_bayt, "
            "baslangic, son_etkinlik, istemci_ip) VALUES(?,?,?,'yukleniyor',?,?,?,?,?)",
            (teslim_id, odev_id, ogrenci["id"], len(liste), toplam, simdi, simdi, istemci_ip))
        baglanti.executemany(
            "INSERT INTO teslim_dosya(teslim_id, sira, goreli_yol, boyut, depo_adi) "
            "VALUES(?,?,?,?,?)",
            [(teslim_id, sira, d["yol"], d["boyut"], f"{sira:04d}")
             for sira, d in enumerate(liste, start=1)])
    for eski in eskiler:
        shutil.rmtree(_gecici(eski), ignore_errors=True)
    _gecici(teslim_id).mkdir(mode=0o770)
    return {"teslim_id": teslim_id,
            "dosyalar": [{"sira": sira, "yol": d["yol"], "boyut": d["boyut"]}
                         for sira, d in enumerate(liste, start=1)]}


async def dosya_yaz(ogrenci: dict, teslim_id: str, sira: int, akis,
                    beyan_boyut: int | None) -> dict:
    """Tek dosyayı akış halinde geçici alana yazar; aynı dosya yeniden denenebilir."""
    teslim = _teslim(ogrenci, teslim_id)
    if teslim["durum"] != "yukleniyor":
        raise TeslimHatasi("Bu gönderim artık geçerli değil; yeniden gönderin.")
    odev = vt.tek("SELECT * FROM odev WHERE id=?", (teslim["odev_id"],))
    kabul, _, neden = teslime_uygun(odev)
    if not kabul:
        _yarim_yap(teslim_id, neden)
        raise TeslimHatasi(neden)
    dosya = vt.tek("SELECT * FROM teslim_dosya WHERE teslim_id=? AND sira=?", (teslim_id, sira))
    if not dosya:
        raise TeslimHatasi("Dosya bu gönderimde yok.", 404)
    if beyan_boyut is not None and beyan_boyut != dosya["boyut"]:
        _yarim_yap(teslim_id, f"dosya seçimden sonra değişmiş: {dosya['goreli_yol']}")
        raise TeslimHatasi(f"Dosya boyutu değişmiş: {dosya['goreli_yol']}. Dosyayı yeniden seçin.",
                           400)

    hedef = _gecici(teslim_id) / dosya["depo_adi"]
    parca_yolu = hedef.with_suffix(".parca")
    sha = hashlib.sha256()
    bas = b""
    yazilan = 0
    async with YAZMA_PARALELLIGI:
        try:
            fd = os.open(parca_yolu, os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                         | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0), 0o660)
            with os.fdopen(fd, "wb") as cikis:
                tampon = []
                tampon_boyu = 0
                async for parca in akis:
                    if not parca:
                        continue
                    yazilan += len(parca)
                    if yazilan > dosya["boyut"]:
                        _yarim_yap(teslim_id, f"dosya bildirilenden büyük: {dosya['goreli_yol']}")
                        raise TeslimHatasi(f"Dosya bildirilenden büyük: {dosya['goreli_yol']}. "
                                           "Dosyayı yeniden seçip gönderin.", 400)
                    sha.update(parca)
                    if len(bas) < 8192:
                        bas += parca[:8192 - len(bas)]
                    tampon.append(parca)
                    tampon_boyu += len(parca)
                    if tampon_boyu >= TAMPON:
                        await asyncio.to_thread(cikis.write, b"".join(tampon))
                        tampon, tampon_boyu = [], 0
                if tampon:
                    await asyncio.to_thread(cikis.write, b"".join(tampon))
                await asyncio.to_thread(cikis.flush)
                await asyncio.to_thread(os.fsync, cikis.fileno())
        except TeslimHatasi:
            parca_yolu.unlink(missing_ok=True)
            raise
        except OSError as hata:
            parca_yolu.unlink(missing_ok=True)
            if hata.errno == errno.ENOSPC:
                _yarim_yap(teslim_id, "diskte yer kalmadı")
                raise TeslimHatasi("Öğretmen bilgisayarında yer kalmadı; teslim alınamadı. "
                                   "Öğretmeninize haber verin.", 507)
            raise
        except BaseException:
            parca_yolu.unlink(missing_ok=True)  # bağlantı kesildi / iptal
            raise

    if yazilan != dosya["boyut"]:
        parca_yolu.unlink(missing_ok=True)
        raise TeslimHatasi(f"Aktarım yarım kaldı: {dosya['goreli_yol']}. Yeniden deneyin.", 400)
    if not kurallar.icerik_uyusuyor_mu(kurallar.uzanti(dosya["goreli_yol"]), bas, yazilan):
        # Aynı dosya listesiyle bu gönderim hiç tamamlanamaz: hemen "yükleme hatası".
        _yarim_yap(teslim_id, f"içerik uzantıyla uyuşmuyor: {dosya['goreli_yol']}")
        raise TeslimHatasi(f"Dosyanın içeriği uzantısıyla uyuşmuyor: {dosya['goreli_yol']}. "
                           "Bu dosyayı seçimden çıkarıp yeniden gönderin.", 415)
    os.replace(parca_yolu, hedef)
    vt.calistir("UPDATE teslim_dosya SET sha256=?, alindi=1 WHERE teslim_id=? AND sira=?",
                (sha.hexdigest(), teslim_id, sira))
    vt.calistir("UPDATE teslim SET son_etkinlik=? WHERE id=?", (ortak.simdi_iso(), teslim_id))
    return {"sira": sira, "alindi": True}


def makbuz(teslim_id: str) -> dict:
    t = vt.tek("SELECT t.*, o.baslik, g.ad_soyad, g.numara, s.ad AS sinif FROM teslim t "
               "JOIN odev o ON o.id=t.odev_id JOIN ogrenci g ON g.id=t.ogrenci_id "
               "JOIN sinif s ON s.id=g.sinif_id WHERE t.id=?", (teslim_id,))
    return {"teslim_no": teslim_no(t["id"]), "surum": t["surum"], "odev": t["baslik"],
            "ad_soyad": t["ad_soyad"], "numara": t["numara"], "sinif": t["sinif"],
            "zaman": ortak.yerel_metin(t["bitis"]), "dosya_sayisi": t["dosya_sayisi"],
            "toplam_bayt": t["toplam_bayt"], "gec": bool(t["gec"])}


def tamamla(ogrenci: dict, teslim_id: str) -> dict:
    """İdempotent sonlandırma: aynı istek tekrar gelirse aynı makbuz döner."""
    teslim = _teslim(ogrenci, teslim_id)
    if teslim["durum"] == "tamamlandi":
        return makbuz(teslim_id)
    if teslim["durum"] != "yukleniyor":
        raise TeslimHatasi("Bu gönderim tamamlanamadı; dosyaları yeniden gönderin.")
    odev = vt.tek("SELECT * FROM odev WHERE id=?", (teslim["odev_id"],))
    kabul, gec, neden = teslime_uygun(odev)
    if not kabul:
        _yarim_yap(teslim_id, neden)
        raise TeslimHatasi(neden)
    kaynak = _gecici(teslim_id)
    for dosya in vt.sorgula("SELECT * FROM teslim_dosya WHERE teslim_id=?", (teslim_id,)):
        yol = kaynak / dosya["depo_adi"]
        if not dosya["alindi"] or not yol.is_file() or yol.stat().st_size != dosya["boyut"]:
            raise TeslimHatasi(f"Eksik dosya: {dosya['goreli_yol']}. Gönderimi tamamlayın "
                               "veya yeniden başlatın.", 400)

    hedef = _kalici(teslim["odev_id"], teslim_id)
    with vt.islem() as baglanti:
        durum = baglanti.execute("SELECT durum FROM teslim WHERE id=?", (teslim_id,)).fetchone()[0]
        if durum != "yukleniyor":  # eşzamanlı ikinci istek önce davrandı
            if durum == "tamamlandi":
                return makbuz(teslim_id)
            raise TeslimHatasi("Bu gönderim tamamlanamadı; dosyaları yeniden gönderin.")
        surum = baglanti.execute(
            "SELECT COALESCE(MAX(surum), 0) + 1 FROM teslim WHERE odev_id=? AND ogrenci_id=?",
            (teslim["odev_id"], ogrenci["id"])).fetchone()[0]
        hedef.parent.mkdir(parents=True, exist_ok=True)
        os.rename(kaynak, hedef)  # aynı dosya sisteminde tek adım
        try:
            _dizini_esitle(hedef.parent)
            baglanti.execute(
                "UPDATE teslim SET durum='tamamlandi', surum=?, gec=?, bitis=?, son_etkinlik=? "
                "WHERE id=?", (surum, int(gec), ortak.simdi_iso(), ortak.simdi_iso(), teslim_id))
        except BaseException:
            os.rename(hedef, kaynak)
            raise
    return makbuz(teslim_id)


def _dizini_esitle(dizin: Path) -> None:
    if os.name != "posix":
        return
    fd = os.open(dizin, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def iptal(ogrenci: dict, teslim_id: str) -> None:
    teslim = _teslim(ogrenci, teslim_id)
    if teslim["durum"] == "yukleniyor":
        _yarim_yap(teslim_id, "öğrenci iptal etti")


def durum(ogrenci: dict, teslim_id: str) -> dict:
    """Sayfa yeniden açıldığında sunucudaki gerçek durum (istem §6)."""
    teslim = _teslim(ogrenci, teslim_id)
    sonuc = {"durum": teslim["durum"], "hata": teslim["hata"]}
    if teslim["durum"] == "tamamlandi":
        sonuc["makbuz"] = makbuz(teslim_id)
    else:
        sonuc["alinan"] = [d["sira"] for d in vt.sorgula(
            "SELECT sira FROM teslim_dosya WHERE teslim_id=? AND alindi=1", (teslim_id,))]
    return sonuc


# ---------------------------------------------------------------- bakım

def onar(acilista: bool = False) -> dict:
    """Yarım kalanları temizler ve disk ile veritabanını uzlaştırır.

    `acilista`: servis yeni başladıysa süren bütün aktarımlar kesilmiştir; yalnız
    bu durumda kalıcı alan da uzlaştırılır (çalışırken yapılırsa o anda tamamlanan
    bir teslimle yarışabilir). Tamamlanmış teslimlere asla dokunulmaz.
    """
    sinir = ortak.simdi().timestamp() - ortak.YARIM_ZAMAN_ASIMI_SN
    yarim = 0
    for t in vt.sorgula("SELECT id, son_etkinlik FROM teslim WHERE durum='yukleniyor'"):
        if acilista or ortak.iso_oku(t["son_etkinlik"]).timestamp() < sinir:
            _yarim_yap(t["id"], "servis yeniden başladı" if acilista else "aktarım zaman aşımı")
            yarim += 1
    # Kayıtsız geçici klasörler; yeni başlamış bir gönderimle yarışmamak için
    # çalışırken yalnız 10 dakikadan eskiler silinir.
    gecerli = {t["id"] for t in vt.sorgula("SELECT id FROM teslim WHERE durum='yukleniyor'")}
    yas_siniri = ortak.simdi().timestamp() - 600
    gecici = ortak.yollar()["gecici"]
    if gecici.is_dir():
        for dizin in gecici.iterdir():
            if dizin.name not in gecerli and (acilista or dizin.stat().st_mtime < yas_siniri):
                shutil.rmtree(dizin, ignore_errors=True)
    if acilista:
        # Tamamla, klasörü taşıdıktan sonra ve kayıttan önce kesildiyse kayıtsız
        # klasör kalır: bu bir teslim değildir.
        tamam = {t["id"] for t in vt.sorgula("SELECT id FROM teslim WHERE durum='tamamlandi'")}
        kalici = ortak.yollar()["teslimler"]
        if kalici.is_dir():
            for odev_dizini in kalici.iterdir():
                for dizin in odev_dizini.iterdir() if odev_dizini.is_dir() else []:
                    if dizin.name not in tamam:
                        shutil.rmtree(dizin, ignore_errors=True)
    return {"yarim": yarim}
