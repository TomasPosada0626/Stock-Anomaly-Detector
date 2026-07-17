from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from services.backtesting_service import BacktestingService


@dataclass(frozen=True)
class StrategyArtifact:
    strategy_name: str
    notebook_path: str
    signals_path: str
    buy_column: str
    sell_column: str
    created_at: str


class StrategyPipelineService:
    """Promote notebook-generated strategy artifacts into runnable manifests."""

    def __init__(self, output_dir: str = "storage/strategies") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_signals(df: pd.DataFrame, buy_column: str, sell_column: str) -> None:
        """Validate required signal dataframe schema before promotion."""
        if df.empty:
            raise ValueError("signals dataframe cannot be empty")
        if "Close" not in df.columns:
            raise ValueError("signals dataframe must include Close column")
        if buy_column not in df.columns or sell_column not in df.columns:
            raise ValueError("signals dataframe must include buy/sell signal columns")

    def promote_notebook_strategy(
        self,
        strategy_name: str,
        notebook_path: str,
        signals_df: pd.DataFrame,
        buy_column: str = "buy_signal",
        sell_column: str = "sell_signal",
    ) -> Path:
        """Persist a strategy manifest and associated signal CSV artifact.

        Args:
            strategy_name: Human-readable strategy name.
            notebook_path: Source notebook file path.
            signals_df: Frame containing close prices and signal columns.
            buy_column: Buy signal column name.
            sell_column: Sell signal column name.

        Returns:
            Path to the generated manifest.
        """
        strategy_key = strategy_name.strip().lower().replace(" ", "_")
        if not strategy_key:
            raise ValueError("strategy_name must not be empty")

        self._validate_signals(signals_df, buy_column, sell_column)

        strategy_dir = self.output_dir / strategy_key
        strategy_dir.mkdir(parents=True, exist_ok=True)

        signals_path = strategy_dir / "signals.csv"
        manifest_path = strategy_dir / "manifest.json"

        signals_df.to_csv(signals_path)

        artifact = StrategyArtifact(
            strategy_name=strategy_name.strip(),
            notebook_path=notebook_path,
            signals_path=str(signals_path),
            buy_column=buy_column,
            sell_column=sell_column,
            created_at=pd.Timestamp.now("UTC").isoformat(),
        )
        manifest_path.write_text(json.dumps(artifact.__dict__, indent=2), encoding="utf-8")
        return manifest_path

    @staticmethod
    def load_artifact(manifest_path: str | Path) -> dict[str, Any]:
        """Load and validate a promoted strategy manifest payload."""
        path = Path(manifest_path)
        payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        required = {
            "strategy_name",
            "notebook_path",
            "signals_path",
            "buy_column",
            "sell_column",
            "created_at",
        }
        missing = required.difference(payload.keys())
        if missing:
            raise ValueError(f"artifact manifest missing required keys: {sorted(missing)}")
        return payload

    def run_promoted_strategy(
        self,
        manifest_path: str | Path,
        initial_capital: float = 10_000.0,
    ) -> dict[str, float]:
        """Run backtesting for a previously promoted strategy artifact."""
        artifact = self.load_artifact(manifest_path)
        signals_df = pd.read_csv(artifact["signals_path"], index_col=0, parse_dates=True)

        service = BacktestingService()
        result = service.run_simple_strategy(
            signals_df,
            buy_signal_col=str(artifact["buy_column"]),
            sell_signal_col=str(artifact["sell_column"]),
            initial_capital=float(initial_capital),
        )
        return result
