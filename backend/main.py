"""
BiasGuard Backend — main.py
================================================================
The FastAPI application. Wraps the validated bias detection engine
in a REST API a web frontend can call.

Endpoints:
  POST /signup          create an account
  POST /login           get a JWT token
  GET  /me              current user info
  POST /trades          log a trade
  GET  /trades          list my trades
  DELETE /trades/{id}   remove a trade
  POST /analyze         run bias detection on my trades
  GET  /report          get my latest analysis result

Run:
  cd backend
  uvicorn main:app --reload
"""

import json
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import bias_engine
import market_data
from auth import (
    hash_password, verify_password, create_access_token, get_current_user,
)
from database import (
    User, Trade, BiasResult, get_db, init_db,
)

# ----------------------------------------------------------------
# App setup
# ----------------------------------------------------------------
app = FastAPI(title="BiasGuard API", version="1.0")

# CORS — allow the React dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ----------------------------------------------------------------
# Pydantic schemas (request/response shapes)
# ----------------------------------------------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TradeRequest(BaseModel):
    ticker: str
    action: str          # "Buy" or "Sell"
    quantity: float
    price: float
    trade_date: str       # ISO date string, e.g. "2024-03-15"
    reason: str | None = None


class TradeResponse(BaseModel):
    id: int
    ticker: str
    action: str
    quantity: float
    price: float
    value: float
    trade_date: str
    reason: str | None

    class Config:
        from_attributes = True


# ----------------------------------------------------------------
# AUTH ENDPOINTS
# ----------------------------------------------------------------
@app.post("/signup", response_model=TokenResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    user = User(
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@app.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses 'username' — we treat it as email
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email,
            "created_at": user.created_at}


# ----------------------------------------------------------------
# TRADE ENDPOINTS
# ----------------------------------------------------------------
@app.post("/trades", response_model=TradeResponse)
def create_trade(req: TradeRequest,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if req.action not in ("Buy", "Sell"):
        raise HTTPException(
            status_code=400, detail="action must be 'Buy' or 'Sell'",
        )
    if req.quantity <= 0 or req.price <= 0:
        raise HTTPException(
            status_code=400, detail="quantity and price must be positive",
        )
    try:
        trade_dt = pd.to_datetime(req.trade_date).to_pydatetime()
    except Exception:
        raise HTTPException(
            status_code=400, detail="trade_date must be a valid date",
        )

    trade = Trade(
        user_id=user.id,
        ticker=market_data.normalize_ticker(req.ticker),
        action=req.action,
        quantity=req.quantity,
        price=req.price,
        trade_date=trade_dt,
        reason=req.reason,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return _trade_to_response(trade)


@app.get("/trades", response_model=list[TradeResponse])
def list_trades(user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id)
        .order_by(Trade.trade_date)
        .all()
    )
    return [_trade_to_response(t) for t in trades]


@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    trade = (
        db.query(Trade)
        .filter(Trade.id == trade_id, Trade.user_id == user.id)
        .first()
    )
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(trade)
    db.commit()
    return {"deleted": trade_id}


# ----------------------------------------------------------------
# ANALYSIS ENDPOINTS
# ----------------------------------------------------------------
@app.post("/analyze")
def analyze(user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    """Run bias detection on all of the user's trades."""
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id)
        .order_by(Trade.trade_date)
        .all()
    )
    if len(trades) < 10:
        raise HTTPException(
            status_code=400,
            detail=(f"Need at least 10 trades to detect patterns. "
                    f"You have {len(trades)}."),
        )

    # Build the trades DataFrame the engine expects
    trades_df = pd.DataFrame([{
        "ticker": t.ticker,
        "action": t.action,
        "quantity": t.quantity,
        "price": t.price,
        "value": t.quantity * t.price,
        "date": t.trade_date,
    } for t in trades])

    # Date range we need price data for
    start = trades_df["date"].min()
    end = trades_df["date"].max()

    # Fetch price history + Nifty context
    tickers = trades_df["ticker"].unique().tolist()
    prices = market_data.get_prices_for_tickers(db, tickers, start, end)
    nifty = market_data.get_nifty_history(db, start, end)

    if len(prices) == 0:
        raise HTTPException(
            status_code=502,
            detail="Could not fetch price data for your stocks. "
                   "Check the ticker symbols.",
        )
    if len(nifty) == 0:
        raise HTTPException(
            status_code=502,
            detail="Could not fetch Nifty 50 market data.",
        )

    # Run the validated detection engine
    result = bias_engine.analyze_user_trades(trades_df, prices, nifty)

    # Quantify what each flagged bias cost (forward counterfactual)
    costs = bias_engine.compute_bias_costs(result, prices)
    result["costs"] = costs
    costs["timelines"] = bias_engine.build_timelines(result, prices)

    # Persist a summary
    bias_result = BiasResult(
        user_id=user.id,
        panic_flagged=result["panic"]["flagged_count"],
        panic_rate=result["panic"]["rate_pct"],
        fomo_flagged=result["fomo"]["flagged_count"],
        fomo_rate=result["fomo"]["rate_pct"],
        overtrading_flagged=result["overtrading"]["flagged_weeks"],
        overtrading_rate=result["overtrading"]["rate_pct"],
        detail_json=json.dumps(result, default=str),
    )
    db.add(bias_result)
    db.commit()
    db.refresh(bias_result)

    return {
        "run_at": bias_result.run_at,
        "costs": costs,
        "panic": result["panic"],
        "fomo": result["fomo"],
        "overtrading": result["overtrading"],
        "summary": {
            "total_trades": len(trades),
            "panic_rate_pct": result["panic"]["rate_pct"],
            "fomo_rate_pct": result["fomo"]["rate_pct"],
            "overtrading_rate_pct": result["overtrading"]["rate_pct"],
        },
    }


@app.get("/debug-analyze")
def debug_analyze(user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """
    DIAGNOSTIC endpoint — runs the analysis pipeline but returns every
    intermediate value so we can see exactly what the detector sees.
    Temporary: for debugging why flags don't fire.
    """
    import bias_engine as be

    trades = (
        db.query(Trade)
        .filter(Trade.user_id == user.id)
        .order_by(Trade.trade_date)
        .all()
    )
    out = {"trade_count": len(trades), "steps": {}}

    trades_df = pd.DataFrame([{
        "ticker": t.ticker, "action": t.action, "quantity": t.quantity,
        "price": t.price, "value": t.quantity * t.price, "date": t.trade_date,
    } for t in trades])
    trades_df["date"] = pd.to_datetime(trades_df["date"])

    start = trades_df["date"].min()
    end = trades_df["date"].max()
    out["steps"]["date_range"] = {"start": str(start), "end": str(end)}

    tickers = trades_df["ticker"].unique().tolist()
    out["steps"]["tickers"] = tickers

    prices = market_data.get_prices_for_tickers(db, tickers, start, end)
    nifty = market_data.get_nifty_history(db, start, end)
    out["steps"]["price_rows_fetched"] = len(prices)
    out["steps"]["nifty_rows_fetched"] = len(nifty)

    if len(prices) > 0:
        prices = prices.copy()
        prices["date"] = pd.to_datetime(prices["date"])
        out["steps"]["price_date_min"] = str(prices["date"].min())
        out["steps"]["price_date_max"] = str(prices["date"].max())
        out["steps"]["price_sample"] = prices.head(3).astype(str).to_dict("records")

    if len(prices) == 0 or len(nifty) == 0:
        out["steps"]["ABORT"] = "no price or nifty data — cannot enrich"
        return out

    nifty = nifty.copy()
    nifty["date"] = pd.to_datetime(nifty["date"])

    # run enrichment and dump the enriched trades
    enriched = be.enrich_trades(trades_df.copy(), prices.copy(), nifty.copy())
    sells = enriched[enriched["action"] == "Sell"]
    out["steps"]["enriched_sells"] = sells[[
        "ticker", "date", "holding_days", "sold_fraction_of_position",
        "return_3d", "market_avg_3d",
    ]].astype(str).to_dict("records")

    # evaluate each panic condition explicitly
    cond_rows = []
    for _, s in sells.iterrows():
        cond_rows.append({
            "ticker": s["ticker"],
            "date": str(s["date"]),
            "holding_days": str(s["holding_days"]),
            "return_3d": str(s["return_3d"]),
            "market_avg_3d": str(s["market_avg_3d"]),
            "sold_fraction": str(s["sold_fraction_of_position"]),
            "cond_holding(<30)": bool(s["holding_days"] < 30)
                if pd.notna(s["holding_days"]) else "NaN",
            "cond_drop(<=-5)": bool(s["return_3d"] <= -5)
                if pd.notna(s["return_3d"]) else "NaN",
            "cond_market(<=0)": bool(s["market_avg_3d"] <= 0)
                if pd.notna(s["market_avg_3d"]) else "NaN",
            "cond_fraction(>=0.5)": bool(s["sold_fraction_of_position"] >= 0.5)
                if pd.notna(s["sold_fraction_of_position"]) else "NaN",
        })
    out["steps"]["panic_conditions"] = cond_rows

    return out


@app.get("/report")
def latest_report(user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Return the user's most recent analysis result."""
    result = (
        db.query(BiasResult)
        .filter(BiasResult.user_id == user.id)
        .order_by(BiasResult.run_at.desc())
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No analysis yet. POST /analyze first.",
        )
    return {
        "run_at": result.run_at,
        "panic_flagged": result.panic_flagged,
        "panic_rate": result.panic_rate,
        "fomo_flagged": result.fomo_flagged,
        "fomo_rate": result.fomo_rate,
        "overtrading_flagged": result.overtrading_flagged,
        "overtrading_rate": result.overtrading_rate,
        "detail": json.loads(result.detail_json) if result.detail_json else None,
    }


@app.get("/")
def root():
    return {"service": "BiasGuard API", "status": "running",
            "docs": "/docs"}


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def _trade_to_response(t: Trade) -> TradeResponse:
    return TradeResponse(
        id=t.id,
        ticker=t.ticker,
        action=t.action,
        quantity=t.quantity,
        price=t.price,
        value=t.quantity * t.price,
        trade_date=t.trade_date.strftime("%Y-%m-%d"),
        reason=t.reason,
    )
