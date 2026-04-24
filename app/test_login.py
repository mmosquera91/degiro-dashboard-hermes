"""Script mínimo para probar login con degiro-connector directamente."""
import sys
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.core.exceptions import DeGiroConnectionError

if len(sys.argv) < 3:
    print("Usage: python test_login.py <username> <password> [otp]")
    sys.exit(1)

username = sys.argv[1].lower().strip()
password = sys.argv[2]
otp = sys.argv[3] if len(sys.argv) > 3 else None

print(f"Username: {username[:3]}***")
print(f"OTP provided: {bool(otp)}")

creds_data = {"username": username, "password": password}
if otp:
    creds_data["one_time_password"] = str(otp)

credentials = Credentials.model_construct(**creds_data)
trading_api = TradingAPI(credentials=credentials)

try:
    session_id = trading_api.connect.call()
    print(f"SUCCESS! session_id: {session_id[:10]}...")
except DeGiroConnectionError as exc:
    print(f"DeGiroConnectionError: {exc}")
    login_error = getattr(exc, "login_error", None)
    if login_error:
        print(f"Login error details: {login_error.model_dump(mode='python', by_alias=True)}")
except Exception as exc:
    print(f"Exception: {type(exc).__name__}: {exc}")
