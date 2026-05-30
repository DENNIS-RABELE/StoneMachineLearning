from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TIME_BAND_ORDER = ["Midnight", "Morning", "Lunch", "Afternoon", "Evening", "Night"]


def top_value(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return "Unknown"
    return str(values.value_counts().idxmax())


def top_share(series: pd.Series) -> float:
    values = series.dropna()
    if values.empty:
        return 0.0
    counts = values.value_counts()
    return round(float(counts.iloc[0] / len(values)), 4)


def percent(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return round(float(numerator / denominator * 100), 2)


def promotion_hint(row: pd.Series) -> str:
    if row["total_bets"] < 10:
        return "New / Low History"
    if row["combo_bet_rate"] >= 65:
        return "Accumulator Insurance / Combo Boost"
    if row["high_odds_rate"] >= 60:
        return "High Odds Boost"
    if row["night_bet_rate"] >= 45:
        return "Night-Time Campaign"
    if row["weekend_bet_rate"] >= 60:
        return "Weekend Campaign"
    if row["average_stake"] >= 250:
        return "High-Value Offer"
    if row["win_rate"] < 35 and row["roi_percent"] < -30:
        return "Retention / Safer Play"
    return "General Personalized Offer"


def risk_hint(row: pd.Series) -> str:
    risk_points = 0
    if row["night_bet_rate"] >= 50:
        risk_points += 1
    if row["high_odds_rate"] >= 60:
        risk_points += 1
    if row["average_stake"] >= 250:
        risk_points += 1
    if row["stake_volatility"] >= 150:
        risk_points += 1
    if row["loss_rate"] >= 65:
        risk_points += 1

    if risk_points >= 3:
        return "High"
    if risk_points == 2:
        return "Medium"
    return "Low"


def build_profiles(cleaned_path: Path) -> pd.DataFrame:
    df = pd.read_csv(cleaned_path, parse_dates=["placed_at", "settled_at"])
    required = {
        "player_id",
        "bet_id",
        "stake",
        "odds",
        "profit",
        "payout_amount",
        "is_win",
        "is_loss",
        "is_combo_bet",
        "placed_hour",
        "placed_day_name",
        "placed_time_band",
        "is_weekend",
        "option_code",
        "option_family",
        "stake_band",
        "odds_band",
        "strategy_style",
        "settlement_seconds",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise SystemExit(f"Cleaned dataset is missing required columns: {', '.join(missing)}")

    bool_columns = ["is_win", "is_loss", "is_combo_bet", "is_weekend"]
    for column in bool_columns:
        if df[column].dtype == object:
            df[column] = df[column].astype(str).str.lower().isin(["true", "1", "yes"])

    grouped = df.groupby("player_id", dropna=False)

    profiles = grouped.agg(
        total_bets=("bet_id", "count"),
        unique_slips=("slip_id", "nunique"),
        active_days=("placed_date", "nunique"),
        first_bet_at=("placed_at", "min"),
        last_bet_at=("placed_at", "max"),
        total_stake=("stake", "sum"),
        average_stake=("stake", "mean"),
        median_stake=("stake", "median"),
        max_stake=("stake", "max"),
        min_stake=("stake", "min"),
        stake_volatility=("stake", "std"),
        average_odds=("odds", "mean"),
        max_odds=("odds", "max"),
        min_odds=("odds", "min"),
        total_payout=("payout_amount", "sum"),
        total_profit=("profit", "sum"),
        wins=("is_win", "sum"),
        losses=("is_loss", "sum"),
        combo_bets=("is_combo_bet", "sum"),
        weekend_bets=("is_weekend", "sum"),
        average_settlement_seconds=("settlement_seconds", "mean"),
    ).reset_index()

    profiles["stake_volatility"] = profiles["stake_volatility"].fillna(0)
    profiles["win_rate"] = profiles.apply(lambda row: percent(row["wins"], row["total_bets"]), axis=1)
    profiles["loss_rate"] = profiles.apply(lambda row: percent(row["losses"], row["total_bets"]), axis=1)
    profiles["combo_bet_rate"] = profiles.apply(lambda row: percent(row["combo_bets"], row["total_bets"]), axis=1)
    profiles["weekend_bet_rate"] = profiles.apply(lambda row: percent(row["weekend_bets"], row["total_bets"]), axis=1)
    profiles["roi_percent"] = profiles.apply(lambda row: percent(row["total_profit"], row["total_stake"]), axis=1)
    profiles["bets_per_active_day"] = profiles.apply(lambda row: round(row["total_bets"] / row["active_days"], 2) if row["active_days"] else 0, axis=1)

    preference_frames = []
    for player_id, group in grouped:
        high_odds_bets = group["odds_band"].isin(["High Odds", "Very High Odds"]).sum()
        night_bets = group["placed_time_band"].isin(["Night", "Midnight"]).sum()
        total_bets = len(group)
        preference_frames.append(
            {
                "player_id": player_id,
                "favorite_time_band": top_value(group["placed_time_band"]),
                "favorite_time_band_share": top_share(group["placed_time_band"]),
                "favorite_hour": int(group["placed_hour"].mode().iloc[0]) if not group["placed_hour"].mode().empty else -1,
                "favorite_day_name": top_value(group["placed_day_name"]),
                "preferred_option_code": top_value(group["option_code"]),
                "preferred_option_code_share": top_share(group["option_code"]),
                "preferred_option_family": top_value(group["option_family"]),
                "preferred_stake_band": top_value(group["stake_band"]),
                "preferred_odds_band": top_value(group["odds_band"]),
                "preferred_strategy_style": top_value(group["strategy_style"]),
                "high_odds_rate": percent(high_odds_bets, total_bets),
                "night_bet_rate": percent(night_bets, total_bets),
            }
        )

    preferences = pd.DataFrame(preference_frames)
    profiles = profiles.merge(preferences, on="player_id", how="left")

    numeric_round_columns = [
        "total_stake",
        "average_stake",
        "median_stake",
        "max_stake",
        "min_stake",
        "stake_volatility",
        "average_odds",
        "max_odds",
        "min_odds",
        "total_payout",
        "total_profit",
        "average_settlement_seconds",
    ]
    for column in numeric_round_columns:
        profiles[column] = profiles[column].round(2)

    profiles["promotion_targeting_signal"] = profiles.apply(promotion_hint, axis=1)
    profiles["responsible_gambling_risk_hint"] = profiles.apply(risk_hint, axis=1)

    sort_columns = ["total_stake", "total_bets", "player_id"]
    return profiles.sort_values(sort_columns, ascending=[False, False, True])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bettor-level analytics profiles.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("Data") / "cleaned" / "cleaned_bets.csv",
        help="Cleaned bet-level CSV produced by clean_betting_data.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Data") / "profiles",
        help="Directory where bettor profile outputs will be written.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    profiles = build_profiles(args.input)

    profile_csv = args.output_dir / "bettor_profiles.csv"
    summary_md = args.output_dir / "bettor_profiles_summary.md"
    profiles.to_csv(profile_csv, index=False)

    top_promotions = (
        profiles["promotion_targeting_signal"]
        .value_counts()
        .rename_axis("promotion_targeting_signal")
        .reset_index(name="bettor_count")
    )
    top_strategies = (
        profiles["preferred_strategy_style"]
        .value_counts()
        .rename_axis("preferred_strategy_style")
        .reset_index(name="bettor_count")
    )
    top_time_bands = (
        pd.DataFrame({"favorite_time_band": TIME_BAND_ORDER})
        .merge(
            profiles["favorite_time_band"]
            .value_counts()
            .rename_axis("favorite_time_band")
            .reset_index(name="bettor_count"),
            on="favorite_time_band",
            how="left",
        )
        .fillna({"bettor_count": 0})
    )
    top_time_bands["bettor_count"] = top_time_bands["bettor_count"].astype(int)
    risk_counts = (
        profiles["responsible_gambling_risk_hint"]
        .value_counts()
        .rename_axis("responsible_gambling_risk_hint")
        .reset_index(name="bettor_count")
    )

    top_promotions.to_csv(args.output_dir / "promotion_signal_counts.csv", index=False)
    top_strategies.to_csv(args.output_dir / "preferred_strategy_counts.csv", index=False)
    top_time_bands.to_csv(args.output_dir / "favorite_time_band_counts.csv", index=False)
    risk_counts.to_csv(args.output_dir / "risk_hint_counts.csv", index=False)

    summary = [
        "# Bettor-Level Profiles",
        "",
        f"Input file: `{args.input}`",
        f"Profile rows: `{len(profiles):,}`",
        f"Output file: `{profile_csv}`",
        "",
        "## What This Dataset Is For",
        "",
        "Each row summarizes one bettor. These features are ready for admin analytics and later ML clustering.",
        "",
        "## Core Feature Groups",
        "",
        "- Timing: favorite time band, favorite hour, favorite day, weekend rate, night rate",
        "- Strategy: preferred strategy style, option family, combo rate, preferred option code",
        "- Value: total stake, average stake, payout, profit, ROI",
        "- Odds behavior: average odds, preferred odds band, high odds rate",
        "- Outcome behavior: win rate and loss rate",
        "- Promotion support: promotion targeting signal",
        "- Safety support: responsible gambling risk hint",
        "",
        "## Promotion Signals",
        "",
        top_promotions.to_string(index=False),
        "",
        "## Preferred Strategy Styles",
        "",
        top_strategies.to_string(index=False),
        "",
        "## Favorite Time Bands",
        "",
        top_time_bands.to_string(index=False),
        "",
        "## Responsible Gambling Risk Hints",
        "",
        risk_counts.to_string(index=False),
        "",
    ]
    summary_md.write_text("\n".join(summary), encoding="utf-8")

    print(f"Bettor profiles: {profile_csv}")
    print(f"Summary: {summary_md}")


if __name__ == "__main__":
    main()
