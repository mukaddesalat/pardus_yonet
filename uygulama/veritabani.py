"""SQLite tabanlı envanter, iş geçmişi ve ayar deposu.

Tek süreç içinde birden çok iş parçacığından erişildiği için bağlantı
kilitle korunur. Parola veya özel anahtar bu veritabanına asla yazılmaz.
"""

import ipaddress
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from . import ayarlar

_kilit = threading.Lock()
_baglanti: sqlite3.Connection | None = None

SEMA = """
CREATE TABLE IF NOT EXISTS ayar (
    anahtar TEXT PRIMARY KEY,
    deger   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cihaz (
    id               TEXT PRIMARY KEY,          -- benzersiz dahili kimlik (karar 10)
    ip               TEXT NOT NULL,
    ssh_port         INTEGER NOT NULL DEFAULT 22,
    hostname         TEXT,
    pardus_surum     TEXT,
    masaustu         TEXT,                      -- "GNOME" / "desteklenmiyor" / NULL
    baglanti_hesabi  TEXT,                      -- pardus / hp
    profil_hesabi    TEXT NOT NULL DEFAULT 'ogrenci',
    profil_var       INTEGER,                   -- ogrenci hesabı hedefte var mı (1/0/NULL)
    sudo_durumu      TEXT,                      -- 'parolasiz' / 'parola_ile' / 'yetersiz' / NULL
    anahtar_durumu   TEXT NOT NULL DEFAULT 'gerekli',  -- 'gerekli' / 'ok'
    anahtar_tipi     TEXT,                      -- ssh host anahtarı türü
    anahtar_b64      TEXT,                      -- ssh host anahtarı (base64)
    parmak_izi       TEXT,                      -- SHA256:...
    parmak_izi_onay  INTEGER NOT NULL DEFAULT 0,
    yinelenen_kimlik INTEGER NOT NULL DEFAULT 0, -- klon host anahtarı uyarısı (karar 10)
    grup             TEXT NOT NULL DEFAULT 'Laboratuvar',
    durum            TEXT NOT NULL,             -- envanter durumu (istem §5)
    son_kontrol      TEXT,
    etiket           TEXT,                      -- öğretmenin verdiği görünen ad
    korunan          INTEGER NOT NULL DEFAULT 0, -- EBA/ETAP: hiçbir işleme dahil edilmez
    korunan_neden    TEXT,
    giris_yoneticisi TEXT,                      -- gdm3 / lightdm / ...
    yonetim_hesaplari TEXT,                     -- JSON: hedefte bulunan hp/pardus hesapları
    ogrenci_oturumu  INTEGER,                   -- son kontrolde ogrenci oturumu açık mı
    gizleme_durumu   TEXT,                      -- 'gizli' / 'gorunur' / 'desteklenmiyor'
    otomatik_giris   TEXT,                      -- otomatik giriş yapan hesap / 'kapali'
    gorunum_durumu   TEXT,                      -- 'uygulandi' / 'yok'
    disk_bos         INTEGER,                   -- ev dizininin bulunduğu diskte boş bayt
    ogrenci_sudo     INTEGER,                   -- ogrenci sudo grubunda mı (uyarı)
    erisim           INTEGER,                   -- son canlı denemede SSH portu açık mı
    erisim_zamani    TEXT,
    veyon_surum      TEXT,                      -- hedeften okunan TAM paket sürümü (dağıtım revizyonuyla)
    veyon_durumu     TEXT,                      -- 'kurulu' / 'kurulu_degil' / 'hatali' / 'okunamadi'
    veyon_yapilandirma TEXT,                    -- JSON: servis, yöntem, anahtar eşleşmesi
    veyon_kontrol    TEXT,                      -- Veyon bilgisinin okunduğu zaman
    guc_durumu       TEXT,                      -- JSON: uyku kapalı mı, ekran koruyucu, kapatma planları
    UNIQUE(ip, ssh_port)
);

CREATE TABLE IF NOT EXISTS bulunan (             -- Ağda Bul sonuçları; envanter değildir
    ip          TEXT NOT NULL,
    ssh_port    INTEGER NOT NULL,
    anahtar_tipi TEXT,
    anahtar_b64  TEXT,
    parmak_izi   TEXT,
    zaman        TEXT NOT NULL,
    PRIMARY KEY (ip, ssh_port)
);

CREATE TABLE IF NOT EXISTS paket (               -- öğretmenin yüklediği yerel .deb dosyaları
    sha256       TEXT PRIMARY KEY,
    dosya_adi    TEXT NOT NULL,
    paket        TEXT NOT NULL,
    surum        TEXT NOT NULL,
    mimari       TEXT NOT NULL,
    boyut        INTEGER NOT NULL,
    kurulu_kb    INTEGER,
    kontrol      TEXT NOT NULL,                  -- JSON: control alanları
    zaman        TEXT NOT NULL,
    tur          TEXT NOT NULL DEFAULT 'genel'   -- 'genel' (M2-S2) / 'veyon' (M1-S4); listeler ayrıdır
);

CREATE TABLE IF NOT EXISTS is_kaydi (
    id                 TEXT PRIMARY KEY,
    tip                TEXT NOT NULL,      -- 'kesif' / 'dogrulama' / 'yonetime_al' / 'durum'
    durum              TEXT NOT NULL,      -- 'calisiyor' / 'tamamlandi' / 'iptal' / 'hata' / 'kesildi'
    baslangic          TEXT NOT NULL,
    bitis              TEXT,
    ozet               TEXT,
    parametreler       TEXT,               -- JSON; parola içermez
    ogretmen_kullanici TEXT,
    ogretmen_ad        TEXT,
    ogretmen_rol       TEXT
);

CREATE TABLE IF NOT EXISTS is_hedef (
    is_id    TEXT NOT NULL,
    hedef    TEXT NOT NULL,         -- ip veya cihaz id
    durum    TEXT NOT NULL,         -- 'bekliyor' / 'calisiyor' / 'basarili' / 'basarisiz' / 'atlandi'
    asama    TEXT,
    mesaj    TEXT,
    zaman    TEXT,
    veri     TEXT,                  -- JSON: yapılandırılmış sonuç (tablolar için)
    PRIMARY KEY (is_id, hedef)
);

CREATE TABLE IF NOT EXISTS deneme_butcesi (
    ip     TEXT NOT NULL,
    hesap  TEXT NOT NULL,
    kalan  INTEGER NOT NULL,
    zaman  TEXT NOT NULL,
    PRIMARY KEY (ip, hesap)
);

CREATE TABLE IF NOT EXISTS ogretmen (
    id            TEXT PRIMARY KEY,
    kullanici_adi TEXT NOT NULL UNIQUE,
    ad_soyad      TEXT NOT NULL,
    brans         TEXT NOT NULL DEFAULT '',
    parola_ozeti  TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'standart', -- 'admin' | 'standart'
    yetkiler      TEXT NOT NULL DEFAULT '{}',       -- JSON: {"paket_gorunum": bool, "komut_gonder": bool}
    aktif         INTEGER NOT NULL DEFAULT 1,
    olusturma     TEXT NOT NULL,
    son_giris     TEXT
);

CREATE TABLE IF NOT EXISTS kayitli_komut (
    id           TEXT PRIMARY KEY,
    baslik       TEXT NOT NULL,
    kategori     TEXT NOT NULL DEFAULT 'Genel',
    komut        TEXT NOT NULL,
    aciklama     TEXT NOT NULL DEFAULT '',
    sudo_gerekli INTEGER NOT NULL DEFAULT 1,
    yerlesik     INTEGER NOT NULL DEFAULT 0,
    olusturan    TEXT NOT NULL DEFAULT 'sistem',
    zaman        TEXT NOT NULL
);
"""


def simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_YERLESIK_KOMUTLAR = [
    (
        "k_hosts",
        "Hosts Dosyasına Adres Ekle (abc.local -> 192.168.23.142)",
        "Ağ & DNS",
        "grep -qE '(^|[[:space:]])abc\\.local([[:space:]]|$)' /etc/hosts "
        "&& sed -i 's/.*[[:space:]]abc\\.local.*/192.168.23.142\\tabc.local/' /etc/hosts "
        "|| printf '\\n192.168.23.142\\tabc.local\\n' >> /etc/hosts && grep 'abc.local' /etc/hosts",
        "abc.local adresini tüm öğrenci bilgisayarlarında 192.168.23.142 olarak /etc/hosts dosyasına ekler veya günceller.",
        1,
    ),
    (
        "k_userdel",
        "Kullanıcıyı ve Ev Dizinini Sil (userdel -r abc)",
        "Kullanıcı Yönetimi",
        "if id abc &>/dev/null; then pkill -KILL -u abc 2>/dev/null || true; "
        "userdel -r abc && echo 'OK: abc kullanıcısı ve ev dizini silindi'; "
        "else echo 'ATLANDI: abc kullanıcısı zaten yok'; fi",
        "abc kullanıcısının açık süreçlerini kapatır ve ev diziniyle birlikte sistemden kaldırır.",
        1,
    ),
    (
        "k_dns",
        "Ağ ve DNS Önbelleğini Yenile",
        "Ağ & DNS",
        "systemctl restart NetworkManager 2>/dev/null || true; "
        "resolvectl flush-caches 2>/dev/null || true; echo 'Ağ ve DNS önbelleği yenilendi'",
        "Ağ bağlantısını ve yerel DNS çözümleme önbelleğini tazeler.",
        1,
    ),
    (
        "k_kaynak",
        "Disk, Bellek ve Sistem Özeti",
        "Sistem Durumu",
        "echo \"=== HOST: $(hostname) ===\"; free -h | awk 'NR<=2'; df -h / /home | awk 'NR<=3'",
        "Öğrenci bilgisayarının RAM ve disk doluluk durumunu raporlar.",
        0,
    ),
    (
        "k_dpkg_onar",
        "Yarım Kalan Paket Kurulumlarını Onar (dpkg --configure -a)",
        "Paket & Bakım",
        "DEBIAN_FRONTEND=noninteractive dpkg --configure -a && apt-get -f install -y && echo 'Paket sistemi onarıldı'",
        "Kilitli veya yarım kalmış .deb paket kurulumlarını onarır.",
        1,
    ),
]


def ac() -> sqlite3.Connection:
    global _baglanti
    with _kilit:
        if _baglanti is None:
            yol = ayarlar.veri_yollari()["veritabani"]
            yol.parent.mkdir(parents=True, exist_ok=True)
            _baglanti = sqlite3.connect(yol, check_same_thread=False)
            _baglanti.row_factory = sqlite3.Row
            _baglanti.executescript("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")
            _baglanti.executescript(SEMA)
            _goc(_baglanti)
            _yerlesik_komutlari_yukle(_baglanti)
            _baglanti.commit()
        return _baglanti


# Eski sürümlerden kalan veritabanlarına eksik sütunları ekler (0.1.0 -> 0.7.0).
_EK_SUTUNLAR = {
    "paket": {"tur": "TEXT NOT NULL DEFAULT 'genel'"},
    "cihaz": {
        "etiket": "TEXT",
        "korunan": "INTEGER NOT NULL DEFAULT 0",
        "korunan_neden": "TEXT",
        "giris_yoneticisi": "TEXT",
        "yonetim_hesaplari": "TEXT",
        "ogrenci_oturumu": "INTEGER",
        "gizleme_durumu": "TEXT",
        "otomatik_giris": "TEXT",
        "gorunum_durumu": "TEXT",
        "disk_bos": "INTEGER",
        "ogrenci_sudo": "INTEGER",
        "erisim": "INTEGER",
        "erisim_zamani": "TEXT",
        "veyon_surum": "TEXT",
        "veyon_durumu": "TEXT",
        "veyon_yapilandirma": "TEXT",
        "veyon_kontrol": "TEXT",
        "guc_durumu": "TEXT",
    },
    "is_kaydi": {
        "ogretmen_kullanici": "TEXT",
        "ogretmen_ad": "TEXT",
        "ogretmen_rol": "TEXT",
    },
    "is_hedef": {"veri": "TEXT"},
}


def _goc(vt: sqlite3.Connection) -> None:
    for tablo, sutunlar in _EK_SUTUNLAR.items():
        mevcut = {s[1] for s in vt.execute(f"PRAGMA table_info({tablo})")}
        for ad, tip in sutunlar.items():
            if ad not in mevcut:
                vt.execute(f"ALTER TABLE {tablo} ADD COLUMN {ad} {tip}")


def _yerlesik_komutlari_yukle(vt: sqlite3.Connection) -> None:
    zaman = simdi()
    for kid, baslik, kategori, komut, aciklama, sudo_gerekli in _YERLESIK_KOMUTLAR:
        vt.execute(
            "INSERT OR IGNORE INTO kayitli_komut"
            "(id, baslik, kategori, komut, aciklama, sudo_gerekli, yerlesik, olusturan, zaman) "
            "VALUES(?, ?, ?, ?, ?, ?, 1, 'sistem', ?)",
            (kid, baslik, kategori, komut, aciklama, sudo_gerekli, zaman),
        )


def calistir(sql: str, params: tuple = ()) -> None:
    vt = ac()
    with _kilit:
        vt.execute(sql, params)
        vt.commit()


def sorgula(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    vt = ac()
    with _kilit:
        return vt.execute(sql, params).fetchall()


def tek(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    satirlar = sorgula(sql, params)
    return satirlar[0] if satirlar else None


# ---- ayar tablosu ----

def ayar_oku(anahtar: str) -> str | None:
    satir = tek("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,))
    return satir["deger"] if satir else None


def ayar_yaz(anahtar: str, deger: str) -> None:
    calistir(
        "INSERT INTO ayar(anahtar, deger) VALUES(?, ?) "
        "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
        (anahtar, deger),
    )


# ---- cihaz ----

def cihaz_bul_veya_olustur(ip: str, port: int) -> str:
    satir = tek("SELECT id FROM cihaz WHERE ip=? AND ssh_port=?", (ip, port))
    if satir:
        return satir["id"]
    yeni_id = uuid.uuid4().hex[:12]
    calistir(
        "INSERT INTO cihaz(id, ip, ssh_port, durum) VALUES(?, ?, ?, ?)",
        (yeni_id, ip, port, "SSH erişilemiyor"),
    )
    return yeni_id


def cihaz_guncelle(cihaz_id: str, **alanlar) -> None:
    if not alanlar:
        return
    if isinstance(alanlar.get("yonetim_hesaplari"), (list, tuple)):
        alanlar["yonetim_hesaplari"] = json.dumps(list(alanlar["yonetim_hesaplari"]))
    for alan in ("veyon_yapilandirma", "guc_durumu"):
        if isinstance(alanlar.get(alan), dict):
            alanlar[alan] = json.dumps(alanlar[alan], ensure_ascii=False)
    parcalar = ", ".join(f"{ad}=?" for ad in alanlar)
    calistir(f"UPDATE cihaz SET {parcalar} WHERE id=?", (*alanlar.values(), cihaz_id))


def _cihaz_sozluk(satir) -> dict:
    c = dict(satir)
    for alan in ("yonetim_hesaplari", "veyon_yapilandirma", "guc_durumu"):
        try:
            c[alan] = json.loads(c.get(alan) or "null")
        except ValueError:
            c[alan] = None
    return c


def cihazlar() -> list[dict]:
    satirlar = [_cihaz_sozluk(s) for s in sorgula("SELECT * FROM cihaz")]
    return sorted(satirlar, key=lambda c: (ipaddress.ip_address(c["ip"]), c["ssh_port"]))


def cihaz(cihaz_id: str) -> dict | None:
    satir = tek("SELECT * FROM cihaz WHERE id=?", (cihaz_id,))
    return _cihaz_sozluk(satir) if satir else None


def cihaz_sil(cihaz_id: str) -> None:
    """Yalnızca envanter kaydını siler. Deneme bütçesi korunur: kaydı silip
    yeniden eklemek parola deneme sınırını sıfırlamamalıdır (istem §5.4)."""
    calistir("DELETE FROM cihaz WHERE id=?", (cihaz_id,))


def cihaz_adi(cihaz: dict) -> str:
    return cihaz.get("etiket") or cihaz.get("hostname") or cihaz["ip"]


# ---- saklama sınırı (istem §9.15) ----

SAKLAMA_VARSAYILAN = 5


def saklama_adedi() -> int:
    deger = ayar_oku("saklama_adedi")
    return int(deger) if deger and deger.isdigit() else SAKLAMA_VARSAYILAN


# ---- iş kayıtları ----

def is_olustur(tip: str, parametreler: dict, hedefler: list[str],
               ogretmen: dict | None = None) -> str:
    is_id = uuid.uuid4().hex[:12]
    ogr_kullanici = (ogretmen or {}).get("kullanici_adi")
    ogr_ad = (ogretmen or {}).get("ad_soyad")
    ogr_rol = (ogretmen or {}).get("rol")
    calistir(
        "INSERT INTO is_kaydi(id, tip, durum, baslangic, parametreler, "
        "ogretmen_kullanici, ogretmen_ad, ogretmen_rol) VALUES(?,?,?,?,?,?,?,?)",
        (is_id, tip, "calisiyor", simdi(), json.dumps(parametreler, ensure_ascii=False),
         ogr_kullanici, ogr_ad, ogr_rol),
    )
    for hedef in hedefler:
        calistir(
            "INSERT OR REPLACE INTO is_hedef(is_id, hedef, durum, zaman) VALUES(?,?,?,?)",
            (is_id, hedef, "bekliyor", simdi()),
        )
    return is_id


def is_bitir(is_id: str, durum: str, ozet: str = "") -> None:
    calistir(
        "UPDATE is_kaydi SET durum=?, bitis=?, ozet=COALESCE(NULLIF(?, ''), ozet, '') WHERE id=?",
        (durum, simdi(), ozet, is_id),
    )


def hedef_guncelle(is_id: str, hedef: str, durum: str, asama: str = "", mesaj: str = "",
                   veri: dict | None = None) -> None:
    """Hedef satırını günceller. `veri` verilmezse önceki yapılandırılmış sonuç korunur."""
    calistir(
        "INSERT INTO is_hedef(is_id, hedef, durum, asama, mesaj, zaman, veri) "
        "VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(is_id, hedef) DO UPDATE SET durum=excluded.durum, "
        "asama=excluded.asama, mesaj=excluded.mesaj, zaman=excluded.zaman, "
        "veri=COALESCE(excluded.veri, is_hedef.veri)",
        (is_id, hedef, durum, asama, mesaj, simdi(),
         json.dumps(veri, ensure_ascii=False) if veri is not None else None),
    )


def is_durumu(is_id: str) -> dict | None:
    kayit = tek("SELECT * FROM is_kaydi WHERE id=?", (is_id,))
    if not kayit:
        return None
    hedefler = []
    for satir in sorgula("SELECT * FROM is_hedef WHERE is_id=? ORDER BY hedef", (is_id,)):
        h = dict(satir)
        try:
            h["veri"] = json.loads(h["veri"]) if h.get("veri") else None
        except ValueError:
            h["veri"] = None
        hedefler.append(h)
    sonuc = dict(kayit)
    try:
        sonuc["parametreler"] = json.loads(sonuc.get("parametreler") or "{}")
    except ValueError:
        sonuc["parametreler"] = {}
    sonuc["hedefler"] = hedefler
    return sonuc


def yarim_isleri_isaretle() -> None:
    """Uygulama açılışında yarım kalmış işleri işaretle (istem §11)."""
    calistir(
        "UPDATE is_kaydi SET durum='kesildi', ozet='Kesildi — kontrol gerekli' "
        "WHERE durum='calisiyor'"
    )


# ---- deneme bütçesi (istem §5.4) ----

def butce_al(ip: str, hesap: str) -> int:
    satir = tek("SELECT kalan FROM deneme_butcesi WHERE ip=? AND hesap=?", (ip, hesap))
    if satir is None:
        calistir(
            "INSERT INTO deneme_butcesi(ip, hesap, kalan, zaman) VALUES(?,?,?,?)",
            (ip, hesap, ayarlar.DENEME_BUTCESI, simdi()),
        )
        return ayarlar.DENEME_BUTCESI
    return satir["kalan"]


def butce_dus(ip: str, hesap: str) -> None:
    butce_al(ip, hesap)  # kayıt yoksa oluştur; yoksa düşüş sessizce kaybolur
    calistir(
        "UPDATE deneme_butcesi SET kalan=MAX(kalan-1,0), zaman=? WHERE ip=? AND hesap=?",
        (simdi(), ip, hesap),
    )


def butce_sifirla(ip: str, hesap: str) -> None:
    """Yalnızca başarılı girişten sonra çağrılır; yeniden tarama sıfırlamaz."""
    calistir(
        "UPDATE deneme_butcesi SET kalan=?, zaman=? WHERE ip=? AND hesap=?",
        (ayarlar.DENEME_BUTCESI, simdi(), ip, hesap),
    )


# ---- okul kimliği (okul adı ve logosu) ----

VARSAYILAN_OKUL_ADI = "Şehit Cengiz Polat Fen ve Teknoloji Anadolu İmam Hatip Lisesi"
VARSAYILAN_OKUL_ALT = "Bilişim Teknolojileri Laboratuvarı"
VARSAYILAN_OKUL_LOGO = (
    "data:image/svg+xml;utf8,"
    "%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E"
    "%3Ccircle%20cx%3D%2232%22%20cy%3D%2232%22%20r%3D%2230%22%20fill%3D%22%231B5FC1%22%20stroke%3D%22%2393C5FD%22%20stroke-width%3D%222.5%22%2F%3E"
    "%3Cpath%20d%3D%22M32%2012L14%2021v12c0%2011.5%207.7%2021.8%2018%2025%2010.3-3.2%2018-13.5%2018-25V21L32%2012z%22%20fill%3D%22%230F2A56%22%2F%3E"
    "%3Cpath%20d%3D%22M22%2036c4-2%208-2%2010%200%202-2%206-2%2010%200V24c-4-2-8-2-10%200-2-2-6-2-10%200v12z%22%20fill%3D%22%23FFFFFF%22%2F%3E"
    "%3Ccircle%20cx%3D%2232%22%20cy%3D%2219%22%20r%3D%222.5%22%20fill%3D%22%23FBBF24%22%2F%3E%3C%2Fsvg%3E"
)


def okul_bilgisi() -> dict:
    ad = ayar_oku("okul_adi") or VARSAYILAN_OKUL_ADI
    alt = ayar_oku("okul_alt_baslik") or VARSAYILAN_OKUL_ALT
    logo = ayar_oku("okul_logo")
    if logo is None:
        logo = VARSAYILAN_OKUL_LOGO
    return {
        "ad": ad,
        "okul_adi": ad,
        "alt_baslik": alt,
        "logo_b64": logo,
        "okul_logo": logo,
    }


def okul_kaydet(okul_adi: str, alt_baslik: str | None = None,
                okul_logo: str | None = None) -> dict:
    ad = (okul_adi or "").strip() or VARSAYILAN_OKUL_ADI
    ayar_yaz("okul_adi", ad[:120])
    # 2 parametreli eski çağrı uyumu: 2. parametre data:image/... ise logo olarak işle
    if alt_baslik is not None and okul_logo is None and str(alt_baslik).startswith("data:image/"):
        ayar_yaz("okul_logo", alt_baslik)
    else:
        if alt_baslik is not None:
            ayar_yaz("okul_alt_baslik", (alt_baslik or "").strip()[:120] or VARSAYILAN_OKUL_ALT)
        if okul_logo is not None:
            ayar_yaz("okul_logo", okul_logo)
    return okul_bilgisi()


# ---- öğretmen hesapları ve yetkiler ----

GECERLI_YETKILER = ("paket_gorunum", "komut_gonder")


def _yetki_listesi_norm(yetkiler, rol: str = "standart") -> list[str]:
    if rol == "admin":
        return list(GECERLI_YETKILER)
    if isinstance(yetkiler, str):
        try:
            yetkiler = json.loads(yetkiler)
        except ValueError:
            yetkiler = []
    if isinstance(yetkiler, dict):
        return [k for k in GECERLI_YETKILER if bool(yetkiler.get(k))]
    if isinstance(yetkiler, (list, tuple, set)):
        return [k for k in GECERLI_YETKILER if k in yetkiler]
    return []


def _ogretmen_sozluk(satir, gizli_kaldir: bool = True) -> dict:
    o = dict(satir)
    if gizli_kaldir:
        o.pop("parola_ozeti", None)
    o["yetkiler"] = _yetki_listesi_norm(o.get("yetkiler"), o.get("rol", "standart"))
    o["aktif"] = bool(o.get("aktif", 1))
    return o


def ogretmenler() -> list[dict]:
    return [_ogretmen_sozluk(s) for s in sorgula(
        "SELECT * FROM ogretmen ORDER BY rol ASC, ad_soyad ASC")]


def ogretmen_bul(kullanici_adi: str, gizli_kaldir: bool = False) -> dict | None:
    satir = tek("SELECT * FROM ogretmen WHERE lower(kullanici_adi)=lower(?)",
                ((kullanici_adi or "").strip(),))
    return _ogretmen_sozluk(satir, gizli_kaldir=gizli_kaldir) if satir else None


def ogretmen_getir(ogretmen_id: str, gizli_kaldir: bool = True) -> dict | None:
    satir = tek("SELECT * FROM ogretmen WHERE id=?", (ogretmen_id,))
    return _ogretmen_sozluk(satir, gizli_kaldir=gizli_kaldir) if satir else None


def _admin_sayisi() -> int:
    satir = tek("SELECT COUNT(*) AS n FROM ogretmen WHERE rol='admin' AND aktif=1")
    return int(satir["n"]) if satir else 0


def ogretmen_ekle(kullanici_adi: str, ad_soyad: str, parola_ozeti: str,
                  rol: str = "standart", brans: str = "",
                  yetkiler: list | dict | None = None) -> dict:
    k_adi = (kullanici_adi or "").strip().lower()
    if not k_adi:
        raise ValueError("Kullanıcı adı boş olamaz")
    if ogretmen_bul(k_adi):
        raise ValueError(f"'{k_adi}' kullanıcı adı zaten kayıtlı")
    yeni_id = "ogr_" + uuid.uuid4().hex[:10]
    rol_norm = "admin" if rol == "admin" else "standart"
    yetki_json = json.dumps(_yetki_listesi_norm(yetkiler, rol_norm), ensure_ascii=False)
    calistir(
        "INSERT INTO ogretmen(id, kullanici_adi, ad_soyad, brans, parola_ozeti, rol, yetkiler, aktif, olusturma) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?)",
        (yeni_id, k_adi, (ad_soyad or k_adi).strip(), (brans or "").strip(),
         parola_ozeti, rol_norm, yetki_json, simdi()),
    )
    return ogretmen_getir(yeni_id)


def ogretmen_guncelle(ogretmen_id: str, **alanlar) -> dict | None:
    mevcut = ogretmen_getir(ogretmen_id, gizli_kaldir=False)
    if not mevcut:
        return None
    guncel = {}
    if "ad_soyad" in alanlar and alanlar["ad_soyad"]:
        guncel["ad_soyad"] = str(alanlar["ad_soyad"]).strip()
    if "brans" in alanlar and alanlar["brans"] is not None:
        guncel["brans"] = str(alanlar["brans"]).strip()
    if "rol" in alanlar and alanlar["rol"] in ("admin", "standart"):
        if mevcut["rol"] == "admin" and alanlar["rol"] != "admin" and _admin_sayisi() <= 1:
            raise ValueError("Son Admin Öğretmen hesabı standart role düşürülemez.")
        guncel["rol"] = alanlar["rol"]
    if "yetkiler" in alanlar and alanlar["yetkiler"] is not None:
        hedef_rol = guncel.get("rol", mevcut["rol"])
        guncel["yetkiler"] = json.dumps(
            _yetki_listesi_norm(alanlar["yetkiler"], hedef_rol), ensure_ascii=False
        )
    if "parola_ozeti" in alanlar and alanlar["parola_ozeti"]:
        guncel["parola_ozeti"] = alanlar["parola_ozeti"]
    if "son_giris" in alanlar:
        guncel["son_giris"] = alanlar["son_giris"]
    if guncel:
        parcalar = ", ".join(f"{k}=?" for k in guncel)
        calistir(f"UPDATE ogretmen SET {parcalar} WHERE id=?", (*guncel.values(), ogretmen_id))
    return ogretmen_getir(ogretmen_id)


def ogretmen_sil(ogretmen_id: str) -> bool:
    mevcut = ogretmen_getir(ogretmen_id)
    if not mevcut:
        return False
    if mevcut["rol"] == "admin" and _admin_sayisi() <= 1:
        raise ValueError("Son Admin Öğretmen hesabı silinemez.")
    calistir("DELETE FROM ogretmen WHERE id=?", (ogretmen_id,))
    return True


# ---- kayıtlı SSH komutları ----

def _komut_sozluk(satir) -> dict:
    d = dict(satir)
    d["ad"] = d.get("baslik") or ""
    d["sudo"] = bool(d.get("sudo_gerekli", 1))
    d["yerlesik"] = bool(d.get("yerlesik", 0))
    return d


def kayitli_komutlar() -> list[dict]:
    return [_komut_sozluk(s) for s in sorgula(
        "SELECT * FROM kayitli_komut ORDER BY yerlesik DESC, zaman DESC")]


def komut_getir(komut_id: str) -> dict | None:
    s = tek("SELECT * FROM kayitli_komut WHERE id=?", (komut_id,))
    return _komut_sozluk(s) if s else None


def komut_ekle(baslik: str | None = None, komut: str = "", kategori: str = "Genel",
               aciklama: str = "", sudo_gerekli: bool | None = None,
               olusturan: str = "admin", ad: str | None = None,
               sudo: bool | None = None) -> dict:
    komut_baslik = (ad or baslik or "").strip()
    if not komut_baslik:
        raise ValueError("Komut başlığı boş olamaz")
    sudo_bayrak = sudo if sudo is not None else (sudo_gerekli if sudo_gerekli is not None else True)
    kid = "k_" + uuid.uuid4().hex[:10]
    calistir(
        "INSERT INTO kayitli_komut(id, baslik, kategori, komut, aciklama, sudo_gerekli, yerlesik, olusturan, zaman) "
        "VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (kid, komut_baslik, (kategori or "Genel").strip(), komut.strip(),
         (aciklama or "").strip(), 1 if sudo_bayrak else 0, olusturan, simdi()),
    )
    return komut_getir(kid)


def komut_sil(komut_id: str) -> bool:
    mevcut = komut_getir(komut_id)
    if not mevcut:
        return False
    if mevcut.get("yerlesik"):
        raise ValueError("Yerleşik komutlar silinemez")
    calistir("DELETE FROM kayitli_komut WHERE id=?", (komut_id,))
    return True


