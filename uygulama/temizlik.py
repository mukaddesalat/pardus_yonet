"""Ders sonu temizliği: alan seçimi, güvenli önizleme ve kurtarılabilir karantina (istem §9).

Öğretmen temizlenecek alanları onay kutularıyla seçer. Genel seçim tüm seçili
bilgisayarlara uygulanır ve bir sonraki temizlik için hatırlanır; bilgisayar
bazında istisna yalnızca o temizlik için geçerlidir ve kaydedilmez (proje
sahibi kararı, 26 Eyl 2026).

Asıl iş öğrenci PC'de root olarak çalışan uzak/temizlik.py betiğindedir; tüm yol
çözümleme ve güvenlik kontrolleri hedefte, işlemden hemen önce yeniden yapılır.
"""

import asyncio
import json

from . import ayarlar, secim, ssh_araclari, uzak, veritabani, yonetim

# Sunucu tarafı izin listesi; uzak betik aynı adları tanır.
# ad -> (arayüz etiketi, tablo başlığı için kısa etiket)
ALANLAR = {
    "masaustu": ("Masaüstü", "Masaüstü"),
    "indirilenler": ("İndirilenler", "İndirilenler"),
    "cop": ("Çöp kutusu", "Çöp"),
    "belgeler": ("Belgeler", "Belgeler"),
    "resimler": ("Resimler", "Resimler"),
    "muzik": ("Müzik", "Müzik"),
    "videolar": ("Videolar", "Videolar"),
    "tarayici": ("Tarayıcı geçmişi ve çerezleri", "Tarayıcı"),
    "son_dosyalar": ("Son açılan dosyalar listesi", "Son dosyalar"),
}
VARSAYILAN_ALANLAR = ["masaustu", "indirilenler", "cop"]


def alanlari_dogrula(alanlar: list[str]) -> list[str]:
    """İzin listesi dışı alanı reddeder; sırayı katalog sırasına getirir."""
    bilinmeyen = [a for a in alanlar if a not in ALANLAR]
    if bilinmeyen:
        raise ValueError(f"Bilinmeyen temizlik alanı: {', '.join(bilinmeyen)}")
    return [a for a in ALANLAR if a in set(alanlar)]


def genel_alanlar() -> list[str]:
    kayit = veritabani.ayar_oku("temizlik_genel_alanlar")
    if kayit:
        try:
            return alanlari_dogrula(json.loads(kayit))
        except (ValueError, TypeError):
            pass
    return list(VARSAYILAN_ALANLAR)


def genel_alanlari_kaydet(alanlar: list[str]) -> None:
    veritabani.ayar_yaz("temizlik_genel_alanlar", json.dumps(alanlari_dogrula(alanlar)))


def katalog() -> list[dict]:
    return [{"ad": ad, "etiket": etiket, "kisa": kisa}
            for ad, (etiket, kisa) in ALANLAR.items()]


def plan_olustur(cihaz_idler: list[str], genel: list[str],
                 istisnalar: dict[str, list[str]]) -> dict[str, list[str]]:
    """Her bilgisayar için temizlenecek alan listesi: istisna varsa o, yoksa genel."""
    genel = alanlari_dogrula(genel)
    yabanci = set(istisnalar) - set(cihaz_idler)
    if yabanci:
        raise ValueError("İstisna, seçili olmayan bir bilgisayar için verilmiş")
    return {cid: alanlari_dogrula(istisnalar[cid]) if cid in istisnalar else genel
            for cid in cihaz_idler}


def _mb(bayt: int) -> str:
    return f"{bayt / 1048576:.1f} MB"


async def temizlik_isi(is_id: str, plan: dict[str, list[str]], mod: str,
                       iptal: asyncio.Event) -> None:
    """mod: 'onizleme' (salt okunur ölçüm) veya 'temizle' (karantinaya taşıma)."""
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    saklama = veritabani.saklama_adedi()

    async def _tek(cihaz_id: str, alanlar: list[str]):
        cihaz = veritabani.cihaz(cihaz_id)
        if not cihaz:
            return
        ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
        veri = {"cihaz_id": cihaz_id, "ad": ad, "alanlar": alanlar}
        if iptal.is_set():
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "iptal", "Kullanıcı iptal etti", veri)
            return
        if not alanlar:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "secim",
                                      f"{ad} — temizlenecek alan seçilmedi",
                                      {**veri, "neden": "Alan seçilmedi"})
            return
        neden = secim.uygunluk(cihaz, "temizlik")
        if neden:
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "kapsam", f"{ad} — {neden}",
                                      {**veri, "neden": neden})
            return
        async with sinir:
            await asyncio.to_thread(_calistir, is_id, cihaz, mod, alanlar, saklama)

    await asyncio.gather(*(_tek(cid, alanlar) for cid, alanlar in plan.items()))


def _calistir(is_id: str, cihaz: dict, mod: str, alanlar: list[str], saklama: int) -> None:
    ip = cihaz["ip"]
    ad = veritabani.cihaz_adi(cihaz)
    asama = "önizleme" if mod == "onizleme" else "temizlik"
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "alanlar": alanlar}
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", asama, f"{ad} — {asama} için bağlanılıyor", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti",
                                  f"{ad} — bağlantı kurulamadı: {hata}",
                                  {**veri, "neden": "Erişilemiyor"})
        return

    try:
        # Aktif oturum bilgisi her iki modda da rapora eklenir (istem §9.5)
        oturumlar = ssh_araclari.aktif_oturumlar(istemci)
        veri["oturum_acik"] = ayarlar.PROFIL_HESABI in oturumlar
        try:
            sonuc = ssh_araclari.sudo_betik(
                istemci, uzak.betik("temizlik"),
                {"hesap": ayarlar.PROFIL_HESABI, "mod": mod, "alanlar": alanlar,
                 "saklama": saklama}, zaman=300)
        except (RuntimeError, ssh_araclari.SudoHatasi) as hata:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", asama, f"{ad} — {hata}",
                                      {**veri, "neden": str(hata)})
            return
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", asama, f"{ad} — {sonuc['hata']}",
                                      {**veri, "neden": sonuc["hata"]})
            return
        veri["sonuc"] = sonuc
        olcum = sonuc.get("olcum") or {}
        if mod == "temizle" and olcum.get("ev_bos") is not None and olcum.get("ev_bos_sonra") is not None:
            veri["gerceklesen"] = olcum["ev_bos_sonra"] - olcum["ev_bos"]

        parcalar = []
        for alan_adi, bilgi in sonuc.get("alanlar", {}).items():
            etiket = ALANLAR.get(alan_adi, (alan_adi,))[0]
            if "atlandi" in bilgi:
                parcalar.append(f"{etiket}: ATLANDI ({bilgi['atlandi']})")
            elif mod == "onizleme":
                parcalar.append(f"{etiket}: {bilgi['adet']} öğe, {_mb(bilgi['bayt'])}")
            else:
                parcalar.append(f"{etiket}: {bilgi.get('tasinan', 0)} öğe taşındı"
                                + (f", {bilgi['hatali']} hata" if bilgi.get("hatali") else ""))
        oturum_notu = (f" | UYARI: {ayarlar.PROFIL_HESABI} oturumu açık; kaydedilmemiş "
                       f"veriler kaybolabilir" if veri["oturum_acik"] else "")
        ek = ""
        if mod == "temizle":
            ek = (" | karantinaya alındı; M2-S1 “Yedekten dön” ile geri alınabilir"
                  if sonuc.get("karantina") else " | taşınacak dosya yoktu")
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — {'; '.join(parcalar) or 'temizlenecek alan yok'}{ek}{oturum_notu}", veri)
        veritabani.cihaz_guncelle(cihaz["id"], son_kontrol=veritabani.simdi(),
                                  ogrenci_oturumu=1 if veri["oturum_acik"] else 0)
    finally:
        istemci.close()


# ---- profil sıfırlama önizlemesi (ölçüm; hiçbir şey değişmez) ----

async def sifirlama_olcum_isi(is_id: str, cihaz_idler: list[str], kapsam: str,
                              iptal: asyncio.Event) -> None:
    sinir = asyncio.Semaphore(ayarlar.DOGRULAMA_PARALELLIGI)
    saklama = veritabani.saklama_adedi()

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz or iptal.is_set():
            return
        ad = veritabani.cihaz_adi(cihaz)
        neden = secim.uygunluk(cihaz, "temizlik")
        if neden:
            veritabani.hedef_guncelle(is_id, cihaz["ip"], "atlandi", "kapsam", f"{ad} — {neden}",
                                      {"cihaz_id": cid, "ad": ad, "neden": neden})
            return
        async with sinir:
            await asyncio.to_thread(_sifirlama_olc, is_id, cihaz, kapsam, saklama)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _sifirlama_olc(is_id: str, cihaz: dict, kapsam: str, saklama: int) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "kapsam": kapsam}
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}",
                                  {**veri, "neden": "Erişilemiyor"})
        return
    try:
        veri["oturum_acik"] = ayarlar.PROFIL_HESABI in ssh_araclari.aktif_oturumlar(istemci)
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("yedek"),
            {"mod": "olc", "hesap": ayarlar.PROFIL_HESABI, "kapsam": kapsam, "saklama": saklama},
            zaman=300)
        if "hata" in sonuc:
            raise RuntimeError(sonuc["hata"])
        veri["sonuc"] = sonuc
        yedek = sonuc["yedek"]
        uyarilar = []
        if veri["oturum_acik"]:
            uyarilar.append("öğrenci oturumu açık — kapatılmadan sıfırlama başlamaz")
        if not yedek["yeterli"]:
            uyarilar.append("yedek için boş alan yetersiz — sıfırlama yapılamaz")
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — silinecek: {sonuc['silinecek']['adet']} öğe, "
            f"{_mb(sonuc['silinecek']['ayrilmis'])}; yedek için gereken boş alan: "
            f"{_mb(yedek['gerekli_bos'])} (var: {_mb(yedek['bos'])})"
            + (" | UYARI: " + "; ".join(uyarilar) if uyarilar else ""), veri)
    except (RuntimeError, ssh_araclari.SudoHatasi) as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "olcum", f"{ad} — {hata}",
                                  {**veri, "neden": str(hata)})
    finally:
        istemci.close()
