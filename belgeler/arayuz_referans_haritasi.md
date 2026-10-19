# Arayüz referans haritası (M / S / B)

Sürüm 0.6.0. **Otomatik üretildi** (`python araclar/referans_haritasi.py`); kaynak `uygulama/arayuz/referans.js`. Elle düzenlemeyin.

- **M** = menü, **S** = sayfa, **B** = düğme. Tam kod: `M2-S1-B3`.
- Satır düğmeleri satırdaki bilgisayarın (veya öğrenci/ödev/iş) kimliğiyle biter: `M2-S1-B4-LAB01`. Tabloda `<kimlik>` diye gösterilir.
- Kod, düğmenin yerine değil işlevine bağlıdır: düğme taşınınca kod değişmez. Silinen düğmenin kodu *emekli* listesine alınır ve başka düğmeye verilmez.
- Arayüzde kodlar sağ üstteki **M0-S1-B1** ile gizlenip gösterilir; tam kod her düğmenin `data-ui-id` özniteliğindedir ve etiketin üzerine gelince görünür.

## Geri bildirim biçimi

Kısa ve tutarlı yazın; tek satırda bir değişiklik:

```text
M2-S1-B3: metni “Ev dizinini tamamen sıfırla” olsun.
M2 menüsü, S1 Profil Temizliği sayfasındaki B7 düğmesi kırmızı (tehlikeli) olsun.
M1-S1 tablosunda “Kontrol” sütunu “Gereken işlem”den sonra gelsin.
M2-S1-B4-LAB01: bu satırda düğme yerine yalnız uyarı görünsün.
```

## M0 — Ortak araçlar (her sayfada ortak)

### M0-S1 — Üst çubuk

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M0-S1-B1` | Referans kodlarını göster/gizle | Menü, sayfa ve düğme kodlarını açar/kapatır |
| `M0-S1-B2` | Çıkış | Uygulama oturumunu kapatır |
| `M0-S1-B3` | Seçim çipi | Seçili bilgisayarların listesini açar (M0-S5) |

### M0-S2 — Seçim araçları

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M0-S2-B1` | Görünen uygun bilgisayarları seç | Tablonun bu sayfasında görünen ve işleme uygun satırları seçer |
| `M0-S2-B2` | Laboratuvardaki tüm uygun bilgisayarları seç | Sayfalama ve arama filtresinden bağımsız, seçili laboratuvardaki bütün uygun kayıtları seçer |
| `M0-S2-B3` | Seçimi temizle | Tüm seçimi kaldırır |
| `M0-S2-B4` | Başlık seçim kutusu | Yalnız görünen satırları seçer / bırakır |
| `M0-S2-B5-<kimlik>` | Tek bilgisayar seç (satır) | O satırdaki bilgisayarı seçime ekler/çıkarır; korunan cihazda kapalıdır |
| `M0-S2-B6` | Laboratuvar seçici | Tabloyu ve “tüm uygun” kapsamını bir laboratuvarla sınırlar |
| `M0-S2-B7` | Önceki tablo sayfası | Tablo sayfalaması |
| `M0-S2-B8` | Sonraki tablo sayfası | Tablo sayfalaması |
| `M0-S2-B9` | Tablo arama kutusu | Ad, IP veya bilgisayar adına göre süzer (seçimi değiştirmez) |
| `M0-S2-B10` | Yalnız seçilileri göster | Tabloyu seçili bilgisayarlarla sınırlar |

### M0-S3 — Onay penceresi

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M0-S3-B1` | Onayla ve başlat | Onay penceresindeki kesin hedef listesiyle işi başlatır |
| `M0-S3-B2` | Vazgeç | Onay penceresini kapatır; hiçbir şey yapılmaz |
| `M0-S3-B3` | Onay kutusu | Yıkıcı işlemlerde “okudum, onaylıyorum” kutusu |

### M0-S4 — İş durumu paneli

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M0-S4-B1` | İş ayrıntısı | Çalışan/biten işi M4-S1'de açar |
| `M0-S4-B2` | İşi iptal et | İşi güvenli noktada durdurur; başlamış adımları geri almaz |
| `M0-S4-B3` | Paneli kapat | İş durumu panelini gizler (iş sürer) |

### M0-S5 — Seçim listesi penceresi

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M0-S5-B1` | Seçim listesini kapat | Pencereyi kapatır |
| `M0-S5-B2-<kimlik>` | Seçimden çıkar (satır) | O bilgisayarı seçimden çıkarır |

## M1 — Envanter

### M1-S1 — Bilgisayarlar

Tek envanter: ekran kutucukları veya tablo; durumlar renk ve simgeyle (hazır, kapalı, anahtar yok…); kayıt ekleme, içe aktarma, Veyon sürümü ve hedef seçimi.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M1-S1-B1` | Bilgisayar ekle | Elle kayıt penceresini açar (bağlantı kurmaz) |
| `M1-S1-B2` | Dosyadan içe aktar | Ansible INI envanteri veya CSV dosyasını önizleyip ekler |
| `M1-S1-B3` | Durumu kontrol et | Seçili bilgisayarlardan canlı durum okur (salt okunur) |
| `M1-S1-B4` | Envanterden çıkar | Seçilileri envanterden çıkarır (isteğe bağlı anahtar kaldırma) |
| `M1-S1-B5` | Ansible envanterini indir | Hazır bilgisayarların parolasız Ansible envanteri |
| `M1-S1-B6` | Filtreleri temizle | Arama, durum ve laboratuvar filtresini sıfırlar (seçimi değiştirmez) |
| `M1-S1-B7-<kimlik>` | Düzenle (satır) | Ad, laboratuvar, yönetim hesabı ve korunan cihaz ayarı |
| `M1-S1-B8-<kimlik>` | Gereken işleme git (satır) | Satırdaki “gereken işlem” sayfasını açar |
| `M1-S1-B9` | Kaydet (ekle/düzenle penceresi) | Kaydı kaydeder |
| `M1-S1-B10` | Vazgeç (ekle/düzenle penceresi) | Pencereyi kapatır |
| `M1-S1-B11` | Dosya seç (içe aktarma) | Envanter dosyasını seçer ve önizler |
| `M1-S1-B12` | İçe aktar | Önizlemede “eklenecek” olan satırları ekler |
| `M1-S1-B13` | Vazgeç (içe aktarma) | Pencereyi kapatır |
| `M1-S1-B14` | Çıkar (çıkarma penceresi) | Onaylanan bilgisayarları çıkarır |
| `M1-S1-B15` | Vazgeç (çıkarma penceresi) | Pencereyi kapatır |
| `M1-S1-B16` | Durum filtresi | Hazır / hazırlık gerekli / erişilemiyor / korunan / oturum açık |
| `M1-S1-B17` | Veyon filtresi | Kurulu değil / seçili paketten eski / aynı / daha yeni / bilinmiyor |
| `M1-S1-B18` | Ekran görünümü | Bilgisayarları ekran kutucukları olarak gösterir (durum rengi ve simgesiyle) |
| `M1-S1-B19` | Tablo görünümü | Bilgisayarları ayrıntılı tablo olarak gösterir |
| `M1-S1-B20-<kimlik>` | Durum göstergesi (satır) | Renk açıklaması; tıklanınca yalnız o durumdaki bilgisayarlar gösterilir |
| `M1-S1-B21` | Ekranları kilitle (Bana Bakın) | Seçili öğrenci bilgisayarlarının ekranını kilitler ve dikkat mesajı gösterir |
| `M1-S1-B22` | Kilitleri aç | Öğrenci bilgisayarlarındaki ekran kilidini açar |
| `M1-S1-B23` | Duyuru gönder | Seçili öğrenci ekranlarında bildirim ve mesaj penceresi açar |
| `M1-S1-B24` | İnternet erişimini kısıtla/aç | Yerel ağ açık kalacak şekilde dış interneti kısıtlar veya açar |

### M1-S2 — Bilgisayarları Hazırla

Bir kez yapılır: bilgisayarı tanıma (kimlik onayı), yönetime bağlama (SSH anahtarı, parolasız yetki, ogrenci hesabı) ve fazla yönetici hesabını temizleme.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M1-S2-B1` | Kimlikleri oku (adım 1) | Parola göndermeden bilgisayarın SSH kimliğini (parmak izi) okur |
| `M1-S2-B2` | Onayla (adım 1) | Okunan kimlikleri onaylar (klon kimlik uyarısıyla) |
| `M1-S2-B3` | Yönetime bağla (adım 2) | Anahtar + parolasız yetki + ogrenci hesabı; parola bir kez sorulur |
| `M1-S2-B4` | Önce göster (adım 3) | hp ve pardus birlikte olan bilgisayarlarda neyin silineceğini gösterir |
| `M1-S2-B5` | Temizle (adım 3) | Seçilen hesabı korur, diğerini yedekleyip siler |
| `M1-S2-B6-<kimlik>` | Korunacak hesap (satır) | O bilgisayarda korunacak yönetim hesabı: pardus veya hp |
| `M1-S2-B7` | Devam et (parola penceresi) | Hazırlık işini başlatır |
| `M1-S2-B8` | Vazgeç (parola penceresi) | Pencereyi kapatır; parola silinir |
| `M1-S2-B9` | ogrenci hesabı yoksa oluştur | Hazırlıkta eksik öğrenci hesabını oluşturur (sudo verilmez) |

### M1-S3 — Ağda Bul

Kendi ağındaki bilgisayarları bulur; onaylananlar envantere eklenir ve hazırlanır.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M1-S3-B1` | Taramayı başlat | Ağda SSH açık bilgisayarları ve kimliklerini bulur (parola göndermez) |
| `M1-S3-B2` | Envantere ekle | Seçili bulunanları kimlik onayıyla envantere ekler (bağlanmaz) |
| `M1-S3-B3` | Envantere ekle ve hazırla | Ekler ve M1-S2 hazırlığını başlatır (parola bir kez) |
| `M1-S3-B4` | Bulunanları temizle | Tarama sonuç listesini boşaltır (envantere dokunmaz) |
| `M1-S3-B5-<kimlik>` | Bulunanı seç (satır) | Bulunan bilgisayarı seçer |
| `M1-S3-B6` | Tüm bulunanları seç | Listedeki envanterde olmayanları seçer |
| `M1-S3-B7` | Önerilen ağı kullan | Öğretmen bilgisayarının ağını tarama kutusuna yazar |

### M1-S4 — Veyon Ayarları

Veyon paketi ve public key yükleme; seçili bilgisayarlara Veyon kurma/güncelleme, yapılandırma, bağlantı doğrulama ve geri alma.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M1-S4-B1` | Veyon paketini yükle (.deb seç) | Veyon .deb dosyasını yükler ve metadata ile doğrular; kurulum başlatmaz |
| `M1-S4-B2-<kimlik>` | Kurulacak paket (satır) | Birden çok Veyon paketi varsa uygulanacak olanı seçer |
| `M1-S4-B3-<kimlik>` | Paketi sil (satır) | Yüklenen Veyon paketini öğretmen PC'den siler (kurulu bilgisayarlar etkilenmez) |
| `M1-S4-B4` | Public key yükle | Veyon public key dosyasını yükler ve doğrular (private/SSH anahtarı reddedilir) |
| `M1-S4-B5` | Anahtar adı | Öğretmen PC'deki private key ile aynı ad (ör. teacher) |
| `M1-S4-B6` | Public key'i kaldır | Uygulamadaki public key kaydını siler (öğrenci bilgisayarları değişmez) |
| `M1-S4-B7` | Öğretmen PC'yi denetle | Private key var mı, Veyon Master okuyabilir mi, yöntem anahtar mı (salt okunur) |
| `M1-S4-B8` | Hazırlığı kontrol et | Seçililerde sürüm, kurulum planı ve yapılandırma farkını gösterir; hiçbir şey değişmez |
| `M1-S4-B9` | Seçililere Veyon kur/güncelle | Önizleme + onayla kurar; aynı sürüm atlanır, düşürme yapılmaz |
| `M1-S4-B10` | Seçililerde Veyon'u yapılandır | Önizleme + onayla anahtar, yöntem ve servisi ayarlar (önce yedek) |
| `M1-S4-B11` | Kur ve yapılandır | Önce kurulum, başarılıysa yapılandırma; tek önizleme ve onay |
| `M1-S4-B12` | Bağlantıyı doğrula | Servis, yöntem, anahtar eşleşmesi ve öğretmen PC'den sunucu yanıtı |
| `M1-S4-B13` | Sürümleri yenile | Bilinen envanter kayıtlarından kurulu Veyon sürümünü okur (ağ taraması yok) |
| `M1-S4-B14` | Önceki ayarları geri yükle | Son yapılandırmadan önce alınan Veyon ayar yedeğini geri koyar |
| `M1-S4-B15` | Sürüm filtresi | Kurulu değil / seçili paketten eski / aynı / daha yeni / bilinmiyor |
| `M1-S4-B16` | Onayla ve uygula (önizleme penceresi) | Önizlenen kesin hedeflere işlemi başlatır |
| `M1-S4-B17` | Vazgeç (önizleme penceresi) | Hiçbir şey yapılmaz |
| `M1-S4-B18` | Öğretmen PC sorununa rağmen devam | Private key/yöntem sorunu bilinerek yapılandırmaya izin verir |
| `M1-S4-B19` | Yedekle ve değiştir (anahtar) | Aynı adlı farklı anahtarı yedekleyip yenisiyle değiştirir |
| `M1-S4-B20` | Vazgeç (anahtar değişimi) | Mevcut anahtar korunur |

## M2 — İşlemler

### M2-S1 — Profil Temizliği

Ders sonu temizliği, profil sıfırlama, öğrenci oturumlarını kapatma, yedek ve yedekten dönüş.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S1-B1` | Kapsam: Ders sonu temizliği | Seçilen alanlar kurtarılabilir karantinaya taşınır |
| `M2-S1-B2` | Kapsam: Profil ayarlarını sıfırla | Gizli dosyalar (tarayıcı verileri dahil) silinir; Belgeler korunur |
| `M2-S1-B3` | Kapsam: Ev dizininin tamamını sıfırla | Belgeler ve tarayıcı verileri DAHİL her şey silinir |
| `M2-S1-B4-<kimlik>` | Bu bilgisayardaki öğrenci oturumunu kapat (satır) | Tek bilgisayarda ogrenci oturumunu kapatır (onaylı) |
| `M2-S1-B5` | Tüm öğrenci oturumlarını kapat | Seçili bilgisayarların hepsinde ogrenci oturumunu kapatır (onaylı) |
| `M2-S1-B6` | Önizle | Seçili bilgisayarlarda ölçüm yapar; hiçbir şey silinmez |
| `M2-S1-B7` | Temizliği başlat | Önizlenen kapsamı onayla uygular |
| `M2-S1-B8-<kimlik>` | İstisna (satır) | O bilgisayarın alanlarını yalnız bu temizlik için değiştirir |
| `M2-S1-B9` | Yalnız yedek al | Seçili bilgisayarlarda profil yedeği alır ve doğrular |
| `M2-S1-B10` | Yedekten dön… | Bir bilgisayarın yedeklerini canlı listeler |
| `M2-S1-B11` | Yedekleri listele | Seçilen bilgisayardaki yedekleri okur |
| `M2-S1-B12` | Seçili yedeğe geri dön | Yedeğin tamamını hash kuralıyla geri koyar |
| `M2-S1-B13` | Vazgeç (yedek penceresi) | Pencereyi kapatır |
| `M2-S1-B14` | Genel alan seçimi | Tüm seçili bilgisayarlarda temizlenecek alanlar |
| `M2-S1-B15` | İstisnayı kaydet | Yalnız bu temizlik için; kalıcı değildir |
| `M2-S1-B16` | Genel seçime döndür | O bilgisayarın istisnasını kaldırır |
| `M2-S1-B17` | Vazgeç (istisna penceresi) | Pencereyi kapatır |

### M2-S2 — Paket Kurulumu

Öğretmen bilgisayarındaki .deb paketini seçili bilgisayarlara plan ve onayla kurar (Veyon hariç: M1-S4).

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S2-B1` | .deb dosyası seç | Öğretmen bilgisayarından paket seçer; yapı doğrulanır |
| `M2-S2-B2` | Kurulum planını hazırla | Aktarım + SHA-256 + sürüm/mimari/alan/kilit/bağımlılık denetimi |
| `M2-S2-B3` | Planı onayla ve kur | Yalnız planda “kurulacak/güncellenecek” çıkanlara kurar |
| `M2-S2-B4` | Paketi öğretmen PC'den sil | Yüklü paket dosyasını siler |
| `M2-S2-B5-<kimlik>` | Plan ayrıntısı (satır) | O bilgisayarın plan ayrıntısını gösterir |
| `M2-S2-B6` | Paket seçici | Daha önce yüklenen paketlerden birini seçer |
| `M2-S2-B7` | Kapat (plan ayrıntısı) | Plan ayrıntısı penceresini kapatır |

### M2-S3 — Görünüm ve Giriş

Windows 10 benzeri ortak Pardus görünümü, duvar kâğıdı, ekran kilidi, otomatik giriş, yönetim hesabını gizleme.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S3-B1` | Windows 10 benzeri düzen | Pardus Karşılayıcı “10” düzeni: alt görev çubuğu + uygulama menüsü |
| `M2-S3-B2` | Standart duvar kâğıdı | Yüklenen görseli tüm bilgisayarlara uygular |
| `M2-S3-B3` | Duvar kâğıdı görseli seç | PNG/JPEG, en çok 20 MB |
| `M2-S3-B4` | Ekran kilidini kapat | Öğrenci ekran kilidi kapalı olur |
| `M2-S3-B5` | Öğrenci otomatik girişi | GDM ogrenci hesabıyla otomatik giriş yapar |
| `M2-S3-B6` | Yönetim hesabını giriş ekranında gizle | hp/pardus giriş listesinde görünmez; SSH sürer |
| `M2-S3-B7` | Ayarları kilitle | Duvar kâğıdı ve düzen ayarlarını öğrenci değiştiremez |
| `M2-S3-B8` | Önizle | Hedeflerde ne değişeceğini gösterir (salt okunur) |
| `M2-S3-B9` | Uygula | Önizlenen ayarları onayla uygular |
| `M2-S3-B10` | İşlem yönü | Uygula veya daha önce uygulananı kaldır |

### M2-S4 — Güç ve Uyku

Yeniden başlatma / kapatma ve uyku ayarı: bilgisayarlar boşta uykuya geçmez, kapanmaz; yalnız ekran kararır.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S4-B1` | Yeniden başlat | Seçili bilgisayarları yeniden başlatır ve açılışı doğrular |
| `M2-S4-B2` | Kapat | Seçili bilgisayarları kapatır ve kapanmayı doğrular |
| `M2-S4-B3` | Ekran koruyucu süresi | Boşta kalınca ekranın kararacağı süre (uyku yok) |
| `M2-S4-B4` | Güç ayarını önizle | Seçililerde şu anki uyku/ekran ayarını okur; hiçbir şey değişmez |
| `M2-S4-B5` | Uyku modunu kapat | Bilgisayarlar uykuya geçmez, boşta kapanmaz; ekran koruyucu kalır |
| `M2-S4-B6` | Varsayılan güç ayarına dön | Bu uygulamanın yaptığı uyku ayarını geri alır |

### M2-S5 — Zamanlı Kapatma

Bir kez (at gibi) veya her hafta (cron gibi) kapanma zamanı; uyarı süresi, plan listesi, kaldırma ve bekleyen kapatmayı iptal.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S5-B1` | Plan türü: bir kez | Belirli bir tarih ve saatte bir kez kapat (at gibi) |
| `M2-S5-B2` | Plan türü: her hafta | Seçilen günlerde aynı saatte kapat (cron gibi) |
| `M2-S5-B3` | Tarih | Bir kezlik planın tarihi |
| `M2-S5-B4` | Günler | Her hafta planının günleri |
| `M2-S5-B5` | Saat | Kapanma saati (uyarı bu saatte gösterilir) |
| `M2-S5-B6` | Uyarı süresi | Öğrencilere uyarı gösterildikten kaç dakika sonra kapanacağı |
| `M2-S5-B7` | Açıklama | Planı tanımak için kısa not (isteğe bağlı) |
| `M2-S5-B8` | Seçili bilgisayarlara ekle | Planı onayla seçili bilgisayarlara kurar ve sonraki kapanmayı gösterir |
| `M2-S5-B9` | Planları oku | Bilgisayarlardaki kapatma planlarını okur (salt okunur) |
| `M2-S5-B10-<kimlik>` | Bu planı kaldır (plan satırı) | Planı bulunduğu bilgisayarlardan kaldırır (kesin liste onayda gösterilir) |
| `M2-S5-B11` | Seçililerdeki tüm planları kaldır | Seçili bilgisayarlarda bu uygulamanın tüm kapatma planlarını siler |
| `M2-S5-B12` | Bekleyen kapatmayı iptal et | Uyarı süresi içindeki kapatmayı durdurur |

### M2-S6 — Komut Gönder

Kayıtlı veya özel bash/shell komutunu SSH ile seçili bilgisayarlara gönderir; canlı çıktı ve özet raporlar; /etc/hosts kaydı ekler.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M2-S6-B1` | Komutu çalıştır | Bash komutunu SSH ile seçili bilgisayarlara gönderir ve çıktıları toplar |
| `M2-S6-B2` | Kütüphaneye kaydet | Yazılan komutu kayıtlı komutlar listesine ekler |
| `M2-S6-B3-<kimlik>` | Kayıtlı komutu yükle (satır) | Kayıtlı komutu düzenleyiciye yükler |
| `M2-S6-B4-<kimlik>` | Kayıtlı komutu sil (satır) | Özel kayıtlı komutu listeden siler |
| `M2-S6-B5` | Hosts kaydını dağıt | /etc/hosts dosyasına IP ve alan adı kaydını (ör. 192.168.23.142 abc.local) ekler |
| `M2-S6-B6` | Sudo ile çalıştır | Komutu parolasız sudo yetkisiyle çalıştırır |

## M3 — Ödevler

### M3-S1 — Teslimler

Ödevler, teslim takibi, masaüstüne ders materyali dağıtımı ve tek / seçili / tüm teslimleri indirme.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M3-S1-B1` | Yeni ödev | Ödev formunu açar (taslak) |
| `M3-S1-B2` | Yenile | Ödev listesini yeniler |
| `M3-S1-B3-<kimlik>` | Takibi aç (satır) | O ödevin teslim takibini açar |
| `M3-S1-B4` | Tüm teslimleri indir (ZIP) | Sınıfın bütün teslimleri |
| `M3-S1-B5` | Seçili teslimleri indir (ZIP) | İşaretli öğrencilerin teslimleri |
| `M3-S1-B6-<kimlik>` | Tek teslimi indir (satır) | O öğrencinin son teslimini ZIP indirir |
| `M3-S1-B7` | Ödev listesine dön | Takipten listeye döner |
| `M3-S1-B8` | Teslimleri aç | Öğrenciler ödevi görür ve teslim eder |
| `M3-S1-B9` | Teslimleri kapat | Yeni teslim alınmaz |
| `M3-S1-B10` | Arşivle | Ödevi arşive taşır (teslimler korunur) |
| `M3-S1-B11` | Arşivden çıkar | Ödevi arşivden geri alır |
| `M3-S1-B12` | Ödevi sil | Yalnız arşivdeki ödev; teslimler kalıcı silinir |
| `M3-S1-B13` | Ödevi düzenle | Ödev formunu açar |
| `M3-S1-B14` | Önceki sürümleri dahil et | ZIP'e öğrencinin önceki teslimlerini de ekler |
| `M3-S1-B15-<kimlik>` | Dosyaları göster (satır) | Öğrencinin teslim dosyalarını listeler |
| `M3-S1-B16` | Kaydet (ödev penceresi) | Ödevi kaydeder |
| `M3-S1-B17` | Vazgeç (ödev penceresi) | Pencereyi kapatır |
| `M3-S1-B18-<kimlik>` | Dosyayı indir (satır) | Teslimdeki tek dosyayı indirir |
| `M3-S1-B19` | Bu teslimi ZIP indir | Açık teslimin tüm dosyaları |
| `M3-S1-B20` | Kapat (dosyalar penceresi) | Pencereyi kapatır |
| `M3-S1-B21-<kimlik>` | Önceki teslimi göster (satır) | Öğrencinin eski bir teslimini açar |
| `M3-S1-B22` | Masaüstüne bağlantı gönder | Seçili öğrenci masaüstlerine web bağlantısı (.desktop) kısayolu bırakır |
| `M3-S1-B23` | Masaüstüne dosya dağıt | Seçilen çalışma dosyasını öğrenci masaüstlerine kopyalar |

### M3-S2 — Sınıflar ve Kodlar

Sınıf listeleri, öğrenci teslim kodları ve öğrenci portalı ayarları.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M3-S2-B1` | CSV dosyası seç | Sınıf listesi dosyası |
| `M3-S2-B2` | İçe aktar | CSV'deki öğrencileri ekler/günceller |
| `M3-S2-B3` | Sınıf seçici | Listelenecek sınıf |
| `M3-S2-B4` | Listeyi CSV indir | Kodlar hariç sınıf listesi |
| `M3-S2-B5` | Sınıfı sil | Sınıfı ve öğrenci listesini siler |
| `M3-S2-B6` | Sınıf ekle | Yeni boş sınıf |
| `M3-S2-B7` | Öğrenci ekle | Seçili sınıfa tek öğrenci ekler |
| `M3-S2-B8` | Kodu olmayanlara kod üret | Yalnız kodsuz öğrenciler |
| `M3-S2-B9` | Seçililere yeni kod üret | Eski kod hemen geçersiz olur |
| `M3-S2-B10-<kimlik>` | Öğrenciyi sil (satır) | Öğrenciyi listeden siler |
| `M3-S2-B11-<kimlik>` | Adı düzenle (satır) | Öğrencinin adını değiştirir |
| `M3-S2-B12` | Kartları yazdır | Kod kartlarını yazdırır |
| `M3-S2-B13` | Kapat (kod penceresi) | Kodlar bellekten ve sayfadan silinir |
| `M3-S2-B14` | Portal ayarlarını kaydet | Adres adı ve izinli laboratuvar ağları |

## M4 — Kayıtlar

### M4-S1 — İşlem Geçmişi

Tüm işlerin öğretmen, hedef listesi ve bilgisayar bazında sonuçları.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M4-S1-B1` | Yenile | İş listesini yeniler |
| `M4-S1-B2-<kimlik>` | Ayrıntı (satır) | İşin hedef listesi ve sonuçları |
| `M4-S1-B3` | Sonuçları CSV indir | Hassas bilgi içermeyen sonuç dökümü |
| `M4-S1-B4` | Çalışan işi iptal et | Güvenli noktada durdurur |
| `M4-S1-B5` | İşlem türü filtresi | Listeyi işlem türüne göre süzer |

## M5 — Ayarlar

### M5-S1 — Uygulama Ayarları ve Referans Rehberi

Saklama sınırı, sürüm bilgisi ve tüm menü/sayfa/düğme kodları.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M5-S1-B1` | Saklama sayısını kaydet | Her bilgisayarda tutulacak yedek/karantina sayısı |
| `M5-S1-B2` | Referans kodlarını göster/gizle | M0-S1-B1 ile aynı işlev |
| `M5-S1-B3` | Rehberde ara | Kod veya ada göre süzer |
| `M5-S1-B4` | Referans haritasını indir | Tüm kodları Markdown dosyası olarak indirir |

### M5-S2 — Okul ve Öğretmenler

Okul adı ve logosu, öğretmen hesapları, Admin/Standart rolü ve isteğe bağlı menü yetkileri.

| Kod | Ad | İşlev |
| --- | --- | --- |
| `M5-S2-B1` | Okul bilgilerini kaydet | Okul adını, alt başlığı ve logoyu kaydeder |
| `M5-S2-B2` | Okul logosu seç | Okul logosu görselini (PNG/JPG/SVG) yükler |
| `M5-S2-B3` | Yeni öğretmen ekle | Yeni öğretmen hesabı ve yetki penceresini açar |
| `M5-S2-B4-<kimlik>` | Öğretmeni düzenle (satır) | Öğretmen rolünü, yetkilerini veya şifresini günceller |
| `M5-S2-B5-<kimlik>` | Öğretmeni sil (satır) | Öğretmen hesabını siler |
| `M5-S2-B6` | Kaydet (öğretmen penceresi) | Öğretmen hesabını ve yetkilerini kaydeder |
| `M5-S2-B7` | Vazgeç (öğretmen penceresi) | Öğretmen penceresini kapatır |

## Emekli kodlar

Henüz yok.
