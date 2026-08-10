from __future__ import annotations

import unittest

from lora_energy_lab.canonical_json import CanonicalJSONError, hash_value, loads
from lora_energy_lab.contracts import load_scenario


class ContractTests(unittest.TestCase):
    def test_frozen_scenario_identity(self) -> None:
        scenario = load_scenario("scenarios/ntpu-energy-decision-01.json")
        self.assertEqual(
            hash_value(scenario["scenario_anchor"]),
            scenario["scenario_anchor_sha256"],
        )
        without_hash = dict(scenario)
        without_hash.pop("scenario_sha256")
        self.assertEqual(hash_value(without_hash), scenario["scenario_sha256"])
        self.assertEqual({(case["lab_id"], case["case_id"]) for case in scenario["cases"]}, {
            ("A", "baseline"), ("A", "candidate"), ("A", "hidden"),
            ("B", "trace-a-baseline"), ("B", "trace-a-candidate"), ("B", "trace-b"),
            ("C", "baseline"), ("C", "candidate"), ("C", "revision"), ("C", "surprise"),
        })

    def test_duplicate_keys_and_nonfinite_numbers_reject(self) -> None:
        with self.assertRaises(CanonicalJSONError):
            loads('{"a": 1, "a": 2}')
        with self.assertRaises(CanonicalJSONError):
            loads('{"a": NaN}')
