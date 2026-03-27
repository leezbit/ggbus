"""Tests for lowPlate normalization helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
import importlib.util
import types
import sys

if "aiohttp" not in sys.modules:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientError = Exception
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub

API_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "ggbus" / "api.py"
SPEC = importlib.util.spec_from_file_location("ggbus_api", API_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

_first_present = MODULE._first_present
_to_low_plate_code = MODULE._to_low_plate_code


class TestLowPlateNormalization(unittest.TestCase):
    def test_to_low_plate_code_maps_official_codes(self) -> None:
        self.assertEqual(_to_low_plate_code("0"), "0")
        self.assertEqual(_to_low_plate_code("1"), "1")
        self.assertEqual(_to_low_plate_code("2"), "2")
        self.assertEqual(_to_low_plate_code("5"), "5")
        self.assertEqual(_to_low_plate_code("6"), "6")
        self.assertEqual(_to_low_plate_code("7"), "7")

    def test_to_low_plate_code_maps_boolean_like_values(self) -> None:
        self.assertEqual(_to_low_plate_code("Y"), "1")
        self.assertEqual(_to_low_plate_code("ON"), "1")
        self.assertEqual(_to_low_plate_code("N"), "0")
        self.assertEqual(_to_low_plate_code("OFF"), "0")

    def test_first_present_keeps_zero_value(self) -> None:
        payload = {"lowPlate1": 0, "lowplate1": 1}
        self.assertEqual(_first_present(payload, "lowPlate1", "lowplate1"), 0)


if __name__ == "__main__":
    unittest.main()
