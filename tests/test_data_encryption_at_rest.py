import sqlite3

from services.alerts_service import AlertRule, AlertsService
from services.watchlist_service import WatchlistInput, WatchlistService


def test_watchlist_ticker_encrypted_at_rest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-secret-key")
    db_path = str(tmp_path / "encrypted_watchlists.db")

    service = WatchlistService(db_path=db_path, use_sqlalchemy=False)
    watchlist_id = service.create_watchlist(WatchlistInput(username="alice", name="Tech"))
    service.add_ticker(watchlist_id, "AAPL")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT ticker FROM watchlist_items WHERE watchlist_id = ?", (watchlist_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row[0] != "AAPL"
    assert str(row[0]).startswith("qv_enc_v")

    items = service.list_items(watchlist_id)
    assert items.iloc[0]["ticker"] == "AAPL"


def test_alert_message_encrypted_at_rest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "test-secret-key")
    db_path = str(tmp_path / "encrypted_alerts.db")

    service = AlertsService(db_path=db_path, use_sqlalchemy=False)
    rule_id = service.create_rule(
        AlertRule(username="alice", ticker="AAPL", alert_type="rsi_gt_70", threshold=None, active=True)
    )
    assert rule_id > 0
    service.emit_alert("alice", "AAPL", "rsi_gt_70", "RSI reached 80")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT ticker, message FROM alert_history LIMIT 1").fetchone()
    conn.close()

    assert row is not None
    assert row[0] != "AAPL"
    assert str(row[0]).startswith("qv_enc_v")
    assert str(row[1]).startswith("qv_enc_v")

    history = service.list_history("alice")
    assert "RSI reached 80" in history.iloc[0]["message"]
