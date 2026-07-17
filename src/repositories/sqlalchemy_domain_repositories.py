from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from config import DATABASE_URL

try:
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        Float,
        Integer,
        MetaData,
        String,
        Table,
        create_engine,
        delete,
        insert,
        select,
    )
except Exception:  # pragma: no cover - optional dependency
    Boolean = Column = DateTime = Float = Integer = MetaData = String = Table = None  # type: ignore[assignment]
    create_engine = delete = insert = select = None  # type: ignore[assignment]


class _BaseSqlRepository:
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        if create_engine is None or MetaData is None:
            raise RuntimeError("SQLAlchemy dependency not available")
        self.engine = create_engine(database_url, future=True)
        self.meta = MetaData()

    def _now(self) -> datetime:
        return datetime.now(UTC)


class SqlPortfolioRepository(_BaseSqlRepository):
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        super().__init__(database_url)
        assert Table is not None
        self.positions = Table(
            "portfolio_positions",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(120), nullable=False, index=True),
            Column("ticker", String(20), nullable=False),
            Column("quantity", Float, nullable=False),
            Column("buy_price", Float, nullable=False),
            Column("buy_date", String(40), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.meta.create_all(self.engine)

    def add_position(self, username: str, ticker: str, quantity: float, buy_price: float, buy_date: str) -> int:
        assert insert is not None
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.positions).values(
                    username=username,
                    ticker=ticker.upper(),
                    quantity=float(quantity),
                    buy_price=float(buy_price),
                    buy_date=buy_date,
                    created_at=self._now(),
                )
            )
            return int(result.inserted_primary_key[0])

    def remove_position(self, position_id: int, username: str) -> None:
        assert delete is not None
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.positions).where(
                    self.positions.c.id == int(position_id), self.positions.c.username == username
                )
            )

    def list_positions(self, username: str) -> pd.DataFrame:
        assert select is not None
        with self.engine.begin() as conn:
            result = conn.execute(
                select(
                    self.positions.c.id,
                    self.positions.c.ticker,
                    self.positions.c.quantity,
                    self.positions.c.buy_price,
                    self.positions.c.buy_date,
                )
                .where(self.positions.c.username == username)
                .order_by(self.positions.c.buy_date.asc())
            )
            rows = result.mappings().all()
        return pd.DataFrame(rows)


class SqlWatchlistRepository(_BaseSqlRepository):
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        super().__init__(database_url)
        assert Table is not None
        self.watchlists = Table(
            "watchlists",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(120), nullable=False, index=True),
            Column("name", String(120), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.watchlist_items = Table(
            "watchlist_items",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("watchlist_id", Integer, nullable=False, index=True),
            Column("ticker", String(20), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.meta.create_all(self.engine)

    def create_watchlist(self, username: str, name: str) -> int:
        assert select is not None and insert is not None
        name_clean = name.strip()
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(self.watchlists.c.id).where(
                    self.watchlists.c.username == username, self.watchlists.c.name == name_clean
                )
            ).first()
            if existing:
                return int(existing[0])
            result = conn.execute(
                insert(self.watchlists).values(username=username, name=name_clean, created_at=self._now())
            )
            return int(result.inserted_primary_key[0])

    def delete_watchlist(self, watchlist_id: int, username: str) -> None:
        assert delete is not None
        with self.engine.begin() as conn:
            conn.execute(delete(self.watchlist_items).where(self.watchlist_items.c.watchlist_id == int(watchlist_id)))
            conn.execute(
                delete(self.watchlists).where(
                    self.watchlists.c.id == int(watchlist_id), self.watchlists.c.username == username
                )
            )

    def add_ticker(self, watchlist_id: int, ticker: str) -> None:
        assert select is not None and insert is not None
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.watchlist_items.c.id).where(
                    self.watchlist_items.c.watchlist_id == int(watchlist_id),
                    self.watchlist_items.c.ticker == ticker.upper(),
                )
            ).first()
            if not exists:
                conn.execute(
                    insert(self.watchlist_items).values(
                        watchlist_id=int(watchlist_id), ticker=ticker.upper(), created_at=self._now()
                    )
                )

    def remove_ticker(self, watchlist_id: int, ticker: str) -> None:
        assert delete is not None
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.watchlist_items).where(
                    self.watchlist_items.c.watchlist_id == int(watchlist_id),
                    self.watchlist_items.c.ticker == ticker.upper(),
                )
            )

    def list_watchlists(self, username: str) -> pd.DataFrame:
        assert select is not None
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.watchlists.c.id, self.watchlists.c.name, self.watchlists.c.created_at)
                .where(self.watchlists.c.username == username)
                .order_by(self.watchlists.c.created_at.asc())
            ).mappings().all()
        return pd.DataFrame(rows)

    def list_items(self, watchlist_id: int) -> pd.DataFrame:
        assert select is not None
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.watchlist_items.c.ticker)
                .where(self.watchlist_items.c.watchlist_id == int(watchlist_id))
                .order_by(self.watchlist_items.c.ticker.asc())
            ).mappings().all()
        return pd.DataFrame(rows)


class SqlAlertsRepository(_BaseSqlRepository):
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        super().__init__(database_url)
        assert Table is not None
        self.rules = Table(
            "alert_rules",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(120), nullable=False, index=True),
            Column("ticker", String(20), nullable=False),
            Column("alert_type", String(60), nullable=False),
            Column("threshold", Float, nullable=True),
            Column("active", Boolean, nullable=False, default=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.history = Table(
            "alert_history",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(120), nullable=False, index=True),
            Column("ticker", String(20), nullable=False),
            Column("alert_type", String(60), nullable=False),
            Column("message", String(400), nullable=False),
            Column("triggered_at", DateTime(timezone=True), nullable=False),
        )
        self.meta.create_all(self.engine)

    def create_rule(self, username: str, ticker: str, alert_type: str, threshold: float | None, active: bool) -> int:
        assert insert is not None
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.rules).values(
                    username=username,
                    ticker=ticker.upper(),
                    alert_type=alert_type,
                    threshold=threshold,
                    active=bool(active),
                    created_at=self._now(),
                )
            )
            return int(result.inserted_primary_key[0])

    def list_rules(self, username: str) -> pd.DataFrame:
        assert select is not None
        with self.engine.begin() as conn:
            query = select(
                self.rules.c.id,
                self.rules.c.username,
                self.rules.c.ticker,
                self.rules.c.alert_type,
                self.rules.c.threshold,
                self.rules.c.active,
            ).order_by(self.rules.c.id.desc())
            if username:
                query = query.where(self.rules.c.username == username)
            rows = conn.execute(query).mappings().all()
        return pd.DataFrame(rows)

    def delete_rule(self, rule_id: int, username: str) -> None:
        assert delete is not None
        with self.engine.begin() as conn:
            conn.execute(delete(self.rules).where(self.rules.c.id == int(rule_id), self.rules.c.username == username))

    def emit_alert(self, username: str, ticker: str, alert_type: str, message: str) -> int:
        assert insert is not None
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.history).values(
                    username=username,
                    ticker=ticker.upper(),
                    alert_type=alert_type,
                    message=message,
                    triggered_at=self._now(),
                )
            )
            return int(result.inserted_primary_key[0])

    def list_history(self, username: str, limit: int = 200) -> pd.DataFrame:
        assert select is not None
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.history.c.ticker,
                    self.history.c.alert_type,
                    self.history.c.message,
                    self.history.c.triggered_at,
                )
                .where(self.history.c.username == username)
                .order_by(self.history.c.id.desc())
                .limit(int(limit))
            ).mappings().all()
        return pd.DataFrame(rows)

    def list_rule_owners(self) -> list[str]:
        assert select is not None
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.rules.c.username).distinct()).all()
        return sorted(str(row[0]) for row in rows if row and row[0])
