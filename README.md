# Neurological Deterioration Assessment

This repository contains the frozen M1 research-use inference tool associated with the manuscript **“Prioritizing Repeat Neurological Assessment Before Algorithm-Confirmed GCS Deterioration in Adults With Acute Brain Injury in the ICU Using Dynamic Prediction.”**

M1 is a **dynamic prioritization tool for repeat neurological assessment**. Every four hours, it combines recent GCS motor, mean arterial pressure, heart rate, sodium, demographic, diagnostic, mechanical-ventilation, and ICU-time information to estimate the model's six-hour cumulative incidence for confirmed neurological deterioration in the presence of competing events.

> **Research-use prototype only.** This software has not been prospectively validated as a clinical decision-support system. An alert is intended only to prioritize a standardized repeat neurological assessment. It does not directly recommend or trigger CT, medication, external ventricular drainage, surgery, or any other intervention. Calibration limitations restrict interpretation of the output as an absolute probability.

## Use the browser calculator

The online calculator is intended to be available at:

**https://lwg550-maker.github.io/Neurological-Deterioration-Assessment/**

The same single-file calculator is stored at [`calculator/index.html`](calculator/index.html) and [`docs/index.html`](docs/index.html). It can be downloaded and opened locally. All calculations run in the browser; the page contains no server call and does not transmit entered data.

## Repository contents

| Path | Purpose |
|---|---|
| `calculator/index.html` | Standalone browser calculator |
| `inference/m1_frozen_inference.py` | Python reference implementation; no fitting or calibration |
| `inference/m1_frozen_model_spec.json` | Frozen variables, preprocessing, coefficients, baseline intercepts, competing-risk function, and threshold provenance |
| `inference/example_case_raw.json` | Synthetic worked input; not a real patient |
| `inference/example_case_output.json` | Archived expected output for the synthetic case |
| `validation/inference_reproduction_sample_1000.csv` | Deidentified numerical reproduction audit with only expected value, recomputed value, and absolute error |
| `validation/M1_TOOL_REPRODUCTION_AUDIT.json` | Original 1,000-anchor reproduction audit |
| `tests/` | Automated Python and browser-calculator parity checks |

The repository provides frozen inference and its reproducibility checks. Restricted cohort extraction data and patient-level MIMIC-IV/eICU-CRD data are not distributed.

## Inputs and frozen time windows

The compact calculator accepts:

- age (capped at 89 years, with an over-89 indicator), sex, overlapping ICH/SAH/SDH/TBI indicators, and ICU elapsed time;
- mechanical ventilation observed during the preceding four hours;
- eligible GCS motor observations from the preceding six hours;
- valid MAP and heart-rate observations from the preceding six hours; and
- valid sodium observations from the preceding 24 hours.

Entered observations must already satisfy the study's Tier C eligibility, availability-time, physiologic-range, sedation, and source-deduplication rules. Full feature definitions and frozen preprocessing parameters are in [`inference/m1_frozen_model_spec.json`](inference/m1_frozen_model_spec.json).

## Install and run the Python reference implementation

Tested for this release with Python 3.12.14 and NumPy 2.3.5. The declared compatibility range is in `requirements.txt`.

```bash
python -m pip install -r requirements.txt
python inference/m1_frozen_inference.py inference/example_case_raw.json --output reproduced_example.json
```

Module use:

```python
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path("inference").resolve()))
from m1_frozen_inference import engineer_from_raw, load_spec, predict_engineered

raw = json.loads(Path("inference/example_case_raw.json").read_text(encoding="utf-8"))
spec = load_spec(Path("inference/m1_frozen_model_spec.json"))
features = engineer_from_raw(raw)
result = predict_engineered(features, spec)
print(result)
```

The Python program reconstructs frozen preprocessing, six one-hour cause-specific event hazards, six competing-event hazards, the six-hour cumulative incidence function, and the inclusive alert rule. It does **not** fit or recalibrate either prediction model and does **not** optimize the threshold.

## Frozen threshold and expected synthetic output

The exact M1 alert threshold is:

```text
0.028094640664533963
```

The calculator may display this value as `0.0281`, but all alert decisions use the exact value with the inclusive rule `score >= threshold`. The threshold was prespecified in the MIMIC-IV 2017–2019 freeze set to target 80% event-level sensitivity, then applied unchanged to the 2020–2022 internal temporal validation set and the eICU external validation. It was not selected in a validation set, by the Youden index, or as a default 0.5 cutoff. Its low value should be interpreted in the context of the low absolute six-hour event rate.

For the included synthetic case, the expected results are:

- M1 six-hour event model score/CIF: `0.056738982411137256`
- competing-event six-hour CIF: `0.1347475396927663`
- exact threshold: `0.028094640664533963`
- alert: `true`

## Reproducibility checks

Run both test suites:

```bash
python -m unittest discover -s tests -p "test_frozen_inference.py" -v
node tests/test_html_calculator.mjs
```

The archived 1,000-anchor audit reported a maximum absolute difference of `1.1102230246251565e-16` between frozen predictions and the reference implementation, below the prespecified tolerance of `1e-12`. The published CSV contains only numerical expected, recomputed, and error columns; it contains no patient, encounter, hospital, date, or source-row identifier.

## Data availability and privacy

MIMIC-IV and eICU-CRD are credentialed-access databases governed by PhysioNet data-use agreements. Their patient-level data and derived row-level source data cannot be redistributed through this repository. Eligible users must obtain the databases from PhysioNet and comply with the applicable agreements. The worked example is synthetic.

## License and versioning

Code is released under the [MIT License](LICENSE). The frozen public release is `v1.0.0`. Model parameters, preprocessing, and the exact threshold are versioned together; users should cite a fixed release or commit for reproducible use.
