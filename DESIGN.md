---
version: alpha
name: Pardus Sınıf Yönetimi — Sade Kurum
description: Öğretmen bilgisayarında çalışan, laboratuvar yönetimi için sakin, okunaklı ve güven veren Türkçe yönetim arayüzü.
colors:
  primary: "#1B5FC1"
  primary-hover: "#154C9C"
  on-primary: "#FFFFFF"
  secondary: "#4E5D6C"
  neutral: "#F3F5F8"
  surface: "#FFFFFF"
  surface-alt: "#EDF1F5"
  on-surface: "#16212C"
  border: "#D3DBE3"
  focus: "#1B5FC1"
  success: "#1B7340"
  success-bg: "#E5F3EA"
  warning: "#8A5300"
  warning-bg: "#FFF1D6"
  error: "#B42318"
  error-bg: "#FCE9E7"
  info-bg: "#E6EFFB"
  ref: "#5B2C99"
  ref-bg: "#EFE7FA"
  demo: "#6B4100"
  demo-bg: "#FFE7A8"
  sidebar: "#16212C"
  on-sidebar: "#E8EEF4"
  sidebar-active: "#24364A"
typography:
  headline-lg:
    fontFamily: Ubuntu
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.3
  headline-md:
    fontFamily: Ubuntu
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.35
  body-md:
    fontFamily: Ubuntu
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: Ubuntu
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.45
  label-md:
    fontFamily: Ubuntu
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.3
  label-sm:
    fontFamily: Ubuntu
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.2
  code-sm:
    fontFamily: Ubuntu Mono
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.3
rounded:
  sm: 4px
  md: 6px
  lg: 10px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  sidebar: 232px
  content-max: 1180px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px
    height: 34px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: 8px
    height: 34px
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.error}"
    rounded: "{rounded.md}"
  badge-ok:
    backgroundColor: "{colors.success-bg}"
    textColor: "{colors.success}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
  badge-warn:
    backgroundColor: "{colors.warning-bg}"
    textColor: "{colors.warning}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
  badge-error:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
  badge-neutral:
    backgroundColor: "{colors.surface-alt}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-sm}"
    rounded: "{rounded.full}"
  ref-code:
    backgroundColor: "{colors.ref-bg}"
    textColor: "{colors.ref}"
    typography: "{typography.code-sm}"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: 16px
  sidebar:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.on-sidebar}"
    width: 232px
  selection-bar:
    backgroundColor: "{colors.info-bg}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    padding: 8px
  demo-banner:
    backgroundColor: "{colors.demo-bg}"
    textColor: "{colors.demo}"
    typography: "{typography.label-md}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    height: 34px
---

# Pardus Sınıf Yönetimi — Tasarım Sistemi

Bu dosya [DESIGN.md biçimindedir](https://github.com/google-labs-code/design.md):
ön bölümdeki belirteçler (tokens) bağlayıcıdır, metin nasıl uygulanacağını anlatır.
`araclar/belirtec_css.py` belirteçleri `uygulama/arayuz/belirtecler.css` dosyasına
CSS değişkeni olarak yazar; gerçek arayüz ve `arayuz-onizleme.html` aynı dosyayı
kullanır. Belirteci değiştirdikten sonra aracı çalıştırın; test, üretilmiş dosyanın
güncel olduğunu denetler.

## Overview

Kullanıcı teknik uzman olmayabilecek bir öğretmendir; ekran bir kontrol paneli
değil, sakin bir iş listesi gibi hissettirmelidir. Ton kurumsal ve güven vericidir:
az renk, net durum rozetleri, tek birincil eylem. Yoğunluk orta-yüksektir; 30–40
bilgisayarlık tablo 1366×768 ekranda kaydırmadan okunabilmelidir. Her menü, sayfa
ve düğme sabit bir referans kodu taşır (M = menü, S = sayfa, B = düğme); kodlar
mor tonda, içerikten ayrışan küçük etiketlerdir ve tek düğmeyle gizlenebilir.

## Colors

Palet tek bir mavi eylem rengi ile nötr griler üzerine kuruludur.

- **Primary (#1B5FC1):** "Pardus mavisi" — yalnızca sayfadaki asıl eylem, odak
  halkası ve seçili menü göstergesi için.
- **Secondary (#4E5D6C):** yardımcı metin, sütun başlıkları, açıklamalar.
- **Neutral (#F3F5F8):** sayfa zemini; kartlar ve tablolar beyaz **Surface** üzerinde durur.
- **Durum renkleri:** Success (#1B7340), Warning (#8A5300), Error (#B42318) yalnız
  rozet, uyarı kutusu ve sonuç satırlarında, açık zemin eşleriyle (`*-bg`) kullanılır.
- **Ref (#5B2C99):** referans kodu etiketleri; başka hiçbir öğe mor kullanmaz.
- **Demo (#6B4100 / #FFE7A8):** yalnız önizleme dosyasındaki kalıcı "DEMO" şeridi.
- **Sidebar (#16212C):** koyu yan menü; üzerindeki metin On-sidebar (#E8EEF4).

## Typography

Pardus'un varsayılan arayüz yazı tipi **Ubuntu**'dur (Pardus GNOME ayarlarında
`font-name = 'Ubuntu 11'`); internet gerekmesin diye web yazı tipi yüklenmez,
yoksa Noto Sans / DejaVu Sans kullanılır. Kodlar ve parmak izleri **Ubuntu Mono**.

- **Headline-lg (20px/600):** sayfa başlığı.
- **Headline-md (16px/600):** kart ve pencere başlıkları.
- **Body-md (14px):** genel metin; **Body-sm (13px):** tablo hücreleri.
- **Label-md (13px/600):** düğmeler; **Label-sm (11px/600):** rozetler.
- **Code-sm (12px mono):** referans kodları, IP, parmak izi.

## Layout

Sabit 232px koyu yan menü + esnek içerik alanı (en çok 1180px). Boşluk ölçeği
4px tabanlıdır (4/8/12/16/24). Sayfa düzeni her zaman aynıdır: kod etiketli başlık
→ kısa açıklama → seçim çubuğu (bilgisayar seçilen sayfalarda) → araç düğmeleri →
tablo → sonuç/ilerleme paneli. 1366×768'de yatay kaydırma yalnız tablo kabının
içinde olabilir, sayfanın kendisi yatay kaymaz.

## Elevation & Depth

Gölge neredeyse yoktur; hiyerarşi ton katmanlarıyla kurulur: zemin (Neutral) →
kart (Surface, 1px Border) → vurgulu şerit (info-bg). Yalnız açılır pencereler
belirgin gölge ve arkada yarı saydam koyu perde kullanır.

## Shapes

Düğme ve girişler 6px, kartlar 10px, rozetler tam yuvarlak köşelidir. Referans
kodu etiketleri 4px köşeli ve mono yazılıdır; böylece rozetlerle karışmaz.

## Components

- **Düğmeler:** birincil (dolu mavi), ikincil (beyaz, çerçeveli), tehlikeli (beyaz,
  kırmızı yazı + kırmızı çerçeve). Her düğmenin sağında küçük `B<n>` kodu durur.
- **Rozetler:** durum için `badge-ok/warn/error/neutral`; metin her zaman durumu
  sözle de söyler (yalnız renge dayanılmaz).
- **Seçim çubuğu:** "32 bilgisayar seçili — 2 erişilemiyor — 1 korunan cihaz kapsam
  dışında" biçiminde tek satır özet + toplu seçim düğmeleri.
- **Onay penceresi:** kesin hedef listesi, kapsam dışı kalanlar ve nedenleri, yıkıcı
  işlemlerde ayrıca onay kutusu.
- **Özet kartları:** büyük sayı + kısa etiket + gerekiyorsa "ölçülemedi" notu.

## Do's and Don'ts

- Do sayfa başına tek birincil düğme kullan.
- Do ölçülemeyen değeri "ölçülemedi" yaz; asla 0 gösterme.
- Do temsili çizimleri "temsili" diye etiketle; gerçek ekran görüntüsü gibi sunma.
- Don't durum bilgisini yalnız renkle verme; her rozet metin içerir.
- Don't mor rengi referans kodları dışında kullanma.
- Don't bir referans kodunu, silinen düğmeninki olsa bile başka düğmeye verme.
