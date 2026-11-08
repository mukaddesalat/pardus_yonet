# Arayüz sadeleştirme yol haritası ve Komut Mağazası tasarımı

Analiz raporu · 8 Kasım 2026 · Kaynak: `Desktop/arayuz-onizleme.html` (demo, 0.6.0 + taslak
eklemeler) ve `uygulama/arayuz/referans.js`

> Bu belge bir karar önerisidir. Hiçbir kod değişmedi. Sayfa ve düğme kodları (M/S/B) kuraldaki
> gibi sabit kalır; aşağıdaki öneriler yalnız **gruplama, görünürlük ve sıra** üzerinedir.

---

## 1. Durum tespiti: demo neden karmaşık hissettiriyor?

Masaüstündeki demo, depodaki 0.6.0 önizlemesinden yaklaşık %47 daha büyük. Eklenen taslak
özellikler (Komut Gönder, Yazılım Merkezi, Sistem Yedeği/Taşıma, Okul Kimliği, Öğretmen
hesapları, Sınıf Masası hızlı eylemleri) hepsi **aynı görünürlük seviyesinde** sunulmuş. Sorun
özelliklerin çokluğu değil, hepsinin aynı anda "bağırması".

Demo menüsünün bugünkü hali:

| Bölüm | Menü öğesi | Sayfa sayısı | Gözlem |
| --- | --- | --- | --- |
| Günlük ders akışı | Sınıf Masası | 1 | 6 eylem kartı + envanter çekmecesi + filtreler + tablo aynı ekranda |
| | Ödev & Dosya Dağıt | 2 | İyi; iki kavram ama ilişkili |
| | Bakım, Görünüm & Güç | 5 | Başlıkta üç kavram; "&" bölünemediğinin işareti |
| | Komut Gönder | 1 | Kütüphane + hosts formu + editör + canlı log tek sayfada |
| | İşlem Geçmişi | 1 | İyi |
| Yönetici & Kurulum | Kurulum, Okul & Öğretmen | 5 | Bir kez yapılan işler ile sürekli ayarlar karışık |

Somut belirtiler:

1. **Menü etiketleri uzun ve çoklu.** "Bakım, Görünüm & Güç", "Kurulum, Okul & Öğretmen". Bir
   öğretmen "duvar kâğıdını nereden değiştiririm?" sorusunu bu etiketlerden kestiremez.
2. **Sayfa = özellik yığını.** M5-S1'de yedek oluştur, yedekten dön, terminal komutu ve arşiv
   listesi alt alta. M2-S6'da dört ayrı iş tek sayfada. Her sayfa "bir iş" olmalı.
3. **Rol ile uzmanlık karışmış.** `yalnizAdmin` bayrağı yetki (kim yapabilir) sorusunu çözüyor,
   ama "deneyimli öğretmen ayrıntı görmek istiyor" sorusuna cevap yok. İkisi ayrı eksendir.
4. **Sınıf Masası iki iş yapıyor.** Ders anında kullanılan kontroller ile envanter yönetimi
   (ekle/çıkar/içe aktar/Ansible indir) aynı ekranda. Envanter işi haftada bir, kontroller her
   ders yapılır.
5. **Simge dili tutarsız.** Emoji kullanımı DESIGN.md'deki `IKONLAR` setiyle çelişiyor; emoji
   platforma göre farklı çizilir, renk belirteçlerine uymaz.
6. **Referans kodları tamamen gizlendi** (`.ref { display:none }`). Destek için kodlar değerli;
   gizlemek yerine varsayılan kapalı, ayardan açılır olmalı (M0-S1-B1 zaten var).
7. **Kurulum menüde kalıcı.** "İlk Hazırlık", "Ağda Bul" gibi bir kez yapılan işler, her gün
   görünen menüde yer kaplıyor.

İyi olanlar, korunmalı: M1-S2'deki "üç adım + Teknik ayrıntı katlanır bölüm" örüntüsü,
önizle → kesin hedef listesi → onayla akışı (M0-S3), tek birincil düğme kuralı, iş durumu
paneli, lab seçici ve seçim çipi.

---

## 2. Yazılım dünyasında bu sorunun bilinen çözümü

Bu sorun "feature creep" sonrası klasik bilgi mimarisi (IA) sorunudur. Olgun ürünlerin
izlediği yol haritası şu beş ilkeye dayanır:

### 2.1 Kademeli açığa çıkarma (progressive disclosure)

Nielsen Norman Group'un en çok atıf alan ilkesi. Kullanıcıya önce **en sık ve en güvenli**
işlemleri göster; nadir ve riskli olanları bir adım geride tut. Üç katman yeterlidir:

| Katman | Ne | Kim görür | Örnek |
| --- | --- | --- | --- |
| 0 · Ana ekran | Her ders yapılan 4–6 iş | Herkes | Ekranı kilitle, duyuru, ders sonu temizliği |
| 1 · Menü | Görev grupları, en fazla 5–7 öğe | Herkes (yetkiye göre süzülür) | Ödevler, Bakım, Geçmiş |
| 2 · Sayfa içi "Gelişmiş" | Teknik ayrıntı, nadir seçenekler | Gelişmiş görünüm açık olanlar | Sudo yöntemi, dconf anahtarı, ham çıktı |

Örnekler: GNOME Ayarlar (sık olanlar üstte, "Hakkında" en altta), VS Code Ayarlar ("Commonly
Used" bölümü), Home Assistant (profilde tek "Gelişmiş mod" anahtarı), Proxmox ve Synology
DSM (basit sihirbaz, "Gelişmiş" katlanır).

### 2.2 Görev odaklı menü, özellik odaklı değil

Menü, yazılımın modüllerini değil kullanıcının **o anki niyetini** yansıtmalı. "Veyon
Ayarları" bir modül adıdır; "Öğrenci ekranlarını izle" bir niyettir. Test yöntemi: beş
öğretmene 10 görev yazdırıp "bunu hangi menüde ararsın?" diye sormak (card sorting ve tree
testing). Beş kişi, hataların %80'ini ortaya çıkarır.

### 2.3 Yetki ve uzmanlık iki ayrı eksen

| | Standart görünüm | Gelişmiş görünüm |
| --- | --- | --- |
| **Öğretmen** | Günlük işler, sade sayfalar | Aynı sayfalar + teknik ayrıntı bölümleri açık |
| **Yönetici** | Günlük işler + Kurulum menüsü | Her şey + Komut Mağazası yönetimi + ham çıktılar |

- **Yetki** (rol) sunucuda doğrulanır ve menüyü **siler**; M5-S2'deki yetki şablonu bu eksen.
- **Uzmanlık** (görünüm modu) yalnız istemci tarafında **katlar/açar**, kullanıcı başına
  kalıcıdır, üst çubuktaki kullanıcı menüsünden tek anahtarla değişir. Gizlenen şey
  erişilebilir kalır; sadece bir tık uzaktadır.

Yaygın hata, gelişmiş modu ayrı bir menü yapmaktır. Doğrusu, aynı sayfanın altında
`<details>` ile açılan "Gelişmiş" bölümüdür. Kullanıcı yer değiştirmez, zihinsel haritası
bozulmaz.

### 2.4 Hick yasası ve etiket disiplini

Seçenek sayısı arttıkça karar süresi logaritmik büyür. Pratik sınırlar:

- Yan menüde 5–7 öğe, her öğede en fazla 5 alt sayfa.
- Etiket: **tek kavram, en fazla iki kelime, "&" yok.** Alt açıklama (gri küçük yazı) yerine
  üzerine gelince ipucu.
- Sayfa başlığı fiil + nesne: "Bilgisayarları Hazırla" iyi, "Sistem, Yedekleme ve Başka
  Bilgisayara Taşıma" kötü.

### 2.5 Sihirbaz, komut paleti ve "boş durum"

- Bir kez yapılan işler menüde değil **ilk kurulum sihirbazında** yaşar. Sonra menüde yalnız
  "Kurulum eksik: 3 bilgisayar hazırlanmadı" gibi bir rozet kalır.
- Uzman kullanıcı için **komut paleti (Ctrl+K)**: her sayfa, düğme ve mağaza aracına yazarak
  ulaşılır. Menü sadeleşirken hız kaybolmaz. M/S/B kodları paletten de aranabilir
  ("M2-S5" yazınca Zamanlı Kapatma açılır).
- Boş sayfa (hiç bilgisayar yok, hiç ödev yok) tablo yerine "ilk adımı" gösterir.

---

## 3. Önerilen menü tasarımı

### 3.1 Yeni yan menü (standart öğretmen, standart görünüm)

```
┌─────────────────────────────┐
│ [logo] Okul adı             │
│        Lab Kaptanı          │
├─────────────────────────────┤
│ 🖥  Sınıf Masası            │  ← açılış sayfası; ders anı
│ 📚  Ödevler                 │  ← Teslimler · Sınıflar ve Kodlar
│ 🧹  Bakım                   │  ← Ders Sonu Temizliği · Güç ve Uyku · Zamanlı Kapatma
│ 📋  Geçmiş                  │
├─────────────────────────────┤
│ ⚙   Ayarlar                 │  ← görünüm, parola, destek kodları
└─────────────────────────────┘
```

### 3.2 Gelişmiş görünüm açıkken eklenenler

```
│ 🧰  Araç Kutusu             │  ← Komut Mağazası · Yazılım Kurulumu · Masaüstü Görünümü
```

Araç Kutusu, standart görünümde gizlidir çünkü sistem değiştiren işler barındırır. Öğretmen
"Gelişmiş görünüm"ü açınca belirir; yetkisi yoksa içindeki kartlar "yönetici izni gerekir"
notuyla pasif görünür (gizlenmez, çünkü neden göremediğini anlamalı).

### 3.3 Yönetici için eklenen bölüm

```
├─ YÖNETİM ───────────────────┤
│ 🏫  Okul ve Öğretmenler     │  ← M5-S2
│ 🔑  Bilgisayar Kurulumu     │  ← sihirbaz: Ağda Bul → Hazırla → Veyon (M1-S3, M1-S2, M1-S4)
│ 💾  Yedek ve Taşıma         │  ← M5-S1
│ 🏪  Mağaza Yönetimi         │  ← katalog kaynağı, kanal, kurulu araç sürümleri
```

"Bilgisayar Kurulumu" tek giriş noktasıdır ve içinde sekmeli ya da adımlı üç sayfa vardır.
Kurulum tamamsa yeşil onay, eksikse "2 bilgisayar hazırlanmadı" rozeti gösterir.

### 3.4 Eski → yeni eşleme (kodlar değişmez)

| Kod | Eski yeri | Yeni yeri | Görünürlük |
| --- | --- | --- | --- |
| M1-S1 | Sınıf Masası | Sınıf Masası (envanter araçları "Bilgisayarları yönet" alt sayfasına) | Herkes |
| M1-S2, M1-S3, M1-S4 | Kurulum, Okul & Öğretmen | Yönetim → Bilgisayar Kurulumu (sihirbaz) | Yönetici |
| M2-S1, M2-S4, M2-S5 | Bakım, Görünüm & Güç | Bakım | Herkes |
| M2-S2, M2-S3 | Bakım, Görünüm & Güç | Araç Kutusu | Gelişmiş görünüm |
| M2-S6 | Komut Gönder | Araç Kutusu → Komut Mağazası (yeniden tasarlanır, §4) | Gelişmiş + yetki |
| M3-S1, M3-S2 | Ödev & Dosya Dağıt | Ödevler | Herkes |
| M4-S1 | İşlem Geçmişi | Geçmiş | Herkes |
| M5-S1 | Kurulum, Okul & Öğretmen | Yönetim → Yedek ve Taşıma | Yönetici |
| M5-S2 | Kurulum, Okul & Öğretmen | Yönetim → Okul ve Öğretmenler | Yönetici |

Sonuç: standart öğretmen menüde **5 öğe** görür (bugün 6 öğe, 15 sayfa). Yönetici gelişmiş
görünümde 10 öğe görür ama iki bölüme ayrılmış halde.

### 3.5 Her sayfa için tek şablon

Her sayfa aynı iskelete oturursa kullanıcı ikinci sayfada ne bekleyeceğini bilir:

1. **Başlık + bir cümle** (ne yapar, kime yapar).
2. **Birincil eylem kartı** (tek mavi düğme; gerekiyorsa 2–3 alan).
3. **Hedef / durum tablosu** (lab seçici ve seçim çipi ortak).
4. **Gelişmiş** (katlanır; yalnız gelişmiş görünümde açık gelir, standartta kapalı gelir).
5. **Tehlikeli bölge** (en altta, kırmızı çerçeve, ayrı onay kutusu). Örnek: "Yedekleri sil",
   "Anahtarı iptal et".

M5-S1 bu şablona göre: birincil = "Yedek oluştur ve indir"; tablo = arşivdeki yedekler;
gelişmiş = terminal komutu ve `yedekten-kur.sh`; tehlikeli = geri yükle.

### 3.6 Sınıf Masası'nın sadeleşmesi

Ders anı ekranıdır; başka hiçbir şey olmamalı:

- Üstte 6 hızlı eylem kartı (mevcut tasarım iyi). Yönetici, kartlardan birini Komut
  Mağazası'ndaki bir araçla değiştirebilir ("sabitle", §4.7).
- Altında ekran kutucukları / liste geçişi ve filtreler.
- "Bilgisayar ekle, içe aktar, çıkar, Ansible indir" → sağ üstte tek "Bilgisayarları yönet"
  düğmesiyle açılan alt sayfaya taşınır. Kodlar aynı kalır (M1-S1-B1…B5).

### 3.7 Küçük ama etkili kurallar

- Emoji yerine `IKONLAR` seti; emoji yalnız demo verisi ve öğrenci portalında kalabilir.
- Sayfa başlığında M/S kodu, yalnız "Destek kodlarını göster" açıkken (M0-S1-B1 korunur).
- Alt başlık metinleri menüden kalkar, ipucuna taşınır.
- Menü öğesi sırası sıklığa göre: her ders → her hafta → bir kez.
- Her ayar sayfasında "Varsayılana dön" ikincil düğme olarak bulunur.

### 3.8 Geçiş planı

| Adım | İş | Kodlara etkisi |
| --- | --- | --- |
| 1 | 10 görevlik kart sıralama testi, 5 öğretmen (1 saat) | Yok |
| 2 | `referans.js` menü nesnesine `grup`, `gorunurluk` (herkes / gelismis / yonetici) ve `sira` alanları | Yok (yalnız ek alan) |
| 3 | Yan menü üreticisinin yeni alanlara göre çizmesi; kullanıcı başına "Gelişmiş görünüm" anahtarı (`ayarlar.py`) | Yok |
| 4 | Sayfaların §3.5 şablonuna göre yeniden dizilmesi; ikon dönüşümü | Yok (B kodları yer değiştirir, numarası değişmez) |
| 5 | Bilgisayar Kurulumu sihirbazı (M1-S3 → M1-S2 → M1-S4 akışı tek kabukta) | Yok |
| 6 | Komut paleti (Ctrl+K) | Yeni M0-S6 sayfası |
| 7 | Ağaç testi tekrarı; başarı ölçütü: görevlerin %80'i ilk denemede doğru menüden bulunur | — |

---

## 4. Komut Mağazası tasarımı

### 4.1 Kavram ve adlandırma

Son kullanıcı "kod" ya da "betik" kelimesini sevmez; "araç" der. Önerilen adlar:

- **Mağaza**: katalogdaki indirilebilir araçlar.
- **Araçlarım**: bu öğretmen bilgisayarına kurulmuş araçlar (bugünkü "Kayıtlı Komut
  Kütüphanesi"nin yerini alır).
- **Araç**: parametreli, açıklamalı, imzalı bir shell betiği paketi.

M2-S6'daki her şey bu modele dönüşür. "Hosts kaydı ekle" ve "Veyon servisini aç" ilk iki
mağaza aracı olur; serbest bash editörü yalnız gelişmiş görünüm + yönetici için "Yeni araç
taslağı" sayfasında kalır.

### 4.2 Araç paketi biçimi

Bir dizin = bir araç. Git deposunda `araclar/<id>/` altında:

```
araclar/kullanici-ev-dizini-sil/
├── arac.yaml        # manifest (zorunlu)
├── calistir.sh      # asıl betik (zorunlu)
├── kontrol.sh       # kuru çalıştırma / önizleme: ne değişecek? (önerilir)
├── geri-al.sh       # geri alma (isteğe bağlı; varsa "geri alınabilir" rozeti)
├── README.md        # mağaza detay sayfasında gösterilen uzun açıklama
└── ikon.svg         # isteğe bağlı
```

Örnek manifest (kullanıcının verdiği "ev dizini sil" senaryosu):

```yaml
sema: 1
id: kullanici-ev-dizini-sil
ad: Kullanıcı ve ev dizinini sil
surum: 1.2.0
ozet: Verilen yerel kullanıcıyı ve /home altındaki dizinini kaldırır.
kategori: kullanici            # kullanici | ag | sistem | paket | veyon | gorunum | bakim
yazar: "Ad Soyad <eposta>"
lisans: GPL-3.0-or-later
risk: yikici                   # bilgi | degisiklik | yikici
sudo: true
geri_alinabilir: false
sure_tahmini_sn: 5
hedef_os:
  - pardus-23
  - pardus-25
hedef_os_disi: [eba-etap]      # korunan cihazlar her durumda kapsam dışı
masaustu: [gnome, herhangi]
gereksinimler:
  paketler: []                 # apt paket adları; yoksa kontrol.sh "ön koşul yok" döner
degistirdigi_yollar:
  - /home/{kullanici}
  - /etc/passwd
parametreler:
  - ad: kullanici
    etiket: Silinecek kullanıcı adı
    tip: kullanici_adi         # metin | sayi | secim | onay | kullanici_adi | dizin | ip | alan_adi | dosya
    zorunlu: true
    dogrulama: "^[a-z_][a-z0-9_-]{0,31}$"
    yasak: [root, pardus, hp, ogrenci]
    ornek: ali
    aciklama: Sistem ve yönetim hesapları seçilemez.
  - ad: yedek_al
    etiket: Silmeden önce ev dizinini arşivle
    tip: onay
    varsayilan: true
cikti:
  bicim: psy-satir             # §4.4
degisiklikler:
  - "1.2.0: yedek_al parametresi eklendi"
  - "1.0.0: ilk sürüm"
```

Manifest JSON Schema ile doğrulanır; şema hem CI'da hem uygulamada aynı dosyadır.

### 4.3 Parametrelerin betiğe güvenli aktarımı

Komut satırına metin birleştirerek **asla** gönderilmez; bu kök yetkili bir ortamda komut
enjeksiyonu demektir. Kural:

- Uygulama her parametreyi manifestteki `tip` ve `dogrulama` ile doğrular; `yasak`
  listesini uygular; `kullanici_adi`, `dizin`, `ip`, `alan_adi` tiplerinin yerleşik
  doğrulayıcıları vardır.
- Betiğe **ortam değişkeni** olarak verilir: `PSY_P_KULLANICI=ali`, `PSY_P_YEDEK_AL=1`.
  Ayrıca `PSY_ARAC_ID`, `PSY_ARAC_SURUM`, `PSY_HEDEF_OS`, `PSY_KURU=1` (önizleme) sabit
  değişkenleri gelir.
- Betik standart başlıkla başlar; CI bunu zorunlu tutar:

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${PSY_P_KULLANICI:?kullanici parametresi gerekli}"
```

- Mevcut altyapı buna hazır: `ssh_araclari.sudo_betik` bugün Python betiği + JSON parametre
  gönderiyor. Bash için aynı yol, `bash -s` ile stdin'den betik ve `env -i` ile temiz ortam.
  Uzak tarafa dosya yazılmaz.

### 4.4 Çıktı sözleşmesi: uygulamanın betiği "anlaması"

Betik stdout'a serbest yazabilir, ama uygulamanın parse ettiği satırlar `::psy:` önekiyle
başlar:

```
::psy:ilerleme=30
::psy:bilgi=ali kullanıcısının 2,3 GB verisi /var/yedek/ali-2026-11-08.tar.gz dosyasına alındı
::psy:degisti=/home/ali
::psy:sonuc=ok
```

Çıkış kodları standardı:

| Kod | Anlam | Arayüzde |
| --- | --- | --- |
| 0 | Yapıldı | Yeşil |
| 10 | Zaten yapılmıştı, atlandı (idempotent) | Gri "değişiklik yok" |
| 20 | Ön koşul yok (OS uyumsuz, paket eksik) | Sarı, nedenle |
| 30 | Parametre reddedildi (betik içi ek kontrol) | Sarı |
| 1 | Hata | Kırmızı, stderr son 20 satır |

Böylece canlı log tablosu ham metin yerine bilgisayar başına "durum, mesaj, değişen yollar"
gösterir; ham çıktı "Gelişmiş" altında kalır. `kontrol.sh` aynı sözleşmeyle "ne olacak"
satırları döner ve mevcut önizleme penceresine (M0-S3) beslenir.

### 4.5 Depo, doğrulama ve yayın akışı

Ayrı bir GitHub deposu: örneğin `lab-kaptani-magaza`. Akış:

```
Katkıcı                  GitHub                              Öğretmen PC
───────                  ──────                              ───────────
araç dizini + PR  ──►   CI doğrulama:                        
                         • arac.yaml JSON Schema              
                         • shellcheck (hata = red)            
                         • yasak kalıp taraması               
                           (rm -rf /, dd, mkfs, curl|bash,    
                           eval, base64 -d|sh)                
                         • parametre tutarlılığı              
                           (manifestteki her parametre        
                           betikte kullanılıyor mu)           
                         • debian:12 ve Pardus 25 taban       
                           imajında kuru çalıştırma           
                   ──►  gözden geçirme (siz) → birleştir      
                   ──►  yayın işi:                             
                         • katalog.json (tüm araçların özeti)  
                         • <id>-<surum>.tar.gz + .sha256       
                         • minisign/age imzası (özel anahtar   
                           yalnız sizde)                        
                                                        ◄──  Mağaza "Yenile": katalog.json
                                                             indir, imzayı gömülü açık
                                                             anahtarla doğrula, listele
                                                        ◄──  "Kur": tar.gz indir, sha256 +
                                                             imza doğrula, Araçlarım'a ekle
```

Kararlar:

- **İmza zorunlu.** Parolasız sudo ile çalışan ortamda mağaza tedarik zincirinin en zayıf
  halkasıdır. Uygulama imzasız veya imzası bozuk aracı listelemez bile. Açık anahtar `.deb`
  içinde gömülü gelir; değiştirilebilir ama yalnız yönetici ve uyarıyla.
- **Katalog kaynağı sabit ve tek.** Varsayılan GitHub Pages/Releases adresi; yönetici
  "Mağaza Yönetimi"nden değiştirebilir (okul içi ayna için).
- **Çevrimdışı yol.** Lab internete çıkmayabilir: tüm mağazanın `.zip` paketi indirilip
  M1-S4'teki Veyon .deb yükleme örüntüsüyle elle yüklenebilir. Aynı imza doğrulaması geçer.
- **İki kanal:** `kararli` ve `test`. Test kanalı yalnız gelişmiş görünümde seçilebilir.
- **Sürüm politikası:** semver; "Güncelle" yalnız ileri sürüme; düşürme yok (Veyon kararıyla
  tutarlı).
- **Katkı şablonu:** depoda `araclar/_sablon/` ve `KATKI.md`. Uygulamadaki "Yeni araç
  taslağı" sayfası formu doldurtup `arac.yaml` + `calistir.sh` içeren zip üretir ve PR adımını
  anlatır. Katkıcı GitHub bilmiyorsa zip'i e-posta ile gönderir, siz PR açarsınız.

### 4.6 Arayüz: Mağaza, Araçlarım, Çalıştır

**Mağaza (katalog)**: kart ızgarası. Her kartta ikon, ad, tek cümle özet, risk rozeti
(bilgi / değişiklik / yıkıcı), hedef OS rozetleri (Pardus 23 · 25), sürüm ve "Kur" ya da
"Güncelle" düğmesi. Üstte kategori sekmeleri ve arama. Yönetici dışı kullanıcı "Kur"u göremez.

**Araç detayı**: README, parametre tablosu (etiket, tip, varsayılan, açıklama), değiştirdiği
yollar, gereksinimler, sürüm geçmişi, yazar, lisans. Gelişmiş görünümde "Betiği görüntüle"
(salt okunur, vurgulu) ve imza/özet bilgisi.

**Araçlarım**: kurulu araçlar listesi; sürüm, son çalıştırma, "güncelleme var" rozeti,
"Sınıf Masası'na sabitle", "Kaldır".

**Çalıştır** akışı (mevcut örüntülerle birebir):

1. Araç seçilir → parametre formu **manifestten otomatik üretilir** (tip → alan: onay kutusu,
   açılır liste, metin, kullanıcı adı seçici). Yanlış girdi anında kırmızı açıklamayla
   reddedilir.
2. Hedef seçimi: ortak seçim çipi ve lab seçici. Manifestteki `hedef_os` ile uyuşmayan ve
   korunan bilgisayarlar **kapsam dışı listesine** nedeniyle düşer (bugünkü M0-S3 davranışı).
3. "Önce göster": `kontrol.sh` varsa her hedefte kuru çalıştırılır; sonuç onay penceresinde
   "LAB07'de /home/ali yok, atlanacak" gibi satırlarla görünür.
4. Onayla ve başlat → iş paneli (M0-S4) → canlı tablo (§4.4 ile parse edilmiş).
5. Geçmiş (M4-S1) kaydına araç id, sürüm, parametre değerleri (gizli tipli parametreler
   maskeli), hedef listesi ve bilgisayar başına çıkış kodu yazılır.

### 4.7 Yetki ve görünürlük

| Risk | Standart öğretmen | Yönetici izin verirse | Yönetici |
| --- | --- | --- | --- |
| bilgi (salt okunur) | Çalıştırır | — | Çalıştırır |
| degisiklik | Yalnız sabitlenmiş ön ayarları | Tümünü | Tümünü |
| yikici | Hayır | Sabitlenmiş ön ayarı | Tümünü |

**Sabitleme / ön ayar (preset):** yönetici bir aracı parametreleri doldurulmuş ve kilitlenmiş
halde "Ders sonu: misafir hesabını temizle" adıyla Sınıf Masası kartına dönüştürür. Standart
öğretmen tek tıkla çalıştırır, parametreleri göremez. Mağaza böylece yalnız yöneticinin değil,
öğretmenin günlük işine de hizmet eder. M5-S2'deki yetki şablonuna "Komut Mağazası: ön ayar /
tümü / kapalı" seçeneği eklenir.

### 4.8 Güvenlik notları (SECURITY.md'ye eklenecek)

- Mağaza aracı = kök yetkili kod. İmza doğrulaması atlanamaz; "yine de kur" seçeneği yoktur.
- Betikler ağa çıkamaz varsayımı yoktur; ancak CI `curl|bash` tarzı indir-çalıştır kalıplarını
  reddeder. Paket kurulumu yalnız `apt-get` ile ve manifestte beyan edilmiş paketlerle.
- Her çalıştırma denetim kaydına yazılır; kayıt silinemez (M4-S1 zaten böyle).
- Parametre tipleri allowlist mantığıyla çalışır; serbest metin tipi için manifestte
  `dogrulama` zorunludur, yoksa CI reddeder.
- Hedef OS dışı bilgisayara gönderim uygulama tarafında engellenir; betiğe güvenilmez.

### 4.9 Benzer modeller (ilham)

Home Assistant HACS (topluluk deposu + manifest), Proxmox VE Helper-Scripts (GitHub'da açık
betikler, web katalog), Ansible Galaxy (rol meta verisi, platform listesi), Nextcloud App Store
(imzalı paket, sürüm uyumu), VS Code uzantı manifesti (`package.json` contributes), Debian
`debian/control` (bağımlılık ve açıklama alanları). Önerilen biçim bunların kesişimidir:
manifest + betik + imza + katalog indeksi.

### 4.10 Mağaza geçiş planı

| Faz | İçerik |
| --- | --- |
| A | `arac.yaml` JSON Schema, 3 örnek araç (hosts ekle, Veyon servisini aç, kullanıcı sil), CI (schema + shellcheck + yasak kalıp) |
| B | Uygulamada çevrimdışı yükleme + Araçlarım + parametre formu + çıktı parse; serbest bash editörü yönetici/gelişmiş'e taşınır |
| C | Katalog indirme, imza doğrulama, güncelleme, kanallar |
| D | Ön ayar/sabitleme, Sınıf Masası kartı, yetki şablonu |
| E | "Yeni araç taslağı" üreticisi, KATKI.md, topluluk duyurusu |

---

## 5. Ek özellik önerileri (sınav modülü hariç)

Öncelik sırasına göre. "Küçük" olanlar bir sürüme sığar.

### Hemen değer katanlar

1. **İlk kurulum sihirbazı.** Okul adı → ağda bul → hazırla → Veyon → öğretmen hesapları →
   bitti. Menüden kurulum sayfaları kalkar; eksik varsa rozet. (§3.3)
2. **Komut paleti (Ctrl+K).** Sayfa, düğme, araç ve M/S/B kodu araması. Uzman için hız,
   yeni kullanıcı için keşif.
3. **Ders profilleri (tek tık senaryolar).** "Ders başlıyor" (ekran aç, internet açık,
   portal masaüstüne), "Sunum" (ekran kilidi + öğretmen ekranı), "Ders bitti" (temizlik +
   uyku kilidi + 10 dk sonra kapat). Mevcut işlemlerin sıralı demeti; Komut Mağazası ön
   ayarlarını da içerebilir. Küçük.
4. **Sağlık panosu.** Sınıf Masası'nın üstünde tek satır: disk doluluk uyarısı, Veyon servisi
   kapalı, güncelleme bekleyen, saat kayması. Salt okunur `durum.py` zaten veriyi topluyor.
5. **Yerinde yardım.** Her sayfa başlığında "?" → iki cümle + ilgili kılavuz bölümüne
   bağlantı. İlk açılışta 5 adımlık tur (coach marks). Küçük.

### Bir sonraki sürümlerde

6. **Ders zili / zaman çizelgesi.** Haftalık ders programı girilir; "Ders bitti" profili ve
   zamanlı kapatma programdan beslenir. M2-S5'in doğal uzantısı.
7. **Geri alma merkezi.** Yedekten dön, Veyon ayarlarını geri yükle, görünümü varsayılana
   döndür, araç `geri-al.sh` çalıştır: tek sayfa, tek liste. Güven artırır.
8. **Otomatik sistem yedeği.** M5-S1 yedeğini haftalık alıp son 4'ü tutma; "son yedek 12 gün
   önce" uyarısı.
9. **Uygulama güncelleme denetimi.** GitHub Releases'tan yeni `.deb` var mı; indir, sha256
   doğrula, kurulum komutunu göster (otomatik kurmaz).
10. **Destek paketi dışa aktar.** Hata durumunda günlükler, sürüm, M/S/B kodları ve envanter
    özeti tek zip; kişisel veri maskeli. Açık kaynak kullanıcıları için issue açmayı
    kolaylaştırır.
11. **USB depolama kısıtı ve web engelleme listesi.** İnternet kısıtının yanına; her ikisi
    Komut Mağazası aracı olarak gelebilir, çekirdeğe girmesi gerekmez.
12. **Erişilebilirlik ve görünüm.** Yazı boyutu, yüksek karşıtlık, koyu tema. Projektörde
    öğretmen ekranı gösterilirken yazı boyutu özellikle önemli.
13. **Aylık özet raporu.** Kaç ders, kaç temizlik, kaç teslim; PDF/CSV. İdareye gösterilebilir.

### Yapılmaması önerilenler

- **Serbest bash editörünü standart öğretmene açmak.** Mağaza + ön ayar modeli bu ihtiyacı
  güvenli biçimde karşılar.
- **Her yeni özelliği yeni menü öğesi yapmak.** Yeni özellik önce "hangi görev grubunun altına
  girer, hangi katmanda yaşar" sorusuna cevap vermeli. Cevap yoksa Komut Mağazası aracı olmalı,
  çekirdek değil.
- **Telemetri.** Okul ortamında güven kaybettirir; destek paketi (madde 10) yeterlidir.

---

## 6. Özet karar listesi

1. Menü: 5 öğe standart, +1 gelişmiş görünüm, +4 yönetim bölümü. Etiketler tek kavram.
2. Yetki (rol, sunucu) ve uzmanlık (görünüm, istemci) ayrı eksen; gelişmiş içerik sayfa içinde
   katlanır, ayrı menü olmaz.
3. Her sayfa aynı şablon: başlık · birincil eylem · tablo · gelişmiş · tehlikeli bölge.
4. Bir kez yapılan işler sihirbaza; menüde yalnız rozet.
5. Komut Gönder → Komut Mağazası: manifest + betik + imza + katalog; parametreler ortam
   değişkeniyle, çıktı `::psy:` sözleşmesiyle; hedef OS ve risk rozetleri; ön ayarla Sınıf
   Masası'na sabitleme.
6. M/S/B kodları hiç değişmez; `referans.js`'e yalnız gruplama ve görünürlük alanları eklenir.
