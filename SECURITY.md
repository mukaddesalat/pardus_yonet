# Güvenlik politikası

## Desteklenen sürümler

| Sürüm | Destek |
| --- | --- |
| 0.6.x | Evet (son kararlı sürüm) |
| 0.5.x ve öncesi | Hayır; 0.6.x'e yükseltin |

## Güvenlik açığı bildirme

Güvenlik açıklarını **herkese açık issue açarak bildirmeyin.** Bunun yerine GitHub'ın
özel bildirim özelliğini kullanın: depo sayfasında **Security → Report a vulnerability**.
Bildirimde şunları yazın:

- Etkilenen sürüm ve Pardus sürümü
- Adımlar veya kavram kanıtı (parola, özel anahtar veya gerçek kişisel veri **eklemeyin**)
- Etkisi: hangi bilgisayarlara, hangi yetkiyle erişilebilir

Bildirimler en geç 7 gün içinde yanıtlanmaya çalışılır. Düzeltme yayınlanana kadar
ayrıntılar paylaşılmaz; düzeltmeden sonra katkıcı isterse adı sürüm notunda anılır.

## Bilerek verilen yetkiler (açık tasarım kararı)

Bu uygulamanın güvenlik modelini anlamak için:

- Yönetim hesaplarına (`pardus`, `hp`) **parolasız sudo (`NOPASSWD: ALL`)** verilir.
  Bu, uygulamanın SSH anahtarına sahip olan herkesin öğrenci bilgisayarında **root
  eşdeğeri** yetkiye sahip olması demektir. Bu bir hata değil, Ansible ve uzaktan
  yönetim için gereken bilinçli bir karardır; ama öğretmen bilgisayarının güvenliği
  laboratuvarın güvenliğidir.
- Uygulama arayüzü yalnızca `127.0.0.1` üzerinde dinler; Host/Origin denetimi yapılır.
  Uzak bilgisayarlarda yalnızca izin listesindeki betikler çalıştırılır; serbest komut
  girişi yoktur.
- `ogrenci` hesabına sudo verilmez, root SSH girişi açılmaz.

## Bilinen sınırlar

- Öğrenci ödev portalı (`uygulama/odev/`) **düz HTTP** ile çalışır; laboratuvar ağında
  şifresiz iletişim yapılır. Portal yönetim verisine erişemez, ancak ağdaki biri teslim
  kodlarını ve dosyaları görebilir. Bu, proje sahibinin bilinçli kararıdır ve
  belgelenmiştir (`belgeler/odev_ogretmen_kilavuzu.md`).
- Arayüz giriş parolası ve kurulum kodu yerel makinede tutulur; öğretmen bilgisayarı ele
  geçirilirse yönetim yetkisi de ele geçirilmiş olur.
