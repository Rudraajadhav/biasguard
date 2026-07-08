"""
test_yfinance_india.py - BiasGuard live-data diagnostic (Open Problem #1)

Answers ONE question: does yfinance return usable price data for the Indian
NSE tickers + Nifty in THIS environment, right now?

No DB, no FastAPI, no React. Pure yfinance round-trip plus the exact
nearest-trading-day lookup the detection engine depends on.

Run with your backend venv active:
    python test_yfinance_india.py
"""

import sys
import time
from datetime import datetime, timedelta

try:
    import yfinance as yf
    import pandas as pd
except ImportError as e:
    print(f"FATAL: missing dependency: {e}")
    print("Run: pip install -U yfinance pandas")
    sys.exit(1)

print(f"yfinance {yf.__version__} | pandas {pd.__version__}\n")

# Exact tickers from the handoff. NSE stocks REQUIRE the .NS suffix.
STOCKS = ["TCS.NS", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "WIPRO.NS", "SBIN.NS"]
INDEX = "^NSEI"  # Nifty 50 - the market-context index
ALL = STOCKS + [INDEX]

END = datetime.today()
START = END - timedelta(days=730)  # ~2y, matches expected trade dates


def fetch(ticker):
    """Fetch one ticker, normalising column shape across yfinance versions."""
    df = yf.download(
        ticker,
        start=START.strftime("%Y-%m-%d"),
        end=END.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,  # be explicit: default flipped to True in recent versions
        threads=False,     # single-threaded -> fewer rate-limit trips
    )
    # yf.download can return MultiIndex columns even for a single ticker.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def price_on_or_before(df, target):
    """Nearest close at/just before target. This is what the engine needs when a
    trade lands on a weekend/holiday with no matching price row."""
    if df.empty or "Close" not in df.columns:
        return None
    if getattr(df.index, "tz", None) is not None:  # kill tz-vs-naive comparison errors
        df = df.copy()
        df.index = df.index.tz_localize(None)
    sub = df.loc[: pd.Timestamp(target)]
    return None if sub.empty else float(sub["Close"].iloc[-1])


def classify_error(err):
    s = str(err).lower()
    if "too many requests" in s or "rate limit" in s or "429" in s:
        return "RATE_LIMIT"
    if "delisted" in s or "no price data" in s or "no timezone" in s:
        return "YF_BUG_OR_BAD_TICKER"
    return "OTHER"


results, errors = {}, {}
for t in ALL:
    print(f"--- {t} ---")
    try:
        df = fetch(t)
        if df.empty:
            print("  EMPTY frame (bad ticker, rate-limit, or no data in range)")
            results[t], errors[t] = False, "EMPTY"
        else:
            first, last = df.index.min().date(), df.index.max().date()
            probe = END - timedelta(days=200)
            p = price_on_or_before(df, probe)
            print(f"  rows={len(df)}  range={first}..{last}  "
                  f"last_close={float(df['Close'].iloc[-1]):.2f}")
            print(f"  columns={list(df.columns)}  tz={getattr(df.index, 'tz', None)}")
            print(f"  nearest close on/before {probe.date()}: {p}")
            results[t] = True
    except Exception as e:
        kind = classify_error(e)
        print(f"  ERROR [{kind}]: {type(e).__name__}: {e}")
        results[t], errors[t] = False, kind
    time.sleep(1.0)  # gentle spacing - don't self-inflict a rate limit
    print()

ok = sum(results.values())
rate_limited = any(v == "RATE_LIMIT" or v == "EMPTY" for v in errors.values())
print("=" * 56)
print(f"VERDICT: {ok}/{len(ALL)} tickers fetched")
if ok == len(ALL):
    print("PASS - the live fetch works here. Any /analyze failure is NOT in")
    print("       raw fetching. Confirm market_data.py uses .NS + the column/tz")
    print("       handling above, then the bug is downstream (engine or report).")
elif ok == 0 and rate_limited:
    print("BLOCKED - looks like rate-limiting/empty frames, not your ticker logic.")
    print("          Wait a few minutes, or switch network, then re-run. This is")
    print("          the same risk you'll hit on a cloud deploy (Problem #7).")
else:
    print("PARTIAL - the failing tickers above pinpoint where market_data.py breaks.")
    print("          If failures are YF_BUG_OR_BAD_TICKER on known-good names like")
    print("          RELIANCE.NS, that's the known yfinance<->Yahoo issue: `pip install")
    print("          -U yfinance` and retry before assuming your code is wrong.")
