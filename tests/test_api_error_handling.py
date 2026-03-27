"""Tests for API error handling branches."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

if "aiohttp" not in sys.modules:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientError = Exception
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub

API_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "ggbus" / "api.py"
SPEC = importlib.util.spec_from_file_location("ggbus_api_for_errors", API_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

GGBusApi = MODULE.GGBusApi
GGBusAuthError = MODULE.GGBusAuthError
GGBusQuotaError = MODULE.GGBusQuotaError


class _FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def text(self) -> str:
        return self._text


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def get(self, *_args, **_kwargs):
        return self._response


class TestApiErrorHandling(unittest.TestCase):
    def test_http_401_raises_auth_error(self) -> None:
        api = GGBusApi(_FakeSession(_FakeResponse(401, "{}")), "dummy")
        with self.assertRaises(GGBusAuthError):
            asyncio.run(api._request("http://example.com", {}))

    def test_http_429_raises_quota_error(self) -> None:
        api = GGBusApi(_FakeSession(_FakeResponse(429, "{}")), "dummy")
        with self.assertRaises(GGBusQuotaError):
            asyncio.run(api._request("http://example.com", {}))

    def test_result_code_auth_raises_auth_error(self) -> None:
        payload = '{"response":{"msgHeader":{"resultCode":"SERVICE_KEY_IS_NOT_REGISTERED_ERROR"}}}'
        api = GGBusApi(_FakeSession(_FakeResponse(200, payload)), "dummy")
        with self.assertRaises(GGBusAuthError):
            asyncio.run(api._request("http://example.com", {}))

    def test_result_code_quota_raises_quota_error(self) -> None:
        payload = '{"response":{"msgHeader":{"resultCode":"LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}'
        api = GGBusApi(_FakeSession(_FakeResponse(200, payload)), "dummy")
        with self.assertRaises(GGBusQuotaError):
            asyncio.run(api._request("http://example.com", {}))


if __name__ == "__main__":
    unittest.main()
