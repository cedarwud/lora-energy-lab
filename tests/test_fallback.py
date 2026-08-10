from __future__ import annotations

import unittest

from lora_energy_lab.canonical_json import load_file
from lora_energy_lab.contracts import SCENARIO_ID
from lora_energy_lab.validation import validate_freeze_receipt, validate_result


class FallbackTests(unittest.TestCase):
    @staticmethod
    def _evidence_signature(result):
        summary = result["summary"]
        event_signature = tuple(
            (event["type"], event.get("action"), event.get("state"), tuple(event.get("packet_ids", [])))
            for event in result["events"]
            if event["type"] in {
                "POLICY_DECISION", "STATE_INTERVAL", "PACKET_ATTEMPT",
                "PACKET_DELIVERED", "PACKET_COLLISION", "PACKET_EXPIRED",
            }
        )
        return (
            summary["attempted_packets"], summary["unique_delivered_packets"],
            summary["delivered_bits"], summary["collisions"],
            summary["retransmissions"], summary["expired_packets"],
            summary["active_time_s"], summary["wake_count"],
            summary["endpoint_energy_j"], summary["service_pass"], event_signature,
        )

    def test_fallback_manifest_and_artifacts_share_identity(self) -> None:
        manifest = load_file("fallback_artifacts/manifest.json")
        self.assertEqual(manifest["scenario_id"], SCENARIO_ID)
        self.assertFalse(manifest["upstream_execution"])
        expected = [
            "baseline-A", "candidate-A", "hidden-A", "trace-a-baseline-B",
            "trace-a-candidate-B", "trace-b-B", "baseline-C", "candidate-C",
            "revision-C", "surprise-C",
        ]
        self.assertEqual([item["label"] for item in manifest["artifacts"]], expected)
        for item in manifest["artifacts"]:
            result = load_file(item["path"])
            validate_result(result)
            self.assertEqual(result["artifact_source"], "same-scenario-fallback")
            self.assertEqual(result["run_id"], item["run_id"])
            replay = load_file(item["replay_path"])
            self.assertEqual(replay["run_id"], result["run_id"])
            self.assertEqual(replay["scenario_sha256"], result["scenario_sha256"])
            if result["case_id"] in ("hidden", "trace-b", "surprise"):
                self.assertIsNotNone(result["policy"]["freeze_receipt_sha256"])
                self.assertIsNotNone(result["policy"]["predecessor_policy_sha256"])
            if (result["lab_id"], result["case_id"]) in (("B", "trace-a-baseline"), ("C", "baseline"), ("C", "candidate")):
                self.assertIsNone(result["policy"]["freeze_receipt_sha256"])
        for name in ("a", "b", "c"):
            validate_freeze_receipt(load_file(f"fallback_artifacts/receipts/{name}.json"))

    def test_each_lab_edit_changes_consequential_evidence(self) -> None:
        def result(label):
            return load_file(f"fallback_artifacts/{label}/result.json")

        self.assertNotEqual(self._evidence_signature(result("baseline-A")), self._evidence_signature(result("candidate-A")))
        self.assertNotEqual(self._evidence_signature(result("trace-a-baseline-B")), self._evidence_signature(result("trace-a-candidate-B")))
        self.assertNotEqual(self._evidence_signature(result("baseline-C")), self._evidence_signature(result("candidate-C")))
        self.assertNotEqual(self._evidence_signature(result("candidate-C")), self._evidence_signature(result("revision-C")))
