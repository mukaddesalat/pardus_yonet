/* M2 İşlemler: S1 Profil Temizliği, S2 Paket Kurulumu, S3 Görünüm ve Giriş, S4 Güç. */
"use strict";

/* ================================================================ M2-S1 Profil Temizliği */

const KAPSAM_METNI = {
  alanlar: "Seçilen alanlar karantinaya taşınır (öğrenci PC'de, geri alınabilir)",
  ayarlar: "Profil ayarları: gizli dosyalar silinir — tarayıcı verileri (geçmiş, çerezler, kayıtlı parolalar) DAHİL; Belgeler, Masaüstü ve görünür klasörler korunur",
  tam: "Ev dizininin TAMAMI silinir — Belgeler, Masaüstü, İndirilenler ve tarayıcı verileri DAHİL",
};

const m2s1 = {
  tablo: null,
  kapsam: "alanlar",
  katalog: [],
  genel: new Set(),
  istisnalar: new Map(),   // cihaz_id -> Set (yalnız bu temizlik; kaydedilmez)
  onizleme: new Map(),     // cihaz_id -> hedef veri
  onizlemeKapsami: null,
  sonuclar: new Map(),     // cihaz_id -> uygulama işi hedef verisi
  saklama: 5,
  ogretmenBos: null,

  kur() {
    this.tablo = new CihazTablosu($("#m2s1-tablo"), {
      islem: "temizlik",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Hedef hesap", hucre: (c) => el("div", {}, el("span", { class: "mono", metin: "ogrenci" }),
          el("span", { class: "alt", metin: c.profil_var === 0 ? "hesap yok" : "/home/ogrenci" })) },
        { baslik: "Oturum", hucre: (c) => this.oturumHucresi(c) },
        { baslik: "Temizlenecek kapsam", hucre: (c) => this.kapsamHucresi(c) },
        { baslik: "Tahmini açılacak alan", hucre: (c) => this.alanHucresi(c) },
        { baslik: "Yedek durumu", hucre: (c) => this.yedekHucresi(c) },
        { baslik: "Uygunluk / bekleme nedeni", hucre: (c) => this.uygunlukHucresi(c) },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S1 .secim-yeri"), "temizlik", () => this.tablo);
    for (const d of $$("#sayfa-M2-S1 .kapsam")) d.addEventListener("click", () => this.kapsamSec(d.dataset.kapsam));
    $("#m2s1-onizle").addEventListener("click", () => this.onizle());
    $("#m2s1-baslat").addEventListener("click", () => this.baslat());
    $("#m2s1-oturumlar").addEventListener("click", () => this.oturumKapat(Secim.liste()));
    $("#m2s1-yedek").addEventListener("click", () => this.yedekAl());
    $("#m2s1-geri").addEventListener("click", () => yedekPenceresiAc());
    Secim.dinleyiciler.add(() => this.kartlar());
  },

  async ac() {
    if (!this.katalog.length) {
      try {
        const b = await api("/api/temizlik/alanlar");
        this.katalog = b.katalog;
        this.genel = new Set(b.genel);
        this.saklama = b.saklama;
        this.ogretmenBos = b.ogretmen_bos;
      } catch (hata) { bildir(hata.message, true); }
    }
    this.kapsamSec(this.kapsam, true);
    Secim.bildir();
    erisimTazele(300);
  },

  kapsamSec(kapsam, sessiz = false) {
    if (!sessiz && kapsam !== this.kapsam) this.gecersizKil();
    this.kapsam = kapsam;
    for (const d of $$("#sayfa-M2-S1 .kapsam")) d.setAttribute("aria-checked", d.dataset.kapsam === kapsam ? "true" : "false");
    $("#m2s1-alanlar").hidden = kapsam !== "alanlar";
    const uyari = $("#m2s1-kapsam-uyari");
    uyari.classList.toggle("kirmizi", kapsam === "tam");
    uyari.textContent = kapsam === "alanlar" ? this.alanUyarisi()
      : kapsam === "ayarlar" ? `Profil ayarlarını sıfırla: ${KAPSAM_METNI.ayarlar}. Önce öğrenci PC'ye doğrulanmış yedek alınır; yedek başarısızsa silme başlamaz.`
        : `Ev dizininin tamamını sıfırla: ${KAPSAM_METNI.tam}. Önce öğrenci PC'ye doğrulanmış yedek alınır; yedek başarısızsa silme başlamaz.`;
    this.alanKutulari();
    $("#m2s1-baslat").firstChild.textContent = kapsam === "alanlar" ? "Temizliği başlat" : "Sıfırlamayı başlat";
    this.tablo.ciz();
    this.kartlar();
  },

  alanUyarisi() {
    const secili = (ad) => this.genel.has(ad) || [...this.istisnalar.values()].some((k) => k.has(ad));
    const u = [];
    const kisisel = this.katalog.filter((a) => ["belgeler", "resimler", "muzik", "videolar"].includes(a.ad) && secili(a.ad));
    if (kisisel.length) u.push(`${kisisel.map((a) => a.etiket).join(", ")} seçildi: öğrencinin kişisel dosyaları karantinaya taşınır.`);
    if (secili("tarayici")) u.push("Tarayıcı: geçmiş, çerezler, kayıtlı parolalar ve yer imleri taşınır; tarayıcı açıksa bu alan atlanır.");
    return u.join(" ");
  },

  alanKutulari() {
    const kap = $("#m2s1-alan-kutulari");
    kap.replaceChildren(...this.katalog.map((a) => el("label", { class: "onay-kutusu" },
      el("input", { type: "checkbox", checked: this.genel.has(a.ad), onchange: (o) => {
        if (o.target.checked) this.genel.add(a.ad); else this.genel.delete(a.ad);
        this.gecersizKil(); this.kapsamSec("alanlar", true);
      } }), a.etiket)));
  },

  gecersizKil() {
    this.onizleme = new Map();
    this.onizlemeKapsami = null;
    $("#m2s1-baslat").disabled = true;
  },

  alanlar(c) { return this.istisnalar.get(c.id) || this.genel; },

  oturumHucresi(c) {
    const v = this.onizleme.get(c.id);
    const acik = v && "oturum_acik" in v ? v.oturum_acik : c.ogrenci_oturumu === 1 ? true : c.ogrenci_oturumu === 0 ? false : null;
    if (acik === null) return rozet("?", "notr");
    if (!acik) return rozet("Kapalı", "notr");
    return el("div", {}, rozet("Açık", "orta"), " ",
      dugme("Oturumu kapat", `M2-S1-B4-${satirKimligi(c)}`, () => this.oturumKapat([c.id]), "tehlikeli kucuk"));
  },

  kapsamHucresi(c) {
    if (this.kapsam !== "alanlar") {
      return el("span", { class: this.kapsam === "tam" ? "hata" : "", metin: this.kapsam === "tam"
        ? "Ev dizininin tamamı (Belgeler + tarayıcı DAHİL)" : "Profil ayarları (tarayıcı verileri DAHİL; Belgeler korunur)" });
    }
    const alanlar = this.alanlar(c);
    const metin = this.katalog.filter((a) => alanlar.has(a.ad)).map((a) => a.kisa).join(", ") || "— (alan yok)";
    return el("div", {}, el("span", { metin }), this.istisnalar.has(c.id) ? rozet("İstisna", "orta") : null, " ",
      dugme("İstisna", `M2-S1-B8-${satirKimligi(c)}`, () => istisnaAc(c), "ikincil kucuk"));
  },

  /** {tip: "tek"|"aralik"|"yok", deger | en_az, en_cok, not} — ölçülemeyen asla 0 sayılmaz */
  tahmin(c) {
    const v = this.onizleme.get(c.id);
    if (!v || !v.sonuc) return { tip: "yok", not: v && v.neden ? v.neden : "ölçülmedi" };
    const s = v.sonuc;
    if (this.onizlemeKapsami === "alanlar") {
      const o = s.olcum;
      if (!o) return { tip: "yok", not: "ölçülemedi" };
      return { tip: "tek", deger: o.tahmini_acilacak,
        not: o.ayni_dosya_sistemi
          ? `${boyut(o.kaldirilacak.ayrilmis)} öğrenci alanından karantinaya taşınır (aynı disk: yer açmaz); budanacak eski karantina: ${boyut(o.budanacak_bayt)}`
          : `ayrı bölüm: ev diskinde ${boyut(o.kaldirilacak.serbest_kalabilir)} açılır, karantina diskinde kullanılır` };
    }
    const sil = s.silinecek.serbest_kalabilir;
    const budanan = s.yedek.budanacak_bayt;
    if (!s.ayni_dosya_sistemi) {
      return { tip: "tek", deger: sil, not: `yedek ayrı bölümde; orada en çok ${boyut(s.yedek.ust_sinir)} kullanılır` };
    }
    return { tip: "aralik", en_az: sil + budanan - s.yedek.ust_sinir, en_cok: sil + budanan,
      not: `silinecek ${boyut(s.silinecek.ayrilmis)} (mantıksal ${boyut(s.silinecek.bayt)}); yedek arşivinin sıkıştırılmış boyutu önceden bilinemez` };
  },

  alanHucresi(c) {
    const g = this.sonuclar.get(c.id);
    const t = this.tahmin(c);
    const kap = el("div");
    if (t.tip === "tek") kap.append(el("strong", { metin: boyut(t.deger) }), " ", rozet("tahmini", "mavi"));
    else if (t.tip === "aralik") kap.append(el("strong", { metin: `${boyut(t.en_az)} … ${boyut(t.en_cok)}` }), " ", rozet("tahmini aralık", "mavi"));
    else kap.append(rozet("ölçülemedi", "notr"));
    if (t.not) kap.append(el("span", { class: "alt", metin: t.not }));
    if (g && g.gerceklesen != null) kap.append(el("span", { class: "alt" }, "Gerçekleşen: ", el("strong", { metin: boyut(g.gerceklesen) }), " ", rozet("ölçüldü", "iyi")));
    return kap;
  },

  yedekHucresi(c) {
    const g = this.sonuclar.get(c.id);
    if (g && g.yedek) return el("div", {}, rozet("Yedek doğrulandı", "iyi"), el("span", { class: "alt mono", metin: g.yedek.ad }));
    if (this.kapsam === "alanlar") return el("span", { class: "alt", metin: `Karantina — öğrenci PC (son ${this.saklama} kayıt)` });
    const v = this.onizleme.get(c.id);
    if (!v || !v.sonuc) return el("span", { class: "alt", metin: "Önce öğrenci PC'ye yedek alınacak" });
    const y = v.sonuc.yedek;
    return el("div", {}, y.yeterli ? rozet("Alan yeterli", "iyi") : rozet("Alan YETERSİZ", "kotu"),
      el("span", { class: "alt", metin: `Öğrenci PC'de gereken: ${boyut(y.gerekli_bos)}, boş: ${boyut(y.bos)}` }));
  },

  engel(c) {
    const neden = c.uygunluk.temizlik;
    if (neden) return neden;
    if (c.erisim === 0) return "Erişilemiyor";
    const v = this.onizleme.get(c.id);
    if (!v || this.onizlemeKapsami !== this.kapsam) return "Önizleme bekleniyor";
    if (!v.sonuc) return v.neden || "Önizleme başarısız";
    if (this.kapsam !== "alanlar" && !v.sonuc.yedek.yeterli) return "Yedek için alan yetersiz";
    if (this.kapsam === "alanlar" && !this.alanlar(c).size) return "Alan seçilmedi";
    return null;
  },

  uygunlukHucresi(c) {
    const e = this.engel(c);
    const v = this.onizleme.get(c.id);
    const oturum = v ? v.oturum_acik : c.ogrenci_oturumu === 1;
    if (e) return el("span", { class: "alt", metin: e });
    if (this.kapsam !== "alanlar" && oturum) return rozet("Oturum kapatılmadan başlamaz", "orta");
    if (oturum) return rozet("Uygun — oturum açık (uyarı)", "orta");
    return rozet("Uygun", "iyi");
  },

  kartlar() {
    if ($("#sayfa-M2-S1").hidden) return;
    const secili = Secim.liste().map((id) => Veri.bul(id));
    const uygun = secili.filter((c) => !this.engel(c));
    let tek = 0, enAz = 0, enCok = 0, olculemeyen = 0, aralik = false, gercek = 0, gercekSay = 0, yedekUst = 0;
    for (const c of secili.filter((x) => !x.uygunluk.temizlik)) {
      const t = this.tahmin(c);
      if (t.tip === "tek") { tek += t.deger; enAz += t.deger; enCok += t.deger; }
      else if (t.tip === "aralik") { aralik = true; enAz += t.en_az; enCok += t.en_cok; }
      else olculemeyen += 1;
      const v = this.onizleme.get(c.id);
      if (v && v.sonuc && v.sonuc.yedek) yedekUst += v.sonuc.yedek.ust_sinir;
      const g = this.sonuclar.get(c.id);
      if (g && g.gerceklesen != null) { gercek += g.gerceklesen; gercekSay += 1; }
    }
    const olculen = secili.length - olculemeyen - secili.filter((x) => x.uygunluk.temizlik).length;
    const kartlar = [
      ozetKarti(secili.length, "Seçili bilgisayar"),
      ozetKarti(uygun.length, "İşleme uygun", this.onizlemeKapsami !== this.kapsam ? "önizleme bekleniyor" : null, true),
      ozetKarti(!olculen ? "ölçülemedi" : aralik ? `${boyut(enAz)} … ${boyut(enCok)}` : boyut(tek),
        "Öğrenci bilgisayarlarında tahmini açılacak toplam alan",
        [olculemeyen ? `${olculemeyen} bilgisayar ölçülemedi (0 sayılmadı)` : null,
          "her bilgisayar kendi diskinde; tek ortak disk değildir"].filter(Boolean).join(" · ")),
      ozetKarti("0 B", "Öğretmen PC'de gereken tahmini yedek alanı", "yedekler öğrenci PC'de tutulur (karar 18)"),
      ozetKarti(boyut(this.ogretmenBos), "Öğretmen PC'nin kullanılabilir boş alanı", "bu işlem için kullanılmaz"),
    ];
    if (this.kapsam !== "alanlar" && yedekUst) {
      kartlar.push(ozetKarti(`≤ ${boyut(yedekUst)}`, "Öğrenci PC'lerinde yedek için kullanılacak alan (toplam)", "sıkıştırma sonrası daha az olabilir"));
    }
    if (gercekSay) kartlar.push(ozetKarti(boyut(gercek), "Gerçekleşen kazanç (ölçüldü)", `${gercekSay} bilgisayarda disk boş alanı ölçüldü`));
    $("#m2s1-kartlar").replaceChildren(...kartlar);
  },

  async onizle() {
    const cihazlar = Secim.liste();
    if (!cihazlar.length) { bildir("Önce bilgisayar seçin.", true); return; }
    const kapsam = this.kapsam;
    const govde = { cihazlar, kapsam, alanlar: [...this.genel],
      istisnalar: Object.fromEntries([...this.istisnalar].filter(([id]) => cihazlar.includes(id)).map(([id, k]) => [id, [...k]])) };
    const kayit = await isBaslat("/api/temizlik/onizle", govde);
    if (!kayit) return;
    this.onizleme = new Map();
    this.sonuclar = new Map();
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.onizleme.set(h.veri.cihaz_id, h.veri);
    this.onizlemeKapsami = kapsam;
    $("#m2s1-baslat").disabled = !Secim.liste().some((id) => !this.engel(Veri.bul(id)));
    this.tablo.ciz();
    this.kartlar();
  },

  async baslat() {
    const adaylar = Secim.liste().filter((id) => !this.engel(Veri.bul(id)));
    const tam = this.kapsam === "tam";
    const sifirlama = this.kapsam !== "alanlar";
    const acikOturum = adaylar.filter((id) => (this.onizleme.get(id) || {}).oturum_acik);
    const kapatKutusu = el("input", { type: "checkbox", id: "m2s1-oturum-kapat" });
    const ek = sifirlama ? el("div", { class: tam ? "uyari-kutusu kirmizi" : "uyari-kutusu" },
      el("p", { metin: KAPSAM_METNI[this.kapsam] + "." }),
      acikOturum.length ? el("label", { class: "onay-kutusu" }, kapatKutusu,
        `${acikOturum.length} bilgisayarda öğrenci oturumu açık. Bu bilgisayarlarda oturumu kapatıp devam et (kaydedilmemiş çalışmalar kaybolur). İşaretlemezseniz bu bilgisayarlar “bekliyor” kalır.`) : null)
      : null;
    const hedefler = await onayIste({
      islem: "temizlik", cihazlar: adaylar,
      baslik: sifirlama ? (tam ? "Ev dizininin tamamını sıfırla" : "Profil ayarlarını sıfırla") : "Ders sonu temizliği",
      aciklama: sifirlama
        ? "Her bilgisayarda önce öğrenci PC'ye tam profil yedeği alınır ve doğrulanır; yedek başarısızsa o bilgisayarda silme başlamaz. Sonra standart başlangıç dosyaları (/etc/skel) konur."
        : "Seçilen alanlar silinmez; öğrenci PC'deki karantinaya taşınır ve M2-S1 “Yedekten dön” ile geri alınabilir.",
      uyarilar: [
        ...(!sifirlama && acikOturum.length ? [`${acikOturum.length} bilgisayarda öğrenci oturumu açık: kaydedilmemiş veriler kaybolabilir.`] : []),
        "Ödev teslim arşivi (öğretmen PC) bu işleme dahil değildir.",
      ],
      yikici: true, ek,
      onayMetni: tam ? "Belgeler ve tarayıcı verileri dahil ev dizininin tamamının silineceğini anladım"
        : sifirlama ? "Tarayıcı verileri dahil profil ayarlarının silineceğini anladım" : "Önizlemeyi inceledim; temizliği onaylıyorum",
      baslatMetni: sifirlama ? "Sıfırlamayı başlat" : "Temizliği başlat",
    });
    if (!hedefler) return;
    const govde = { cihazlar: hedefler, kapsam: this.kapsam, alanlar: [...this.genel], onay: true,
      oturumlari_kapat: Boolean(sifirlama && kapatKutusu.checked),
      istisnalar: Object.fromEntries([...this.istisnalar].filter(([id]) => hedefler.includes(id)).map(([id, k]) => [id, [...k]])) };
    const kayit = await isBaslat("/api/temizlik/uygula", govde);
    if (!kayit) return;
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, h.veri);
    this.istisnalar = new Map();   // istisnalar kaydedilmez
    $("#m2s1-baslat").disabled = true;
    this.tablo.ciz();
    this.kartlar();
  },

  async oturumKapat(cihazlar) {
    if (!cihazlar.length) { bildir("Önce bilgisayar seçin.", true); return; }
    const hedefler = await onayIste({
      islem: "oturum", cihazlar, baslik: cihazlar.length === 1 ? "Öğrenci oturumunu kapat" : "Seçili bilgisayarlardaki tüm öğrenci oturumlarını kapat",
      aciklama: "ogrenci oturumu kapatılır; süreçlerin ve kullanıcı bağlamalarının bittiği doğrulanır. “Komut gönderildi” ile “oturum kapandı” ayrı raporlanır.",
      uyarilar: ["Öğrencinin kaydedilmemiş çalışmaları kaybolur."],
      yikici: true, onayMetni: "Kaydedilmemiş çalışmaların kaybolabileceğini anladım", baslatMetni: "Oturumları kapat",
    });
    if (!hedefler) return;
    await isBaslat("/api/oturum-kapat", { cihazlar: hedefler, onay: true });
    for (const id of hedefler) { const v = this.onizleme.get(id); if (v) v.oturum_acik = false; }
    this.tablo.ciz();
  },

  async yedekAl() {
    const hedefler = await onayIste({ islem: "temizlik", cihazlar: Secim.liste(), baslik: "Yalnız yedek al",
      aciklama: "ogrenci profilinin tam yedeği öğrenci PC'de alınır ve doğrulanır. Yerel yedek disk arızasına karşı koruma sağlamaz." });
    if (hedefler) isBaslat("/api/yedek", { cihazlar: hedefler });
  },
};

/* ---- istisna penceresi ---- */
let istisnaCihazi = null;
function istisnaAc(c) {
  istisnaCihazi = c;
  $("#istisna-baslik").textContent = `İstisna — ${c.ad}`;
  const mevcut = m2s1.alanlar(c);
  $("#istisna-kutulari").replaceChildren(...m2s1.katalog.map((a) => el("label", { class: "onay-kutusu" },
    el("input", { type: "checkbox", value: a.ad, checked: mevcut.has(a.ad) }), a.etiket)));
  $("#istisna-penceresi").showModal();
}
$("#istisna-penceresi").addEventListener("close", () => {
  const d = $("#istisna-penceresi").returnValue;
  if (!istisnaCihazi || !["kaydet", "genel"].includes(d)) return;
  if (d === "genel") m2s1.istisnalar.delete(istisnaCihazi.id);
  else m2s1.istisnalar.set(istisnaCihazi.id, new Set($$("#istisna-kutulari input:checked").map((k) => k.value)));
  m2s1.gecersizKil();
  m2s1.kapsamSec("alanlar", true);
});

/* ---- yedekten dön ---- */
let yedekKayitlari = [];
function yedekPenceresiAc() {
  const uygun = Veri.cihazlar.filter((c) => !c.uygunluk.temizlik);
  const sec = $("#yedek-cihaz");
  sec.replaceChildren(...(uygun.length ? uygun.map((c) => el("option", { value: c.id, metin: `${c.ad} (${c.ip})` }))
    : [el("option", { value: "", metin: "Hazır bilgisayar yok" })]));
  const ilk = Secim.liste().find((id) => uygun.some((c) => c.id === id));
  if (ilk) sec.value = ilk;
  $("#yedek-durum").textContent = "";
  $("#yedek-listesi").replaceChildren();
  $("#yedek-geri").disabled = true;
  $("#yedek-zorla-etiket").hidden = true;
  $("#yedek-penceresi").showModal();
}
$("#yedek-cihaz").addEventListener("change", () => { $("#yedek-listesi").replaceChildren(); $("#yedek-geri").disabled = true; });
$("#yedek-listele").addEventListener("click", async () => {
  const id = $("#yedek-cihaz").value;
  if (!id) return;
  $("#yedek-durum").textContent = "Yedekler öğrenci bilgisayarından okunuyor…";
  let s;
  try { s = await api("/api/yedekler/listele", { cihaz: id }); }
  catch (hata) { $("#yedek-durum").textContent = hata.message; return; }
  yedekKayitlari = s.yedekler;
  $("#yedek-durum").textContent = (yedekKayitlari.length ? `${yedekKayitlari.length} kayıt bulundu.` : "Bu bilgisayarda yedek veya karantina kaydı yok.")
    + (s.oturum_acik ? " Öğrenci oturumu şu an açık." : "");
  const ETIKET = Object.fromEntries(m2s1.katalog.map((a) => [a.ad, a.kisa]));
  const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["", "Tarih", "Tür", "İçerik", "Boyut"].map((b) => el("th", { metin: b })))));
  const g = el("tbody");
  yedekKayitlari.forEach((k, i) => {
    const kilit = k.eski_bicim || (k.tur === "profil" && !k.dogrulanabilir);
    g.append(el("tr", {}, el("td", {}, el("input", { type: "radio", name: "yedek-sec", value: String(i), disabled: kilit,
      "aria-label": k.etiket, onchange: () => { $("#yedek-geri").disabled = false; $("#yedek-zorla-etiket").hidden = k.tur !== "profil"; } })),
    el("td", { metin: k.etiket }), el("td", {}, k.tur === "profil" ? rozet("Profil yedeği", "iyi") : rozet("Temizlik karantinası", "notr")),
    el("td", { metin: k.tur === "profil" ? (k.dogrulanabilir ? "Profilin tamamı" : "Sağlama yok — geri yüklenemez")
      : k.eski_bicim ? "Eski biçim — kılavuza bakın" : `${k.alanlar.map((a) => ETIKET[a] || a).join(", ")} — ${k.adet} öğe` }),
    el("td", { metin: k.bayt ? boyut(k.bayt) : "—" })));
  });
  tablo.append(g);
  $("#yedek-listesi").replaceChildren(tablo);
});
$("#yedek-geri").addEventListener("click", async () => {
  const r = $('input[name="yedek-sec"]:checked');
  if (!r) return;
  const kayit = yedekKayitlari[Number(r.value)];
  const cihaz = $("#yedek-cihaz").value;
  const zorla = $("#yedek-zorla").checked;
  $("#yedek-penceresi").close();
  const hedefler = await onayIste({
    islem: "temizlik", cihazlar: [cihaz], baslik: "Yedekten dön",
    aciklama: `${kayit.etiket} tarihli ${kayit.tur === "profil" ? "profil yedeğinin" : "temizlik karantinasının"} TAMAMI geri konacak.`,
    uyarilar: ["Aynı adlı dosya içerik olarak aynıysa (SHA-256) üzerine yazılır.",
      "Farklıysa ikisi de tutulur: geri gelen “ad (yedek TARİH)” adını alır. Hiçbir dosya silinmez.",
      ...(kayit.tur === "profil" ? [zorla ? "Öğrenci oturumu açıksa kapatılacak." : "Öğrenci oturumu açıksa geri yükleme yapılmaz."] : [])],
    yikici: true, onayMetni: "Geri dönmeyi onaylıyorum", baslatMetni: "Geri dön",
  });
  if (hedefler) isBaslat("/api/yedekler/geri-yukle", { cihaz, tur: kayit.tur, ad: kayit.ad, zorla_kapat: zorla, onay: true });
});

/* ================================================================ M2-S2 Paket Kurulumu */

const PLAN_ROZETI = {
  kurulacak: ["Kurulacak", "iyi"], guncellenecek: ["Güncellenecek", "iyi"], atlanacak: ["Atlanacak", "notr"],
  engellendi: ["Engellendi", "kotu"], kapsam_disi: ["Kapsam dışı", "notr"], hata: ["Hata", "kotu"],
};

const m2s2 = {
  tablo: null,
  paketler: [],
  sha: null,
  planIsId: null,
  planlar: new Map(),
  sonuclar: new Map(),
  kur() {
    this.tablo = new CihazTablosu($("#m2s2-tablo"), {
      islem: "paket",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Pardus", hucre: (c) => c.pardus_surum || "—" },
        { baslik: "Kurulu sürüm", hucre: (c) => { const p = this.planlar.get(c.id); return p && p.plan ? (p.plan.kurulu_surum || "kurulu değil") : "—"; } },
        { baslik: "Plan", hucre: (c) => this.planHucresi(c) },
        { baslik: "Bağımlılık / indirme", hucre: (c) => this.bagimlilikHucresi(c) },
        { baslik: "Sonuç", hucre: (c) => this.sonucHucresi(c) },
        { baslik: "", hucre: (c) => (this.planlar.has(c.id) ? dugme("Ayrıntı", `M2-S2-B5-${satirKimligi(c)}`, () => this.ayrinti(c), "ikincil kucuk") : "") },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S2 .secim-yeri"), "paket", () => this.tablo);
    $("#m2s2-dosya").addEventListener("change", (o) => this.yukle(o.target.files[0]));
    $("#m2s2-paket").addEventListener("change", (o) => { this.sha = o.target.value; this.sifirla(); this.bilgi(); });
    $("#m2s2-sil").addEventListener("click", () => this.sil());
    $("#m2s2-plan").addEventListener("click", () => this.plan());
    $("#m2s2-kur").addEventListener("click", () => this.kurulum());
  },
  async ac() { await this.listele(); this.tablo.ciz(); Secim.bildir(); erisimTazele(300); },
  async listele() {
    try { this.paketler = await api("/api/paketler"); } catch (hata) { bildir(hata.message, true); return; }
    const sec = $("#m2s2-paket");
    sec.replaceChildren(...(this.paketler.length ? this.paketler.map((p) => el("option", { value: p.sha256,
      metin: `${p.paket} ${p.surum} (${p.mimari}) — ${p.dosya_adi}` })) : [el("option", { value: "", metin: "Henüz paket yüklenmedi" })]));
    if (!this.paketler.some((p) => p.sha256 === this.sha)) this.sha = this.paketler.length ? this.paketler[0].sha256 : null;
    if (this.sha) sec.value = this.sha;
    this.bilgi();
  },
  paket() { return this.paketler.find((p) => p.sha256 === this.sha); },
  bilgi() {
    const p = this.paket();
    const dl = $("#m2s2-bilgi");
    if (!p) { dl.replaceChildren(); return; }
    const k = p.kontrol;
    const satirlar = [["Paket", p.paket], ["Sürüm", p.surum], ["Mimari", p.mimari], ["Dosya boyutu", boyut(p.boyut)],
      ["Kurulu boyut", p.kurulu_kb ? boyut(p.kurulu_kb * 1024) : "belirtilmemiş"], ["SHA-256", p.sha256],
      ["Bağımlılıklar", k.Depends || "—"], ["Ön bağımlılıklar", k["Pre-Depends"] || "—"],
      ["Çakışır / bozar", [k.Conflicts, k.Breaks].filter(Boolean).join("; ") || "—"],
      ["Açıklama", (k.Description || "").split("\n")[0] || "—"], ["Yüklendi", tarih(p.zaman)]];
    dl.replaceChildren(...satirlar.flatMap(([a, d]) => [el("dt", { metin: a }), el("dd", { class: a === "SHA-256" ? "mono" : "", metin: d })]));
  },
  sifirla() { this.planlar = new Map(); this.sonuclar = new Map(); this.planIsId = null; $("#m2s2-kur").disabled = true; this.kartlar(); this.tablo.ciz(); },
  async yukle(dosya) {
    if (!dosya) return;
    $("#m2s2-yukleme").textContent = `${dosya.name} yükleniyor ve paket yapısı doğrulanıyor…`;
    try {
      const p = await apiDosya("/api/paketler", dosya);
      $("#m2s2-yukleme").textContent = `Doğrulandı: ${p.paket} ${p.surum} (${p.mimari}). Bu paket öğretmenin yüklediği dosyadır; öğrenci portalına gelen dosyalar bu listeye giremez.`;
      this.sha = p.sha256;
      this.sifirla();
      await this.listele();
    } catch (hata) { $("#m2s2-yukleme").textContent = `Reddedildi: ${hata.message}`; }
    $("#m2s2-dosya").value = "";
  },
  async sil() {
    const p = this.paket();
    if (!p || !confirm(`${p.paket} ${p.surum} öğretmen bilgisayarından silinsin mi? Kurulu bilgisayarlar etkilenmez.`)) return;
    try { await api(`/api/paketler/${p.sha256}`, null, "DELETE"); this.sha = null; this.sifirla(); await this.listele(); }
    catch (hata) { bildir(hata.message, true); }
  },
  async plan() {
    const p = this.paket();
    if (!p) { bildir("Önce bir .deb dosyası seçin.", true); return; }
    const hedefler = await onayIste({ islem: "paket", cihazlar: Secim.liste(), baslik: `Kurulum planı — ${p.paket} ${p.surum}`,
      aciklama: "Paket her hedefe aktarılır ve SHA-256 ile doğrulanır; ardından Pardus sürümü, mimari, boş alan, paket yöneticisi kilidi, kurulu sürüm ve bağımlılıklar denetlenir. Bu adımda hiçbir şey KURULMAZ.",
      baslatMetni: "Planı hazırla" });
    if (!hedefler) return;
    const kayit = await isBaslat(`/api/paketler/${p.sha256}/plan`, { cihazlar: hedefler });
    if (!kayit) return;
    this.planIsId = kayit.id;
    this.planlar = new Map();
    this.sonuclar = new Map();
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.planlar.set(h.veri.cihaz_id, h.veri);
    $("#m2s2-kur").disabled = !this.kurulabilir().length;
    this.kartlar();
    this.tablo.ciz();
  },
  kurulabilir() {
    return [...this.planlar].filter(([, v]) => v.plan && ["kurulacak", "guncellenecek"].includes(v.plan.durum)).map(([id]) => id);
  },
  async kurulum() {
    const p = this.paket();
    const adaylar = this.kurulabilir().filter((id) => Secim.kume.has(id));
    if (!adaylar.length) { bildir("Seçimde planı “kurulacak/güncellenecek” olan bilgisayar yok.", true); return; }
    const guncel = adaylar.filter((id) => this.planlar.get(id).plan.durum === "guncellenecek").length;
    const hedefler = await onayIste({ islem: "paket", cihazlar: adaylar, baslik: `Kur — ${p.paket} ${p.surum}`,
      aciklama: "Yalnız plan denetiminden geçen bilgisayarlara kurulur. Kurulumdan hemen önce denetimler yeniden yapılır; paket kaldırma veya sürüm düşürme gerekirse kurulum durur.",
      uyarilar: [...(guncel ? [`${guncel} bilgisayarda mevcut sürüm güncellenecek.`] : []),
        "Paketin kurulum betikleri root yetkisiyle çalışır; yalnız güvendiğiniz paketleri kurun."],
      yikici: true, onayMetni: "Kurulum planını inceledim ve onaylıyorum", baslatMetni: "Kur",
      hedefEk: { baslik: "Plan", hucre: (h) => { const v = this.planlar.get(h.id); return v ? PLAN_ROZETI[v.plan.durum][0] : "—"; } } });
    if (!hedefler) return;
    const kayit = await isBaslat(`/api/paketler/${p.sha256}/kur`, { cihazlar: hedefler, plan_is_id: this.planIsId, onay: true });
    if (!kayit) return;
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, { ...h.veri, durum: h.durum, mesaj: h.mesaj });
    this.kartlar();
    this.tablo.ciz();
  },
  planHucresi(c) {
    const v = this.planlar.get(c.id);
    if (!v) return c.uygunluk.paket ? el("span", { class: "alt", metin: c.uygunluk.paket }) : "—";
    const plan = v.plan || { durum: "hata", neden: "plan alınamadı" };
    const [m, t] = PLAN_ROZETI[plan.durum] || [plan.durum, "notr"];
    const neden = plan.durum === "engellendi" ? (plan.engeller || []).join("; ") : plan.neden;
    return el("div", {}, rozet(m, t), neden ? el("span", { class: "alt", metin: neden }) : null);
  },
  bagimlilikHucresi(c) {
    const v = this.planlar.get(c.id);
    if (!v || !v.plan || !v.plan.apt) return "—";
    const p = this.paket();
    const yeni = v.plan.apt.yeni.filter((y) => !p || y.paket !== p.paket).length;
    const parcalar = [`${yeni} yeni bağımlılık`];
    if (v.plan.indirilecek != null) parcalar.push(`${v.plan.indirilecek} dosya indirilecek`);
    if (v.plan.depo_erisimi === false) parcalar.push("depoya erişilemiyor!");
    return el("span", { class: "alt", metin: parcalar.join(" · ") });
  },
  sonucHucresi(c) {
    const s = this.sonuclar.get(c.id);
    if (!s) return "—";
    if (s.durum === "basarili") return el("div", {}, rozet("Kuruldu", "iyi"), el("span", { class: "alt mono", metin: (s.sonuc || {}).kurulu_surum || "" }));
    if (s.durum === "atlandi") return rozet("Atlandı", "notr");
    return el("div", {}, rozet("Başarısız", "kotu"), el("span", { class: "alt", metin: s.mesaj || "" }));
  },
  kartlar() {
    const say = (d) => [...this.planlar.values()].filter((v) => (v.plan || {}).durum === d).length;
    const kap = $("#m2s2-kartlar");
    if (!this.planlar.size) { kap.replaceChildren(); return; }
    const kartlar = [ozetKarti(say("kurulacak"), "Kurulacak", null, true), ozetKarti(say("guncellenecek"), "Güncellenecek"),
      ozetKarti(say("atlanacak"), "Atlanacak (aynı sürüm)"), ozetKarti(say("engellendi"), "Engellendi"),
      ozetKarti(say("kapsam_disi") + say("hata"), "Kapsam dışı / hata")];
    if (this.sonuclar.size) {
      const sonuc = [...this.sonuclar.values()];
      kartlar.push(ozetKarti(sonuc.filter((s) => s.durum === "basarili").length, "Kuruldu ve doğrulandı", null, true));
      const hatali = sonuc.filter((s) => s.durum === "basarisiz").length;
      if (hatali) kartlar.push(ozetKarti(hatali, "Kurulum başarısız", "ayrıntı: Sonuç sütunu ve M4-S1"));
    }
    kap.replaceChildren(...kartlar);
  },
  ayrinti(c) {
    const v = this.planlar.get(c.id);
    const plan = (v && v.plan) || {};
    $("#plan-baslik").textContent = `Plan ayrıntısı — ${c.ad}`;
    const liste = (baslik, ogeler) => el("div", {}, el("h3", { metin: `${baslik} (${ogeler.length})` }),
      ogeler.length ? el("ul", {}, ...ogeler.map((o) => el("li", { class: "mono", metin: o }))) : el("p", { class: "ipucu", metin: "yok" }));
    const apt = plan.apt || { yeni: [], guncellenecek: [], kaldirilacak: [], dusurulecek: [] };
    $("#plan-icerik").replaceChildren(
      el("p", {}, "Durum: ", this.planHucresi(c)),
      el("p", { class: "ipucu", metin: `Pardus: ${plan.pardus || "?"} · mimari: ${plan.mimari || "?"} · kurulu: ${plan.kurulu_surum || "yok"} · boş alan: ${boyut(plan.bos_alan)} / gereken: ${boyut(plan.gerekli_alan)} · depo erişimi: ${plan.depo_erisimi == null ? "gerekmedi" : plan.depo_erisimi ? "var" : "YOK"}` }),
      liste("Yeni kurulacak paketler", apt.yeni.map((y) => `${y.paket} ${y.surum}`)),
      liste("Güncellenecek paketler", apt.guncellenecek.map((g) => `${g.paket} ${g.eski} → ${g.yeni}`)),
      liste("Kaldırılacak paketler (engel)", apt.kaldirilacak),
      liste("Uyarılar", plan.uyarilar || []));
    $("#plan-penceresi").showModal();
  },
};

/* ================================================================ M2-S3 Görünüm ve Giriş */

const GORUNUM_OGELERI = { duzen: "Düzen", duvar: "Duvar kâğıdı", ekran_kilidi: "Ekran kilidi", otomatik_giris: "Otomatik giriş", gizle: "Hesap gizleme" };
const OGE_DURUMU = {
  uygulanacak: ["uygulanacak", "mavi"], kaldirilacak: ["kaldırılacak", "mavi"], zaten: ["zaten öyle", "notr"],
  zaten_yok: ["zaten yok", "notr"], uygulandi: ["uygulandı", "iyi"], kaldirildi: ["kaldırıldı", "iyi"],
  desteklenmiyor: ["desteklenmiyor", "orta"], hata: ["HATA", "kotu"],
};

const m2s3 = {
  tablo: null,
  sonuclar: new Map(),
  onizlemeVar: false,
  kur() {
    this.tablo = new CihazTablosu($("#m2s3-tablo"), {
      islem: "gorunum",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Masaüstü", hucre: (c) => el("div", {}, c.masaustu === "GNOME" ? rozet("GNOME", "iyi") : rozet(c.masaustu || "?", c.masaustu ? "orta" : "notr"),
          el("span", { class: "alt", metin: c.giris_yoneticisi || "" })) },
        { baslik: "Düzen", hucre: (c) => (c.gorunum_durumu === "uygulandi" ? rozet("Uygulandı", "iyi") : c.gorunum_durumu === "yok" ? rozet("Yok", "notr") : rozet("?", "notr")) },
        { baslik: "Otomatik giriş", hucre: (c) => (c.otomatik_giris === "ogrenci" ? rozet("ogrenci", "iyi")
          : c.otomatik_giris === "kapali" ? rozet("Kapalı", "notr") : rozet(c.otomatik_giris || "?", "notr")) },
        { baslik: "Yönetim hs. gizli", hucre: (c) => { const r = GIZLEME_ROZETI[c.gizleme_durumu]; return r ? rozet(r[0], r[1]) : rozet("?", "notr"); } },
        { baslik: "Oturum", hucre: (c) => evetHayir(c.ogrenci_oturumu, ["Açık", "orta"], ["Kapalı", "notr"]) },
        { baslik: "Önizleme / sonuç", hucre: (c) => this.sonucHucresi(c) },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S3 .secim-yeri"), "gorunum", () => this.tablo);
    $("#m2s3-temsili").innerHTML = TEMSILI_SVG;   // sabit çizim; kullanıcı/uzak veri içermez
    $("#m2s3-gorsel").addEventListener("change", (o) => this.gorselYukle(o.target.files[0]));
    for (const id of ["m2s3-duzen", "m2s3-duvar", "m2s3-kilit-ekran", "m2s3-otomatik", "m2s3-gizle", "m2s3-kilitle", "m2s3-yon"]) {
      $(`#${id}`).addEventListener("change", () => { this.onizlemeVar = false; $("#m2s3-uygula").disabled = true; });
    }
    $("#m2s3-onizle").addEventListener("click", () => this.calistir("onizle"));
    $("#m2s3-uygula").addEventListener("click", () => this.calistir("uygula"));
  },
  async ac() {
    this.tablo.ciz(); Secim.bildir(); erisimTazele(300);
    try {
      const b = await api("/api/gorunum");
      $("#m2s3-gorsel-bilgi").textContent = b.gorsel ? `Yüklü görsel: ${b.gorsel.ad} (${boyut(b.gorsel.bayt)})` : "Henüz görsel yüklenmedi.";
    } catch (_) { /* önemsiz */ }
  },
  secenekler() {
    const yon = $("#m2s3-yon").value;
    const s = {};
    const esle = { duzen: "m2s3-duzen", duvar: "m2s3-duvar", ekran_kilidi: "m2s3-kilit-ekran", otomatik_giris: "m2s3-otomatik", gizle: "m2s3-gizle" };
    for (const [ad, id] of Object.entries(esle)) if ($(`#${id}`).checked) s[ad] = yon;
    s.kilit = $("#m2s3-kilitle").checked;
    return s;
  },
  async gorselYukle(dosya) {
    if (!dosya) return;
    const b64 = await new Promise((coz, reddet) => {
      const o = new FileReader();
      o.onload = () => coz(o.result.split(",")[1]);
      o.onerror = reddet;
      o.readAsDataURL(dosya);
    });
    try {
      await api("/api/duvar-kagidi/gorsel", { icerik_b64: b64, uzanti: dosya.name.toLowerCase().endsWith(".png") ? ".png" : ".jpg" });
      $("#m2s3-gorsel-bilgi").textContent = `Yüklü görsel: ${dosya.name} (${boyut(dosya.size)})`;
      $("#m2s3-duvar").checked = true;
    } catch (hata) { bildir(hata.message, true); }
    $("#m2s3-gorsel").value = "";
  },
  sonucHucresi(c) {
    const v = this.sonuclar.get(c.id);
    if (!v) return c.uygunluk.gorunum ? el("span", { class: "alt", metin: c.uygunluk.gorunum }) : "—";
    if (!v.ogeler) return el("span", { class: "alt", metin: v.mesaj || "—" });
    const kap = el("div", { class: "dugme-grubu" });
    for (const [ad, bilgi] of Object.entries(v.ogeler)) {
      const [m, t] = OGE_DURUMU[bilgi.durum] || [bilgi.durum, "notr"];
      const r = rozet(`${GORUNUM_OGELERI[ad] || ad}: ${m}`, t);
      r.title = [bilgi.ayrinti, bilgi.dogrulama, bilgi.karsilayici ? `Pardus Karşılayıcı: ${bilgi.karsilayici}` : null,
        (bilgi.atlanan || []).length ? `${bilgi.atlanan.length} anahtar kurulu şemada olmadığı için atlandı` : null].filter(Boolean).join(" · ");
      kap.append(r);
    }
    if (v.ortam && v.ortam.ogrenci_oturumu) kap.append(rozet("oturum açık", "orta"));
    return kap;
  },
  async calistir(kip) {
    const secenekler = this.secenekler();
    if (Object.keys(secenekler).length <= 1) { bildir("En az bir seçenek işaretleyin.", true); return; }
    let hedefler = Secim.liste();
    if (kip === "uygula") {
      const acik = [...this.sonuclar.values()].filter((v) => v.ortam && v.ortam.ogrenci_oturumu).map((v) => v.ad);
      hedefler = await onayIste({ islem: "gorunum", cihazlar: hedefler, baslik: "Görünüm ve giriş ayarlarını uygula",
        aciklama: "Ayarlar dconf sistem veritabanına ve GDM ayarlarına yazılır. Masaüstü ortamı değiştirilmez; XFCE bilgisayarlar kapsam dışıdır.",
        uyarilar: [
          ...(acik.length ? [`Öğrenci oturumu açık: ${acik.join(", ")} — kilitli ayarlar bu oturumlarda hemen değişebilir; düzenin tamamı sonraki girişte görünür.`] : []),
          ...(secenekler.otomatik_giris ? ["Otomatik giriş bir sonraki açılışta veya giriş ekranı yeniden başladığında etkinleşir."] : []),
          ...(secenekler.gizle ? ["Yönetim hesabı yalnız giriş ekranı listesinden gizlenir; hesap ve SSH erişimi korunur. Gerçek giriş ekranında görsel doğrulama yapılmaz."] : []),
        ],
        yikici: true, onayMetni: "Değişiklikleri inceledim; uygulamayı onaylıyorum", baslatMetni: "Uygula" });
      if (!hedefler) return;
    } else if (!hedefler.length) { bildir("Önce bilgisayar seçin.", true); return; }
    const kayit = await isBaslat(`/api/gorunum/${kip}`, { cihazlar: hedefler, secenekler, onay: kip === "uygula" });
    if (!kayit) return;
    this.sonuclar = new Map();
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, { ...h.veri, mesaj: h.mesaj });
    this.onizlemeVar = kip === "onizle";
    $("#m2s3-uygula").disabled = !(kip === "onizle" && kayit.hedefler.some((h) => h.durum === "basarili"));
    this.tablo.ciz();
  },
};

/* Temsili hedef görünüm çizimi — gerçek ekran görüntüsü DEĞİLDİR. */
const TEMSILI_SVG = `
<svg viewBox="0 0 480 300" role="img" aria-label="Temsili çizim: altta görev çubuğu, solda uygulama menüsü açık masaüstü ve yalnız ogrenci hesabının listelendiği giriş ekranı">
  <defs>
    <linearGradient id="tg-zemin" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6A4FA3"/><stop offset=".55" stop-color="#9C7CC9"/><stop offset="1" stop-color="#E6B8D8"/>
    </linearGradient>
  </defs>
  <rect width="480" height="300" fill="url(#tg-zemin)"/>
  <g fill="#FFFFFF" fill-opacity=".9">
    <rect x="14" y="14" width="26" height="22" rx="3"/><rect x="14" y="52" width="26" height="22" rx="3"/>
  </g>
  <g font-family="Ubuntu, sans-serif" font-size="7" fill="#FFFFFF">
    <text x="12" y="45">Belgeler</text><text x="16" y="83">Çöp</text>
  </g>
  <rect x="6" y="104" width="178" height="162" rx="6" fill="#1F2330" fill-opacity=".96"/>
  <g font-family="Ubuntu, sans-serif" font-size="8" fill="#E8EEF4">
    <text x="16" y="122" font-weight="bold">Uygulama menüsü (ArcMenu “Windows”)</text>
    <rect x="16" y="130" width="72" height="12" rx="2" fill="#2E3446"/><text x="20" y="139">Firefox</text>
    <rect x="16" y="146" width="72" height="12" rx="2" fill="#2E3446"/><text x="20" y="155">Dosyalar</text>
    <rect x="16" y="162" width="72" height="12" rx="2" fill="#2E3446"/><text x="20" y="171">Pardus Yazılım</text>
    <rect x="16" y="178" width="72" height="12" rx="2" fill="#2E3446"/><text x="20" y="187">LibreOffice</text>
    <rect x="96" y="130" width="78" height="60" rx="2" fill="#2E3446"/><text x="100" y="140">Sabitlenenler</text>
    <rect x="16" y="240" width="158" height="16" rx="8" fill="#3A4157"/><text x="24" y="251">Ara…</text>
  </g>
  <rect x="0" y="272" width="480" height="28" fill="#141821" fill-opacity=".95"/>
  <circle cx="16" cy="286" r="9" fill="#F2B632"/><text x="12.5" y="289.5" font-family="Ubuntu, sans-serif" font-size="10" font-weight="bold" fill="#141821">P</text>
  <g fill="#DDE3EA">
    <rect x="36" y="277" width="18" height="18" rx="4" fill="#E66A2C"/>
    <rect x="60" y="277" width="18" height="18" rx="4" fill="#4A90D9"/>
    <rect x="84" y="277" width="18" height="18" rx="4" fill="#3FAE6A"/>
    <rect x="40" y="297" width="10" height="2"/><rect x="64" y="297" width="10" height="2"/>
  </g>
  <g font-family="Ubuntu, sans-serif" font-size="7.5" fill="#E8EEF4">
    <text x="418" y="284">14:05</text><text x="410" y="294">28.09.2026</text>
  </g>
  <g fill="#9AA6B2"><rect x="380" y="281" width="8" height="8" rx="2"/><rect x="394" y="281" width="8" height="8" rx="2"/></g>
  <rect x="300" y="96" width="166" height="150" rx="8" fill="#FFFFFF" fill-opacity=".94"/>
  <g font-family="Ubuntu, sans-serif" fill="#16212C">
    <text x="312" y="114" font-size="8" font-weight="bold">Giriş ekranı (temsili)</text>
    <circle cx="383" cy="148" r="18" fill="#D3DBE3"/><circle cx="383" cy="142" r="7" fill="#9AA6B2"/>
    <rect x="370" y="151" width="26" height="12" rx="6" fill="#9AA6B2"/>
    <text x="366" y="182" font-size="10">ogrenci</text>
    <text x="312" y="202" font-size="7" fill="#4E5D6C">Otomatik giriş açık · ekran kilidi kapalı</text>
    <text x="312" y="214" font-size="7" fill="#4E5D6C">Yönetim hesabı (hp/pardus) listelenmez;</text>
    <text x="312" y="224" font-size="7" fill="#4E5D6C">SSH ile yönetim sürer.</text>
  </g>
  <rect x="352" y="8" width="120" height="18" rx="4" fill="#FFE7A8"/>
  <text x="360" y="20" font-family="Ubuntu, sans-serif" font-size="8.5" font-weight="bold" fill="#6B4100">TEMSİLİ ÇİZİM</text>
</svg>`;

sayfaKaydet("M2-S1", m2s1);
sayfaKaydet("M2-S2", m2s2);
sayfaKaydet("M2-S3", m2s3);

/* ================================================================ M2-S6 Komut Gönder */

const m2s6 = {
  tablo: null,
  komutlar: [],
  sonuclar: new Map(),
  sonOzet: null,
  kur() {
    this.tablo = new CihazTablosu($("#m2s6-log-tablo"), {
      islem: "komut",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Uygunluk", hucre: (c) => uygunlukHucresi(c, "komut") },
        { baslik: "Durum / RC", hucre: (c) => this.durumHucresi(c) },
        { baslik: "Canlı Çıktı (stdout / stderr)", hucre: (c) => this.ciktiHucresi(c) },
      ],
    });
    secimCubuguKur($("#sayfa-M2-S6 .secim-yeri"), "komut", () => this.tablo);
    $("#m2s6-kaydet").addEventListener("click", () => this.komutKaydet());
    $("#m2s6-calistir").addEventListener("click", () => this.komutCalistir());
    $("#m2s6-hosts-ekle").addEventListener("click", () => this.hostsDagit());
  },
  async ac() {
    await this.kutuphaneYukle();
    this.sayaclariCiz();
    this.tablo.ciz();
    Secim.bildir();
    erisimTazele(300);
  },
  async kutuphaneYukle() {
    try { this.komutlar = await api("/api/komutlar"); }
    catch (hata) { bildir(hata.message, true); return; }
    this.kutuphaneCiz();
  },
  kutuphaneCiz() {
    const kap = $("#m2s6-kutuphane");
    if (!kap) return;
    if (!this.komutlar.length) {
      kap.replaceChildren(el("p", { class: "ipucu", metin: "Kayıtlı komut yok." }));
      return;
    }
    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Komut", "Kategori", "Sudo", ""].map((b) => el("th", { metin: b })))));
    const govde = el("tbody");
    for (const k of this.komutlar) {
      const slug = kimlikSlug(k.id);
      const eylemler = el("div", { class: "dugme-grubu" },
        dugme("Yükle", `M2-S6-B3-${slug}`, () => {
          $("#m2s6-ad").value = k.ad;
          $("#m2s6-kategori").value = k.kategori || "Genel";
          $("#m2s6-komut").value = k.komut;
          $("#m2s6-sudo").checked = Boolean(k.sudo);
          bildir(`“${k.ad}” düzenleyiciye yüklendi.`);
        }, "ikincil kucuk"),
        !k.yerlesik ? dugme("Sil", `M2-S6-B4-${slug}`, () => this.komutSil(k), "tehlikeli kucuk") : null
      );
      govde.append(el("tr", {},
        el("td", {}, el("strong", { metin: k.ad }), el("span", { class: "alt mono", metin: k.komut.slice(0, 72) })),
        el("td", {}, rozet(k.kategori || "Genel", "notr")),
        el("td", {}, k.sudo ? rozet("sudo", "mavi") : rozet("kullanıcı", "notr")),
        el("td", {}, eylemler)
      ));
    }
    tablo.append(govde);
    kap.replaceChildren(tablo);
  },
  async komutKaydet() {
    const ad = $("#m2s6-ad").value.trim();
    const komut = $("#m2s6-komut").value.trim();
    const kategori = $("#m2s6-kategori").value;
    const sudo = $("#m2s6-sudo").checked;
    if (!ad || !komut) { bildir("Komut başlığı ve bash komutu zorunludur.", true); return; }
    try {
      await api("/api/komutlar", { ad, komut, kategori, sudo, aciklama: "" });
      bildir(`“${ad}” kütüphaneye kaydedildi.`);
      await this.kutuphaneYukle();
    } catch (hata) { bildir(hata.message, true); }
  },
  async komutSil(k) {
    if (!confirm(`“${k.ad}” kayıtlı komut listesinden silinsin mi?`)) return;
    try {
      await api(`/api/komutlar/${k.id}`, null, "DELETE");
      await this.kutuphaneYukle();
    } catch (hata) { bildir(hata.message, true); }
  },
  async komutCalistir() {
    const ad = $("#m2s6-ad").value.trim() || "Bash Komutu";
    const komut = $("#m2s6-komut").value.trim();
    const sudo = $("#m2s6-sudo").checked;
    if (!komut) { bildir("Çalıştırılacak bash komutunu yazın.", true); return; }
    const hedefler = await onayIste({
      islem: "komut", cihazlar: Secim.liste(),
      baslik: `SSH Komutu Gönder — ${ad}`,
      aciklama: `Komut: ${komut}`,
      uyarilar: [
        sudo ? "Komut seçili bilgisayarlarda parolasız sudo (root yetkisi) ile çalıştırılacaktır." : "Komut yönetim kullanıcısı yetkisiyle çalıştırılacaktır.",
      ],
      yikici: true,
      onayMetni: "Komutu inceledim; seçili bilgisayarlarda çalıştırılmasını onaylıyorum",
      baslatMetni: "Komutu Gönder",
    });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/komutlar/calistir", { cihazlar: hedefler, ad, komut, sudo });
    if (kayit) this.sonuclariIsle(kayit);
  },
  async hostsDagit() {
    const ip = $("#m2s6-hosts-ip").value.trim();
    const alan_adi = $("#m2s6-hosts-ad").value.trim();
    if (!ip || !alan_adi) { bildir("IP adresi ve alan adı zorunludur.", true); return; }
    const hedefler = await onayIste({
      islem: "komut", cihazlar: Secim.liste(),
      baslik: `/etc/hosts Kaydı Dağıt — ${ip} ${alan_adi}`,
      aciklama: `Seçili bilgisayarların /etc/hosts dosyasına “${ip} ${alan_adi}” satırı idempotent olarak eklenecek veya güncellenecektir.`,
      baslatMetni: "Hosts Kaydını Dağıt",
    });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/komutlar/hosts-ekle", { cihazlar: hedefler, ip, alan_adi });
    if (kayit) this.sonuclariIsle(kayit);
  },
  sonuclariIsle(kayit) {
    this.sonuclar = new Map();
    let gonderilen = kayit.hedefler.length;
    let ulasilamadi = 0;
    let basarili = 0;
    let hatali = 0;
    for (const h of kayit.hedefler) {
      const veri = h.veri || {};
      const cid = veri.cihaz_id;
      if (cid) this.sonuclar.set(cid, { durum: h.durum, asama: h.asama, mesaj: h.mesaj, ...veri });
      if (h.asama === "ulasilamadi") ulasilamadi++;
      else if (h.durum === "basarili") basarili++;
      else if (h.durum === "basarisiz") hatali++;
    }
    this.sonOzet = {
      gonderilen, ulasilamadi, basarili, hatali,
      metin: kayit.ozet || `${gonderilen} bilgisayara gönderildi · ${ulasilamadi} bilgisayara ulaşılamadı · ${basarili} başarılı · ${hatali} hata alındı`,
    };
    this.sayaclariCiz();
    this.tablo.ciz();
  },
  sayaclariCiz() {
    const kap = $("#m2s6-sayaclar");
    const etiket = $("#m2s6-ozet-metin");
    if (!kap || !etiket) return;
    if (!this.sonOzet) {
      etiket.textContent = "Henüz komut çalıştırılmadı";
      kap.replaceChildren(
        ozetKarti(0, "Gönderildi"),
        ozetKarti(0, "Ulaşılamadı"),
        ozetKarti(0, "Başarılı (RC=0)", null, true),
        ozetKarti(0, "Hata Alındı")
      );
      return;
    }
    etiket.textContent = this.sonOzet.metin;
    kap.replaceChildren(
      ozetKarti(this.sonOzet.gonderilen, "Bilgisayara Gönderildi"),
      ozetKarti(this.sonOzet.ulasilamadi, "Bilgisayara Ulaşılamadı"),
      ozetKarti(this.sonOzet.basarili, "Bilgisayarda Başarılı", "RC = 0", true),
      ozetKarti(this.sonOzet.hatali, "Bilgisayarda Hata Alındı", "RC ≠ 0")
    );
  },
  durumHucresi(c) {
    const s = this.sonuclar.get(c.id);
    if (!s) return "—";
    if (s.asama === "ulasilamadi") return rozet("Ulaşılamadı", "orta");
    if (s.durum === "basarili") return rozet(`Başarılı (RC=${s.rc ?? 0})`, "iyi");
    return rozet(`Hata (RC=${s.rc ?? 1})`, "kotu");
  },
  ciktiHucresi(c) {
    const s = this.sonuclar.get(c.id);
    if (!s) return el("span", { class: "alt", metin: "Çıktı bekleniyor…" });
    const metin = [s.stdout, s.stderr].filter(Boolean).join("\n") || s.mesaj || "(çıktı yok)";
    return el("pre", { class: `komut-cikti${s.durum === "basarisiz" ? " hatali" : ""}`, metin });
  },
};

sayfaKaydet("M2-S6", m2s6);
