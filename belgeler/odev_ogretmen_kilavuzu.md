# Ödev Teslim — Öğretmen Kılavuzu

Öğrencileriniz ödevlerini laboratuvardaki bilgisayarlardan, tarayıcıyla sizin
bilgisayarınıza yükler. İnternet, bulut hesabı veya ek program gerekmez.
Dosyalar yalnız sizin bilgisayarınızda saklanır.

## 1. Sınıf listesini ekleyin (bir kez)

**Pardus Sınıf Yönetimi → Ödevler → Sınıf listeleri ve kodlar**

- **CSV içe aktarma:** Sütunlar `sınıf; öğrenci numarası; ad soyad`.
  Excel'de "CSV" olarak kaydettiğiniz dosya olabilir. Örnek:
  `belgeler/ornek_sinif_listesi.csv`.
- Ya da sınıfı ekleyip öğrencileri tek tek yazın.

## 2. Öğrencilere teslim kodu verin

1. **Kodu olmayanlara kod üret** düğmesine basın.
2. Açılan pencerede **Kartları yazdır** ile her öğrenci için bir kart basın
   (sınıf, numara, kişisel kod ve portal adresi yazar), kesip dağıtın.

> Kodlar **yalnız bu pencerede** görünür; kapatınca bir daha gösterilmez.
> Kodunu kaybeden öğrenciyi listeden seçip **Seçililere yeni kod üret** deyin;
> eski kod hemen geçersiz olur.

Her öğrencinin kendi kodu vardır. Başkasının adına teslim yapılamaz; ortak
bir "sınıf kodu" yoktur.

## 3. Ödev oluşturun ve açın

**Ödevler → Yeni ödev**

- Başlık, sınıf, kısa yönerge.
- **Son teslim** (boş bırakırsanız süresiz). İsterseniz "süre dolduktan sonra
  da kabul et" seçeneğiyle geç teslimleri "Geç teslim" olarak alırsınız;
  varsayılan olarak süre dolunca teslim kapanır.
- Kabul edilen dosya türleri, dosya sayısı ve toplam boyut sınırı, klasör izni.

Ödev **Taslak** olarak kaydedilir. Öğrencilerin görmesi için **Teslimleri aç**
deyin. Bitince **Teslimleri kapat**; o anda süren yüklemeler teslim sayılmaz.
**Arşivle** silmez; ödev listeden kalkar, teslimler durur.

## 4. Takip edin ve indirin

**Takip** ekranında sınıf listesindeki her öğrenci görünür:
Teslim etmedi · Yükleme sürüyor · Teslim alındı · Geç teslim · Yükleme hatası.

- **Dosyalar:** öğrencinin teslim ettiği dosyalar ve geçmiş sürümler
  (Teslim 1, Teslim 2…).
- **Tüm sınıfı indir (ZIP):** her öğrencinin son teslimi; "Önceki sürümleri de
  dahil et" ile hepsi. ZIP içinde `sınıf / numara ad / Teslim N /` klasörleri
  vardır, aynı adlı dosyalar karışmaz.

Dosyalar her zaman indirilir, tarayıcıda açılmaz. Sunucunun dosyayı saklaması
dosyanın zararsız olduğu anlamına gelmez; virüs taraması yapılmaz.

## 5. Öğrenci adresi

Ödevler ekranının üstünde yazar, örneğin `http://ogretmen.lab:8090/`.
Öğrenci bilgisayarlarının bu adı tanıması için ad kaydı gerekir; kayıt
yoksa aynı yerde yazan IP'li adres kullanılabilir (örneğin `http://192.168.10.2:8090/`).

**Öğrenciler bağlanamıyorsa:**
1. Bilgisayarınız açık ve laboratuvar ağına bağlı mı?
2. Ödevler ekranında portal durumu **Çalışıyor** mu?
3. Öğrenci bilgisayarında IP'li adresi deneyin. Açılıyorsa sorun ad
   kaydındadır; açılmıyorsa ağ bağlantısını kontrol edin.
4. Bilgisayarınızın IP adresi değiştiyse (DHCP) öğrencilerin kayıtlı adresi
   eskir; ağ yöneticinizden sabit IP isteyin.

## Bilmeniz gerekenler

- Bağlantı şifresizdir (HTTP): kodlar ve dosyalar laboratuvar ağında şifrelenmeden
  taşınır. Portal yalnız tanımlı laboratuvar ağından gelen bağlantıyı kabul eder.
- Teslimler öğrenci profil yedeklerinden ayrıdır; profil sıfırlama veya yedek
  temizliği ödevleri silmez.
- **Tek kopya yedek değildir.** Dönem sonunda tüm sınıfları ZIP olarak indirip
  USB bellek veya okul sunucusu gibi ayrı bir yere kopyalayın.
- Uygulamayı kaldırmak (tam silme dahil) teslimleri silmez. Ödevi kalıcı silmek
  için önce arşivleyin, sonra **Sil**; bu geri alınamaz.
