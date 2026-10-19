"""Belgeler için arayüzden temiz, yüksek çözünürlüklü ekran alıntıları üretir."""

import subprocess
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
HTML = (KOK / "arayuz-onizleme.html").read_text(encoding="utf-8")
HTML_TEMIZ = HTML.replace(".demo-serit {", ".demo-serit { display: none !important; ")

GORSEL_DIZIN = KOK / "belgeler" / "gorseller"
GORSEL_DIZIN.mkdir(parents=True, exist_ok=True)

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

PAGES = [
    ("01_sinif_masasi.png", "#M1-S1", "1366,1080", ""),
    ("02_bilgisayarlar_ekranlar.png", "#M1-S1", "1366,850", "setTimeout(() => { const el = document.querySelector('.ekran-izgarasi'); if (el) el.scrollIntoView(); }, 800);"),
    (
        "03_cihaz_ozeti.png",
        "#M1-S1",
        "1366,850",
        "setTimeout(() => { const el = document.querySelector('.ekran-gorseli') || document.querySelector('.cihaz-ad-link'); if (el) el.click(); }, 1200);",
    ),
    ("04_hazirlik.png", "#M1-S2", "1366,850", ""),
    ("05_bakim_ve_guc.png", "#M2-S4", "1366,850", ""),
    ("06_komut_merkezi.png", "#M2-S6", "1366,850", ""),
    ("07_odevler.png", "#M3-S1", "1366,850", ""),
    ("08_okul_ve_ogretmen.png", "#M5-S2", "1366,850", ""),
]


def uret():
    cop_dizin = KOK / ".trash"
    cop_dizin.mkdir(parents=True, exist_ok=True)

    for ad, fragment, boyut, extra_js in PAGES:
        sayfa_html = HTML_TEMIZ
        if extra_js:
            betik = f"<script>window.addEventListener('load', () => {{ {extra_js} }});</script></body>"
            sayfa_html = sayfa_html.replace("</body>", betik)
        tmp = cop_dizin / f"tmp_{ad}.html"
        tmp.write_text(sayfa_html, encoding="utf-8")
        out_file = GORSEL_DIZIN / ad

        cmd = [
            EDGE_EXE,
            "--headless",
            "--disable-gpu",
            f"--window-size={boyut}",
            "--virtual-time-budget=4000",
            f"--screenshot={out_file}",
            f"file:///{tmp.as_posix()}{fragment}",
        ]
        subprocess.run(cmd, capture_output=True)
        print(f"{ad}: {out_file.exists()} ({out_file.stat().st_size if out_file.exists() else 0} bayt)")
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    uret()
