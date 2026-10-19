/* M1 Envanter: S1 Bilgisayarlar, S2 SSH ve Hesap Hazırlığı, S3 Ağda Bul (S4 Veyon: veyon.js). */
"use strict";

/* ================================================================ M1-S1 Bilgisayarlar */

const SUDO_ROZETI = {
  parolasiz: ["Var", "iyi"], parola_gerekli: ["Parola istiyor", "orta"],
  yetersiz: ["Yetki yok", "kotu"], belirsiz: ["?", "notr"],
};
const GIZLEME_ROZETI = {
  gizli: ["Gizli", "iyi"], yapilandirildi: ["Ayarlı (doğrulanmadı)", "orta"],
  gorunur: ["Görünür", "orta"], desteklenmiyor: ["Desteklenmiyor", "notr"],
};

function kisaSurum(metin) {
  if (!metin) return "—";
  return metin.replace("GNU/Linux ", "").replace(/\s*\(.*\)\s*$/, "");
}

function durumFiltresi(c, deger) {
  const hazir = c.anahtar_durumu === "ok" && c.sudo_durumu === "parolasiz";
  return {
    "": true, hazir: hazir && !c.korunan, hazirlik: !hazir && !c.korunan,
    erisilemiyor: c.erisim === 0, oturum: c.ogrenci_oturumu === 1, korunan: Boolean(c.korunan),
  }[deger];
}

function yonetimHesabiHucresi(c) {
  const kap = el("div", {}, c.baglanti_hesabi ? el("span", { class: "mono", metin: c.baglanti_hesabi })
    : el("span", { class: "alt", metin: "hazırlıkta" }));
  const hepsi = c.yonetim_hesaplari || [];
  if (hepsi.length > 1) kap.append(" ", rozet(`${hepsi.join(" + ")}: tekilleştir`, "orta"));
  return kap;
}

function anahtarHucresi(c) {
  if (c.anahtar_durumu === "ok") return rozet("Kurulu", "iyi");
  if (!c.parmak_izi) return rozet("Kimlik okunmadı", "notr");
  if (!c.parmak_izi_onay) return rozet("Onay bekliyor", "orta");
  return rozet("Kurulu değil", "notr");
}

function gerekenHucresi(c) {
  if (!c.gereken) return rozet("Hazır", "iyi");
  const kap = el("div", { class: "gereken" }, el("span", { metin: c.gereken.metin }));
  if (c.gereken.sayfa) {
    kap.append(" ", dugme("Git", `M1-S1-B8-${satirKimligi(c)}`, () => {
      Secim.sec(c.id, true); Secim.bildir(); git(c.gereken.sayfa);
    }, "ikincil kucuk"));
  }
  return kap;
}

const m1s1 = {
  tablo: null,
  filtre: "",
  veyonFiltre: "",
  pcFiltre: "",
  filtreDugumleri: [],
  kur() {
    this.filtreDugumleri = [...$("#m1s1-filtreler").children];
    const vf = $("#m1s1-veyon-filtre");
    vf.replaceChildren(...VEYON_FILTRELERI.map(([d, a]) => el("option", { value: d, metin: a })));
    vf.addEventListener("change", () => { this.veyonFiltre = vf.value; this.tablo.sayfaNo = 0; this.tablo.ciz(); Secim.bildir(); });
    this.tablo = new CihazTablosu($("#m1s1-tablo"), {
      islem: "durum",
      ekFiltre: (c) => durumFiltresi(c, this.filtre) && veyonFiltresi(c, this.veyonFiltre)
        && (!this.pcFiltre || pcDurumu(c).kod === this.pcFiltre),
      ustEk: () => this.filtreDugumleri,
      kip: this.kipOku(),
      kutucukEk: (c) => this.kutucukEk(c),
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Pardus", hucre: (c) => kisaSurum(c.pardus_surum) },
        { baslik: "Masaüstü", hucre: (c) => el("div", {},
          c.masaustu === "GNOME" ? rozet("GNOME", "iyi") : rozet(c.masaustu || "?", c.masaustu ? "orta" : "notr"),
          el("span", { class: "alt", metin: c.giris_yoneticisi || "" })) },
        { baslik: "Yönetim hs.", hucre: yonetimHesabiHucresi },
        { baslik: "SSH anahtarı", hucre: anahtarHucresi },
        { baslik: "Parolasız sudo", hucre: (c) => { const r = SUDO_ROZETI[c.sudo_durumu]; return r ? rozet(r[0], r[1]) : rozet("?", "notr"); } },
        { baslik: "ogrenci", hucre: (c) => el("div", {}, evetHayir(c.profil_var, ["Var", "iyi"], ["Yok", "orta"]),
          c.ogrenci_sudo ? rozet("sudo'da!", "kotu") : null) },
        { baslik: "Oturum", hucre: (c) => evetHayir(c.ogrenci_oturumu, ["Açık", "orta"], ["Kapalı", "notr"]) },
        { baslik: "Girişte gizli", hucre: (c) => { const r = GIZLEME_ROZETI[c.gizleme_durumu]; return r ? rozet(r[0], r[1]) : rozet("?", "notr"); } },
        { baslik: "Veyon sürümü", hucre: (c) => veyonHucresi(c) },
        { baslik: "Kontrol", hucre: (c) => el("div", {}, goreliZaman(c.son_kontrol),
          c.erisim === 0 ? el("span", { class: "alt" }, rozet("Erişilemiyor", "kotu")) : null) },
        { baslik: "Gereken işlem", hucre: gerekenHucresi },
        { baslik: "", hucre: (c) => dugme("Düzenle", `M1-S1-B7-${satirKimligi(c)}`, () => cihazPenceresi(c), "ikincil kucuk") },
      ],
    });
    secimCubuguKur($("#sayfa-M1-S1 .secim-yeri"), "durum", () => this.tablo);
    $("#m1s1-filtre").addEventListener("change", (o) => { this.filtre = o.target.value; this.tablo.sayfaNo = 0; this.tablo.ciz(); Secim.bildir(); });
    $("#m1s1-filtre-temizle").addEventListener("click", () => {
      this.filtre = ""; $("#m1s1-filtre").value = ""; this.veyonFiltre = ""; $("#m1s1-veyon-filtre").value = "";
      this.pcFiltre = "";
      this.tablo.arama = ""; Secim.lab = ""; Secim.bildir();
    });
    $("#m1s1-kip-kutucuk").addEventListener("click", () => this.kipSec("kutucuk"));
    $("#m1s1-kip-tablo").addEventListener("click", () => this.kipSec("tablo"));
    this.kipDugmeleri();
    $("#m1s1-ekle").addEventListener("click", () => cihazPenceresi(null));
    $("#m1s1-ice").addEventListener("click", iceAktarAc);
    $("#m1s1-durum").addEventListener("click", async () => {
      const hedefler = await onayIste({ islem: "durum", cihazlar: Secim.liste(), baslik: "Durumu kontrol et",
        aciklama: "Seçili bilgisayarlardan salt okunur durum okunur; hiçbir ayar değişmez. Anahtarı kurulu olmayanlarda yalnız erişim ve sunucu kimliği denetlenir." });
      if (hedefler) isBaslat("/api/durum-kontrol", { cihazlar: hedefler });
    });
    $("#m1s1-cikar").addEventListener("click", cikarAc);
    $("#m1s1-ekran-kilitle").addEventListener("click", async () => {
      const hedefler = await onayIste({
        islem: "sinif", cihazlar: Secim.liste(), baslik: "Öğrenci ekranlarını kilitle (Bana Bakın)",
        aciklama: "Seçili öğrenci bilgisayarlarının ekranı kilitlenir ve öğretmen dikkat uyarısı gösterilir.",
      });
      if (hedefler) {
        await isBaslat("/api/sinif/ekran-kilit", { cihazlar: hedefler, kilitle: true, mesaj: "Lütfen öğretmeninizi dinleyin." });
        yanDurumGuncelle(true, Uyg.internetKisitli);
      }
    });
    $("#m1s1-ekran-ac").addEventListener("click", async () => {
      const hedefler = await onayIste({
        islem: "sinif", cihazlar: Secim.liste(), baslik: "Öğrenci ekran kilitlerini aç",
        aciklama: "Seçili öğrenci bilgisayarlarındaki ekran kilidi kaldırılır.",
      });
      if (hedefler) {
        await isBaslat("/api/sinif/ekran-kilit", { cihazlar: hedefler, kilitle: false });
        yanDurumGuncelle(false, Uyg.internetKisitli);
      }
    });
    $("#m1s1-duyuru").addEventListener("click", async () => {
      const mesaj = window.prompt("Öğrenci ekranlarına gönderilecek duyuru metni:", "Lütfen çalışmalarınızı kaydedin, 5 dakika içinde ders bitecektir.");
      if (!mesaj || !mesaj.trim()) return;
      const hedefler = await onayIste({
        islem: "sinif", cihazlar: Secim.liste(), baslik: "Sınıf duyurusu gönder",
        aciklama: `Mesaj: “${mesaj.trim()}”`,
      });
      if (hedefler) isBaslat("/api/sinif/duyuru", { cihazlar: hedefler, baslik: "Öğretmen Duyurusu", mesaj: mesaj.trim() });
    });
    $("#m1s1-internet").addEventListener("click", async () => {
      const btn = $("#m1s1-internet");
      const kisitli = btn.dataset.kisitli === "1";
      const yeniKisitla = !kisitli;
      const hedefler = await onayIste({
        islem: "sinif", cihazlar: Secim.liste(),
        baslik: yeniKisitla ? "Dış internet erişimini kısıtla" : "Dış internet erişimini aç",
        aciklama: yeniKisitla
          ? "Öğrenci bilgisayarlarında yerel laboratuvar ağı (ödev portalı ve öğretmen PC) açık kalır; dış internet erişimi kapatılır."
          : "Daha önce uygulanan internet kısıtlaması kaldırılır.",
      });
      if (hedefler) {
        await isBaslat("/api/sinif/internet", { cihazlar: hedefler, kisitla: yeniKisitla });
        btn.dataset.kisitli = yeniKisitla ? "1" : "0";
        yanDurumGuncelle(Uyg.ekranKilitli, yeniKisitla);
        const baslikEl = $("#m1s1-internet-baslik");
        if (baslikEl) baslikEl.textContent = yeniKisitla ? "İnterneti Aç (Kısıtlı)" : "İnterneti Kısıtla";
        else btn.firstChild.textContent = yeniKisitla ? "İnterneti Aç" : "İnterneti Kısıtla";
      }
    });
    const hizliDosya = $("#m1s1-hizli-dosya");
    if (hizliDosya) hizliDosya.addEventListener("click", () => git("M3-S1"));
    const hizliTemizlik = $("#m1s1-hizli-temizlik");
    if (hizliTemizlik) hizliTemizlik.addEventListener("click", () => git("M2-S1"));
    Veri.dinleyiciler.add(() => this.kartlar());
  },
  kipOku() {
    try { return localStorage.getItem("psy-m1s1-kip") || "kutucuk"; } catch (_) { return "kutucuk"; }
  },
  kipSec(kip) {
    try { localStorage.setItem("psy-m1s1-kip", kip); } catch (_) { /* depolama yok */ }
    this.tablo.kipAyarla(kip);
    this.kipDugmeleri();
  },
  kipDugmeleri() {
    const kip = this.tablo.kip;
    $("#m1s1-kip-kutucuk").setAttribute("aria-pressed", String(kip === "kutucuk"));
    $("#m1s1-kip-tablo").setAttribute("aria-pressed", String(kip === "tablo"));
  },
  kutucukEk(c) {
    const kap = el("div", { class: "pc-eylem" });
    if (c.gereken && c.gereken.sayfa) {
      kap.append(dugme("Düzelt", `M1-S1-B8-${satirKimligi(c)}`, () => { Secim.sec(c.id, true); Secim.bildir(); git(c.gereken.sayfa); }, "ikincil kucuk"));
    }
    kap.append(dugme("Düzenle", `M1-S1-B7-${satirKimligi(c)}`, () => cihazPenceresi(c), "ikincil kucuk"));
    return kap;
  },
  gosterge() {
    const liste = Veri.cihazlar.filter(labKapsami);
    const say = {};
    for (const c of liste) { const k = pcDurumu(c).kod; say[k] = (say[k] || 0) + 1; }
    const cipler = PC_DURUMLARI.filter(([k]) => say[k] || this.pcFiltre === k).map(([k]) => {
      const d = PC_DURUM[k];
      return el("button", { type: "button", class: `durum-cipi ton-${d.ton}${this.pcFiltre === k ? " etkin" : ""}`,
        "data-ui-id": `M1-S1-B20-${kimlikSlug(k)}`, "aria-pressed": String(this.pcFiltre === k), title: d.aciklama,
        onclick: () => { this.pcFiltre = this.pcFiltre === k ? "" : k; this.tablo.sayfaNo = 0; this.tablo.ciz(); this.gosterge(); Secim.bildir(); } },
      el("span", { class: "nokta" }, ikon(d.ikon, "ikon")), `${d.ad}`, el("b", { metin: String(say[k] || 0) }));
    });
    $("#m1s1-gosterge").replaceChildren(...cipler);
  },
  kartlar() {
    this.gosterge();
    const t = Veri.cihazlar;
    const hazir = t.filter((c) => c.anahtar_durumu === "ok" && c.sudo_durumu === "parolasiz" && !c.korunan).length;
    $("#m1s1-kartlar").replaceChildren(
      ozetKarti(t.length, "Kayıtlı bilgisayar"),
      ozetKarti(hazir, "Hazır (anahtar + parolasız sudo)", null, true),
      ozetKarti(t.filter((c) => !c.korunan).length - hazir, "Hazırlık gerekli"),
      ozetKarti(t.filter((c) => c.erisim === 0).length, "Son denemede erişilemedi"),
      ozetKarti(t.filter((c) => c.ogrenci_oturumu === 1).length, "Öğrenci oturumu açık"),
      ozetKarti(t.filter((c) => c.korunan).length, "Korunan (EBA/ETAP)"));
  },
  ac() { this.kartlar(); this.tablo.ciz(); Secim.bildir(); erisimTazele(300); },
};

let duzenlenenCihaz = null;

function cihazPenceresi(c) {
  duzenlenenCihaz = c;
  $("#cihaz-pencere-baslik").textContent = c ? `Düzenle — ${c.ad}` : "Bilgisayar ekle";
  $("#cihaz-kimlik").textContent = c ? `${c.ip}${c.ssh_port === 22 ? "" : ":" + c.ssh_port}` +
    (c.hostname ? ` — bilgisayar adı: ${c.hostname}` : "") + (c.korunan_neden ? ` — ${c.korunan_neden}` : "") : "";
  $("#cf-ip").value = c ? c.ip : "";
  $("#cf-port").value = c ? c.ssh_port : 22;
  $("#cf-ip").disabled = Boolean(c);
  $("#cf-port").disabled = Boolean(c);
  $("#cf-ad").value = c ? (c.etiket || "") : "";
  $("#cf-lab").value = c ? c.laboratuvar : (Secim.lab || "Laboratuvar");
  const hesap = $("#cf-hesap");
  hesap.value = c ? (c.baglanti_hesabi || "") : "";
  if (c && c.baglanti_hesabi && !["pardus", "hp"].includes(c.baglanti_hesabi)) {
    hesap.append(el("option", { value: c.baglanti_hesabi, metin: c.baglanti_hesabi }));
    hesap.value = c.baglanti_hesabi;
  }
  $("#cf-korunan").checked = Boolean(c && c.korunan);
  $("#cf-hesap-uyari").hidden = true;
  $("#cihaz-penceresi").showModal();
}

$("#cf-hesap").addEventListener("change", () => {
  $("#cf-hesap-uyari").hidden = !(duzenlenenCihaz && duzenlenenCihaz.anahtar_durumu === "ok"
    && $("#cf-hesap").value !== (duzenlenenCihaz.baglanti_hesabi || ""));
});

$("#cihaz-penceresi").addEventListener("close", async () => {
  if ($("#cihaz-penceresi").returnValue !== "kaydet") return;
  const govde = { etiket: $("#cf-ad").value.trim() || null, grup: $("#cf-lab").value.trim() || null,
    baglanti_hesabi: $("#cf-hesap").value || null, korunan: $("#cf-korunan").checked };
  try {
    if (duzenlenenCihaz) {
      const s = await api(`/api/cihazlar/${duzenlenenCihaz.id}`, govde, "PATCH");
      bildir(s.hesap_degisti ? "Kaydedildi. Yönetim hesabı değişti: bu bilgisayarı M1-S2'den yeniden hazırlayın." : "Kaydedildi.");
    } else {
      await api("/api/cihazlar", { ...govde, ip: $("#cf-ip").value.trim(), port: Number($("#cf-port").value) || 22 });
      bildir("Eklendi. Bağlantı kurulmadı; sunucu kimliğini M1-S2'de okuyup onaylayın.");
    }
    await cihazlariYukle();
  } catch (hata) { bildir(hata.message, true); }
});

/* ---- içe aktarma ---- */
let iceIcerik = "";

function iceAktarAc() {
  iceIcerik = "";
  $("#ice-dosya").value = "";
  $("#ice-ozet").textContent = "Bir dosya seçin.";
  $("#ice-onizleme").replaceChildren();
  $("#ice-aktar").disabled = true;
  $("#ice-lab").value = Secim.lab || "Laboratuvar";
  $("#ice-penceresi").showModal();
}

async function iceOnizle() {
  if (!iceIcerik) return;
  let s;
  try { s = await api("/api/cihazlar/ice-aktar/onizle", { icerik: iceIcerik, laboratuvar: $("#ice-lab").value.trim() || null }); }
  catch (hata) { $("#ice-ozet").textContent = hata.message; return; }
  const DURUM = { eklenecek: ["Eklenecek", "iyi"], var: ["Zaten var", "notr"], yinelenen: ["Yinelenen", "orta"], gecersiz: ["Geçersiz", "kotu"] };
  $("#ice-ozet").textContent = `Biçim: ${s.bicim === "ansible" ? "Ansible INI" : "CSV"} · ${s.satirlar.length} satır · ${s.eklenecek} eklenecek. Bağlantı kurulmaz.`;
  const tablo = el("table", {}, el("thead", {}, el("tr", {},
    ...["Satır", "IP", "Ad", "Hesap", "Laboratuvar", "Durum"].map((b) => el("th", { metin: b })))));
  const g = el("tbody");
  for (const r of s.satirlar) {
    const [m, t] = DURUM[r.durum];
    g.append(el("tr", {}, el("td", { metin: r.satir }), el("td", { class: "mono", metin: r.ip }),
      el("td", { metin: r.etiket || "—" }), el("td", { metin: r.hesap || "—" }), el("td", { metin: r.laboratuvar }),
      el("td", {}, rozet(m, t), r.neden ? el("span", { class: "alt", metin: r.neden }) : null)));
  }
  tablo.append(g);
  $("#ice-onizleme").replaceChildren(tablo);
  $("#ice-aktar").disabled = !s.eklenecek;
}

$("#ice-dosya").addEventListener("change", async (o) => {
  const dosya = o.target.files[0];
  if (!dosya) return;
  if (dosya.size > 2_000_000) { $("#ice-ozet").textContent = "Dosya çok büyük (en çok 2 MB)."; return; }
  iceIcerik = await dosya.text();
  iceOnizle();
});
$("#ice-lab").addEventListener("change", iceOnizle);
$("#ice-aktar").addEventListener("click", async () => {
  try {
    const s = await api("/api/cihazlar/ice-aktar", { icerik: iceIcerik, laboratuvar: $("#ice-lab").value.trim() || null });
    $("#ice-penceresi").close();
    bildir(`${s.eklenen} bilgisayar eklendi, ${s.atlanan} satır atlandı. Bağlantı kurulmadı.`);
    await cihazlariYukle();
  } catch (hata) { bildir(hata.message, true); }
});

/* ---- çıkarma ---- */
function cikarAc() {
  const secili = Secim.liste();
  if (!secili.length) { bildir("Önce tablodan bilgisayar seçin.", true); return; }
  const adlar = secili.map((id) => Veri.bul(id).ad);
  $("#cikar-hedefler").textContent = `${adlar.length} bilgisayar: ${adlar.join(", ")}`;
  $("#cikar-onay").checked = false;
  $('input[name="cikar-tur"][value="liste"]').checked = true;
  $("#cikar-penceresi").dataset.cihazlar = JSON.stringify(secili);
  $("#cikar-penceresi").showModal();
}

$("#cikar-penceresi").addEventListener("close", async () => {
  const p = $("#cikar-penceresi");
  if (p.returnValue !== "cikar") return;
  if (!$("#cikar-onay").checked) { bildir("Çıkarmak için onay kutusunu işaretleyin.", true); return; }
  const govde = { cihazlar: JSON.parse(p.dataset.cihazlar), onay: true,
    anahtari_kaldir: $('input[name="cikar-tur"]:checked').value === "anahtar" };
  if (govde.anahtari_kaldir) { isBaslat("/api/cihazlar/cikar", govde); return; }
  try {
    const s = await api("/api/cihazlar/cikar", govde);
    bildir(`${s.silinen} bilgisayar envanterden çıkarıldı.`);
    await cihazlariYukle();
  } catch (hata) { bildir(hata.message, true); }
});

/* ================================================================ M1-S2 SSH ve Hesap Hazırlığı */

const m1s2 = {
  tablo: null,
  tekOnizleme: new Map(),   // cihaz_id -> {hesaplar, oneri}
  korunacak: new Map(),     // cihaz_id -> "pardus" | "hp"
  kur() {
    this.tablo = new CihazTablosu($("#m1s2-tablo"), {
      islem: "hazirlik",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Durum", hucre: (c) => { const d = pcDurumu(c); return el("span", { class: `durum-etiketi ton-${d.ton}`, title: d.aciklama }, ikon(d.ikon, "ikon"), d.ad); } },
        { baslik: "1 · Tanıma", hucre: (c) => el("div", { title: c.parmak_izi || "" },
          c.parmak_izi_onay ? rozet("Tanındı", "iyi") : c.parmak_izi ? rozet("Onay bekliyor", "mavi") : rozet("Okunmadı", "notr"),
          c.yinelenen_kimlik ? rozet("Klon kimlik!", "orta") : null) },
        { baslik: "2 · Yönetim", hucre: (c) => el("div", {},
          c.anahtar_durumu === "ok" && c.sudo_durumu === "parolasiz" ? rozet(`Bağlı (${c.baglanti_hesabi})`, "iyi")
            : c.anahtar_durumu === "ok" ? rozet("Yetki eksik", "orta") : rozet("Bağlı değil", "notr"),
          c.profil_var === 0 ? el("span", { class: "alt", metin: "öğrenci hesabı yok" }) : null) },
        { baslik: "3 · Hesaplar", hucre: (c) => ((c.yonetim_hesaplari || []).length > 1 ? this.korunacakHucresi(c)
          : el("span", { class: "alt", metin: (c.yonetim_hesaplari || (c.baglanti_hesabi ? [c.baglanti_hesabi] : [])).join(", ") || "—" })) },
        { baslik: "Ne yapmalı?", hucre: (c) => (c.gereken ? c.gereken.metin : rozet("Hazır", "iyi")) },
      ],
    });
    secimCubuguKur($("#sayfa-M1-S2 .secim-yeri"), "hazirlik", () => this.tablo);
    $("#m1s2-kimlik-oku").addEventListener("click", () => this.kimlikOku());
    $("#m1s2-kimlik-onayla").addEventListener("click", () => this.kimlikOnayla());
    $("#m1s2-hazirla").addEventListener("click", () => hazirlikAkisi(Secim.liste()));
    $("#m1s2-tek-onizle").addEventListener("click", () => this.tekOnizle());
    $("#m1s2-tek-uygula").addEventListener("click", () => this.tekUygula());
    Veri.dinleyiciler.add(() => this.sayaclar());
  },
  korunacakHucresi(c) {
    const o = this.tekOnizleme.get(c.id);
    if (!o || !o.oneri) return "—";
    const var_olan = Object.entries(o.hesaplar).filter(([, v]) => v).map(([h]) => h);
    const sec = el("select", { "data-ui-id": `M1-S2-B6-${satirKimligi(c)}`, "aria-label": `${c.ad} korunacak hesap`,
      onchange: (e) => this.korunacak.set(c.id, e.target.value) },
    ...var_olan.map((h) => el("option", { value: h, metin: `${h} korunsun` })));
    sec.value = this.korunacak.get(c.id) || o.oneri;
    const sil = var_olan.find((h) => h !== sec.value);
    const bilgi = o.hesaplar[sil];
    return el("div", {}, sec, bilgi ? el("span", { class: "alt",
      metin: `Silinecek ${sil}: ${boyut(bilgi.ev_bayt)} ev dizini, ${bilgi.anahtar_sayisi} anahtar${bilgi.oturum ? ", AÇIK OTURUM" : ""}` }) : null);
  },
  async kimlikOku() {
    const hedefler = await onayIste({ islem: "durum", cihazlar: Secim.liste(), baslik: "Sunucu kimliklerini oku",
      aciklama: "Parola göndermeden yalnız SSH parmak izi okunur. Değişen kimlik ayrıca uyarılır.", canli: false });
    if (hedefler) isBaslat("/api/hazirlik/kimlik-oku", { cihazlar: hedefler });
  },
  async kimlikOnayla() {
    const adaylar = Secim.liste().filter((id) => { const c = Veri.bul(id); return c.parmak_izi && !c.parmak_izi_onay; });
    if (!adaylar.length) { bildir("Seçimde onay bekleyen sunucu kimliği yok. Önce B1 ile kimlikleri okuyun.", true); return; }
    const klon = adaylar.filter((id) => Veri.bul(id).yinelenen_kimlik).length;
    const hedefler = await onayIste({
      islem: "durum", cihazlar: adaylar, baslik: "Sunucu kimliklerini onayla", canli: false,
      aciklama: "Bu parmak izleri, bilgisayarlara kimlik bilgisi göndermeden önce son güvenlik denetimidir.",
      uyarilar: klon ? [`${klon} bilgisayar aynı kimliği paylaşıyor (klon imaj). Bu yaygındır ama bilgisayarlar birbirinin yerine geçebilir.`] : [],
      yikici: true, onayMetni: "Bu parmak izlerinin kendi laboratuvarıma ait olduğunu doğruladım",
      baslatMetni: "Kimlikleri onayla",
      hedefEk: { baslik: "Parmak izi", hucre: (h) => el("span", { class: "parmakizi", metin: Veri.bul(h.id).parmak_izi }) },
    });
    if (!hedefler) return;
    try {
      const s = await api("/api/hazirlik/kimlik-onayla", { cihazlar: hedefler });
      bildir(`${s.onaylanan} sunucu kimliği onaylandı. Sıradaki adım: B3 Hazırlığı başlat.`);
      await cihazlariYukle();
    } catch (hata) { bildir(hata.message, true); }
  },
  async tekOnizle() {
    const kayit = await isBaslat("/api/tekillestirme/onizle", { cihazlar: Secim.liste() });
    if (!kayit) return;
    this.tekOnizleme = new Map();
    for (const h of kayit.hedefler) if (h.veri && h.veri.oneri) this.tekOnizleme.set(h.veri.cihaz_id, h.veri);
    $("#m1s2-tek-uygula").disabled = !this.tekOnizleme.size;
    bildir(this.tekOnizleme.size
      ? `${this.tekOnizleme.size} bilgisayarda hp ve pardus birlikte var. Tabloda korunacak hesabı seçip B5 ile uygulayın.`
      : "Seçili bilgisayarlarda tekilleştirme gerektiren durum yok.");
    this.tablo.ciz();
  },
  async tekUygula() {
    const adaylar = Secim.liste().filter((id) => this.tekOnizleme.has(id));
    if (!adaylar.length) { bildir("Önizlemesi yapılmış ve seçili bilgisayar yok.", true); return; }
    const secim = (id) => this.korunacak.get(id) || this.tekOnizleme.get(id).oneri;
    const hedefler = await onayIste({
      islem: "tekillestirme", cihazlar: adaylar, baslik: "hp / pardus tekilleştirme",
      aciklama: "Her bilgisayarda seçilen hesap korunur. Diğer hesabın ev dizini ve hesap kayıtları öğrenci bilgisayarında yedeklenir, sonra hesap silinir.",
      uyarilar: ["Korunacak hesapla yeni oturumda anahtar ve parolasız sudo doğrulanmadan silme yapılmaz.",
        "Silinecek hesapta açık oturum varsa o bilgisayar atlanır.",
        "Envanter ve Ansible dışa aktarımı korunacak hesaba geçer."],
      yikici: true, onayMetni: "Seçilen yönetim hesaplarının silineceğini anladım", baslatMetni: "Tekilleştir",
      hedefEk: { baslik: "Korunacak → silinecek", hucre: (h) => { const k = secim(h.id); return `${k} korunur → ${k === "pardus" ? "hp" : "pardus"} silinir`; } },
    });
    if (!hedefler) return;
    const korunacaklar = Object.fromEntries(hedefler.map((id) => [id, secim(id)]));
    await isBaslat("/api/tekillestirme/uygula", { korunacaklar, onay: true });
    this.tekOnizleme = new Map();
    $("#m1s2-tek-uygula").disabled = true;
  },
  ac() { this.sayaclar(); this.tablo.ciz(); Secim.bildir(); },
  sayaclar() {
    const t = Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan && !c.ogretmen_pc);
    const say = (f) => t.filter(f).length;
    const metin = (n, var_, yok) => (n ? `${n} ${var_}` : yok);
    $("#m1s2-adim1").textContent = metin(say((c) => !c.parmak_izi) + say((c) => c.parmak_izi && !c.parmak_izi_onay),
      "bilgisayar tanınmayı veya onay bekliyor", "✓ Tüm bilgisayarlar tanındı");
    $("#m1s2-adim2").textContent = metin(say((c) => c.parmak_izi_onay && !(c.anahtar_durumu === "ok" && c.sudo_durumu === "parolasiz")),
      "bilgisayar yönetime bağlanmayı bekliyor", "✓ Tanınan bilgisayarların hepsi yönetime bağlı");
    $("#m1s2-adim3").textContent = metin(say((c) => (c.yonetim_hesaplari || []).length > 1),
      "bilgisayarda iki yönetici hesabı var", "✓ Temizlenecek fazla hesap yok");
  },
};

/* Parola bir kez → kesin hedef listesi → hazırlık işi. Parola alanları hemen temizlenir. */
async function hazirlikAkisi(cihazIdler) {
  if (!cihazIdler.length) { bildir("Önce bilgisayar seçin.", true); return; }
  const p = $("#parola-penceresi");
  $("#pp-pardus").value = ""; $("#pp-hp").value = "";
  p.returnValue = "";
  p.showModal();
  await new Promise((coz) => p.addEventListener("close", coz, { once: true }));
  const parolalar = { pardus: $("#pp-pardus").value, hp: $("#pp-hp").value };
  $("#pp-pardus").value = ""; $("#pp-hp").value = "";
  if (p.returnValue !== "devam") return;
  const hedefler = await onayIste({
    islem: "hazirlik", cihazlar: cihazIdler, baslik: "SSH ve hesap hazırlığı",
    aciklama: "Her bilgisayarda: uygulama anahtarı eklenir, yönetim hesabına parolasız sudo verilir (visudo ile doğrulanır)"
      + ($("#pp-ogrenci").checked ? ", ogrenci hesabı yoksa oluşturulur" : "")
      + "; sonra yalnız anahtarla yeni oturumda doğrulanır.",
    uyarilar: ["NOPASSWD: ALL yönetim hesabına root eşdeğeri yetki verir. Öğretmen bilgisayarını ve uygulama anahtarını koruyun.",
      "Parola kaydedilmez; hesap+bilgisayar başına en çok 3 yanlış deneme yapılır."],
    yikici: true, onayMetni: "Yönetim hesabına parolasız sudo verileceğini anladım", baslatMetni: "Hazırlığı başlat",
  });
  if (!hedefler) return;
  await isBaslat("/api/hazirlik/baslat", { cihazlar: hedefler, parolalar, ogrenci_olustur: $("#pp-ogrenci").checked });
  parolalar.pardus = ""; parolalar.hp = "";
}

/* ================================================================ M1-S3 Ağda Bul */

const m1s3 = {
  bulunanlar: [],
  secili: new Set(),
  oneri: null,
  kur() {
    $("#m1s3-form").addEventListener("submit", async (o) => {
      o.preventDefault();
      const haric = $("#m1s3-haric").value.split(",").map((s) => s.trim()).filter(Boolean);
      await isBaslat("/api/kesif/tara", { aralik: $("#m1s3-aralik").value, haric });
      this.yukle();
    });
    $("#m1s3-oneri").addEventListener("click", () => { if (this.oneri && this.oneri.ag) $("#m1s3-aralik").value = this.oneri.ag; });
    $("#m1s3-ekle").addEventListener("click", () => this.ekle(false));
    $("#m1s3-ekle-hazirla").addEventListener("click", () => this.ekle(true));
    $("#m1s3-temizle").addEventListener("click", async () => {
      if (!confirm("Tarama sonuç listesi boşaltılsın mı? Envantere dokunulmaz.")) return;
      await api("/api/kesif/temizle", {});
      this.yukle();
    });
  },
  async ac() {
    try {
      this.oneri = await api("/api/kesif/ag");
      $("#m1s3-oneri-metin").textContent = this.oneri.ag
        ? `Öğretmen bilgisayarı ${this.oneri.adres} adresinde; önerilen tarama ağı ${this.oneri.ag}. Öğretmen bilgisayarı taranmaz.`
        : "Ağ bilgisi okunamadı; aralığı elle yazın.";
      if (!$("#m1s3-aralik").value && this.oneri.ag) $("#m1s3-aralik").value = this.oneri.ag;
    } catch (_) { /* önemsiz */ }
    this.yukle();
  },
  async yukle() {
    try { this.bulunanlar = await api("/api/kesif/bulunanlar"); } catch (hata) { bildir(hata.message, true); return; }
    const anahtar = (b) => `${b.ip}:${b.ssh_port}`;
    this.secili = new Set([...this.secili].filter((k) => this.bulunanlar.some((b) => anahtar(b) === k)));
    const kap = $("#m1s3-tablo");
    if (!this.bulunanlar.length) { kap.replaceChildren(el("p", { class: "bos-tablo", metin: "Henüz tarama sonucu yok." })); return; }
    const yeniler = this.bulunanlar.filter((b) => !b.envanter_id);
    const tumu = el("input", { type: "checkbox", "data-ui-id": "M1-S3-B6", "aria-label": "Tüm yeni bulunanları seç",
      checked: yeniler.length && yeniler.every((b) => this.secili.has(anahtar(b))),
      onchange: (o) => { for (const b of yeniler) { if (o.target.checked) this.secili.add(anahtar(b)); else this.secili.delete(anahtar(b)); } this.yukle(); } });
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, el("th", { class: "sec" }, tumu),
      ...["IP", "Sunucu kimliği (parmak izi)", "Durum", "Bulunma"].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const b of this.bulunanlar) {
      const k = anahtar(b);
      const durum = b.kimlik_farkli ? rozet("Envanterde, kimlik DEĞİŞMİŞ", "kotu")
        : b.envanter_id ? rozet("Envanterde", "notr") : rozet("Yeni", "mavi");
      g.append(el("tr", { class: this.secili.has(k) ? "secili" : "" },
        el("td", { class: "sec" }, el("input", { type: "checkbox", checked: this.secili.has(k),
          "data-ui-id": `M1-S3-B5-${kimlikSlug(b.ip)}`, "aria-label": `${b.ip} seç`,
          onchange: (o) => { if (o.target.checked) this.secili.add(k); else this.secili.delete(k); } })),
        el("td", { class: "mono", metin: b.ssh_port === 22 ? b.ip : k }),
        el("td", {}, el("span", { class: "parmakizi", metin: b.parmak_izi }),
          b.ayni_kimlikli > 1 ? el("span", { class: "alt" }, rozet(`Aynı kimlik ${b.ayni_kimlikli} bilgisayarda (klon)`, "orta")) : null),
        el("td", {}, durum), el("td", { metin: goreliZaman(b.zaman) })));
    }
    tablo.append(g);
    kap.replaceChildren(tablo);
  },
  async ekle(hazirla) {
    const secilenler = [...this.secili];
    if (!secilenler.length) { bildir("Önce listeden bilgisayar seçin.", true); return; }
    if (!confirm(`${secilenler.length} bilgisayar, listede gördüğünüz parmak izleriyle ONAYLI olarak envantere eklenecek.\n\n` +
      "Bu kimliklerin kendi laboratuvarınıza ait olduğundan emin misiniz? Ekleme bağlantı kurmaz.")) return;
    let s;
    try { s = await api("/api/kesif/ekle", { bulunanlar: secilenler, laboratuvar: $("#m1s3-lab").value.trim() || null }); }
    catch (hata) { bildir(hata.message, true); return; }
    await cihazlariYukle();
    this.secili.clear();
    this.yukle();
    bildir(`${s.eklenen.length} bilgisayar envantere eklendi.`);
    if (hazirla && s.eklenen.length) {
      for (const id of s.eklenen) Secim.sec(id, true);
      Secim.bildir();
      hazirlikAkisi(s.eklenen);
    }
  },
};

sayfaKaydet("M1-S1", m1s1);
sayfaKaydet("M1-S2", m1s2);
sayfaKaydet("M1-S3", m1s3);
