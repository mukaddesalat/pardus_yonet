/* M1-S4 Veyon Ayarları: paket ve public key yükleme, önizle → onayla → kur/yapılandır,
 * bağlantı doğrulama, sürüm yenileme ve geri alma. Paket alanı M2-S2'den ayrıdır. */
"use strict";

const VEYON_KIPLERI = { kur: "Veyon kur/güncelle", yapilandir: "Veyon'u yapılandır", ikisi: "Kur ve yapılandır" };
const VEYON_KURULUM = {
  kurulacak: ["Kurulacak", "mavi"], guncellenecek: ["Güncellenecek", "mavi"], atlanacak: ["Aynı sürüm — atlanır", "notr"],
  engellendi: ["Engellendi", "kotu"],
};
const VEYON_OGE = {
  zaten: ["zaten öyle", "notr"], eklenecek: ["eklenecek", "mavi"], degistirilecek: ["DEĞİŞECEK", "orta"],
  ayarlanacak: ["ayarlanacak", "mavi"], etkinlestirilecek: ["başlatılacak", "mavi"], uygulandi: ["uygulandı", "iyi"], hata: ["HATA", "kotu"],
};

function veyonOgeRozeti(ad, oge) {
  if (!oge) return null;
  const [m, t] = VEYON_OGE[oge.durum] || [oge.durum, "notr"];
  return el("span", { class: "oge" }, `${ad}: `, rozet(m, t));
}

const m1s4 = {
  tablo: null,
  bilgi: { paketler: [], secili_sha: null, anahtar: null },
  filtre: "",
  sonuclar: new Map(),     // cihaz_id -> son Veyon işinin hedef kaydı
  sonKayit: null,
  bekleyenAnahtar: null,   // onay bekleyen anahtar dosyası (yalnız bellekte)

  kur() {
    const filtre = $("#m1s4-filtre");
    filtre.replaceChildren(...VEYON_FILTRELERI.map(([d, a]) => el("option", { value: d, metin: a })));
    filtre.addEventListener("change", () => { this.filtre = filtre.value; this.tablo.sayfaNo = 0; this.tablo.ciz(); Secim.bildir(); });
    const filtreDugumleri = [...$("#m1s4-filtreler").children];
    this.tablo = new CihazTablosu($("#m1s4-tablo"), {
      islem: "veyon",
      ekFiltre: (c) => veyonFiltresi(c, this.filtre),
      ustEk: () => filtreDugumleri,
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Veyon sürümü", hucre: (c) => veyonHucresi(c, true) },
        { baslik: "Servis", hucre: veyonServisHucresi },
        { baslik: "Yapılandırma", hucre: veyonYapilandirmaHucresi },
        { baslik: "Son işlem", hucre: (c) => this.sonucHucresi(c) },
        { baslik: "Uygunluk", hucre: (c) => uygunlukHucresi(c, "veyon") },
      ],
    });
    secimCubuguKur($("#sayfa-M1-S4 .secim-yeri"), "veyon", () => this.tablo);
    $("#m1s4-dosya").addEventListener("change", (o) => this.paketYukle(o.target.files[0]));
    $("#m1s4-anahtar-dosya").addEventListener("change", (o) => this.anahtarYukle(o.target.files[0]));
    $("#m1s4-anahtar-sil").addEventListener("click", () => this.anahtarSil());
    $("#m1s4-ogretmen").addEventListener("click", () => this.ogretmenDenetle());
    $("#m1s4-kontrol").addEventListener("click", () => this.plan(this.kontrolKipi(), true));
    $("#m1s4-kur").addEventListener("click", () => this.plan("kur"));
    $("#m1s4-yapilandir").addEventListener("click", () => this.plan("yapilandir"));
    $("#m1s4-ikisi").addEventListener("click", () => this.plan("ikisi"));
    $("#m1s4-dogrula").addEventListener("click", () => this.dogrula());
    $("#m1s4-surumler").addEventListener("click", () => this.surumler());
    $("#m1s4-geri").addEventListener("click", () => this.geriAl());
    $("#vo-onay").addEventListener("change", () => this.onayDurumu());
    $("#vo-ogretmen").addEventListener("change", () => this.onayDurumu());
    Veri.dinleyiciler.add(() => this.kartlar());
  },

  async ac() {
    await this.yukle();
    this.tablo.ciz();
    Secim.bildir();
    erisimTazele(300);
    let id = null;
    try { id = sessionStorage.getItem("psy-veyon-son-is"); } catch (_) { /* yok */ }
    if (id && !this.sonKayit) {
      try { this.sonuclariGoster(await api(`/api/isler/${id}`)); } catch (_) { /* iş silinmiş olabilir */ }
    }
  },

  async yukle() {
    try { this.bilgi = await api("/api/veyon"); } catch (hata) { bildir(hata.message, true); return; }
    this.paketleriCiz();
    this.anahtariCiz();
    this.kartlar();
  },

  secili() { return this.bilgi.paketler.find((p) => p.sha256 === this.bilgi.secili_sha) || null; },

  kontrolKipi() {
    if (this.bilgi.secili_sha && this.bilgi.anahtar) return "ikisi";
    if (this.bilgi.secili_sha) return "kur";
    if (this.bilgi.anahtar) return "yapilandir";
    return null;
  },

  /* ---------------------------------------------------------------- Veyon paketi */
  paketleriCiz() {
    const kap = $("#m1s4-paketler");
    const liste = this.bilgi.paketler;
    if (!liste.length) {
      kap.replaceChildren(el("p", { class: "bos-tablo", metin: "Henüz Veyon paketi yüklenmedi. Paket yüklenmeden kurulum yapılamaz; yalnız yapılandırma ve doğrulama kullanılabilir." }));
      return;
    }
    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Uygula", "Dosya", "Paket", "Tam sürüm", "Mimari", "Boyut", "Yüklendi", "Doğrulama", ""].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const p of liste) {
      const kimlik = kimlikSlug(p.surum) || p.sha256.slice(0, 6).toUpperCase();
      const secili = p.sha256 === this.bilgi.secili_sha;
      g.append(el("tr", { class: secili ? "secili" : "" },
        el("td", { class: "sec" }, el("input", { type: "radio", name: "m1s4-paket", checked: secili,
          "data-ui-id": `M1-S4-B2-${kimlik}`, "aria-label": `${p.surum} kurulacak paket olsun`,
          onchange: () => this.paketSec(p.sha256) })),
        el("td", { class: "kirp", metin: p.dosya_adi, title: p.dosya_adi }),
        el("td", { class: "mono", metin: p.paket }),
        el("td", { class: "mono", metin: p.surum }),
        el("td", { metin: p.mimari }),
        el("td", { metin: boyut(p.boyut) }),
        el("td", { metin: tarih(p.zaman) }),
        el("td", {}, rozet("Veyon paketi doğrulandı", "iyi"),
          el("span", { class: "alt", metin: `metadata: Package ${p.paket}; sağladıkları: ${(p.kontrol.Provides || "—").slice(0, 60)}` })),
        el("td", {}, dugme("Sil", `M1-S4-B3-${kimlik}`, () => this.paketSil(p), "ikincil kucuk"))));
    }
    tablo.append(g);
    const not = liste.length > 1 && !this.bilgi.secili_sha
      ? el("p", { class: "uyari-kutusu", metin: "Birden fazla Veyon paketi var: kurulacak olanı “Uygula” sütunundan seçin." }) : null;
    kap.replaceChildren(...[not, tablo].filter(Boolean));
  },

  async paketYukle(dosya) {
    if (!dosya) return;
    const durum = $("#m1s4-paket-durum");
    durum.textContent = `${dosya.name} yükleniyor ve Veyon paketi olduğu doğrulanıyor…`;
    try {
      const p = await apiDosya("/api/paketler", dosya, { "X-Paket-Turu": "veyon" });
      const onceki = this.bilgi.secili_sha;
      if (!onceki) await api("/api/veyon/paket-sec", { sha: p.sha256 });
      durum.textContent = `Doğrulandı: ${p.paket} ${p.surum} (${p.mimari}). Kurulum başlamadı.` + (onceki && onceki !== p.sha256
        ? " Kurulacak paket değişmedi; yenisini kullanmak için “Uygula” sütunundan seçin." : " Bilgisayarları seçip “Kur ve yapılandır” deyin.");
      await this.yukle();
      await cihazlariYukle();
    } catch (hata) { durum.textContent = `Reddedildi: ${hata.message}`; }
    $("#m1s4-dosya").value = "";
  },

  async paketSec(sha) {
    try { await api("/api/veyon/paket-sec", { sha }); } catch (hata) { bildir(hata.message, true); }
    await this.yukle();
    await cihazlariYukle();   // sürüm karşılaştırması seçili pakete göre yeniden hesaplanır
  },

  async paketSil(p) {
    if (!confirm(`${p.paket} ${p.surum} (${p.dosya_adi}) öğretmen bilgisayarından silinsin mi? Kurulu bilgisayarlar etkilenmez.`)) return;
    try { await api(`/api/paketler/${p.sha256}`, null, "DELETE"); } catch (hata) { bildir(hata.message, true); return; }
    await this.yukle();
    await cihazlariYukle();
  },

  /* ---------------------------------------------------------------- public key */
  anahtariCiz() {
    const a = this.bilgi.anahtar;
    const dl = $("#m1s4-anahtar");
    if (!a) { dl.replaceChildren(); $("#m1s4-anahtar-sil").disabled = true; return; }
    $("#m1s4-anahtar-sil").disabled = false;
    $("#m1s4-anahtar-adi").value = a.ad;
    const satirlar = [["Anahtar adı", a.ad], ["Dosya", a.dosya_adi], ["Tür", `RSA ${a.bit} bit — public key`],
      ["Veyon çift kimliği", a.cift_kimligi], ["SHA-256", a.parmak_izi], ["Yüklendi", tarih(a.zaman)]];
    if (a.onceki) satirlar.push(["Önceki anahtar", `${a.onceki.ad} [${a.onceki.cift_kimligi}] — yedeklendi`]);
    dl.replaceChildren(...satirlar.flatMap(([k, d]) => [el("dt", { metin: k }),
      el("dd", { class: ["SHA-256", "Veyon çift kimliği"].includes(k) ? "mono" : "", metin: d })]));
  },

  async anahtarYukle(dosya, onay = false) {
    if (!dosya) return;
    const ad = $("#m1s4-anahtar-adi").value.trim();
    const durum = $("#m1s4-anahtar-durum");
    durum.textContent = `${dosya.name} doğrulanıyor…`;
    try {
      const a = await apiDosya("/api/veyon/anahtar", dosya, { "X-Anahtar-Adi": encodeURIComponent(ad), "X-Onay": onay ? "1" : "0" });
      durum.textContent = `Kabul edildi: '${a.ad}' RSA ${a.bit} bit, çift kimliği ${a.cift_kimligi}. Öğretmen PC denetleniyor…`;
      this.bekleyenAnahtar = null;
      await this.yukle();
      await this.ogretmenDenetle();
    } catch (hata) {
      if (hata.durum === 409 && hata.veri && hata.veri.onay_gerekli) {
        this.bekleyenAnahtar = dosya;
        $("#vad-metin").textContent = hata.message;
        const p = $("#veyon-anahtar-degisim");
        p.returnValue = "";
        p.showModal();
        p.addEventListener("close", () => {
          if (p.returnValue === "degistir" && this.bekleyenAnahtar) this.anahtarYukle(this.bekleyenAnahtar, true);
          else { durum.textContent = "Vazgeçildi; mevcut anahtar korundu."; this.bekleyenAnahtar = null; }
        }, { once: true });
      } else {
        durum.textContent = `Reddedildi: ${hata.message}`;
      }
    }
    $("#m1s4-anahtar-dosya").value = "";
  },

  async anahtarSil() {
    if (!confirm("Uygulamadaki Veyon public key kaydı silinsin mi? Öğrenci bilgisayarlarındaki anahtarlar değişmez.")) return;
    try { await api("/api/veyon/anahtar", null, "DELETE"); } catch (hata) { bildir(hata.message, true); return; }
    $("#m1s4-anahtar-durum").textContent = "Public key kaydı kaldırıldı.";
    $("#m1s4-ogretmen-sonuc").replaceChildren();
    await this.yukle();
  },

  async ogretmenDenetle() {
    let h;
    try { h = await api("/api/veyon/hazirlik"); } catch (hata) { bildir(hata.message, true); return null; }
    const ok = h.ozel_anahtar;
    const ayrinti = [
      `Veyon Master: ${h.veyon ? `${h.veyon.paket} ${h.veyon.surum}` : "kurulu değil"}`,
      `kimlik doğrulama: ${h.yontem === 1 ? "anahtar dosyası" : h.yontem === 0 ? "oturum parolası" : "ayarlanmamış"}`,
      ok ? (ok.var ? `private key: var (grup ${ok.grup}, izin ${ok.izin}${ok.okuyabilenler.length ? `, okuyabilen: ${ok.okuyabilenler.join(", ")}` : ""}; içerik okunmadı)`
        : ok.var === false ? "private key: YOK" : "private key: denetlenemedi") : null,
      h.eslesen ? `yüklenen public key bu bilgisayardaki '${h.eslesen}' anahtarıyla aynı` : null,
    ].filter(Boolean).join(" · ");
    $("#m1s4-ogretmen-sonuc").replaceChildren(
      el("p", {}, h.hazir ? rozet("Öğretmen PC hazır", "iyi") : rozet("Öğretmen PC'de sorun var", "kotu"), " ",
        el("span", { class: "ipucu", metin: ayrinti })),
      ...(h.sorunlar.length ? [el("ul", { class: "uyari-listesi hata-listesi" }, ...h.sorunlar.map((s) => el("li", { metin: s })))] : []),
      ...(h.uyarilar.length ? [el("ul", { class: "uyari-listesi" }, ...h.uyarilar.map((s) => el("li", { metin: s })))] : []),
      ...(h.komutlar.length ? [el("p", { class: "ipucu", metin: "Öğretmen PC'de bir kez çalıştırılacak komutlar (yönetici parolası sorulur):" }),
        el("pre", { class: "komut" }, h.komutlar.join("\n"))] : []));
    return h;
  },

  /* ---------------------------------------------------------------- bilgisayarlar */
  kartlar() {
    const t = Veri.cihazlar.filter((c) => !c.korunan && labKapsami(c));
    const say = (f) => t.filter(f).length;
    const k = (c) => (c.veyon || {}).karsilastirma;
    const d = (c) => (c.veyon || {}).durum;
    const secili = this.secili();
    $("#m1s4-kartlar").replaceChildren(
      ozetKarti(say((c) => d(c) === "kurulu"), "Veyon kurulu", null, true),
      ozetKarti(say((c) => d(c) === "kurulu_degil"), "Kurulu değil"),
      ozetKarti(secili ? say((c) => k(c) === "eski") : "—", secili ? `${secili.surum} sürümünden eski` : "Eski (paket seçilmedi)"),
      ozetKarti(secili ? say((c) => k(c) === "ayni") : "—", "Seçili paketle aynı"),
      ozetKarti(say((c) => ["erisilemiyor", "kontrol_edilmedi", "okunamadi"].includes(d(c))), "Durumu bilinmiyor", "erişilemeyen / kontrol edilmemiş"),
      ozetKarti(say((c) => d(c) === "hatali"), "Kurulum hatalı / yarım"));
  },

  sonucHucresi(c) {
    const s = this.sonuclar.get(c.id);
    if (!s) return "—";
    const [m, t] = HEDEF_ROZETI[s.durum] || ["…", "mavi"];
    return el("div", { class: "sonuc-hucre" }, rozet(m, t), el("span", { class: "alt", metin: (s.mesaj || "").replace(/^[^—]*— /, "").slice(0, 140) }));
  },

  async plan(kip, yalnizKontrol = false) {
    if (!kip) { bildir("Önce Veyon paketini veya public key'i yükleyin.", true); return; }
    if (kip !== "yapilandir" && !this.bilgi.secili_sha) { bildir("Önce Veyon .deb paketini yükleyin ve kurulacak paketi seçin (M1-S4-B1 / B2).", true); return; }
    if (kip !== "kur" && !this.bilgi.anahtar) { bildir("Önce Veyon public key dosyasını yükleyin (M1-S4-B4).", true); return; }
    const hedefler = await onayIste({ islem: "veyon", cihazlar: Secim.liste(),
      baslik: yalnizKontrol ? "Hazırlığı kontrol et" : `Önizleme — ${VEYON_KIPLERI[kip]}`,
      aciklama: "Her hedefte kurulu Veyon sürümü okunur" + (kip !== "yapilandir" ? ", paket aktarılıp SHA-256 ile doğrulanır; sürüm, mimari, boş alan, paket kilidi ve bağımlılıklar denetlenir" : "")
        + (kip !== "kur" ? ", uygulanacak ayarların farkı çıkarılır" : "") + ". Bu adımda hiçbir şey KURULMAZ ve ayar DEĞİŞMEZ.",
      baslatMetni: "Önizlemeyi hazırla" });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/veyon/plan", { cihazlar: hedefler, kip });
    if (!kayit) return;
    this.sonuclariGoster(kayit);
    if (!yalnizKontrol) await this.onizlemeAc(kayit, kip);
  },

  async onizlemeAc(kayit, kip) {
    const hazir = kayit.hedefler.filter((h) => h.veri && h.veri.durum === "hazir");
    const digerleri = kayit.hedefler.filter((h) => !(h.veri && h.veri.durum === "hazir"));
    const p = this.secili();
    const a = this.bilgi.anahtar;
    $("#vo-baslik").textContent = `${VEYON_KIPLERI[kip]} — önizleme`;
    $("#vo-aciklama").textContent = kip === "ikisi"
      ? "Her bilgisayarda önce kurulum yapılır; kurulum başarısız veya yarım kalırsa o bilgisayarda yapılandırmaya geçilmez. Diğer bilgisayarların sonuçları korunur."
      : kip === "kur" ? "Aynı sürüm kuruluysa yeniden kurulmaz; daha yeni sürüm kuruluysa düşürme yapılmaz." : "Veyon kurulu bilgisayarlarda ayarlar uygulanır; önce mevcut ayarlar öğrenci PC'de yedeklenir.";
    const ayarlar = [];
    if (kip !== "yapilandir" && p) ayarlar.push(["Kurulacak paket", `${p.paket} ${p.surum} (${p.mimari}) — ${p.dosya_adi}`]);
    if (kip !== "kur" && a) {
      ayarlar.push(["Public key", `${a.ad} — çift kimliği ${a.cift_kimligi} → /etc/veyon/keys/public/${a.ad}/key`],
        ["Kimlik doğrulama", "Anahtar dosyası (Authentication/Method = 1)"],
        ["Veyon servisi", "açılışta başlar; ayar değiştiyse yeniden başlatılır"],
        ["Ağ portu", "11100 (Veyon varsayılanı; değiştirilmez)"],
        ["Yedek", "önceki Veyon ayarları ve anahtarları öğrenci PC'de yedeklenir (M1-S4-B14 ile geri alınır)"]);
    }
    $("#vo-ayarlar").replaceChildren(...ayarlar.flatMap(([k, d]) => [el("dt", { metin: k }), el("dd", { metin: d })]));
    $("#vo-hedef-baslik").textContent = `Uygulanacak bilgisayarlar — kesin liste (${hazir.length})`;
    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Bilgisayar", "Mevcut sürüm", "Kurulacak sürüm", "Kurulum", "Yapılandırma"].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const h of hazir) {
      const v = h.veri.veyon || {};
      const k = h.veri.kurulum;
      const y = h.veri.yapilandirma;
      const kurulumHucresi = !k ? el("span", { class: "alt", metin: "—" }) : el("div", {},
        rozet(...(VEYON_KURULUM[k.durum] || [k.durum, "notr"])),
        k.yerine_gececek ? el("span", { class: "alt", metin: `yerine geçecek: ${k.yerine_gececek.join(", ")}` }) : null);
      const yapHucresi = !y ? el("span", { class: "alt", metin: "—" }) : y.veyon_yok
        ? el("span", { class: "alt", metin: "kurulumdan sonra yapılandırılır" })
        : el("div", { class: "oge-listesi" }, veyonOgeRozeti("anahtar", y.ogeler.anahtar), veyonOgeRozeti("yöntem", y.ogeler.yontem),
          veyonOgeRozeti("servis", y.ogeler.servis));
      g.append(el("tr", {}, el("td", { metin: h.veri.ad }),
        el("td", { class: "mono", metin: v.durum === "kurulu" ? `${v.surum}${v.parcali ? " (parçalı)" : ""}` : v.durum === "kurulu_degil" ? "kurulu değil" : (v.durum || "?") }),
        el("td", { class: "mono", metin: kip !== "yapilandir" && p ? p.surum : "—" }), el("td", {}, kurulumHucresi), el("td", {}, yapHucresi)));
    }
    tablo.append(g);
    $("#vo-hedefler").replaceChildren(hazir.length ? tablo : el("p", { class: "bos-tablo", metin: "Uygulanabilir bilgisayar yok." }));
    $("#vo-disarida-kap").hidden = !digerleri.length;
    $("#vo-disarida-baslik").textContent = `Uygulanmayacak (${digerleri.length}) — bu bilgisayarlara dokunulmaz`;
    const dt = el("table", {}, el("thead", {}, el("tr", {}, el("th", { metin: "Bilgisayar" }), el("th", { metin: "Neden" }))));
    const db = el("tbody");
    for (const h of digerleri) db.append(el("tr", {}, el("td", { metin: (h.veri && h.veri.ad) || h.hedef }),
      el("td", { metin: (h.mesaj || "").replace(/^[^—]*— /, "") })));
    dt.append(db);
    $("#vo-disarida").replaceChildren(dt);
    const uyarilar = [];
    const degisen = hazir.filter((h) => h.veri.yapilandirma && h.veri.yapilandirma.ogeler && h.veri.yapilandirma.ogeler.anahtar.durum === "degistirilecek");
    if (degisen.length) uyarilar.push(`${degisen.length} bilgisayarda aynı adlı FARKLI Veyon anahtarı var; onaylarsanız değiştirilir (eskisi yedeklenir).`);
    const guncel = hazir.filter((h) => h.veri.kurulum && h.veri.kurulum.durum === "guncellenecek");
    if (guncel.length) uyarilar.push(`${guncel.length} bilgisayarda Veyon sürümü yükseltilecek; açık Veyon bağlantıları kısa süre kopar.`);
    const parcali = hazir.filter((h) => h.veri.kurulum && h.veri.kurulum.yerine_gececek);
    if (parcali.length) uyarilar.push(`${parcali.length} bilgisayarda Pardus'un parçalı Veyon paketleri kaldırılıp yerine tek paket kurulacak (yalnız Veyon paketleri).`);
    if (kip !== "yapilandir") uyarilar.push("Paketin kurulum betikleri root yetkisiyle çalışır; yalnız güvendiğiniz kaynaktan indirdiğiniz Veyon paketini kurun.");
    let h = null;
    if (kip !== "kur") h = await this.ogretmenDenetle();
    const ogretmenSorunu = Boolean(h && h.sorunlar.length);
    if (ogretmenSorunu) uyarilar.push(`Öğretmen PC: ${h.sorunlar.join(" ")}`);
    $("#vo-uyarilar").replaceChildren(...uyarilar.map((u) => el("li", { metin: u })));
    $("#vo-ogretmen-etiket").hidden = !ogretmenSorunu;
    $("#vo-ogretmen").checked = false;
    $("#vo-onay").checked = false;
    this.bekleyen = { kayit, kip, hazir: hazir.map((x) => x.veri.cihaz_id), ogretmenSorunu };
    this.onayDurumu();
    const pencere = $("#veyon-onizleme");
    pencere.returnValue = "";
    pencere.showModal();
    pencere.addEventListener("close", async () => {
      if (pencere.returnValue !== "uygula" || $("#vo-uygula").disabled) return;
      const b = this.bekleyen;
      const yeni = await isBaslat("/api/veyon/uygula", { cihazlar: b.hazir, kip: b.kip, plan_is_id: b.kayit.id, onay: true,
        anahtar_uyarisi_onay: $("#vo-ogretmen").checked });
      if (yeni) this.sonuclariGoster(yeni);
    }, { once: true });
  },

  onayDurumu() {
    const b = this.bekleyen;
    $("#vo-uygula").disabled = !b || !b.hazir.length || !$("#vo-onay").checked || (b.ogretmenSorunu && !$("#vo-ogretmen").checked);
  },

  async dogrula() {
    const hedefler = await onayIste({ islem: "veyon_oku", cihazlar: Secim.liste(), baslik: "Bağlantıyı doğrula",
      aciklama: "Salt okunur: Veyon kurulumu, servis, kimlik doğrulama yöntemi ve public key eşleşmesi okunur; öğretmen PC'den 11100 portuna bağlanılıp Veyon sunucusunun yanıtı denetlenir. Anahtarla gerçek oturum Veyon Master'da açılır." });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/veyon/dogrula", { cihazlar: hedefler });
    if (kayit) this.sonuclariGoster(kayit);
  },

  async surumler() {
    let ids = Secim.liste();
    if (!ids.length) ids = Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan && !c.uygunluk.veyon_oku).map((c) => c.id);
    const hedefler = await onayIste({ islem: "veyon_oku", cihazlar: ids, baslik: "Veyon sürümlerini yenile",
      aciklama: "Yalnız envanterdeki bilgisayarlardan kurulu Veyon sürümü okunur (ağ taraması yapılmaz). Seçim yoksa laboratuvardaki tüm uygun bilgisayarlar sorgulanır." });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/veyon/surumler", { cihazlar: hedefler });
    if (kayit) this.sonuclariGoster(kayit);
  },

  async geriAl() {
    const hedefler = await onayIste({ islem: "veyon", cihazlar: Secim.liste(), baslik: "Önceki Veyon ayarlarını geri yükle",
      aciklama: "Her bilgisayarda bu uygulamanın son Veyon yapılandırmasından önce aldığı yedek geri konur: Veyon.conf, public anahtarlar ve servisin açık/kapalı durumu. Veyon paketi kaldırılmaz; sürüm değişmez.",
      uyarilar: ["Geri alınca bu uygulamanın kurduğu anahtar kalkabilir; Veyon Master o bilgisayarlara anahtarla bağlanamayabilir."],
      yikici: true, onayMetni: "Önceki Veyon ayarlarına dönmeyi onaylıyorum", baslatMetni: "Geri yükle" });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/veyon/geri-al", { cihazlar: hedefler, onay: true });
    if (kayit) this.sonuclariGoster(kayit);
  },

  /* ---------------------------------------------------------------- işlem sonuçları */
  sonuclariGoster(kayit) {
    this.sonKayit = kayit;
    try { sessionStorage.setItem("psy-veyon-son-is", kayit.id); } catch (_) { /* yok */ }
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, h);
    const say = (d) => kayit.hedefler.filter((h) => h.durum === d).length;
    $("#m1s4-sonuc-baslik").textContent = `${IS_ADLARI[kayit.tip] || kayit.tip} — ${tarih(kayit.baslangic)} · ✓ ${say("basarili")} · ✗ ${say("basarisiz")} · → ${say("atlandi")}`;
    const tablo = el("table", {}, el("thead", {}, el("tr", {}, ...["Bilgisayar", "Sonuç", "Aşama", "Ayrıntı"].map((b) => el("th", { metin: b })))));
    const g = el("tbody");
    for (const h of kayit.hedefler) {
      const [m, t] = HEDEF_ROZETI[h.durum] || ["…", "mavi"];
      g.append(el("tr", {}, el("td", { metin: (h.veri && h.veri.ad) || h.hedef }), el("td", {}, rozet(m, t)),
        el("td", { metin: h.asama || "—" }), el("td", { class: "uzun-metin", metin: (h.mesaj || "").replace(/^[^—]*— /, "") })));
    }
    tablo.append(g);
    $("#m1s4-sonuclar").replaceChildren(tablo);
    this.tablo.ciz();
  },
};

sayfaKaydet("M1-S4", m1s4);
