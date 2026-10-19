"""Debian paket sürümü karşılaştırması (`dpkg --compare-versions` kuralları).

Sürüm: `[epoch:]upstream[-revision]`. Bölümler sırayla karşılaştırılır; her
bölümde rakam olmayan parçalar `~` < (boş) < harf < diğer sırasıyla, rakam
parçaları sayısal olarak karşılaştırılır (dpkg `verrevcmp`). Öğretmen PC'de
dpkg olmayabilir (geliştirme/test); hedefte gerçek dpkg kullanılır, burada
yalnız filtre ve gösterim için aynı kural uygulanır. Arayüzdeki
`debSurumKarsilastir` (ortak.js) bu algoritmanın birebir kopyasıdır; testler
ikisini aynı örneklerle denetler.
"""


def _parcala(surum: str) -> tuple[int, str, str]:
    surum = surum.strip()
    epoch = 0
    if ":" in surum:
        e, surum = surum.split(":", 1)
        epoch = int(e) if e.isdigit() else 0
    if "-" in surum:
        ust, rev = surum.rsplit("-", 1)
    else:
        ust, rev = surum, ""
    return epoch, ust, rev


def _sira(c: str) -> int:
    """dpkg `order()`: rakam 0, harf kendi kodu, ~ = -1, diğerleri kod+256."""
    if not c or c.isdigit():
        return 0
    if c.isalpha():
        return ord(c)
    if c == "~":
        return -1
    return ord(c) + 256


def _bolum_karsilastir(a: str, b: str) -> int:
    ia = ib = 0
    while ia < len(a) or ib < len(b):
        while (ia < len(a) and not a[ia].isdigit()) or (ib < len(b) and not b[ib].isdigit()):
            ca = _sira(a[ia]) if ia < len(a) and not a[ia].isdigit() else 0
            cb = _sira(b[ib]) if ib < len(b) and not b[ib].isdigit() else 0
            if ca != cb:
                return -1 if ca < cb else 1
            ia += 1
            ib += 1
        sa = sb = ""
        while ia < len(a) and a[ia].isdigit():
            sa += a[ia]
            ia += 1
        while ib < len(b) and b[ib].isdigit():
            sb += b[ib]
            ib += 1
        na, nb = int(sa or "0"), int(sb or "0")
        if na != nb:
            return -1 if na < nb else 1
    return 0


def karsilastir(a: str, b: str) -> int:
    """-1: a < b, 0: eşit, 1: a > b."""
    ea, ua, ra = _parcala(a)
    eb, ub, rb = _parcala(b)
    if ea != eb:
        return -1 if ea < eb else 1
    sonuc = _bolum_karsilastir(ua, ub)
    if sonuc:
        return sonuc
    return _bolum_karsilastir(ra, rb)


def iliski(kurulu: str | None, hedef: str) -> str:
    """Kurulu sürümün seçilen pakete göre durumu: 'kurulu_degil' / 'eski' / 'ayni' / 'yeni'."""
    if not kurulu:
        return "kurulu_degil"
    fark = karsilastir(kurulu, hedef)
    return "eski" if fark < 0 else "ayni" if fark == 0 else "yeni"
