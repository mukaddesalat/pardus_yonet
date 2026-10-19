# Lab Kaptanı — Ödev ve Dosya Dağıtım Kılavuzu

Bu belge, Lab Kaptanı'nın **Ödev Teslim ve Materyal Dağıtım Modülü**'nün hem öğretmen hem de öğrenci tarafındaki kullanımını açıklar. Sistem tamamen yerel ağda çalışır; internet veya harici bulut servisi gerektirmez.

---

## 👩‍🏫 Bölüm 1: Öğretmen Kullanımı

### 1. Sınıf Listesini Ekleyin
**Ödev & Dosya Dağıt → Sınıf Listeleri & Öğrenci Kod Kartları**

* **CSV ile İçe Aktarma:** `sınıf;öğrenci numarası;ad soyad` formatındaki CSV dosyanızı yükleyebilirsiniz. Şablon dosya için depodaki [`belgeler/ornek_sinif_listesi.csv`](ornek_sinif_listesi.csv) örneğini kullanabilirsiniz.
* **Elle Ekleme:** Dilerseniz sınıfı oluşturup öğrencileri ad ve numaralarıyla tek tek listeye ekleyebilirsiniz.

### 2. Öğrenci Teslim Kodlarını Dağıtın
1. **Kodu Olmayanlara Kod Üret** butonuna tıklayın. Sistem her öğrenci için tahmin edilemeyen, güvenli 8 karakterlik bir kişisel kod (`XXXX-XXXX`) üretir.
2. **Kartları Yazdır** butonuna basarak her öğrenciye ait sınıf, numara, kod ve portal adresini içeren teslim fişlerini yazdırıp öğrencilere dağıtın.
3. *Güvenlik Notu:* Kodunu kaybeden öğrenci olursa, listeden öğrenciyi seçip **Seçililere Yeni Kod Üret** diyebilirsiniz; eski kod anında iptal edilir.

### 3. Ödev Oluşturun ve Teslimleri Açın
**Ödev & Dosya Dağıt → Yeni Ödev**

* **Başlık, Sınıf ve Yönerge:** Ödev konusunu ve açıklamasını girin.
* **Son Teslim Tarihi:** İsteğe bağlıdır; boş bırakılırsa süresiz olur. Geç teslim politikasını belirleyebilirsiniz.
* **Dosya Kısıtlamaları:** İzin verilen dosya uzantıları (`.pdf`, `.py`, `.sb3`, `.docx`, `.zip` vb.), maksimum dosya sayısı ve boyut sınırını tanımlayın.
* Ödev ilk başta **Taslak** durumundadır. Öğrencilerin görmesi için **Teslimleri Aç** butonuna basın.

### 4. Masaüstüne Ders Materyali Dağıtın
* Dilerseniz öğrencilerin bilgisayarlarındaki `/home/ogrenci/Masaüstü` klasörüne çalışma kağıdı, PDF, proje şablonu veya doğrudan tıklanabilir web bağlantısı (URL kısayolu) gönderebilirsiniz.

### 5. Teslimleri Takip Edin ve Toplu İndirin (ZIP)
* **Takip** ekranında sınıftaki her öğrencinin teslim durumu anlık listelenir:
  * *Teslim Edildi* / *Geç Teslim* / *Yükleme Sürüyor* / *Teslim Etmedi*
* **Tüm Sınıfı İndir (ZIP):** Tek tıkla tüm sınıfın ödevlerini `Sınıf / Numara_AdSoyad / Teslim_1 /` klasör hiyerarşisinde düzenlenmiş tek bir ZIP arşivi olarak bilgisayarınıza kaydedin.

---

## 👨‍🎓 Bölüm 2: Öğrenci Kullanımı

Öğrenciler kendi bilgisayarlarından web tarayıcısını açarak ödevlerini teslim eder:

1. **Portala Giriş:** Tarayıcının adres satırına `http://ogretmen.lab:8090` yazın (varsa masaüstündeki **Ödev Teslim** simgesine tıklayın).
2. **Kimlik Doğrulama:**
   * Sınıfınızı seçin,
   * Öğrenci numaranızı yazın,
   * Öğretmeninizin dağıttığı karttaki **Kişisel Teslim Kodunu** girin.
3. **Ödev Seçimi:** Teslim etmek istediğiniz ödevi seçin, yönergeleri ve dosya sınırlarını inceleyin.
4. **Dosyaları Yükleme:**
   * **Dosya Seç** butonunu kullanın veya dosyalarınızı yükleme alanına sürükleyip bırakın.
   * Projeler birden çok dosyadan oluşuyorsa ZIP formatında yükleyebilirsiniz.
5. **Gönder:** Gönder butonuna tıklayın ve *"Ödeviniz başarıyla teslim alındı"* onay mesajını görene kadar sayfayı kapatmayın.
6. **Sürüm Desteği:** Yanlış dosya gönderdiyseniz süre dolmadan tekrar yükleme yapabilirsiniz; sistem bunu *Teslim 2* olarak öğretmene ulaştırır, önceki dosyanız kaybolmaz.

---

## 🌐 Bölüm 3: Ağ ve Teknik Notlar

* **Portal Portu:** Ödev teslim portalı varsayılan olarak `8090` portunda çalışır (`http://<öğretmen-ip>:8090`).
* **Ad Çözümleme (`ogretmen.lab`):** Öğrencilerin IP adresi yerine kolayca `ogretmen.lab:8090` yazabilmesi için, Lab Kaptanı'nın **Komut Gönder** ekranındaki **Hızlı /etc/hosts Ekleme** aracıyla öğretmen IP'si sınıfa tek tıkla tanımlanabilir.
* **Depolama Güvenliği:** Öğrenci teslimleri öğretmen bilgisayarında `/var/lib/pardus-sinif-odev/` altında güvenle saklanır.
