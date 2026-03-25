"""Config flow for Gyeonggi Bus integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .api import GGBusApi, GGBusApiError, GGBusAuthError, GGBusQuotaError, GGBusStationNotFoundError
from .const import (
    CONF_API_KEY,
    CONF_SELECTED_ROUTES,
    CONF_STATION_CODE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GGBusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GGBus."""

    VERSION = 1

    _api_key: str
    _station_code: str
    _station_id: str
    _station_name: str
    _route_options: dict[str, str]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY].strip()
            self._station_code = user_input[CONF_STATION_CODE].strip()
            api = GGBusApi(async_get_clientsession(self.hass), self._api_key)

            try:
                station = await api.resolve_station_by_code(self._station_code)
                arrivals = await api.get_station_arrivals(station.station_id)
            except GGBusAuthError:
                errors["base"] = "invalid_auth"
            except GGBusStationNotFoundError:
                errors["base"] = "station_not_found"
            except GGBusQuotaError:
                errors["base"] = "quota_exceeded"
            except GGBusApiError as err:
                _LOGGER.warning("GGBus setup failed for station_code=%s: %s", self._station_code, err)
                errors["base"] = "cannot_connect"
            else:
                self._station_id = station.station_id
                self._station_name = station.station_name
                self._route_options = {
                    route_id: arrival.route_name
                    for route_id, arrival in sorted(
                        arrivals.items(), key=lambda item: item[1].route_name
                    )
                }
                if not self._route_options:
                    errors["base"] = "no_routes_found"
                else:
                    await self.async_set_unique_id(self._station_id)
                    self._abort_if_unique_id_configured()
                    return await self.async_step_routes()

        default_api = self._default_api_key()
        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=default_api): str,
                vol.Required(CONF_STATION_CODE): vol.All(str, vol.Length(min=5, max=5)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_routes: list[str] = user_input[CONF_SELECTED_ROUTES]
            if not selected_routes:
                errors["base"] = "no_route_selected"
            else:
                return self.async_create_entry(
                    title=f"{self._station_name} ({self._station_code})",
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_STATION_CODE: self._station_code,
                        CONF_STATION_ID: self._station_id,
                        CONF_STATION_NAME: self._station_name,
                    },
                    options={CONF_SELECTED_ROUTES: selected_routes},
                )

        selector = SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"label": _route_label(name), "value": route_id}
                    for route_id, name in self._route_options.items()
                ],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
        schema = vol.Schema({vol.Required(CONF_SELECTED_ROUTES): selector})

        return self.async_show_form(
            step_id="routes",
            data_schema=schema,
            errors=errors,
            description_placeholders={"station_name": self._station_name},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GGBusOptionsFlow(config_entry)

    def _default_api_key(self) -> str:
        entries = self._async_current_entries()
        if not entries:
            return ""
        return entries[0].data.get(CONF_API_KEY, "")


class GGBusOptionsFlow(config_entries.OptionsFlow):
    """Options flow for selected route management."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        api = GGBusApi(
            async_get_clientsession(self.hass),
            self.config_entry.data[CONF_API_KEY],
        )

        try:
            arrivals = await api.get_station_arrivals(self.config_entry.data[CONF_STATION_ID])
        except GGBusAuthError:
            errors["base"] = "invalid_auth"
            arrivals = {}
        except GGBusQuotaError:
            errors["base"] = "quota_exceeded"
            arrivals = {}
        except GGBusApiError as err:
            _LOGGER.warning("GGBus options refresh failed for station_id=%s: %s", self.config_entry.data[CONF_STATION_ID], err)
            errors["base"] = "cannot_connect"
            arrivals = {}
        except Exception as err:  # defensive: avoid 500 in options dialog
            _LOGGER.exception("Unexpected error while opening GGBus options: %s", err)
            errors["base"] = "cannot_connect"
            arrivals = {}

        route_options = {
            route_id: arrival.route_name
            for route_id, arrival in sorted(
                arrivals.items(), key=lambda item: item[1].route_name
            )
        }

        if not route_options and not errors:
            errors["base"] = "no_routes_found"

        current_selected = self.config_entry.options.get(CONF_SELECTED_ROUTES, [])

        if user_input is not None and not errors:
            selected_routes: list[str] = user_input[CONF_SELECTED_ROUTES]
            if not selected_routes:
                errors["base"] = "no_route_selected"
            else:
                return self.async_create_entry(data={CONF_SELECTED_ROUTES: selected_routes})

        selector = SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"label": _route_label(name), "value": route_id}
                    for route_id, name in route_options.items()
                ],
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_ROUTES,
                    default=[rid for rid in current_selected if rid in route_options],
                ): selector
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


def _route_label(route_name: str) -> str:
    cleaned = route_name.strip()
    if not cleaned:
        return route_name
    if cleaned.endswith("번"):
        return cleaned
    return f"{cleaned}번"
