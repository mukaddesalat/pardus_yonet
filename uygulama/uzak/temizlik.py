"""Uzak betik — ders sonu temizliği (öğrenci PC'de root olarak çalışır).

Parametre (argv[1], JSON):
    {"hesap": "ogrenci", "mod": "onizleme" | "temizle",
     "alanlar": ["masaustu", ...], "saklama": 5}
Çıktı: tek satır JSON.

Güvenlik (istem §9):
- Kullanıcı dosyaları shell kodu olarak yorumlanmaz; user-dirs.dirs elle ayrıştırılır.
- Her yol ev dizininden başlanarak bileşen bileşen O_NOFOLLOW ile açılır ve taşıma
  bu dosya tanıtıcıları üzerinden yapılır. Önizlemeden sonra bir klasör sembolik
  bağlantıya çevrilse bile ev dizini dışına çıkılamaz.
- Dosyalar silinmez; KARANTINA/<zaman>-<hesap>/veri/ altına, ev dizinine göre aynı
  göreli yolla taşınır. "Yedekten dön" aynı yollara geri koyar (uzak/yedek.py).
"""

import json
import os
import pwd
import re
import shutil
import stat
import sys
import time

KOK = "/var/lib/pardus-sinif-yonetimi"
KARANTINA = KOK + "/karantina"

# alan -> (XDG anahtarı, varsayılan klasör adları); klasörün İÇERİĞİ taşınır
XDG_ALANLARI = {
    "masaustu": ("DESKTOP", ["Masaüstü", "Desktop"]),
    "indirilenler": ("DOWNLOAD", ["İndirilenler", "Downloads"]),
    "belgeler": ("DOCUMENTS", ["Belgeler", "Documents"]),
    "resimler": ("PICTURES", ["Resimler", "Pictures"]),
    "muzik": ("MUSIC", ["Müzik", "Music"]),
    "videolar": ("VIDEOS", ["Videolar", "Videos"]),
}

# alan -> [(göreli yol, tür)]; "icerik": klasörün içindekiler, "kendisi": yolun kendisi
SABIT_ALANLAR = {
    "cop": [(".local/share/Trash", "icerik")],
    "tarayici": [
        (".mozilla", "kendisi"), (".cache/mozilla", "kendisi"),
        (".config/chromium", "kendisi"), (".cache/chromium", "kendisi"),
        (".config/google-chrome", "kendisi"), (".cache/google-chrome", "kendisi"),
    ],
    "son_dosyalar": [
        (".local/share/recently-used.xbel", "kendisi"),
        (".cache/thumbnails", "icerik"),
    ],
}

TARAYICI_SURECLERI = {"firefox", "firefox-esr", "firefox-bin", "chromium",
                      "chromium-browse", "chrome", "google-chrome"}

# Linux'ta her iki bayrak da vardır; getattr yalnızca Windows'ta birim testi içe aktarması içindir.
_KLASOR_BAYRAKLARI = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                      | getattr(os, "O_NOFOLLOW", 0))


def bilesenler(goreli):
    """'a/b/c' -> ['a', 'b', 'c']; boş, '.', '..' içeren yolları reddeder."""
    parcalar = [p for p in goreli.split("/") if p not in ("", ".")]
    if not parcalar or ".." in parcalar:
        raise ValueError("geçersiz göreli yol: %r" % goreli)
    return parcalar


def klasor_ac(ev_fd, parcalar):
    """Ev dizininden başlayıp her bileşeni sembolik bağlantı izlemeden açar."""
    fd = os.dup(ev_fd)
    try:
        for parca in parcalar:
            yeni = os.open(parca, _KLASOR_BAYRAKLARI, dir_fd=fd)
            os.close(fd)
            fd = yeni
        return fd
    except OSError:
        os.close(fd)
        raise


def xdg_oku(ev_fd):
    """~/.config/user-dirs.dirs dosyasını shell çalıştırmadan ayrıştırır.

    Yalnızca "$HOME/..." biçimindeki göreli değerler kabul edilir; "$HOME/"
    (ev dizininin kendisi), mutlak yollar ve '..' içerenler yok sayılır.
    """
    sonuc = {}
    try:
        cfg = klasor_ac(ev_fd, [".config"])
    except OSError:
        return sonuc
    try:
        fd = os.open("user-dirs.dirs", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=cfg)
        with os.fdopen(fd, encoding="utf-8", errors="replace") as f:
            for satir in f.read(65536).splitlines():
                es = re.match(r'^XDG_([A-Z]+)_DIR="\$HOME/([^"]*)"$', satir.strip())
                if not es:
                    continue
                try:
                    sonuc[es.group(1)] = "/".join(bilesenler(es.group(2)))
                except ValueError:
                    pass
    except OSError:
        pass
    finally:
        os.close(cfg)
    return sonuc


def alan_yollari(alan, ev_fd, xdg):
    """Alanın ev dizinine göre göreli hedeflerini [(yol, tür)] olarak döndürür."""
    if alan in SABIT_ALANLAR:
        return list(SABIT_ALANLAR[alan])
    anahtar, varsayilanlar = XDG_ALANLARI[alan]
    adaylar = ([xdg[anahtar]] if anahtar in xdg else []) + varsayilanlar
    for aday in adaylar:
        try:
            fd = klasor_ac(ev_fd, bilesenler(aday))
        except (OSError, ValueError):
            continue
        os.close(fd)
        return [(aday, "icerik")]
    return []


def tarayici_acik_mi(uid):
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if os.stat("/proc/" + pid).st_uid != uid:
                continue
            with open("/proc/%s/comm" % pid) as f:
                ad = f.read().strip()
        except OSError:
            continue
        if ad in TARAYICI_SURECLERI:
            return ad
    return None


class Olcum:
    """Salt okunur boyut ölçümü (karar 26).

    - mantıksal: dosya boyutlarının toplamı (st_size),
    - ayrılmış: diskte gerçekten kapladığı alan (st_blocks × 512; seyrek dosyalar
      küçük, küçük dosyalar blok boyutuna yuvarlanmış görünür),
    - aynı dosya (inode) iç içe klasörlerde veya sabit bağlantıyla iki kez görünse
      de bir kez sayılır,
    - serbest_kalabilir: yalnız TÜM bağlantıları ölçülen kümenin içinde olan
      dosyaların ayrılmış alanı (dışarıda başka adı olan dosya silinse de yer açmaz).
    """

    def __init__(self):
        self.goruldu = {}  # (dev, ino) -> [nlink, görülen, ayrılmış]
        self.adet = 0
        self.mantiksal = 0

    def ekle(self, yol):
        try:
            st = os.lstat(yol)
        except OSError:
            return
        self._kaydet(st)
        if not stat.S_ISDIR(st.st_mode):
            return
        for kok, klasorler, dosyalar in os.walk(yol, followlinks=False):
            for ad in klasorler + dosyalar:
                try:
                    self._kaydet(os.lstat(os.path.join(kok, ad)))
                except OSError:
                    continue

    def _kaydet(self, st):
        anahtar = (st.st_dev, st.st_ino)
        kayit = self.goruldu.get(anahtar)
        if kayit is None:
            # klasörün bağlantı sayısı alt klasörleri sayar; içeriğiyle taşındığından
            # klasör her zaman "tamamı içeride" kabul edilir (nlink=1)
            nlink = 1 if stat.S_ISDIR(st.st_mode) else st.st_nlink
            self.goruldu[anahtar] = [nlink, 1, st.st_blocks * 512]
            self.adet += 1
            if not stat.S_ISDIR(st.st_mode):
                self.mantiksal += st.st_size
        else:
            kayit[1] += 1

    def sonuc(self):
        ayrilmis = sum(k[2] for k in self.goruldu.values())
        serbest = sum(k[2] for k in self.goruldu.values() if k[1] >= k[0])
        return {"adet": self.adet, "bayt": self.mantiksal, "ayrilmis": ayrilmis,
                "serbest_kalabilir": serbest}


def bos_alan(yol):
    try:
        sv = os.statvfs(yol)
        return sv.f_bavail * sv.f_frsize
    except OSError:
        return None


def var_olan_ust(yol):
    while not os.path.exists(yol):
        yol = os.path.dirname(yol)
    return yol


def budanacaklar(klasor, desen, saklama):
    """Yeni kayıt eklenince silinecek eski kayıtlar ve diskte açacakları alan."""
    try:
        adlar = sorted((a for a in os.listdir(klasor) if desen.match(a)), reverse=True)
    except OSError:
        return [], 0
    silinecek = adlar[max(0, max(1, saklama) - 1):]
    olcum = Olcum()
    for ad in silinecek:
        olcum.ekle(os.path.join(klasor, ad))
    return silinecek, olcum.sonuc()["serbest_kalabilir"]


def say(yol):
    """Salt okunur boyut hesabı; sembolik bağlantılar izlenmez."""
    adet = bayt = 0
    try:
        st = os.lstat(yol)
    except OSError:
        return 0, 0
    if not stat.S_ISDIR(st.st_mode):
        return 1, st.st_size
    for kok, klasorler, dosyalar in os.walk(yol, followlinks=False):
        for ad in klasorler + dosyalar:
            try:
                st = os.lstat(os.path.join(kok, ad))
            except OSError:
                continue
            adet += 1
            if not stat.S_ISDIR(st.st_mode):
                bayt += st.st_size
    return adet, bayt


def kaynaklari_bul(ev_fd, ev_dev, goreli, tur):
    """Taşınacak girdileri (kaynak yolu, karantinadaki göreli yol) olarak verir.

    Kaynak yolu /proc/self/fd/<fd>/<ad> biçimindedir: üst klasör sembolik
    bağlantı izlenmeden açıldığı için yol değiştirme yarışı ev dışına çıkamaz.
    Dönüş: (girdiler, açık tanıtıcılar, sorun | None)
    """
    parcalar = bilesenler(goreli)
    if tur == "icerik":
        try:
            fd = klasor_ac(ev_fd, parcalar)
        except OSError as hata:
            return [], [], ("yok" if hata.errno == 2 else "güvensiz yol (%s)" % hata.strerror)
        if os.fstat(fd).st_dev != ev_dev:
            os.close(fd)
            return [], [], "ayrı dosya sistemi / bağlama noktası"
        girdiler = [("/proc/self/fd/%d/%s" % (fd, ad), "/".join(parcalar + [ad]))
                    for ad in sorted(os.listdir(fd))]
        return girdiler, [fd], None

    try:
        ust = klasor_ac(ev_fd, parcalar[:-1])
    except OSError as hata:
        return [], [], ("yok" if hata.errno == 2 else "güvensiz yol (%s)" % hata.strerror)
    try:
        st = os.stat(parcalar[-1], dir_fd=ust, follow_symlinks=False)
    except OSError:
        os.close(ust)
        return [], [], "yok"
    if stat.S_ISLNK(st.st_mode):
        os.close(ust)
        return [], [], "sembolik bağlantı"
    if st.st_dev != ev_dev:
        os.close(ust)
        return [], [], "ayrı dosya sistemi / bağlama noktası"
    return [("/proc/self/fd/%d/%s" % (ust, parcalar[-1]), "/".join(parcalar))], [ust], None


def buda(klasor, desen, saklama):
    """Desene uyan kayıtlardan en yeni `saklama` tanesi dışındakileri siler."""
    try:
        adlar = sorted((a for a in os.listdir(klasor) if desen.match(a)), reverse=True)
    except OSError:
        return 0
    silinen = 0
    for ad in adlar[max(1, saklama):]:
        shutil.rmtree(os.path.join(klasor, ad), ignore_errors=True)
        silinen += 1
    return silinen


def calistir(p):
    hesap, mod = p["hesap"], p["mod"]
    istenen = [a for a in p.get("alanlar", []) if a in XDG_ALANLARI or a in SABIT_ALANLAR]
    try:
        kayit = pwd.getpwnam(hesap)
    except KeyError:
        return {"hata": "'%s' hesabı bu makinede yok" % hesap}
    ev = os.path.realpath(kayit.pw_dir)
    if not os.path.isdir(ev) or ev in ("/", "/home", "/root"):
        return {"hata": "güvensiz ev dizini: %s" % ev}
    if mod == "temizle" and os.geteuid() != 0:
        return {"hata": "temizlik root yetkisi gerektirir"}

    ev_fd = os.open(ev, _KLASOR_BAYRAKLARI)
    acik = [ev_fd]
    try:
        ev_dev = os.fstat(ev_fd).st_dev
        xdg = xdg_oku(ev_fd)
        toplam_olcum = Olcum()
        tarayici = tarayici_acik_mi(kayit.pw_uid) if "tarayici" in istenen else None

        sonuc = {"hesap": hesap, "alanlar": {}}
        plan = {}  # alan -> [(kaynak, göreli)]
        for alan in istenen:
            if alan == "tarayici" and tarayici:
                sonuc["alanlar"][alan] = {"atlandi": "tarayıcı açık (%s)" % tarayici}
                continue
            girdiler, sorunlar = [], []
            for goreli, tur in alan_yollari(alan, ev_fd, xdg):
                bulunan, fdler, sorun = kaynaklari_bul(ev_fd, ev_dev, goreli, tur)
                acik += fdler
                girdiler += bulunan
                if sorun and sorun != "yok":
                    sorunlar.append("%s: %s" % (goreli, sorun))
            if sorunlar and not girdiler:
                sonuc["alanlar"][alan] = {"atlandi": "; ".join(sorunlar)}
                continue
            olcum = Olcum()
            for kaynak, _ in girdiler:
                olcum.ekle(kaynak)
                toplam_olcum.ekle(kaynak)
            bilgi = olcum.sonuc()
            if sorunlar:
                bilgi["uyari"] = "; ".join(sorunlar)
            sonuc["alanlar"][alan] = bilgi
            plan[alan] = girdiler

        # Diskte açılacak alan: dosyalar silinmez, karantinaya TAŞINIR. Karantina ev
        # dizini ile aynı dosya sistemindeyse taşıma yer açmaz; yer, saklama sınırını
        # aşan eski karantinalar budandığında açılır (karar 26).
        ayni = os.stat(var_olan_ust(KARANTINA)).st_dev == ev_dev
        desen = re.compile(r"^\d{8}-\d{6}-%s$" % re.escape(hesap))
        toplam = toplam_olcum.sonuc()
        # taşınacak bir şey yoksa yeni karantina oluşmaz, budama da yapılmaz
        silinecek, budanan_bayt = (budanacaklar(KARANTINA, desen, int(p.get("saklama", 5)))
                                   if toplam["adet"] else ([], 0))
        sonuc["olcum"] = {
            "kaldirilacak": toplam,
            "ayni_dosya_sistemi": ayni,
            "budanacak_kayit": len(silinecek),
            "budanacak_bayt": budanan_bayt,
            "tahmini_acilacak": budanan_bayt + (0 if ayni else toplam["serbest_kalabilir"]),
            "ev_bos": bos_alan(ev),
        }

        if mod == "onizleme":
            return sonuc

        # ---- mod == temizle: karantinaya taşı ----
        os.makedirs(KARANTINA, mode=0o700, exist_ok=True)
        os.chmod(KOK, 0o700)
        os.chmod(KARANTINA, 0o700)
        for _ in range(5):
            ad = "%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), hesap)
            hedef_kok = os.path.join(KARANTINA, ad)
            try:
                os.mkdir(hedef_kok, 0o700)
                break
            except FileExistsError:
                time.sleep(1.1)
        else:
            return {"hata": "karantina klasörü oluşturulamadı"}
        veri = os.path.join(hedef_kok, "veri")
        os.mkdir(veri, 0o700)

        toplam_tasinan = 0
        for alan, girdiler in plan.items():
            tasinan = hatali = 0
            for kaynak, goreli in girdiler:
                hedef = os.path.join(veri, goreli)
                try:
                    os.makedirs(os.path.dirname(hedef), mode=0o700, exist_ok=True)
                    shutil.move(kaynak, hedef)
                    tasinan += 1
                except OSError:
                    hatali += 1
            sonuc["alanlar"][alan]["tasinan"] = tasinan
            sonuc["alanlar"][alan]["hatali"] = hatali
            toplam_tasinan += tasinan

        if not toplam_tasinan:
            shutil.rmtree(hedef_kok, ignore_errors=True)
            sonuc["karantina"] = None
            return sonuc

        manifest = {
            "surum": 1, "tur": "temizlik", "hesap": hesap,
            "zaman": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "alanlar": {a: {"adet": b.get("adet", 0), "bayt": b.get("bayt", 0)}
                        for a, b in sonuc["alanlar"].items() if b.get("tasinan")},
        }
        with open(os.path.join(hedef_kok, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)
        sonuc["karantina"] = ad
        sonuc["budanan"] = buda(KARANTINA, desen, int(p.get("saklama", 5)))
        sonuc["olcum"]["ev_bos_sonra"] = bos_alan(ev)
        return sonuc
    finally:
        for fd in acik:
            try:
                os.close(fd)
            except OSError:
                pass


def ana():
    try:
        sonuc = calistir(json.loads(sys.argv[1]))
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
