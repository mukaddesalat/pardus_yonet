"""M2-S2 Paket Kurulumu: öğretmenin yerel .deb paketini seçili bilgisayarlara kurma (karar 24).

Akış: dosyayı yükle (yapı doğrulanır) → hedefleri seç → planı hazırla (aktarım +
SHA-256 + Pardus sürümü, mimari, boş alan, paket yöneticisi kilidi, kurulu sürüm,
apt benzetimi, depo erişimi) → öğretmen planı onaylar → kur → kurulu sürümü doğrula.

- Bu yetki, öğretmenin kendi yüklediği dosyaya özeldir: paketler yalnız yönetim
  arayüzünden (127.0.0.1) yüklenir ve yönetim veri dizininde tutulur. API dosya
  yolu kabul etmez; öğrenci ödev portalına yüklenen dosyalar (ayrı servis, ayrı
  kullanıcı, erişilemez dizin) bu akışa giremez.
- Paket kaldırma, sürüm düşürme ve çözülemeyen bağımlılık planı engeller; aynı
  sürüm zaten kuruluysa yeniden kurulmaz. Sudo parolası sorulmaz (karar 22).
"""

import asyncio
import hashlib
import json
import os

from . import ayarlar, debpaket, secim, ssh_araclari, uzak, veritabani, yonetim

ONBELLEK = "/var/cache/pardus-sinif-yonetimi"


def paket_dizini():
    d = ayarlar.veri_yollari()["paket_dizini"]
    d.mkdir(parents=True, exist_ok=True)
    try:
        # Paket dizini izinleri (sahip kısıtlı)
        os.chmod(d, 0o700)  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
    except OSError:
        pass
    return d


async def yukle(akis, dosya_adi: str, tur: str = "genel") -> dict:
    """Tarayıcıdan gelen gövdeyi diske akıtır, doğrular ve kaydeder.

    tur='veyon' (M1-S4) yalnız Veyon paketini kabul eder; tur='genel' (M2-S2) Veyon
    paketini reddedip Veyon sayfasına yönlendirir. İki liste birbirinden ayrıdır.
    """
    from . import veyon  # döngüsel içe aktarma
    dizin = paket_dizini()
    gecici = dizin / f".yukleniyor-{os.getpid()}-{id(akis)}"
    sha = hashlib.sha256()
    boyut = 0
    try:
        with open(gecici, "wb") as f:
            async for parca in akis:
                boyut += len(parca)
                if boyut > ayarlar.EN_BUYUK_PAKET:
                    raise debpaket.PaketHatasi("Paket 1 GB sınırını aşıyor")
                sha.update(parca)
                f.write(parca)
        if boyut == 0:
            raise debpaket.PaketHatasi("Boş dosya")
        bilgi = await asyncio.to_thread(debpaket.incele, str(gecici))
        if tur == "veyon":
            veyon.paket_dogrula(bilgi)
        elif veyon.veyon_paketi_mi(bilgi):
            raise debpaket.PaketHatasi(
                "Bu bir Veyon paketi. Veyon, M1-S4 “Veyon Ayarları” sayfasındaki “Veyon paketi” alanından "
                "yüklenir; kurulum ve yapılandırma da oradan yapılır.")
        ozet = sha.hexdigest()
        hedef = dizin / f"{ozet}.deb"
        os.replace(gecici, hedef)
    finally:
        if gecici.exists():
            gecici.unlink()
    ad = os.path.basename(dosya_adi or "paket.deb")[:120]
    veritabani.calistir(
        "INSERT INTO paket(sha256, dosya_adi, paket, surum, mimari, boyut, kurulu_kb, kontrol, zaman, tur) "
        "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(sha256) DO UPDATE SET dosya_adi=excluded.dosya_adi, "
        "zaman=excluded.zaman, tur=excluded.tur",
        (ozet, ad, bilgi["paket"], bilgi["surum"], bilgi["mimari"], boyut, bilgi["kurulu_kb"],
         json.dumps(bilgi["kontrol"], ensure_ascii=False), veritabani.simdi(), tur))
    return paket_bilgisi(ozet)


def paket_bilgisi(sha: str) -> dict | None:
    s = veritabani.tek("SELECT * FROM paket WHERE sha256=?", (sha,))
    if not s:
        return None
    p = dict(s)
    p["kontrol"] = json.loads(p["kontrol"])
    return p


def paketler(tur: str = "genel") -> list[dict]:
    return [paket_bilgisi(s["sha256"]) for s in
            veritabani.sorgula("SELECT sha256 FROM paket WHERE tur=? ORDER BY zaman DESC", (tur,))]


def paket_sil(sha: str) -> bool:
    from . import veyon  # döngüsel içe aktarma
    if not paket_bilgisi(sha):
        return False
    yol = paket_dizini() / f"{sha}.deb"
    if yol.exists():
        yol.unlink()
    veritabani.calistir("DELETE FROM paket WHERE sha256=?", (sha,))
    veyon.paket_silindi(sha)
    return True


# ---------------------------------------------------------------- uzak adımlar

def _aktar(istemci, paket: dict) -> None:
    """Paket hedefte yoksa özel geçici klasöre gönderir; root'a ait önbelleğe alır."""
    hedef = f"{ONBELLEK}/{paket['sha256']}.deb"
    rc, _, _ = ssh_araclari.sudo_komut(istemci, ["test", "-f", hedef])
    if rc == 0:
        return
    rc, klasor, hata = ssh_araclari.komut(istemci, ["mktemp", "-d", "/tmp/psy-paket-XXXXXXXX"])
    klasor = klasor.strip()
    if rc != 0 or not klasor.startswith("/tmp/psy-paket-"):
        raise RuntimeError(f"geçici klasör oluşturulamadı: {hata.strip()}")
    sftp = istemci.open_sftp()
    try:
        sftp.put(str(paket_dizini() / f"{paket['sha256']}.deb"), f"{klasor}/paket.deb")
    finally:
        sftp.close()
    sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("paket"),
                                    {"kip": "al", "kaynak": f"{klasor}/paket.deb",
                                     "sha256": paket["sha256"]}, zaman=300)
    if "hata" in sonuc:
        ssh_araclari.komut(istemci, ["rm", "-rf", "--", klasor])
        raise RuntimeError(sonuc["hata"])


def _parametre(paket: dict, kip: str) -> dict:
    return {"kip": kip, "sha256": paket["sha256"], "paket": paket["paket"],
            "surum": paket["surum"], "mimari": paket["mimari"],
            "kurulu_kb": paket["kurulu_kb"] or 0, "boyut": paket["boyut"]}


async def plan_isi(is_id: str, sha: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    paket = paket_bilgisi(sha)
    sinir = asyncio.Semaphore(ayarlar.PAKET_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or iptal.is_set():
            return
        neden = secim.uygunluk(cihaz, "paket")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}",
                                      {"cihaz_id": cid, "ad": veritabani.cihaz_adi(cihaz),
                                       "plan": {"durum": "kapsam_disi", "neden": neden}})
            return
        async with sinir:
            await asyncio.to_thread(_plan, is_id, cihaz, paket)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _plan(is_id: str, cihaz: dict, paket: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "aktarim", f"{ad} — paket aktarılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}",
                                  {**veri, "plan": {"durum": "hata", "neden": "bağlanılamadı"}})
        return
    try:
        _aktar(istemci, paket)
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "plan",
                                  f"{ad} — SHA-256 doğrulandı; denetleniyor", veri)
        plan = ssh_araclari.sudo_betik(istemci, uzak.betik("paket"), _parametre(paket, "plan"),
                                       zaman=400)
        if "hata" in plan:
            raise RuntimeError(plan["hata"])
        veri["plan"] = plan
        durum = plan["durum"]
        ozet = {"kurulacak": "kurulacak", "guncellenecek":
                f"güncellenecek ({plan.get('kurulu_surum')} → {paket['surum']})",
                "atlanacak": plan.get("neden", "atlanacak"),
                "engellendi": "ENGELLENDİ: " + "; ".join(plan.get("engeller", []))}[durum]
        ek = []
        if plan.get("apt"):
            bagimli = [y for y in plan["apt"]["yeni"] if y["paket"] != paket["paket"]]
            if bagimli:
                ek.append(f"{len(bagimli)} yeni bağımlılık")
        if plan.get("indirilecek"):
            ek.append(f"{plan['indirilecek']} dosya depodan indirilecek")
        ek += plan.get("uyarilar", [])
        veritabani.hedef_guncelle(
            is_id, ip, "basarisiz" if durum == "engellendi" else "basarili", "plan",
            f"{ad} — {ozet}" + (f" ({'; '.join(ek)})" if ek else ""), veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}",
                                  {**veri, "plan": {"durum": "hata", "neden": str(hata)}})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "plan", f"{ad} — {hata}",
                                  {**veri, "plan": {"durum": "hata", "neden": str(hata)}})
    finally:
        istemci.close()


def onaylanabilir_hedefler(plan_is_id: str, sha: str) -> list[str]:
    """Plan işinden yalnız "kurulacak/güncellenecek" çıkan cihazlar."""
    kayit = veritabani.is_durumu(plan_is_id)
    if not kayit or kayit["tip"] != "paket_plan" or kayit["parametreler"].get("sha256") != sha:
        return []
    return [h["veri"]["cihaz_id"] for h in kayit["hedefler"]
            if h.get("veri") and (h["veri"].get("plan") or {}).get("durum") in ("kurulacak", "guncellenecek")]


async def kur_isi(is_id: str, sha: str, cihaz_idler: list[str], iptal: asyncio.Event) -> None:
    paket = paket_bilgisi(sha)
    sinir = asyncio.Semaphore(ayarlar.PAKET_PARALELLIGI)

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz:
            return
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "iptal", "Kullanıcı iptal etti")
            return
        neden = secim.uygunluk(cihaz, "paket")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam",
                                      f"{veritabani.cihaz_adi(cihaz)} — {neden}")
            return
        async with sinir:
            await asyncio.to_thread(_kur, is_id, cihaz, paket)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _kur(is_id: str, cihaz: dict, paket: dict) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "baglanti", f"{ad} — bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}")
        return
    try:
        _aktar(istemci, paket)
        veritabani.hedef_guncelle(is_id, ip, "calisiyor", "kurulum",
                                  f"{ad} — {paket['paket']} {paket['surum']} kuruluyor", veri)
        sonuc = ssh_araclari.sudo_betik(istemci, uzak.betik("paket"), _parametre(paket, "kur"),
                                        zaman=2000)
        if "hata" in sonuc:
            raise RuntimeError(sonuc["hata"])
        veri["sonuc"] = sonuc
        if sonuc.get("durum") == "atlanacak":
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "tamam",
                                      f"{ad} — {sonuc.get('neden')}", veri)
        elif sonuc.get("kuruldu"):
            veritabani.hedef_guncelle(
                is_id, ip, "basarili", "tamam",
                f"{ad} — kuruldu ve doğrulandı: {paket['paket']} {sonuc['kurulu_surum']}", veri)
        elif sonuc.get("durum") == "engellendi":
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "denetim",
                                      f"{ad} — kurulmadı: " + "; ".join(sonuc.get("engeller", [])), veri)
        else:
            son = " | ".join(sonuc.get("kayit", [])[-3:])
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kurulum",
                                      f"{ad} — kurulum başarısız (apt rc={sonuc.get('rc')}): {son}", veri)
    except ssh_araclari.SudoHatasi as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "sudo", f"{ad} — {hata}", veri)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kurulum", f"{ad} — {hata}", veri)
    finally:
        istemci.close()

