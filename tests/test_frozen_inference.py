from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFERENCE_DIR = ROOT / "inference"
sys.path.insert(0, str(INFERENCE_DIR))

import m1_frozen_inference as m1  # noqa: E402


EXPECTED_THRESHOLD = 0.028094640664533963
EXPECTED_EVENT_CIF = 0.056738982411137256
EXPECTED_COMPETING_CIF = 0.1347475396927663


class FrozenInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads((INFERENCE_DIR / "example_case_raw.json").read_text(encoding="utf-8"))
        cls.expected = json.loads((INFERENCE_DIR / "example_case_output.json").read_text(encoding="utf-8"))
        cls.spec = m1.load_spec(INFERENCE_DIR / "m1_frozen_model_spec.json")

    def test_exact_frozen_threshold_and_alert_rule(self) -> None:
        self.assertEqual(self.spec["threshold"]["value"], EXPECTED_THRESHOLD)
        self.assertFalse(m1.is_alert(math.nextafter(EXPECTED_THRESHOLD, -math.inf), EXPECTED_THRESHOLD))
        self.assertTrue(m1.is_alert(EXPECTED_THRESHOLD, EXPECTED_THRESHOLD))
        self.assertTrue(m1.is_alert(math.nextafter(EXPECTED_THRESHOLD, math.inf), EXPECTED_THRESHOLD))

    def test_synthetic_example_matches_archived_output(self) -> None:
        features = m1.engineer_from_raw(self.raw)
        prediction = m1.predict_engineered(features, self.spec)
        self.assertAlmostEqual(prediction["m1_event_cif_6h"], EXPECTED_EVENT_CIF, places=15)
        self.assertAlmostEqual(prediction["competitor_cif_6h"], EXPECTED_COMPETING_CIF, places=15)
        self.assertEqual(prediction["threshold"], EXPECTED_THRESHOLD)
        self.assertTrue(prediction["alert"])
        self.assertEqual(features, self.expected["engineered_features"])
        for key, value in self.expected["prediction"].items():
            if isinstance(value, float):
                self.assertAlmostEqual(prediction[key], value, places=15, msg=key)
            else:
                self.assertEqual(prediction[key], value, key)

    def test_missing_continuous_value_uses_frozen_development_median(self) -> None:
        features = m1.engineer_from_raw(self.raw)
        missing = copy.deepcopy(features)
        missing["map_last"] = None
        design = m1._design(missing, self.spec["preprocessors"]["m1"])
        names = self.spec["preprocessors"]["m1"]["feature_names"]
        index = names.index("map_last")
        median = self.spec["preprocessors"]["m1"]["medians"][index]
        mean = self.spec["preprocessors"]["m1"]["means"][index]
        scale = self.spec["preprocessors"]["m1"]["scales"][index]
        self.assertAlmostEqual(design[index], (median - mean) / scale, places=15)
        prediction = m1.predict_engineered(missing, self.spec)
        self.assertTrue(math.isfinite(prediction["m1_event_cif_6h"]))


if __name__ == "__main__":
    unittest.main()
