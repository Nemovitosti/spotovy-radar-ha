"""Konstanty integrace Spotový Radar."""

import logging
from datetime import timedelta

DOMAIN = "spotovy_radar"
LOGGER = logging.getLogger(__package__)

BASE_URL = "https://spotovyradar.cz"
ACCOUNT_URL = f"{BASE_URL}/ucet/api"
# Data se mění nejvýš po čtvrthodině, limit API je 240 dotazů za hodinu na klíč (D67).
UPDATE_INTERVAL = timedelta(minutes=5)
HORIZON_HOURS = 72
CHEAPEST_WINDOW_HOURS = 3
CHEAPEST_WITHIN = timedelta(hours=24)
