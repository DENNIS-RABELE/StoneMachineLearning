from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


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


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def value_counts_frame(series: pd.Series, name: str, top: int = 20) -> pd.DataFrame:
    frame = series.fillna("__MISSING__").astype(str).value_counts(dropna=False).head(top)
    return frame.rename_axis(name).reset_index(name="count")


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return ""

    headers = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row[column]) for column in df.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit raw Stone Odds betting data.")
    parser.add_argument("input", type=Path, help="Path to .xlsx, .csv, or .json raw betting data.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Reports") / "raw_data_audit",
        help="Directory where audit reports will be written.",
    )
    args = parser.parse_args()

    input_path = args.input
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_path)
    elif input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    elif input_path.suffix.lower() == ".json":
        df = pd.read_json(input_path)
    else:
        raise SystemExit(f"Unsupported file type: {input_path.suffix}")

    df.columns = [str(column).strip() for column in df.columns]

    missing_columns = [column for column in EXPECTED_COLUMNS if column not in df.columns]
    extra_columns = [column for column in df.columns if column not in EXPECTED_COLUMNS]

    row_count = len(df)
    column_count = len(df.columns)

    missing_summary = (
        df.isna()
        .sum()
        .rename_axis("field")
        .reset_index(name="missing_count")
    )
    missing_summary["missing_percent"] = (
        missing_summary["missing_count"] / row_count * 100 if row_count else 0
    ).round(2)
    missing_summary = missing_summary.sort_values(
        ["missing_count", "field"], ascending=[False, True]
    )

    for column in ["placed_at", "settled_at"]:
        if column in df.columns:
            df[f"{column}_parsed"] = pd.to_datetime(df[column], errors="coerce")

    for column in ["stake", "odds", "payout_amount", "profit"]:
        if column in df.columns:
            df[f"{column}_numeric"] = pd.to_numeric(df[column], errors="coerce")

    invalid_dates = {}
    for column in ["placed_at", "settled_at"]:
        if column in df.columns:
            raw_present = df[column].notna()
            parsed_missing = df[f"{column}_parsed"].isna()
            invalid_dates[column] = int((raw_present & parsed_missing).sum())

    invalid_numeric = {}
    for column in ["stake", "odds", "payout_amount", "profit"]:
        if column in df.columns:
            raw_present = df[column].notna()
            parsed_missing = df[f"{column}_numeric"].isna()
            invalid_numeric[column] = int((raw_present & parsed_missing).sum())

    business_rule_failures = {
        "stake_lte_0": int((df.get("stake_numeric", pd.Series(dtype=float)) <= 0).sum()),
        "odds_lte_1": int((df.get("odds_numeric", pd.Series(dtype=float)) <= 1).sum()),
        "payout_lt_0": int((df.get("payout_amount_numeric", pd.Series(dtype=float)) < 0).sum()),
    }

    duplicate_by_bet_id = 0
    if "bet_id" in df.columns:
        duplicate_by_bet_id = int(df.duplicated(subset=["bet_id"], keep=False).sum())

    event_key = [
        column
        for column in [
            "player_id",
            "slip_id",
            "game_round_pk",
            "character_id",
            "option_code",
            "stake",
            "odds",
            "placed_at",
        ]
        if column in df.columns
    ]
    duplicate_by_event_key = (
        int(df.duplicated(subset=event_key, keep=False).sum()) if event_key else 0
    )

    usable_mask = pd.Series(True, index=df.index)
    for column in ["bet_id", "player_id", "option_code", "bet_type"]:
        if column in df.columns:
            usable_mask &= df[column].notna()
    if "placed_at_parsed" in df.columns:
        usable_mask &= df["placed_at_parsed"].notna()
    if "stake_numeric" in df.columns:
        usable_mask &= df["stake_numeric"].notna() & (df["stake_numeric"] > 0)
    if "odds_numeric" in df.columns:
        usable_mask &= df["odds_numeric"].notna() & (df["odds_numeric"] > 1)
    usable_rows = int(usable_mask.sum())

    if "placed_at_parsed" in df.columns:
        placed = df["placed_at_parsed"]
        df["placed_hour"] = placed.dt.hour
        df["placed_date"] = placed.dt.date
        df["placed_week"] = placed.dt.strftime("%G-W%V")
        df["placed_month"] = placed.dt.to_period("M").astype(str)
        df["placed_year"] = placed.dt.year
        df["placed_day_name"] = placed.dt.day_name()
        df["placed_time_band"] = df["placed_hour"].apply(classify_time_band)

    profile_summary = {
        "unique_players": int(df["player_id"].nunique()) if "player_id" in df.columns else 0,
        "unique_slips": int(df["slip_id"].nunique()) if "slip_id" in df.columns else 0,
        "unique_bets": int(df["bet_id"].nunique()) if "bet_id" in df.columns else 0,
        "placed_min": str(df["placed_at_parsed"].min()) if "placed_at_parsed" in df.columns else "",
        "placed_max": str(df["placed_at_parsed"].max()) if "placed_at_parsed" in df.columns else "",
        "settled_min": str(df["settled_at_parsed"].min()) if "settled_at_parsed" in df.columns else "",
        "settled_max": str(df["settled_at_parsed"].max()) if "settled_at_parsed" in df.columns else "",
    }
    for column in ["stake", "odds", "payout_amount", "profit"]:
        numeric_column = f"{column}_numeric"
        if numeric_column in df.columns:
            profile_summary[f"{column}_min"] = round(float(df[numeric_column].min()), 2)
            profile_summary[f"{column}_max"] = round(float(df[numeric_column].max()), 2)
            profile_summary[f"{column}_avg"] = round(float(df[numeric_column].mean()), 2)
            profile_summary[f"{column}_sum"] = round(float(df[numeric_column].sum()), 2)

    if "placed_at_parsed" in df.columns and "settled_at_parsed" in df.columns:
        settlement_seconds = (
            df["settled_at_parsed"] - df["placed_at_parsed"]
        ).dt.total_seconds()
        profile_summary["settlement_seconds_avg"] = round(float(settlement_seconds.mean()), 2)
        profile_summary["settlement_seconds_max"] = round(float(settlement_seconds.max()), 2)

    summary_tables = {
        "missing_values.csv": missing_summary,
    }
    if "option_code" in df.columns:
        summary_tables["top_option_codes.csv"] = value_counts_frame(df["option_code"], "option_code", 30)
    if "bet_type" in df.columns:
        summary_tables["bet_type_counts.csv"] = value_counts_frame(df["bet_type"], "bet_type", 30)
    if "settlement_result" in df.columns:
        summary_tables["settlement_result_counts.csv"] = value_counts_frame(
            df["settlement_result"], "settlement_result", 30
        )
    if "bet_status" in df.columns:
        summary_tables["bet_status_counts.csv"] = value_counts_frame(df["bet_status"], "bet_status", 30)
    if "character_name" in df.columns:
        summary_tables["top_characters.csv"] = value_counts_frame(df["character_name"], "character_name", 30)

    if "placed_hour" in df.columns:
        summary_tables["bets_by_hour.csv"] = (
            df.groupby("placed_hour", dropna=False).size().rename("bet_count").reset_index()
        )
        time_band_order = ["Midnight", "Morning", "Lunch", "Afternoon", "Evening", "Night"]
        time_band_counts = (
            df.groupby("placed_time_band", dropna=False).size().rename("bet_count").reset_index()
        )
        time_band_counts = (
            pd.DataFrame({"placed_time_band": time_band_order})
            .merge(time_band_counts, on="placed_time_band", how="left")
            .fillna({"bet_count": 0})
        )
        time_band_counts["bet_count"] = time_band_counts["bet_count"].astype(int)
        summary_tables["bets_by_time_band.csv"] = time_band_counts
        summary_tables["bets_by_day.csv"] = (
            df.groupby("placed_date", dropna=False).size().rename("bet_count").reset_index()
        )
        summary_tables["bets_by_week.csv"] = (
            df.groupby("placed_week", dropna=False).size().rename("bet_count").reset_index()
        )
        summary_tables["bets_by_month.csv"] = (
            df.groupby("placed_month", dropna=False).size().rename("bet_count").reset_index()
        )
        summary_tables["bets_by_year.csv"] = (
            df.groupby("placed_year", dropna=False).size().rename("bet_count").reset_index()
        )
        summary_tables["day_hour_heatmap.csv"] = (
            df.groupby(["placed_day_name", "placed_hour"], dropna=False)
            .size()
            .rename("bet_count")
            .reset_index()
        )

    for filename, table in summary_tables.items():
        write_csv(table, output_dir / filename)

    report_path = output_dir / "audit_report.md"
    usable_percent = round((usable_rows / row_count * 100), 2) if row_count else 0

    top_options = summary_tables.get("top_option_codes.csv", pd.DataFrame()).head(10)
    top_bands = summary_tables.get("bets_by_time_band.csv", pd.DataFrame()).sort_values(
        "bet_count", ascending=False
    ) if "bets_by_time_band.csv" in summary_tables else pd.DataFrame()

    report = [
        "# Raw Betting Data Audit",
        "",
        f"Input file: `{input_path}`",
        f"Rows: `{row_count:,}`",
        f"Columns: `{column_count:,}`",
        f"Usable rows for first-pass ML analytics: `{usable_rows:,}` (`{usable_percent}%`)",
        "",
        "## Schema Check",
        "",
        f"Missing expected columns: `{', '.join(missing_columns) if missing_columns else 'None'}`",
        f"Extra columns: `{', '.join(extra_columns) if extra_columns else 'None'}`",
        "",
        "## Date And Number Quality",
        "",
        *[f"- Invalid `{column}` values: `{count:,}`" for column, count in invalid_dates.items()],
        *[f"- Invalid numeric `{column}` values: `{count:,}`" for column, count in invalid_numeric.items()],
        *[f"- Business rule failure `{name}`: `{count:,}`" for name, count in business_rule_failures.items()],
        "",
        "## Dataset Profile",
        "",
        f"- Unique players: `{profile_summary['unique_players']:,}`",
        f"- Unique slips: `{profile_summary['unique_slips']:,}`",
        f"- Unique bets: `{profile_summary['unique_bets']:,}`",
        f"- Placed range: `{profile_summary['placed_min']}` to `{profile_summary['placed_max']}`",
        f"- Settled range: `{profile_summary['settled_min']}` to `{profile_summary['settled_max']}`",
        f"- Stake range: `{profile_summary.get('stake_min', 0):,}` to `{profile_summary.get('stake_max', 0):,}`, average `{profile_summary.get('stake_avg', 0):,}`",
        f"- Odds range: `{profile_summary.get('odds_min', 0):,}` to `{profile_summary.get('odds_max', 0):,}`, average `{profile_summary.get('odds_avg', 0):,}`",
        f"- Total payout: `{profile_summary.get('payout_amount_sum', 0):,}`",
        f"- Total profit: `{profile_summary.get('profit_sum', 0):,}`",
        f"- Average settlement time: `{profile_summary.get('settlement_seconds_avg', 0):,}` seconds",
        f"- Maximum settlement time: `{profile_summary.get('settlement_seconds_max', 0):,}` seconds",
        "",
        "## Duplicate Signals",
        "",
        f"- Rows sharing a repeated `bet_id`: `{duplicate_by_bet_id:,}`",
        f"- Rows sharing the event key `{', '.join(event_key)}`: `{duplicate_by_event_key:,}`",
        "",
        "Repeated `option_code` values are treated as popularity/frequency signals, not duplicates.",
        "",
        "## Top Option Codes",
        "",
        markdown_table(top_options) if not top_options.empty else "No option_code data found.",
        "",
        "## Bets By Time Band",
        "",
        markdown_table(top_bands) if not top_bands.empty else "No placed_at data found.",
        "",
        "## Output Tables",
        "",
    ]
    report.extend(f"- `{filename}`" for filename in sorted(summary_tables))
    report.append("")
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"Audit complete: {report_path}")


if __name__ == "__main__":
    main()
