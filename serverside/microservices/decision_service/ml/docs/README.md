# Machine Learning Betting Behavior Clustering

This module implements k-means clustering to analyze and group bettor behaviors and strategies within the decision_service. It helps identify bettor archetypes and provides insights for decision-making and strategy recommendations.

## Overview

The ML clustering system analyzes bettor behavior through the following features:

- **Win Rate**: Percentage of successful bets
- **Bet Amount Statistics**: Average, min, max, and variance of bet amounts
- **Betting Frequency**: Number of bets per round and total active rounds
- **Strategy Diversity**: How varied a bettor's betting approaches are
- **ROI (Return on Investment)**: Profit efficiency metric

## Architecture

### Models
- `BettorProfile`: Aggregated statistics for each bettor
- `ClusteringModel`: Trained k-means model metadata
- `BettorCluster`: Assignment of bettors to clusters
- `ClusterCharacteristics`: Statistical profile of each cluster
- `MLMetrics`: Performance tracking of models

### Services
- `kmeans_clustering.py`: Main clustering engine
- `data_preprocessing.py`: Data preparation utilities
- `model_analysis.py`: Advanced analysis and persistence

### API Endpoints
- `/api/ml/bettor-profiles/`: Bettor profile management
- `/api/ml/clustering-models/`: Model training and management
- `/api/ml/bettor-clusters/`: Cluster predictions and assignments
- `/api/ml/ml-metrics/`: Performance metrics tracking

### Management Commands
- `generate_sample_bettors`: Create sample bettor data
- `train_clustering_model`: Train k-means models

## Quick Start

1. Run migrations: `python manage.py migrate`
2. Generate sample data: `python manage.py generate_sample_bettors --count=200`
3. Train model: `python manage.py train_clustering_model --name="v1" --clusters=5`
4. Use API: `GET /api/ml/clustering-models/1/cluster_summary/`

## Feature Dictionary

| Feature | Description | Range |
|---------|-------------|-------|
| `win_rate` | Proportion of successful bets | 0.0 - 1.0 |
| `average_bet_amount` | Mean bet size | 0.0 - ∞ |
| `bet_variance` | Variance in bet amounts | 0.0 - ∞ |
| `average_bets_per_round` | Mean bets per round | 0.0 - ∞ |
| `strategy_diversity` | Different strategies used | 0.0 - 1.0 |
| `roi` | Return on investment % | -∞ - ∞ |

## Model Evaluation Metrics

- **Silhouette Score**: -1 to 1 (higher is better, >0.5 is good)
- **Davies-Bouldin Index**: 0 to ∞ (lower is better)
- **Inertia**: Sum of squared distances to centroids

## Documentation

See the `/ml/docs/` folder for:
- `INTEGRATION_GUIDE.md`: Setup and integration steps
- `IMPLEMENTATION_SUMMARY.md`: Complete implementation overview
- `EXAMPLES.py`: 12 practical usage examples
