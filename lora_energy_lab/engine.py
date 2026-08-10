"""Deterministic LoRa energy coherent simulated adapter.

This is intentionally a small course model.  It reuses the concepts named in
the LoRaEnergySim provenance (sleep/process/TX/RX, packets and collisions),
but it does not import or execute the upstream research repository.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from typing import Any, Callable

from .canonical_json import hash_bytes, hash_value
from .contracts import (
    CLAIM_BOUNDARY,
    ENERGY_SCOPE,
    ENGINE_MODE,
    LEGAL_ACTIONS,
    POLICY_API_VERSION,
    RESULT_VERSION,
    SCENARIO_ID,
    UPSTREAM_COMMIT,
    UPSTREAM_REPOSITORY,
    WRAPPER_VERSION,
)
from .policy_api import PolicyError, PolicyObservation, call_policy


@dataclass
class Packet:
    packet_id: str
    packet_class: str
    generated_s: int
    deadline_s: int
    freshness_limit_s: int
    payload_bits: int
    attempts: int = 0
    delivered_s: int | None = None
    expired: bool = False


def _round(value: float) -> float:
    return round(float(value), 6)


class SimulationError(RuntimeError):
    """A policy or deterministic engine execution error."""


def _outcome_roll(seed: int, packet_id: str, attempt: int, elapsed_s: int) -> int:
    preimage = f"{seed}|{packet_id}|{attempt}|{elapsed_s}".encode("ascii")
    return int(hashlib.sha256(preimage).hexdigest()[:8], 16) % 100


def _quality_at(scenario: dict[str, Any], elapsed_s: int, allowed_contacts: set[str]) -> tuple[int, str | None]:
    point = scenario["quality_band_trace"]["points"][0]
    for candidate in scenario["quality_band_trace"]["points"]:
        if candidate["elapsed_s"] <= elapsed_s:
            point = candidate
        else:
            break
    contact = point["contact_id"] if point["contact_id"] in allowed_contacts else None
    quality = point["quality_band"] if contact else 0
    return quality, contact


def _contact_remaining(scenario: dict[str, Any], elapsed_s: int, contact_id: str | None) -> int:
    if not contact_id:
        return 0
    for contact in scenario["contact_windows"]:
        if contact["contact_id"] == contact_id:
            return max(0, contact["end_s"] - elapsed_s)
    return 0


def _event_base(
    events: list[dict[str, Any]],
    event_type: str,
    start_s: float,
    end_s: float,
    case_id: str,
    policy_sha: str,
    contact_id: str | None,
    quality_band: int,
    event_energy: float,
    cumulative_energy: float,
    **extra: Any,
) -> None:
    event = {
        "event_id": f"evt-{len(events):04d}",
        "index": len(events),
        "type": event_type,
        "start_s": _round(start_s),
        "end_s": _round(end_s),
        "case_id": case_id,
        "policy_sha256": policy_sha,
        "contact_id": contact_id,
        "quality_band": quality_band,
        "event_endpoint_energy_j": _round(event_energy),
        "cumulative_endpoint_energy_j": _round(cumulative_energy),
    }
    event.update(extra)
    events.append(event)


def _state_event(
    events: list[dict[str, Any]],
    state: str,
    start_s: float,
    end_s: float,
    case_id: str,
    policy_sha: str,
    contact_id: str | None,
    quality_band: int,
    energy: float,
    cumulative: float,
) -> None:
    _event_base(
        events, "STATE_INTERVAL", start_s, end_s, case_id, policy_sha,
        contact_id, quality_band, energy, cumulative, state=state,
    )


def _observation(
    elapsed_s: int,
    quality_band: int,
    contact_id: str | None,
    stable_steps: int,
    send_mode_active: bool,
    steps_since_send: int,
    queue: list[Packet],
    previous_action: str | None,
    scenario: dict[str, Any],
) -> PolicyObservation:
    pending_urgent = [
        packet for packet in queue
        if packet.packet_class == "urgent"
        and not packet.expired
        and packet.delivered_s is None
    ]
    due = min((packet.deadline_s - elapsed_s for packet in pending_urgent), default=None)
    return PolicyObservation(
        elapsed_s=elapsed_s,
        contact_open=contact_id is not None and quality_band > 0,
        quality_band=quality_band,
        stable_steps=stable_steps,
        send_mode_active=send_mode_active,
        steps_since_send=steps_since_send,
        contact_remaining_s=_contact_remaining(scenario, elapsed_s, contact_id),
        queue_size=len([packet for packet in queue if not packet.expired and packet.delivered_s is None]),
        urgent_pending=bool(pending_urgent),
        urgent_due_in_s=due,
        previous_action=previous_action,
    )


def run_simulation(
    scenario: dict[str, Any],
    case: dict[str, Any],
    policy_sha: str,
    policy_function: Callable[[PolicyObservation], str],
    *,
    artifact_source: str = "student-run",
    freeze_receipt_sha256: str | None = None,
    predecessor_policy_sha256: str | None = None,
    lock_sha256: str,
    python_version: str | None = None,
) -> dict[str, Any]:
    """Run one fixed case and return a schema-shaped result object."""
    duration = int(scenario["clock"]["duration_s"])
    step = int(scenario["clock"]["step_s"])
    profile = scenario["endpoint_energy_profile"]
    allowed_contacts = set(case["contact_window_ids"])
    allowed_cards = set(case["traffic_card_ids"])
    cards_by_id = {card["packet_id"]: card for card in scenario["traffic_cards"] if card["packet_id"] in allowed_cards}
    events: list[dict[str, Any]] = []
    queue: list[Packet] = []
    packets: dict[str, Packet] = {}
    breakdown = {"sleep": 0.0, "awake_idle": 0.0, "wake": 0.0, "process": 0.0, "tx": 0.0, "rx": 0.0}
    total_energy = 0.0
    active_time = 0.0
    wake_count = 0
    attempted = 0
    collisions = 0
    retransmissions = 0
    delivered_ids: set[str] = set()
    expired_ids: set[str] = set()
    asleep = False
    previous_action: str | None = None
    steps_since_send = 2
    stable_steps = 0
    last_quality = 0
    send_mode_active = False
    globals_ns = getattr(policy_function, "__globals__", {})
    enter_quality = int(globals_ns.get("ENTER_QUALITY", 2))
    exit_quality = int(globals_ns.get("EXIT_QUALITY", 1))
    required_batch_size = int(globals_ns.get("BATCH_SIZE", 3))
    del required_batch_size  # The student policy itself decides the action.

    def add_energy(amount: float, bucket: str) -> None:
        nonlocal total_energy
        breakdown[bucket] += amount
        total_energy += amount

    def generate_at(elapsed_s: int, quality: int, contact: str | None) -> None:
        for card in sorted(cards_by_id.values(), key=lambda item: (item["generated_s"], item["packet_id"])):
            if card["generated_s"] == elapsed_s:
                packet = Packet(
                    packet_id=card["packet_id"], packet_class=card["class"],
                    generated_s=card["generated_s"], deadline_s=card["deadline_s"],
                    freshness_limit_s=card["freshness_limit_s"], payload_bits=card["payload_bits"],
                )
                packets[packet.packet_id] = packet
                queue.append(packet)
                _event_base(events, "PACKET_GENERATED", elapsed_s, elapsed_s, case["case_id"], policy_sha, contact, quality, 0.0, total_energy, packet_ids=[packet.packet_id])

    def expire_at(elapsed_s: int, quality: int, contact: str | None) -> None:
        for packet in queue:
            if packet.delivered_s is None and not packet.expired and elapsed_s >= packet.deadline_s:
                packet.expired = True
                expired_ids.add(packet.packet_id)
                _event_base(events, "PACKET_EXPIRED", elapsed_s, elapsed_s, case["case_id"], policy_sha, contact, quality, 0.0, total_energy, packet_ids=[packet.packet_id])

    for elapsed_s in range(0, duration, step):
        quality, contact = _quality_at(scenario, elapsed_s, allowed_contacts)
        generate_at(elapsed_s, quality, contact)
        expire_at(elapsed_s, quality, contact)
        if quality == last_quality and quality > 0:
            stable_steps += 1
        elif quality > 0:
            stable_steps = 1
        else:
            stable_steps = 0
        last_quality = quality

        if send_mode_active:
            next_mode = quality >= exit_quality
        else:
            next_mode = quality >= enter_quality and stable_steps >= int(globals_ns.get("STABLE_STEPS", 2))
        if next_mode != send_mode_active:
            _event_base(
                events, "MODE_CHANGE", elapsed_s, elapsed_s, case["case_id"], policy_sha,
                contact, quality, 0.0, total_energy,
                from_mode="SEND_READY" if send_mode_active else "REST",
                to_mode="SEND_READY" if next_mode else "REST",
            )
            send_mode_active = next_mode

        obs = _observation(
            elapsed_s, quality, contact, stable_steps, send_mode_active,
            steps_since_send, queue, previous_action, scenario,
        )
        try:
            action = call_policy(policy_function, obs)
        except PolicyError as exc:
            raise SimulationError(str(exc)) from exc

        # A policy may request a send after its queue was emptied by an
        # earlier decision in the same fixed step, or while a sleeping radio
        # cannot finish its declared wake before contact closes.  The strict
        # importer treats every SEND_* decision as an attempted action, so
        # record the safe WAIT/SLEEP decision that the adapter actually can
        # execute rather than leaving a phantom SEND_* event in the ledger.
        selected_for_action: list[Packet] = []
        if action in ("SEND_ONE", "SEND_URGENT", "FLUSH_BATCH"):
            pending_for_action = [
                packet for packet in queue
                if packet.delivered_s is None and not packet.expired
            ]
            if action == "SEND_URGENT":
                selected_for_action = [
                    packet for packet in pending_for_action
                    if packet.packet_class == "urgent"
                ][:1]
            elif action == "FLUSH_BATCH":
                selected_for_action = pending_for_action[: max(1, int(globals_ns.get("BATCH_SIZE", 3)))]
            else:
                selected_for_action = pending_for_action[:1]
            if not selected_for_action:
                action = "WAIT"
            elif asleep and _contact_remaining(scenario, elapsed_s, contact) <= float(profile["wake_latency_s"]):
                action = "SLEEP"
                selected_for_action = []
        _event_base(
            events, "POLICY_DECISION", elapsed_s, elapsed_s, case["case_id"], policy_sha,
            contact, quality, 0.0, total_energy, action=action,
            observation={
                "elapsed_s": obs.elapsed_s, "contact_open": obs.contact_open,
                "quality_band": obs.quality_band, "stable_steps": obs.stable_steps,
                "send_mode_active": obs.send_mode_active, "steps_since_send": obs.steps_since_send,
                "contact_remaining_s": obs.contact_remaining_s, "queue_size": obs.queue_size,
                "urgent_pending": obs.urgent_pending, "urgent_due_in_s": obs.urgent_due_in_s,
                "previous_action": obs.previous_action,
            },
        )

        if contact is None and action != "SLEEP":
            raise SimulationError(f"contact closed at line decision {elapsed_s}: only SLEEP is legal")

        if action in ("SEND_ONE", "SEND_URGENT", "FLUSH_BATCH"):
            pending = [packet for packet in queue if packet.delivered_s is None and not packet.expired]
            if action == "SEND_URGENT":
                selected = [packet for packet in pending if packet.packet_class == "urgent"][:1]
            elif action == "FLUSH_BATCH":
                selected = pending[: max(1, int(globals_ns.get("BATCH_SIZE", 3)))]
            else:
                selected = pending[:1]
            if selected:
                cursor = float(elapsed_s)
                if asleep:
                    wake_latency = float(profile["wake_latency_s"])
                    wake_energy = float(profile["wake_energy_j"])
                    wake_end = cursor + wake_latency
                    wake_success = _contact_remaining(scenario, elapsed_s, contact) > wake_latency
                    add_energy(wake_energy, "wake")
                    wake_count += 1
                    _event_base(
                        events, "WAKE", cursor, wake_end, case["case_id"], policy_sha,
                        contact, quality, wake_energy, total_energy,
                        outcome_code="wake-complete" if wake_success else "wake-missed-contact",
                    )
                    cursor = wake_end
                    asleep = False
                    if not wake_success:
                        previous_action = action
                        steps_since_send += 1
                        continue
                process_end = cursor + 1.0
                process_energy = float(profile["process_power_w"])
                add_energy(process_energy, "process")
                active_time += 1.0
                _state_event(events, "PROCESS", cursor, process_end, case["case_id"], policy_sha, contact, quality, process_energy, total_energy)
                tx_end = process_end + 2.0
                tx_energy = float(profile["tx_power_w"]) * 2.0
                add_energy(tx_energy, "tx")
                active_time += 2.0
                _state_event(events, "TX", process_end, tx_end, case["case_id"], policy_sha, contact, quality, tx_energy, total_energy)
                rx_end = tx_end + 1.0
                rx_energy = float(profile["rx_power_w"])
                add_energy(rx_energy, "rx")
                active_time += 1.0
                _state_event(events, "RX", tx_end, rx_end, case["case_id"], policy_sha, contact, quality, rx_energy, total_energy)
                attempted += len(selected)
                for packet in selected:
                    packet.attempts += 1
                _event_base(
                    events, "PACKET_ATTEMPT", rx_end, rx_end, case["case_id"], policy_sha,
                    contact, quality, 0.0, total_energy,
                    packet_ids=[packet.packet_id for packet in selected], action=action,
                )
                threshold = {1: 45, 2: 75, 3: 92}.get(quality, 0)
                failed = [
                    packet for packet in selected
                    if _outcome_roll(int(case["seed"]), packet.packet_id, packet.attempts, elapsed_s) >= threshold
                ]
                succeeded = [packet for packet in selected if packet not in failed]
                if failed:
                    collisions += 1
                    _event_base(
                        events, "PACKET_COLLISION", rx_end, rx_end, case["case_id"], policy_sha,
                        contact, quality, 0.0, total_energy,
                        packet_ids=[packet.packet_id for packet in failed],
                    )
                    retryable = [packet for packet in failed if packet.attempts < 3]
                    retransmissions += len(retryable)
                    if retryable:
                        _event_base(
                            events, "PACKET_RETRY", rx_end, rx_end, case["case_id"], policy_sha,
                            contact, quality, 0.0, total_energy,
                            packet_ids=[packet.packet_id for packet in retryable],
                            attempt_number=max(packet.attempts + 1 for packet in retryable),
                        )
                for packet in succeeded:
                    packet.delivered_s = int(rx_end)
                    delivered_ids.add(packet.packet_id)
                    _event_base(
                        events, "PACKET_DELIVERED", rx_end, rx_end, case["case_id"], policy_sha,
                        contact, quality, 0.0, total_energy, packet_ids=[packet.packet_id],
                    )
                steps_since_send = 0
                previous_action = action
                continue

        # WAIT and SLEEP each own exactly one scenario clock step.
        state = "SLEEP" if action == "SLEEP" else "AWAKE_IDLE"
        power_key = "sleep_power_w" if state == "SLEEP" else "awake_idle_power_w"
        energy = float(profile[power_key]) * step
        bucket = "sleep" if state == "SLEEP" else "awake_idle"
        add_energy(energy, bucket)
        _state_event(events, state, elapsed_s, elapsed_s + step, case["case_id"], policy_sha, contact, quality, energy, total_energy)
        asleep = state == "SLEEP"
        steps_since_send += 1
        previous_action = action

    # A final deadline check is an event at the fixed evaluation boundary.
    quality, contact = _quality_at(scenario, duration, allowed_contacts)
    expire_at(duration, quality, contact)
    delivered_bits = sum(packets[packet_id].payload_bits for packet_id in delivered_ids)
    required_ids = set(scenario["mission_contract"]["required_packet_ids"])
    required_delivered = required_ids <= delivered_ids
    deadline_pass = all(
        packet_id in delivered_ids and packets[packet_id].delivered_s is not None and packets[packet_id].delivered_s <= packets[packet_id].deadline_s
        for packet_id in required_ids
    )
    # Freshness is a mission-contract property, not a property of whichever
    # packets happened to arrive.  A required packet that expired must make
    # the verdict expired even when no required packet was delivered; an empty
    # required set is the only not-applicable case.
    if not required_ids:
        freshness_status = "not-applicable"
    elif any(packets[packet_id].expired for packet_id in required_ids):
        freshness_status = "expired"
    elif all(
        packets[packet_id].delivered_s is not None
        and packets[packet_id].delivered_s - packets[packet_id].generated_s
        <= packets[packet_id].freshness_limit_s
        for packet_id in required_ids
    ):
        freshness_status = "fresh"
    else:
        freshness_status = "stale"
    service_pass = (
        required_delivered
        and deadline_pass
        and delivered_bits >= int(scenario["mission_contract"]["minimum_unique_delivered_bits"])
        and len(expired_ids) <= int(scenario["mission_contract"]["maximum_expired_packets"])
        and freshness_status in ("fresh", "not-applicable")
    )
    endpoint_energy = _round(total_energy)
    efficiency = _round(delivered_bits / endpoint_energy) if endpoint_energy > 0 else 0.0
    warnings = ["SIMULATED_ADAPTER", "UPSTREAM_EXECUTION_FALSE", "SERVICE_BOUNDARY_ENDPOINT_ONLY"]
    if artifact_source == "same-scenario-fallback":
        warnings.insert(0, "FALLBACK_ARTIFACT")
    if required_ids - delivered_ids:
        warnings.append("REQUIRED_PACKET_NOT_DELIVERED")
    if expired_ids:
        warnings.append("PACKET_EXPIRY_PRESENT")
    role = case["run_role"]
    result = {
        "schema_version": RESULT_VERSION,
        "scenario_id": SCENARIO_ID,
        "scenario_sha256": scenario["scenario_sha256"],
        "scenario_anchor_sha256": scenario["scenario_anchor_sha256"],
        "run_id": "sha256:" + "0" * 64,
        "lab_id": case["lab_id"],
        "case_id": case["case_id"],
        "run_role": role,
        "seed": case["seed"],
        "seed_role": case["seed_role"],
        "artifact_source": artifact_source,
        "runner_provenance": {
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_commit": UPSTREAM_COMMIT,
            "wrapper_version": WRAPPER_VERSION,
            "python_version": python_version or f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "lock_sha256": lock_sha256,
            "engine_mode": ENGINE_MODE,
            "upstream_execution": False,
        },
        "policy": {
            "policy_sha256": policy_sha,
            "predecessor_policy_sha256": predecessor_policy_sha256,
            "freeze_receipt_sha256": freeze_receipt_sha256,
            "active_block_id": f"lab-{case['lab_id'].lower()}-" + {"A": "pace-rest", "B": "enter-exit-hold", "C": "batch-urgent"}[case["lab_id"]],
            "policy_api_version": POLICY_API_VERSION,
        },
        "energy_scope": ENERGY_SCOPE,
        "units": {"time": "s", "power": "W", "energy": "J", "data": "bit", "rate": "bit/s", "endpoint_energy_efficiency": "bit/J"},
        "summary": {
            "generated_packets": len(packets),
            "attempted_packets": attempted,
            "unique_delivered_packets": len(delivered_ids),
            "delivered_bits": delivered_bits,
            "collisions": collisions,
            "retransmissions": retransmissions,
            "expired_packets": len(expired_ids),
            "deadline_pass": deadline_pass,
            "freshness_status": freshness_status,
            "rate_bits_per_s": _round(delivered_bits / duration),
            "active_time_s": _round(active_time),
            "wake_count": wake_count,
            "endpoint_energy_j": endpoint_energy,
            "endpoint_energy_efficiency_bits_per_j": efficiency,
            "service_pass": service_pass,
        },
        "energy_breakdown_j": {key: _round(value) for key, value in breakdown.items()},
        "events": events,
        "warnings": warnings,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    result["run_id"] = hash_value({key: value for key, value in result.items() if key != "run_id"})
    return result
