"""Sensor platform for Gyeonggi Bus arrivals."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Arrival, run_status_text
from .const import (
    CONF_SELECTED_ROUTES,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
)
from .coordinator import GGBusCoordinator


@dataclass(frozen=True, slots=True)
class GGBusMetricDescription:
    """Description for per-route metric entity."""

    key: str
    name_suffix: str
    icon: str
    value_fn: Callable[[Arrival], Any]
    unit: str | None = None


METRICS: tuple[GGBusMetricDescription, ...] = (
    GGBusMetricDescription(
        key="arrival_1",
        name_suffix="1번째 도착예정",
        icon="mdi:clock-outline",
        unit="분",
        value_fn=lambda arrival: arrival.predict_time_1,
    ),
    GGBusMetricDescription(
        key="location_1",
        name_suffix="1번째 전 정류장",
        icon="mdi:map-marker-distance",
        unit="번째 전",
        value_fn=lambda arrival: arrival.location_no_1,
    ),
    GGBusMetricDescription(
        key="low_plate_1",
        name_suffix="1번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        value_fn=lambda arrival: _low_floor_text(arrival.low_plate_1),
    ),
    GGBusMetricDescription(
        key="arrival_2",
        name_suffix="2번째 도착예정",
        icon="mdi:clock-fast",
        unit="분",
        value_fn=lambda arrival: arrival.predict_time_2,
    ),
    GGBusMetricDescription(
        key="location_2",
        name_suffix="2번째 전 정류장",
        icon="mdi:map-marker-distance",
        unit="번째 전",
        value_fn=lambda arrival: arrival.location_no_2,
    ),
    GGBusMetricDescription(
        key="low_plate_2",
        name_suffix="2번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        value_fn=lambda arrival: _low_floor_text(arrival.low_plate_2),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up bus arrival sensors based on a config entry."""
    coordinator: GGBusCoordinator = entry.runtime_data
    selected_route_ids = entry.options.get(CONF_SELECTED_ROUTES, [])

    registry = er.async_get(hass)
    valid_unique_ids = {f"{entry.entry_id}_api_status"}
    for route_id in selected_route_ids:
        for metric in METRICS:
            valid_unique_ids.add(f"{entry.entry_id}_{route_id}_{metric.key}")

    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.unique_id and reg_entry.unique_id.startswith(f"{entry.entry_id}_"):
            if reg_entry.unique_id not in valid_unique_ids:
                registry.async_remove(reg_entry.entity_id)

    device_registry = dr.async_get(hass)
    station_id = entry.data[CONF_STATION_ID]
    selected_set = set(selected_route_ids)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain != DOMAIN:
                continue
            prefix = f"{station_id}_"
            if identifier.startswith(prefix):
                route_id = identifier[len(prefix) :]
                if route_id not in selected_set:
                    device_registry.async_remove_device(device.id)
                break

    entities: list[SensorEntity] = [GGBusApiStatusSensor(coordinator, entry)]
    entities.extend(
        GGBusRouteMetricSensor(coordinator, entry, route_id, metric)
        for route_id in selected_route_ids
        for metric in METRICS
    )
    async_add_entities(entities)


class GGBusApiStatusSensor(CoordinatorEntity[GGBusCoordinator], SensorEntity):
    """Expose API status and last error for easier troubleshooting."""

    _attr_icon = "mdi:api"

    def __init__(self, coordinator: GGBusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_api_status"
        self._attr_name = "API 상태"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to parent station device."""
        station_id = self._entry.data[CONF_STATION_ID]
        station_name = self._entry.data[CONF_STATION_NAME]
        return DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            name=station_name,
            manufacturer="Gyeonggi-do",
            model="Bus Stop",
        )

    @property
    def native_value(self) -> str:
        return _api_status_text(self.coordinator.last_api_status)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        success_at = self.coordinator.last_success_at
        return {
            "raw_api_status": self.coordinator.last_api_status,
            "last_api_error": self.coordinator.last_api_error,
            "last_success_at": success_at.isoformat() if success_at else None,
            "current_poll_seconds": int(self.coordinator.update_interval.total_seconds()),
        }

    @property
    def available(self) -> bool:
        """Always show status sensor even during API errors."""
        return True


class GGBusRouteMetricSensor(CoordinatorEntity[GGBusCoordinator], SensorEntity):
    """Represent one metric for a specific route at a station."""

    def __init__(
        self,
        coordinator: GGBusCoordinator,
        entry: ConfigEntry,
        route_id: str,
        metric: GGBusMetricDescription,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._route_id = route_id
        self._metric = metric
        self._attr_unique_id = f"{entry.entry_id}_{route_id}_{metric.key}"
        self._attr_name = metric.name_suffix
        self._attr_has_entity_name = True
        self._attr_icon = metric.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return bus device metadata (child of station device)."""
        arrival = self._arrival
        route_name = _route_label(arrival.route_name if arrival else self._route_id)
        station_id = self._entry.data[CONF_STATION_ID]
        station_name = self._entry.data[CONF_STATION_NAME]

        return DeviceInfo(
            identifiers={(DOMAIN, f"{station_id}_{self._route_id}")},
            name=route_name,
            manufacturer="Gyeonggi-do",
            model="Bus Route",
            via_device=(DOMAIN, station_id),
            suggested_area=station_name,
        )

    @property
    def native_value(self) -> Any:
        """Return metric value for the route."""
        arrival = self._arrival
        if arrival is None:
            return None

        value = self._metric.value_fn(arrival)
        if self._metric.key in {"arrival_1", "arrival_2"} and value is None:
            if run_status_text(arrival.flag) == "미운행" or self.coordinator.is_inferred_stopped(self._route_id):
                return "운행종료"
            return "대기 중"
        if self._metric.key in {"location_1", "location_2"} and value is None:
            return "정보없음"
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit only when state is numeric."""
        if self._metric.unit is None:
            return None
        value = self.native_value
        return self._metric.unit if isinstance(value, (int, float)) else None

    @property
    def available(self) -> bool:
        """Entity availability follows route presence in station payload."""
        return super().available and self._arrival is not None

    @property
    def _arrival(self) -> Arrival | None:
        return self.coordinator.data.get(self._route_id) if self.coordinator.data else None


def _route_label(route_name: str) -> str:
    cleaned = str(route_name).strip()
    if not cleaned:
        return "노선"
    if cleaned.endswith("번"):
        return cleaned
    return f"{cleaned}번"


def _low_floor_text(code: str | None) -> str:
    mapping = {
        "0": "일반",
        "1": "저상",
        "2": "2층",
        "5": "전세",
        "6": "예약",
        "7": "트롤리",
    }
    return mapping.get(code, "정보없음")


def _api_status_text(status: str | None) -> str:
    mapping = {
        "ok": "정상",
        "auth_error": "인증오류",
        "quota_exceeded": "할당초과",
        "api_error": "API오류",
        "unknown_error": "오류",
    }
    if not status:
        return "알 수 없음"
    return mapping.get(status, status)
