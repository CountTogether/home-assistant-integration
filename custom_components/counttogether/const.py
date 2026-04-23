"""Constants for the CountTogether integration."""

DOMAIN = "counttogether"

BASE_URL = "https://developers.counttogether.app"
API_V2 = "/v2"

CONF_API_TOKEN = "api_token"
CONF_TIMEZONE = "timezone"

DEFAULT_SCAN_INTERVAL = 60  # seconds

COUNTER_TYPE_UPDOWN = "UpDown"
COUNTER_TYPE_FROM_DATE = "FromDate"
COUNTER_TYPE_TO_DATE = "ToDate"

# Service names
SERVICE_INCREMENT = "increment"
SERVICE_DECREMENT = "decrement"
SERVICE_SET_VALUE = "set_value"
SERVICE_SET_START_DATE = "set_start_date"
SERVICE_SET_END_DATE = "set_end_date"
SERVICE_RESET = "reset"

# Service field names
ATTR_COUNTER_ID = "counter_id"
ATTR_AMOUNT = "amount"
ATTR_VALUE = "value"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"

