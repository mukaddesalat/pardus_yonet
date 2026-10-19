"""Uzak betik — yetkili hesap hazırlığı (öğrenci PC'de root olarak çalışır).

Kipler (argv[1], JSON):
    {"kip": "sudoers", "hesaplar": ["pardus"]}
        Yönetim hesaplarına parolasız sudo (NOPASSWD: ALL) verir. Dosya önce
        sudo'nun okumadığı geçici adla yazılır, `visudo -cf` ile doğrulanır, sonra
        yerine taşınır ve tüm yapılandırma `visudo -c` ile yeniden denetlenir;
        başarısızsa eski hâline döndürülür. Hesap listesi boşsa dosya kaldırılır.
    {"kip": "ogrenci", "hesap": "ogrenci"}
        Öğrenci hesabı yoksa oluşturur (sudo grubu VERİLMEZ, parola boş: giriş
        ekranından parolasız girilir; SSH boş parolayı kabul etmez).
    {"kip": "sshd_izin", "hesap": "hp"}
        sshd AllowUsers/AllowGroups kısıtı varsa hesabın girebilmesi için ek izin
        dosyası yazar (`sshd -t` ile doğrulanır). DenyUsers/DenyGroups engelini
        kendiliğinden kaldırmaz; açık hata verir.
Çıktı: tek satır JSON.
"""

import fnmatch
import grp
import json
import os
import pwd
import re
import subprocess
import sys

SUDOERS = "/etc/sudoers.d/pardus-sinif-yonetimi"
SSHD_EK = "/etc/ssh/sshd_config.d/pardus-sinif-yonetimi.conf"
YONETIM = ("pardus", "hp")
HESAP_DESENI = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
ORTAM = dict(os.environ, LC_ALL="C", LANG="C")
OGRENCI_GRUPLARI = ("audio", "video", "plugdev", "netdev", "bluetooth", "scanner", "users")
YETKILI_GRUPLAR = {"sudo", "admin", "wheel", "adm"}


def calistir(argv, zaman=30, girdi=None):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman,
                           env=ORTAM, input=girdi)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as hata:
        return 127, "", str(hata)


def sudoers_icerigi(hesaplar):
    satirlar = [
        "# Pardus Sınıf Yönetimi — yönetim hesabına parolasız sudo.",
        "# UYARI: NOPASSWD: ALL bu hesaba root eşdeğeri yetki verir (karar 22).",
        "# Uygulama tarafından yönetilir; elle değiştirmeyin.",
    ]
    satirlar += ["%s ALL=(ALL:ALL) NOPASSWD: ALL" % h for h in hesaplar]
    return "\n".join(satirlar) + "\n"


def mevcut_hesaplar():
    """Uygulamanın sudoers dosyasında yetkilendirilmiş hesaplar."""
    try:
        with open(SUDOERS, encoding="utf-8") as f:
            return [s.split()[0] for s in f if re.match(r"^[a-z_][a-z0-9_-]* ALL=", s)]
    except OSError:
        return []


def sudoers(p):
    if "hesaplar" in p:
        hesaplar = list(p["hesaplar"] or [])
    else:  # ekle / çıkar: diğer yönetim hesabının satırı korunur
        hesaplar = [h for h in mevcut_hesaplar() if h not in (p.get("cikar") or [])]
        hesaplar += [h for h in (p.get("ekle") or []) if h not in hesaplar]
    for h in hesaplar:
        if h not in YONETIM or not HESAP_DESENI.match(h):
            return {"hata": "yalnız yönetim hesapları (pardus/hp) yetkilendirilebilir: %r" % h}
        try:
            pwd.getpwnam(h)
        except KeyError:
            return {"hata": "'%s' hesabı bu bilgisayarda yok" % h}
    if not os.path.isdir("/etc/sudoers.d"):
        return {"hata": "/etc/sudoers.d yok; sudo yapılandırması desteklenmiyor"}

    eski = None
    if os.path.lexists(SUDOERS):
        if os.path.islink(SUDOERS):
            return {"hata": "%s sembolik bağlantı; dokunulmadı" % SUDOERS}
        with open(SUDOERS, encoding="utf-8") as f:
            eski = f.read()

    if not hesaplar:
        if eski is not None:
            os.unlink(SUDOERS)
        return {"durum": "kaldirildi" if eski is not None else "zaten_yok"}

    yeni = sudoers_icerigi(hesaplar)
    if eski == yeni:
        rc, _, hata = calistir(["visudo", "-c"])
        return {"durum": "zaten_var"} if rc == 0 else {"hata": "sudo yapılandırması bozuk: " + hata.strip()[-200:]}

    # Nokta içeren adları sudo okumaz (sudoers.d kuralı): yarım dosya hiç etkin olmaz.
    gecici = "/etc/sudoers.d/.pardus-sinif-yonetimi.%d" % os.getpid()
    fd = os.open(gecici, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(yeni)
        f.flush()
        os.fsync(f.fileno())
    os.chown(gecici, 0, 0)
    rc, _, hata = calistir(["visudo", "-cf", gecici])
    if rc != 0:
        os.unlink(gecici)
        return {"hata": "visudo doğrulaması başarısız; değişiklik uygulanmadı: " + hata.strip()[-200:]}
    os.replace(gecici, SUDOERS)
    rc, _, hata = calistir(["visudo", "-c"])
    if rc != 0:  # tüm yapılandırma bozulduysa eski hâle dön
        if eski is None:
            os.unlink(SUDOERS)
        else:
            with open(SUDOERS, "w", encoding="utf-8") as f:
                f.write(eski)
            os.chmod(SUDOERS, 0o440)
        return {"hata": "sudo yapılandırması doğrulanamadı; eski hâline döndürüldü: " + hata.strip()[-200:]}
    return {"durum": "yazildi", "dosya": SUDOERS}


def ogrenci(p):
    ad = p.get("hesap", "ogrenci")
    if not HESAP_DESENI.match(ad) or ad in YONETIM or ad == "root":
        return {"hata": "geçersiz öğrenci hesabı adı"}
    try:
        kayit = pwd.getpwnam(ad)
    except KeyError:
        kayit = None
    if kayit is not None:
        gruplar = {g.gr_name for g in grp.getgrall() if ad in g.gr_mem}
        return {"durum": "zaten_var", "uid": kayit.pw_uid,
                "yetkili_grup": sorted(gruplar & YETKILI_GRUPLAR)}

    mevcut = {g.gr_name for g in grp.getgrall()}
    ek = [g for g in OGRENCI_GRUPLARI if g in mevcut]
    argv = ["useradd", "-m", "-s", "/bin/bash", "-c", "Ogrenci"]
    if ek:
        argv += ["-G", ",".join(ek)]
    rc, _, hata = calistir(argv + [ad])
    if rc != 0:
        return {"hata": "useradd başarısız: " + hata.strip()[-200:]}
    # Boş parola: giriş ekranında parolasız giriş (laboratuvar hesabı). sshd varsayılanı
    # PermitEmptyPasswords no olduğundan ağdan bu hesapla girilemez.
    rc, _, hata = calistir(["passwd", "-d", ad])
    if rc != 0:
        return {"hata": "hesap oluştu ama parola boşaltılamadı: " + hata.strip()[-200:]}
    return {"durum": "olusturuldu", "uid": pwd.getpwnam(ad).pw_uid, "gruplar": ek}


def sshd_etkin(hesap):
    rc, cikti, hata = calistir(["sshd", "-T", "-C", "user=%s,host=pardus-sinif,addr=127.0.0.1" % hesap])
    if rc != 0:
        rc, cikti, hata = calistir(["/usr/sbin/sshd", "-T", "-C",
                                    "user=%s,host=pardus-sinif,addr=127.0.0.1" % hesap])
    if rc != 0:
        return None, hata.strip()[-200:]
    ayar = {}
    for satir in cikti.splitlines():
        parca = satir.split()
        if len(parca) >= 2 and parca[0] in ("allowusers", "allowgroups", "denyusers", "denygroups"):
            ayar.setdefault(parca[0], []).extend(parca[1:])
    return ayar, None


def _eslesir(desenler, ad):
    return any(fnmatch.fnmatchcase(ad, d.split("@", 1)[0]) for d in desenler)


def sshd_izin(p):
    hesap = p.get("hesap", "")
    if hesap not in YONETIM:
        return {"hata": "yalnız yönetim hesapları için"}
    try:
        kayit = pwd.getpwnam(hesap)
    except KeyError:
        return {"hata": "'%s' hesabı yok" % hesap}
    gruplar = {g.gr_name for g in grp.getgrall() if hesap in g.gr_mem}
    try:
        gruplar.add(grp.getgrgid(kayit.pw_gid).gr_name)
    except KeyError:
        pass
    ayar, hata = sshd_etkin(hesap)
    if ayar is None:
        return {"hata": "sshd yapılandırması okunamadı: %s" % hata}
    if _eslesir(ayar.get("denyusers", []), hesap) or set(ayar.get("denygroups", [])) & gruplar:
        return {"hata": "sshd DenyUsers/DenyGroups '%s' hesabını engelliyor; elle düzeltilmeli" % hesap}
    eklenecek = []
    if ayar.get("allowusers") and not _eslesir(ayar["allowusers"], hesap):
        eklenecek.append("AllowUsers %s" % hesap)
    if ayar.get("allowgroups") and not (set(ayar["allowgroups"]) & gruplar):
        eklenecek.append("AllowGroups %s" % grp.getgrgid(kayit.pw_gid).gr_name)
    if not eklenecek:
        return {"durum": "izinli", "kisitlar": {k: v for k, v in ayar.items() if v}}
    if not os.path.isdir("/etc/ssh/sshd_config.d"):
        return {"hata": "sshd AllowUsers/AllowGroups kısıtı var ve ek yapılandırma dizini yok; elle düzeltilmeli"}
    mevcut = ""
    if os.path.isfile(SSHD_EK) and not os.path.islink(SSHD_EK):
        with open(SSHD_EK, encoding="utf-8") as f:
            mevcut = f.read()
    yeni = (mevcut or "# Pardus Sınıf Yönetimi — yönetim hesabının SSH izni\n")
    for satir in eklenecek:
        if satir not in yeni.splitlines():
            yeni += satir + "\n"
    with open(SSHD_EK + ".yeni", "w", encoding="utf-8") as f:
        f.write(yeni)
    os.replace(SSHD_EK + ".yeni", SSHD_EK)
    rc, _, hata = calistir(["sshd", "-t"])
    if rc != 0:
        if mevcut:
            with open(SSHD_EK, "w", encoding="utf-8") as f:
                f.write(mevcut)
        else:
            os.unlink(SSHD_EK)
        return {"hata": "sshd -t başarısız; değişiklik geri alındı: " + hata.strip()[-200:]}
    calistir(["systemctl", "reload", "ssh"])
    return {"durum": "eklendi", "satirlar": eklenecek}


def ana():
    try:
        p = json.loads(sys.argv[1])
        if os.geteuid() != 0:
            sonuc = {"hata": "root yetkisi gerekli"}
        else:
            sonuc = {"sudoers": sudoers, "ogrenci": ogrenci, "sshd_izin": sshd_izin}[p["kip"]](p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
