"""Öğrenci kişisel teslim kodu (proje sahibi kararı: 8 karakter harf+rakam).

Kod yalnız üretildiği anda öğretmene gösterilir (yazdırılabilir kart); veritabanında
scrypt özeti tutulur. Kaybolan kod açığa çıkarılmaz, yenisi üretilir (istem §4).
"""

import base64
import hashlib
import hmac
import os
import secrets

# Karışan karakterler yok: 0/O, 1/I/L. 31 karakter ^ 8 ≈ 8,5·10^11 olasılık.
ALFABE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
UZUNLUK = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def uret() -> str:
    """'K7QM-3XRA' biçiminde yeni kod."""
    ham = "".join(secrets.choice(ALFABE) for _ in range(UZUNLUK))
    return f"{ham[:4]}-{ham[4:]}"


def normallestir(kod: str) -> str:
    """Kullanıcı girişini karşılaştırılabilir hâle getirir: büyük harf, tire/boşluksuz."""
    return "".join(ch for ch in (kod or "").upper() if ch not in "- \t")


def ozet(kod: str) -> str:
    tuz = os.urandom(16)
    deger = hashlib.scrypt(normallestir(kod).encode(), salt=tuz, **_SCRYPT)
    return base64.b64encode(tuz).decode() + "$" + base64.b64encode(deger).decode()


def dogru_mu(kod: str, kayit: str | None) -> bool:
    normal = normallestir(kod)
    if not kayit or len(normal) != UZUNLUK or any(ch not in ALFABE for ch in normal):
        return False
    try:
        tuz_b64, ozet_b64 = kayit.split("$", 1)
        tuz, beklenen = base64.b64decode(tuz_b64), base64.b64decode(ozet_b64)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(hashlib.scrypt(normal.encode(), salt=tuz, **_SCRYPT), beklenen)


# Kimliği olmayan veya kodu tanımsız öğrenci için de aynı süreyi harcamak üzere
# (numaranın var olup olmadığı zamanlamadan anlaşılmasın).
SAHTE_KAYIT = ozet(uret())
