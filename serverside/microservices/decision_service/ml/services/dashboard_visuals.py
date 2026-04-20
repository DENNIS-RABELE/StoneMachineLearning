"""Helpers for ML dashboard summaries and inline SVG charts."""
from html import escape
from typing import Dict, List, Optional, Sequence, Tuple

from django.utils import timezone

from ..models import BettorProfile, ClusteringModel
from .historical_betting_import import HistoricalBettingImporter


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _format_money(value: float) -> str:
    return f"{value:,.2f}"


def make_bar_chart_svg(
    items: Sequence[Tuple[str, float]],
    title: str,
    color: str = "#d96c06",
    width: int = 820,
    height: int = 320,
) -> str:
    """Render a simple horizontal bar chart as inline SVG."""
    if not items:
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            'xmlns="http://www.w3.org/2000/svg">'
            '<defs><linearGradient id="emptyBarBg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0%" stop-color="#fff7ed" /><stop offset="100%" stop-color="#ffedd5" />'
            '</linearGradient></defs>'
            '<rect width="100%" height="100%" rx="30" fill="url(#emptyBarBg)" />'
            f'<text x="28" y="48" fill="#7c2d12" font-size="24" font-family="Georgia, serif">{escape(title)}</text>'
            '<text x="28" y="92" fill="#9a3412" font-size="15">No data available yet.</text>'
            "</svg>"
        )

    left_pad = 240
    top_pad = 68
    bar_height = 26
    gap = 20
    max_value = max(value for _, value in items) or 1
    inner_width = width - left_pad - 62
    total_height = top_pad + len(items) * (bar_height + gap) + 30
    view_height = max(height, total_height)
    gradient_id = f"barGradient{abs(hash((title, color))) % 100000}"

    parts = [
        f'<svg viewBox="0 0 {width} {view_height}" width="{width}" height="{view_height}" xmlns="http://www.w3.org/2000/svg">',
        '<defs>',
        f'<linearGradient id="{gradient_id}" x1="0" y1="0" x2="1" y2="0">',
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.85" />',
        f'<stop offset="100%" stop-color="{color}" stop-opacity="1" />',
        '</linearGradient>',
        '</defs>',
        '<rect width="100%" height="100%" rx="30" fill="#fffaf5" />',
        f'<text x="28" y="46" fill="#7c2d12" font-size="24" font-family="Georgia, serif">{escape(title)}</text>',
    ]

    for index, (label, value) in enumerate(items):
        y = top_pad + index * (bar_height + gap)
        bar_width = 0 if max_value <= 0 else (value / max_value) * inner_width
        parts.extend(
            [
                f'<text x="28" y="{y + 18}" fill="#431407" font-size="15" font-weight="600">{escape(label)}</text>',
                f'<rect x="{left_pad}" y="{y}" width="{inner_width}" height="{bar_height}" rx="13" fill="#fed7aa" fill-opacity="0.65" />',
                f'<rect x="{left_pad}" y="{y}" width="{max(8, bar_width):.2f}" height="{bar_height}" rx="13" fill="url(#{gradient_id})" />',
                f'<text x="{left_pad + inner_width + 12}" y="{y + 18}" fill="#7c2d12" font-size="14" font-weight="600">{escape(str(round(value, 2)))}</text>',
            ]
        )

    parts.append("</svg>")
    return "".join(parts)


def make_scatter_svg(
    points: Sequence[Dict[str, object]],
    title: str,
    width: int = 820,
    height: int = 380,
) -> str:
    """Render a scatter plot of ROI vs average bet amount."""
    if not points:
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100%" height="100%" rx="30" fill="#eff6ff" />'
            f'<text x="28" y="46" fill="#1d4ed8" font-size="24" font-family="Georgia, serif">{escape(title)}</text>'
            '<text x="28" y="92" fill="#1e40af" font-size="15">No bettor points available yet.</text>'
            "</svg>"
        )

    left = 82
    right = width - 34
    top = 58
    bottom = height - 58
    plot_width = right - left
    plot_height = bottom - top

    min_x = min(float(point["average_bet_amount"]) for point in points)
    max_x = max(float(point["average_bet_amount"]) for point in points)
    min_y = min(float(point["roi"]) for point in points)
    max_y = max(float(point["roi"]) for point in points)
    if min_x == max_x:
        min_x -= 1
        max_x += 1
    if min_y == max_y:
        min_y -= 1
        max_y += 1

    def project_x(value: float) -> float:
        return left + ((value - min_x) / (max_x - min_x)) * plot_width

    def project_y(value: float) -> float:
        return bottom - ((value - min_y) / (max_y - min_y)) * plot_height

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="100%" height="100%" rx="30" fill="#f8fafc" />',
        f'<text x="28" y="38" fill="#0f172a" font-size="24" font-family="Georgia, serif">{escape(title)}</text>',
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#94a3b8" stroke-width="2" />',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#94a3b8" stroke-width="2" />',
        f'<text x="{right - 110}" y="{height - 18}" fill="#475569" font-size="13">Avg bet amount</text>',
        f'<text x="18" y="{top + 10}" fill="#475569" font-size="13">ROI %</text>',
    ]

    for point in points:
        x = project_x(float(point["average_bet_amount"]))
        y = project_y(float(point["roi"]))
        radius = 6 + _clamp(float(point["total_bets"]) / 8, 0, 12)
        color = "#0f766e" if float(point["roi"]) >= 0 else "#dc2626"
        label = escape(str(point["bettor_id"]))
        parts.extend(
            [
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" fill-opacity="0.82" stroke="#ffffff" stroke-width="2" />',
                f'<title>{label}: ROI {float(point["roi"]):.2f}%, avg bet {float(point["average_bet_amount"]):.2f}</title>',
            ]
        )

    parts.extend(
        [
            f'<text x="{left}" y="{height - 18}" fill="#334155" font-size="12">{_format_money(min_x)}</text>',
            f'<text x="{right - 52}" y="{height - 18}" fill="#334155" font-size="12">{_format_money(max_x)}</text>',
            f'<text x="18" y="{bottom}" fill="#334155" font-size="12">{min_y:.1f}</text>',
            f'<text x="18" y="{top + 6}" fill="#334155" font-size="12">{max_y:.1f}</text>',
            "</svg>",
        ]
    )
    return "".join(parts)


def make_line_chart_svg(
    points: Sequence[Tuple[str, Optional[float]]],
    title: str,
    color: str = "#2563eb",
    width: int = 720,
    height: int = 320,
) -> str:
    """Render a simple line chart as inline SVG."""
    valid_points = [(label, value) for label, value in points if value is not None]
    if len(valid_points) < 2:
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100%" height="100%" rx="24" fill="#eff6ff" />'
            f'<text x="24" y="42" fill="#1d4ed8" font-size="20" font-family="Georgia, serif">{escape(title)}</text>'
            '<text x="24" y="82" fill="#1e40af" font-size="14">Train more than one model to see a trend line.</text>'
            "</svg>"
        )

    left = 54
    right = width - 24
    top = 52
    bottom = height - 48
    plot_width = right - left
    plot_height = bottom - top
    min_y = min(value for _, value in valid_points)
    max_y = max(value for _, value in valid_points)
    if min_y == max_y:
        min_y -= 1
        max_y += 1

    def px(index: int) -> float:
        if len(valid_points) == 1:
            return left + plot_width / 2
        return left + (index / (len(valid_points) - 1)) * plot_width

    def py(value: float) -> float:
        return bottom - ((value - min_y) / (max_y - min_y)) * plot_height

    path_parts = []
    circles = []
    for index, (label, value) in enumerate(valid_points):
        x = px(index)
        y = py(value)
        path_parts.append(f"{'M' if index == 0 else 'L'} {x:.2f} {y:.2f}")
        circles.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}"><title>{escape(label)}: {value:.4f}</title></circle>'
        )

    x_labels = []
    for index, (label, _) in enumerate(valid_points):
        x = px(index)
        short_label = escape(label[-5:] if len(label) > 5 else label)
        x_labels.append(
            f'<text x="{x:.2f}" y="{height - 18}" text-anchor="middle" fill="#475569" font-size="11">{short_label}</text>'
        )

    return "".join(
        [
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<rect width="100%" height="100%" rx="24" fill="#f8fbff" />',
            f'<text x="24" y="34" fill="#0f172a" font-size="20" font-family="Georgia, serif">{escape(title)}</text>',
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#94a3b8" stroke-width="2" />',
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#94a3b8" stroke-width="2" />',
            f'<path d="{" ".join(path_parts)}" fill="none" stroke="{color}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" />',
            *circles,
            *x_labels,
            f'<text x="10" y="{bottom}" fill="#334155" font-size="12">{min_y:.2f}</text>',
            f'<text x="10" y="{top + 6}" fill="#334155" font-size="12">{max_y:.2f}</text>',
            "</svg>",
        ]
    )


def build_dashboard_context(
    time_window_days: Optional[int] = None,
    top_n: int = 8,
) -> Dict[str, object]:
    """Collect dashboard metrics, tables, and chart SVGs."""
    bettor_queryset = BettorProfile.objects.order_by("-total_bets", "bettor_id")
    if time_window_days:
        cutoff = timezone.now() - timezone.timedelta(days=time_window_days)
        bettor_queryset = bettor_queryset.filter(last_updated__gte=cutoff)
    bettor_profiles = list(bettor_queryset)
    latest_model = ClusteringModel.objects.order_by("-trained_at").first()
    active_model = ClusteringModel.objects.filter(is_active=True).first()
    model_history = list(ClusteringModel.objects.order_by("trained_at")[:20])

    top_bettors = [
        {
            "bettor_id": profile.bettor_id,
            "total_bets": profile.total_bets,
            "win_rate_pct": round(profile.win_rate * 100, 2),
            "roi": round(profile.roi, 2),
            "average_bet_amount": round(profile.average_bet_amount, 2),
        }
        for profile in bettor_profiles[:max(5, min(top_n, 12))]
    ]

    scatter_points = [
        {
            "bettor_id": profile.bettor_id,
            "average_bet_amount": profile.average_bet_amount,
            "roi": profile.roi,
            "total_bets": profile.total_bets,
        }
        for profile in bettor_profiles[:50]
    ]

    cluster_rows: List[Dict[str, object]] = []
    cluster_bar_data: List[Tuple[str, float]] = []
    if latest_model:
        characteristics = list(
            latest_model.cluster_characteristics.order_by("cluster_id")
        )
        cluster_rows = [
            {
                "cluster_id": row.cluster_id,
                "profile_name": row.profile_name or f"Cluster {row.cluster_id}",
                "cluster_size": row.cluster_size,
                "avg_roi": round(row.avg_roi, 2),
                "avg_win_rate_pct": round(row.avg_win_rate * 100, 2),
                "avg_bet_amount": round(row.avg_bet_amount, 2),
            }
            for row in characteristics
        ]
        cluster_bar_data = [
            (f"C{row.cluster_id} {row.profile_name or ''}".strip(), float(row.cluster_size))
            for row in characteristics
        ]

    top_characters: List[Dict[str, object]] = []
    character_bar_data: List[Tuple[str, float]] = []
    historical_error = None
    try:
        _, top_character_rows = HistoricalBettingImporter().build_bettor_histories(
            time_window_days=time_window_days,
        )
        total_character_stake = sum(row["total_stake"] for row in top_character_rows) or 0
        for row in top_character_rows[:top_n]:
            top_characters.append(
                {
                    "character_id": row["character_id"],
                    "character_name": row["character_name"],
                    "total_stake": round(row["total_stake"], 2),
                    "bet_count": row["bet_count"],
                    "share_pct": round(
                        (row["total_stake"] / total_character_stake) * 100, 2
                    ) if total_character_stake else 0.0,
                }
            )
        character_bar_data = [
            (row["character_name"], float(row["total_stake"]))
            for row in top_character_rows[: min(top_n, 6)]
        ]
    except Exception as exc:
        historical_error = str(exc)

    training_history_points = [
        (
            model.trained_at.strftime("%m-%d"),
            model.silhouette_score,
        )
        for model in model_history
    ]

    average_roi = round(
        sum(profile.roi for profile in bettor_profiles) / len(bettor_profiles),
        2,
    ) if bettor_profiles else 0.0
    average_win_rate = round(
        sum(profile.win_rate for profile in bettor_profiles) / len(bettor_profiles) * 100,
        2,
    ) if bettor_profiles else 0.0

    return {
        "summary_cards": [
            {"label": "Bettor Profiles", "value": len(bettor_profiles), "tone": "warm"},
            {"label": "Latest Model", "value": latest_model.name if latest_model else "None", "tone": "cool"},
            {"label": "Active Model", "value": active_model.name if active_model else "None", "tone": "olive"},
            {"label": "Average ROI", "value": f"{average_roi:.2f}%", "tone": "rose"},
            {"label": "Average Win Rate", "value": f"{average_win_rate:.2f}%", "tone": "sky"},
        ],
        "latest_model": latest_model,
        "cluster_rows": cluster_rows,
        "top_bettors": top_bettors,
        "top_characters": top_characters,
        "historical_error": historical_error,
        "filters": {
            "time_window_days": time_window_days,
            "top_n": top_n,
        },
        "cluster_chart_svg": make_bar_chart_svg(cluster_bar_data, "Cluster Sizes", color="#0f766e"),
        "character_chart_svg": make_bar_chart_svg(character_bar_data, "Most-Bet Characters", color="#b45309"),
        "scatter_chart_svg": make_scatter_svg(scatter_points, "ROI vs Average Bet"),
        "training_history_svg": make_line_chart_svg(
            training_history_points,
            "Model Silhouette Trend",
            color="#2563eb",
        ),
    }
