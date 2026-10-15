from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


EXACT_THRESHOLD = 0.028094640664533963
EXPECTED_EVENT_CIF = 0.056738982411137256
EXPECTED_COMPETING_CIF = 0.1347475396927663
EXPECTED_MAX_ERROR = 1.1102230246251565e-16
ALLOWED_REPRODUCTION_COLUMNS = ["expected", "recomputed", "absolute_error"]
IDENTIFIER_TOKENS = {
    "subject_id", "hadm_id", "stay_id", "patientunitstayid", "uniquepid",
    "hospitalid", "patienthealthsystemstayid", "charttime", "storetime",
    "admittime", "dischtime", "date", "dob", "name", "address", "phone",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    return {
        "command": [Path(command[0]).name, *command[1:]],
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "passed": completed.returncode == 0,
    }


def load_public_inference(root: Path):
    sys.path.insert(0, str(root / "inference"))
    import m1_frozen_inference as m1  # type: ignore
    return m1


def comparable_spec(spec: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(json.dumps(spec))
    copy.pop("source_files", None)
    return copy


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit frozen M1 public-release materials")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-prototype", type=Path)
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--remote-status", default="local_only_pre_release")
    args = parser.parse_args()

    root = args.root.resolve()
    inference_dir = root / "inference"
    validation_dir = root / "validation"
    calculator = root / "calculator" / "index.html"
    docs = root / "docs" / "index.html"
    spec_path = inference_dir / "m1_frozen_model_spec.json"
    example_raw_path = inference_dir / "example_case_raw.json"
    example_output_path = inference_dir / "example_case_output.json"
    reproduction_path = validation_dir / "inference_reproduction_sample_1000.csv"
    original_audit_path = validation_dir / "M1_TOOL_REPRODUCTION_AUDIT.json"

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    raw = json.loads(example_raw_path.read_text(encoding="utf-8"))
    expected = json.loads(example_output_path.read_text(encoding="utf-8"))
    original_audit = json.loads(original_audit_path.read_text(encoding="utf-8"))
    m1 = load_public_inference(root)
    features = m1.engineer_from_raw(raw)
    prediction = m1.predict_engineered(features, spec)

    with reproduction_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = list(reader)
    max_error = max(float(row["absolute_error"]) for row in rows)
    identifier_hits = sorted({column for column in columns if column.lower() in IDENTIFIER_TOKENS})
    reproduction_numeric_only = all(
        all(cell is not None and cell.strip() != "" and np.isfinite(float(cell)) for cell in row.values())
        for row in rows
    )

    html_text = calculator.read_text(encoding="utf-8")
    prohibited_network_tokens = [token for token in ("fetch(", "XMLHttpRequest", "WebSocket", "navigator.sendBeacon") if token in html_text]
    prohibited_local_paths = []
    local_path_markers = ("E:" + "\\Explore", "C:" + "\\Users")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".py", ".html", ".csv", ".cff", ".txt"}:
            continue
        if path.name in {"PRE_RELEASE_AUDIT.json", "PRE_RELEASE_AUDIT.md", "FILE_SHA256.csv"}:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if any(marker in text for marker in local_path_markers):
            prohibited_local_paths.append(path.relative_to(root).as_posix())

    source_match: bool | None = None
    if args.source_prototype:
        source_spec = json.loads((args.source_prototype / "m1_frozen_model_spec.json").read_text(encoding="utf-8"))
        source_match = comparable_spec(source_spec) == comparable_spec(spec)

    python_tests = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_frozen_inference.py", "-v"],
        root,
    )
    html_tests = run([str(args.node), "tests/test_html_calculator.mjs"], root)

    excluded = {
        "validation/PRE_RELEASE_AUDIT.json",
        "validation/PRE_RELEASE_AUDIT.md",
        "validation/FILE_SHA256.csv",
    }
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if rel not in excluded:
            hashes[rel] = sha256(path)

    checks = {
        "exact_threshold_matches": spec["threshold"]["value"] == EXACT_THRESHOLD == prediction["threshold"],
        "synthetic_event_cif_matches": abs(prediction["m1_event_cif_6h"] - EXPECTED_EVENT_CIF) <= 1e-15,
        "synthetic_competing_cif_matches": abs(prediction["competitor_cif_6h"] - EXPECTED_COMPETING_CIF) <= 1e-15,
        "synthetic_alert_true": prediction["alert"] is True,
        "synthetic_output_matches": features == expected["engineered_features"],
        "calculator_and_docs_identical": sha256(calculator) == sha256(docs),
        "calculator_contains_exact_threshold": repr(EXACT_THRESHOLD) in html_text,
        "calculator_uses_inclusive_rule": "ce>=SPEC.threshold.value" in html_text,
        "calculator_has_no_network_calls": not prohibited_network_tokens,
        "no_local_absolute_paths": not prohibited_local_paths,
        "reproduction_columns_allowlisted": columns == ALLOWED_REPRODUCTION_COLUMNS,
        "reproduction_has_no_identifier_columns": not identifier_hits,
        "reproduction_numeric_only": reproduction_numeric_only,
        "reproduction_rows_1000": len(rows) == 1000,
        "reproduction_max_error_matches": abs(max_error - EXPECTED_MAX_ERROR) <= 1e-30,
        "reproduction_audit_passed": original_audit.get("passed") is True,
        "model_not_refit": original_audit.get("model_refit") is False,
        "threshold_not_changed": original_audit.get("threshold_changed") is False,
        "python_tests_passed": python_tests["passed"],
        "html_parity_test_passed": html_tests["passed"],
    }
    if source_match is not None:
        checks["freeze_critical_spec_matches_source"] = source_match

    node_version = run([str(args.node), "--version"], root)
    audit = {
        "audit_type": "frozen_m1_public_release_preflight",
        "release": "v1.0.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "remote_status": args.remote_status,
        "repository": "https://github.com/lwg550-maker/Neurological-Deterioration-Assessment",
        "pages_url": "https://lwg550-maker.github.io/Neurological-Deterioration-Assessment/",
        "release_url": "https://github.com/lwg550-maker/Neurological-Deterioration-Assessment/releases/tag/v1.0.0",
        "commit_sha": args.commit_sha,
        "model_refit": False,
        "threshold_changed": False,
        "threshold": EXACT_THRESHOLD,
        "threshold_display": 0.0281,
        "threshold_rule": "inclusive score >= threshold",
        "threshold_selection": "MIMIC-IV 2017-2019 freeze set; event-level target sensitivity 80%; not validation set, Youden index, or 0.5",
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "platform": platform.platform(),
            "node": node_version["stdout"],
        },
        "synthetic_example": {
            "m1_event_cif_6h": prediction["m1_event_cif_6h"],
            "competitor_cif_6h": prediction["competitor_cif_6h"],
            "threshold": prediction["threshold"],
            "alert": prediction["alert"],
        },
        "reproduction_audit": {
            "columns": columns,
            "rows": len(rows),
            "maximum_absolute_error": max_error,
            "tolerance": original_audit.get("tolerance"),
            "identifier_column_hits": identifier_hits,
            "contains_patient_level_source_fields": False,
        },
        "static_checks": {
            "prohibited_network_tokens": prohibited_network_tokens,
            "prohibited_local_paths": prohibited_local_paths,
        },
        "test_runs": {"python": python_tests, "html": html_tests},
        "checks": checks,
        "passed": all(checks.values()),
        "file_sha256": hashes,
        "hash_exclusions": sorted(excluded),
    }

    json_path = validation_dir / "PRE_RELEASE_AUDIT.json"
    md_path = validation_dir / "PRE_RELEASE_AUDIT.md"
    csv_path = validation_dir / "FILE_SHA256.csv"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "sha256"])
        writer.writerows(hashes.items())

    lines = [
        "# Frozen M1 v1.0.0 Public-Release Preflight Audit",
        "",
        f"- Overall status: **{'PASS' if audit['passed'] else 'FAIL'}**",
        f"- Remote status: `{audit['remote_status']}`",
        f"- Model refit: `{audit['model_refit']}`",
        f"- Threshold changed: `{audit['threshold_changed']}`",
        f"- Exact threshold: `{audit['threshold']}`",
        f"- Synthetic M1 six-hour score: `{prediction['m1_event_cif_6h']}`",
        f"- Synthetic competing-event CIF: `{prediction['competitor_cif_6h']}`",
        f"- Synthetic alert: `{prediction['alert']}`",
        f"- Reproduction rows: `{len(rows)}`",
        f"- Maximum absolute reproduction error: `{max_error:.17g}`",
        f"- Identifier-like columns in reproduction CSV: `{identifier_hits}`",
        f"- Browser network-call tokens found: `{prohibited_network_tokens}`",
        f"- Local absolute paths found: `{prohibited_local_paths}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {'PASS' if value else 'FAIL'} — `{name}`" for name, value in checks.items())
    lines += [
        "",
        "## Reproducibility boundary",
        "",
        "The included 1,000-row file contains only numerical expected, recomputed, and absolute-error columns. It contains no patient, encounter, hospital, date, or source-row identifier. Restricted MIMIC-IV and eICU-CRD patient-level data are not included.",
        "",
        "File hashes are recorded in `PRE_RELEASE_AUDIT.json` and `FILE_SHA256.csv`. The three audit-output files are excluded from their own hash set to avoid self-referential checksums.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"passed": audit["passed"], "audit_json": str(json_path), "audit_md": str(md_path)}, ensure_ascii=False))
    raise SystemExit(0 if audit["passed"] else 1)


if __name__ == "__main__":
    main()
