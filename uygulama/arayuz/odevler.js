/* M3 Ödevler (öğretmen tarafı): S1 Teslimler, S2 Sınıflar ve Kodlar.
 * ortak.js'teki yardımcıları ($, $$, el, api, bildir, rozet, indir...) kullanır.
 * Öğrenci kodları yalnız üretildikleri anda bu sayfanın belleğinde durur;
 * pencere kapanınca silinir. */
"use strict";

let odevDurum = null;          // /api/odev/durum
let odevSiniflar = [];
let takipOdevId = null;
let takipVerisi = null;
let takipZamanlayici = null;
let duzenlenenOdevId = null;
let sonKodlar = [];

const TESLIM_DURUMLARI = {
  alindi: ["Teslim alındı", "iyi"], gec: ["Geç teslim", "orta"],
  etmedi: ["Teslim etmedi", "notr"], yukleniyor: ["Yükleme sürüyor", "mavi"],
  hata: ["Yükleme hatası", "kotu"],
};
const ODEV_DURUM_TONU = { taslak: "notr", acik: "iyi", kapali: "orta", arsiv: "notr" };
// eylem -> [metin, referans kodu, sınıf]
const ODEV_EYLEMLERI = {
  ac: ["Teslimleri aç", "M3-S1-B8"], kapat: ["Teslimleri kapat", "M3-S1-B9"],
  arsivle: ["Arşivle", "M3-S1-B10"], arsivden_cikar: ["Arşivden çıkar", "M3-S1-B11"],
  sil: ["Sil", "M3-S1-B12", "tehlikeli"],
};

function boyutYaz(bayt) { return bayt == null ? "—" : boyut(bayt); }

function guvenliMetin(deger) { return el("span", { metin: deger == null ? "" : String(deger) }); }

function tabloBasligi(tablo, basliklar) {
  tablo.append(el("thead", {}, el("tr", {}, ...basliklar.map((b) => el("th", { scope: "col", metin: b })))));
}

function odevKimligi(o) { return kimlikSlug(o.id).slice(0, 8) || "ODEV"; }

/* ---- sayfalar ---- */

const m3s1 = {
  async ac() {
    await Promise.all([portalDurumuYukle(), sinifListesiniYukle()]);
    takipGoster(Boolean(takipOdevId));
  },
  kapat() { clearInterval(takipZamanlayici); },
};

const m3s2 = {
  async ac() { await portalDurumuYukle(); ogrenciListesiniYukle(); },
};

function takipGoster(takip) {
  $("#alt-odev-liste").hidden = takip;
  $("#alt-odev-takip").hidden = !takip;
  clearInterval(takipZamanlayici);
  if (!takip) { takipOdevId = null; odevListesiniYukle(); return; }
  takipYukle();
  takipZamanlayici = setInterval(() => {
    if ($("#sayfa-M3-S1").hidden || $("#alt-odev-takip").hidden) { clearInterval(takipZamanlayici); return; }
    takipYukle(true);
  }, 5000);
}

/* ---- portal durumu ve ayarları ---- */

async function portalDurumuYukle() {
  try {
    odevDurum = await api("/api/odev/durum");
  } catch (hata) { bildir(hata.message, true); return; }
  $("#portal-adres").textContent = odevDurum.adres;
  $("#portal-durum").replaceChildren(odevDurum.portal_calisiyor
    ? rozet("Çalışıyor", "iyi") : rozet("Portal yanıt vermiyor", "kotu"));
  $("#portal-bilgi").textContent =
    `Boş disk alanı: ${boyutYaz(odevDurum.bos_alan)}. Öğrenci bilgisayarlarının bu adı ` +
    "çözebilmesi gerekir (okul DNS'i veya öğrenci PC'lerine dağıtılan ad kaydı).";
  $("#portal-ad").value = odevDurum.adres_adi;
  $("#portal-aglar").value = odevDurum.aglar.join(", ");
}

$("#portal-ayar-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  try {
    const sonuc = await api("/api/odev/ayarlar", {
      adres_adi: $("#portal-ad").value.trim(),
      aglar: $("#portal-aglar").value.split(",").map((s) => s.trim()).filter(Boolean),
    });
    bildir(`Kaydedildi. ${sonuc.not}`);
    portalDurumuYukle();
  } catch (hata) { bildir(hata.message, true); }
});

/* ---- ödev listesi ---- */

async function odevListesiniYukle() {
  let liste;
  try { liste = await api("/api/odev/odevler"); } catch (hata) { bildir(hata.message, true); return; }
  const kap = $("#odev-tablosu");
  kap.replaceChildren();
  if (!liste.length) {
    const p = document.createElement("p");
    p.className = "ipucu";
    p.textContent = odevSiniflar.length
      ? "Henüz ödev yok. “Yeni ödev” (M3-S1-B1) ile başlayın."
      : "Önce M3-S2 Sınıflar ve Kodlar sayfasından sınıf listesini ekleyin.";
    kap.append(p);
    return;
  }
  const tablo = document.createElement("table");
  tabloBasligi(tablo, ["Ödev", "Sınıf", "Durum", "Son teslim", "Teslim eden", "İşlemler"]);
  for (const o of liste) {
    const tr = document.createElement("tr");
    const baslik = document.createElement("td");
    baslik.append(guvenliMetin(o.baslik));
    const sinif = document.createElement("td"); sinif.append(guvenliMetin(o.sinif));
    const durum = document.createElement("td"); durum.append(rozet(o.durum_adi, ODEV_DURUM_TONU[o.durum]));
    const son = document.createElement("td"); son.append(guvenliMetin(o.son_tarih || "Süresiz"));
    const sayi = document.createElement("td");
    sayi.append(guvenliMetin(`${o.teslim_eden} / ${o.ogrenci_sayisi}`));
    const islem = document.createElement("td");
    islem.className = "dugme-grubu";
    islem.append(dugme("Takip", `M3-S1-B3-${odevKimligi(o)}`, () => { takipOdevId = o.id; takipGoster(true); }, "birincil kucuk"));
    tr.append(baslik, sinif, durum, son, sayi, islem);
    tablo.append(tr);
  }
  kap.append(tablo);
}

function odevEylemleri(durum) {
  return {
    taslak: ["ac", "arsivle"], acik: ["kapat"], kapali: ["ac", "arsivle"], arsiv: ["arsivden_cikar", "sil"],
  }[durum] || [];
}

async function durumDegistir(odevId, eylem, baslik) {
  try {
    if (eylem === "sil") {
      const onay = confirm(`"${baslik}" ödevi ve BÜTÜN öğrenci teslimleri kalıcı olarak ` +
        "silinecek. Bu işlem geri alınamaz.\n\nÖnce tüm sınıfı ZIP olarak indirmeniz önerilir. " +
        "Silmek istiyor musunuz?");
      if (!onay) return;
      await api(`/api/odev/odevler/${odevId}/sil`, { onay: true });
      bildir("Ödev ve teslimleri silindi.");
      takipOdevId = null;
      takipGoster(false);
      return;
    }
    if (eylem === "kapat" && !confirm("Teslimler kapatılacak. Şu anda süren yüklemeler " +
        "teslim sayılmaz ve öğrenciler hata mesajı görür. Devam edilsin mi?")) return;
    await api(`/api/odev/odevler/${odevId}/durum`, { eylem });
    bildir({ ac: "Teslimler açıldı; öğrenciler ödevi görebilir.", kapat: "Teslimler kapatıldı.",
      arsivle: "Ödev arşivlendi (teslimler korunur).", arsivden_cikar: "Ödev arşivden çıkarıldı." }[eylem]);
    if (takipOdevId) takipYukle(); else odevListesiniYukle();
  } catch (hata) { bildir(hata.message, true); }
}

$("#btn-odev-yenile").addEventListener("click", odevListesiniYukle);
$("#btn-takip-geri").addEventListener("click", () => takipGoster(false));

/* ---- ödev formu ---- */

function sinifSecenekleri(secim, seciliId) {
  secim.replaceChildren();
  for (const s of odevSiniflar) {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = `${s.ad} (${s.ogrenci_sayisi} öğrenci)`;
    secim.append(o);
  }
  if (seciliId) secim.value = seciliId;
}

function odevFormunuAc(odev = null) {
  if (!odevSiniflar.length) {
    bildir("Önce bir sınıf listesi ekleyin (M3-S2 Sınıflar ve Kodlar).", true);
    return;
  }
  duzenlenenOdevId = odev ? odev.id : null;
  $("#odev-pencere-baslik").textContent = odev ? "Ödevi düzenle" : "Yeni ödev";
  $("#odev-form-hata").textContent = "";
  $("#of-baslik").value = odev ? odev.baslik : "";
  sinifSecenekleri($("#of-sinif"), odev ? odev.sinif_id : null);
  $("#of-yonerge").value = odev ? odev.yonerge : "";
  $("#of-son").value = odev ? odev.son_tarih_giris : "";
  $("#of-gec").checked = odev ? odev.gec_teslim : false;
  const turKap = $("#of-turler");
  turKap.replaceChildren();
  const secili = odev ? odev.turler : odevDurum.varsayilan_turler;
  for (const [ad, etiket] of Object.entries(odevDurum.turler)) {
    turKap.append(el("label", { class: "onay-kutusu" },
      el("input", { type: "checkbox", name: "of-tur", value: ad, checked: secili.includes(ad) }), etiket));
  }
  $("#of-ek").value = odev ? odev.ek_uzantilar.join(", ") : "";
  $("#of-dosya").value = odev ? odev.en_fazla_dosya : 20;
  $("#of-mb").value = odev ? odev.en_fazla_mb : 100;
  $("#of-klasor").checked = odev ? odev.klasor_izni : true;
  $("#odev-penceresi").showModal();
}

$("#btn-yeni-odev").addEventListener("click", () => odevFormunuAc());

$("#of-kaydet").addEventListener("click", async () => {
  const govde = {
    baslik: $("#of-baslik").value.trim(),
    sinif_id: $("#of-sinif").value,
    yonerge: $("#of-yonerge").value,
    son_tarih: $("#of-son").value || null,
    gec_teslim: $("#of-gec").checked,
    turler: $$('input[name="of-tur"]:checked').map((k) => k.value),
    ek_uzantilar: $("#of-ek").value.split(",").map((s) => s.trim()).filter(Boolean),
    en_fazla_dosya: Number($("#of-dosya").value),
    en_fazla_mb: Number($("#of-mb").value),
    klasor_izni: $("#of-klasor").checked,
  };
  try {
    if (duzenlenenOdevId) {
      await api(`/api/odev/odevler/${duzenlenenOdevId}`, govde, "PUT");
      bildir("Ödev güncellendi.");
    } else {
      await api("/api/odev/odevler", govde);
      bildir("Ödev taslak olarak kaydedildi. Öğrencilerin görmesi için \"Teslimleri aç\" deyin.");
    }
    $("#odev-penceresi").close();
    if (takipOdevId) takipYukle(); else odevListesiniYukle();
  } catch (hata) { $("#odev-form-hata").textContent = hata.message; }
});

/* ---- takip ---- */

async function takipYukle(sessiz = false) {
  if (!takipOdevId) return;
  try { takipVerisi = await api(`/api/odev/odevler/${takipOdevId}`); }
  catch (hata) { if (!sessiz) bildir(hata.message, true); return; }
  const { odev, ogrenciler, ozet } = takipVerisi;
  $("#takip-baslik").textContent = `${odev.baslik} — ${odev.sinif}`;
  $("#takip-bilgi").textContent = `Durum: ${odev.durum_adi}. ` +
    (odev.son_tarih ? `Son teslim: ${odev.son_tarih}` : "Süre sınırı yok") +
    (odev.gec_teslim ? " (geç teslim kabul ediliyor)." : ".");
  $("#takip-tamam").hidden = !ozet.tamami_teslim_etti;

  const kartlar = $("#takip-ozet");
  kartlar.replaceChildren();
  for (const [sayi, etiket] of [[`${ozet.teslim_eden} / ${ozet.toplam}`, "Teslim eden"],
    [ozet.gec, "Geç teslim"], [ozet.etmedi, "Teslim etmedi"], [ozet.yukleniyor, "Yükleme sürüyor"],
    [ozet.hata, "Yükleme hatası"]]) {
    kartlar.append(ozetKarti(sayi, etiket));
  }

  const eylemler = $("#takip-eylemler");
  eylemler.replaceChildren();
  if (odev.durum !== "arsiv") eylemler.append(dugme("Ödevi düzenle", "M3-S1-B13", () => odevFormunuAc(odev)));
  for (const eylem of odevEylemleri(odev.durum)) {
    const [metin, kod, sinif] = ODEV_EYLEMLERI[eylem];
    eylemler.append(dugme(eylem === "ac" && odev.durum === "kapali" ? "Yeniden aç" : metin, kod,
      () => durumDegistir(odev.id, eylem, odev.baslik), sinif || "ikincil"));
  }

  // Seçim kutularının durumu yenilemede korunur
  const secili = new Set(seciliOgrenciler());
  const kap = $("#takip-tablosu");
  const tablo = document.createElement("table");
  tabloBasligi(tablo, ["Seç", "No", "Ad soyad", "Durum", "Son teslim", "Sürüm", "Dosya", "Boyut", ""]);
  for (const s of ogrenciler) {
    const tr = document.createElement("tr");
    const secTd = document.createElement("td");
    const kutu = document.createElement("input");
    kutu.type = "checkbox"; kutu.name = "takip-sec"; kutu.value = s.ogrenci_id;
    kutu.checked = secili.has(s.ogrenci_id);
    kutu.disabled = !s.teslimler.length;
    kutu.setAttribute("aria-label", `${s.ad_soyad} seç`);
    secTd.append(kutu);
    const [etiket, ton] = TESLIM_DURUMLARI[s.durum];
    const durumTd = document.createElement("td");
    durumTd.append(rozet(etiket, ton));
    if (s.durum === "hata" && s.son_hata) {
      const alt = document.createElement("div"); alt.className = "ipucu"; alt.textContent = s.son_hata;
      durumTd.append(alt);
    }
    const hucreler = [s.numara, s.ad_soyad].map((d) => { const td = document.createElement("td"); td.append(guvenliMetin(d)); return td; });
    const zaman = document.createElement("td"); zaman.append(guvenliMetin(s.son_zaman || "—"));
    const surum = document.createElement("td");
    surum.append(guvenliMetin(s.surum ? `Teslim ${s.surum}` : "—"));
    const dosya = document.createElement("td"); dosya.append(guvenliMetin(s.dosya_sayisi ?? "—"));
    const boyut = document.createElement("td"); boyut.append(guvenliMetin(boyutYaz(s.toplam_bayt)));
    const islem = document.createElement("td");
    islem.className = "dugme-grubu";
    if (s.teslimler.length) {
      const no = kimlikSlug(s.numara) || "OGR";
      islem.append(dugme("Dosyalar", `M3-S1-B15-${no}`, () => dosyalariGoster(s, s.teslimler[0]), "ikincil kucuk"));
      islem.append(dugme("Teslimi indir", `M3-S1-B6-${no}`, () => indir(`/api/odev/teslimler/${s.teslimler[0].id}/zip`), "ikincil kucuk"));
      if (s.teslimler.length > 1) {
        const gecmis = document.createElement("details");
        const ozet2 = document.createElement("summary");
        ozet2.textContent = `Geçmiş (${s.teslimler.length})`;
        gecmis.append(ozet2);
        for (const t of s.teslimler) {
          const satir = document.createElement("div");
          satir.append(dugme(`Teslim ${t.surum} — ${t.zaman}${t.gec ? " (geç)" : ""}`,
            `M3-S1-B21-${kimlikSlug(s.numara)}-${t.surum}`, () => dosyalariGoster(s, t), "baglanti-dugme"));
          gecmis.append(satir);
        }
        islem.append(gecmis);
      }
    }
    tr.append(secTd, ...hucreler, durumTd, zaman, surum, dosya, boyut, islem);
    tablo.append(tr);
  }
  const acikGecmis = new Set($$("#takip-tablosu details[open]").map((d) =>
    d.closest("tr").querySelector('input[name="takip-sec"]').value));
  kap.replaceChildren(tablo);
  $$("#takip-tablosu details").forEach((d) => {
    if (acikGecmis.has(d.closest("tr").querySelector('input[name="takip-sec"]').value)) d.open = true;
  });
}

function seciliOgrenciler() {
  return $$('input[name="takip-sec"]:checked').map((k) => k.value);
}

async function dosyalariGoster(ogrenci, t) {
  let dosyalar;
  try { dosyalar = await api(`/api/odev/teslimler/${t.id}/dosyalar`); }
  catch (hata) { bildir(hata.message, true); return; }
  $("#dosyalar-baslik").textContent =
    `${ogrenci.numara} ${ogrenci.ad_soyad} — Teslim ${t.surum} (${t.zaman}${t.gec ? ", geç" : ""}) · No: ${t.teslim_no}`;
  const tablo = document.createElement("table");
  tabloBasligi(tablo, ["Dosya", "Boyut", "SHA-256 (ilk 12)", ""]);
  for (const d of dosyalar) {
    const tr = document.createElement("tr");
    const ad = document.createElement("td"); ad.append(guvenliMetin(d.goreli_yol));
    const boyut = document.createElement("td"); boyut.append(guvenliMetin(boyutYaz(d.boyut)));
    const ozet = document.createElement("td"); ozet.className = "parmakizi";
    ozet.append(guvenliMetin((d.sha256 || "").slice(0, 12)));
    const islem = document.createElement("td");
    islem.append(dugme("İndir", `M3-S1-B18-${d.sira}`, () => indir(`/api/odev/teslimler/${t.id}/dosya/${d.sira}`), "ikincil kucuk"));
    tr.append(ad, boyut, ozet, islem);
    tablo.append(tr);
  }
  $("#dosyalar-listesi").replaceChildren(tablo);
  $("#dosyalar-zip").href = `/api/odev/teslimler/${t.id}/zip`;
  $("#dosyalar-zip").onclick = (o) => { if (window.PSY_DEMO) { o.preventDefault(); indir(`/api/odev/teslimler/${t.id}/zip`); } };
  $("#dosyalar-penceresi").showModal();
}

$("#btn-zip-tum").addEventListener("click", () => {
  if (!takipOdevId) return;
  const tum = $("#zip-tum-surum").checked ? 1 : 0;
  indir(`/api/odev/odevler/${takipOdevId}/zip?tum_surumler=${tum}`);
});

$("#btn-zip-secili").addEventListener("click", () => {
  const secili = seciliOgrenciler();
  if (!secili.length) { bildir("Önce listeden öğrenci seçin.", true); return; }
  const tum = $("#zip-tum-surum").checked ? 1 : 0;
  indir(`/api/odev/odevler/${takipOdevId}/zip?tum_surumler=${tum}&ogrenciler=${encodeURIComponent(secili.join(","))}`);
});

/* ---- sınıf listeleri ve kodlar ---- */

async function sinifListesiniYukle() {
  try { odevSiniflar = await api("/api/odev/siniflar"); } catch (hata) { bildir(hata.message, true); return; }
  const secim = $("#sinif-sec");
  const onceki = secim.value;
  sinifSecenekleri(secim, onceki);
  if (!odevSiniflar.some((s) => s.id === onceki) && odevSiniflar.length) secim.value = odevSiniflar[0].id;
}

async function ogrenciListesiniYukle() {
  await sinifListesiniYukle();
  const sinifId = $("#sinif-sec").value;
  const kap = $("#ogrenci-tablosu");
  kap.replaceChildren();
  $("#sinif-csv-indir").href = sinifId ? `/api/odev/siniflar/${sinifId}/csv` : "#";
  $("#sinif-csv-indir").onclick = (o) => { if (window.PSY_DEMO) { o.preventDefault(); indir($("#sinif-csv-indir").getAttribute("href")); } };
  if (!sinifId) {
    const p = document.createElement("p"); p.className = "ipucu";
    p.textContent = "Henüz sınıf yok. CSV içe aktarın veya sınıf ekleyin.";
    kap.append(p); return;
  }
  let liste;
  try { liste = await api(`/api/odev/siniflar/${sinifId}/ogrenciler`); } catch (hata) { bildir(hata.message, true); return; }
  const tablo = document.createElement("table");
  tabloBasligi(tablo, ["Seç", "No", "Ad soyad", "Teslim kodu", ""]);
  for (const o of liste) {
    const tr = document.createElement("tr");
    const secTd = document.createElement("td");
    const kutu = document.createElement("input");
    kutu.type = "checkbox"; kutu.name = "ogrenci-sec"; kutu.value = o.id;
    kutu.setAttribute("aria-label", `${o.ad_soyad} seç`);
    secTd.append(kutu);
    const no = document.createElement("td"); no.append(guvenliMetin(o.numara));
    const ad = document.createElement("td"); ad.append(guvenliMetin(o.ad_soyad));
    const kodTd = document.createElement("td");
    kodTd.append(o.kodu_var ? rozet("Üretildi", "iyi") : rozet("Kod yok", "orta"));
    if (o.kod_zamani) {
      const alt = document.createElement("div"); alt.className = "ipucu";
      alt.textContent = new Date(o.kod_zamani).toLocaleString("tr-TR");
      kodTd.append(alt);
    }
    const islem = document.createElement("td");
    islem.className = "dugme-grubu";
    islem.append(dugme("Adı düzenle", `M3-S2-B11-${kimlikSlug(o.numara)}`, async () => {
      const yeni = prompt("Ad soyad:", o.ad_soyad);
      if (!yeni || yeni.trim() === o.ad_soyad) return;
      try { await api(`/api/odev/ogrenciler/${o.id}`, { ad_soyad: yeni.trim() }, "PATCH"); ogrenciListesiniYukle(); }
      catch (hata) { bildir(hata.message, true); }
    }, "ikincil kucuk"));
    islem.append(dugme("Sil", `M3-S2-B10-${kimlikSlug(o.numara)}`, async () => {
      if (!confirm(`${o.numara} ${o.ad_soyad} listeden silinsin mi?`)) return;
      try { await api(`/api/odev/ogrenciler/${o.id}`, null, "DELETE"); ogrenciListesiniYukle(); }
      catch (hata) { bildir(hata.message, true); }
    }, "tehlikeli kucuk"));
    tr.append(secTd, no, ad, kodTd, islem);
    tablo.append(tr);
  }
  kap.append(tablo);
}

$("#sinif-sec").addEventListener("change", ogrenciListesiniYukle);

$("#sinif-ekle-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  try {
    const { id } = await api("/api/odev/siniflar", { ad: $("#yeni-sinif").value.trim() });
    $("#yeni-sinif").value = "";
    await sinifListesiniYukle();
    $("#sinif-sec").value = id;
    ogrenciListesiniYukle();
  } catch (hata) { bildir(hata.message, true); }
});

$("#btn-sinif-sil").addEventListener("click", async () => {
  const sinifId = $("#sinif-sec").value;
  const sinif = odevSiniflar.find((s) => s.id === sinifId);
  if (!sinif || !confirm(`${sinif.ad} sınıfı ve öğrenci listesi silinsin mi?`)) return;
  try { await api(`/api/odev/siniflar/${sinifId}`, null, "DELETE"); bildir("Sınıf silindi."); ogrenciListesiniYukle(); }
  catch (hata) { bildir(hata.message, true); }
});

$("#ogrenci-ekle-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  const sinifId = $("#sinif-sec").value;
  if (!sinifId) { bildir("Önce sınıf ekleyin veya seçin.", true); return; }
  try {
    await api(`/api/odev/siniflar/${sinifId}/ogrenciler`,
      { numara: $("#yeni-numara").value.trim(), ad_soyad: $("#yeni-ad").value.trim() });
    $("#yeni-numara").value = ""; $("#yeni-ad").value = "";
    ogrenciListesiniYukle();
  } catch (hata) { bildir(hata.message, true); }
});

$("#csv-dosya").addEventListener("change", () => {
  const d = $("#csv-dosya").files[0];
  $("#csv-ad").textContent = d ? d.name : "";
});

$("#btn-csv-aktar").addEventListener("click", async () => {
  const dosya = $("#csv-dosya").files[0];
  if (!dosya) { bildir("Önce CSV dosyası seçin.", true); return; }
  const b64 = await new Promise((coz, reddet) => {
    const okuyucu = new FileReader();
    okuyucu.onload = () => coz(okuyucu.result.split(",")[1]);
    okuyucu.onerror = reddet;
    okuyucu.readAsDataURL(dosya);
  });
  try {
    const sonuc = await api("/api/odev/ice-aktar", { icerik_b64: b64 });
    $("#csv-sonuc").textContent = `${sonuc.eklenen} öğrenci eklendi, ${sonuc.guncellenen} güncellendi.` +
      (sonuc.hatalar.length ? ` Hatalı satırlar: ${sonuc.hatalar.join(" · ")}` : "");
    $("#csv-dosya").value = "";
    $("#csv-ad").textContent = "";
    ogrenciListesiniYukle();
  } catch (hata) { bildir(hata.message, true); }
});

async function kodUret(govde, aciklama) {
  if (!confirm(`${aciklama}\n\nYeni kod üretilen öğrencilerin eski kodları hemen geçersiz olur. Devam edilsin mi?`)) return;
  try {
    sonKodlar = await api("/api/odev/kod-uret", govde);
  } catch (hata) { bildir(hata.message, true); return; }
  const tablo = document.createElement("table");
  tabloBasligi(tablo, ["Sınıf", "No", "Ad soyad", "Teslim kodu"]);
  for (const k of sonKodlar) {
    const tr = document.createElement("tr");
    for (const d of [k.sinif, k.numara, k.ad_soyad]) { const td = document.createElement("td"); td.append(guvenliMetin(d)); tr.append(td); }
    const kodTd = document.createElement("td"); kodTd.className = "kod-hucre"; kodTd.textContent = k.kod;
    tr.append(kodTd);
    tablo.append(tr);
  }
  $("#kod-listesi").replaceChildren(tablo);
  $("#kod-penceresi").showModal();
  ogrenciListesiniYukle();
}

$("#btn-kod-eksik").addEventListener("click", () => {
  const sinifId = $("#sinif-sec").value;
  if (!sinifId) return;
  kodUret({ sinif_id: sinifId, sadece_kodsuz: true }, "Kodu olmayan öğrencilere kod üretilecek.");
});

$("#btn-kod-secili").addEventListener("click", () => {
  const secili = $$('input[name="ogrenci-sec"]:checked').map((k) => k.value);
  if (!secili.length) { bildir("Önce listeden öğrenci seçin.", true); return; }
  kodUret({ ogrenci_idler: secili }, `${secili.length} öğrenciye yeni kod üretilecek.`);
});

$("#btn-kod-yazdir").addEventListener("click", () => {
  const alan = $("#yazdir-alani");
  alan.replaceChildren();
  const adres = odevDurum ? odevDurum.adres : "";
  const okulAdi = (Uyg.okul && Uyg.okul.ad) || "Ödev Teslim";
  for (const k of sonKodlar) {
    const kart = document.createElement("div");
    kart.className = "kod-karti";
    const baslik = document.createElement("strong"); baslik.textContent = `${okulAdi} — Ödev Teslim`;
    const kim = document.createElement("div"); kim.textContent = `${k.ad_soyad} — ${k.sinif}, No: ${k.numara}`;
    const kod = document.createElement("div"); kod.className = "kart-kod"; kod.textContent = k.kod;
    const nasil = document.createElement("div"); nasil.className = "kart-not";
    nasil.textContent = `Adres: ${adres} · Sınıfını, numaranı ve bu kodu yaz. Kodunu kimseyle paylaşma.`;
    kart.append(baslik, kim, kod, nasil);
    alan.append(kart);
  }
  window.print();
});

/* ---- M3-S1 Masaüstüne bağlantı / dosya dağıtımı ---- */
if ($("#m3s1-url-gonder")) {
  $("#m3s1-url-gonder").addEventListener("click", async () => {
    const baslik = $("#m3s1-url-baslik").value.trim() || "Ders Bağlantısı";
    const url = $("#m3s1-url-adres").value.trim();
    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      bildir("Geçerli bir http:// veya https:// web adresi yazın.", true);
      return;
    }
    const hedefler = await onayIste({
      islem: "sinif", cihazlar: Secim.liste(),
      baslik: `Masaüstüne bağlantı gönder — ${baslik}`,
      aciklama: `Seçili öğrenci bilgisayarlarının Masaüstü klasörüne “${url}” kısayolu oluşturulacaktır.`,
    });
    if (hedefler) isBaslat("/api/sinif/masaustu-url", { cihazlar: hedefler, baslik, url });
  });
}

if ($("#m3s1-dosya-gonder")) {
  $("#m3s1-dosya-gonder").addEventListener("click", async () => {
    const dosya = $("#m3s1-dosya-sec").files[0];
    if (!dosya) { bildir("Önce dağıtılacak dosyayı seçin.", true); return; }
    if (dosya.size > 20 * 1024 * 1024) { bildir("Masaüstüne dağıtılacak dosya en çok 20 MB olabilir.", true); return; }
    const b64 = await new Promise((coz, reddet) => {
      const okuyucu = new FileReader();
      okuyucu.onload = () => coz(okuyucu.result.split(",")[1]);
      okuyucu.onerror = reddet;
      okuyucu.readAsDataURL(dosya);
    });
    const hedefler = await onayIste({
      islem: "sinif", cihazlar: Secim.liste(),
      baslik: `Masaüstüne dosya dağıt — ${dosya.name}`,
      aciklama: `“${dosya.name}” (${boyutYaz(dosya.size)}) seçili öğrenci bilgisayarlarının Masaüstü klasörüne kopyalanacaktır.`,
    });
    if (hedefler) {
      await isBaslat("/api/sinif/masaustu-dosya", { cihazlar: hedefler, dosya_adi: dosya.name, icerik_b64: b64 });
      $("#m3s1-dosya-sec").value = "";
    }
  });
}

/* Kodlar pencere kapanınca bellekten ve sayfadan silinir. Tek bir olaya
 * güvenilmez: düğme doğrudan siler; ESC (cancel) ve close da ayrıca siler. */
function kodlariTemizle() {
  sonKodlar = [];
  $("#kod-listesi").replaceChildren();
  $("#yazdir-alani").replaceChildren();
}
$("#btn-kod-kapat").addEventListener("click", () => {
  kodlariTemizle();
  $("#kod-penceresi").close();
});
$("#kod-penceresi").addEventListener("cancel", kodlariTemizle);
$("#kod-penceresi").addEventListener("close", kodlariTemizle);
window.addEventListener("afterprint", () => $("#yazdir-alani").replaceChildren());

sayfaKaydet("M3-S1", m3s1);
sayfaKaydet("M3-S2", m3s2);
