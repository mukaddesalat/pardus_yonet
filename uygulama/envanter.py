"""M1-S1 Envanter: bilgisayar kayıtlarının TEK yönetim noktası (karar 19, 25).

- Elle ekleme ve dosyadan içe aktarma yalnız kayıt oluşturur: bağlantı, hesap
  değişikliği veya paket kurulumu BAŞLATMAZ. Sunucu kimliği M1-S2'de okunur ve
  onaylanır; o zamana kadar hiçbir kimlik bilgisi gönderilmez (istem §5.2).
- Bağlantı hesabı değiştirilirse anahtar yeni hesapta kurulu olmadığından cihaz
  yeniden hazırlık ister.
- Korunan (EBA/ETAP) cihazlar envanterde görünür ama hiçbir işleme girmez.
- Öğretmen bilgisayarının kendisi envantere eklenemez.
"""

import asyncio
import csv
import io
import ipaddress
import re

from . import ag, anahtar, ayarlar, ssh_araclari, veritabani

# Debian/Pardus kullanıcı adı kuralı (useradd NAME_REGEX varsayılanı)
_HESAP_DESENI = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_METIN_SINIRI = 40
EN_FAZLA_ICE_AKTARMA = 500


class EnvanterHatasi(ValueError):
    """Kullanıcıya olduğu gibi gösterilebilecek doğrulama hatası."""


def hesap_dogrula(hesap: str | None) -> str | None:
    hesap = (hesap or "").strip()
    if not hesap:
        return None
    if not _HESAP_DESENI.match(hesap):
        raise EnvanterHatasi("Geçersiz kullanıcı adı (küçük harf, rakam, '_' ve '-')")
    if hesap == "root":
        raise EnvanterHatasi("Root hesabıyla SSH bağlantısı kullanılmaz")
    if hesap == ayarlar.PROFIL_HESABI:
        raise EnvanterHatasi(
            f"'{hesap}' yönetilen öğrenci hesabıdır; bağlantı hesabı olarak seçilemez")
    return hesap


def _metin(deger: str | None, alan: str) -> str | None:
    deger = (deger or "").strip()
    if len(deger) > _METIN_SINIRI:
        raise EnvanterHatasi(f"{alan} en çok {_METIN_SINIRI} karakter olabilir")
    return deger or None


def _adres(ip: str, port: int) -> tuple[str, int]:
    try:
        adres = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        raise EnvanterHatasi("Geçersiz IP adresi")
    if adres.is_loopback or adres.is_multicast or adres.is_unspecified:
        raise EnvanterHatasi("Bu adres bir laboratuvar bilgisayarına ait olamaz")
    if ag.ogretmen_adresi_mi(str(adres)):
        raise EnvanterHatasi("Bu adres öğretmen bilgisayarının kendisi; envantere eklenmez")
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise EnvanterHatasi("SSH portu sayı olmalı")
    if not 1 <= port <= 65535:
        raise EnvanterHatasi("SSH portu 1–65535 arasında olmalı")
    return str(adres), port


def cihaz_ekle(ip: str, port: int = 22, etiket: str | None = None,
               grup: str | None = None, hesap: str | None = None,
               korunan: bool = False) -> str:
    """Yalnız kayıt oluşturur; hiçbir ağ bağlantısı kurmaz."""
    ip, port = _adres(ip, port)
    if veritabani.tek("SELECT id FROM cihaz WHERE ip=? AND ssh_port=?", (ip, port)):
        raise EnvanterHatasi(f"{ip}:{port} zaten envanterde")
    alanlar = {"etiket": _metin(etiket, "Görünen ad"),
               "grup": _metin(grup, "Laboratuvar") or "Laboratuvar",
               "baglanti_hesabi": hesap_dogrula(hesap),
               "durum": "Kimlik okunmadı"}
    if korunan:
        alanlar.update(korunan=1, korunan_neden="Öğretmen işaretledi")
    cihaz_id = veritabani.cihaz_bul_veya_olustur(ip, port)
    veritabani.cihaz_guncelle(cihaz_id, **alanlar)
    return cihaz_id


def cihaz_duzenle(cihaz_id: str, degisiklik: dict) -> dict:
    """İzinli alanlar: etiket, grup, baglanti_hesabi, korunan. IP/port değiştirilemez;
    farklı bir adres yeni bir cihaz demektir (istem §5)."""
    cihaz = veritabani.cihaz(cihaz_id)
    if not cihaz:
        raise EnvanterHatasi("Bilgisayar bulunamadı")
    guncel = {}
    if "etiket" in degisiklik:
        guncel["etiket"] = _metin(degisiklik["etiket"], "Görünen ad")
    if "grup" in degisiklik:
        guncel["grup"] = _metin(degisiklik["grup"], "Laboratuvar") or "Laboratuvar"
    if "korunan" in degisiklik and bool(degisiklik["korunan"]) != bool(cihaz["korunan"]):
        guncel["korunan"] = 1 if degisiklik["korunan"] else 0
        guncel["korunan_neden"] = "Öğretmen işaretledi" if degisiklik["korunan"] else None
    if "baglanti_hesabi" in degisiklik:
        yeni = hesap_dogrula(degisiklik["baglanti_hesabi"])
        if yeni != cihaz["baglanti_hesabi"]:
            guncel["baglanti_hesabi"] = yeni
            # Anahtar eski hesabın authorized_keys dosyasında; yenisinde yok.
            guncel["anahtar_durumu"] = "gerekli"
            guncel["sudo_durumu"] = None
            if cihaz["parmak_izi_onay"]:
                guncel["durum"] = "Hazırlık gerekli"
    veritabani.cihaz_guncelle(cihaz_id, **guncel)
    return {"hesap_degisti": "baglanti_hesabi" in guncel}


# ---------------------------------------------------------------- içe aktarma

def _ini_ayristir(metin: str) -> list[dict]:
    """Ansible INI envanteri: [grup] altındaki satırlar; [grup:vars] varsayılanları."""
    kayitlar, degiskenler = [], {}
    bolum, tur = "ungrouped", "host"
    for no, ham in enumerate(metin.splitlines(), 1):
        satir = ham.split("#", 1)[0].split(";", 1)[0].strip()
        if not satir:
            continue
        if satir.startswith("[") and satir.endswith("]"):
            ad = satir[1:-1].strip()
            bolum, _, ek = ad.partition(":")
            tur = {"": "host", "vars": "vars", "children": "children"}.get(ek, "diger")
            continue
        if tur == "vars":
            if "=" in satir:
                a, d = satir.split("=", 1)
                degiskenler.setdefault(bolum, {})[a.strip()] = d.strip().strip("'\"")
            continue
        if tur != "host":
            continue
        parca = satir.split()
        ozellik = dict(p.split("=", 1) for p in parca[1:] if "=" in p)
        kayitlar.append({"satir": no, "takma_ad": parca[0], "ozellik": ozellik, "grup": bolum})
    sonuc = []
    for k in kayitlar:
        ortak = {**degiskenler.get("all", {}), **degiskenler.get(k["grup"], {}), **k["ozellik"]}
        takma = k["takma_ad"]
        ip = ortak.get("ansible_host") or takma
        sonuc.append({
            "satir": k["satir"],
            "ip": ip.strip("'\""),
            "port": ortak.get("ansible_port", "22"),
            "etiket": None if _ip_mi(takma) else takma,
            "hesap": ortak.get("ansible_user"),
            "laboratuvar": None if k["grup"] in ("ungrouped", "all") else k["grup"],
        })
    return sonuc


def _ip_mi(metin: str) -> bool:
    try:
        ipaddress.ip_address(metin)
        return True
    except ValueError:
        return False


def _csv_ayristir(metin: str) -> list[dict]:
    """CSV: ad;ip;hesap;laboratuvar (başlık satırı isteğe bağlı; ';' veya ',')."""
    ayirici = ";" if metin.count(";") >= metin.count(",") else ","
    sonuc = []
    for no, satir in enumerate(csv.reader(io.StringIO(metin), delimiter=ayirici), 1):
        hucre = [h.strip() for h in satir] + ["", "", "", ""]
        if not any(hucre):
            continue
        if no == 1 and not _ip_mi(hucre[1]) and not _ip_mi(hucre[0]):
            continue  # başlık
        ad, ip = (hucre[0], hucre[1]) if not _ip_mi(hucre[0]) else (hucre[1], hucre[0])
        sonuc.append({"satir": no, "ip": ip, "port": "22", "etiket": ad or None,
                      "hesap": hucre[2] or None, "laboratuvar": hucre[3] or None})
    return sonuc


def ice_aktar_onizle(icerik: str, varsayilan_lab: str | None = None) -> dict:
    """Dosyayı ayrıştırır; hiçbir kayıt eklemez. Her satır için durum döndürür."""
    icerik = icerik.lstrip("﻿")
    bicim = "ansible" if (re.search(r"^\s*\[", icerik, re.M) or "ansible_host" in icerik) else "csv"
    satirlar = _ini_ayristir(icerik) if bicim == "ansible" else _csv_ayristir(icerik)
    if len(satirlar) > EN_FAZLA_ICE_AKTARMA:
        raise EnvanterHatasi(f"Dosyada {len(satirlar)} kayıt var (sınır {EN_FAZLA_ICE_AKTARMA})")
    goruldu = set()
    for s in satirlar:
        s["laboratuvar"] = s["laboratuvar"] or varsayilan_lab or "Laboratuvar"
        try:
            ip, port = _adres(s["ip"], s["port"])
            s["ip"], s["port"] = ip, port
            hesap = hesap_dogrula(s["hesap"])
            _metin(s["etiket"], "Görünen ad")
            _metin(s["laboratuvar"], "Laboratuvar")
        except EnvanterHatasi as hata:
            s["durum"], s["neden"] = "gecersiz", str(hata)
            continue
        if (ip, port) in goruldu:
            s["durum"], s["neden"] = "yinelenen", "dosyada ikinci kez geçiyor"
        elif veritabani.tek("SELECT id FROM cihaz WHERE ip=? AND ssh_port=?", (ip, port)):
            s["durum"], s["neden"] = "var", "zaten envanterde"
        else:
            s["durum"] = "eklenecek"
            s["neden"] = (None if hesap in (None, *ayarlar.YONETIM_HESAPLARI)
                          else f"yönetim hesabı pardus/hp değil ({hesap})")
        goruldu.add((ip, port))
    return {"bicim": bicim, "satirlar": satirlar,
            "eklenecek": sum(1 for s in satirlar if s["durum"] == "eklenecek")}


def ice_aktar(icerik: str, varsayilan_lab: str | None = None) -> dict:
    """Önizlemede "eklenecek" olan satırları ekler (bağlantı kurmaz)."""
    onizleme = ice_aktar_onizle(icerik, varsayilan_lab)
    eklenen = 0
    for s in onizleme["satirlar"]:
        if s["durum"] != "eklenecek":
            continue
        cihaz_ekle(s["ip"], s["port"], s["etiket"], s["laboratuvar"], s["hesap"])
        eklenen += 1
    return {"eklenen": eklenen, "atlanan": len(onizleme["satirlar"]) - eklenen}


# ---------------------------------------------------------------- Ansible dışa aktarımı

def _grup_adi(metin: str) -> str:
    ad = re.sub(r"[^A-Za-z0-9_]", "_", metin.strip().lower()
                .translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))) or "laboratuvar"
    return ad if not ad[0].isdigit() else "lab_" + ad


def ansible_envanteri() -> str:
    """Parolasız Ansible envanteri (karar 12, 21): yalnız hazır cihazlar, laboratuvara
    göre gruplu. Korunan (EBA/ETAP) cihazlar dahil edilmez."""
    gruplar: dict[str, list[str]] = {}
    for c in veritabani.cihazlar():
        if c["anahtar_durumu"] != "ok" or c["korunan"] or not c["baglanti_hesabi"]:
            continue
        ad = re.sub(r"[^A-Za-z0-9_.-]", "_", c["etiket"] or c["hostname"] or c["ip"])
        gruplar.setdefault(_grup_adi(c["grup"] or "Laboratuvar"), []).append(
            f"{ad} ansible_host={c['ip']} ansible_port={c['ssh_port']} "
            f"ansible_user={c['baglanti_hesabi']}")
    satirlar = ["# Pardus Sınıf Yönetimi — Ansible envanteri (parola içermez).",
                "# Yönetim hesaplarında parolasız sudo vardır (root eşdeğeri; karar 22).", ""]
    for grup, hostlar in sorted(gruplar.items()):
        satirlar += [f"[{grup}]", *hostlar, ""]
    satirlar += ["[laboratuvar:children]", *sorted(gruplar), "",
                 "[laboratuvar:vars]", "ansible_python_interpreter=/usr/bin/python3",
                 "ansible_become=true", "ansible_become_method=sudo", ""]
    return "\n".join(satirlar)


# ---------------------------------------------------------------- çıkarma

async def cikar_isi(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    """Önce hedefteki uygulama anahtarını kaldırır, başarılıysa kaydı siler."""
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    acik_satir = anahtar.acik_anahtar_satiri()

    async def _tek(cihaz_id: str):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "iptal",
                                      "Kullanıcı iptal etti")
            return
        async with sinir:
            await asyncio.to_thread(_cikar, is_id, cihaz, acik_satir)

    await asyncio.gather(*(_tek(cid) for cid in cihaz_idler))


def _cikar(is_id: str, cihaz: dict, acik_satir: str) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    if cihaz["anahtar_durumu"] != "ok":
        veritabani.cihaz_sil(cihaz["id"])
        veritabani.hedef_guncelle(is_id, ip, "basarili", "tamam",
                                  f"{ad} — anahtar kurulu değildi; envanterden çıkarıldı")
        return
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "anahtar",
                              f"{ad} — uygulama anahtarı kaldırılıyor")
    try:
        istemci = ssh_araclari.anahtar_ile_baglan(
            ip, cihaz["ssh_port"], cihaz["baglanti_hesabi"], anahtar.ozel_anahtar_yolu(),
            cihaz["anahtar_tipi"], cihaz["anahtar_b64"])
    except Exception as hata:
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz", "baglanti",
            f"{ad} — bağlanılamadı ({hata}); anahtar kaldırılamadığı için kayıt korundu. "
            f"Bilgisayar kapalıysa açıp yeniden deneyin ya da yalnızca listeden çıkarın")
        return
    try:
        sonuc = ssh_araclari.anahtar_sil(istemci, acik_satir)
    finally:
        istemci.close()
    if sonuc not in ("SILINDI", "YOK"):
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "anahtar",
                                  f"{ad} — anahtar kaldırılamadı: {sonuc}; kayıt korundu")
        return
    veritabani.cihaz_sil(cihaz["id"])
    veritabani.hedef_guncelle(
        is_id, ip, "basarili", "tamam",
        f"{ad} — uygulama anahtarı {cihaz['baglanti_hesabi']} hesabından kaldırıldı; "
        f"envanterden çıkarıldı" if sonuc == "SILINDI"
        else f"{ad} — anahtar zaten yoktu; envanterden çıkarıldı")
