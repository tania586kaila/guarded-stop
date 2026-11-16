# AI Guard — model evaluation

- Model: `guard-gbdt-v1 (synthetic, seed 42)` — scikit-learn `HistGradientBoostingClassifier`
- Data: synthetic series from `gen_data.py` (wick / trend / chop), features from the first 30 post-breach ticks (the same window the live guard uses)
- Split: train 900 / held-out test 300 (stratified, seed 42)
- Target: 1 = EXECUTE (trend reversal), 0 = VETO (wick + chop)
- Generated: 2026-11-16 09:37 UTC

## Headline metrics (held-out test set)

- **Accuracy: 0.9967**
- Probability-threshold (0.5) accuracy check: 0.9967

| class | precision | recall | F1 | support |
|---|---|---|---|---|
| VETO (0) | 1.0000 | **0.9950** | 0.9975 | 200 |
| EXECUTE (1) | 0.9901 | **1.0000** | 0.9950 | 100 |

Recall is the number that matters per class: VETO recall = share of non-reversals where the position was kept; EXECUTE recall = share of real reversals where the stop actually fired.

## Correct-action rate by scenario

| scenario | correct action | rate | n |
|---|---|---|---|
| wick | VETO | 1.0000 | 95 |
| trend | EXECUTE | 1.0000 | 100 |
| chop | VETO | 0.9905 | 105 |

## Confusion matrix

Rows = true class, columns = predicted class.

|  | pred VETO | pred EXECUTE |
|---|---|---|
| true VETO | 199 | 1 |
| true EXECUTE | 0 | 100 |

## Feature importance (permutation, held-out set)

| feature | importance (accuracy drop) |
|---|---|
| drawdown_depth | 0.0057 |
| rebound_ratio | 0.0033 |
| end_below_stop | 0.0017 |
| n_stop_crossings | 0.0000 |
| vol_shock | 0.0000 |
| vol_post | 0.0000 |
| volume_proxy | 0.0000 |
| volume_proxy_ratio | 0.0000 |
| post_slope | 0.0000 |
| vol_pre | 0.0000 |
| rebound_speed | 0.0000 |
| recovery_time_s | 0.0000 |
| time_to_trough_s | 0.0000 |
| longest_below_s | 0.0000 |
| breach_duration_ratio | 0.0000 |
| drop_from_pre | 0.0000 |

## Notes

- Synthetic-data model: it demonstrates the guard loop and gives the demo reproducible numbers; it is not trained on real market data.
- The costly error is a false EXECUTE on a wick (selling the bottom); the threshold in `guard.py` can be raised above 0.5 to trade EXECUTE recall for fewer false executions.
