# BiasGuard Backend

FastAPI backend that wraps the validated bias-detection engine in a REST API.

## What's in here

| File | What it does |
|------|--------------|
| `bias_engine.py` | The validated detection logic (panic / FOMO / overtrading), single-user version |
| `database.py` | SQLAlchemy models — users, trades, price cache, results |
| `market_data.py` | Fetches Indian stock prices from Yahoo Finance, caches in DB |
| `auth.py` | JWT signup/login, password hashing |
| `main.py` | The FastAPI app — all the endpoints |
| `test_integration.py` | End-to-end test (24 checks, all passing) |

## Setup

```bash
cd backend
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn main:app --reload
```

Then open **http://localhost:8000/docs** — FastAPI auto-generates an
interactive API explorer. You can test every endpoint from there.

## Run the tests

```bash
python test_integration.py
```

Expected: `24 passed, 0 failed`. The test mocks market data so it
runs without internet.

## API endpoints

| Method | Path | What |
|--------|------|------|
| POST | `/signup` | Create account → returns JWT |
| POST | `/login` | Log in → returns JWT |
| GET | `/me` | Current user info |
| POST | `/trades` | Log a trade |
| GET | `/trades` | List my trades |
| DELETE | `/trades/{id}` | Delete a trade |
| POST | `/analyze` | Run bias detection on my trades |
| GET | `/report` | Get my latest analysis |

All endpoints except signup/login need an `Authorization: Bearer <token>` header.

## How detection works

1. User logs trades (ticker, buy/sell, qty, price, date)
2. On `/analyze`, the backend fetches price history for those Indian
   stocks + the Nifty 50 index from Yahoo Finance (cached in the DB)
3. The validated `bias_engine` runs the three detectors
4. Results are stored and returned

Indian tickers: type `TCS` and it becomes `TCS.NS` automatically.
Use `.BO` suffix for BSE stocks.

## Important notes

- **Detection thresholds** in `bias_engine.py` are identical to the
  validated research script. Do not change them without re-validating.
- **Minimum 10 trades** required before `/analyze` will run — below
  that, pattern detection is statistically meaningless.
- `SECRET_KEY` in `auth.py` is a dev placeholder. For deployment, set
  the `BIASGUARD_SECRET_KEY` environment variable.
- Database is SQLite (`biasguard.db`). For production, change one URL
  in `database.py` to PostgreSQL.

## Known limitation

The detection engine was validated on European retail data (FAR-Trans).
It is deployed here for Indian markets. Cross-market generalization is
assumed (behavioral biases are universal) but not independently
validated on Indian data — this is documented as future work.
