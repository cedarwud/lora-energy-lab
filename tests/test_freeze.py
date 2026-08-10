from __future__ import annotations

import unittest

from lora_energy_lab.canonical_json import hash_file
from lora_energy_lab.contracts import case_for, load_scenario
from lora_energy_lab.policy_api import read_policy
from lora_energy_lab.result_writer import make_freeze_receipt
from lora_energy_lab.validation import validate_freeze_receipt


class FreezeTests(unittest.TestCase):
    def test_receipt_is_content_addressed(self) -> None:
        scenario = load_scenario("scenarios/ntpu-energy-decision-01.json")
        policy = read_policy("student_policy.baseline.py")
        case = case_for(scenario, "A", "candidate")
        receipt = make_freeze_receipt(
            scenario, "A", "candidate", "lab-a-pace-rest", policy.policy_sha256,
            policy.policy_sha256, hash_file("requirements-lock.txt"), case["seed_role"], case["seed"],
        )
        self.assertEqual(validate_freeze_receipt(receipt), receipt)
        self.assertTrue(receipt["receipt_sha256"].startswith("sha256:"))
