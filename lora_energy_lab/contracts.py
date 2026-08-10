"""Validation and identity helpers for the frozen LoRa energy scenario contract."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .canonical_json import CanonicalJSONError, hash_value, load_file

SCENARIO_VERSION = "lora-energy-scenario-v1"
RESULT_VERSION = "lora-energy-run-result-v1"
FREEZE_VERSION = "lora-energy-freeze-receipt-v1"
REPLAY_VERSION = "lora-energy-endpoint-replay-v1"
SCENARIO_ID = "ntpu-energy-decision-01"
COURSE_ID = "LORA-ENERGY-DECISION-1R"
CONTRACT_VERSION = "lora-energy-leo-v1"
WRAPPER_VERSION = "lora-energy-runner-v1"
POLICY_API_VERSION = "lora-energy-policy-v1"
UPSTREAM_REPOSITORY = "https://github.com/GillesC/LoRaEnergySim"
UPSTREAM_COMMIT = "f854462cda0cd30cb56e3f0c576cb004711842f6"
ENGINE_MODE = "coherent-course-simulated-adapter"
CLAIM_BOUNDARY = (
    "SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / "
    "NOT CANONICAL-PARITY-VERIFIED"
)
ENERGY_SCOPE = "endpoint-radio-and-processing-course-assumptions"
LEGAL_ACTIONS = ("SLEEP", "WAIT", "SEND_ONE", "SEND_URGENT", "FLUSH_BATCH")
BLOCK_IDS = {
    "A": "lab-a-pace-rest",
    "B": "lab-b-enter-exit-hold",
    "C": "lab-c-batch-urgent",
}
CASE_KEYS = (
    ("A", "baseline"),
    ("A", "candidate"),
    ("A", "hidden"),
    ("B", "trace-a-baseline"),
    ("B", "trace-a-candidate"),
    ("B", "trace-b"),
    ("C", "baseline"),
    ("C", "candidate"),
    ("C", "revision"),
    ("C", "surprise"),
)


class ContractError(ValueError):
    """A fail-closed contract or identity error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _finite_nonnegative(value: Any, field: str) -> None:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field} must be numeric")
    _require(math.isfinite(float(value)), f"{field} must be finite")
    _require(float(value) >= 0, f"{field} must be non-negative")


def _hash(value: Any, expected: Any, field: str) -> None:
    _require(isinstance(expected, str) and expected.startswith("sha256:"), f"{field} has invalid hash")
    _require(hash_value(value) == expected, f"{field} does not match canonical preimage")


def _keys(value: dict[str, Any], required: set[str], allowed: set[str], field: str) -> None:
    _require(isinstance(value, dict), f"{field} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - allowed
    _require(not missing, f"{field} missing: {sorted(missing)}")
    _require(not unknown, f"{field} has unknown fields: {sorted(unknown)}")


def _validate_anchor(anchor: dict[str, Any]) -> None:
    required = {
        "course_id", "contract_version", "provider_kind", "provider_id",
        "fixture_id", "fixture_version", "scenario_id", "source_mode",
        "tle_source_id", "target_utc", "claim_boundary", "claim_levels", "units",
    }
    _keys(anchor, required, required, "scenario_anchor")
    _require(anchor["course_id"] == COURSE_ID, "anchor course_id mismatch")
    _require(anchor["contract_version"] == "lora-fixture-first-v2", "anchor contract mismatch")
    _require(anchor["provider_kind"] in ("fixture", "canonical-adapter"), "anchor provider kind")
    _require(anchor["scenario_id"] == SCENARIO_ID, "anchor scenario mismatch")
    _require(anchor["source_mode"] in ("bundled", "fallback"), "anchor source mode")
    _require(anchor["tle_source_id"] == "oneweb-0314-archive-2026-08-08", "anchor TLE source mismatch")
    _require(anchor["target_utc"] == "2026-08-09T04:00:00Z", "anchor target mismatch")
    _require(anchor["claim_boundary"] == CLAIM_BOUNDARY, "anchor claim boundary mismatch")
    _require(anchor["claim_levels"] == ["SIMULATED_TEACHING_DATA", "NOT_LIVE", "NOT_MEASURED", "NOT_CANONICAL_PARITY_VERIFIED"], "anchor claim levels mismatch")
    expected_units = {
        "elapsedTime": "s", "activeTime": "s", "deadline": "s", "freshness": "s",
        "power": "W", "consumedEnergy": "J", "energyBudget": "J", "rate": "bit/s",
        "deliveredData": "bit", "energyEfficiency": "bit/J", "angle": "deg",
        "distance": "km", "quality": "teaching-band",
    }
    _require(anchor["units"] == expected_units, "anchor units mismatch")


def _validate_case(case: dict[str, Any], contacts: set[str], cards: set[str], lab: str, case_id: str) -> None:
    required = {
        "case_id", "lab_id", "run_role", "seed_role", "seed", "contact_window_ids",
        "quality_trace_id", "traffic_card_ids", "expected_predecessor_role",
        "expected_freeze_role", "withheld",
    }
    _keys(case, required, required, f"case {lab}/{case_id}")
    _require(case["lab_id"] == lab and case["case_id"] == case_id, "case identity mismatch")
    _require(case["seed"] >= 0 and case["seed"] <= 2147483647, "case seed out of range")
    _require(isinstance(case["seed_role"], str) and case["seed_role"].startswith(f"lab-{lab.lower()}-"), "case seed role mismatch")
    _require(case["quality_trace_id"] == "ntpu-quality-course-v1", "case quality trace mismatch")
    _require(case["contact_window_ids"] and set(case["contact_window_ids"]) <= contacts, "case contact IDs mismatch")
    _require(case["traffic_card_ids"] and set(case["traffic_card_ids"]) <= cards, "case traffic IDs mismatch")
    _require(isinstance(case["withheld"], bool), "case withheld must be boolean")


def validate_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Validate the frozen scenario and all semantic invariants not in JSON Schema."""
    required = {
        "schema_version", "course_id", "runner_contract_version", "scenario_id",
        "scenario_sha256", "scenario_anchor_sha256", "source_mode", "target_utc",
        "tle_source_id", "scenario_anchor", "runner", "units", "clock",
        "contact_windows", "quality_band_trace", "traffic_cards",
        "endpoint_energy_profile", "mission_contract", "cases", "claim_boundary",
    }
    _keys(scenario, required, required, "scenario")
    _require(scenario["schema_version"] == SCENARIO_VERSION, "scenario schema mismatch")
    _require(scenario["course_id"] == COURSE_ID, "scenario course mismatch")
    _require(scenario["runner_contract_version"] == CONTRACT_VERSION, "runner contract mismatch")
    _require(scenario["scenario_id"] == SCENARIO_ID, "scenario ID mismatch")
    _require(scenario["source_mode"] in ("bundled", "fallback"), "scenario source mode")
    _require(scenario["target_utc"] == "2026-08-09T04:00:00Z", "scenario target mismatch")
    _require(scenario["tle_source_id"] == "oneweb-0314-archive-2026-08-08", "scenario TLE source mismatch")
    _require(scenario["claim_boundary"] == CLAIM_BOUNDARY, "scenario claim boundary mismatch")

    _validate_anchor(scenario["scenario_anchor"])
    _hash(scenario["scenario_anchor"], scenario["scenario_anchor_sha256"], "scenario_anchor_sha256")
    scenario_without_hash = dict(scenario)
    scenario_without_hash.pop("scenario_sha256", None)
    _hash(scenario_without_hash, scenario["scenario_sha256"], "scenario_sha256")

    runner = scenario["runner"]
    runner_required = {"upstream_repository", "upstream_commit", "wrapper_version", "policy_api_version", "seed", "engine_mode", "upstream_execution"}
    _keys(runner, runner_required, runner_required, "runner")
    _require(runner["upstream_repository"] == UPSTREAM_REPOSITORY, "upstream repository mismatch")
    _require(runner["upstream_commit"] == UPSTREAM_COMMIT, "upstream commit mismatch")
    _require(runner["wrapper_version"] == WRAPPER_VERSION, "wrapper version mismatch")
    _require(runner["policy_api_version"] == POLICY_API_VERSION, "policy API mismatch")
    _require(runner["engine_mode"] == ENGINE_MODE and runner["upstream_execution"] is False, "runner must be simulated")
    _require(runner["seed"] == 12001, "scenario seed mismatch")

    _require(scenario["units"] == {"time": "s", "power": "W", "energy": "J", "data": "bit", "rate": "bit/s"}, "runner units mismatch")
    clock = scenario["clock"]
    _keys(clock, {"step_s", "duration_s"}, {"step_s", "duration_s"}, "clock")
    _require(1 <= clock["step_s"] <= 60 and 60 <= clock["duration_s"] <= 3600, "clock bounds")

    contacts = scenario["contact_windows"]
    _require(1 <= len(contacts) <= 16, "contact window count")
    contact_ids: set[str] = set()
    previous_end = -1
    for contact in contacts:
        _keys(contact, {"contact_id", "satellite_id", "source_id", "start_s", "end_s", "quality_trace_id", "handover_target_id"}, {"contact_id", "satellite_id", "source_id", "start_s", "end_s", "quality_trace_id", "handover_target_id"}, "contact window")
        cid = contact["contact_id"]
        _require(cid not in contact_ids, "duplicate contact ID")
        contact_ids.add(cid)
        _require(contact["source_id"] == scenario["tle_source_id"], "contact source mismatch")
        _require(contact["quality_trace_id"] == "ntpu-quality-course-v1", "contact trace mismatch")
        _require(0 <= contact["start_s"] < contact["end_s"] <= clock["duration_s"], "contact bounds")
        _require(contact["start_s"] >= previous_end, "contact windows out of order/overlap")
        previous_end = contact["end_s"]

    trace = scenario["quality_band_trace"]
    _keys(trace, {"trace_id", "ordinal_labels", "points"}, {"trace_id", "ordinal_labels", "points"}, "quality trace")
    _require(trace["trace_id"] == "ntpu-quality-course-v1", "quality trace ID")
    _require(trace["ordinal_labels"] == ["closed", "weak", "usable", "strong"], "quality labels")
    previous_time = -1
    trace_times: set[int] = set()
    for point in trace["points"]:
        _keys(point, {"elapsed_s", "contact_id", "quality_band"}, {"elapsed_s", "contact_id", "quality_band"}, "quality point")
        _require(point["elapsed_s"] > previous_time and point["elapsed_s"] <= clock["duration_s"], "quality points out of order")
        _require(point["elapsed_s"] not in trace_times, "duplicate quality point")
        trace_times.add(point["elapsed_s"])
        previous_time = point["elapsed_s"]
        _require(point["contact_id"] is None or point["contact_id"] in contact_ids, "quality contact mismatch")
        _require(0 <= point["quality_band"] <= 3, "quality band out of range")
        if point["quality_band"] == 0:
            _require(point["contact_id"] is None, "closed quality must have no contact")
        else:
            _require(point["contact_id"] is not None, "open quality needs contact")

    cards = scenario["traffic_cards"]
    _require(1 <= len(cards) <= 64, "traffic card count")
    card_ids: set[str] = set()
    for card in cards:
        _keys(card, {"packet_id", "class", "generated_s", "deadline_s", "freshness_limit_s", "payload_bits", "destination_id"}, {"packet_id", "class", "generated_s", "deadline_s", "freshness_limit_s", "payload_bits", "destination_id"}, "traffic card")
        _require(card["packet_id"] not in card_ids, "duplicate packet ID")
        card_ids.add(card["packet_id"])
        _require(card["class"] in ("normal", "urgent"), "packet class")
        _require(0 <= card["generated_s"] < clock["duration_s"], "packet generation time")
        _require(card["deadline_s"] > card["generated_s"], "packet deadline")
        _require(card["freshness_limit_s"] > 0 and card["payload_bits"] > 0, "packet bounds")

    profile = scenario["endpoint_energy_profile"]
    profile_fields = {"scope", "sleep_power_w", "awake_idle_power_w", "process_power_w", "tx_power_w", "rx_power_w", "wake_energy_j", "wake_latency_s"}
    _keys(profile, profile_fields, profile_fields, "endpoint energy profile")
    _require(profile["scope"] == ENERGY_SCOPE, "energy scope mismatch")
    for name in profile_fields - {"scope"}:
        _finite_nonnegative(profile[name], f"energy profile {name}")
    _require(profile["sleep_power_w"] > 0 and profile["awake_idle_power_w"] > 0 and profile["process_power_w"] > 0 and profile["tx_power_w"] > 0 and profile["rx_power_w"] > 0, "energy powers must be positive")

    mission = scenario["mission_contract"]
    mission_fields = {"contract_id", "evaluation_end_s", "required_packet_ids", "minimum_unique_delivered_bits", "deadline_rule", "freshness_rule", "maximum_expired_packets", "system_boundary_id", "power_model_id"}
    _keys(mission, mission_fields, mission_fields, "mission contract")
    _require(mission["evaluation_end_s"] == clock["duration_s"], "mission evaluation end mismatch")
    _require(set(mission["required_packet_ids"]) <= card_ids, "mission packet mismatch")
    _require(mission["minimum_unique_delivered_bits"] > 0, "mission bit minimum")
    _require(mission["system_boundary_id"] == "endpoint-radio-and-processing-only", "mission system boundary")
    _require(mission["power_model_id"] == "course-endpoint-energy-v1", "mission power model")

    _require(isinstance(scenario["cases"], list) and 10 <= len(scenario["cases"]), "case table too small")
    seen: set[tuple[str, str]] = set()
    for case in scenario["cases"]:
        key = (case.get("lab_id"), case.get("case_id"))
        _require(key in CASE_KEYS, f"unexpected case: {key}")
        _require(key not in seen, f"duplicate case: {key}")
        seen.add(key)
        _validate_case(case, contact_ids, card_ids, key[0], key[1])
    _require(seen == set(CASE_KEYS), "scenario case table does not contain all required cases")
    return scenario


def load_scenario(path: str | Path) -> dict[str, Any]:
    try:
        scenario = load_file(path)
    except (OSError, CanonicalJSONError) as exc:
        raise ContractError(f"scenario cannot be read: {exc}") from exc
    return validate_scenario(scenario)


def case_for(scenario: dict[str, Any], lab_id: str, case_id: str) -> dict[str, Any]:
    for case in scenario["cases"]:
        if case["lab_id"] == lab_id and case["case_id"] == case_id:
            return case
    raise ContractError(f"unknown lab/case: {lab_id}/{case_id}")
