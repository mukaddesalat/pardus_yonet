# Pardus Sınıf Yönetimi — Komut Mağazası (Topluluk Deposu)

Bu depo, **Lab Kaptanı (Pardus Sınıf Yönetimi)** uygulaması için öğretmenler tarafından hazırlanan hazır sınıf yönetim araçlarını ve bash betiklerini barındırır.

## 🤝 Katkıda Bulunma Rehberi (Öğretmenler İçin)
Öğretmenlerin katkı sağlaması için karmaşık dijital imza süreçlerine **gerek yoktur**.

1. Bu depoyu çatallayın (Fork) veya doğrudan bir dal (branch) açın.
2. `araclar/<arac-id>/` klasörü oluşturun:
   - `arac.json` (veya `arac.yaml`): Aracın adı, açıklaması, parametreleri ve kategorisi.
   - `betik.sh`: Pardus bilgisayarlarında çalıştırılacak shell betiği.
3. Bir Pull Request (PR) gönderin. Depo yöneticisi güvenlik kontrolünü yapıp birleştirdiğinde, tüm okullardaki Lab Kaptanı uygulamaları tek tıkla aracı indirip kullanabilir!

## 📦 Katalog Dosyası
Okullardaki Lab Kaptanı uygulaması, tüm depoyu klonlamadan doğrudan bu depodaki `katalog.json` dosyasını HTTP GET ile çeker.
URL: `https://raw.githubusercontent.com/mukaddesalat/pardus_yonet_magaza/main/katalog.json`

