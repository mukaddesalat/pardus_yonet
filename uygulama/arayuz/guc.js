/* M2 İşlemler: S4 Güç ve Uyku, S5 Zamanlı Kapatma. */
"use strict";

function durumEtiketi(c) {
  const d = pcDurumu(c);
  return el("span", { class: `durum-etiketi ton-${d.ton}`, title: d.aciklama }, ikon(d.ikon, "ikon"), d.ad);
}

function gucUykuHucresi(c) {
  const g = c.guc_durumu;
  if (!g || g.uyku_kapali == null) return rozet("Bilinmiyor", "notr");
  return el("div", {}, g.uyku_kapali ? rozet("Uyku kapalı", "iyi") : rozet("Uyku açık", "orta"),
    el("span", { class: "alt", metin: g.ekran_dk == null ? "ekran: sistem varsayılanı"
      : g.ekran_dk ? `boşta ${g.ekran_dk} dk sonra ekran kararır` : "ekran kararmaz" }));
}

function kapatmaHucresi(c) {
  const g = c.guc_durumu;
  if (!g) return el("span", { class: "alt", metin: "okunmadı" });
  const planlar = g.planlar || [];
  return el("div", { class: "plan-cipleri" },
    ...(planlar.length ? planlar.map((p) => el("span", { class: "plan-cipi", title: p.sonraki ? `Sonraki kapanma: ${p.sonraki}` : "" },
      ikon("saat", "ikon mini-ikon"), p.etiket || p.id)) : [el("span", { class: "alt", metin: "plan yok" })]),
    g.bekleyen ? rozet(g.bekleyen_saat ? `Kapanma sayacı çalışıyor (${g.bekleyen_saat})` : "Kapanma sayacı çalışıyor", "kotu") : null);
}

/* ================================================================ M2-S4 Güç ve Uyku */

const m2s4 = {
  tablo: null,
  kur() {
    this.tablo = new CihazTablosu($("#m2s4-tablo"), {
      islem: "guc",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Durum", hucre: durumEtiketi },
        { baslik: "Uyku ve ekran", hucre: gucUykuHucresi },
        { baslik: "Zamanlı kapatma", hucre: kapatmaHucresi },
        { baslik: "Öğrenci oturumu", hucre: (c) => evetHayir(c.ogrenci_oturumu, ["Açık", "orta"], ["Kapalı", "notr"]) },
        { baslik: "Uygunluk", hucre: (c) => uygunlukHucresi(c, "guc") },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S4 .secim-yeri"), "guc", () => this.tablo);
    $("#m2s4-yeniden").addEventListener("click", () => this.eylem("yeniden_baslat"));
    $("#m2s4-kapat").addEventListener("click", () => this.eylem("kapat"));
    $("#m2s4-uyku-onizle").addEventListener("click", () => this.uyku("onizle"));
    $("#m2s4-uyku-uygula").addEventListener("click", () => this.uyku("uygula"));
    $("#m2s4-uyku-kaldir").addEventListener("click", () => this.uyku("kaldir"));
  },
  ac() { this.tablo.ciz(); Secim.bildir(); erisimTazele(300); },
  async eylem(eylem) {
    const yeniden = eylem === "yeniden_baslat";
    const hedefler = await onayIste({ islem: "guc", cihazlar: Secim.liste(),
      baslik: yeniden ? "Yeniden başlat" : "Bilgisayarları kapat",
      aciklama: yeniden ? "Seçili bilgisayarlar yeniden başlatılır; yeniden açılma ayrıca doğrulanır." : "Seçili bilgisayarlar kapatılır; kapanma ayrıca doğrulanır.",
      uyarilar: ["Öğrencilerin kaydedilmemiş çalışmaları kaybolabilir."],
      yikici: true, onayMetni: "Kaydedilmemiş çalışmaların kaybolabileceğini anladım", baslatMetni: yeniden ? "Yeniden başlat" : "Kapat" });
    if (hedefler) isBaslat("/api/guc", { cihazlar: hedefler, eylem, onay: true });
  },
  async uyku(islem) {
    const ekranDk = Number($("#m2s4-ekran").value);
    const ekranMetni = ekranDk ? `boşta ${ekranDk} dakika sonra ekran kararır` : "ekran hiç kararmaz";
    const bilgi = {
      onizle: ["Güç ayarını önizle", "Seçili bilgisayarlarda şu anki uyku ve ekran ayarı okunur; hiçbir şey değişmez.", "Önizle"],
      uygula: ["Uyku modunu kapat", `Bilgisayarlar boşta uykuya geçmez ve kendiliğinden kapanmaz; ${ekranMetni}. Giriş ekranında beklerken de uyumaz. Öğrenci bu ayarı değiştiremez.`, "Uygula"],
      kaldir: ["Varsayılan güç ayarına dön", "Bu uygulamanın yaptığı uyku ayarı geri alınır; bilgisayarlar Pardus'un varsayılan güç davranışına döner (boşta uykuya geçebilir).", "Varsayılana dön"],
    }[islem];
    const hedefler = await onayIste({ islem: "guc", cihazlar: Secim.liste(), baslik: bilgi[0], aciklama: bilgi[1],
      uyarilar: islem === "kaldir" ? ["Uykuya geçen bilgisayarlar uyanana kadar bu uygulamadan erişilemez."] : [],
      baslatMetni: bilgi[2] });
    if (hedefler) isBaslat("/api/guc/uyku", { cihazlar: hedefler, islem, ekran_dk: ekranDk, onay: islem !== "onizle" });
  },
};

/* ================================================================ M2-S5 Zamanlı Kapatma */

const GUNLER_TR = [["Mon", "Pzt"], ["Tue", "Sal"], ["Wed", "Çar"], ["Thu", "Per"], ["Fri", "Cum"], ["Sat", "Cmt"], ["Sun", "Paz"]];

function gunEtiketi(gunler) {
  const sira = GUNLER_TR.map(([g]) => g).map((g, i) => (gunler.includes(g) ? i : -1)).filter((i) => i >= 0);
  if (sira.length === 7) return "Her gün";
  const gruplar = [];
  for (const i of sira) {
    const son = gruplar[gruplar.length - 1];
    if (son && i === son[son.length - 1] + 1) son.push(i); else gruplar.push([i]);
  }
  return gruplar.flatMap((g) => (g.length >= 3 ? [`${GUNLER_TR[g[0]][1]}–${GUNLER_TR[g[g.length - 1]][1]}`] : g.map((i) => GUNLER_TR[i][1]))).join(", ");
}

const m2s5 = {
  tablo: null,
  tur: "surekli",
  kur() {
    const gunler = $("#m2s5-gunler");
    gunler.append(...GUNLER_TR.map(([g, ad], i) => el("label", { class: "gun" },
      el("input", { type: "checkbox", value: g, checked: i < 5, onchange: () => this.ozet() }), ad)));
    const yarin = new Date(Date.now() + 86400000);
    $("#m2s5-tarih").value = `${yarin.getFullYear()}-${String(yarin.getMonth() + 1).padStart(2, "0")}-${String(yarin.getDate()).padStart(2, "0")}`;
    $("#m2s5-tek").addEventListener("click", () => this.turSec("tek"));
    $("#m2s5-hafta").addEventListener("click", () => this.turSec("surekli"));
    for (const id of ["#m2s5-tarih", "#m2s5-saat", "#m2s5-uyari"]) $(id).addEventListener("change", () => this.ozet());
    $("#m2s5-ekle").addEventListener("click", () => this.ekle());
    $("#m2s5-oku").addEventListener("click", () => this.oku());
    $("#m2s5-hepsini-sil").addEventListener("click", () => this.sil(null, Secim.liste()));
    $("#m2s5-iptal").addEventListener("click", () => this.iptal());
    this.tablo = new CihazTablosu($("#m2s5-tablo"), {
      islem: "guc",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Durum", hucre: durumEtiketi },
        { baslik: "Kapatma planları", hucre: kapatmaHucresi },
        { baslik: "Uyku ve ekran", hucre: gucUykuHucresi },
        { baslik: "Uygunluk", hucre: (c) => uygunlukHucresi(c, "guc") },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S5 .secim-yeri"), "guc", () => this.tablo);
    Veri.dinleyiciler.add(() => this.planlariCiz());
    this.turSec("surekli");
  },
  ac() { this.planlariCiz(); this.tablo.ciz(); Secim.bildir(); erisimTazele(300); },
  turSec(tur) {
    this.tur = tur;
    $("#m2s5-tek").setAttribute("aria-checked", String(tur === "tek"));
    $("#m2s5-hafta").setAttribute("aria-checked", String(tur === "surekli"));
    $("#m2s5-tarih-kap").hidden = tur !== "tek";
    $("#m2s5-gun-kap").hidden = tur !== "surekli";
    this.ozet();
  },
  secilenGunler() { return $$("#m2s5-gunler input:checked").map((k) => k.value); },
  ozet() {
    const saat = $("#m2s5-saat").value || "—";
    const uyari = Number($("#m2s5-uyari").value);
    const ne = this.tur === "tek"
      ? `${($("#m2s5-tarih").value || "—").split("-").reverse().join(".")} ${saat} (bir kez)`
      : `${gunEtiketi(this.secilenGunler()) || "gün seçilmedi"} ${saat} (her hafta)`;
    $("#m2s5-ozet").textContent = `${ne}: saat gelince ${uyari ? `öğrencilere uyarı gösterilir, ${uyari} dakika sonra kapanır` : "uyarmadan kapanır"}.`;
  },
  async ekle() {
    const govde = { tur: this.tur, saat: $("#m2s5-saat").value, tarih: this.tur === "tek" ? $("#m2s5-tarih").value : null,
      gunler: this.tur === "surekli" ? this.secilenGunler() : [], uyari_dk: Number($("#m2s5-uyari").value),
      aciklama: $("#m2s5-aciklama").value.trim() };
    if (!govde.saat) { bildir("Saat seçin.", true); return; }
    if (govde.tur === "surekli" && !govde.gunler.length) { bildir("En az bir gün seçin.", true); return; }
    if (govde.tur === "tek" && !govde.tarih) { bildir("Tarih seçin.", true); return; }
    const hedefler = await onayIste({ islem: "guc", cihazlar: Secim.liste(), baslik: "Zamanlı kapatma planı ekle",
      aciklama: $("#m2s5-ozet").textContent,
      uyarilar: ["Kapanma zamanında kaydedilmemiş çalışmalar kaybolabilir.",
        "Bilgisayar o saatte kapalıysa kapatma atlanır; sonradan açıldığında kapanmaz.",
        "Kapanan bilgisayar yeniden açılana kadar bu uygulamadan erişilemez."],
      baslatMetni: "Planı ekle" });
    if (hedefler) isBaslat("/api/kapatma/ekle", { ...govde, cihazlar: hedefler, onay: true });
  },
  async oku() {
    let ids = Secim.liste();
    if (!ids.length) ids = Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan && !c.uygunluk.guc).map((c) => c.id);
    const hedefler = await onayIste({ islem: "guc", cihazlar: ids, baslik: "Kapatma planlarını oku",
      aciklama: "Bilgisayarlardaki zamanlı kapatma planları ve uyku ayarı okunur; hiçbir şey değişmez. Seçim yoksa laboratuvardaki tüm uygun bilgisayarlar okunur.",
      baslatMetni: "Oku" });
    if (hedefler) isBaslat("/api/kapatma/oku", { cihazlar: hedefler });
  },
  planlariCiz() {
    const kap = $("#m2s5-planlar");
    if (!kap) return;
    const gruplar = new Map();
    for (const c of Veri.cihazlar.filter(labKapsami)) {
      for (const p of (c.guc_durumu && c.guc_durumu.planlar) || []) {
        if (!gruplar.has(p.id)) gruplar.set(p.id, { ...p, cihazlar: [] });
        gruplar.get(p.id).cihazlar.push(c);
      }
    }
    if (!gruplar.size) {
      kap.replaceChildren(el("p", { class: "bos-tablo", metin: "Bilinen plan yok. Bilgisayarlardaki planları görmek için “Planları oku”." }));
      return;
    }
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["Plan", "Uyarı", "Bilgisayarlar", "Sonraki", ""].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const p of gruplar.values()) {
      g.append(el("tr", {},
        el("td", {}, el("strong", { metin: p.etiket || p.id }), p.aciklama ? el("span", { class: "alt", metin: p.aciklama }) : null),
        el("td", { metin: p.uyari_dk ? `${p.uyari_dk} dk` : "yok" }),
        el("td", { metin: `${p.cihazlar.length}: ${p.cihazlar.map((c) => c.ad).slice(0, 8).join(", ")}${p.cihazlar.length > 8 ? "…" : ""}` }),
        el("td", { class: "mono", metin: p.sonraki || "—" }),
        el("td", {}, dugme("Kaldır", `M2-S5-B10-${kimlikSlug(p.id)}`, () => this.sil([p.id], p.cihazlar.map((c) => c.id)), "ikincil kucuk"))));
    }
    tablo.append(g);
    kap.replaceChildren(el("div", { class: "tablo-kap" }, tablo));
  },
  async sil(idler, cihazlar) {
    const hedefler = await onayIste({ islem: "guc", cihazlar, baslik: idler ? "Kapatma planını kaldır" : "Tüm kapatma planlarını kaldır",
      aciklama: idler ? "Bu plan, listedeki bilgisayarlardan kaldırılır; bilgisayarlar o zamanlarda kapanmaz."
        : "Seçili bilgisayarlarda bu uygulamanın kurduğu tüm zamanlı kapatma planları kaldırılır.",
      baslatMetni: "Kaldır" });
    if (hedefler) isBaslat("/api/kapatma/sil", { cihazlar: hedefler, idler, onay: true });
  },
  async iptal() {
    const hedefler = await onayIste({ islem: "guc", cihazlar: Secim.liste(), baslik: "Bekleyen kapatmayı iptal et",
      aciklama: "Uyarı süresi içinde bekleyen (kapanma sayacı çalışan) bilgisayarlarda kapatma durdurulur. Planlar silinmez; bir sonraki zamanda yine çalışır.",
      baslatMetni: "İptal et" });
    if (hedefler) isBaslat("/api/kapatma/iptal", { cihazlar: hedefler, onay: true });
  },
};

sayfaKaydet("M2-S4", m2s4);
sayfaKaydet("M2-S5", m2s5);
