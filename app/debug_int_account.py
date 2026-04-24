"""Find where intAccount lives in client_details response."""
import json
import sys
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials

session_id = sys.argv[1] if len(sys.argv) > 1 else input("Session ID: ").strip()

credentials = Credentials.model_construct(username="x", password="x")
trading_api = TradingAPI(credentials=credentials)
trading_api.connection_storage.session_id = session_id

client_details = trading_api.get_client_details.call()
print("Type:", type(client_details))

if isinstance(client_details, dict):
    # Search recursively for any key containing 'intAccount' or 'int_account'
    def find_keys(obj, prefix=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "int" in str(k).lower() and "account" in str(k).lower():
                    found.append((prefix + k, v))
                if isinstance(v, (dict, list)):
                    found.extend(find_keys(v, prefix + k + "."))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(find_keys(v, prefix + f"[{i}]."))
        return found

    matches = find_keys(client_details)
    if matches:
        print("Found intAccount keys:")
        for path, val in matches:
            print(f"  {path}: {val}")
    else:
        print("No intAccount found. Top-level keys:", list(client_details.keys()))
else:
    print("Not a dict. Dumping:")
    print(json.dumps(client_details, indent=2, default=str)[:2000])
