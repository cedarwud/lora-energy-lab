from __future__ import annotations

import unittest

from lora_energy_lab.contracts import BLOCK_IDS
from lora_energy_lab.policy_api import PolicyError, compare_outside, load_policy, parse_policy_source, read_policy


class PolicyTests(unittest.TestCase):
    def test_baseline_is_bounded_and_legal(self) -> None:
        current = read_policy("student_policy.py")
        baseline = read_policy("student_policy.baseline.py")
        self.assertEqual(current.policy_sha256, baseline.policy_sha256)
        _, function = load_policy("student_policy.py", BLOCK_IDS["A"])
        observation = type("Observation", (), {
            "contact_open": False, "quality_band": 0, "stable_steps": 0,
            "send_mode_active": False, "steps_since_send": 0,
            "contact_remaining_s": 0, "queue_size": 1,
            "urgent_pending": False, "urgent_due_in_s": None,
            "previous_action": None, "elapsed_s": 0,
        })()
        self.assertEqual(function(observation), "SLEEP")

    def test_only_active_block_may_differ(self) -> None:
        baseline = read_policy("student_policy.baseline.py")
        edited = baseline.source.replace(b"REST_DURING_GAP = SLEEP", b"REST_DURING_GAP = WAIT")
        surface = parse_policy_source(edited)
        compare_outside(surface, baseline, BLOCK_IDS["A"])
        with self.assertRaises(PolicyError):
            compare_outside(surface, baseline, BLOCK_IDS["B"])

    def test_imports_and_arbitrary_calls_are_rejected(self) -> None:
        baseline = read_policy("student_policy.baseline.py")
        with self.assertRaises(PolicyError):
            parse_policy_source(b"import os\n" + baseline.source)
        bad = baseline.source.replace(b"return WAIT", b"return open('x')", 1)
        with self.assertRaises(PolicyError):
            parse_policy_source(bad)
