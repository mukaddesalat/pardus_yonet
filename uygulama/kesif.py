"""M1-S3 Ağda Bul: laboratuvar ağını tarama ve bulunanları envantere alma.

Tarama yalnız SSH portunu ve sunucu kimliğini (host anahtarı) toplar; kimlik
bilgisi GÖNDERMEZ ve envantere kayıt EKLEMEZ. Bulunanlar ayrı listede durur;
öğretmen parmak izlerini görüp onaylayınca envantere eklenir. Hazırlık (anahtar,
parolasız sudo, ogrenci hesabı) ayrı ve açık bir adımdır (hazirlik.py); parola
listesi denenmez — yalnız pardus/hp hesaplarının öğretmence bilinen parolası,
cihaz+hesap başına sınırlı deneme bütçesiyle kullanılır.
"""

import asyncio
import ipaddress
import logging

from . import ag, ayarlar, hazirlik, ssh_araclari, veritabani

log = logging.getLogger("psy.kesif")


def aralik_genislet(metin: str, haric: list[str]) -> list[str]:
    """CIDR ('192.168.10.0/24'), aralık ('192.168.10.10-60') veya virgüllü liste."""
    metin = metin.strip()
    adresler: list[str] = []
    if "/" in metin:
        ag_ = ipaddress.ip_network(metin, strict=False)
        adresler = [str(a) for a in ag_.hosts()]
    elif "-" in metin and "," not in metin:
        bas, son = metin.rsplit("-", 1)
        bas_ip = ipaddress.ip_address(bas.strip())
        if "." in son:
            son_ip = ipaddress.ip_address(son.strip())
        else:
            son_ip = ipaddress.ip_address(".".join(bas.strip().split(".")[:3] + [son.strip()]))
        if int(son_ip) < int(bas_ip):
            raise ValueError("Aralık sonu başlangıçtan küçük")
        adresler = [str(ipaddress.ip_address(i)) for i in range(int(bas_ip), int(son_ip) + 1)]
    else:
        adresler = [str(ipaddress.ip_address(p.strip())) for p in metin.split(",") if p.strip()]

    haric_kume = {h.strip() for h in haric if h.strip()}
    adresler = [a for a in adresler if a not in haric_kume]
    if len(adresler) > ayarlar.EN_FAZLA_HEDEF:
        raise ValueError(
            f"Kapsam çok geniş: {len(adresler)} adres (sınır {ayarlar.EN_FAZLA_HEDEF}). "
            "Laboratuvar aralığını daraltın.")
    return adresler


async def _ssh_acik_mi(ip: str, port: int) -> bool:
    try:
        _, yazici = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=ayarlar.TCP_ZAMAN_ASIMI)
        yazici.close()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def kesif_isi(is_id: str, adresler: list[str], port: int,
                    iptal: asyncio.Event) -> None:
    """SSH erişimi + sunucu kimliği toplama. Kimlik bilgisi gönderilmez."""
    sinir = asyncio.Semaphore(ayarlar.TARAMA_PARALELLIGI)
    yerel = ag.yerel_adresler()

    async def _tek(ip: str):
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        if ip in yerel:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam",
                                      "Öğretmen bilgisayarının kendisi — taranmadı")
            return
        async with sinir:
            veritabani.hedef_guncelle(is_id, ip, "calisiyor", "tcp", "SSH portu kontrol ediliyor")
            if not await _ssh_acik_mi(ip, port):
                veritabani.hedef_guncelle(is_id, ip, "atlandi", "tcp",
                                          "SSH erişilemiyor (kapalı olabilir, kesin değil)")
                return
            try:
                kimlik = await asyncio.to_thread(ssh_araclari.host_kimligi_topla, ip, port)
            except Exception as hata:
                veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kimlik",
                                          f"Sunucu kimliği alınamadı: {hata}")
                return
            veritabani.calistir(
                "INSERT INTO bulunan(ip, ssh_port, anahtar_tipi, anahtar_b64, parmak_izi, zaman) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(ip, ssh_port) DO UPDATE SET "
                "anahtar_tipi=excluded.anahtar_tipi, anahtar_b64=excluded.anahtar_b64, "
                "parmak_izi=excluded.parmak_izi, zaman=excluded.zaman",
                (ip, port, kimlik["tip"], kimlik["b64"], kimlik["parmak_izi"], veritabani.simdi()))
            kayitli = veritabani.tek("SELECT * FROM cihaz WHERE ip=? AND ssh_port=?", (ip, port))
            if kayitli and kayitli["parmak_izi"] and kayitli["parmak_izi"] != kimlik["parmak_izi"]:
                mesaj = f"Envanterde var ama sunucu kimliği DEĞİŞMİŞ — {kimlik['parmak_izi']}"
            elif kayitli:
                mesaj = f"Zaten envanterde ({veritabani.cihaz_adi(dict(kayitli))})"
            else:
                mesaj = f"Bulundu — {kimlik['parmak_izi']}"
            veritabani.hedef_guncelle(is_id, ip, "basarili", "kimlik", mesaj,
                                      {"parmak_izi": kimlik["parmak_izi"], "envanterde": bool(kayitli)})

    await asyncio.gather(*(_tek(ip) for ip in adresler))


def bulunanlar() -> list[dict]:
    satirlar = []
    for s in veritabani.sorgula("SELECT * FROM bulunan"):
        b = dict(s)
        b.pop("anahtar_b64", None)
        kayit = veritabani.tek("SELECT id, etiket, hostname, ip, parmak_izi FROM cihaz "
                               "WHERE ip=? AND ssh_port=?", (b["ip"], b["ssh_port"]))
        b["envanter_id"] = kayit["id"] if kayit else None
        b["kimlik_farkli"] = bool(kayit and kayit["parmak_izi"] and kayit["parmak_izi"] != b["parmak_izi"])
        b["ayni_kimlikli"] = veritabani.tek(
            "SELECT COUNT(*) AS n FROM bulunan WHERE parmak_izi=?", (b["parmak_izi"],))["n"]
        satirlar.append(b)
    return sorted(satirlar, key=lambda b: (ipaddress.ip_address(b["ip"]), b["ssh_port"]))


def envantere_ekle(anahtarlar: list[str], laboratuvar: str | None) -> list[str]:
    """Bulunanları (ip:port) kimlikleri ONAYLI olarak envantere ekler.

    Onay, öğretmenin listede parmak izini görüp "ekle" demesidir. Bağlantı
    kurulmaz, hesap değiştirilmez, paket kurulmaz.
    """
    eklenen = []
    for anahtar_metin in dict.fromkeys(anahtarlar):
        ip, _, port = anahtar_metin.rpartition(":")
        b = veritabani.tek("SELECT * FROM bulunan WHERE ip=? AND ssh_port=?", (ip, int(port or 22)))
        if not b or ag.ogretmen_adresi_mi(ip):
            continue
        cihaz_id = veritabani.cihaz_bul_veya_olustur(b["ip"], b["ssh_port"])
        cihaz = veritabani.cihaz(cihaz_id)
        alanlar = {"anahtar_tipi": b["anahtar_tipi"], "anahtar_b64": b["anahtar_b64"],
                   "parmak_izi": b["parmak_izi"], "parmak_izi_onay": 1, "erisim": 1,
                   "erisim_zamani": b["zaman"]}
        if cihaz["parmak_izi"] and cihaz["parmak_izi"] != b["parmak_izi"]:
            # kimlik değiştiyse eski anahtar erişimi artık güvenilir değildir
            alanlar.update(anahtar_durumu="gerekli", sudo_durumu=None)
        if cihaz["durum"] in ("SSH erişilemiyor", None) or alanlar.get("anahtar_durumu"):
            alanlar["durum"] = "Hazırlık gerekli"
        if laboratuvar:
            alanlar["grup"] = laboratuvar.strip()[:40]
        veritabani.cihaz_guncelle(cihaz_id, **alanlar)
        hazirlik.klon_isaretle(b["parmak_izi"])
        eklenen.append(cihaz_id)
    return eklenen


def bulunanlari_temizle() -> None:
    veritabani.calistir("DELETE FROM bulunan")
