# LoRa energy lab contract v1

This directory is the frozen JSON boundary between the separately packaged
course runner and Leo's `/course` importer. It does not authorize Leo to run
uploaded Python or to reinterpret endpoint energy as current LoRa energy system
energy.

Contract constants:

- scenario: `ntpu-energy-decision-01`;
- upstream reference: `GillesC/LoRaEnergySim@f854462cda0cd30cb56e3f0c576cb004711842f6`;
- runner: `lora-energy-runner-v1`;
- policy API: `lora-energy-policy-v1`;
- replay: `lora-energy-endpoint-replay-v1`;
- workbook extension: `lora-energy-decision-workbook-v3`;
- artifact source: `student-run` or `same-scenario-fallback`;
- engine mode for this bounded implementation:
  `coherent-course-simulated-adapter`, with `upstream_execution: false`.

The importer validates the result in the SDD's fail-closed order and changes
no session state until all checks and endpoint replay materialization succeed.
The `golden/` directory contains one valid baseline result, its endpoint-only
replay, one freeze receipt, and the resulting workbook extension. Invalid and
mismatch cases are derived from these fixtures in tests so they cannot drift
into accidentally valid second authorities.

Claim boundary on every artifact and UI surface:

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`
