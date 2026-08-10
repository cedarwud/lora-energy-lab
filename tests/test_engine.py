from __future__ import annotations

import unittest

from lora_energy_lab.canonical_json import hash_file
from lora_energy_lab.contracts import case_for, load_scenario
from lora_energy_lab.engine import run_simulation
from lora_energy_lab.policy_api import load_policy
from lora_energy_lab.replay import make_endpoint_replay
from lora_energy_lab.validation import validate_result


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = load_scenario("scenarios/ntpu-energy-decision-01.json")
        cls.lock_sha = hash_file("requirements-lock.txt")
        cls.surface, policy_function = load_policy("student_policy.py", "lab-a-pace-rest")
        cls.policy_function = staticmethod(policy_function)
        cls.case = case_for(cls.scenario, "A", "baseline")

    def test_same_seed_and_policy_are_byte_stable(self) -> None:
        first = run_simulation(
            self.scenario, self.case, self.surface.policy_sha256, self.policy_function,
            lock_sha256=self.lock_sha, python_version="3.11.9",
        )
        second = run_simulation(
            self.scenario, self.case, self.surface.policy_sha256, self.policy_function,
            lock_sha256=self.lock_sha, python_version="3.11.9",
        )
        self.assertEqual(first, second)
        validate_result(first)

    def test_state_energy_and_replay_are_present(self) -> None:
        result = run_simulation(
            self.scenario, self.case, self.surface.policy_sha256, self.policy_function,
            lock_sha256=self.lock_sha, python_version="3.11.9",
        )
        states = {event.get("state") for event in result["events"] if event["type"] == "STATE_INTERVAL"}
        self.assertTrue({"SLEEP", "AWAKE_IDLE", "PROCESS", "TX", "RX"} <= states)
        self.assertGreaterEqual(result["summary"]["wake_count"], 1)
        self.assertAlmostEqual(
            sum(result["energy_breakdown_j"].values()),
            result["summary"]["endpoint_energy_j"],
            places=6,
        )
        replay = make_endpoint_replay(result, self.scenario)
        self.assertEqual(replay["run_id"], result["run_id"])
        self.assertEqual(replay["energy_scope"], "endpoint-radio-and-processing-course-assumptions")
        self.assertFalse(result["runner_provenance"]["upstream_execution"])

    def test_every_send_decision_has_a_matching_attempt(self) -> None:
        result = run_simulation(
            self.scenario, self.case, self.surface.policy_sha256, self.policy_function,
            lock_sha256=self.lock_sha, python_version="3.11.9",
        )
        events = result["events"]
        send_actions = {"SEND_ONE", "SEND_URGENT", "FLUSH_BATCH"}
        for index, event in enumerate(events):
            if event["type"] != "POLICY_DECISION" or event["action"] not in send_actions:
                continue
            next_decision = next(
                (candidate for candidate in range(index + 1, len(events)) if events[candidate]["type"] == "POLICY_DECISION"),
                len(events),
            )
            attempts = [
                candidate for candidate in events[index + 1:next_decision]
                if candidate["type"] == "PACKET_ATTEMPT" and candidate.get("action") == event["action"]
            ]
            self.assertTrue(attempts, f"phantom {event['action']} decision at event {index}")

    def test_required_expiry_is_not_not_applicable(self) -> None:
        result = run_simulation(
            self.scenario, self.case, self.surface.policy_sha256, self.policy_function,
            lock_sha256=self.lock_sha, python_version="3.11.9",
        )
        self.assertIn("urgent-1", {
            packet_id for event in result["events"]
            if event["type"] == "PACKET_EXPIRED"
            for packet_id in event["packet_ids"]
        })
        self.assertEqual(result["summary"]["freshness_status"], "expired")
