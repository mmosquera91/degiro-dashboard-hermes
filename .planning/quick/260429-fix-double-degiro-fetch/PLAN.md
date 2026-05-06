"""DeGiro authentication and portfolio fetching (degiro-connector v3 API)."""

import logging
import threading
import time
from typing import Optional

import requests

from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.account import UpdateRequest, UpdateOption
from degiro_connector.trading.models.login import Login, LoginError, LoginSuccess
from degiro_connector.core.exceptions import DeGiroConnectionError, CaptchaRequiredError, MaintenanceError
from degiro_connector.core.constants import urls
from degiro_connector.core.abstracts.abstract_action import AbstractAction

logger = logging.getLogger(__name__)

# ─── Module-level fetch cache (prevents duplicate DeGiro calls within TTL) ───
_fetch_cache: dict[int, tuple[dict, float]] = {}
_fetch_lock = threading.Lock()
_FETCH_TTL = 30.0  # seconds