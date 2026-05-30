# Raw Betting Data Audit

Input file: `RawData\second second batch.xlsx`
Rows: `500,000`
Columns: `20`
Usable rows for first-pass ML analytics: `500,000` (`100.0%`)

## Schema Check

Missing expected columns: `None`
Extra columns: `None`

## Date And Number Quality

- Invalid `placed_at` values: `0`
- Invalid `settled_at` values: `0`
- Invalid numeric `stake` values: `0`
- Invalid numeric `odds` values: `0`
- Invalid numeric `payout_amount` values: `0`
- Invalid numeric `profit` values: `0`
- Business rule failure `stake_lte_0`: `0`
- Business rule failure `odds_lte_1`: `0`
- Business rule failure `payout_lt_0`: `0`

## Dataset Profile

- Unique players: `8,000`
- Unique slips: `486,504`
- Unique bets: `500,000`
- Placed range: `2023-01-01 00:00:10` to `2026-12-31 23:48:33`
- Settled range: `2023-01-01 00:01:17` to `2026-12-31 23:49:45`
- Stake range: `1.0` to `50.0`, average `11.42`
- Odds range: `4.0` to `8.0`, average `6.0`
- Total payout: `8,588,419.82`
- Total profit: `2,878,972.82`
- Average settlement time: `47.53` seconds
- Maximum settlement time: `90.0` seconds

## Duplicate Signals

- Rows sharing a repeated `bet_id`: `0`
- Rows sharing the event key `player_id, slip_id, game_round_pk, character_id, option_code, stake, odds, placed_at`: `0`

Repeated `option_code` values are treated as popularity/frequency signals, not duplicates.

## Top Option Codes

| option_code | count |
| --- | --- |
| D3 | 35649 |
| D2 | 35279 |
| F1 | 35252 |
| F5 | 35114 |
| F2 | 35107 |
| D1 | 35034 |
| F4 | 34998 |
| F3 | 34941 |
| D5 | 34937 |
| D4 | 34812 |

## Bets By Time Band

| placed_time_band | bet_count |
| --- | --- |
| Midnight | 100475 |
| Morning | 99691 |
| Lunch | 99449 |
| Afternoon | 75123 |
| Evening | 65340 |
| Night | 59922 |

## Output Tables

- `bet_status_counts.csv`
- `bet_type_counts.csv`
- `bets_by_day.csv`
- `bets_by_hour.csv`
- `bets_by_month.csv`
- `bets_by_time_band.csv`
- `bets_by_week.csv`
- `bets_by_year.csv`
- `day_hour_heatmap.csv`
- `missing_values.csv`
- `settlement_result_counts.csv`
- `top_characters.csv`
- `top_option_codes.csv`
