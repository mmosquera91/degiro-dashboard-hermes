"""Debug script to inspect raw DeGiro portfolio response structure.

Run inside the brokr container with an active session:
    docker compose exec brokr python app/debug_portfolio.py <session_id>
"""
import json
import sys
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.account import UpdateRequest, UpdateOption

session_id = sys.argv[1] if len(sys.argv) > 1 else input("Session ID: ").strip()

credentials = Credentials.model_construct(username="x", password="x")
trading_api = TradingAPI(credentials=credentials)
trading_api.connection_storage.session_id = session_id

# Fetch int_account
print("=== CLIENT DETAILS ===")
try:
    client_details = trading_api.get_client_details.call()
    print(json.dumps(client_details, indent=2, default=str)[:3000])
except Exception as e:
    print(f"ERROR: {e}")

# Fetch raw update
print("\n=== PORTFOLIO UPDATE (RAW) ===")
try:
    request_list = [
        UpdateRequest(option=UpdateOption.PORTFOLIO, last_updated=0),
        UpdateRequest(option=UpdateOption.TOTAL_PORTFOLIO, last_updated=0),
        UpdateRequest(option=UpdateOption.CASH_FUNDS, last_updated=0),
    ]
    update = trading_api.get_update.call(request_list=request_list)

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

    # Print first 5000 chars to avoid flooding
    print(json.dumps(update_dict, indent=2, default=str)[:5000])

    # Show portfolio structure specifically
    portfolio_data = update_dict.get("portfolio", {})
    print("\n=== PORTFOLIO STRUCTURE ===")
    print(f"Type: {type(portfolio_data)}")
    if isinstance(portfolio_data, dict):
        print(f"Keys: {list(portfolio_data.keys())}")
        values = portfolio_data.get("value", [])
        print(f"Number of positions: {len(values)}")
        if values:
            print("\n--- First position (full) ---")
            print(json.dumps(values[0], indent=2, default=str))
            print("\n--- Second position (full) ---")
            if len(values) > 1:
                print(json.dumps(values[1], indent=2, default=str))
    elif isinstance(portfolio_data, list):
        print(f"Number of positions: {len(portfolio_data)}")
        if portfolio_data:
            print("\n--- First position (full) ---")
            print(json.dumps(portfolio_data[0], indent=2, default=str))

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
