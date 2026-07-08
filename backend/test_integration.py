"""
Integration test for the BiasGuard backend.

Tests the full flow: signup -> login -> log trades -> analyze -> report.

Market data is MOCKED — the sandbox has no internet, and we don't
want the test to depend on live Yahoo Finance anyway. We inject
synthetic price history with a known crash so we can verify the
detection actually fires through the API layer.
"""

import sys
from datetime import datetime, timedelta

import pandas as pd

# Patch market_data BEFORE importing main, so main picks up the mocks
import market_data


def _mock_prices(db, tickers, start, end):
    """Synthetic price history with a crash, for all requested tickers."""
    days = pd.bdate_range("2024-01-01", periods=120)
    frames = []
    for t in set(tickers):
        norm = market_data.normalize_ticker(t)
        prices = []
        p = 100.0
        for i in range(120):
            # Inject a crash between day 40 and 45
            if 40 <= i <= 45:
                p *= 0.96
            else:
                p *= 1.002
            prices.append(p)
        for d, pr in zip(days, prices):
            frames.append({"ticker": norm, "date": d, "close": pr})
    return pd.DataFrame(frames)


def _mock_nifty(db, start, end):
    """Synthetic Nifty history — also crashes day 40-45 (market-wide)."""
    days = pd.bdate_range("2024-01-01", periods=120)
    rows = []
    p = 22000.0
    for i in range(120):
        if 40 <= i <= 45:
            p *= 0.97
        else:
            p *= 1.001
        rows.append({"date": days[i], "close": p})
    return pd.DataFrame(rows)


# Apply the mocks
market_data.get_prices_for_tickers = _mock_prices
market_data.get_nifty_history = _mock_nifty

# Now import the app
from fastapi.testclient import TestClient
from database import init_db, DB_PATH
import main

# Fresh database
if DB_PATH.exists():
    DB_PATH.unlink()
init_db()

client = TestClient(main.app)

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


print("=" * 60)
print("BiasGuard Backend — Integration Test")
print("=" * 60)

# ---- 1. Signup ----
print("\n[1] Signup")
r = client.post("/signup", json={
    "email": "rudra@test.com", "password": "testpass123"})
check("signup returns 200", r.status_code == 200, f"got {r.status_code}")
token = r.json().get("access_token")
check("signup returns a token", token is not None)
headers = {"Authorization": f"Bearer {token}"}

# ---- 2. Duplicate signup rejected ----
r = client.post("/signup", json={
    "email": "rudra@test.com", "password": "testpass123"})
check("duplicate signup rejected", r.status_code == 400)

# ---- 3. Short password rejected ----
r = client.post("/signup", json={
    "email": "x@test.com", "password": "short"})
check("short password rejected", r.status_code == 400)

# ---- 4. Login ----
print("\n[2] Login")
r = client.post("/login", data={
    "username": "rudra@test.com", "password": "testpass123"})
check("login returns 200", r.status_code == 200, f"got {r.status_code}")
check("login returns a token", r.json().get("access_token") is not None)

r = client.post("/login", data={
    "username": "rudra@test.com", "password": "wrongpass"})
check("wrong password rejected", r.status_code == 401)

# ---- 5. /me ----
print("\n[3] Protected route /me")
r = client.get("/me", headers=headers)
check("/me works with token", r.status_code == 200)
check("/me returns correct email",
      r.json().get("email") == "rudra@test.com")

r = client.get("/me")
check("/me rejects no token", r.status_code == 401)

# ---- 6. Log trades ----
print("\n[4] Logging trades")
# Build a trade history with a panic sell:
# buy TCS, then sell it during the crash window (day 40-45)
days = pd.bdate_range("2024-01-01", periods=120)

trades_to_log = []
# 8 routine trades
for i in range(8):
    trades_to_log.append({
        "ticker": "INFY", "action": "Buy" if i % 2 == 0 else "Sell",
        "quantity": 10, "price": 100 + i,
        "trade_date": days[i * 2].strftime("%Y-%m-%d"),
    })
# A buy just before the crash
trades_to_log.append({
    "ticker": "TCS", "action": "Buy", "quantity": 100, "price": 100,
    "trade_date": days[38].strftime("%Y-%m-%d"),
})
# A panic sell during the crash
trades_to_log.append({
    "ticker": "TCS", "action": "Sell", "quantity": 100, "price": 85,
    "trade_date": days[44].strftime("%Y-%m-%d"),
})

logged_ids = []
for t in trades_to_log:
    r = client.post("/trades", json=t, headers=headers)
    if r.status_code == 200:
        logged_ids.append(r.json()["id"])
check("all 10 trades logged", len(logged_ids) == 10,
      f"logged {len(logged_ids)}")

# ---- 7. List trades ----
r = client.get("/trades", headers=headers)
check("list trades returns 10", len(r.json()) == 10,
      f"got {len(r.json())}")

# ---- 8. Invalid trade rejected ----
r = client.post("/trades", json={
    "ticker": "TCS", "action": "Hold", "quantity": 10,
    "price": 100, "trade_date": "2024-01-01"}, headers=headers)
check("invalid action rejected", r.status_code == 400)

r = client.post("/trades", json={
    "ticker": "TCS", "action": "Buy", "quantity": -5,
    "price": 100, "trade_date": "2024-01-01"}, headers=headers)
check("negative quantity rejected", r.status_code == 400)

# ---- 9. Analyze ----
print("\n[5] Running analysis")
r = client.post("/analyze", headers=headers)
check("analyze returns 200", r.status_code == 200,
      f"got {r.status_code}: {r.text[:200]}")
if r.status_code == 200:
    result = r.json()
    check("result has panic section", "panic" in result)
    check("result has fomo section", "fomo" in result)
    check("result has overtrading section", "overtrading" in result)
    # The TCS panic sell should be flagged
    panic_count = result["panic"]["flagged_count"]
    check("panic sell was detected", panic_count >= 1,
          f"flagged {panic_count}")
    print(f"       -> panic flagged: {panic_count}")
    print(f"       -> fomo flagged:  {result['fomo']['flagged_count']}")
    print(f"       -> overtrading:   {result['overtrading']['flagged_weeks']}")

# ---- 10. Report ----
print("\n[6] Fetching report")
r = client.get("/report", headers=headers)
check("report returns 200", r.status_code == 200)
check("report has panic_rate", "panic_rate" in r.json())

# ---- 11. Analyze with too few trades ----
print("\n[7] Edge case: too few trades")
client.post("/signup", json={
    "email": "newbie@test.com", "password": "testpass123"})
r2 = client.post("/login", data={
    "username": "newbie@test.com", "password": "testpass123"})
h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
client.post("/trades", json={
    "ticker": "TCS", "action": "Buy", "quantity": 10, "price": 100,
    "trade_date": "2024-01-01"}, headers=h2)
r = client.post("/analyze", headers=h2)
check("analyze rejects <10 trades", r.status_code == 400)

# ---- 12. Delete trade ----
print("\n[8] Deleting a trade")
r = client.delete(f"/trades/{logged_ids[0]}", headers=headers)
check("delete trade works", r.status_code == 200)
r = client.get("/trades", headers=headers)
check("trade count dropped to 9", len(r.json()) == 9)

# ---- Summary ----
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {FAIL} failed")
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
