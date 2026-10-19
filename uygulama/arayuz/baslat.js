/* Başlatıcı: oturum akışı (ilk kurulum / giriş) ve sayfaların kurulumu. En son yüklenir. */
"use strict";

function girisHatasi(mesaj) {
  const kutu = $("#giris-hata");
  kutu.textContent = mesaj;
  kutu.hidden = false;
}

let sayfalarKuruldu = false;

async function uygulamayiAc(bilgi) {
  okulBilgisiniUygula(bilgi.okul);
  ogretmenBilgisiniUygula(bilgi.ogretmen);
  $("#giris-ekrani").hidden = true;
  $("#uygulama").hidden = false;
  $("#surum").textContent = `sürüm ${bilgi.versiyon || ""}`;
  menuKur();
  if (!sayfalarKuruldu) {
    sayfalarKuruldu = true;
    Secim.yukle();
    for (const s of Object.values(SAYFALAR)) if (s.kur) s.kur();
    refRozeti($$("[data-ui-id]"));
    let goster = true;
    try { goster = localStorage.getItem("psy-kodlar") !== "0"; } catch (_) { /* depolama yok */ }
    kodlariGoster(goster);
  } else {
    refRozeti($$("[data-ui-id]"));
  }
  await cihazlariYukle();
  sayfaGoster(location.hash.slice(1) || "M1-S1");
}

function ogretmenCipleriCiz(liste) {
  const kap = $("#giris-ogretmen-cipler");
  if (!kap) return;
  if (!Array.isArray(liste) || !liste.length) {
    kap.hidden = true;
    return;
  }
  kap.replaceChildren(
    el("span", { class: "ipucu", metin: "Hızlı öğretmen seçimi:" }),
    ...liste.map((o) => el("button", {
      type: "button",
      class: "ikincil kucuk",
      onclick: () => {
        $("#giris-kullanici").value = o.kullanici_adi;
        $("#giris-parola").focus();
      },
    }, `${o.ad_soyad} (${o.rol === "admin" ? "Admin" : "Standart"})`))
  );
  kap.hidden = false;
}

async function baslat() {
  const bilgi = await api("/api/oturum");
  Uyg.csrf = bilgi.csrf;
  if (bilgi.okul) okulBilgisiniUygula(bilgi.okul);
  if (bilgi.girisli) { await uygulamayiAc(bilgi); return; }
  $("#uygulama").hidden = true;
  $("#giris-ekrani").hidden = false;
  if (bilgi.kurulum_tamam) {
    $("#giris-formu").hidden = false;
    $("#kurulum-formu").hidden = true;
    ogretmenCipleriCiz(bilgi.ogretmenler_ozet || []);
  } else {
    $("#kurulum-formu").hidden = false;
    $("#giris-formu").hidden = true;
    $("#giris-aciklama").textContent = "İlk kurulum: okul adını, yönetici öğretmeni, kurulum kodunu ve giriş parolasını belirleyin.";
    // Masaüstü simgesi kodu adres parçasıyla (#kod=...) getirir; parça sunucuya gönderilmez.
    const kod = new URLSearchParams(location.hash.slice(1)).get("kod")
      || new URLSearchParams(location.search).get("kod");
    if (kod) $("#kurulum-kodu").value = kod;
  }
}

$("#kurulum-formu").addEventListener("submit", async (o) => {
  o.preventDefault();
  $("#giris-hata").hidden = true;
  const parola = $("#kurulum-parola").value;
  if (parola !== $("#kurulum-parola2").value) { girisHatasi("Parolalar birbirini tutmuyor."); return; }
  try {
    const y = await api("/api/kurulum", {
      kod: $("#kurulum-kodu").value,
      parola,
      kullanici_adi: ($("#kurulum-kullanici") && $("#kurulum-kullanici").value) || "admin",
      ad_soyad: ($("#kurulum-ad") && $("#kurulum-ad").value) || "Sistem Yöneticisi",
      okul_adi: ($("#kurulum-okul") && $("#kurulum-okul").value) || "",
    });
    Uyg.csrf = y.csrf;
    history.replaceState(null, "", "/");
    await baslat();
  } catch (hata) { girisHatasi(hata.message); }
});

$("#giris-formu").addEventListener("submit", async (o) => {
  o.preventDefault();
  $("#giris-hata").hidden = true;
  try {
    const kullanici = ($("#giris-kullanici") && $("#giris-kullanici").value.trim()) || "admin";
    const y = await api("/api/giris", { kullanici_adi: kullanici, parola: $("#giris-parola").value });
    Uyg.csrf = y.csrf;
    $("#giris-parola").value = "";
    await baslat();
  } catch (hata) { girisHatasi(hata.message); }
});

$("#cikis").addEventListener("click", async () => {
  try { await api("/api/cikis", {}); } catch (_) { /* yine de çık */ }
  Uyg.csrf = null;
  Uyg.ogretmen = null;
  try { sessionStorage.removeItem("psy-secim"); } catch (_) { /* yok */ }
  try { history.replaceState(null, "", location.pathname); } catch (_) { /* yok */ }
  location.reload();
});

$("#kod-dugmesi").addEventListener("click", () => kodlariGoster(!kodlarGorunur()));
$("#secim-cipi").addEventListener("click", secimListesiAc);
$("#is-paneli-kapat").addEventListener("click", () => { $("#is-paneli").hidden = true; });
$("#is-paneli-iptal").addEventListener("click", async () => {
  if (!izlenen) return;
  try { const s = await api(`/api/isler/${izlenen.id}/iptal`, {}); bildir(s.not); } catch (hata) { bildir(hata.message, true); }
});
$("#is-paneli-ayrinti").addEventListener("click", () => {
  const id = izlenen ? izlenen.id : sonIs;
  git("M4-S1");
  if (id) setTimeout(() => m4s1.ayrinti(id), 50);
  else m4s1.yukle();
});

baslat().catch((hata) => {
  girisHatasi(`Uygulamaya ulaşılamıyor: ${hata.message}`);
  $("#giris-ekrani").hidden = false;
});
