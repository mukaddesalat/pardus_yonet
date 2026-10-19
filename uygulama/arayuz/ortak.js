/* Pardus Sınıf Yönetimi — ortak arayüz altyapısı (çerçevesiz JavaScript).
 *
 * İçerik: yardımcılar, API, referans kodu rozetleri, menü/sayfa yönlendirme,
 * toplu seçim deposu (M0-S2), bilgisayar tablosu, seçim çubuğu, onay penceresi
 * (M0-S3), seçim listesi (M0-S5) ve iş durumu paneli (M0-S4).
 * Hedef bilgisayardan gelen metinler güvenilmezdir (istem §10): DOM'a yalnız
 * textContent ile yazılır; innerHTML'e kullanıcı/uzak veri konmaz.
 */
"use strict";

/* ================================================================ yardımcılar */

const $ = (s, kok = document) => kok.querySelector(s);
const $$ = (s, kok = document) => Array.from(kok.querySelectorAll(s));

/** el("button", {class: "x", "data-ui-id": "M1-S1-B1", onclick: f}, "metin", düğüm...) */
function el(etiket, ozellikler = {}, ...cocuklar) {
  const d = document.createElement(etiket);
  for (const [ad, deger] of Object.entries(ozellikler || {})) {
    if (deger == null || deger === false) continue;
    if (ad.startsWith("on") && typeof deger === "function") d.addEventListener(ad.slice(2), deger);
    else if (ad === "class") d.className = deger;
    else if (ad === "metin") d.textContent = deger;
    else if (ad in d && typeof deger !== "string") d[ad] = deger;
    else d.setAttribute(ad, deger === true ? "" : deger);
  }
  for (const c of cocuklar.flat()) {
    if (c == null || c === false) continue;
    d.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return d;
}

function dugme(metin, uiId, islev, sinif = "ikincil") {
  return el("button", { type: "button", class: sinif, "data-ui-id": uiId, onclick: islev }, metin);
}

function rozet(metin, ton = "notr") {
  return el("span", { class: `rozet ${ton}`, metin });
}

function bildir(mesaj, hata = false) {
  const kutu = $("#bildirim");
  kutu.textContent = mesaj;
  kutu.classList.toggle("hata-bildirim", Boolean(hata));
  kutu.hidden = false;
  clearTimeout(kutu._zaman);
  kutu._zaman = setTimeout(() => { kutu.hidden = true; }, hata ? 9000 : 6000);
}

const SAYI = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });

function boyut(bayt) {
  if (bayt == null || Number.isNaN(bayt)) return "ölçülemedi";
  const isaret = bayt < 0 ? "−" : "";
  let b = Math.abs(bayt);
  for (const birim of ["B", "KB", "MB", "GB", "TB"]) {
    if (b < 1024 || birim === "TB") return `${isaret}${SAYI.format(b)} ${birim}`;
    b /= 1024;
  }
  return "";
}

function tarih(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
}

function goreliZaman(iso) {
  if (!iso) return "hiç";
  const fark = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(fark)) return "—";
  if (fark < 60) return "az önce";
  if (fark < 3600) return `${Math.floor(fark / 60)} dk önce`;
  if (fark < 86400) return `${Math.floor(fark / 3600)} sa önce`;
  return `${Math.floor(fark / 86400)} gün önce`;
}

/** Satır düğmesi kimliği: LAB01, ETAP-TAHTA... (Türkçe harfler sadeleştirilir). */
function kimlikSlug(metin) {
  return String(metin || "")
    .replace(/ı/g, "i").replace(/İ/g, "I")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 20);
}

function indir(url) {
  if (window.PSY_DEMO && window.PSY_DEMO.indir) { window.PSY_DEMO.indir(url); return; }
  const a = el("a", { href: url, download: "" });
  document.body.append(a);
  a.click();
  a.remove();
}

/* ================================================================ API */

const Uyg = { csrf: null, surum: "" };

async function api(yol, govde = null, metod = null) {
  const secenekler = {
    method: metod || (govde ? "POST" : "GET"),
    headers: { "Content-Type": "application/json" },
  };
  if (Uyg.csrf) secenekler.headers["X-CSRF"] = Uyg.csrf;
  if (govde) secenekler.body = JSON.stringify(govde);
  const yanit = await fetch(yol, secenekler);
  let veri = null;
  try { veri = await yanit.json(); } catch (_) { /* gövdesiz yanıt */ }
  if (!yanit.ok) {
    const ayrinti = veri && veri.detail;
    const mesaj = Array.isArray(ayrinti) ? ayrinti.map((a) => a.msg).join("; ")
      : (ayrinti || `Sunucu hatası (${yanit.status})`);
    throw new Error(mesaj);
  }
  return veri;
}

/** Ham dosya gövdesi yükler (paketler, Veyon anahtarı). Yol parametresi yoktur; yalnız içerik gider.
 *  Hata nesnesi sunucu yanıtını (.durum, .veri) taşır: ör. 409 + onay_gerekli. */
async function apiDosya(yol, dosya, ekBasliklar = {}) {
  const yanit = await fetch(yol, {
    method: "POST",
    headers: { "X-CSRF": Uyg.csrf || "", "X-Dosya-Adi": encodeURIComponent(dosya.name),
      "Content-Type": "application/octet-stream", ...ekBasliklar },
    body: dosya,
  });
  let veri = null;
  try { veri = await yanit.json(); } catch (_) { /* yok */ }
  if (!yanit.ok) {
    const hata = new Error((veri && veri.detail) || `Sunucu hatası (${yanit.status})`);
    hata.durum = yanit.status;
    hata.veri = veri;
    throw hata;
  }
  return veri;
}

/* ================================================================ ikonlar (satır içi SVG; dış kaynak yok) */

const IKONLAR = {
  bilgisayar: "M3 4h18v12H3z M8 20h8 M12 16v4",
  liste: "M8 6h13 M8 12h13 M8 18h13 M3.5 6h.01 M3.5 12h.01 M3.5 18h.01",
  anahtar: "M15 7a4 4 0 1 1-3.9 4.9L3 20v-3h3v-3h3l2.1-2.1A4 4 0 0 1 15 7z M16 9.5h.01",
  ara: "M11 4a7 7 0 1 1 0 14a7 7 0 0 1 0-14z M20 20l-4-4",
  ekran: "M2 5h20v12H2z M7 21h10 M12 17v4 M9 9l3 2l-3 2z",
  arac: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6l-2.4-.6l-.6-2.4z",
  supurge: "M14 3l-3.5 9 M7 12h9l1.5 9h-12z M9.5 16v3 M12.5 16v3",
  paket: "M3 7l9-4l9 4v10l-9 4l-9-4z M3 7l9 4l9-4 M12 11v10",
  gorunum: "M3 4h18v16H3z M3 9h18 M9 9v11",
  guc: "M12 3v9 M6.3 6.3a8 8 0 1 0 11.4 0",
  odev: "M9 3h6v3H9z M7 5H5v16h14V5h-2 M8 12l3 3l5-6",
  teslim: "M3 13l3-9h12l3 9v7H3z M3 13h5l1 3h6l1-3h5",
  kisiler: "M9 11a4 4 0 1 0 0-8a4 4 0 0 0 0 8z M2 21v-1a7 7 0 0 1 14 0v1 M16 3.5a4 4 0 0 1 0 7 M22 21v-1a7 7 0 0 0-4-6.3",
  gecmis: "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5 M12 7v5l3 3",
  ayar: "M12 9a3 3 0 1 1 0 6a3 3 0 0 1 0-6z M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3a1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5a1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8a1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  ok: "M9 6l6 6l-6 6",
  saat: "M12 3a9 9 0 1 1 0 18a9 9 0 0 1 0-18z M12 7v5l3.5 2",
  kalkan: "M12 3l8 3v6c0 4.5-3.3 8-8 9c-4.7-1-8-4.5-8-9V6z",
  kilit: "M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3",
  kisi: "M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0",
  kisi_yok: "M10 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8z M3 21a7 7 0 0 1 11-5.7 M16 15l5 5 M21 15l-5 5",
  tamam: "M5 12.5l4.5 4.5L19 7",
  soru: "M9.2 9a3 3 0 1 1 4.3 2.7c-.9.5-1.5 1.2-1.5 2.3v.5 M12 18h.01",
  kimlik: "M4 5h16v14H4z M9 10a2 2 0 1 0 0 .01 M6.5 16a2.8 2.8 0 0 1 5 0 M14 9h4 M14 13h4",
  uyari: "M12 4l9 16H3z M12 10v4 M12 17h.01",
  ay: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z",
  izgara: "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z",
  ekran_kapali: "M12 3v8 M6.3 6.3a8 8 0 1 0 11.4 0",
};

function ikon(ad, sinif = "ikon") {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", sinif);
  svg.setAttribute("aria-hidden", "true");
  const yol = document.createElementNS(ns, "path");
  yol.setAttribute("d", IKONLAR[ad] || IKONLAR.liste);
  svg.append(yol);
  return svg;
}

/* ================================================================ referans kodları (temizlendi) */

const REF = window.PSY_REFERANS;

function refAnahtari(kod) {
  const es = /^(M\d+-S\d+-B\d+)(-.+)?$/.exec(kod || "");
  if (!es) return null;
  return es[2] ? `${es[1]}-*` : es[1];
}

function refRozeti() {
  /* Destek kodları (B1, B2...) arayüz sadeleştirmesi kapsamında kaldırıldı. */
}

function kodlariGoster() {
  document.body.classList.add("kodlar-gizli");
  const d = $("#kod-dugmesi");
  if (d) d.hidden = true;
}

function kodlarGorunur() {
  return false;
}

/* ================================================================ sezgisel menü ve sayfalar */

const SAYFALAR = {};   // "M1-S1" -> {ac(), kapat()}
let aktifSayfa = null;

function sayfaKaydet(kod, islevler) { SAYFALAR[kod] = islevler; }

function sayfaAdi(kod) {
  const [m, s] = kod.split("-");
  const menu = REF.menuler.find((x) => x.kod === m);
  const sayfa = menu && menu.sayfalar.find((x) => x.kod === s);
  return { menu, sayfa };
}

/** Standart öğretmen yetki denetimi: M1-S1, M2-S1, M2-S4, M3-S1, M3-S2, M4-S1 her zaman açık;
 *  M2-S2/M2-S3 -> paket_gorunum yetkisi; M2-S6 -> komut_gonder yetkisi; diğerleri yalnız Admin. */
function sayfaYetkiliMi(kod) {
  const ogr = Uyg.ogretmen;
  if (!ogr || ogr.rol === "admin") return true;
  const yetkiler = Array.isArray(ogr.yetkiler) ? ogr.yetkiler : [];
  if (["M1-S1", "M2-S1", "M2-S4", "M3-S1", "M3-S2", "M4-S1"].includes(kod)) return true;
  if (["M2-S2", "M2-S3"].includes(kod)) return yetkiler.includes("paket_gorunum");
  if (kod === "M2-S6") return yetkiler.includes("komut_gonder");
  return false;
}

const SEZGISEL_MENULER = [
  {
    bolum: "GÜNLÜK DERS AKIŞI",
    ogeler: [
      {
        id: "nav-sinif",
        emoji: "🖥️",
        baslik: "Sınıf Masası",
        alt: "Ekran Kilit, Duyuru, İnternet, Güç",
        sayfalar: [["M1-S1", "🖥️ Sınıf Masası"]],
      },
      {
        id: "nav-odev",
        emoji: "📚",
        baslik: "Ödev & Dosya Dağıt",
        alt: "Teslimler, Materyal, Öğrenci Kartları",
        sayfalar: [
          ["M3-S1", "📚 Ödev Teslimleri & Masaüstüne Dağıtım"],
          ["M3-S2", "🪪 Sınıf Listeleri & Öğrenci Kod Kartları"],
        ],
      },
      {
        id: "nav-bakim",
        emoji: "🧹",
        baslik: "Bakım & Görünüm",
        alt: "Ders Sonu Temizliği, Paket, Uyku",
        altStandart: "Ders Sonu Temizliği & Uyku Kilidi",
        sayfalar: [
          ["M2-S1", "🧹 Ders Sonu Temizliği & Yedek"],
          ["M2-S4", "🔌 Güç & Uyku Ayarı"],
          ["M2-S2", "📦 .deb Paket Kurulumu"],
          ["M2-S3", "🖼️ Masaüstü Görünümü"],
        ],
      },
      {
        id: "nav-komut",
        emoji: "💻",
        baslik: "Komut Gönder",
        alt: "SSH Bash, Hosts, Canlı Çıktı",
        sayfalar: [["M2-S6", "💻 SSH Komut & Hosts Merkezi"]],
      },
      {
        id: "nav-gecmis",
        emoji: "📋",
        baslik: "İşlem Geçmişi",
        alt: "Yapılan İşlemler & CSV Rapor",
        sayfalar: [["M4-S1", "📋 İşlem Geçmişi"]],
      },
    ],
  },
  {
    bolum: "YÖNETİCİ & KURULUM",
    yalnizAdmin: true,
    ogeler: [
      {
        id: "nav-kurulum",
        emoji: "⚙️",
        baslik: "Kurulum, Okul & Öğretmen",
        alt: "Logo, Hesaplar, İlk Hazırlık, Veyon",
        sayfalar: [
          ["M5-S2", "🏫 Okul Logosu & Öğretmenler"],
          ["M1-S2", "🔑 İlk Hazırlık (SSH & Sudo)"],
          ["M1-S3", "🔍 Ağda Bilgisayar Bul"],
          ["M1-S4", "👁️ Veyon Kurulumu"],
          ["M2-S5", "⏰ Zamanlı Kapatma"],
          ["M5-S1", "🛠️ Sistem Ayarları"],
        ],
      },
    ],
  },
];

function _sayfayiIcerenGrup(kod) {
  for (const b of SEZGISEL_MENULER) {
    for (const o of b.ogeler) {
      if (o.sayfalar.some(([k]) => k === kod)) return o;
    }
  }
  return SEZGISEL_MENULER[0].ogeler[0];
}

const VARSAYILAN_OKUL_ADI = "Şehit Cengiz Polat Fen ve Teknoloji Anadolu İmam Hatip Lisesi";
const VARSAYILAN_OKUL_LOGO =
  "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2232%22%20r%3D%2230%22%20fill%3D%22%231B5FC1%22%20stroke%3D%22%2393C5FD%22%20stroke-width%3D%222.5%22%2F%3E%3Cpath%20d%3D%22M32%2012L14%2021v12c0%2011.5%207.7%2021.8%2018%2025%2010.3-3.2%2018-13.5%2018-25V21L32%2012z%22%20fill%3D%22%230F2A56%22%2F%3E%3Cpath%20d%3D%22M22%2036c4-2%208-2%2010%200%202-2%206-2%2010%200V24c-4-2-8-2-10%200-2-2-6-2-10%200v12z%22%20fill%3D%22%23FFFFFF%22%2F%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2219%22%20r%3D%222.5%22%20fill%3D%22%23FBBF24%22%2F%3E%3C%2Fsvg%3E";

function okulBilgisiniUygula(okul) {
  if (!okul) return;
  Uyg.okul = okul;
  const ad = okul.ad || VARSAYILAN_OKUL_ADI;
  const alt = okul.alt_baslik || "Bilişim Teknolojileri Laboratuvarı";
  const logo = okul.logo_b64 || VARSAYILAN_OKUL_LOGO;
  if ($("#giris-okul-ad")) {
    $("#giris-okul-ad").textContent = ad;
    $("#giris-okul-ad").title = ad;
  }
  if ($("#giris-okul-alt")) {
    $("#giris-okul-alt").textContent = alt;
    $("#giris-okul-alt").title = alt;
  }
  if ($("#giris-okul-logo")) {
    $("#giris-okul-logo").src = logo || "";
    $("#giris-okul-logo").hidden = !logo;
  }
  if ($("#yan-okul-ad")) {
    $("#yan-okul-ad").textContent = ad;
    $("#yan-okul-ad").title = ad;
  }
  if ($("#yan-okul-alt")) {
    $("#yan-okul-alt").textContent = alt;
    $("#yan-okul-alt").title = alt;
  }
  const yanOkulLogo = $("#yan-okul-logo");
  const yanVarsayilanLogo = $("#yan-varsayilan-logo");
  if (yanOkulLogo && yanVarsayilanLogo) {
    if (logo) {
      yanOkulLogo.src = logo;
      yanOkulLogo.hidden = false;
      yanOkulLogo.style.display = "block";
      yanVarsayilanLogo.setAttribute("hidden", "");
      yanVarsayilanLogo.style.display = "none";
    } else {
      yanOkulLogo.src = "";
      yanOkulLogo.hidden = true;
      yanOkulLogo.style.display = "none";
      yanVarsayilanLogo.removeAttribute("hidden");
      yanVarsayilanLogo.style.display = "block";
    }
  }
}

function ogretmenBilgisiniUygula(ogr) {
  Uyg.ogretmen = ogr || null;
  const cip = $("#aktif-ogretmen-cip");
  if (cip) {
    if (ogr) {
      const adminMi = ogr.rol === "admin";
      const rolEtiket = adminMi ? "🛡️ Admin Öğretmen" : "👨‍🏫 Standart Öğretmen";
      cip.replaceChildren(
        el("strong", { metin: ogr.ad_soyad || ogr.kullanici_adi }),
        " ",
        rozet(rolEtiket, adminMi ? "mavi" : "iyi")
      );
      cip.title = `${ogr.ad_soyad || ogr.kullanici_adi} (${rolEtiket})`;
      cip.hidden = false;
    } else {
      cip.hidden = true;
    }
  }
  const yanKart = $("#yan-ogretmen-kutu");
  if (yanKart) {
    if (ogr) {
      const adminMi = ogr.rol === "admin";
      const ogrAdEl = $("#yan-ogr-ad");
      if (ogrAdEl) {
        ogrAdEl.textContent = ogr.ad_soyad || ogr.kullanici_adi;
        ogrAdEl.title = ogr.ad_soyad || ogr.kullanici_adi;
      }
      const ogrRolEl = $("#yan-ogr-rol");
      if (ogrRolEl) {
        ogrRolEl.textContent = adminMi ? "🛡️ Admin Öğretmen" : "👨‍🏫 Standart Öğretmen";
        ogrRolEl.className = "yan-ogr-rol-etiket " + (adminMi ? "admin" : "standart");
      }
      yanDurumGuncelle();
      yanKart.hidden = false;
    } else {
      yanKart.hidden = true;
    }
  }
  const tamSifirla = $("#m2s1-tam");
  if (tamSifirla) {
    tamSifirla.hidden = Boolean(ogr && ogr.rol !== "admin");
  }
}

/** Sol alt paneldeki Ekran / Ağ durum özetini dinamik günceller */
function yanDurumGuncelle(ekranKilitli, internetKisitli) {
  if (ekranKilitli !== undefined) Uyg.ekranKilitli = Boolean(ekranKilitli);
  if (internetKisitli !== undefined) Uyg.internetKisitli = Boolean(internetKisitli);
  const elOzet = $("#yan-durum-ozet");
  if (!elOzet) return;
  const kilitli = Boolean(Uyg.ekranKilitli);
  const kisitli = Boolean(Uyg.internetKisitli);
  const ekranMetin = kilitli ? "🔒 Kilitli" : "🔓 Serbest";
  const agMetin = kisitli ? "🚫 Kısıtlı" : "🌐 Açık";
  elOzet.textContent = `${ekranMetin} · ${agMetin}`;
  if (kilitli || kisitli) {
    elOzet.style.color = kilitli ? "#EF4444" : "#F59E0B";
  } else {
    elOzet.style.color = "#22C55E";
  }
}

/** Sezgisel sol menü (demo_arayuz.html düzeni): büyük ikonlu kartlar + üst alt-sekme çubuğu. */
function menuKur() {
  const nav = $("#menu");
  nav.replaceChildren();
  const ogr = Uyg.ogretmen;
  const adminMi = !ogr || ogr.rol === "admin";
  const yetkiler = (ogr && Array.isArray(ogr.yetkiler)) ? ogr.yetkiler : [];

  for (const bolum of SEZGISEL_MENULER) {
    if (bolum.yalnizAdmin && !adminMi) continue;
    const gorunenOgeler = bolum.ogeler.map((oge) => ({
      ...oge,
      yetkiliSayfalar: oge.sayfalar.filter(([kod]) => sayfaYetkiliMi(kod)),
    })).filter((oge) => oge.yetkiliSayfalar.length > 0);
    if (!gorunenOgeler.length) continue;

    nav.append(el("div", { class: "sezgisel-bolum-baslik", metin: bolum.bolum }));
    for (const oge of gorunenOgeler) {
      const altMetin = (!adminMi && oge.altStandart && !yetkiler.includes("paket_gorunum"))
        ? oge.altStandart
        : oge.alt;
      const btn = el("button", {
        type: "button",
        class: "sezgisel-nav-dugme",
        "data-grup-id": oge.id,
        "data-ilk-sayfa": oge.yetkiliSayfalar[0][0],
        onclick: () => git(oge.yetkiliSayfalar[0][0]),
      },
      el("span", { class: "sezgisel-nav-emoji", "aria-hidden": "true", metin: oge.emoji }),
      el("div", { class: "sezgisel-nav-metin" },
        el("strong", { class: "sezgisel-nav-baslik", metin: oge.baslik }),
        el("span", { class: "sezgisel-nav-alt", metin: altMetin })
      ));
      nav.append(btn);
    }
  }
}

function _altSekmeleriCiz(aktifKod) {
  let cubuk = $("#alt-sekme-cubugu");
  if (!cubuk) {
    cubuk = el("div", { id: "alt-sekme-cubugu", class: "alt-sekme-cubugu", role: "tablist" });
    const sayfalarKap = $("#sayfalar");
    if (sayfalarKap) sayfalarKap.prepend(cubuk);
  }
  const grup = _sayfayiIcerenGrup(aktifKod);
  const yetkili = grup ? grup.sayfalar.filter(([k]) => sayfaYetkiliMi(k)) : [];
  if (yetkili.length <= 1) {
    cubuk.hidden = true;
    cubuk.replaceChildren();
    return;
  }
  cubuk.replaceChildren(
    ...yetkili.map(([kod, etiket]) => el("button", {
      type: "button",
      role: "tab",
      class: `alt-sekme-dugme${kod === aktifKod ? " aktif" : ""}`,
      "aria-selected": kod === aktifKod ? "true" : "false",
      onclick: () => git(kod),
    }, etiket))
  );
  cubuk.hidden = false;
}

function sayfaGoster(kod) {
  if (!SAYFALAR[kod] || !$(`#sayfa-${kod}`) || !sayfaYetkiliMi(kod)) kod = "M1-S1";
  if (aktifSayfa && SAYFALAR[aktifSayfa] && SAYFALAR[aktifSayfa].kapat) SAYFALAR[aktifSayfa].kapat();
  aktifSayfa = kod;
  for (const s of $$(".sayfa")) s.hidden = s.id !== `sayfa-${kod}`;
  const grup = _sayfayiIcerenGrup(kod);
  for (const b of $$(".sezgisel-nav-dugme")) {
    b.classList.toggle("aktif", Boolean(grup && b.dataset.grupId === grup.id));
  }
  _altSekmeleriCiz(kod);
  const { sayfa } = sayfaAdi(kod);
  const sekmeEtiketi = grup && grup.sayfalar.find(([k]) => k === kod);
  $("#ust-baslik").textContent = (sekmeEtiketi && sekmeEtiketi[1]) || (sayfa && sayfa.ad) || "Lab Kaptanı";
  document.title = `${(sayfa && sayfa.ad) || "Sınıf Masası"} — ${(Uyg.okul && Uyg.okul.ad) || "Lab Kaptanı"}`;
  window.scrollTo(0, 0);
  if (SAYFALAR[kod].ac) SAYFALAR[kod].ac();
}

/** Sayfaya geçer ve adresi (#M1-S1) günceller; adres değiştirilemeyen ortamda da çalışır. */
function git(kod) {
  sayfaGoster(kod);
  try { history.replaceState(null, "", `#${kod}`); } catch (_) { /* ör. data: adresi */ }
}

window.addEventListener("hashchange", () => {
  const kod = location.hash.slice(1);
  if (kod && kod !== aktifSayfa) sayfaGoster(kod);
});

/* ================================================================ veri ve seçim deposu */

const Veri = {
  cihazlar: [],
  kimlikler: new Map(),   // id -> satır kimliği (LAB01)
  dinleyiciler: new Set(),
  bul(id) { return this.cihazlar.find((c) => c.id === id); },
  labler() { return [...new Set(this.cihazlar.map((c) => c.laboratuvar))].sort((a, b) => a.localeCompare(b, "tr")); },
};

async function cihazlariYukle() {
  try { Veri.cihazlar = await api("/api/cihazlar"); }
  catch (hata) { bildir(hata.message, true); return; }
  Veri.kimlikler = new Map();
  const kullanilan = new Map();
  for (const c of Veri.cihazlar) {
    let k = kimlikSlug(c.etiket || c.hostname || c.ip) || c.id.slice(0, 6).toUpperCase();
    if (kullanilan.has(k)) k = `${k}-${c.ip.split(".").pop()}`;
    kullanilan.set(k, c.id);
    Veri.kimlikler.set(c.id, k);
  }
  // envanterden çıkan kayıtlar seçimden de düşer
  for (const id of [...Secim.kume]) if (!Veri.bul(id)) Secim.kume.delete(id);
  const dl = $("#lab-listesi");
  if (dl) dl.replaceChildren(...Veri.labler().map((l) => el("option", { value: l })));
  Secim.bildir();
  Veri.dinleyiciler.forEach((f) => f());
}

function satirKimligi(c) { return Veri.kimlikler.get(c.id) || kimlikSlug(c.ip); }

const Secim = {
  kume: new Set(),
  lab: "",
  dinleyiciler: new Set(),
  sec(id, secili) {
    const c = Veri.bul(id);
    if (!c || c.korunan) return;        // korunan cihaz seçime giremez
    if (secili) this.kume.add(id); else this.kume.delete(id);
  },
  temizle() { this.kume.clear(); this.bildir(); },
  liste() { return [...this.kume].filter((id) => Veri.bul(id)); },
  bildir() {
    try { sessionStorage.setItem("psy-secim", JSON.stringify({ k: [...this.kume], l: this.lab })); } catch (_) { /* yok */ }
    const n = this.liste().length;
    const cip = $("#secim-cipi");
    if (cip) cip.firstChild.textContent = `${n} bilgisayar seçili`;
    this.dinleyiciler.forEach((f) => f());
  },
  yukle() {
    try {
      const k = JSON.parse(sessionStorage.getItem("psy-secim") || "null");
      if (k) { this.kume = new Set(k.k || []); this.lab = k.l || ""; }
    } catch (_) { /* yok */ }
  },
};

function labKapsami(c) { return !Secim.lab || c.laboratuvar === Secim.lab; }

/* ---- canlı erişim denemesi (yalnız TCP; kimlik bilgisi gönderilmez) ---- */
let erisimZamanlayici = null;
function erisimTazele(gecikme = 900) {
  clearTimeout(erisimZamanlayici);
  erisimZamanlayici = setTimeout(async () => {
    const simdi = Date.now();
    const adaylar = Secim.liste().filter((id) => {
      const c = Veri.bul(id);
      return c && (!c.erisim_zamani || simdi - new Date(c.erisim_zamani).getTime() > 60000);
    }).slice(0, 300);
    if (!adaylar.length) return;
    try {
      const sonuc = await api("/api/erisim", { cihazlar: adaylar });
      const zaman = new Date().toISOString();
      for (const [id, acik] of Object.entries(sonuc)) {
        const c = Veri.bul(id);
        if (c) { c.erisim = acik ? 1 : 0; c.erisim_zamani = zaman; }
      }
      Secim.dinleyiciler.forEach((f) => f());
    } catch (_) { /* sessiz: özet son bilinen durumla kalır */ }
  }, gecikme);
}

/* ================================================================ bilgisayar tablosu */

class CihazTablosu {
  /**
   * @param kap       kapsayıcı öğe
   * @param ayar      {islem, sutunlar: [{baslik, hucre(c) -> Node|metin}], ekFiltre(c), bosMetin}
   */
  constructor(kap, ayar) {
    this.kap = kap;
    this.ayar = ayar;
    this.arama = "";
    this.sayfaNo = 0;
    this.yalnizSecili = false;
    this.kip = ayar.kip || "tablo";        // "tablo" | "kutucuk" (ekran kutucukları)
    this.sayfaBoyu = this.kip === "kutucuk" ? 60 : 25;
    Secim.dinleyiciler.add(() => this.ciz());
    Veri.dinleyiciler.add(() => this.ciz());
  }

  uygunMu(c) { return !c.korunan && !c.uygunluk[this.ayar.islem]; }

  kipAyarla(kip) {
    this.kip = kip;
    this.sayfaBoyu = kip === "kutucuk" ? 60 : 25;
    this.sayfaNo = 0;
    this.ciz();
  }

  /** Ekran kutucukları (Veyon benzeri): her bilgisayar bir monitör, durum renk ve simgeyle. */
  izgara(gorunen) {
    if (!gorunen.length) return el("p", { class: "bos-tablo", metin: "Bu filtrede bilgisayar yok." });
    return el("div", { class: "pc-izgara", role: "list" }, ...gorunen.map((c) => pcKutucugu(c, {
      secili: Secim.kume.has(c.id), pasif: Boolean(c.uygunluk[this.ayar.islem]),
      ek: this.ayar.kutucukEk ? this.ayar.kutucukEk(c) : null })));
  }

  /** Laboratuvar + arama + ek filtre (sayfalama hariç) */
  filtreli() {
    const a = this.arama.trim().toLocaleLowerCase("tr-TR");
    return Veri.cihazlar.filter((c) => labKapsami(c)
      && (!a || [c.ad, c.ip, c.hostname, c.etiket, satirKimligi(c)].some((x) => (x || "").toLocaleLowerCase("tr-TR").includes(a)))
      && (!this.yalnizSecili || Secim.kume.has(c.id))
      && (!this.ayar.ekFiltre || this.ayar.ekFiltre(c)));
  }

  gorunen() {
    const f = this.filtreli();
    const enSon = Math.max(0, Math.ceil(f.length / this.sayfaBoyu) - 1);
    if (this.sayfaNo > enSon) this.sayfaNo = enSon;
    return f.slice(this.sayfaNo * this.sayfaBoyu, (this.sayfaNo + 1) * this.sayfaBoyu);
  }

  ciz() {
    const sayfa = this.kap.closest(".sayfa");
    if (!this.kap.isConnected || (sayfa && sayfa.hidden)) return;  // sayfa açılınca çizilir
    const odak = document.activeElement && document.activeElement.id === `${this.kap.id}-ara`;
    const filtreli = this.filtreli();
    const gorunen = this.gorunen();
    const ust = el("div", { class: "tablo-ust" },
      el("input", { type: "search", id: `${this.kap.id}-ara`, placeholder: "Ad, IP veya kimlik ara",
        value: this.arama, "data-ui-id": "M0-S2-B9", "aria-label": "Tabloda ara",
        oninput: (o) => { this.arama = o.target.value; this.sayfaNo = 0; this.ciz(); Secim.dinleyiciler.forEach((f) => f()); } }),
      el("label", { class: "onay-kutusu satir-ici" },
        el("input", { type: "checkbox", checked: this.yalnizSecili, "data-ui-id": "M0-S2-B10",
          onchange: (o) => { this.yalnizSecili = o.target.checked; this.sayfaNo = 0; this.ciz(); } }),
        "Yalnız seçilileri göster"),
      ...(this.ayar.ustEk ? this.ayar.ustEk() : []),
      el("span", { class: "bosluk" }),
      el("span", { class: "ipucu", metin: `${filtreli.length} kayıt` }));

    const secilebilir = gorunen.filter((c) => !c.korunan);
    const hepsi = secilebilir.length && secilebilir.every((c) => Secim.kume.has(c.id));
    const baslikKutusu = el("input", { type: "checkbox", "data-ui-id": "M0-S2-B4",
      "aria-label": "Görünen satırları seç", checked: Boolean(hepsi),
      onchange: (o) => { for (const c of secilebilir) Secim.sec(c.id, o.target.checked); Secim.bildir(); } });
    baslikKutusu.indeterminate = !hepsi && secilebilir.some((c) => Secim.kume.has(c.id));

    const tablo = el("table", {},
      el("thead", {}, el("tr", {}, el("th", { class: "sec" }, baslikKutusu),
        ...this.ayar.sutunlar.map((s) => el("th", { metin: s.baslik })))));
    const govde = el("tbody");
    for (const c of gorunen) {
      const secili = Secim.kume.has(c.id);
      const neden = c.uygunluk[this.ayar.islem];
      const kutu = el("input", { type: "checkbox", checked: secili, disabled: Boolean(c.korunan),
        "data-ui-id": `M0-S2-B5-${satirKimligi(c)}`, "aria-label": `${c.ad} seç`,
        title: c.korunan ? "Korunan cihaz (EBA/ETAP) seçilemez" : "",
        onchange: (o) => { Secim.sec(c.id, o.target.checked); Secim.bildir(); } });
      const tr = el("tr", { class: [secili ? "secili" : "", neden ? "pasif" : ""].join(" ").trim() },
        el("td", { class: "sec" }, kutu),
        ...this.ayar.sutunlar.map((s) => {
          const icerik = s.hucre(c);
          return el("td", {}, icerik instanceof Node ? icerik : String(icerik ?? "—"));
        }));
      govde.append(tr);
    }
    tablo.append(govde);

    const bas = filtreli.length ? this.sayfaNo * this.sayfaBoyu + 1 : 0;
    const son = Math.min(filtreli.length, (this.sayfaNo + 1) * this.sayfaBoyu);
    const alt = el("div", { class: "tablo-alt" },
      el("span", { metin: `${bas}–${son} / ${filtreli.length}` }),
      el("span", { class: "bosluk" }),
      dugme("‹ Önceki", "M0-S2-B7", () => { this.sayfaNo = Math.max(0, this.sayfaNo - 1); this.ciz(); }, "ikincil kucuk"),
      dugme("Sonraki ›", "M0-S2-B8", () => { this.sayfaNo += 1; this.ciz(); }, "ikincil kucuk"));
    $$("button", alt)[0].disabled = this.sayfaNo === 0;
    $$("button", alt)[1].disabled = son >= filtreli.length;

    const parcalar = [ust];
    if (!Veri.cihazlar.length) {
      parcalar.push(el("p", { class: "bos-tablo", metin: this.ayar.bosMetin
        || "Envanter boş. M1-S1'den bilgisayar ekleyin veya M1-S3 ile ağda bulun." }));
    } else {
      parcalar.push(this.kip === "kutucuk" ? this.izgara(gorunen) : tablo, alt);
    }
    this.kap.replaceChildren(...parcalar);
    if (odak) { const g = $(`#${this.kap.id}-ara`); g.focus(); g.setSelectionRange(g.value.length, g.value.length); }
  }
}

/* ================================================================ seçim çubuğu (M0-S2) */

function secimOzeti(islem, tablo) {
  const secili = Secim.liste().map((id) => Veri.bul(id));
  const disarida = secili.filter((c) => c.uygunluk[islem]);
  const uygun = secili.filter((c) => !c.uygunluk[islem]);
  const erisilemiyor = uygun.filter((c) => c.erisim === 0);
  const korunan = Veri.cihazlar.filter((c) => c.korunan && labKapsami(c)).length;
  const filtreDisi = tablo ? (() => { const f = new Set(tablo.filtreli().map((c) => c.id)); return secili.filter((c) => !f.has(c.id)).length; })() : 0;
  return { secili, disarida, uygun, erisilemiyor, korunan, filtreDisi };
}

function secimCubuguKur(kap, islem, tabloGetir) {
  const ozetYeri = el("div", { class: "secim-ozeti", role: "status" });
  const labSec = el("select", { "data-ui-id": "M0-S2-B6", "aria-label": "Laboratuvar",
    onchange: (o) => { Secim.lab = o.target.value; Secim.bildir(); } });
  const cubuk = el("div", { class: "secim-cubugu", "data-ui-id": "M0-S2" },
    el("label", { class: "satir-ici", metin: "Laboratuvar" }), labSec, ozetYeri,
    dugme("Görünen uygun bilgisayarları seç", "M0-S2-B1", () => {
      const t = tabloGetir();
      for (const c of t.gorunen()) if (t.uygunMu(c)) Secim.sec(c.id, true);
      Secim.bildir();
    }, "ikincil kucuk"),
    dugme("Laboratuvardaki tüm uygun bilgisayarları seç", "M0-S2-B2", () => {
      for (const c of Veri.cihazlar) if (labKapsami(c) && !c.korunan && !c.uygunluk[islem]) Secim.sec(c.id, true);
      Secim.bildir();
    }, "ikincil kucuk"),
    dugme("Seçimi temizle", "M0-S2-B3", () => Secim.temizle(), "ikincil kucuk"));
  kap.replaceChildren(cubuk);

  const guncelle = () => {
    if (!kap.isConnected) return;
    const labler = Veri.labler();
    const secenekler = [el("option", { value: "", metin: "Tüm laboratuvarlar" }),
      ...labler.map((l) => el("option", { value: l, metin: l }))];
    labSec.replaceChildren(...secenekler);
    labSec.value = labler.includes(Secim.lab) ? Secim.lab : "";
    const o = secimOzeti(islem, tabloGetir());
    const parcalar = [`${o.secili.length} bilgisayar seçili`];
    if (o.erisilemiyor.length) parcalar.push(`${o.erisilemiyor.length} erişilemiyor`);
    if (o.korunan) parcalar.push(`${o.korunan} korunan cihaz kapsam dışında`);
    if (o.disarida.length) parcalar.push(`${o.disarida.length} bu işlem için hazır değil`);
    ozetYeri.replaceChildren(parcalar.join(" — "));
    if (o.filtreDisi) ozetYeri.append(el("span", { class: "ek", metin: ` · ${o.filtreDisi} seçili bilgisayar filtre dışında (seçimde kalır)` }));
  };
  Secim.dinleyiciler.add(guncelle);
  Veri.dinleyiciler.add(guncelle);
  guncelle();
  return guncelle;
}

/* ================================================================ onay penceresi (M0-S3) */

/**
 * Kesin hedef listesini sunucudan alır ve gösterir. Onaylanırsa hedef kimliklerini
 * döndürür (iş bu listeyle başlar; sonradan değişen seçim işi etkilemez).
 */
async function onayIste({ islem, cihazlar, baslik, aciklama, uyarilar = [], yikici = false,
  onayMetni = null, baslatMetni = "Onayla ve başlat", ek = null, canli = true, hedefEk = null }) {
  let ozet;
  try { ozet = await api("/api/secim/ozet", { cihazlar, islem, canli }); }
  catch (hata) { bildir(hata.message, true); return null; }
  const p = $("#onay-penceresi");
  $("#onay-baslik").textContent = baslik;
  $("#onay-aciklama").textContent = aciklama || "";
  $("#onay-ek").replaceChildren(...(ek ? [ek] : []));
  $("#onay-hedef-baslik").textContent = `Hedefler — kesin liste (${ozet.hedefler.length} bilgisayar)`;
  const hedefTablo = el("table", {}, el("thead", {}, el("tr", {},
    ...["Bilgisayar", "IP", "Laboratuvar", ...(hedefEk ? [hedefEk.baslik] : [])].map((b) => el("th", { metin: b })))));
  const hb = el("tbody");
  for (const h of ozet.hedefler) {
    hb.append(el("tr", {}, el("td", { metin: h.ad }), el("td", { class: "mono", metin: h.ip }),
      el("td", { metin: h.laboratuvar || "—" }), ...(hedefEk ? [el("td", {}, hedefEk.hucre(h))] : [])));
  }
  hedefTablo.append(hb);
  $("#onay-hedefler").replaceChildren(ozet.hedefler.length ? hedefTablo
    : el("p", { class: "bos-tablo", metin: "Uygun hedef yok; işlem başlatılamaz." }));
  const disarida = [...ozet.erisilemeyen, ...ozet.kapsam_disi];
  $("#onay-disarida-kap").hidden = !disarida.length;
  $("#onay-disarida-baslik").textContent = `Kapsam dışı (${disarida.length}) — bu bilgisayarlara dokunulmaz`;
  const dt = el("table", {}, el("thead", {}, el("tr", {}, el("th", { metin: "Bilgisayar" }), el("th", { metin: "Neden" }))));
  const db = el("tbody");
  for (const d of disarida) db.append(el("tr", {}, el("td", { metin: d.ad }), el("td", { metin: d.neden })));
  dt.append(db);
  $("#onay-disarida").replaceChildren(dt);
  $("#onay-uyarilar").replaceChildren(...uyarilar.map((u) => el("li", { metin: u })));
  const kutu = $("#onay-kutu");
  kutu.checked = false;
  $("#onay-kutu-etiket").hidden = !yikici;
  $("#onay-kutu-metin").textContent = onayMetni || "Yukarıdakileri okudum; işlemi onaylıyorum";
  const baslat = $("#onay-baslat");
  baslat.firstChild.textContent = baslatMetni;
  const durumGuncelle = () => { baslat.disabled = !ozet.hedefler.length || (yikici && !kutu.checked); };
  kutu.onchange = durumGuncelle;
  durumGuncelle();
  p.returnValue = "";
  p.showModal();
  return new Promise((coz) => {
    p.addEventListener("close", () => {
      coz(p.returnValue === "baslat" && !baslat.disabled ? ozet.hedefler.map((h) => h.id) : null);
    }, { once: true });
  });
}

/* ================================================================ seçim listesi (M0-S5) */

function secimListesiAc() {
  const liste = Secim.liste().map((id) => Veri.bul(id));
  $("#secim-penceresi-ozet").textContent = liste.length
    ? `${liste.length} bilgisayar seçili. Seçim sayfalar arasında korunur.`
    : "Henüz bilgisayar seçilmedi.";
  const tablo = el("table", {}, el("thead", {}, el("tr", {},
    ...["Bilgisayar", "IP", "Laboratuvar", ""].map((b) => el("th", { metin: b })))));
  const govde = el("tbody");
  for (const c of liste) {
    govde.append(el("tr", {}, el("td", { metin: c.ad }), el("td", { class: "mono", metin: c.ip }),
      el("td", { metin: c.laboratuvar }),
      el("td", {}, dugme("Seçimden çıkar", `M0-S5-B2-${satirKimligi(c)}`, (o) => {
        Secim.sec(c.id, false); Secim.bildir(); o.currentTarget.closest("tr").remove();
      }, "ikincil kucuk"))));
  }
  tablo.append(govde);
  $("#secim-penceresi-liste").replaceChildren(...(liste.length ? [tablo] : []));
  $("#secim-penceresi").showModal();
}

/* ================================================================ iş durumu paneli (M0-S4) */

const IS_ADLARI = {
  kesif: "Ağ taraması", durum: "Durum kontrolü", kimlik_oku: "Sunucu kimliği okuma",
  hazirlik: "SSH ve hesap hazırlığı", tekillestirme_onizleme: "Tekilleştirme önizlemesi",
  tekillestirme: "Hesap tekilleştirme", temizlik_onizleme: "Temizlik önizlemesi",
  temizlik: "Ders sonu temizliği", sifirlama_onizleme: "Sıfırlama önizlemesi",
  profil_sifirla: "Profil sıfırlama", oturum_kapat: "Öğrenci oturumu kapatma",
  yedek: "Kullanıcı yedekleme", geri_yukle: "Yedekten dönüş",
  paket_plan: "Paket kurulum planı", paket_kur: "Paket kurulumu",
  gorunum_onizleme: "Görünüm önizlemesi", gorunum: "Görünüm ve giriş",
  guc_yeniden_baslat: "Yeniden başlatma", guc_kapat: "Kapatma",
  envanterden_cikar: "Envanterden çıkarma",
  veyon_surum: "Veyon sürümlerini yenileme", veyon_plan: "Veyon önizlemesi / hazırlık kontrolü",
  veyon_uygula: "Veyon kurulum ve yapılandırma", veyon_dogrula: "Veyon bağlantı doğrulaması",
  veyon_geri_al: "Veyon ayarlarını geri yükleme",
  uyku_onizleme: "Güç ayarı önizlemesi", uyku_ayari: "Uyku modunu kapatma", uyku_varsayilan: "Varsayılan güç ayarına dönüş",
  kapatma_oku: "Kapatma planlarını okuma", kapatma_ekle: "Zamanlı kapatma planı ekleme",
  kapatma_sil: "Zamanlı kapatma planı kaldırma", kapatma_iptal: "Bekleyen kapatmayı iptal",
  sinif_ekran_kilitle: "Öğrenci ekranlarını kilitleme", sinif_ekran_ac: "Ekran kilitlerini açma",
  sinif_duyuru: "Sınıf duyurusu gönderme", sinif_internet_kisitla: "İnternet erişimini kısıtlama",
  sinif_internet_ac: "İnternet erişimini açma", sinif_masaustu_url: "Masaüstüne web kısayolu dağıtma",
  sinif_masaustu_dosya: "Masaüstüne ders materyali dağıtma",
  ssh_komut: "SSH bash komutu çalıştırma", hosts_ekle: "/etc/hosts adres kaydı dağıtma",
};
const HEDEF_ROZETI = { basarili: ["✓", "iyi"], basarisiz: ["✗", "kotu"], atlandi: ["→", "notr"] };

let izlenen = null;
let sonIs = null;

function isIzle(isId, { bitince } = {}) {
  sonIs = isId;
  return new Promise((coz) => {
    if (izlenen) clearInterval(izlenen.zamanlayici);
    izlenen = { id: isId, bitince, coz, zamanlayici: setInterval(() => isGuncelle(), 1200) };
    $("#is-paneli").hidden = false;
    isGuncelle();
  });
}

async function isGuncelle() {
  if (!izlenen) return;
  const takip = izlenen;
  let kayit;
  try { kayit = await api(`/api/isler/${takip.id}`); }
  catch (hata) { bildir(hata.message, true); clearInterval(takip.zamanlayici); return; }
  if (izlenen !== takip) return;
  const toplam = kayit.hedefler.length || 1;
  const bitmis = kayit.hedefler.filter((h) => !["bekliyor", "calisiyor"].includes(h.durum)).length;
  const say = (d) => kayit.hedefler.filter((h) => h.durum === d).length;
  $("#is-paneli-baslik").textContent = `${IS_ADLARI[kayit.tip] || kayit.tip} — ${
    { calisiyor: "sürüyor", tamamlandi: "bitti", iptal: "iptal edildi", hata: "hata", kesildi: "kesildi" }[kayit.durum] || kayit.durum}`;
  $("#is-paneli-sayac").textContent =
    `${bitmis}/${kayit.hedefler.length} · ✓ ${say("basarili")} · ✗ ${say("basarisiz")} · → ${say("atlandi")}`;
  $("#is-paneli-cubuk").style.width = `${Math.round((bitmis / toplam) * 100)}%`;
  $("#is-paneli-iptal").hidden = kayit.durum !== "calisiyor";
  const g = $("#is-gostergesi");
  g.hidden = kayit.durum !== "calisiyor";
  g.textContent = `İş sürüyor: ${bitmis}/${kayit.hedefler.length}`;
  const liste = $("#is-paneli-liste");
  liste.replaceChildren(...kayit.hedefler.filter((h) => h.durum !== "bekliyor").slice(-40).map((h) => {
    const [isaret, ton] = HEDEF_ROZETI[h.durum] || ["•", "mavi"];
    return el("li", {}, h.durum === "calisiyor" ? el("span", { class: "donen" }) : rozet(isaret, ton),
      el("span", { metin: h.mesaj || `${h.hedef} — ${h.asama || h.durum}` }));
  }));
  if (kayit.durum !== "calisiyor") {
    clearInterval(takip.zamanlayici);
    izlenen = null;
    await cihazlariYukle();
    if (takip.bitince) takip.bitince(kayit);
    takip.coz(kayit);
  }
}

/** İşi başlatan API çağrısını yapar, paneli açar ve bitişi bekler. */
async function isBaslat(yol, govde, bitince) {
  let yanit;
  try { yanit = await api(yol, govde); }
  catch (hata) { bildir(hata.message, true); return null; }
  return isIzle(yanit.is_id, { bitince });
}

/* ================================================================ küçük ortak parçalar */

function ozetKarti(sayi, etiket, not = null, vurgu = false) {
  return el("div", { class: `ozet-kart${vurgu ? " vurgu" : ""}` },
    el("span", { class: "sayi", metin: sayi }), el("span", { class: "etiket", metin: etiket }),
    not ? el("span", { class: "not", metin: not }) : null);
}

function evetHayir(deger, evet, hayir, bilinmiyor = "?") {
  if (deger === 1 || deger === true) return rozet(evet[0], evet[1]);
  if (deger === 0 || deger === false) return rozet(hayir[0], hayir[1]);
  return rozet(bilinmiyor, "notr");
}

function cihazHucresi(c) {
  const adDugme = el("button", {
    type: "button",
    class: "cihaz-ad-link",
    metin: c.ad,
    title: `${c.ad} özelliklerini ve durumunu görüntüle`,
    onclick: (e) => {
      e.stopPropagation();
      cihazOzetPenceresi(c);
    }
  });
  return el("div", {},
    adDugme,
    el("span", { class: "alt mono", metin: c.ssh_port === 22 ? c.ip : `${c.ip}:${c.ssh_port}` }),
    c.korunan ? rozet("Korunan", "orta") : null,
    c.yinelenen_kimlik ? rozet("Klon kimlik!", "orta") : null);
}

/* ---- Veyon sürümü: M1-S1 ve M1-S4 aynı merkezi envanter verisini aynı biçimde gösterir ---- */

const VEYON_DURUMU = {
  kurulu: ["Kurulu", "iyi"], kurulu_degil: ["Kurulu değil", "notr"], kontrol_edilmedi: ["Henüz kontrol edilmedi", "notr"],
  erisilemiyor: ["Erişilemiyor", "kotu"], okunamadi: ["Sürüm okunamadı", "orta"], hatali: ["Kurulum hatalı veya yarım", "kotu"],
};
const VEYON_KARSILASTIRMA = {
  eski: ["Seçili paketten eski", "orta"], ayni: ["Seçili paketle aynı sürüm", "mavi"],
  yeni: ["Seçili paketten yeni", "notr"],
};
const VEYON_FILTRELERI = [["", "Tümü"], ["kurulu_degil", "Kurulu değil"], ["eski", "Seçili paketten eski"],
  ["ayni", "Seçili paketle aynı sürüm"], ["yeni", "Seçili paketten yeni"], ["bilinmiyor", "Durumu bilinmiyor"]];

function veyonFiltresi(c, deger) {
  if (!deger) return true;
  const k = (c.veyon || {}).karsilastirma;
  if (deger === "bilinmiyor") return k === "bilinmiyor";
  return k === deger;
}

function veyonHucresi(c, ayrintili = false) {
  const v = c.veyon || { durum: "kontrol_edilmedi" };
  const [m, t] = VEYON_DURUMU[v.durum] || [v.durum, "notr"];
  const kap = el("div", { class: "veyon-hucre" });
  if (v.durum === "kurulu" || v.durum === "hatali") {
    kap.append(el("span", { class: "mono surum-metni", metin: v.surum || "?" }));
    if (v.durum === "hatali") kap.append(" ", rozet(m, t));
  } else if (v.durum === "erisilemiyor") {
    kap.append(rozet(m, t));
    if (v.son_bilinen === "kurulu" && v.surum) {
      kap.append(el("span", { class: "alt", metin: `son bilinen: ${v.surum} · ${goreliZaman(v.zaman)} · eski bilgi` }));
    } else if (v.son_bilinen) {
      kap.append(el("span", { class: "alt", metin: `son bilinen: ${(VEYON_DURUMU[v.son_bilinen] || [v.son_bilinen])[0]} · ${goreliZaman(v.zaman)} · eski bilgi` }));
    }
    return kap;
  } else {
    kap.append(rozet(m, t));
  }
  const k = VEYON_KARSILASTIRMA[v.karsilastirma];
  if (k && v.durum === "kurulu") kap.append(" ", rozet(k[0], k[1]));
  if (ayrintili && v.zaman) kap.append(el("span", { class: "alt", metin: `okundu: ${goreliZaman(v.zaman)}` }));
  return kap;
}

function veyonServisHucresi(c) {
  const v = c.veyon || {};
  const y = v.yapilandirma;
  if (!y || v.durum !== "kurulu") return "—";
  const s = y.servis || {};
  return el("div", {}, s.calisiyor ? rozet("Çalışıyor", "iyi") : rozet(s.etkin ? "Durmuş" : "Kapalı", "orta"),
    s.etkin === false ? el("span", { class: "alt", metin: "açılışta başlamaz" }) : null);
}

function veyonYapilandirmaHucresi(c) {
  const v = c.veyon || {};
  const y = v.yapilandirma;
  if (!y || v.durum !== "kurulu") return "—";
  const yontem = y.yontem === 1 ? "anahtar dosyası" : y.yontem === 0 ? "oturum parolası" : "ayarlanmamış";
  const anahtar = { eslesiyor: ["Anahtar eşleşiyor", "iyi"], farkli: ["Anahtar FARKLI", "kotu"], yok: ["Anahtar yok", "orta"] }[y.eslesme];
  return el("div", {}, anahtar ? rozet(anahtar[0], anahtar[1]) : rozet("Anahtar yüklenmedi", "notr"),
    el("span", { class: "alt", metin: `yöntem: ${yontem}` }));
}

function uygunlukHucresi(c, islem) {
  const neden = c.uygunluk[islem];
  if (neden) return el("span", { class: "alt", metin: neden });
  if (c.erisim === 0) return rozet("Erişilemiyor", "kotu");
  return rozet("Uygun", "iyi");
}

/* ================================================================ bilgisayar durumu (görsel) */

/** Tek, öncelikli durum: kutucuk rengi/simgesi, durum göstergesi ve M1-S2 için ortak. */
const PC_DURUMLARI = [
  ["korunan", "Korunan (EBA/ETAP)", "mor", "kalkan", "Hiçbir işleme dahil edilmez"],
  ["kapali", "Kapalı / erişilemiyor", "kapali", "ekran_kapali", "Son denemede ağdan ulaşılamadı (kapalı olabilir)"],
  ["taninmadi", "Henüz tanınmadı", "soluk", "soru", "Kimliği okunmadı (M1-S2 adım 1)"],
  ["onay", "Kimlik onayı bekliyor", "mavi", "kimlik", "Okunan kimliği onaylayın (M1-S2 adım 1)"],
  ["anahtar", "SSH anahtarı yok", "orta", "anahtar", "Yönetime bağlanmamış (M1-S2 adım 2)"],
  ["yetki", "Yönetim yetkisi yok", "orta", "kilit", "Parolasız yetki hazır değil (M1-S2 adım 2)"],
  ["ogrenci_yok", "Öğrenci hesabı yok", "orta", "kisi_yok", "ogrenci hesabı oluşturulmalı (M1-S2 adım 2)"],
  ["iki_hesap", "İki yönetici hesabı", "sari", "kisiler", "hp ve pardus birlikte (M1-S2 adım 3)"],
  ["oturum", "Hazır — öğrenci çalışıyor", "iyi", "kisi", "Öğrenci oturumu açık"],
  ["bilinmiyor", "Hazır — durum okunmadı", "iyi-soluk", "soru", "Durumu kontrol edin (M1-S1-B3)"],
  ["hazir", "Hazır", "iyi", "tamam", "Tüm işlemlere hazır"],
];
const PC_DURUM = Object.fromEntries(PC_DURUMLARI.map(([k, ad, ton, ikonAdi, aciklama]) => [k, { kod: k, ad, ton, ikon: ikonAdi, aciklama }]));

function pcDurumu(c) {
  let k = "hazir";
  if (c.korunan) k = "korunan";
  else if (c.erisim === 0) k = "kapali";
  else if (!c.parmak_izi) k = "taninmadi";
  else if (!c.parmak_izi_onay) k = "onay";
  else if (c.anahtar_durumu !== "ok") k = "anahtar";
  else if (c.sudo_durumu !== "parolasiz") k = "yetki";
  else if (c.profil_var === 0) k = "ogrenci_yok";
  else if ((c.yonetim_hesaplari || []).length > 1) k = "iki_hesap";
  else if (c.ogrenci_oturumu === 1) k = "oturum";
  else if (!c.son_kontrol) k = "bilinmiyor";
  return PC_DURUM[k];
}

/** Monitör çizimi: ekran rengi duruma göre, ortasında durum simgesi. */
function pcEkrani(durum) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 64 52");
  svg.setAttribute("class", `pc-ekran ton-${durum.ton}`);
  svg.setAttribute("aria-hidden", "true");
  const sekil = (ad, ozellik) => { const n = document.createElementNS(ns, ad); for (const [k, v] of Object.entries(ozellik)) n.setAttribute(k, v); svg.append(n); return n; };
  sekil("rect", { x: 3, y: 3, width: 58, height: 37, rx: 4, class: "kasa" });
  sekil("rect", { x: 6.5, y: 6.5, width: 51, height: 30, rx: 2, class: "ekran" });
  sekil("path", { d: "M26 40h12l2 6H24z", class: "ayak" });
  sekil("rect", { x: 19, y: 45.5, width: 26, height: 3, rx: 1.5, class: "ayak" });
  const g = sekil("g", { transform: "translate(22.5 12) scale(0.8)", class: "isaret" });
  const yol = document.createElementNS(ns, "path");
  yol.setAttribute("d", IKONLAR[durum.ikon] || IKONLAR.soru);
  g.append(yol);
  return svg;
}

/** Bir bilgisayar kutucuğu: tıklayınca seçilir (korunan seçilemez). */
function pcKutucugu(c, { secili = false, pasif = false, ek = null } = {}) {
  const d = pcDurumu(c);
  const kutu = el("input", { type: "checkbox", checked: secili, disabled: Boolean(c.korunan),
    "data-ui-id": `M0-S2-B5-${satirKimligi(c)}`, "aria-label": `${c.ad} seç`,
    onchange: (o) => { Secim.sec(c.id, o.target.checked); Secim.bildir(); } });
  const rozetler = el("div", { class: "pc-rozetler" });
  const v = c.veyon || {};
  if (v.durum === "kurulu") rozetler.append(el("span", { class: "mini", title: `Veyon ${v.surum}`, metin: `Veyon ${String(v.surum || "").split(/[-+]/)[0]}` }));
  const g = c.guc_durumu;
  if (g && g.uyku_kapali) rozetler.append(el("span", { class: "mini iyi", title: "Uyku kapalı: boşta uykuya geçmez" }, ikon("ay", "ikon mini-ikon"), "uyku yok"));
  else if (g && g.uyku_kapali === false) rozetler.append(el("span", { class: "mini orta", title: "Uyku açık: boşta uykuya geçip erişilemez olabilir (M2-S4)" }, ikon("ay", "ikon mini-ikon"), "uyku açık"));
  if (g && g.planlar && g.planlar.length) rozetler.append(el("span", { class: "mini", title: g.planlar.map((p) => p.etiket).join(" · ") }, ikon("saat", "ikon mini-ikon"), String(g.planlar.length)));
  if (c.yinelenen_kimlik) rozetler.append(el("span", { class: "mini kotu", metin: "klon kimlik!" }));

  const ekranGorseli = pcEkrani(d);
  ekranGorseli.classList.add("pc-ekran-tiklanabilir");
  ekranGorseli.setAttribute("role", "button");
  ekranGorseli.setAttribute("tabindex", "0");
  ekranGorseli.title = `${c.ad} özelliklerini ve durumunu açmak için tıklayın`;
  ekranGorseli.onclick = (e) => {
    e.stopPropagation();
    cihazOzetPenceresi(c);
  };
  ekranGorseli.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.stopPropagation();
      e.preventDefault();
      cihazOzetPenceresi(c);
    }
  };

  const adMetni = el("strong", { class: "pc-ad", metin: c.ad, title: c.ad });

  const kart = el("div", { class: `pc-kutu ton-${d.ton}${secili ? " secili" : ""}${pasif ? " pasif" : ""}`, role: "listitem",
    title: `${c.ad} — ${d.ad}: ${d.aciklama}`,
    onclick: (o) => { if (c.korunan || o.target.closest("button, a, input, label, svg")) return; kutu.checked = !kutu.checked; kutu.dispatchEvent(new Event("change")); } },
  el("label", { class: "pc-sec" }, kutu),
  ekranGorseli,
  adMetni,
  el("span", { class: "pc-ip mono", metin: c.ssh_port === 22 ? c.ip : `${c.ip}:${c.ssh_port}` }),
  el("span", { class: "pc-durum", metin: d.ad }),
  rozetler,
  ek);
  return kart;
}

/* ================================================================ Bilgisayar Detay Özeti Açılır Penceresi */

let seciliOzetCihaz = null;

function cihazOzetPenceresi(c) {
  if (!c) return;
  seciliOzetCihaz = c;
  const d = pcDurumu(c);

  const elAd = $("#co-ad");
  if (elAd) elAd.textContent = c.ad || c.hostname || c.ip;

  const elIp = $("#co-ip");
  if (elIp) elIp.textContent = c.ssh_port === 22 ? c.ip : `${c.ip}:${c.ssh_port}`;

  const elDurum = $("#co-durum");
  if (elDurum) {
    elDurum.replaceChildren(rozet(d.ad, d.ton));
  }

  const elLab = $("#co-lab");
  if (elLab) elLab.textContent = c.grup || "Laboratuvar";

  const elHesap = $("#co-hesap");
  if (elHesap) elHesap.textContent = c.baglanti_hesabi || "Otomatik (pardus/hp)";

  const elPort = $("#co-port");
  if (elPort) elPort.textContent = String(c.ssh_port || 22);

  const elSurum = $("#co-surum");
  if (elSurum) {
    const parcalar = [c.pardus_surum ? `Pardus ${c.pardus_surum}` : "Pardus", c.masaustu].filter(Boolean);
    elSurum.textContent = parcalar.join(" · ") || "Pardus";
  }

  const elVeyon = $("#co-veyon");
  if (elVeyon) {
    const v = c.veyon || {};
    if (v.durum === "kurulu") {
      elVeyon.replaceChildren(rozet(`Kurulu (v${String(v.surum || "").split(/[-+]/)[0]})`, "iyi"));
    } else if (v.durum === "kurulu_degil") {
      elVeyon.replaceChildren(rozet("Kurulu değil", "notr"));
    } else {
      elVeyon.replaceChildren(rozet(v.durum || "Bilinmiyor", "orta"));
    }
  }

  const elOturum = $("#co-oturum");
  if (elOturum) {
    elOturum.textContent = c.ogrenci_oturumu === 1 ? "👤 Öğrenci oturumu açık" : "🔒 Kapalı / kilitli";
  }

  const elGuc = $("#co-guc");
  if (elGuc) {
    const g = c.guc_durumu || {};
    if (g.uyku_kapali) elGuc.textContent = "Uyku kapalı (boşta kapanmaz)";
    else if (g.uyku_kapali === false) elGuc.textContent = "Uyku açık (boşta uyuyabilir)";
    else elGuc.textContent = "Standart";
  }

  const elAciklama = $("#co-aciklama");
  if (elAciklama) elAciklama.textContent = d.aciklama || "—";

  const elUyariKutu = $("#co-uyari-kutu");
  const elUyari = $("#co-uyari");
  if (elUyariKutu && elUyari) {
    const uyarilar = [];
    if (c.korunan) uyarilar.push("🛡️ Korunan cihaz (EBA/ETAP) — yönetim dışı");
    if (c.yinelenen_kimlik) uyarilar.push("⚠️ Klon kimlik (aynı host anahtarı birden çok cihazda)");
    if (c.ogrenci_sudo) uyarilar.push("⚠️ Öğrenci hesabı sudo grubunda!");
    if (uyarilar.length) {
      elUyari.replaceChildren(...uyarilar.map((m) => el("div", { metin: m })));
      elUyariKutu.hidden = false;
    } else {
      elUyariKutu.hidden = true;
    }
  }

  const secBtn = $("#co-sec-dugme");
  if (secBtn) {
    const secili = Secim.kume.has(c.id);
    secBtn.textContent = secili ? "Seçimi Bırak" : "Bu Bilgisayarı Seç";
    secBtn.disabled = Boolean(c.korunan);
  }

  const dlg = $("#cihaz-ozet-penceresi");
  if (dlg && typeof dlg.showModal === "function") {
    dlg.showModal();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const secBtn = $("#co-sec-dugme");
  if (secBtn) {
    secBtn.addEventListener("click", () => {
      if (seciliOzetCihaz && !seciliOzetCihaz.korunan) {
        const yeniDurum = !Secim.kume.has(seciliOzetCihaz.id);
        Secim.sec(seciliOzetCihaz.id, yeniDurum);
        Secim.bildir();
        const dlg = $("#cihaz-ozet-penceresi");
        if (dlg) dlg.close();
      }
    });
  }

  const duzenleBtn = $("#co-duzenle-dugme");
  if (duzenleBtn) {
    duzenleBtn.addEventListener("click", () => {
      const hedef = seciliOzetCihaz;
      const dlg = $("#cihaz-ozet-penceresi");
      if (dlg) dlg.close();
      if (hedef && typeof cihazPenceresi === "function") {
        cihazPenceresi(hedef);
      } else if (hedef) {
        git("M1-S1");
        setTimeout(() => {
          if (typeof cihazPenceresi === "function") cihazPenceresi(hedef);
        }, 120);
      }
    });
  }
});
