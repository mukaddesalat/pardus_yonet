"""Uzak betik — hp/pardus yönetim hesabı tekilleştirme (öğrenci PC'de root).

Kipler (argv[1], JSON):
    {"kip": "kapsam", "hesaplar": ["pardus", "hp"]}
        Salt okunur: her hesabın ev dizini boyutu, oturum/süreç, sudo yetkisi,
        cron işi, yetkili anahtar sayısı ve giriş ekranı ayarı.
    {"kip": "yedekle", "hesap": "hp"}
        Silinecek hesabın ev dizini ve hesap kayıtları (passwd/group/shadow
        satırları) /var/lib/pardus-sinif-yonetimi/hesap-yedekleri/ altına
        alınır; arşiv okunarak ve SHA-256 ile doğrulanır.
    {"kip": "sil", "hesap": "hp", "korunan": "pardus", "anahtar": "<blob>",
     "arsiv": "...", "sha256": "..."}
        Güvenlik koşulları sağlanırsa hesabı siler. Koşullar: yalnız pardus/hp,
        korunan hesap var ve parolasız sudo'su tanımlı, korunan hesabın
        authorized_keys dosyasında uygulama anahtarı var, doğrulanmış yedek var,
        silinecek hesabın açık oturumu yok.
Çıktı: tek satır JSON.
"""

import grp
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time

YONETIM = ("pardus", "hp")
KOK = "/var/lib/pardus-sinif-yonetimi"
YEDEK = KOK + "/hesap-yedekleri"
SUDOERS = "/etc/sudoers.d/pardus-sinif-yonetimi"
SSHD_EK = "/etc/ssh/sshd_config.d/pardus-sinif-yonetimi.conf"
ORTAM = dict(os.environ, LC_ALL="C", LANG="C")


def calistir(argv, zaman=60):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ORTAM)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as hata:
        return 127, "", str(hata)


def ayrilmis_boyut(kok):
    """Diskte kapladığı alan (st_blocks); sabit bağlantılar bir kez sayılır."""
    goruldu, toplam = set(), 0
    try:
        kok_dev = os.lstat(kok).st_dev
    except OSError:
        return None
    for yol, klasorler, dosyalar in os.walk(kok, followlinks=False):
        klasorler[:] = [k for k in klasorler
                        if os.lstat(os.path.join(yol, k)).st_dev == kok_dev]
        for ad in klasorler + dosyalar:
            try:
                st = os.lstat(os.path.join(yol, ad))
            except OSError:
                continue
            if (st.st_dev, st.st_ino) in goruldu:
                continue
            goruldu.add((st.st_dev, st.st_ino))
            toplam += st.st_blocks * 512
    return toplam


def kendi_oturumum():
    """Bu betiği çalıştıran SSH bağlantısının logind oturumu (sudo yeni oturum açmaz)."""
    try:
        with open("/proc/self/sessionid") as f:
            return f.read().strip()
    except OSError:
        return None


def oturumlar(hesap):
    """Hesabın açık oturumları; uygulamanın kendi bağlantısı ve kapanmakta olanlar hariç."""
    rc, cikti, _ = calistir(["loginctl", "list-sessions", "--no-legend"])
    if rc != 0:
        return []
    kendi, sonuc = kendi_oturumum(), []
    for satir in cikti.splitlines():
        p = satir.split()
        if len(p) < 3 or p[2] != hesap or p[0] == kendi:
            continue
        _, ayrinti, _ = calistir(["loginctl", "show-session", p[0], "-p", "State",
                                  "-p", "Remote", "-p", "Type"])
        oz = dict(x.split("=", 1) for x in ayrinti.splitlines() if "=" in x)
        if oz.get("State") == "closing":
            continue
        sonuc.append({"kimlik": p[0], "durum": oz.get("State"), "tur": oz.get("Type"),
                      "uzak": oz.get("Remote") == "yes"})
    return sonuc


def oturum_var_mi(hesap):
    return bool(oturumlar(hesap))


def surec_var_mi(hesap):
    return calistir(["pgrep", "-u", hesap])[0] == 0


def sudo_bilgisi(hesap):
    rc, cikti, _ = calistir(["sudo", "-n", "-l", "-U", hesap])
    return {"sudo": rc == 0 and "may run the following" in cikti,
            "parolasiz": bool(re.search(r"NOPASSWD:\s*ALL", cikti))}


def anahtar_sayisi(ev):
    yol = os.path.join(ev, ".ssh", "authorized_keys")
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            return sum(1 for s in f if s.strip() and not s.lstrip().startswith("#"))
    except OSError:
        return 0


def kapsam(p):
    sonuc = {}
    for ad in p.get("hesaplar", YONETIM):
        if ad not in YONETIM:
            continue
        try:
            k = pwd.getpwnam(ad)
        except KeyError:
            sonuc[ad] = None
            continue
        gruplar = sorted({g.gr_name for g in grp.getgrall() if ad in g.gr_mem})
        rc, son, _ = calistir(["lastlog", "-u", ad])
        son_giris = son.strip().splitlines()[-1] if rc == 0 and son.strip() else None
        if son_giris and "Never logged in" in son_giris:
            son_giris = "hiç giriş yapılmamış"
        sonuc[ad] = {
            "uid": k.pw_uid, "ev": k.pw_dir, "gruplar": gruplar,
            "ev_bayt": ayrilmis_boyut(k.pw_dir) if os.path.isdir(k.pw_dir) else 0,
            "oturum": oturum_var_mi(ad), "oturumlar": oturumlar(ad), "surec": surec_var_mi(ad),
            "cron": os.path.exists("/var/spool/cron/crontabs/" + ad),
            "anahtar_sayisi": anahtar_sayisi(k.pw_dir),
            "son_giris": son_giris,
            **sudo_bilgisi(ad),
        }
    return {"hesaplar": sonuc}


def dosya_ozeti(yol):
    sha = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1048576), b""):
            sha.update(parca)
    return sha.hexdigest()


def _satirlar(yol, ad):
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            return [s.rstrip("\n") for s in f if s.split(":", 1)[0] == ad
                    or (yol.endswith("group") and ad in s.rstrip("\n").split(":")[-1].split(","))]
    except OSError:
        return []


def yedekle(p):
    ad = p["hesap"]
    if ad not in YONETIM:
        return {"hata": "yalnız pardus/hp hesapları yedeklenir"}
    try:
        k = pwd.getpwnam(ad)
    except KeyError:
        return {"hata": "'%s' hesabı yok" % ad}
    os.makedirs(YEDEK, mode=0o700, exist_ok=True)
    # Yedek dizinleri yalnızca root tarafından okunabilir olmalıdır
    os.chmod(KOK, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    os.chmod(YEDEK, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    zaman = time.strftime("%Y%m%d-%H%M%S")
    arsiv = os.path.join(YEDEK, "%s-%s.tar.gz" % (ad, zaman))
    ev = os.path.realpath(k.pw_dir)
    if os.path.isdir(ev) and ev not in ("/", "/home", "/root"):
        gerekli = ayrilmis_boyut(ev) or 0
        sv = os.statvfs(YEDEK)
        if sv.f_bavail * sv.f_frsize < gerekli + 100 * 1048576:
            return {"hata": "hesap yedeği için yetersiz alan"}
        tar = subprocess.run(["tar", "--warning=no-file-changed", "--one-file-system", "-czf",
                              arsiv, "-C", os.path.dirname(ev), os.path.basename(ev)],
                             capture_output=True, text=True, env=ORTAM)
        if tar.returncode >= 2 or not os.path.exists(arsiv):
            try:
                os.unlink(arsiv)
            except OSError:
                pass
            return {"hata": "hesap yedeği alınamadı: " + tar.stderr.strip()[-200:]}
    else:
        subprocess.run(["tar", "-czf", arsiv, "--files-from", "/dev/null"], env=ORTAM)
    os.chmod(arsiv, 0o600)
    liste = subprocess.run(["tar", "-tzf", arsiv], capture_output=True, text=True, env=ORTAM)
    if liste.returncode != 0:
        os.unlink(arsiv)
        return {"hata": "hesap yedeği doğrulanamadı"}
    kayitlar = {dosya: _satirlar(dosya, ad) for dosya in
                ("/etc/passwd", "/etc/shadow", "/etc/group", "/etc/gshadow")}
    ek = os.path.join(YEDEK, "%s-%s.json" % (ad, zaman))
    fd = os.open(ek, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"hesap": ad, "zaman": zaman, "kayitlar": kayitlar}, f, ensure_ascii=False)
    return {"arsiv": arsiv, "sha256": dosya_ozeti(arsiv), "bayt": os.path.getsize(arsiv),
            "kayit": len(liste.stdout.splitlines())}


def _anahtar_var(ev, blob):
    try:
        with open(os.path.join(ev, ".ssh", "authorized_keys"), encoding="utf-8", errors="replace") as f:
            return any(blob in s.split() for s in f)
    except OSError:
        return False


def _sudoers_hesap_cikar(ad):
    """Uygulamanın sudoers dosyasından yalnız bu hesabın satırını çıkarır (visudo ile)."""
    if not os.path.isfile(SUDOERS) or os.path.islink(SUDOERS):
        return
    with open(SUDOERS, encoding="utf-8") as f:
        eski = f.read()
    yeni = "".join(s for s in eski.splitlines(True) if not s.startswith(ad + " "))
    if yeni == eski:
        return
    gecici = "/etc/sudoers.d/.pardus-sinif-yonetimi.%d" % os.getpid()
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(yeni)
    os.chmod(gecici, 0o440)
    if calistir(["visudo", "-cf", gecici])[0] == 0:
        os.replace(gecici, SUDOERS)
    else:
        os.unlink(gecici)


def _sshd_hesap_cikar(ad):
    if not os.path.isfile(SSHD_EK) or os.path.islink(SSHD_EK):
        return
    with open(SSHD_EK, encoding="utf-8") as f:
        eski = f.read()
    yeni = "".join(s for s in eski.splitlines(True) if s.strip() not in
                   ("AllowUsers %s" % ad, "AllowGroups %s" % ad))
    if yeni != eski:
        with open(SSHD_EK, "w", encoding="utf-8") as f:
            f.write(yeni)
        if calistir(["sshd", "-t"])[0] == 0:
            calistir(["systemctl", "reload", "ssh"])
        else:
            with open(SSHD_EK, "w", encoding="utf-8") as f:
                f.write(eski)


def sil(p):
    ad, korunan = p["hesap"], p["korunan"]
    if ad not in YONETIM or korunan not in YONETIM or ad == korunan:
        return {"hata": "yalnız pardus/hp arasında, farklı iki hesapla çalışır"}
    try:
        k = pwd.getpwnam(ad)
        kk = pwd.getpwnam(korunan)
    except KeyError as hata:
        return {"hata": "hesap bulunamadı: %s" % hata}
    if k.pw_uid < 1000 or k.pw_uid == 0:
        return {"hata": "sistem hesabı silinemez"}
    if os.environ.get("SUDO_USER") == ad:
        return {"hata": "bağlantıyı sağlayan hesap kendi oturumundan silinemez; "
                        "önce korunan hesapla bağlanılmalı"}
    if not sudo_bilgisi(korunan)["parolasiz"]:
        return {"hata": "korunan hesabın (%s) parolasız sudo yetkisi doğrulanamadı; silme yapılmadı" % korunan}
    if not _anahtar_var(kk.pw_dir, p.get("anahtar", "")):
        return {"hata": "korunan hesapta uygulama anahtarı yok; silme yapılmadı"}
    arsiv = p.get("arsiv", "")
    if not (arsiv.startswith(YEDEK + "/") and os.path.isfile(arsiv)
            and dosya_ozeti(arsiv) == p.get("sha256")):
        return {"hata": "doğrulanmış hesap yedeği bulunamadı; silme yapılmadı"}
    # Uygulamanın silinecek hesapla kurduğu önceki bağlantı yeni kapandıysa oturumu
    # birkaç saniye içinde düşer; başka (gerçek) bir oturum varsa silme yapılmaz.
    for _ in range(15):
        if not oturum_var_mi(ad):
            break
        time.sleep(1)
    else:
        return {"hata": "'%s' hesabında açık oturum var (%s); silme yapılmadı"
                        % (ad, ", ".join("%s %s" % (o["tur"], "uzak" if o["uzak"] else "yerel")
                                         for o in oturumlar(ad)))}

    if surec_var_mi(ad):
        calistir(["pkill", "-TERM", "-u", ad])
        time.sleep(2)
        if surec_var_mi(ad):
            calistir(["pkill", "-KILL", "-u", ad])
            time.sleep(1)
    calistir(["loginctl", "disable-linger", ad])
    rc, _, hata = calistir(["userdel", "-r", ad], zaman=300)
    # 12: ev dizini silinemedi (ör. yoktu); hesap yine silinmiştir
    if rc not in (0, 12):
        return {"hata": "userdel başarısız (rc=%d): %s" % (rc, hata.strip()[-200:])}
    try:
        pwd.getpwnam(ad)
        return {"hata": "hesap silinemedi"}
    except KeyError:
        pass
    try:
        os.unlink("/var/lib/AccountsService/users/" + ad)
    except OSError:
        pass
    _sudoers_hesap_cikar(ad)
    _sshd_hesap_cikar(ad)
    ev_kaldi = os.path.isdir(k.pw_dir)
    if ev_kaldi and os.path.realpath(k.pw_dir) not in ("/", "/home", "/root"):
        shutil.rmtree(k.pw_dir, ignore_errors=True)
    return {"durum": "silindi", "hesap": ad, "userdel_rc": rc}


def ana():
    try:
        p = json.loads(sys.argv[1])
        if os.geteuid() != 0:
            sonuc = {"hata": "root yetkisi gerekli"}
        else:
            sonuc = {"kapsam": kapsam, "yedekle": yedekle, "sil": sil}[p["kip"]](p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
