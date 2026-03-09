"""Constants for the DTEK Monitor integration."""

DOMAIN = "dtek_monitor"

DTEK_BASE_URL = "https://www.dtek-oem.com.ua"
DTEK_SHUTDOWNS_URL = f"{DTEK_BASE_URL}/ua/shutdowns"
DTEK_AJAX_URL = f"{DTEK_BASE_URL}/ua/ajax"

CONF_CITY = "city"
CONF_STREET = "street"
CONF_HOUSE = "house_num"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_SECONDS = 300
MIN_SCAN_INTERVAL_SECONDS = 60
MAX_SCAN_INTERVAL_SECONDS = 3600
REQUEST_TIMEOUT = 15

OUTAGE_TYPE_NONE = "ok"
OUTAGE_TYPE_EMERGENCY = "emergency"
OUTAGE_TYPE_PLANNED = "planned"
OUTAGE_TYPE_STABILIZATION = "stabilization"

DTEK_RAW_TYPE_EMERGENCY = "2"

ATTR_OUTAGE_TYPE = "outage_type"
ATTR_OUTAGE_DESCRIPTION = "outage_description"
ATTR_OUTAGE_START = "outage_start"
ATTR_OUTAGE_END = "outage_end"
ATTR_SCHEDULE_GROUPS = "schedule_groups"
ATTR_PRIMARY_SCHEDULE_GROUP = "primary_schedule_group"
ATTR_LAST_UPDATE = "last_update"

EVENT_SUMMARY_OUTAGE = "Планове відключення"
EVENT_SUMMARY_POSSIBLE = "Можливе відключення"
EVENT_DESCRIPTION_PLANNED = "Planned"
EVENT_DESCRIPTION_POSSIBLE = "Possible"

DEFAULT_NEXT_EVENT_LOOKAHEAD_DAYS = 8
