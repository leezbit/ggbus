"""Constants for the Gyeonggi Bus integration."""

from __future__ import annotations

DOMAIN = "ggbus"
PLATFORMS = ["sensor"]

CONF_API_KEY = "api_key"
CONF_STATION_CODE = "station_code"
CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"
CONF_SELECTED_ROUTES = "selected_routes"
CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"
CONF_REDUCED_INTERVAL_MINUTES = "reduced_interval_minutes"

DEFAULT_SCAN_INTERVAL_SECONDS = 90
DEFAULT_REDUCED_INTERVAL_MINUTES = 20

ATTR_ROUTE_ID = "route_id"
ATTR_ROUTE_NAME = "route_name"
ATTR_LOCATION_NO_1 = "location_no_1"
ATTR_PREDICT_TIME_1 = "predict_time_1"
ATTR_LOCATION_NO_2 = "location_no_2"
ATTR_PREDICT_TIME_2 = "predict_time_2"
ATTR_FLAG = "flag"
ATTR_LOW_PLATE_1 = "low_plate_1"
ATTR_LOW_PLATE_2 = "low_plate_2"
ATTR_PLATE_NO_1 = "plate_no_1"
ATTR_PLATE_NO_2 = "plate_no_2"
