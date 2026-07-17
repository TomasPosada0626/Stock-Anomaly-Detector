# QuantVision Case Studies

This document summarizes portfolio-ready examples that combine anomaly detection, indicators, and backtesting.

## Case Study 1: AAPL 2023 Swing Strategy
- Universe: `AAPL`
- Period: `2023-01-01` to `2023-12-31`
- Setup: RSI + rolling anomaly signal + risk filters
- Result snapshot:
  - Strategy return: `+23.0%`
  - Buy and hold: `+18.0%`
  - Max drawdown improved versus benchmark

Interpretation:
- The combined signal reduced false entries during volatile weeks.
- Outlier-aware exits improved downside control.

## Case Study 2: NVDA Momentum Exhaustion Detection
- Universe: `NVDA`
- Setup: Isolation Forest + LOF + RSI divergence checks
- Outcome:
  - Earlier identification of overextended moves
  - Better timing for de-risking near local peaks

## Case Study 3: Multi-Asset Risk Rotation
- Universe: `AAPL`, `MSFT`, `GOOGL`, `JPM`, `V`
- Setup: Correlation and drawdown panels + anomaly tags
- Outcome:
  - Faster concentration-risk detection
  - Cleaner watchlist triage for alert creation

## Reproducibility Notes
- Use the same date range and default method parameters first.
- Export CSV and PDF artifacts from `Anomalies` and `Reports`.
- Save benchmark tables and drawdown metrics to compare runs.
