"""Test from_session_id to see if get_client_details works."""
import sys
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials

session_id = sys.argv[1] if len(sys.argv) > 1 else input("Session ID: ").strip()

print("Creating TradingAPI with dummy credentials...")
credentials = Credentials.model_construct(username="x", password="x")
trading_api = TradingAPI(credentials=credentials)
trading_api.connection_storage.session_id = session_id

print(f"Session ID set: {trading_api.connection_storage.session_id[:20]}...")

print("\nCalling get_client_details...")
try:
    client_details = trading_api.get_client_details.call()
    print(f"Success! Type: {type(client_details)}")
    if isinstance(client_details, dict):
        print(f"Keys: {list(client_details.keys())}")
        data = client_details.get("data", {})
        print(f"data.intAccount: {data.get('intAccount')}")
    else:
        print(f"Has model_dump: {hasattr(client_details, 'model_dump')}")
        if hasattr(client_details, 'model_dump'):
            d = client_details.model_dump(mode="python")
            print(f"Dump keys: {list(d.keys())}")
except Exception as e:
    import traceback
    print(f"FAILED: {e}")
    traceback.print_exc()
