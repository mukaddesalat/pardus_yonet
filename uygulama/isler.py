"""Arka plan iş yürütücüsü.

İşler asyncio görevleri olarak çalışır; ilerleme veritabanına yazılır ki
tarayıcı kapanıp açıldığında gerçek durum geri gelsin (istem §11).
"""

import asyncio
import logging

from . import veritabani

log = logging.getLogger("psy.isler")

_aktif: dict[str, dict] = {}   # is_id -> {"gorev": Task, "iptal": Event, "tip": str}


def aktif_is_var_mi(tip: str | None = None) -> bool:
    for bilgi in _aktif.values():
        if not bilgi["gorev"].done() and (tip is None or bilgi["tip"] == tip):
            return True
    return False


def iptal_iste(is_id: str) -> bool:
    bilgi = _aktif.get(is_id)
    if bilgi and not bilgi["gorev"].done():
        bilgi["iptal"].set()
        return True
    return False


def baslat(is_id: str, tip: str, coro_fabrikasi) -> None:
    """coro_fabrikasi(iptal: asyncio.Event) -> coroutine"""
    iptal = asyncio.Event()

    async def _sar():
        try:
            await coro_fabrikasi(iptal)
            durum = "iptal" if iptal.is_set() else "tamamlandi"
            veritabani.is_bitir(is_id, durum)
        except Exception as hata:  # işin kendisi hedef hatalarını ayrıca kaydeder
            log.exception("İş %s beklenmeyen hatayla bitti", is_id)
            veritabani.is_bitir(is_id, "hata", f"Beklenmeyen hata: {hata}")
        finally:
            _aktif.pop(is_id, None)

    gorev = asyncio.get_running_loop().create_task(_sar())
    _aktif[is_id] = {"gorev": gorev, "iptal": iptal, "tip": tip}
