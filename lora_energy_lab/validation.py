"""Fail-closed validation for generated results and freeze receipts."""

from __future__ import annotations

import math
import re
from typing import Any

from .canonical_json import hash_value
from .contracts import (
    BLOCK_IDS,
    CLAIM_BOUNDARY,
    CONTRACT_VERSION,
    ENERGY_SCOPE,
    FREEZE_VERSION,
    LEGAL_ACTIONS,
    POLICY_API_VERSION,
    RESULT_VERSION,
    SCENARIO_ID,
    UPSTREAM_COMMIT,
    UPSTREAM_REPOSITORY,
    WRAPPER_VERSION,
)

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EVENT_TYPES = {
    "POLICY_DECISION", "MODE_CHANGE", "STATE_INTERVAL", "WAKE",
    "PACKET_GENERATED", "PACKET_ATTEMPT", "PACKET_COLLISION",
    "PACKET_RETRY", "PACKET_DELIVERED", "PACKET_EXPIRED",
}
STATES = {"SLEEP", "AWAKE_IDLE", "PROCESS", "TX", "RX"}


class ResultError(ValueError):
    """A result or receipt violates the import contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ResultError(message)


def _hash(value: Any, field: str) -> None:
    _require(isinstance(value, str) and HASH_RE.match(value) is not None, f"{field} is not a sha256 hash")


def _number(value: Any, field: str) -> None:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field} must be numeric")
    _require(math.isfinite(float(value)) and float(value) >= 0, f"{field} must be finite/non-negative")


def _event_base(event: dict[str, Any], index: int, policy_sha: str, case_id: str) -> None:
    required = {"event_id", "index", "type", "start_s", "end_s", "case_id", "policy_sha256", "contact_id", "quality_band", "event_endpoint_energy_j", "cumulative_endpoint_energy_j"}
    _require(required <= event.keys(), f"event {index} missing base field")
    _require(event["event_id"] == f"evt-{index:04d}", f"event {index} ID is not stable")
    _require(event["index"] == index, f"event {index} index mismatch")
    _require(event["case_id"] == case_id, f"event {index} case mismatch")
    _require(event["policy_sha256"] == policy_sha, f"event {index} policy mismatch")
    _require(event["type"] in EVENT_TYPES, f"event {index} type is unknown")
    _number(event["start_s"], f"event {index} start")
    _number(event["end_s"], f"event {index} end")
    _require(event["end_s"] >= event["start_s"], f"event {index} has negative duration")
    _require(event["contact_id"] is None or isinstance(event["contact_id"], str), f"event {index} contact")
    _require(event["quality_band"] is None or event["quality_band"] in (0, 1, 2, 3), f"event {index} quality")
    _number(event["event_endpoint_energy_j"], f"event {index} energy")
    _number(event["cumulative_endpoint_energy_j"], f"event {index} cumulative energy")

    if event["type"] == "POLICY_DECISION":
        _require(event.get("action") in LEGAL_ACTIONS, f"event {index} action")
        _require(isinstance(event.get("observation"), dict), f"event {index} observation")
    elif event["type"] == "MODE_CHANGE":
        _require(event.get("from_mode") in ("SEND_READY", "REST"), f"event {index} from_mode")
        _require(event.get("to_mode") in ("SEND_READY", "REST"), f"event {index} to_mode")
    elif event["type"] == "STATE_INTERVAL":
        _require(event.get("state") in STATES, f"event {index} state")
        _require(event["end_s"] > event["start_s"], f"event {index} state duration")
    elif event["type"] == "WAKE":
        _require(event.get("outcome_code") in ("wake-complete", "wake-missed-contact"), f"event {index} wake outcome")
    elif event["type"] == "PACKET_ATTEMPT":
        _require(event.get("packet_ids") and isinstance(event["packet_ids"], list), f"event {index} packet IDs")
        _require(event.get("action") in ("SEND_ONE", "SEND_URGENT", "FLUSH_BATCH"), f"event {index} packet action")
    elif event["type"] == "PACKET_RETRY":
        _require(event.get("packet_ids") and event.get("attempt_number", 0) >= 2, f"event {index} retry")
    else:
        _require(event.get("packet_ids") and isinstance(event["packet_ids"], list), f"event {index} packet IDs")


def validate_result(result: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scenario_id", "scenario_sha256", "scenario_anchor_sha256",
        "run_id", "lab_id", "case_id", "run_role", "seed", "seed_role",
        "artifact_source", "runner_provenance", "policy", "energy_scope", "units",
        "summary", "energy_breakdown_j", "events", "warnings", "claim_boundary",
    }
    _require(set(result) == required, f"result fields differ: {sorted(set(result) ^ required)}")
    _require(result["schema_version"] == RESULT_VERSION, "result schema version")
    _require(result["scenario_id"] == SCENARIO_ID, "result scenario ID")
    _hash(result["scenario_sha256"], "scenario_sha256")
    _hash(result["scenario_anchor_sha256"], "scenario_anchor_sha256")
    _hash(result["run_id"], "run_id")
    _require(result["lab_id"] in ("A", "B", "C"), "result lab")
    _require(result["run_role"] in ("baseline", "candidate", "revision", "withheld"), "result role")
    _require(result["artifact_source"] in ("student-run", "same-scenario-fallback"), "artifact source")
    _require(isinstance(result["seed"], int) and result["seed"] >= 0, "result seed")
    provenance = result["runner_provenance"]
    provenance_required = {"upstream_repository", "upstream_commit", "wrapper_version", "python_version", "lock_sha256", "engine_mode", "upstream_execution"}
    _require(set(provenance) == provenance_required, "provenance fields")
    _require(provenance["upstream_repository"] == UPSTREAM_REPOSITORY and provenance["upstream_commit"] == UPSTREAM_COMMIT, "upstream provenance")
    _require(provenance["wrapper_version"] == WRAPPER_VERSION and provenance["engine_mode"] == "coherent-course-simulated-adapter" and provenance["upstream_execution"] is False, "runner mode is not honest simulated mode")
    _hash(provenance["lock_sha256"], "lock_sha256")
    _require(isinstance(provenance["python_version"], str) and provenance["python_version"].startswith("3."), "python version")

    policy = result["policy"]
    policy_required = {"policy_sha256", "predecessor_policy_sha256", "freeze_receipt_sha256", "active_block_id", "policy_api_version"}
    _require(set(policy) == policy_required, "policy fields")
    _hash(policy["policy_sha256"], "policy hash")
    _require(policy["predecessor_policy_sha256"] is None or HASH_RE.match(policy["predecessor_policy_sha256"] or ""), "predecessor hash")
    _require(policy["freeze_receipt_sha256"] is None or HASH_RE.match(policy["freeze_receipt_sha256"] or ""), "freeze hash")
    _require(policy["active_block_id"] in BLOCK_IDS.values() and policy["policy_api_version"] == POLICY_API_VERSION, "policy API")

    _require(result["energy_scope"] == ENERGY_SCOPE, "energy scope")
    _require(result["units"] == {"time": "s", "power": "W", "energy": "J", "data": "bit", "rate": "bit/s", "endpoint_energy_efficiency": "bit/J"}, "result units")
    summary = result["summary"]
    summary_required = {"generated_packets", "attempted_packets", "unique_delivered_packets", "delivered_bits", "collisions", "retransmissions", "expired_packets", "deadline_pass", "freshness_status", "rate_bits_per_s", "active_time_s", "wake_count", "endpoint_energy_j", "endpoint_energy_efficiency_bits_per_j", "service_pass"}
    _require(set(summary) == summary_required, "summary fields")
    for name, value in summary.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            _number(value, f"summary.{name}")
    _require(summary["freshness_status"] in ("fresh", "stale", "expired", "not-applicable"), "freshness status")
    breakdown = result["energy_breakdown_j"]
    breakdown_required = {"sleep", "awake_idle", "wake", "process", "tx", "rx"}
    _require(set(breakdown) == breakdown_required, "energy breakdown fields")
    for name, value in breakdown.items():
        _number(value, f"energy_breakdown_j.{name}")
    total = sum(float(value) for value in breakdown.values())
    _require(abs(total - float(summary["endpoint_energy_j"])) <= 1e-6, "energy breakdown does not reconcile")

    previous_time = -1.0
    previous_energy = 0.0
    for index, event in enumerate(result["events"]):
        _require(isinstance(event, dict), f"event {index} object")
        _event_base(event, index, policy["policy_sha256"], result["case_id"])
        _require(event["start_s"] >= previous_time, f"event {index} out of order")
        _require(event["cumulative_endpoint_energy_j"] + 1e-9 >= previous_energy, f"event {index} cumulative energy decreases")
        previous_time = float(event["start_s"])
        previous_energy = float(event["cumulative_endpoint_energy_j"])
    _require(result["events"], "result has no events")
    expected_run_id = hash_value({key: value for key, value in result.items() if key != "run_id"})
    _require(result["run_id"] == expected_run_id, "run_id preimage mismatch")
    _require(result["claim_boundary"] == CLAIM_BOUNDARY, "claim boundary")
    return result


def validate_freeze_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "scenario_id", "scenario_sha256", "scenario_anchor_sha256", "lab_id",
        "frozen_case_id", "active_block_id", "policy_api_version", "policy_sha256",
        "predecessor_policy_sha256", "upstream_commit", "wrapper_version", "lock_sha256",
        "seed_role", "seed", "canonicalization", "receipt_sha256",
    }
    _require(set(receipt) == required, "freeze receipt fields")
    _require(receipt["schema_version"] == FREEZE_VERSION and receipt["scenario_id"] == SCENARIO_ID, "freeze receipt identity")
    _hash(receipt["scenario_sha256"], "receipt scenario hash")
    _hash(receipt["scenario_anchor_sha256"], "receipt anchor hash")
    _hash(receipt["policy_sha256"], "receipt policy hash")
    _hash(receipt["predecessor_policy_sha256"], "receipt predecessor hash")
    _hash(receipt["lock_sha256"], "receipt lock hash")
    _hash(receipt["receipt_sha256"], "receipt hash")
    _require(receipt["lab_id"] in ("A", "B", "C"), "receipt lab")
    _require(receipt["frozen_case_id"] in ("candidate", "trace-a-candidate", "revision"), "receipt case")
    _require(receipt["active_block_id"] in BLOCK_IDS.values(), "receipt block")
    _require(receipt["policy_api_version"] == POLICY_API_VERSION, "receipt policy API")
    _require(receipt["upstream_commit"] == UPSTREAM_COMMIT and receipt["wrapper_version"] == WRAPPER_VERSION, "receipt runner identity")
    _require(receipt["canonicalization"] == "RFC8785", "receipt canonicalization")
    expected = hash_value({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    _require(receipt["receipt_sha256"] == expected, "receipt hash preimage mismatch")
    return receipt
