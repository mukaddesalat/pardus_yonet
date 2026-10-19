"""Ortak test hazırlığı: testler geçici veri dizini kullanır; gerçek veriye dokunmaz."""

import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Uzak betikler (uygulama/uzak/) yalnızca Linux'ta çalışır ve `pwd` kullanır;
# saf işlevlerinin Windows geliştirme makinesinde de test edilebilmesi için.
if sys.platform == "win32":
    sys.modules.setdefault("pwd", types.ModuleType("pwd"))
    sys.modules.setdefault("grp", types.ModuleType("grp"))

_gecici = tempfile.mkdtemp(prefix="psy-test-")
os.environ["PSY_VERI_DIZINI"] = _gecici
os.environ["PSY_ODEV_DIZINI"] = os.path.join(_gecici, "odev")

from uygulama import ayarlar  # noqa: E402
from uygulama.odev import ortak as odev_ortak  # noqa: E402

ayarlar.VERI_DIZINI = Path(_gecici)
odev_ortak.ODEV_DIZINI = Path(_gecici) / "odev"
