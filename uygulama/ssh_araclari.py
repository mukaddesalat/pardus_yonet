"""SSH yardımcıları: host kimliği toplama, doğrulamalı bağlantı, güvenli komutlar.

Kurallar (istem §5-6):
- Kimlik bilgisi göndermeden önce sunucu anahtarı toplanır ve kullanıcı onayına
  sunulur; sessiz AutoAddPolicy kullanılmaz.
- Parola/anahtar komut satırına veya loglara yazılmaz.
- Anahtar testi yalnızca uygulama anahtarıyla yapılır; parola geri dönüşü kapalıdır.
"""

import base64
import hashlib
import shlex
import socket

import paramiko

from . import ayarlar


class SunucuKimligiHatasi(Exception):
    """Beklenen host anahtarı ile sunulan anahtar uyuşmuyor."""


class _ReddetPolitikasi(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        raise SunucuKimligiHatasi(
            f"{hostname}: sunucu kimliği kayıtlı değil veya değişmiş")


def parmak_izi(anahtar: paramiko.PKey) -> str:
    ozet = hashlib.sha256(anahtar.asbytes()).digest()
    return "SHA256:" + base64.b64encode(ozet).decode().rstrip("=")


def _anahtar_nesnesi(tip: str, b64: str) -> paramiko.PKey:
    veri = base64.b64decode(b64)
    try:
        return paramiko.PKey.from_type_string(tip, veri)
    except AttributeError:  # eski paramiko sürümleri
        siniflar = {
            "ssh-ed25519": paramiko.Ed25519Key,
            "ssh-rsa": paramiko.RSAKey,
            "ecdsa-sha2-nistp256": paramiko.ECDSAKey,
        }
        return siniflar[tip](data=veri)


def _host_adi(ip: str, port: int) -> str:
    return ip if port == 22 else f"[{ip}]:{port}"


def host_kimligi_topla(ip: str, port: int) -> dict:
    """Kimlik bilgisi GÖNDERMEDEN sunucunun host anahtarını alır."""
    sock = socket.create_connection((ip, port), timeout=ayarlar.SSH_ZAMAN_ASIMI)
    aktarim = paramiko.Transport(sock)
    try:
        aktarim.start_client(timeout=ayarlar.SSH_ZAMAN_ASIMI)
        anahtar = aktarim.get_remote_server_key()
        return {
            "tip": anahtar.get_name(),
            "b64": anahtar.get_base64(),
            "parmak_izi": parmak_izi(anahtar),
        }
    finally:
        aktarim.close()


def _istemci(ip: str, port: int, tip: str, b64: str) -> paramiko.SSHClient:
    """Onaylanmış host anahtarı önceden yüklenmiş, reddeden politikalı istemci."""
    istemci = paramiko.SSHClient()
    istemci.set_missing_host_key_policy(_ReddetPolitikasi())
    istemci.get_host_keys().add(_host_adi(ip, port), tip, _anahtar_nesnesi(tip, b64))
    return istemci


def parola_ile_baglan(ip: str, port: int, kullanici: str, parola: str,
                      tip: str, b64: str) -> paramiko.SSHClient:
    istemci = _istemci(ip, port, tip, b64)
    istemci.connect(
        ip, port=port, username=kullanici, password=parola,
        timeout=ayarlar.SSH_ZAMAN_ASIMI, allow_agent=False, look_for_keys=False,
    )
    return istemci


def anahtar_ile_baglan(ip: str, port: int, kullanici: str,
                       ozel_anahtar_yolu: str, tip: str, b64: str) -> paramiko.SSHClient:
    """Yalnızca uygulama anahtarıyla bağlanır; parola geri dönüşü yoktur."""
    istemci = _istemci(ip, port, tip, b64)
    pkey = paramiko.Ed25519Key.from_private_key_file(ozel_anahtar_yolu)
    istemci.connect(
        ip, port=port, username=kullanici, pkey=pkey,
        timeout=ayarlar.SSH_ZAMAN_ASIMI, allow_agent=False, look_for_keys=False,
    )
    return istemci


def komut(istemci: paramiko.SSHClient, argv: list[str],
          girdi: str | None = None, zaman: int | None = None) -> tuple[int, str, str]:
    """Argüman listesini güvenli kaçışla çalıştırır (istem §7)."""
    satir = " ".join(shlex.quote(p) for p in argv)
    stdin, stdout, stderr = istemci.exec_command(
        satir, timeout=zaman or ayarlar.KOMUT_ZAMAN_ASIMI)
    if girdi is not None:
        stdin.write(girdi)
        stdin.flush()
    stdin.channel.shutdown_write()
    cikti = stdout.read().decode(errors="replace")
    hata = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, cikti, hata


class SudoHatasi(RuntimeError):
    """Parolasız sudo kullanılamıyor (karar 22). Parola döngüsüne girilmez;
    öğretmen M1-S2'deki hazırlığa yönlendirilir."""


SUDO_YOK_MESAJI = ("Parolasız sudo hazır değil — bu bilgisayarı M1-S2 “SSH ve Hesap "
                   "Hazırlığı” sayfasından hazırlayın")


def sudo_komut(istemci: paramiko.SSHClient, argv: list[str],
               sudo_parola: str | None = None, girdi: str | None = None,
               zaman: int | None = None) -> tuple[int, str, str]:
    """Komutu sudo ile çalıştırır.

    Günlük işlerde parola verilmez: yalnızca parolasız sudo denenir (-n) ve
    parola isteyen sudo açık hata verir (SudoHatasi). Parola yalnız ilk hazırlıkta
    (hazirlik.py) verilir; stdin'den geçirilir (-S), komut satırına ve loglara yazılmaz.
    """
    kuyruk = " ".join(shlex.quote(p) for p in argv)
    if sudo_parola is None:
        satir = "LC_ALL=C sudo -n -- " + kuyruk
        tam_girdi = girdi
    else:
        satir = "LC_ALL=C sudo -S -p '' -- " + kuyruk
        tam_girdi = sudo_parola + "\n" + (girdi or "")
    stdin, stdout, stderr = istemci.exec_command(
        satir, timeout=zaman or ayarlar.KOMUT_ZAMAN_ASIMI)
    if tam_girdi is not None:
        stdin.write(tam_girdi)
        stdin.flush()
    stdin.channel.shutdown_write()
    cikti = stdout.read().decode(errors="replace")
    hata = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if rc != 0 and sudo_parola is None and _sudo_parola_istedi(hata):
        raise SudoHatasi(SUDO_YOK_MESAJI)
    return rc, cikti, hata


def _sudo_parola_istedi(hata: str) -> bool:
    kucuk = hata.lower()
    return "sudo:" in kucuk and ("password is required" in kucuk
                                 or "a terminal is required" in kucuk
                                 or "not in the sudoers" in kucuk
                                 or "may not run sudo" in kucuk)


def sudo_betik(istemci: paramiko.SSHClient, betik: str, parametre: dict,
               sudo_parola: str | None = None, zaman: int | None = None) -> dict:
    """Uzak Python betiğini root olarak çalıştırır; JSON sonuç bekler (karar 12).

    Parametreler argv ile JSON olarak geçirilir; betikler yalnızca izin listesindendir,
    serbest komut girişi yoktur (istem §7). Parolasız sudo yoksa SudoHatasi.
    """
    import json as _json
    if sudo_parola is None:
        rc, cikti, hata = sudo_komut(
            istemci, ["python3", "-", _json.dumps(parametre, ensure_ascii=False)],
            girdi=betik, zaman=zaman)
    else:
        rc, cikti, hata = sudo_komut(
            istemci, ["python3", "-c", betik, _json.dumps(parametre, ensure_ascii=False)],
            sudo_parola=sudo_parola, zaman=zaman)
    if rc != 0:
        ozet = (hata or cikti).strip().splitlines()
        raise RuntimeError(ozet[-1] if ozet else f"uzak betik rc={rc}")
    try:
        return _json.loads(cikti.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"uzak betik geçersiz çıktı verdi: {cikti[:200]!r}")


def betik(istemci: paramiko.SSHClient, kod: str, parametre: dict,
          zaman: int | None = None) -> dict:
    """Uzak Python betiğini bağlı kullanıcının yetkisiyle (sudo'suz) çalıştırır."""
    import json as _json
    rc, cikti, hata = komut(
        istemci, ["python3", "-", _json.dumps(parametre, ensure_ascii=False)],
        girdi=kod, zaman=zaman)
    if rc != 0:
        ozet = (hata or cikti).strip().splitlines()
        raise RuntimeError(ozet[-1] if ozet else f"uzak betik rc={rc}")
    try:
        return _json.loads(cikti.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"uzak betik geçersiz çıktı verdi: {cikti[:200]!r}")


def parolasiz_sudo_var_mi(istemci: paramiko.SSHClient) -> bool:
    """Sistem değiştirmeden `sudo -n true` dener."""
    rc, _, _ = komut(istemci, ["sudo", "-n", "true"])
    return rc == 0


# ---- hedef bilgisi toplama (salt okunur) ----

def os_bilgisi(istemci) -> dict:
    rc, cikti, _ = komut(istemci, ["cat", "/etc/os-release"])
    bilgi = {}
    if rc == 0:
        for satir in cikti.splitlines():
            if "=" in satir:
                ad, deger = satir.split("=", 1)
                bilgi[ad] = deger.strip().strip('"')
    return bilgi


def hostname_al(istemci) -> str:
    rc, cikti, _ = komut(istemci, ["hostname"])
    return cikti.strip() if rc == 0 else ""


def masaustu_tespit(istemci) -> str:
    """Kurulu ortamı dosya sisteminden doğrular (karar 2); ortam değişkenine güvenmez."""
    rc, _, _ = komut(istemci, ["test", "-x", "/usr/bin/gnome-shell"])
    if rc == 0:
        return "GNOME"
    rc, _, _ = komut(istemci, ["test", "-x", "/usr/bin/xfce4-session"])
    if rc == 0:
        return "XFCE (desteklenmiyor)"
    return "bilinmiyor (desteklenmiyor)"


def hesap_bilgisi(istemci, hesap: str) -> dict | None:
    """getent ile hesabın varlığını ve gerçek ev dizinini tespit eder (istem §6.3)."""
    rc, cikti, _ = komut(istemci, ["getent", "passwd", hesap])
    if rc != 0 or not cikti.strip():
        return None
    parcalar = cikti.strip().split(":")
    return {"hesap": parcalar[0], "uid": int(parcalar[2]), "ev": parcalar[5]}


def sudo_dogrula(istemci, parola: str | None = None) -> str:
    """Sistem değiştirmeden sudo kullanılabilirliğini kontrol eder (istem §5.7).

    Dönüş: 'parolasiz' (sudo -n çalışıyor) / 'parola_gerekli' (parolayla çalışıyor,
    hazırlık gerekli) / 'yetersiz' (sudo yetkisi yok) / 'belirsiz' (parola verilmedi).
    """
    if parolasiz_sudo_var_mi(istemci):
        return "parolasiz"
    if parola is not None:
        rc, _, _ = komut(istemci, ["sudo", "-S", "-p", "", "-v"], girdi=parola + "\n")
        if rc == 0:
            # doğrulama zaman damgasını hemen kapat; iz bırakma
            komut(istemci, ["sudo", "-k"])
            return "parola_gerekli"
        return "yetersiz"
    return "belirsiz"


def aktif_oturumlar(istemci) -> list[str]:
    """logind oturumları; who yalnızca tty oturumlarını gösterdiği için yetmez."""
    kullanicilar: set[str] = set()
    rc, cikti, _ = komut(istemci, ["loginctl", "list-sessions", "--no-legend"])
    if rc == 0:
        for satir in cikti.splitlines():
            parcalar = satir.split()
            if len(parcalar) >= 3:  # SESSION UID USER ...
                kullanicilar.add(parcalar[2])
    else:  # loginctl yoksa geri dönüş
        rc, cikti, _ = komut(istemci, ["who", "-s"])
        if rc == 0:
            kullanicilar = {s.split()[0] for s in cikti.splitlines() if s.split()}
    return sorted(kullanicilar)


# ---- authorized_keys güvenli ekleme (istem §6) ----

_ANAHTAR_EKLE_BETIGI = r'''
import os, pwd, stat, sys

acik_satir = sys.stdin.read().strip()
if not acik_satir.startswith("ssh-ed25519 "):
    print("HATA: beklenmeyen anahtar biçimi"); sys.exit(2)

bilgi = pwd.getpwuid(os.getuid())
ev = bilgi.pw_dir
ssh_dizin = os.path.join(ev, ".ssh")
ak_yolu = os.path.join(ssh_dizin, "authorized_keys")

# .ssh dizini: sembolik bağlantı veya yabancı sahiplik varsa dur (istem §6.4)
if os.path.islink(ssh_dizin):
    print("HATA: .ssh sembolik bağlantı"); sys.exit(3)
if not os.path.isdir(ssh_dizin):
    os.mkdir(ssh_dizin, 0o700)
st = os.lstat(ssh_dizin)
if st.st_uid != os.getuid():
    print("HATA: .ssh sahibi farklı"); sys.exit(3)

if os.path.islink(ak_yolu):
    print("HATA: authorized_keys sembolik bağlantı"); sys.exit(3)

fd = os.open(ak_yolu, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
with os.fdopen(fd, "r+") as f:
    st = os.fstat(f.fileno())
    if st.st_uid != os.getuid():
        print("HATA: authorized_keys sahibi farklı"); sys.exit(3)
    icerik = f.read()
    anahtar_parcasi = " ".join(acik_satir.split()[:2])
    if any(anahtar_parcasi in satir for satir in icerik.splitlines()):
        print("ZATEN_VAR")
    else:
        if icerik and not icerik.endswith("\n"):
            f.write("\n")
        f.write(acik_satir + "\n")
        print("EKLENDI")
os.chmod(ak_yolu, 0o600)
'''


_ANAHTAR_SIL_BETIGI = r'''
import os, sys, tempfile

acik_satir = sys.stdin.read().strip()
parcalar = acik_satir.split()
if len(parcalar) < 2 or parcalar[0] != "ssh-ed25519":
    print("HATA: beklenmeyen anahtar biçimi"); sys.exit(2)
blob = parcalar[1]

ssh_dizin = os.path.join(os.path.expanduser("~"), ".ssh")
ak_yolu = os.path.join(ssh_dizin, "authorized_keys")
if os.path.islink(ssh_dizin) or os.path.islink(ak_yolu):
    print("HATA: sembolik bağlantı"); sys.exit(3)
if not os.path.isfile(ak_yolu):
    print("YOK"); sys.exit(0)

fd = os.open(ak_yolu, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
with os.fdopen(fd) as f:
    if os.fstat(f.fileno()).st_uid != os.getuid():
        print("HATA: authorized_keys sahibi farklı"); sys.exit(3)
    satirlar = f.read().splitlines(True)

# yalnızca uygulamanın anahtarı olan satırlar kaldırılır; diğerleri aynen kalır
kalan = [s for s in satirlar if blob not in s.split()]
if len(kalan) == len(satirlar):
    print("YOK"); sys.exit(0)

gecici_fd, gecici = tempfile.mkstemp(dir=ssh_dizin, prefix=".authorized_keys.")
with os.fdopen(gecici_fd, "w") as f:
    f.writelines(kalan)
os.chmod(gecici, 0o600)
os.replace(gecici, ak_yolu)
print("SILINDI")
'''


def anahtar_sil(istemci, acik_satir: str) -> str:
    """Bağlı kullanıcının authorized_keys dosyasından YALNIZCA uygulama anahtarını
    kaldırır (istem §6: iptal yalnızca uygulamaya ait anahtarı etkiler).

    Dönüş: 'SILINDI' / 'YOK' / hata metni.
    """
    rc, cikti, hata = komut(
        istemci, ["python3", "-c", _ANAHTAR_SIL_BETIGI], girdi=acik_satir + "\n")
    sonuc = (cikti or hata).strip()
    if rc != 0 and not sonuc:
        sonuc = f"HATA: uzak betik rc={rc}"
    return sonuc


def anahtar_ekle(istemci, acik_satir: str) -> str:
    """Bağlı kullanıcının authorized_keys dosyasına uygulama anahtarını ekler.

    Mevcut içerik korunur, yinelenen kayıt eklenmez, sembolik bağlantı ve
    sahiplik sorunlarında durur. Dönüş: 'EKLENDI' / 'ZATEN_VAR' / hata metni.
    """
    rc, cikti, hata = komut(
        istemci, ["python3", "-c", _ANAHTAR_EKLE_BETIGI], girdi=acik_satir + "\n")
    sonuc = (cikti or hata).strip()
    if rc != 0 and not sonuc:
        sonuc = f"HATA: uzak betik rc={rc}"
    return sonuc
