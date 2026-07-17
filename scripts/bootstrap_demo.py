import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.auth_service import AuthService
from services.market_data_service import get_ticker_data


def ensure_demo_user(username: str, email: str, password: str) -> None:
    auth = AuthService()
    auth.initialize()
    conn = auth.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username=? OR email=?", (username, email.lower()))
    cursor.execute(
        "DELETE FROM failed_logins WHERE identifier IN (?, ?)", (username, email.lower())
    )
    conn.commit()
    conn.close()

    ok, err = auth.register_user(username, email, "Demo", "User", password)
    if not ok:
        raise RuntimeError(f"Could not create demo user: {err}")


def ensure_demo_data(tickers: list[str]) -> None:
    start_date = datetime(2019, 1, 1)
    end_date = datetime(2026, 1, 1)
    for ticker in tickers:
        get_ticker_data(ticker=ticker, start_date=start_date, end_date=end_date, data_dir="data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap demo user and optional data.")
    parser.add_argument("--username", default="demo")
    parser.add_argument("--email", default="demo@quantvision.dev")
    parser.add_argument("--password", default="Demo123!@")
    parser.add_argument("--with-data", action="store_true")
    parser.add_argument("--tickers", default="AAPL,MSFT,GOOGL")
    args = parser.parse_args()

    ensure_demo_user(args.username, args.email, args.password)
    if args.with_data:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        ensure_demo_data(tickers)

    print("Demo bootstrap completed.")
    print(f"username={args.username}")
    print(f"email={args.email.lower()}")
