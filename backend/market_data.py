"""
BiasGuard Backend — market_data.py
================================================================
Fetches Indian stock price history from Yahoo Finance and caches
it in the database so we don't re-fetch the same stock repeatedly.

Indian tickers on Yahoo Finance use suffixes:
  - NSE stocks:  TCS.NS, RELIANCE.NS, INFY.NS
  - BSE stocks:  TCS.BO
  - Nifty 50:    ^NSEI

The detection engine needs:
  - price history for each stock the user traded
  - Nifty 50 history for market context

CACHING STRATEGY:
  Price data older than 7 days is considered stable and reused.
  We only re-fetch if a ticker has no cached data or the cache
  doesn't cover the date range we need.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from database import PriceCache

NIFTY_TICKER = "^NSEI"


# ----------------------------------------------------------------
# yfinance import is deferred so the module imports even if the
# package isn't installed yet (useful for testing other parts).
# ----------------------------------------------------------------
def _yf():
    try:
        import yfinance as yf
        return yf
    except ImportError:
        raise RuntimeError(
            "yfinance not installed. Run: pip install yfinance"
        )


def normalize_ticker(ticker: str) -> str:
    """
    Ensure an Indian ticker has the right Yahoo suffix.
    'TCS' -> 'TCS.NS'  (default to NSE)
    'TCS.NS' -> 'TCS.NS'  (unchanged)
    '^NSEI' -> '^NSEI'  (index, unchanged)
    """
    ticker = ticker.strip().upper()
    if ticker.startswith("^"):
        return ticker
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return ticker
    return f"{ticker}.NS"


def _cache_covers(db: Session, ticker: str,
                  start: datetime, end: datetime) -> bool:
    """True if the cache has data spanning the requested range."""
    rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker)
        .order_by(PriceCache.price_date)
        .all()
    )
    if not rows:
        return False
    cached_min = rows[0].price_date
    cached_max = rows[-1].price_date
    # Allow a few days slack — markets are closed on weekends/holidays
    return (cached_min <= start + timedelta(days=5)
            and cached_max >= end - timedelta(days=5))


def _fetch_from_yahoo(ticker: str, start: datetime,
                      end: datetime) -> pd.DataFrame:
    """
    Download daily close prices from Yahoo Finance.

    This is written to be ROBUST across yfinance versions: different
    versions name and structure the returned columns differently
    (some use a MultiIndex, some name the date column 'Date', some
    'Datetime', some leave it as the index). So instead of assuming
    column names, we find the date and close columns by inspection.
    """
    yf = _yf()
    # Pad the range so rolling-window features have lookback room
    padded_start = start - timedelta(days=30)
    data = yf.download(
        ticker,
        start=padded_start.strftime("%Y-%m-%d"),
        end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if data is None or len(data) == 0:
        return pd.DataFrame(columns=["date", "close"])

    # --- Step 1: flatten MultiIndex columns to simple strings ---
    if isinstance(data.columns, pd.MultiIndex):
        # take the first level ('Close', 'Open', ...) — drop the ticker level
        data.columns = [
            c[0] if isinstance(c, tuple) else c
            for c in data.columns
        ]

    # --- Step 2: get the date out of the index ---
    # The date is the DataFrame index. reset_index() turns it into a
    # column whose name varies by version — so we name it ourselves.
    data = data.reset_index()
    # the first column after reset_index() is always the former index (the date)
    date_col = data.columns[0]

    # --- Step 3: find the close-price column case-insensitively ---
    close_col = None
    for c in data.columns:
        if str(c).strip().lower() == "close":
            close_col = c
            break
    if close_col is None:
        # no close column at all — return empty, caller handles it
        return pd.DataFrame(columns=["date", "close"])

    # --- Step 4: build the clean [date, close] frame ---
    out = pd.DataFrame({
        "date": pd.to_datetime(data[date_col]),
        "close": pd.to_numeric(data[close_col], errors="coerce"),
    })
    out = out.dropna(subset=["close"]).reset_index(drop=True)
    return out


def _store_in_cache(db: Session, ticker: str, df: pd.DataFrame):
    """Insert fetched prices into the cache, skipping duplicates."""
    existing = {
        (r.ticker, r.price_date.date())
        for r in db.query(PriceCache).filter(PriceCache.ticker == ticker).all()
    }
    new_rows = []
    for row in df.itertuples(index=False):
        key = (ticker, row.date.date())
        if key in existing:
            continue
        new_rows.append(PriceCache(
            ticker=ticker,
            price_date=row.date.to_pydatetime(),
            close=float(row.close),
        ))
    if new_rows:
        db.bulk_save_objects(new_rows)
        db.commit()


def get_price_history(db: Session, ticker: str,
                      start: datetime, end: datetime) -> pd.DataFrame:
    """
    Return [date, close] for a ticker over [start, end].
    Uses the DB cache; fetches from Yahoo only if needed.
    """
    ticker = normalize_ticker(ticker)

    if not _cache_covers(db, ticker, start, end):
        fetched = _fetch_from_yahoo(ticker, start, end)
        if len(fetched) > 0:
            _store_in_cache(db, ticker, fetched)

    rows = (
        db.query(PriceCache)
        .filter(PriceCache.ticker == ticker)
        .order_by(PriceCache.price_date)
        .all()
    )
    df = pd.DataFrame(
        [{"date": r.price_date, "close": r.close} for r in rows]
    )
    return df


def get_prices_for_tickers(db: Session, tickers: list,
                           start: datetime, end: datetime) -> pd.DataFrame:
    """
    Fetch price history for multiple tickers, returned in the shape
    the bias engine expects: [ticker, date, close].
    """
    frames = []
    for t in set(tickers):
        norm = normalize_ticker(t)
        hist = get_price_history(db, norm, start, end)
        if len(hist) > 0:
            hist = hist.copy()
            hist["ticker"] = norm
            frames.append(hist[["ticker", "date", "close"]])
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "close"])
    return pd.concat(frames, ignore_index=True)


def get_nifty_history(db: Session, start: datetime,
                      end: datetime) -> pd.DataFrame:
    """Fetch Nifty 50 index history for market context."""
    return get_price_history(db, NIFTY_TICKER, start, end)
