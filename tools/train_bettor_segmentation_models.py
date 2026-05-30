from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler


FEATURE_COLUMNS = [
    "total_bets",
    "active_days",
    "total_stake",
    "average_stake",
    "stake_volatility",
    "average_odds",
    "max_odds",
    "total_profit",
    "win_rate",
    "loss_rate",
    "combo_bet_rate",
    "weekend_bet_rate",
    "roi_percent",
    "bets_per_active_day",
    "favorite_time_band_share",
    "preferred_option_code_share",
    "high_odds_rate",
    "night_bet_rate",
]

INTERPRETATION_COLUMNS = [
    "favorite_time_band",
    "favorite_hour",
    "favorite_day_name",
    "preferred_option_code",
    "preferred_option_family",
    "preferred_stake_band",
    "preferred_odds_band",
    "preferred_strategy_style",
    "promotion_targeting_signal",
    "responsible_gambling_risk_hint",
]


def safe_score(metric_func, x_scaled: np.ndarray, labels: np.ndarray) -> float | None:
    unique_labels = np.unique(labels)
    if len(unique_labels) < 2 or len(unique_labels) >= len(labels):
        return None
    try:
        return round(float(metric_func(x_scaled, labels)), 4)
    except Exception:
        return None


def model_selection_score(row: pd.Series) -> float:
    silhouette = row.get("silhouette_score")
    davies = row.get("davies_bouldin_score")
    size_ratio = row.get("min_cluster_size_ratio")
    if pd.isna(silhouette) or pd.isna(davies) or pd.isna(size_ratio):
        return -999.0
    return round(float(silhouette) - (float(davies) * 0.08) + (float(size_ratio) * 0.35), 4)


def top_value(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return "Unknown"
    return str(values.value_counts().idxmax())


def profile_cluster_name(row: pd.Series) -> str:
    strategy = str(row.get("preferred_strategy_style", ""))
    time_band = str(row.get("favorite_time_band", ""))
    promo = str(row.get("promotion_targeting_signal", ""))
    risk = str(row.get("responsible_gambling_risk_hint", ""))

    if "High Odds" in promo or row.get("high_odds_rate_mean", 0) >= 60:
        base = "High-Odds Bettors"
    elif "Combo" in strategy or row.get("combo_bet_rate_mean", 0) >= 55:
        base = "Combo-Heavy Bettors"
    elif row.get("average_stake_mean", 0) >= 175:
        base = "High-Value Bettors"
    elif time_band in {"Night", "Midnight"}:
        base = "Late-Time Bettors"
    else:
        base = "Balanced Regulars"

    if risk == "High":
        return f"{base} With Safety Watch"
    return base


def describe_cluster(row: pd.Series) -> str:
    return (
        f"{row['cluster_size']} bettors, usually active around {row['favorite_time_band']} "
        f"with preferred style {row['preferred_strategy_style']}. "
        f"Average stake {row['average_stake_mean']:.2f}, average odds {row['average_odds_mean']:.2f}, "
        f"combo rate {row['combo_bet_rate_mean']:.2f}%, high-odds rate {row['high_odds_rate_mean']:.2f}%, "
        f"ROI {row['roi_percent_mean']:.2f}%."
    )


def summarize_clusters(profiles: pd.DataFrame, labels: np.ndarray, algorithm: str) -> pd.DataFrame:
    work = profiles.copy()
    work["cluster_id"] = labels

    numeric_summary = work.groupby("cluster_id").agg(
        cluster_size=("player_id", "count"),
        total_bets_mean=("total_bets", "mean"),
        average_stake_mean=("average_stake", "mean"),
        stake_volatility_mean=("stake_volatility", "mean"),
        average_odds_mean=("average_odds", "mean"),
        win_rate_mean=("win_rate", "mean"),
        combo_bet_rate_mean=("combo_bet_rate", "mean"),
        weekend_bet_rate_mean=("weekend_bet_rate", "mean"),
        roi_percent_mean=("roi_percent", "mean"),
        high_odds_rate_mean=("high_odds_rate", "mean"),
        night_bet_rate_mean=("night_bet_rate", "mean"),
    ).reset_index()

    rows = []
    for cluster_id, group in work.groupby("cluster_id"):
        rows.append(
            {
                "cluster_id": cluster_id,
                "favorite_time_band": top_value(group["favorite_time_band"]),
                "preferred_strategy_style": top_value(group["preferred_strategy_style"]),
                "preferred_option_family": top_value(group["preferred_option_family"]),
                "preferred_odds_band": top_value(group["preferred_odds_band"]),
                "promotion_targeting_signal": top_value(group["promotion_targeting_signal"]),
                "responsible_gambling_risk_hint": top_value(group["responsible_gambling_risk_hint"]),
            }
        )
    categorical_summary = pd.DataFrame(rows)
    summary = numeric_summary.merge(categorical_summary, on="cluster_id", how="left")
    summary["algorithm"] = algorithm

    round_columns = [
        "total_bets_mean",
        "average_stake_mean",
        "stake_volatility_mean",
        "average_odds_mean",
        "win_rate_mean",
        "combo_bet_rate_mean",
        "weekend_bet_rate_mean",
        "roi_percent_mean",
        "high_odds_rate_mean",
        "night_bet_rate_mean",
    ]
    for column in round_columns:
        summary[column] = summary[column].round(2)

    summary["cluster_name"] = summary.apply(profile_cluster_name, axis=1)
    summary["cluster_description"] = summary.apply(describe_cluster, axis=1)
    return summary.sort_values("cluster_id")


def evaluate_models(x_scaled: np.ndarray, cluster_range: range, random_state: int) -> tuple[pd.DataFrame, dict]:
    records = []
    fitted_models = {}

    for k in cluster_range:
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=25)
        kmeans_labels = kmeans.fit_predict(x_scaled)
        kmeans_counts = pd.Series(kmeans_labels).value_counts()
        records.append(
            {
                "algorithm": "kmeans",
                "n_clusters": k,
                "silhouette_score": safe_score(silhouette_score, x_scaled, kmeans_labels),
                "davies_bouldin_score": safe_score(davies_bouldin_score, x_scaled, kmeans_labels),
                "calinski_harabasz_score": safe_score(calinski_harabasz_score, x_scaled, kmeans_labels),
                "min_cluster_size": int(kmeans_counts.min()),
                "max_cluster_size": int(kmeans_counts.max()),
                "min_cluster_size_ratio": round(float(kmeans_counts.min() / len(kmeans_labels)), 4),
            }
        )
        fitted_models[("kmeans", k)] = (kmeans, kmeans_labels, None)

        gmm = GaussianMixture(
            n_components=k,
            covariance_type="full",
            random_state=random_state,
            n_init=10,
        )
        gmm_labels = gmm.fit_predict(x_scaled)
        gmm_probs = gmm.predict_proba(x_scaled)
        gmm_counts = pd.Series(gmm_labels).value_counts()
        records.append(
            {
                "algorithm": "gmm",
                "n_clusters": k,
                "silhouette_score": safe_score(silhouette_score, x_scaled, gmm_labels),
                "davies_bouldin_score": safe_score(davies_bouldin_score, x_scaled, gmm_labels),
                "calinski_harabasz_score": safe_score(calinski_harabasz_score, x_scaled, gmm_labels),
                "min_cluster_size": int(gmm_counts.min()),
                "max_cluster_size": int(gmm_counts.max()),
                "min_cluster_size_ratio": round(float(gmm_counts.min() / len(gmm_labels)), 4),
                "bic": round(float(gmm.bic(x_scaled)), 2),
                "aic": round(float(gmm.aic(x_scaled)), 2),
            }
        )
        fitted_models[("gmm", k)] = (gmm, gmm_labels, gmm_probs)

    results = pd.DataFrame(records)
    results["selection_score"] = results.apply(model_selection_score, axis=1)
    return results.sort_values("selection_score", ascending=False), fitted_models


def main() -> None:
    parser = argparse.ArgumentParser(description="Train K-Means and GMM bettor segmentation models.")
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("Data") / "profiles" / "bettor_profiles.csv",
        help="Bettor profile CSV produced by build_bettor_profiles.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Data") / "models" / "bettor_segmentation",
        help="Directory where model artifacts and segment outputs will be written.",
    )
    parser.add_argument("--min-clusters", type=int, default=3)
    parser.add_argument("--max-clusters", type=int, default=8)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    profiles = pd.read_csv(args.profiles)

    missing_features = [column for column in FEATURE_COLUMNS if column not in profiles.columns]
    if missing_features:
        raise SystemExit(f"Missing model feature columns: {', '.join(missing_features)}")

    model_input = profiles[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(model_input)

    cluster_range = range(args.min_clusters, args.max_clusters + 1)
    evaluation, fitted_models = evaluate_models(x_scaled, cluster_range, args.random_state)
    evaluation.to_csv(args.output_dir / "model_comparison.csv", index=False)

    best_by_algorithm = (
        evaluation.sort_values(["algorithm", "selection_score"], ascending=[True, False])
        .groupby("algorithm", as_index=False)
        .head(1)
        .sort_values("algorithm")
    )

    segment_outputs = []
    cluster_summaries = []
    model_artifacts = {
        "feature_columns": FEATURE_COLUMNS,
        "interpretation_columns": INTERPRETATION_COLUMNS,
        "scaler": scaler,
        "random_state": args.random_state,
        "model_selection": best_by_algorithm.to_dict(orient="records"),
    }

    for _, row in best_by_algorithm.iterrows():
        algorithm = row["algorithm"]
        k = int(row["n_clusters"])
        model, labels, probs = fitted_models[(algorithm, k)]
        model_artifacts[f"{algorithm}_model"] = model

        summary = summarize_clusters(profiles, labels, algorithm)
        summary.to_csv(args.output_dir / f"{algorithm}_cluster_summary.csv", index=False)
        cluster_summaries.append(summary)

        cluster_name_lookup = summary.set_index("cluster_id")["cluster_name"].to_dict()
        cluster_description_lookup = summary.set_index("cluster_id")["cluster_description"].to_dict()
        segments = profiles[["player_id"] + FEATURE_COLUMNS + INTERPRETATION_COLUMNS].copy()
        segments["algorithm"] = algorithm
        segments["cluster_id"] = labels
        segments["cluster_name"] = segments["cluster_id"].map(cluster_name_lookup)
        segments["cluster_description"] = segments["cluster_id"].map(cluster_description_lookup)
        if probs is not None:
            segments["cluster_confidence"] = np.max(probs, axis=1).round(4)
            segments["secondary_cluster_id"] = np.argsort(probs, axis=1)[:, -2]
            segments["secondary_cluster_probability"] = np.sort(probs, axis=1)[:, -2].round(4)
        else:
            transformed = model.transform(x_scaled)
            similarity = np.exp(-transformed)
            probability_like = similarity / similarity.sum(axis=1, keepdims=True)
            segments["cluster_confidence"] = np.max(probability_like, axis=1).round(4)
            segments["secondary_cluster_id"] = np.argsort(probability_like, axis=1)[:, -2]
            segments["secondary_cluster_probability"] = np.sort(probability_like, axis=1)[:, -2].round(4)

        segments.to_csv(args.output_dir / f"{algorithm}_bettor_segments.csv", index=False)
        segment_outputs.append(segments)

    combined_segments = pd.concat(segment_outputs, ignore_index=True)
    combined_segments.to_csv(args.output_dir / "combined_bettor_segments.csv", index=False)
    pd.concat(cluster_summaries, ignore_index=True).to_csv(
        args.output_dir / "combined_cluster_summaries.csv",
        index=False,
    )
    joblib.dump(model_artifacts, args.output_dir / "bettor_segmentation_models.joblib")

    summary_path = args.output_dir / "training_summary.md"
    lines = [
        "# Bettor Segmentation Model Training",
        "",
        f"Input profiles: `{args.profiles}`",
        f"Bettors trained: `{len(profiles):,}`",
        f"Features used: `{len(FEATURE_COLUMNS)}`",
        f"Cluster range tested: `{args.min_clusters}` to `{args.max_clusters}`",
        "",
        "## Best Model Per Algorithm",
        "",
        best_by_algorithm.to_string(index=False),
        "",
        "## Outputs",
        "",
        "- `model_comparison.csv`",
        "- `kmeans_bettor_segments.csv`",
        "- `gmm_bettor_segments.csv`",
        "- `combined_bettor_segments.csv`",
        "- `kmeans_cluster_summary.csv`",
        "- `gmm_cluster_summary.csv`",
        "- `combined_cluster_summaries.csv`",
        "- `bettor_segmentation_models.joblib`",
        "",
        "K-Means gives hard, admin-friendly primary segments. GMM gives soft segment probabilities for mixed bettor behavior.",
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Training summary: {summary_path}")
    print(f"Model comparison: {args.output_dir / 'model_comparison.csv'}")
    print(f"Model artifact: {args.output_dir / 'bettor_segmentation_models.joblib'}")


if __name__ == "__main__":
    main()
