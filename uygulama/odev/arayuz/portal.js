/* Ödev Teslim — öğrenci portalı (sade, çerçevesiz JavaScript).
 * Giriş bilgileri tarayıcıda saklanmaz; oturum yalnız HttpOnly çerezdedir.
 * sessionStorage yalnız süren gönderimin kimliğini tutar (sayfa yenilenirse
 * sunucudaki gerçek durumu sormak için) ve çıkışta silinir. */
"use strict";

const $ = (s) => document.querySelector(s);
const BOSTA_SINIRI_MS = 10 * 60 * 1000;   // ortak bilgisayarda kısa hareketsizlik süresi
const SURUP_ANAHTARI = "odev_suren_teslim";

let odevler = [];
let odev = null;              // açık ödev
let secim = [];               // {dosya: File, yol, boyut, hata}
let gonderim = null;          // {teslimId, dosyalar, sonraki, xhr, iptal}
let sonEtkinlik = Date.now();

/* ---- yardımcılar ---- */

async function api(yol, govde = null, metod = null) {
  const secenek = { method: metod || (govde ? "POST" : "GET"), headers: { "X-Odev": "1" },
                    credentials: "same-origin" };
  if (govde) {
    secenek.headers["Content-Type"] = "application/json";
    secenek.body = JSON.stringify(govde);
  }
  let yanit;
  try { yanit = await fetch(yol, secenek); }
  catch (_) { throw Object.assign(new Error("Bağlantı kurulamadı. Ağ bağlantınızı kontrol edin."), { ag: true }); }
  let veri = null;
  try { veri = await yanit.json(); } catch (_) { /* gövdesiz */ }
  if (yanit.status === 401 && yol !== "/api/giris") { oturumBitti(veri && veri.detail); }
  if (!yanit.ok) {
    throw Object.assign(new Error((veri && veri.detail) || `Sunucu hatası (${yanit.status})`),
                        { durum: yanit.status });
  }
  return veri;
}

function boyutMetni(bayt) {
  if (bayt >= 1048576) return `${(bayt / 1048576).toFixed(bayt >= 10485760 ? 0 : 1)} MB`;
  if (bayt >= 1024) return `${Math.round(bayt / 1024)} KB`;
  return `${bayt} bayt`;
}

function goster(bolum) {
  for (const ad of ["giris", "liste", "odev"]) $(`#${ad}`).classList.toggle("gizli", ad !== bolum);
}

function bilgi(metin) {
  const kutu = $("#bilgi");
  kutu.textContent = metin;
  kutu.classList.toggle("gizli", !metin);
}

function uzanti(yol) {
  const ad = yol.split("/").pop().toLowerCase();
  if (ad.startsWith(".") && ad.split(".").length === 2) return ad.slice(1);
  return ad.includes(".") ? ad.split(".").pop() : "";
}

/* ---- giriş / çıkış ---- */

async function baslat() {
  try {
    const ben = await api("/api/ben");
    girisYapildi(ben);
  } catch (_) {
    await girisEkrani();
  }
}

async function girisEkrani() {
  goster("giris");
  $("#kimlik").classList.add("gizli");
  const secim = $("#g-sinif");
  secim.replaceChildren();
  try {
    const siniflar = await api("/api/siniflar");
    const bos = document.createElement("option");
    bos.value = ""; bos.textContent = siniflar.length ? "Sınıfınızı seçin" : "Henüz sınıf tanımlanmadı";
    secim.append(bos);
    for (const s of siniflar) {
      const o = document.createElement("option");
      o.value = s.id; o.textContent = s.ad;
      secim.append(o);
    }
  } catch (hata) { $("#giris-hata").textContent = hata.message; }
}

$("#giris-formu").addEventListener("submit", async (olay) => {
  olay.preventDefault();
  $("#giris-hata").textContent = "";
  try {
    await api("/api/giris", { sinif_id: $("#g-sinif").value, numara: $("#g-numara").value.trim(),
                              kod: $("#g-kod").value });
    $("#g-kod").value = "";
    $("#g-numara").value = "";
    girisYapildi(await api("/api/ben"));
  } catch (hata) {
    $("#g-kod").value = "";
    $("#giris-hata").textContent = hata.message;
  }
});

function girisYapildi(ben) {
  $("#kimlik-metin").textContent = `${ben.ad_soyad} · ${ben.sinif} · ${ben.numara}`;
  $("#kimlik").classList.remove("gizli");
  bilgi("");
  sonEtkinlik = Date.now();
  listeyiYukle().then(suremiKontrol);
}

async function cikisYap(mesaj = "") {
  if (gonderim && gonderim.xhr) gonderim.xhr.abort();
  gonderim = null;
  try { await api("/api/cikis", {}); } catch (_) { /* yine de yerel durumu sil */ }
  temizleYerel();
  await girisEkrani();
  bilgi(mesaj);
}

function oturumBitti(mesaj) {
  if (!$("#giris").classList.contains("gizli")) return;
  temizleYerel();
  girisEkrani();
  bilgi(mesaj || "Oturumunuz kapandı; yeniden giriş yapın.");
}

/* Sonraki öğrenci öncekinin dosya listesini göremesin. */
function temizleYerel() {
  try { sessionStorage.removeItem(SURUP_ANAHTARI); } catch (_) { /* depolama kapalı */ }
  odevler = []; odev = null; secim = []; gonderim = null;
  $("#odev-kartlari").replaceChildren();
  $("#gecmis").replaceChildren();
  $("#secim-tablo tbody").replaceChildren();
  $("#makbuz-bilgi").replaceChildren();
  $("#kimlik-metin").textContent = "";
}

$("#cikis").addEventListener("click", () => cikisYap("Çıkış yapıldı."));

/* Hareketsizlik: yükleme sürmüyorsa oturum kapatılır. */
for (const olay of ["click", "keydown", "mousemove", "touchstart", "dragover"]) {
  document.addEventListener(olay, () => { sonEtkinlik = Date.now(); }, { passive: true });
}
setInterval(() => {
  const girisli = !$("#kimlik").classList.contains("gizli");
  if (girisli && !gonderim && Date.now() - sonEtkinlik > BOSTA_SINIRI_MS) {
    cikisYap("Uzun süre işlem yapılmadığı için oturum kapatıldı.");
  }
}, 30000);

window.addEventListener("beforeunload", (olay) => {
  if (gonderim) { olay.preventDefault(); olay.returnValue = ""; }
});

/* ---- ödev listesi ---- */

async function listeyiYukle() {
  goster("liste");
  try { odevler = await api("/api/odevler"); } catch (hata) { bilgi(hata.message); return; }
  const kap = $("#odev-kartlari");
  kap.replaceChildren();
  $("#liste-bos").classList.toggle("gizli", odevler.length > 0);
  for (const o of odevler) {
    const kart = document.createElement("button");
    kart.className = "odev-karti";
    const baslik = document.createElement("strong");
    baslik.textContent = o.baslik;
    const sure = document.createElement("span");
    sure.textContent = sureMetni(o);
    const durum = document.createElement("span");
    durum.className = o.son_teslim ? "rozet iyi" : "rozet notr";
    durum.textContent = o.son_teslim
      ? `Teslim ${o.son_teslim.surum} alındı${o.son_teslim.gec ? " (geç)" : ""}` : "Teslim edilmedi";
    kart.append(baslik, sure, durum);
    kart.addEventListener("click", () => odevAc(o.id));
    kap.append(kart);
  }
}

function sureMetni(o) {
  if (!o.son_tarih) return "Süre sınırı yok";
  if (o.kalan_sn <= 0) return o.gec_teslim ? `Süre doldu (${o.son_tarih}) — geç teslim kabul ediliyor`
                                           : `Süre doldu (${o.son_tarih})`;
  const gun = Math.floor(o.kalan_sn / 86400);
  const saat = Math.floor((o.kalan_sn % 86400) / 3600);
  const dk = Math.floor((o.kalan_sn % 3600) / 60);
  const kalan = gun ? `${gun} gün ${saat} saat` : saat ? `${saat} saat ${dk} dakika` : `${dk} dakika`;
  return `Son teslim: ${o.son_tarih} — ${kalan} kaldı`;
}

$("#geri").addEventListener("click", () => {
  if (gonderim) { bilgi("Gönderim sürüyor; önce bitmesini bekleyin veya iptal edin."); return; }
  listeyiYukle();
});

/* ---- ödev sayfası ---- */

async function odevAc(odevId) {
  odev = odevler.find((o) => o.id === odevId);
  if (!odev) return;
  goster("odev");
  bilgi("");
  $("#o-baslik").textContent = odev.baslik;
  $("#o-sure").textContent = sureMetni(odev);
  $("#o-yonerge").textContent = odev.yonerge || "";
  $("#o-kurallar").textContent =
    `Kabul edilen türler: ${odev.uzantilar.join(", ")}. En çok ${odev.en_fazla_dosya} dosya, ` +
    `toplam ${boyutMetni(odev.en_fazla_bayt)}.` + (odev.klasor_izni ? " Klasör yüklenebilir." : "");
  const klasorDestegi = "webkitdirectory" in document.createElement("input");
  $("#klasor-dugme").classList.toggle("gizli", !odev.klasor_izni || !klasorDestegi);
  $("#klasor-uyari").classList.toggle("gizli", !odev.klasor_izni || klasorDestegi);
  $("#makbuz").classList.add("gizli");
  $("#yukleme-karti").classList.remove("gizli");
  secimiSifirla();
  if (!odev.kabul) {
    $("#yukleme-hata").textContent = odev.red_nedeni;
    $("#gonder").disabled = true;
  }
  gecmisiYukle();
}

async function gecmisiYukle() {
  const kap = $("#gecmis");
  kap.replaceChildren();
  let teslimler = [];
  try { teslimler = await api(`/api/odevler/${odev.id}/teslimlerim`); } catch (_) { return; }
  if (!teslimler.length) {
    const p = document.createElement("p"); p.className = "ipucu"; p.textContent = "Henüz teslim yok.";
    kap.append(p); return;
  }
  for (const t of teslimler) {
    const ayrinti = document.createElement("details");
    const ozet = document.createElement("summary");
    ozet.textContent = `Teslim ${t.surum} — ${t.zaman}${t.gec ? " (geç teslim)" : ""} — ` +
      `${t.dosya_sayisi} dosya, ${boyutMetni(t.toplam_bayt)} — No: ${t.teslim_no}`;
    const liste = document.createElement("ul");
    for (const ad of t.dosyalar) {
      const li = document.createElement("li"); li.textContent = ad; liste.append(li);
    }
    ayrinti.append(ozet, liste);
    kap.append(ayrinti);
  }
}

/* ---- dosya seçimi ---- */

function secimiSifirla() {
  secim = [];
  $("#yukleme-hata").textContent = "";
  $("#ilerleme").classList.add("gizli");
  $("#iptal").classList.add("gizli");
  $("#yeniden").classList.add("gizli");
  $("#gonder").classList.remove("gizli");
  secimiCiz();
}

function ekle(ogeler) {
  if (gonderim) return;
  $("#makbuz").classList.add("gizli");
  $("#yukleme-hata").textContent = "";
  for (const { dosya, yol } of ogeler) {
    const temiz = (yol || dosya.name).replace(/\\/g, "/").replace(/^\/+/, "");
    if (secim.some((s) => s.yol.toLowerCase() === temiz.toLowerCase())) continue;
    secim.push({ dosya, yol: temiz, boyut: dosya.size, hata: null });
  }
  secimiCiz();
}

function denetle() {
  const gorulen = new Set();
  for (const s of secim) {
    s.hata = s.sunucuHatasi || null;   // sunucunun reddettiği dosya işaretli kalır
    if (s.hata) { gorulen.add(s.yol.toLowerCase()); continue; }
    const parcalar = s.yol.split("/");
    if (parcalar.some((p) => p === ".." || /[\x00-\x1f\\:*?"<>|]/.test(p))) s.hata = "Geçersiz dosya adı";
    else if (!odev.klasor_izni && parcalar.length > 1) s.hata = "Bu ödev klasör kabul etmiyor";
    else if (!odev.uzantilar.includes(uzanti(s.yol))) s.hata = "Bu dosya türü kabul edilmiyor";
    else if (gorulen.has(s.yol.toLowerCase())) s.hata = "Aynı ad iki kez seçildi";
    gorulen.add(s.yol.toLowerCase());
  }
  const toplam = secim.reduce((t, s) => t + s.boyut, 0);
  const genel = [];
  if (secim.length > odev.en_fazla_dosya) genel.push(`En çok ${odev.en_fazla_dosya} dosya gönderilebilir.`);
  if (toplam > odev.en_fazla_bayt) genel.push(`Toplam boyut sınırı ${boyutMetni(odev.en_fazla_bayt)}.`);
  return { toplam, genel, hatali: secim.filter((s) => s.hata).length };
}

function secimiCiz() {
  const tablo = $("#secim-tablo");
  const govde = tablo.querySelector("tbody");
  govde.replaceChildren();
  if (!odev) return;
  const { toplam, genel, hatali } = denetle();
  tablo.classList.toggle("gizli", secim.length === 0);
  secim.forEach((s, sira) => {
    const tr = document.createElement("tr");
    if (s.hata) tr.className = "hatali";
    const ad = document.createElement("td"); ad.textContent = s.yol;
    const boyut = document.createElement("td"); boyut.textContent = boyutMetni(s.boyut);
    const durum = document.createElement("td");
    durum.textContent = s.hata ? `✗ ${s.hata}` : (s.durum || "Hazır");
    const islem = document.createElement("td");
    const cikar = document.createElement("button");
    cikar.className = "ikincil kucuk";
    cikar.textContent = "Çıkar";
    cikar.setAttribute("aria-label", `${s.yol} dosyasını seçimden çıkar`);
    cikar.disabled = Boolean(gonderim);
    cikar.addEventListener("click", () => { secim.splice(sira, 1); secimiCiz(); });
    islem.append(cikar);
    tr.append(ad, boyut, durum, islem);
    govde.append(tr);
  });
  const ozet = secim.length ? `${secim.length} dosya seçildi — toplam ${boyutMetni(toplam)}.` : "";
  const uyarilar = [...genel];
  if (hatali) uyarilar.push(`${hatali} dosya kabul edilmiyor; seçimden çıkarın.`);
  $("#secim-ozet").textContent = [ozet, ...uyarilar].filter(Boolean).join(" ");
  $("#secim-ozet").classList.toggle("uyari", uyarilar.length > 0);
  $("#gonder").disabled = !odev.kabul || !secim.length || hatali > 0 || genel.length > 0 || Boolean(gonderim);
}

$("#dosya-dugme").addEventListener("click", () => $("#dosya-sec").click());
$("#klasor-dugme").addEventListener("click", () => $("#klasor-sec").click());
$("#temizle").addEventListener("click", () => { if (!gonderim) secimiSifirla(); });
for (const kimlik of ["#dosya-sec", "#klasor-sec"]) {
  $(kimlik).addEventListener("change", (olay) => {
    ekle([...olay.target.files].map((f) => ({ dosya: f, yol: f.webkitRelativePath || f.name })));
    olay.target.value = "";
  });
}

const birak = $("#birak");
birak.addEventListener("click", () => $("#dosya-sec").click());
birak.addEventListener("keydown", (o) => { if (o.key === "Enter" || o.key === " ") { o.preventDefault(); $("#dosya-sec").click(); } });
birak.addEventListener("dragover", (o) => { o.preventDefault(); birak.classList.add("uzerinde"); });
birak.addEventListener("dragleave", () => birak.classList.remove("uzerinde"));
birak.addEventListener("drop", async (olay) => {
  olay.preventDefault();
  birak.classList.remove("uzerinde");
  // Girdiler olay bitmeden alınmalı; sonra klasörler eşzamansız gezilir.
  const girdiler = [...olay.dataTransfer.items]
    .map((i) => (i.webkitGetAsEntry ? i.webkitGetAsEntry() : null)).filter(Boolean);
  if (!girdiler.length) {
    ekle([...olay.dataTransfer.files].map((f) => ({ dosya: f, yol: f.name })));
    return;
  }
  const sonuc = [];
  async function gez(girdi, onek) {
    if (girdi.isFile) {
      const dosya = await new Promise((coz, reddet) => girdi.file(coz, reddet));
      sonuc.push({ dosya, yol: onek + dosya.name });
    } else if (girdi.isDirectory) {
      const okuyucu = girdi.createReader();
      for (;;) {
        const parti = await new Promise((coz, reddet) => okuyucu.readEntries(coz, reddet));
        if (!parti.length) break;
        for (const alt of parti) await gez(alt, `${onek}${girdi.name}/`);
      }
    }
  }
  try {
    for (const g of girdiler) await gez(g, "");
    ekle(sonuc);
  } catch (_) {
    $("#yukleme-hata").textContent = "Bırakılan öğeler okunamadı; Dosya seç veya Klasör seç düğmesini kullanın.";
  }
});

/* ---- gönderim ---- */

function asama(metin) { $("#asama").textContent = metin; }

function ilerlemeyiGuncelle(ekBayt = 0) {
  const toplam = gonderim.dosyalar.reduce((t, d) => t + d.boyut, 0) || 1;
  const biten = gonderim.dosyalar.filter((d) => d.bitti).reduce((t, d) => t + d.boyut, 0);
  const yuzde = Math.min(100, Math.floor(((biten + ekBayt) / toplam) * 100));
  $("#cubuk").value = yuzde;
  $("#ilerleme-metin").textContent =
    `${boyutMetni(biten + ekBayt)} / ${boyutMetni(toplam)} (%${yuzde})`;
}

function gonderimArayuzu(suruyor) {
  $("#gonder").classList.toggle("gizli", suruyor);
  $("#iptal").classList.toggle("gizli", !suruyor);
  $("#yeniden").classList.add("gizli");
  for (const k of ["#dosya-dugme", "#klasor-dugme", "#temizle"]) $(k).disabled = suruyor;
  $("#ilerleme").classList.remove("gizli");
}

$("#gonder").addEventListener("click", async () => {
  if (!odev || gonderim) return;
  $("#yukleme-hata").textContent = "";
  $("#makbuz").classList.add("gizli");
  gonderim = { teslimId: null, dosyalar: [], xhr: null, iptal: false };
  gonderimArayuzu(true);
  asama("Gönderim hazırlanıyor…");
  try {
    const yanit = await api("/api/teslim/baslat", {
      odev_id: odev.id, dosyalar: secim.map((s) => ({ yol: s.yol, boyut: s.boyut })) });
    gonderim.teslimId = yanit.teslim_id;
    gonderim.dosyalar = yanit.dosyalar.map((d, i) => ({ ...d, oge: secim[i], bitti: false }));
    try { sessionStorage.setItem(SURUP_ANAHTARI, JSON.stringify({ teslimId: yanit.teslim_id, odevId: odev.id })); }
    catch (_) { /* depolama kapalıysa yalnız kurtarma çalışmaz */ }
    await dosyalariGonder();
  } catch (hata) {
    gonderimHatasi(hata);
  }
});

async function dosyalariGonder() {
  const toplam = gonderim.dosyalar.length;
  for (const [i, d] of gonderim.dosyalar.entries()) {
    if (d.bitti) continue;
    if (gonderim.iptal) return;
    asama(`Dosyalar yükleniyor. Bu pencereyi kapatmayın. (${i + 1}/${toplam}) ${d.yol}`);
    d.oge.durum = "Yükleniyor…";
    secimiCiz();
    await dosyaGonder(d);
    d.bitti = true;
    d.oge.durum = "✓ Aktarıldı";
    ilerlemeyiGuncelle();
  }
  secimiCiz();
  asama("Aktarım tamamlandı; teslim doğrulanıyor…");
  let makbuz = null;
  for (let deneme = 0; deneme < 3 && !makbuz; deneme++) {
    try { makbuz = await api(`/api/teslim/${gonderim.teslimId}/tamamla`, {}); }
    catch (hata) {
      if (!hata.ag || deneme === 2) throw hata;   // tamamla idempotenttir; ağ hatasında yinelenir
      await new Promise((coz) => setTimeout(coz, 1500));
    }
  }
  teslimAlindi(makbuz);
}

function dosyaGonder(d) {
  return new Promise((coz, reddet) => {
    const xhr = new XMLHttpRequest();
    gonderim.xhr = xhr;
    xhr.open("PUT", `/api/teslim/${gonderim.teslimId}/dosya/${d.sira}`);
    xhr.setRequestHeader("X-Odev", "1");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (o) => { if (o.lengthComputable) ilerlemeyiGuncelle(o.loaded); };
    xhr.onload = () => {
      gonderim.xhr = null;
      if (xhr.status >= 200 && xhr.status < 300) { coz(); return; }
      let mesaj = `Sunucu hatası (${xhr.status})`;
      try { mesaj = JSON.parse(xhr.responseText).detail || mesaj; } catch (_) { /* düz metin */ }
      if (xhr.status === 401) oturumBitti(mesaj);
      reddet(Object.assign(new Error(mesaj), { durum: xhr.status, dosya: d }));
    };
    xhr.onerror = () => { gonderim.xhr = null; reddet(Object.assign(new Error("ag"), { ag: true, dosya: d })); };
    xhr.onabort = () => { gonderim.xhr = null; reddet(Object.assign(new Error("iptal"), { iptal: true })); };
    xhr.send(d.oge.dosya);
  });
}

function gonderimHatasi(hata) {
  if (!gonderim) return;
  if (hata.iptal || gonderim.iptal) return;
  if (hata.dosya) hata.dosya.oge.durum = "✗ Gönderilemedi";
  if (hata.ag && gonderim.teslimId) {
    $("#yukleme-hata").textContent = "Bağlantı kesildi. Teslim henüz tamamlanmadı; yeniden gönderebilirsiniz.";
    $("#yeniden").classList.remove("gizli");
    $("#iptal").classList.remove("gizli");
    $("#gonder").classList.add("gizli");
    asama("Gönderim durdu.");
    secimiCiz();
    return;   // gönderim nesnesi korunur: "Yeniden dene" kaldığı dosyadan sürdürür
  }
  if (hata.durum === 415 && hata.dosya) hata.dosya.oge.sunucuHatasi = "İçerik türü uzantıyla uyuşmuyor";
  $("#yukleme-hata").textContent = `${hata.message} Teslim tamamlanmadı.`;
  gonderim = null;
  try { sessionStorage.removeItem(SURUP_ANAHTARI); } catch (_) { /* yok */ }
  gonderimArayuzu(false);
  asama("");
  $("#ilerleme").classList.add("gizli");
  secimiCiz();
}

$("#yeniden").addEventListener("click", async () => {
  if (!gonderim) return;
  $("#yukleme-hata").textContent = "";
  gonderimArayuzu(true);
  try { await dosyalariGonder(); }
  catch (hata) {
    if (hata.durum === 409 || hata.durum === 404) {   // gönderim geçersiz olmuş: baştan
      gonderim = null;
      gonderimArayuzu(false);
      $("#ilerleme").classList.add("gizli");
      $("#yukleme-hata").textContent = `${hata.message} Gönder düğmesiyle baştan gönderin.`;
      secim.forEach((s) => { s.durum = null; });
      secimiCiz();
      return;
    }
    gonderimHatasi(hata);
  }
});

$("#iptal").addEventListener("click", async () => {
  if (!gonderim) return;
  gonderim.iptal = true;
  if (gonderim.xhr) gonderim.xhr.abort();
  const kimlik = gonderim.teslimId;
  gonderim = null;
  try { sessionStorage.removeItem(SURUP_ANAHTARI); } catch (_) { /* yok */ }
  if (kimlik) { try { await api(`/api/teslim/${kimlik}/iptal`, {}); } catch (_) { /* zaten geçersiz */ } }
  gonderimArayuzu(false);
  $("#ilerleme").classList.add("gizli");
  secim.forEach((s) => { s.durum = null; });
  secimiCiz();
  $("#yukleme-hata").textContent = "Gönderim iptal edildi. Teslim yapılmadı.";
});

function teslimAlindi(m) {
  gonderim = null;
  try { sessionStorage.removeItem(SURUP_ANAHTARI); } catch (_) { /* yok */ }
  asama("");
  $("#ilerleme").classList.add("gizli");
  $("#yukleme-karti").classList.add("gizli");
  makbuzuCiz(m);
  secim = [];
  gecmisiYukle();
  listeyiGuncelleSessiz();
}

function makbuzuCiz(m) {
  const dl = $("#makbuz-bilgi");
  dl.replaceChildren();
  const satirlar = [
    ["Öğrenci", `${m.ad_soyad} (${m.sinif}, ${m.numara})`],
    ["Ödev", m.odev],
    ["Teslim numarası", `${m.teslim_no} (Teslim ${m.surum})`],
    ["Sunucu teslim zamanı", m.zaman + (m.gec ? " — geç teslim" : "")],
    ["Dosyalar", `${m.dosya_sayisi} dosya, ${boyutMetni(m.toplam_bayt)}`],
  ];
  for (const [ad, deger] of satirlar) {
    const dt = document.createElement("dt"); dt.textContent = ad;
    const dd = document.createElement("dd"); dd.textContent = deger;
    dl.append(dt, dd);
  }
  $("#makbuz").classList.remove("gizli");
  $("#makbuz").focus();
}

$("#yeni-gonderim").addEventListener("click", () => {
  $("#makbuz").classList.add("gizli");
  $("#yukleme-karti").classList.remove("gizli");
  secimiSifirla();
});

async function listeyiGuncelleSessiz() {
  try { odevler = await api("/api/odevler"); } catch (_) { /* önemsiz */ }
}

/* Sayfa yenilendiyse süren gönderimin sunucudaki gerçek durumu gösterilir. */
async function suremiKontrol() {
  let kayit = null;
  try { kayit = JSON.parse(sessionStorage.getItem(SURUP_ANAHTARI) || "null"); } catch (_) { return; }
  if (!kayit) return;
  try { sessionStorage.removeItem(SURUP_ANAHTARI); } catch (_) { /* yok */ }
  try {
    const d = await api(`/api/teslim/${kayit.teslimId}`);
    if (d.durum === "tamamlandi") {
      await odevAc(kayit.odevId);
      $("#yukleme-karti").classList.add("gizli");
      makbuzuCiz(d.makbuz);
    } else {
      bilgi("Önceki gönderiminiz tamamlanmadı; teslim alınmadı. Dosyaları yeniden gönderebilirsiniz.");
      if (d.durum === "yukleniyor") { try { await api(`/api/teslim/${kayit.teslimId}/iptal`, {}); } catch (_) { /* yok */ } }
    }
  } catch (_) { /* başka öğrenciye aitse veya yoksa sessizce geç */ }
}

baslat();
