# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini izler ve
sürüm numaraları [Anlamsal Sürümleme](https://semver.org/lang/tr/) ile verilir.

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
