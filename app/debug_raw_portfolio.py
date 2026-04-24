"""Dump raw portfolio data without numeric parsing to find the list field."""
import json
import sys
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.account import UpdateRequest, UpdateOption

session_id = sys.argv[1] if len(sys.argv) > 1 else input("Session ID: ").strip()
int_account = int(sys.argv[2]) if len(sys.argv) > 2 else int(input("int_account: ").strip())

credentials = Credentials.model_construct(username="x", password="x", int_account=int_account)
trading_api = TradingAPI(credentials=credentials)
trading_api.connection_storage.session_id = session_id

print("Fetching raw update...")
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

portfolio_data = update_dict.get("portfolio", {})
position_list = portfolio_data.get("value", []) if isinstance(portfolio_data, dict) else portfolio_data

print(f"\nNumber of positions: {len(position_list)}")

if position_list:
    for i, pos in enumerate(position_list[:3]):
        print(f"\n--- Position {i} (raw) ---")
        print(json.dumps(pos, indent=2, default=str))
        # Show types of potentially problematic fields
        for k, v in pos.items():
            if isinstance(v, list):
                print(f"  >>> LIST FIELD: {k} = {v}")

# Also check cash funds
cash_data = update_dict.get("cashFunds", update_dict.get("cash_funds", {}))
print(f"\n--- Cash Funds (raw) ---")
print(json.dumps(cash_data, indent=2, default=str)[:2000])
