"""Uygulamaya özel Ed25519 SSH anahtar çifti (istem §6, karar 3).

Anahtar parolasızdır; koruma dosya izinleri ve arayüz oturumudur.
Mevcut anahtar varsa yeniden üretilmez (istem §3, tekrar kurulum).
"""

import os
import socket

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import ayarlar

YORUM = "pardus-sinif-yonetimi"


def anahtar_var_mi() -> bool:
    y = ayarlar.veri_yollari()
    return y["ozel_anahtar"].exists() and y["acik_anahtar"].exists()


def anahtar_uret_veya_yukle() -> str:
    """Anahtar çiftini hazırlar ve açık anahtar satırını döndürür."""
    y = ayarlar.veri_yollari()
    if anahtar_var_mi():
        return y["acik_anahtar"].read_text(encoding="utf-8").strip()

    y["anahtar_dizini"].mkdir(parents=True, exist_ok=True)
    try:
        # Özel anahtar dizini yalnızca sahibi (root/uygulama) tarafından okunabilir olmalıdır
        os.chmod(y["anahtar_dizini"], 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    except OSError:
        pass

    ozel = Ed25519PrivateKey.generate()
    ozel_pem = ozel.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    acik_ssh = ozel.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    acik_satir = f"{acik_ssh.decode()} {YORUM}@{socket.gethostname()}"

    # Önce kısıtlı izinle oluştur, sonra yaz (özel anahtar hiç açık izinle durmasın)
    fd = os.open(y["ozel_anahtar"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(ozel_pem)
    y["acik_anahtar"].write_text(acik_satir + "\n", encoding="utf-8")
    try:
        os.chmod(y["acik_anahtar"], 0o644)
    except OSError:
        pass
    return acik_satir


def acik_anahtar_satiri() -> str:
    return anahtar_uret_veya_yukle()


def ozel_anahtar_yolu() -> str:
    return str(ayarlar.veri_yollari()["ozel_anahtar"])
