"""Geliştirme sunucusu: ayrı veri dizini (./veri-gelistirme) ile yönetim arayüzünü açar.

Kullanım: python araclar/gelistirme.py [port]
"""
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
os.environ.setdefault("PSY_VERI_DIZINI", str(KOK / "veri-gelistirme"))
os.environ.setdefault("PSY_ODEV_DIZINI", str(KOK / "veri-gelistirme" / "odev"))
if len(sys.argv) > 1:
    os.environ["PSY_PORT"] = sys.argv[1]

from uygulama import ana  # noqa: E402

ana.calistir()
