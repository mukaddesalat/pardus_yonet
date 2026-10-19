"""Toplu seçim, işlem uygunluğu ve "gereken işlem" hesabı (karar 25).

Seçim tarayıcıda tutulur; sunucu her işte hedef listesini YENİDEN denetler:
korunan (EBA/ETAP) cihazlar ve öğretmen bilgisayarının kendisi hiçbir işe
girmez, hazır olmayan cihaz açık nedenle "atlandı" olur. İş başladığında hedef
listesi iş kaydına yazılır (anlık görüntü); sonradan değişen seçim çalışan işi
etkilemez.
"""

import asyncio

from . import ag, ayarlar, surum, veritabani

ISLEMLER = {
    "durum": "Durum kontrolü",
    "hazirlik": "SSH ve hesap hazırlığı",
    "tekillestirme": "Hesap tekilleştirme",
    "temizlik": "Profil temizliği",
    "oturum": "Öğrenci oturumunu kapatma",
    "paket": "Paket kurulumu",
    "veyon": "Veyon kurulum ve yapılandırma",
    "veyon_oku": "Veyon sürümü ve bağlantı denetimi",
    "gorunum": "Görünüm ve giriş",
    "guc": "Güç işlemleri",
    "sinif": "Sınıf yönetimi işlemleri",
    "komut": "Uzak SSH komutu gönderme",
    "cikar": "Envanterden çıkarma",
}


def _gnome_degil(cihaz: dict) -> bool:
    masa = cihaz.get("masaustu") or ""
    return bool(masa) and not masa.startswith("GNOME")


def uygunluk(cihaz: dict, islem: str) -> str | None:
    """None: işleme uygun. Metin: kapsam dışı bırakma nedeni (öğretmene gösterilir)."""
    if islem == "cikar":
        return None
    if cihaz.get("korunan"):
        return "Korunan cihaz (EBA/ETAP) — kapsam dışı"
    if ag.ogretmen_adresi_mi(cihaz["ip"]):
        return "Öğretmen bilgisayarının kendisi — kapsam dışı"
    if islem == "durum":
        return None
    if islem == "hazirlik":
        if not cihaz.get("parmak_izi"):
            return "Sunucu kimliği okunmadı (M1-S2-B1)"
        if not cihaz.get("parmak_izi_onay"):
            return "Sunucu kimliği onaylanmadı (M1-S2-B2)"
        return None
    if cihaz.get("anahtar_durumu") != "ok":
        return "SSH anahtarı kurulu değil (M1-S2)"
    if islem == "veyon_oku":
        return None  # salt okunur: parolasız sudo gerekmez
    if cihaz.get("sudo_durumu") != "parolasiz":
        return "Parolasız sudo hazır değil (M1-S2)"
    if islem == "tekillestirme":
        hesaplar = cihaz.get("yonetim_hesaplari")
        if hesaplar is None:
            return "Yönetim hesapları bilinmiyor — önce durumu kontrol edin"
        if len(hesaplar) < 2:
            return "Tek yönetim hesabı var; tekilleştirme gerekmez"
    if islem in ("temizlik", "oturum"):
        if cihaz.get("profil_var") == 0:
            return f"'{ayarlar.PROFIL_HESABI}' hesabı yok (M1-S2)"
        if cihaz.get("baglanti_hesabi") == ayarlar.PROFIL_HESABI:
            return "Yönetilen profil ile bağlantı hesabı aynı; reddedildi"
    if islem == "gorunum" and _gnome_degil(cihaz):
        return "Masaüstü GNOME değil — XFCE için ayrı geçiş planı ve onay gerekir"
    return None


def gereken_islem(cihaz: dict) -> dict | None:
    """Envanterde gösterilecek tek, öncelikli "sonraki adım" (None: hazır)."""
    if cihaz.get("korunan"):
        return {"metin": "Korunan cihaz — işlem yapılmaz", "sayfa": None}
    if ag.ogretmen_adresi_mi(cihaz["ip"]):
        return {"metin": "Öğretmen bilgisayarı — envanterden çıkarın", "sayfa": "M1-S1"}
    if not cihaz.get("parmak_izi"):
        return {"metin": "Sunucu kimliğini okuyun", "sayfa": "M1-S2"}
    if not cihaz.get("parmak_izi_onay"):
        return {"metin": "Sunucu kimliğini onaylayın", "sayfa": "M1-S2"}
    if cihaz.get("anahtar_durumu") != "ok":
        return {"metin": "SSH anahtarını kurun", "sayfa": "M1-S2"}
    if cihaz.get("sudo_durumu") != "parolasiz":
        return {"metin": "Parolasız sudo hazırlayın", "sayfa": "M1-S2"}
    if cihaz.get("profil_var") == 0:
        return {"metin": f"'{ayarlar.PROFIL_HESABI}' hesabı oluşturun", "sayfa": "M1-S2"}
    if len(cihaz.get("yonetim_hesaplari") or []) > 1:
        return {"metin": "hp/pardus hesaplarını tekilleştirin", "sayfa": "M1-S2"}
    if _gnome_degil(cihaz):
        return {"metin": "GNOME geçişi ayrı planlanmalı", "sayfa": None}
    if cihaz.get("gizleme_durumu") == "gorunur":
        return {"metin": "Yönetim hesabını giriş ekranında gizleyin", "sayfa": "M2-S3"}
    if not cihaz.get("son_kontrol"):
        return {"metin": "Durumu kontrol edin", "sayfa": "M1-S1"}
    return None


def veyon_gorunumu(cihaz: dict, hedef_surum: str | None = None) -> dict:
    """M1-S1 ve M1-S4'ün ortak Veyon sütunu. Erişilemeyen bilgisayar "kurulu değil"
    gösterilmez: son bilinen sürüm ve zamanı "eski bilgi" olarak verilir."""
    durum, zaman = cihaz.get("veyon_durumu"), cihaz.get("veyon_kontrol")
    erisilemiyor = cihaz.get("erisim") == 0 and (not zaman or (cihaz.get("erisim_zamani") or "") > zaman)
    if erisilemiyor:
        gosterim = "erisilemiyor"
    elif not durum:
        gosterim = "kontrol_edilmedi"
    else:
        gosterim = durum
    if gosterim == "kurulu":
        karsilastirma = surum.iliski(cihaz.get("veyon_surum"), hedef_surum) if hedef_surum else "kurulu"
    elif gosterim == "kurulu_degil":
        karsilastirma = "kurulu_degil"
    else:
        karsilastirma = "bilinmiyor"
    return {"durum": gosterim, "surum": cihaz.get("veyon_surum"), "son_bilinen": durum,
            "eski_bilgi": erisilemiyor and bool(durum), "zaman": zaman,
            "karsilastirma": karsilastirma, "yapilandirma": cihaz.get("veyon_yapilandirma")}


def gorunum(cihaz: dict, veyon_hedef: str | None = None) -> dict:
    """Arayüze giden cihaz kaydı: ham alanlar + hesaplanan alanlar."""
    c = dict(cihaz)
    for gizli in ("anahtar_b64",):
        c.pop(gizli, None)
    c["ad"] = veritabani.cihaz_adi(cihaz)
    c["laboratuvar"] = cihaz.get("grup") or "Laboratuvar"
    c["gereken"] = gereken_islem(cihaz)
    c["uygunluk"] = {islem: uygunluk(cihaz, islem) for islem in ISLEMLER}
    c["ogretmen_pc"] = ag.ogretmen_adresi_mi(cihaz["ip"])
    c["veyon"] = veyon_gorunumu(cihaz, veyon_hedef)
    return c


def hedefleri_ayir(cihaz_idler: list[str], islem: str) -> tuple[list[dict], list[dict]]:
    """(uygun cihazlar, [{cihaz, neden}]) — sıra korunur, yinelenenler atılır."""
    uygun, disarida, goruldu = [], [], set()
    for cid in cihaz_idler:
        if cid in goruldu:
            continue
        goruldu.add(cid)
        cihaz = veritabani.cihaz(cid)
        if not cihaz:
            disarida.append({"id": cid, "ad": cid, "neden": "Envanterde yok"})
            continue
        neden = uygunluk(cihaz, islem)
        if neden:
            disarida.append({"id": cid, "ad": veritabani.cihaz_adi(cihaz), "ip": cihaz["ip"],
                             "neden": neden})
        else:
            uygun.append(cihaz)
    return uygun, disarida


async def _port_acik_mi(ip: str, port: int) -> bool:
    try:
        _, yazici = await asyncio.wait_for(asyncio.open_connection(ip, port),
                                           timeout=ayarlar.TCP_ZAMAN_ASIMI)
        yazici.close()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


async def erisim_dene(cihaz_idler: list[str]) -> dict[str, bool]:
    """Canlı erişim denemesi (yalnız TCP bağlantısı; kimlik bilgisi gönderilmez)."""
    sinir = asyncio.Semaphore(ayarlar.TARAMA_PARALELLIGI)
    sonuc: dict[str, bool] = {}

    async def _tek(cid: str):
        cihaz = veritabani.cihaz(cid)
        if not cihaz:
            return
        async with sinir:
            acik = await _port_acik_mi(cihaz["ip"], cihaz["ssh_port"])
        sonuc[cid] = acik
        veritabani.cihaz_guncelle(cid, erisim=1 if acik else 0, erisim_zamani=veritabani.simdi())

    await asyncio.gather(*(_tek(c) for c in dict.fromkeys(cihaz_idler)))
    return sonuc


async def ozet(cihaz_idler: list[str], islem: str, canli: bool = True) -> dict:
    """Onay penceresi ve seçim çubuğu için kesin hedef listesi."""
    uygun, disarida = hedefleri_ayir(cihaz_idler, islem)
    erisim = await erisim_dene([c["id"] for c in uygun]) if canli and islem != "cikar" else {}
    hedefler, erisilemeyen = [], []
    for c in uygun:
        kayit = {"id": c["id"], "ad": veritabani.cihaz_adi(c), "ip": c["ip"],
                 "laboratuvar": c.get("grup")}
        if erisim.get(c["id"]) is False:
            erisilemeyen.append({**kayit, "neden": "Şu an erişilemiyor (SSH portu kapalı)"})
        else:
            hedefler.append(kayit)
    return {
        "islem": islem,
        "islem_adi": ISLEMLER.get(islem, islem),
        "secili": len(dict.fromkeys(cihaz_idler)),
        "hedefler": hedefler,
        "erisilemeyen": erisilemeyen,
        "kapsam_disi": disarida,
        "korunan": sum(1 for d in disarida if d["neden"].startswith("Korunan")),
    }
