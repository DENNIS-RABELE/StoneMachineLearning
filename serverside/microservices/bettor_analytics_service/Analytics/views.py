from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

"""
Analytics view intentionally decoupled from bet data service models.
Gateway integration will populate transactions and balances when available.
"""


DECIMAL_ZERO = Decimal("0")
ALLOWED_RANGE_VALUES = {"7", "30", "90", "all"}


@staff_member_required
def analytics_dashboard(request):
    range_value = str(request.GET.get("range", "30")).strip().lower()
    if range_value not in ALLOWED_RANGE_VALUES:
        range_value = "30"

    cutoff_date = None
    if range_value != "all":
        days = int(range_value)
        cutoff_date = timezone.now().date() - timedelta(days=days - 1)

    # TODO: Replace with gateway API call once services are wired together.
    transactions = []

    daily_net = defaultdict(lambda: DECIMAL_ZERO)
    stake_count = 0
    payout_count = 0
    total_stake = DECIMAL_ZERO
    total_payout = DECIMAL_ZERO

    for tx in transactions:
        tx_day = tx.created_at.date()
        if cutoff_date and tx_day < cutoff_date:
            continue

        amount = Decimal(tx.amount)
        if tx.tx_type == "BET_STAKE":
            total_stake += amount
            daily_net[tx_day] += amount
            stake_count += 1
        elif tx.tx_type == "BET_PAYOUT":
            total_payout += amount
            daily_net[tx_day] -= amount
            payout_count += 1

    ordered_days = sorted(daily_net.keys())

    rows = []
    cumulative_balance = DECIMAL_ZERO
    for day in ordered_days:
        net_change = daily_net[day]
        previous_balance = cumulative_balance
        cumulative_balance += net_change

        if previous_balance == DECIMAL_ZERO:
            pct_change = None
        else:
            pct_change = (net_change / abs(previous_balance)) * Decimal("100")

        rows.append(
            {
                "day": day,
                "net_change": net_change,
                "cumulative_balance": cumulative_balance,
                "pct_change": pct_change,
            }
        )

    chart_points = _build_chart_points(rows)
    # TODO: Replace with gateway API call once services are wired together.
    final_balance = DECIMAL_ZERO

    context = {
        "rows": rows,
        "chart_points": chart_points,
        "final_balance": final_balance,
        "total_stake": total_stake,
        "total_payout": total_payout,
        "resolved_count": stake_count,
        "unresolved_count": payout_count,
        "selected_range": range_value,
        "range_options": [
            {"value": "7", "label": "Last 7 days"},
            {"value": "30", "label": "Last 30 days"},
            {"value": "90", "label": "Last 90 days"},
            {"value": "all", "label": "All time"},
        ],
    }
    is_embed = str(request.GET.get("embed", "")).strip().lower() in {"1", "true", "yes"}
    template_name = (
        "bettor_analytics/dashboard_embed.html"
        if is_embed
        else "bettor_analytics/dashboard.html"
    )
    return render(request, template_name, context)


def _build_chart_points(rows: list[dict]) -> str:
    if not rows:
        return ""

    width = 860
    height = 300
    padding = 24
    inner_w = width - (padding * 2)
    inner_h = height - (padding * 2)

    values = [row["cumulative_balance"] for row in rows]
    min_val = min(values)
    max_val = max(values)
    span = max_val - min_val
    if span == DECIMAL_ZERO:
        span = Decimal("1")

    points = []
    for idx, row in enumerate(rows):
        x_ratio = Decimal(idx) / Decimal(max(len(rows) - 1, 1))
        y_ratio = (row["cumulative_balance"] - min_val) / span

        x = float(Decimal(padding) + (Decimal(inner_w) * x_ratio))
        y = float(Decimal(height - padding) - (Decimal(inner_h) * y_ratio))
        points.append(f"{x:.2f},{y:.2f}")

    return " ".join(points)
