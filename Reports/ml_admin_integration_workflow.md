# ML Admin Integration Workflow

This workflow updates the offline Stone Odds bettor behavior analytics used by the admin ML dashboard.

## Admin Dashboard

Open the admin portal and use:

```text
http://127.0.0.1:9006/admin/ml/bettor-segments/
```

The page reads model outputs from:

```text
Data\models\bettor_segmentation\
```

It shows:

- approved 3-cluster K-Means segments
- GMM comparison segments
- promotion targeting signals
- responsible gambling risk hints
- favorite betting time bands
- sample bettor-to-cluster assignments

## Current Business Decision

Keep `3` clusters for model version 1.

Reason:

- K-Means and GMM both selected `3` as the strongest first structure.
- Cluster sizes are balanced.
- Forcing `5` or `6` clusters would create more admin categories, but the current batch does not strongly support those extra groups yet.

Use the 3 ML clusters as the base, then use promotion overlays such as:

- `High Odds Boost`
- `Night-Time Campaign`
- `General Personalized Offer`
- `Accumulator Insurance / Combo Boost`

## Repeatable Raw Batch Workflow

When a new raw batch is added to `RawData`, run these commands from `C:\stoney`:

```powershell
.\.venv\Scripts\python.exe tools\audit_raw_bets.py "RawData\Bets- first batch of data.xlsx"
.\.venv\Scripts\python.exe tools\clean_betting_data.py "RawData\Bets- first batch of data.xlsx"
.\.venv\Scripts\python.exe tools\build_bettor_profiles.py
.\.venv\Scripts\python.exe tools\train_bettor_segmentation_models.py
```

Replace the raw file path with the latest batch filename.

## Later Supervised ML Requirement

Promotion-response prediction is not trained yet because it needs promotion outcome history.

Required future fields:

- promotion sent
- promotion type
- sent time
- user viewed/clicked
- user claimed bonus
- user deposited after promotion
- user placed bet after promotion
- stake after promotion
- revenue/profit after promotion

Once those exist, add supervised models for:

- promotion response prediction
- bettor lifetime value
- odds sensitivity
