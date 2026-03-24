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
        key="low_plate_1",
        name_suffix="1번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        value_fn=lambda arrival: arrival.low_plate_1,
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
        key="low_plate_2",
        name_suffix="2번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        value_fn=lambda arrival: arrival.low_plate_2,
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

    entities = [
        GGBusRouteMetricSensor(coordinator, entry, route_id, metric)
        for route_id in selected_route_ids
        for metric in METRICS
    ]
    async_add_entities(entities)


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
        """Return station device metadata."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.data[CONF_STATION_ID])},
            name=f"{self._entry.data[CONF_STATION_NAME]} ({self._entry.data[CONF_STATION_CODE]})",
            manufacturer="Gyeonggi-do",
            model="Bus Stop",
            entry_type="service",
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
