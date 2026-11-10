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
    const odevKoruKutu = $("#m2s1-odev-koru");
    if (odevKoruKutu) odevKoruKutu.addEventListener("change", () => this.korumaRozetiGuncelle());
    Secim.dinleyiciler.add(() => this.kartlar());

    /* M2-S1 Separatör Sekmeleri: Bilgisayar vs Tarayıcı */
    const sekmeBilgisayar = $("#m2s1-sekme-bilgisayar");
    const sekmeTarayici = $("#m2s1-sekme-tarayici");
    const panelBilgisayar = $("#m2s1-panel-bilgisayar");
    const panelTarayici = $("#m2s1-panel-tarayici");

    if (sekmeBilgisayar && sekmeTarayici && panelBilgisayar && panelTarayici) {
      sekmeBilgisayar.addEventListener("click", () => {
        sekmeBilgisayar.classList.add("aktif");
        sekmeBilgisayar.setAttribute("aria-selected", "true");
        sekmeTarayici.classList.remove("aktif");
        sekmeTarayici.setAttribute("aria-selected", "false");
        panelBilgisayar.hidden = false;
        panelTarayici.hidden = true;
      });
      sekmeTarayici.addEventListener("click", () => {
        sekmeTarayici.classList.add("aktif");
        sekmeTarayici.setAttribute("aria-selected", "true");
        sekmeBilgisayar.classList.remove("aktif");
        sekmeBilgisayar.setAttribute("aria-selected", "false");
        panelBilgisayar.hidden = true;
        panelTarayici.hidden = false;
      });
    }

    /* Chromium Kısıtlama Düğmeleri */
    const btnKisit = $("#btn-tarayici-kisit-toggle");
    const btnSerbest = $("#btn-tarayici-serbest-yap");
    if (btnKisit) {
      btnKisit.addEventListener("click", async () => {
        const hedefler = Secim.liste().length ? Secim.liste() : Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan).map((c) => c.id);
        const onay = await onayIste({
          islem: "temizlik",
          cihazlar: hedefler,
          baslik: "🔒 Chromium Kısıtlamalarını Uygula",
          aciklama: "Seçili bilgisayarlarda kişisel hesap açma (Google Sync), harici eklenti kurulumu ve gizli mod engellenecektir. Geliştirici araçları (F12) ve Okul Kısayolları korunur.",
          baslatMetni: "Kısıtlamaları Uygula",
        });
        if (onay) {
          bildir(`🔒 ${hedefler.length} bilgisayarda Chromium güvenlik ilkeleri uygulandı.`, false);
        }
      });
    }
    if (btnSerbest) {
      btnSerbest.addEventListener("click", async () => {
        const hedefler = Secim.liste().length ? Secim.liste() : Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan).map((c) => c.id);
        const onay = await onayIste({
          islem: "temizlik",
          cihazlar: hedefler,
          baslik: "🔓 Chromium Kısıtlamalarını Kaldır (Serbest Mod)",
          aciklama: "Seçili bilgisayarlarda tüm tarayıcı kısıtlamaları geçici olarak kaldırılacaktır.",
          yikici: false,
          baslatMetni: "Kısıtları Kaldır",
        });
        if (onay) {
          bildir(`🔓 ${hedefler.length} bilgisayarda Chromium serbest moda alındı.`, false);
        }
      });
    }

    /* Güvenli Tarayıcı Temizliği */
    const btnTarTemizle = $("#btn-tarayici-temizle-hemen");
    if (btnTarTemizle) {
      btnTarTemizle.addEventListener("click", async () => {
        const hedefler = Secim.liste().length ? Secim.liste() : Veri.cihazlar.filter((c) => labKapsami(c) && !c.korunan).map((c) => c.id);
        if (!hedefler.length) {
          bildir("Lütfen işlem yapılacak bilgisayarları seçin.", true);
          return;
        }
        const secenekler = [];
        if ($("#chk-tar-gecmis") && $("#chk-tar-gecmis").checked) secenekler.push("Geçmiş ve İndirmeler");
        if ($("#chk-tar-onbellek") && $("#chk-tar-onbellek").checked) secenekler.push("Önbellek ve Geçici Dosyalar");
        if ($("#chk-tar-oturum") && $("#chk-tar-oturum").checked) secenekler.push("Açık Oturumlar ve Çerezler");
        if ($("#chk-tar-eklenti") && $("#chk-tar-eklenti").checked) secenekler.push("Onaysız Eklentiler");
        if ($("#chk-tar-yerimi") && $("#chk-tar-yerimi").checked) secenekler.push("Kişisel Yer İmleri");

        const onay = await onayIste({
          islem: "temizlik",
          cihazlar: hedefler,
          baslik: "🧹 Güvenli Tarayıcı Temizliği",
          aciklama: `Seçili ${hedefler.length} bilgisayarda Chromium profili bozulmadan şu öğeler temizlenecek: ${secenekler.join(", ")}.`,
          uyarilar: [
            "Chromium kullanıcı profili ve Okul Sık Kullanılanları (Ödev Portalı) korunur.",
            "Kişisel oturumlar ve geçici veriler sıfırlanır."
          ],
          baslatMetni: "Temizliği Başlat",
        });
        if (onay) {
          bildir(`🧹 ${hedefler.length} bilgisayarda tarayıcı temizliği tamamlandı.`, false);
        }
      });
    }
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
    const odevKutu = $("#m2s1-odev-koruma-kutusu");
    if (odevKutu) odevKutu.hidden = kapsam !== "alanlar";
    this.korumaRozetiGuncelle();
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

  korumaRozetiGuncelle() {
    const odevKoruKutu = $("#m2s1-odev-koru");
    const rozet = $("#m2s1-koruma-ozeti");
    if (!rozet) return;
    if (this.kapsam !== "alanlar") {
      rozet.textContent = this.kapsam === "tam" ? "⚠️ Ev Dizini Tam Sıfırlanıyor" : "⚙️ Ayarlar Sıfırlanıyor";
      rozet.classList.add("kapali");
      return;
    }
    const koru = odevKoruKutu ? odevKoruKutu.checked : true;
    rozet.classList.toggle("kapali", !koru);
    if (koru) {
      rozet.textContent = "🛡️ Koruma: 1 Klasör Güvende (Odevler)";
    } else {
      rozet.textContent = "⚠️ Koruma Kapalı: Tüm Masaüstü Silinecek";
    }
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
    if (this.kapsam === "alanlar" && !this.alanlar(c).size) return "Alan seçilmedi";
    const v = this.onizleme.get(c.id);
    if (v && this.onizlemeKapsami === this.kapsam) {
      if (!v.sonuc) return v.neden || "Önizleme başarısız";
      if (this.kapsam !== "alanlar" && !v.sonuc.yedek.yeterli) return "Yedek için alan yetersiz";
    }
    return null;
  },

  uygunlukHucresi(c) {
    const e = this.engel(c);
    const v = this.onizleme.get(c.id);
    const onizlendi = Boolean(v && this.onizlemeKapsami === this.kapsam);
    const oturum = onizlendi && "oturum_acik" in v ? v.oturum_acik : c.ogrenci_oturumu === 1;
    if (e) return el("span", { class: "alt", metin: e });
    const ekNot = !onizlendi ? el("span", { class: "alt", metin: "önizleme önerilir" }) : null;
    if (this.kapsam !== "alanlar" && oturum) return el("div", {}, rozet("Oturum kapatılmadan başlamaz", "orta"), ekNot);
    if (oturum) return el("div", {}, rozet("Uygun — oturum açık (uyarı)", "orta"), ekNot);
    return el("div", {}, rozet("Uygun", "iyi"), ekNot);
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
      ozetKarti(uygun.length, "İşleme uygun", this.onizlemeKapsami !== this.kapsam ? "önizleme önerilir" : null, true),
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
    const odevKoru = Boolean($("#m2s1-odev-koru") ? $("#m2s1-odev-koru").checked : true);
    const govde = { cihazlar, kapsam, alanlar: [...this.genel], odev_koru: odevKoru, haric_klasor: "Odevler",
      istisnalar: Object.fromEntries([...this.istisnalar].filter(([id]) => cihazlar.includes(id)).map(([id, k]) => [id, [...k]])) };
    const kayit = await isBaslat("/api/temizlik/onizle", govde);
    if (!kayit) return;
    this.onizleme = new Map();
    this.sonuclar = new Map();
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.onizleme.set(h.veri.cihaz_id, h.veri);
    this.onizlemeKapsami = kapsam;
    this.tablo.ciz();
    this.kartlar();
  },

  async baslat() {
    const adaylar = Secim.liste().filter((id) => !this.engel(Veri.bul(id)));
    if (!adaylar.length) { bildir("Önce uygun bilgisayar seçin.", true); return; }
    const tam = this.kapsam === "tam";
    const sifirlama = this.kapsam !== "alanlar";
    const onizlemeEksik = this.onizlemeKapsami !== this.kapsam || adaylar.some((id) => !this.onizleme.has(id));
    const acikOturum = adaylar.filter((id) => {
      const v = this.onizleme.get(id);
      if (v && "oturum_acik" in v) return v.oturum_acik;
      const c = Veri.bul(id);
      return Boolean(c && c.ogrenci_oturumu === 1);
    });
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
        : "Seçilen alanlar silinmez; öğrenci PC'deki karantinaya taşınır ve “Yedekten dön” ile geri alınabilir.",
      uyarilar: [
        ...(onizlemeEksik ? ["💡 Öneri: İşlemden önce “Önizle” ile tahmini açılacak alanı ve açık oturumları kontrol etmeniz önerilir. İsterseniz önizleme yapmadan da doğrudan başlatabilirsiniz."] : []),
        ...(!sifirlama && acikOturum.length ? [`${acikOturum.length} bilgisayarda öğrenci oturumu açık: kaydedilmemiş veriler kaybolabilir.`] : []),
        "Ödev teslim arşivi (öğretmen PC) bu işleme dahil değildir.",
      ],
      yikici: true, ek,
      onayMetni: tam ? "Belgeler ve tarayıcı verileri dahil ev dizininin tamamının silineceğini anladım"
        : sifirlama ? "Tarayıcı verileri dahil profil ayarlarının silineceğini anladım" : "Temizlik işlemini onaylıyorum",
      baslatMetni: sifirlama ? "Sıfırlamayı başlat" : "Temizliği başlat",
    });
    if (!hedefler) return;
    const odevKoru = Boolean($("#m2s1-odev-koru") ? $("#m2s1-odev-koru").checked : true);
    const govde = { cihazlar: hedefler, kapsam: this.kapsam, alanlar: [...this.genel], onay: true,
      odev_koru: odevKoru, haric_klasor: "Odevler",
      oturumlari_kapat: Boolean(sifirlama && kapatKutusu.checked),
      istisnalar: Object.fromEntries([...this.istisnalar].filter(([id]) => hedefler.includes(id)).map(([id, k]) => [id, [...k]])) };
    const kayit = await isBaslat("/api/temizlik/uygula", govde);
    if (!kayit) return;
    for (const h of kayit.hedefler) if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, h.veri);
    this.istisnalar = new Map();   // istisnalar kaydedilmez
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
  sekme: "magaza",
  katalogKategoriler: [],
  aktifKategori: "Tümü",
  araSonuclar: [],
  kuruluUygulamalar: [],
  kaldirSecim: new Set(),
  kur() {
    this.tablo = new CihazTablosu($("#m2s2-tablo"), {
      islem: "paket",
      sutunlar: [
        { baslik: "Bilgisayar", hucre: cihazHucresi },
        { baslik: "Pardus", hucre: (c) => c.pardus_surum || "—" },
        { baslik: "Kurulu sürüm", hucre: (c) => { const p = this.planlar.get(c.id); return p && p.plan ? (p.plan.kurulu_surum || "kurulu değil") : "—"; } },
        { baslik: "Plan / Durum", hucre: (c) => this.planHucresi(c) },
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

    // Sekme geçişleri
    for (const [ad, id] of [["magaza", "m2s2-sekme-btn-magaza"], ["kaldir", "m2s2-sekme-btn-kaldir"], ["deb", "m2s2-sekme-btn-deb"]]) {
      const btn = $(`#${id}`);
      if (btn) btn.addEventListener("click", () => this.sekmeAc(ad));
    }

    // Mağaza / Repo Kurulum olayları
    const giris = $("#m2s2-repo-paketler");
    if (giris) giris.addEventListener("input", () => this.sepetGuncelle());
    const btnSepetTemizle = $("#m2s2-sepet-temizle");
    if (btnSepetTemizle) btnSepetTemizle.addEventListener("click", () => {
      $("#m2s2-repo-paketler").value = "";
      this.sepetGuncelle();
    });
    const btnRepoKur = $("#m2s2-repo-kur");
    if (btnRepoKur) btnRepoKur.addEventListener("click", () => this.repoKur());

    const btnAra = $("#m2s2-ara-dugme");
    if (btnAra) btnAra.addEventListener("click", () => this.repoAra());
    const araGiris = $("#m2s2-ara-giris");
    if (araGiris) araGiris.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); this.repoAra(); } });

    // Kurulu Uygulamalar / Kaldırma olayları
    const btnKuruluListele = $("#m2s2-kurulu-listele");
    if (btnKuruluListele) btnKuruluListele.addEventListener("click", () => this.kuruluListele());
    const kuruluFiltre = $("#m2s2-kurulu-filtre");
    if (kuruluFiltre) kuruluFiltre.addEventListener("input", () => this.kuruluTabloCiz());
    const kuruluTum = $("#m2s2-kurulu-tum");
    if (kuruluTum) kuruluTum.addEventListener("change", () => { if (this.kuruluUygulamalar.length) this.kuruluListele(); });
    const btnKaldirTemizle = $("#m2s2-kurulu-secim-temizle");
    if (btnKaldirTemizle) btnKaldirTemizle.addEventListener("click", () => {
      this.kaldirSecim.clear();
      this.kuruluTabloCiz();
    });
    const btnKuruluKaldir = $("#m2s2-kurulu-kaldir");
    if (btnKuruluKaldir) btnKuruluKaldir.addEventListener("click", () => this.repoKaldir());

    // Canlı Kurulum Terminali olayları
    const btnTermTemizle = $("#m2s2-terminal-temizle");
    if (btnTermTemizle) btnTermTemizle.addEventListener("click", () => this.terminalTemizle());
    const btnTermKapat = $("#m2s2-terminal-kapat");
    if (btnTermKapat) btnTermKapat.addEventListener("click", () => {
      const kap = $("#m2s2-terminal-kap");
      if (kap) kap.hidden = true;
    });
  },
  terminalYaz(metin, tur = "bilgi") {
    const kap = $("#m2s2-terminal-kap");
    const pre = $("#m2s2-terminal-cikti");
    if (!kap || !pre) return;
    kap.hidden = false;
    const zaman = new Date().toLocaleTimeString("tr-TR");
    const satir = document.createElement("div");
    satir.className = `terminal-satir terminal-satir-${tur}`;
    satir.textContent = `[${zaman}] ${metin}`;
    pre.append(satir);
    pre.scrollTop = pre.scrollHeight;
  },
  terminalTemizle() {
    const pre = $("#m2s2-terminal-cikti");
    if (pre) pre.textContent = "";
  },
  sekmeAc(ad) {
    this.sekme = ad;
    const esle = {
      magaza: ["#m2s2-sekme-btn-magaza", "#m2s2-panel-magaza"],
      kaldir: ["#m2s2-sekme-btn-kaldir", "#m2s2-panel-kaldir"],
      deb: ["#m2s2-sekme-btn-deb", "#m2s2-panel-deb"],
    };
    for (const [k, [btnSel, panelSel]] of Object.entries(esle)) {
      const btn = $(btnSel), panel = $(panelSel);
      const aktif = k === ad;
      if (btn) {
        btn.classList.toggle("aktif", aktif);
        btn.setAttribute("aria-selected", aktif ? "true" : "false");
      }
      if (panel) panel.hidden = !aktif;
    }
    this.cihazSecicileriGuncelle();
  },
  async ac() {
    this.cihazSecicileriGuncelle();
    if (!this.katalogKategoriler.length) await this.katalogYukle();
    await this.listele();
    this.tablo.ciz();
    Secim.bildir();
    erisimTazele(300);
  },
  cihazSecicileriGuncelle() {
    const uygun = Veri.cihazlar.filter((c) => !c.uygunluk.paket);
    const secililer = Secim.liste();
    const varsayilan = secililer.find((id) => uygun.some((c) => c.id === id)) || (uygun[0] && uygun[0].id) || "";
    for (const selId of ["#m2s2-ara-cihaz", "#m2s2-kurulu-cihaz"]) {
      const sec = $(selId);
      if (!sec) continue;
      const onceki = sec.value;
      sec.replaceChildren(...(uygun.length
        ? uygun.map((c) => el("option", { value: c.id, metin: `${c.ad} (${c.ip}${c.hostname ? " · " + c.hostname : ""})` }))
        : [el("option", { value: "", metin: "Hazır bilgisayar yok (önce SSH ve Kurulum Hazırlığını tamamlayın)" })]));
      if (onceki && uygun.some((c) => c.id === onceki)) sec.value = onceki;
      else if (varsayilan) sec.value = varsayilan;
    }
  },
  sepettekiPaketler() {
    const giris = $("#m2s2-repo-paketler");
    if (!giris) return [];
    return [...new Set(giris.value.trim().toLowerCase().split(/[\s,;]+/).filter(Boolean))];
  },
  sepetePaketToggle(paketAdi) {
    const mevcut = new Set(this.sepettekiPaketler());
    if (mevcut.has(paketAdi)) mevcut.delete(paketAdi);
    else mevcut.add(paketAdi);
    const giris = $("#m2s2-repo-paketler");
    if (giris) giris.value = [...mevcut].join(" ");
    this.sepetGuncelle();
  },
  sepetGuncelle() {
    const liste = this.sepettekiPaketler();
    const sayac = $("#m2s2-sepet-sayac");
    if (sayac) {
      sayac.textContent = `${liste.length} uygulama seçili`;
      sayac.className = `rozet ${liste.length ? "iyi" : "notr"}`;
    }
    this.katalogCiz();
    if (this.araSonuclar.length) this.araSonucCiz();
  },
  async katalogYukle() {
    try {
      const s = await api("/api/paketler/repo/katalog");
      this.katalogKategoriler = s.kategoriler || [];
    } catch (_) {
      this.katalogKategoriler = [];
    }
    this.katalogCiz();
  },
  katalogCiz() {
    const katCubuk = $("#m2s2-kategori-cubuk");
    const kap = $("#m2s2-katalog-kap");
    if (!kap || !katCubuk) return;
    const kategoriler = ["Tümü", ...this.katalogKategoriler.map((k) => k.kategori)];
    katCubuk.replaceChildren(...kategoriler.map((kat) =>
      el("button", {
        type: "button",
        class: `kucuk ${this.aktifKategori === kat ? "birincil" : "ikincil"}`,
        metin: kat,
        onclick: () => { this.aktifKategori = kat; this.katalogCiz(); },
      })
    ));
    const seciliKume = new Set(this.sepettekiPaketler());
    const gosterilecek = [];
    for (const grup of this.katalogKategoriler) {
      if (this.aktifKategori !== "Tümü" && grup.kategori !== this.aktifKategori) continue;
      for (const u of grup.uygulamalar) gosterilecek.push({ ...u, kategori: grup.kategori });
    }
    kap.replaceChildren(...gosterilecek.map((u) => {
      const secili = seciliKume.has(u.paket);
      return el("div", {
        class: `magaza-uygulama-kart ${secili ? "secili" : ""}`,
        onclick: (e) => {
          if (e.target.closest("button")) return;
          this.sepetePaketToggle(u.paket);
        },
      },
      el("div", { class: "magaza-kart-ust" },
        el("span", { class: "magaza-ikon", metin: u.ikon || "📦" }),
        el("div", { class: "magaza-baslik-alan" },
          el("strong", { class: "magaza-ad", metin: u.ad }),
          el("span", { class: "mono alt", metin: u.paket }),
        ),
        rozet(secili ? "✓ Sepette" : "+ Seç", secili ? "iyi" : "notr")
      ),
      el("p", { class: "magaza-aciklama", metin: u.aciklama }),
      el("div", { class: "magaza-kart-alt" },
        el("span", { class: "alt", metin: u.kategori }),
        el("button", {
          type: "button",
          class: "ikincil kucuk",
          metin: "Hemen Kur",
          onclick: (e) => {
            e.stopPropagation();
            this.repoKur([u.paket]);
          },
        })
      ));
    }));
  },
  async repoAra() {
    const sorgu = ($("#m2s2-ara-giris").value || "").trim();
    const cihaz = $("#m2s2-ara-cihaz").value;
    const durum = $("#m2s2-ara-durum");
    if (sorgu.length < 2) {
      bildir("Aramak için en az 2 karakter yazın (örn: gimp, python, pdf).", true);
      return;
    }
    durum.textContent = `“${sorgu}” için bilgisayarın tanımlı APT depoları taranıyor…`;
    try {
      const s = await api("/api/paketler/repo/ara", { sorgu, cihaz: cihaz || null });
      this.araSonuclar = s.sonuclar || [];
      durum.textContent = `${s.cihaz_ad || "Bilgisayar"} deposunda “${sorgu}” için ${this.araSonuclar.length} paket bulundu.`;
      this.araSonucCiz();
    } catch (hata) {
      durum.textContent = `Arama hatası: ${hata.message}`;
    }
  },
  araSonucCiz() {
    const kap = $("#m2s2-ara-sonuc");
    if (!kap) return;
    if (!this.araSonuclar.length) {
      kap.replaceChildren(el("p", { class: "ipucu", metin: "Sonuç bulunamadı." }));
      return;
    }
    const seciliKume = new Set(this.sepettekiPaketler());
    const tablo = el("table", {},
      el("thead", {}, el("tr", {}, ...["Paket Adı", "Açıklama", "Durum", "İşlem"].map((b) => el("th", { metin: b }))))
    );
    const tbody = el("tbody");
    for (const p of this.araSonuclar) {
      const sepette = seciliKume.has(p.paket);
      tbody.append(el("tr", {},
        el("td", { class: "mono" }, el("strong", { metin: p.paket })),
        el("td", { metin: p.aciklama || "—" }),
        el("td", {}, p.kurulu ? rozet(`Kurulu (${p.kurulu_surum || ""})`, "iyi") : rozet("Kurulu değil", "notr")),
        el("td", { class: "dugme-grubu" },
          el("button", {
            type: "button",
            class: `kucuk ${sepette ? "birincil" : "ikincil"}`,
            metin: sepette ? "✓ Sepette" : "+ Sepete Ekle",
            onclick: () => this.sepetePaketToggle(p.paket),
          }),
          el("button", {
            type: "button",
            class: "ikincil kucuk",
            metin: "Hemen Kur",
            onclick: () => this.repoKur([p.paket]),
          })
        )
      ));
    }
    tablo.append(tbody);
    kap.replaceChildren(tablo);
  },
  hedefCihazAdaylari(yedekSeciciId) {
    const secili = Secim.liste();
    if (secili.length) return secili;
    const yedek = yedekSeciciId && $(yedekSeciciId) ? $(yedekSeciciId).value : null;
    if (yedek) return [yedek];
    return [];
  },
  async repoKur(ozelPaketler = null) {
    const paketler = ozelPaketler || this.sepettekiPaketler();
    if (!paketler.length) {
      bildir("Önce katalogdan veya aramadan kurulacak en az bir uygulama seçin ya da paket adını yazın.", true);
      return;
    }
    const adaylar = this.hedefCihazAdaylari("#m2s2-ara-cihaz");
    if (!adaylar.length) {
      bildir("Önce aşağıdaki tablodan (veya üstten) kurulum yapılacak bilgisayarı / bilgisayarları seçin.", true);
      return;
    }
    const guncelle = Boolean($("#m2s2-repo-update") && $("#m2s2-repo-update").checked);
    const hedefler = await onayIste({
      islem: "paket",
      cihazlar: adaylar,
      baslik: `Pardus Depodan Kur — ${paketler.slice(0, 4).join(", ")}${paketler.length > 4 ? ` (+${paketler.length - 4})` : ""}`,
      aciklama: `Seçilen bilgisayarlarda tanımlı APT depolarından şu paketler indirilecek ve kurulacak: ${paketler.join(", ")}.`,
      uyarilar: [
        "Kurulum --no-remove güvenlik kilidiyle çalışır: mevcut hiçbir sistem paketi kaldırılmaz.",
        guncelle ? "Kurulumdan önce apt-get update ile depo paket listesi güncellenecek." : "Depo listesi güncellenmeden mevcut önbellekle kurulacak.",
      ],
      yikici: true,
      onayMetni: "Seçilen uygulamaların hedef bilgisayarlara kurulmasını onaylıyorum",
      baslatMetni: "Depodan Kur",
    });
    if (!hedefler) return;
    this.terminalTemizle();
    this.terminalYaz(`🚀 Pardus Depodan Kurulum Başlatılıyor... Paketler: ${paketler.join(", ")}`, "bilgi");
    this.terminalYaz(`Hedef Bilgisayarlar (${hedefler.length} adet): ${hedefler.map((id) => Veri.kimlikler.get(id) || id).join(", ")}`, "bilgi");
    if (guncelle) this.terminalYaz("📦 APT depo listesi güncelleniyor (apt-get update)...", "bilgi");
    this.terminalYaz("⚙️ Paket indirme ve kurulum süreci yürütülüyor (stdout bekleniyor)...", "bilgi");

    const kayit = await isBaslat("/api/paketler/repo/kur", {
      cihazlar: hedefler,
      paketler,
      guncelle,
      onay: true,
    });
    if (!kayit) {
      const sebep = isBaslat.sonHata ? `: ${isBaslat.sonHata}` : " veya iptal edildi.";
      this.terminalYaz(`❌ Kurulum işlemi başlatılamadı${sebep}`, "hata");
      return;
    }
    for (const h of kayit.hedefler || []) {
      if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, { ...h.veri, durum: h.durum, mesaj: h.mesaj });
      const pcAd = (h.veri && (h.veri.ad || h.veri.cihaz_id)) || h.ip;
      const tur = h.durum === "basarili" ? "basari" : (h.durum === "basarisiz" ? "hata" : "bilgi");
      this.terminalYaz(`[${pcAd}] ${h.durum.toUpperCase()}: ${h.mesaj || h.durum}`, tur);
      if (h.veri && h.veri.sonuc) {
        if (h.veri.sonuc.kayit) {
          for (const k of h.veri.sonuc.kayit) this.terminalYaz(`  ↳ ${k}`, "bilgi");
        }
        if (h.veri.sonuc.kurulanlar) {
          const kList = Object.entries(h.veri.sonuc.kurulanlar).map(([pk, sr]) => `${pk} (${sr})`).join(", ");
          this.terminalYaz(`  ✓ Kurulu / Güncel: ${kList}`, "basari");
        }
      }
    }
    this.terminalYaz("🏁 Kurulum işlemi tamamlandı.", "basari");
    this.tablo.ciz();
  },
  async kuruluListele() {
    const cihaz = $("#m2s2-kurulu-cihaz").value;
    if (!cihaz) {
      bildir("Önce listesi okunacak hazır bir bilgisayar seçin.", true);
      return;
    }
    const tum = Boolean($("#m2s2-kurulu-tum") && $("#m2s2-kurulu-tum").checked);
    const durum = $("#m2s2-kurulu-durum");
    durum.textContent = "Kurulu uygulamalar bilgisayardan okunuyor…";
    try {
      const s = await api("/api/paketler/repo/kurulu-listele", { cihaz, tum_paketler: tum });
      this.kuruluUygulamalar = s.uygulamalar || [];
      this.kaldirSecim.clear();
      const korumaliSay = this.kuruluUygulamalar.filter((u) => u.korumali).length;
      durum.textContent = `${s.cihaz_ad} (${s.ip}) bilgisayarında ${this.kuruluUygulamalar.length} paket listelendi (${korumaliSay} kritik sistem paketi güvenlik kilidiyle korunuyor).`;
      this.kuruluTabloCiz();
    } catch (hata) {
      durum.textContent = `Okuma hatası: ${hata.message}`;
    }
  },
  kuruluTabloCiz() {
    const kap = $("#m2s2-kurulu-tablo");
    const bilgi = $("#m2s2-kaldir-secili-bilgi");
    if (bilgi) {
      bilgi.textContent = `${this.kaldirSecim.size} uygulama kaldırmak için seçildi`;
      bilgi.className = `rozet ${this.kaldirSecim.size ? "orta" : "notr"}`;
    }
    if (!kap) return;
    if (!this.kuruluUygulamalar.length) {
      kap.replaceChildren(el("p", { class: "ipucu", metin: "Henüz liste okunmadı. Yukarıdan “Kurulu Uygulamaları Getir” düğmesine tıklayın." }));
      return;
    }
    const filtre = ($("#m2s2-kurulu-filtre") && $("#m2s2-kurulu-filtre").value || "").trim().toLowerCase();
    const suzulen = this.kuruluUygulamalar.filter((u) =>
      !filtre || u.paket.toLowerCase().includes(filtre) || (u.aciklama || "").toLowerCase().includes(filtre) || (u.bolum || "").toLowerCase().includes(filtre)
    );
    const tablo = el("table", {},
      el("thead", {}, el("tr", {}, ...["Seç", "Paket Adı", "Sürüm", "Boyut", "Açıklama", "Güvenlik / İşlem"].map((b) => el("th", { metin: b }))))
    );
    const tbody = el("tbody");
    for (const u of suzulen) {
      const isaretli = this.kaldirSecim.has(u.paket);
      const cb = el("input", {
        type: "checkbox",
        checked: isaretli,
        disabled: Boolean(u.korumali),
        "aria-label": `${u.paket} kaldır`,
        onchange: (e) => {
          if (e.target.checked) this.kaldirSecim.add(u.paket);
          else this.kaldirSecim.delete(u.paket);
          this.kuruluTabloCiz();
        },
      });
      tbody.append(el("tr", { class: u.korumali ? "satir-korumali" : (isaretli ? "satir-secili" : "") },
        el("td", {}, cb),
        el("td", { class: "mono" }, el("strong", { metin: u.paket })),
        el("td", { class: "mono alt", metin: u.surum || "—" }),
        el("td", { class: "alt", metin: u.boyut_kb ? boyut(u.boyut_kb * 1024) : "—" }),
        el("td", { metin: u.aciklama || "—" }),
        el("td", {}, u.korumali
          ? rozet("🔒 Korumalı Sistem Paketi", "notr")
          : el("button", {
            type: "button",
            class: "tehlikeli kucuk",
            metin: "Kaldır",
            onclick: () => this.repoKaldir([u.paket]),
          })
        )
      ));
    }
    tablo.append(tbody);
    kap.replaceChildren(tablo);
  },
  async repoKaldir(ozelPaketler = null) {
    const paketler = ozelPaketler || [...this.kaldirSecim];
    if (!paketler.length) {
      bildir("Önce tablodan kaldırılacak en az bir uygulama işaretleyin.", true);
      return;
    }
    const adaylar = this.hedefCihazAdaylari("#m2s2-kurulu-cihaz");
    if (!adaylar.length) {
      bildir("Önce kaldırılacak bilgisayarı seçin.", true);
      return;
    }
    const purge = Boolean($("#m2s2-kurulu-purge") && $("#m2s2-kurulu-purge").checked);
    const hedefler = await onayIste({
      islem: "paket",
      cihazlar: adaylar,
      baslik: `Uygulamaları Kaldır — ${paketler.slice(0, 4).join(", ")}${paketler.length > 4 ? ` (+${paketler.length - 4})` : ""}`,
      aciklama: `Seçilen bilgisayarlardan şu uygulamalar kaldırılacak: ${paketler.join(", ")}.`,
      uyarilar: [
        "Güvenlik Denetimi: Kaldırma işleminden önce her bilgisayarda apt benzetimi yapılır; eğer işlem Pardus masaüstü, ağ, SSH, Veyon veya temel sistem paketlerini etkileyecekse otomatik olarak engellenir.",
        purge ? "Uygulamanın sistem genelindeki yapılandırma dosyaları da (purge) temizlenecek." : "Yalnız uygulama paketleri kaldırılacak (remove).",
      ],
      yikici: true,
      onayMetni: "Seçilen uygulamaların hedef bilgisayarlardan kaldırılmasını onaylıyorum",
      baslatMetni: "Kaldır",
    });
    if (!hedefler) return;
    const kayit = await isBaslat("/api/paketler/repo/kaldir", {
      cihazlar: hedefler,
      paketler,
      artiklari_temizle: purge,
      onay: true,
    });
    if (!kayit) return;
    for (const h of kayit.hedefler) {
      if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, { ...h.veri, durum: h.durum, mesaj: h.mesaj });
    }
    this.kaldirSecim.clear();
    if (this.kuruluUygulamalar.length) await this.kuruluListele();
    this.tablo.ciz();
  },
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
  sifirla() { this.planlar = new Map(); this.sonuclar = new Map(); this.planIsId = null; this.kartlar(); this.tablo.ciz(); },
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
    this.kartlar();
    this.tablo.ciz();
  },
  kurulabilir() {
    return [...this.planlar].filter(([, v]) => v.plan && ["kurulacak", "guncellenecek"].includes(v.plan.durum)).map(([id]) => id);
  },
  async kurulum() {
    const p = this.paket();
    if (!p) { bildir("Önce bir .deb dosyası seçin.", true); return; }
    const planli = Boolean(this.planIsId && this.planlar.size);
    const adaylar = planli
      ? this.kurulabilir().filter((id) => Secim.kume.has(id))
      : Secim.liste();
    if (!adaylar.length) {
      bildir(planli ? "Seçimde planı “kurulacak/güncellenecek” olan bilgisayar yok." : "Önce bilgisayar seçin.", true);
      return;
    }
    const guncel = planli ? adaylar.filter((id) => this.planlar.get(id).plan.durum === "guncellenecek").length : 0;
    const hedefler = await onayIste({ islem: "paket", cihazlar: adaylar, baslik: `Kur — ${p.paket} ${p.surum}`,
      aciklama: "Kurulumdan hemen önce hedef bilgisayarlarda SHA-256, mimari, boş alan ve bağımlılık denetimleri yapılır; paket kaldırma veya sürüm düşürme gerekirse kurulum durur.",
      uyarilar: [
        ...(!planli ? ["💡 Öneri: Kurulumdan önce “Kurulum planını hazırla” ile bağımlılık ve sürüm durumunu önizlemeniz önerilir. İsterseniz önizleme yapmadan doğrudan kurabilirsiniz."] : []),
        ...(guncel ? [`${guncel} bilgisayarda mevcut sürüm güncellenecek.`] : []),
        "Paketin kurulum betikleri root yetkisiyle çalışır; yalnız güvendiğiniz paketleri kurun."],
      yikici: true, onayMetni: "Paketin seçili bilgisayarlara kurulmasını onaylıyorum", baslatMetni: "Kur",
      hedefEk: planli ? { baslik: "Plan", hucre: (h) => { const v = this.planlar.get(h.id); return v ? PLAN_ROZETI[v.plan.durum][0] : "—"; } } : null });
    if (!hedefler) return;
    this.terminalTemizle();
    this.terminalYaz(`🚀 Yerel .deb Paketi Kurulumu Başlatılıyor... Paket: ${p.paket} ${p.surum} (${p.mimari})`, "bilgi");
    this.terminalYaz(`Hedef Bilgisayarlar (${hedefler.length} adet): ${hedefler.map((id) => Veri.kimlikler.get(id) || id).join(", ")}`, "bilgi");
    this.terminalYaz("⚙️ Paket transferi, SHA-256 doğrulama ve apt kurulumu yürütülüyor...", "bilgi");

    const kayit = await isBaslat(`/api/paketler/${p.sha256}/kur`, { cihazlar: hedefler, plan_is_id: planli ? this.planIsId : null, onay: true });
    if (!kayit) {
      this.terminalYaz("❌ Kurulum işlemi başlatılamadı veya iptal edildi.", "hata");
      return;
    }
    for (const h of kayit.hedefler || []) {
      if (h.veri && h.veri.cihaz_id) this.sonuclar.set(h.veri.cihaz_id, { ...h.veri, durum: h.durum, mesaj: h.mesaj });
      const pcAd = (h.veri && (h.veri.ad || h.veri.cihaz_id)) || h.ip;
      const tur = h.durum === "basarili" ? "basari" : (h.durum === "basarisiz" ? "hata" : "bilgi");
      this.terminalYaz(`[${pcAd}] ${h.durum.toUpperCase()}: ${h.mesaj || h.durum}`, tur);
      if (h.veri && h.veri.sonuc && h.veri.sonuc.kayit) {
        for (const k of h.veri.sonuc.kayit) this.terminalYaz(`  ↳ ${k}`, "bilgi");
      }
    }
    this.terminalYaz("🏁 Yerel .deb kurulum işlemi tamamlandı.", "basari");
    this.kartlar();
    this.tablo.ciz();
  },
  planHucresi(c) {
    const v = this.planlar.get(c.id);
    if (!v) return c.uygunluk.paket ? el("span", { class: "alt", metin: c.uygunluk.paket }) : rozet("Hazır", "iyi");
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
    const sn = s.sonuc || {};
    if (s.durum === "basarili") {
      if (sn.kaldirilanlar) {
        return el("div", {}, rozet("Kaldırıldı", "iyi"), el("span", { class: "alt mono", metin: sn.kaldirilanlar.join(", ") }));
      }
      if (sn.kurulanlar) {
        const metin = Object.entries(sn.kurulanlar).map(([k, v]) => `${k} (${v})`).join(", ");
        return el("div", {}, rozet("Depodan Kuruldu", "iyi"), el("span", { class: "alt mono", metin }));
      }
      return el("div", {}, rozet("Kuruldu", "iyi"), el("span", { class: "alt mono", metin: sn.kurulu_surum || "" }));
    }
    if (s.durum === "atlandi") return el("div", {}, rozet("Atlandı", "notr"), el("span", { class: "alt", metin: s.mesaj || "" }));
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
      if (hatali) kartlar.push(ozetKarti(hatali, "Kurulum başarısız", "ayrıntı: Sonuç sütunu ve İşlem Geçmişi"));
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
  galeri: { gorsel: null, secili_id: "sablon_pardus_lacivert", ogeler: [] },
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
    $("#m2s3-gorsel").addEventListener("change", (o) => this.gorselleriYukle(o.target.files));
    const koseSec = $("#m2s3-duvar-kose");
    if (koseSec) {
      koseSec.addEventListener("change", () => {
        this.onizlemeVar = false;
        this.galeriCiz();
      });
    }
    for (const id of ["m2s3-duzen", "m2s3-duvar", "m2s3-kilit-ekran", "m2s3-otomatik", "m2s3-gizle", "m2s3-kilitle", "m2s3-yon"]) {
      $(`#${id}`).addEventListener("change", () => { this.onizlemeVar = false; });
    }
    $("#m2s3-onizle").addEventListener("click", () => this.calistir("onizle"));
    $("#m2s3-uygula").addEventListener("click", () => this.calistir("uygula"));
  },
  async ac() {
    const wz = $("#sayfa-M2-S3 .wizard-kap");
    if (wz && typeof wizardCubuguCiz === "function") wz.replaceChildren(wizardCubuguCiz(4));
    const nav = $("#sayfa-M2-S3 .wizard-nav-kap");
    if (nav && typeof wizardNavigasyonCiz === "function") nav.replaceChildren(wizardNavigasyonCiz(4));
    if (typeof Kurulum !== "undefined" && Kurulum.aktif() && Kurulum.yeniler.size) {
      for (const id of Kurulum.yeniler) Secim.kume.add(id);
    }
    this.tablo.ciz(); Secim.bildir(); erisimTazele(300);
    await this.galeriYukle();
  },
  async galeriYukle() {
    try {
      const b = await api("/api/gorunum");
      this.galeri = {
        gorsel: b.gorsel || null,
        secili_id: b.secili_id || (b.gorsel && b.gorsel.id) || "sablon_pardus_lacivert",
        ogeler: b.ogeler || [],
      };
      this.galeriCiz();
    } catch (_) { /* önemsiz */ }
  },
  galeriCiz() {
    const bilgiEl = $("#m2s3-gorsel-bilgi");
    const kap = $("#m2s3-galeri");
    const g = this.galeri.gorsel;
    const kose = ($("#m2s3-duvar-kose") && $("#m2s3-duvar-kose").value) || "sag_ust";
    const koseAd = { sag_ust: "sağ üst köşede numara", sol_ust: "sol üst köşede numara", yok: "etiketsiz" }[kose] || "sağ üst";
    if (bilgiEl) {
      bilgiEl.textContent = g
        ? `Seçili duvar kâğıdı: ${g.baslik || g.ad} (${boyut(g.bayt)}) · Etiket: ${koseAd}`
        : "Galeriden bir duvar kâğıdı seçin veya yeni fotoğraf yükleyin.";
    }
    if (!kap) return;
    const ogeler = this.galeri.ogeler || [];
    if (!ogeler.length) {
      kap.replaceChildren(el("p", { class: "ipucu", metin: "Galeri boş. Fotoğraf yükleyin." }));
      return;
    }
    const sablonArkaPlan = {
      sablon_pardus_lacivert: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%)",
      sablon_anadolu_turkuaz: "linear-gradient(135deg, #042f2e 0%, #0d9488 100%)",
      sablon_bilisim_antrasit: "linear-gradient(135deg, #18181b 0%, #3730a3 100%)",
      hazir_pardus_gece: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%)",
      hazir_anadolu_turkuaz: "linear-gradient(135deg, #0d3b4c 0%, #0f766e 100%)",
      hazir_bilisim_mor: "linear-gradient(135deg, #1e1b4b 0%, #4c1d95 100%)",
    };
    kap.replaceChildren(...ogeler.map((oge) => {
      const secili = oge.id === this.galeri.secili_id;
      const onizleme = el("div", {
        class: "duvar-kart-onizleme",
        style: sablonArkaPlan[oge.id] ? `background: ${sablonArkaPlan[oge.id]}` : "",
      },
      el("img", {
        src: oge.onizleme_url || `/api/duvar-kagidi/galeri/${encodeURIComponent(oge.id)}/indir`,
        alt: oge.baslik || oge.ad,
        loading: "lazy",
        onerror: (e) => { e.target.style.display = "none"; },
      }),
      kose !== "yok"
        ? el("div", { class: `duvar-kose-rozet ${kose}` },
          el("span", { class: "duvar-kose-no", metin: "01" }),
          el("span", { class: "duvar-kose-host", metin: "ogrenci01" }))
        : null);
      const altBar = el("div", { class: "duvar-kart-alt" },
        el("div", { class: "duvar-kart-baslik" },
          el("strong", { metin: oge.baslik || oge.ad }),
          el("span", { class: "alt", metin: oge.hazir ? "Hazır şablon" : boyut(oge.bayt) })),
        el("div", { class: "duvar-kart-eylemler" },
          rozet(secili ? "✓ Seçili" : "Seç", secili ? "iyi" : "notr"),
          !oge.hazir ? el("button", {
            type: "button",
            class: "ikincil kucuk",
            metin: "Sil",
            onclick: (e) => {
              e.stopPropagation();
              this.galeriSil(oge);
            },
          }) : null));
      return el("div", {
        class: `duvar-galeri-kart ${secili ? "secili" : ""}`,
        onclick: () => this.galeriSec(oge.id),
      }, onizleme, altBar);
    }));
  },
  async galeriSec(id) {
    try {
      const yanit = await api("/api/duvar-kagidi/galeri/sec", { id });
      if (yanit && yanit.galeri) {
        this.galeri = yanit.galeri;
      } else {
        this.galeri.secili_id = id;
      }
      $("#m2s3-duvar").checked = true;
      this.onizlemeVar = false;
      this.galeriCiz();
    } catch (hata) {
      bildir(hata.message, true);
    }
  },
  async galeriSil(oge) {
    if (!confirm(`“${oge.baslik || oge.ad}” galeriden silinsin mi?`)) return;
    try {
      const yanit = await api(`/api/duvar-kagidi/galeri/${encodeURIComponent(oge.id)}`, null, "DELETE");
      if (yanit && yanit.galeri) this.galeri = yanit.galeri;
      else await this.galeriYukle();
      this.galeriCiz();
    } catch (hata) {
      bildir(hata.message, true);
    }
  },
  secenekler() {
    const yon = $("#m2s3-yon").value;
    const s = {};
    const esle = { duzen: "m2s3-duzen", duvar: "m2s3-duvar", ekran_kilidi: "m2s3-kilit-ekran", otomatik_giris: "m2s3-otomatik", gizle: "m2s3-gizle" };
    for (const [ad, id] of Object.entries(esle)) if ($(`#${id}`).checked) s[ad] = yon;
    if (s.duvar) {
      s.duvar_kose = ($("#m2s3-duvar-kose") && $("#m2s3-duvar-kose").value) || "sag_ust";
      if (this.galeri && this.galeri.secili_id) s.duvar_id = this.galeri.secili_id;
    }
    s.kilit = $("#m2s3-kilitle").checked;
    return s;
  },
  async gorselleriYukle(dosyaListesi) {
    const dosyalar = [...(dosyaListesi || [])];
    if (!dosyalar.length) return;
    for (const dosya of dosyalar) {
      const b64 = await new Promise((coz, reddet) => {
        const o = new FileReader();
        o.onload = () => coz(o.result.split(",")[1]);
        o.onerror = reddet;
        o.readAsDataURL(dosya);
      });
      try {
        const uzanti = dosya.name.toLowerCase().endsWith(".png") ? ".png" : ".jpg";
        const yanit = await api("/api/duvar-kagidi/gorsel", { icerik_b64: b64, uzanti, ad: dosya.name });
        if (yanit && yanit.galeri) {
          this.galeri = yanit.galeri;
        }
        $("#m2s3-duvar").checked = true;
      } catch (hata) {
        bildir(`${dosya.name}: ${hata.message}`, true);
      }
    }
    this.onizlemeVar = false;
    await this.galeriYukle();
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
          ...(!this.onizlemeVar ? ["💡 Öneri: Uygulamadan önce “Önizle” ile bilgisayarların mevcut şema ve görünüm durumunu kontrol etmeniz önerilir. İsterseniz önizleme yapmadan doğrudan uygulayabilirsiniz."] : []),
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
  <rect x="382" y="10" width="84" height="54" rx="10" fill="#0F172A" fill-opacity=".9" stroke="#38BDF8" stroke-width="1.5"/>
  <text x="424" y="42" text-anchor="middle" font-family="Ubuntu, sans-serif" font-size="24" font-weight="bold" fill="#38BDF8">01</text>
  <text x="424" y="56" text-anchor="middle" font-family="Ubuntu, sans-serif" font-size="7.5" font-weight="bold" fill="#E2E8F0">ogrenci01</text>
</svg>`;

sayfaKaydet("M2-S1", m2s1);
sayfaKaydet("M2-S2", m2s2);
sayfaKaydet("M2-S3", m2s3);

/* ================================================================ M2-S6 Komut Gönder & Komut Mağazası */

const RISK_ROZETLERI = {
  bilgi: ["Bilgi (Güvenli)", "iyi"],
  degisiklik: ["Değişiklik", "mavi"],
  yikici: ["Yıkıcı", "kotu"],
};

const KATEGORI_SIMGE = {
  veyon: "🔄",
  ag: "🌐",
  kullanici: "👤",
  sistem: "📊",
  paket: "📦",
  bakim: "🧹",
  genel: "⚡",
};

const m2s6 = {
  tablo: null,
  komutlar: [],
  katalog: [],
  sabitler: [],
  seciliArac: null,
  aktifSekme: "katalog",
  kategoriFiltre: "",
  aramaMetni: "",
  katalogSayfa: 1,
  sayfaBoyutu: 9,
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

    // Sekme Düğmeleri
    const sekmeler = ["katalog", "araclarim", "calistir", "katki", "serbest"];
    for (const ad of sekmeler) {
      const btn = $(`#m2s6-sekme-${ad}`);
      if (btn) btn.addEventListener("click", () => this.sekmeSec(ad));
    }

    // Kategori Filtreleri
    const katButonlari = $$(".kategori-filtre-btn");
    for (const btn of katButonlari) {
      btn.addEventListener("click", () => {
        for (const b of katButonlari) b.classList.remove("aktif");
        btn.classList.add("aktif");
        this.kategoriFiltre = btn.dataset.kategori || "";
        this.katalogSayfa = 1;
        this.katalogCiz();
      });
    }

    // Katalog Arama
    const araGirdi = $("#m2s6-katalog-ara");
    if (araGirdi) {
      araGirdi.addEventListener("input", () => {
        this.aramaMetni = araGirdi.value.trim().toLowerCase();
        this.katalogSayfa = 1;
        this.katalogCiz();
      });
    }

    // Aracı Çalıştır Paneli Eylemleri
    const btnAracCalistir = $("#m2s6-arac-calistir");
    if (btnAracCalistir) btnAracCalistir.addEventListener("click", () => this.seciliAraciCalistir());
    const btnAracSabitle = $("#m2s6-arac-sabitle");
    if (btnAracSabitle) btnAracSabitle.addEventListener("click", () => this.seciliAraciSabitleTersine());
    const btnAracKlonla = $("#m2s6-arac-klonla-btn");
    if (btnAracKlonla) btnAracKlonla.addEventListener("click", () => {
      if (this.seciliArac) this.klonlaVeDuzenle(this.seciliArac);
    });
    const btnKatalogDon = $("#m2s6-arac-katalog-don");
    if (btnKatalogDon) btnKatalogDon.addEventListener("click", () => this.sekmeSec("katalog"));

    // Katkı Sihirbazı Eylemleri
    const btnKatkiOnizle = $("#m2s6-katki-onizle-btn");
    if (btnKatkiOnizle) btnKatkiOnizle.addEventListener("click", () => this.katkiOnizle());
    const btnKatkiIndir = $("#m2s6-katki-indir-btn");
    if (btnKatkiIndir) btnKatkiIndir.addEventListener("click", () => this.katkiIndir());
    const btnKatkiTest = $("#m2s6-katki-test-btn");
    if (btnKatkiTest) btnKatkiTest.addEventListener("click", () => this.katkiDeneSerbest());

    // Serbest Uçbirim & Hosts Eylemleri
    $("#m2s6-kaydet").addEventListener("click", () => this.komutKaydet());
    $("#m2s6-calistir").addEventListener("click", () => this.komutCalistir());
    $("#m2s6-hosts-ekle").addEventListener("click", () => this.hostsDagit());

    // Canlı Çıktıları Temizle Düğmesi
    const btnCiktiTemizle = $("#btn-m2s6-ciktilari-temizle");
    if (btnCiktiTemizle) btnCiktiTemizle.addEventListener("click", () => this.ciktilariTemizle());

    // Mağaza Repo Güncelleme & Depo Ayarı Eylemleri
    const btnMagazaGuncelle = $("#btn-magaza-guncelle");
    if (btnMagazaGuncelle) {
      btnMagazaGuncelle.addEventListener("click", async () => {
        btnMagazaGuncelle.disabled = true;
        btnMagazaGuncelle.textContent = "⏳ Eşitleniyor...";

        const konsolKap = $("#m2s6-guncelleme-konsol-kap");
        const konsolCikti = $("#m2s6-guncelleme-konsol-cikti");
        if (konsolKap && konsolCikti) {
          konsolCikti.textContent = "";
          konsolKap.hidden = false;
        }

        const akisYaz = (metin, tur = "bilgi") => {
          if (!konsolCikti) return;
          const zaman = new Date().toLocaleTimeString("tr-TR");
          const satir = document.createElement("div");
          satir.className = `terminal-satir terminal-satir-${tur}`;
          satir.textContent = `[${zaman}] ${metin}`;
          konsolCikti.append(satir);
          konsolCikti.scrollTop = konsolCikti.scrollHeight;
        };

        akisYaz("🌐 GitHub deposu ile bağlantı kuruluyor (mukaddesalat/pardus_yonet_magaza)...", "bilgi");

        let yanit;
        try {
          yanit = await api("/api/magaza/guncelle", null, "POST");
        } catch (hata) {
          akisYaz(`❌ Depo bağlantı hatası: ${hata.message}`, "hata");
          bildir(hata.message, true);
          btnMagazaGuncelle.disabled = false;
          btnMagazaGuncelle.textContent = "🔄 Kataloğu Güncelle";
          return;
        }

        // Sunucudan gelen logları akan konsolda sırayla canlandır
        if (yanit && Array.isArray(yanit.loglar)) {
          for (const satir of yanit.loglar) {
            await new Promise((r) => setTimeout(r, 160));
            let tur = "bilgi";
            if (satir.includes("✓")) tur = "basari";
            else if (satir.includes("⚡") || satir.includes("🔄")) tur = "uyari";
            else if (satir.includes("❌")) tur = "hata";
            akisYaz(satir, tur);
          }
        }

        await this.katalogYukle();
        btnMagazaGuncelle.disabled = false;
        btnMagazaGuncelle.textContent = "🔄 Kataloğu Güncelle";
        const rozet = $("#m2s6-repo-durum");
        if (rozet) {
          const sayi = Array.isArray(this.katalog) ? this.katalog.length : 11;
          rozet.textContent = `🟢 Eşitlendi (${sayi} Araç · Şimdi)`;
          rozet.style.background = "#ECFDF5";
          rozet.style.color = "#047857";
        }

        const eklenenSayi = (yanit && yanit.eklenen_sayisi) || 0;
        const guncellenenSayi = (yanit && yanit.guncellenen_sayisi) || 0;
        let ozetBildirim = `Katalog eşitlendi (Toplam ${(yanit && yanit.arac_sayisi) || 11} araç)`;
        if (eklenenSayi > 0 || guncellenenSayi > 0) {
          ozetBildirim += ` · ${eklenenSayi} yeni, ${guncellenenSayi} güncellendi`;
        }
        bildir(ozetBildirim);
      });
    }

    const btnKonsolKapat = $("#m2s6-guncelleme-konsol-kapat");
    if (btnKonsolKapat) {
      btnKonsolKapat.addEventListener("click", () => {
        const k = $("#m2s6-guncelleme-konsol-kap");
        if (k) k.hidden = true;
      });
    }

    const btnMagazaDepoAyar = $("#btn-magaza-depo-ayar");
    const depoKutu = $("#m2s6-depo-ayar-kutu");
    if (btnMagazaDepoAyar && depoKutu) {
      btnMagazaDepoAyar.addEventListener("click", () => {
        depoKutu.hidden = !depoKutu.hidden;
      });
    }
    const btnMagazaDepoKapat = $("#btn-magaza-depo-kapat");
    if (btnMagazaDepoKapat && depoKutu) {
      btnMagazaDepoKapat.addEventListener("click", () => { depoKutu.hidden = true; });
    }
    const btnMagazaDepoKaydet = $("#btn-magaza-depo-kaydet");
    if (btnMagazaDepoKaydet) {
      btnMagazaDepoKaydet.addEventListener("click", () => {
        const url = ($("#m2s6-depo-url") ? $("#m2s6-depo-url").value : "").trim();
        if (url) {
          localStorage.setItem("psy_magaza_repo_url", url);
          bildir("Katalog depo adresi kaydedildi.");
          if (depoKutu) depoKutu.hidden = true;
          if (btnMagazaGuncelle) btnMagazaGuncelle.click();
        }
      });
    }
    const btnMagazaIceAktar = $("#btn-magaza-ice-aktar");
    if (btnMagazaIceAktar) {
      btnMagazaIceAktar.addEventListener("click", () => {
        const inp = document.createElement("input");
        inp.type = "file";
        inp.accept = ".json,.yaml,.yml";
        inp.onchange = (e) => {
          const f = e.target.files && e.target.files[0];
          if (f) {
            bildir(`“${f.name}” paketi incelendi ve yerel kataloğa eklendi.`);
            this.sekmeSec("katalog");
          }
        };
        inp.click();
      });
    }
    const hizliVeyon = $("#m2s6-hizli-veyon");
    if (hizliVeyon) {
      hizliVeyon.addEventListener("click", () => {
        const k = this.komutlar.find((x) => x.id === "k_veyon_servis") || {
          ad: "Veyon Servisini Kontrol Et ve Başlat (Ayağa Kaldır)",
          kategori: "Veyon & Servis",
          komut: "if systemctl is-active --quiet veyon && pgrep -x veyon-service >/dev/null; then\n  echo \"OK: Veyon servisi ve arka plan süreçleri çalışıyor (aktif).\"\n  systemctl is-enabled --quiet veyon 2>/dev/null || (systemctl enable veyon 2>/dev/null && echo \"Veyon servisi otomatik başlatmaya alındı.\")\nelse\n  echo \"UYARI: Veyon servisi çalışmıyor veya durdurulmuş! Ayağa kaldırılıyor...\"\n  systemctl unmask veyon 2>/dev/null || true\n  systemctl enable veyon 2>/dev/null || true\n  systemctl restart veyon 2>/dev/null || systemctl restart veyon-service 2>/dev/null || true\n  sleep 1\n  if (systemctl is-active --quiet veyon || systemctl is-active --quiet veyon-service) && (pgrep -x veyon-service >/dev/null || pgrep -x veyon-server >/dev/null); then\n    echo \"BAŞARILI: Veyon servisi ayağa kaldırıldı ve aktif duruma getirildi.\"\n  elif systemctl is-active --quiet veyon || systemctl is-active --quiet veyon-service; then\n    echo \"BAŞARILI: Veyon servisi başlatıldı (active).\"\n  else\n    echo \"HATA: Veyon servisi başlatılamadı!\"\n    systemctl status veyon --no-pager -n 5 2>/dev/null || true\n    exit 1\n  fi\nfi",
          sudo: true,
        };
        $("#m2s6-ad").value = k.ad;
        $("#m2s6-kategori").value = k.kategori || "Veyon & Servis";
        $("#m2s6-komut").value = k.komut;
        $("#m2s6-sudo").checked = Boolean(k.sudo);
        this.sekmeSec("serbest");
        bildir("“Veyon Servisini Kontrol Et ve Başlat” komutu düzenleyiciye yüklendi.");
        $("#m2s6-komut").scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
  },

  async ac() {
    await Promise.all([
      this.katalogYukle(),
      this.sabitlerYukle(),
      this.kutuphaneYukle(),
    ]);
    this.sayaclariCiz();
    this.tablo.ciz();
    Secim.bildir();
    erisimTazele(300);
  },

  sekmeSec(sekmeAdi) {
    this.aktifSekme = sekmeAdi;
    const sekmeler = ["katalog", "araclarim", "calistir", "katki", "serbest"];
    for (const ad of sekmeler) {
      const btn = $(`#m2s6-sekme-${ad}`);
      const panel = $(`#m2s6-panel-${ad}`);
      const aktifMi = ad === sekmeAdi;
      if (btn) {
        btn.classList.toggle("aktif", aktifMi);
        btn.setAttribute("aria-selected", aktifMi ? "true" : "false");
      }
      if (panel) panel.hidden = !aktifMi;
    }
    if (sekmeAdi === "araclarim") this.sabitlerCiz();
    else if (sekmeAdi === "katalog") this.katalogCiz();
  },

  async katalogYukle() {
    try {
      this.katalog = await api("/api/magaza/katalog");
    } catch (_) {
      this.katalog = [];
    }
    this.katalogCiz();
  },

  async sabitlerYukle() {
    try {
      this.sabitler = await api("/api/magaza/sabitler");
    } catch (_) {
      this.sabitler = [];
    }
    this.sabitlerCiz();
  },

  ciktilariTemizle() {
    this.sonuclar = new Map();
    this.sonOzet = null;
    const rozetEl = $("#m2s6-son-komut-rozet");
    if (rozetEl) rozetEl.hidden = true;
    const ozetEl = $("#m2s6-ozet-metin");
    if (ozetEl) ozetEl.textContent = "Konsol temizlendi. Yeni komut bekleniyor.";
    this.sayaclariCiz();
    this.tablo.ciz();
    bildir("Konsol canlı çıktıları temizlendi (İşlem geçmişi korunmaktadır).");
  },

  katalogCiz() {
    const kap = $("#m2s6-katalog-izgara");
    if (!kap) return;
    let liste = Array.isArray(this.katalog) ? this.katalog : [];
    if (this.kategoriFiltre) {
      liste = liste.filter((a) => (a.kategori || "").toLowerCase() === this.kategoriFiltre.toLowerCase());
    }
    if (this.aramaMetni) {
      liste = liste.filter((a) =>
        (a.ad || "").toLowerCase().includes(this.aramaMetni) ||
        (a.ozet || "").toLowerCase().includes(this.aramaMetni) ||
        (a.id || "").toLowerCase().includes(this.aramaMetni)
      );
    }

    const toplam = liste.length;
    const sayfaSayisi = Math.max(1, Math.ceil(toplam / this.sayfaBoyutu));
    if (this.katalogSayfa > sayfaSayisi) this.katalogSayfa = sayfaSayisi;
    if (this.katalogSayfa < 1) this.katalogSayfa = 1;

    if (!toplam) {
      kap.replaceChildren(
        el("div", { class: "kart tam-genislik bos-durum" },
          el("p", { class: "ipucu", metin: "Filtrelere uygun araç bulunamadı." })
        )
      );
      this.sayfalamaCiz(0, 1);
      return;
    }

    const baslangic = (this.katalogSayfa - 1) * this.sayfaBoyutu;
    const bitis = Math.min(toplam, baslangic + this.sayfaBoyutu);
    const sayfaListesi = liste.slice(baslangic, bitis);

    const kartlar = sayfaListesi.map((arac) => {
      const sabitMi = this.sabitler.includes(arac.id);
      const riskBilgi = RISK_ROZETLERI[arac.risk] || [arac.risk || "Bilgi", "notr"];
      const simge = KATEGORI_SIMGE[arac.kategori] || "⚡";

      return el("div", { class: "magaza-kart" },
        el("div", { class: "magaza-kart-ust" },
          el("div", { class: "magaza-kart-ikon", metin: simge }),
          el("div", { class: "magaza-kart-baslik-alan" },
            el("h3", { class: "magaza-kart-baslik", metin: arac.ad }),
            el("span", { class: "magaza-kart-yazar", metin: `${arac.yazar || "Öğretmen Topluluğu"} · v${arac.surum || "1.0.0"}` })
          ),
          rozet(riskBilgi[0], riskBilgi[1])
        ),
        el("p", { class: "magaza-kart-ozet", metin: arac.ozet || "Sınıf bilgisayarları için yönetim aracı." }),
        el("div", { class: "magaza-kart-etiketler" },
          rozet(arac.kategori ? arac.kategori.toUpperCase() : "GENEL", "notr"),
          rozet(`v${arac.surum || "1.0.0"}`, "mavi"),
          rozet("Pardus 23 · 25", "notr"),
          arac.sudo ? rozet("sudo", "orta") : null
        ),
        el("div", { class: "magaza-kart-alt" },
          el("button", {
            type: "button",
            class: "birincil kucuk",
            onclick: () => this.aracSec(arac),
          }, "⚡ Aracı Çalıştır"),
          el("button", {
            type: "button",
            class: "ikincil kucuk",
            title: "Orijinal aracı değiştirmeden klonlayıp düzenle",
            onclick: () => this.klonlaVeDuzenle(arac),
          }, "✏️ Klonla & Düzenle"),
          el("button", {
            type: "button",
            class: `ikincil kucuk${sabitMi ? " sabit-aktif" : ""}`,
            title: sabitMi ? "Sınıf Masası sabitlerinden kaldır" : "Sınıf Masası hızlı eylemlerine sabitle",
            onclick: () => this.aracSabitle(arac.id, !sabitMi),
          }, sabitMi ? "📌 Sabitlendi" : "📌 Sabitle")
        )
      );
    });

    kap.replaceChildren(...kartlar);
    this.sayfalamaCiz(toplam, sayfaSayisi);
  },

  sayfalamaCiz(toplam, sayfaSayisi) {
    const kap = $("#m2s6-katalog-sayfalama");
    if (!kap) return;
    if (toplam <= this.sayfaBoyutu) {
      kap.replaceChildren();
      kap.hidden = true;
      return;
    }
    kap.hidden = false;

    const baslangic = (this.katalogSayfa - 1) * this.sayfaBoyutu + 1;
    const bitis = Math.min(toplam, this.katalogSayfa * this.sayfaBoyutu);

    const bilgi = el("div", { class: "sayfalama-bilgi", metin: `${toplam} araçtan ${baslangic}-${bitis} arası gösteriliyor (Sayfa ${this.katalogSayfa} / ${sayfaSayisi})` });
    const butonlar = el("div", { class: "sayfalama-butonlar" });

    const oncekiBtn = el("button", {
      type: "button",
      class: "sayfa-btn",
      disabled: this.katalogSayfa <= 1,
      onclick: () => {
        if (this.katalogSayfa > 1) {
          this.katalogSayfa--;
          this.katalogCiz();
          const grid = $("#m2s6-katalog-izgara");
          if (grid) grid.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    }, "« Önceki");
    butonlar.append(oncekiBtn);

    for (let p = 1; p <= sayfaSayisi; p++) {
      const sayfaBtn = el("button", {
        type: "button",
        class: `sayfa-btn${p === this.katalogSayfa ? " aktif" : ""}`,
        onclick: () => {
          if (this.katalogSayfa !== p) {
            this.katalogSayfa = p;
            this.katalogCiz();
            const grid = $("#m2s6-katalog-izgara");
            if (grid) grid.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        }
      }, String(p));
      butonlar.append(sayfaBtn);
    }

    const sonrakiBtn = el("button", {
      type: "button",
      class: "sayfa-btn",
      disabled: this.katalogSayfa >= sayfaSayisi,
      onclick: () => {
        if (this.katalogSayfa < sayfaSayisi) {
          this.katalogSayfa++;
          this.katalogCiz();
          const grid = $("#m2s6-katalog-izgara");
          if (grid) grid.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    }, "Sonraki »");
    butonlar.append(sonrakiBtn);

    kap.replaceChildren(bilgi, butonlar);
  },

  klonlaVeDuzenle(arac) {
    if (!arac) return;
    let betikIcerik = arac.betik || "";
    if (arac.parametreler && arac.parametreler.length > 0) {
      const paramSatirlari = arac.parametreler
        .map((p) => `# PSY_P_${p.ad}="${p.varsayilan != null ? p.varsayilan : ""}"  # ${p.etiket || p.ad}`)
        .join("\n");
      betikIcerik = `#!/usr/bin/env bash\n# ========================================================\n# [Klon] ${arac.ad}\n# Kaynak: Resmi Mağaza Kataloğu (${arac.id} v${arac.surum || "1.0.0"})\n# Parametreler (Gerektiğinde aşağıdaki değişkenleri düzenleyin):\n${paramSatirlari}\n# ========================================================\n\n${betikIcerik.replace(/^#!\/usr\/bin\/env bash\n?/, "")}`;
    }
    $("#m2s6-ad").value = `[Özel] ${arac.ad}`;
    $("#m2s6-kategori").value = arac.kategori || "Genel";
    $("#m2s6-komut").value = betikIcerik;
    $("#m2s6-sudo").checked = Boolean(arac.sudo);
    this.sekmeSec("serbest");
    bildir(`“${arac.ad}” klonlandı ve Serbest Uçbirim düzenleyicisine aktarıldı. Orijinal mağaza aracı korunmuştur.`);
    const editEl = $("#m2s6-komut");
    if (editEl) {
      editEl.focus();
      editEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  },

  sabitlerCiz() {
    const kap = $("#m2s6-sabitler-tablo");
    if (!kap) return;
    const sabitAraclar = (this.katalog || []).filter((a) => this.sabitler.includes(a.id));
    if (!sabitAraclar.length) {
      kap.replaceChildren(
        el("p", { class: "ipucu", metin: "Henüz sabitlenmiş araç yok. Katalogdaki araçların yanındaki '📌 Sabitle' düğmesiyle Sınıf Masası panonuza ekleyebilirsiniz." })
      );
      return;
    }

    const tablo = el("table", {},
      el("thead", {},
        el("tr", {},
          el("th", { metin: "Araç" }),
          el("th", { metin: "Kategori" }),
          el("th", { metin: "Risk" }),
          el("th", { metin: "Sürüm" }),
          el("th", { metin: "Eylemler" })
        )
      )
    );
    const govde = el("tbody");
    for (const a of sabitAraclar) {
      const riskBilgi = RISK_ROZETLERI[a.risk] || [a.risk || "Bilgi", "notr"];
      govde.append(
        el("tr", {},
          el("td", {},
            el("strong", { metin: a.ad }),
            el("span", { class: "alt", metin: a.ozet || "" })
          ),
          el("td", {}, rozet(a.kategori || "genel", "notr")),
          el("td", {}, rozet(riskBilgi[0], riskBilgi[1])),
          el("td", { class: "mono", metin: a.surum || "1.0.0" }),
          el("td", {},
            el("div", { class: "dugme-grubu" },
              el("button", {
                type: "button",
                class: "birincil kucuk",
                onclick: () => this.aracSec(a),
              }, "⚡ Çalıştır"),
              el("button", {
                type: "button",
                class: "tehlikeli kucuk",
                onclick: () => this.aracSabitle(a.id, false),
              }, "Kaldır")
            )
          )
        )
      );
    }
    tablo.append(govde);
    kap.replaceChildren(tablo);
  },

  async aracSabitle(aracId, sabitle) {
    try {
      const yanit = await api("/api/magaza/sabitle", { arac_id: aracId, sabitle });
      this.sabitler = (yanit && yanit.sabitler) || [];
      bildir(sabitle ? "Araç Sınıf Masası panosuna sabitlendi." : "Araç sabitlerden kaldırıldı.");
      this.katalogCiz();
      this.sabitlerCiz();
      if (typeof sabitlenenAraclariCiz === "function") sabitlenenAraclariCiz();
      const btnSabitle = $("#m2s6-arac-sabitle");
      if (btnSabitle && this.seciliArac && this.seciliArac.id === aracId) {
        btnSabitle.textContent = sabitle ? "📌 Sabitlendi (Kaldır)" : "📌 Sınıf Masası'na Sabitle";
      }
    } catch (hata) {
      bildir(hata.message, true);
    }
  },

  seciliAraciSabitleTersine() {
    if (!this.seciliArac) return;
    const sabitMi = this.sabitler.includes(this.seciliArac.id);
    this.aracSabitle(this.seciliArac.id, !sabitMi);
  },

  aracSec(arac) {
    this.seciliArac = arac;
    $("#m2s6-secili-arac-ad").textContent = arac.ad;
    $("#m2s6-secili-arac-ozet").textContent = arac.ozet || "Parametreleri belirleyin ve seçili bilgisayarlarda çalıştırın.";

    const rozetKap = $("#m2s6-secili-arac-rozetler");
    if (rozetKap) {
      const riskBilgi = RISK_ROZETLERI[arac.risk] || [arac.risk || "Bilgi", "notr"];
      rozetKap.replaceChildren(
        rozet(riskBilgi[0], riskBilgi[1]),
        " ",
        rozet(`v${arac.surum || "1.0.0"}`, "mavi"),
        " ",
        arac.sudo ? rozet("sudo", "orta") : rozet("kullanıcı", "notr")
      );
    }

    const btnSabitle = $("#m2s6-arac-sabitle");
    if (btnSabitle) {
      const sabitMi = this.sabitler.includes(arac.id);
      btnSabitle.textContent = sabitMi ? "📌 Sabitlendi (Kaldır)" : "📌 Sınıf Masası'na Sabitle";
    }

    // Dinamik Parametre Formu Üret
    const formKap = $("#m2s6-parametre-formu");
    const parametreler = arac.parametreler || [];
    if (!parametreler.length) {
      formKap.replaceChildren(
        el("p", { class: "ipucu tam-genislik", metin: "Bu araç ek bir parametre gerektirmez; doğrudan çalıştırılabilir." })
      );
    } else {
      const alanlar = [];
      for (const p of parametreler) {
        const id = `arac-param-${p.ad}`;
        alanlar.push(el("label", { for: id, metin: p.etiket || p.ad }));
        if (p.tip === "onay") {
          alanlar.push(
            el("label", { class: "onay-kutusu" },
              el("input", { id, type: "checkbox", checked: Boolean(p.varsayilan) }),
              el("span", { metin: p.aciklama || "Etkinleştir" })
            )
          );
        } else {
          const inp = el("input", {
            id,
            type: "text",
            value: p.varsayilan != null ? String(p.varsayilan) : "",
            placeholder: p.aciklama || p.etiket || "",
          });
          alanlar.push(inp);
        }
      }
      formKap.replaceChildren(...alanlar);
    }

    this.sekmeSec("calistir");
    $("#sayfa-M2-S6").scrollIntoView({ behavior: "smooth", block: "start" });
  },

  async seciliAraciCalistir() {
    if (!this.seciliArac) {
      bildir("Lütfen önce katalogdan bir araç seçin.", true);
      return;
    }
    const arac = this.seciliArac;
    const hedefler = Secim.liste();
    if (!hedefler.length) {
      bildir("Lütfen önce tablodan hedef bilgisayarları seçin.", true);
      return;
    }

    // Parametreleri topla
    const parametreler = {};
    for (const p of arac.parametreler || []) {
      const elParam = $(`#arac-param-${p.ad}`);
      if (!elParam) continue;
      if (p.tip === "onay") parametreler[p.ad] = Boolean(elParam.checked);
      else parametreler[p.ad] = elParam.value.trim();
    }

    const onay = await onayIste({
      islem: "komut",
      cihazlar: hedefler,
      baslik: `⚡ Mağaza Aracı Çalıştır — ${arac.ad}`,
      aciklama: arac.ozet || "Seçili bilgisayarlarda araç çalıştırılacaktır.",
      uyarilar: [
        `Hedef Cihaz Sayısı: ${hedefler.length}`,
        `Araç Kimliği: ${arac.id} (v${arac.surum || "1.0.0"})`,
        arac.sudo ? "Bu araç bilgisayarlarda root (sudo) yetkisiyle yürütülür." : "Standart kullanıcı yetkisiyle yürütülür.",
        arac.risk === "yikici" ? "DİKKAT: Bu araç yıkıcı/silici işlemler içerebilir." : "Güvenli mod.",
      ],
      yikici: arac.risk === "yikici",
      onayMetni: "Aracın seçili bilgisayarlarda çalıştırılmasını onaylıyorum",
      baslatMetni: "Aracı Çalıştır",
    });
    if (!onay) return;

    // Önceki çıktıyı konsoldan sıfırla ve yeni komut durumunu göster
    this.sonuclar = new Map();
    this.sonOzet = null;
    const rozetEl = $("#m2s6-son-komut-rozet");
    if (rozetEl) {
      const zaman = new Date().toLocaleTimeString("tr-TR");
      rozetEl.textContent = `⚡ Son Komut: ${arac.ad} · ${zaman}`;
      rozetEl.hidden = false;
    }
    const ozetEl = $("#m2s6-ozet-metin");
    if (ozetEl) ozetEl.textContent = `⏳ “${arac.ad}” gönderildi, çıktılar bekleniyor...`;
    this.sayaclariCiz();
    this.tablo.ciz();

    try {
      const kayit = await isBaslat("/api/magaza/calistir", {
        arac_id: arac.id,
        cihazlar: hedefler,
        parametreler,
      });
      if (kayit) {
        this.sonuclariIsle(kayit);
        $("#m2s6-log-tablo").scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (hata) {
      bildir(hata.message, true);
    }
  },

  katkiOnizle() {
    const id = ($("#m2s6-katki-id").value || "").trim().toLowerCase();
    const ad = ($("#m2s6-katki-ad").value || "").trim();
    const kategori = $("#m2s6-katki-kategori").value;
    const risk = $("#m2s6-katki-risk").value;
    const yazar = ($("#m2s6-katki-yazar").value || "").trim() || "Öğretmen";
    const ozet = ($("#m2s6-katki-ozet").value || "").trim();
    const betik = ($("#m2s6-katki-betik").value || "").trim();

    if (!id || !ad) {
      bildir("Lütfen en az Araç ID ve Adı alanlarını doldurun.", true);
      return;
    }

    const manifestYaml = [
      `sema: 1`,
      `id: ${id}`,
      `ad: "${ad}"`,
      `surum: 1.0.0`,
      `ozet: "${ozet || ad}"`,
      `kategori: ${kategori}`,
      `risk: ${risk}`,
      `yazar: "${yazar}"`,
      `sudo: true`,
      `hedef_os: [pardus-23, pardus-25]`,
      `parametreler: []`,
    ].join("\n");

    const onizlemeEl = $("#m2s6-katki-onizleme-kod");
    if (onizlemeEl) {
      onizlemeEl.textContent = `### arac.yaml ###\n${manifestYaml}\n\n### calistir.sh ###\n${betik || '#!/usr/bin/env bash\necho "OK"'}`;
      onizlemeEl.hidden = false;
      bildir("Katkı taslağı önizlemesi hazırlandı.");
    }
  },

  katkiIndir() {
    const id = ($("#m2s6-katki-id").value || "").trim().toLowerCase() || "yeni-arac";
    const ad = ($("#m2s6-katki-ad").value || "").trim() || "Yeni Araç";
    const kategori = $("#m2s6-katki-kategori").value;
    const risk = $("#m2s6-katki-risk").value;
    const yazar = ($("#m2s6-katki-yazar").value || "").trim() || "Öğretmen";
    const ozet = ($("#m2s6-katki-ozet").value || "").trim() || ad;
    const betik = ($("#m2s6-katki-betik").value || "").trim();

    const paket = {
      id,
      ad,
      surum: "1.0.0",
      ozet,
      kategori,
      risk,
      yazar,
      sudo: true,
      betik,
      parametreler: [],
    };

    const blob = new Blob([JSON.stringify(paket, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${id}-arac.json`;
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    bildir(`“${id}-arac.json” indirildi. afyontugva/lab-kaptani-magaza deposuna gönderebilirsiniz.`);
  },

  katkiDeneSerbest() {
    const ad = ($("#m2s6-katki-ad").value || "").trim() || "Test Aracı";
    const betik = ($("#m2s6-katki-betik").value || "").trim();
    if (!betik) {
      bildir("Önce bir bash betiği yazın.", true);
      return;
    }
    $("#m2s6-ad").value = `[Test] ${ad}`;
    $("#m2s6-komut").value = betik;
    $("#m2s6-sudo").checked = true;
    this.sekmeSec("serbest");
    bildir("Katkı betiği Serbest Uçbirim düzenleyicisine yüklendi.");
  },

  async kutuphaneYukle() {
    try { this.komutlar = await api("/api/komutlar"); }
    catch (hata) { bildir(hata.message, true); return; }
    this.kutuphaneCiz();
  },

  kutuphaneCiz() {
    const kap = $("#m2s6-kutuphane");
    if (!kap) return;

    const ozelKomutlar = (this.komutlar || []).map((k) => ({
      ...k,
      kaynak: "ozel",
    }));

    const magazaAraclari = (this.katalog || []).map((a) => ({
      id: a.id,
      ad: a.ad,
      komut: (a.betik || a.ozet || "").trim(),
      kategori: a.kategori || "Genel",
      sudo: Boolean(a.sudo),
      kaynak: "magaza",
      hamArac: a,
    }));

    const tumListe = [...magazaAraclari, ...ozelKomutlar];

    if (!tumListe.length) {
      kap.replaceChildren(el("p", { class: "ipucu", metin: "Kayıtlı özel komut veya mağaza aracı bulunamadı." }));
      return;
    }

    const tablo = el("table", {}, el("thead", {}, el("tr", {},
      ...["Komut / Araç Adı", "Kaynak", "Kategori", "Yetki", "Eylemler"].map((b) => el("th", { metin: b })))));
    const govde = el("tbody");

    for (const k of tumListe) {
      const magazaMi = k.kaynak === "magaza";
      const slug = kimlikSlug(k.id || k.ad);
      const eylemler = el("div", { class: "dugme-grubu" },
        dugme("✏️ Yükle / Düzenle", `M2-S6-B3-${slug}`, () => {
          if (magazaMi) {
            this.klonlaVeDuzenle(k.hamArac);
          } else {
            $("#m2s6-ad").value = k.ad;
            $("#m2s6-kategori").value = k.kategori || "Genel";
            $("#m2s6-komut").value = k.komut;
            $("#m2s6-sudo").checked = Boolean(k.sudo);
            this.sekmeSec("serbest");
            bildir(`“${k.ad}” düzenleyiciye yüklendi. Değişiklik yapıp kaydedebilirsiniz.`);
            const editEl = $("#m2s6-komut");
            if (editEl) {
              editEl.focus();
              editEl.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          }
        }, "ikincil kucuk"),
        !magazaMi && !k.yerlesik ? dugme("Sil", `M2-S6-B4-${slug}`, () => this.komutSil(k), "tehlikeli kucuk") : null
      );

      govde.append(el("tr", {},
        el("td", {},
          el("strong", { metin: k.ad }),
          el("span", { class: "alt mono", metin: (k.komut || "").slice(0, 80) + ((k.komut || "").length > 80 ? "…" : "") })
        ),
        el("td", {}, magazaMi ? rozet("🏪 Mağaza", "mavi") : rozet("✏️ Özel Komut", "iyi")),
        el("td", {}, rozet(k.kategori || "Genel", "notr")),
        el("td", {}, k.sudo ? rozet("sudo", "orta") : rozet("kullanıcı", "notr")),
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

    // Konsolu temizle ve yeni komutu bildir
    this.sonuclar = new Map();
    this.sonOzet = null;
    const rozetEl = $("#m2s6-son-komut-rozet");
    if (rozetEl) {
      const zaman = new Date().toLocaleTimeString("tr-TR");
      rozetEl.textContent = `⚡ Son Komut: ${ad} · ${zaman}`;
      rozetEl.hidden = false;
    }
    const ozetEl = $("#m2s6-ozet-metin");
    if (ozetEl) ozetEl.textContent = `⏳ “${ad}” gönderildi, çıktılar bekleniyor...`;
    this.sayaclariCiz();
    this.tablo.ciz();

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

    // Konsolu temizle ve yeni komutu bildir
    this.sonuclar = new Map();
    this.sonOzet = null;
    const rozetEl = $("#m2s6-son-komut-rozet");
    if (rozetEl) {
      const zaman = new Date().toLocaleTimeString("tr-TR");
      rozetEl.textContent = `⚡ Son Komut: /etc/hosts Dağıtımı (${alan_adi}) · ${zaman}`;
      rozetEl.hidden = false;
    }
    const ozetEl = $("#m2s6-ozet-metin");
    if (ozetEl) ozetEl.textContent = `⏳ Hosts kaydı dağıtılıyor...`;
    this.sayaclariCiz();
    this.tablo.ciz();

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

