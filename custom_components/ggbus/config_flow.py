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
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
    _target_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            input_key = user_input[CONF_API_KEY].strip()
            self._api_key = input_key or self._default_api_key()
            self._station_code = user_input[CONF_STATION_CODE].strip()
            if not self._api_key:
                errors["base"] = "invalid_auth"
                api = None
            else:
                api = GGBusApi(async_get_clientsession(self.hass), self._api_key)

            try:
                if api is None:
                    raise GGBusAuthError
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
                    existing_entry = self._find_entry_by_station_id(self._station_id)
                    if existing_entry is not None:
                        self._target_entry = existing_entry
                        return await self.async_step_update_existing()

                    await self.async_set_unique_id(self._station_id)
                    self._abort_if_unique_id_configured()
                    return await self.async_step_routes()

        default_api = self._default_api_key()
        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=default_api): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
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

        return self.async_show_form(
            step_id="routes",
            data_schema=_build_route_schema(self._route_options),
            errors=errors,
            description_placeholders={"station_name": self._station_name},
        )

    async def async_step_update_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Update route selections for an already configured station."""
        errors: dict[str, str] = {}
        if self._target_entry is None:
            return self.async_abort(reason="cannot_connect")

        current_selected_raw = self._target_entry.options.get(CONF_SELECTED_ROUTES, [])
        current_selected = current_selected_raw if isinstance(current_selected_raw, list) else []

        if user_input is not None:
            selected_routes: list[str] = user_input[CONF_SELECTED_ROUTES]
            if not selected_routes:
                errors["base"] = "no_route_selected"
            else:
                self.hass.config_entries.async_update_entry(
                    self._target_entry,
                    options={CONF_SELECTED_ROUTES: selected_routes},
                )
                await self.hass.config_entries.async_reload(self._target_entry.entry_id)
                return self.async_abort(reason="reconfigured")

        return self.async_show_form(
            step_id="update_existing",
            data_schema=_build_route_schema(
                self._route_options,
                default=[rid for rid in current_selected if rid in self._route_options],
            ),
            errors=errors,
            description_placeholders={"station_name": self._station_name},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle clicking gear on an existing config entry."""
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        if entry is None:
            return self.async_abort(reason="cannot_connect")

        self._target_entry = entry
        self._api_key = entry.data[CONF_API_KEY]
        self._station_id = entry.data[CONF_STATION_ID]
        self._station_name = entry.data[CONF_STATION_NAME]
        self._station_code = entry.data[CONF_STATION_CODE]

        api = GGBusApi(async_get_clientsession(self.hass), self._api_key)
        errors: dict[str, str] = {}
        try:
            arrivals = await api.get_station_arrivals(self._station_id)
            self._route_options = {
                route_id: arrival.route_name
                for route_id, arrival in sorted(
                    arrivals.items(), key=lambda item: item[1].route_name
                )
            }
        except GGBusAuthError:
            errors["base"] = "invalid_auth"
            self._route_options = {}
        except GGBusQuotaError:
            errors["base"] = "quota_exceeded"
            self._route_options = {}
        except GGBusApiError as err:
            _LOGGER.warning("GGBus reconfigure load failed for station_id=%s: %s", self._station_id, err)
            errors["base"] = "cannot_connect"
            self._route_options = {}

        if not self._route_options:
            current_selected_raw = entry.options.get(CONF_SELECTED_ROUTES, [])
            current_selected = current_selected_raw if isinstance(current_selected_raw, list) else []
            self._route_options = {rid: rid for rid in current_selected}

        if errors:
            # still allow opening flow with cached/current selected routes
            _LOGGER.debug("Reconfigure opened with fallback options due to error: %s", errors)

        return await self.async_step_update_existing(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return GGBusOptionsFlow(config_entry)

    def _default_api_key(self) -> str:
        entries = self._async_current_entries()
        if not entries:
            return ""
        return entries[0].data.get(CONF_API_KEY, "")

    def _find_entry_by_station_id(self, station_id: str) -> config_entries.ConfigEntry | None:
        for entry in self._async_current_entries():
            if entry.data.get(CONF_STATION_ID) == station_id:
                return entry
        return None


class GGBusOptionsFlow(config_entries.OptionsFlow):
    """Options flow for selected route management."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        current_selected_raw = self.config_entry.options.get(CONF_SELECTED_ROUTES, [])
        current_selected = current_selected_raw if isinstance(current_selected_raw, list) else []
        route_options: dict[str, str] = {}

        try:
            api = GGBusApi(
                async_get_clientsession(self.hass),
                self.config_entry.data[CONF_API_KEY],
            )
            arrivals = await api.get_station_arrivals(self.config_entry.data[CONF_STATION_ID])
            route_options = {
                route_id: arrival.route_name
                for route_id, arrival in sorted(
                    arrivals.items(), key=lambda item: item[1].route_name
                )
            }
            if not route_options:
                errors["base"] = "no_routes_found"
        except GGBusAuthError:
            errors["base"] = "invalid_auth"
            route_options = {rid: rid for rid in current_selected}
        except GGBusQuotaError:
            errors["base"] = "quota_exceeded"
            route_options = {rid: rid for rid in current_selected}
        except GGBusApiError as err:
            _LOGGER.warning(
                "GGBus options refresh failed for station_id=%s: %s",
                self.config_entry.data[CONF_STATION_ID],
                err,
            )
            errors["base"] = "cannot_connect"
            route_options = {rid: rid for rid in current_selected}
        except Exception as err:
            _LOGGER.exception("Unexpected error while opening GGBus options: %s", err)
            errors["base"] = "cannot_connect"
            route_options = {rid: rid for rid in current_selected}

        if user_input is not None and not errors:
            selected_routes: list[str] = user_input[CONF_SELECTED_ROUTES]
            if not selected_routes:
                errors["base"] = "no_route_selected"
            else:
                return self.async_create_entry(data={CONF_SELECTED_ROUTES: selected_routes})

        return self.async_show_form(
            step_id="init",
            data_schema=_build_route_schema(
                route_options,
                default=[rid for rid in current_selected if rid in route_options],
            ),
            errors=errors,
        )


def _build_route_schema(route_options: dict[str, str], default: list[str] | None = None) -> vol.Schema:
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
    return vol.Schema(
        {
            vol.Required(
                CONF_SELECTED_ROUTES,
                default=default if default is not None else [],
            ): selector
        }
    )


def _route_label(route_name: str) -> str:
    cleaned = str(route_name).strip()
    if not cleaned:
        return "노선"
    if cleaned.endswith("번"):
        return cleaned
    return f"{cleaned}번"
