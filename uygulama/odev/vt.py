"""Ödev veritabanı (SQLite): sınıflar, öğrenciler, ödevler, teslimler.

Portal ve yönetim paneli aynı dosyayı ayrı süreçlerden açar; WAL kipi ve
meşgul zaman aşımı eşzamanlı erişimi karşılar. Teslim kodları düz metin olarak
asla saklanmaz (yalnız scrypt özeti).
"""

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager

from . import ortak

_kilit = threading.RLock()
_baglanti: sqlite3.Connection | None = None

SEMA = """
CREATE TABLE IF NOT EXISTS ayar (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sinif (
    id  TEXT PRIMARY KEY,
    ad  TEXT NOT NULL UNIQUE COLLATE NOCASE          -- örn. "9-A"
);

CREATE TABLE IF NOT EXISTS ogrenci (
    id         TEXT PRIMARY KEY,
    sinif_id   TEXT NOT NULL REFERENCES sinif(id),
    numara     TEXT NOT NULL,
    ad_soyad   TEXT NOT NULL,
    kod_ozeti  TEXT,                                 -- scrypt; NULL = kod üretilmedi
    kod_zamani TEXT,
    UNIQUE(sinif_id, numara)
);

CREATE TABLE IF NOT EXISTS odev (
    id             TEXT PRIMARY KEY,
    sinif_id       TEXT NOT NULL REFERENCES sinif(id),
    baslik         TEXT NOT NULL,
    yonerge        TEXT NOT NULL DEFAULT '',
    son_tarih      TEXT,                             -- UTC ISO; NULL = süresiz
    gec_teslim     INTEGER NOT NULL DEFAULT 0,       -- 1: süre sonrası "Geç teslim" olarak kabul
    turler         TEXT NOT NULL,                    -- JSON: izinli tür kategorileri
    ek_uzantilar   TEXT NOT NULL DEFAULT '[]',       -- JSON: kategoriler dışında izinli uzantılar
    en_fazla_dosya INTEGER NOT NULL,
    en_fazla_bayt  INTEGER NOT NULL,
    klasor_izni    INTEGER NOT NULL DEFAULT 1,
    durum          TEXT NOT NULL DEFAULT 'taslak',   -- taslak / acik / kapali / arsiv
    olusturma      TEXT NOT NULL,
    guncelleme     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teslim (
    id            TEXT PRIMARY KEY,                  -- sunucu üretir (uuid4)
    odev_id       TEXT NOT NULL REFERENCES odev(id),
    ogrenci_id    TEXT NOT NULL REFERENCES ogrenci(id),
    durum         TEXT NOT NULL,                     -- yukleniyor / tamamlandi / yarim
    surum         INTEGER,                           -- yalnız tamamlanınca: 1, 2, ...
    gec           INTEGER NOT NULL DEFAULT 0,
    dosya_sayisi  INTEGER NOT NULL,
    toplam_bayt   INTEGER NOT NULL,
    baslangic     TEXT NOT NULL,
    son_etkinlik  TEXT NOT NULL,
    bitis         TEXT,
    istemci_ip    TEXT,                              -- yalnız "tahmini PC" uyarısı için
    hata          TEXT,
    UNIQUE(odev_id, ogrenci_id, surum)
);
CREATE INDEX IF NOT EXISTS teslim_odev ON teslim(odev_id, ogrenci_id);

CREATE TABLE IF NOT EXISTS teslim_dosya (
    teslim_id  TEXT NOT NULL REFERENCES teslim(id),
    sira       INTEGER NOT NULL,
    goreli_yol TEXT NOT NULL,                        -- öğrencinin gönderdiği ad (yalnız üstveri)
    boyut      INTEGER NOT NULL,
    depo_adi   TEXT NOT NULL,                        -- diskteki ad (sunucu üretir)
    sha256     TEXT,
    alindi     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (teslim_id, sira)
);
"""


def yeni_kimlik() -> str:
    return uuid.uuid4().hex


def ac() -> sqlite3.Connection:
    global _baglanti
    with _kilit:
        if _baglanti is None:
            yol = ortak.yollar()["veritabani"]
            yol.parent.mkdir(parents=True, exist_ok=True)
            _baglanti = sqlite3.connect(yol, check_same_thread=False, isolation_level=None,
                                        timeout=15)
            _baglanti.row_factory = sqlite3.Row
            _baglanti.execute("PRAGMA busy_timeout=15000")
            _baglanti.execute("PRAGMA journal_mode=WAL")
            _baglanti.execute("PRAGMA foreign_keys=ON")
            _baglanti.executescript(SEMA)
            _grup_yazilabilir_yap(yol)
        return _baglanti


def _grup_yazilabilir_yap(yol) -> None:
    """Portal ve yönetim servisi aynı grupta; ikisi de veritabanına yazabilmeli.

    SQLite dosyaları 0644 ile açar (UMask'e rağmen grup yazamaz). Dosyanın sahibi
    olan süreç izni 0660 yapar; -wal/-shm dosyaları ana dosyanın iznini devralır.
    """
    for ek in ("", "-wal", "-shm"):
        try:
            # Grup yazılabilirliği (portal ve yönetim servisleri ortak grubu)
            os.chmod(f"{yol}{ek}", 0o660)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
        except OSError:
            pass  # sahibi değilsek (diğer servis) veya dosya yoksa


def kapat() -> None:
    """Testler ve veri dizini değişimi için bağlantıyı bırakır."""
    global _baglanti
    with _kilit:
        if _baglanti is not None:
            _baglanti.close()
            _baglanti = None


def calistir(sql: str, params: tuple = ()) -> int:
    vt = ac()
    with _kilit:
        return vt.execute(sql, params).rowcount


def sorgula(sql: str, params: tuple = ()) -> list[dict]:
    vt = ac()
    with _kilit:
        return [dict(s) for s in vt.execute(sql, params).fetchall()]


def tek(sql: str, params: tuple = ()) -> dict | None:
    satirlar = sorgula(sql, params)
    return satirlar[0] if satirlar else None


@contextmanager
def islem():
    """Yazma kilidini hemen alan işlem: sürüm numarası gibi değerler yarışsız atanır."""
    vt = ac()
    with _kilit:
        vt.execute("BEGIN IMMEDIATE")
        try:
            yield vt
        except BaseException:
            vt.execute("ROLLBACK")
            raise
        vt.execute("COMMIT")


def ayar_oku(anahtar: str, varsayilan: str | None = None) -> str | None:
    satir = tek("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,))
    return satir["deger"] if satir else varsayilan


def ayar_yaz(anahtar: str, deger: str) -> None:
    calistir("INSERT INTO ayar(anahtar, deger) VALUES(?, ?) "
             "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger", (anahtar, deger))
