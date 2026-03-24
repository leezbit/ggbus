"""API client for Gyeonggi bus data.go.kr endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

ARRIVAL_BASES = (
    "https://apis.data.go.kr/6410000/busarrivalservice/v2",
    "https://apis.data.go.kr/6410000/busarrivalservice",
)
STATION_BASES = (
    "https://apis.data.go.kr/6410000/busstationservice/v2",
    "https://apis.data.go.kr/6410000/busstationservice",
)


class GGBusApiError(Exception):
    """Base API error."""


class GGBusAuthError(GGBusApiError):
    """Authentication/authorization error."""


@dataclass(slots=True)
class Station:
    """A resolved bus station."""

    station_id: str
    station_name: str
    station_no: str


@dataclass(slots=True)
class Arrival:
    """Arrival data for a route at a station."""

    route_id: str
    route_name: str
    location_no_1: int | None
    predict_time_1: int | None
    location_no_2: int | None
    predict_time_2: int | None
    flag: str | None
    low_plate_1: bool | None
    low_plate_2: bool | None
    plate_no_1: str | None
    plate_no_2: str | None


class GGBusApi:
    """Thin async API wrapper."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def resolve_station_by_code(self, station_code: str) -> Station:
        """Resolve stop 5-digit code to stationId and name."""
        query = station_code.strip()
        if not query:
            raise GGBusApiError("Station code is empty")

        endpoints = (
            f"{base}/getBusStationList?serviceKey={quote_plus(self._api_key)}&keyword={quote_plus(query)}"
            for base in STATION_BASES
        )
        payload = await self._request_with_fallback(endpoints)
        items = _extract_items(payload)
        for item in items:
            station_no = str(item.get("stationNo") or item.get("stationno") or "").strip()
            if station_no == query:
                station_id = str(item.get("stationId") or item.get("stationid") or "").strip()
                station_name = str(item.get("stationName") or item.get("stationname") or query).strip()
                if station_id:
                    return Station(station_id=station_id, station_name=station_name, station_no=station_no)

        raise GGBusApiError(f"Station code {station_code} was not found")

    async def get_station_arrivals(self, station_id: str) -> dict[str, Arrival]:
        """Fetch all arrivals for a station in a single API call."""
        endpoints = (
            f"{base}/getBusArrivalListv2?serviceKey={quote_plus(self._api_key)}&stationId={quote_plus(station_id)}"
            for base in ARRIVAL_BASES
        )
        payload = await self._request_with_fallback(endpoints)
        items = _extract_items(payload)
        arrivals: dict[str, Arrival] = {}
        for item in items:
            route_id = str(item.get("routeId") or item.get("routeid") or "").strip()
            route_name = str(item.get("routeName") or item.get("routename") or "").strip()
            if not route_id or not route_name:
                continue

            arrivals[route_id] = Arrival(
                route_id=route_id,
                route_name=route_name,
                location_no_1=_to_int(item.get("locationNo1")),
                predict_time_1=_to_int(item.get("predictTime1")),
                location_no_2=_to_int(item.get("locationNo2")),
                predict_time_2=_to_int(item.get("predictTime2")),
                flag=_to_optional_str(item.get("flag")),
                low_plate_1=_to_bool(item.get("lowPlate1")),
                low_plate_2=_to_bool(item.get("lowPlate2")),
                plate_no_1=_to_optional_str(item.get("plateNo1")),
                plate_no_2=_to_optional_str(item.get("plateNo2")),
            )
        return arrivals

    async def _request_with_fallback(self, endpoints: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        for url in endpoints:
            try:
                payload = await self._request(url)
                return payload
            except GGBusAuthError:
                raise
            except GGBusApiError as err:
                last_error = err
                _LOGGER.debug("GGBus endpoint failed %s: %s", url, err)

        raise GGBusApiError(str(last_error) if last_error else "Unknown API failure")

    async def _request(self, url: str) -> dict[str, Any]:
        try:
            response = await self._session.get(url, timeout=15)
            text = await response.text()
        except ClientError as err:
            raise GGBusApiError(f"Connection error: {err}") from err

        if response.status in (401, 403):
            raise GGBusAuthError("API key is not authorized")
        if response.status >= 400:
            raise GGBusApiError(f"API HTTP error {response.status}")

        payload = _parse_payload(text)
        result_code = _extract_result_code(payload)
        if result_code and result_code not in {"0", "00", "INFO-000", "SUCCESS"}:
            if "SERVICE_KEY" in result_code:
                raise GGBusAuthError(result_code)
            raise GGBusApiError(result_code)
        return payload


def _parse_payload(text: str) -> dict[str, Any]:
    body = text.strip()
    if not body:
        raise GGBusApiError("Empty response")

    if body.startswith("{"):
        import json

        return json.loads(body)

    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise GGBusApiError("Unsupported payload") from err

    return _xml_to_dict(root)


def _xml_to_dict(element: ET.Element) -> dict[str, Any] | str:
    if len(element) == 0:
        return (element.text or "").strip()

    values: dict[str, Any] = {}
    for child in element:
        value = _xml_to_dict(child)
        if child.tag in values:
            existing = values[child.tag]
            if not isinstance(existing, list):
                values[child.tag] = [existing, value]
            else:
                existing.append(value)
        else:
            values[child.tag] = value
    return values


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        (((payload.get("response") or {}).get("msgBody") or {}).get("busArrivalList")),
        (((payload.get("response") or {}).get("msgBody") or {}).get("busStationList")),
        (((payload.get("ServiceResult") or {}).get("msgBody") or {}).get("busArrivalList")),
        (((payload.get("ServiceResult") or {}).get("msgBody") or {}).get("busStationList")),
    ]
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    return []


def _extract_result_code(payload: dict[str, Any]) -> str | None:
    paths = [
        ((payload.get("response") or {}).get("msgHeader") or {}).get("resultCode"),
        ((payload.get("ServiceResult") or {}).get("msgHeader") or {}).get("resultCode"),
        (payload.get("cmmMsgHeader") or {}).get("returnReasonCode"),
    ]
    for value in paths:
        if value is not None:
            return str(value)
    return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    return str(value) in {"1", "true", "True", "Y", "y"}


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized if normalized else None
