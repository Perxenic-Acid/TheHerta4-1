import sys
import types
import unittest

try:
    import bpy  # noqa: F401
except ImportError:
    sys.modules["bpy"] = types.SimpleNamespace(
        context=types.SimpleNamespace(scene=types.SimpleNamespace()),
        props=types.SimpleNamespace(
            BoolProperty=lambda **kwargs: None,
            EnumProperty=lambda **kwargs: None,
            PointerProperty=lambda **kwargs: None,
            StringProperty=lambda **kwargs: None,
        ),
        types=types.SimpleNamespace(PropertyGroup=object, Scene=type("Scene", (), {})),
    )
from common.global_config import LogicName


class LogicNameTests(unittest.TestCase):
    def test_zzmidx12_stays_in_zzmi_family(self):
        self.assertTrue(LogicName.is_zzmi_family(LogicName.ZZMI))
        self.assertTrue(LogicName.is_zzmi_family(LogicName.ZZMIDX12))
        self.assertFalse(LogicName.is_zzmi_family(LogicName.GIMI))


if __name__ == "__main__":
    unittest.main()
