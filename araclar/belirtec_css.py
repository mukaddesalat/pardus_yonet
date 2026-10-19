"""DESIGN.md belirteçlerini CSS değişkenlerine çevirir.

Kullanım:  python araclar/belirtec_css.py          (dosyayı yazar)
           python araclar/belirtec_css.py --denetle (güncel değilse 1 ile çıkar)

DESIGN.md (https://github.com/google-labs-code/design.md) ön bölümü YAML'dır.
Paket bağımlılığı eklememek için yalnız bu projenin kullandığı alt küme
(girintili eşlemeler + tek satırlık skaler değerler) okunur.
"""

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "DESIGN.md"
HEDEF = KOK / "uygulama" / "arayuz" / "belirtecler.css"

# Yazı tipi yoksa kullanılacak yedekler (çevrimdışı; web yazı tipi yüklenmez)
YEDEK_YAZI = {
    "Ubuntu": '"Ubuntu", "Noto Sans", "DejaVu Sans", system-ui, sans-serif',
    "Ubuntu Mono": '"Ubuntu Mono", "DejaVu Sans Mono", monospace',
}


def on_bolum(metin: str) -> str:
    satirlar = metin.splitlines()
    if not satirlar or satirlar[0].strip() != "---":
        raise ValueError("DESIGN.md '---' ile başlamalı")
    for sira, satir in enumerate(satirlar[1:], 1):
        if satir.strip() == "---":
            return "\n".join(satirlar[1:sira])
    raise ValueError("DESIGN.md ön bölümü kapanmamış")


def _skaler(deger: str):
    deger = deger.strip()
    if len(deger) >= 2 and deger[0] == deger[-1] and deger[0] in "\"'":
        return deger[1:-1]
    if re.fullmatch(r"-?\d+", deger):
        return int(deger)
    if re.fullmatch(r"-?\d+\.\d+", deger):
        return float(deger)
    return deger


def yaml_oku(metin: str) -> dict:
    """Girintiye dayalı iç içe eşleme ayrıştırıcısı (liste ve çok satırlı değer yok)."""
    kok: dict = {}
    yigin = [(-1, kok)]
    for ham in metin.splitlines():
        if not ham.strip() or ham.lstrip().startswith("#"):
            continue
        girinti = len(ham) - len(ham.lstrip(" "))
        anahtar, _, deger = ham.strip().partition(":")
        if not _:
            raise ValueError(f"çözülemeyen satır: {ham!r}")
        while yigin[-1][0] >= girinti:
            yigin.pop()
        ust = yigin[-1][1]
        if deger.strip():
            ust[anahtar.strip()] = _skaler(deger)
        else:
            ust[anahtar.strip()] = {}
            yigin.append((girinti, ust[anahtar.strip()]))
    return kok


def belirtecler() -> dict:
    return yaml_oku(on_bolum(KAYNAK.read_text(encoding="utf-8")))


def css_uret(b: dict) -> str:
    satirlar = [
        "/* OTOMATİK ÜRETİLDİ — elle düzenlemeyin.",
        "   Kaynak: DESIGN.md; üretici: araclar/belirtec_css.py */",
        ":root {",
    ]
    for ad, deger in b["colors"].items():
        satirlar.append(f"  --c-{ad}: {deger};")
    for ad, deger in b["rounded"].items():
        satirlar.append(f"  --r-{ad}: {deger};")
    for ad, deger in b["spacing"].items():
        satirlar.append(f"  --s-{ad}: {deger};")
    for ad, t in b["typography"].items():
        aile = YEDEK_YAZI.get(t["fontFamily"], f'"{t["fontFamily"]}", sans-serif')
        satirlar.append(f"  --t-{ad}: {t['fontWeight']} {t['fontSize']}/{t['lineHeight']} {aile};")
    satirlar.append("}")
    return "\n".join(satirlar) + "\n"


# ---- WCAG kontrast (DESIGN.md lint kuralı "contrast-ratio" yerine; npx gerektirmez) ----

def _parlaklik(hex_renk: str) -> float:
    hex_renk = hex_renk.lstrip("#")
    kanallar = [int(hex_renk[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    dogrusal = [k / 12.92 if k <= 0.03928 else ((k + 0.055) / 1.055) ** 2.4 for k in kanallar]
    return 0.2126 * dogrusal[0] + 0.7152 * dogrusal[1] + 0.0722 * dogrusal[2]


def kontrast(on: str, arka: str) -> float:
    a, b = sorted((_parlaklik(on), _parlaklik(arka)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def ana():
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8", errors="replace")
    css = css_uret(belirtecler())
    if "--denetle" in sys.argv:
        guncel = HEDEF.exists() and HEDEF.read_text(encoding="utf-8") == css
        print("güncel" if guncel else "GÜNCEL DEĞİL: python araclar/belirtec_css.py çalıştırın")
        sys.exit(0 if guncel else 1)
    HEDEF.write_text(css, encoding="utf-8", newline="\n")
    print(f"yazıldı: {HEDEF.relative_to(KOK)}")


if __name__ == "__main__":
    ana()
