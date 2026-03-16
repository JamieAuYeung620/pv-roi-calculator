# Empirical Load Archetype Validation Summary

- Load model version: `uk_empirical_v1`
- Validation schema version: `1.0`
- Source dataset: `Low Carbon London smart-meter dataset`
- Reference asset generation mode: `empirical_from_input`
- Reference asset source name: `Low Carbon London smart-meter dataset`
- Generated at (UTC): `2026-03-16T14:55:53Z`
- Validation split fraction: `0.2`

## Retained / split counts

- Retained households: `333`
- Training households: `267`
- Validation households: `66`

### Split counts by provisional archetype

| Archetype | Training | Validation |
|---|---:|---:|
| Evening-peaked household | 89 | 22 |
| Daytime-occupied household | 89 | 22 |
| Balanced household | 89 | 22 |

## Overall validation metrics

### Flattened 12 x 2 x 24 profile

- Mean MAE: `0.260053`
- Median MAE: `0.231941`
- Mean RMSE: `0.355104`
- Median RMSE: `0.300307`
- Mean Pearson correlation: `0.702713`

### Weekday / weekend 24 h fallback profile

- Mean MAE: `0.208404`
- Median MAE: `0.198611`
- Mean RMSE: `0.267789`
- Median RMSE: `0.247008`
- Mean Pearson correlation: `0.772290`

## Per-archetype validation metrics

| Archetype | Validation households | Mean MAE | Mean RMSE | Mean Pearson correlation |
|---|---:|---:|---:|---:|
| Evening-peaked household | 22 | 0.252205 | 0.334011 | 0.783758 |
| Daytime-occupied household | 22 | 0.319593 | 0.461359 | 0.649906 |
| Balanced household | 22 | 0.208360 | 0.269941 | 0.674476 |

## Interpretation

The held-out validation suggests that the training-only archetypes capture broad demand-timing patterns in unseen households with a mean flattened-profile RMSE of 0.355104 and a mean Pearson correlation of 0.702713. The nearest-centroid assignment matched the provisional held-out archetype label for 77.3% of validation households. This supports the use of the archetypes as a low-dimensional behavioural approximation for PV self-consumption studies, but it should still be interpreted as archetype-level validation rather than property-specific load forecasting.
