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

const m5s1 = {
  sistem: null,
  yedekler: [],
  seciliDosya: null,
  seciliInceleme: null,
  kur() {
    $("#m5s1-saklama-formu").addEventListener("submit", async (o) => {
      o.preventDefault();
      try {
        const s = await api("/api/ayarlar", { saklama_adedi: Number($("#m5s1-saklama").value) });
        bildir(`Her bilgisayarda en fazla ${s.saklama_adedi} yedek/karantina kaydı tutulacak.`);
      } catch (hata) { bildir(hata.message, true); }
    });

    const btnOlustur = $("#m5s1-yedek-olustur");
    if (btnOlustur) btnOlustur.addEventListener("click", () => this.yedekOlustur(true));
    const btnSunucu = $("#m5s1-yedek-sadece-sunucu");
    if (btnSunucu) btnSunucu.addEventListener("click", () => this.yedekOlustur(false));
    const btnYenile = $("#m5s1-yedek-yenile");
    if (btnYenile) btnYenile.addEventListener("click", () => this.yedekleriYukle());
    const inpDosya = $("#m5s1-yedek-dosya");
    if (inpDosya) inpDosya.addEventListener("change", (o) => this.dosyaSecildi(o.target.files[0]));
    const btnYukle = $("#m5s1-yedek-yukle-btn");
    if (btnYukle) btnYukle.addEventListener("click", () => this.dosyadanGeriYukle());
  },
  async ac() {
    try {
      const a = await api("/api/ayarlar");
      $("#m5s1-saklama").value = a.saklama_adedi;
      $("#m5s1-surum").textContent = `Sürüm ${a.versiyon} · ödev arşivi: ${a.odev_dizini} (temizlik ve sıfırlama bu dizine hiçbir zaman dokunmaz)`;
    } catch (hata) { bildir(hata.message, true); }
    await this.yedekleriYukle();
  },
  async yedekleriYukle() {
    try {
      const veri = await api("/api/sistem-yedek");
      this.sistem = veri.sistem || null;
      this.yedekler = veri.yedekler || [];
      this.sistemOzetiCiz();
      this.yedekTablosuCiz();
    } catch (_) {
      /* Standart öğretmen ise gizle */
    }
  },
  sistemOzetiCiz() {
    const kap = $("#m5s1-sistem-ozet");
    if (!kap || !this.sistem) return;
    const s = this.sistem;
    kap.replaceChildren(
      ozetKarti(s.cihaz_sayisi || 0, "Envanterdeki Bilgisayar", s.ssh_anahtari_var ? "🔑 SSH anahtarı hazır" : "Anahtar yok"),
      ozetKarti(s.ogretmen_sayisi || 0, "Öğretmen Hesabı", s.okul_adi || "Okul tanımlı"),
      ozetKarti(`${s.sinif_sayisi || 0} / ${s.ogrenci_sayisi || 0}`, "Sınıf / Öğrenci", `${s.teslim_sayisi || 0} ödev teslimi`),
      ozetKarti(s.deb_hazir ? "Hazır" : (s.deb_uretilebilir ? "Üretilebilir" : "Yok"), "Uygulama .deb Paketi",
        s.deb_boyut ? `${s.deb_paketi} (${boyut(s.deb_boyut)})` : `v${s.uygulama_surumu}`),
    );
  },
  yedekTablosuCiz() {
    const kap = $("#m5s1-yedek-tablo");
    if (!kap) return;
    if (!this.yedekler.length) {
      kap.replaceChildren(el("p", { class: "bos-tablo", metin: "Henüz oluşturulmuş bir sistem yedeği yok. Yukarıdan “Şimdi Yedek Oluştur ve İndir” düğmesine tıklayarak ilk taşıma paketinizi oluşturabilirsiniz." }));
      return;
    }
    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Tarih & Dosya Adı", "Açıklama", "İçerik Özeti", "Boyut", ""].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const y of this.yedekler) {
      const oz = y.ozet || {};
      const sec = y.secenekler || {};
      const slug = kimlikSlug(y.dosya_adi).slice(-14);
      const etiketler = [
        `${oz.cihaz_sayisi ?? 0} PC`,
        `${oz.ogretmen_sayisi ?? 0} Öğretmen`,
        `${oz.sinif_sayisi ?? 0} Sınıf`,
        oz.ssh_anahtari_var ? "🔑 SSH Anahtarlı" : null,
        sec.deb_dahil ? "📦 .deb + yedekten-kur.sh" : null,
      ].filter(Boolean).join(" · ");
      g.append(el("tr", {},
        el("td", {},
          el("strong", { metin: tarih(y.olusturma_zamani) }),
          el("span", { class: "alt mono", metin: y.dosya_adi })),
        el("td", { metin: y.aciklama || "—" }),
        el("td", {},
          rozet(`v${y.uygulama_surumu || "?"}`, "mavi"), " ",
          el("span", { class: "alt", metin: etiketler })),
        el("td", { class: "mono", metin: boyut(y.boyut) }),
        el("td", {}, el("div", { class: "dugme-grubu" },
          dugme("⬇️ İndir", `M5-S1-B8-${slug}`, () => indir(`/api/sistem-yedek/${encodeURIComponent(y.dosya_adi)}/indir`), "birincil kucuk"),
          dugme("♻️ Geri Yükle", `M5-S1-B9-${slug}`, () => this.sunucudanGeriYukle(y), "ikincil kucuk"),
          dugme("Sil", `M5-S1-B10-${slug}`, () => this.yedekSil(y), "tehlikeli kucuk"),
        )),
      ));
    }
    tablo.append(g);
    kap.replaceChildren(tablo);
  },
  async yedekOlustur(hemenIndir = true) {
    const durumEl = $("#m5s1-yedek-durum");
    const btn1 = $("#m5s1-yedek-olustur");
    const btn2 = $("#m5s1-yedek-sadece-sunucu");
    if (btn1) btn1.disabled = true;
    if (btn2) btn2.disabled = true;
    if (durumEl) durumEl.textContent = "⏳ Yedek arşivi ve taşıma paketi hazırlanıyor, lütfen bekleyin...";
    try {
      const yanit = await api("/api/sistem-yedek/olustur", {
        aciklama: ($("#m5s1-yedek-aciklama") && $("#m5s1-yedek-aciklama").value.trim()) || "",
        deb_dahil: Boolean($("#m5s1-yedek-deb") && $("#m5s1-yedek-deb").checked),
        odev_teslimleri_dahil: Boolean($("#m5s1-yedek-teslimler") && $("#m5s1-yedek-teslimler").checked),
        yerel_paketler_dahil: Boolean($("#m5s1-yedek-paketler") && $("#m5s1-yedek-paketler").checked),
      });
      this.sistem = yanit.sistem || this.sistem;
      this.yedekler = yanit.yedekler || this.yedekler;
      this.sistemOzetiCiz();
      this.yedekTablosuCiz();
      const y = yanit.yedek;
      if (durumEl) durumEl.textContent = `✓ Yedek hazır: ${y.dosya_adi} (${boyut(y.boyut)})`;
      bildir(`Tam sistem yedeği oluşturuldu: ${y.dosya_adi}`);
      if (hemenIndir && y && y.dosya_adi) {
        indir(`/api/sistem-yedek/${encodeURIComponent(y.dosya_adi)}/indir`);
      }
    } catch (hata) {
      if (durumEl) durumEl.textContent = `✗ Hata: ${hata.message}`;
      bildir(hata.message, true);
    } finally {
      if (btn1) btn1.disabled = false;
      if (btn2) btn2.disabled = false;
    }
  },
  async dosyaSecildi(dosya) {
    const kutu = $("#m5s1-inceleme-kutu");
    const btn = $("#m5s1-yedek-yukle-btn");
    this.seciliDosya = null;
    this.seciliInceleme = null;
    if (btn) btn.disabled = true;
    if (!dosya) { if (kutu) kutu.hidden = true; return; }
    if (kutu) {
      kutu.hidden = false;
      kutu.replaceChildren(el("p", { class: "ipucu", metin: `⏳ "${dosya.name}" bütünlüğü ve SHA-256 özetleri doğrulanıyor...` }));
    }
    try {
      const inc = await apiDosya("/api/sistem-yedek/incele", dosya);
      this.seciliDosya = dosya;
      this.seciliInceleme = inc;
      if (btn) btn.disabled = false;
      const oz = inc.ozet || {};
      kutu.replaceChildren(
        el("div", { class: "kart" },
          el("p", {}, rozet("✓ SHA-256 Bütünlüğü Doğrulandı", "iyi"), " ", el("strong", { metin: dosya.name })),
          el("p", { class: "ipucu", metin: `Okul: ${oz.okul_adi || "—"} · Sürüm: v${inc.uygulama_surumu || "?"} · Tarih: ${tarih(inc.olusturma_zamani)}` }),
          el("p", { class: "ipucu", metin: `İçerik: ${oz.cihaz_sayisi ?? 0} bilgisayar, ${oz.ogretmen_sayisi ?? 0} öğretmen, ${oz.sinif_sayisi ?? 0} sınıf (${oz.ogrenci_sayisi ?? 0} öğrenci), SSH Anahtarı: ${oz.ssh_anahtari_var ? "Var" : "Yok"}` }),
        ),
      );
    } catch (hata) {
      if (kutu) {
        kutu.replaceChildren(el("p", { class: "hata-metni", metin: `✗ Geçersiz yedek: ${hata.message}` }));
      }
      bildir(hata.message, true);
    }
  },
  async dosyadanGeriYukle() {
    if (!this.seciliDosya || !this.seciliInceleme) return;
    const oz = this.seciliInceleme.ozet || {};
    const onay = await onayIste({
      baslik: "Yedekten Geri Yükle (Dosyadan)",
      aciklama: `"${this.seciliDosya.name}" yedeği mevcut sistemin üzerine geri yüklenecek.`,
      hedefler: [{ ad: oz.okul_adi || "Yönetim Sunucusu", ip: `${oz.cihaz_sayisi ?? 0} PC · ${oz.ogretmen_sayisi ?? 0} Öğretmen`, durum: "v" + (this.seciliInceleme.uygulama_surumu || "?") }],
      uyarilar: [
        "Geri yükleme öncesinde şu anki veritabanınız otomatik olarak güvenlik yedeğine alınır.",
        "Envanter, öğretmen hesapları, SSH anahtarları, Veyon/Galeri dosyaları ve ödev veritabanı yedekteki haline döner.",
      ],
      kutuMetni: "Yedeğin mevcut yapılandırmanın üzerine yazılmasını onaylıyorum",
    });
    if (!onay) return;
    try {
      const sonuc = await apiDosya("/api/sistem-yedek/geri-yukle", this.seciliDosya, { "X-Onay": "1" });
      await this.geriYuklemeSonrasi(sonuc);
    } catch (hata) { bildir(hata.message, true); }
  },
  async sunucudanGeriYukle(yedek) {
    const oz = yedek.ozet || {};
    const onay = await onayIste({
      baslik: "Kayıtlı Yedekten Geri Yükle",
      aciklama: `"${yedek.dosya_adi}" (${tarih(yedek.olusturma_zamani)}) yedeği geri yüklenecek.`,
      hedefler: [{ ad: oz.okul_adi || "Yönetim Sunucusu", ip: `${oz.cihaz_sayisi ?? 0} PC · ${oz.ogretmen_sayisi ?? 0} Öğretmen`, durum: "v" + (yedek.uygulama_surumu || "?") }],
      uyarilar: [
        "Geri yükleme öncesinde şu anki durumunuz otomatik olarak güvenlik yedeğine alınır.",
        "Envanter, öğretmen hesapları, SSH anahtarları ve ödev veritabanı seçilen yedekteki haline döner.",
      ],
      kutuMetni: "Seçilen yedeğin geri yüklenmesini onaylıyorum",
    });
    if (!onay) return;
    try {
      const sonuc = await api("/api/sistem-yedek/geri-yukle", { dosya_adi: yedek.dosya_adi, onay: true });
      await this.geriYuklemeSonrasi(sonuc);
    } catch (hata) { bildir(hata.message, true); }
  },
  async geriYuklemeSonrasi(sonuc) {
    if (sonuc.csrf) Uyg.csrf = sonuc.csrf;
    if (sonuc.okul) okulBilgisiniUygula(sonuc.okul);
    this.sistem = sonuc.guncel_ozet || this.sistem;
    this.yedekler = sonuc.yedekler || this.yedekler;
    this.seciliDosya = null;
    this.seciliInceleme = null;
    const inp = $("#m5s1-yedek-dosya");
    if (inp) inp.value = "";
    const kutu = $("#m5s1-inceleme-kutu");
    if (kutu) kutu.hidden = true;
    const btn = $("#m5s1-yedek-yukle-btn");
    if (btn) btn.disabled = true;
    this.sistemOzetiCiz();
    this.yedekTablosuCiz();
    await Veri.cihazlariYukle();
    bildir(`Yedek başarıyla geri yüklendi (${(sonuc.geri_yuklenen || []).length} bileşen yenilendi).`);
  },
  async yedekSil(yedek) {
    const onay = await onayIste({
      baslik: "Sistem Yedeğini Sil",
      aciklama: `"${yedek.dosya_adi}" yedek arşivi sunucudan kalıcı olarak silinecek.`,
      hedefler: [{ ad: yedek.dosya_adi, ip: boyut(yedek.boyut), durum: tarih(yedek.olusturma_zamani) }],
      uyarilar: ["Bu işlem yalnızca seçilen yedek dosyasını siler; çalışan sistemi etkilemez."],
      kutuMetni: "Yedek arşivinin silinmesini onaylıyorum",
    });
    if (!onay) return;
    try {
      const s = await api(`/api/sistem-yedek/${encodeURIComponent(yedek.dosya_adi)}`, null, "DELETE");
      this.yedekler = s.yedekler || [];
      this.yedekTablosuCiz();
      bildir("Yedek arşivi silindi.");
    } catch (hata) { bildir(hata.message, true); }
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
