import csv
import time
import logging
import jwt
from functools import lru_cache, wraps
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
from django.contrib import admin
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.views import redirect_to_login
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.core.exceptions import SuspiciousOperation

from gateway import views as gateway_views
from .models import SupportEnquiry
from .support_auth import user_is_customer_support

logger = logging.getLogger(__name__)

TIME_BAND_ORDER = ["Midnight", "Morning", "Lunch", "Afternoon", "Evening", "Night"]
DAY_NAME_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
REPORTING_CUTOFF_AT = pd.Timestamp("2026-04-30 23:59:59.999999")
REPORTING_CUTOFF_DATE = REPORTING_CUTOFF_AT.normalize()
REPORTING_CUTOFF_LABEL = "30 April 2026"
TIME_BAND_COLORS = {
    "Midnight": "#3b4cc0",
    "Morning": "#138a55",
    "Lunch": "#d69f00",
    "Afternoon": "#e76f51",
    "Evening": "#1167b1",
    "Night": "#6f4bb2",
}
REPORT_METRICS = {
    "bet_count": {"label": "Bet Count", "color": "#1167b1", "decimals": 0},
    "unique_bettors": {"label": "Active Bettors", "color": "#1f8a70", "decimals": 0},
    "total_stake": {"label": "Total Stake", "color": "#138a55", "decimals": 2},
    "total_payout": {"label": "Total Payout", "color": "#d69f00", "decimals": 2},
    "total_profit": {"label": "Total Profit", "color": "#e76f51", "decimals": 2},
    "avg_odds": {"label": "Average Odds", "color": "#6f4bb2", "decimals": 2},
    "roi_percent": {"label": "ROI", "color": "#0f766e", "decimals": 2, "suffix": "%"},
    "win_rate": {"label": "Win Rate", "color": "#ba2c2c", "decimals": 2, "suffix": "%"},
}


def _repo_root():
    """Return the Stone Odds repo root from the admin_portal service path."""
    return Path(settings.BASE_DIR).resolve().parents[2]


def _model_output_dir():
    return _repo_root() / "Data" / "models" / "bettor_segmentation"


def _cleaned_bets_path():
    return _repo_root() / "Data" / "cleaned" / "cleaned_bets.csv"


def _time_band_for_hour(hour):
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


def _format_compact_number(value, decimals=0):
    value = float(value)
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.1f}K"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def _format_date_window(start_at, end_at):
    if pd.isna(start_at) or pd.isna(end_at):
        return "No betting window available"
    return f"{start_at:%b %d, %Y} to {end_at:%b %d, %Y}"


def _empty_betting_activity_payload(df, excluded_after_cutoff=0):
    return {
        "report_window": "No betting window available",
        "report_cutoff": REPORTING_CUTOFF_LABEL,
        "excluded_after_cutoff": int(excluded_after_cutoff),
        "overview_cards": _overview_cards(df),
        "metric_meta": REPORT_METRICS,
        "time_band_order": TIME_BAND_ORDER,
        "time_band_colors": TIME_BAND_COLORS,
        "calendar": {
            "start_date": None,
            "end_date": None,
            "cutoff_date": REPORTING_CUTOFF_DATE.strftime("%Y-%m-%d"),
            "cutoff_label": REPORTING_CUTOFF_LABEL,
        },
        "hourly": {
            "metrics": [],
            "heatmap": {
                "days": DAY_NAME_ORDER,
                "hours": [],
                "values": [],
                "values_by_metric": {metric_key: [] for metric_key in REPORT_METRICS},
            },
        },
        "daily": {"metrics": [], "time_bands": [], "time_band_metrics_by_date": {}, "hourly_by_date": {}},
        "weekly": {"metrics": [], "time_bands": [], "time_band_metrics_by_start": {}},
        "monthly": {"metrics": [], "time_bands": [], "time_band_metrics_by_month": {}},
        "annual": {"metrics": [], "time_bands": []},
    }


def _overview_cards(df):
    total_bets = int(len(df))
    active_bettors = int(df["player_id"].nunique()) if not df.empty else 0
    total_stake = float(df["stake"].sum()) if not df.empty else 0.0
    total_profit = float(df["profit"].sum()) if not df.empty else 0.0
    avg_odds = float(df["odds"].mean()) if not df.empty else 0.0
    roi_percent = (total_profit / total_stake * 100) if total_stake else 0.0
    win_rate = float(df["is_win"].mean() * 100) if not df.empty else 0.0
    return [
        {"label": "Bet Tickets", "value": f"{total_bets:,}", "note": "Cleaned tickets in the reporting dataset"},
        {"label": "Active Bettors", "value": f"{active_bettors:,}", "note": "Unique player IDs across the window"},
        {"label": "Total Stake", "value": _format_compact_number(total_stake, 2), "note": "Summed stake across every ticket"},
        {"label": "Total Profit", "value": _format_compact_number(total_profit, 2), "note": "Net profit recorded in the file"},
        {"label": "Average Odds", "value": f"{avg_odds:.2f}", "note": "Mean odds across all tickets"},
        {"label": "ROI", "value": f"{roi_percent:.2f}%", "note": "Total profit divided by total stake"},
        {"label": "Win Rate", "value": f"{win_rate:.2f}%", "note": "Percentage of tickets settled as wins"},
    ]


def _serialize_metric_rows(frame, label_formatter, key_name="label", include_hour_band=False, extra_serializer=None):
    records = []
    for _, row in frame.iterrows():
        label = label_formatter(row[key_name])
        record = {
            "label": label,
            "bet_count": int(row["bet_count"]),
            "unique_bettors": int(row["unique_bettors"]),
            "total_stake": round(float(row["total_stake"]), 2),
            "total_payout": round(float(row["total_payout"]), 2),
            "total_profit": round(float(row["total_profit"]), 2),
            "avg_odds": round(float(row["avg_odds"]), 2),
            "roi_percent": round(float(row["roi_percent"]), 2),
            "win_rate": round(float(row["win_rate"]), 2),
        }
        if include_hour_band:
            band = _time_band_for_hour(row[key_name])
            record["time_band"] = band
            record["color"] = TIME_BAND_COLORS.get(band, "#637083")
        if extra_serializer:
            record.update(extra_serializer(row))
        records.append(record)
    return records


def _aggregate_metric_frame(df, group_field, ordered_index):
    grouped = (
        df.groupby(group_field)
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(ordered_index, fill_value=0)
    grouped.index.name = group_field
    grouped = grouped.reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"] * 100).round(2)
    return grouped


def _aggregate_time_band_rows(df, group_field, ordered_index, label_formatter, extra_serializer=None):
    counts = (
        df[df["placed_time_band"].isin(TIME_BAND_ORDER)]
        .groupby([group_field, "placed_time_band"])
        .size()
        .unstack(fill_value=0)
    )
    counts = counts.reindex(index=ordered_index, columns=TIME_BAND_ORDER, fill_value=0)
    counts.index.name = group_field
    counts = counts.reset_index()
    rows = []
    for _, row in counts.iterrows():
        record = {
            "label": label_formatter(row[group_field]),
            **{band: int(row.get(band, 0)) for band in TIME_BAND_ORDER},
        }
        if extra_serializer:
            record.update(extra_serializer(row))
        rows.append(record)
    return rows


def _aggregate_daily_time_band_metric_rows(df, ordered_dates):
    band_index = pd.MultiIndex.from_product(
        [ordered_dates, TIME_BAND_ORDER],
        names=["placed_date", "placed_time_band"],
    )
    grouped = (
        df[df["placed_time_band"].isin(TIME_BAND_ORDER)]
        .groupby(["placed_date", "placed_time_band"])
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(band_index, fill_value=0).reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].fillna(0).round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"].fillna(0) * 100).round(2)

    by_date = {}
    for date_value, date_rows in grouped.groupby("placed_date", sort=False):
        date_key = pd.Timestamp(date_value).strftime("%Y-%m-%d")
        metric_rows = _serialize_metric_rows(
            date_rows.rename(columns={"placed_time_band": "label"}),
            lambda value: str(value),
        )
        for record in metric_rows:
            record["color"] = TIME_BAND_COLORS.get(record["label"], "#637083")
        by_date[date_key] = metric_rows
    return by_date


def _aggregate_weekly_time_band_metric_rows(df, ordered_weeks):
    band_index = pd.MultiIndex.from_product(
        [ordered_weeks, TIME_BAND_ORDER],
        names=["week_start", "placed_time_band"],
    )
    grouped = (
        df[df["placed_time_band"].isin(TIME_BAND_ORDER)]
        .groupby(["week_start", "placed_time_band"])
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(band_index, fill_value=0).reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].fillna(0).round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"].fillna(0) * 100).round(2)

    by_week = {}
    for week_value, week_rows in grouped.groupby("week_start", sort=False):
        week_key = pd.Timestamp(week_value).strftime("%Y-%m-%d")
        metric_rows = _serialize_metric_rows(
            week_rows.rename(columns={"placed_time_band": "label"}),
            lambda value: str(value),
        )
        for record in metric_rows:
            record["color"] = TIME_BAND_COLORS.get(record["label"], "#637083")
        by_week[week_key] = metric_rows
    return by_week


def _aggregate_monthly_time_band_metric_rows(df, ordered_months):
    band_index = pd.MultiIndex.from_product(
        [ordered_months, TIME_BAND_ORDER],
        names=["month_start", "placed_time_band"],
    )
    grouped = (
        df[df["placed_time_band"].isin(TIME_BAND_ORDER)]
        .groupby(["month_start", "placed_time_band"])
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(band_index, fill_value=0).reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].fillna(0).round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"].fillna(0) * 100).round(2)

    by_month = {}
    for month_value, month_rows in grouped.groupby("month_start", sort=False):
        month_key = pd.Timestamp(month_value).strftime("%Y-%m")
        metric_rows = _serialize_metric_rows(
            month_rows.rename(columns={"placed_time_band": "label"}),
            lambda value: str(value),
        )
        for record in metric_rows:
            record["color"] = TIME_BAND_COLORS.get(record["label"], "#637083")
        by_month[month_key] = metric_rows
    return by_month


def _aggregate_hourly_by_date_rows(df, ordered_dates):
    hourly_index = pd.MultiIndex.from_product(
        [ordered_dates, list(range(24))],
        names=["placed_date", "placed_hour"],
    )
    grouped = (
        df.groupby(["placed_date", "placed_hour"])
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(hourly_index, fill_value=0).reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].fillna(0).round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"].fillna(0) * 100).round(2)

    by_date = {}
    for date_value, date_rows in grouped.groupby("placed_date", sort=False):
        date_key = pd.Timestamp(date_value).strftime("%Y-%m-%d")
        date_rows = date_rows.rename(columns={"placed_hour": "label"})
        by_date[date_key] = _serialize_metric_rows(
            date_rows,
            lambda value: f"{int(value):02d}:00",
            include_hour_band=True,
        )
    return by_date


def _daily_metric_meta(row):
    date_value = pd.Timestamp(row["label"])
    return {
        "date_key": date_value.strftime("%Y-%m-%d"),
        "day_name": date_value.strftime("%A"),
        "day_number": int(date_value.day),
        "month_key": date_value.strftime("%Y-%m"),
        "month_label": date_value.strftime("%B %Y"),
    }


def _daily_band_meta(row):
    date_value = pd.Timestamp(row["placed_date"])
    return {
        "date_key": date_value.strftime("%Y-%m-%d"),
        "day_name": date_value.strftime("%A"),
        "day_number": int(date_value.day),
        "month_key": date_value.strftime("%Y-%m"),
        "month_label": date_value.strftime("%B %Y"),
    }


def _weekly_label(value):
    week_start = pd.Timestamp(value)
    week_end = min(week_start + pd.Timedelta(days=6), REPORTING_CUTOFF_DATE)
    if week_start.year == week_end.year:
        return f"{week_start:%b %d} - {week_end:%b %d, %Y}"
    return f"{week_start:%b %d, %Y} - {week_end:%b %d, %Y}"


def _weekly_metric_meta(row):
    week_start = pd.Timestamp(row["label"])
    week_end = min(week_start + pd.Timedelta(days=6), REPORTING_CUTOFF_DATE)
    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "iso_label": f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}",
        "month_key": week_start.strftime("%Y-%m"),
        "month_label": week_start.strftime("%B %Y"),
    }


def _weekly_band_meta(row):
    week_start = pd.Timestamp(row["week_start"])
    week_end = min(week_start + pd.Timedelta(days=6), REPORTING_CUTOFF_DATE)
    return {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "iso_label": f"{week_start.isocalendar().year}-W{week_start.isocalendar().week:02d}",
        "month_key": week_start.strftime("%Y-%m"),
        "month_label": week_start.strftime("%B %Y"),
    }


def _monthly_metric_meta(row):
    month_start = pd.Timestamp(row["label"])
    return {
        "month_key": month_start.strftime("%Y-%m"),
        "year_key": month_start.strftime("%Y"),
        "month_number": month_start.strftime("%m"),
        "month_name": month_start.strftime("%B"),
    }


def _hourly_heatmap_payload(df):
    hourly_index = pd.MultiIndex.from_product(
        [DAY_NAME_ORDER, list(range(24))],
        names=["placed_day_name", "placed_hour"],
    )
    grouped = (
        df.groupby(["placed_day_name", "placed_hour"])
        .agg(
            bet_count=("player_id", "size"),
            unique_bettors=("player_id", "nunique"),
            total_stake=("stake", "sum"),
            total_payout=("payout_amount", "sum"),
            total_profit=("profit", "sum"),
            avg_odds=("odds", "mean"),
            win_rate=("is_win", "mean"),
        )
    )
    grouped = grouped.reindex(hourly_index, fill_value=0).reset_index()
    grouped["avg_odds"] = grouped["avg_odds"].fillna(0).round(2)
    grouped["roi_percent"] = (
        grouped["total_profit"].div(grouped["total_stake"].where(grouped["total_stake"].ne(0))).fillna(0) * 100
    ).round(2)
    grouped["win_rate"] = (grouped["win_rate"].fillna(0) * 100).round(2)

    values_by_metric = {}
    for metric_key, meta in REPORT_METRICS.items():
        matrix = (
            grouped.pivot(index="placed_day_name", columns="placed_hour", values=metric_key)
            .reindex(index=DAY_NAME_ORDER, columns=list(range(24)), fill_value=0)
        )
        decimals = int(meta.get("decimals", 0))
        values_by_metric[metric_key] = [
            [round(float(value), decimals) for value in row]
            for row in matrix.to_numpy().tolist()
        ]

    return {
        "days": DAY_NAME_ORDER,
        "hours": [f"{hour:02d}:00" for hour in range(24)],
        "values": values_by_metric["bet_count"],
        "values_by_metric": values_by_metric,
    }


@lru_cache(maxsize=2)
def _betting_activity_payload(cleaned_path_str, modified_ns):
    usecols = ["player_id", "stake", "payout_amount", "profit", "odds", "is_win", "placed_at"]
    df = pd.read_csv(cleaned_path_str, usecols=usecols, parse_dates=["placed_at"])
    if df.empty:
        return _empty_betting_activity_payload(df)

    df["stake"] = pd.to_numeric(df["stake"], errors="coerce").fillna(0.0)
    df["payout_amount"] = pd.to_numeric(df["payout_amount"], errors="coerce").fillna(0.0)
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0.0)
    df["odds"] = pd.to_numeric(df["odds"], errors="coerce").fillna(0.0)
    df["is_win"] = df["is_win"].astype(str).str.lower().isin(["true", "1", "yes"])
    df = df[df["placed_at"].notna()].copy()
    excluded_after_cutoff = int(df["placed_at"].gt(REPORTING_CUTOFF_AT).sum())
    df = df[df["placed_at"].le(REPORTING_CUTOFF_AT)].copy()
    if df.empty:
        return _empty_betting_activity_payload(df, excluded_after_cutoff)

    df["placed_hour"] = df["placed_at"].dt.hour
    df["placed_date"] = df["placed_at"].dt.normalize()
    df["placed_day_name"] = df["placed_at"].dt.day_name()
    df["week_start"] = df["placed_at"].dt.to_period("W-SUN").dt.start_time
    df["month_start"] = df["placed_at"].dt.to_period("M").dt.start_time
    df["year_start"] = df["placed_at"].dt.to_period("Y").dt.start_time
    df["placed_time_band"] = df["placed_hour"].apply(_time_band_for_hour)

    date_start = df["placed_date"].min()
    date_end = df["placed_date"].max()
    week_start = df["week_start"].min()
    week_end = df["week_start"].max()
    month_start = df["month_start"].min()
    month_end = df["month_start"].max()
    year_start = df["year_start"].min()
    year_end = df["year_start"].max()

    hourly_index = list(range(24))
    daily_index = pd.date_range(date_start, date_end, freq="D")
    weekly_index = pd.date_range(week_start, week_end, freq="7D")
    monthly_index = pd.date_range(month_start, month_end, freq="MS")
    annual_index = pd.date_range(year_start, year_end, freq="YS")

    hourly_frame = _aggregate_metric_frame(df, "placed_hour", hourly_index).rename(columns={"placed_hour": "label"})
    daily_frame = _aggregate_metric_frame(df, "placed_date", daily_index).rename(columns={"placed_date": "label"})
    weekly_frame = _aggregate_metric_frame(df, "week_start", weekly_index).rename(columns={"week_start": "label"})
    monthly_frame = _aggregate_metric_frame(df, "month_start", monthly_index).rename(columns={"month_start": "label"})
    annual_frame = _aggregate_metric_frame(df, "year_start", annual_index).rename(columns={"year_start": "label"})

    payload = {
        "report_window": _format_date_window(df["placed_at"].min(), df["placed_at"].max()),
        "report_cutoff": REPORTING_CUTOFF_LABEL,
        "excluded_after_cutoff": excluded_after_cutoff,
        "overview_cards": _overview_cards(df),
        "metric_meta": REPORT_METRICS,
        "time_band_order": TIME_BAND_ORDER,
        "time_band_colors": TIME_BAND_COLORS,
        "calendar": {
            "start_date": pd.Timestamp(date_start).strftime("%Y-%m-%d"),
            "end_date": pd.Timestamp(date_end).strftime("%Y-%m-%d"),
            "cutoff_date": REPORTING_CUTOFF_DATE.strftime("%Y-%m-%d"),
            "cutoff_label": REPORTING_CUTOFF_LABEL,
        },
        "hourly": {
            "metrics": _serialize_metric_rows(hourly_frame, lambda value: f"{int(value):02d}:00", include_hour_band=True),
            "heatmap": _hourly_heatmap_payload(df),
        },
        "daily": {
            "metrics": _serialize_metric_rows(
                daily_frame,
                lambda value: value.strftime("%b %d, %Y"),
                extra_serializer=_daily_metric_meta,
            ),
            "time_bands": _aggregate_time_band_rows(
                df,
                "placed_date",
                daily_index,
                lambda value: value.strftime("%b %d, %Y"),
                extra_serializer=_daily_band_meta,
            ),
            "time_band_metrics_by_date": _aggregate_daily_time_band_metric_rows(df, daily_index),
            "hourly_by_date": _aggregate_hourly_by_date_rows(df, daily_index),
        },
        "weekly": {
            "metrics": _serialize_metric_rows(
                weekly_frame,
                _weekly_label,
                extra_serializer=_weekly_metric_meta,
            ),
            "time_bands": _aggregate_time_band_rows(
                df,
                "week_start",
                weekly_index,
                _weekly_label,
                extra_serializer=_weekly_band_meta,
            ),
            "time_band_metrics_by_start": _aggregate_weekly_time_band_metric_rows(df, weekly_index),
        },
        "monthly": {
            "metrics": _serialize_metric_rows(
                monthly_frame,
                lambda value: value.strftime("%b %Y"),
                extra_serializer=_monthly_metric_meta,
            ),
            "time_bands": _aggregate_time_band_rows(df, "month_start", monthly_index, lambda value: value.strftime("%b %Y")),
            "time_band_metrics_by_month": _aggregate_monthly_time_band_metric_rows(df, monthly_index),
        },
        "annual": {
            "metrics": _serialize_metric_rows(annual_frame, lambda value: value.strftime("%Y")),
            "time_bands": _aggregate_time_band_rows(df, "year_start", annual_index, lambda value: value.strftime("%Y")),
        },
    }
    return payload


def _read_csv_rows(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_cluster_rows(rows):
    formatted = []
    total = sum(_as_int(row.get("cluster_size")) for row in rows) or 1
    for row in rows:
        cluster_size = _as_int(row.get("cluster_size"))
        formatted.append(
            {
                **row,
                "cluster_size": cluster_size,
                "cluster_share": round(cluster_size / total * 100, 2),
                "average_stake_mean": round(_as_float(row.get("average_stake_mean")), 2),
                "average_odds_mean": round(_as_float(row.get("average_odds_mean")), 2),
                "win_rate_mean": round(_as_float(row.get("win_rate_mean")), 2),
                "combo_bet_rate_mean": round(_as_float(row.get("combo_bet_rate_mean")), 2),
                "high_odds_rate_mean": round(_as_float(row.get("high_odds_rate_mean")), 2),
                "night_bet_rate_mean": round(_as_float(row.get("night_bet_rate_mean")), 2),
                "roi_percent_mean": round(_as_float(row.get("roi_percent_mean")), 2),
            }
        )
    return formatted


def _chart_point(row):
    return {
        "player_id": row.get("player_id"),
        "cluster_id": _as_int(row.get("cluster_id")),
        "cluster_name": row.get("cluster_name") or "Unknown",
        "cluster_confidence": round(_as_float(row.get("cluster_confidence")), 4),
        "secondary_cluster_id": _as_int(row.get("secondary_cluster_id"), -1),
        "secondary_cluster_probability": round(_as_float(row.get("secondary_cluster_probability")), 4),
        "average_stake": round(_as_float(row.get("average_stake")), 2),
        "total_stake": round(_as_float(row.get("total_stake")), 2),
        "average_odds": round(_as_float(row.get("average_odds")), 2),
        "roi_percent": round(_as_float(row.get("roi_percent")), 2),
        "win_rate": round(_as_float(row.get("win_rate")), 2),
        "loss_rate": round(_as_float(row.get("loss_rate")), 2),
        "combo_bet_rate": round(_as_float(row.get("combo_bet_rate")), 2),
        "high_odds_rate": round(_as_float(row.get("high_odds_rate")), 2),
        "night_bet_rate": round(_as_float(row.get("night_bet_rate")), 2),
        "total_bets": _as_int(row.get("total_bets")),
        "favorite_time_band": row.get("favorite_time_band") or "Unknown",
        "preferred_strategy_style": row.get("preferred_strategy_style") or "Unknown",
        "promotion_targeting_signal": row.get("promotion_targeting_signal") or "Unknown",
        "responsible_gambling_risk_hint": row.get("responsible_gambling_risk_hint") or "Unknown",
    }


# =============================================================================
# CACHED SETTINGS ACCESSORS (Efficient, thread-safe)
# =============================================================================

@lru_cache(maxsize=1)
def _get_sso_cookie_attrs():
    """Cached cookie attributes for consistent, efficient reuse."""
    return {
        'httponly': True,
        'samesite': getattr(settings, 'SSO_COOKIE_SAMESITE', 'Lax'),
        'secure': getattr(settings, 'SSO_COOKIE_SECURE', False),
        'domain': getattr(settings, 'SSO_COOKIE_DOMAIN', '') or None,
        'path': getattr(settings, 'SSO_COOKIE_PATH', '/'),
    }

@lru_cache(maxsize=1)
def _get_sso_secret():
    """Cached SSO secret key access."""
    return getattr(settings, 'SSO_SECRET', '')

@lru_cache(maxsize=1)
def _get_sso_ttl_seconds():
    """Cached SSO TTL access."""
    return getattr(settings, 'SSO_TTL_SECONDS', 3600)

@lru_cache(maxsize=1)
def _get_sso_cookie_name():
    """Cached SSO cookie name access."""
    return getattr(settings, 'SSO_COOKIE_NAME', 'admin_jwt')


# =============================================================================
# JWT HELPER (Centralized, safe, reusable)
# =============================================================================

def _create_sso_token(user):
    """
    Create SSO JWT token for authenticated user.
    Returns token string or None on error.
    """
    try:
        payload = {
            'sub': str(user.id),
            'username': user.username,
            'is_staff': getattr(user, 'is_staff', False),
            'exp': int(time.time()) + _get_sso_ttl_seconds(),
        }
        return jwt.encode(payload, _get_sso_secret(), algorithm='HS256')
    except Exception as e:
        logger.error(f"Failed to create SSO token for user {user.id}: {e}")
        return None


# =============================================================================
# CUSTOMER SUPPORT AUTH HELPERS
# =============================================================================

SUPPORT_LOGIN_URL = "/support/login/"
SUPPORT_HOME_URL = "/support/"


def _safe_support_redirect_url(request):
    redirect_url = request.POST.get("next") or request.GET.get("next") or SUPPORT_HOME_URL
    is_safe = url_has_allowed_host_and_scheme(
        redirect_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    redirect_path = urlparse(redirect_url).path
    if is_safe and (redirect_path == "/support" or redirect_path.startswith(SUPPORT_HOME_URL)):
        return redirect_url
    return SUPPORT_HOME_URL


def support_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not user_is_customer_support(request.user):
            return redirect_to_login(request.get_full_path(), login_url=SUPPORT_LOGIN_URL)
        request.support_user = request.user
        return view_func(request, *args, **kwargs)

    return wrapper


def _support_template_context(**extra):
    context = {
        "site_header": "Customer Support",
        "site_title": "Customer Support",
        "is_nav_sidebar_enabled": False,
    }
    context.update(extra)
    return context


def central_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="/admin/login/")
        if user_is_customer_support(request.user):
            return HttpResponseForbidden("Customer support users cannot access central admin use cases.")
        if not request.user.is_active or not request.user.is_staff or not request.user.is_superuser:
            return HttpResponseForbidden("Central admin access requires a Django superuser.")
        return view_func(request, *args, **kwargs)

    return wrapper


# =============================================================================
# VIEW: admin_home (Optimized)
# =============================================================================

@central_admin_required
@require_http_methods(['GET'])
def admin_home(request):
    """
    Render admin portal home page.
    Optimized: Minimal overhead, method restriction.
    """
    # Admin context is lightweight; render directly
    return render(request, 'portal/home.html', admin.site.each_context(request))


@require_http_methods(["GET", "POST"])
def support_login(request):
    if user_is_customer_support(request.user):
        return redirect(_safe_support_redirect_url(request))

    error = ""
    if request.method == "POST":
        username = str(request.POST.get("username", "")).strip()
        password = request.POST.get("password", "")
        support_user = authenticate(request, username=username, password=password)

        if support_user and user_is_customer_support(support_user):
            auth_login(request, support_user)
            return redirect(_safe_support_redirect_url(request))
        if support_user:
            error = "This Django superuser is not assigned to the Customer Support actor."
        else:
            error = "Invalid customer support credentials."

    context = _support_template_context(
        title="Customer Support Login",
        support_error=error,
        signed_in_user=(
            request.user.username
            if request.user.is_authenticated and not user_is_customer_support(request.user)
            else ""
        ),
        next=request.POST.get("next") or request.GET.get("next") or "",
    )
    return render(request, "portal/support_login.html", context)


@support_login_required
@require_http_methods(["GET"])
def support_inbox(request):
    status_filter = request.GET.get("status", "open")
    enquiries = SupportEnquiry.objects.select_related("responded_by")
    if status_filter in {SupportEnquiry.STATUS_OPEN, SupportEnquiry.STATUS_ANSWERED, SupportEnquiry.STATUS_CLOSED}:
        enquiries = enquiries.filter(status=status_filter)
    else:
        status_filter = "all"

    context = _support_template_context(
        title="Customer Support Inbox",
        support_user=request.support_user,
        status_filter=status_filter,
        status_choices=[
            ("open", "Open"),
            ("answered", "Answered"),
            ("closed", "Closed"),
            ("all", "All"),
        ],
        enquiries=enquiries[:200],
    )
    return render(request, "portal/support_inbox.html", context)


@support_login_required
@require_http_methods(["POST"])
def support_respond(request, enquiry_id):
    response = str(request.POST.get("support_response", "")).strip()
    status = request.POST.get("status", SupportEnquiry.STATUS_ANSWERED)
    if status not in {SupportEnquiry.STATUS_ANSWERED, SupportEnquiry.STATUS_CLOSED, SupportEnquiry.STATUS_OPEN}:
        status = SupportEnquiry.STATUS_ANSWERED
    if response:
        SupportEnquiry.objects.filter(id=enquiry_id).update(
            support_response=response,
            status=status,
            responded_by=request.user,
            responded_at=timezone.now(),
        )
    return redirect(SUPPORT_HOME_URL)


@support_login_required
@require_http_methods(["POST"])
def support_logout(request):
    auth_logout(request)
    return redirect(SUPPORT_LOGIN_URL)


# =============================================================================
# VIEW: analytics_embed (Optimized)
# =============================================================================

@central_admin_required
@require_http_methods(['GET'])
def analytics_embed(request):
    """
    Render betting activity reports from the cleaned Stone Odds dataset.
    """
    context = admin.site.each_context(request)
    cleaned_path = _cleaned_bets_path()

    if not cleaned_path.exists():
        context.update(
            {
                "report_missing": True,
                "report_path": str(cleaned_path),
                "report_window": "No betting window available",
                "report_cutoff": REPORTING_CUTOFF_LABEL,
                "excluded_after_cutoff": 0,
            }
        )
        return render(request, "portal/betting_activity_reports.html", context)

    try:
        payload = _betting_activity_payload(str(cleaned_path), cleaned_path.stat().st_mtime_ns)
    except Exception as exc:
        logger.exception("Failed to build betting activity reports: %s", exc)
        context.update(
            {
                "report_missing": True,
                "report_path": str(cleaned_path),
                "report_error": str(exc),
                "report_window": "No betting window available",
                "report_cutoff": REPORTING_CUTOFF_LABEL,
                "excluded_after_cutoff": 0,
            }
        )
        return render(request, "portal/betting_activity_reports.html", context)

    context.update(
        {
            "report_missing": False,
            "report_window": payload["report_window"],
            "report_cutoff": payload["report_cutoff"],
            "excluded_after_cutoff": payload["excluded_after_cutoff"],
            "overview_cards": payload["overview_cards"],
            "report_payload": payload,
        }
    )
    return render(request, "portal/betting_activity_reports.html", context)


# =============================================================================
# VIEW: ml_bettor_segments (Offline ML Admin Review)
# =============================================================================

@central_admin_required
@require_http_methods(["GET"])
def ml_bettor_segments(request):
    """
    Render the offline ML bettor segmentation outputs for admin review.
    Reads generated CSV artifacts from Data/models/bettor_segmentation.
    """
    model_dir = _model_output_dir()
    comparison_rows = _read_csv_rows(model_dir / "model_comparison.csv")
    kmeans_clusters = _format_cluster_rows(_read_csv_rows(model_dir / "kmeans_cluster_summary.csv"))
    gmm_clusters = _format_cluster_rows(_read_csv_rows(model_dir / "gmm_cluster_summary.csv"))
    kmeans_segments = _read_csv_rows(model_dir / "kmeans_bettor_segments.csv")
    gmm_segments = _read_csv_rows(model_dir / "gmm_bettor_segments.csv")

    best_kmeans = next((row for row in comparison_rows if row.get("algorithm") == "kmeans"), None)
    best_gmm = next((row for row in comparison_rows if row.get("algorithm") == "gmm"), None)

    segment_source = request.GET.get("algorithm", "kmeans").lower()
    if segment_source not in {"kmeans", "gmm"}:
        return HttpResponseBadRequest("Invalid algorithm. Use kmeans or gmm.")
    selected_segments = kmeans_segments if segment_source == "kmeans" else gmm_segments
    selected_clusters = kmeans_clusters if segment_source == "kmeans" else gmm_clusters

    top_segments = selected_segments[:25]
    for row in top_segments:
        row["cluster_confidence_pct"] = round(_as_float(row.get("cluster_confidence")) * 100, 2)

    context = admin.site.each_context(request)
    context.update(
        {
            "model_dir": str(model_dir),
            "model_missing": not kmeans_clusters or not gmm_clusters,
            "selected_algorithm": segment_source,
            "cluster_count": len(selected_clusters),
            "bettor_count": len(selected_segments),
            "kmeans_clusters": kmeans_clusters,
            "gmm_clusters": gmm_clusters,
            "selected_clusters": selected_clusters,
            "top_segments": top_segments,
            "best_kmeans": best_kmeans,
            "best_gmm": best_gmm,
            "scatter_points": [_chart_point(row) for row in selected_segments],
        }
    )

    return render(request, "portal/ml_bettor_segments.html", context)


# =============================================================================
# VIEW: issue_token (Optimized)
# =============================================================================

@central_admin_required
@require_http_methods(['POST'])  # Token issuance should be POST for CSRF protection
def issue_token(request):
    """
    Issue SSO JWT token and set secure cookie.
    Optimized: Cached settings, centralized token creation, error handling.
    """
    token = _create_sso_token(request.user)
    
    if not token:
        logger.error(f"Token creation failed for user {request.user.id}")
        return JsonResponse(
            {'error': 'Token generation failed'},
            status=500
        )
    
    # Build response with token
    response = JsonResponse({'token': token})
    
    # Set cookie using cached attributes (efficient, consistent)
    response.set_cookie(
        _get_sso_cookie_name(),
        token,
        **_get_sso_cookie_attrs()
    )
    
    logger.debug(f"Issued SSO token for user {request.user.username}")
    return response


# =============================================================================
# VIEW: unity_game2_proxy (Compatibility)
# =============================================================================

@central_admin_required
@require_http_methods(["GET", "HEAD"])
def unity_game2_proxy(request, path=""):
    """
    Compatibility route: serve Unity WebGL build from /game2/* on the admin portal origin.

    The actual build is hosted under the decision_service at /gameplay/game2/*.
    """
    safe_path = str(path or "").lstrip("/")
    full_path = f"/gameplay/game2/{safe_path}" if safe_path else "/gameplay/game2/"
    return gateway_views.forward_request_raw(request, "decision", full_path)
