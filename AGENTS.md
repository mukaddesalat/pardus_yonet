# Proje Geliştirme ve Agent Yönergeleri

## 1. Bilgi Grafiği (Graphify) ve Token Tasarrufu
Bu projede token tasarrufu ve hızlı mimari analiz için `graphify` bilgi grafiği (`graphify-out/`) kuruludur.

- **Her Kod Değişikliği / Analiz Öncesi**:
  - Kod tabanı, fonksiyon ilişkileri, bağımlılıklar veya akışla ilgili sorularda tüm dosyaları baştan okumak yerine öncelikle `graphify-out/graph.json` grafiğini kullan (`graphify query "<soru>"`, `graphify path "<A>" "<B>"` veya `graphify explain "<sembol>"`).
- **Kod Değişiklikleri Sonrası**:
  - Kod dosyalarında düzenleme yapıldığında grafiği güncel tutmak için `graphify update .` komutunu çalıştır (tamamen yerel AST analizi kullanır, harici token harcamaz).
  - Git commit'leri için `post-commit` kancası zaten kuruludur ve commit anında otomatik güncellenir.

