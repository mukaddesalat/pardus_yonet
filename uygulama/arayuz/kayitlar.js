/* M4 Kayıtlar (S1 İşlem Geçmişi) ve M5 Ayarlar (S1 Uygulama Ayarları ve Referans Rehberi). */
"use strict";

const IS_DURUMU = {
  calisiyor: ["Sürüyor", "mavi"], tamamlandi: ["Bitti", "iyi"], iptal: ["İptal", "notr"],
  hata: ["Hata", "kotu"], kesildi: ["Kesildi", "orta"],
};

const m4s1 = {
  isler: [],
  secili: null,
  kur() {
    $("#m4s1-yenile").addEventListener("click", () => this.yukle());
    $("#m4s1-tur").addEventListener("change", () => this.ciz());
    const tur = $("#m4s1-tur");
    for (const [kod, ad] of Object.entries(IS_ADLARI)) tur.append(el("option", { value: kod, metin: ad }));
  },
  ac() { this.yukle(); },
  async yukle() {
    try { this.isler = await api("/api/isler"); } catch (hata) { bildir(hata.message, true); return; }
    this.ciz();
    if (this.secili) this.ayrinti(this.secili);
  },
  ciz() {
    const filtre = $("#m4s1-tur").value;
    const liste = this.isler.filter((i) => !filtre || i.tip === filtre);
    if (!liste.length) { $("#m4s1-liste").replaceChildren(el("p", { class: "bos-tablo", metin: "Kayıt yok." })); return; }
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["İşlem", "Öğretmen", "Durum", "Başlangıç", ""].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const i of liste) {
      const [m, t] = IS_DURUMU[i.durum] || [i.durum, "notr"];
      const ogrEtiket = i.ogretmen_ad || i.ogretmen_kullanici || "—";
      g.append(el("tr", { class: i.id === this.secili ? "secili" : "" },
        el("td", {}, el("strong", { metin: IS_ADLARI[i.tip] || i.tip }), i.ozet ? el("span", { class: "alt", metin: i.ozet }) : null),
        el("td", {}, el("span", { metin: ogrEtiket }), i.ogretmen_rol ? el("span", { class: "alt", metin: i.ogretmen_rol === "admin" ? "Admin" : "Standart" }) : null),
        el("td", {}, rozet(m, t)), el("td", { metin: tarih(i.baslangic) }),
        el("td", {}, dugme("Ayrıntı", `M4-S1-B2-${kimlikSlug(i.id).slice(0, 6)}`, () => this.ayrinti(i.id), "ikincil kucuk"))));
    }
    tablo.append(g);
    $("#m4s1-liste").replaceChildren(tablo);
  },
  async ayrinti(isId) {
    this.secili = isId;
    let k;
    try { k = await api(`/api/isler/${isId}`); } catch (hata) { bildir(hata.message, true); return; }
    this.ciz();
    const [m, t] = IS_DURUMU[k.durum] || [k.durum, "notr"];
    const hedefOzeti = (k.parametreler && k.parametreler.hedefler) || [];
    const say = (d) => k.hedefler.filter((h) => h.durum === d).length;
    const kap = $("#m4s1-ayrinti");
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["Hedef", "Sonuç", "Aşama", "Mesaj"].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const h of k.hedefler) {
      const [hm, ht] = HEDEF_ROZETI[h.durum] || ["…", "mavi"];
      g.append(el("tr", {}, el("td", { class: "mono", metin: h.hedef }), el("td", {}, rozet(hm, ht)),
        el("td", { metin: h.asama || "—" }), el("td", { metin: h.mesaj || "" })));
    }
    tablo.append(g);
    const ogrMetin = k.ogretmen_ad || k.ogretmen_kullanici
      ? ` · Öğretmen: ${k.ogretmen_ad || k.ogretmen_kullanici} (${k.ogretmen_rol === "admin" ? "Admin" : "Standart"})`
      : "";
    kap.replaceChildren(...[
      el("h2", {}, IS_ADLARI[k.tip] || k.tip, " ", rozet(m, t)),
      el("p", { class: "ipucu", metin: `Başlangıç: ${tarih(k.baslangic)} · Bitiş: ${tarih(k.bitis)}${ogrMetin} · ✓ ${say("basarili")} · ✗ ${say("basarisiz")} · → ${say("atlandi")}` }),
      hedefOzeti.length ? el("p", { class: "ipucu", metin: `Başladığı andaki kesin hedef listesi (${hedefOzeti.length}): ${hedefOzeti.map((h) => h.ad).join(", ")}` }) : null,
      k.ozet ? el("p", { metin: k.ozet }) : null,
      el("div", { class: "arac-cubugu" },
        dugme("Sonuçları CSV indir", "M4-S1-B3", () => indir(`/api/isler/${k.id}/csv`)),
        k.durum === "calisiyor" ? dugme("Çalışan işi iptal et", "M4-S1-B4", async () => {
          try { const s = await api(`/api/isler/${k.id}/iptal`, {}); bildir(s.not); } catch (hata) { bildir(hata.message, true); }
        }, "tehlikeli") : null),
      el("div", { class: "tablo-kap" }, tablo)].filter(Boolean));
  },
};

/* ================================================================ M5-S1 */

function referansSatirlari() {
  const satirlar = [];
  for (const m of REF.menuler) {
    satirlar.push({ kod: m.kod, ad: m.ad, islev: m.ortak ? "Her sayfada kullanılan ortak araçlar" : "Menü", tur: "menu" });
    for (const s of m.sayfalar) {
      const kod = `${m.kod}-${s.kod}`;
      satirlar.push({ kod, ad: s.ad, islev: s.aciklama || "", tur: "sayfa" });
      for (const [bk, [ad, islev]] of Object.entries(REF.dugmeler)) {
        if (bk.startsWith(`${kod}-B`)) satirlar.push({ kod: bk.replace(/-\*$/, "-<kimlik>"), ad, islev, tur: "dugme" });
      }
    }
  }
  return satirlar;
}

const m5s1 = {
  kur() {
    $("#m5s1-saklama-formu").addEventListener("submit", async (o) => {
      o.preventDefault();
      try {
        const s = await api("/api/ayarlar", { saklama_adedi: Number($("#m5s1-saklama").value) });
        bildir(`Her bilgisayarda en fazla ${s.saklama_adedi} yedek/karantina kaydı tutulacak.`);
      } catch (hata) { bildir(hata.message, true); }
    });
    $("#m5s1-kodlar").addEventListener("click", () => kodlariGoster(!kodlarGorunur()));
    $("#m5s1-ara").addEventListener("input", () => this.rehber());
    $("#m5s1-indir").addEventListener("click", () => this.markdown());
  },
  async ac() {
    this.rehber();
    try {
      const a = await api("/api/ayarlar");
      $("#m5s1-saklama").value = a.saklama_adedi;
      $("#m5s1-surum").textContent = `Sürüm ${a.versiyon} · ödev arşivi: ${a.odev_dizini} (temizlik ve sıfırlama bu dizine hiçbir zaman dokunmaz)`;
    } catch (hata) { bildir(hata.message, true); }
  },
  rehber() {
    const a = $("#m5s1-ara").value.trim().toLocaleLowerCase("tr-TR");
    const satirlar = referansSatirlari().filter((s) => !a || `${s.kod} ${s.ad} ${s.islev}`.toLocaleLowerCase("tr-TR").includes(a));
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["Kod", "Ad", "İşlev"].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const s of satirlar) {
      g.append(el("tr", { class: s.tur === "menu" ? "rehber-menu" : "" },
        el("td", {}, el("span", { class: "kod-cip", metin: s.kod })), el("td", { metin: s.tur === "sayfa" ? `  ${s.ad}` : s.ad }),
        el("td", { metin: s.islev })));
    }
    tablo.append(g);
    const emekli = Object.entries(REF.emekli || {});
    $("#m5s1-rehber").replaceChildren(tablo, ...(emekli.length ? [el("p", { class: "ipucu",
      metin: `Emekli kodlar (bir daha kullanılmaz): ${emekli.map(([k, n]) => `${k} (${n})`).join(", ")}` })] : []));
  },
  markdown() {
    const satirlar = ["# Pardus Sınıf Yönetimi — arayüz referans haritası", "",
      `Sürüm ${REF.surum}. M = menü, S = sayfa, B = düğme. Satır düğmeleri bilgisayar kimliğiyle biter (M2-S1-B4-LAB01).`, "",
      "| Kod | Ad | İşlev |", "| --- | --- | --- |",
      ...referansSatirlari().map((s) => `| ${s.kod} | ${s.ad} | ${s.islev.replace(/\|/g, "/")} |`), ""];
    const blob = new Blob([satirlar.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: "arayuz-referans-haritasi.md" });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  },
};

/* ================================================================ M5-S2 Okul ve Öğretmenler */

let duzenlenenOgretmen = null;

const HAZIR_ARMALAR = {
  meb: "data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
    '<circle cx="32" cy="32" r="30" fill="#1B5FC1" stroke="#93C5FD" stroke-width="2.5"/>' +
    '<path d="M32 12L14 21v12c0 11.5 7.7 21.8 18 25 10.3-3.2 18-13.5 18-25V21L32 12z" fill="#0F2A56"/>' +
    '<path d="M22 36c4-2 8-2 10 0 2-2 6-2 10 0V24c-4-2-8-2-10 0-2-2-6-2-10 0v12z" fill="#FFFFFF"/>' +
    '<circle cx="32" cy="19" r="2.5" fill="#FBBF24"/></svg>'
  ),
  pardus: "data:image/svg+xml;utf8," + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
    '<rect width="64" height="64" rx="14" fill="#0F172A"/>' +
    '<circle cx="32" cy="32" r="22" fill="#F59E0B"/>' +
    '<circle cx="24" cy="27" r="3" fill="#0F172A"/>' +
    '<circle cx="40" cy="27" r="3" fill="#0F172A"/>' +
    '<path d="M24 39c3 4 13 4 16 0" stroke="#0F172A" stroke-width="3" fill="none" stroke-linecap="round"/></svg>'
  ),
};

const m5s2 = {
  ogretmenler: [],
  logoB64: "",
  kur() {
    $("#m5s2-logo-dosya").addEventListener("change", (o) => this.logoSec(o.target.files[0]));
    const armaMeb = $("#m5s2-arma-meb");
    if (armaMeb) armaMeb.addEventListener("click", () => this.hazirArmaSec("meb"));
    const armaPardus = $("#m5s2-arma-pardus");
    if (armaPardus) armaPardus.addEventListener("click", () => this.hazirArmaSec("pardus"));
    $("#m5s2-okul-kaydet").addEventListener("click", () => this.okulKaydet());
    $("#m5s2-ogretmen-ekle").addEventListener("click", () => this.pencereAc(null));
    $("#ogf-rol").addEventListener("change", () => {
      $("#ogf-yetkiler-alan").hidden = $("#ogf-rol").value === "admin";
    });
    $("#ogf-kaydet").addEventListener("click", () => this.ogretmenKaydet());
  },
  hazirArmaSec(tip) {
    const veriUrl = HAZIR_ARMALAR[tip];
    if (!veriUrl) return;
    this.logoB64 = veriUrl;
    const img = $("#m5s2-logo-onizleme");
    if (img) { img.src = veriUrl; img.hidden = false; }
    bildir("Hazır arma seçildi; kaydetmek için “Okul Bilgilerini Kaydet” düğmesine basın.");
  },
  async ac() {
    await Promise.all([this.okulYukle(), this.ogretmenleriYukle()]);
  },
  async okulYukle() {
    try {
      const o = await api("/api/okul");
      $("#m5s2-okul-ad").value = o.ad || "";
      $("#m5s2-okul-alt").value = o.alt_baslik || "";
      this.logoB64 = o.logo_b64 || "";
      const img = $("#m5s2-logo-onizleme");
      if (img) {
        img.src = this.logoB64 || "";
        img.hidden = !this.logoB64;
      }
      okulBilgisiniUygula(o);
    } catch (hata) { bildir(hata.message, true); }
  },
  async logoSec(dosya) {
    if (!dosya) return;
    if (dosya.size > 2 * 1024 * 1024) {
      bildir("Okul logosu en fazla 2 MB olabilir.", true);
      return;
    }
    const veriUrl = await new Promise((coz, reddet) => {
      const okuyucu = new FileReader();
      okuyucu.onload = () => coz(okuyucu.result);
      okuyucu.onerror = reddet;
      okuyucu.readAsDataURL(dosya);
    });
    this.logoB64 = veriUrl;
    const img = $("#m5s2-logo-onizleme");
    if (img) { img.src = veriUrl; img.hidden = false; }
    $("#m5s2-logo-dosya").value = "";
  },
  async okulKaydet() {
    const ad = $("#m5s2-okul-ad").value.trim();
    const alt_baslik = $("#m5s2-okul-alt").value.trim();
    if (!ad) { bildir("Okul adı boş bırakılamaz.", true); return; }
    try {
      const yeni = await api("/api/okul", { ad, alt_baslik, logo_b64: this.logoB64 });
      okulBilgisiniUygula(yeni);
      bildir("Okul adı ve logosu güncellendi.");
    } catch (hata) { bildir(hata.message, true); }
  },
  async ogretmenleriYukle() {
    try { this.ogretmenler = await api("/api/ogretmenler"); }
    catch (hata) { bildir(hata.message, true); return; }
    this.ogretmenleriCiz();
  },
  ogretmenleriCiz() {
    const kap = $("#m5s2-ogretmen-tablo");
    if (!kap) return;
    if (!this.ogretmenler.length) {
      kap.replaceChildren(el("p", { class: "bos-tablo", metin: "Kayıtlı öğretmen yok." }));
      return;
    }
    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Ad Soyad", "Kullanıcı Adı", "Branş", "Rol", "Erişebildiği Menüler", "Son Giriş", ""].map((b) => el("th", { metin: b })))));
    const govde = el("tbody");
    for (const o of this.ogretmenler) {
      const slug = kimlikSlug(o.kullanici_adi || o.id);
      const yetkiler = Array.isArray(o.yetkiler) ? o.yetkiler : [];
      const yetkiEtiketi = o.rol === "admin"
        ? "Tüm Menüler (Tam Yetki)"
        : [
            "Sınıf Masası & Temizlik",
            "Ödev & Dosya Dağıt",
            "İşlem Geçmişi",
            ...(yetkiler.includes("paket_gorunum") ? ["Paket & Görünüm"] : []),
            ...(yetkiler.includes("komut_gonder") ? ["Komut Gönder"] : []),
          ].join(" · ");
      govde.append(el("tr", {},
        el("td", {}, el("strong", { metin: o.ad_soyad })),
        el("td", { class: "mono", metin: o.kullanici_adi }),
        el("td", { metin: o.brans || "—" }),
        el("td", {}, o.rol === "admin" ? rozet("Admin Öğretmen", "mavi") : rozet("Standart Öğretmen", "iyi")),
        el("td", {}, el("span", { class: "alt", metin: yetkiEtiketi })),
        el("td", { metin: tarih(o.son_giris) }),
        el("td", {}, el("div", { class: "dugme-grubu" },
          dugme("Düzenle", `M5-S2-B4-${slug}`, () => this.pencereAc(o), "ikincil kucuk"),
          dugme("Sil", `M5-S2-B5-${slug}`, () => this.ogretmenSil(o), "tehlikeli kucuk")
        ))
      ));
    }
    tablo.append(govde);
    kap.replaceChildren(tablo);
  },
  pencereAc(ogretmen = null) {
    duzenlenenOgretmen = ogretmen;
    $("#ogf-hata").hidden = true;
    $("#ogretmen-pencere-baslik").textContent = ogretmen ? `Öğretmeni düzenle — ${ogretmen.ad_soyad}` : "Yeni öğretmen ekle";
    $("#ogf-kullanici").value = ogretmen ? ogretmen.kullanici_adi : "";
    $("#ogf-kullanici").disabled = Boolean(ogretmen);
    $("#ogf-ad").value = ogretmen ? ogretmen.ad_soyad : "";
    $("#ogf-brans").value = ogretmen ? (ogretmen.brans || "") : "Bilişim Teknolojileri";
    $("#ogf-rol").value = ogretmen ? ogretmen.rol : "standart";
    $("#ogf-parola").value = "";
    $("#ogf-parola").placeholder = ogretmen ? "Değiştirmek istemiyorsanız boş bırakın" : "En az 8 karakter";
    const yetkiler = (ogretmen && Array.isArray(ogretmen.yetkiler)) ? ogretmen.yetkiler : [];
    $("#ogf-yetki-paket").checked = yetkiler.includes("paket_gorunum");
    $("#ogf-yetki-komut").checked = yetkiler.includes("komut_gonder");
    $("#ogf-yetkiler-alan").hidden = $("#ogf-rol").value === "admin";
    $("#ogretmen-penceresi").showModal();
  },
  async ogretmenKaydet() {
    $("#ogf-hata").hidden = true;
    const kullanici_adi = $("#ogf-kullanici").value.trim();
    const ad_soyad = $("#ogf-ad").value.trim();
    const brans = $("#ogf-brans").value.trim();
    const rol = $("#ogf-rol").value;
    const parola = $("#ogf-parola").value;
    const yetkiler = [];
    if ($("#ogf-yetki-paket").checked) yetkiler.push("paket_gorunum");
    if ($("#ogf-yetki-komut").checked) yetkiler.push("komut_gonder");
    try {
      if (duzenlenenOgretmen) {
        const govde = { ad_soyad, brans, rol, yetkiler };
        if (parola) govde.parola = parola;
        await api(`/api/ogretmenler/${duzenlenenOgretmen.id}`, govde, "PATCH");
        bildir("Öğretmen bilgileri güncellendi.");
      } else {
        await api("/api/ogretmenler", { kullanici_adi, ad_soyad, brans, rol, parola, yetkiler });
        bildir("Yeni öğretmen hesabı oluşturuldu.");
      }
      $("#ogretmen-penceresi").close();
      await this.ogretmenleriYukle();
    } catch (hata) {
      $("#ogf-hata").textContent = hata.message;
      $("#ogf-hata").hidden = false;
    }
  },
  async ogretmenSil(o) {
    if (!confirm(`“${o.ad_soyad} (${o.kullanici_adi})” öğretmen hesabı silinsin mi?`)) return;
    try {
      await api(`/api/ogretmenler/${o.id}`, null, "DELETE");
      bildir("Öğretmen hesabı silindi.");
      await this.ogretmenleriYukle();
    } catch (hata) { bildir(hata.message, true); }
  },
};

sayfaKaydet("M4-S1", m4s1);
sayfaKaydet("M5-S1", m5s1);
sayfaKaydet("M5-S2", m5s2);
