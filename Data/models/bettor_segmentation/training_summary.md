# Bettor Segmentation Model Training

Input profiles: `Data\profiles\bettor_profiles.csv`
Bettors trained: `8,000`
Features used: `18`
Cluster range tested: `3` to `8`

## Best Model Per Algorithm

algorithm  n_clusters  silhouette_score  davies_bouldin_score  calinski_harabasz_score  min_cluster_size  max_cluster_size  min_cluster_size_ratio       bic        aic  selection_score
      gmm           3            0.1661                2.1673                4373.4765              1000              4500                   0.125 -178327.7 -182303.41           0.0365
   kmeans           3            0.1823                1.8967                4694.2905              1000              3605                   0.125       NaN        NaN           0.0743

## Outputs

- `model_comparison.csv`
- `kmeans_bettor_segments.csv`
- `gmm_bettor_segments.csv`
- `combined_bettor_segments.csv`
- `kmeans_cluster_summary.csv`
- `gmm_cluster_summary.csv`
- `combined_cluster_summaries.csv`
- `bettor_segmentation_models.joblib`

K-Means gives hard, admin-friendly primary segments. GMM gives soft segment probabilities for mixed bettor behavior.
