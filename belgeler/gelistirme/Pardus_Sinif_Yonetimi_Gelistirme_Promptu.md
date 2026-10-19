# Pardus Sınıf Yönetimi — Geliştirme İstemi

Bu metni geliştirme sürecinde mimari ve gereksinim referansı olarak kullanın.

---

## 0. Karar kaydı (22 Eylül 2026)

Aşağıdaki kararlar proje sahibiyle netleştirilmiştir; metnin geri kalanıyla çeliştiği yerde bu bölüm geçerlidir:

1. **Geliştirme sırası:** Önce MVP: `install.sh` + systemd servisi + ağ keşfi + envanter + uygulama üzerinden SSH anahtar kurulumu + salt-okunur durum kontrolü. Yedekleme, temizlik, profil sıfırlama, oturum kapatma ve politika işlemleri 2. aşamadır.
2. **Masaüstü ortamı:** Yalnızca GNOME desteklenir. GNOME olmayan hedefler envanterde "masaüstü desteklenmiyor" olarak işaretlenir; onlara politika uygulanmaz.
3. **Anahtar saklama:** Uygulama anahtarı parolasızdır; koruma, kısıtlı dosya izinleri (0600, yalnızca öğretmenin kullanıcısı) ve arayüz giriş parolasıdır. Şifreli kasa / kasa kilidi akışı yoktur. "Öğretmen PC ele geçirilirse tüm laboratuvarın anahtarı ele geçer" riski belgelenir ve anahtar iptal yolu sağlanır.
4. **Hesap modeli:** Yönetilecek öğrenci profili sabit `ogrenci` hesabıdır. Yönetim bağlantısı mevcut `pardus`/`hp` hesabıyla yapılır; sudo parola isterse yalnızca işlem süresince sorulur. Ayrı yönetim hesabı özelliği bu projede kapsam dışıdır.
5. **İmaj dağıtımı:** Konteyner imajı yalnızca kurulum paketi içindeki, sha256 toplamı doğrulanan `.tar` arşivinden `podman load` ile yüklenir. Registry'den imaj çekilmez; güncellemeler de aynı yolla (yeni paket) dağıtılır.
6. **Çalışma hesabı:** Uygulama, öğretmenin kendi kullanıcısında rootless Podman + `systemd --user` servisi olarak çalışır; ayrı yerel servis hesabı açılmaz.
7. **Ölçek:** Tek laboratuvar, ~20–30 bilgisayar hedeflenir; varsayılan paralellik 8–10, varsayılan tarama kapsamı küçük bir aralıktır.
8. **Quadlet yok:** Hedef Pardus 23.5'te Podman 4.3.1 vardır ve Quadlet desteklemez. Yalnızca klasik systemd kullanıcı servisi yazılır; Quadlet kodu üretilmez.
9. **Depolama sürücüsü:** Podman 4.3 rootless kurulumda kendiliğinden yavaş `vfs` sürücüsüne düşebilir (labda doğrulandı). `install.sh`, `~/.config/containers/storage.conf` dosyasına `driver = "overlay"` ve `mount_program = "/usr/bin/fuse-overlayfs"` yazmalı ve doğrulamalıdır. Gerekli dağıtım paketleri: `podman uidmap slirp4netns fuse-overlayfs catatonit`.
10. **Cihaz kimliği:** Laboratuvar makineleri aynı imajdan klonlanmış olabilir; SSH host anahtarı ve hostname birebir aynı çıkabilir (labda doğrulandı). Host anahtarı tek başına cihaz kimliği olarak kullanılmaz; envanter benzersiz dahili kimlik üretir ve yinelenen host anahtarını kullanıcıya raporlar.
11. **Dil:** Arayüz, kod yorumları ve belgeler Türkçe yazılır; adlandırmada da kütüphane API'leri dışında mümkün olduğunca Türkçe tercih edilir.
12. **Yönetim işlemlerinin uygulanışı:** §2 tablosundaki Ansible tercihi yerine, izin verilen "eşdeğer, daha az bakım gerektiren çözüm" seçeneği kullanılır: işlemler mevcut SSH kanalı üzerinden, hedefteki Python 3 ile çalışan ve sunucu tarafında sabit izin listeli uzak betiklerle yapılır. Gerekçe: küçük imaj, tek SSH yolu, hedefte ek kurulum yok. Parolasız Ansible envanteri dışa aktarımı yine sağlanır; Ansible tabanlı genişletme ileride eklenebilir (sistem yöneticisi genişletmesi de o aşamaya kalır).
13. **Yedek/karantina konumu:** Yedekler ve ders sonu temizliği karantinası öğrenci PC'de `/var/lib/pardus-sinif-yonetimi/` altında (root'a ait, 0700) tutulur. Öğretmen PC'ye kopyalama isteğe bağlı gelecek özelliktir. Yerel yedek disk arızasına karşı koruma sağlamaz; bu sınır arayüzde açıkça belirtilir.
14. **Standart politika kapsamı (2. aşama):** Şimdilik tek somut politika duvar kâğıdıdır: GNOME dconf sistem veritabanı (`/etc/dconf/db/local.d/`) ile varsayılan atama ve isteğe bağlı kilit. Politika listesi genişletilebilir yapıda tasarlanır.

### 26 Eylül 2026 revizyonu

Aşağıdakiler proje sahibiyle netleştirilmiştir; 5, 6, 8 ve 9 numaralı kararların yerini alır:

15. **Dağıtım `.deb` paketidir:** Öğretmen `sudo dpkg -i <paket>.deb` komutunu girer, her şey hazır olur. Podman kullanılmaz. Ana hedef taşınabilirlik ve son kullanıcıyı teknik ayrıntıyla yormamaktır. Paket gömülü Python (python-build-standalone) ve sha256 ile kilitlenmiş kütüphaneleri `/opt/pardus-sinif-yonetimi/` altında taşır; sistem Python'una bağlı değildir. Paket saf Python ile (`paketleme/deb_yap.py`) üretilir.
16. **Çalışma hesabı:** Uygulama, ayrıcalıksız `pardus-sinif` sistem kullanıcısıyla, sertleştirilmiş sistem düzeyi systemd servisi olarak çalışır; veriler `/var/lib/pardus-sinif-yonetimi/` (0700) altındadır. `apt remove` verileri korur, `apt purge` siler. İlk kurulum kodunu yalnızca yönetici okuyabilir (pkexec).
17. **Ders sonu temizliği:** Öğretmen temizlenecek alanları onay kutularıyla seçer: Masaüstü, İndirilenler, Çöp, Belgeler, Resimler, Müzik, Videolar, tarayıcı geçmişi/çerezleri, son açılan dosyalar. Genel seçim tüm seçili bilgisayarlara tepeden verilir ve hatırlanır; tek bilgisayara özel istisna **yalnızca o temizlik için** geçerlidir, kaydedilmez. (§9.4'teki "Belgeler varsayılan kapsam dışında" kuralı korunur: Belgeler varsayılan olarak seçili değildir.)
18. **Yedekten dönüş:** Yedekler öğrenci PC'de kalır; öğrenci verisi öğretmen PC'ye taşınmaz. "Yedekten dön", hedef PC'deki yedekleri canlı listeler; öğretmen bir yedeği seçer ve **tamamına** geri döner. Çakışmada SHA-256 özeti aynıysa üzerine yazılır, farklıysa ikisi de tutulur (geri gelen `ad (yedek <tarih>)` adını alır). Temizlik karantinası da aynı ekrandan geri alınır. Yazma, öğrencinin yetkisine düşürülmüş süreçte yapılır. Karar 13'teki "öğretmen PC'ye kopyalama" gelecek özelliği bu kararla kapsam dışıdır.
19. **Envanter:** Öğretmen envanteri görür; elle ekleme ve çıkarma yapar, bilgisayar başına bağlantı (login) hesabını değiştirebilir. Hesap değişince anahtar yeniden kurulur. Çıkarırken isteğe bağlı olarak o bilgisayardaki uygulama anahtarı kaldırılır.

20. **Ödev Teslim modülü** (`Pardus_Odev_Teslim_Modulu_Gelistirme_Promptu.md`): §2'deki "arayüz yalnız loopback" kuralı daraltılır — öğretmen yönetim paneli yerel kalır; yalnız öğrenci teslim portalı laboratuvar ağına açılır. Portal ayrı servis (`pardus-sinif-odev`) ve ayrı kullanıcıyla (`pardus-odev`) çalışır, yönetim verisine erişemez. Ayrıntılı kararlar ödev isteminin başındaki karar kaydındadır.

### 28 Eylül 2026 revizyonu (0.4.0)

Proje sahibinin yeni istemi ve yanıtlarıyla netleştirilmiştir; 4. kararın “sudo parolası işlem süresince sorulur” kısmının ve §5 keşif akışının yerini alır:

21. **hp / pardus tekilleştirme:** Her öğrenci bilgisayarında hp veya pardus'tan yalnız biri kalır. Yalnız biri varsa o kalır (isim birliği için hesap açılmaz); ikisi varsa öğretmen seçer (öneri pardus). Silinecek hesap önce öğrenci PC'de yedeklenir; korunacak hesapla bağımsız anahtar oturumu ve `sudo -n` doğrulanmadan silinmez; bağlantıyı sağlayan hesap kendi oturumundan silinmez. ogrenci/root/sistem hesapları kapsam dışıdır. Hiçbiri yoksa parola denenmez: “Yetkili hesap hazırlığı gerekiyor”.
22. **Parolasız sudo:** İlk hazırlıkta tek hesabın parolası bir kez alınır; uygulama anahtarı + `/etc/sudoers.d/pardus-sinif-yonetimi` (`NOPASSWD: ALL`, visudo ile doğrulanır) kurulur ve yeni oturumda yalnız anahtarla `sudo -n true` doğrulanır. Günlük işler `sudo -n` kullanır; yetki yoksa açık hata. NOPASSWD: ALL yönetim hesabına root eşdeğeri yetki verir ve belgelenir. ogrenci'ye sudo verilmez; root SSH açılmaz.
23. **Görünüm:** Hedef Pardus Karşılayıcı'nın “10” (Windows 10 benzeri) düzenidir; anahtarlar hedefteki Karşılayıcı tanımından okunur ve kurulu şemaya göre denetlenir. Farklı menü/panel eklentileri tespit edilip gösterilir, düzende olmayanlar kapatılır. dconf dosyaları Pardus EDU varsayılanlarını geçmek için `9x-` önekli yazılır. Yönetim hesabı AccountsService `SystemAccount=true` ile gizlenir; gerçek giriş ekranı görsel doğrulanmaz. XFCE geçişi ayrı plan ister (bu sürümde uygulanmaz).
24. **Yerel .deb dağıtımı:** Öğretmenin yüklediği pakete özel yetki; yapı ve SHA-256 doğrulanır, apt benzetimiyle plan çıkarılır; kaldırma, sürüm düşürme ve çözülemeyen bağımlılık engellenir; aynı sürüm yeniden kurulmaz; kurulu sürüm doğrulanır. Ödev portalı dosyaları bu akışa giremez.
25. **Tek envanter ve toplu seçim:** Envanter (M1-S1) tek yönetim noktasıdır; ekleme/içe aktarma bağlantı kurmaz. Seçim sayfalar arasında korunur; “görünen uygun”, “laboratuvardaki tüm uygun”, “temizle”. Korunan EBA/ETAP cihazları seçilemez. Onayda kesin hedef listesi gösterilir; iş başlayınca hedefler iş kaydına yazılır.
26. **Temizlik önizlemesi:** Bilgisayar başına tek satır ve özet kartları. Yedekler karar 18 gereği öğrenci PC'de kalır (proje sahibi 28 Eylül'de yeniden onayladı); “öğretmen PC'de gereken yedek alanı” 0 gösterilir. Mantıksal/ayrılmış boyut ayrı, sabit bağlantılar tek sayılır, ölçülemeyen 0 sayılmaz; sıfırlamada açılacak alan aralık olarak verilir.
27. **Referans kodları:** M = menü, S = sayfa, B = düğme (ör. M2-S1-B3; satırda M2-S1-B4-LAB01). Kodlar `uygulama/arayuz/referans.js` kayıt defterindedir, işleve bağlıdır, silinen kod yeniden kullanılmaz; testler denetler. Ağ taraması “Ağda Bul” (M1-S3) olarak Envanter altında kalır (proje sahibi kararı): yalnız pardus/hp hesapları, bütçeli deneme.

Açık kalan konular: kurumun hesap kilitleme eşiği, KVKK/saklama politikası, XFCE → GNOME geçişi.

### 4 Ekim 2026 revizyonu — Veyon modülü (karar 28–31)

28. **Veyon kurulumu uygulamadan:** Envanter altında M1-S4 “Veyon Ayarları” (M1-S3 Ağda Bul
    olduğu için S4; kodlar sabit). Veyon yalnız öğretmenin yüklediği `.deb`'den kurulur;
    resmî Pardus deposundan Veyon kurulmaz (kullanıcı kararı; lab CLI testlerinde depodaki
    paket kullanıldı). Karşıda Veyon varsa ve yüklenen paket daha yeniyse güncellenir; aynı
    sürüm atlanır; düşürme yapılmaz. Genel paket sayfası (M2-S2) Veyon paketini kabul etmez.
29. **Parçalı Debian paketleri:** Pardus EDU'da gelen `veyon-service` vb. 4.7.5 paketleri,
    resmî tek `veyon` paketinin `Conflicts/Replaces` tanımıyla yer değiştirir; yalnız bu
    aile için kaldırma izni vardır ve önizlemede gösterilir.
30. **Anahtar modeli:** yalnız public key yüklenir ve doğrulanır; öğretmen PC'de private
    key yalnız `stat` ile denetlenir, okunmaz. Uygulama anahtar üretmez. Aynı adlı farklı
    anahtar yedek + onayla değişir. Yapılandırma: `Authentication/Method=1`, anahtar
    içe aktarma, servis etkin; önce hedefte yedek, “geri yükle” ile dönülür.
31. **Menü:** ana menüler ikonlu ve açılır/kapanır; alt menüler (sayfalar) ikonlu. Kodlar
    değişmedi; emekli kod yok (önceki sürümde Veyon yönlendirme düğmesi yoktu).

### 4 Ekim 2026 (akşam) revizyonu — 0.6.0 (karar 32–35)

32. **Uyku yok:** öğrenci bilgisayarları boşta uykuya geçmez/kapanmaz (uyku hedefleri maskeli,
    GNOME ve GDM güç ayarları kilitli, logind boşta eylemi yok); ekran koruyucu (ekran
    karartma) serbest. Amaç: güç ayarı yüzünden erişilemez bilgisayar kalmaması.
33. **Zamanlı Kapatma (M2-S5):** at/cron benzeri bir kez/her hafta planı; systemd zamanlayıcısı,
    `Persistent=false` (kaçan kapatma açılışta uygulanmaz), uyarı süresi, bekleyen kapatmayı iptal.
34. **Görsellik:** M1-S1 Veyon benzeri ekran kutucukları + durum renk açıklaması; M1-S2 teknik
    olmayan dille üç adım (işlevler ve kodlar aynı).
35. **Ad ve logo:** görünen ad “Lab Kaptanı” (ekran + dümen logosu, özgün çizim); paket adı,
    servis adları ve veri dizinleri değişmedi (yükseltme uyumluluğu).

### 5 Ekim 2026 — 0.6.0 lab bulguları (karar 36–38)

36. **Uyarı süresi kendi zamanlayıcımızla:** `shutdown +N` kapanmaya 5 dk kala `/run/nologin`
    oluşturup root dışı SSH'yi kapattığı için uygulama bekleyen kapatmayı iptal edemiyordu (lab01'de
    görüldü; bilgisayar planlandığı gibi kapandı). Uyarı süresi geçici systemd zamanlayıcısıyla
    (`pardus-sinif-kapatma-bekliyor.timer`) beklenir; iptal öğrencilere bildirilir.
37. **Bildirim gdbus ile:** Pardus'ta `notify-send` kurulu gelmez; bildirim `gdbus` ile GNOME
    bildirim servisine gider (`notify-send` yedek yol).
38. **Giriş ekranı dconf profili:** Pardus/Debian'ın `/usr/share/dconf/profile/gdm` profili
    `system-db:gdm` okumaz; `/etc/dconf/profile/gdm` yoksa imzalı kopyası yazılır, geri alınca silinir.

## 1. Rolün ve hedefin

Deneyimli bir Linux, Python, Ansible ve kullanılabilirlik geliştiricisi olarak çalış. Pardus kullanan bir okul bilgisayar laboratuvarı için kurulumu kolay, güvenli, Türkçe arayüzlü bir merkezi yönetim uygulaması geliştir.

Öğretmen bilgisayarı Pardus işletim sistemine sahiptir. Öğrenci bilgisayarları öncelikle Pardus 23 / Eğitim imajlarıdır. Öğretmen teknik açıdan deneyimli olmayabilir; uygulamayı kullanmak için terminal, SSH veya Ansible bilmesi gerekmemelidir. Sistem yöneticisi ise gerektiğinde Ansible playbook'larını inceleyip genişletebilmelidir.

Uygulama iki mantıksal bölümden oluşmalıdır:

1. **Keşif ve sisteme alma:** Yetkili laboratuvar ağını tara, mevcut `pardus` veya `hp` hesabıyla erişimi doğrula, Pardus bilgisayarları listele ve uygulama üzerinden SSH anahtarlı bağlantıyı kur.
2. **Yönetim:** Kaydedilen bilgisayarlara SSH anahtarıyla bağlan; durum kontrolü, yedekleme, temizlik, profil ayarlarını sıfırlama ve standart politikaları uygulama işlemlerini gerçekleştir.

Bu bölümleri tek uygulama, tek kurulum ve ortak envanter altında sun. Kullanıcı iki ayrı ürün kurmasın. Keşif bileşeni ile Ansible yönetim bileşenini kod düzeyinde ayrı tut.

Temel akış: **Ağ seç → Tara → Kimlik doğrula → Anahtarlı yönetimi kur ve test et → Bilgisayarları seç → İşlemi önizle → Onayla → Sonuçları göster.**

## 2. Teknoloji ve dağıtım

Tercih edilen yapı:

| Bileşen | Tercih ve görev |
| --- | --- |
| Paketleme | Tek Podman konteyneri |
| Otomatik çalıştırma | Klasik systemd kullanıcı servisi (`systemd --user`); hedefteki Podman 4.3.1 Quadlet desteklemez (karar 8) |
| Arayüz | Tarayıcıdan kullanılan yerel Türkçe web arayüzü |
| Uygulama sunucusu | Python; FastAPI gibi hafif bir yapı |
| Ağ/SSH erişimi | Bakımı sürdürülen bir Python SSH kütüphanesi; kimlik doğrulama ve anahtar kurulumu |
| Yönetim işlemleri | Ansible Core ve gerekirse ansible-runner; kontrollü ve modüler playbook'lar |
| Envanter/iş geçmişi | SQLite; ayrıca parolasız Ansible envanteri dışa aktarımı |

Eşdeğer, daha az bakım gerektiren bir çözüm seçebilirsin; seçimin gerekçesini belirt. Gereksiz mikroservis, Kubernetes, Redis, ayrı veritabanı sunucusu veya ağır frontend altyapısı ekleme.

Öğretmen PC'ye Python, Ansible, Node.js veya geliştirme araçları ayrı ayrı kurdurma. Uygulama bağımlılıkları sürümleri sabitlenmiş konteyner imajında bulunsun. İmaj, kurulum paketi içinde `.tar` arşivi olarak hazır dağıtılsın (karar 5); öğretmenin bilgisayarında her açılışta paket indirilmesin veya imaj derlenmesin.

Arayüz, varsayılan olarak yalnızca öğretmen PC'den erişilebilen loopback adresine yayınlansın; örneğin port uygunsa `127.0.0.1:8080`. LAN'a veya internete varsayılan yayın yapma. İnternet olmadan günlük kullanım çalışsın; font, ikon, JavaScript ve CSS dosyaları yerel pakette olsun. Bulut hesabı veya dış servise veri gönderme gerektirmesin.

## 3. Öğretmen PC'de tek betikle kurulum

`install.sh` adlı Bash kurulum betiği hazırla. Hedef kullanım, indirilen ve doğrulanan paket içinden `bash install.sh` çalıştırılmasıdır. Betik gerektiğinde yönetici yetkisi istesin; öğretmene çok sayıda teknik komut veya yapılandırma dosyası düzenletmesin.

Betik şu işleri yapsın:

1. Pardus sürümü, mimari, disk alanı, Podman/systemd sürümleri ve gerekli özellikleri kontrol etsin. Desteklenmeyen ortamda anlaşılır açıklama ile dursun.
2. Eksik Podman ve gerekli rootless çalışma bağımlılıklarını uygun dağıtım paketlerinden kursun. Gereksiz masaüstü konteyner yöneticisi kurmasın.
3. Öğretmenin kullanıcısı için sınırlı izinli veri dizinlerini hazırlasın; ayrı servis hesabı açmasın (karar 6). Gerekli subordinate UID/GID eşlemelerini kontrol etsin.
4. Paketteki, sha256 toplamı doğrulanan yerel imaj arşivini `podman load` ile yüklesin; registry'den imaj çekmesin (karar 5). Çevrimdışı ortamda eksik işletim sistemi paketlerini açıkça listeleyip dursun; eksikleri gizlice internetten tamamlamaya çalışmasın.
5. Rootless Podman için otomatik çalışan systemd kullanıcı servisini öğretmenin hesabında kursun ve bu hesap için linger ayarını yapsın. Rootless servisi rootful unit içine yalnızca `User=` yazarak taklit etmesin.
6. Depolama sürücüsünü doğrulasın: `storage.conf` ile `overlay` + `fuse-overlayfs` yapılandırsın; `vfs` sürücüsüyle kuruluma devam etmesin (karar 9).
7. Uygun yerel portu seçsin, uygulamayı başlatsın ve HTTP sağlık kontrolü başarılı olana kadar sınırlı süre beklesin.
8. Öğretmenin masaüstüne/uygulama menüsüne “Pardus Sınıf Yönetimi” kısayolu eklesin. Kısayol doğru kullanıcıda varsayılan tarayıcıyı açsın; root olarak tarayıcı çalıştırmasın.
9. Türkçe sonuç göstersin: “Kurulum tamamlandı. Masaüstündeki Pardus Sınıf Yönetimi simgesinden açabilirsiniz.” Hata varsa çözüm önerisini ve maskelenmiş tanı kaydını sunsun.

Kurulum tekrar çalıştırıldığında envanteri, anahtarları ve kullanıcı ayarlarını silmesin; aynı anahtar çiftini durmadan yeniden üretmesin. Yarım kalan kurulum güvenle tekrar denenebilsin.

systemd davranışları:

- PC yeniden açılınca uygulama otomatik başlasın; öğretmen `podman run` veya `systemctl` komutu girmesin.
- Hata sonrası sınırlı yeniden deneme ve başlatma hız sınırı olsun; sonsuz hızlı hata döngüsü oluşmasın.
- İnternet veya laboratuvar ağı yokken de yerel arayüz açılabilsin; bağlantı sorununu ekranda bildirsin.
- Her açılışta imaj çekmesin. Güncellemeler kontrollü olsun; önce veri yedeği ve geri dönüş yolu sağlansın.
- Servis yeniden başlaması ağ taramasını, parola denemelerini veya yarım kalmış veri silme işlerini otomatik yeniden başlatmasın.

Envanter, SSH güven kayıtları, uygulama anahtarı, ayarlar ve geçmiş konteyner dışında kalıcı dizinde tutulsun. Öğretmenin hesabı dışındaki sıradan kullanıcılar gizli dosyaları okuyamasın. Podman soketini veya öğretmenin tüm ev dizinini konteynere bağlama; `--privileged` kullanma. TCP tabanlı keşif için raw socket yetkisi veya host network zorunlu kılma.

## 4. Öğrenci PC ön koşulları

İlk sisteme alma için:

- Bilgisayar öğretmen PC'den ağ üzerinden erişilebilir olmalı.
- SSH sunucusu kurulu, etkin ve güvenlik duvarında yönetim kaynağından erişilebilir olmalı.
- `pardus` veya `hp` hesabı mevcut olmalı; kullanıcı tarafından sağlanan geçerli parola ile SSH girişi mümkün olmalı.
- İlgili yönetim işlemleri için gereken sudo yetkisi bulunmalı.
- Ansible işlemleri için desteklenen Python 3 ve gerekli temel araçlar bulunmalı; Ansible veya özel sürekli ajan kurmak gerekmemeli.

Root hesabıyla SSH girişini açma veya zorunlu tutma. SSH kapalıysa uygulamanın uzaktan kendiliğinden açabileceğini iddia etme. Bu durumda teknik personelin öğrenci PC'de yerel olarak uygulayabileceği ayrı ve anlaşılır bir ön hazırlık kılavuzu/betiği sağla; öğretmen kurulumuyla karıştırma. Python gibi eksikler mevcut yetkili bağlantı üzerinden kurulabiliyorsa önce kullanıcı onayı al.

## 5. Bölüm A — Keşif ve erişim doğrulama

### Kullanıcı girdileri

- Açıkça seçilip onaylanmış IP aralığı/CIDR veya sınırlı IP listesi.
- Varsayılan kullanıcı adayları `pardus` ve `hp`.
- Kullanıcının kendi laboratuvarına ait olduğunu bildiği sınırlı parola adayları; maskeli giriş veya yerel dosyadan aktarım.
- Hariç tutulacak IP'ler; öğretmen PC ve altyapı cihazları varsayılan olarak kapsam dışında.

Parolaları sohbetten, buluttan veya harici kaynaktan isteme. Uygulamanın yerel arayüzünden al. Kapsam dışı ağları otomatik keşif kapsamına ekleme. Tarama başlamadan yaklaşık hedef sayısını ve kapsamını göster; varsayılan olarak küçük bir laboratuvar aralığı öner.

### İşleyiş

1. SSH erişimini TCP bağlantısıyla kontrol et; ping cevabını zorunlu koşul yapma.
2. Kimlik bilgisi göndermeden önce hedefin SSH sunucu kimliğini doğrula. Güvenilir `known_hosts` içe aktarımını veya parmak izi karşılaştırmalı ilk kayıt onayını destekle. İlk kullanımda yalnızca kullanıcı kabulüne dayalı güvenin sınırlarını açıkla; sessiz `AutoAddPolicy`/`StrictHostKeyChecking=no` kullanma.
3. Kullanıcı onayladığı hedeflerde, verilen adaylarla sınırlı ve hız kontrollü giriş doğrulaması yap. Otomatik parola üretme, geniş sözlük veya sınırsız deneme ekleme.
4. Hesap/cihaz başına toplam deneme bütçesi, zaman aşımı, bekleme ve iptal mekanizması uygula. Kurumun hesap kilitleme eşiği biliniyorsa altında kal; bilinmiyorsa ihtiyatlı sınır ve açık uyarı kullan. Kilitlenme riskinin sıfır olduğunu iddia etme. Yeniden tarama veya servis yeniden başlatma deneme bütçesini sessizce sıfırlamasın.
5. Başarılı girişte diğer parola adaylarını denemeyi bırak. Kilitlenme/hız sınırı işaretinde hedef için dur.
6. Başarılı girişten sonra `/etc/os-release` gibi yerel işletim sistemi bilgileriyle Pardus kimliğini/sürümünü, hostname ve kullanıcı bilgilerini doğrula. SSH banner'ından veya IP adresinden Pardus sürümü tahmin etme.
7. Sudo yetkisini yalnızca grup üyeliğinden çıkarsama; sistem değiştirmeyen bir doğrulamayla gerekli yetkinin kullanılabilirliğini kontrol et. SSH parolası ile sudo parolasının farklı olabileceğini ele al.
8. Sonuçları anlık listele ve envantere kaydet. Pardus olmayan veya kimliği doğrulanamayan hedefi yönetilebilir diye işaretleme.

Bağlanmadan önce `pardus` veya `hp` hesabının gerçekten var olduğunu kesin bildiğini iddia etme. “Kimlik doğrulanamadı”, tek başına “kullanıcı yok” anlamına gelmez.

### Envanter alanları ve durumlar

Hostname, IP, SSH portu, Pardus adı/sürümü, SSH bağlantı hesabı, yönetilecek profil hesabı, sudo durumu, anahtarlı erişim durumu, doğrulanmış SSH parmak izi, laboratuvar grubu ve son kontrol zamanı bulunsun. IP değişikliğini cihazın aynı olduğu varsayımıyla sessizce kabul etme; kimlik doğrulamasını koru. Envanterde cihaz için benzersiz dahili kimlik kullan.

Durumlar birbirinden ayrı olsun: “SSH erişilemiyor”, “Kimlik onayı gerekli”, “Kimlik doğrulanamadı”, “Pardus doğrulandı”, “Sudo yetkisi yetersiz”, “Anahtar kurulumu gerekli”, “Anahtarlı erişim OK”, “Yönetilebilir”. Hedef erişilemiyorsa bilgisayarın kesin kapalı olduğunu söyleme.

Keşif aşaması yalnızca durum toplasın. Anahtar kurulumu, hesap açılması veya politika değişiklikleri ayrı, açıkça onaylanan sisteme alma adımı olsun.

## 6. Uygulama üzerinden SSH anahtarı kurulumu

“Seçilileri anahtarlı yönetime al” işlemini ekle. Öğretmenin `ssh-keygen` veya `ssh-copy-id` kullanması gerekmesin.

1. Uygulamaya/kuruluma özel bir Ed25519 anahtar çifti güvenli biçimde oluştur veya mevcut uygulama anahtarını kullan. Başka uygulamanın/öğretmenin kişisel anahtarına dokunma.
2. İlk girişin doğrulandığı `pardus` veya `hp` hesabına açık anahtarı ekle. (Ayrı yönetim hesabı kapsam dışıdır; karar 4.)
3. Hedef hesabın gerçek ev dizinini sistemden tespit et; `/home/<ad>` varsayımı yapma. `.ssh` ve `authorized_keys` için doğru sahiplik ve sınırlı izinleri uygula.
4. Mevcut `authorized_keys` içeriğini koru. Yalnızca uygulamanın anahtarını, yinelenmeyecek şekilde ekle. Güvensiz sembolik bağlantı veya sahiplik durumunda dur; genel dosya/izin düzeltmesi yapma.
5. Eski bağlantıyı açık tutarken yeni ve bağımsız bir SSH oturumu aç. Bu testte parola, keyboard-interactive, başka anahtar veya SSH agent kimliği ile geri dönüşe izin verme; yalnızca eklenen anahtarın çalıştığını kanıtla.
6. Test başarılıysa “Anahtarlı bağlantı OK” durumuna geçir. Gerekli sudo kullanılabilirliğini ayrıca göster.
7. Başarısızsa eski erişimi bozma; hangi adımın başarısız olduğunu bildir. Uygulamanın yaptığı değişiklikleri sınırlı ve güvenli biçimde geri alabilecek kayıt tut.

Özel anahtar öğrenci PC'ye gönderilmesin. Anahtar eklemek için SSH sunucusunun parolalı erişimini veya başka yöneticilerin erişimini otomatik kapatma. Daha sonra sertleştirme istenirse ayrı onay, yapılandırma doğrulaması, yeniden bağlantı testi ve geri dönüş planı uygula.

Anahtar yenileme/iptal işlemi yalnızca uygulamaya ait anahtarı etkilemeli. Yenilemede yeni anahtarı test etmeden eskisini kaldırma.

### Anahtarlı SSH ve sudo ayrımı

SSH anahtarı sudo parolası ihtiyacını kendiliğinden ortadan kaldırmaz. Anahtarlı bağlantı sonrası yönetim için şu iki modu açıkça ele al:

- **Mevcut hesap modu:** SSH anahtarı mevcut `pardus`/`hp` hesabına kurulur. Sudo parola istiyorsa uygulama yalnızca yönetim oturumu/işlem süresince bu parolayı güvenli biçimde ister; SSH parolasıyla yeniden bağlantıya dönmez. Kalıcı açık parola saklama veya öğrenci hesabına sessiz `NOPASSWD: ALL` ekleme.
- **Ayrı yönetim hesabı (kapsam dışı, karar 4):** Bu sürümde geliştirilmez. İleride eklenecekse şu kurallar geçerlidir: kullanıcı onayı, açıklanmış sudo politikası, anahtarlı bağlantı ve sudo testi, yönetim hesabının profil temizliği kapsamı dışında tutulması. Geniş sudo gerekirse bunun root eşdeğeri yetki olduğunu açıkça belirt; kullanıcının yazabildiği betik/dosyaları root çalıştıran sahte dar yetki kuralı oluşturma.

Öğrencinin günlük kullandığı hesabın sudo yetkisi olduğu görülürse bunu risk olarak raporla. İlk keşifte veya yönetim hesabı testi tamamlanmadan mevcut hesabın yetkilerini kaldırma.

## 7. Kimlik bilgileri ve uygulama güvenliği

- İlk bağlantı parola listesi varsayılan olarak yalnızca işlem belleğinde yaşasın; işlem sonunda referansları bırakılsın. Kalıcı parola listesi, tarayıcı localStorage kaydı veya geçmişten parola görüntüleme ekleme. Belleğin adli yöntemlere karşı kusursuz temizlendiğini iddia etme.
- Parola ve özel anahtarları loglara, URL'lere, komut satırı argümanlarına, envanter dışa aktarımına, hata raporlarına veya container imajına koyma. Ansible çıktıları dahil gizli alanları maskele; hassas görevlerde `no_log` kullan.
- Uygulamanın özel anahtarı parolasızdır (karar 3); yalnızca kısıtlı dosya izinleriyle (0600, öğretmenin kullanıcısı) kalıcı dizinde saklanır. Anahtarı yedeklere, dışa aktarımlara veya konteyner imajına kopyalama. Öğretmen PC'nin ele geçirilmesinin tüm laboratuvar anahtarını ele geçirmek anlamına geldiğini belgele.
- Servis açılışta otomatik başlasın. Yönetim işlemleri, arayüzde öğretmenin giriş parolasıyla açılmış bir oturum gerektirsin; oturum yokken API uçları anahtar kullanan hiçbir işlemi başlatmasın.
- Yerel arayüzde de kimlik doğrulama, CSRF ve Origin/Host kontrolü uygula. Varsayılan ortak parola kullanma. İlk yönetici oluşturma akışı yalnızca yetkili yerel kullanıcı tarafından tamamlanabilsin.
- Serbest shell komutu veya playbook yolu girişi sunma. Sunucu tarafında işlem ve hedef izin listesi uygula; yalnızca arayüzde buton gizlemekle yetinme. Alt süreçleri argüman listeleriyle çalıştır.
- Öğretmenin anahtarı birçok PC'yi yönetebileceğinden öğretmen PC güvenliğinin önemini ve kayıp/çalınma durumunda uygulama anahtarını iptal etme yolunu belgele.

## 8. Bölüm B — Yönetim işlemleri

Yönetim ekranı keşiften gelen envanteri kullansın. Tek PC, seçilen PC'ler ve seçilen laboratuvar üzerinde çalışabilsin. Her çalıştırmadan önce güncel erişim, kimlik, hedef kullanıcı ve gerektiğinde sudo kontrolü yapılsın. Bir bilgisayarın hatası diğer bilgisayarların sonuçlarını yanlış göstermesin.

| İşlem | Beklenen davranış |
| --- | --- |
| Durumu kontrol et | Kalıcı politika veya kullanıcı verisi değiştirmeden erişim, sürüm, masaüstü ortamı, kullanıcı, sudo, disk ve politika durumunu raporla. Ansible'ın geçici çalışma dosyalarını kalıcı değişiklikten ayır. |
| Standart duvar kâğıdı | Görseli sistemin korunan konumuna yerleştir; doğru kullanıcının masaüstüne uygula. |
| Duvar kâğıdı/ayar kilidi | GNOME oturum tipine uygun desteklenen yöntemi (dconf) kullan; desteklenmeyen kilidi “kilitlendi” olarak sunma. |
| Ders sonu temizliği | Önizleme ve onayla, yalnızca seçilmiş kullanıcıya ait izinli Masaüstü/İndirilenler/çöp alanlarını temizle veya kurtarılabilir karantinaya taşı. |
| Kullanıcı yedekleme | Belirlenen kapsamı, dosya izinlerini ve yeterli alanı kontrol ederek yedekle; doğrulama ve geri yükleme imkânı sağla. |
| Profil ayarlarını sıfırla | Öğrenci oturumu açıksa öğretmeni açıkça uyar. Öğretmen yalnızca ilgili bilgisayarda veya seçilen tüm bilgisayarlarda oturumu zorla kapatma seçeneğini kullanabilsin. Kapatma ve veri kaybı riski onaylanmadan devam etme; ardından doğrulanmış yedek alıp seçilen profil kapsamını standarda döndür. |
| Standarda getir | Seçilmiş ve desteklenen politikaların sapmalarını düzelt; zaten doğru durumda gereksiz değişiklik yapma. |
| Yeniden başlat / kapat | Kaydedilmemiş çalışma riskiyle birlikte hedefleri gösterip onay al; komut gönderildi ile kapanma/yeniden açılma doğrulandı durumlarını ayır. |

Masaüstü ortamını yalnızca SSH oturumunun `XDG_CURRENT_DESKTOP` değerinden çıkarsama; kurulu ortam ve gerçek oturum doğrulanarak GNOME olduğu teyit edilsin. GNOME değilse hedef "masaüstü desteklenmiyor" olarak işaretlensin ve politika uygulanmasın (karar 2); GNOME olmayan ortama dconf kuralı uygulayıp başarı raporlama.

Bağlantı hesabı ve işlem yapılacak öğrenci hesabı ayrı alanlar olsun. Yönetilen profil ile aktif yönetim hesabı aynıysa o hesabın ev dizinini/SSH erişimini bozan sıfırlama reddedilsin. (Yönetim `pardus`/`hp`, yönetilen profil `ogrenci` olduğundan normalde çakışma beklenmez; yine de bu kontrol zorunludur.)

Veyon canlı ekran izleme/kontrolü için ayrı, isteğe bağlı araç olarak kalabilir. Bu projede ekran izlemeyi yeniden geliştirme; temel işlevleri Veyon kurulumuna bağımlı yapma.

## 9. Temizlik, yedekleme ve veri koruma

Veri silen işlemlerde güvenlik zorunludur:

1. Hedef hesabın gerçek ev dizinini ve XDG kullanıcı klasörlerini güvenli şekilde çöz; `Desktop`/`Masaüstü` adını sabit varsayma. Kullanıcı dosyasını shell kodu olarak source etme.
2. Boş yol, kök dizin, ev dizininin tamamı, sistem dizini, izin listesi dışı konum, sembolik bağlantıyla dışarı çıkış ve beklenmeyen mount hedeflerini reddet. XDG klasörü ev dizininin kendisine işaret ederse onu temizleme. Genel `/tmp` veya diğer kullanıcıların dosyalarını hedefleme.
3. İşlemden hemen önce hedef kimliklerini/yollarını yeniden doğrula; önizlemeden sonra yol değişimi veya yarış koşulunda güvenli dur. Mümkünse kurtarılabilir taşıma ve güvenli dosya tanıtıcısı temelli işlemler kullan.
4. Belgeler/Documents ve kullanıcı tarafından korunacak seçilmiş dizinler varsayılan kapsam dışında kalsın. Ders sonu temizliği ile profil ayarlarını sıfırlama ayrı işlevler olsun. Profil sıfırlama adına tüm ev dizinini sessizce silme.
5. `ogrenci` oturumu açıksa işlemi sessizce durdurma ve doğrudan silmeye başlama. Öğretmene hangi bilgisayarlarda hangi kullanıcıların aktif olduğunu gösteren bir uyarı sun: “Öğrenci oturumu açık; devam ederseniz kaydedilmemiş veriler kaybolabilir.” Bu uyarıdan sonra salt-okunur kontroller ve güvenli yedekleme akışı devam edebilir; profil sıfırlama gibi yıkıcı adım için ayrıca oturum kapatma seçimi gerekir.
6. Öğretmen iki kapsamdan birini seçebilsin:
   - **Yalnızca bu bilgisayarda oturumu kapat:** Sadece seçilen tek hedefteki `ogrenci` oturumunu güvenli kapatmayı dene.
   - **Seçilen tüm bilgisayarlarda oturumları kapat:** İşlem listesindeki aktif `ogrenci` oturumlarını olan bütün seçili hedeflerde uygula.
7. Zorla oturum kapatma ayrı ve belirgin bir onay gerektirsin. Onay ekranında hedef bilgisayarlar, aktif kullanıcılar ve kaybolabilecek kaydedilmemiş çalışmalar yazsın. Öğretmen zorla kapatmayı seçmezse yıkıcı profil sıfırlama işlemini erteleyebilsin; uygulama güvenli kontrolleri ve yapılmış yedekleri koruyarak sonucu “Profil sıfırlama bekliyor” diye işaretlesin. “Gönderildi” ile “oturum kapandı” durumlarını ayrı raporla.
8. Oturum kapatma başarısızsa veya hedefte başka bir yönetim oturumu varsa profil sıfırlama işlemini o bilgisayarda başlatma. Diğer hedeflerin sonuçlarını bağımsız olarak sürdür.
9. Oturum kapandıktan sonra proseslerin ve kullanıcı mount'larının sonlanmasını doğrula; profil dizinini yeniden kontrol et. Doğrulama tamamlanmadan yedekleme/sıfırlama adımına geçme.
10. Zorla kapatma özelliği `root`, sistem hesapları veya öğretmen/yönetim hesabı oturumlarını varsayılan olarak kapatmasın. Bu hesaplar için ayrı, yönetici onaylı bir işlem tanımlanmadıkça yalnızca `ogrenci` hedeflenebilir.
11. Profil sıfırlamada doğrulanmış yedeği zorunlu tut. Normal temizlikte kurtarılabilir karantina veya varsayılan açık yedekleme uygula; geri dönüşsüz silme ayrı ve belirgin onay gerektirsin.
12. Yedek kapsamını önceden göster; kaynak ve hedef disk alanını kontrol et. Yerel istemci yedeğinin disk arızasına karşı koruma sağlamadığını belirt. Öğretmen PC'ye alınan yedeklerde transferi de doğrula.
13. Yedek doğrulaması arşivin varlığıyla sınırlı kalmasın; okunabilirlik, bütünlük kontrolü ve geri yükleme testleri sağla. Başarısız/eksik yedekte sonraki silme adımına geçme.
14. “Yedekler / Geri yükle” ekranı, seçilmiş hedefe geri yükleme önizlemesi ve veri çakışması uyarısı sun. Arşiv açarken yol kaçışı ve sembolik bağlantı risklerini engelle.
15. Yedek/karantina saklama süresi ve kapasite sınırı ayarlanabilsin. Doğrulanmış kurtarma kopyasını işlem ortasında otomatik silme. Yedekler gizli öğrenci verisi içerebilir; erişimi sınırlandır.

Ansible `--check` desteğinin her özel işlemde tam önizleme sağladığını varsayma. Temizlik kapsamını ve tahmini boyutu özel, salt durum okuyan bir önizleme adımıyla hesapla. Önizleme güvenle üretilemiyorsa silmeyi başlatma.

## 10. Sade, modern ve açıklayıcı Türkçe arayüz

Teknik olmayan öğretmeni hedefle. Ferah boşluklar, okunabilir yazı, açık zemin, sınırlı renk paleti ve anlaşılır ikonlar kullan. Durumu yalnızca renkle anlatma; her ikonun metin karşılığı olsun. 1366×768 sınıf bilgisayarı ekranında kullanılabilirliği doğrula; klavye erişimi, görünür odak ve yeterli kontrast sağla.

Ana ekranlar:

- **Başlangıç:** Kısa ilk kullanım sihirbazı; hizmet ve yönetim anahtarı durumu.
- **Bilgisayarları bul:** Ağ seçimi, kullanıcı/parola adayları, kapsam onayı, tarama ilerlemesi ve sonuç listesi.
- **Yönetime al:** Hedef kimliğini doğrulama, anahtar kopyalama ve yeni bağlantıyı test etme adımları.
- **Bilgisayarlarım:** Laboratuvar filtresi, arama, çoklu seçim, IP/hostname/sürüm ve ayrı SSH/sudo durumları.
- **İşlem önizlemesi:** Seçili bilgisayarlar, hedef kullanıcı, aktif oturumlar, değişecek/korunacak alanlar, yedek durumu, ölçülebildiğinde tahmini veri miktarı ve onay. Oturum açıksa “Yalnızca bu bilgisayar” ve “Seçilen tüm bilgisayarlar” seçenekleri görünür.
- **İşlem merkezi:** Bilgisayar bazında ilerleme, başarılı/başarısız/bekleyen sayıları, iptal ve güvenli yeniden deneme.
- **Yedekler ve geçmiş:** Geri yükleme, işlem geçmişi ve hassas bilgi içermeyen sonuç dışa aktarımı.
- **Ayarlar ve yardım:** Ağ kapsamı, laboratuvar grupları, duvar kâğıdı, politika/koruma tercihleri ve kısa Türkçe yardım.

Kullanıcı her an ne yapıldığını görsün. Örnek aşama mesajları:

- “Ağ kontrol ediliyor — 30 adresin 12'si incelendi.”
- “LAB05 — Kullanıcı bağlantısı doğrulandı.”
- “LAB05 — Yönetim anahtarı ekleniyor.”
- “LAB05 — Yalnızca yeni anahtarla bağlantı test ediliyor.”
- “LAB05 — Anahtarlı bağlantı hazır; sudo onayı gerekli.”
- “LAB05 — ogrenci oturumu açık; kaydedilmemiş veriler kaybolabilir.”
- “LAB05 — Öğretmen zorla oturum kapatmayı onayladı; oturum kapatılıyor.”
- “LAB05 — Oturum kapandı; profil işlemi için süreçler doğrulanıyor.”
- “LAB05 — Yedek doğrulandı; izinli klasörler temizleniyor.”
- “LAB05 — İşlem tamamlandı; Belgeler korundu.”

Sahte ilerleme yüzdesi, varsayılan başarılı sonuç veya çalışmayan buton kullanma. Bilinmeyen süre için dönen gösterge ve gerçek aşama ismi yeterlidir. Hatalarda üç parçalı açıklama ver: **Ne oldu? Hangi PC etkilendi? Kullanıcı ne yapabilir?**

Ham Ansible/SSH çıktısı ana ekranı doldurmasın. “Teknik ayrıntılar” altında maskelenmiş gerçek loglar bulunabilsin. Hedef bilgisayardan gelen hostname ve hata metinlerini güvenilmeyen veri olarak işle; HTML/komut enjeksiyonunu engelle.

## 11. İş takibi, bakım ve kurtarma

- Uzun işlemler arka planda çalışsın; arayüz donmasın. Tarayıcı kapanıp açıldığında devam eden işin gerçek durumu geri gelsin.
- Aynı PC/profil üzerinde birbiriyle çakışan veri değiştirici işleri engelle. Ağ ve yedekleme yükü için sınırlı paralellik kullan.
- Kuyrukta iptal ile yürütülen işlemin güvenli noktada durmasını ayır. İptal tuşunun başlamış silmeyi geri aldığı iddiasında bulunma.
- Her hedefin sonucunu ayrı kaydet. Toplu işin tek dönüş kodunu bütün bilgisayarlara aynı başarı/hata olarak kopyalama.
- Uygulama/PC beklenmedik kapanırsa yarım kalan işi “Kesildi — kontrol gerekli” olarak işaretle. Güvenli durum doğrulaması yapmadan yıkıcı işi otomatik tekrar etme.
- Loglarda zaman, işlem kimliği, uygulama kullanıcısı, hedef PC, hedef profil, aşama, sonuç ve varsa yedek referansı bulunsun; sırlar ve gereksiz öğrenci dosya içerikleri bulunmasın.
- Güncelleme paketinde veri tabanı geçişlerini, eski sürüme dönme kısıtlarını ve yedeklemeden kurtarmayı belgele. İmajı geri almak tek başına veri tabanı sürümünü geri alıyormuş gibi sunma.
- Kaldırma işlemi varsayılan olarak envanter/anahtar/yedek verilerini korusun. Verileri silme ve istemcilerdeki uygulama anahtarını iptal etme ayrı, açıkça onaylanan işlemler olsun.

## 12. Teslimatlar

Yalnızca mimari açıklama veya görsel taslak teslim etme; uygulanmış ve sınırları dürüstçe belgelenmiş bir proje üret:

1. Modüler kaynak kod ve gerçek backend'e bağlı Türkçe web arayüzü.
2. Containerfile, sabitlenmiş bağımlılıklar ve tekrarlanabilir imaj üretme talimatı.
3. Test edilmiş öğretmen `install.sh` betiği; güncelleme/kaldırma yardımcıları ve masaüstü kısayolu.
4. Uyumlu systemd kullanıcı servisi dosyaları, sağlık kontrolü ve otomatik açılış kurulumu.
5. Keşif, sınırlı kimlik doğrulama, envanter ve uygulama üzerinden anahtar kurulum bileşenleri.
6. Durum, yedek, güvenli temizleme, profil ayarı sıfırlama, duvar kâğıdı, politika, kapatma/yeniden başlatma için modüler Ansible playbook/rolleri.
7. Demo modu ve gerçeğe uygun örnek envanter. Demo modunun ağ taramadığı veya gerçek PC'lerde işlem yapmadığı belirgin olsun.
8. Teknik olmayan öğretmene yönelik ekran görüntülü Türkçe “İlk kullanım — 101” kılavuzu ve ayrı yönetici kılavuzu.
9. Otomatik testler, uçtan uca test senaryoları, desteklenen Pardus/masaüstü/Podman sürüm matrisi ve bilinen sınırlamalar.
10. Çevrimdışı imaj yükleme seçeneği; ilk kuruluma gereken dağıtım paketlerinin durumu ve güvenli güncelleme/geri yükleme yolu.

## 13. Kabul testleri

En az şu davranışları test et ve hangilerinin gerçek Pardus üzerinde, hangilerinin test doubles/demo ile doğrulandığını ayır:

- Tek kurulum betiği temiz desteklenen Pardus ortamında uygulamayı kullanılabilir hale getirir; ikinci çalıştırma verileri bozmaz.
- Öğretmen PC yeniden başlatılınca servis kendiliğinden gelir, kısayol arayüzü açar; internet yokken de arayüz çalışır.
- Uygulama yalnızca onaylanmış ağ aralığını tarar; kimlik bilgileri bilinmeyen/değişmiş SSH kimliğine sessizce gönderilmez.
- Yanlış parola, kapalı SSH, sudo eksikliği, Pardus olmayan cihaz ve ağ zaman aşımı farklı sonuçlar üretir.
- Deneme sınırları ve durdurma mekanizması çalışır; tekrar taramayla sınırsız parola denemesine dönüşmez.
- İlk parola doğrulamasından sonra anahtar arayüzden kurulur. Mevcut yetkili anahtarlar korunur; ikinci kurulum yinelenen kayıt eklemez.
- Parola geri dönüşü kapalı, bağımsız yeni oturum testi anahtarın çalıştığını kanıtlar; sonraki SSH yönetimi bu anahtarla yapılır.
- SSH anahtarı başarılı ancak sudo parola gerektiriyor durumu doğru gösterilir; tam yönetim hazırmış gibi raporlanmaz.
- Envanter, günlükler, dışa aktarımlar ve hata dosyalarında parola/özel anahtar yoktur.
- Sembolik bağlantı, ev dizinine işaret eden XDG yolu, yol değiştirme ve yedekleme hatası testleri veri silmeyi engeller.
- Açık öğrenci oturumu ve yönetim hesabını bozan profil sıfırlama engellenir.
- Açık `ogrenci` oturumunda öğretmen uyarılır; yalnızca ilgili bilgisayar veya seçilen tüm bilgisayarlar için zorla oturum kapatma seçimi yapılmadan profil sıfırlama başlamaz.
- Zorla oturum kapatma sonrası kapanma doğrulanmadan ve aktif proses/mount kalmadığı kontrol edilmeden profil sıfırlama başlamaz.
- Temizlik/sıfırlama sonrasında Belgeler ve korunacak alanlar aynı kalır; test yedeğinden geri yükleme doğrulanır.
- Toplu işlemde bir PC başarısız olduğunda diğer PC'lerin gerçek sonuçları korunur; tarayıcı yenileme ve servis kesintisi doğru ele alınır.
- Anahtarlar ve envanter konteynerin yeniden oluşturulmasından sonra korunur; arayüz oturumu açılmadan yönetim işlemi başlatılamaz.
- GNOME politika sonuçları gerçek hedef oturumda doğrulanır; GNOME olmayan hedefler ve desteklenmeyen özellikler açıkça işaretlenir.

Önce bir test bilgisayarında doğrula; sonra küçük pilot grupla genişlet. Test yapmadığın bir özelliği “çalışıyor” veya “üretime hazır” diye sunma. Eksik işlevi sahte başarıyla örtme.

## 14. Geliştirme sırasında izlenecek yaklaşım

Önce kısa mimari ve veri/kimlik güvenliği kararlarını açıkla. Ardından sırayla kurulum ve servis yaşam döngüsü, keşif/envanter, anahtar kurulumu, salt durum kontrolü, yedek/geri yükleme, güvenli temizlik ve politika işlemlerini geliştir. Her aşamada kullanılabilir bir sonuç ve test üret.

Tercih belirtilmeyen küçük konularda bu hedeflere uygun varsayımlar yapıp belgele. Güvenlik veya veri kaybı açısından kritik eksik kararda sessizce varsayım yapma. Öğretmenin teknik bilgi ihtiyacını, kurulum adımı sayısını ve sürdürülecek bağımlılıkları asgari tut. Kod yorumları, belgeler ve arayüz Türkçe yazılır (karar 11).

**Başarı ölçütü:** Teknik olmayan öğretmen uygulamayı kurar; bilgisayarları bulur; ilk parola erişiminden sonra tek arayüz üzerinden anahtarlı yönetime geçirir; her gün masaüstü simgesinden açıp hangi bilgisayarda ne yapıldığını görerek güvenli yönetim işlemleri gerçekleştirir.

---

## Test laboratuvarı

Geliştirme ve kabul testleri şu gerçek ortamda yapılır (her ikisi Pardus 23.5, GNOME):

- **Öğretmen PC:** uygulamanın kurulduğu Pardus 23.x makinesi; yönetici hesabı sudo yetkili.
- **Öğrenci PC'ler:** aynı imajdan kurulmuş (klon) Pardus bilgisayarlar; yönetilecek profil `ogrenci` (sudo yetkisi yok).
- Test parolaları bu belgeye, kod deposuna, loglara veya örnek verilere yazılmaz; sistem yöneticisinden alınır.
- Öğrenci PC'nin SSH host anahtarları klon imaj nedeniyle yenilendi; keşif testlerinde parmak izi doğrulaması bu makinelere göre yapılır.

---

## Geliştirici için resmî başvuru kaynakları

Hedef Pardus paketleriyle uyumluluğu uygulama sırasında ayrıca doğrula. En yeni belgedeki her özelliğin Pardus'ta kurulu sürümde bulunduğunu varsayma.

- Podman systemd/Quadlet, rootless unit yerleşimi ve otomatik başlatma: [Podman systemd unit belgeleri](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html).
- SSH bağlantısı, anahtar kullanımı ve host key doğrulaması: [Ansible bağlantı belgeleri](https://docs.ansible.com/projects/ansible/latest/inventory_guide/connection_details.html).
- SSH girişinden ayrı sudo/become yetkilendirmesi: [Ansible privilege escalation belgeleri](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_privilege_escalation.html).
- İstemci Python gereksinimi ve konteyner tabanlı kontrol düğümü: [Ansible kurulum belgeleri](https://docs.ansible.com/projects/ansible/latest/installation_guide/intro_installation.html).
- Yetkili anahtar dosyaları ve SSH sunucu davranışı: [OpenSSH sshd kılavuzu](https://man.openbsd.org/sshd).
