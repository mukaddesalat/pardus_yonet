"""Uzak betik — öğretmenin yerel .deb paketini kurma (öğrenci PC'de root).

Kipler (argv[1], JSON):
  {"kip": "al", "kaynak": "/tmp/psy-paket-XXXX/p.deb", "sha256": "..."}
      SFTP ile yönetim hesabının özel geçici klasörüne gelen dosyayı root'a ait
      önbelleğe (/var/cache/pardus-sinif-yonetimi/) kopyalar; SHA-256 tutmazsa reddeder.
  {"kip": "plan", "sha256": "...", "paket": "ad", "surum": "1.0", "mimari": "amd64",
   "kurulu_kb": 123, "boyut": 456,
   "kaldirma_izni": ["veyon-service", ...]?, "esdeger_paketler": ["veyon-service"]?}
      Salt okunur denetim: Pardus sürümü, mimari, boş alan, paket yöneticisi kilidi,
      kurulu sürüm, apt benzetimi (kurulacak / güncellenecek / KALDIRILACAK paketler),
      indirilecek bağımlılıklar ve depo erişimi. `kaldirma_izni` yalnız listedeki
      paketlerin kaldırılmasına izin verir (ör. parçalı Debian Veyon paketlerinin yerine
      tek paketin geçmesi); listede olmayan her kaldırma planı engeller. `esdeger_paketler`
      kurulu sürüm karşılaştırması için aynı yazılımın başka paket adlarıdır.
  {"kip": "kur", ...plan ile aynı}
      Plan koşullarını yeniden denetler; kaldırma ve sürüm düşürme olmadan kurar
      (apt-get --no-remove; --allow-downgrades verilmez) ve kurulu sürümü doğrular.
      `kaldirma_izni` verilmişse --no-remove kullanılmaz; kaldırılacaklar plan
      denetiminden geçmiş (yalnız izinli) paketlerdir.
  {"kip": "temizle", "tut": ["sha256", ...]}
Çıktı: tek satır JSON.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

try:
    import fcntl
except ImportError:  # birim testleri Windows'ta da içe aktarabilsin
    fcntl = None

ONBELLEK = "/var/cache/pardus-sinif-yonetimi"
ORTAM = dict(os.environ, LC_ALL="C", LANG="C", DEBIAN_FRONTEND="noninteractive",
             APT_LISTCHANGES_FRONTEND="none")
KILITLER = ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock",
            "/var/cache/apt/archives/lock", "/var/lib/apt/lists/lock")
SHA_DESENI = re.compile(r"^[0-9a-f]{64}$")
PAKET_DESENI = re.compile(r"^[a-z0-9][a-z0-9+.-]+$")
SURUM_DESENI = re.compile(r"^[A-Za-z0-9.+~:-]+$")


def calistir(argv, zaman=120):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ORTAM)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "zaman aşımı"
    except OSError as hata:
        return 127, "", str(hata)


def dosya_ozeti(yol):
    sha = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1048576), b""):
            sha.update(parca)
    return sha.hexdigest()


def onbellek_yolu(sha):
    if not SHA_DESENI.match(sha or ""):
        raise ValueError("geçersiz SHA-256")
    return os.path.join(ONBELLEK, sha + ".deb")


def al(p):
    kaynak, sha = p["kaynak"], p["sha256"]
    hedef = onbellek_yolu(sha)
    if not re.match(r"^/tmp/psy-paket-[A-Za-z0-9_]+/paket\.deb$", kaynak):
        return {"hata": "beklenmeyen kaynak yolu"}
    sahip = int(os.environ.get("SUDO_UID", "-1"))
    fd = os.open(kaynak, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not (st.st_mode & 0o170000 == 0o100000) or st.st_uid != sahip:
            return {"hata": "kaynak dosya güvenilir değil (tür/sahip)"}
        os.makedirs(ONBELLEK, mode=0o755, exist_ok=True)
        # Önbellek dizini (dizinler için 0o755 standarttır)
        os.chmod(ONBELLEK, 0o755)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
        gecici = hedef + ".yeni"
        with os.fdopen(os.dup(fd), "rb") as giris, open(gecici, "wb") as cikis:
            shutil.copyfileobj(giris, cikis, 1048576)
            cikis.flush()
            os.fsync(cikis.fileno())
    finally:
        os.close(fd)
    if dosya_ozeti(gecici) != sha:
        os.unlink(gecici)
        return {"hata": "aktarım bütünlüğü doğrulanamadı (SHA-256 farklı)"}
    os.chmod(gecici, 0o644)
    os.replace(gecici, hedef)
    shutil.rmtree(os.path.dirname(kaynak), ignore_errors=True)
    return {"durum": "alindi", "yol": hedef}


def kilit_durumu():
    """Paket yöneticisi kilitli mi? Kilidi yalnız dener, hemen bırakır."""
    for yol in KILITLER:
        if not os.path.exists(yol):
            continue
        try:
            fd = os.open(yol, os.O_RDWR)
        except OSError:
            continue
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.lockf(fd, fcntl.LOCK_UN)
        except OSError:
            return yol
        finally:
            os.close(fd)
    return None


def kurulu_surum(paket):
    rc, cikti, _ = calistir(["dpkg-query", "-W", "-f=${Status}\t${Version}", paket])
    if rc != 0 or "\t" not in cikti:
        return None
    durum, surum = cikti.split("\t", 1)
    return surum.strip() if durum.strip().endswith(" installed") else None


def surum_karsilastir(a, islec, b):
    return calistir(["dpkg", "--compare-versions", a, islec, b])[0] == 0


def os_release():
    bilgi = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for satir in f:
                if "=" in satir:
                    ad, deger = satir.rstrip("\n").split("=", 1)
                    bilgi[ad] = deger.strip().strip('"')
    except OSError:
        pass
    return bilgi


def bos_alan(yol):
    while not os.path.exists(yol):
        yol = os.path.dirname(yol)
    sv = os.statvfs(yol)
    return sv.f_bavail * sv.f_frsize


def apt_ciktisi_ayristir(cikti, karsilastir=None):
    """`apt-get -s` çıktısındaki Inst/Remv satırlarını sınıflandırır (saf işlev)."""
    karsilastir = karsilastir or surum_karsilastir
    yeni, guncel, kaldir, dusur = [], [], [], []
    for satir in cikti.splitlines():
        es = re.match(r"^Inst (\S+)(?: \[([^\]]+)\])? \(([^ )]+)", satir)
        if es:
            ad, eski, yeni_surum = es.groups()
            if eski is None:
                yeni.append({"paket": ad, "surum": yeni_surum})
            elif karsilastir(yeni_surum, "lt", eski):
                dusur.append({"paket": ad, "eski": eski, "yeni": yeni_surum})
            else:
                guncel.append({"paket": ad, "eski": eski, "yeni": yeni_surum})
            continue
        es = re.match(r"^Remv (\S+)", satir)
        if es:
            kaldir.append(es.group(1))
    return {"yeni": yeni, "guncellenecek": guncel, "kaldirilacak": kaldir, "dusurulecek": dusur}


def apt_benzetim(yol):
    """apt-get -s: kurulacak/güncellenecek/kaldırılacak paketler (sistem değişmez)."""
    rc, cikti, hata = calistir(["apt-get", "-s", "-q", "-o", "Debug::NoLocking=1",
                                "install", yol], zaman=180)
    sonuc = apt_ciktisi_ayristir(cikti)
    sonuc.update(rc=rc, hata=None if rc == 0 else (hata.strip() or cikti.strip())[-600:])
    return sonuc


def indirilecekler(yol):
    rc, cikti, _ = calistir(["apt-get", "-qq", "--print-uris", "-o", "Debug::NoLocking=1",
                             "install", yol], zaman=180)
    if rc != 0:
        return None
    # yerel paketin kendisi file: adresiyle listelenir; yalnız ağdan inecekler sayılır
    return [s.split()[0].strip("'") for s in cikti.splitlines()
            if s.startswith("'http://") or s.startswith("'https://")]


def depo_erisimi(adresler):
    """İlk indirilecek dosyanın sunucusuna HEAD isteği; None = denenmedi."""
    if not adresler:
        return None
    adres = adresler[0]
    if urllib.parse.urlparse(adres).scheme not in ("http", "https"):
        return None
    try:
        istek = urllib.request.Request(adres, method="HEAD")
        # Yalnızca yukarıda doğrulanmış http/https depolarına HEAD isteği gönderilir
        with urllib.request.urlopen(istek, timeout=6) as yanit:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            return yanit.status < 400
    except Exception:
        return False


def plan(p):
    sha, paket, surum, mimari = p["sha256"], p["paket"], p["surum"], p["mimari"]
    if not PAKET_DESENI.match(paket) or not SURUM_DESENI.match(surum):
        return {"hata": "geçersiz paket adı/sürümü"}
    yol = onbellek_yolu(sha)
    sonuc = {"paket": paket, "surum": surum, "engeller": [], "uyarilar": []}
    osr = os_release()
    sonuc["pardus"] = osr.get("PRETTY_NAME")
    if osr.get("ID") != "pardus":
        sonuc["engeller"].append("Pardus değil (%s)" % osr.get("PRETTY_NAME", "?"))

    rc, yerli, _ = calistir(["dpkg", "--print-architecture"])
    rc2, yabanci, _ = calistir(["dpkg", "--print-foreign-architectures"])
    mimariler = [yerli.strip()] + yabanci.split()
    sonuc["mimari"] = yerli.strip()
    if mimari != "all" and mimari not in mimariler:
        sonuc["engeller"].append("mimari uyumsuz: paket %s, bilgisayar %s" % (mimari, ", ".join(mimariler)))

    kurulu, kurulu_paket = kurulu_surum(paket), paket
    for esdeger in p.get("esdeger_paketler") or []:
        if kurulu is None and PAKET_DESENI.match(esdeger):
            kurulu, kurulu_paket = kurulu_surum(esdeger), esdeger
    sonuc["kurulu_surum"] = kurulu
    sonuc["kurulu_paket"] = kurulu_paket if kurulu is not None else None
    if kurulu is not None:
        if surum_karsilastir(kurulu, "eq", surum):
            sonuc["durum"] = "atlanacak"
            sonuc["neden"] = "aynı sürüm (%s) zaten kurulu; yeniden kurulmaz" % kurulu
            return sonuc
        if surum_karsilastir(kurulu, "gt", surum):
            sonuc["engeller"].append("sürüm düşürme: kurulu %s, paket %s — izin verilmez" % (kurulu, surum))

    gerekli = int(p.get("boyut", 0)) + int(p.get("kurulu_kb", 0)) * 1024 + 100 * 1048576
    sonuc["gerekli_alan"] = gerekli
    sonuc["bos_alan"] = min(bos_alan("/var/cache/apt/archives"), bos_alan("/usr"))
    if sonuc["bos_alan"] < gerekli:
        sonuc["engeller"].append("yetersiz boş alan")

    kilit = kilit_durumu()
    if kilit:
        sonuc["engeller"].append("paket yöneticisi meşgul (%s kilitli); başka kurulum sürüyor olabilir" % kilit)

    if not os.path.isfile(yol):
        sonuc["engeller"].append("paket dosyası bu bilgisayara aktarılmamış")
        sonuc["durum"] = "engellendi"
        return sonuc
    benzetim = apt_benzetim(yol)
    sonuc["apt"] = {k: benzetim[k] for k in ("yeni", "guncellenecek", "kaldirilacak", "dusurulecek")}
    if benzetim["hata"]:
        sonuc["engeller"].append("bağımlılıklar çözülemedi: " + benzetim["hata"])
    izinli = {k for k in (p.get("kaldirma_izni") or []) if PAKET_DESENI.match(k)}
    kaldirilacak = [k.split(":")[0] for k in benzetim["kaldirilacak"]]
    izinsiz = [k for k in kaldirilacak if k not in izinli]
    if izinsiz:
        sonuc["engeller"].append("kurulum şu paketleri KALDIRACAK: %s — izin verilmez"
                                 % ", ".join(izinsiz))
    elif kaldirilacak:
        sonuc["yerine_gececek"] = kaldirilacak
        sonuc["uyarilar"].append("eski paketler kaldırılıp yerine bu paket geçecek: %s"
                                 % ", ".join(kaldirilacak))
    dusen = [d for d in benzetim["dusurulecek"] if d["paket"] != paket]
    if dusen:
        sonuc["engeller"].append("bağımlılık sürümü düşürülecek (%s) — izin verilmez"
                                 % ", ".join(d["paket"] for d in dusen))
    bagimli = [y for y in benzetim["yeni"] if y["paket"] != paket]
    if benzetim["guncellenecek"]:
        diger = [g for g in benzetim["guncellenecek"] if g["paket"] != paket]
        if diger:
            sonuc["uyarilar"].append("%d sistem paketi de güncellenecek" % len(diger))
    adresler = indirilecekler(yol) if not benzetim["hata"] else None
    sonuc["indirilecek"] = len(adresler) if adresler is not None else None
    if adresler:
        erisim = depo_erisimi(adresler)
        sonuc["depo_erisimi"] = erisim
        if erisim is False:
            sonuc["engeller"].append("%d bağımlılık indirilmeli ama paket deposuna erişilemiyor: %s"
                                     % (len(adresler), ", ".join(b["paket"] for b in bagimli) or "?"))
    if sonuc["engeller"]:
        sonuc["durum"] = "engellendi"
    else:
        sonuc["durum"] = "guncellenecek" if kurulu else "kurulacak"
    return sonuc


def kur(p):
    on = plan(p)
    if on.get("hata") or on["durum"] in ("engellendi", "atlanacak"):
        on["kuruldu"] = False
        return on
    yol = onbellek_yolu(p["sha256"])
    if dosya_ozeti(yol) != p["sha256"]:
        return {"durum": "engellendi", "engeller": ["önbellekteki dosyanın SHA-256 özeti tutmuyor"]}
    # kaldırma izni yoksa --no-remove; izin varsa plan() kaldırılacakların yalnız izinliler
    # olduğunu az önce doğruladı (sürüm düşürme hiçbir durumda yapılmaz)
    kaldirma = [] if on.get("yerine_gececek") else ["--no-remove"]
    rc, cikti, hata = calistir(
        ["apt-get", "install", "-y", "-q", *kaldirma,
         "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold", yol],
        zaman=1800)
    kayit = (cikti + "\n" + hata).strip().splitlines()[-15:]
    son = kurulu_surum(p["paket"])
    dogru = rc == 0 and son is not None and surum_karsilastir(son, "eq", p["surum"])
    if dogru:
        try:
            os.unlink(yol)
        except OSError:
            pass
    return {"durum": "kuruldu" if dogru else "hata", "kuruldu": dogru, "kurulu_surum": son,
            "rc": rc, "kayit": kayit, "plan": on}


def temizle(p):
    tut = {s for s in p.get("tut", []) if SHA_DESENI.match(s)}
    silinen = 0
    if os.path.isdir(ONBELLEK):
        for ad in os.listdir(ONBELLEK):
            if ad.endswith(".deb") and ad[:-4] not in tut:
                os.unlink(os.path.join(ONBELLEK, ad))
                silinen += 1
    return {"silinen": silinen}


# ---------------------------------------------------------------- Pardus Yazılım Merkezi / Repo İşlemleri

KORUMALI_PAKETLER = frozenset({
    "apt", "apt-utils", "base-files", "base-passwd", "bash", "bsdutils", "ca-certificates",
    "coreutils", " cron", "dash", "dbus", "debconf", "debianutils", "diffutils", "dpkg",
    "e2fsprogs", "findutils", "gdm3", "gnome-core", "gnome-session", "gnome-shell",
    "grep", "grub-common", "grub-efi-amd64", "grub-pc", "gzip", "hostname", "init",
    "init-system-helpers", "initramfs-tools", "iproute2", "iptables", "libc-bin", "libc6",
    "lightdm", "locales", "login", "mount", "ncurses-base", "ncurses-bin", "network-manager",
    "nftables", "openssh-client", "openssh-server", "pardus-about", "pardus-common",
    "pardus-gnome-desktop", "pardus-menus", "pardus-package-installer", "pardus-software",
    "pardus-update", "pardus-welcome", "passwd", "perl-base", "pkexec", "polkitd",
    "procps", "python3", "python3-apt", "python3-minimal", "sed", "sudo", "systemd",
    "systemd-sysv", "tar", "tzdata", "udev", "util-linux", "veyon", "veyon-configurator",
    "veyon-master", "veyon-plugins", "veyon-service", "xorg", "xserver-xorg",
    "xserver-xorg-core", "xfce4", "xfce4-session", "xfwm4",
})

KORUMALI_ONEKLER = (
    "linux-image-", "linux-headers-", "linux-kbuild-", "grub-", "systemd-",
    "pardus-gnome-", "pardus-xfce-", "gnome-shell-", "xserver-xorg-", "libpam-",
    "libsystemd", "libapt-", "udev", "openssh-", "veyon-",
)

GIZLENECEK_ONEKLER = (
    "lib", "gir1.2-", "fonts-", "xfonts-", "mythes-", "hyphen-", "hunspell-",
    "aspell-", "ispell-", "manpages", "doc-", "linux-headers-", "linux-kbuild-",
    "linux-compiler-", "gcc-", "g++-", "cpp-", "binutils-",
)

GIZLENECEK_SONEKLER = (
    "-dev", "-dbg", "-dbgsym", "-doc", "-data", "-common", "-l10n", "-locales",
    "-bin", "-core", "-minimal", "-base",
)


def korumali_paket_mi(paket_adi, essential="no", priority="optional"):
    ad = (paket_adi or "").split(":")[0].strip().lower()
    if not ad:
        return False
    if essential == "yes" or priority in ("required", "important"):
        return True
    if ad in KORUMALI_PAKETLER:
        return True
    if any(ad.startswith(onek) for onek in KORUMALI_ONEKLER):
        return True
    return False


def _tum_kurulu_sozluk():
    rc, cikti, _ = calistir(["dpkg-query", "-W", "-f=${Package}\t${Status}\t${Version}\n"], zaman=60)
    sonuc = {}
    if rc != 0:
        return sonuc
    for satir in cikti.splitlines():
        parca = satir.split("\t")
        if len(parca) == 3 and parca[1].strip().endswith(" installed"):
            sonuc[parca[0].split(":")[0]] = parca[2].strip()
    return sonuc


def repo_ara(p):
    sorgu = (p.get("sorgu") or "").strip()
    if len(sorgu) < 2 or len(sorgu) > 60 or not re.match(r"^[a-zA-Z0-9.+_-]+(?:\s+[a-zA-Z0-9.+_-]+)*$", sorgu):
        return {"hata": "Arama terimi 2-60 karakter olmalı ve yalnız harf, rakam, '.', '+', '-', '_' içermelidir."}
    kelimeler = sorgu.split()
    rc, cikti, hata = calistir(["apt-cache", "search", "--", *kelimeler], zaman=60)
    if rc != 0:
        return {"hata": "Depo araması başarısız: " + (hata.strip() or cikti.strip())[:300]}
    kurulular = _tum_kurulu_sozluk()
    sonuclar = []
    # Tam veya önekle eşleşenleri öne almak için sıralama
    ham_liste = []
    for satir in cikti.splitlines():
        if " - " not in satir:
            continue
        ad, aciklama = satir.split(" - ", 1)
        ad = ad.strip()
        if not PAKET_DESENI.match(ad):
            continue
        oncelik = 0 if ad == kelimeler[0].lower() else (1 if ad.startswith(kelimeler[0].lower()) else (
            2 if not ad.startswith("lib") else 3))
        ham_liste.append((oncelik, ad, aciklama.strip()))
    ham_liste.sort(key=lambda x: (x[0], x[1]))
    for _, ad, aciklama in ham_liste[:80]:
        surum = kurulular.get(ad)
        korumali = korumali_paket_mi(ad)
        sonuclar.append({
            "paket": ad,
            "aciklama": aciklama,
            "kurulu": surum is not None,
            "kurulu_surum": surum,
            "korumali": korumali,
        })
    return {"sorgu": sorgu, "sonuclar": sonuclar}


def kurulu_listele(p):
    tum_paketler = bool(p.get("tum_paketler", False))
    rc_m, cikti_m, _ = calistir(["apt-mark", "showmanual"], zaman=30)
    elle_kurulan = {s.split(":")[0].strip() for s in cikti_m.splitlines() if s.strip()} if rc_m == 0 else set()
    rc, cikti, hata = calistir(
        ["dpkg-query", "-W",
         "-f=${Package}\t${Status}\t${Version}\t${Installed-Size}\t${Section}\t${Essential}\t${Priority}\t${binary:Summary}\n"],
        zaman=90)
    if rc != 0:
        return {"hata": "Kurulu paketler okunamadı: " + (hata.strip() or cikti.strip())[:300]}
    uygulamalar = []
    for satir in cikti.splitlines():
        parca = satir.split("\t")
        if len(parca) < 8:
            continue
        ad, durum, surum, boyut_kb, bolum, essential, priority, ozet = parca[:8]
        if not durum.strip().endswith(" installed"):
            continue
        ad_yaln = ad.split(":")[0].strip()
        essential = essential.strip().lower()
        priority = priority.strip().lower()
        bolum_alt = bolum.split("/")[-1].strip().lower()
        korumali = korumali_paket_mi(ad_yaln, essential, priority)
        if not tum_paketler:
            if elle_kurulan and ad_yaln not in elle_kurulan and bolum_alt not in (
                    "editors", "education", "electronics", "games", "gnome", "graphics",
                    "math", "net", "science", "sound", "text", "utils", "video", "web", "x11"):
                continue
            if any(ad_yaln.startswith(o) for o in GIZLENECEK_ONEKLER):
                continue
            if any(ad_yaln.endswith(s) for s in GIZLENECEK_SONEKLER) and ad_yaln not in ("firefox-esr", "python3-pip"):
                continue
            if ad_yaln.startswith("python3-") and ad_yaln not in ("python3-pip", "python3-tk", "python3-pygame", "python3-pyqt5"):
                continue
        try:
            kb = int(boyut_kb.strip() or "0")
        except ValueError:
            kb = 0
        uygulamalar.append({
            "paket": ad_yaln,
            "surum": surum.strip(),
            "boyut_kb": kb,
            "bolum": bolum.strip(),
            "aciklama": ozet.strip(),
            "korumali": korumali,
            "koruma_nedeni": "Temel sistem / masaüstü / yönetim bileşeni" if korumali else None,
        })
    uygulamalar.sort(key=lambda x: (x["korumali"], x["paket"]))
    return {"uygulamalar": uygulamalar, "toplam": len(uygulamalar)}


def repo_kur(p):
    paket_listesi = [x.strip() for x in (p.get("paketler") or []) if x and x.strip()]
    if not paket_listesi:
        return {"hata": "Kurulacak paket seçilmedi"}
    for ad in paket_listesi:
        if not PAKET_DESENI.match(ad):
            return {"hata": "Geçersiz paket adı: %s" % ad}
    kilit = kilit_durumu()
    if kilit:
        return {"hata": "Paket yöneticisi meşgul (%s kilitli); başka bir işlem sürüyor olabilir" % kilit}
    if p.get("guncelle", True):
        calistir(["apt-get", "update", "-q"], zaman=180)
    # Önce benzetim: hiçbir paketin kaldırılmayacağını doğrula
    rc_s, cikti_s, hata_s = calistir(
        ["apt-get", "-s", "-q", "-o", "Debug::NoLocking=1", "install", "--no-remove", "--", *paket_listesi],
        zaman=180)
    benzetim = apt_ciktisi_ayristir(cikti_s)
    if rc_s != 0:
        return {"hata": "Paket deposunda bulunamadı veya bağımlılık hatası: " + (hata_s.strip() or cikti_s.strip())[-400:]}
    if benzetim["kaldirilacak"]:
        return {"hata": "Kurulum mevcut paketleri kaldıracağı için engellendi: " + ", ".join(benzetim["kaldirilacak"])}
    rc, cikti, hata = calistir(
        ["apt-get", "install", "-y", "-q", "--no-remove",
         "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold",
         "--", *paket_listesi],
        zaman=1800)
    kurulanlar = {}
    eksikler = []
    for ad in paket_listesi:
        s = kurulu_surum(ad)
        if s:
            kurulanlar[ad] = s
        else:
            eksikler.append(ad)
    if rc != 0 or eksikler:
        return {
            "hata": "Kurulum tamamlanamadı (%s): %s" % (
                ", ".join(eksikler) or "apt hatası",
                (hata.strip() or cikti.strip())[-400:]
            ),
            "kurulanlar": kurulanlar,
        }
    return {
        "durum": "kuruldu",
        "kurulanlar": kurulanlar,
        "yeni_bagimlilik_sayisi": max(0, len(benzetim["yeni"]) - len(paket_listesi)),
        "kayit": (cikti + "\n" + hata).strip().splitlines()[-10:],
    }


def repo_kaldir(p):
    paket_listesi = [x.strip() for x in (p.get("paketler") or []) if x and x.strip()]
    if not paket_listesi:
        return {"hata": "Kaldırılacak paket seçilmedi"}
    for ad in paket_listesi:
        if not PAKET_DESENI.match(ad):
            return {"hata": "Geçersiz paket adı: %s" % ad}
        if korumali_paket_mi(ad):
            return {"hata": "Korumalı sistem paketi kaldırılamaz: %s" % ad}
    kilit = kilit_durumu()
    if kilit:
        return {"hata": "Paket yöneticisi meşgul (%s kilitli); başka bir işlem sürüyor olabilir" % kilit}
    kurulu_olanlar = [ad for ad in paket_listesi if kurulu_surum(ad) is not None]
    if not kurulu_olanlar:
        return {"durum": "atlandi", "mesaj": "Seçilen paketler bu bilgisayarda zaten kurulu değil", "kaldirilanlar": []}
    # Benzetim ile kaldırılacak tüm paketleri denetle (sistem paketi etkilenirse engelle!)
    rc_s, cikti_s, hata_s = calistir(
        ["apt-get", "-s", "-q", "-o", "Debug::NoLocking=1", "remove", "--", *kurulu_olanlar],
        zaman=120)
    if rc_s != 0:
        return {"hata": "Kaldırma benzetimi başarısız: " + (hata_s.strip() or cikti_s.strip())[-400:]}
    benzetim = apt_ciktisi_ayristir(cikti_s)
    tum_kaldirilacak = [k.split(":")[0] for k in benzetim["kaldirilacak"]]
    tehlikeli = [k for k in tum_kaldirilacak if korumali_paket_mi(k)]
    if tehlikeli:
        return {
            "hata": (
                "GÜVENLİK ENGELİ: Bu paketin kaldırılması kritik sistem bileşenlerini de (%s) "
                "kaldıracağı için işlem otomatik olarak durduruldu." % ", ".join(tehlikeli[:8])
            )
        }
    yan_etki = [k for k in tum_kaldirilacak if k not in kurulu_olanlar]
    if len(yan_etki) > 25:
        return {
            "hata": (
                "GÜVENLİK ENGELİ: Bu işlem %d ek paketi daha kaldıracağı için güvenlik amacıyla engellendi."
                % len(yan_etki)
            )
        }
    alt_komut = "purge" if p.get("artiklari_temizle") else "remove"
    rc, cikti, hata = calistir(
        ["apt-get", alt_komut, "-y", "-q",
         "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold",
         "--", *kurulu_olanlar],
        zaman=900)
    hala_kurulu = [ad for ad in kurulu_olanlar if kurulu_surum(ad) is not None]
    if rc != 0 or hala_kurulu:
        return {
            "hata": "Kaldırma tamamlanamadı (%s): %s" % (
                ", ".join(hala_kurulu) or "apt hatası",
                (hata.strip() or cikti.strip())[-400:]
            )
        }
    return {
        "durum": "kaldirildi",
        "kaldirilanlar": kurulu_olanlar,
        "ek_kaldirilanlar": yan_etki,
        "kayit": (cikti + "\n" + hata).strip().splitlines()[-10:],
    }


def ana():
    try:
        p = json.loads(sys.argv[1])
        if os.geteuid() != 0:
            sonuc = {"hata": "root yetkisi gerekli"}
        else:
            sonuc = {
                "al": al, "plan": plan, "kur": kur, "temizle": temizle,
                "repo_ara": repo_ara, "kurulu_listele": kurulu_listele,
                "repo_kur": repo_kur, "repo_kaldir": repo_kaldir,
            }[p["kip"]](p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
