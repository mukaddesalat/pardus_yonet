"""Uzak betik — Veyon durumu, yapılandırması, doğrulaması ve geri alma (öğrenci PC'de).

Kipler (argv[1], JSON):
  {"kip": "durum", "anahtar_adi": "teacher", "parmak_izi": "<sha256 hex>"}
      Salt okunur: kurulu Veyon paketleri ve TAM sürüm (dpkg), servis durumu, kimlik
      doğrulama yöntemi, /etc/veyon/keys/public altındaki anahtarlar ve beklenen
      anahtarla eşleşme. Root gerekmez.
  {"kip": "yapilandir", "anahtar_adi": "teacher", "anahtar_pem": "-----BEGIN PUBLIC KEY-----…",
   "parmak_izi": "…", "uygula": false}
      uygula=false yalnız ne değişeceğini listeler. uygula=true: mevcut ayarları yedekler
      (/var/lib/pardus-sinif-yonetimi/veyon-yedek/<zaman>/), public key'i veyon-cli ile
      içe aktarır, Authentication/Method=1 (anahtar dosyası) yapar, servisi etkinleştirip
      yeniden başlatır; her adımı geri okuyarak doğrular.
  {"kip": "dogrula", ...durum ile aynı}   durum + denetim listesi.
  {"kip": "geri_al", "yedek": "<ad>"?}    En son (veya verilen) yedeği geri koyar.
  {"kip": "yedekler"}                     Yedek listesi.
Çıktı: tek satır JSON. Private key hiçbir kipte yer almaz; paket kurulumu ayrı betiktedir.
"""

import base64
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

KONF = "/etc/xdg/Veyon Solutions/Veyon.conf"
ANAHTAR_KOK = "/etc/veyon/keys"
ACIK_KOK = ANAHTAR_KOK + "/public"
VARSAYILAN_ACIK_DIZIN = ("%GLOBALAPPDATA%/keys/public", ACIK_KOK)
YEDEK_KOK = "/var/lib/pardus-sinif-yonetimi/veyon-yedek"
YEDEK_SAYISI = 5
PAKETLER = ("veyon", "veyon-service", "veyon-master", "veyon-configurator", "veyon-plugins",
            "libveyon-core")
SERVIS = "veyon"
PORT = 11100
AD_DESENI = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,31}$")
YEDEK_DESENI = re.compile(r"^\d{8}-\d{6}(-\d+)?$")
ORTAM = dict(os.environ, LC_ALL="C", LANG="C")


def calistir(argv, zaman=60, ortam=None):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=zaman, env=ortam or ORTAM)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "zaman aşımı"
    except OSError as hata:
        return 127, "", str(hata)


# ---------------------------------------------------------------- salt okunur durum

def paketler():
    """{ad: {"durum": dpkg kısaltması ('ii', 'rc', 'iU'…), "surum": tam sürüm}}; None: okunamadı."""
    rc, cikti, _ = calistir(["dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\t${Version}\n",
                             *PAKETLER])
    sonuc = {}
    for satir in cikti.splitlines():
        parca = satir.split("\t")
        if len(parca) < 3:
            continue
        sonuc[parca[0].split(":")[0]] = {"durum": parca[1].strip(), "surum": parca[2].strip()}
    if not sonuc and rc not in (0, 1):      # rc=1: bazı paketler yok, normal
        return None
    return sonuc


def surum_bilgisi(pk):
    """Envantere yazılacak özet: kurulu / kurulu_degil / hatali / okunamadi + TAM sürüm."""
    if pk is None:
        return {"durum": "okunamadi", "surum": None, "paket": None}
    kurulu = {ad: b for ad, b in pk.items() if b["durum"].startswith("i")}
    yarim = sorted(ad for ad, b in kurulu.items() if b["durum"] != "ii")
    if yarim:
        return {"durum": "hatali", "surum": kurulu[yarim[0]]["surum"], "paket": yarim[0],
                "yarim": yarim, "neden": "dpkg durumu: " + ", ".join(
                    "%s=%s" % (ad, kurulu[ad]["durum"]) for ad in yarim)}
    for ad in ("veyon", "veyon-service"):
        if ad in kurulu:
            return {"durum": "kurulu", "surum": kurulu[ad]["surum"], "paket": ad,
                    "parcali": ad != "veyon"}
    if kurulu:  # yalnız libveyon-core / veyon-master gibi parçalar kalmış
        ad = sorted(kurulu)[0]
        return {"durum": "hatali", "surum": kurulu[ad]["surum"], "paket": ad, "yarim": sorted(kurulu),
                "neden": "veyon-service kurulu değil; kalan parçalar: " + ", ".join(sorted(kurulu))}
    return {"durum": "kurulu_degil", "surum": None, "paket": None}


def port_dinliyor(port):
    hex_port = "%04X" % port
    for yol in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(yol, encoding="ascii", errors="replace") as f:
                next(f, None)
                for satir in f:
                    parca = satir.split()
                    if len(parca) > 3 and parca[3] == "0A" and parca[1].rsplit(":", 1)[-1] == hex_port:
                        return True
        except OSError:
            continue
    return False


def servis():
    rc, yuk, _ = calistir(["systemctl", "show", "-p", "LoadState", "--value", SERVIS + ".service"])
    var = rc == 0 and yuk.strip() == "loaded"
    _, etkin, _ = calistir(["systemctl", "is-enabled", SERVIS])
    _, aktif, _ = calistir(["systemctl", "is-active", SERVIS])
    etkin, aktif = etkin.strip(), aktif.strip()
    return {"var": var,
            "etkin": (etkin == "enabled") if var and etkin else None,
            "etkin_metin": etkin or None,
            "calisiyor": aktif == "active",
            "durum_metin": aktif or None,
            "sunucu_sureci": calistir(["pgrep", "-x", "veyon-server"])[0] == 0,
            "port_dinliyor": port_dinliyor(PORT)}


def ini_oku(yol):
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


def konf_oku():
    ini = ini_oku(KONF)
    if ini is None:
        return {"var": False, "yontem": None, "anahtar_dizini": None}
    kimlik = ini.get("Authentication", {})
    yontem = kimlik.get("Method")
    return {"var": True, "yontem": int(yontem) if yontem and yontem.isdigit() else None,
            "anahtar_dizini": kimlik.get("PublicKeyBaseDir")}


def qt_ozet(veri):
    """Veyon'un PAIR ID'si: Qt5 qHash(QByteArray(DER)) → 8 onaltılık hane (lab'da doğrulandı)."""
    h = 0
    for b in veri:
        h = (31 * h + b) & 0xFFFFFFFF
    return "%08x" % h


def pem_ozet(metin):
    govde = "".join(s.strip() for s in metin.splitlines() if s.strip() and not s.startswith("-----"))
    der = base64.b64decode(govde, validate=True)
    return {"parmak_izi": hashlib.sha256(der).hexdigest(), "cift_kimligi": qt_ozet(der), "bayt": len(der)}


def anahtarlar_oku():
    sonuc = {}
    for yol in sorted(glob.glob(ACIK_KOK + "/*/key")):
        ad = os.path.basename(os.path.dirname(yol))
        try:
            with open(yol, encoding="utf-8", errors="replace") as f:
                bilgi = pem_ozet(f.read(65536))
            bilgi["izin"] = "%04o" % (os.stat(yol).st_mode & 0o7777)
            sonuc[ad] = bilgi
        except (OSError, ValueError) as hata:
            sonuc[ad] = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    return sonuc


def grafik_oturum_var():
    rc, cikti, _ = calistir(["loginctl", "list-sessions", "--no-legend"])
    if rc != 0:
        return None
    for satir in cikti.splitlines():
        parca = satir.split()
        if not parca:
            continue
        rc2, ayrinti, _ = calistir(["loginctl", "show-session", parca[0], "-p", "Type", "-p", "State"])
        if rc2 == 0 and ("Type=x11" in ayrinti or "Type=wayland" in ayrinti) and "State=closing" not in ayrinti:
            return True
    return False


def durum(p):
    pk = paketler()
    s = surum_bilgisi(pk)
    ad, beklenen = p.get("anahtar_adi"), p.get("parmak_izi")
    anahtarlar = anahtarlar_oku()
    eslesme = None
    if ad and beklenen:
        mevcut = anahtarlar.get(ad)
        eslesme = ("yok" if not mevcut else "eslesiyor" if mevcut.get("parmak_izi") == beklenen
                   else "farkli")
    konf = konf_oku()
    return {"durum": s["durum"], "surum": s["surum"], "paket": s.get("paket"),
            "parcali": s.get("parcali", False), "yarim": s.get("yarim"), "neden": s.get("neden"),
            "paketler": pk, "veyon_cli": os.access("/usr/bin/veyon-cli", os.X_OK),
            "servis": servis(), "konf": konf, "yontem": konf["yontem"],
            "anahtarlar": anahtarlar, "anahtar_adi": ad, "eslesme": eslesme,
            "root": os.geteuid() == 0, "zaman": time.strftime("%Y-%m-%dT%H:%M:%S")}


# ---------------------------------------------------------------- yedek

def yedek_listesi():
    sonuc = []
    if not os.path.isdir(YEDEK_KOK):
        return sonuc
    for ad in sorted(os.listdir(YEDEK_KOK), reverse=True):
        if not YEDEK_DESENI.match(ad):
            continue
        try:
            with open(os.path.join(YEDEK_KOK, ad, "bilgi.json"), encoding="utf-8") as f:
                bilgi = json.load(f)
        except (OSError, ValueError):
            bilgi = {}
        sonuc.append({"ad": ad, **bilgi})
    return sonuc


def yedek_al(mevcut):
    zaman = time.strftime("%Y%m%d-%H%M%S")
    dizin = os.path.join(YEDEK_KOK, zaman)
    sayac = 1
    while os.path.exists(dizin):
        sayac += 1
        dizin = os.path.join(YEDEK_KOK, "%s-%d" % (zaman, sayac))
    os.makedirs(dizin, mode=0o700)
    sv = mevcut["servis"]
    bilgi = {"zaman": zaman, "konf_vardi": os.path.exists(KONF),
             "acik_dizin_vardi": os.path.isdir(ACIK_KOK),
             "servis": {"etkin": sv.get("etkin"), "calisiyor": sv.get("calisiyor")},
             "anahtarlar": sorted(mevcut["anahtarlar"]), "yontem": mevcut["yontem"]}
    if bilgi["konf_vardi"]:
        shutil.copy2(KONF, os.path.join(dizin, "Veyon.conf"))
    if bilgi["acik_dizin_vardi"]:
        shutil.copytree(ACIK_KOK, os.path.join(dizin, "public"), symlinks=True)
    with open(os.path.join(dizin, "bilgi.json"), "w", encoding="utf-8") as f:
        json.dump(bilgi, f, ensure_ascii=False)
    eskiler = [y["ad"] for y in yedek_listesi()][YEDEK_SAYISI:]
    for ad in eskiler:
        shutil.rmtree(os.path.join(YEDEK_KOK, ad), ignore_errors=True)
    return {"ad": os.path.basename(dizin), "dizin": dizin, "budanan": len(eskiler), **bilgi}


# ---------------------------------------------------------------- yapılandırma

def yapilandir(p):
    ad, pem = p.get("anahtar_adi", ""), p.get("anahtar_pem", "")
    beklenen, uygula = p.get("parmak_izi", ""), bool(p.get("uygula"))
    if not AD_DESENI.match(ad):
        return {"hata": "geçersiz anahtar adı"}
    if not pem.startswith("-----BEGIN PUBLIC KEY-----"):
        return {"hata": "public key PEM bekleniyor"}
    try:
        hedef = pem_ozet(pem)
    except ValueError:
        return {"hata": "public key PEM okunamadı"}
    if hedef["parmak_izi"] != beklenen:
        return {"hata": "anahtar özeti tutmuyor"}
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}

    mevcut = durum(p)
    a = mevcut["anahtarlar"].get(ad)
    ogeler = {
        "anahtar": {"ad": ad, "hedef_kimlik": hedef["cift_kimligi"],
                    "mevcut_kimlik": a.get("cift_kimligi") if a else None,
                    "durum": ("zaten" if a and a.get("parmak_izi") == beklenen
                              else "degistirilecek" if a else "eklenecek")},
        "yontem": {"mevcut": mevcut["yontem"], "durum": "zaten" if mevcut["yontem"] == 1 else "ayarlanacak"},
        "servis": {"mevcut": mevcut["servis"],
                   "durum": ("zaten" if mevcut["servis"].get("etkin") and mevcut["servis"].get("calisiyor")
                             else "etkinlestirilecek")},
    }
    uyarilar = []
    kd = mevcut["konf"].get("anahtar_dizini")
    if kd and kd not in VARSAYILAN_ACIK_DIZIN:
        uyarilar.append("Veyon.conf özel bir anahtar dizini kullanıyor (%s); bu uygulama %s dizinine yazar"
                        % (kd, ACIK_KOK))
    if not mevcut["veyon_cli"]:
        if uygula:
            return {"hata": "veyon_yok"}
        return {"onizleme": True, "veyon_yok": True, "ogeler": ogeler, "uyarilar": uyarilar,
                "durum": mevcut}
    if not uygula:
        return {"onizleme": True, "ogeler": ogeler, "uyarilar": uyarilar, "durum": mevcut}

    yedek = yedek_al(mevcut)
    gecici = tempfile.mkdtemp(prefix="psy-veyon-")
    ortam = dict(ORTAM, TMPDIR=gecici)     # veyon-cli günlüğü /tmp yerine özel dizine
    try:
        og = ogeler["anahtar"]
        if og["durum"] != "zaten":
            yol = os.path.join(gecici, "acik.pem")
            fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(pem if pem.endswith("\n") else pem + "\n")
            hata = None
            if og["durum"] == "degistirilecek":
                rc, c, h = calistir(["veyon-cli", "authkeys", "delete", ad + "/public"], ortam=ortam)
                if rc != 0:
                    hata = "eski anahtar silinemedi: " + (h or c).strip()[-300:]
            if hata is None:
                rc, c, h = calistir(["veyon-cli", "authkeys", "import", ad + "/public", yol], ortam=ortam)
                if rc != 0:
                    hata = "içe aktarılamadı: " + (h or c).strip()[-300:]
            if hata is None:
                yeni = anahtarlar_oku().get(ad)
                if not yeni or yeni.get("parmak_izi") != beklenen:
                    hata = "geri okunan anahtar beklenenle aynı değil"
            if hata:
                og["durum"], og["neden"] = "hata", hata
            else:
                og["durum"] = "uygulandi"
        oy = ogeler["yontem"]
        if oy["durum"] != "zaten":
            rc, c, h = calistir(["veyon-cli", "config", "set", "Authentication/Method", "1"], ortam=ortam)
            sonra = konf_oku()["yontem"]
            oy["sonra"] = sonra
            if rc != 0 or sonra != 1:
                oy["durum"], oy["neden"] = "hata", (h or c).strip()[-300:] or "geri okunan değer 1 değil"
            else:
                oy["durum"] = "uygulandi"
        os_ = ogeler["servis"]
        degisti = og["durum"] == "uygulandi" or oy["durum"] == "uygulandi"
        if os_["durum"] != "zaten" or degisti:
            calistir(["systemctl", "enable", SERVIS])
            calistir(["systemctl", "restart", SERVIS], zaman=90)
            for _ in range(20):
                time.sleep(0.5)
                if servis()["calisiyor"]:
                    break
            sv2 = servis()
            os_["sonra"] = sv2
            os_["durum"] = "uygulandi" if sv2["calisiyor"] and sv2["etkin"] else "hata"
            if os_["durum"] == "hata":
                os_["neden"] = "servis %s / %s" % (sv2.get("etkin_metin"), sv2.get("durum_metin"))
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    son = durum(p)
    return {"uygulandi": True, "ogeler": ogeler, "uyarilar": uyarilar, "yedek": yedek, "durum": son,
            "hata_var": any(o["durum"] == "hata" for o in ogeler.values())}


def dogrula(p):
    d = durum(p)
    sv = d["servis"]
    denetimler = []
    if d["durum"] == "kurulu":
        denetimler.append(["kurulum", True, "Veyon %s kurulu (%s)" % (d["surum"], d["paket"])])
    else:
        denetimler.append(["kurulum", False, {"kurulu_degil": "Veyon kurulu değil",
                                              "hatali": "kurulum hatalı veya yarım: %s" % d.get("neden"),
                                              "okunamadi": "paket durumu okunamadı"}[d["durum"]]])
    denetimler.append(["servis", bool(sv.get("etkin") and sv.get("calisiyor")),
                       "servis %s, %s" % ({True: "etkin", False: "etkin değil", None: "tanımsız"}[sv.get("etkin")],
                                          "çalışıyor" if sv.get("calisiyor") else "çalışmıyor")])
    denetimler.append(["yontem", d["yontem"] == 1,
                       {1: "kimlik doğrulama: anahtar dosyası", 0: "kimlik doğrulama: oturum parolası (anahtar kullanılmıyor)",
                        None: "kimlik doğrulama yöntemi ayarlanmamış"}.get(d["yontem"], "yöntem: %s" % d["yontem"])])
    a = d["anahtarlar"].get(d.get("anahtar_adi") or "")
    denetimler.append(["anahtar", d["eslesme"] == "eslesiyor",
                       {"eslesiyor": "public key '%s' eşleşiyor (%s)" % (d.get("anahtar_adi"), a and a.get("cift_kimligi")),
                        "farkli": "public key '%s' FARKLI (%s)" % (d.get("anahtar_adi"), a and a.get("cift_kimligi")),
                        "yok": "public key '%s' yok" % d.get("anahtar_adi"),
                        None: "beklenen anahtar verilmedi"}[d["eslesme"]]])
    if sv.get("port_dinliyor"):
        denetimler.append(["sunucu", True, "Veyon sunucusu %d portunu dinliyor" % PORT])
    else:
        grafik = grafik_oturum_var()
        denetimler.append(["sunucu", False, "Veyon sunucusu %d portunu dinlemiyor%s" % (
            PORT, " (açık masaüstü oturumu yok; sunucu oturum açılınca başlar)" if grafik is False else "")])
    return {"durum": d, "denetimler": denetimler, "tamam": all(ok for _, ok, _ in denetimler)}


def geri_al(p):
    if os.geteuid() != 0:
        return {"hata": "root yetkisi gerekli"}
    yedekler = yedek_listesi()
    if not yedekler:
        return {"hata": "Bu bilgisayarda geri alınacak Veyon yedeği yok (bu uygulama burada henüz "
                        "yapılandırma yapmamış)"}
    ad = p.get("yedek") or yedekler[0]["ad"]
    if not YEDEK_DESENI.match(ad) or not os.path.isdir(os.path.join(YEDEK_KOK, ad)):
        return {"hata": "yedek bulunamadı: %s" % ad}
    dizin = os.path.join(YEDEK_KOK, ad)
    try:
        with open(os.path.join(dizin, "bilgi.json"), encoding="utf-8") as f:
            bilgi = json.load(f)
    except (OSError, ValueError):
        return {"hata": "yedek bilgisi okunamadı: %s" % ad}
    adimlar = []
    if bilgi.get("konf_vardi") and os.path.isfile(os.path.join(dizin, "Veyon.conf")):
        os.makedirs(os.path.dirname(KONF), exist_ok=True)
        shutil.copy2(os.path.join(dizin, "Veyon.conf"), KONF)
        adimlar.append("Veyon.conf yedekten geri kondu")
    elif os.path.exists(KONF):
        os.unlink(KONF)
        adimlar.append("Veyon.conf kaldırıldı (yedek anında yoktu)")
    if os.path.isdir(ACIK_KOK):
        shutil.rmtree(ACIK_KOK)
    if os.path.isdir(os.path.join(dizin, "public")):
        shutil.copytree(os.path.join(dizin, "public"), ACIK_KOK, symlinks=True)
        adimlar.append("public anahtarlar geri kondu: " + (", ".join(bilgi.get("anahtarlar") or []) or "(boş)"))
    else:
        adimlar.append("public anahtar dizini kaldırıldı (yedek anında yoktu)")
    sv = servis()
    if sv["var"]:
        onceki = bilgi.get("servis") or {}
        calistir(["systemctl", "enable" if onceki.get("etkin") else "disable", SERVIS])
        calistir(["systemctl", "restart" if onceki.get("calisiyor") else "stop", SERVIS], zaman=90)
        adimlar.append("servis %s / %s" % ("etkin" if onceki.get("etkin") else "etkin değil",
                                            "yeniden başlatıldı" if onceki.get("calisiyor") else "durduruldu"))
    adimlar.append("Veyon paketi kaldırılmadı (yalnız ayarlar geri alındı)")
    return {"geri_alindi": True, "yedek": ad, "adimlar": adimlar, "durum": durum(p)}


def ana():
    try:
        p = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
        kip = p.get("kip", "durum")
        islev = {"durum": durum, "yapilandir": yapilandir, "dogrula": dogrula, "geri_al": geri_al,
                 "yedekler": lambda _p: {"yedekler": yedek_listesi()}}[kip]
        sonuc = islev(p)
    except Exception as hata:  # tek satır JSON sözleşmesi korunur
        sonuc = {"hata": "%s: %s" % (type(hata).__name__, hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
