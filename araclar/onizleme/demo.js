/* arayuz-onizleme.html için DEMO arka ucu.
 *
 * Gerçek arayüz kodu (ortak.js, envanter.js, islemler.js, odevler.js, kayitlar.js)
 * değiştirilmeden çalışır; yalnız fetch() burada ÖRNEK VERİLERLE yanıtlanır.
 * Hiçbir ağ bağlantısı, SSH, paket kurulumu, hesap silme veya dosya temizliği
 * yapılmaz; parola veya özel anahtar istenmez. İndirmeler yalnız bildirimle gösterilir.
 * Uygunluk kuralları uygulama/secim.py ile aynıdır (testler kodları denetler).
 */
"use strict";

(() => {
  const SIMDI = () => new Date().toISOString();
  const DK = (n) => new Date(Date.now() - n * 60000).toISOString();
  const YONETIM = ["pardus", "hp"];
  let sayac = 1000;
  const yeniId = (on = "d") => `${on}${(sayac++).toString(16)}`;

  /* ================================================================ örnek envanter */

  function cihaz(no, ad, lab, ek = {}) {
    const ip = lab === "Bilişim-2" ? `192.168.20.${100 + no}` : `192.168.10.${100 + no}`;
    return {
      id: `c${lab === "Bilişim-2" ? 2 : 1}${String(no).padStart(2, "0")}`, ip, ssh_port: 22,
      hostname: ad.toLowerCase(), etiket: ad, grup: lab, pardus_surum: "Pardus 23.5", masaustu: "GNOME",
      giris_yoneticisi: "gdm3", baglanti_hesabi: "pardus", yonetim_hesaplari: ["pardus"], profil_var: 1,
      sudo_durumu: "parolasiz", anahtar_durumu: "ok", parmak_izi: `SHA256:ornek${no}${lab.length}Qx7Lm2PzR8wT4nV6yK1bH3jD5fG9cS0aE`,
      parmak_izi_onay: 1, yinelenen_kimlik: 0, durum: "Yönetilebilir", son_kontrol: DK(12 + no),
      korunan: 0, korunan_neden: null, ogrenci_oturumu: 0, gizleme_durumu: "gizli", otomatik_giris: "ogrenci",
      gorunum_durumu: "uygulandi", disk_bos: (38 + (no * 7) % 60) * 1073741824, ogrenci_sudo: 0,
      erisim: 1, erisim_zamani: DK(1), ...ek,
    };
  }

  const cihazlar = [];
  for (let i = 1; i <= 24; i += 1) cihazlar.push(cihaz(i, `LAB${String(i).padStart(2, "0")}`, "Bilişim-1"));
  const bul = (ad) => cihazlar.find((c) => c.etiket === ad);
  Object.assign(bul("LAB03"), { ogrenci_oturumu: 1 });
  Object.assign(bul("LAB07"), { ogrenci_oturumu: 1 });
  Object.assign(bul("LAB12"), { ogrenci_oturumu: 1 });
  Object.assign(bul("LAB05"), { erisim: 0, durum: "SSH erişilemiyor", son_kontrol: DK(300) });
  Object.assign(bul("LAB09"), { yonetim_hesaplari: ["pardus", "hp"] });
  Object.assign(bul("LAB11"), { gizleme_durumu: "gorunur", otomatik_giris: "kapali", gorunum_durumu: "yok" });
  Object.assign(bul("LAB14"), { baglanti_hesabi: "hp", yonetim_hesaplari: ["hp"] });
  Object.assign(bul("LAB21"), { anahtar_durumu: "gerekli", sudo_durumu: null, parmak_izi_onay: 0, durum: "Kimlik onayı gerekli",
    yonetim_hesaplari: null, gizleme_durumu: null, otomatik_giris: null, gorunum_durumu: null, ogrenci_oturumu: null, son_kontrol: null });
  Object.assign(bul("LAB22"), { anahtar_durumu: "gerekli", sudo_durumu: null, durum: "Hazırlık gerekli", baglanti_hesabi: null,
    yonetim_hesaplari: null, gizleme_durumu: null, otomatik_giris: null, gorunum_durumu: null, ogrenci_oturumu: null });
  Object.assign(bul("LAB23"), { sudo_durumu: "parola_gerekli", durum: "Parolasız sudo gerekli", gizleme_durumu: null });
  Object.assign(bul("LAB24"), { profil_var: 0, otomatik_giris: "kapali" });
  cihazlar.push(cihaz(25, "ETAP-TAHTA", "Bilişim-1", { korunan: 1, korunan_neden: "Otomatik: ETAP paketi kurulu: etap-pardus-tahta",
    masaustu: "GNOME", pardus_surum: "Pardus 21 ETAP" }));
  for (let i = 1; i <= 8; i += 1) cihazlar.push(cihaz(i, `B2-${String(i).padStart(2, "0")}`, "Bilişim-2"));
  Object.assign(bul("B2-03"), { masaustu: "XFCE", giris_yoneticisi: "lightdm", gizleme_durumu: "desteklenmiyor",
    otomatik_giris: "desteklenmiyor", gorunum_durumu: "yok" });
  Object.assign(bul("B2-06"), { yonetim_hesaplari: ["pardus", "hp"], ogrenci_oturumu: 1 });
  Object.assign(bul("B2-08"), { erisim: 0, durum: "SSH erişilemiyor", son_kontrol: DK(2000) });

  /* ---- Veyon: hedeften okunmuş TAM paket sürümleri (örnek) ---- */
  const VEYON_ESKI = "4.7.5+repack1-1";            // Pardus'un parçalı Debian paketi
  const VEYON_YENI = "4.11.0.0-debian.12";         // öğretmenin yüklediği tek paket
  const vyap = (eslesme, yontem, calisiyor, parcali = false) => ({ paket: parcali ? "veyon-service" : "veyon", parcali,
    servis: { etkin: calisiyor, calisiyor, port: calisiyor }, yontem, anahtarlar: eslesme === "eslesiyor" ? { teacher: "37b08aea" } : {},
    anahtar_adi: "teacher", eslesme: eslesme || "yok" });
  for (const c of cihazlar) {
    Object.assign(c, { veyon_durumu: "kurulu", veyon_surum: VEYON_ESKI, veyon_kontrol: c.son_kontrol || DK(30),
      veyon_yapilandirma: vyap("yok", null, false, true) });
  }
  for (const ad of ["LAB01", "LAB02", "LAB03", "LAB04"]) Object.assign(bul(ad), { veyon_surum: VEYON_YENI, veyon_yapilandirma: vyap("eslesiyor", 1, true) });
  Object.assign(bul("LAB06"), { veyon_durumu: "kurulu_degil", veyon_surum: null, veyon_yapilandirma: null });
  Object.assign(bul("LAB05"), { veyon_kontrol: DK(2900) });   // erişilemiyor: son bilinen sürüm "eski bilgi"
  Object.assign(bul("LAB10"), { veyon_durumu: "hatali", veyon_surum: VEYON_YENI,
    veyon_yapilandirma: { ...vyap("yok", 0, false), neden: "dpkg durumu: veyon=iU" } });
  Object.assign(bul("LAB15"), { veyon_surum: "4.12.0.0-debian.12", veyon_yapilandirma: vyap("farkli", 1, true) });
  for (const ad of ["LAB21", "LAB22"]) Object.assign(bul(ad), { veyon_durumu: null, veyon_surum: null, veyon_kontrol: null, veyon_yapilandirma: null });
  for (const ad of ["B2-01", "B2-02", "B2-03"]) Object.assign(bul(ad), { veyon_surum: "4.10.4.0-debian.12", veyon_yapilandirma: vyap("eslesiyor", 1, true) });
  Object.assign(bul("B2-04"), { veyon_durumu: "kurulu_degil", veyon_surum: null, veyon_yapilandirma: null });
  Object.assign(bul("B2-08"), { veyon_durumu: null, veyon_surum: null, veyon_kontrol: null, veyon_yapilandirma: null });
  Object.assign(bul("ETAP-TAHTA"), { veyon_durumu: "kurulu_degil", veyon_surum: null, veyon_yapilandirma: null });

  /* ---- güç: uyku ayarı ve zamanlı kapatma planları (örnek) ---- */
  const GUNSONU = { id: "a1b2c3", etiket: "Pzt–Cum 17:30 (her hafta)", tur: "surekli", uyari_dk: 5, sonraki: "Pzt 2026-10-05 17:30:00 +03", etkin: true, aciklama: "Gün sonu" };
  for (const c of cihazlar) {
    const lab1 = c.grup === "Bilişim-1";
    c.guc_durumu = { uyku_kapali: lab1, ekran_dk: lab1 ? 10 : null, bekleyen: false, planlar: lab1 ? [{ ...GUNSONU }] : [], zaman: c.son_kontrol };
  }
  for (const ad of ["LAB21", "LAB22", "LAB23", "B2-08"]) Object.assign(bul(ad), { guc_durumu: null });
  Object.assign(bul("LAB12"), { guc_durumu: { uyku_kapali: true, ekran_dk: 10, bekleyen: true, bekleyen_saat: "17:35", planlar: [{ ...GUNSONU }], zaman: DK(1) } });
  Object.assign(bul("B2-02"), { guc_durumu: { uyku_kapali: false, ekran_dk: null, bekleyen: false,
    planlar: [{ id: "d4e5f6", etiket: "05.10.2026 12:00 (bir kez)", tur: "tek", uyari_dk: 2, sonraki: "Pzt 2026-10-05 12:00:00 +03", etkin: true, aciklama: "Sınav günü" }], zaman: DK(20) } });

  /* dpkg sürüm karşılaştırması (uygulama/surum.py ile aynı kural) */
  function debKarsilastir(a, b) {
    const parca = (s) => { let e = 0; if (s.includes(":")) { const [x, y] = s.split(/:(.*)/s); e = Number(x) || 0; s = y; }
      const i = s.lastIndexOf("-"); return [e, i >= 0 ? s.slice(0, i) : s, i >= 0 ? s.slice(i + 1) : ""]; };
    const sira = (c) => (!c || /\d/.test(c) ? 0 : /[A-Za-z]/.test(c) ? c.charCodeAt(0) : c === "~" ? -1 : c.charCodeAt(0) + 256);
    const bolum = (a1, b1) => {
      let i = 0, j = 0;
      while (i < a1.length || j < b1.length) {
        while ((i < a1.length && !/\d/.test(a1[i])) || (j < b1.length && !/\d/.test(b1[j]))) {
          const ca = i < a1.length && !/\d/.test(a1[i]) ? sira(a1[i]) : 0;
          const cb = j < b1.length && !/\d/.test(b1[j]) ? sira(b1[j]) : 0;
          if (ca !== cb) return ca < cb ? -1 : 1;
          i += 1; j += 1;
        }
        let sa = "", sb = "";
        while (i < a1.length && /\d/.test(a1[i])) sa += a1[i++];
        while (j < b1.length && /\d/.test(b1[j])) sb += b1[j++];
        const na = Number(sa || 0), nb = Number(sb || 0);
        if (na !== nb) return na < nb ? -1 : 1;
      }
      return 0;
    };
    const [ea, ua, ra] = parca(a), [eb, ub, rb] = parca(b);
    if (ea !== eb) return ea < eb ? -1 : 1;
    return bolum(ua, ub) || bolum(ra, rb);
  }

  const bulunanlar = [
    { ip: "192.168.10.130", ssh_port: 22, parmak_izi: "SHA256:yeniA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUvWxYz", zaman: DK(3) },
    { ip: "192.168.10.131", ssh_port: 22, parmak_izi: "SHA256:yeniA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUvWxYz", zaman: DK(3) },
    { ip: "192.168.10.132", ssh_port: 22, parmak_izi: "SHA256:farkliZz9Yy8Xx7Ww6Vv5Uu4Tt3Ss2Rr1Qq0Pp", zaman: DK(3) },
  ];

  /* ---- uygunluk: uygulama/secim.py ile aynı kurallar ---- */
  const OGRETMEN = new Set(["192.168.10.2"]);
  function uygunluk(c, islem) {
    if (islem === "cikar") return null;
    if (c.korunan) return "Korunan cihaz (EBA/ETAP) — kapsam dışı";
    if (OGRETMEN.has(c.ip)) return "Öğretmen bilgisayarının kendisi — kapsam dışı";
    if (islem === "durum") return null;
    if (islem === "hazirlik") {
      if (!c.parmak_izi) return "Sunucu kimliği okunmadı (M1-S2-B1)";
      if (!c.parmak_izi_onay) return "Sunucu kimliği onaylanmadı (M1-S2-B2)";
      return null;
    }
    if (c.anahtar_durumu !== "ok") return "SSH anahtarı kurulu değil (M1-S2)";
    if (islem === "veyon_oku") return null;
    if (c.sudo_durumu !== "parolasiz") return "Parolasız sudo hazır değil (M1-S2)";
    if (islem === "tekillestirme") {
      if (c.yonetim_hesaplari == null) return "Yönetim hesapları bilinmiyor — önce durumu kontrol edin";
      if (c.yonetim_hesaplari.length < 2) return "Tek yönetim hesabı var; tekilleştirme gerekmez";
    }
    if ((islem === "temizlik" || islem === "oturum" || islem === "sinif") && c.profil_var === 0) return "'ogrenci' hesabı yok (M1-S2)";
    if (islem === "gorunum" && c.masaustu && !c.masaustu.startsWith("GNOME")) return "Masaüstü GNOME değil — XFCE için ayrı geçiş planı ve onay gerekir";
    return null;
  }
  function gereken(c) {
    if (c.korunan) return { metin: "Korunan cihaz — işlem yapılmaz", sayfa: null };
    if (!c.parmak_izi) return { metin: "Sunucu kimliğini okuyun", sayfa: "M1-S2" };
    if (!c.parmak_izi_onay) return { metin: "Sunucu kimliğini onaylayın", sayfa: "M1-S2" };
    if (c.anahtar_durumu !== "ok") return { metin: "SSH anahtarını kurun", sayfa: "M1-S2" };
    if (c.sudo_durumu !== "parolasiz") return { metin: "Parolasız sudo hazırlayın", sayfa: "M1-S2" };
    if (c.profil_var === 0) return { metin: "'ogrenci' hesabı oluşturun", sayfa: "M1-S2" };
    if ((c.yonetim_hesaplari || []).length > 1) return { metin: "hp/pardus hesaplarını tekilleştirin", sayfa: "M1-S2" };
    if (c.masaustu && !c.masaustu.startsWith("GNOME")) return { metin: "GNOME geçişi ayrı planlanmalı", sayfa: null };
    if (c.gizleme_durumu === "gorunur") return { metin: "Yönetim hesabını giriş ekranında gizleyin", sayfa: "M2-S3" };
    if (!c.son_kontrol) return { metin: "Durumu kontrol edin", sayfa: "M1-S1" };
    return null;
  }
  const ISLEMLER = { durum: "Durum kontrolü", hazirlik: "SSH ve hesap hazırlığı", tekillestirme: "Hesap tekilleştirme",
    temizlik: "Profil temizliği", oturum: "Öğrenci oturumunu kapatma", paket: "Paket kurulumu",
    veyon: "Veyon kurulum ve yapılandırma", veyon_oku: "Veyon sürümü ve bağlantı denetimi",
    gorunum: "Görünüm ve giriş", guc: "Güç işlemleri", sinif: "Sınıf hızlı işlemleri",
    komut: "SSH bash komutu çalıştırma", cikar: "Envanterden çıkarma" };
  /* uygulama/secim.py veyon_gorunumu ile aynı kural */
  function veyonGorunumu(c) {
    const d = c.veyon_durumu, z = c.veyon_kontrol;
    const erisilemiyor = c.erisim === 0 && (!z || (c.erisim_zamani || "") > z);
    const gosterim = erisilemiyor ? "erisilemiyor" : !d ? "kontrol_edilmedi" : d;
    const hedef = (veyonPaketleri.find((p) => p.sha256 === veyonSecili) || {}).surum;
    let k = "bilinmiyor";
    if (gosterim === "kurulu") { const f = hedef ? debKarsilastir(c.veyon_surum, hedef) : null; k = f === null ? "kurulu" : f < 0 ? "eski" : f === 0 ? "ayni" : "yeni"; }
    else if (gosterim === "kurulu_degil") k = "kurulu_degil";
    return { durum: gosterim, surum: c.veyon_surum, son_bilinen: d, eski_bilgi: erisilemiyor && Boolean(d), zaman: z,
      karsilastirma: k, yapilandirma: c.veyon_yapilandirma };
  }
  const gorunumu = (c) => ({ ...c, ad: c.etiket || c.hostname || c.ip, laboratuvar: c.grup || "Laboratuvar",
    gereken: gereken(c), ogretmen_pc: false, veyon: veyonGorunumu(c),
    uygunluk: Object.fromEntries(Object.keys(ISLEMLER).map((i) => [i, uygunluk(c, i)])) });
  const cihazAl = (id) => cihazlar.find((c) => c.id === id);
  const adi = (c) => c.etiket || c.hostname || c.ip;

  /* ================================================================ paketler, işler, ödevler */

  const paketler = [{
    sha256: "4f1c9e0b7a2d5e8f3c6b9a1d4e7f0a3b6c9d2e5f8a1b4c7d0e3f6a9b2c5d8e1f", dosya_adi: "okul-sinav-araci_2.1_amd64.deb",
    paket: "okul-sinav-araci", surum: "2.1", mimari: "amd64", boyut: 18874368, kurulu_kb: 61440, zaman: DK(90),
    kontrol: { Package: "okul-sinav-araci", Version: "2.1", Architecture: "amd64", Depends: "python3 (>= 3.9), python3-gi, libqrencode4",
      Conflicts: "eski-sinav-araci", Description: "Örnek okul sınav aracı (DEMO paketi)\nBu paket yalnız önizleme verisidir." },
  }];

  const veyonPaketleri = [{
    sha256: "4583472ff29fbb441e4795e1e64ae549b97ecb415b2a3a328f737e146f7e9d6c", dosya_adi: "veyon_4.11.0.0-debian.12_amd64.deb",
    paket: "veyon", surum: "4.11.0.0-debian.12", mimari: "amd64", boyut: 2004828, kurulu_kb: 9151, zaman: DK(45), tur: "veyon",
    kontrol: { Package: "veyon", Version: "4.11.0.0-debian.12", Architecture: "amd64", Provides: "veyon-configurator, veyon-master, veyon-plugins, veyon-service",
      Conflicts: "veyon-configurator, veyon-master, veyon-plugins, veyon-service", Description: "Cross-platform computer control and classroom management" },
  }];
  let veyonSecili = veyonPaketleri[0].sha256;
  let veyonAnahtar = { ad: "teacher", dosya_adi: "teacher_public_key.pem", parmak_izi: "9c1f0b7e2a4d6c8e0f1a3b5c7d9e1f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e",
    cift_kimligi: "37b08aea", bit: 4096, zaman: DK(40), onceki: null };

  const isler = new Map();
  const gecmis = [];
  function gecmisIs(tip, durum, dakika, hedefler) {
    const id = yeniId("i");
    const k = { id, tip, durum, baslangic: DK(dakika), bitis: DK(dakika - 1), ozet: null, parametreler: { hedefler: [] },
      hedefler: hedefler.map(([ad, d, asama, mesaj]) => { const c = bul(ad); return { is_id: id, hedef: c.ip, durum: d, asama, mesaj: `${ad} — ${mesaj}`, zaman: DK(dakika - 1), veri: { cihaz_id: c.id, ad } }; }) };
    k.parametreler.hedefler = k.hedefler.map((h) => ({ id: h.veri.cihaz_id, ad: h.veri.ad, ip: h.hedef }));
    isler.set(id, k);
    gecmis.push(k);
  }
  gecmisIs("paket_kur", "tamamlandi", 80, [["LAB01", "basarili", "tamam", "kuruldu ve doğrulandı: okul-sinav-araci 2.1"],
    ["LAB05", "basarisiz", "baglanti", "bağlanılamadı: [Errno 113] No route to host"],
    ["B2-05", "basarisiz", "denetim", "kurulmadı: kurulum şu paketleri KALDIRACAK: eski-sinav-araci — izin verilmez"]]);
  gecmisIs("temizlik", "tamamlandi", 240, [["LAB02", "basarili", "tamam", "Masaüstü: 14 öğe taşındı; İndirilenler: 3 öğe taşındı | karantinaya alındı"],
    ["LAB23", "basarisiz", "sudo", "Parolasız sudo hazır değil — bu bilgisayarı M1-S2 “SSH ve Hesap Hazırlığı” sayfasından hazırlayın"]]);
  gecmisIs("hazirlik", "tamamlandi", 600, [["LAB14", "basarili", "tamam", "hazır: hp hesabı, anahtar ve parolasız sudo bağımsız oturumda doğrulandı"],
    ["LAB22", "basarisiz", "yetki", "Yetkili hesap hazırlığı gerekiyor: sudo yapabilen pardus/hp hesabıyla girilemedi (pardus: giriş yapılamadı (hesap yok veya parola yanlış))"]]);

  const odev = {
    siniflar: [{ id: "s9a", ad: "9-A", ogrenci_sayisi: 6 }, { id: "s10b", ad: "10-B", ogrenci_sayisi: 4 }],
    ogrenciler: {
      s9a: [["101", "Ayşe Yılmaz"], ["102", "Mehmet Demir"], ["103", "Zeynep Kaya"], ["104", "Emre Şahin"], ["105", "Elif Çelik"], ["106", "Can Aydın"]]
        .map(([n, a], i) => ({ id: `o${n}`, numara: n, ad_soyad: a, kodu_var: i < 5, kod_zamani: i < 5 ? DK(3000) : null })),
      s10b: [["201", "Deniz Arslan"], ["202", "Selin Koç"], ["203", "Burak Öztürk"], ["204", "İrem Doğan"]]
        .map(([n, a]) => ({ id: `o${n}`, numara: n, ad_soyad: a, kodu_var: true, kod_zamani: DK(5000) })),
    },
    odevler: [
      { id: "a1f00c", baslik: "Scratch: Labirent Oyunu", sinif_id: "s9a", sinif: "9-A", durum: "acik", durum_adi: "Teslimler açık",
        son_tarih: "30.09.2026 17:00", son_tarih_giris: "2026-09-30T17:00", gec_teslim: true, yonerge: "Projeyi .sb3 olarak yükleyin.",
        turler: ["belge", "gorsel", "arsiv", "kod"], ek_uzantilar: ["sb3"], en_fazla_dosya: 20, en_fazla_mb: 100, klasor_izni: true,
        teslim_eden: 4, ogrenci_sayisi: 6 },
      { id: "b2e11d", baslik: "Algoritma Ödevi", sinif_id: "s10b", sinif: "10-B", durum: "arsiv", durum_adi: "Arşiv",
        son_tarih: null, son_tarih_giris: "", gec_teslim: false, yonerge: "", turler: ["belge"], ek_uzantilar: [],
        en_fazla_dosya: 5, en_fazla_mb: 20, klasor_izni: false, teslim_eden: 4, ogrenci_sayisi: 4 },
    ],
  };
  const teslimDurum = { 101: "alindi", 102: "gec", 103: "alindi", 104: "etmedi", 105: "yukleniyor", 106: "hata" };

  /* ================================================================ iş benzetimi */

  function isBaslat(tip, cihazIdler, parametreler, sonucFn, bitince) {
    const id = yeniId("i");
    const hedefler = cihazIdler.map((cid) => cihazAl(cid)).filter(Boolean);
    const k = { id, tip, durum: "calisiyor", baslangic: SIMDI(), bitis: null, ozet: null,
      parametreler: { ...parametreler, hedefler: hedefler.map((c) => ({ id: c.id, ad: adi(c), ip: c.ip })) },
      hedefler: hedefler.map((c) => ({ is_id: id, hedef: c.ip, durum: "bekliyor", asama: null, mesaj: null, zaman: SIMDI(),
        veri: { cihaz_id: c.id, ad: adi(c) } })),
      _bas: Date.now(), _sonuc: sonucFn, _bitince: bitince, _cihazlar: hedefler };
    isler.set(id, k);
    gecmis.push(k);
    return { is_id: id, hedef_sayisi: hedefler.length };
  }

  function isIlerlet(k) {
    if (k.durum !== "calisiyor") return;
    const gecen = Date.now() - k._bas;
    k.hedefler.forEach((h, i) => {
      const c = k._cihazlar[i];
      const bitis = 700 + i * 260;
      if (h.durum === "bekliyor" && gecen > bitis - 600) { h.durum = "calisiyor"; h.mesaj = `${adi(c)} — bağlanılıyor`; }
      if (h.durum === "calisiyor" && gecen > bitis) {
        const neden = k._uygunlukIslemi ? uygunluk(c, k._uygunlukIslemi) : null;
        let r;
        if (neden) r = { durum: "atlandi", asama: "kapsam", mesaj: neden };
        else if (c.erisim === 0 && k.tip !== "kimlik_oku") r = { durum: "basarisiz", asama: "baglanti", mesaj: "bağlanılamadı: [Errno 113] No route to host (DEMO)" };
        else r = k._sonuc(c, i);
        h.durum = r.durum; h.asama = r.asama || "tamam"; h.mesaj = `${adi(c)} — ${r.mesaj}`; h.zaman = SIMDI();
        h.veri = { cihaz_id: c.id, ad: adi(c), ...(r.veri || {}) };
        if (r.durum === "basarili" && r.etki) r.etki(c);
      }
    });
    if (k.hedefler.every((h) => !["bekliyor", "calisiyor"].includes(h.durum))) {
      k.durum = k._iptal ? "iptal" : "tamamlandi";
      k.bitis = SIMDI();
      if (k._bitince) k._bitince(k);
    }
  }

  const disa = (k) => { const { _bas, _sonuc, _bitince, _cihazlar, ...geri } = k; return JSON.parse(JSON.stringify(geri)); };

  /* ---- ölçüm verisi (her bilgisayar için tutarlı, uydurma ama anlamlı) ---- */
  const MB = 1048576;
  function temizlikOlcum(c, alanlar) {
    const n = Number(c.id.slice(-2));
    const al = {};
    let top = { adet: 0, bayt: 0, ayrilmis: 0, serbest_kalabilir: 0 };
    const boyutlar = { masaustu: 40, indirilenler: 220, cop: 15, belgeler: 90, resimler: 60, muzik: 0, videolar: 300, tarayici: 180, son_dosyalar: 2 };
    for (const a of alanlar) {
      const b = Math.round((boyutlar[a] || 10) * MB * (0.3 + ((n * 13 + a.length * 7) % 10) / 10));
      const o = { adet: 3 + ((n + a.length) % 40), bayt: b, ayrilmis: Math.round(b * 0.93), serbest_kalabilir: Math.round(b * 0.9) };
      if (a === "tarayici" && c.ogrenci_oturumu) { al[a] = { atlandi: "tarayıcı açık (firefox-esr)" }; continue; }
      al[a] = o;
      for (const x of Object.keys(top)) top[x] += o[x];
    }
    const ayri = n % 6 === 4;  // bu bilgisayarlarda /home ayrı bölüm (DEMO)
    const budanacak = n % 3 === 0 ? Math.round(150 * MB * (1 + (n % 4))) : 0;
    return { hesap: "ogrenci", alanlar: al, olcum: { kaldirilacak: top, ayni_dosya_sistemi: !ayri,
      budanacak_kayit: budanacak ? 1 : 0, budanacak_bayt: budanacak,
      tahmini_acilacak: budanacak + (ayri ? top.serbest_kalabilir : 0), ev_bos: c.disk_bos } };
  }
  function sifirlamaOlcum(c, kapsam) {
    const n = Number(c.id.slice(-2));
    const ev = (900 + (n * 137) % 2400) * MB;
    const sil = kapsam === "tam" ? ev : Math.round(ev * (0.25 + (n % 5) / 20));
    const bos = n === 18 ? 300 * MB : c.disk_bos;
    return { kapsam, ev: { adet: 4200, bayt: ev, ayrilmis: Math.round(ev * 0.95), serbest_kalabilir: Math.round(ev * 0.95) },
      silinecek: { adet: kapsam === "tam" ? 4199 : 1700, bayt: sil, ayrilmis: Math.round(sil * 0.95), serbest_kalabilir: Math.round(sil * 0.94) },
      silinecek_adlar: [], gorunur_klasorler: ["Belgeler", "Masaüstü", "İndirilenler"], tarayici_verisi: [".mozilla"],
      yedek: { ust_sinir: ev, gerekli_bos: ev + 200 * MB, bos, yeterli: bos >= ev + 200 * MB,
        budanacak_kayit: n % 2, budanacak_bayt: n % 2 ? Math.round(ev * 0.4) : 0 },
      ayni_dosya_sistemi: n % 6 !== 4, ev_bos: bos };
  }

  /* ================================================================ istek yönlendirme */

  const bekle = (ms) => new Promise((r) => setTimeout(r, ms));
  class Hata extends Error { constructor(kod, mesaj) { super(mesaj); this.kod = kod; } }
  const yanit = (veri, durum = 200) => new Response(typeof veri === "string" ? veri : JSON.stringify(veri),
    { status: durum, headers: { "Content-Type": "application/json" } });

  function ozet(ids, islem) {
    const hedefler = [], erisilemeyen = [], kapsam_disi = [];
    for (const id of [...new Set(ids)]) {
      const c = cihazAl(id);
      if (!c) { kapsam_disi.push({ id, ad: id, neden: "Envanterde yok" }); continue; }
      const neden = uygunluk(c, islem);
      const k = { id: c.id, ad: adi(c), ip: c.ip, laboratuvar: c.grup };
      if (neden) kapsam_disi.push({ ...k, neden });
      else if (c.erisim === 0 && islem !== "cikar") erisilemeyen.push({ ...k, neden: "Şu an erişilemiyor (SSH portu kapalı)" });
      else hedefler.push(k);
    }
    return { islem, islem_adi: ISLEMLER[islem], secili: new Set(ids).size, hedefler, erisilemeyen, kapsam_disi,
      korunan: kapsam_disi.filter((d) => d.neden.startsWith("Korunan")).length };
  }

  const ALANLAR = [["masaustu", "Masaüstü", "Masaüstü"], ["indirilenler", "İndirilenler", "İndirilenler"], ["cop", "Çöp kutusu", "Çöp"],
    ["belgeler", "Belgeler", "Belgeler"], ["resimler", "Resimler", "Resimler"], ["muzik", "Müzik", "Müzik"], ["videolar", "Videolar", "Videolar"],
    ["tarayici", "Tarayıcı geçmişi ve çerezleri", "Tarayıcı"], ["son_dosyalar", "Son açılan dosyalar listesi", "Son dosyalar"]]
    .map(([ad, etiket, kisa]) => ({ ad, etiket, kisa }));
  const ALAN_ADI = Object.fromEntries(ALANLAR.map((a) => [a.ad, a.kisa]));
  let saklama = 5;

  const yollar = [];
  const yol = (metod, desen, islev) => yollar.push({ metod, desen: new RegExp(`^${desen}$`), islev });

  const VARSAYILAN_OKUL_LOGO =
    "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2064%2064%22%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2232%22%20r%3D%2230%22%20fill%3D%22%231B5FC1%22%20stroke%3D%22%2393C5FD%22%20stroke-width%3D%222.5%22%2F%3E%3Cpath%20d%3D%22M32%2012L14%2021v12c0%2011.5%207.7%2021.8%2018%2025%2010.3-3.2%2018-13.5%2018-25V21L32%2012z%22%20fill%3D%22%230F2A56%22%2F%3E%3Cpath%20d%3D%22M22%2036c4-2%208-2%2010%200%202-2%206-2%2010%200V24c-4-2-8-2-10%200-2-2-6-2-10%200v12z%22%20fill%3D%22%23FFFFFF%22%2F%3E%3Ccircle%20cx%3D%2232%22%20cy%3D%2219%22%20r%3D%222.5%22%20fill%3D%22%23FBBF24%22%2F%3E%3C%2Fsvg%3E";

  let demoOkul = {
    ad: "Şehit Cengiz Polat Fen ve Teknoloji Anadolu İmam Hatip Lisesi",
    alt_baslik: "Bilişim Teknolojileri Laboratuvarı",
    logo_b64: VARSAYILAN_OKUL_LOGO,
  };
  let demoOgretmenler = [
    { id: "ogr1", kullanici_adi: "admin", ad_soyad: "Mukaddes ALAT", rol: "admin", brans: "Bilişim Teknolojileri", yetkiler: ["paket_gorunum", "komut_gonder"], son_giris: SIMDI() },
    { id: "ogr2", kullanici_adi: "zeynep.demir", ad_soyad: "Zeynep Demir", rol: "standart", brans: "Web Programcılığı", yetkiler: [], son_giris: DK(120) },
    { id: "ogr3", kullanici_adi: "ali.yilmaz", ad_soyad: "Ali Yılmaz", rol: "standart", brans: "Ağ Sistemleri", yetkiler: ["komut_gonder"], son_giris: DK(1440) },
  ];
  let demoKomutlar = [
    { id: "k_hosts", ad: "Hosts Dosyasına Adres Ekle (abc.local -> 192.168.23.142)", kategori: "Ağ / DNS",
      komut: "grep -qE '(^|[[:space:]])abc\\.local([[:space:]]|$)' /etc/hosts && sed -i -E 's/^[0-9.]+[[:space:]]+.*abc\\.local.*/192.168.23.142\\tabc.local/' /etc/hosts || printf '\\n192.168.23.142\\tabc.local\\n' >> /etc/hosts && grep 'abc.local' /etc/hosts",
      sudo: true, yerlesik: true },
    { id: "k_userdel", ad: "abc Kullanıcısını ve Ev Dizinini Sil (userdel)", kategori: "Kullanıcı",
      komut: "id -u abc >/dev/null 2>&1 && userdel -r abc && echo 'abc kullanicisi ve ev dizini silindi.' || echo 'abc kullanicisi bulunamadi.'",
      sudo: true, yerlesik: true },
    { id: "k_disk_ram", ad: "Disk ve Bellek Durumunu Raporla", kategori: "Sistem",
      komut: "df -h / | tail -n 1 && free -m | awk 'NR==2{printf \"RAM: %s/%s MB\\n\", $3,$2}'",
      sudo: false, yerlesik: true },
    { id: "k_apt_fix", ad: "Yarım Kalan Paket Kurulumlarını Onar (dpkg --configure -a)", kategori: "Paket",
      komut: "DEBIAN_FRONTEND=noninteractive dpkg --configure -a && apt-get -f install -y",
      sudo: true, yerlesik: true },
  ];

  yol("GET", "/api/oturum", () => ({ kurulum_tamam: true, girisli: true, csrf: "demo", versiyon: "0.6.0 · DEMO",
    okul: demoOkul, ogretmen: demoOgretmenler[0], ogretmenler_ozet: demoOgretmenler }));
  yol("POST", "/api/cikis", () => { throw new Hata(409, "DEMO: önizlemede çıkış yapılmaz."); });
  yol("GET", "/api/cihazlar", () => cihazlar.map(gorunumu));
  yol("POST", "/api/secim/ozet", (g) => ozet(g.cihazlar, g.islem));
  yol("POST", "/api/erisim", (g) => Object.fromEntries(g.cihazlar.map((id) => { const c = cihazAl(id); c.erisim_zamani = SIMDI(); return [id, c.erisim === 1]; })));
  yol("POST", "/api/cihazlar", (g) => {
    if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(g.ip || "")) throw new Hata(422, "Geçersiz IP adresi");
    if (cihazlar.some((c) => c.ip === g.ip)) throw new Hata(422, `${g.ip}:22 zaten envanterde`);
    const c = { ...cihaz(90 + cihazlar.length, g.etiket || g.ip, g.grup || "Laboratuvar"), ip: g.ip, etiket: g.etiket || null,
      anahtar_durumu: "gerekli", sudo_durumu: null, parmak_izi: null, parmak_izi_onay: 0, durum: "Kimlik okunmadı",
      baglanti_hesabi: g.baglanti_hesabi || null, yonetim_hesaplari: null, korunan: g.korunan ? 1 : 0, son_kontrol: null,
      gizleme_durumu: null, otomatik_giris: null, gorunum_durumu: null, ogrenci_oturumu: null, pardus_surum: null, masaustu: null,
      giris_yoneticisi: null, erisim: null };
    c.id = yeniId("c");
    cihazlar.push(c);
    return { id: c.id };
  });
  yol("PATCH", "/api/cihazlar/([\\w-]+)", (g, [id]) => {
    const c = cihazAl(id);
    const degisti = "baglanti_hesabi" in g && g.baglanti_hesabi !== c.baglanti_hesabi;
    if ("etiket" in g) c.etiket = g.etiket;
    if ("grup" in g) c.grup = g.grup || "Laboratuvar";
    if ("korunan" in g) { c.korunan = g.korunan ? 1 : 0; c.korunan_neden = g.korunan ? "Öğretmen işaretledi" : null; }
    if (degisti) Object.assign(c, { baglanti_hesabi: g.baglanti_hesabi, anahtar_durumu: "gerekli", sudo_durumu: null, durum: "Hazırlık gerekli" });
    return { hesap_degisti: degisti };
  });
  yol("POST", "/api/cihazlar/ice-aktar/onizle", (g) => iceAktar(g, false));
  yol("POST", "/api/cihazlar/ice-aktar", (g) => iceAktar(g, true));
  function iceAktar(g, ekle) {
    const ansible = /^\s*\[/m.test(g.icerik) || g.icerik.includes("ansible_host");
    const satirlar = [];
    let grup = null;
    g.icerik.split(/\r?\n/).forEach((ham, i) => {
      const s = ham.split("#")[0].trim();
      if (!s) return;
      if (s.startsWith("[")) { grup = s.includes(":") ? null : s.slice(1, -1); return; }
      if (ansible && !grup) return;
      const p = ansible ? s.split(/\s+/) : s.split(/[;,]/).map((x) => x.trim());
      const oz = Object.fromEntries(p.slice(1).filter((x) => x.includes("=")).map((x) => x.split("=")));
      const ip = ansible ? (oz.ansible_host || p[0]) : (p.find((x) => /^\d+(\.\d+){3}$/.test(x)) || "");
      if (!ansible && i === 0 && !ip) return;
      const r = { satir: i + 1, ip, port: 22, etiket: ansible ? (/^\d/.test(p[0]) ? null : p[0]) : p[0], hesap: oz.ansible_user || (ansible ? null : p[2] || null),
        laboratuvar: (ansible ? grup : p[3]) || g.laboratuvar || "Laboratuvar" };
      if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) Object.assign(r, { durum: "gecersiz", neden: "Geçersiz IP adresi" });
      else if (cihazlar.some((c) => c.ip === ip) || satirlar.some((x) => x.ip === ip)) Object.assign(r, { durum: "var", neden: "zaten envanterde" });
      else r.durum = "eklenecek";
      satirlar.push(r);
    });
    const eklenecek = satirlar.filter((s) => s.durum === "eklenecek");
    if (!ekle) return { bicim: ansible ? "ansible" : "csv", satirlar, eklenecek: eklenecek.length };
    for (const s of eklenecek) yollar.find((y) => y.metod === "POST" && y.desen.source === "^/api/cihazlar$").islev({ ip: s.ip, etiket: s.etiket, grup: s.laboratuvar, baglanti_hesabi: s.hesap });
    return { eklenen: eklenecek.length, atlanan: satirlar.length - eklenecek.length };
  }
  yol("POST", "/api/cihazlar/cikar", (g) => {
    for (const id of g.cihazlar) { const i = cihazlar.findIndex((c) => c.id === id); if (i >= 0) cihazlar.splice(i, 1); }
    return { silinen: g.cihazlar.length };
  });
  yol("GET", "/api/envanter/ansible", () => "");

  yol("POST", "/api/durum-kontrol", (g) => {
    const r = isBaslat("durum", g.cihazlar, {}, (c) => {
      if (c.anahtar_durumu !== "ok") return { durum: "basarili", mesaj: "erişilebilir; SSH anahtarı kurulu değil (M1-S2)" };
      const u = [];
      if (c.ogrenci_oturumu) u.push("ogrenci oturumu açık");
      if (c.sudo_durumu !== "parolasiz") u.push("parolasız sudo yok (M1-S2)");
      if ((c.yonetim_hesaplari || []).length > 1) u.push("hp ve pardus birlikte var (tekilleştirme)");
      return { durum: "basarili", mesaj: `${c.pardus_surum}, ${c.masaustu}` + (u.length ? ` | UYARI: ${u.join("; ")}` : ""), etki: (x) => { x.son_kontrol = SIMDI(); } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "durum";
    return r;
  });
  yol("POST", "/api/hazirlik/kimlik-oku", (g) => isBaslat("kimlik_oku", g.cihazlar, {}, (c) => {
    if (c.erisim === 0) return { durum: "basarisiz", asama: "baglanti", mesaj: "SSH erişilemiyor (timed out)" };
    if (!c.parmak_izi) c.parmak_izi = `SHA256:okundu${c.id}Mx4Tq9Zb2Wn7Hp5Kc1Ld8Fg3Vs6Yr0Ja`;
    return { durum: "basarili", asama: "kimlik", mesaj: c.parmak_izi_onay ? "sunucu kimliği önceki onayla aynı" : `onay bekliyor: ${c.parmak_izi}`,
      etki: (x) => { if (!x.parmak_izi_onay) x.durum = "Kimlik onayı gerekli"; } };
  }));
  yol("POST", "/api/hazirlik/kimlik-onayla", (g) => {
    let n = 0;
    for (const id of g.cihazlar) { const c = cihazAl(id); if (c && c.parmak_izi) { c.parmak_izi_onay = 1; c.durum = "Hazırlık gerekli"; n += 1; } }
    return { onaylanan: n, atlanan: g.cihazlar.length - n };
  });
  yol("POST", "/api/hazirlik/baslat", (g) => {
    const r = isBaslat("hazirlik", g.cihazlar, { hesaplar: ["pardus"], ogrenci_olustur: g.ogrenci_olustur }, (c) => {
      if (c.etiket === "LAB22") return { durum: "basarisiz", asama: "yetki", mesaj: "Yetkili hesap hazırlığı gerekiyor: sudo yapabilen pardus/hp hesabıyla girilemedi (pardus: giriş yapılamadı (hesap yok veya parola yanlış); hp: giriş yapılamadı). Bilgisayarda yerel hazırlık yapın (yönetici kılavuzu: “Yerel hazırlık”). (DEMO örnek hata)" };
      const hesap = c.baglanti_hesabi || "pardus";
      const adimlar = [`${hesap} hesabıyla bağlanıldı`, "uygulama anahtarı eklendi", "parolasız sudo yapılandırıldı (visudo doğrulandı)",
        ...(c.profil_var === 0 && g.ogrenci_olustur ? ["ogrenci hesabı oluşturuldu (sudo yok, giriş ekranında parolasız)"] : []),
        "yeni oturumda yalnız anahtarla doğrulanıyor"];
      const diger = (c.yonetim_hesaplari || []).filter((h) => h !== hesap);
      return { durum: "basarili", mesaj: `hazır: ${hesap} hesabı, anahtar ve parolasız sudo bağımsız oturumda doğrulandı` + (diger.length ? `; ikinci yönetim hesabı da var (${diger.join(", ")}) — tekilleştirme önerilir` : ""),
        veri: { adimlar, hesap },
        etki: (x) => Object.assign(x, { baglanti_hesabi: hesap, anahtar_durumu: "ok", sudo_durumu: "parolasiz", durum: "Yönetilebilir",
          profil_var: g.ogrenci_olustur ? 1 : x.profil_var, yonetim_hesaplari: x.yonetim_hesaplari || [hesap], son_kontrol: SIMDI(),
          pardus_surum: x.pardus_surum || "Pardus 23.5", masaustu: x.masaustu || "GNOME", giris_yoneticisi: x.giris_yoneticisi || "gdm3",
          gizleme_durumu: x.gizleme_durumu || "gorunur", ogrenci_oturumu: x.ogrenci_oturumu ?? 0 }) };
    });
    isler.get(r.is_id)._uygunlukIslemi = "hazirlik";
    return r;
  });
  yol("POST", "/api/tekillestirme/onizle", (g) => {
    const r = isBaslat("tekillestirme_onizleme", g.cihazlar, {}, (c) => {
      if ((c.yonetim_hesaplari || []).length < 2) return { durum: "atlandi", mesaj: `yalnız ${(c.yonetim_hesaplari || [c.baglanti_hesabi]).join(", ")} var; tekilleştirme gerekmez` };
      const hesaplar = { pardus: { ev_bayt: 420 * MB, anahtar_sayisi: 2, oturum: false, parolasiz: true },
        hp: { ev_bayt: 1300 * MB, anahtar_sayisi: 1, oturum: c.etiket === "B2-06", parolasiz: false } };
      return { durum: "basarili", mesaj: `iki yönetim hesabı var (pardus, hp); öneri: pardus korunsun`, veri: { hesaplar, oneri: "pardus", baglanti: c.baglanti_hesabi } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "tekillestirme";
    return r;
  });
  yol("POST", "/api/tekillestirme/uygula", (g) => {
    const r = isBaslat("tekillestirme", Object.keys(g.korunacaklar), { korunacaklar: g.korunacaklar }, (c) => {
      const k = g.korunacaklar[c.id], s = k === "pardus" ? "hp" : "pardus";
      if (c.etiket === "B2-06" && s === "hp") return { durum: "basarisiz", asama: "oturum", mesaj: "hp hesabında açık oturum var (x11 yerel); silme yapılmadı" };
      return { durum: "basarili", mesaj: `${s} silindi, ${k} korundu (yedek öğrenci PC'de: /var/lib/pardus-sinif-yonetimi/hesap-yedekleri/${s}-20260928-101500.tar.gz); Ansible envanteri ${k} hesabını kullanır`,
        etki: (x) => Object.assign(x, { baglanti_hesabi: k, yonetim_hesaplari: [k] }) };
    });
    isler.get(r.is_id)._uygunlukIslemi = "tekillestirme";
    return r;
  });

  yol("GET", "/api/kesif/ag", () => ({ ag: "192.168.10.0/24", adres: "192.168.10.2", arayuz: "enp3s0" }));
  yol("POST", "/api/kesif/tara", (g) => {
    const id = yeniId("i");
    const hedefler = bulunanlar.map((b) => ({ is_id: id, hedef: b.ip, durum: "basarili", asama: "kimlik", mesaj: `Bulundu — ${b.parmak_izi}`, zaman: SIMDI(), veri: null }));
    const k = { id, tip: "kesif", durum: "tamamlandi", baslangic: SIMDI(), bitis: SIMDI(), ozet: null, parametreler: { aralik: g.aralik }, hedefler };
    isler.set(id, k); gecmis.push(k);
    return { is_id: id, hedef_sayisi: 254 };
  });
  yol("GET", "/api/kesif/bulunanlar", () => bulunanlar.map((b) => ({ ...b, envanter_id: (cihazlar.find((c) => c.ip === b.ip) || {}).id || null,
    kimlik_farkli: false, ayni_kimlikli: bulunanlar.filter((x) => x.parmak_izi === b.parmak_izi).length })));
  yol("POST", "/api/kesif/ekle", (g) => {
    const eklenen = [];
    for (const k of g.bulunanlar) {
      const b = bulunanlar.find((x) => `${x.ip}:${x.ssh_port}` === k);
      if (!b || cihazlar.some((c) => c.ip === b.ip)) continue;
      const c = { ...cihaz(60 + eklenen.length, b.ip, g.laboratuvar || "Laboratuvar"), ip: b.ip, etiket: null, hostname: null,
        anahtar_durumu: "gerekli", sudo_durumu: null, parmak_izi: b.parmak_izi, parmak_izi_onay: 1, durum: "Hazırlık gerekli",
        baglanti_hesabi: null, yonetim_hesaplari: null, son_kontrol: null, pardus_surum: null, masaustu: null, gizleme_durumu: null,
        otomatik_giris: null, gorunum_durumu: null, ogrenci_oturumu: null, giris_yoneticisi: null,
        yinelenen_kimlik: bulunanlar.filter((x) => x.parmak_izi === b.parmak_izi).length > 1 ? 1 : 0 };
      c.id = yeniId("c");
      cihazlar.push(c);
      eklenen.push(c.id);
    }
    return { eklenen };
  });
  yol("POST", "/api/kesif/temizle", () => { bulunanlar.length = 0; return { tamam: true }; });

  yol("GET", "/api/temizlik/alanlar", () => ({ katalog: ALANLAR, genel: ["masaustu", "indirilenler", "cop"], saklama,
    kapsamlar: {}, ogretmen_bos: 212 * 1073741824, ogretmen_toplam: 465 * 1073741824 }));
  yol("POST", "/api/temizlik/onizle", (g) => {
    const tip = g.kapsam === "alanlar" ? "temizlik_onizleme" : "sifirlama_onizleme";
    const r = isBaslat(tip, g.cihazlar, { kapsam: g.kapsam }, (c) => {
      const alanlar = g.istisnalar[c.id] || g.alanlar;
      if (g.kapsam === "alanlar") {
        const s = temizlikOlcum(c, alanlar);
        const parca = Object.entries(s.alanlar).map(([a, b]) => b.atlandi ? `${ALAN_ADI[a]}: ATLANDI (${b.atlandi})` : `${ALAN_ADI[a]}: ${b.adet} öğe`);
        return { durum: "basarili", mesaj: parca.join("; ") + (c.ogrenci_oturumu ? " | UYARI: ogrenci oturumu açık; kaydedilmemiş veriler kaybolabilir" : ""),
          veri: { alanlar, oturum_acik: Boolean(c.ogrenci_oturumu), sonuc: s } };
      }
      const s = sifirlamaOlcum(c, g.kapsam);
      return { durum: "basarili", mesaj: `silinecek: ${s.silinecek.adet} öğe` + (s.yedek.yeterli ? "" : " | UYARI: yedek için boş alan yetersiz — sıfırlama yapılamaz"),
        veri: { kapsam: g.kapsam, oturum_acik: Boolean(c.ogrenci_oturumu), sonuc: s } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "temizlik";
    return r;
  });
  yol("POST", "/api/temizlik/uygula", (g) => {
    const sifirla = g.kapsam !== "alanlar";
    const r = isBaslat(sifirla ? "profil_sifirla" : "temizlik", g.cihazlar, { kapsam: g.kapsam }, (c) => {
      if (sifirla && c.ogrenci_oturumu && !g.oturumlari_kapat) return { durum: "atlandi", asama: "oturum", mesaj: "ogrenci oturumu açık; oturum kapatma onaylanmadığı için durum: Profil sıfırlama bekliyor" };
      if (sifirla) {
        const s = sifirlamaOlcum(c, g.kapsam);
        const gercek = s.silinecek.serbest_kalabilir + s.yedek.budanacak_bayt - Math.round(s.yedek.ust_sinir * 0.45);
        return { durum: "basarili", mesaj: `${g.kapsam === "tam" ? "ev dizininin tamamı" : "ayarlar"} sıfırlandı; standart başlangıç dosyaları kondu; yedek: ogrenci-20260928-101500.tar.gz`,
          veri: { yedek: { ad: "ogrenci-20260928-101500.tar.gz" }, gerceklesen: gercek }, etki: (x) => { x.ogrenci_oturumu = 0; } };
      }
      const s = temizlikOlcum(c, g.istisnalar[c.id] || g.alanlar);
      return { durum: "basarili", mesaj: "seçilen alanlar karantinaya alındı; M2-S1 “Yedekten dön” ile geri alınabilir",
        veri: { gerceklesen: s.olcum.tahmini_acilacak + (Number(c.id.slice(-2)) % 4) * 4096 } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "temizlik";
    return r;
  });
  yol("POST", "/api/oturum-kapat", (g) => {
    const r = isBaslat("oturum_kapat", g.cihazlar, {}, (c) => (c.ogrenci_oturumu
      ? { durum: "basarili", mesaj: "öğrenci oturumu kapatıldı; süreçler doğrulandı", etki: (x) => { x.ogrenci_oturumu = 0; } }
      : { durum: "basarili", mesaj: "öğrenci oturumu zaten kapalıydı" }));
    isler.get(r.is_id)._uygunlukIslemi = "oturum";
    return r;
  });
  yol("POST", "/api/yedek", (g) => {
    const r = isBaslat("yedek", g.cihazlar, {}, () => ({ durum: "basarili", mesaj: "yedek doğrulandı: ogrenci-20260928-101500.tar.gz (412 MB, 4180 kayıt). Yerel yedek disk arızasına karşı koruma sağlamaz." }));
    isler.get(r.is_id)._uygunlukIslemi = "temizlik";
    return r;
  });
  yol("POST", "/api/yedekler/listele", (g) => ({ oturum_acik: Boolean(cihazAl(g.cihaz).ogrenci_oturumu), yedekler: [
    { tur: "temizlik", ad: "20260928-154000-ogrenci", zaman: "2026-09-28T15:40:00", etiket: "28.09.2026 15.40", alanlar: ["masaustu", "indirilenler"], adet: 17, bayt: 96 * MB, eski_bicim: false },
    { tur: "profil", ad: "ogrenci-20260927-120000.tar.gz", zaman: "2026-09-27T12:00:00", etiket: "27.09.2026 12.00", bayt: 388 * MB, dogrulanabilir: true },
    { tur: "profil", ad: "ogrenci-20260920-090000.tar.gz", zaman: "2026-09-20T09:00:00", etiket: "20.09.2026 09.00", bayt: 350 * MB, dogrulanabilir: false },
  ] }));
  yol("POST", "/api/yedekler/geri-yukle", (g) => isBaslat("geri_yukle", [g.cihaz], {}, () => ({ durum: "basarili",
    mesaj: "geri yükleme tamamlandı: 12 dosya geri kondu, 4 dosya zaten aynıydı, 1 dosya farklı olduğu için '(yedek …)' adıyla yanına kondu" })));

  yol("GET", "/api/paketler", (g) => (g.tur === "veyon" ? veyonPaketleri : paketler));
  yol("DELETE", "/api/paketler/(\\w+)", (_, [sha]) => {
    for (const liste of [paketler, veyonPaketleri]) { const i = liste.findIndex((p) => p.sha256 === sha); if (i >= 0) liste.splice(i, 1); }
    if (veyonSecili === sha) veyonSecili = veyonPaketleri.length === 1 ? veyonPaketleri[0].sha256 : null;
    return { tamam: true };
  });

  /* ---- M1-S4 Veyon ---- */
  const VEYON_YOK = "Bu bilgisayarda Veyon kurulu değil. Bu sayfadaki Veyon paketi alanından uygun .deb dosyasını yükleyerek kurulumu başlatabilirsiniz.";
  const veyonPaketi = () => veyonPaketleri.find((p) => p.sha256 === veyonSecili) || null;
  yol("GET", "/api/veyon", () => ({ paketler: veyonPaketleri, secili_sha: veyonPaketi() ? veyonSecili : null, anahtar: veyonAnahtar,
    anahtar_adi_varsayilan: "teacher", veyon_yok_mesaji: VEYON_YOK, kipler: {} }));
  yol("POST", "/api/veyon/paket-sec", (g) => { veyonSecili = g.sha; return veyonPaketi(); });
  yol("DELETE", "/api/veyon/anahtar", () => { const vardi = Boolean(veyonAnahtar); veyonAnahtar = null; return { silindi: vardi }; });
  yol("GET", "/api/veyon/hazirlik", () => {
    if (!veyonAnahtar) return { hazir: false, veyon: { paket: "veyon", surum: "4.11.0.0-debian.12" }, yontem: 1, eslesen: null, ozel_anahtar: null,
      sorunlar: ["Henüz Veyon public key yüklenmedi (M1-S4-B4)."], uyarilar: [], komutlar: [] };
    const tanidik = veyonAnahtar.cift_kimligi === "37b08aea";
    return { hazir: tanidik, veyon: { paket: "veyon", surum: "4.11.0.0-debian.12" }, yontem: 1, eslesen: tanidik ? veyonAnahtar.ad : null,
      ozel_anahtar: { var: tanidik, yol: `/etc/veyon/keys/private/${veyonAnahtar.ad}/key`, grup: "ogretmen", izin: "0440", okuyabilenler: tanidik ? ["ogretmen"] : [] },
      sorunlar: tanidik ? [] : [`Öğretmen PC'de '${veyonAnahtar.ad}' adlı private key yok (/etc/veyon/keys/private/${veyonAnahtar.ad}/key). Veyon Master bu anahtarla bağlanamaz. (DEMO örneği)`],
      uyarilar: [], komutlar: [] };
  });
  const vOge = (c, kur) => {
    const y = c.veyon_yapilandirma || {};
    const ayni = y.eslesme === "eslesiyor";
    return { anahtar: { ad: veyonAnahtar ? veyonAnahtar.ad : "teacher", durum: ayni ? "zaten" : y.eslesme === "farkli" ? "degistirilecek" : "eklenecek", mevcut_kimlik: y.eslesme === "farkli" ? "5d0c11fe" : null },
      yontem: { durum: y.yontem === 1 && !kur ? "zaten" : "ayarlanacak" }, servis: { durum: (y.servis || {}).calisiyor && !kur ? "zaten" : "etkinlestirilecek" } };
  };
  function veyonPlani(c, kip) {
    const p = veyonPaketi();
    const vey = { durum: c.veyon_durumu || "kurulu_degil", surum: c.veyon_surum, paket: (c.veyon_yapilandirma || {}).paket, parcali: (c.veyon_yapilandirma || {}).parcali };
    const veri = { kip, veyon: vey };
    const parca = [];
    let engel = false;
    if (kip !== "yapilandir") {
      let k;
      if (c.etiket === "LAB19") k = { durum: "engellendi", engeller: ["paket yöneticisi meşgul (/var/lib/dpkg/lock-frontend kilitli); başka kurulum sürüyor olabilir"] };
      else if (vey.durum !== "kurulu") k = { durum: "kurulacak", kurulu_surum: null };
      else {
        const f = debKarsilastir(vey.surum, p.surum);
        k = f < 0 ? { durum: "guncellenecek", kurulu_surum: vey.surum, kurulu_paket: vey.paket, yerine_gececek: vey.parcali ? ["veyon-configurator", "veyon-master", "veyon-service", "libveyon-core", "veyon-plugins"] : null }
          : f === 0 ? { durum: "atlanacak", kurulu_surum: vey.surum, neden: `aynı sürüm (${vey.surum}) zaten kurulu; yeniden kurulmaz` }
            : { durum: "atlanacak", kurulu_surum: vey.surum, neden: `daha yeni Veyon kurulu (${vey.surum}); seçili paket daha eski — sürüm düşürülmez, kurulum atlanır` };
      }
      veri.kurulum = k;
      if (k.durum === "engellendi") { engel = true; parca.push(`kurulum ENGELLENDİ: ${k.engeller.join("; ")}`); }
      else parca.push(k.durum === "kurulacak" ? `kurulum: veyon ${p.surum} kurulacak` : k.durum === "guncellenecek" ? `kurulum: güncellenecek (${k.kurulu_paket} ${k.kurulu_surum} → veyon ${p.surum})` : `kurulum: ${k.neden}`);
    }
    if (kip !== "kur") {
      if (kip === "yapilandir" && vey.durum !== "kurulu") {
        engel = true; veri.yapilandirma = { durum: "engellendi", neden: vey.durum === "hatali" ? "Veyon kurulumu hatalı veya yarım; önce kurulumu düzeltin" : VEYON_YOK };
        parca.push(`yapılandırma: ${veri.yapilandirma.neden}`);
      } else {
        const yeniKurulum = veri.kurulum && veri.kurulum.durum !== "atlanacak";
        veri.yapilandirma = { onizleme: true, veyon_yok: vey.durum !== "kurulu", ogeler: vOge(c, yeniKurulum) };
        const o = veri.yapilandirma.ogeler;
        parca.push(`yapılandırma: anahtar '${o.anahtar.ad}' ${o.anahtar.durum === "zaten" ? "zaten aynı" : o.anahtar.durum === "degistirilecek" ? "DEĞİŞTİRİLECEK" : "eklenecek"}, yöntem → anahtar dosyası, servis etkinleştirilecek`);
      }
    }
    veri.durum = engel ? "engellendi" : "hazir";
    return { durum: engel ? "basarisiz" : "basarili", asama: "plan", mesaj: parca.join("; "), veri };
  }
  yol("POST", "/api/veyon/plan", (g) => {
    const r = isBaslat("veyon_plan", g.cihazlar, { kip: g.kip }, (c) => veyonPlani(c, g.kip));
    isler.get(r.is_id)._uygunlukIslemi = "veyon";
    return r;
  });
  yol("POST", "/api/veyon/uygula", (g) => {
    const p = veyonPaketi();
    const r = isBaslat("veyon_uygula", g.cihazlar, { kip: g.kip, plan_is_id: g.plan_is_id }, (c) => {
      if (g.kip !== "yapilandir" && c.etiket === "LAB16") {
        return { durum: "basarisiz", asama: "kurulum", mesaj: "kurulum başarısız (apt rc=100): E: Sub-process /usr/bin/dpkg returned an error code (1) (DEMO örnek hata); yapılandırmaya geçilmedi", veri: { durum: "hata" } };
      }
      const adim = [];
      let yeniSurum = c.veyon_surum;
      if (g.kip !== "yapilandir") {
        const f = c.veyon_durumu === "kurulu" ? debKarsilastir(c.veyon_surum, p.surum) : -1;
        if (f < 0) { adim.push(`kuruldu ve doğrulandı: veyon ${p.surum}`); yeniSurum = p.surum; }
        else adim.push(f === 0 ? "kurulum atlandı: aynı sürüm zaten kurulu" : `kurulum atlandı: daha yeni Veyon kurulu (${c.veyon_surum}); sürüm düşürülmez`);
      }
      if (g.kip !== "kur") adim.push("yapılandırma: anahtar 'teacher' kuruldu ve geri okunarak doğrulandı, yöntem anahtar dosyası yapıldı, servis etkin ve çalışıyor (önceki ayarlar yedeklendi: 20261004-101500)");
      return { durum: "basarili", mesaj: `${adim.join("; ")} | Veyon ${yeniSurum} kurulu; servis çalışıyor`, veri: { durum: "tamam" },
        etki: (x) => Object.assign(x, { veyon_durumu: "kurulu", veyon_surum: yeniSurum, veyon_kontrol: SIMDI(),
          veyon_yapilandirma: g.kip === "kur" ? { ...(x.veyon_yapilandirma || vyap("yok", null, false)), paket: "veyon", parcali: false } : vyap("eslesiyor", 1, true) }) };
    });
    isler.get(r.is_id)._uygunlukIslemi = "veyon";
    return r;
  });
  yol("POST", "/api/veyon/surumler", (g) => {
    const r = isBaslat("veyon_surum", g.cihazlar, {}, (c) => ({ durum: "basarili",
      mesaj: c.veyon_durumu === "kurulu" ? `Veyon ${c.veyon_surum} kurulu; servis ${((c.veyon_yapilandirma || {}).servis || {}).calisiyor ? "çalışıyor" : "kapalı"}` : c.veyon_durumu === "hatali" ? "Veyon kurulumu hatalı veya yarım (dpkg durumu: veyon=iU)" : "Veyon kurulu değil",
      etki: (x) => { x.veyon_kontrol = SIMDI(); if (!x.veyon_durumu) Object.assign(x, { veyon_durumu: "kurulu_degil" }); } }));
    isler.get(r.is_id)._uygunlukIslemi = "veyon_oku";
    return r;
  });
  yol("POST", "/api/veyon/dogrula", (g) => {
    const r = isBaslat("veyon_dogrula", g.cihazlar, {}, (c) => {
      const y = c.veyon_yapilandirma || {};
      const den = [[c.veyon_durumu === "kurulu", c.veyon_durumu === "kurulu" ? `Veyon ${c.veyon_surum} kurulu` : "Veyon kurulu değil"],
        [Boolean((y.servis || {}).calisiyor), (y.servis || {}).calisiyor ? "servis etkin, çalışıyor" : "servis çalışmıyor"],
        [y.yontem === 1, y.yontem === 1 ? "kimlik doğrulama: anahtar dosyası" : "kimlik doğrulama: oturum parolası (anahtar kullanılmıyor)"],
        [y.eslesme === "eslesiyor", y.eslesme === "eslesiyor" ? "public key 'teacher' eşleşiyor (37b08aea)" : y.eslesme === "farkli" ? "public key 'teacher' FARKLI (5d0c11fe)" : "public key 'teacher' yok"],
        [Boolean((y.servis || {}).calisiyor), (y.servis || {}).calisiyor ? "öğretmen PC'den Veyon sunucusu yanıt verdi (RFB 003.008)" : "öğretmen PC'den 11100 portuna bağlanılamadı"]];
      const tamam = den.every(([ok]) => ok);
      return { durum: tamam ? "basarili" : "basarisiz", asama: "dogrulama", veri: { durum: tamam ? "tamam" : "hata" },
        mesaj: den.map(([ok, m]) => `${ok ? "✓" : "✗"} ${m}`).join("; ") + " | Anahtarla gerçek oturum yalnız Veyon Master'da denenebilir" };
    });
    isler.get(r.is_id)._uygunlukIslemi = "veyon_oku";
    return r;
  });
  yol("POST", "/api/veyon/geri-al", (g) => {
    const r = isBaslat("veyon_geri_al", g.cihazlar, {}, (c) => ((c.veyon_yapilandirma || {}).yontem === 1
      ? { durum: "basarili", mesaj: "yedek 20261004-101500 geri alındı: Veyon.conf kaldırıldı (yedek anında yoktu); public anahtar dizini kaldırıldı; servis etkin değil / durduruldu; Veyon paketi kaldırılmadı",
        etki: (x) => { x.veyon_yapilandirma = { ...vyap("yok", null, false), paket: (x.veyon_yapilandirma || {}).paket }; x.veyon_kontrol = SIMDI(); } }
      : { durum: "basarisiz", asama: "geri_alma", mesaj: "Bu bilgisayarda geri alınacak Veyon yedeği yok (bu uygulama burada henüz yapılandırma yapmamış)" }));
    isler.get(r.is_id)._uygunlukIslemi = "veyon";
    return r;
  });
  yol("POST", "/api/paketler/(\\w+)/plan", (g, [sha]) => {
    const p = paketler.find((x) => x.sha256 === sha);
    const r = isBaslat("paket_plan", g.cihazlar, { sha256: sha }, (c) => {
      const n = Number(c.id.slice(-2));
      const apt = { yeni: [{ paket: p.paket, surum: p.surum }, { paket: "libqrencode4", surum: "4.1.1-1" }], guncellenecek: [], kaldirilacak: [], dusurulecek: [] };
      let plan = { durum: "kurulacak", kurulu_surum: null, engeller: [], uyarilar: [], apt, indirilecek: 1, depo_erisimi: true,
        pardus: "Pardus GNU/Linux 23 (yirmiuc)", mimari: "amd64", bos_alan: c.disk_bos, gerekli_alan: p.boyut + p.kurulu_kb * 1024 + 100 * MB };
      if (c.etiket === "LAB14") plan = { ...plan, durum: "atlanacak", kurulu_surum: p.surum, neden: `aynı sürüm (${p.surum}) zaten kurulu; yeniden kurulmaz` };
      else if (c.etiket === "B2-05") plan = { ...plan, durum: "engellendi", apt: { ...apt, kaldirilacak: ["eski-sinav-araci"] }, engeller: ["kurulum şu paketleri KALDIRACAK: eski-sinav-araci — izin verilmez"] };
      else if (c.etiket === "B2-07") plan = { ...plan, durum: "guncellenecek", kurulu_surum: "2.0", apt: { ...apt, yeni: apt.yeni.slice(1), guncellenecek: [{ paket: p.paket, eski: "2.0", yeni: p.surum }] } };
      else if (c.etiket === "B2-04") plan = { ...plan, durum: "engellendi", depo_erisimi: false, engeller: ["1 bağımlılık indirilmeli ama paket deposuna erişilemiyor: libqrencode4"] };
      else if (n === 19) plan = { ...plan, durum: "engellendi", engeller: ["paket yöneticisi meşgul (/var/lib/dpkg/lock-frontend kilitli); başka kurulum sürüyor olabilir"] };
      const metin = { kurulacak: "kurulacak (1 yeni bağımlılık; 1 dosya depodan indirilecek)", guncellenecek: `güncellenecek (2.0 → ${p.surum})`,
        atlanacak: plan.neden, engellendi: `ENGELLENDİ: ${plan.engeller.join("; ")}` }[plan.durum];
      return { durum: plan.durum === "engellendi" ? "basarisiz" : "basarili", asama: "plan", mesaj: metin, veri: { plan } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "paket";
    return r;
  });
  yol("POST", "/api/paketler/(\\w+)/kur", (g, [sha]) => {
    const p = paketler.find((x) => x.sha256 === sha);
    const r = isBaslat("paket_kur", g.cihazlar, { sha256: sha, plan_is_id: g.plan_is_id }, (c) => (c.etiket === "LAB16"
      ? { durum: "basarisiz", asama: "kurulum", mesaj: "kurulum başarısız (apt rc=100): E: Sub-process /usr/bin/dpkg returned an error code (1) (DEMO örnek hata)" }
      : { durum: "basarili", mesaj: `kuruldu ve doğrulandı: ${p.paket} ${p.surum}`, veri: { sonuc: { kurulu_surum: p.surum, kuruldu: true } } }));
    isler.get(r.is_id)._uygunlukIslemi = "paket";
    return r;
  });

  /* ---- M2-S4 uyku ayarı ve M2-S5 zamanlı kapatma ---- */
  const gucOzet = (g) => (g ? `${g.uyku_kapali ? "uyku KAPALI" : "uyku AÇIK (bilgisayar boşta uykuya geçebilir)"}; ${g.planlar.length} kapatma planı${g.bekleyen ? `; BEKLEYEN KAPATMA VAR${g.bekleyen_saat ? ` (kapanma ${g.bekleyen_saat})` : ""}` : ""}` : "güç durumu okundu");
  const gucBos = () => ({ uyku_kapali: false, ekran_dk: null, bekleyen: false, planlar: [], zaman: SIMDI() });
  yol("POST", "/api/guc/uyku", (g) => {
    const tip = { onizle: "uyku_onizleme", uygula: "uyku_ayari", kaldir: "uyku_varsayilan" }[g.islem];
    const r = isBaslat(tip, g.cihazlar, { islem: g.islem, ekran_dk: g.ekran_dk }, (c) => {
      const once = c.guc_durumu || gucBos();
      if (g.islem === "onizle") return { durum: "basarili", asama: "onizleme", mesaj: `şu an: ${gucOzet(once)} → ${once.uyku_kapali ? "uyku zaten kapalı" : "5 uyku hedefi kapatılacak"}, ekran koruyucu ${g.ekran_dk ? `${g.ekran_dk} dk` : "kapalı"} olacak` };
      if (g.islem === "kaldir") return { durum: "basarili", mesaj: "uyku hedefleri eski haline döndü; GNOME güç ayarları varsayılana döndü; logind ayarı kaldırıldı",
        etki: (x) => { x.guc_durumu = { ...(x.guc_durumu || gucBos()), uyku_kapali: false, ekran_dk: null }; } };
      return { durum: "basarili", mesaj: `uyku/askıya alma hedefleri kapatıldı (5/5 maskeli); oturum: boşta uyku yok, ekran koruyucu ${g.ekran_dk ? `${g.ekran_dk} dk` : "kapalı"} (kilitli); giriş ekranı (GDM): boşta uyku yok; güç tuşu/kapak uyku yapmaz (logind; bir sonraki açılışta tam geçerli)`,
        etki: (x) => { x.guc_durumu = { ...(x.guc_durumu || gucBos()), uyku_kapali: true, ekran_dk: g.ekran_dk }; } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });
  yol("POST", "/api/kapatma/oku", (g) => {
    const r = isBaslat("kapatma_oku", g.cihazlar, {}, (c) => ({ durum: "basarili", mesaj: gucOzet(c.guc_durumu || gucBos()),
      etki: (x) => { if (!x.guc_durumu) x.guc_durumu = gucBos(); } }));
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });
  yol("POST", "/api/kapatma/ekle", (g) => {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(g.saat || "")) throw new Hata(422, "Saat SS:DD biçiminde olmalı (ör. 17:30)");
    let etiket;
    if (g.tur === "tek") {
      if (!g.tarih || new Date(`${g.tarih}T${g.saat}`) <= new Date()) throw new Hata(422, "Geçmiş bir zaman seçilemez");
      etiket = `${g.tarih.split("-").reverse().join(".")} ${g.saat} (bir kez)`;
    } else {
      if (!g.gunler.length) throw new Hata(422, "En az bir gün seçin");
      etiket = `${gunEtiketi(g.gunler)} ${g.saat} (her hafta)`;   // guc.js ile aynı gösterim
    }
    const plan = { id: yeniId("p").slice(0, 6), etiket, tur: g.tur, uyari_dk: g.uyari_dk, aciklama: g.aciklama, etkin: true,
      sonraki: g.tur === "tek" ? `${g.tarih} ${g.saat}:00` : `ilk uygun gün ${g.saat}:00 (DEMO)` };
    const r = isBaslat("kapatma_ekle", g.cihazlar, { plan }, () => ({ durum: "basarili", mesaj: `plan eklendi: ${etiket}; sonraki kapanma: ${plan.sonraki}`,
      etki: (x) => { const gd = x.guc_durumu || gucBos(); x.guc_durumu = { ...gd, planlar: [...gd.planlar.filter((p2) => p2.id !== plan.id), { ...plan }] }; } }));
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });
  yol("POST", "/api/kapatma/sil", (g) => {
    const r = isBaslat("kapatma_sil", g.cihazlar, { idler: g.idler || "hepsi" }, (c) => {
      const gd = c.guc_durumu || gucBos();
      const kalan = g.idler ? gd.planlar.filter((p2) => !g.idler.includes(p2.id)) : [];
      const silinen = gd.planlar.length - kalan.length;
      return { durum: "basarili", mesaj: `${silinen ? `${silinen} plan kaldırıldı` : "kaldırılacak plan yoktu"}; kalan: ${kalan.length}`,
        etki: (x) => { x.guc_durumu = { ...(x.guc_durumu || gucBos()), planlar: kalan }; } };
    });
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });
  yol("POST", "/api/kapatma/iptal", (g) => {
    const r = isBaslat("kapatma_iptal", g.cihazlar, {}, (c) => ((c.guc_durumu || {}).bekleyen
      ? { durum: "basarili", mesaj: "bekleyen kapatma iptal edildi; 1 masaüstüne bildirildi", etki: (x) => { x.guc_durumu.bekleyen = false; x.guc_durumu.bekleyen_saat = null; } }
      : { durum: "basarili", mesaj: "bekleyen kapatma yoktu" }));
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });

  let gorsel = null;
  yol("GET", "/api/gorunum", () => ({ gorsel }));
  yol("POST", "/api/duvar-kagidi/gorsel", (g) => { gorsel = { ad: `duvar${g.uzanti}`, bayt: Math.round(g.icerik_b64.length * 0.75) }; return { tamam: true, bayt: gorsel.bayt }; });
  function gorunumIs(g, kip) {
    const r = isBaslat(kip === "uygula" ? "gorunum" : "gorunum_onizleme", g.cihazlar, { secenekler: g.secenekler }, (c) => {
      const d = (a) => (kip === "uygula" ? (g.secenekler[a] === "kaldir" ? "kaldirildi" : "uygulandi") : (g.secenekler[a] === "kaldir" ? "kaldirilacak" : "uygulanacak"));
      const ogeler = {};
      if (g.secenekler.duzen) ogeler.duzen = { durum: d("duzen"), atlanan: [{ anahtar: "/org/gnome/shell/extensions/dash-to-dock/trans-panel-opacity", neden: "kurulu şemada yok" }],
        ayrinti: `Karşılayıcı'da seçili düzen: ${c.gorunum_durumu === "uygulandi" ? "10" : "pardus"}; şu an etkin menü/panel: ${c.etiket === "LAB11" ? "Dash to Dock (rıhtım)" : "ArcMenu (uygulama menüsü), Dash to Panel (görev çubuğu)"}${c.etiket === "LAB11" ? "; kapatılacak farklı menü: Dash to Dock (rıhtım)" : ""}`,
        karsilayici: g.secenekler.kilit ? "öğrenci girişinde açılmayacak" : "öğrenci girişinde açılabilir (kilit yok)",
        dogrulama: kip === "uygula" ? "derlenmiş sistem veritabanından okundu; 19 anahtar yazılanla aynı" : null };
      if (g.secenekler.duvar) ogeler.duvar = { durum: d("duvar") };
      if (g.secenekler.ekran_kilidi) ogeler.ekran_kilidi = { durum: d("ekran_kilidi"), atlanan: [{ anahtar: "/org/gnome/desktop/screensaver/ubuntu-lock-on-suspend", neden: "kurulu şemada yok" }] };
      if (g.secenekler.otomatik_giris) ogeler.otomatik_giris = { durum: c.otomatik_giris === "ogrenci" && g.secenekler.otomatik_giris === "uygula" ? "zaten" : d("otomatik_giris"),
        dogrulama: kip === "uygula" ? "GDM ayar dosyası yeniden okundu; bir sonraki açılışta etkinleşir" : null };
      if (g.secenekler.gizle) ogeler.gizle = { durum: c.gizleme_durumu === "gizli" && g.secenekler.gizle === "uygula" ? "zaten" : d("gizle"),
        dogrulama: kip === "uygula" ? "AccountsService listesinde yok; gerçek giriş ekranında görsel doğrulama yapılmadı" : null };
      const ad = { duzen: "Windows 10 benzeri düzen", duvar: "Duvar kâğıdı", ekran_kilidi: "Ekran kilidi kapalı", otomatik_giris: "Öğrenci otomatik girişi", gizle: "Yönetim hesabını gizle" };
      return { durum: "basarili", mesaj: Object.entries(ogeler).map(([k, v]) => `${ad[k]}: ${v.durum}`).join("; ") + (c.ogrenci_oturumu ? "; UYARI: öğrenci oturumu açık" : ""),
        veri: { ortam: { masaustu: c.masaustu, giris_yoneticisi: c.giris_yoneticisi, ogrenci_oturumu: Boolean(c.ogrenci_oturumu) }, ogeler },
        etki: kip === "uygula" ? (x) => Object.assign(x, g.secenekler.duzen ? { gorunum_durumu: g.secenekler.duzen === "uygula" ? "uygulandi" : "yok" } : {},
          g.secenekler.gizle ? { gizleme_durumu: g.secenekler.gizle === "uygula" ? "gizli" : "gorunur" } : {},
          g.secenekler.otomatik_giris ? { otomatik_giris: g.secenekler.otomatik_giris === "uygula" ? "ogrenci" : "kapali" } : {}) : null };
    });
    isler.get(r.is_id)._uygunlukIslemi = "gorunum";
    return r;
  }
  yol("POST", "/api/gorunum/onizle", (g) => gorunumIs(g, "onizle"));
  yol("POST", "/api/gorunum/uygula", (g) => gorunumIs(g, "uygula"));
  yol("POST", "/api/guc", (g) => {
    const r = isBaslat(`guc_${g.eylem}`, g.cihazlar, { eylem: g.eylem }, () => ({ durum: "basarili",
      mesaj: g.eylem === "kapat" ? "kapanma doğrulandı" : "yeniden açılma doğrulandı" }));
    isler.get(r.is_id)._uygunlukIslemi = "guc";
    return r;
  });

  yol("GET", "/api/isler", () => [...gecmis].reverse().map((k) => { isIlerlet(k); const { hedefler, parametreler, ...ust } = disa(k); return { ogretmen_kullanici: "admin", ogretmen_ad: "Mukaddes ALAT", ogretmen_rol: "admin", ...ust }; }));
  yol("GET", "/api/isler/(\\w+)", (_, [id]) => { const k = isler.get(id); if (!k) throw new Hata(404, "İş bulunamadı"); isIlerlet(k); return { ogretmen_kullanici: "admin", ogretmen_ad: "Mukaddes ALAT", ogretmen_rol: "admin", ...disa(k) }; });
  yol("POST", "/api/isler/(\\w+)/iptal", (_, [id]) => { const k = isler.get(id); if (!k || k.durum !== "calisiyor") throw new Hata(409, "İş çalışmıyor veya zaten bitti"); k._iptal = true; return { tamam: true, not: "İptal, güvenli noktada durdurur; başlamış adımları geri almaz" }; });
  yol("GET", "/api/ayarlar", () => ({ saklama_adedi: saklama, versiyon: "0.6.0 · DEMO", odev_dizini: "/var/lib/pardus-sinif-odev", okul: demoOkul }));
  yol("POST", "/api/ayarlar", (g) => { saklama = g.saklama_adedi; return { saklama_adedi: saklama }; });

  /* ---- sınıf hızlı araçlar ve M2-S6 komut gönder ---- */
  yol("POST", "/api/sinif/ekran-kilit", (g) => isBaslat(g.kilitle ? "sinif_ekran_kilitle" : "sinif_ekran_ac", g.cihazlar, g, () => ({
    durum: "basarili", mesaj: g.kilitle ? "ekran kilitlendi ve bildirim gösterildi" : "ekran kilidi açıldı",
  })));
  yol("POST", "/api/sinif/duyuru", (g) => isBaslat("sinif_duyuru", g.cihazlar, g, () => ({
    durum: "basarili", mesaj: `duyuru gösterildi: ${g.mesaj}`,
  })));
  yol("POST", "/api/sinif/internet", (g) => isBaslat(g.kisitla ? "sinif_internet_kisitla" : "sinif_internet_ac", g.cihazlar, g, () => ({
    durum: "basarili", mesaj: g.kisitla ? "dış internet kısıtlandı (yerel ağ açık)" : "internet kısıtlaması kaldırıldı",
  })));
  yol("POST", "/api/sinif/masaustu-url", (g) => isBaslat("sinif_masaustu_url", g.cihazlar, g, () => ({
    durum: "basarili", mesaj: `masaüstüne kısayol bırakıldı: ${g.baslik}.desktop`,
  })));
  yol("POST", "/api/sinif/masaustu-dosya", (g) => isBaslat("sinif_masaustu_dosya", g.cihazlar, g, () => ({
    durum: "basarili", mesaj: `masaüstüne dosya kopyalandı: ${g.dosya_adi}`,
  })));
  yol("GET", "/api/komutlar", () => demoKomutlar);
  yol("POST", "/api/komutlar", (g) => {
    const yeni = { id: yeniId("k"), ad: g.ad, komut: g.komut, kategori: g.kategori || "Genel", sudo: Boolean(g.sudo), yerlesik: false };
    demoKomutlar.push(yeni);
    return yeni;
  });
  yol("DELETE", "/api/komutlar/([\\w-]+)", (_, [id]) => {
    demoKomutlar = demoKomutlar.filter((k) => k.id !== id || k.yerlesik);
    return { tamam: true };
  });
  yol("POST", "/api/komutlar/calistir", (g) => isBaslat("ssh_komut", g.cihazlar, g, (c) => {
    if (c.erisim === 0) return { durum: "basarisiz", asama: "ulasilamadi", mesaj: "Ulaşılamadı: SSH zaman aşımı", veri: { cihaz_id: c.id, rc: -1, stdout: "", stderr: "Connection timed out" } };
    if (c.etiket === "LAB16") return { durum: "basarisiz", asama: "komut", mesaj: "RC=1 — hata alındı (DEMO örnek)", veri: { cihaz_id: c.id, rc: 1, stdout: "", stderr: "userdel: user 'abc' does not exist" } };
    return { durum: "basarili", asama: "komut", mesaj: "RC=0 — başarıyla tamamlandı", veri: { cihaz_id: c.id, rc: 0, stdout: `[${c.etiket}] Komut başarıyla çalıştırıldı (DEMO).`, stderr: "" } };
  }));
  yol("POST", "/api/komutlar/hosts-ekle", (g) => isBaslat("hosts_ekle", g.cihazlar, g, (c) => {
    if (c.erisim === 0) return { durum: "basarisiz", asama: "ulasilamadi", mesaj: "Ulaşılamadı: SSH zaman aşımı", veri: { cihaz_id: c.id, rc: -1, stdout: "", stderr: "Connection timed out" } };
    return { durum: "basarili", asama: "hosts", mesaj: `${g.ip} ${g.alan_adi} /etc/hosts dosyasına eklendi`, veri: { cihaz_id: c.id, rc: 0, stdout: `${g.ip}\t${g.alan_adi}`, stderr: "" } };
  }));

  /* ---- M5-S2 okul ve öğretmenler ---- */
  yol("GET", "/api/okul", () => demoOkul);
  yol("POST", "/api/okul", (g) => { demoOkul = { ad: g.ad, alt_baslik: g.alt_baslik || "", logo_b64: g.logo_b64 || "" }; return demoOkul; });
  yol("GET", "/api/ogretmenler", () => demoOgretmenler);
  yol("POST", "/api/ogretmenler", (g) => {
    const yeni = { id: yeniId("ogr"), kullanici_adi: g.kullanici_adi, ad_soyad: g.ad_soyad, brans: g.brans || "", rol: g.rol || "standart", yetkiler: g.yetkiler || [], son_giris: null };
    demoOgretmenler.push(yeni);
    return yeni;
  });
  yol("PATCH", "/api/ogretmenler/([\\w-]+)", (g, [id]) => {
    const o = demoOgretmenler.find((x) => x.id === id);
    if (o) Object.assign(o, { ad_soyad: g.ad_soyad ?? o.ad_soyad, brans: g.brans ?? o.brans, rol: g.rol ?? o.rol, yetkiler: g.yetkiler ?? o.yetkiler });
    return o || {};
  });
  yol("DELETE", "/api/ogretmenler/([\\w-]+)", (_, [id]) => {
    demoOgretmenler = demoOgretmenler.filter((x) => x.id !== id);
    return { tamam: true };
  });

  /* ---- ödevler ---- */
  yol("GET", "/api/odev/durum", () => ({ adres: "http://ogretmen.lab", adres_adi: "ogretmen.lab", aglar: ["192.168.10.0/24", "192.168.20.0/24"],
    portal_calisiyor: true, bos_alan: 212 * 1073741824, turler: { belge: "Belgeler", gorsel: "Görseller", arsiv: "Arşivler (zip)", kod: "Kod dosyaları", medya: "Ses / video" },
    varsayilan_turler: ["belge", "gorsel", "arsiv"] }));
  yol("POST", "/api/odev/ayarlar", () => ({ not: "DEMO: ayar kaydedildi (gerçekte portal yeniden yapılandırılır)." }));
  yol("GET", "/api/odev/siniflar", () => odev.siniflar);
  yol("POST", "/api/odev/siniflar", (g) => { const s = { id: yeniId("s"), ad: g.ad, ogrenci_sayisi: 0 }; odev.siniflar.push(s); odev.ogrenciler[s.id] = []; return { id: s.id }; });
  yol("DELETE", "/api/odev/siniflar/(\\w+)", (_, [id]) => { odev.siniflar = odev.siniflar.filter((s) => s.id !== id); return { tamam: true }; });
  yol("GET", "/api/odev/siniflar/(\\w+)/ogrenciler", (_, [id]) => odev.ogrenciler[id] || []);
  yol("POST", "/api/odev/siniflar/(\\w+)/ogrenciler", (g, [id]) => { odev.ogrenciler[id].push({ id: yeniId("o"), numara: g.numara, ad_soyad: g.ad_soyad, kodu_var: false }); return { tamam: true }; });
  yol("PATCH", "/api/odev/ogrenciler/(\\w+)", (g, [id]) => { for (const l of Object.values(odev.ogrenciler)) for (const o of l) if (o.id === id) o.ad_soyad = g.ad_soyad; return { tamam: true }; });
  yol("DELETE", "/api/odev/ogrenciler/(\\w+)", (_, [id]) => { for (const k of Object.keys(odev.ogrenciler)) odev.ogrenciler[k] = odev.ogrenciler[k].filter((o) => o.id !== id); return { tamam: true }; });
  yol("POST", "/api/odev/ice-aktar", () => ({ eklenen: 0, guncellenen: 0, hatalar: ["DEMO: CSV içeriği işlenmez"] }));
  yol("POST", "/api/odev/kod-uret", (g) => {
    const liste = g.ogrenci_idler ? Object.values(odev.ogrenciler).flat().filter((o) => g.ogrenci_idler.includes(o.id))
      : (odev.ogrenciler[g.sinif_id] || []).filter((o) => !o.kodu_var);
    return liste.map((o) => { o.kodu_var = true; o.kod_zamani = SIMDI(); return { sinif: "9-A", numara: o.numara, ad_soyad: o.ad_soyad, kod: "DEMO-KOD1" }; });
  });
  yol("GET", "/api/odev/odevler", () => odev.odevler);
  yol("POST", "/api/odev/odevler", (g) => { const s = odev.siniflar.find((x) => x.id === g.sinif_id);
    odev.odevler.unshift({ ...g, id: yeniId("a"), sinif: s.ad, durum: "taslak", durum_adi: "Taslak", son_tarih: g.son_tarih, son_tarih_giris: g.son_tarih || "", teslim_eden: 0, ogrenci_sayisi: s.ogrenci_sayisi }); return { tamam: true }; });
  yol("PUT", "/api/odev/odevler/(\\w+)", (g, [id]) => { Object.assign(odev.odevler.find((o) => o.id === id), g); return { tamam: true }; });
  yol("POST", "/api/odev/odevler/(\\w+)/durum", (g, [id]) => { const o = odev.odevler.find((x) => x.id === id);
    const yeni = { ac: ["acik", "Teslimler açık"], kapat: ["kapali", "Teslimler kapalı"], arsivle: ["arsiv", "Arşiv"], arsivden_cikar: ["kapali", "Teslimler kapalı"] }[g.eylem];
    [o.durum, o.durum_adi] = yeni; return { tamam: true }; });
  yol("POST", "/api/odev/odevler/(\\w+)/sil", (_, [id]) => { odev.odevler = odev.odevler.filter((o) => o.id !== id); return { tamam: true }; });
  yol("GET", "/api/odev/odevler/(\\w+)", (_, [id]) => {
    const o = odev.odevler.find((x) => x.id === id);
    const ogrenciler = (odev.ogrenciler[o.sinif_id] || []).map((s, i) => {
      const d = o.sinif_id === "s9a" ? teslimDurum[s.numara] : "alindi";
      const teslimler = ["alindi", "gec", "yukleniyor", "hata"].includes(d) && d !== "yukleniyor" && d !== "hata"
        ? [{ id: `t${s.numara}b`, surum: 2, zaman: "28.09.2026 14:10", gec: d === "gec", teslim_no: `A${s.numara}-2` }, { id: `t${s.numara}a`, surum: 1, zaman: "27.09.2026 10:02", gec: false, teslim_no: `A${s.numara}-1` }].slice(0, 1 + (i % 2))
        : [];
      return { ogrenci_id: s.id, numara: s.numara, ad_soyad: s.ad_soyad, durum: d, son_hata: d === "hata" ? "servis yeniden başladı" : null,
        son_zaman: teslimler.length ? teslimler[0].zaman : null, surum: teslimler.length ? teslimler[0].surum : null,
        dosya_sayisi: teslimler.length ? 3 : null, toplam_bayt: teslimler.length ? 2.4 * MB : null, teslimler };
    });
    const say = (d) => ogrenciler.filter((x) => x.durum === d).length;
    return { odev: o, ogrenciler, ozet: { toplam: ogrenciler.length, teslim_eden: say("alindi") + say("gec"), gec: say("gec"), etmedi: say("etmedi"),
      yukleniyor: say("yukleniyor"), hata: say("hata"), tamami_teslim_etti: say("etmedi") === 0 && say("hata") === 0 && say("yukleniyor") === 0 } };
  });
  yol("GET", "/api/odev/teslimler/(\\w+)/dosyalar", () => [
    { sira: 1, goreli_yol: "Labirent/labirent.sb3", boyut: 2.1 * MB, sha256: "9f86d081884c7d659a2f" },
    { sira: 2, goreli_yol: "Labirent/sesler/zipla.wav", boyut: 280000, sha256: "60303ae22b998861bce3" },
    { sira: 3, goreli_yol: "Labirent/BENIOKU.txt", boyut: 420, sha256: "fd61a03af4f77d870fc2" }]);

  /* ---- fetch ---- */
  const gercekFetch = window.fetch.bind(window);
  window.fetch = async (girdi, secenekler = {}) => {
    const url = new URL(typeof girdi === "string" ? girdi : girdi.url, "http://demo.local");
    if (!url.pathname.startsWith("/api/")) return gercekFetch(girdi, secenekler);
    const metod = (secenekler.method || "GET").toUpperCase();
    await bekle(80 + Math.random() * 160);
    try {
      if (metod === "POST" && url.pathname === "/api/paketler") {
        const dosya = secenekler.body;
        const basliklar = secenekler.headers || {};
        const ad = decodeURIComponent(basliklar["X-Dosya-Adi"] || "paket.deb");
        const veyonMu = basliklar["X-Paket-Turu"] === "veyon";
        const bas = new Uint8Array(await dosya.slice(0, 8).arrayBuffer());
        if (String.fromCharCode(...bas) !== "!<arch>\n") throw new Hata(422, "Dosya bir Debian paketi değil (ar imzası yok) — DEMO'da gerçek bir .deb seçin; içeriği işlenmez, yalnız adı okunur");
        const es = /^([a-z0-9][a-z0-9+.-]+)_([^_]+)_([a-z0-9]+)\.deb$/.exec(ad) || [null, "ornek-paket", "1.0", "all"];
        if (veyonMu && es[1] !== "veyon") throw new Hata(422, `Bu dosya Veyon paketi değil (paket adı: ${es[1]}). Veyon sayfası yalnız 'veyon' paketini kabul eder; başka uygulamalar M2-S2 Paket Kurulumu'ndan kurulur. (DEMO: ad dosya adından okunur; gerçek uygulama control dosyasını denetler)`);
        if (!veyonMu && es[1].startsWith("veyon")) throw new Hata(422, "Bu bir Veyon paketi. Veyon, M1-S4 “Veyon Ayarları” sayfasındaki “Veyon paketi” alanından yüklenir; kurulum ve yapılandırma da oradan yapılır.");
        const p = { sha256: Array.from({ length: 64 }, (_, i) => "0123456789abcdef"[(ad.charCodeAt(i % ad.length) + i) % 16]).join(""),
          dosya_adi: ad, paket: es[1], surum: es[2], mimari: es[3], boyut: dosya.size, kurulu_kb: Math.round(dosya.size / 300), zaman: SIMDI(),
          tur: veyonMu ? "veyon" : "genel",
          kontrol: { Package: es[1], Version: es[2], Architecture: es[3], Depends: "(DEMO: control dosyası okunmadı)", Description: "DEMO önizleme — paket içeriği işlenmedi",
            ...(veyonMu ? { Provides: "veyon-service (DEMO)" } : {}) } };
        const liste = veyonMu ? veyonPaketleri : paketler;
        if (!liste.some((x) => x.sha256 === p.sha256)) liste.unshift(p);
        return yanit(p);
      }
      if (metod === "POST" && url.pathname === "/api/veyon/anahtar") {
        const basliklar = secenekler.headers || {};
        const ad = decodeURIComponent(basliklar["X-Anahtar-Adi"] || "");
        const metin = await secenekler.body.text();
        if (!/^[A-Za-z][A-Za-z0-9]{0,31}$/.test(ad)) throw new Hata(422, "Anahtar adı harfle başlamalı, yalnız harf ve rakam içermeli (ör. teacher). Öğretmen PC'deki private key ile aynı ad olmalıdır.");
        if (/PRIVATE KEY/i.test(metin)) throw new Hata(422, "Bu bir PRIVATE (özel) anahtar! Özel anahtar hiçbir zaman yüklenmez; bu uygulama onu saklamadı. Yalnız Veyon PUBLIC key dosyasını (…_public_key.pem) seçin.");
        if (/^\s*(ssh-|ecdsa-sha2-|sk-)/.test(metin)) throw new Hata(422, "Bu bir SSH public key; Veyon anahtarı değil. Veyon public key'i PEM biçimindedir (-----BEGIN PUBLIC KEY-----).");
        if (!/-----BEGIN (RSA )?PUBLIC KEY-----/.test(metin)) throw new Hata(422, "Geçerli bir Veyon public key değil ('BEGIN PUBLIC KEY' PEM bekleniyor).");
        let h = 0;
        for (const ch of metin) h = (31 * h + ch.charCodeAt(0)) >>> 0;
        const kimlik = h.toString(16).padStart(8, "0");
        if (veyonAnahtar && veyonAnahtar.cift_kimligi !== kimlik && basliklar["X-Onay"] !== "1") {
          return yanit({ detail: `Uygulamada kayıtlı '${veyonAnahtar.ad}' anahtarından ([${veyonAnahtar.cift_kimligi}]) farklı bir anahtar yüklüyorsunuz ([${kimlik}]). Onaylarsanız mevcut anahtar yedeklenir ve değiştirilir.`,
            onay_gerekli: true, mevcut: veyonAnahtar }, 409);
        }
        const onceki = veyonAnahtar && veyonAnahtar.cift_kimligi !== kimlik ? { ad: veyonAnahtar.ad, cift_kimligi: veyonAnahtar.cift_kimligi, zaman: veyonAnahtar.zaman } : null;
        veyonAnahtar = { ad, dosya_adi: secenekler.body.name, parmak_izi: `${kimlik}`.repeat(8), cift_kimligi: kimlik, bit: 4096, zaman: SIMDI(), onceki };
        return yanit(veyonAnahtar);
      }
      const govde = secenekler.body ? JSON.parse(secenekler.body) : null;
      for (const y of yollar) {
        if (y.metod !== metod) continue;
        const es = y.desen.exec(url.pathname);
        if (es) return yanit(y.islev(govde || Object.fromEntries(url.searchParams), es.slice(1)) ?? {});
      }
      throw new Hata(404, `DEMO'da tanımlı değil: ${metod} ${url.pathname}`);
    } catch (hata) {
      return yanit({ detail: hata.message }, hata.kod || 500);
    }
  };

  /* ---- indirmeler ve DEMO kısıtları ---- */
  const INDIRME = [
    [/\/api\/envanter\/ansible/, "envanter.ini — hazır bilgisayarların Ansible envanteri"],
    [/\/api\/odev\/odevler\/\w+\/zip\?(.*ogrenciler=)/, "seçili öğrencilerin teslimleri (ZIP)"],
    [/\/api\/odev\/odevler\/\w+\/zip/, "sınıfın tüm teslimleri (ZIP)"],
    [/\/api\/odev\/teslimler\/\w+\/zip/, "tek teslim (ZIP)"],
    [/\/api\/odev\/teslimler\/\w+\/dosya\/\d+/, "tek dosya"],
    [/\/api\/odev\/siniflar\/\w+\/csv/, "sınıf listesi (CSV, kodsuz)"],
    [/\/api\/isler\/\w+\/csv/, "işlem sonuçları (CSV)"],
  ];
  window.PSY_DEMO = {
    indir(url) {
      const bulunan = INDIRME.find(([d]) => d.test(url));
      bildir(`DEMO: indirme simüle edildi — ${bulunan ? bulunan[1] : url}. Gerçek uygulamada dosya iner.`);
    },
  };
  document.addEventListener("click", (o) => {
    const a = o.target.closest && o.target.closest('a[href^="/api/"]');
    if (a) { o.preventDefault(); window.PSY_DEMO.indir(a.getAttribute("href")); }
  }, true);
  document.addEventListener("click", (o) => {
    if (o.target.closest && o.target.closest("#cikis")) {
      o.stopPropagation(); o.preventDefault();
      bildir("DEMO: önizlemede çıkış yapılmaz.");
    }
  }, true);
  const seritOlc = () => {
    const serit = document.querySelector(".demo-serit");
    if (serit) document.documentElement.style.setProperty("--serit", `${serit.offsetHeight}px`);
  };
  window.addEventListener("resize", seritOlc);
  document.addEventListener("DOMContentLoaded", () => {
    seritOlc();
    for (const id of ["pp-pardus", "pp-hp"]) {
      const g = document.getElementById(id);
      if (g) { g.disabled = true; g.placeholder = "DEMO: parola girilmez"; }
    }
    const f = document.getElementById("parola-formu");
    if (f) f.querySelector(".form-izgara").after(Object.assign(document.createElement("p"),
      { className: "uyari-kutusu", textContent: "DEMO: Önizleme gerçek parola istemez ve hiçbir bilgisayara bağlanmaz. Parola alanları kapalıdır." }));
  });
})();
