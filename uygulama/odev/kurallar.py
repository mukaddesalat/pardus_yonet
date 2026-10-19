"""Teslim kuralları: izinli türler, içerik imzası ve göreli yol doğrulaması.

Tarayıcının bildirdiği MIME türüne güvenilmez; uzantı izin listesiyle
karşılaştırılır, dosya diske yazıldıktan sonra içeriğin ilk baytları uzantıyla
uyuşuyor mu diye ayrıca denetlenir (istem §8). Hiçbir yüklenen dosya sunucuda
çalıştırılmaz, açılmaz veya önizlenmez.
"""

import re
import unicodedata

# kategori -> (arayüz etiketi, uzantılar)
KATEGORILER = {
    "belge": ("Belgeler (PDF, ODT, DOCX, TXT…)",
              ["pdf", "odt", "ods", "odp", "odg", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
               "txt", "rtf", "csv", "md"]),
    "gorsel": ("Görseller (PNG, JPG…)", ["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"]),
    "arsiv": ("ZIP arşivi", ["zip"]),
    "kod": ("Kaynak kod ve proje dosyaları",
            ["py", "ipynb", "c", "h", "cpp", "hpp", "cs", "java", "js", "ts", "html", "htm",
             "css", "php", "json", "xml", "sql", "sh", "rb", "go", "rs", "kt", "swift", "sb3",
             "ino", "pde", "lua", "yaml", "yml", "toml", "ini", "cfg", "gitignore"]),
    "medya": ("Ses ve video", ["mp3", "wav", "ogg", "oga", "m4a", "mp4", "webm", "mkv"]),
}
VARSAYILAN_KATEGORILER = ["belge", "gorsel", "arsiv"]

_ZIP = (b"PK\x03\x04", b"PK\x05\x06")
_OLE = (b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",)
IMZALAR = {
    "pdf": (b"%PDF-",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xFF\xD8\xFF",), "jpeg": (b"\xFF\xD8\xFF",),
    "gif": (b"GIF87a", b"GIF89a"),
    "bmp": (b"BM",),
    "zip": _ZIP, "docx": _ZIP, "xlsx": _ZIP, "pptx": _ZIP, "odt": _ZIP, "ods": _ZIP,
    "odp": _ZIP, "odg": _ZIP, "sb3": _ZIP,
    "doc": _OLE, "xls": _OLE, "ppt": _OLE,
    "rtf": (b"{\\rtf",),
    "mp3": (b"ID3", b"\xFF\xFB", b"\xFF\xF3", b"\xFF\xF2"),
    "ogg": (b"OggS",), "oga": (b"OggS",),
    "webm": (b"\x1A\x45\xDF\xA3",), "mkv": (b"\x1A\x45\xDF\xA3",),
}
# (başlangıç, 8. bayttan itibaren beklenen) RIFF/ftyp türleri
_OZEL = {"webp": (b"RIFF", b"WEBP"), "wav": (b"RIFF", b"WAVE")}
_FTYP = {"mp4", "m4a"}
# Metin olması beklenen türler: ilk 8 KB'de NUL bayt olmamalı
METIN = set(KATEGORILER["kod"][1]) | {"txt", "csv", "md", "svg"}
METIN.discard("sb3")

_YASAK_KARAKTER = re.compile(r'[\x00-\x1f\x7f\\:*?"<>|]')
YOL_SINIRI = 400
AD_SINIRI = 200


class KuralHatasi(ValueError):
    """Öğrenciye olduğu gibi gösterilebilecek doğrulama hatası."""


def uzanti(ad: str) -> str:
    """'odev.tar.gz' -> 'gz'; '.gitignore' -> 'gitignore'; uzantısız -> ''."""
    son = ad.rsplit("/", 1)[-1].lower()
    if son.startswith(".") and son.count(".") == 1:
        return son[1:]
    return son.rsplit(".", 1)[1] if "." in son else ""


def izinli_uzantilar(kategoriler: list[str], ek: list[str]) -> set[str]:
    sonuc = set()
    for kategori in kategoriler:
        if kategori in KATEGORILER:
            sonuc.update(KATEGORILER[kategori][1])
    sonuc.update(u.lower().lstrip(".") for u in ek)
    return sonuc


def ek_uzantilari_dogrula(ek: list[str]) -> list[str]:
    temiz = []
    for u in ek:
        u = u.strip().lower().lstrip(".")
        if not u:
            continue
        if not re.fullmatch(r"[a-z0-9]{1,10}", u):
            raise KuralHatasi(f"Geçersiz uzantı: {u}")
        temiz.append(u)
    return sorted(set(temiz))


def yol_dogrula(ham: str) -> str:
    """Öğrencinin gönderdiği göreli yolu doğrular ve normalleştirir.

    Mutlak yol, '..', boş bileşen, denetim karakteri ve aşırı uzunluk reddedilir.
    Sonuç yalnız üstveridir; diskte asla yol olarak kullanılmaz.
    """
    if not isinstance(ham, str) or not ham.strip():
        raise KuralHatasi("Dosya adı boş olamaz")
    yol = unicodedata.normalize("NFC", ham.replace("\\", "/")).strip()
    if yol.startswith("/") or re.match(r"^[A-Za-z]:", yol):
        raise KuralHatasi(f"Mutlak yol kabul edilmez: {ham}")
    parcalar = [p for p in yol.split("/") if p not in ("", ".")]
    if not parcalar:
        raise KuralHatasi("Dosya adı boş olamaz")
    for parca in parcalar:
        if parca == "..":
            raise KuralHatasi(f"Üst klasöre çıkan yol kabul edilmez: {ham}")
        if _YASAK_KARAKTER.search(parca):
            raise KuralHatasi(f"Dosya adında izin verilmeyen karakter var: {parca}")
        if len(parca) > AD_SINIRI:
            raise KuralHatasi(f"Dosya adı çok uzun: {parca[:40]}…")
    sonuc = "/".join(parcalar)
    if len(sonuc) > YOL_SINIRI:
        raise KuralHatasi(f"Klasör yolu çok uzun: {sonuc[:40]}…")
    return sonuc


def liste_dogrula(dosyalar: list[dict], odev: dict, izinli: set[str]) -> list[dict]:
    """Gönderim öncesi bildirilen listeyi doğrular.

    Bir dosya bile kurala uymuyorsa bütün liste reddedilir; sunucu hatalı
    dosyayı sessizce atıp kalanını tam teslim saymaz (istem §6).
    """
    if not dosyalar:
        raise KuralHatasi("En az bir dosya seçin")
    if len(dosyalar) > odev["en_fazla_dosya"]:
        raise KuralHatasi(f"En çok {odev['en_fazla_dosya']} dosya gönderilebilir "
                          f"({len(dosyalar)} dosya seçildi)")
    temiz, gorulen, toplam = [], set(), 0
    for dosya in dosyalar:
        yol = yol_dogrula(dosya.get("yol", ""))
        boyut = dosya.get("boyut")
        if not isinstance(boyut, int) or boyut < 0:
            raise KuralHatasi(f"Geçersiz dosya boyutu: {yol}")
        if "/" in yol and not odev["klasor_izni"]:
            raise KuralHatasi("Bu ödev klasör kabul etmiyor; dosyaları tek tek seçin")
        uz = uzanti(yol)
        if uz not in izinli:
            raise KuralHatasi(f"Bu dosya türü kabul edilmiyor: {yol}")
        anahtar = yol.casefold()  # Windows/ZIP'te çakışacak aynı adlar da reddedilir
        if anahtar in gorulen:
            raise KuralHatasi(f"Aynı yol iki kez seçildi: {yol}")
        gorulen.add(anahtar)
        toplam += boyut
        temiz.append({"yol": yol, "boyut": boyut})
    if toplam > odev["en_fazla_bayt"]:
        raise KuralHatasi(f"Toplam boyut sınırı aşıldı: en çok "
                          f"{odev['en_fazla_bayt'] // 1048576} MB")
    # klasör ile aynı adı taşıyan dosya ("a" dosyası ve "a/b") çakışır
    klasorler = {"/".join(d["yol"].split("/")[:i]).casefold()
                 for d in temiz for i in range(1, d["yol"].count("/") + 1)}
    for d in temiz:
        if d["yol"].casefold() in klasorler:
            raise KuralHatasi(f"Aynı adda hem dosya hem klasör var: {d['yol']}")
    return temiz


def icerik_uyusuyor_mu(uz: str, bas: bytes, boyut: int) -> bool:
    """Diske yazılmış dosyanın ilk baytları uzantıyla uyuşuyor mu?"""
    if boyut == 0:
        return uz in METIN  # boş metin dosyası olabilir; boş PDF/ZIP olamaz
    if uz in IMZALAR:
        return bas.startswith(IMZALAR[uz])
    if uz in _OZEL:
        on, tur = _OZEL[uz]
        return bas.startswith(on) and bas[8:12] == tur
    if uz in _FTYP:
        return bas[4:8] == b"ftyp"
    if uz in METIN:
        return b"\x00" not in bas
    return True  # öğretmenin eklediği özel uzantılar: yalnız uzantı denetimi
