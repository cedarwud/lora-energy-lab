from __future__ import annotations

import unittest

from lora_energy_lab.canonical_json import hash_value, load_file
from lora_energy_lab.contracts import REPLAY_VERSION
from lora_energy_lab.replay import make_endpoint_replay


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenario = load_file("scenarios/ntpu-energy-decision-01.json")
        cls.result = load_file("fallback_artifacts/baseline-A/result.json")
        cls.replay = make_endpoint_replay(cls.result, cls.scenario)

    def test_endpoint_replay_id_uses_camel_case_input_identity(self) -> None:
        result = self.result
        policy = result["policy"]
        input_identity = {
            "contract_version": REPLAY_VERSION,
            "scenario_anchor_sha256": result["scenario_anchor_sha256"],
            "scenario_sha256": result["scenario_sha256"],
            "lab_id": result["lab_id"],
            "case_id": result["case_id"],
            "seed": result["seed"],
            "policy_sha256": policy["policy_sha256"],
            "predecessor_policy_sha256": policy["predecessor_policy_sha256"],
            "freeze_receipt_sha256": policy["freeze_receipt_sha256"],
        }
        input_id = hash_value(input_identity)
        expected = hash_value({
            "endpoint_replay_contract_version": REPLAY_VERSION,
            "endpointReplayInputId": input_id,
            "run_id": result["run_id"],
            "scenario_anchor_sha256": result["scenario_anchor_sha256"],
            "scenario_sha256": result["scenario_sha256"],
        })
        self.assertEqual(self.replay["endpoint_replay_input_id"], input_id)
        self.assertEqual(self.replay["endpoint_replay_id"], expected)

    def test_frames_materialize_every_event_and_terminal_service(self) -> None:
        events = self.result["events"]
        frames = self.replay["frames"]
        self.assertEqual(len(frames), len(events))
        self.assertEqual(frames[0]["elapsed_s"], 0)
        self.assertEqual(frames[-1]["elapsed_s"], self.scenario["clock"]["duration_s"])
        self.assertEqual(
            [frame["elapsed_s"] for frame in frames],
            [event["end_s"] for event in events],
        )
        self.assertTrue(all(not frame["service_pass"] for frame in frames[:-1]))
        self.assertEqual(frames[-1]["service_pass"], self.result["summary"]["service_pass"])

        queue: list[str] = []
        packet_event_ids: list[str] = []
        radio_state = "SLEEP"
        action = None
        for event, frame in zip(events, frames):
            packet_ids = event.get("packet_ids", [])
            if event["type"] == "PACKET_GENERATED":
                queue.extend(packet_id for packet_id in packet_ids if packet_id not in queue)
            if event["type"] in {"PACKET_DELIVERED", "PACKET_EXPIRED"}:
                queue[:] = [packet_id for packet_id in queue if packet_id not in packet_ids]
            if event["type"] == "POLICY_DECISION":
                action = event["action"]
            if event["type"] == "WAKE":
                radio_state = "WAKE"
            elif event["type"] == "STATE_INTERVAL":
                radio_state = event["state"]
            expected_packet_event_ids = [event["event_id"]] if packet_ids else []
            packet_event_ids.extend(expected_packet_event_ids)
            self.assertEqual(frame["queue_packet_ids"], queue)
            self.assertEqual(frame["radio_state"], radio_state)
            self.assertEqual(frame["action"], action)
            self.assertEqual(frame["packet_event_ids"], expected_packet_event_ids)
            self.assertEqual(frame["cumulative_endpoint_energy_j"], event["cumulative_endpoint_energy_j"])
        self.assertEqual(len(packet_event_ids), len(set(packet_event_ids)))
        self.assertEqual(frames[-1]["queue_packet_ids"], [])


if __name__ == "__main__":
    unittest.main()
