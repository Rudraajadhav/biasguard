"""
BiasGuard Backend — database.py
================================================================
SQLAlchemy models. SQLite for development, designed so switching
to PostgreSQL later is a one-line URL change.

Tables:
  - users          : accounts
  - trades         : user-logged trades
  - price_cache    : cached stock price history (shared across users)
  - bias_results   : stored detection results per analysis run
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Boolean, ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ----------------------------------------------------------------
# Engine — SQLite for dev. For Postgres, swap this URL for:
#   "postgresql://user:pass@host/biasguard"
# ----------------------------------------------------------------
DB_PATH = Path(__file__).parent / "biasguard.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


# ================================================================
# MODELS
# ================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    trades = relationship("Trade", back_populates="user",
                           cascade="all, delete-orphan")
    results = relationship("BiasResult", back_populates="user",
                            cascade="all, delete-orphan")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    ticker = Column(String, nullable=False, index=True)   # e.g. "TCS.NS"
    action = Column(String, nullable=False)               # "Buy" or "Sell"
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)                 # price per share
    trade_date = Column(DateTime, nullable=False)
    reason = Column(String, nullable=True)                # optional dropdown
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="trades")

    @property
    def value(self):
        return self.quantity * self.price


class PriceCache(Base):
    """
    Cached daily close prices for stocks (and the Nifty index).
    Shared across all users — if one user logs a TCS trade, the
    fetched TCS history is reused for everyone.
    """
    __tablename__ = "price_cache"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    price_date = Column(DateTime, nullable=False)
    close = Column(Float, nullable=False)
    fetched_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "price_date", name="uix_ticker_date"),
    )


class BiasResult(Base):
    """
    Stores the outcome of one analysis run for a user.
    The detailed flags are stored as JSON text for simplicity.
    """
    __tablename__ = "bias_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    run_at = Column(DateTime, default=utcnow)

    panic_flagged = Column(Integer, default=0)
    panic_rate = Column(Float, default=0.0)
    fomo_flagged = Column(Integer, default=0)
    fomo_rate = Column(Float, default=0.0)
    overtrading_flagged = Column(Integer, default=0)
    overtrading_rate = Column(Float, default=0.0)

    detail_json = Column(Text, nullable=True)   # full flag detail as JSON

    user = relationship("User", back_populates="results")


# ================================================================
# INIT
# ================================================================
def init_db():
    """Create all tables. Safe to call repeatedly."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session, closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
