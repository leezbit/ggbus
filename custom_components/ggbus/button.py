"""Button platform for manual trigger refresh."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STATION_ID, CONF_STATION_NAME, DOMAIN
from .coordinator import GGBusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trigger refresh button."""
    coordinator: GGBusCoordinator = entry.runtime_data
    async_add_entities([GGBusTriggerRefreshButton(coordinator, entry)])


class GGBusTriggerRefreshButton(CoordinatorEntity[GGBusCoordinator], ButtonEntity):
    """Expose a button to trigger refresh window."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: GGBusCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_trigger_refresh"
        self._attr_name = "도착정보 갱신 시작"

    @property
    def device_info(self) -> DeviceInfo:
        station_id = self._entry.data[CONF_STATION_ID]
        station_name = self._entry.data[CONF_STATION_NAME]
        return DeviceInfo(
            identifiers={(DOMAIN, station_id)},
            name=station_name,
            manufacturer="Gyeonggi-do",
            model="Bus Stop",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_trigger_refresh_window()
