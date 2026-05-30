# Cleaned Betting Dataset

Input files:
- `RawData\Bets- first batch of data.xlsx`
- `RawData\second second batch.xlsx`

Reporting cutoff: `2026-04-30 23:59:59`
Rows after reporting cutoff removed: `120,494`
Original rows: `600,000`
Cleaned rows: `479,506`
Removed rows: `120,494`

## Exported Files

- `Data\cleaned\cleaned_bets.csv`
- Parquet export skipped because no parquet engine is installed.

## Added Analytics Fields

- `placed_hour`, `placed_day`, `placed_day_name`, `placed_week`, `placed_month`, `placed_year`
- `placed_time_band`: Midnight, Morning, Lunch, Afternoon, Evening, Night
- `is_weekend`
- `settlement_seconds`, `settlement_minutes`
- `option_family`: Float, Drown, Combo
- `stake_band`: Small, Medium, Large, Very Large
- `odds_band`: Lower Odds, Medium Odds, High Odds, Very High Odds
- `strategy_style`: Conservative Single, Balanced Single, High-Odds Hunter, Combo / Multi-Phase
- `is_win`, `is_loss`, `roi_percent`

These fields support bettor timing analysis, strategy/style segmentation, odds influence analysis, and promotion targeting.
