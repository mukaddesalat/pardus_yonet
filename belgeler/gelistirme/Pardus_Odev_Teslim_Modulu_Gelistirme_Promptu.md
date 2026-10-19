# Pardus Sınıf Yönetimi — Ödev Teslim Modülü Geliştirme İstemi

**Tarih:** 26 Eylül 2026  
**Kullanım:** Mevcut `Pardus_Sinif_Yonetimi_Gelistirme_Promptu.md` dosyasına ek gereksinim olarak uygulanacak bağımsız geliştirme istemidir. Hedef davranışı tarif eder; uygulamanın tamamlandığı veya test edildiği anlamına gelmez.

## 0. Karar kaydı (26 Eylül 2026)

Proje sahibiyle netleştirilmiştir; metnin geri kalanıyla çeliştiği yerde bu bölüm geçerlidir:

1. **Mevcut mimariye uyarlama:** Podman/Bash kurulum yerine aynı `.deb` paketinde ikinci systemd servisi; Ansible yerine mevcut izin listeli uzak betikler; "SSH anahtar kasası" yoktur (ana istem karar 3) — karşılığı: portal, öğretmen panele giriş yapmamışken ve yönetim servisi kapalıyken de teslim alır. Ana projedeki yedek saklama sayı bazlıdır; ödevler buna hiç girmez.
2. **Kişisel teslim kodu:** 8 karakter harf+rakam (`XXXX-XXXX`, karışan 0/O/1/I/L yok), scrypt özeti saklanır, yalnız üretimde gösterilir/yazdırılır.
3. **Düz HTTP:** §7.6'daki HTTPS şartından bilinçli sapma. Kodlar ve dosyalar laboratuvar ağında şifresiz taşınır; risk kılavuzlarda belirtilir. Portal portu: 80 boşsa 80, değilse 8090–8099.
4. **Kaldırma:** `apt remove` ve `apt purge` öğrenci teslimlerini silmez; teslimler yalnız uygulama içinden (arşivlenmiş ödev + açık onay) silinir.
5. **İki aşama:** 1) çekirdek — sınıf listesi/kodlar, ödev yaşam döngüsü, portal, güvenilir yükleme ve sürümler, takip, ZIP indirme (tamamlandı, 0.3.0); 2) dağıtım — öğrenci PC'lerine `ogretmen.lab` ad kaydı ve kısayol, aktif yükleme sırasında profil sıfırlama uyarısı, 21–40 eşzamanlı öğrenci yük testi.

## 1. Görev

Mevcut Pardus Sınıf Yönetimi uygulamasına **Ödev Teslim** modülü ekle. Öğretmen, kendi bilgisayarında ödev oluşturabilsin; öğrenciler laboratuvar ağında `ogretmen.lab` adresini tarayıcıdan açarak dosya veya klasör yükleyebilsin.

Öğretmen bilgisayarı Pardus 23 EDU, laboratuvar 21–40 öğrenci bilgisayarıdır. Mevcut projede Ansible ile yönetim, Podman ile paketleme, Bash kurulum ve systemd ile otomatik başlangıç hedeflenmektedir. Mevcut teknolojilere uyum sağla; bu modül için ayrı bir büyük dosya paylaşım platformu veya öğrenci istemci uygulaması kurmayı zorunlu tutma.

Temel akış:

**Öğretmen ödev oluşturur → teslimleri açar → öğrenci sayfadan yükler → sunucu teslimi doğrular → öğretmen teslimleri takip eder ve indirir.**

Öğrenci PC'lerinde tarayıcı yeterli olsun. Öğretmen PC açık, servis çalışır ve yerel ağ erişimi mevcutken internet gerekmesin. Dosyalar öğretmen PC'de saklansın; buluta veya üçüncü taraf hizmete gönderilmesin.

## 2. Mevcut projeyle ilişkisi

- Ağ taraması, cihaz keşfi, kullanıcı/parola adaylarını deneme özellikleri bu modüle de eklenmeyecek.
- Öğrencinin tarayıcıdan dosya göndermesi SSH bağlantısı gerektirmeyecek. Dosya teslimini öğrenci PC'ye uzaktan bağlanıp dosya çekme şeklinde uygulama.
- Mevcut öğretmen yönetim paneli, profil yedekleme/sıfırlama ve SSH anahtar yönetimi korunacak.
- Ana şartnamedeki “bütün arayüz yalnız loopback üzerinden erişilebilir” kuralını şöyle daralt: **öğretmen yönetim paneli yerel kalır; yalnız öğrenci teslim servisi laboratuvar ağına açılır.** Yönetim API'leri bu istisnaya dahil değildir.
- Yeni modül mevcut kurulum, güncelleme ve otomatik başlatma akışına dahil olsun. Öğretmen ikinci bir ürünü elle kurup yönetmesin.

## 3. Öğretmen ekranı

Mevcut öğretmen paneline **Ödevler** bölümü ekle.

Öğretmen bir ödev için şunları belirleyebilsin:

- Ödev başlığı, sınıf ve kısa yönerge.
- İsteğe bağlı teslim son tarihi ve saati; saat dilimi `Europe/Istanbul`.
- İzinli dosya türleri, teslim başına toplam boyut ve dosya sayısı sınırı.
- Dosya, birden fazla dosya ve klasör kabulü.
- Geç teslim politikası; varsayılan olarak süre dolunca yeni teslim reddedilsin.

Ödev durumları **Taslak / Teslime açık / Teslime kapalı / Arşivlendi** olsun. Öğretmen “Teslimleri aç”, “Teslimleri kapat” ve “Arşivle” işlemlerini yapabilsin. Arşivleme silme anlamına gelmesin. Öğretmen teslimleri kapattığında veya geç teslim kapalı bir ödevin süresi dolduğunda henüz tamamlanmamış aktarım teslim sayılmasın; öğrenci açık hata mesajı alsın. Geç teslim açık bırakılmışsa süre sonrasında tamamlanan gönderim “Geç teslim” olarak kaydedilsin.

Ödev detayında sınıf listesindeki her öğrenci için şu bilgiler görünsün:

- Ad soyad, öğrenci numarası.
- Teslim etmedi / Yükleme sürüyor / Teslim alındı / Geç teslim / Yükleme hatası.
- Son teslim zamanı, sürüm, dosya sayısı ve toplam boyut.
- Dosya listesi, öğrencinin teslim sürümünü indirme ve geçmiş teslimleri görme.

“Sınıfın tamamı teslim etti” hesabı sınıf listesine dayansın; yalnız yükleme yapanları sayarak bu sonucu üretme.

Öğretmen bir öğrencinin teslimini, seçili teslimleri veya bütün sınıfın teslimlerini ZIP olarak indirebilsin. Toplu indirmede varsayılan her öğrencinin son tamamlanmış teslimi olsun; önceki sürümleri dahil etme ayrıca seçilsin. Öğrenci ve teslim sürümü ayrımı ZIP içinde korunarak aynı adlı dosyaların çakışması önlensin.

## 4. Öğrenci kimliği ve kolay giriş

Öğrenciler aynı yerel `ogrenci` hesabını kullanıyor. Bu nedenle Linux kullanıcı adı, IP adresi veya bilgisayar adı öğrencinin kimliği kabul edilmesin.

Öğretmen sınıf listesini elle veya şu alanlarla CSV'den ekleyebilsin: **sınıf, öğrenci numarası, ad soyad**. Uygulama her öğrenci için kişiye özel bir teslim kodu oluştursun. Ayrı işletim sistemi hesabı veya e-posta hesabı açmak gerekmesin.

Öğrenci **sınıf + öğrenci numarası + kendisine verilen teslim kodu** ile giriş yapsın. Ad soyad sınıf kaydından gelsin; yalnız serbest ad yazmakla başkasının adına teslim yapılmasın. Bütün sınıfın bildiği ortak ödev kodunu kişisel kimlik doğrulaması sayma.

Kodlar rastgele, yeterli uzunlukta ve tahmin denemelerine karşı hız sınırıyla korunsun; doğrulama için düz metin yerine uygun hash saklansın. Kod üretiminde öğretmene dağıtım/çıktı olanağı sağla; kaybolursa mevcut kodu açığa çıkarmak yerine yeni kod üretilebilsin. Kodlar URL'ye, loglara veya standart sınıf CSV dışa aktarımına yazılmasın.

Ortak bilgisayarda kısa hareketsizlik süresi ve görünür “Çıkış” düğmesi olsun. Giriş bilgilerini kalıcı tarayıcı deposuna kaydetme. Öğrenci çıkış yaptığında sonraki öğrenci öncekinin dosya listesini göremesin.

## 5. Öğrenci teslim ekranı

Öğrenci yalnız kendi sınıfına açık ödevleri görsün. Ödev sayfası şu öğeleri içersin:

- Ödev başlığı, yönerge, teslim süresi ve kalan zaman.
- Kabul edilen dosya türleri ve boyut/dosya sayısı sınırı.
- **Dosya seç**, **Klasör seç** ve **Gönder** düğmeleri.
- Desteklenen tarayıcılarda sürükle-bırak.
- Gönderim öncesinde seçilen dosyalar, göreli klasör yapısı, toplam boyut ve dosya sayısı.
- Hatalı/izin verilmeyen dosyalar için açıklama ve seçimden çıkarma olanağı.
- Gerçek aktarım ilerlemesi, mevcut aşama, iptal ve hata sonrası yeniden deneme.

Öğrencinin birden fazla dosyayı ve alt klasörlü projeyi tek teslimde göndermesi mümkün olsun. Klasör yüklemede göreli dizin yapısını koru. Desteklenen tarayıcılarda `webkitdirectory` gibi uygun dosya seçme desteğini kullan; Pardus'taki gerçek tarayıcı sürümlerinde doğrula. Desteklenmeyen tarayıcıda ZIP yükleme yolunu açıkça göster. Boş klasörlerin her tarayıcıda korunacağını varsayma.

**“Teslim alındı” yalnız bütün dosyalar öğretmen PC'de kalıcı olarak kaydedilip sunucu doğrulaması tamamlandığında gösterilsin.** Tarayıcı aktarımı yüzde 100 gösterdiğinde gerekiyorsa ayrıca “Teslim doğrulanıyor” aşaması olsun.

Başarı ekranında öğrenci, ödev, teslim numarası, sunucu teslim zamanı, dosya sayısı ve toplam boyut bulunsun. Öğrenci yalnız kendi teslimlerinin durumunu ve dosya adlarını görebilsin. Öğrenciler birbirlerinin teslimlerini listeleyemesin, indiremesin, değiştiremesin veya silemesin.

## 6. Yükleme, kesinti ve sürümler

Her teslim sunucunun ürettiği benzersiz bir kimliğe sahip olsun. Kullanıcının gönderdiği dosya adı, öğrenci numarası veya klasör yolu doğrudan fiziksel depolama yolu olarak kullanılmasın; özgün adlar metadata olarak korunabilsin.

Yükleme önce geçici alana alınsın. Beklenen dosya listesi, dosya sayısı ve boyutlarla karşılaştırılsın; sunucuda dosya bütünlüğü için özetler kaydedilsin. Tamamlanınca dosyalar ve teslim kaydı tutarlı şekilde sonlandırılsın. Çökme sonrası eksik dosyalı kayıt “Teslim alındı” olarak kalmasın.

- Aynı adlı dosyalar farklı öğrenci veya teslimlere aitse birbirini ezmesin.
- Öğrencinin yeniden gönderimi **Teslim 1, Teslim 2** gibi yeni sürüm oluştursun; önceki tamamlanmış sürüm korunabilsin.
- Ağ nedeniyle aynı isteğin tekrar gönderilmesi yanlışlıkla ikinci tamamlanmış teslim üretmesin; idempotent sonlandırma kullan.
- Bağlantı kesilirse veya öğretmen PC kapanırsa yarım aktarım teslim sayılmasın. Sayfa yeniden açıldığında sunucudaki gerçek durum sorgulanabilsin.
- İlk sürümde kesilen teslim güvenle baştan gönderilebilsin. Parçalı/devam edilebilir yükleme uygulanmadıysa böyle bir özellik varmış gibi gösterme.
- Öğrenci arayüzünde veya sunucuda limite takılan dosyaları sessizce atıp kalanları tam teslim diye kabul etme; seçim listesinin düzeltilmesi veya açık yeni gönderim gereksin.
- Süresi geçmiş yarım yüklemeler temizlenebilir; aktif aktarımı veya tamamlanmış ödevi bu temizliğe dahil etme.

Dosyaları RAM'e topluca almak yerine akış halinde diske yaz. 21–40 öğrencinin eşzamanlı kullanımına uygun sınırlı aktarım paralelliği ve geri bildirim uygula. Dolan diskte mevcut teslimler bozulmasın; yeni yükleme anlaşılır mesajla reddedilsin.

## 7. Yerel adres ve kurulum

Öğrenci erişim adresi `ogretmen.lab` olsun; kurulumda değiştirilebilir bırak. Bu adın kendiliğinden çözüleceğini varsayma.

1. Öğretmen PC için sabit adres veya okul ağında DHCP rezervasyonu gereksinimini kurulumda kontrol et ve belgele. Uygulama yetkisi olmayan DHCP cihazını değiştirmeye çalışmasın.
2. Yerel DNS yönetilebiliyorsa `ogretmen.lab` adını öğretmen PC'nin adresine eşleştir.
3. DNS yönetilemiyorsa yalnız mevcut envanterdeki seçili öğrenci PC'lere, Ansible üzerinden yönetilen `/etc/hosts` kaydı dağıt. Diğer kayıtları koru; aynı girdiyi çoğaltma. Bu işlem ağ keşfi değildir.
4. Öğrenci masaüstüne “Ödev Teslim” kısayolu ekle; profil sıfırlama sonrasında da standart profilden geri gelsin.
5. Öğrenci portalının gerekli portunu yalnız tanımlı laboratuvar ağına aç. Öğretmen yönetim portunu ağa açma.
6. Güvenilir HTTPS erişimi sağla. Kurumun uygun sertifika altyapısı varsa onu kullan; yoksa yerel sertifika/güven dağıtımı ve yenileme yolunu kurulumun parçası olarak belgele. Öğrenciye sertifika uyarısını atlamayı öğretme.

Podman/systemd ve kurulum betikleri bu modülü de otomatik başlatsın. Tek kurulum deneyimi korunurken öğrenci servisi ile yetkili yönetim bileşeni erişim bakımından ayrıştırılsın. Öğretmenin SSH anahtar kasası kilitliyken de önceden teslime açılmış ödevler alınabilsin; dosya kabul etmek için kasa açılması veya root yetkisi gerekmesin.

Kurulu uygulama, yazı tipleri ve arayüz varlıkları dahil internet olmadan çalışsın. Öğretmen PC'nin kapalı olması veya ağ izolasyonu nedeniyle erişim yoksa uygulamanın bunu aşabildiği iddia edilmesin; kılavuzda kısa bağlantı kontrol adımları olsun.

## 8. Erişim ayrımı ve dosya güvenliği

Öğrenci portalını yalnız öğretmen panelindeki düğmeleri gizleyerek oluşturma. Ayrı API/servis yetkileri kullan; öğrenci servisi yönetim anahtarlarına, sudo/Ansible çalıştırmaya, kullanıcı temizliğine veya yönetim loglarına erişemesin. Konteynere yönetim soketi ya da öğretmenin bütün ev dizini bağlanmasın.

Yüklenen içerikler uygulama kodundan, çalıştırılabilir dosyalardan, profil yedeklerinden ve SSH anahtarlarından ayrı kalıcı alanda bulunsun. Öğrenci servisinin erişimi ödevler için gereken alanla sınırlı olsun.

- Yetkilendirme her API isteğinde sunucuda yapılsın; başka öğrenci/ödev/teslim kimliği yazılarak erişilemesin.
- Dosya türü, sayısı ve boyutu hem seçim sırasında hem sunucuda doğrulansın. Tarayıcının bildirdiği MIME türüne veya uzantıya tek başına güvenilmesin.
- Yol kaçışı, mutlak yollar, `..`, tehlikeli bağlantılar ve aynı teslim içinde çakışan yollar engellensin.
- Yüklenen HTML, SVG, script, makro ve program dosyaları sunucuda çalıştırılmasın; ilk sürümde etkin içerik önizlemesi sunulmasın. İzin verilen eğitim kaynak kodları yalnız dosya olarak saklansın.
- ZIP dosyaları ilk sürümde sunucuda otomatik açılmadan saklanabilsin. İleride açma eklenirse yol kaçışı ve aşırı açılmış boyut limitleri ayrıca uygulansın.
- Öğretmen indirmeleri yetkilendirilmiş uçlardan, güvenli dosya adı ve indirme başlıklarıyla sunulsun; genel erişimli statik dizin oluşturulmasın.
- Oturum, CSRF/Origin kontrolleri, istek hız sınırı, depolama kotası ve güvenli hata mesajları uygulansın.

Sunucunun dosyayı saklaması, dosyanın zararsız olduğunun onayı değildir. Zararlı yazılım taraması eklenirse gerçek tarama sonucu ayrı gösterilsin; uygulanmamış tarama varmış gibi raporlanmasın.

## 9. Saklama ve profil sıfırlamayla ilişki

Ödev teslimleri **öğrenci profil yedeklerinden ayrı** saklansın. Ana projedeki 30 günlük profil yedeği temizliği ödevlere uygulanmasın. Öğrenci PC'nin `ogrenci` profili sıfırlandığında öğretmen PC'ye tamamlanmış teslimler kaybolmasın.

İlk sürümde tamamlanmış ödevler için otomatik süre dolumu/silme kapalı olsun. Öğretmen dönem sonunda arşivleme, dışa aktarma ve açık onayla silme yapabilsin. Sonradan ödev saklama süresi tanımlanırsa hangi verinin ne zaman silineceği ayrıca gösterilsin.

Aktif aktarım sırasında aynı öğrenci PC için profil sıfırlama veya oturum kapatma başlatılırsa öğretmene uyarı ver. Yükleyen PC, yalnız IP'den öğrenci kimliği çıkarılarak belirlenmesin; güvenilir cihaz eşlemesi yoksa belirsizliği açıkça göster. Aktif yükleme durumunu sonlandırılmış teslimden ayır; varsayılan olarak işlemi erteleme seçeneği sun.

Konteyner güncelleme, yeniden oluşturma veya normal uygulama kaldırma tamamlanmış teslimleri kendiliğinden silmesin. Ödev verileri ile kayıtlarının birlikte yedeklenmesi ve geri yüklenmesi belgelensin. Öğretmen PC'de tek kopya tutmak ayrı bir yedek olarak tanımlanmasın.

## 10. Arayüz dili ve kapsam

Sade, modern Türkçe arayüz kullan. Teknik olmayan öğretmen ve öğrenci için kısa, doğrudan metinler yaz. Durumu yalnız renkle anlatma; klavye erişimi ve okunabilir hata mesajları sağla.

Örnek mesajlar:

- “Yüklemek istediğiniz dosyaları veya klasörü seçin.”
- “12 dosya seçildi — toplam 38 MB.”
- “Dosyalar yükleniyor. Bu pencereyi kapatmayın.”
- “Aktarım tamamlandı; teslim doğrulanıyor.”
- “Ödeviniz teslim alındı. Teslim numarası: …”
- “Bağlantı kesildi. Teslim henüz tamamlanmadı; yeniden gönderebilirsiniz.”
- “Teslim süresi doldu. Öğretmeninizden yeniden açmasını isteyin.”

İlk sürümün zorunlu kapsamı: sınıf listesi ve kişisel teslim kodu, ödev oluşturma/açma/kapatma, dosya/klasör/ZIP kabulü, güvenilir teslim kaydı, sürümlü yeniden gönderim, öğretmen takip ekranı ve toplu ZIP indirme.

Notlandırma, intihal analizi, bulut senkronizasyonu, çevrimiçi belge düzenleme ve canlı ekran izleme bu modülün ilk sürümüne eklenmesin.

## 11. Kabul testleri ve teslimatlar

En az şu durumları doğrula:

1. Öğrenci, ek uygulama kurmadan ve internet olmadan, yerel ad üzerinden portala erişir.
2. Öğrenci portalından öğretmen yönetim API'sine, SSH anahtarına veya Ansible işlemine erişilemez.
3. Başka öğrencinin kimliğini/teslim numarasını kullanarak dosyalar görülemez veya değiştirilemez; yanlış teslim kodu reddedilir.
4. Tek dosya, çoklu dosya ve alt klasörlü teslim hedef tarayıcıda çalışır; desteklenmeyen klasör yüklemede ZIP yolu açıklanır.
5. Aynı adlı dosyalar öğrenciler arasında çakışmaz; bilinçli yeni gönderim yeni sürüm oluşturur, ağ tekrarı çift teslim üretmez.
6. Yarım aktarım, dolu disk, kota aşımı, süre dolumu, servis yeniden başlaması ve öğrenci çıkışı hatalı başarıya yol açmaz.
7. Bütün dosyalar doğrulanmadan “Teslim alındı” gösterilmez; sınıf toplamları gerçek tamamlanmış teslimlerle eşleşir.
8. Yol kaçışı ve çalıştırılabilir içerik testleri uygulama dosyalarına erişemez; indirme yetkileri doğrulanır.
9. Toplu ZIP indirme doğru öğrenci ve sürüm ayrımını korur; dosyalar eksiksiz açılabilir.
10. Profil sıfırlama ve 30 günlük profil yedeği temizliği ödevleri silmez; aktif aktarımda ilgili uyarı çalışır.
11. Öğretmen anahtar kasası kilitliyken açık ödevlere teslim yapılabilir.
12. Güncelleme sonrası veri kalır; örnek ödev yedeği geri yüklenebilir.
13. 21–40 eşzamanlı öğrenci için kullanılan test ortamı, dosya boyutları ve sonuçlar raporlanır; ölçülmeyen performans iddia edilmez.

Teslim et: çalışan kaynak kod, veri tabanı geçişleri, gerekli servis/kurulum değişiklikleri, örnek sınıf CSV'si, Türkçe öğretmen/öğrenci kısa kılavuzları ve test sonuçları. Ana istemin erişim, arayüz, depolama ve kurulum bölümlerini bu ekle tutarlı hale getir.

Mevcut kodu önce incele; sadece plan veya görsel taslakla yetinme. Gerçek Pardus veya sınıf ağına erişimin yoksa o kontrollerin yapılmadığını belirt; yerel test ile saha doğrulamasını birbirine karıştırma.

**Başarı ölçütü:** Öğretmen ödevi açar; öğrenci `ogretmen.lab` üzerinden yükler ve doğrulanmış teslim belgesi görür; öğretmen bütün teslimleri öğrenci bazında takip edip indirebilir. Günlük kullanım ek program, terminal komutu veya internet gerektirmez.
