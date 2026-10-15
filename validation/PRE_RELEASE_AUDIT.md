# Frozen M1 v1.0.0 Public-Release Preflight Audit

- Overall status: **PASS**
- Remote status: `release_candidate_pre_push`
- Model refit: `False`
- Threshold changed: `False`
- Exact threshold: `0.028094640664533963`
- Synthetic M1 six-hour score: `0.056738982411137256`
- Synthetic competing-event CIF: `0.1347475396927663`
- Synthetic alert: `True`
- Reproduction rows: `1000`
- Maximum absolute reproduction error: `1.1102230246251565e-16`
- Identifier-like columns in reproduction CSV: `[]`
- Browser network-call tokens found: `[]`
- Local absolute paths found: `[]`

## Checks

- PASS — `exact_threshold_matches`
- PASS — `synthetic_event_cif_matches`
- PASS — `synthetic_competing_cif_matches`
- PASS — `synthetic_alert_true`
- PASS — `synthetic_output_matches`
- PASS — `calculator_and_docs_identical`
- PASS — `calculator_contains_exact_threshold`
- PASS — `calculator_uses_inclusive_rule`
- PASS — `calculator_has_no_network_calls`
- PASS — `no_local_absolute_paths`
- PASS — `reproduction_columns_allowlisted`
- PASS — `reproduction_has_no_identifier_columns`
- PASS — `reproduction_numeric_only`
- PASS — `reproduction_rows_1000`
- PASS — `reproduction_max_error_matches`
- PASS — `reproduction_audit_passed`
- PASS — `model_not_refit`
- PASS — `threshold_not_changed`
- PASS — `python_tests_passed`
- PASS — `html_parity_test_passed`
- PASS — `freeze_critical_spec_matches_source`

## Reproducibility boundary

The included 1,000-row file contains only numerical expected, recomputed, and absolute-error columns. It contains no patient, encounter, hospital, date, or source-row identifier. Restricted MIMIC-IV and eICU-CRD patient-level data are not included.

File hashes are recorded in `PRE_RELEASE_AUDIT.json` and `FILE_SHA256.csv`. The three audit-output files are excluded from their own hash set to avoid self-referential checksums.
