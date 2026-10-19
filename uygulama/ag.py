"""Öğretmen bilgisayarının ağ bilgileri: kendi adresleri ve laboratuvar ağı önerisi.

Kendi adresleri, öğretmen bilgisayarının envantere/işlemlere hedef olarak
girmesini engellemek için kullanılır (ödev teslim arşivi ve yönetim verisi bu
makinededir; temizlik vb. işler buraya asla uygulanmaz).

Servis sertleştirmesi (RestrictAddressFamilies) netlink'e izin vermediği için
`ip` komutu servis içinde çalışmaz; bilgiler /proc/net dosyalarından okunur
(lab'da doğrulandı). `ip` yalnız geliştirme ortamında ek kaynaktır.
"""

import ipaddress
import json
import socket
import struct
import subprocess
import time
from functools import lru_cache


def _ip_json(*argv) -> list:
    try:
        cikti = subprocess.run(["ip", "-j", *argv], capture_output=True, text=True,
                               timeout=5).stdout
        return json.loads(cikti or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def _kaynak_adres() -> str | None:
    """Dış bağlantının kaynak adresi (paket gönderilmez; yalnız yönlendirme seçilir)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def fib_yerel(metin: str) -> set[str]:
    """/proc/net/fib_trie içeriğinden bu makinenin (LOCAL) IPv4 adresleri."""
    adresler, onceki = set(), None
    for satir in metin.splitlines():
        kirp = satir.strip()
        if kirp.startswith("|--") or kirp.startswith("+--"):
            onceki = kirp.split()[1]
        elif "/32 host LOCAL" in kirp and onceki:
            adresler.add(onceki)
    return adresler


def rota_agi(metin: str, adres: str | None) -> dict | None:
    """/proc/net/route içeriğinden varsayılan arayüzün, adresi içeren ağı."""
    satirlar = [s.split() for s in metin.splitlines()[1:] if s.strip()]
    varsayilan = next((s[0] for s in satirlar if len(s) > 7 and s[1] == "00000000"), None)
    for s in satirlar:
        if len(s) < 8 or s[0] != varsayilan or s[1] == "00000000":
            continue
        hedef = socket.inet_ntoa(struct.pack("<I", int(s[1], 16)))
        maske = socket.inet_ntoa(struct.pack("<I", int(s[7], 16)))
        ag = ipaddress.ip_network(f"{hedef}/{maske}", strict=False)
        if adres is None or ipaddress.ip_address(adres) in ag:
            return {"ag": str(ag), "arayuz": varsayilan}
    return None


def _oku(yol: str) -> str:
    try:
        with open(yol, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


@lru_cache(maxsize=1)
def _yerel_onbellek(_dakika: int) -> frozenset:
    adresler = {"127.0.0.1", "::1"} | fib_yerel(_oku("/proc/net/fib_trie"))
    kaynak = _kaynak_adres()
    if kaynak:
        adresler.add(kaynak)
    for arayuz in _ip_json("addr", "show"):
        for bilgi in arayuz.get("addr_info", []):
            if bilgi.get("local"):
                adresler.add(bilgi["local"])
    try:
        for kayit in socket.getaddrinfo(socket.gethostname(), None):
            adresler.add(kayit[4][0])
    except OSError:
        pass
    return frozenset(adresler)


def yerel_adresler() -> frozenset:
    """Bu makinenin IP adresleri (dakikalık önbellek; DHCP değişimine uyum)."""
    return _yerel_onbellek(int(time.time() // 60))


def ogretmen_adresi_mi(ip: str) -> bool:
    return ip in yerel_adresler()


def varsayilan_ag() -> dict:
    """Varsayılan rotanın arayüzündeki IPv4 ağı; tarama önerisi olarak gösterilir."""
    adres = _kaynak_adres()
    bulunan = rota_agi(_oku("/proc/net/route"), adres)
    if bulunan:
        ag = ipaddress.ip_network(bulunan["ag"])
        if ag.num_addresses > 1024:  # çok geniş ağlarda /24'e daralt
            ag = ipaddress.ip_network(f"{adres}/24", strict=False)
        return {"ag": str(ag), "adres": adres, "arayuz": bulunan["arayuz"]}
    rota = _ip_json("route", "show", "default")
    arayuz = rota[0].get("dev") if rota else None
    for kayit in _ip_json("-4", "addr", "show"):
        if arayuz and kayit.get("ifname") != arayuz:
            continue
        for bilgi in kayit.get("addr_info", []):
            if bilgi.get("family") == "inet" and bilgi.get("scope") == "global":
                ag = ipaddress.ip_network(f"{bilgi['local']}/{bilgi['prefixlen']}", strict=False)
                if ag.num_addresses > 1024:
                    ag = ipaddress.ip_network(f"{bilgi['local']}/24", strict=False)
                return {"ag": str(ag), "adres": bilgi["local"], "arayuz": kayit.get("ifname")}
    if adres:
        return {"ag": str(ipaddress.ip_network(f"{adres}/24", strict=False)), "adres": adres,
                "arayuz": None}
    return {"ag": None, "adres": None, "arayuz": None}
