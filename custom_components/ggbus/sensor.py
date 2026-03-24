"""Sensor platform for Gyeonggi Bus arrivals."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Arrival
from .const import (
    CONF_SELECTED_ROUTES,
    CONF_STATION_CODE,
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


METRICS: tuple[GGBusMetricDescription, ...] = (
    GGBusMetricDescription(
        key="arrival_1",
        name_suffix="1번째 도착예정",
        icon="mdi:clock-outline",
        value_fn=lambda arrival: None if arrival.predict_time_1 is None else f"{arrival.predict_time_1}분",
    ),
    GGBusMetricDescription(
        key="location_1",
        name_suffix="1번째 남은 정류장",
        icon="mdi:map-marker-distance",
        value_fn=lambda arrival: arrival.location_no_1,
    ),
    GGBusMetricDescription(
        key="arrival_2",
        name_suffix="2번째 도착예정",
        icon="mdi:clock-fast",
        value_fn=lambda arrival: None if arrival.predict_time_2 is None else f"{arrival.predict_time_2}분",
    ),
    GGBusMetricDescription(
        key="location_2",
        name_suffix="2번째 남은 정류장",
        icon="mdi:map-marker-distance",
        value_fn=lambda arrival: arrival.location_no_2,
    ),
    GGBusMetricDescription(
        key="flag",
        name_suffix="운행상태",
        icon="mdi:bus-alert",
        value_fn=lambda arrival: arrival.flag,
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
        self._attr_name = f"{entry.data[CONF_STATION_NAME]} API 상태"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to parent station device."""
        station_id = self._entry.data[CONF_STATION_ID]
        station_name = self._entry.data[CONF_STATION_NAME]
        station_code = self._entry.data[CONF_STATION_CODE]
        return DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            name=f"{station_name} ({station_code})",
            manufacturer="Gyeonggi-do",
            model="Bus Stop",
        )

    @property
    def native_value(self) -> str:
        return self.coordinator.last_api_status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        success_at = self.coordinator.last_success_at
        return {
            "last_api_error": self.coordinator.last_api_error,
            "last_success_at": success_at.isoformat() if success_at else None,
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
        station_name = entry.data[CONF_STATION_NAME]

        self._attr_unique_id = f"{entry.entry_id}_{route_id}_{metric.key}"
        self._attr_name = f"{station_name} {route_id} {metric.name_suffix}"
        self._attr_icon = metric.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return bus device metadata (child of station device)."""
        arrival = self._arrival
        route_name = arrival.route_name if arrival else self._route_id
        station_id = self._entry.data[CONF_STATION_ID]
        station_name = self._entry.data[CONF_STATION_NAME]
        station_code = self._entry.data[CONF_STATION_CODE]

        return DeviceInfo(
            identifiers={(DOMAIN, f"{station_id}_{self._route_id}")},
            name=f"{route_name} ({self._route_id})",
            manufacturer="Gyeonggi-do",
            model="Bus Route",
            via_device=(DOMAIN, station_id),
            suggested_area=station_name,
            configuration_url=f"https://www.gbis.go.kr/gbis2014/station/stationInfo.do?stationId={station_id}",
            hw_version=f"Station {station_code}",
        )

    @property
    def native_value(self) -> Any:
        """Return metric value for the route."""
        arrival = self._arrival
        if arrival is None:
            return None
        return self._metric.value_fn(arrival)

    @property
    def available(self) -> bool:
        """Entity availability follows route presence in station payload."""
        return super().available and self._arrival is not None

    @property
    def _arrival(self) -> Arrival | None:
        return self.coordinator.data.get(self._route_id) if self.coordinator.data else None
