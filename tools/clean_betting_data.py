from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPORTING_CUTOFF_AT = pd.Timestamp("2026-04-30 23:59:59.999999")

EXPECTED_COLUMNS = [
    "round_id",
    "game_round_pk",
    "bet_id",
    "slip_id",
    "slip_item_id",
    "player_id",
    "character_id",
    "character_name",
    "bet_type",
    "option_code",
    "phase_start",
    "phase_end",
    "stake",
    "odds",
    "bet_status",
    "settlement_result",
    "payout_amount",
    "profit",
    "placed_at",
    "settled_at",
]


def classify_time_band(hour: int | float | None) -> str | None:
    if pd.isna(hour):
        return None
    hour = int(hour)
    if 0 <= hour <= 5:
        return "Midnight"
    if 6 <= hour <= 10:
        return "Morning"
    if 11 <= hour <= 14:
        return "Lunch"
    if 15 <= hour <= 17:
        return "Afternoon"
    if 18 <= hour <= 20:
        return "Evening"
    if 21 <= hour <= 23:
        return "Night"
    return None


def classify_stake_band(stake: float | int | None) -> str:
    if pd.isna(stake):
        return "Unknown"
    stake = float(stake)
    if stake < 50:
        return "Small"
    if stake < 150:
        return "Medium"
    if stake < 300:
        return "Large"
    return "Very Large"


def classify_odds_band(odds: float | int | None) -> str:
    if pd.isna(odds):
        return "Unknown"
    odds = float(odds)
    if odds < 4:
        return "Lower Odds"
    if odds < 5:
        return "Medium Odds"
    if odds < 6:
        return "High Odds"
    return "Very High Odds"


def normalize_option_code(value: object) -> str:
    option = str(value or "").strip().upper()
    option = " ".join(option.split())
    return option


def classify_option_family(option_code: str) -> str:
    option = normalize_option_code(option_code)
    compact = option.replace(" ", "")
    if "AND" in compact:
        return "Combo"
    if compact.startswith("F"):
        return "Float"
    if compact.startswith("D"):
        return "Drown"
    return "Unknown"


def classify_strategy_style(row: pd.Series) -> str:
    bet_type = str(row.get("bet_type", "")).upper()
    option_family = str(row.get("option_family", ""))
    odds_band = str(row.get("odds_band", ""))

    if bet_type == "DOUBLE" or option_family == "Combo":
        return "Combo / Multi-Phase"
    if odds_band in {"Very High Odds", "High Odds"}:
        return "High-Odds Hunter"
    if odds_band == "Lower Odds":
        return "Conservative Single"
    return "Balanced Single"


def read_raw(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        return pd.read_json(path)
    raise SystemExit(f"Unsupported file type: {path.suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean Stone Odds betting data for ML analytics.")
    parser.add_argument("inputs", type=Path, nargs="+", help="Path(s) to raw .xlsx, .csv, or .json files.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Data") / "cleaned",
        help="Directory where cleaned datasets will be written.",
    )
    parser.add_argument(
        "--reporting-cutoff",
        type=pd.Timestamp,
        default=REPORTING_CUTOFF_AT,
        help="Latest placed_at timestamp to keep in the cleaned reporting dataset.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    frames = []
    original_rows = 0
    for input_path in args.inputs:
        frame = read_raw(input_path)
        frame.columns = [str(column).strip() for column in frame.columns]
        frame["source_file"] = str(input_path)
        frames.append(frame)
        original_rows += len(frame)

    df = pd.concat(frames, ignore_index=True)

    missing_columns = [column for column in EXPECTED_COLUMNS if column not in df.columns]
    if missing_columns:
        raise SystemExit(f"Missing required columns: {', '.join(missing_columns)}")

    for column in ["placed_at", "settled_at"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    for column in ["stake", "odds", "payout_amount", "profit"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in ["round_id", "game_round_pk", "bet_id", "slip_id", "slip_item_id", "player_id", "character_id"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    df["character_name"] = df["character_name"].astype(str).str.strip()
    df["bet_type"] = df["bet_type"].astype(str).str.strip().str.upper()
    df["option_code"] = df["option_code"].apply(normalize_option_code)
    df["bet_status"] = df["bet_status"].astype(str).str.strip().str.upper()
    df["settlement_result"] = df["settlement_result"].astype(str).str.strip().str.upper()

    after_reporting_cutoff = df["placed_at"].gt(args.reporting_cutoff)
    future_rows_removed = int(after_reporting_cutoff.sum())

    required_valid = (
        df["bet_id"].notna()
        & df["player_id"].notna()
        & df["placed_at"].notna()
        & df["placed_at"].le(args.reporting_cutoff)
        & df["stake"].notna()
        & (df["stake"] > 0)
        & df["odds"].notna()
        & (df["odds"] > 1)
        & df["option_code"].ne("")
        & df["bet_type"].ne("")
    )
    df = df.loc[required_valid].copy()

    df = df.drop_duplicates(subset=["bet_id"], keep="first")
    event_key = ["player_id", "slip_id", "game_round_pk", "character_id", "option_code", "stake", "odds", "placed_at"]
    df = df.drop_duplicates(subset=event_key, keep="first")

    placed = df["placed_at"]
    settled = df["settled_at"]
    df["placed_date"] = placed.dt.date.astype(str)
    df["placed_hour"] = placed.dt.hour
    df["placed_day"] = placed.dt.day
    df["placed_day_name"] = placed.dt.day_name()
    df["placed_week"] = placed.dt.strftime("%G-W%V")
    df["placed_month"] = placed.dt.to_period("M").astype(str)
    df["placed_year"] = placed.dt.year
    df["is_weekend"] = df["placed_day_name"].isin(["Saturday", "Sunday"])
    df["placed_time_band"] = df["placed_hour"].apply(classify_time_band)

    df["settled_date"] = settled.dt.date.astype(str)
    df["settled_hour"] = settled.dt.hour
    df["settlement_seconds"] = (settled - placed).dt.total_seconds()
    df["settlement_minutes"] = (df["settlement_seconds"] / 60).round(2)

    df["option_family"] = df["option_code"].apply(classify_option_family)
    df["is_combo_bet"] = (df["bet_type"].eq("DOUBLE")) | df["option_family"].eq("Combo")
    df["stake_band"] = df["stake"].apply(classify_stake_band)
    df["odds_band"] = df["odds"].apply(classify_odds_band)
    df["strategy_style"] = df.apply(classify_strategy_style, axis=1)
    df["is_win"] = df["settlement_result"].eq("WIN")
    df["is_loss"] = df["settlement_result"].isin(["LOSE", "LOSS"])
    df["roi_percent"] = (df["profit"] / df["stake"] * 100).round(2)

    clean_columns = EXPECTED_COLUMNS + [
        "placed_date",
        "placed_hour",
        "placed_day",
        "placed_day_name",
        "placed_week",
        "placed_month",
        "placed_year",
        "is_weekend",
        "placed_time_band",
        "settled_date",
        "settled_hour",
        "settlement_seconds",
        "settlement_minutes",
        "option_family",
        "is_combo_bet",
        "stake_band",
        "odds_band",
        "strategy_style",
        "is_win",
        "is_loss",
        "roi_percent",
    ]
    clean_df = df[clean_columns].sort_values(["placed_at", "bet_id"]).copy()

    cleaned_csv = output_dir / "cleaned_bets.csv"
    cleaned_parquet = output_dir / "cleaned_bets.parquet"
    summary_path = output_dir / "cleaning_summary.md"

    clean_df.to_csv(cleaned_csv, index=False)
    parquet_written = True
    try:
        clean_df.to_parquet(cleaned_parquet, index=False)
    except Exception:
        parquet_written = False

    summary = [
        "# Cleaned Betting Dataset",
        "",
        "Input files:",
        *[f"- `{input_path}`" for input_path in args.inputs],
        "",
        f"Reporting cutoff: `{args.reporting_cutoff:%Y-%m-%d %H:%M:%S}`",
        f"Rows after reporting cutoff removed: `{future_rows_removed:,}`",
        f"Original rows: `{original_rows:,}`",
        f"Cleaned rows: `{len(clean_df):,}`",
        f"Removed rows: `{original_rows - len(clean_df):,}`",
        "",
        "## Exported Files",
        "",
        f"- `{cleaned_csv}`",
        f"- `{cleaned_parquet}`" if parquet_written else "- Parquet export skipped because no parquet engine is installed.",
        "",
        "## Added Analytics Fields",
        "",
        "- `placed_hour`, `placed_day`, `placed_day_name`, `placed_week`, `placed_month`, `placed_year`",
        "- `placed_time_band`: Midnight, Morning, Lunch, Afternoon, Evening, Night",
        "- `is_weekend`",
        "- `settlement_seconds`, `settlement_minutes`",
        "- `option_family`: Float, Drown, Combo",
        "- `stake_band`: Small, Medium, Large, Very Large",
        "- `odds_band`: Lower Odds, Medium Odds, High Odds, Very High Odds",
        "- `strategy_style`: Conservative Single, Balanced Single, High-Odds Hunter, Combo / Multi-Phase",
        "- `is_win`, `is_loss`, `roi_percent`",
        "",
        "These fields support bettor timing analysis, strategy/style segmentation, odds influence analysis, and promotion targeting.",
        "",
    ]
    summary_path.write_text("\n".join(summary), encoding="utf-8")

    print(f"Cleaned CSV: {cleaned_csv}")
    print(f"Summary: {summary_path}")
    if parquet_written:
        print(f"Cleaned Parquet: {cleaned_parquet}")


if __name__ == "__main__":
    main()
