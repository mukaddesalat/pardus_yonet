"""Sınıf listesi ve öğrenci kodları (yönetim paneli tarafı; istem §4).

Öğrenciler aynı yerel `ogrenci` hesabını kullandığı için Linux kullanıcı adı,
IP veya bilgisayar adı kimlik sayılmaz: kimlik = sınıf + numara + kişisel kod.
"""

import csv
import io
import re

from . import kod, ortak, vt

_AD_SINIRI = 80


class SinifHatasi(ValueError):
    """Öğretmene olduğu gibi gösterilebilecek hata."""


def _sinif_adi(ad: str) -> str:
    ad = re.sub(r"\s+", " ", (ad or "").strip())
    if not ad or len(ad) > 20:
        raise SinifHatasi("Sınıf adı 1–20 karakter olmalı (örn. 9-A)")
    return ad


def _numara(numara: str) -> str:
    numara = (numara or "").strip()
    if not re.fullmatch(r"[0-9A-Za-z-]{1,12}", numara):
        raise SinifHatasi(f"Geçersiz öğrenci numarası: {numara!r}")
    return numara


def _ad_soyad(ad: str) -> str:
    ad = re.sub(r"\s+", " ", (ad or "").strip())
    if not ad or len(ad) > _AD_SINIRI or any(ord(ch) < 32 for ch in ad):
        raise SinifHatasi(f"Geçersiz ad soyad: {ad[:30]!r}")
    return ad


# ---- sınıflar ----

def siniflar() -> list[dict]:
    return vt.sorgula(
        "SELECT s.id, s.ad, COUNT(o.id) AS ogrenci_sayisi, "
        "SUM(CASE WHEN o.kod_ozeti IS NULL AND o.id IS NOT NULL THEN 1 ELSE 0 END) AS kodsuz "
        "FROM sinif s LEFT JOIN ogrenci o ON o.sinif_id = s.id "
        "GROUP BY s.id ORDER BY s.ad")


def sinif_bul_veya_olustur(ad: str) -> str:
    ad = _sinif_adi(ad)
    satir = vt.tek("SELECT id FROM sinif WHERE ad=?", (ad,))
    if satir:
        return satir["id"]
    kimlik = vt.yeni_kimlik()
    vt.calistir("INSERT INTO sinif(id, ad) VALUES(?, ?)", (kimlik, ad))
    return kimlik


def sinif_sil(sinif_id: str) -> None:
    if vt.tek("SELECT 1 FROM odev WHERE sinif_id=? LIMIT 1", (sinif_id,)):
        raise SinifHatasi("Bu sınıfa ait ödevler var; önce ödevleri silin")
    with vt.islem() as baglanti:
        baglanti.execute("DELETE FROM ogrenci WHERE sinif_id=?", (sinif_id,))
        baglanti.execute("DELETE FROM sinif WHERE id=?", (sinif_id,))


# ---- öğrenciler ----

def ogrenciler(sinif_id: str) -> list[dict]:
    satirlar = vt.sorgula(
        "SELECT id, numara, ad_soyad, kod_zamani, kod_ozeti IS NOT NULL AS kodu_var "
        "FROM ogrenci WHERE sinif_id=?", (sinif_id,))
    return sorted(satirlar, key=_numara_sirasi)


def _numara_sirasi(ogr: dict):
    n = ogr["numara"]
    return (0, int(n), n) if n.isdigit() else (1, 0, n)


def ogrenci_ekle(sinif_id: str, numara: str, ad_soyad: str) -> str:
    if not vt.tek("SELECT 1 FROM sinif WHERE id=?", (sinif_id,)):
        raise SinifHatasi("Sınıf bulunamadı")
    numara, ad_soyad = _numara(numara), _ad_soyad(ad_soyad)
    if vt.tek("SELECT 1 FROM ogrenci WHERE sinif_id=? AND numara=?", (sinif_id, numara)):
        raise SinifHatasi(f"{numara} numaralı öğrenci bu sınıfta zaten var")
    kimlik = vt.yeni_kimlik()
    vt.calistir("INSERT INTO ogrenci(id, sinif_id, numara, ad_soyad) VALUES(?,?,?,?)",
                (kimlik, sinif_id, numara, ad_soyad))
    return kimlik


def ogrenci_duzenle(ogrenci_id: str, ad_soyad: str) -> None:
    if not vt.calistir("UPDATE ogrenci SET ad_soyad=? WHERE id=?",
                       (_ad_soyad(ad_soyad), ogrenci_id)):
        raise SinifHatasi("Öğrenci bulunamadı")


def ogrenci_sil(ogrenci_id: str) -> None:
    if vt.tek("SELECT 1 FROM teslim WHERE ogrenci_id=? LIMIT 1", (ogrenci_id,)):
        raise SinifHatasi("Bu öğrencinin teslimleri var; kaydı silinemez")
    vt.calistir("DELETE FROM ogrenci WHERE id=?", (ogrenci_id,))


# ---- CSV ----

def _metni_coz(veri: bytes) -> str:
    if veri.startswith(b"\xef\xbb\xbf"):
        return veri[3:].decode("utf-8")
    try:
        return veri.decode("utf-8")
    except UnicodeDecodeError:
        return veri.decode("cp1254")  # Türkçe Windows/Excel dışa aktarımı


def ice_aktar(veri: bytes) -> dict:
    """'sınıf, öğrenci numarası, ad soyad' sütunlu CSV'yi içe aktarır.

    Ayırıcı ; , veya sekme olabilir; başlık satırı varsa atlanır. Var olan
    (sınıf, numara) kaydının adı güncellenir, kodu korunur.
    """
    metin = _metni_coz(veri)
    try:
        lehce = csv.Sniffer().sniff(metin[:4096], delimiters=";,\t")
    except csv.Error:
        class lehce(csv.excel):  # noqa: N801 — csv lehçesi sınıf olarak tanımlanır
            delimiter = ";" if metin.count(";") >= metin.count(",") else ","
    eklenen = guncellenen = 0
    hatalar = []
    for satir_no, satir in enumerate(csv.reader(io.StringIO(metin), lehce), start=1):
        hucreler = [h.strip() for h in satir]
        if not any(hucreler):
            continue
        if satir_no == 1 and not any(ch.isdigit() for ch in "".join(hucreler[1:2])):
            continue  # başlık satırı
        if len(hucreler) < 3:
            hatalar.append(f"{satir_no}. satır: 3 sütun gerekli (sınıf, numara, ad soyad)")
            continue
        try:
            sinif_id = sinif_bul_veya_olustur(hucreler[0])
            numara, ad = _numara(hucreler[1]), _ad_soyad(" ".join(hucreler[2:]).strip())
            mevcut = vt.tek("SELECT id FROM ogrenci WHERE sinif_id=? AND numara=?",
                            (sinif_id, numara))
            if mevcut:
                vt.calistir("UPDATE ogrenci SET ad_soyad=? WHERE id=?", (ad, mevcut["id"]))
                guncellenen += 1
            else:
                ogrenci_ekle(sinif_id, numara, ad)
                eklenen += 1
        except SinifHatasi as hata:
            hatalar.append(f"{satir_no}. satır: {hata}")
    return {"eklenen": eklenen, "guncellenen": guncellenen, "hatalar": hatalar[:50]}


def disari_aktar(sinif_id: str) -> str:
    """Standart sınıf CSV'si. Kodlar (ve özetleri) asla dahil edilmez (istem §4)."""
    sinif = vt.tek("SELECT ad FROM sinif WHERE id=?", (sinif_id,))
    if not sinif:
        raise SinifHatasi("Sınıf bulunamadı")
    cikti = io.StringIO()
    yazici = csv.writer(cikti, delimiter=";", lineterminator="\r\n")
    yazici.writerow(["sınıf", "öğrenci numarası", "ad soyad"])
    for ogr in ogrenciler(sinif_id):
        yazici.writerow([sinif["ad"], ogr["numara"], ogr["ad_soyad"]])
    return "﻿" + cikti.getvalue()  # Excel'in UTF-8'i tanıması için BOM


# ---- kodlar ----

def kod_uret(ogrenci_idler: list[str]) -> list[dict]:
    """Seçili öğrencilere yeni kod üretir; kodlar YALNIZ bu yanıtta döner.

    Eski kod anında geçersiz olur. Kodlar loglara, URL'lere ve dışa aktarımlara
    yazılmaz.
    """
    sonuc = []
    for ogrenci_id in ogrenci_idler:
        ogr = vt.tek("SELECT o.id, o.numara, o.ad_soyad, s.ad AS sinif FROM ogrenci o "
                     "JOIN sinif s ON s.id = o.sinif_id WHERE o.id=?", (ogrenci_id,))
        if not ogr:
            continue
        yeni = kod.uret()
        vt.calistir("UPDATE ogrenci SET kod_ozeti=?, kod_zamani=? WHERE id=?",
                    (kod.ozet(yeni), ortak.simdi_iso(), ogrenci_id))
        sonuc.append({**ogr, "kod": yeni})
    return sorted(sonuc, key=lambda o: (o["sinif"], _numara_sirasi(o)))
