"""
BiasGuard Backend — bias_engine.py
================================================================
The validated bias detection logic, adapted to run on ONE user's
trades (instead of the full FAR-Trans dataset).

This module is the single source of truth for detection. The
thresholds here are IDENTICAL to the validated detect_biases.py
research script. Do not change them without re-validating.

Detectors:
  - detect_panic_selling
  - detect_fomo_buying
  - detect_overtrading

Each takes a user's enriched trade DataFrame and returns flagged
trades + confidence scores.
"""

import numpy as np
import pandas as pd

# ================================================================
# CONFIG — identical to the validated research script
# ================================================================

# --- Panic Selling ---
PANIC_MAX_HOLDING_DAYS = 30
PANIC_STOCK_DROP_PCT = -5.0
PANIC_LOOKBACK_TRADING_DAYS = 3
PANIC_MARKET_NEG_THRESHOLD = 0.0
PANIC_MIN_SELL_FRACTION = 0.50

# --- FOMO Buying ---
FOMO_STOCK_RISE_PCT = 20.0
FOMO_LOOKBACK_TRADING_DAYS = 7
FOMO_MIN_TRADE_SIZE_MULTIPLIER = 2.0

# --- Overtrading ---
OT_MIN_WEEKLY_TRADES = 7
OT_CHURN_RATIO_THRESHOLD = 0.4
OT_MIN_POSITIONS_FOR_CHURN = 15


# ================================================================
# FEATURE ENGINEERING
# ================================================================
def compute_price_features(prices: pd.DataFrame) -> pd.DataFrame:
    """
    prices: DataFrame with columns [ticker, date, close]
    Returns the same frame with return_1d, return_3d, return_7d added.
    """
    prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
    prices["return_1d"] = prices.groupby("ticker")["close"].pct_change(1) * 100
    prices["return_3d"] = prices.groupby("ticker")["close"].pct_change(3) * 100
    prices["return_7d"] = prices.groupby("ticker")["close"].pct_change(7) * 100
    return prices


def compute_market_context(nifty: pd.DataFrame) -> pd.DataFrame:
    """
    nifty: DataFrame with columns [date, close] for the Nifty 50 index.
    Returns [date, market_avg_return, market_avg_3d].

    For Indian deployment we use the real Nifty 50 index as market
    context — better than the synthetic average used on FAR-Trans.
    """
    nifty = nifty.sort_values("date").reset_index(drop=True)
    nifty["market_avg_return"] = nifty["close"].pct_change(1) * 100
    nifty["market_avg_3d"] = nifty["market_avg_return"].rolling(3).mean()
    return nifty[["date", "market_avg_return", "market_avg_3d"]]


def build_investor_profile(trades: pd.DataFrame) -> dict:
    """Per-user summary stats needed by the detectors."""
    buys = trades[trades["action"] == "Buy"]
    sells = trades[trades["action"] == "Sell"]
    return {
        "n_trades": len(trades),
        "n_buys": len(buys),
        "n_sells": len(sells),
        "median_buy_value": buys["value"].median() if len(buys) else 0.0,
        "median_sell_value": sells["value"].median() if len(sells) else 0.0,
        "first_trade_date": trades["date"].min() if len(trades) else None,
        "last_trade_date": trades["date"].max() if len(trades) else None,
    }


def match_buys_to_sells(trades: pd.DataFrame) -> pd.DataFrame:
    """
    FIFO matching of sells to prior buys, per ticker.
    Adds: matched_buy_date, holding_days, sold_fraction_of_position.

    Identical logic to the validated research script.
    """
    trades = trades.sort_values(["ticker", "date"]).reset_index(drop=True)

    matched_buy_date = []
    holding_days = []
    sold_fraction = []

    current_ticker = None
    queue = []           # list of [buy_date, units_remaining]
    position_units = 0

    for row in trades.itertuples(index=False):
        if row.ticker != current_ticker:
            current_ticker = row.ticker
            queue = []
            position_units = 0

        if row.action == "Buy":
            queue.append([row.date, row.quantity])
            position_units += row.quantity
            matched_buy_date.append(pd.NaT)
            holding_days.append(np.nan)
            sold_fraction.append(np.nan)
        else:  # Sell
            if not queue or position_units <= 0:
                matched_buy_date.append(pd.NaT)
                holding_days.append(np.nan)
                sold_fraction.append(np.nan)
                position_units = max(0, position_units - row.quantity)
            else:
                earliest_buy_date = queue[0][0]
                matched_buy_date.append(earliest_buy_date)
                holding_days.append((row.date - earliest_buy_date).days)
                sold_fraction.append(min(1.0, row.quantity / position_units))

                units_to_remove = row.quantity
                while units_to_remove > 0 and queue:
                    if queue[0][1] <= units_to_remove:
                        units_to_remove -= queue[0][1]
                        queue.pop(0)
                    else:
                        queue[0][1] -= units_to_remove
                        units_to_remove = 0
                position_units = max(0, position_units - row.quantity)

    trades["matched_buy_date"] = matched_buy_date
    trades["holding_days"] = holding_days
    trades["sold_fraction_of_position"] = sold_fraction
    return trades


def enrich_trades(trades: pd.DataFrame, prices: pd.DataFrame,
                  nifty: pd.DataFrame) -> pd.DataFrame:
    """
    Combine trades with price features and market context.

    trades:  [ticker, action, quantity, price, value, date]
    prices:  [ticker, date, close]  (price history for the user's tickers)
    nifty:   [date, close]          (Nifty 50 index history)

    Returns trades enriched with everything the detectors need.

    IMPORTANT — date matching:
    A trade date may not land exactly on a price bar (weekends, market
    holidays, or a bar simply missing from the data feed). So instead
    of an exact-date join, we use merge_asof, which matches each trade
    to the most recent trading day ON OR BEFORE the trade date. This is
    the correct financial behaviour: a Saturday sell uses Friday's data.
    """
    prices_feat = compute_price_features(prices)
    market = compute_market_context(nifty)

    trades = match_buys_to_sells(trades)

    # Normalise all date columns to tz-naive midnight so the joins are
    # robust regardless of how yfinance returned the timestamps.
    def _norm(df, col):
        df = df.copy()
        s = pd.to_datetime(df[col])
        if getattr(s.dt, "tz", None) is not None:
            s = s.dt.tz_localize(None)
        df[col] = s.dt.normalize()
        return df

    trades = _norm(trades, "date")
    prices_feat = _norm(prices_feat, "date")
    market = _norm(market, "date")

    # --- Attach per-stock return features (as-of join, per ticker) ---
    # merge_asof needs both sides sorted by the join key.
    trades = trades.sort_values("date").reset_index(drop=True)
    prices_feat = prices_feat.sort_values("date").reset_index(drop=True)

    trades = pd.merge_asof(
        trades,
        prices_feat[["ticker", "date", "return_3d", "return_7d"]],
        on="date", by="ticker", direction="backward",
    )

    # --- Attach market context (as-of join on date) ---
    market = market.sort_values("date").reset_index(drop=True)
    trades = pd.merge_asof(
        trades,
        market[["date", "market_avg_return", "market_avg_3d"]],
        on="date", direction="backward",
    )

    return trades


# ================================================================
# DETECTOR 1: Panic Selling
# ================================================================
def detect_panic_selling(enriched: pd.DataFrame) -> pd.DataFrame:
    sells = enriched[enriched["action"] == "Sell"].copy()
    if len(sells) == 0:
        sells["panic_flag"] = []
        sells["panic_confidence"] = []
        return sells

    cond_holding = sells["holding_days"] < PANIC_MAX_HOLDING_DAYS
    cond_drop = sells["return_3d"] <= PANIC_STOCK_DROP_PCT
    cond_market = sells["market_avg_3d"] <= PANIC_MARKET_NEG_THRESHOLD
    cond_fraction = sells["sold_fraction_of_position"] >= PANIC_MIN_SELL_FRACTION

    sells["panic_flag"] = (
        cond_holding & cond_drop & cond_market & cond_fraction
    ).fillna(False)

    drop_score = np.clip(-sells["return_3d"] * 5, 0, 100)
    holding_score = np.clip(
        (PANIC_MAX_HOLDING_DAYS - sells["holding_days"])
        / PANIC_MAX_HOLDING_DAYS * 100, 0, 100,
    )
    fraction_score = sells["sold_fraction_of_position"].fillna(0) * 100

    sells["panic_confidence"] = np.where(
        sells["panic_flag"],
        (drop_score * 0.5 + holding_score * 0.3
         + fraction_score * 0.2).clip(0, 100),
        0.0,
    )
    return sells


# ================================================================
# DETECTOR 2: FOMO Buying
# ================================================================
def detect_fomo_buying(enriched: pd.DataFrame, profile: dict) -> pd.DataFrame:
    buys = enriched[enriched["action"] == "Buy"].copy()
    if len(buys) == 0:
        buys["fomo_flag"] = []
        buys["fomo_confidence"] = []
        buys["size_multiplier"] = []
        return buys

    median_buy = profile.get("median_buy_value", 0) or 0

    cond_runup = buys["return_7d"] >= FOMO_STOCK_RISE_PCT
    size_multiplier = np.where(
        median_buy > 0, buys["value"] / median_buy, 0,
    )
    cond_size = size_multiplier >= FOMO_MIN_TRADE_SIZE_MULTIPLIER

    buys["fomo_flag"] = (cond_runup & cond_size).fillna(False)
    buys["size_multiplier"] = size_multiplier

    runup_score = np.clip(buys["return_7d"] * 2, 0, 100)
    size_score = np.clip((size_multiplier - 1.0) * 20, 0, 100)

    buys["fomo_confidence"] = np.where(
        buys["fomo_flag"],
        (runup_score * 0.5 + size_score * 0.5).clip(0, 100),
        0.0,
    )
    return buys


# ================================================================
# DETECTOR 3: Overtrading (weekly)
# ================================================================
def detect_overtrading(enriched: pd.DataFrame) -> pd.DataFrame:
    tx = enriched.copy()
    if len(tx) == 0:
        return pd.DataFrame(columns=["week", "weekly_trades", "weekly_sells",
                                     "churn_ratio", "overtrading_flag",
                                     "overtrading_confidence"])

    tx["week"] = tx["date"].dt.to_period("W")

    weekly = (
        tx.groupby("week")
        .agg(
            weekly_trades=("date", "count"),
            weekly_sells=("action", lambda s: (s == "Sell").sum()),
            weekly_buys=("action", lambda s: (s == "Buy").sum()),
        )
        .reset_index()
    )

    # Cumulative unique tickers as a position-count proxy
    tx_sorted = tx.sort_values("date")
    tx_sorted["ticker_seen_before"] = (
        tx_sorted.groupby("ticker").cumcount() > 0
    )
    tx_sorted["cum_unique_tickers"] = (~tx_sorted["ticker_seen_before"]).cumsum()
    weekly_positions = (
        tx_sorted.groupby(tx_sorted["date"].dt.to_period("W"))
        ["cum_unique_tickers"].max()
        .reset_index()
        .rename(columns={"date": "week", "cum_unique_tickers": "positions_proxy"})
    )
    weekly = weekly.merge(weekly_positions, on="week", how="left")

    weekly["churn_ratio"] = np.where(
        weekly["positions_proxy"] > 0,
        np.clip(weekly["weekly_sells"] / weekly["positions_proxy"], 0, 1),
        0,
    )

    weekly["overtrading_flag"] = (
        (weekly["weekly_trades"] >= OT_MIN_WEEKLY_TRADES)
        | (
            (weekly["churn_ratio"] >= OT_CHURN_RATIO_THRESHOLD)
            & (weekly["positions_proxy"] >= OT_MIN_POSITIONS_FOR_CHURN)
        )
    )

    trade_score = np.clip((weekly["weekly_trades"] - 1) * 15, 0, 100)
    churn_score = weekly["churn_ratio"] * 100
    weekly["overtrading_confidence"] = np.where(
        weekly["overtrading_flag"],
        np.maximum(trade_score, churn_score).clip(0, 100),
        0.0,
    )
    return weekly


# ================================================================
# TOP-LEVEL: run all detectors for one user
# ================================================================
def _json_safe(records):
    """Replace NaN/NaT/inf with None so the result is JSON-serialisable.
    Starlette's JSONResponse uses allow_nan=False and rejects NaN."""
    import math
    out = []
    for rec in records:
        safe = {}
        for k, v in rec.items():
            try:
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    safe[k] = None
                elif pd.isna(v):
                    safe[k] = None
                else:
                    safe[k] = v
            except (TypeError, ValueError):
                safe[k] = v
        out.append(safe)
    return out


def analyze_user_trades(trades: pd.DataFrame, prices: pd.DataFrame,
                        nifty: pd.DataFrame) -> dict:
    """
    The main entry point the API calls.

    Inputs:
      trades: [ticker, action, quantity, price, value, date]
      prices: [ticker, date, close]  price history for user's tickers
      nifty:  [date, close]          Nifty 50 index history

    Returns a dict with flagged trades and summary rates.
    """
    if len(trades) == 0:
        return {"error": "no trades provided"}

    # Ensure date columns are datetime
    trades = trades.copy()
    trades["date"] = pd.to_datetime(trades["date"])
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    nifty = nifty.copy()
    nifty["date"] = pd.to_datetime(nifty["date"])

    profile = build_investor_profile(trades)
    enriched = enrich_trades(trades, prices, nifty)

    panic = detect_panic_selling(enriched)
    fomo = detect_fomo_buying(enriched, profile)
    overtrading = detect_overtrading(enriched)

    panic_flagged = panic[panic["panic_flag"]] if len(panic) else panic
    fomo_flagged = fomo[fomo["fomo_flag"]] if len(fomo) else fomo
    ot_flagged = (overtrading[overtrading["overtrading_flag"]]
                  if len(overtrading) else overtrading)

    n_sells = profile["n_sells"]
    n_buys = profile["n_buys"]
    active_weeks = max(len(overtrading), 1)

    return {
        "profile": profile,
        "panic": {
            "flagged_count": int(len(panic_flagged)),
            "rate_pct": round(len(panic_flagged) / n_sells * 100, 2)
                        if n_sells else 0.0,
            "flags": _json_safe(panic_flagged.to_dict("records")),
        },
        "fomo": {
            "flagged_count": int(len(fomo_flagged)),
            "rate_pct": round(len(fomo_flagged) / n_buys * 100, 2)
                        if n_buys else 0.0,
            "flags": _json_safe(fomo_flagged.to_dict("records")),
        },
        "overtrading": {
            "flagged_weeks": int(len(ot_flagged)),
            "rate_pct": round(len(ot_flagged) / active_weeks * 100, 2),
            "flags": _json_safe(ot_flagged.to_dict("records")),
        },
    }


# ================================================================
# COST OF BIAS - what each flagged bias actually cost (forward view)
# ================================================================
def compute_bias_costs(result: dict, prices: pd.DataFrame,
                       horizon: int = 30) -> dict:
    """
    Quantify what each flagged bias cost, using forward prices only.

      panic sell : missed recovery = (close[t+horizon] - sell_price) x qty
      fomo buy   : chase loss      = (buy_price - close[t+horizon]) x qty
      round trip : sold low, then rebought the SAME stock high

    Uses only the prices already fetched. Flagged trades without `horizon`
    trading days of forward data are skipped (cost not yet measurable).
    """
    p = prices.copy()
    p["date"] = pd.to_datetime(p["date"])
    if getattr(p["date"].dt, "tz", None) is not None:
        p["date"] = p["date"].dt.tz_localize(None)
    by_ticker = {tk: d.sort_values("date").reset_index(drop=True)
                 for tk, d in p.groupby("ticker")}

    def close_after(ticker, t):
        d = by_ticker.get(ticker)
        if d is None:
            return None
        fwd = d[d["date"] > pd.Timestamp(t)]
        if len(fwd) < horizon:
            return None
        return float(fwd["close"].iloc[horizon - 1])

    panic_items, panic_total = [], 0.0
    for f in result["panic"]["flags"]:
        c = close_after(f["ticker"], f["date"])
        if c is None:
            continue
        missed = max((c - f["price"]) * f["quantity"], 0.0)
        panic_total += missed
        panic_items.append({
            "ticker": f["ticker"], "date": str(f["date"])[:10],
            "sell_price": round(float(f["price"]), 2),
            "price_later": round(c, 2), "missed_recovery": round(missed, 2),
        })

    fomo_items, fomo_total = [], 0.0
    for f in result["fomo"]["flags"]:
        c = close_after(f["ticker"], f["date"])
        if c is None:
            continue
        loss = max((f["price"] - c) * f["quantity"], 0.0)
        fomo_total += loss
        fomo_items.append({
            "ticker": f["ticker"], "date": str(f["date"])[:10],
            "buy_price": round(float(f["price"]), 2),
            "price_later": round(c, 2), "chase_loss": round(loss, 2),
        })

    round_trips, rt_total = [], 0.0
    panic_by_tk = {f["ticker"]: f for f in result["panic"]["flags"]}
    for f in result["fomo"]["flags"]:
        s = panic_by_tk.get(f["ticker"])
        if s and pd.to_datetime(f["date"]) > pd.to_datetime(s["date"]):
            shares = min(float(s["quantity"]), float(f["quantity"]))
            rt = (float(f["price"]) - float(s["price"])) * shares
            rt_total += rt
            round_trips.append({
                "ticker": f["ticker"],
                "sold_price": round(float(s["price"]), 2),
                "sold_date": str(s["date"])[:10],
                "rebought_price": round(float(f["price"]), 2),
                "rebought_date": str(f["date"])[:10],
                "shares": shares, "cost": round(rt, 2),
            })

    return {
        "horizon_trading_days": horizon,
        "panic_missed_recovery": round(panic_total, 2),
        "fomo_chase_loss": round(fomo_total, 2),
        "round_trip_total": round(rt_total, 2),
        "round_trips": round_trips,
        "panic_items": panic_items,
        "fomo_items": fomo_items,
    }


# ================================================================
# TIMELINES - price series + markers for each panic->FOMO round trip
# ================================================================
def build_timelines(result: dict, prices: pd.DataFrame,
                    pre: int = 20, post: int = 40) -> list:
    """
    For each round trip, return the stock's real price series windowed from
    `pre` trading days before the panic sell to `post` after the FOMO rebuy,
    plus the two markers. JSON-safe (dates as strings, prices as floats).
    """
    round_trips = result.get("costs", {}).get("round_trips", [])
    if not round_trips:
        return []

    p = prices.copy()
    p["date"] = pd.to_datetime(p["date"])
    if getattr(p["date"].dt, "tz", None) is not None:
        p["date"] = p["date"].dt.tz_localize(None)

    timelines = []
    for rt in round_trips:
        d = (p[p["ticker"] == rt["ticker"]]
             .sort_values("date").reset_index(drop=True))
        if d.empty:
            continue
        sold = pd.Timestamp(rt["sold_date"])
        bought = pd.Timestamp(rt["rebought_date"])
        sell_pos = d.index[d["date"] <= sold]
        buy_pos = d.index[d["date"] <= bought]
        if len(sell_pos) == 0 or len(buy_pos) == 0:
            continue
        lo = max(0, int(sell_pos[-1]) - pre)
        hi = min(len(d) - 1, int(buy_pos[-1]) + post)
        window = d.iloc[lo:hi + 1]
        series = [{"date": dt.strftime("%Y-%m-%d"), "close": round(float(c), 2)}
                  for dt, c in zip(window["date"], window["close"])]
        timelines.append({
            "ticker": rt["ticker"],
            "series": series,
            "sell": {"date": rt["sold_date"], "price": rt["sold_price"]},
            "buy": {"date": rt["rebought_date"], "price": rt["rebought_price"]},
            "cost": rt["cost"],
            "shares": rt["shares"],
        })
    return timelines
