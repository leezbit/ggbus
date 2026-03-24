"""Sensor platform for Gyeonggi Bus arrivals."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Arrival
from .const import (
    ATTR_FLAG,
    ATTR_LOCATION_NO_1,
    ATTR_LOCATION_NO_2,
    ATTR_LOW_PLATE_1,
    ATTR_LOW_PLATE_2,
    ATTR_PLATE_NO_1,
    ATTR_PLATE_NO_2,
    ATTR_PREDICT_TIME_1,
    ATTR_PREDICT_TIME_2,
    ATTR_ROUTE_ID,
    ATTR_ROUTE_NAME,
    CONF_SELECTED_ROUTES,
    CONF_STATION_CODE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
)
from .coordinator import GGBusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up bus arrival sensors based on a config entry."""
    coordinator: GGBusCoordinator = entry.runtime_data
    selected_route_ids = entry.options.get(CONF_SELECTED_ROUTES, [])

    entities = [
        GGBusArrivalSensor(coordinator, entry, route_id)
        for route_id in selected_route_ids
    ]
    async_add_entities(entities)


class GGBusArrivalSensor(CoordinatorEntity[GGBusCoordinator], SensorEntity):
    """Represent a route arrival sensor under a station device."""

    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: GGBusCoordinator, entry: ConfigEntry, route_id: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._route_id = route_id
        station_name = entry.data[CONF_STATION_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{route_id}"
        self._attr_name = f"{station_name} {route_id}"

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
    def native_value(self) -> str | None:
        """Return a concise first-arrival status."""
        arrival = self._arrival
        if arrival is None:
            return None
        if arrival.predict_time_1 is None:
            return "운행정보 없음"
        return f"{arrival.predict_time_1}분"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose full first/second arrival payload."""
        arrival = self._arrival
        if arrival is None:
            return {}

        return {
            ATTR_ROUTE_ID: arrival.route_id,
            ATTR_ROUTE_NAME: arrival.route_name,
            ATTR_LOCATION_NO_1: arrival.location_no_1,
            ATTR_PREDICT_TIME_1: arrival.predict_time_1,
            ATTR_LOCATION_NO_2: arrival.location_no_2,
            ATTR_PREDICT_TIME_2: arrival.predict_time_2,
            ATTR_FLAG: arrival.flag,
            ATTR_LOW_PLATE_1: arrival.low_plate_1,
            ATTR_LOW_PLATE_2: arrival.low_plate_2,
            ATTR_PLATE_NO_1: arrival.plate_no_1,
            ATTR_PLATE_NO_2: arrival.plate_no_2,
        }

    @property
    def available(self) -> bool:
        """Entity availability follows route presence in station payload."""
        return super().available and self._arrival is not None

    @property
    def _arrival(self) -> Arrival | None:
        return self.coordinator.data.get(self._route_id) if self.coordinator.data else None
