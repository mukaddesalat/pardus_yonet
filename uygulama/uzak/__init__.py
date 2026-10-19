"""Öğrenci PC'de çalışan uzak betikler (karar 12).

Her dosya kendi başına çalışabilir olmalıdır: `python3 -c <içerik> <json>` ile
gönderilir, hedefteki Python 3.9+ ile uyumludur ve yalnızca standart kütüphane
kullanır. Sunucu yalnızca bu dizindeki izinli betikleri gönderir; serbest betik
veya komut girişi yoktur (istem §7).
"""

from functools import cache
from pathlib import Path

_DIZIN = Path(__file__).parent
_IZINLI = frozenset({"temizlik", "yedek", "durum", "hazirlik", "hesap", "gorunum", "paket", "veyon", "guc_ayar", "sinif"})


@cache
def betik(ad: str) -> str:
    if ad not in _IZINLI:
        raise ValueError(f"izin listesinde olmayan uzak betik: {ad}")
    return (_DIZIN / f"{ad}.py").read_text(encoding="utf-8")
