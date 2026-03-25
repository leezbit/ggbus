"""Binary sensor platform for low-floor information."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Arrival
from .const import (
    CONF_SELECTED_ROUTES,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
)
from .coordinator import GGBusCoordinator


@dataclass(frozen=True, slots=True)
class GGBusLowFloorDescription:
    """Description for low-floor binary sensors."""

    key: str
    name_suffix: str
    icon: str
    getter: str


LOW_FLOOR_METRICS: tuple[GGBusLowFloorDescription, ...] = (
    GGBusLowFloorDescription(
        key="low_plate_1",
        name_suffix="1번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        getter="low_plate_1",
    ),
    GGBusLowFloorDescription(
        key="low_plate_2",
        name_suffix="2번째 저상버스",
        icon="mdi:wheelchair-accessibility",
        getter="low_plate_2",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up low-floor binary sensors based on a config entry."""
    coordinator: GGBusCoordinator = entry.runtime_data
    selected_route_ids = entry.options.get(CONF_SELECTED_ROUTES, [])

    entities = [
        GGBusLowFloorBinarySensor(coordinator, entry, route_id, metric)
        for route_id in selected_route_ids
        for metric in LOW_FLOOR_METRICS
    ]
    async_add_entities(entities)


class GGBusLowFloorBinarySensor(CoordinatorEntity[GGBusCoordinator], BinarySensorEntity):
    """Binary sensor for low-floor availability per route."""

    def __init__(
        self,
        coordinator: GGBusCoordinator,
        entry: ConfigEntry,
        route_id: str,
        metric: GGBusLowFloorDescription,
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
        route_name = arrival.route_name if arrival else self._route_id
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
    def is_on(self) -> bool | None:
        """Return whether this arrival is a low-floor bus."""
        arrival = self._arrival
        if arrival is None:
            return None
        return getattr(arrival, self._metric.getter)

    @property
    def available(self) -> bool:
        """Entity availability follows route presence in station payload."""
        return super().available and self._arrival is not None

    @property
    def _arrival(self) -> Arrival | None:
        return self.coordinator.data.get(self._route_id) if self.coordinator.data else None
