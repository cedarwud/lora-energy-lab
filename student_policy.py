"""Bounded student policy for the LoRa energy energy-decision lab.

Learners may edit only the three marked blocks.  The runner checks the source
surface, hashes the exact UTF-8/LF bytes, and executes this function locally.
No student policy is uploaded to or executed by Leo.
"""

WAIT = "WAIT"
SLEEP = "SLEEP"
SEND_ONE = "SEND_ONE"
SEND_URGENT = "SEND_URGENT"
FLUSH_BATCH = "FLUSH_BATCH"

# === LORA EDITABLE: lab-a-pace-rest ===
PACE_GAP_STEPS = 2
REST_DURING_GAP = SLEEP
# === LORA END EDITABLE: lab-a-pace-rest ===

# === LORA EDITABLE: lab-b-enter-exit-hold ===
ENTER_QUALITY = 2
EXIT_QUALITY = 1
STABLE_STEPS = 2
# === LORA END EDITABLE: lab-b-enter-exit-hold ===

# === LORA EDITABLE: lab-c-batch-urgent ===
BATCH_SIZE = 3
URGENT_MARGIN_S = 20
# === LORA END EDITABLE: lab-c-batch-urgent ===


def choose_action(observation):
    """Choose one legal action using only current/past observation fields."""
    if not observation.contact_open:
        return SLEEP
    if observation.urgent_pending and observation.urgent_due_in_s <= URGENT_MARGIN_S:
        return SEND_URGENT
    if observation.steps_since_send < PACE_GAP_STEPS:
        return REST_DURING_GAP
    if observation.send_mode_active:
        quality_ready = observation.quality_band >= EXIT_QUALITY
    else:
        quality_ready = (
            observation.quality_band >= ENTER_QUALITY
            and observation.stable_steps >= STABLE_STEPS
        )
    if quality_ready:
        if observation.queue_size >= BATCH_SIZE:
            return FLUSH_BATCH
        return SEND_ONE
    return WAIT
