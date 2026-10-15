"""Reference inference for the frozen M1 six-hour competing-risk model.

Research use only. This module reconstructs the published frozen preprocessing,
six one-hour cause-specific hazards, six-hour CIF, and frozen alert threshold.
It never fits a model or chooses a threshold.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "m1_frozen_model_spec.json"


def is_alert(score: float, threshold: float) -> bool:
    """Apply the frozen inclusive alert rule without tuning either value."""
    return float(score) >= float(threshold)


def _sigmoid(value: np.ndarray) -> np.ndarray:
    value = np.clip(np.asarray(value, dtype=float), -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-value))


def _rcs1(value: float, knots: list[float]) -> float:
    """Second column of the exact restricted-cubic-spline basis used in training."""
    x = float(value)
    k0, k1, k2 = map(float, knots)
    scale = max((k2 - k0) ** 2, 1e-12)
    term = max(x - k0, 0.0) ** 3
    term -= ((k2 - k0) / (k2 - k1)) * max(x - k1, 0.0) ** 3
    term += ((k1 - k0) / (k2 - k1)) * max(x - k2, 0.0) ** 3
    return term / scale


def _numeric(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    return float(value)


def _design(features: dict[str, Any], preprocessor: dict[str, Any]) -> np.ndarray:
    values = np.array([_numeric(features.get(name)) for name in preprocessor["feature_names"]], dtype=float)
    medians = np.asarray(preprocessor["medians"], dtype=float)
    means = np.asarray(preprocessor["means"], dtype=float)
    scales = np.asarray(preprocessor["scales"], dtype=float)
    values = np.where(np.isnan(values), medians, values)
    return (values - means) / scales


def predict_engineered(features: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Predict from the exact engineered feature dictionary used by formal analysis."""
    values = dict(features)
    values["icu_hours_rcs1"] = _rcs1(float(values["icu_hours"]), spec["rcs_knots"]["icu_hours"])
    values["age_rcs1"] = _rcs1(float(values["age"]), spec["rcs_knots"]["age"])

    x_event = _design(values, spec["preprocessors"]["m1"])
    x_comp = _design(values, spec["preprocessors"]["competing"])
    event = spec["event_model"]
    competing = spec["competing_model"]
    event_hazard = _sigmoid(
        x_event @ np.asarray(event["coefficients"], dtype=float)
        + np.asarray(event["baseline_intercepts"], dtype=float)
    )
    competitor_hazard = _sigmoid(
        x_comp @ np.asarray(competing["coefficients"], dtype=float)
        + np.asarray(competing["baseline_intercepts"], dtype=float)
    )

    total = event_hazard + competitor_hazard
    incoherent = total >= 1.0
    if np.any(incoherent):
        factor = (1.0 - 1e-8) / total[incoherent]
        event_hazard[incoherent] *= factor
        competitor_hazard[incoherent] *= factor

    survival = 1.0
    event_cif = 0.0
    competitor_cif = 0.0
    for h_event, h_comp in zip(event_hazard, competitor_hazard):
        event_cif += survival * float(h_event)
        competitor_cif += survival * float(h_comp)
        survival *= 1.0 - float(h_event) - float(h_comp)

    threshold = float(spec["threshold"]["value"])
    return {
        "m1_event_cif_6h": event_cif,
        "competitor_cif_6h": competitor_cif,
        "event_hazards_1h": event_hazard.tolist(),
        "competitor_hazards_1h": competitor_hazard.tolist(),
        "survival_6h": survival,
        "threshold": threshold,
        "alert": is_alert(event_cif, threshold),
        "rescaled_interval_hazards": int(np.sum(incoherent)),
    }


def _series_features(observations: list[dict[str, Any]], window: float) -> dict[str, Any]:
    rows = [
        (float(item["hours_before_anchor"]), float(item["value"]))
        for item in observations
        if 0.0 <= float(item["hours_before_anchor"]) <= window
    ]
    rows.sort(reverse=True)  # oldest to newest
    if not rows:
        return {"last": None, "mean": None, "slope": None, "arv": None, "count": 0}
    hours_before = np.asarray([item[0] for item in rows], dtype=float)
    values = np.asarray([item[1] for item in rows], dtype=float)
    elapsed = -hours_before
    elapsed -= elapsed[0]
    slope = float("nan")
    if len(values) >= 2:
        centered = elapsed - elapsed.mean()
        denominator = float(np.dot(centered, centered))
        if denominator > 0:
            slope = float(np.dot(centered, values - values.mean()) / denominator)
    arv = float(np.mean(np.abs(np.diff(values)))) if len(values) >= 2 else float("nan")
    return {
        "last": float(values[-1]),
        "mean": float(values.mean()),
        "slope": None if math.isnan(slope) else slope,
        "arv": None if math.isnan(arv) else arv,
        "count": int(len(values)),
    }


def engineer_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Derive the frozen feature set from compact research-calculator inputs.

    Entered observations are assumed to have passed the source validity,
    availability-time, sedation, and Tier C eligibility filters.
    """
    age_raw = float(raw["age_years"])
    gcs_rows = [
        (float(item["hours_before_anchor"]), float(item["value"]))
        for item in raw.get("gcs_motor", [])
        if 0.0 <= float(item["hours_before_anchor"]) <= 6.0
    ]
    gcs_rows.sort(reverse=True)
    if not gcs_rows:
        raise ValueError("At least one eligible GCS-M observation within 6 h is required")
    map_f = _series_features(raw.get("map", []), 6.0)
    hr_f = _series_features(raw.get("heart_rate", []), 6.0)
    na24 = [
        (float(item["hours_before_anchor"]), float(item["value"]))
        for item in raw.get("sodium", [])
        if 0.0 <= float(item["hours_before_anchor"]) <= 24.0
    ]
    na24.sort(reverse=True)
    na6 = _series_features(raw.get("sodium", []), 6.0)
    dx = raw.get("diagnoses", {})
    features = {
        "gcs_motor_last": gcs_rows[-1][1],
        "gcs_motor_delta_6h": gcs_rows[-1][1] - gcs_rows[0][1],
        "gcs_motor_recency_hours": gcs_rows[-1][0],
        "icu_hours": float(raw["icu_hours"]),
        "age": min(age_raw, 89.0),
        "age_over_89": int(age_raw > 89.0),
        "sex_male": int(bool(raw.get("sex_male", False))),
        "dx_ich": int(bool(dx.get("ich", False))),
        "dx_sah": int(bool(dx.get("sah", False))),
        "dx_sdh": int(bool(dx.get("sdh", False))),
        "dx_tbi": int(bool(dx.get("tbi", False))),
        "mechanical_ventilation": int(bool(raw.get("mechanical_ventilation", False))),
        "map_last": map_f["last"],
        "map_mean_6h": map_f["mean"],
        "map_slope_6h": map_f["slope"],
        "map_arv_6h": map_f["arv"],
        "map_count_6h": map_f["count"],
        "map_missing": int(map_f["count"] == 0),
        "heart_rate_last": hr_f["last"],
        "heart_rate_mean_6h": hr_f["mean"],
        "heart_rate_slope_6h": hr_f["slope"],
        "heart_rate_arv_6h": hr_f["arv"],
        "heart_rate_count_6h": hr_f["count"],
        "heart_rate_missing": int(hr_f["count"] == 0),
        "sodium_last": na24[-1][1] if na24 else None,
        "sodium_min_24h": min((item[1] for item in na24), default=None),
        "sodium_max_24h": max((item[1] for item in na24), default=None),
        "sodium_arv_6h": na6["arv"],
        "sodium_count_24h": len(na24),
        "sodium_missing": int(len(na24) == 0),
    }
    return features


def load_spec(path: Path = DEFAULT_SPEC) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen M1 research-use inference")
    parser.add_argument("input_json", type=Path, help="raw compact input JSON or engineered feature JSON")
    parser.add_argument("--engineered", action="store_true", help="input is already an engineered feature dictionary")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    spec = load_spec(args.spec)
    features = payload if args.engineered else engineer_from_raw(payload)
    result = {"engineered_features": features, "prediction": predict_engineered(features, spec)}
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
