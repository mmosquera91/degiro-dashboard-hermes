"""DeGiro authentication and portfolio fetching (degiro-connector v3 API)."""

import logging
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


def _extract_error_message(login_error: LoginError) -> str:
    """Extract a human-readable message from a LoginError."""
    d = login_error.model_dump(mode="python", by_alias=True, exclude_none=True)
    status_text = d.get("statusText") or d.get("status_text", "")
    status_code = d.get("status")
    captcha = d.get("captchaRequired") or d.get("captcha_required", False)
    remaining = d.get("remainingAttempts", d.get("remaining_attempts"))

    if captcha:
        return "Captcha required. Log in to DeGiro via your browser first to solve the captcha, then try again."
    if status_text:
        if status_text.lower() == "badcredentials":
            msg = "Invalid username or password."
            if remaining is not None:
                msg += f" ({remaining} attempts remaining before lockout.)"
            return msg
        return f"DeGiro login error: {status_text}"
    if status_code == 6:
        return "2FA is required. Please provide your one-time code."
    if status_code == 12:
        return "Open the DeGiro app and approve the login request."
    if status_code == 405:
        return "DeGiro is under maintenance."
    return f"DeGiro login failed (status {status_code})."


def _send_raw_request(
    session: requests.Session,
    url: str,
    payload: dict,
    extra_headers: Optional[dict] = None,
) -> tuple[requests.Response, dict]:
    """Send a raw request and return (response, request_info)."""
    request = requests.Request(method="POST", url=url, json=payload)
    prepped = session.prepare_request(request)

    if extra_headers:
        for k, v in extra_headers.items():
            prepped.headers[k] = v

    request_info = {
        "url": url,
        "payload": payload,
        "headers": dict(prepped.headers),
    }

    try:
        response = session.send(prepped)
        return response, request_info
    except Exception as e:
        logger.error("Request failed: %s", e)
        raise


def _try_login_variant(
    username: str,
    password: str,
    otp: Optional[str] = None,
    variant_name: str = "",
    payload_override: Optional[dict] = None,
    headers_override: Optional[dict] = None,
    two_step: bool = False,
) -> dict:
    """Try a specific login variant and return detailed result."""
    session = requests.Session()
    url_login = urls.LOGIN
    url_totp = urls.LOGIN + "/totp"

    payload = payload_override or {
        "username": username.lower().strip(),
        "password": password,
        "isPassCodeReset": False,
        "isRedirectToMobile": False,
        "oneTimePassword": otp,
        "queryTarams": {},
    }

    extra_headers = headers_override or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        "Origin": "https://trader.degiro.nl",
        "Referer": "https://trader.degiro.nl/trader/",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    result = {"variant": variant_name, "steps": []}

    try:
        if two_step and otp:
            # Step 1: /login
            step1_payload = {k: v for k, v in payload.items()}
            response1, req_info1 = _send_raw_request(session, url_login, step1_payload, extra_headers)
            result["steps"].append({
                "url": url_login,
                "status_code": response1.status_code,
                "response_body": response1.text[:1000],
                "response_headers": dict(response1.headers),
                "request_payload": step1_payload,
            })

            # Step 2: /totp
            response, req_info = _send_raw_request(session, url_totp, payload, extra_headers)
            result["steps"].append({
                "url": url_totp,
                "status_code": response.status_code,
                "response_body": response.text[:1000],
                "response_headers": dict(response.headers),
                "request_payload": payload,
            })
        else:
            url = url_totp if otp else url_login
            response, req_info = _send_raw_request(session, url, payload, extra_headers)
            result["steps"].append({
                "url": url,
                "status_code": response.status_code,
                "response_body": response.text[:1000],
                "response_headers": dict(response.headers),
                "request_payload": payload,
            })

        # Parse final response
        final_response = response
        if final_response.status_code == 200:
            login_success = LoginSuccess.model_validate_json(json_data=final_response.text)
            result["session_id_present"] = bool(login_success.session_id)
            result["parsed_success"] = login_success.model_dump(mode="python", by_alias=True, exclude_none=True)
        else:
            try:
                login_error = LoginError.model_validate_json(json_data=final_response.text)
                result["parsed_error"] = login_error.model_dump(mode="python", by_alias=True, exclude_none=True)
            except Exception as parse_err:
                result["parse_error"] = str(parse_err)

    except Exception as e:
        result["exception"] = str(e)

    return result


def debug_login_variants(username: str, password: str, otp: Optional[str] = None) -> list[dict]:
    """Try multiple login variants and return results for comparison."""
    username_clean = username.lower().strip()

    variants = []

    # Variant A: degiro-connector v3 style (direct /totp, queryTarams, no extra headers)
    variants.append(_try_login_variant(
        username, password, otp,
        variant_name="A: degiro-connector style (direct /totp, queryTarams, no extra headers)",
        payload_override={
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "oneTimePassword": otp,
            "queryTarams": {},
        },
        headers_override={"Content-Type": "application/json"},
        two_step=False,
    ))

    # Variant B: TypeScript repo style (2-step, queryParams, browser headers)
    variants.append(_try_login_variant(
        username, password, otp,
        variant_name="B: TS repo style (2-step, queryParams, browser headers)",
        payload_override={
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "oneTimePassword": otp,
            "queryParams": {"reason": "session_expired"},
        },
        two_step=True,
    ))

    # Variant C: Minimal payload, direct /totp, minimal headers
    variants.append(_try_login_variant(
        username, password, otp,
        variant_name="C: minimal payload, direct /totp, minimal headers",
        payload_override={
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "oneTimePassword": otp,
        },
        headers_override={"Content-Type": "application/json"},
        two_step=False,
    ))

    # Variant D: degiro-connector payload but WITH browser headers (direct /totp)
    variants.append(_try_login_variant(
        username, password, otp,
        variant_name="D: degiro-connector payload + browser headers (direct /totp)",
        payload_override={
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "oneTimePassword": otp,
            "queryTarams": {},
        },
        headers_override={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://trader.degiro.nl",
            "Referer": "https://trader.degiro.nl/trader/",
            "Content-Type": "application/json",
        },
        two_step=False,
    ))

    # Variant E: 2-step without OTP in first request
    if otp:
        session = requests.Session()
        url_login = urls.LOGIN
        url_totp = urls.LOGIN + "/totp"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://trader.degiro.nl",
            "Referer": "https://trader.degiro.nl/trader/",
            "Content-Type": "application/json",
        }

        step1_payload = {
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "queryTarams": {},
        }

        result_e = {"variant": "E: 2-step, step1 WITHOUT otp, step2 WITH otp", "steps": []}
        try:
            response1, _ = _send_raw_request(session, url_login, step1_payload, headers)
            result_e["steps"].append({
                "url": url_login,
                "status_code": response1.status_code,
                "response_body": response1.text[:1000],
                "request_payload": step1_payload,
            })

            step2_payload = {
                "username": username_clean,
                "password": password,
                "isPassCodeReset": False,
                "isRedirectToMobile": False,
                "oneTimePassword": otp,
                "queryTarams": {},
            }
            response2, _ = _send_raw_request(session, url_totp, step2_payload, headers)
            result_e["steps"].append({
                "url": url_totp,
                "status_code": response2.status_code,
                "response_body": response2.text[:1000],
                "request_payload": step2_payload,
            })

            if response2.status_code == 200:
                login_success = LoginSuccess.model_validate_json(json_data=response2.text)
                result_e["session_id_present"] = bool(login_success.session_id)
                result_e["parsed_success"] = login_success.model_dump(mode="python", by_alias=True, exclude_none=True)
            else:
                try:
                    login_error = LoginError.model_validate_json(json_data=response2.text)
                    result_e["parsed_error"] = login_error.model_dump(mode="python", by_alias=True, exclude_none=True)
                except Exception as parse_err:
                    result_e["parse_error"] = str(parse_err)
        except Exception as e:
            result_e["exception"] = str(e)

        variants.append(result_e)

    # Variant F: GET login page first (to obtain session cookies), then POST to /totp
    session = requests.Session()
    url_login_page = "https://trader.degiro.nl/login"
    url_totp = urls.LOGIN + "/totp"
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    result_f = {"variant": "F: GET login page first for cookies, then POST /totp", "steps": []}
    try:
        # Step 1: GET login page
        get_response = session.get(url_login_page, headers=browser_headers, allow_redirects=True)
        result_f["steps"].append({
            "url": get_response.url,
            "status_code": get_response.status_code,
            "cookies": dict(session.cookies),
            "response_headers": dict(get_response.headers),
        })

        # Step 2: POST to /totp using the same session (with cookies)
        payload_f = {
            "username": username_clean,
            "password": password,
            "isPassCodeReset": False,
            "isRedirectToMobile": False,
            "oneTimePassword": otp,
            "queryTarams": {},
        }
        post_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,nl;q=0.8",
            "Origin": "https://trader.degiro.nl",
            "Referer": "https://trader.degiro.nl/login",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        response_f, _ = _send_raw_request(session, url_totp, payload_f, post_headers)
        result_f["steps"].append({
            "url": url_totp,
            "status_code": response_f.status_code,
            "response_body": response_f.text[:1000],
            "request_payload": payload_f,
        })

        if response_f.status_code == 200:
            login_success = LoginSuccess.model_validate_json(json_data=response_f.text)
            result_f["session_id_present"] = bool(login_success.session_id)
            result_f["parsed_success"] = login_success.model_dump(mode="python", by_alias=True, exclude_none=True)
        else:
            try:
                login_error = LoginError.model_validate_json(json_data=response_f.text)
                result_f["parsed_error"] = login_error.model_dump(mode="python", by_alias=True, exclude_none=True)
            except Exception as parse_err:
                result_f["parse_error"] = str(parse_err)
    except Exception as e:
        result_f["exception"] = str(e)

    variants.append(result_f)

    return variants


def _login_request(username: str, password: str, otp: Optional[str] = None) -> tuple[Optional[str], Optional[LoginError]]:
    """Perform a raw login request against DeGiro using the most reliable variant.

    Returns (session_id, login_error). Both can be None.
    """
    session = requests.Session()
    username = username.lower().strip()

    # Use the payload that matches degiro-connector v3 exactly
    payload = {
        "username": username,
        "password": password,
        "isPassCodeReset": False,
        "isRedirectToMobile": False,
        "oneTimePassword": otp,
        "queryTarams": {},
    }

    url = urls.LOGIN + "/totp" if otp else urls.LOGIN

    logger.info("Login URL: %s", url)
    logger.info("Username: %s***", username[:3] if len(username) > 3 else username[:1])
    logger.info("OTP provided: %s", bool(otp))

    request = requests.Request(method="POST", url=url, json=payload)
    prepped = session.prepare_request(request)

    # Minimal headers — only Content-Type, no browser headers that might cause issues
    prepped.headers["Content-Type"] = "application/json"

    try:
        response = session.send(prepped)
        logger.info("Login response status: %s", response.status_code)

        if response.status_code == 200:
            login_success = LoginSuccess.model_validate_json(json_data=response.text)
            logger.info("Login success, session_id present: %s", bool(login_success.session_id))
            return login_success.session_id, None
        elif response.status_code == 405:
            return None, LoginError(error="Scheduled maintenance", status=405, status_text="Maintenance")
        elif response.status_code >= 500:
            logger.error("DeGiro server error %s: %s", response.status_code, response.text[:500])
            return None, LoginError(error=f"Server error {response.status_code}", status=response.status_code, status_text="ServerError")
        else:
            try:
                login_error = LoginError.model_validate_json(json_data=response.text)
                logger.info("Login error parsed: status=%s statusText=%s", login_error.status, getattr(login_error, 'status_text', getattr(login_error, 'statusText', '')))
                return None, login_error
            except Exception as parse_err:
                logger.error("Failed to parse login error response: %s", parse_err)
                logger.error("Raw response (%s): %s", response.status_code, response.text[:500])
                return None, LoginError(error=f"Unexpected response ({response.status_code}): {response.text[:200]}", status=response.status_code, status_text="ParseError")
    except requests.HTTPError as e:
        logger.error("HTTP error during login: %s", e)
        return None, LoginError(error=str(e), status=0, status_text="HTTPError")
    except Exception as e:
        logger.error("Exception during login: %s", e)
        return None, LoginError(error=str(e), status=0, status_text="Exception")


def _extract_error_from_exception(exc: Exception) -> str:
    """Extract a human-readable message from a DeGiro exception."""
    if isinstance(exc, (CaptchaRequiredError, MaintenanceError)):
        return str(exc)

    login_error = getattr(exc, "login_error", None)
    if login_error and isinstance(login_error, LoginError):
        return _extract_error_message(login_error)

    msg = str(exc)
    if "No session id returned" in msg:
        return "Invalid username or password."
    return msg


def _kv_list_to_dict(kv_list):
    """Convert DeGiro key-value list format to flat dict.

    DeGiro sometimes returns data as:
        [{"name": "size", "value": 64, "isAdded": True}, ...]
    instead of flat dicts. This converts it back.
    If already a dict, returns as-is.
    """
    if isinstance(kv_list, dict):
        return kv_list
    if not isinstance(kv_list, list):
        return {}
    return {
        item.get("name"): item.get("value")
        for item in kv_list
        if isinstance(item, dict) and "name" in item
    }


def _infer_currency_from_isin(isin: str) -> str:
    """Infer likely trading currency from ISIN country prefix.

    This is a last-resort fallback only — used when DeGiro's product info
    does not include an explicit currency field.

    ISIN prefixes: US → USD, CA → CAD, GB → GBP, JP → JPY.
    IE/LU → UCITS ETF (could be EUR or USD depending on listing — return "")
    so the caller falls through to the hardcoded "EUR" default instead.
    """
    if not isin or len(isin) < 2:
        return ""
    prefix = isin[:2].upper()
    return {
        "US": "USD",
        "CA": "CAD",
        "GB": "GBP",
        "JP": "JPY",
        "AU": "AUD",
        "CH": "CHF",
    }.get(prefix, "")


_EXCHANGE_ID_CURRENCY: dict[str, str] = {
    # EUR exchanges
    "200": "EUR",  # Euronext Amsterdam
    "394": "EUR",  # Euronext Paris
    "645": "EUR",  # Xetra (Deutsche Börse)
    "72":  "EUR",  # Frankfurt
    "2":   "EUR",  # Hamburg
    "3":   "EUR",  # Berlin
    "4":   "EUR",  # Düsseldorf
    "5":   "EUR",  # Munich
    "6":   "EUR",  # Stuttgart
    "109": "EUR",  # Helsinki
    "296": "EUR",  # Borsa Italiana (Milan)
    "750": "EUR",  # Bolsa de Madrid
    "490": "EUR",  # Euronext Brussels
    "314": "EUR",  # Euronext Lisbon
    "194": "SEK",  # Stockholm
    "518": "NOK",  # Oslo
    "735": "DKK",  # Copenhagen
    # CHF
    "455": "CHF",  # SIX Swiss Exchange
    # GBP
    "663": "GBP",  # London Stock Exchange
    # USD
    "676": "USD",  # NASDAQ
    "13":  "USD",  # NYSE
    "14":  "USD",  # NASDAQ (alternate)
    "75":  "USD",  # NASDAQ (alternate)
    "71":  "USD",  # NYSE MKT (AMEX)
    # CAD
    "130": "CAD",  # Toronto Stock Exchange
    # SGD
    "737": "SGD",  # Singapore Exchange
}


def _currency_from_exchange_id(exchange_id: str) -> str:
    """Return the trading currency for a DeGiro exchangeId.
    Returns empty string if unknown, so caller falls through."""
    return _EXCHANGE_ID_CURRENCY.get(str(exchange_id), "")


# Well-known US tickers that commonly appear in European DeGiro portfolios.
    # This list is a catch-all for when product info is unavailable.
    # Pattern: bare uppercase alpha symbols that trade on US exchanges only.
    _KNOWN_USD_SYMBOLS = {
        "UNH", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META",
        "TSLA", "BRK-B", "JPM", "V", "MA", "JNJ", "WMT", "PG", "HD",
        "CVX", "XOM", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
        "COST", "AVGO", "ORCL", "ACN", "TXN", "NEE", "RTX", "HON", "UPS",
        "CAT", "GS", "MS", "BAC", "WFC", "C", "BLK", "SCHW", "AXP",
        "QUBT", "RGTI", "LWLG", "ONDS", "POET", "CRGO",
    }

    @staticmethod
    def _infer_currency_from_symbol(symbol: str) -> str:
        """Infer trading currency from well-known US stock symbols.
        Returns 'USD' if recognised, '' otherwise.
        """
        if not symbol:
            return ""
        return "USD" if symbol.upper() in DeGiroClient._KNOWN_USD_SYMBOLS else ""


class DeGiroClient:
    """Handles DeGiro authentication and portfolio data retrieval."""

    @staticmethod
    def authenticate(username: str, password: str, otp: Optional[str] = None) -> TradingAPI:
        """Authenticate with DeGiro using the official connector flow.

        Credentials are NOT stored anywhere — only used to establish the session.
        """
        username = username.lower().strip()

        creds_data = {
            "username": username,
            "password": password,
        }
        if otp:
            creds_data["one_time_password"] = str(otp)

        # model_construct skips Pydantic validation so one_time_password stays a string
        # (preserving leading zeros that int() would strip).
        credentials = Credentials.model_construct(**creds_data)
        trading_api = TradingAPI(credentials=credentials)

        try:
            trading_api.connect.call()
        except DeGiroConnectionError as exc:
            login_error = getattr(exc, "login_error", None)
            status = getattr(login_error, "status", None) if login_error else None

            if not otp and status == 6:
                raise ConnectionError(
                    "DeGiro authentication failed: 2FA is enabled on your account. "
                    "Please enter your one-time code and try again."
                )

            msg = _extract_error_from_exception(exc)
            raise ConnectionError(f"DeGiro authentication failed: {msg}")

        except (CaptchaRequiredError, MaintenanceError) as exc:
            msg = _extract_error_from_exception(exc)
            raise ConnectionError(f"DeGiro authentication failed: {msg}")

        except Exception as exc:
            logger.error("Unexpected auth exception: %s", exc)
            raise ConnectionError(f"DeGiro authentication failed: {str(exc)}")

        DeGiroClient._fetch_int_account(trading_api)
        logger.info("DeGiro authentication successful for user: %s", username[:3] + "***")
        return trading_api

    @staticmethod
    def from_session_id(session_id: str, int_account: int | None = None) -> TradingAPI:
        """Create a TradingAPI from an existing session ID (e.g. extracted from browser).

        No credentials are required or stored.
        """
        if not session_id:
            raise ConnectionError("Session ID is required.")

        credentials = Credentials.model_construct(username="x", password="x")
        trading_api = TradingAPI(credentials=credentials)
        trading_api.connection_storage.session_id = session_id

        if int_account:
            trading_api.credentials.int_account = int_account
            logger.info("DeGiro session loaded from browser session_id (int_account provided).")
        else:
            DeGiroClient._fetch_int_account(trading_api)
            logger.info("DeGiro session loaded from browser session_id.")
        return trading_api

    @staticmethod
    def _fetch_int_account(trading_api: TradingAPI) -> None:
        """Fetch and set int_account from client details."""
        try:
            client_details = trading_api.get_client_details.call()
            if client_details:
                data = client_details.get("data", client_details)
                if isinstance(data, dict):
                    int_account = data.get("intAccount")
                    if int_account:
                        trading_api.credentials.int_account = int_account
        except Exception as e:
            logger.warning("Failed to fetch int_account: %s", e)

    @staticmethod
    def fetch_portfolio(trading_api: TradingAPI) -> dict:
        """Fetch complete portfolio from DeGiro.

        Returns a dict with:
            - positions: list of position dicts
            - cash_available: float
            - currency: str (account base currency, typically EUR)
        """
        try:
            # Fetch update with portfolio, totalPortfolio, and cashFunds
            request_list = [
                UpdateRequest(option=UpdateOption.PORTFOLIO, last_updated=0),
                UpdateRequest(option=UpdateOption.TOTAL_PORTFOLIO, last_updated=0),
                UpdateRequest(option=UpdateOption.CASH_FUNDS, last_updated=0),
            ]
            update = trading_api.get_update.call(request_list=request_list)

            if update is None:
                raise RuntimeError("DeGiro returned empty update.")

            # The update object might be an AccountUpdate model or a raw dict
            if hasattr(update, "model_dump"):
                update_dict = update.model_dump(mode="python", by_alias=True)
            elif hasattr(update, "portfolio"):
                update_dict = {
                    "portfolio": update.portfolio,
                    "totalPortfolio": update.total_portfolio,
                    "cashFunds": update.cash_funds,
                }
            else:
                update_dict = update if isinstance(update, dict) else {}

            portfolio_data = update_dict.get("portfolio", {})
            cash_funds_data = update_dict.get("cashFunds", update_dict.get("cash_funds", {}))
            total_portfolio_data = update_dict.get("totalPortfolio", update_dict.get("total_portfolio", {}))

            # Extract positions
            positions = []
            product_ids = []
            raw_positions = []

            position_list = portfolio_data.get("value", []) if isinstance(portfolio_data, dict) else []
            if not position_list and isinstance(portfolio_data, list):
                position_list = portfolio_data

            for pos in position_list:
                if not isinstance(pos, dict):
                    continue

                # Detect and convert DeGiro key-value list format if needed
                if pos.get("name") == "positionrow" and isinstance(pos.get("value"), list):
                    flat_pos = _kv_list_to_dict(pos.get("value"))
                else:
                    flat_pos = pos

                # Skip non-product entries (like cash lines)
                position_type = flat_pos.get("positionType", flat_pos.get("position_type", "")).upper()
                if position_type and position_type not in ("PRODUCT", "STOCK", "ETF", "FUND"):
                    continue

                pid = flat_pos.get("id", flat_pos.get("productId", flat_pos.get("product_id", 0)))
                if not pid:
                    continue

                product_ids.append(int(pid))
                raw_positions.append(flat_pos)

            # Fetch product details
            products_map = {}
            if product_ids:
                try:
                    products_info = trading_api.get_products_info.call(product_list=product_ids)
                    if products_info:
                        if hasattr(products_info, "model_dump"):
                            pinfo = products_info.model_dump(mode="python", by_alias=True)
                        elif hasattr(products_info, "data"):
                            pinfo = products_info.data if hasattr(products_info.data, "__iter__") else {}
                        else:
                            pinfo = products_info if isinstance(products_info, dict) else {}

                        if isinstance(pinfo, dict):
                            products_list = pinfo.get("data", pinfo.get("products", []))
                            if isinstance(products_list, dict):
                                # Products might be a dict keyed by ID
                                for k, v in products_list.items():
                                    try:
                                        products_map[int(k)] = v if isinstance(v, dict) else v.__dict__ if hasattr(v, "__dict__") else {}
                                    except (ValueError, TypeError):
                                        pass
                            elif isinstance(products_list, list):
                                for prod in products_list:
                                    if isinstance(prod, dict):
                                        pid = prod.get("id", prod.get("productId", 0))
                                        if pid:
                                            products_map[int(pid)] = prod
                except Exception as e:
                    logger.warning("Failed to fetch product info: %s", str(e))

            # Combine position + product data
            for pos in raw_positions:
                pid = int(pos.get("id", pos.get("productId", pos.get("product_id", 0))))
                prod = products_map.get(pid, {})

                quantity = float(pos.get("size", pos.get("quantity", 0)))
                if quantity <= 0:
                    continue  # skip closed/sold positions
                current_price = float(pos.get("price", pos.get("currentPrice", 0)))
                # Always compute from price × quantity so current_value is in native
                # trading currency. DeGiro's `value` field is pre-converted to EUR
                # and must NOT be used directly — enrich_positions() applies FX once.
                if current_price > 0 and quantity > 0:
                    current_value = round(current_price * quantity, 2)
                else:
                    # Fallback only when price is absent — accept DeGiro's value as-is
                    current_value = float(pos.get("value", pos.get("currentValue", 0)))
                avg_buy_price = float(pos.get("breakEvenPrice", pos.get("break_even_price", pos.get("averagePrice", 0))))

                # plBase comes as {"EUR": -29.98} in newer DeGiro format
                pl_base = pos.get("plBase", pos.get("pl", pos.get("unrealizedPl", 0)))
                if isinstance(pl_base, dict):
                    unrealized_pl = float(pl_base.get("EUR", list(pl_base.values())[0] if pl_base else 0))
                else:
                    unrealized_pl = float(pl_base or 0)

                unrealized_pl_pct = 0.0
                if avg_buy_price > 0:
                    unrealized_pl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

                if unrealized_pl == 0 and avg_buy_price > 0:
                    unrealized_pl = (current_price - avg_buy_price) * quantity

                # Determine asset type
                product_type_raw = str(prod.get("productType", prod.get("product_type", ""))).lower()
                if "etf" in product_type_raw or prod.get("etf", False):
                    asset_type = "ETF"
                elif "stock" in product_type_raw or "share" in product_type_raw:
                    asset_type = "STOCK"
                else:
                    name = (prod.get("name") or "").upper()
                    if "ETF" in name or "UCITS" in name or "TRACK" in name:
                        asset_type = "ETF"
                    else:
                        asset_type = "STOCK"

                position = {
                    "id": str(pos.get("id", pid)),
                    "product_id": pid,
                    "name": prod.get("name", f"Product {pid}"),
                    "isin": prod.get("isin", ""),
                    "symbol": prod.get("symbol", ""),
                    "exchange_id": str(
                        prod.get("exchangeId")
                        or prod.get("exchange_id")
                        or pos.get("exchangeId")
                        or pos.get("exchange_id")
                        or ""
                    ),
                    "currency": (
                        _currency_from_exchange_id(pos.get("exchangeId", ""))
                        or prod.get("currency")
                        or prod.get("tradingCurrency")
                        or pos.get("currency")
                        or pos.get("currencyCode")
                        or _infer_currency_from_isin(prod.get("isin", ""))
                        or DeGiroClient._infer_currency_from_symbol(prod.get("symbol", pos.get("symbol", "")))
                        or "EUR"
                    ),
                    "asset_type": asset_type,
                    "quantity": quantity,
                    "avg_buy_price": round(avg_buy_price, 4),
                    "current_price": round(current_price, 4),
                    "current_value": round(current_value, 2),
                    "unrealized_pl": round(unrealized_pl, 2),
                    "unrealized_pl_pct": round(unrealized_pl_pct, 2),
                    "sector": "",
                    "country": "",
                }
                positions.append(position)

            # Extract cash available
            cash_available = 0.0
            if isinstance(cash_funds_data, dict):
                cash_list = cash_funds_data.get("value", cash_funds_data.get("cashFunds", []))
                if isinstance(cash_list, list):
                    for cash in cash_list:
                        if isinstance(cash, dict):
                            # Detect and convert DeGiro key-value list format if needed
                            if cash.get("name") == "cashFund" and isinstance(cash.get("value"), list):
                                flat_cash = _kv_list_to_dict(cash.get("value"))
                            else:
                                flat_cash = cash

                            # Find EUR cash, or use the first available
                            curr = flat_cash.get("currencyCode", flat_cash.get("currency", ""))
                            val = float(flat_cash.get("value", 0))
                            if curr == "EUR":
                                cash_available = val
                                break
                            elif cash_available == 0:
                                cash_available = val

            logger.info("Fetched %d positions from DeGiro", len(positions))
            return {
                "positions": positions,
                "cash_available": round(cash_available, 2),
                "currency": "EUR",
            }

        except Exception as e:
            logger.error("Failed to fetch portfolio: %s", str(e))
            raise RuntimeError(f"Failed to fetch portfolio: {str(e)}") from e
