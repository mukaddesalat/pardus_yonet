"""belgeler/arayuz_referans_haritasi.md dosyasını uygulama/arayuz/referans.js'ten üretir.

Kullanım:  python araclar/referans_haritasi.py            (dosyayı yazar)
           python araclar/referans_haritasi.py --denetle  (güncel değilse 1 ile çıkar)
"""

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "uygulama" / "arayuz" / "referans.js"
HEDEF = KOK / "belgeler" / "arayuz_referans_haritasi.md"


def ayristir(metin: str) -> tuple[list, dict, dict]:
    menuler = []
    for m in re.finditer(r'\{ kod: "(M\d+)", ad: "([^"]+)"(, ortak: true)?(?:, ikon: "\w+")?, sayfalar: \[(.*?)\] \}',
                         metin, re.S):
        sayfalar = []
        for s in re.finditer(r'\{ kod: "(S\d+)", ad: "([^"]+)"(?:, ikon: "\w+")?(?:,\s*aciklama: "([^"]*)")? \}',
                             m.group(4), re.S):
            sayfalar.append((s.group(1), s.group(2), s.group(3) or ""))
        menuler.append((m.group(1), m.group(2), bool(m.group(3)), sayfalar))
    dugme_bolumu = metin[metin.index("dugmeler: {"):metin.index("emekli:")]
    dugmeler = {k: (a, i) for k, a, i in re.findall(
        r'"(M\d+-S\d+-B\d+(?:-\*)?)": \["([^"]+)", "([^"]*)"\]', dugme_bolumu)}
    emekli = dict(re.findall(r'"(M\d+-S\d+-B\d+(?:-\*)?)": "([^"]*)"', metin[metin.index("emekli:"):]))
    return menuler, dugmeler, emekli


def uret() -> str:
    metin = KAYNAK.read_text(encoding="utf-8")
    surum = re.search(r'surum: "([^"]+)"', metin).group(1)
    menuler, dugmeler, emekli = ayristir(metin)
    satir = [
        "# Arayüz referans haritası (M / S / B)", "",
        f"Sürüm {surum}. **Otomatik üretildi** (`python araclar/referans_haritasi.py`); kaynak "
        "`uygulama/arayuz/referans.js`. Elle düzenlemeyin.", "",
        "- **M** = menü, **S** = sayfa, **B** = düğme. Tam kod: `M2-S1-B3`.",
        "- Satır düğmeleri satırdaki bilgisayarın (veya öğrenci/ödev/iş) kimliğiyle biter: "
        "`M2-S1-B4-LAB01`. Tabloda `<kimlik>` diye gösterilir.",
        "- Kod, düğmenin yerine değil işlevine bağlıdır: düğme taşınınca kod değişmez. Silinen "
        "düğmenin kodu *emekli* listesine alınır ve başka düğmeye verilmez.",
        "- Arayüzde kodlar sağ üstteki **M0-S1-B1** ile gizlenip gösterilir; tam kod her düğmenin "
        "`data-ui-id` özniteliğindedir ve etiketin üzerine gelince görünür.", "",
        "## Geri bildirim biçimi", "",
        "Kısa ve tutarlı yazın; tek satırda bir değişiklik:", "",
        "```text",
        "M2-S1-B3: metni “Ev dizinini tamamen sıfırla” olsun.",
        "M2 menüsü, S1 Profil Temizliği sayfasındaki B7 düğmesi kırmızı (tehlikeli) olsun.",
        "M1-S1 tablosunda “Kontrol” sütunu “Gereken işlem”den sonra gelsin.",
        "M2-S1-B4-LAB01: bu satırda düğme yerine yalnız uyarı görünsün.",
        "```", "",
    ]
    for kod, ad, ortak, sayfalar in menuler:
        satir.append(f"## {kod} — {ad}" + (" (her sayfada ortak)" if ortak else ""))
        satir.append("")
        for skod, sad, aciklama in sayfalar:
            tam = f"{kod}-{skod}"
            satir.append(f"### {tam} — {sad}")
            if aciklama:
                satir += ["", aciklama]
            satir += ["", "| Kod | Ad | İşlev |", "| --- | --- | --- |"]
            for bk, (bad, islev) in dugmeler.items():
                if bk.startswith(f"{tam}-B"):
                    satir.append(f"| `{bk.replace('-*', '-<kimlik>')}` | {bad} | {islev} |")
            satir.append("")
    satir += ["## Emekli kodlar", ""]
    satir += [f"- `{k}` — {n}" for k, n in emekli.items()] or ["Henüz yok."]
    return "\n".join(satir) + "\n"


def ana():
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8", errors="replace")
    icerik = uret()
    if "--denetle" in sys.argv:
        guncel = HEDEF.exists() and HEDEF.read_text(encoding="utf-8") == icerik
        print("güncel" if guncel else "GÜNCEL DEĞİL: python araclar/referans_haritasi.py çalıştırın")
        sys.exit(0 if guncel else 1)
    HEDEF.write_text(icerik, encoding="utf-8", newline="\n")
    print(f"yazıldı: {HEDEF.relative_to(KOK)}")


if __name__ == "__main__":
    ana()
