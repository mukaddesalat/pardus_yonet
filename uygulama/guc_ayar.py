"""M2-S4 uyku/ekran koruyucu ayarı ve M2-S5 Zamanlı Kapatma (karar 32–33).

- Uyku ayarı: öğrenci bilgisayarları boşta UYKUYA GEÇMEZ ve KAPANMAZ; yalnız ekran kararır
  (ekran koruyucu süresi seçilebilir). Böylece güç ayarı yüzünden erişilemez olmazlar.
  Uyku hedefleri maskelenir (oturum ve giriş ekranı dahil her yerde geçerli), GNOME güç
  ayarları dconf'ta kilitlenir. "Varsayılana dön" yalnız bu uygulamanın yaptıklarını geri alır.
- Zamanlı kapatma: Linux `at` (bir kez) ve `cron` (her hafta) benzeri planlar; öğrenci
  PC'de systemd zamanlayıcısı olarak kurulur (Persistent=false: kapalıyken kaçan kapatma
  açılışta uygulanmaz). Zamanı gelince öğrencilere uyarı gösterilir; uyarı süresi sonunda
  kapanır; bekleyen kapatma öğretmen tarafından iptal edilebilir.
"""

import asyncio
import re
import secrets
from datetime import datetime

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

GUNLER = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
GUN_ADLARI = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
SAAT_DESENI = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
TARIH_DESENI = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EKRAN_SURELERI = (0, 5, 10, 15, 30, 60)
UYARI_SURELERI = (0, 1, 2, 5, 10, 15)


class GucHatasi(ValueError):
    """Öğretmene olduğu gibi gösterilir."""


def _gun_etiketi(gunler: list[str]) -> str:
    """["Mon".."Fri"] → "Pzt–Cum"; ardışık olmayanlar virgülle."""
    sira = sorted(GUNLER.index(g) for g in gunler)
    if len(sira) == 7:
        return "Her gün"
    gruplar = [[sira[0]]]
    for g in sira[1:]:
        if g == gruplar[-1][-1] + 1:
            gruplar[-1].append(g)
        else:
            gruplar.append([g])
    parcalar = []
    for grup in gruplar:
        if len(grup) >= 3:
            parcalar.append(f"{GUN_ADLARI[grup[0]]}–{GUN_ADLARI[grup[-1]]}")
        else:
            parcalar += [GUN_ADLARI[g] for g in grup]
    return ", ".join(parcalar)


def takvim_olustur(tur: str, saat: str, tarih: str | None = None, gunler: list[str] | None = None,
                   simdi: datetime | None = None) -> tuple[str, str]:
    """(systemd OnCalendar ifadesi, öğretmene gösterilecek etiket)."""
    if not SAAT_DESENI.match(saat or ""):
        raise GucHatasi("Saat SS:DD biçiminde olmalı (ör. 17:30)")
    if tur == "tek":
        if not TARIH_DESENI.match(tarih or ""):
            raise GucHatasi("Tarih seçin")
        try:
            zaman = datetime.strptime(f"{tarih} {saat}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise GucHatasi("Geçersiz tarih")
        if zaman <= (simdi or datetime.now()):
            raise GucHatasi("Geçmiş bir zaman seçilemez")
        return f"{tarih} {saat}:00", f"{zaman:%d.%m.%Y} {saat} (bir kez)"
    if tur == "surekli":
        gunler = [g for g in GUNLER if g in set(gunler or [])]
        if not gunler:
            raise GucHatasi("En az bir gün seçin")
        on_ek = "" if len(gunler) == 7 else ",".join(gunler) + " "
        return f"{on_ek}*-*-* {saat}:00", f"{_gun_etiketi(gunler)} {saat} (her hafta)"
    raise GucHatasi("Plan türü 'bir kez' veya 'her hafta' olmalı")


def plan_olustur(tur: str, saat: str, tarih: str | None, gunler: list[str] | None, uyari_dk: int,
                 aciklama: str = "") -> dict:
    if uyari_dk not in UYARI_SURELERI:
        raise GucHatasi("Uyarı süresi geçersiz")
    takvim, etiket = takvim_olustur(tur, saat, tarih, gunler)
    temiz = re.sub(r"[\x00-\x1f]", " ", aciklama or "").strip()[:80]
    return {"id": secrets.token_hex(3), "tur": tur, "takvim": takvim, "etiket": etiket,
            "uyari_dk": uyari_dk, "aciklama": temiz}


# ---------------------------------------------------------------- envanter

def envanter_alani(d: dict) -> dict:
    """Uzak durum → cihaz.guc_durumu (M1-S1 kutucuğu, M2-S4/S5 tabloları)."""
    u = d.get("uyku") or {}
    return {"guc_durumu": {
        "uyku_kapali": u.get("kapali"), "ekran_dk": u.get("ekran_dk"), "bekleyen": d.get("bekleyen"),
        "bekleyen_saat": d.get("bekleyen_saat"),
        "planlar": [{"id": p.get("id"), "etiket": p.get("etiket") or p.get("takvim"), "tur": p.get("tur"),
                     "uyari_dk": p.get("uyari_dk"), "sonraki": p.get("sonraki"), "etkin": p.get("etkin"),
                     "aciklama": p.get("aciklama")} for p in d.get("planlar") or []],
        "zaman": veritabani.simdi()}}


def _ozet(d: dict) -> str:
    u = d.get("uyku") or {}
    parca = ["uyku KAPALI" if u.get("kapali") else "uyku AÇIK (bilgisayar boşta uykuya geçebilir)"]
    if u.get("ekran_dk") is not None:
        parca.append(f"ekran koruyucu {u['ekran_dk']} dk" if u["ekran_dk"] else "ekran koruyucu kapalı")
    planlar = d.get("planlar") or []
    parca.append(f"{len(planlar)} kapatma planı" + (": " + ", ".join(p.get("etiket") or p.get("takvim", "?")
                                                                    for p in planlar) if planlar else ""))
    if d.get("bekleyen"):
        parca.append("BEKLEYEN KAPATMA VAR" + (f" (kapanma {d['bekleyen_saat']})" if d.get("bekleyen_saat") else ""))
    return "; ".join(parca)


# ---------------------------------------------------------------- işler

async def _is(is_id: str, cihaz_idler: list[str], iptal: asyncio.Event, tek, *ek) -> None:
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz:
            return
        ad = veritabani.cihaz_adi(cihaz)
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "iptal", f"{ad} — kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "guc")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam", f"{ad} — {neden}",
                                      {"cihaz_id": cid, "ad": ad})
            return
        async with sinir:
            await asyncio.to_thread(_calistir, is_id, cihaz, tek, *ek)

    await asyncio.gather(*(_tek(c) for c in dict.fromkeys(cihaz_idler)))


def _calistir(is_id: str, cihaz: dict, tek, *ek) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.cihaz_guncelle(cihaz["id"], erisim=0, erisim_zamani=veritabani.simdi())
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}", veri)
        return
    try:
        durum, asama, mesaj, ek_veri = tek(istemci, *ek)
        d = ek_veri.get("durum_sonra")
        if d:
            veritabani.cihaz_guncelle(cihaz["id"], erisim=1, erisim_zamani=veritabani.simdi(), **envanter_alani(d))
        veritabani.hedef_guncelle(is_id, ip, durum, asama, f"{ad} — {mesaj}", {**veri, **ek_veri})
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "guc", f"{ad} — {hata}", veri)
    finally:
        istemci.close()


def _betik(istemci, parametre: dict, zaman: int = 120) -> dict:
    sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("guc_ayar"), parametre, zaman=zaman)
    if "hata" in sonuc:
        raise RuntimeError(sonuc["hata"])
    return sonuc


def _uyku(istemci, islem: str, ekran_dk: int):
    s = _betik(istemci, {"kip": "uyku", "islem": islem, "ekran_dk": ekran_dk})
    if islem == "onizle":
        once = s["once"]
        ne = (f"{len(s['maskelenecek'])} uyku hedefi kapatılacak, " if s["maskelenecek"] else "uyku zaten kapalı, ")
        ne += f"ekran koruyucu {ekran_dk} dk olacak" if ekran_dk else "ekran koruyucu kapatılacak"
        if s.get("gdm"):
            ne += "; giriş ekranı da boşta uyumayacak"
        return "basarili", "onizleme", f"şu an: {_ozet(once)} → {ne}", {"durum_sonra": once, "onizleme": s}
    sonra = s["sonra"]
    metin = "; ".join(s["adimlar"]) + (" | HATA: " + "; ".join(s["hatalar"]) if s["hatalar"] else "")
    return ("basarisiz" if s["hatalar"] else "basarili"), "tamam", metin, {"durum_sonra": sonra, "sonuc": s}


async def uyku_isi(is_id, cihaz_idler, islem: str, ekran_dk: int, iptal):
    await _is(is_id, cihaz_idler, iptal, _uyku, islem, ekran_dk)


def _oku(istemci):
    # Planlar varsa hedefteki yardımcı betik bu sürümünkiyle yenilenir (uygulama güncellenince eski kalmasın)
    d = _betik(istemci, {"kip": "durum", "yardimci_yenile": True}, 60)
    ek = "; kapatma yardımcısı güncellendi" if d.get("yardimci_yenilendi") else ""
    return "basarili", "tamam", _ozet(d) + ek, {"durum_sonra": d}


async def oku_isi(is_id, cihaz_idler, iptal):
    await _is(is_id, cihaz_idler, iptal, _oku)


def _ekle(istemci, plan: dict):
    s = _betik(istemci, {"kip": "kapatma_ekle", **plan})
    d = _betik(istemci, {"kip": "durum"}, 60)
    return "basarili", "tamam", f"plan eklendi: {plan['etiket']}; sonraki kapanma: {s.get('sonraki')}", \
        {"durum_sonra": d, "plan": plan}


async def ekle_isi(is_id, cihaz_idler, plan: dict, iptal):
    await _is(is_id, cihaz_idler, iptal, _ekle, plan)


def _sil(istemci, idler):
    s = _betik(istemci, {"kip": "kapatma_sil", "idler": idler})
    d = _betik(istemci, {"kip": "durum"}, 60)
    metin = (f"{len(s['silinen'])} plan kaldırıldı" if s["silinen"] else "kaldırılacak plan yoktu")
    return "basarili", "tamam", metin + f"; kalan: {len(s['planlar'])}", {"durum_sonra": d}


async def sil_isi(is_id, cihaz_idler, idler, iptal):
    await _is(is_id, cihaz_idler, iptal, _sil, idler)


def _iptal(istemci):
    s = _betik(istemci, {"kip": "kapatma_iptal"})
    d = _betik(istemci, {"kip": "durum"}, 60)
    if not s["bekleyen_vardi"]:
        return "basarili", "tamam", "bekleyen kapatma yoktu", {"durum_sonra": d}
    if s["iptal_edildi"]:
        bildirim = f"; {s['bildirilen']} masaüstüne bildirildi" if s.get("bildirilen") else ""
        return "basarili", "tamam", "bekleyen kapatma iptal edildi" + bildirim, {"durum_sonra": d}
    return "basarisiz", "iptal", "bekleyen kapatma iptal edilemedi", {"durum_sonra": d}


async def iptal_isi(is_id, cihaz_idler, iptal):
    await _is(is_id, cihaz_idler, iptal, _iptal)
