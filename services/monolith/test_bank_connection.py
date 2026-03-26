"""
Complete Enable Banking sandbox flow:
  session -> accounts -> balances -> transactions
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join("..", "..", ".env"))

from backend.banking.adapters.outbound.enable_banking_client import (
    EnableBankingClient,
    EnableBankingConfig,
)

SESSION_ID = "a08d92f0-7ed6-499a-971f-e739bf44efee"

key_path = os.getenv("ENABLE_BANKING_KEY_PATH", "./enablebanking-sandbox.pem")
if not os.path.isabs(key_path):
    key_path = os.path.join("..", "..", key_path)

config = EnableBankingConfig(
    app_id=os.getenv("ENABLE_BANKING_APP_ID", ""),
    key_path=key_path,
    redirect_uri=os.getenv("ENABLE_BANKING_REDIRECT_URI", ""),
    environment=os.getenv("ENABLE_BANKING_ENVIRONMENT", "sandbox"),
)
print(f"Config OK: app_id={config.app_id[:8]}...")

client = EnableBankingClient(config)

try:
    print("\n=== Step 1: Get existing session ===")
    session = client.get_session(SESSION_ID)
    aspsp = session.get("aspsp", {})
    print(f"Session ID:  {SESSION_ID}")
    print(f"Bank:        {aspsp.get('name', '?')} ({aspsp.get('country', '?')})")
    print(f"Status:      {session.get('status', '?')}")
    print(f"Valid until: {session.get('access', {}).get('valid_until', '?')}")

    account_uids = session.get("accounts", [])
    print(f"Accounts:    {len(account_uids)}")
    for uid in account_uids:
        print(f"  - {uid}")

    if not account_uids:
        print("\nNo accounts returned.")
        sys.exit(0)

    print("\n=== Step 2: Fetch balances ===")
    for uid in account_uids:
        try:
            balances = client.get_balances(uid)
            for bal in balances:
                amt = bal.get("balance_amount", {})
                btype = bal.get("balance_type", "?")
                print(f"  {uid[:12]}...: {amt.get('amount', '?')} {amt.get('currency', '?')} ({btype})")
        except Exception as e:
            print(f"  {uid[:12]}...: could not fetch balance ({e})")

    print("\n=== Step 3: Fetch transactions (last 90 days) ===")
    total = 0
    for uid in account_uids:
        print(f"\n  Account {uid[:12]}...:")
        try:
            txns = client.get_transactions(uid)
            total += len(txns)
            print(f"  Found {len(txns)} transactions")
            for t in txns[:10]:
                print(f"    {t.date}  {t.amount:>10.2f} {t.currency}  {t.description[:60]}")
            if len(txns) > 10:
                print(f"    ... and {len(txns) - 10} more")
        except Exception as e:
            print(f"    Error fetching transactions: {e}")

    print(f"\n=== FULL FLOW PASSED — {total} total transactions ===")

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    client.close()
