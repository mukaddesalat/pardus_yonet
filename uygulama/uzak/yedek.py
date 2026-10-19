"""Uzak betik — profil yedeği, yedek listesi ve yedekten dönüş (öğrenci PC'de root).

Parametre (argv[1], JSON):
    {"mod": "yedekle",    "hesap": "ogrenci", "saklama": 5}
    {"mod": "listele",    "hesap": "ogrenci"}
    {"mod": "geri_yukle", "hesap": "ogrenci", "tur": "profil" | "temizlik", "ad": "..."}
    {"mod": "olc",        "hesap": "ogrenci", "kapsam": "ayarlar" | "tam", "saklama": 5}
Çıktı: tek satır JSON.

Yedekler öğrenci PC'de kalır (karar 13); öğretmen PC'ye dosya aktarılmaz.

Geri yükleme kuralı (proje sahibi kararı, 26 Eyl 2026):
- Hedefte aynı adlı dosya yoksa geri konur.
- Varsa ve SHA-256 özeti aynıysa üzerine yazılır.
- Özeti farklıysa ikisi de tutulur; geri gelen "ad (yedek 26.09.2026 14.30).uzanti" olur.
Ev dizinine yazma, öğrencinin kendi yetkisine düşürülmüş alt süreçte yapılır;
arşivdeki veya ev dizinindeki sembolik bağlantılar root yetkisiyle kullanılamaz.
"""

import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time

KOK = "/var/lib/pardus-sinif-yonetimi"
YEDEK = KOK + "/yedek"
KARANTINA = KOK + "/karantina"
PARCA = 1024 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)  # birim testleri Windows'ta da çalışsın


# ---------------------------------------------------------------- yardımcılar

def ev_dizini(hesap):
    try:
        kayit = pwd.getpwnam(hesap)
    except KeyError:
        raise ValueError("'%s' hesabı bu makinede yok" % hesap)
    ev = os.path.realpath(kayit.pw_dir)
    if not os.path.isdir(ev) or ev in ("/", "/home", "/root"):
        raise ValueError("güvensiz ev dizini: %s" % ev)
    return kayit, ev


def dosya_ozeti(yol):
    sha = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(PARCA), b""):
            sha.update(parca)
    return sha.hexdigest()


def profil_deseni(hesap):
    return re.compile(r"^%s-(\d{8})-(\d{6})\.tar\.gz$" % re.escape(hesap))


def karantina_deseni(hesap):
    return re.compile(r"^(\d{8})-(\d{6})-%s$" % re.escape(hesap))


def zaman_bilgisi(tarih, saat):
    """('20260926', '143000') -> ('2026-09-26T14:30:00', '26.09.2026 14.30')"""
    iso = "%s-%s-%sT%s:%s:%s" % (tarih[:4], tarih[4:6], tarih[6:], saat[:2], saat[2:4], saat[4:])
    etiket = "%s.%s.%s %s.%s" % (tarih[6:], tarih[4:6], tarih[:4], saat[:2], saat[2:4])
    return iso, etiket


def yan_ad(hedef, etiket):
    """'rapor.odt' -> 'rapor (yedek 26.09.2026 14.30).odt'; doluysa ' 2', ' 3'..."""
    klasor, ad = os.path.split(hedef)
    govde, uzanti = os.path.splitext(ad)
    if len(uzanti) > 16:  # uzantı gibi görünmeyen uzun sonek
        govde, uzanti = ad, ""
    ek = " (yedek %s)" % etiket
    for sira in range(1, 1000):
        sayi = "" if sira == 1 else " %d" % sira
        aday = os.path.join(klasor, govde[:180] + ek + sayi + uzanti)
        if not os.path.lexists(aday):
            return aday
    raise OSError("boş ad bulunamadı: %s" % hedef)


def buda(klasor, desen, saklama, ekler=("",)):
    """Desene uyan kayıtlardan en yeni `saklama` tanesi dışındakileri siler."""
    try:
        adlar = sorted((a for a in os.listdir(klasor) if desen.match(a)), reverse=True)
    except OSError:
        return 0
    for ad in adlar[max(1, saklama):]:
        for ek in ekler:
            yol = os.path.join(klasor, ad + ek)
            if os.path.isdir(yol) and not os.path.islink(yol):
                shutil.rmtree(yol, ignore_errors=True)
            else:
                try:
                    os.unlink(yol)
                except OSError:
                    pass
    return max(0, len(adlar) - max(1, saklama))


# ---------------------------------------------------------------- yedekle

def yedekle(p):
    hesap = p["hesap"]
    _, ev = ev_dizini(hesap)

    du = subprocess.run(["du", "-sbx", ev], capture_output=True, text=True)
    kaynak_bayt = int(du.stdout.split()[0]) if du.returncode == 0 and du.stdout else 0
    os.makedirs(YEDEK, mode=0o700, exist_ok=True)
    os.chmod(KOK, 0o700)
    os.chmod(YEDEK, 0o700)
    sv = os.statvfs(YEDEK)
    bos = sv.f_bavail * sv.f_frsize
    if bos < kaynak_bayt + 200 * PARCA:
        return {"hata": "yedek için yetersiz alan: %d MB boş, %d MB gerekli"
                        % (bos // PARCA, kaynak_bayt // PARCA)}

    arsiv = os.path.join(YEDEK, "%s-%s.tar.gz" % (hesap, time.strftime("%Y%m%d-%H%M%S")))
    tar = subprocess.run(
        ["tar", "--warning=no-file-changed", "--one-file-system", "-czf", arsiv,
         "-C", os.path.dirname(ev), os.path.basename(ev)],
        capture_output=True, text=True)
    # rc=1: "dosya değişti" gibi uyarılar; rc>=2 gerçek hata
    if tar.returncode >= 2 or not os.path.exists(arsiv):
        try:
            os.unlink(arsiv)
        except OSError:
            pass
        satirlar = tar.stderr.strip().splitlines()
        return {"hata": "arşiv oluşturulamadı: " + (satirlar[-1][:200] if satirlar else "tar hatası")}
    os.chmod(arsiv, 0o600)

    # doğrulama: arşiv baştan sona okunabiliyor mu (istem §9.13)
    liste = subprocess.run(["tar", "-tzf", arsiv], capture_output=True, text=True)
    kayit_sayisi = len(liste.stdout.splitlines())
    if liste.returncode != 0 or kayit_sayisi == 0:
        os.unlink(arsiv)
        return {"hata": "yedek doğrulanamadı: arşiv okunamıyor"}

    ozet = dosya_ozeti(arsiv)
    with open(arsiv + ".sha256", "w") as f:
        f.write("%s  %s\n" % (ozet, os.path.basename(arsiv)))

    budanan = buda(YEDEK, profil_deseni(hesap), int(p.get("saklama", 5)), ekler=("", ".sha256"))
    return {"arsiv": arsiv, "ad": os.path.basename(arsiv), "bayt": os.path.getsize(arsiv),
            "kayit": kayit_sayisi, "sha256": ozet, "budanan": budanan}


# ---------------------------------------------------------------- listele

def listele(p):
    hesap = p["hesap"]
    yedekler = []

    desen = profil_deseni(hesap)
    for ad in (os.listdir(YEDEK) if os.path.isdir(YEDEK) else []):
        es = desen.match(ad)
        if not es:
            continue
        iso, etiket = zaman_bilgisi(es.group(1), es.group(2))
        yol = os.path.join(YEDEK, ad)
        yedekler.append({"tur": "profil", "ad": ad, "zaman": iso, "etiket": etiket,
                         "bayt": os.path.getsize(yol),
                         "dogrulanabilir": os.path.isfile(yol + ".sha256")})

    desen = karantina_deseni(hesap)
    for ad in (os.listdir(KARANTINA) if os.path.isdir(KARANTINA) else []):
        es = desen.match(ad)
        if not es:
            continue
        iso, etiket = zaman_bilgisi(es.group(1), es.group(2))
        kayit = {"tur": "temizlik", "ad": ad, "zaman": iso, "etiket": etiket,
                 "alanlar": [], "adet": 0, "bayt": 0, "eski_bicim": True}
        try:
            with open(os.path.join(KARANTINA, ad, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            kayit["eski_bicim"] = False
            kayit["alanlar"] = sorted(manifest.get("alanlar", {}))
            kayit["adet"] = sum(a.get("adet", 0) for a in manifest["alanlar"].values())
            kayit["bayt"] = sum(a.get("bayt", 0) for a in manifest["alanlar"].values())
        except (OSError, ValueError, KeyError, AttributeError):
            pass  # manifest'siz eski biçim: listelenir ama geri yüklenemez
        yedekler.append(kayit)

    yedekler.sort(key=lambda y: y["zaman"], reverse=True)
    return {"yedekler": yedekler}


# ---------------------------------------------------------------- geri yükle

def _uye_adi(ad, kok_ad):
    """Arşiv üye adını kök bileşeni atılmış parça demetine çevirir (sabit bağlantılar için)."""
    parcalar = [p for p in ad.split("/") if p not in ("", ".")]
    if parcalar and parcalar[0] == kok_ad:
        parcalar = parcalar[1:]
    return tuple(parcalar)


def birlestir(tf, ev, kok_ad, etiket):
    """Tar akışındaki ağacı `ev` altına kurala göre yerleştirir.

    `kok_ad`: üyelerin ortak ilk bileşeni (atılır); None ise ilk üyeden öğrenilir.
    Öğrenci yetkisiyle çalışır; yine de mutlak yol ve '..' içeren üyeler atlanır.
    """
    sayac = {"yeni": 0, "ayni": 0, "yan_yana": 0, "atlanan": 0, "hatali": 0}
    yeniden = {}  # çakışma nedeniyle yeniden adlandırılan klasörler: parçalar -> yeni parçalar
    yazilan = {}  # arşivdeki (kök atılmış) yol parçaları -> diske yazılan gerçek yol
    sira = [0]

    def yerlestir(kaynak, kip, mtime, hedef, ust):
        """Akışı önce aynı klasörde geçici ada yazar (özet akış sırasında), sonra
        kurala göre yerleştirir. Dönüş: dosyanın konduğu gerçek yol."""
        sira[0] += 1
        gecici = os.path.join(ust, ".psy-geri-%d-%d" % (os.getpid(), sira[0]))
        fd = os.open(gecici, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
                     | getattr(os, "O_BINARY", 0), 0o600)
        sha = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as cikis:
                for parca in iter(lambda: kaynak.read(PARCA), b""):
                    sha.update(parca)
                    cikis.write(parca)
            os.chmod(gecici, kip & 0o777)
            os.utime(gecici, (mtime, mtime))
        except BaseException:
            try:
                os.unlink(gecici)
            except OSError:
                pass
            raise
        if not os.path.lexists(hedef):
            os.rename(gecici, hedef)
            sayac["yeni"] += 1
            return hedef
        ayni = False
        if os.path.isfile(hedef) and not os.path.islink(hedef):
            try:
                ayni = dosya_ozeti(hedef) == sha.hexdigest()
            except OSError:
                ayni = False
        if ayni:
            os.replace(gecici, hedef)
            sayac["ayni"] += 1
            return hedef
        yan = yan_ad(hedef, etiket)
        os.rename(gecici, yan)
        sayac["yan_yana"] += 1
        return yan

    def yeniden_adlandir(parcalar):
        for i in range(len(parcalar), 0, -1):
            onek = tuple(parcalar[:i])
            if onek in yeniden:
                return list(yeniden[onek]) + parcalar[i:]
        return parcalar

    for uye in tf:
        ad = uye.name
        parcalar = [p for p in ad.split("/") if p not in ("", ".")]
        if ad.startswith("/") or ".." in parcalar or not parcalar:
            sayac["atlanan"] += 1
            continue
        if kok_ad is None:
            kok_ad = parcalar[0]
        if parcalar[0] != kok_ad:
            sayac["atlanan"] += 1
            continue
        parcalar = parcalar[1:]
        if not parcalar:
            continue  # kök klasörün kendisi
        anahtar = tuple(parcalar)  # yeniden adlandırmadan önceki arşiv yolu
        parcalar = yeniden_adlandir(parcalar)
        hedef = os.path.join(ev, *parcalar)

        try:
            if uye.isdir():
                if not os.path.lexists(hedef):
                    os.makedirs(hedef, mode=0o700)
                    os.chmod(hedef, uye.mode & 0o777 | 0o700)
                elif os.path.islink(hedef) or not os.path.isdir(hedef):
                    yeni = yan_ad(hedef, etiket)
                    os.makedirs(yeni, mode=0o700)
                    yeniden[tuple(parcalar)] = tuple(os.path.relpath(yeni, ev).split(os.sep))
                continue

            ust = os.path.dirname(hedef)
            if not os.path.isdir(ust):
                os.makedirs(ust, mode=0o700)

            if uye.issym():
                if not os.path.lexists(hedef):
                    os.symlink(uye.linkname, hedef)
                    sayac["yeni"] += 1
                elif os.path.islink(hedef) and os.readlink(hedef) == uye.linkname:
                    sayac["ayni"] += 1
                else:
                    os.symlink(uye.linkname, yan_ad(hedef, etiket))
                    sayac["yan_yana"] += 1
                continue

            if uye.islnk():
                # Sabit bağlantı: hedefi daha önce geri konan dosyanın içeriği ayrı
                # bir dosya olarak konur (bağ ilişkisi değil, içerik korunur).
                kaynak_yol = yazilan.get(_uye_adi(uye.linkname, kok_ad))
                if kaynak_yol is None or not os.path.isfile(kaynak_yol):
                    sayac["atlanan"] += 1
                    continue
                with open(kaynak_yol, "rb") as kaynak:
                    yazilan[anahtar] = yerlestir(kaynak, uye.mode, uye.mtime, hedef, ust)
                continue

            if not uye.isfile():
                sayac["atlanan"] += 1  # aygıt, fifo
                continue

            yazilan[anahtar] = yerlestir(tf.extractfile(uye), uye.mode, uye.mtime, hedef, ust)
        except OSError as hata:
            if hata.errno == 28:  # ENOSPC: devam etmek anlamsız
                sayac["hata"] = "diskte yer kalmadı; geri yükleme yarım kaldı"
                break
            sayac["hatali"] += 1
    return sayac


def _alt_surecte_birlestir(kayit, ev, akis_fd, kip, kok_ad, etiket, besle=None,
                           cocukta_kapat=()):
    """Birleştirmeyi öğrenci yetkisine düşürülmüş alt süreçte yapar.

    `besle`: None değilse, üst süreç (root) bu işlevle akışın yazma ucunu besler.
    `cocukta_kapat`: alt sürecin devralmaması gereken tanıtıcılar (borunun yazma
    ucu açık kalırsa alt süreç hiçbir zaman akış sonunu göremez).
    """
    sonuc_oku, sonuc_yaz = os.pipe()
    pid = os.fork()
    if pid == 0:  # alt süreç
        os.close(sonuc_oku)
        for fd in cocukta_kapat:
            os.close(fd)
        try:
            os.setgroups([])
            os.setgid(kayit.pw_gid)
            os.setuid(kayit.pw_uid)
            os.umask(0o022)
            os.chdir(ev)
            with os.fdopen(akis_fd, "rb") as ham:
                with tarfile.open(fileobj=ham, mode=kip) as tf:
                    sonuc = birlestir(tf, ev, kok_ad, etiket)
        except BaseException as hata:
            sonuc = {"hata": "geri yükleme: %s: %s" % (type(hata).__name__, hata)}
        with os.fdopen(sonuc_yaz, "wb") as f:
            f.write(json.dumps(sonuc, ensure_ascii=False).encode("utf-8"))
        os._exit(0)

    os.close(sonuc_yaz)
    besleme_hatasi = None
    if besle is not None:
        try:
            besle()
        except (BrokenPipeError, OSError) as hata:
            besleme_hatasi = str(hata)
    with os.fdopen(sonuc_oku, "rb") as f:
        metin = f.read().decode("utf-8", errors="replace")
    os.waitpid(pid, 0)
    try:
        sonuc = json.loads(metin)
    except ValueError:
        sonuc = {"hata": "geri yükleme alt süreci sonuç vermedi"}
    if besleme_hatasi and "hata" not in sonuc:
        sonuc["hata"] = "karantina okunamadı: %s" % besleme_hatasi
    return sonuc


def geri_yukle(p):
    if os.geteuid() != 0:
        return {"hata": "geri yükleme root yetkisi gerektirir"}
    hesap, tur, ad = p["hesap"], p["tur"], p["ad"]
    kayit, ev = ev_dizini(hesap)

    if tur == "profil":
        es = profil_deseni(hesap).match(ad)
        if not es:
            return {"hata": "geçersiz yedek adı"}
        yol = os.path.join(YEDEK, ad)
        if not os.path.isfile(yol) or os.path.islink(yol):
            return {"hata": "yedek bulunamadı"}
        try:
            with open(yol + ".sha256") as f:
                beklenen = f.read().split()[0]
        except (OSError, IndexError):
            return {"hata": "yedeğin sağlama dosyası yok; doğrulanamayan yedek geri yüklenmez"}
        if dosya_ozeti(yol) != beklenen:
            return {"hata": "yedek sağlaması tutmuyor; yedek bozulmuş olabilir"}
        _, etiket = zaman_bilgisi(es.group(1), es.group(2))
        fd = os.open(yol, os.O_RDONLY | _NOFOLLOW)
        # alt süreç açık tanıtıcıyı devralır; arşiv dosyasına ayrıca erişmesi gerekmez
        sonuc = _alt_surecte_birlestir(kayit, ev, fd, "r|gz", None, etiket)
        os.close(fd)
        return sonuc

    if tur == "temizlik":
        es = karantina_deseni(hesap).match(ad)
        if not es:
            return {"hata": "geçersiz kayıt adı"}
        klasor = os.path.join(KARANTINA, ad)
        veri = os.path.join(klasor, "veri")
        if not os.path.isfile(os.path.join(klasor, "manifest.json")) or not os.path.isdir(veri):
            return {"hata": "eski biçimli karantina; yönetici kılavuzundaki elle geri yükleme adımlarını izleyin"}
        _, etiket = zaman_bilgisi(es.group(1), es.group(2))
        okuma, yazma = os.pipe()

        def besle():
            os.close(okuma)
            with os.fdopen(yazma, "wb") as cikis:
                with tarfile.open(fileobj=cikis, mode="w|") as tf:
                    tf.add(veri, arcname="veri")  # sembolik bağlantılar izlenmez

        return _alt_surecte_birlestir(kayit, ev, okuma, "r|", "veri", etiket, besle,
                                      cocukta_kapat=(yazma,))

    return {"hata": "bilinmeyen yedek türü"}


# ---------------------------------------------------------------- ölçüm (sıfırlama önizlemesi)

def _olc(yollar):
    """Mantıksal/ayrılmış boyut; aynı inode bir kez sayılır. Ayrıntı: uzak/temizlik.py Olcum."""
    goruldu, adet, mantiksal = {}, 0, 0

    def kaydet(st):
        nonlocal adet, mantiksal
        anahtar = (st.st_dev, st.st_ino)
        if anahtar in goruldu:
            goruldu[anahtar][1] += 1
            return
        nlink = 1 if stat.S_ISDIR(st.st_mode) else st.st_nlink
        goruldu[anahtar] = [nlink, 1, st.st_blocks * 512]
        adet += 1
        if not stat.S_ISDIR(st.st_mode):
            mantiksal += st.st_size

    for yol in yollar:
        try:
            st = os.lstat(yol)
        except OSError:
            continue
        kaydet(st)
        if stat.S_ISDIR(st.st_mode):
            for kok, klasorler, dosyalar in os.walk(yol, followlinks=False):
                for ad in klasorler + dosyalar:
                    try:
                        kaydet(os.lstat(os.path.join(kok, ad)))
                    except OSError:
                        pass
    return {"adet": adet, "bayt": mantiksal,
            "ayrilmis": sum(k[2] for k in goruldu.values()),
            "serbest_kalabilir": sum(k[2] for k in goruldu.values() if k[1] >= k[0])}


def _bos(yol):
    while not os.path.exists(yol):
        yol = os.path.dirname(yol)
    sv = os.statvfs(yol)
    return sv.f_bavail * sv.f_frsize, os.stat(yol).st_dev


def olc(p):
    """Profil sıfırlama önizlemesi: silinecek kapsam, yedek alanı ve budanacak yedekler.

    Yedek arşivinin sıkıştırılmış boyutu içeriğe bağlıdır ve önceden bilinemez;
    bu yüzden diskte açılacak alan kesin sayı değil, alt-üst sınır olarak verilir.
    """
    hesap, kapsam = p["hesap"], p.get("kapsam", "ayarlar")
    if kapsam not in ("ayarlar", "tam"):
        return {"hata": "bilinmeyen kapsam"}
    _, ev = ev_dizini(hesap)
    girdiler = [os.path.join(ev, a) for a in os.listdir(ev)]
    silinecek = [g for g in girdiler if kapsam == "tam" or os.path.basename(g).startswith(".")]
    ev_olcum = _olc([ev])
    sil_olcum = _olc(silinecek)
    tarayici = [a for a in (".mozilla", ".config/chromium", ".config/google-chrome")
                if os.path.lexists(os.path.join(ev, a))]
    belgeler = [a for a in os.listdir(ev) if not a.startswith(".")]

    saklama = int(p.get("saklama", 5))
    desen = profil_deseni(hesap)
    adlar = sorted((a for a in (os.listdir(YEDEK) if os.path.isdir(YEDEK) else []) if desen.match(a)),
                   reverse=True)
    eskiler = adlar[max(0, max(1, saklama) - 1):]
    budanan = sum(os.path.getsize(os.path.join(YEDEK, a)) for a in eskiler
                  if os.path.isfile(os.path.join(YEDEK, a)))

    ev_bos, ev_dev = _bos(ev)
    yedek_bos, yedek_dev = _bos(YEDEK)
    gerekli = ev_olcum["bayt"] + 200 * PARCA  # yedekle() ile aynı kural
    return {
        "kapsam": kapsam,
        "ev": ev_olcum,
        "silinecek": sil_olcum,
        "silinecek_adlar": sorted(os.path.basename(g) for g in silinecek)[:40],
        "gorunur_klasorler": belgeler[:40],
        "tarayici_verisi": tarayici,
        "yedek": {"ust_sinir": ev_olcum["bayt"], "gerekli_bos": gerekli, "bos": yedek_bos,
                  "yeterli": yedek_bos >= gerekli, "budanacak_kayit": len(eskiler),
                  "budanacak_bayt": budanan},
        "ayni_dosya_sistemi": ev_dev == yedek_dev,
        "ev_bos": ev_bos,
    }


# ---------------------------------------------------------------- giriş

def ana():
    try:
        p = json.loads(sys.argv[1])
        mod = p.get("mod")
        if mod == "yedekle":
            sonuc = yedekle(p)
        elif mod == "listele":
            sonuc = listele(p)
        elif mod == "geri_yukle":
            sonuc = geri_yukle(p)
        elif mod == "olc":
            sonuc = olc(p)
        else:
            sonuc = {"hata": "bilinmeyen mod"}
    except ValueError as hata:
        sonuc = {"hata": str(hata)}
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
