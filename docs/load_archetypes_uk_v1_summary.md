# UK Load Archetypes Summary

- Load model version: `uk_empirical_v1`
- Schema version: `1.0`
- Generation mode: `empirical_from_input`
- Source name: `Low Carbon London smart-meter dataset`
- Generated at (UTC): `2026-03-16T02:21:46Z`
- Timezone used for behaviour lookup: `Europe/London`

## Retained households

- Total retained households: `333`
- `empirical_evening_peaked`: `111` households
- `empirical_daytime_occupied`: `111` households
- `empirical_balanced`: `111` households

## Derivation notes

- Household timestamps are parsed as UTC/GMT, shifted back 30 minutes to represent the start of each half-hour measurement period, then converted to `Europe/London` for behavioural lookups.
- Rows with missing timestamps, missing household IDs, negative kWh values, or half-hour demand above the configured outlier threshold are dropped before aggregation.
- Households are retained only if they meet the configured completeness threshold and minimum number of complete hourly observations.
- Retained households are ranked by daytime-minus-evening demand share and split deterministically into evening-peaked, balanced, and daytime-occupied terciles.

## Filtering parameters

- `min_completeness`: `0.85`
- `min_complete_hours`: `2880`
- `max_halfhour_kwh`: `8.0`
- `files_processed`: `12`
- `max_sources_requested`: `12`
