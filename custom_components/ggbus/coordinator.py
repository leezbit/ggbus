"""Data coordinator for Gyeonggi Bus."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
INFER_STOP_AFTER = timedelta(hours=1)
NIGHT_INFER_START = (1, 0)
NIGHT_INFER_END = (4, 30)

class GGBusCoordinator(DataUpdateCoordinator[dict[str, Arrival]]):
    """Coordinate station arrivals for all selected buses."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.entry = entry
        api_key = entry.data[CONF_API_KEY]
        self.station_id = entry.data[CONF_STATION_ID]
        self.api = GGBusApi(async_get_clientsession(hass), api_key)
        scan_seconds = int(entry.options.get(CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS))
        self._default_interval = timedelta(seconds=max(30, scan_seconds))
        self._no_predict_since: dict[str, datetime] = {}

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
            now_utc = datetime.now(timezone.utc)
            self.last_api_status = "ok"
            self.last_api_error = None
            self.last_success_at = now_utc
            self._update_no_predict_tracking(arrivals, now_utc)
            self.update_interval = self._default_interval
            return arrivals
        except GGBusAuthError as err:
            self.last_api_status = "auth_error"
            self.last_api_error = str(err)
            raise ConfigEntryAuthFailed from err
        except GGBusQuotaError as err:
            self.last_api_status = "quota_exceeded"
            self.last_api_error = str(err)
            self.update_interval = self._default_interval
            raise UpdateFailed(str(err)) from err
        except GGBusApiError as err:
            self.last_api_error = str(err)
            if _is_quota_error(str(err)):
                self.last_api_status = "quota_exceeded"
                self.update_interval = self._default_interval
            else:
                self.last_api_status = "api_error"
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # pragma: no cover - defensive
            self.last_api_status = "unknown_error"
            self.last_api_error = str(err)
            raise ConfigEntryError(str(err)) from err

    def is_inferred_stopped(self, route_id: str, *, now_utc: datetime | None = None) -> bool:
        """Infer non-running state for late-night PASS/WAIT with no ETA."""
        since = self._no_predict_since.get(route_id)
        if since is None:
            return False

        now = now_utc or datetime.now(timezone.utc)
        if now - since < INFER_STOP_AFTER:
            return False

        return _is_night_infer_window(dt_util.as_local(now))

    def _update_no_predict_tracking(self, arrivals: dict[str, Arrival], now_utc: datetime) -> None:
        active_route_ids = set(arrivals)
        for route_id in list(self._no_predict_since):
            if route_id not in active_route_ids:
                self._no_predict_since.pop(route_id, None)

        for route_id, arrival in arrivals.items():
            run_status = run_status_text(arrival.flag)
            is_waiting_like = run_status == "운행 중" and str(arrival.flag or "").strip().upper() in {"PASS", "WAIT"}
            no_eta = arrival.predict_time_1 is None and arrival.predict_time_2 is None
            if is_waiting_like and no_eta:
                self._no_predict_since.setdefault(route_id, now_utc)
            else:
                self._no_predict_since.pop(route_id, None)

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


def _is_night_infer_window(value: datetime) -> bool:
    return NIGHT_INFER_START <= (value.hour, value.minute) <= NIGHT_INFER_END
