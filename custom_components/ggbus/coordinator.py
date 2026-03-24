"""Data coordinator for Gyeonggi Bus."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Arrival, GGBusApi, GGBusApiError, GGBusAuthError
from .const import (
    CONF_API_KEY,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GGBusCoordinator(DataUpdateCoordinator[dict[str, Arrival]]):
    """Coordinate station arrivals for all selected buses."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        api_key = entry.data[CONF_API_KEY]
        self.station_id = entry.data[CONF_STATION_ID]
        self.api = GGBusApi(async_get_clientsession(hass), api_key)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Arrival]:
        try:
            return await self.api.get_station_arrivals(self.station_id)
        except GGBusAuthError as err:
            raise ConfigEntryAuthFailed from err
        except GGBusApiError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # pragma: no cover - defensive
            raise ConfigEntryError(str(err)) from err
