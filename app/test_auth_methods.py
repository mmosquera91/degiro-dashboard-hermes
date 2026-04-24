"""Test script to compare one_time_password vs totp_secret_key login.

Run this INSIDE the brokr container with your real credentials:
    docker compose exec brokr python app/test_auth_methods.py

The script will prompt for credentials interactively (password is hidden).
"""
import getpass
import sys

from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.core.exceptions import DeGiroConnectionError


def try_login(credentials: Credentials, label: str) -> bool:
    """Attempt login and return True if successful."""
    trading_api = TradingAPI(credentials=credentials)
    try:
        session_id = trading_api.connect.call()
        print(f"  [{label}] SUCCESS! session_id: {session_id[:15]}...")
        return True
    except DeGiroConnectionError as exc:
        login_error = getattr(exc, "login_error", None)
        if login_error:
            err = login_error.model_dump(mode="python", by_alias=True, exclude_none=True)
            print(f"  [{label}] FAILED: {err}")
        else:
            print(f"  [{label}] FAILED: {exc}")
        return False
    except Exception as exc:
        print(f"  [{label}] FAILED with exception: {type(exc).__name__}: {exc}")
        return False


def main():
    print("=" * 60)
    print("DeGiro Login Test — comparing OTP methods")
    print("=" * 60)
    print()
    print("Your credentials are ONLY used for this test and are NOT stored.")
    print()

    username = input("Username (email): ").strip().lower()
    if not username:
        print("Username required.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("Password required.")
        sys.exit(1)

    otp_manual = input("One-time password (6 digits, leave empty if using secret key): ").strip() or None
    totp_secret = input("TOTP secret key (leave empty if not using): ").strip() or None

    if not otp_manual and not totp_secret:
        print("\nYou must provide either a one-time password OR a TOTP secret key.")
        sys.exit(1)

    print()
    print("Testing login methods...")
    print("-" * 60)

    results = []

    # Method 1: one_time_password (manual OTP)
    if otp_manual:
        print("\n[1] Testing with one_time_password (manual OTP)...")
        creds1 = Credentials.model_construct(
            username=username,
            password=password,
            one_time_password=str(otp_manual),
        )
        ok1 = try_login(creds1, "one_time_password")
        results.append(("one_time_password", ok1))

    # Method 2: totp_secret_key
    if totp_secret:
        print("\n[2] Testing with totp_secret_key...")
        creds2 = Credentials.model_construct(
            username=username,
            password=password,
            totp_secret_key=totp_secret,
        )
        ok2 = try_login(creds2, "totp_secret_key")
        results.append(("totp_secret_key", ok2))

    print()
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for method, ok in results:
        status = "✅ SUCCESS" if ok else "❌ FAILED"
        print(f"  {method}: {status}")
    print()

    success_methods = [m for m, ok in results if ok]
    if success_methods:
        print(f"Working method(s): {', '.join(success_methods)}")
        print("Use this method in brokr.")
    else:
        print("Both methods failed. Check credentials / OTP timing / account status.")


if __name__ == "__main__":
    main()
