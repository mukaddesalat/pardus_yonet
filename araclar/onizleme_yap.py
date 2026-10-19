"""arayuz-onizleme.html üretir: GERÇEK arayüz kodu + örnek verili DEMO arka ucu, tek dosya.

Kullanım:  python araclar/onizleme_yap.py            (dosyayı yazar)
           python araclar/onizleme_yap.py --denetle  (güncel değilse 1 ile çıkar)

Önizleme; uygulama/arayuz/ altındaki index.html, belirtecler.css, stil.css ve tüm
JS dosyalarını olduğu gibi gömer, yalnız fetch() isteklerini araclar/onizleme/demo.js
örnek verilerle yanıtlar. Böylece önizlemedeki ekranlar, düğmeler ve M/S/B kodları
gerçek arayüzle aynıdır. Sunucu, internet, derleme veya harici kaynak gerekmez.
"""

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
ARAYUZ = KOK / "uygulama" / "arayuz"
DEMO = Path(__file__).resolve().parent / "onizleme" / "demo.js"
HEDEF = KOK / "arayuz-onizleme.html"

BETIK_SIRASI = ["referans.js", "@demo", "ortak.js", "envanter.js", "veyon.js", "islemler.js", "guc.js", "odevler.js",
                "kayitlar.js", "baslat.js"]

SERIT = """<div class="demo-serit" role="note">
  <strong>DEMO — örnek veriler.</strong>
  Bu önizleme gerçek bir bilgisayara bağlanmaz: SSH, paket kurulumu, hesap silme ve dosya
  temizliği yapmaz; parola veya özel anahtar istemez. İndirmeler yalnız bildirimle gösterilir.
  Ekranlar, düğmeler ve M/S/B kodları gerçek uygulamayla aynıdır.
</div>"""

DEMO_CSS = """
/* ---- yalnız önizleme ---- */
.demo-serit {
  position: sticky; top: 0; z-index: 60;
  background: var(--c-demo-bg); color: var(--c-demo);
  font: var(--t-body-sm); padding: 7px var(--s-lg);
  border-bottom: 1px solid #E5C766;
}
.demo-serit strong { font: var(--t-label-md); margin-right: 6px; }
.ust-cubuk { top: var(--serit, 34px); }
.yan-menu { top: var(--serit, 34px); height: calc(100vh - var(--serit, 34px)); }
"""


def _gom(metin: str) -> str:
    # gömülü betikte "</script" dizisi HTML ayrıştırıcısını erken kapatmasın
    return metin.replace("</script", "<\\/script")


def uret() -> str:
    html = (ARAYUZ / "index.html").read_text(encoding="utf-8")
    css = ((ARAYUZ / "belirtecler.css").read_text(encoding="utf-8") + "\n"
           + (ARAYUZ / "stil.css").read_text(encoding="utf-8") + DEMO_CSS)
    html = re.sub(r'<link rel="stylesheet" href="/statik/belirtecler.css">\s*'
                  r'<link rel="stylesheet" href="/statik/stil.css">',
                  lambda _: f"<style>\n{css}</style>", html)
    html = html.replace("<title>Lab Kaptanı — Pardus Sınıf Yönetimi</title>",
                        '<title>Arayüz Önizlemesi — Lab Kaptanı (DEMO)</title>\n'
                        '<meta name="description" content="Lab Kaptanı (Pardus Sınıf Yönetimi) 0.6.0 arayüzünün '
                        'örnek verili, tek dosyalık etkileşimli önizlemesi.">')
    html = html.replace("<!--ONIZLEME-SERIT-->", SERIT)
    betikler = []
    for ad in BETIK_SIRASI:
        kaynak = DEMO if ad == "@demo" else ARAYUZ / ad
        etiket = "demo.js (örnek veri)" if ad == "@demo" else ad
        betikler.append(f"<script>/* ==== {etiket} ==== */\n"
                        f"{_gom(kaynak.read_text(encoding='utf-8').strip())}\n</script>")
    html = re.sub(r'(<script src="/statik/[\w.]+\.js"></script>\s*)+',
                  lambda _: "\n".join(betikler) + "\n", html)
    kalan = re.findall(r'(?:src|href)="/statik/[^"]+"', html)
    if kalan:
        raise SystemExit(f"gömülmemiş kaynak kaldı: {kalan}")
    return html


def ana():
    for akis in (sys.stdout, sys.stderr):
        akis.reconfigure(encoding="utf-8", errors="replace")
    html = uret()
    if "--denetle" in sys.argv:
        guncel = HEDEF.exists() and HEDEF.read_text(encoding="utf-8") == html
        print("güncel" if guncel else "GÜNCEL DEĞİL: python araclar/onizleme_yap.py çalıştırın")
        sys.exit(0 if guncel else 1)
    HEDEF.parent.mkdir(parents=True, exist_ok=True)
    HEDEF.write_text(html, encoding="utf-8", newline="\n")
    print(f"yazıldı: {HEDEF.relative_to(KOK).as_posix()} ({len(html.encode('utf-8')) // 1024} KB)")


if __name__ == "__main__":
    ana()
