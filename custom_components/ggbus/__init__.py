"""The Gyeonggi Bus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_STATION_CODE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import GGBusCoordinator

GGBusConfigEntry = ConfigEntry[GGBusCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GGBusConfigEntry) -> bool:
    """Set up Gyeonggi Bus from a config entry."""
    coordinator = GGBusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    station_id = entry.data[CONF_STATION_ID]
    station_name = entry.data[CONF_STATION_NAME]
    station_code = entry.data[CONF_STATION_CODE]

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, station_id)},
        manufacturer="Gyeonggi-do",
        model="Bus Stop",
        name=f"{station_name} ({station_code})"
    )

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GGBusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: GGBusConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
