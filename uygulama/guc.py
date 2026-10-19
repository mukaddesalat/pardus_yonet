"""Yeniden başlatma / kapatma (istem §8).

"Komut gönderildi" ile "kapanma/yeniden açılma doğrulandı" ayrı raporlanır.
"""

import asyncio
import socket
import time

from . import ayarlar, secim, ssh_araclari, veritabani, yonetim


def _port_acik_mi(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=2):
            return True
    except OSError:
        return False


async def guc_isi(is_id: str, cihaz_idler: list[str], eylem: str,
                  iptal: asyncio.Event) -> None:
    """eylem: 'yeniden_baslat' veya 'kapat'."""
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz or iptal.is_set():
            return
        ip = cihaz["ip"]
        neden = secim.uygunluk(cihaz, "guc")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(_uygula, is_id, cihaz, eylem)

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))


def _uygula(is_id: str, cihaz: dict, eylem: str) -> None:
    ip, port = cihaz["ip"], cihaz["ssh_port"]
    ad = veritabani.cihaz_adi(cihaz)
    komut = "reboot" if eylem == "yeniden_baslat" else "poweroff"
    etiket = "yeniden başlatma" if eylem == "yeniden_baslat" else "kapatma"

    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "gonder",
                              f"{ad} — {etiket} komutu gönderiliyor")
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — bağlantı kurulamadı: {hata}")
        return
    try:
        # bağlantı komut sırasında kopabilir; bu bir hata değildir
        try:
            ssh_araclari.sudo_komut(istemci, ["systemctl", komut], zaman=15)
        except ssh_araclari.SudoHatasi as hata:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}")
            return
        except Exception:
            pass
    finally:
        istemci.close()

    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "dogrula",
                              f"{ad} — komut gönderildi; kapanma bekleniyor")
    kapandi = False
    for _ in range(45):
        if not _port_acik_mi(ip, port):
            kapandi = True
            break
        time.sleep(2)
    if not kapandi:
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "dogrula",
            f"{ad} — komut gönderildi ancak kapanma doğrulanamadı")
        return

    if eylem == "kapat":
        veritabani.cihaz_guncelle(cihaz["id"], durum="SSH erişilemiyor",
                                  son_kontrol=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                  f"{ad} — kapanma doğrulandı")
        return

    for _ in range(60):
        if _port_acik_mi(ip, port):
            veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                      f"{ad} — yeniden açılma doğrulandı")
            veritabani.cihaz_guncelle(cihaz["id"], son_kontrol=veritabani.simdi())
            return
        time.sleep(3)
    veritabani.hedef_guncelle(
        is_id, ip, "basarisiz", "dogrula",
        f"{ad} — kapandı ancak {180} saniye içinde yeniden açılmadı; elle kontrol edin")
