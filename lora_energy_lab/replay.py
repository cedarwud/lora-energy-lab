"""Endpoint-only replay materialization for Leo's JSON boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical_json import hash_value, write_file
from .contracts import CLAIM_BOUNDARY, ENERGY_SCOPE, REPLAY_VERSION, SCENARIO_ID


def make_endpoint_replay(result: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
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
    # The controller's replay adapter materializes one frame per result event,
    # rather than sampling only policy decisions.  This preserves state,
    # packet, and energy transitions that can share one clock timestamp.
    frames = []
    queue: list[str] = []
    radio_state = "SLEEP"
    action: str | None = None
    for index, event in enumerate(result["events"]):
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
        frames.append({
            "frame_index": index,
            "elapsed_s": event["end_s"],
            "contact_id": event["contact_id"],
            "quality_band": event["quality_band"],
            "queue_packet_ids": list(queue),
            "radio_state": radio_state,
            "action": action,
            "packet_event_ids": [event["event_id"]] if packet_ids else [],
            "cumulative_endpoint_energy_j": event["cumulative_endpoint_energy_j"],
            "service_pass": False,
        })
    if not frames:
        raise ValueError("LoRa energy endpoint result has no replayable events")
    frames[-1]["service_pass"] = result["summary"]["service_pass"]
    replay = {
        "contract_version": REPLAY_VERSION,
        "endpoint_replay_id": "sha256:" + "0" * 64,
        "endpoint_replay_input_id": input_id,
        "run_id": result["run_id"],
        "scenario_anchor_sha256": result["scenario_anchor_sha256"],
        "scenario_sha256": result["scenario_sha256"],
        "scenario_id": SCENARIO_ID,
        "lab_id": result["lab_id"],
        "case_id": result["case_id"],
        "seed": result["seed"],
        "policy": policy,
        "energy_scope": ENERGY_SCOPE,
        "units": {"time": "s", "energy": "J", "data": "bit", "rate": "bit/s", "endpoint_energy_efficiency": "bit/J"},
        "clock": scenario["clock"],
        "frames": frames,
        "outcome": {
            **result["summary"],
            "energy_breakdown_j": result["energy_breakdown_j"],
        },
        "artifact_source": result["artifact_source"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    replay_identity = {
        "endpoint_replay_contract_version": REPLAY_VERSION,
        "endpointReplayInputId": input_id,
        "run_id": result["run_id"],
        "scenario_anchor_sha256": result["scenario_anchor_sha256"],
        "scenario_sha256": result["scenario_sha256"],
    }
    replay["endpoint_replay_id"] = hash_value(replay_identity)
    return replay


def write_endpoint_replay(result_path: str | Path, replay: dict[str, Any]) -> Path:
    target = Path(result_path).parent / "endpoint-replay.json"
    write_file(target, replay)
    return target
