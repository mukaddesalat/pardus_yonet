"""Ödev Teslim modülü.

İki süreç bu paketi kullanır:
- Öğrenci portalı (`python -m uygulama.odev.portal`): laboratuvar ağına açık,
  ayrı `pardus-odev` kullanıcısıyla çalışır; yalnız bu paketi içe aktarır ve
  yönetim verisine (SSH anahtarı, envanter) işletim sistemi düzeyinde erişemez.
- Yönetim paneli (`uygulama.ana`): `yonetim_api` yönlendiricisiyle sınıfları,
  kodları ve ödevleri yönetir, teslimleri indirir.

Ortak veri: PSY_ODEV_DIZINI (kurulu pakette /var/lib/pardus-sinif-odev).
"""
