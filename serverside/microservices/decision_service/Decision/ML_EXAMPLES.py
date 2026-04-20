"""
Example usage of the ML clustering module.

This file demonstrates how to use the k-means clustering functionality
for analyzing betting behavior.
"""

# Example 1: Generate Sample Data
# ==============================
"""
from django.core.management import call_command

# Generate 100 sample bettors
call_command('generate_sample_bettors', count=100, seed=42, clear=True)
"""

# Example 2: Train a Clustering Model
# ===================================
"""
from django.core.management import call_command

# Train a 5-cluster model
call_command(
    'train_clustering_model',
    name='production_v1',
    clusters=5,
    description='Production model for bettor segmentation'
)
"""

# Example 3: Use API to List Models
# =================================
"""
import requests

# Get all clustering models
response = requests.get(
    'http://localhost:8000/api/ml/clustering-models/',
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)
models = response.json()
print(f"Found {len(models)} models")
"""

# Example 4: Get Cluster Summary
# =============================
"""
import requests

model_id = 1

response = requests.get(
    f'http://localhost:8000/api/ml/clustering-models/{model_id}/cluster_summary/',
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

summary = response.json()
print(f"Model: {summary['model_name']}")
print(f"Silhouette Score: {summary['silhouette_score']:.4f}")
print(f"Number of Clusters: {summary['n_clusters']}")

for cluster in summary['clusters']:
    print(f"\n  Cluster {cluster['cluster_id']}: {cluster['profile_name']}")
    print(f"    Size: {cluster['cluster_size']} bettors")
    print(f"    Win Rate: {cluster['avg_win_rate']:.2%}")
    print(f"    ROI: {cluster['avg_roi']:.2%}")
"""

# Example 5: Predict Cluster for a Bettor
# ======================================
"""
import requests

response = requests.post(
    'http://localhost:8000/api/ml/bettor-clusters/predict_cluster/',
    json={'bettor_id': 'bettor_000001'},
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

prediction = response.json()
print(f"Bettor {prediction['bettor_id']} belongs to cluster {prediction['cluster_id']}")
print(f"Confidence: {prediction['confidence']:.2%}")
"""

# Example 6: Analyze Cluster Cohesion
# ==================================
"""
from Decision.services.model_analysis import ClusterAnalyzer
from Decision.ml_models import ClusteringModel

model = ClusteringModel.objects.get(is_active=True)
cohesion_scores = ClusterAnalyzer.analyze_cluster_cohesion(model)

for cluster_id, cohesion in cohesion_scores.items():
    print(f"Cluster {cluster_id} Cohesion: {cohesion:.4f}")
"""

# Example 7: Find Cluster Outliers
# ===============================
"""
from Decision.services.model_analysis import ClusterAnalyzer
from Decision.ml_models import ClusteringModel

model = ClusteringModel.objects.get(is_active=True)
outliers = ClusterAnalyzer.find_cluster_outliers(model, cluster_id=0, percentile=10)

print(f"Found {len(outliers)} outliers in cluster 0:")
for bettor_id in outliers:
    print(f"  - {bettor_id}")
"""

# Example 8: Get Strategy Profile
# ==============================
"""
from Decision.services.model_analysis import BettorStrategyAnalyzer
from Decision.ml_models import ClusteringModel

model = ClusteringModel.objects.get(is_active=True)
strategy = BettorStrategyAnalyzer.get_cluster_strategy_profile(model, cluster_id=0)

print(f"Strategy Profile: {strategy['profile_name']}")
print(f"Description: {strategy['profile_description']}")
print(f"Member Count: {strategy['member_count']}")
print(f"Avg Win Rate: {strategy['metrics']['avg_win_rate']:.2%}")
print(f"Avg ROI: {strategy['metrics']['avg_roi']:.2%}")

print("\nRecommendations:")
for rec in strategy['strategy_recommendations']:
    print(f"  - {rec}")
"""

# Example 9: Update Bettor Profile from History
# ============================================
"""
from Decision.services.data_preprocessing import BettorDataAggregator

betting_history = [
    {
        'amount': 100,
        'outcome': 'win',
        'payout': 200,
        'round_id': 1,
        'bet_type': 'moderate',
        'timestamp': '2024-04-19'
    },
    {
        'amount': 150,
        'outcome': 'loss',
        'payout': 0,
        'round_id': 2,
        'bet_type': 'aggressive',
        'timestamp': '2024-04-19'
    },
]

profile = BettorDataAggregator.update_bettor_profile_from_betting_history(
    bettor_id='bettor_custom_123',
    betting_history=betting_history,
    time_window_days=30
)

print(f"Updated profile for {profile.bettor_id}")
print(f"Win Rate: {profile.win_rate:.2%}")
print(f"ROI: {profile.roi:.2%}")
"""

# Example 10: Compare Models
# =========================
"""
from Decision.services.model_analysis import ClusterAnalyzer

comparison = ClusterAnalyzer.compare_models(model1_id=1, model2_id=2)

print(f"Model Comparison:")
print(f"  Model 1 Silhouette: {comparison['model1']['silhouette']:.4f}")
print(f"  Model 2 Silhouette: {comparison['model2']['silhouette']:.4f}")
print(f"  Better Model: {comparison['better_model']}")
"""

# Example 11: Get Model Performance Report
# =======================================
"""
from Decision.services.model_analysis import ModelEvaluationService
from Decision.ml_models import ClusteringModel

model = ClusteringModel.objects.get(is_active=True)
report = ModelEvaluationService.get_model_performance_report(model)

print(f"Model: {report['model_name']}")
print(f"Quality Metrics:")
print(f"  Silhouette: {report['quality_metrics']['silhouette_score']:.4f}")
print(f"  Davies-Bouldin: {report['quality_metrics']['davies_bouldin_score']:.4f}")
print(f"  Inertia: {report['quality_metrics']['inertia']:.2f}")
print(f"\nCluster Distribution:")
for cluster_name, size in report['cluster_distribution'].items():
    print(f"  {cluster_name}: {size} bettors")
"""

# Example 12: Batch Update Multiple Profiles
# =========================================
"""
from Decision.services.data_preprocessing import BettorDataAggregator

bettor_betting_data = {
    'bettor_001': [
        {'amount': 100, 'outcome': 'win', 'payout': 200, ...},
        {'amount': 150, 'outcome': 'loss', 'payout': 0, ...},
    ],
    'bettor_002': [
        {'amount': 200, 'outcome': 'win', 'payout': 400, ...},
    ],
}

profiles = BettorDataAggregator.batch_update_profiles(
    bettor_betting_data=bettor_betting_data,
    time_window_days=7
)

print(f"Updated {len(profiles)} profiles")
"""

print(__doc__)
