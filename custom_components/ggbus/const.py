"""Constants for the Gyeonggi Bus integration."""

from __future__ import annotations

DOMAIN = "ggbus"
PLATFORMS = ["sensor", "button"]

CONF_API_KEY = "api_key"
CONF_STATION_CODE = "station_code"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_SELECTED_ROUTES = "selected_routes"
CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"
CONF_TRIGGER_REFRESH_INTERVAL_SECONDS = "trigger_refresh_interval_seconds"
CONF_TRIGGER_REFRESH_DURATION_MINUTES = "trigger_refresh_duration_minutes"

DEFAULT_SCAN_INTERVAL_SECONDS = 90
DEFAULT_TRIGGER_REFRESH_INTERVAL_SECONDS = 30
DEFAULT_TRIGGER_REFRESH_DURATION_MINUTES = 0
