# Lab Kaptanı — İlk Kullanım 101

Bu kılavuz, teknik bilgisi olmayan öğretmenler içindir. Birkaç adımda
laboratuvarınızı yönetmeye başlarsınız. Ekrandaki her menü, sayfa ve düğmenin
küçük mor bir kodu vardır (ör. **M1-S2-B3**); yardım isterken bu kodu söylemeniz
yeterlidir. Kodları sağ üstteki **Kodları gizle** düğmesiyle gizleyebilirsiniz.

## 0. Kurulum (bir kez)

Size verilen `.deb` dosyasının bulunduğu klasörde bir terminal açıp şunu yazın
(yönetici parolanız sorulur):

```bash
sudo dpkg -i pardus-sinif-yonetimi_0.6.0_amd64.deb
```

İnternet gerekmez; kurulum bitince uygulama çalışır ve bilgisayar her açıldığında
kendiliğinden başlar.

## 1. Uygulamayı açın

Masaüstündeki **Pardus Sınıf Yönetimi** simgesine tıklayın. İlk açılışta kendinize
bir **uygulama giriş parolası** belirleyin (en az 8 karakter). Bu parola yalnız bu
uygulamaya girmek içindir; öğrenci bilgisayarlarının parolası değildir.

## 2. Bilgisayarları envantere ekleyin — M1 Envanter

Üç yol vardır; hiçbiri öğrenci bilgisayarında bir şey değiştirmez:

- **M1-S3 Ağda Bul:** **B7** ile önerilen ağı yazın, **B1 Taramayı başlat** deyin.
  Bulunanların parmak izlerini kontrol edip seçin ve **B3 Envantere ekle ve hazırla**'ya
  tıklayın (hazırlık için 3. adıma bakın).
- **M1-S1-B1 Bilgisayar ekle:** IP adresini ve isterseniz görünen adı yazın.
- **M1-S1-B2 Dosyadan içe aktar:** sistem yöneticinizin Ansible envanter dosyası
  veya `ad;ip;hesap;laboratuvar` satırlı bir CSV. Önce önizlenir.

Etkileşimli tahta gibi **dokunulmaması gereken** cihazları düzenle penceresinde
**Korunan cihaz (EBA/ETAP)** olarak işaretleyin; hiçbir işleme dahil edilmezler.

## 3. Bir kez hazırlayın — M1-S2 Bilgisayarları Hazırla

1. Bilgisayarları seçin (seçim çubuğu: **Laboratuvardaki tüm uygun bilgisayarları seç**).
2. **B1 Sunucu kimliklerini oku**, ardından **B2 Kimlikleri onayla**. Bu, karşıdaki
   bilgisayarın gerçekten sizin laboratuvarınıza ait olduğunu doğrulamak içindir.
3. **B3 Hazırlığı başlat:** öğrenci bilgisayarlarındaki **pardus** ve/veya **hp**
   hesabının parolasını bir kez yazın. Uygulama her bilgisayara kendi güvenli
   anahtarını kurar, yönetim hesabına parolasız yetki verir ve gerekirse **ogrenci**
   hesabını oluşturur. Parola kaydedilmez.

Bundan sonra günlük işlerde **hiç parola sorulmaz**. Bilgisayarda hem hp hem pardus
varsa tablo “tekilleştirin” der: **B4 Tekilleştirmeyi önizle**, korunacak hesabı seçin
(öneri: pardus), **B5 Tekilleştirmeyi uygula**. Diğer hesap önce yedeklenir.

## 3b. Veyon (isteğe bağlı) — M1-S4 Veyon Ayarları

1. **B1 Veyon paketini yükle:** `veyon_<sürüm>_amd64.deb` dosyasını seçin. Yalnız
   gerçek Veyon paketi kabul edilir; yüklemek kurulum başlatmaz.
2. **B4 Public key yükle:** Veyon'un *public* anahtar dosyası (`…_public_key.pem`).
   **B5** anahtar adı, sizin bilgisayarınızdaki private key'in adıyla aynı olmalıdır.
   Private key istenmez; yanlışlıkla seçerseniz reddedilir ve saklanmaz.
3. **B7 Öğretmen PC'yi denetle:** sorun varsa ne yapılacağı yazılır.
4. Bilgisayarları seçip **B11 Kur ve yapılandır**: önizlemede mevcut ve kurulacak
   sürümü, uygulanacak ayarları görürsünüz; onaylayınca kurulum ve ayar yapılır.
   Aynı sürüm yeniden kurulmaz, eski sürüme düşürme yapılmaz.
5. **B12 Bağlantıyı doğrula** ile sonucu görün; Veyon Master'dan bağlanın.

Geri almak için **B14 Önceki ayarları geri yükle**. Kurulu sürümler M1-S1 tablosundaki
“Veyon sürümü” sütununda da görünür; **B13 Sürümleri yenile** yalnız envanteri sorgular.

## 3c. Ekranlar ne anlatıyor? — M1-S1

Her bilgisayar bir ekran olarak görünür. **Yeşil ✓** hazır, **yeşil kişi** öğrenci çalışıyor,
**karanlık ekran** kapalı veya ağda yok, **turuncu** hazırlık eksik (anahtar/yetki/öğrenci
hesabı), **mavi** kimlik onayı bekliyor, **mor kalkan** korunan cihaz. Üstteki renk
açıklamasına tıklayınca yalnız o durumdakiler görünür. Tablo isterseniz **B19 Tablo**.

## 3d. Bilgisayarlar uyumasın, zamanında kapansın — M2-S4 / M2-S5

- **M2-S4 Güç ve Uyku → B5 Uyku modunu kapat:** bilgisayarlar boşta uykuya geçmez ve
  kendiliğinden kapanmaz (uygulamadan hep erişilebilir); yalnız ekran kararır.
- **M2-S5 Zamanlı Kapatma:** “Bir kez” (tarih+saat) veya “Her hafta” (günler+saat) seçin,
  uyarı süresini belirleyin, **B8 Seçili bilgisayarlara ekle**. Saat gelince öğrencilere
  uyarı çıkar, sonra bilgisayar kapanır. Vazgeçerseniz **B12 Bekleyen kapatmayı iptal et**.

## 4. Seçim nasıl çalışır?

- Satırdaki kutu tek bilgisayar seçer; başlıktaki kutu yalnız ekranda görünenleri seçer.
- **Laboratuvardaki tüm uygun bilgisayarları seç** tüm sayfaları kapsar; korunan,
  hazır olmayan ve kapalı bilgisayarlar nedeniyle birlikte dışarıda gösterilir.
- Seçiminiz sayfalar arasında korunur (sağ üstte “N bilgisayar seçili”).
- Her işlem, başlamadan önce **kesin hedef listesini** gösterir ve onay ister.

## 5. Günlük işlemler — M2 İşlemler

| Sayfa | Ne yapar? |
| --- | --- |
| **M2-S1 Profil Temizliği** | Ders sonu temizliği (seçtiğiniz alanlar karantinaya taşınır, geri alınabilir), profil ayarlarını sıfırlama veya ev dizininin tamamını sıfırlama. Önce **B6 Önizle**: her bilgisayar için tek satır ve üstte özet kartları. |
| **M2-S2 Paket Kurulumu** | Bilgisayarınızdaki bir `.deb` dosyasını seçin, **B2** ile planı görün, **B3** ile onaylayıp kurun. |
| **M2-S3 Görünüm ve Giriş** | Windows 10 benzeri Pardus görünümü, duvar kâğıdı, ekran kilidini kapatma, öğrenci otomatik girişi, yönetim hesabını giriş ekranında gizleme. |
| **M2-S4 Güç** | Yeniden başlat / kapat. |

**Öğrenci oturumu açıksa:** Profil Temizliği tablosunda satırdaki **B4 Oturumu kapat**
tek bilgisayarı, **B5 Tüm öğrenci oturumlarını kapat** seçili tüm bilgisayarları
kapatır (kaydedilmemiş çalışmalar kaybolur; onay istenir). Oturum açıkken profil
sıfırlama başlamaz.

**Ev dizininin tamamını sıfırla** seçilirse **Belgeler ve tarayıcı verileri de silinir**
(önce yedek alınır). Yedekler öğrenci bilgisayarında tutulur; öğretmen
bilgisayarınızda yer kaplamaz ve ödev teslimleriniz bu işlemlerden etkilenmez.

## 6. Yedekten dönün

**M2-S1-B10 Yedekten dön…** ile bilgisayarı seçip **B11 Yedekleri listele** deyin.
Bir kaydı seçip **B12 Seçili yedeğe geri dön**. Aynı adlı dosya aynıysa üzerine
yazılır; farklıysa ikisi de tutulur (`rapor (yedek 26.09.2026 14.30).odt`).

## 7. Ödevler — M3

**M3-S2**'de sınıf listesini CSV ile ekleyin ve öğrencilere kod üretin. **M3-S1**'de
ödevi oluşturun, **Teslimleri aç** deyin; takip ekranında tek teslimi, seçili
öğrencileri veya tüm sınıfı ZIP olarak indirin.

## Sık sorulanlar

**İşlem sırasında ne olduğunu nereden görürüm?** Sağ alttaki iş panelinde; tüm
geçmiş **M4-S1 İşlem Geçmişi**'nde, her bilgisayar için ayrı sonuçla.

**“Parolasız sudo hazır değil” hatası:** O bilgisayar henüz hazırlanmamış; M1-S2'de
**B3 Hazırlığı başlat** ile bir kez hazırlayın.

**“Yetkili hesap hazırlığı gerekiyor”:** Bilgisayarda pardus/hp hesabı yok veya
parola yanlış. Sistem yöneticinizden yerel hazırlık isteyin.

**Arayüzü denemek istiyorum:** `/usr/share/doc/pardus-sinif-yonetimi/arayuz-onizleme.html`
dosyasını çift tıklayın; örnek verilerle çalışır, hiçbir bilgisayara bağlanmaz.

**Uyarı:** Bu bilgisayar tüm laboratuvarı yönetebilir. Başından ayrılırken ekranı
kilitleyin ve giriş parolanızı kimseye vermeyin.
