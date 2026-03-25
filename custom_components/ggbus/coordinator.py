"""Data coordinator for Gyeonggi Bus."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Arrival,
    GGBusApi,
    GGBusApiError,
    GGBusAuthError,
    GGBusQuotaError,
    run_status_text,
)
from .const import (
    CONF_API_KEY,
    CONF_REDUCED_INTERVAL_MINUTES,
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_STATION_ID,
    DEFAULT_REDUCED_INTERVAL_MINUTES,
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
        scan_seconds = int(entry.options.get(CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS))
        reduced_minutes = int(entry.options.get(CONF_REDUCED_INTERVAL_MINUTES, DEFAULT_REDUCED_INTERVAL_MINUTES))
        self._default_interval = timedelta(seconds=max(30, scan_seconds))
        self._reduced_interval = timedelta(minutes=max(5, reduced_minutes))

        self.last_api_status: str = "unknown"
        self.last_api_error: str | None = None
        self.last_success_at: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=self._default_interval,
        )

    async def _async_update_data(self) -> dict[str, Arrival]:
        try:
            arrivals = await self.api.get_station_arrivals(self.station_id)
            self.last_api_status = "ok"
            self.last_api_error = None
            self.last_success_at = datetime.now(timezone.utc)
            self._adjust_update_interval(arrivals)
            return arrivals
        except GGBusAuthError as err:
            self.last_api_status = "auth_error"
            self.last_api_error = str(err)
            raise ConfigEntryAuthFailed from err
        except GGBusQuotaError as err:
            self.last_api_status = "quota_exceeded"
            self.last_api_error = str(err)
            self.update_interval = self._reduced_interval
            raise UpdateFailed(str(err)) from err
        except GGBusApiError as err:
            self.last_api_error = str(err)
            if _is_quota_error(str(err)):
                self.last_api_status = "quota_exceeded"
                self.update_interval = self._reduced_interval
            else:
                self.last_api_status = "api_error"
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # pragma: no cover - defensive
            self.last_api_status = "unknown_error"
            self.last_api_error = str(err)
            raise ConfigEntryError(str(err)) from err

    def _adjust_update_interval(self, arrivals: dict[str, Arrival]) -> None:
        if arrivals and all(run_status_text(arrival.flag) == "미운행" for arrival in arrivals.values()):
            self.update_interval = self._reduced_interval
            return

        self.update_interval = self._default_interval

def _is_quota_error(message: str) -> bool:
    normalized = message.upper()
    keywords = (
        "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR",
        "LIMITED NUMBER OF SERVICE REQUESTS",
        "SERVICE REQUESTS EXCEEDS",
        "TOO MANY REQUESTS",
        "QUOTA",
    )
    return any(keyword in normalized for keyword in keywords)
