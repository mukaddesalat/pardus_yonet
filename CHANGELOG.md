# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini izler ve
sürüm numaraları [Anlamsal Sürümleme](https://semver.org/lang/tr/) ile verilir.

## [0.9.0] — 2026-11-08

### Eklenen & Geliştirilen
- **Komut Mağazası ve Topluluk Araçları Modülü (M2-S6):**
  - Resmi GitHub deposu ([`mukaddesalat/pardus_yonet_magaza`](https://github.com/mukaddesalat/pardus_yonet_magaza)) entegrasyonu; tüm depoyu klonlamadan `katalog.json` üzerinden tek tıkla canlı güncelleme.
  - 5 işlevsel sekme: *🏪 Komut Kataloğu*, *🧰 Araçlarım & Sabitlenenler*, *⚡ Aracı Çalıştır*, *➕ Yeni Araç Taslağı* ve *💻 Serbest Uçbirim & Hosts*.
  - Sık kullanılan araçları tek tıkla doğrudan canlı **Sınıf Masası Panosu**'na sabitleme (`M1-S1-PANO`) ve derste 1-tık ile çalıştırma.
  - Yeni hazır araç: **Güncellenebilir Paket Sayacı ve Raporu (`paket-guncelleme-sayaci`)** ile sınıftaki bilgisayarların bekleyen güncelleme ve güvenlik yamalarını tek tek sayıp raporlama.
- **Arayüz ve Menü Sadeleştirmesi:**
  - Modern 3 ana grup hiyerarşisi: *Günlük Ders Akışı*, *Araç Kutusu*, *Yönetici & Kurulum*.
  - Menü başlığı taşmaları ve seperatör hizalamaları düzeltildi; alt sekmeli gezinim getirildi.
- **Ödev ve Materyal Dağıtımı (M1-S3):**
  - Öğrenci masaüstü hedef klasörünü dinamik olarak belirleme (varsayılan `/home/ogrenci/Masaüstü/Odevler`, öğretmen dilerse `/home/ogrenci/Masaüstü/DersNotlari` vb. olarak değiştirebilir; klasör yoksa uzaktan otomatik oluşturulur).
  - Admin öğretmen ve standart ders öğretmeni rol yetkileri ayrıştırıldı.
- **Belirgin ve Kendiliğinden Kapanan Öğrenci Bildirim Sistemi (OSD):**
  - GNOME bildirimlerinin kaybolmama ve fark edilmeme sorununa karşılık ekranda belirgin, 8 saniye sonra otomatik kapanan kurumsal duyuru katmanı eklendi.
- **Dokümantasyon ve 23 Yeni Yüksek Çözünürlüklü Ekran Görüntüsü:**
  - `belgeler/gorseller/` dizinine 23 yeni yüksek çözünürlüklü arayüz görseli eklendi.
  - `kullanim_kilavuzu.md`, `yonetici_kilavuzu.md` ve `odev_kilavuzu.md` yeni menü yapısına göre baştan sona güncellendi.
  - Yeni [belgeler/magaza_kilavuzu.md](belgeler/magaza_kilavuzu.md) dokümanı eklendi (Mağaza mimarisi, parametre şeması, paket güncelleme sayacı senaryosu ve katkı rehberi).
  - Arayüz referans haritası (`belgeler/arayuz_referans_haritasi.md`) güncellendi.

## [0.8.2] — 2026-11-07

### Düzeltilen & Geliştirilen
- **Öğrenci Masaüstüne Dosya Bırakma (M3-S1 / SFTP Aktarımı):**
  - Dosyaların SSH komut satırı argümanı (`argv[1]`) üzerinden Base64 ile gönderilmesinden kaynaklanan Linux `MAX_ARG_STRLEN` (128 KB) ve `E2BIG` kanal boyutu aşımı hatası giderildi.
  - Dosyalar artık doğrudan SFTP kanalı (ve stdin akış desteği) ile öğrenci bilgisayarına `/tmp/psy-dosya-...` olarak aktarılıp `masaustu_dosya` betiği tarafından `/home/ogrenci/Masaüstü/` dizinine taşınıyor; dosya boyutu sınırı **50 MB**'a çıkarıldı.
  - `M3-S1` sayfasına doğrudan bilgisayar seçim çubuğu eklendi; bilgisayar seçilmediğinde mevcut laboratuvardaki tüm uygun bilgisayarları otomatik hedefleme sağlandı.
  - Sürükle-bırak destekli dosya bırakma alanı, seçili dosya adı, rozet ve temizleme kontrolleriyle arayüz zenginleştirildi.
- **Masaüstüne Web Bağlantısı ve Ödev Portalı Kısayolu (M3-S1):**
  - Pardus GNOME masaüstünde kırık veya yetkisiz `.lnk` gibi görünen `Type=Link` dosya yapısı düzeltildi.
  - Her masaüstü ortamında (GNOME/XFCE) çift tıklandığında güvenlik engeline takılmadan varsayılan web tarayıcısında açılan **`.html` web yönlendirici dosyası** ve `Type=Application` (`xdg-open`) güvenilir `.desktop` başlatıcısı birlikte oluşturuldu.
  - Gönderilen web bağlantısını veya Ödev Teslim Portalını öğrenci ekranlarında anında tarayıcıda açan **"Öğrenci ekranlarında web sayfasını hemen aç"** (`otomatik_ac`) seçeneği eklendi.
  - **"🎯 Ödev Portalını Sınıfa Gönder ve Aç"** kısayolu ile öğretmen bilgisayarının IP adresi (`ogretmen.lab`) öğrenci bilgisayarlarının `/etc/hosts` dosyasına otomatik kaydedilerek isim çözümleme sorunu giderildi.
- **Menü Düzeni:**
  - **⏰ Zamanlı Kapatma (`M2-S5`)**, sistem ayarları grubundan çıkarılarak **🧹 Bakım, Görünüm & Güç (`nav-bakim`)** menüsü altına, **🔌 Güç & Uyku Ayarı (`M2-S4`)** yanına taşındı. `M2-S4` sayfasına tek tıkla zamanlı kapatma planlamaya geçiş kısayolu eklendi.

## [0.8.1] — 2026-11-07

### Eklenen
- **Yönetim Uygulaması Yedekleme ve Başka Bilgisayara Taşıma Modülü (M5-S1):**
  - Envanter veritabanı (`envanter.db`), ödev veritabanı (`odev.db`), SSH anahtar çifti (`uygulama_ed25519`), Veyon `.deb` paketi ve RSA public key, duvar kâğıdı galerisi, öğrenci ödev teslimleri ve uygulamanın kendi `.deb` kurulum paketini tek bir taşınabilir `.tar.gz` arşivinde yedekleme (`uygulama/sistem_yedek.py`).
  - Her yedek arşivinin içine sıfırdan Pardus bilgisayarda tek komutla (`sudo bash yedekten-kur.sh`) hem `.deb` paketini kuran hem de tüm verileri/anahtarları/izinleri geri yükleyen otomatik kurulum betiği (`yedekten-kur.sh`) ve SHA-256 doğrulama manifestosu (`manifest.json`) ekleme.
  - Web yönetim panelinden (`M5-S1`) canlı sistem özeti görüntüleme, yedek oluşturup indirme, sunucudaki yedekleri yönetme ve yüklenen `.tar.gz` yedeğini SHA-256 bütünlük önizlemesiyle kesintisiz geri yükleme (geri yükleme öncesi otomatik güvenlik yedeği alarak).
  - `/usr/bin/pardus-sinif-yonetimi` komut satırı aracına `--yedekle`, `--geri-yukle` ve `--yedek-listele` parametreleri.
- **Kullanım ve Yönetici Kılavuzları Güncellemeleri:**
  - `belgeler/kullanim_kilavuzu.md` ve `belgeler/yonetici_kilavuzu.md` dosyalarına sistem yedekleme, geri yükleme ve sıfırdan kurulum adımları eklendi.
  - 12 adet güncel ve yüksek çözünürlüklü arayüz ekran görüntüsü (`01_sinif_masasi.png` ... `12_sistem_yedekleme.png`) Headless Edge ile yeniden üretildi.
- **Veyon Servis Kurtarma ve Kontrol Komutu (M2-S6):**
  - SSH Komut Merkezi'ne (M2-S6) öğrencilerin Veyon servisini kapatması durumunda servisi kontrol edip unmask/enable ederek anında ayağa kaldıran yerleşik komut (`k_veyon_servis`) ve tek tıkla yükleme kısayolu (`🔄 Veyon Servisini Aç`) eklendi.

## [0.8.0] — 2026-11-07

### Eklenen
- **Duvar Kâğıdı Galerisi ve Köşede Bilgisayar Numarası (M2-S3):**
  - Çoklu görsel yükleme, önizleme, seçme ve silme özelliklerine sahip etkileşimli Duvar Kâğıdı Galerisi.
  - 3 adet hazır kurumsal laboratuvar şablonu (*Pardus Gece Mavisi*, *Anadolu Turkuazı*, *Bilişim Atölyesi*).
  - Seçilen duvar kâğıdına bilgisayarın `hostname` rakamlarını (örn: `ogrenci01` → **01**) sağ üst veya sol üst köşeye yüksek kontrastlı rozet olarak otomatik işleme; uzaktan bakıldığında her bilgisayarın anında tanınabilmesi.
- **Pardus Yazılım Merkezi / APT Depodan Uygulama Kurulum & Kaldırma (M2-S2):**
  - Tanımlı APT depolarında arama yapma ve kategorize edilmiş eğitim/kodlama/tasarım mağaza vitrininden uygulama seçme.
  - Seçili tek veya birden çok bilgisayara depodan tek tıkla toplu uygulama kurma.
  - Kurulu uygulamaları listeleme ve kritik sistem paketlerini (`gdm3`, `network-manager`, `sudo`, `openssh-server` vb.) kazara kaldırılmaya karşı koruyarak güvenle kaldırma.
- **Veyon Uzman Ayarları Paneli (M1-S4):**
  - İleri düzey sistem yöneticileri için katlanabilir `veyon-cli` yapılandırma paneli.
  - Kimlik yöntemi, yetkilendirme anahtarı erişim grubu, kullanıcı grupları arka ucu, VNC sunucusu ve görüntü kalitesi parametrelerini önceden tanımlı güvenli varsayılanlarla inceleme ve özelleştirme.
- **"Bana Bakın" Ekran Kilidinde Görünür Bilgisayar Numarası & Hostname (M1-S1):**
  - Tam ekran kilit katmanında sağ üst köşede devasa (`108pt`) bilgisayar numarası rozeti ve ekranın ortasında yüksek kontrastlı hostname kartı (`🖥️ 01 · ogrenci01`).
  - Kilit süresince monitörün kapanmasını veya kararmasını engelleyen otomatik DPMS koruması.

### Değişen
- **Bilgisayar Detay Özeti (M1-S1):**
  - Açılır pencerede gereksiz SSH portu kaldırıldı; yerine **Hostname** (bilgisayar adı) ve **IP adresi** öne çıkarıldı.
  - Bilgisayar düzenleme formundan bilgisayar adı (hostname) değiştirilebilir hale getirildi ve uzak istemcide `hostnamectl set-hostname` ile anında güncellenmesi sağlandı.
  - Cihaz işlemlerinde (kurulum, güç, duvar kağıdı) önizleme zorunluluğu esnetildi; kullanıcıya öneride bulunulup doğrudan uygulama esnekliği sağlandı.
- **Veyon Kurulum ve Yapılandırma Standartları (M1-S4):**
  - Paket ve public key yüklü olduğunda "Kur ve yapılandır" işlemi artık soru sormadan tüm Veyon ayarlarını otomatik tamamlar.
  - Kimlik doğrulama varsayılan olarak **Anahtar dosya yetkilendirmesi** (`Authentication/Method=1`), erişim grubu `root`, kullanıcı grupları varsayılan POSIX sistem grupları, VNC sunucusu **Dahili VNC** ve görüntü kalitesi **Yüksek** olarak uygulandı.
- **Güç ve Ekran Koruyucu Yönetimi (M2-S4):**
  - Ekran kapanma süresi varsayılan olarak **`0` ("Hiç kapanmasın — ekran hep açık kalır")** olarak belirlendi.
  - GNOME `idle-dim`, `idle-activation-enabled`, `lock-enabled` kapatıldı; GDM `idle-delay=0` kilitlendi.
  - X11 DPMS donanımsal monitör kapanmasını engelleyen `/etc/X11/xorg.conf.d/90-pardus-sinif-dpms.conf` ve açık oturumlarda `xset -dpms` uygulayan autostart servisi eklendi.
  - `systemd-logind` HUP sinyali ile oturumlar kesilmeden yeni güç yapılandırmasını anında devreye alacak şekilde güncellendi.

## [0.7.0] — 2026-10-19

### Eklenen
- **Canlı Sınıf Masası Araçları:**
  - Bana Bakın (Ekran Kilitle): Öğrenci ekranlarını dikkat uyarısıyla anında kilitleme ve klavye/fareyi geçici olarak engelleme.
  - Ekran Kilitlerini Aç: Kilitli ekranları tek tıkla serbest bırakma.
  - Sınıfa Duyuru Gönder: Öğrenci masaüstünde anlık duyuru/mesaj penceresi açma.
  - İnterneti Kısıtla / Aç: Dış internet erişimini kesip yerel laboratuvar ağı ve ödev portalını açık tutma.
- **Cihaz Detay Özeti:** Monitör kutucuğuna veya bilgisayar adına tıklandığında açılan açılır özet bilgi penceresi (IP, bağlantı durumu, Veyon sürümü, RAM, disk ve çalışma durumu).
- **Okul Kimliği ve Öğretmen Yönetimi:**
  - Okul adı ve logo yükleme desteği (Varsayılan: Şehit Cengiz Polat Fen ve Teknoloji AİHL).
  - Standart Öğretmen hesapları ve rol tabanlı yetki şablonu (Admin: Mukaddes ALAT).
  - Sol alt menüde aktif öğretmen, yetki rolü ve Ekran/Ağ durum kutucuğu.
- **SSH Komut Merkezi:** Tüm sınıfa aynı anda Bash/Shell komutu gönderme, canlı çıktı izleme, tek tıkla `/etc/hosts` yerel alan adı tanımlama.
- **Masaüstüne Materyal Dağıtımı:** Öğrenci masaüstüne çalışma kağıdı, dosya veya web bağlantısı gönderme.

### Değişen
- Belgelendirme tamamen yenilendi; tüm kılavuzlara güncel ve gerçek arayüz ekran alıntıları eklendi.
- Arayüzden teknik referans kodları emekliye ayrıldı; sade, Türkçe ve sezgisel menü yapısına geçildi.
- Uzak SSH komut çalıştırma altyapısı `stdin` akışı ve `systemd-run` ile güçlendirildi.

## [0.6.0] — 2026-10-05

### Eklenen
- Uygulama adı ve logosu **Lab Kaptanı** (paket adı `pardus-sinif-yonetimi` değişmedi).
- M1-S1 Bilgisayarlar: ekran kutucukları (Veyon benzeri) ve tıklanabilir durum renk
  açıklaması; durum öncelikli olarak tek bir renk ve simgeyle gösterilir.
- M2-S4 Güç ve Uyku: bilgisayarların boşta uykuya geçmesini ve kendiliğinden
  kapanmasını önleyen uyku ayarı (ekran koruyucu serbest). Önizleme, uygulama ve
  varsayılana dönüş.
- M2-S5 Zamanlı Kapatma: "bir kez" veya "her hafta" kapanma planları, uyarı süresi,
  plan listesi ve kaldırma, bekleyen kapatmayı iptal.

### Değişen
- M1-S2 "Bilgisayarları Hazırla": teknik olmayan dille üç adım; teknik ayrıntılar
  katlanır bölümde. İşlevler ve kodlar aynı kaldı.

### Düzeltilen
- Zamanlı kapatma iptali, bildirimler ve giriş ekranındaki uyku ayarı lab denemesinde
  düzeltildi.

## [0.5.0] — 2026-10-04

### Eklenen
- M1-S4 Veyon Ayarları: Veyon `.deb` ve public key yükleme; önizle → onayla → kur /
  güncelle ve anahtar dosyasıyla yapılandırma (önce yedek); bağlantı doğrulama; geri
  alma. Yalnız yüklenen paketten kurulur; resmî depodan kurulmaz.
- M1-S1'de "Veyon sürümü" sütunu ve filtresi (hedeften okunan tam sürüm).

### Değişen
- Ana menüler ikonlu ve açılır/kapanır; alt sayfalar ikonlu.

## [0.4.0] — 2026-09-29

0.2.0 ve 0.3.0 ara sürümleri de bu sürümle birlikte yayınlandı.

### Eklenen
- Tek envanter (M1-S1): elle ekleme, Ansible INI / CSV içe aktarma, korunan EBA/ETAP
  cihazları, durum sütunları.
- SSH ve hesap hazırlığı: parola bir kez, uygulama anahtarı, `visudo` ile doğrulanan
  parolasız yetki, `ogrenci` hesabı.
- hp / pardus tekilleştirme (öğrenci PC'de yedekli, bağımsız oturumda doğrulamalı).
- Ağda Bul (M1-S3), toplu seçim ve kesin hedef listesi onayı.
- Profil temizliği ve yedekten dönüş (M2-S1), yerel `.deb` dağıtımı (M2-S2), görünüm ve
  giriş ayarları (M2-S3), güç işlemleri (M2-S4 o zamanki adıyla).
- Sabit M/S/B referans kodları ve referans rehberi (M5-S1), DESIGN.md belirteçleri,
  tek dosyalık etkileşimli önizleme.
- Ödev Teslim modülü 1. aşama: öğrenci portalı, sınıf ve teslim kodları, teslim takibi,
  ZIP indirme.

## [0.2.0] — 2026-09-29 (0.4.0 ile birlikte)

- `.deb` paketi (gömülü Python, systemd servisi, kurulum kodu, masaüstü başlatıcı).
- Duvar kâğıdı, güvenli temizlik (karantina), yedekleme, profil sıfırlama.

## [0.1.0] — 2026-09-22

- İlk çekirdek: keşif, sunucu kimliği onayı, anahtar kurulumu, durum kontrolü.
- Bu sürümdeki Podman tabanlı dağıtım sonradan `.deb` ile değiştirildi.
