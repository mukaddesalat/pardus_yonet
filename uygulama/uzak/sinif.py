"""Uzak betik — Hızlı Sınıf Masası araçları (öğrenci PC'de, root).

Kipler (argv[1], JSON):
  {"kip": "ekran_kilit", "eylem": "kilitle"|"ac", "mesaj": "..."}
  {"kip": "duyuru", "baslik": "...", "mesaj": "..."}
  {"kip": "internet", "eylem": "kisitla"|"ac"}
  {"kip": "masaustu_url", "baslik": "...", "url": "...", "otomatik_ac": true|false}
  {"kip": "masaustu_dosya", "dosya_adi": "...", "icerik_b64": "..."}
  {"kip": "hosts_ekle", "ip": "192.168.23.142", "ad": "abc.local"}
Çıktı: tek satır JSON.
"""

import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import pwd
except ImportError:  # Windows test ortamı
    pwd = None

PROFIL = "ogrenci"
ZINCIR = "PSY_SINIF_NET"
HOSTS_YOLU = Path("/etc/hosts")
# runuser /usr/sbin altındadır; dar PATH ile "No such file or directory: 'runuser'" hatası alınıyordu.
YOL = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
KILIT_BETIGI = Path("/run/psy-bana-bakin.py")
KILIT_GUNLUGU = Path("/run/psy-bana-bakin.log")

# Öğrenci masaüstünde öğrenci hesabıyla çalışan tam ekran "Bana Bakın" katmanı.
# GTK3 (Pardus GNOME'da hazır) ile; olmazsa Tk ile. Klavye ve fare yakalanır,
# pencere kapatılamaz; öğretmen "Ekran Kilitlerini Aç" deyince SIGTERM ile kapanır.
# Güvenlik ağı: öğretmen PC'ye ulaşılamazsa bile `sure_dk` dakika sonra kendiliğinden açılır.
KATMAN_KODU = r'''
import json, os, signal, sys
p = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
BASLIK = p.get("baslik") or "Bana Bakın"
MESAJ = p.get("mesaj") or "Lütfen öğretmeninizi dinleyin."
OKUL = p.get("okul") or ""
SURE_SN = max(1, int(p.get("sure_dk") or 60)) * 60


def gtk_katman():
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    css = Gtk.CssProvider()
    css.load_from_data(b"""
      window.psy-katman { background-color: #0F172A; }
      .psy-ikon { font-size: 96px; }
      .psy-baslik { color: #FFFFFF; font-size: 60px; font-weight: 800; }
      .psy-mesaj { color: #E2E8F0; font-size: 28px; }
      .psy-okul { color: #93C5FD; font-size: 20px; font-weight: 700; }
      .psy-alt { color: #64748B; font-size: 14px; }
    """)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    ekran = Gdk.Display.get_default()
    pencereler = []
    for i in range(max(1, ekran.get_n_monitors())):
        geo = ekran.get_monitor(i).get_geometry()
        w = Gtk.Window(type=Gtk.WindowType.POPUP)   # pencere yöneticisi dışı: küçültülemez, Alt+Tab ile geçilemez
        w.get_style_context().add_class("psy-katman")
        w.move(geo.x, geo.y)
        w.set_default_size(geo.width, geo.height)
        w.set_size_request(geo.width, geo.height)
        w.connect("delete-event", lambda *a: True)
        kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        kutu.set_valign(Gtk.Align.CENTER)
        kutu.set_halign(Gtk.Align.CENTER)
        for metin, sinif in (("\U0001F512", "psy-ikon"), (BASLIK, "psy-baslik"), (MESAJ, "psy-mesaj"),
                             (OKUL, "psy-okul"), ("Ekran öğretmen tarafından kilitlendi · Lab Kaptanı", "psy-alt")):
            if not metin:
                continue
            e = Gtk.Label(label=metin)
            e.set_line_wrap(True)
            e.set_justify(Gtk.Justification.CENTER)
            e.set_max_width_chars(48)
            e.get_style_context().add_class(sinif)
            kutu.pack_start(e, False, False, 0)
        w.add(kutu)
        w.show_all()
        pencereler.append(w)
    koltuk = ekran.get_default_seat()

    def tut():
        for w in pencereler:
            gw = w.get_window()
            if gw is not None:
                gw.raise_()
        gw = pencereler[0].get_window()
        if gw is not None:
            koltuk.grab(gw, Gdk.SeatCapabilities.ALL, False, None, None, None, None)
        return True

    GLib.timeout_add(700, tut)
    GLib.timeout_add_seconds(SURE_SN, lambda: Gtk.main_quit() or False)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda *a: Gtk.main_quit() or False)
    tut()
    Gtk.main()


def tk_katman():
    import tkinter as tk
    kok = tk.Tk()
    kok.configure(bg="#0F172A")
    gen, yuk = kok.winfo_screenwidth(), kok.winfo_screenheight()
    kok.geometry(f"{gen}x{yuk}+0+0")
    kok.overrideredirect(True)
    kok.attributes("-topmost", True)
    kok.protocol("WM_DELETE_WINDOW", lambda: None)
    cerceve = tk.Frame(kok, bg="#0F172A")
    cerceve.place(relx=0.5, rely=0.5, anchor="center")
    for metin, renk, boy in (("\U0001F512", "#FFFFFF", 72), (BASLIK, "#FFFFFF", 48), (MESAJ, "#E2E8F0", 24),
                             (OKUL, "#93C5FD", 16)):
        if metin:
            tk.Label(cerceve, text=metin, fg=renk, bg="#0F172A", font=("Sans", boy, "bold"),
                     wraplength=int(gen * 0.7), justify="center").pack(pady=8)
    durum = {"kapat": False}
    signal.signal(signal.SIGTERM, lambda *a: durum.update(kapat=True))

    def tut():
        if durum["kapat"]:
            kok.destroy()
            return
        try:
            kok.lift()
            kok.focus_force()
            kok.grab_set_global()
        except Exception:
            pass
        kok.after(700, tut)

    kok.after(SURE_SN * 1000, kok.destroy)
    tut()
    kok.mainloop()


try:
    gtk_katman()
except Exception as hata:
    print("GTK kullanılamadı:", hata, file=sys.stderr)
    tk_katman()
'''


def _calistir(argv: list[str], **ek) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, capture_output=True, timeout=15, **ek)


def _arac(ad: str) -> str | None:
    return shutil.which(ad, path=YOL)


def _ogrenci_bilgi():
    if pwd is None or not hasattr(pwd, "getpwnam"):
        return None
    try:
        return pwd.getpwnam(PROFIL)
    except KeyError:
        return None


def _x_ekrani(uid: int) -> str | None:
    """Öğrencinin X ekranı (GDM oturumu çoğu zaman :0 değildir); soket sahibine bakılır."""
    dizin = Path("/tmp/.X11-unix")
    adaylar = []
    try:
        for soket in dizin.iterdir():
            if soket.name.startswith("X") and soket.name[1:].isdigit():
                try:
                    if soket.stat().st_uid == uid:
                        adaylar.append(int(soket.name[1:]))
                except OSError:
                    pass
    except OSError:
        return None
    return f":{min(adaylar)}" if adaylar else None


def _oturum_ortami():
    """(bilgi, ortam): ortam None ise öğrencinin açık grafik oturumu yoktur."""
    bilgi = _ogrenci_bilgi()
    if not bilgi:
        return None, None
    calisma = f"/run/user/{bilgi.pw_uid}"
    if not os.path.exists(f"{calisma}/bus"):
        return bilgi, None
    ortam = {
        "PATH": YOL,
        "HOME": bilgi.pw_dir,
        "USER": bilgi.pw_name,
        "LOGNAME": bilgi.pw_name,
        "LANG": os.environ.get("LANG") or "tr_TR.UTF-8",
        "XDG_RUNTIME_DIR": calisma,
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={calisma}/bus",
    }
    ekran = _x_ekrani(bilgi.pw_uid)
    if ekran:
        ortam["DISPLAY"] = ekran
    for xauth in (f"{calisma}/gdm/Xauthority", f"{bilgi.pw_dir}/.Xauthority"):
        if os.path.exists(xauth):
            ortam["XAUTHORITY"] = xauth
            break
    try:
        wayland = sorted(a for a in os.listdir(calisma) if a.startswith("wayland-") and not a.endswith(".lock"))
    except OSError:
        wayland = []
    if wayland:
        ortam["WAYLAND_DISPLAY"] = wayland[0]
    if "DISPLAY" not in ortam and "WAYLAND_DISPLAY" not in ortam:
        return bilgi, None
    return bilgi, ortam


def _ogrenci_komutu(argv: list[str], ortam: dict) -> list[str]:
    runuser = _arac("runuser")
    if not runuser:
        raise RuntimeError("runuser bulunamadı (util-linux)")
    return [runuser, "-u", PROFIL, "--", "env", *[f"{k}={v}" for k, v in ortam.items()], *argv]


def _gvariant_metin(metin: str) -> str:
    return "'" + metin.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _kullanici_bildir(baslik: str, mesaj: str, acil: bool = True) -> bool:
    """Masaüstü bildirimi; asla istisna fırlatmaz (bildirim, asıl işin önüne geçmemeli)."""
    try:
        _, ortam = _oturum_ortami()
        if not ortam:
            return False
        gdbus = _arac("gdbus")
        if gdbus:
            r = _calistir(_ogrenci_komutu([
                gdbus, "call", "--session", "--dest", "org.freedesktop.Notifications",
                "--object-path", "/org/freedesktop/Notifications",
                "--method", "org.freedesktop.Notifications.Notify",
                _gvariant_metin("Lab Kaptanı"), "0", _gvariant_metin("dialog-information"),
                _gvariant_metin(baslik), _gvariant_metin(mesaj), "[]",
                "{'urgency': <byte %d>}" % (2 if acil else 1), "15000"], ortam))
            if r.returncode == 0:
                return True
        notify = _arac("notify-send")
        if notify:
            r = _calistir(_ogrenci_komutu(
                [notify, "-u", "critical" if acil else "normal", "-a", "Lab Kaptanı", baslik, mesaj], ortam))
            return r.returncode == 0
    except Exception:
        return False
    return False


def _arka_planda(argv: list[str], gunluk: Path | None = None) -> subprocess.Popen:
    """SSH oturumu kapanınca ölmesin diye yeni oturumda, çıktısı boru tutmadan başlatır."""
    cikti = open(gunluk, "w") if gunluk else subprocess.DEVNULL
    return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=cikti, stderr=cikti,
                            start_new_session=True, close_fds=True)


def _katmani_kapat() -> int:
    """Çalışan "Bana Bakın" katmanlarını kapatır; kapatılan süreç sayısını döndürür."""
    systemctl = _arac("systemctl")
    if systemctl:
        _calistir([systemctl, "stop", "psy-bana-bakin"])
    pkill = _arac("pkill")
    if pkill:
        r = _calistir([pkill, "-TERM", "-f", str(KILIT_BETIGI)])
        return 1 if r.returncode == 0 else 0
    return 1


def ekran_kilit(p: dict) -> dict:
    eylem = p.get("eylem", "kilitle")
    mesaj = (p.get("mesaj") or "Lütfen öğretmeninizi dinleyin.").strip()[:300]
    if eylem != "kilitle":
        kapatilan = _katmani_kapat()
        _kullanici_bildir("Ekran Kilidi Açıldı", "Çalışmanıza devam edebilirsiniz.", acil=False)
        return {"tamam": True, "eylem": "ac", "kapatilan": kapatilan,
                "mesaj": "Ekran kilidi açıldı" if kapatilan else "Ekran zaten serbestti"}
    _, ortam = _oturum_ortami()
    if not ortam:
        return {"hata": "Öğrenci masaüstü oturumu açık değil; kilitlenecek ekran yok"}
    python = _arac("python3") or sys.executable
    _katmani_kapat()  # yeniden kilitlemede mesaj güncellensin
    KILIT_BETIGI.write_text(KATMAN_KODU, encoding="utf-8")
    os.chmod(KILIT_BETIGI, 0o644)
    parametre = json.dumps({"baslik": "Bana Bakın", "mesaj": mesaj, "okul": p.get("okul") or "",
                            "sure_dk": p.get("sure_dk") or 60}, ensure_ascii=False)
    systemd_run = _arac("systemd-run")
    if systemd_run:
        cmd = [
            systemd_run,
            "--unit=psy-bana-bakin",
            f"--uid={PROFIL}",
            *[f"--setenv={k}={v}" for k, v in ortam.items()],
            python, str(KILIT_BETIGI), parametre
        ]
        r = _calistir(cmd)
        if r.returncode == 0:
            return {"tamam": True, "eylem": "kilitle", "mesaj": "Ekran kilitlendi (Bana Bakın)"}

    # Yedek yöntem: runuser ile arka planda
    _arka_planda(_ogrenci_komutu([python, str(KILIT_BETIGI), parametre], ortam), KILIT_GUNLUGU)
    return {"tamam": True, "eylem": "kilitle", "mesaj": "Ekran kilitlendi (Bana Bakın)"}


def duyuru(p: dict) -> dict:
    baslik = (p.get("baslik") or "Öğretmen Duyurusu").strip()[:100]
    mesaj = (p.get("mesaj") or "").strip()[:1000]
    if not mesaj:
        return {"hata": "Duyuru metni boş"}
    _, ortam = _oturum_ortami()
    if not ortam:
        return {"hata": "Öğrenci masaüstü oturumu açık değil; duyuru gösterilemedi"}
    bildirim = _kullanici_bildir(baslik, mesaj, acil=True)
    pencere = False
    zenity = _arac("zenity")
    if zenity:
        try:
            _arka_planda(_ogrenci_komutu(
                [zenity, "--info", "--title", baslik, "--text", html.escape(mesaj, quote=False),
                 "--width=460", "--ok-label=Tamam"], ortam))
            pencere = True
        except Exception:
            pencere = False
    if not (bildirim or pencere):
        return {"hata": "Duyuru gösterilemedi (bildirim servisi ve zenity kullanılamadı)"}
    return {"tamam": True, "oturum_acik": True, "pencere": pencere, "bildirim": bildirim,
            "mesaj": "Duyuru öğrenci ekranında gösterildi"}


def internet(p: dict | str = "kisitla") -> dict:
    if isinstance(p, str):
        eylem = p
    else:
        eylem = p.get("eylem") or ("kisitla" if p.get("kisitla") else "ac")

    iptables = _arac("iptables")
    if not iptables:
        return {"tamam": False, "hata": "iptables bulunamadı", "mesaj": "Güvenlik duvarı aracı bulunamadı"}

    zincir = "PARDUS_LAB_KISIT"

    # Önce mevcut özel zinciri kaldır
    _calistir([iptables, "-D", "OUTPUT", "-j", zincir])
    _calistir([iptables, "-F", zincir])
    _calistir([iptables, "-X", zincir])

    if eylem == "kisitla":
        _calistir([iptables, "-N", zincir])
        _calistir([iptables, "-A", zincir, "-o", "lo", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-d", "10.0.0.0/8", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-d", "172.16.0.0/12", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-d", "192.168.0.0/16", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-d", "224.0.0.0/4", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-d", "255.255.255.255/32", "-j", "ACCEPT"])
        _calistir([iptables, "-A", zincir, "-j", "REJECT"])
        _calistir([iptables, "-I", "OUTPUT", "1", "-j", zincir])
        _kullanici_bildir("İnternet Erişimi", "Dış internet erişimi kısıtlandı. Yerel laboratuvar ağı açıktır.", acil=False)
        return {"tamam": True, "durum": "kisitli", "mesaj": "Dış internet kısıtlandı (yerel ağ açık)"}
    else:
        _kullanici_bildir("İnternet Erişimi", "İnternet erişimi kısıtlaması kaldırıldı.", acil=False)
        return {"tamam": True, "durum": "acik", "mesaj": "İnternet erişimi serbest bırakıldı"}


def _masaustu_dizini(ev: str | Path) -> Path:
    ev_yolu = Path(ev)
    for ad in ("Masaüstü", "Desktop"):
        d = ev_yolu / ad
        if d.is_dir():
            return d
    d = ev_yolu / "Masaüstü"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ogrenci_sahip_yap(hedef: Path, bilgi, izin: int = 0o644) -> None:
    try:
        os.chmod(hedef, izin)
    except OSError:
        pass
    if bilgi is not None and hasattr(os, "chown"):
        try:
            os.chown(hedef, bilgi.pw_uid, bilgi.pw_gid)
            os.chown(hedef.parent, bilgi.pw_uid, bilgi.pw_gid)
        except OSError:
            pass




def masaustu_url(p: dict | str, url_arg: str | None = None) -> dict:
    if isinstance(p, str):
        p = {"baslik": p, "url": url_arg or ""}
    bilgi = _ogrenci_bilgi()
    if not bilgi and hasattr(pwd, "getpwnam"):
        return {"hata": f"'{PROFIL}' hesabı bulunamadı"}
    baslik = re.sub(r"[^\w\s\-ğüşöçıİĞÜŞÖÇ.]", "", (p.get("baslik") or "Ders Bağlantısı")).strip()[:60] or "Ders Bağlantısı"
    url = (p.get("url") or "").strip()
    if not re.match(r"^https?://[^\s\"'<>]+$", url):
        return {"hata": "Geçersiz web adresi (http:// veya https:// ile başlamalı)"}
    masa = Path(_masaustu_dizini(bilgi.pw_dir if bilgi else "/home/ogrenci"))
    masa.mkdir(parents=True, exist_ok=True)
    dosya_adi = re.sub(r"\s+", "_", baslik) + ".desktop"
    hedef = masa / dosya_adi
    icerik = (
        "[Desktop Entry]\n"
        "Version=1.0\n"
        "Type=Link\n"
        f"Name={baslik}\n"
        f"URL={url}\n"
        "Icon=text-html\n"
    )
    hedef.write_text(icerik, encoding="utf-8")
    _ogrenci_sahip_yap(hedef, bilgi, 0o755)
    _kullanici_bildir("Masaüstüne Bağlantı Gönderildi", f"{baslik}: {url}", acil=False)
    return {"tamam": True, "dosya": str(hedef), "mesaj": f"Masaüstüne '{dosya_adi}' eklendi"}


def masaustu_dosya(p: dict | str, icerik_b64_arg: str | None = None) -> dict:
    if isinstance(p, str):
        p = {"dosya_adi": p, "icerik_b64": icerik_b64_arg or ""}
    bilgi = _ogrenci_bilgi()
    if not bilgi and hasattr(pwd, "getpwnam"):
        return {"hata": f"'{PROFIL}' hesabı bulunamadı"}
    ham_ad = os.path.basename((p.get("dosya_adi") or "").strip())
    temiz_ad = re.sub(r"[^\w\s.\-ğüşöçıİĞÜŞÖÇ]", "_", ham_ad)[:80]
    if not temiz_ad or temiz_ad.startswith("."):
        return {"hata": "Geçersiz dosya adı"}
    try:
        veri = base64.b64decode(p.get("icerik_b64") or "", validate=True)
    except Exception:
        return {"hata": "Dosya verisi çözümlenemedi"}
    masa = Path(_masaustu_dizini(bilgi.pw_dir if bilgi else "/home/ogrenci"))
    masa.mkdir(parents=True, exist_ok=True)
    hedef = masa / temiz_ad
    hedef.write_bytes(veri)
    _ogrenci_sahip_yap(hedef, bilgi, 0o644)
    _kullanici_bildir("Masaüstüne Dosya Gönderildi", f"'{temiz_ad}' masaüstünüze kaydedildi.", acil=False)
    return {"tamam": True, "dosya": str(hedef), "boyut": len(veri), "mesaj": f"Masaüstüne '{temiz_ad}' kopyalandı ({len(veri)} B)"}


def hosts_ekle(p: dict | str, ad_arg: str | None = None) -> dict:
    if isinstance(p, str):
        p = {"ip": p, "ad": ad_arg or ""}
    ip = (p.get("ip") or "").strip()
    ad = (p.get("ad") or p.get("alan_adi") or "").strip().lower()
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        return {"hata": "Geçersiz IPv4 adresi"}
    if not re.match(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$", ad):
        return {"hata": "Geçersiz alan adı (örn. abc.local)"}
    hosts_yolu = Path(HOSTS_YOLU)
    mevcut = ""
    if hosts_yolu.exists():
        mevcut = hosts_yolu.read_text(encoding="utf-8", errors="replace")
    yeni_satirlar = []
    degisti = False
    for satir in mevcut.splitlines():
        temiz = satir.split("#", 1)[0].split()
        if len(temiz) >= 2 and ad in [x.lower() for x in temiz[1:]]:
            yeni_satirlar.append(f"{ip}\t{ad}")
            degisti = True
        else:
            yeni_satirlar.append(satir)
    if not degisti:
        yeni_satirlar.append(f"{ip}\t{ad}")
    icerik = "\n".join(yeni_satirlar).rstrip("\n") + "\n"
    hosts_yolu.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=str(hosts_yolu.parent), prefix=".hosts.psy.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(icerik)
    try:
        os.chmod(gecici, 0o644)
    except OSError:
        pass
    os.replace(gecici, hosts_yolu)
    return {
        "tamam": True,
        "ip": ip,
        "ad": ad,
        "degisti": degisti,
        "islem": "guncellendi" if degisti else "eklendi",
        "mesaj": f"/etc/hosts: {ip} -> {ad} ({'güncellendi' if degisti else 'eklendi'})",
    }


ISLEMLER = {
    "ekran_kilit": ekran_kilit,
    "duyuru": duyuru,
    "internet": internet,
    "masaustu_url": masaustu_url,
    "masaustu_dosya": masaustu_dosya,
    "hosts_ekle": hosts_ekle,
}


def ana():
    p = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    islev = ISLEMLER.get(p.get("kip"))
    if not islev:
        print(json.dumps({"hata": f"bilinmeyen kip: {p.get('kip')}"}, ensure_ascii=False))
        return
    try:
        sonuc = islev(p)
    except Exception as hata:
        sonuc = {"hata": str(hata)}
    print(json.dumps(sonuc, ensure_ascii=False))


if __name__ == "__main__":
    ana()
