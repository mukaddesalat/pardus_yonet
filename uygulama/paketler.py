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
            "kurulu_kb": paket["kurulu_kb"] or 0, "boyut": paket["boyut"],
            "yeniden_kur": True}


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


# ---------------------------------------------------------------- Pardus Yazılım Merkezi / Repo (APT)

import re
from .uzak import paket as uzak_paket

_PAKET_ADI_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,79}$")

REPO_KATALOG = [
    {
        "kategori": "Kodlama ve Robotik",
        "ikon": "💻",
        "uygulamalar": [
            {"paket": "thonny", "ad": "Thonny Python IDE", "ikon": "🐍",
             "aciklama": "Öğrenciler için adım adım hata ayıklamalı kolay Python geliştirme ortamı"},
            {"paket": "arduino", "ad": "Arduino IDE", "ikon": "🤖",
             "aciklama": "Robotik kodlama ve mikrodenetleyici kart programlama ortamı"},
            {"paket": "fritzing", "ad": "Fritzing", "ikon": "🔌",
             "aciklama": "Elektronik devre şeması ve breadboard prototipleme tasarımı"},
            {"paket": "geany", "ad": "Geany", "ikon": "📝",
             "aciklama": "Hızlı ve hafif C, C++, Python, HTML/JS kod düzenleyici"},
            {"paket": "codeblocks", "ad": "Code::Blocks", "ikon": "⚙️",
             "aciklama": "C ve C++ dersleri için tümleşik geliştirme ortamı (IDE)"},
            {"paket": "sqlitebrowser", "ad": "DB Browser for SQLite", "ikon": "🗄️",
             "aciklama": "Veritabanı dersleri için görsel SQLite tablo ve SQL sorgu aracı"},
            {"paket": "git", "ad": "Git", "ikon": "🌿",
             "aciklama": "Dağıtık sürüm kontrol ve proje takip sistemi"},
            {"paket": "python3-pip", "ad": "Python3 Pip", "ikon": "📦",
             "aciklama": "Python kütüphane ve paket kurulum yöneticisi"},
        ],
    },
    {
        "kategori": "Tasarım, Grafik ve Medya",
        "ikon": "🎨",
        "uygulamalar": [
            {"paket": "gimp", "ad": "GIMP", "ikon": "🖌️",
             "aciklama": "Profesyonel fotoğraf işleme ve görsel tasarım programı"},
            {"paket": "inkscape", "ad": "Inkscape", "ikon": "✒️",
             "aciklama": "Vektörel grafik, logo ve afiş tasarım uygulaması (SVG)"},
            {"paket": "krita", "ad": "Krita", "ikon": "🎨",
             "aciklama": "Dijital boyama, illüstrasyon ve 2B animasyon stüdyosu"},
            {"paket": "kolourpaint", "ad": "KolourPaint", "ikon": "🖼️",
             "aciklama": "Hızlı ve sade resim/çizim programı (MS Paint benzeri)"},
            {"paket": "blender", "ad": "Blender", "ikon": "🧊",
             "aciklama": "3B modelleme, animasyon, simülasyon ve render stüdyosu"},
            {"paket": "kdenlive", "ad": "Kdenlive", "ikon": "🎬",
             "aciklama": "Çok katmanlı video kurgu ve montaj programı"},
            {"paket": "audacity", "ad": "Audacity", "ikon": "🎙️",
             "aciklama": "Ses kaydetme, kesme ve efekt düzenleme stüdyosu"},
            {"paket": "vlc", "ad": "VLC Media Player", "ikon": "▶️",
             "aciklama": "Tüm video ve ses biçimlerini oynatan medya oynatıcı"},
        ],
    },
    {
        "kategori": "Ofis, Eğitim ve Bilim",
        "ikon": "📚",
        "uygulamalar": [
            {"paket": "libreoffice", "ad": "LibreOffice Tam Paket", "ikon": "📄",
             "aciklama": "Kelime işlemci (Writer), hesap tablosu (Calc) ve sunum (Impress)"},
            {"paket": "scratch", "ad": "Scratch", "ikon": "🐱",
             "aciklama": "Blok tabanlı algoritma, animasyon ve oyun geliştirme aracı"},
            {"paket": "geogebra", "ad": "GeoGebra", "ikon": "📐",
             "aciklama": "Etkileşimli geometri, cebir, tablo ve istatistik uygulaması"},
            {"paket": "stellarium", "ad": "Stellarium", "ikon": "🔭",
             "aciklama": "Gerçekçi 3B gökyüzü ve astronomi gözlem simülasyonu"},
            {"paket": "kalzium", "ad": "Kalzium", "ikon": "🧪",
             "aciklama": "Etkileşimli periyodik tablo ve kimya başvuru aracı"},
            {"paket": "gcompris-qt", "ad": "GCompris", "ikon": "🧩",
             "aciklama": "Zengin eğitsel algoritma, matematik ve bilim etkinlikleri"},
        ],
    },
    {
        "kategori": "İnternet ve Sistem Araçları",
        "ikon": "🛠️",
        "uygulamalar": [
            {"paket": "chromium", "ad": "Chromium Tarayıcı", "ikon": "🌐",
             "aciklama": "Hızlı ve modern açık kaynaklı web tarayıcısı"},
            {"paket": "firefox-esr", "ad": "Firefox ESR", "ikon": "🦊",
             "aciklama": "Pardus varsayılan uzun süreli destekli web tarayıcısı"},
            {"paket": "okular", "ad": "Okular PDF Okuyucu", "ikon": "📑",
             "aciklama": "Gelişmiş PDF, EPUB ve e-kitap görüntüleme ve işaretleme aracı"},
            {"paket": "filezilla", "ad": "FileZilla", "ikon": "📂",
             "aciklama": "Web sunucuları için görsel FTP / SFTP dosya aktarım istemcisi"},
            {"paket": "7zip", "ad": "7-Zip", "ikon": "🗜️",
             "aciklama": "7z, ZIP, RAR ve TAR arşiv sıkıştırma ve açma aracı"},
            {"paket": "htop", "ad": "htop", "ikon": "📊",
             "aciklama": "Renkli ve etkileşimli işlemci/bellek süreç izleyicisi"},
        ],
    },
]


def repo_katalog() -> dict:
    return {"kategoriler": REPO_KATALOG}


def paket_listesi_dogrula(paketler_ham: list[str], kaldirma_mi: bool = False) -> list[str]:
    temiz = []
    goruldu = set()
    for p in paketler_ham or []:
        for parca in re.split(r"[\s,;]+", (p or "").strip().lower()):
            if not parca or parca in goruldu:
                continue
            if not _PAKET_ADI_RE.match(parca):
                raise ValueError(f"Geçersiz paket adı: '{parca}'")
            if kaldirma_mi and uzak_paket.korumali_paket_mi(parca):
                raise ValueError(
                    f"'{parca}' kritik sistem veya masaüstü paketidir; güvenli çalışma için kaldırılmasına izin verilmez."
                )
            goruldu.add(parca)
            temiz.append(parca)
    if not temiz:
        raise ValueError("En az bir geçerli paket seçin veya yazın")
    if len(temiz) > 30:
        raise ValueError("Tek seferde en çok 30 paket seçilebilir")
    return temiz


def _referans_cihaz_bul(cihaz_id: str | None = None) -> dict:
    if cihaz_id:
        c = veritabani.cihaz(cihaz_id)
        if not c:
            raise ValueError("Seçilen bilgisayar envanterde bulunamadı")
        neden = secim.uygunluk(c, "paket")
        if neden:
            raise ValueError(f"{veritabani.cihaz_adi(c)} bu işlem için uygun değil: {neden}")
        return c
    for c in veritabani.cihazlar():
        if not secim.uygunluk(c, "paket"):
            return c
    raise ValueError("Depo sorgusu için yönetime hazır (SSH + parolasız sudo) en az bir bilgisayar gereklidir")


def repo_ara(sorgu: str, cihaz_id: str | None = None) -> dict:
    cihaz = _referans_cihaz_bul(cihaz_id)
    ad = veritabani.cihaz_adi(cihaz)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        raise ValueError(f"{ad} bilgisayarına bağlanılamadı: {hata}")
    try:
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("paket"),
            {"kip": "repo_ara", "sorgu": sorgu},
            zaman=90)
        if "hata" in sonuc:
            raise ValueError(sonuc["hata"])
        return {"cihaz_id": cihaz["id"], "cihaz_ad": ad, **sonuc}
    finally:
        istemci.close()


def kurulu_listele(cihaz_id: str, tum_paketler: bool = False) -> dict:
    cihaz = _referans_cihaz_bul(cihaz_id)
    ad = veritabani.cihaz_adi(cihaz)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        raise ValueError(f"{ad} bilgisayarına bağlanılamadı: {hata}")
    try:
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("paket"),
            {"kip": "kurulu_listele", "tum_paketler": tum_paketler},
            zaman=120)
        if "hata" in sonuc:
            raise ValueError(sonuc["hata"])
        return {"cihaz_id": cihaz["id"], "cihaz_ad": ad, "ip": cihaz["ip"], **sonuc}
    finally:
        istemci.close()


async def repo_kur_isi(is_id: str, paket_adlari: list[str], guncelle: bool,
                       cihaz_idler: list[str], iptal: asyncio.Event) -> None:
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
            await asyncio.to_thread(_repo_kur_tek, is_id, cihaz, paket_adlari, guncelle)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _repo_kur_tek(is_id: str, cihaz: dict, paket_adlari: list[str], guncelle: bool) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "paketler": paket_adlari}
    ozet_adlar = ", ".join(paket_adlari[:4]) + (f" (+{len(paket_adlari) - 4})" if len(paket_adlari) > 4 else "")
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "kurulum",
                              f"{ad} — depodan kuruluyor: {ozet_adlar}", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}", veri)
        return
    try:
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("paket"),
            {"kip": "repo_kur", "paketler": paket_adlari, "guncelle": guncelle},
            zaman=2000)
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kurulum",
                                      f"{ad} — {sonuc['hata']}", {**veri, "sonuc": sonuc})
            return
        kurulan = sonuc.get("kurulanlar") or {}
        detay = ", ".join(f"{k} ({v})" for k, v in kurulan.items())
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — kuruldu ve doğrulandı: {detay}",
            {**veri, "sonuc": sonuc})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kurulum", f"{ad} — {hata}", veri)
    finally:
        istemci.close()


async def repo_kaldir_isi(is_id: str, paket_adlari: list[str], artiklari_temizle: bool,
                          cihaz_idler: list[str], iptal: asyncio.Event) -> None:
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
            await asyncio.to_thread(_repo_kaldir_tek, is_id, cihaz, paket_adlari, artiklari_temizle)

    await asyncio.gather(*(_tek(c) for c in cihaz_idler))


def _repo_kaldir_tek(is_id: str, cihaz: dict, paket_adlari: list[str], artiklari_temizle: bool) -> None:
    ip, ad = cihaz["ip"], veritabani.cihaz_adi(cihaz)
    veri = {"cihaz_id": cihaz["id"], "ad": ad, "paketler": paket_adlari}
    ozet_adlar = ", ".join(paket_adlari[:4]) + (f" (+{len(paket_adlari) - 4})" if len(paket_adlari) > 4 else "")
    veritabani.hedef_guncelle(is_id, ip, "calisiyor", "kaldirma",
                              f"{ad} — kaldırılıyor: {ozet_adlar}", veri)
    try:
        istemci = yonetim.baglan(cihaz)
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "baglanti", f"{ad} — bağlanılamadı: {hata}", veri)
        return
    try:
        sonuc = ssh_araclari.sudo_betik(
            istemci, uzak.betik("paket"),
            {"kip": "repo_kaldir", "paketler": paket_adlari, "artiklari_temizle": artiklari_temizle},
            zaman=1000)
        if "hata" in sonuc:
            veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kaldirma",
                                      f"{ad} — {sonuc['hata']}", {**veri, "sonuc": sonuc})
            return
        if sonuc.get("durum") == "atlandi":
            veritabani.hedef_guncelle(is_id, ip, "atlandi", "tamam",
                                      f"{ad} — {sonuc.get('mesaj', 'zaten kurulu değil')}",
                                      {**veri, "sonuc": sonuc})
            return
        kaldirilan = ", ".join(sonuc.get("kaldirilanlar") or paket_adlari)
        veritabani.hedef_guncelle(
            is_id, ip, "basarili", "tamam",
            f"{ad} — güvenli şekilde kaldırıldı: {kaldirilan}",
            {**veri, "sonuc": sonuc})
    except Exception as hata:
        veritabani.hedef_guncelle(is_id, ip, "basarisiz", "kaldirma", f"{ad} — {hata}", veri)
    finally:
        istemci.close()


