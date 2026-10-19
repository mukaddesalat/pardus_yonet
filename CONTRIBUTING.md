# Katkıda bulunma

Lab Kaptanı (Pardus Sınıf Yönetimi) için katkınızı memnuniyetle karşılıyoruz. Önce
[davranış kurallarına](CODE_OF_CONDUCT.md) göz atın; güvenlik açıkları için
[SECURITY.md](SECURITY.md) geçerlidir.

## Geliştirme ortamı

Python 3.12 ve Linux (tercihen Pardus 23) önerilir; testler Windows'ta da çalışır.

```bash
pip install -r paketleme/requirements.txt pytest
python -m uygulama.ana                 # http://127.0.0.1:8080
python -m pytest -q testler            # testler
```

Geliştirme verisi `./veri` altında tutulur (`PSY_VERI_DIZINI` ile değiştirilebilir).
Gerçek bir öğrenci bilgisayarında deneme yapmanız gerekiyorsa bunu yalnızca kendi
test makinenizde yapın.

## Değişiklik yapmadan önce

- **Arayüz düğmesi eklediyseniz** `uygulama/arayuz/referans.js` içine M/S/B kodunu
  ekleyin. Kodlar sabittir: silinen kod **emekli** listesine alınır ve asla yeniden
  kullanılmaz. Testler bunu denetler.
- **Tasarım:** renk, boşluk ve yazı değerleri `DESIGN.md` belirteçlerinden üretilir.
  `belirtecler.css` elle düzenlenmez: `python araclar/belirtec_css.py`.
- **Öğrenci PC'de çalışan kod** `uygulama/uzak/` altındadır ve yalnızca
  `uygulama/uzak/__init__.py` içindeki izin listesinden gönderilir. Serbest komut
  girişi eklemeyin.
- **Üretilen dosyalar:** `arayuz-onizleme.html` elle düzenlenmez. Kaynak değişince yeniden üretin:

  ```bash
  python araclar/onizleme_yap.py
  ```

  CI bu dosyanın güncel olup olmadığını `--denetle` ile kontrol eder.

## Gizli bilgi kuralı

Parola, özel anahtar, gerçek IP adresi, kişisel veri veya kurum bilgisi **hiçbir
dosyaya, teste, örneğe, ekran görüntüsüne veya commit mesajına** girmemelidir. Test
verisi için açıkça sahte değerler kullanın (ör. `Deneme-Parola-2026`, `192.168.10.x`).

## Commit ve pull request

- Tek konuya odaklı, küçük değişiklikler tercih edilir.
- Commit mesajı kısa bir başlıkla başlasın (ör. `M2-S4: uyku ayarı önizlemesi`); ayrıntıyı
  gövdede açıklayın.
- Pull request şablonundaki kontrol listesini doldurun.
- Güvenlik, yetki veya SSH ile ilgili değişikliklerde gerekçeyi açıkça yazın.

## Kod stili

- Arayüz metinleri ve belgeler **Türkçe**; kod tanımlayıcıları da Türkçe yazılmış
  projede tutarlı kalın (mevcut dosyalara bakın).
- Yorumlar "neden"i anlatsın; ne yaptığını zaten koddan okuyabiliyorsak yorum yazmayın.
- Yeni bağımlılık eklemek için `paketleme/requirements.txt` sabitlenmeli ve
  `paketleme/tekerlek_kilidi.txt` yeniden üretilmelidir.
