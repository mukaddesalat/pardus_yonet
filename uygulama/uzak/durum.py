"""Uzak betik — salt okunur durum toplama (öğrenci PC'de).

Parolasız sudo ile root olarak çalışır; sudo yoksa aynı betik bağlantı hesabının
yetkisiyle çalıştırılır ve root gerektiren alanlar `null` döner (ölçülemedi).
Hiçbir dosya veya ayar değiştirilmez.

Parametre (argv[1], JSON): {"profil": "ogrenci", "yonetim": ["pardus", "hp"]}
Çıktı: tek satır JSON.
"""

import base64
import grp
import hashlib
import json
import os
import pwd
import re
import subprocess
import sys

ORTAM = dict(os.environ, LC_ALL="C", LANG="C")
GORUNUM_DOSYASI = "/etc/dconf/db/local.d/92-pardus-sinif-gorunum"
DUVAR_DOSYASI = "/etc/dconf/db/local.d/91-pardus-sinif-duvar"


def calistir(argv, zaman=10):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ORTAM)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as hata:
        return 127, "", str(hata)


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


_ETAP_PAKET = re.compile(r"^Package: (etap[\w.+-]*|[\w.+-]*-etap(?:-[\w.+-]*)?)$")


def etap_izi(osr):
    """EBA/ETAP (etkileşimli tahta) imajı izi. Korunan cihaz önerisi içindir."""
    metin = " ".join(osr.get(k, "") for k in
                     ("NAME", "PRETTY_NAME", "VARIANT", "VARIANT_ID", "ID_LIKE")).lower()
    if "etap" in metin:
        return "os-release ETAP diyor"
    try:
        with open("/var/lib/dpkg/status", encoding="utf-8", errors="replace") as f:
            paket = None
            for satir in f:
                satir = satir.rstrip("\n")
                es = _ETAP_PAKET.match(satir)
                if es:
                    paket = es.group(1)
                elif satir.startswith("Package: "):
                    paket = None
                elif paket and satir.startswith("Status:") and "installed" in satir \
                        and "not-installed" not in satir:
                    return "ETAP paketi kurulu: " + paket
    except OSError:
        pass
    return None


def masaustu():
    if os.access("/usr/bin/gnome-shell", os.X_OK):
        rc, cikti, _ = calistir(["gnome-shell", "--version"])
        surum = cikti.strip().replace("GNOME Shell", "").strip() if rc == 0 else None
        return "GNOME", surum
    if os.access("/usr/bin/xfce4-session", os.X_OK):
        return "XFCE", None
    return None, None


def giris_yoneticisi():
    yol = "/etc/systemd/system/display-manager.service"
    if not os.path.exists(yol):
        return None
    ad = os.path.basename(os.path.realpath(yol))
    if ad.endswith(".service"):
        ad = ad[:-len(".service")]
    return "gdm3" if ad in ("gdm", "gdm3") else ad


def hesap_bilgisi(ad):
    try:
        p = pwd.getpwnam(ad)
    except KeyError:
        return None
    gruplar = {g.gr_name for g in grp.getgrall() if ad in g.gr_mem}
    try:
        gruplar.add(grp.getgrgid(p.pw_gid).gr_name)
    except KeyError:
        pass
    bilgi = {"uid": p.pw_uid, "ev": p.pw_dir, "kabuk": p.pw_shell, "gruplar": sorted(gruplar),
             "sudo": None, "parolasiz_sudo": None}
    if os.geteuid() == 0:
        rc, cikti, _ = calistir(["sudo", "-n", "-l", "-U", ad])
        bilgi["sudo"] = rc == 0 and "may run the following" in cikti
        bilgi["parolasiz_sudo"] = bool(re.search(r"NOPASSWD:\s*ALL", cikti))
    return bilgi


def oturumlar():
    rc, cikti, _ = calistir(["loginctl", "list-sessions", "--no-legend"])
    sonuc = []
    if rc != 0:
        return sonuc
    for satir in cikti.splitlines():
        parca = satir.split()
        if len(parca) < 3:
            continue
        rc2, ayrinti, _ = calistir(["loginctl", "show-session", parca[0], "-p", "Type",
                                    "-p", "Class", "-p", "State", "-p", "Remote"])
        ozellik = dict(s.split("=", 1) for s in ayrinti.splitlines() if "=" in s) if rc2 == 0 else {}
        sonuc.append({"kimlik": parca[0], "hesap": parca[2], "tur": ozellik.get("Type"),
                      "sinif": ozellik.get("Class"), "durum": ozellik.get("State"),
                      "uzak": ozellik.get("Remote") == "yes"})
    return sonuc


def surec_var_mi(ad):
    rc, _, _ = calistir(["pgrep", "-u", ad])
    return rc == 0


def ini_oku(yol):
    """Basit INI okuyucu: {bölüm: {anahtar: değer}}; yorumlar atlanır."""
    sonuc, bolum = {}, None
    try:
        with open(yol, encoding="utf-8", errors="replace") as f:
            for satir in f:
                satir = satir.strip()
                if not satir or satir[0] in "#;":
                    continue
                if satir.startswith("[") and satir.endswith("]"):
                    bolum = satir[1:-1].strip()
                    sonuc.setdefault(bolum, {})
                elif "=" in satir and bolum is not None:
                    ad, deger = satir.split("=", 1)
                    sonuc[bolum][ad.strip()] = deger.strip()
    except OSError:
        return None
    return sonuc


def otomatik_giris(dm):
    if dm != "gdm3":
        return {"destekli": False}
    ini = ini_oku("/etc/gdm3/daemon.conf") or {}
    daemon = ini.get("daemon", {})
    etkin = daemon.get("AutomaticLoginEnable", "").lower() == "true"
    return {"destekli": True, "etkin": etkin,
            "hesap": daemon.get("AutomaticLogin") if etkin else None}


def gizleme(hesaplar):
    """AccountsService: SystemAccount=true olan hesap GDM kullanıcı listesinde görünmez."""
    if os.geteuid() != 0:
        return None
    sonuc = {}
    liste = None
    rc, cikti, _ = calistir(["busctl", "--json=short", "call", "org.freedesktop.Accounts",
                             "/org/freedesktop/Accounts", "org.freedesktop.Accounts",
                             "ListCachedUsers"])
    if rc == 0:
        try:
            liste = set(json.loads(cikti)["data"][0])
        except (ValueError, KeyError, IndexError):
            liste = None
    for ad in hesaplar:
        ini = ini_oku("/var/lib/AccountsService/users/" + ad) or {}
        dosyada = ini.get("User", {}).get("SystemAccount", "").lower() == "true"
        listede = None
        if liste is not None:
            rc, cikti, _ = calistir(["busctl", "--json=short", "call", "org.freedesktop.Accounts",
                                     "/org/freedesktop/Accounts", "org.freedesktop.Accounts",
                                     "FindUserByName", "s", ad])
            if rc == 0:
                try:
                    listede = json.loads(cikti)["data"][0] in liste
                except (ValueError, KeyError, IndexError):
                    listede = None
        sonuc[ad] = {"sistem_hesabi": dosyada, "listede": listede}
    return sonuc


def bos_alan(yol):
    try:
        sv = os.statvfs(yol)
        return sv.f_bavail * sv.f_frsize
    except OSError:
        return None


# ---- Veyon (uzak/veyon.py'deki "durum" kipinin kısa eşdeğeri; alan adları aynı) ----

VEYON_PAKETLERI = ("veyon", "veyon-service", "veyon-master", "veyon-configurator", "veyon-plugins",
                   "libveyon-core")
VEYON_KONF = "/etc/xdg/Veyon Solutions/Veyon.conf"
VEYON_ACIK_KOK = "/etc/veyon/keys/public"


def _qt_ozet(veri):
    h = 0
    for b in veri:
        h = (31 * h + b) & 0xFFFFFFFF
    return "%08x" % h


def veyon_durumu():
    """Kurulu Veyon sürümü (dpkg'den, tam), servis, kimlik doğrulama yöntemi ve public anahtarlar."""
    rc, cikti, _ = calistir(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\t${Version}\n",
                             *VEYON_PAKETLERI])
    pk = {}
    for satir in cikti.splitlines():
        parca = satir.split("\t")
        if len(parca) >= 3:
            pk[parca[0].split(":")[0]] = {"durum": parca[1].strip(), "surum": parca[2].strip()}
    if not pk and rc not in (0, 1):
        sonuc = {"durum": "okunamadi", "surum": None, "paket": None}
    else:
        kurulu = {ad: b for ad, b in pk.items() if b["durum"].startswith("i")}
        yarim = sorted(ad for ad, b in kurulu.items() if b["durum"] != "ii")
        if yarim:
            sonuc = {"durum": "hatali", "surum": kurulu[yarim[0]]["surum"], "paket": yarim[0]}
        elif "veyon" in kurulu:
            sonuc = {"durum": "kurulu", "surum": kurulu["veyon"]["surum"], "paket": "veyon"}
        elif "veyon-service" in kurulu:
            sonuc = {"durum": "kurulu", "surum": kurulu["veyon-service"]["surum"],
                     "paket": "veyon-service", "parcali": True}
        elif kurulu:
            ad = sorted(kurulu)[0]
            sonuc = {"durum": "hatali", "surum": kurulu[ad]["surum"], "paket": ad}
        else:
            sonuc = {"durum": "kurulu_degil", "surum": None, "paket": None}
    _, etkin, _ = calistir(["systemctl", "is-enabled", "veyon"])
    _, aktif, _ = calistir(["systemctl", "is-active", "veyon"])
    sonuc["servis"] = {"etkin": etkin.strip() == "enabled" if etkin.strip() else None,
                       "calisiyor": aktif.strip() == "active"}
    ini = ini_oku(VEYON_KONF) or {}
    yontem = ini.get("Authentication", {}).get("Method")
    sonuc["yontem"] = int(yontem) if yontem and yontem.isdigit() else None
    anahtarlar = {}
    if os.path.isdir(VEYON_ACIK_KOK):
        for ad in sorted(os.listdir(VEYON_ACIK_KOK)):
            yol = os.path.join(VEYON_ACIK_KOK, ad, "key")
            try:
                with open(yol, encoding="utf-8", errors="replace") as f:
                    govde = "".join(s.strip() for s in f.read(65536).splitlines()
                                    if s.strip() and not s.startswith("-----"))
                der = base64.b64decode(govde, validate=True)
                anahtarlar[ad] = {"parmak_izi": hashlib.sha256(der).hexdigest(),
                                  "cift_kimligi": _qt_ozet(der)}
            except (OSError, ValueError):
                anahtarlar[ad] = {"hata": "okunamadı"}
    sonuc["anahtarlar"] = anahtarlar
    return sonuc


# ---- güç (uzak/guc_ayar.py "durum" kipinin kısa eşdeğeri; alan adları aynı) ----

UYKU_HEDEFLERI = ("sleep.target", "suspend.target", "hibernate.target", "hybrid-sleep.target",
                  "suspend-then-hibernate.target")


def guc_durumu():
    hedefler = {}
    for h in UYKU_HEDEFLERI:
        rc, cikti, _ = calistir(["systemctl", "is-enabled", h])
        hedefler[h] = cikti.strip() or ("yok" if rc else "?")
    ekran_dk = None
    try:
        with open("/etc/dconf/db/local.d/94-pardus-sinif-guc", encoding="utf-8") as f:
            es = re.search(r"^idle-delay=uint32 (\d+)", f.read(), re.M)
        ekran_dk = int(es.group(1)) // 60 if es else None
    except OSError:
        pass
    planlar = []
    kok = "/etc/systemd/system"
    for ad in sorted(os.listdir(kok)) if os.path.isdir(kok) else []:
        if not (ad.startswith("pardus-sinif-kapat-") and ad.endswith(".timer")):
            continue
        meta = {"id": ad[len("pardus-sinif-kapat-"):-len(".timer")]}
        try:
            with open(os.path.join(kok, ad), encoding="utf-8") as f:
                for satir in f:
                    if satir.startswith("# psy: "):
                        meta.update(json.loads(satir[7:]))
                    elif satir.startswith("OnCalendar="):
                        meta["takvim"] = satir.split("=", 1)[1].strip()
        except (OSError, ValueError):
            pass
        rc, cikti, _ = calistir(["systemctl", "show", ad, "-p", "NextElapseUSecRealtime", "-p", "ActiveState"])
        alan = dict(s.split("=", 1) for s in cikti.splitlines() if "=" in s)
        meta["sonraki"] = alan.get("NextElapseUSecRealtime") or None
        meta["etkin"] = alan.get("ActiveState") == "active"
        planlar.append(meta)
    # bekleyen: uygulamanın uyarı sayacı (geçici zamanlayıcı) ya da elle verilmiş "shutdown +N"
    _, cikti, _ = calistir(["systemctl", "is-active", "pardus-sinif-kapatma-bekliyor.timer"])
    sayac = cikti.strip() == "active"
    saat = None
    if sayac:
        try:
            with open("/run/pardus-sinif-kapatma", encoding="utf-8") as f:
                saat = f.read().strip()[:5] or None
        except OSError:
            pass
    return {"uyku": {"kapali": all(v == "masked" for v in hedefler.values()), "ekran_dk": ekran_dk},
            "planlar": planlar, "bekleyen": sayac or os.path.exists("/run/systemd/shutdown/scheduled"),
            "bekleyen_saat": saat}


def calistir_betik(p):
    profil_adi = p.get("profil", "ogrenci")
    yonetim = [h for h in p.get("yonetim", ["pardus", "hp"]) if re.match(r"^[a-z_][a-z0-9_-]{0,31}$", h)]
    osr = os_release()
    masa, gnome_surum = masaustu()
    dm = giris_yoneticisi()
    profil = hesap_bilgisi(profil_adi)
    tum_oturumlar = oturumlar()
    ogrenci_oturumu = any(o["hesap"] == profil_adi and o["sinif"] in (None, "user")
                          for o in tum_oturumlar)
    hesaplar = {ad: hesap_bilgisi(ad) for ad in yonetim}
    ev = profil["ev"] if profil else "/home"
    return {
        "root": os.geteuid() == 0,
        "hostname": os.uname().nodename,
        "os": {k: osr.get(k) for k in ("ID", "VERSION_ID", "PRETTY_NAME", "VARIANT")},
        "etap": etap_izi(osr),
        "masaustu": masa,
        "gnome_surum": gnome_surum,
        "giris_yoneticisi": dm,
        "yonetim_hesaplari": hesaplar,
        "profil": profil,
        "profil_sudo": bool(profil and set(profil["gruplar"]) & {"sudo", "admin", "wheel"}),
        "ogrenci_oturumu": ogrenci_oturumu,
        "ogrenci_sureci": surec_var_mi(profil_adi) if profil else False,
        "oturumlar": tum_oturumlar,
        "gizleme": gizleme([h for h in yonetim if hesaplar.get(h)]),
        "otomatik_giris": otomatik_giris(dm),
        "gorunum": {"duzen": os.path.exists(GORUNUM_DOSYASI),
                    "duvar": os.path.exists(DUVAR_DOSYASI)},
        "disk": {"ev_bos": bos_alan(ev if os.path.isdir(ev) else "/home"),
                 "kok_bos": bos_alan("/")},
        "veyon": veyon_durumu(),
        "guc": guc_durumu(),
    }


def ana():
    try:
        sonuc = calistir_betik(json.loads(sys.argv[1]) if len(sys.argv) > 1 else {})
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
