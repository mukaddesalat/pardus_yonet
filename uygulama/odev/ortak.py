"""Ödev modülünün ortak ayarları: veri yolları, portal adresi ve zaman."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Kurulu pakette /var/lib/pardus-sinif-odev; geliştirmede ./veri-odev
ODEV_DIZINI = Path(os.environ.get("PSY_ODEV_DIZINI", "veri-odev")).resolve()

PORTAL_ADRESI = os.environ.get("PSY_ODEV_ADRES", "0.0.0.0")
PORTAL_PORTU = int(os.environ.get("PSY_ODEV_PORT", "8090"))
VARSAYILAN_AD = "ogretmen.lab"

# Varsayılan sınırlar (öğretmen ödev başına değiştirebilir)
VARSAYILAN_EN_FAZLA_DOSYA = 20
VARSAYILAN_EN_FAZLA_MB = 100
EN_FAZLA_DOSYA_SINIRI = 500
EN_FAZLA_MB_SINIRI = 2048
BOS_ALAN_PAYI = 1024 * 1024 * 1024   # yükleme sonrası diskte en az 1 GB kalmalı
YARIM_ZAMAN_ASIMI_SN = 2 * 3600       # etkinliği biten yarım yükleme temizlenir

try:
    from zoneinfo import ZoneInfo
    ISTANBUL = ZoneInfo("Europe/Istanbul")
except Exception:  # tz veritabanı yoksa (ör. Windows geliştirme): 2016'dan beri sabit UTC+3
    ISTANBUL = timezone(timedelta(hours=3), "Europe/Istanbul")


def yollar() -> dict[str, Path]:
    return {
        "veritabani": ODEV_DIZINI / "odev.db",
        "gecici": ODEV_DIZINI / "gecici",
        "teslimler": ODEV_DIZINI / "teslimler",
    }


def simdi() -> datetime:
    return datetime.now(timezone.utc)


def simdi_iso() -> str:
    return simdi().isoformat(timespec="seconds")


def iso_oku(deger: str | None) -> datetime | None:
    if not deger:
        return None
    zaman = datetime.fromisoformat(deger)
    return zaman if zaman.tzinfo else zaman.replace(tzinfo=timezone.utc)


def yerel_metin(deger: str | None) -> str:
    """UTC ISO zamanı İstanbul saatiyle '26.09.2026 14:30' biçiminde verir."""
    zaman = iso_oku(deger)
    return zaman.astimezone(ISTANBUL).strftime("%d.%m.%Y %H:%M") if zaman else ""


def yerelden_utc(metin: str | None) -> str | None:
    """Tarayıcıdan gelen '2026-09-30T17:00' (İstanbul saati) -> UTC ISO."""
    if not metin:
        return None
    zaman = datetime.fromisoformat(metin)
    if zaman.tzinfo is None:
        zaman = zaman.replace(tzinfo=ISTANBUL)
    return zaman.astimezone(timezone.utc).isoformat(timespec="seconds")


def utcden_yerel_giris(deger: str | None) -> str:
    """UTC ISO -> tarayıcı datetime-local değeri ('2026-09-30T17:00')."""
    zaman = iso_oku(deger)
    return zaman.astimezone(ISTANBUL).strftime("%Y-%m-%dT%H:%M") if zaman else ""
