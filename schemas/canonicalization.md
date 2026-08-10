# LoRa energy canonicalization contract

Contract version: `lora-energy-leo-v1`

Every content address in this directory uses RFC 8785 JSON Canonicalization
Scheme (JCS), encoded as UTF-8 and hashed with SHA-256. Hash strings use the
form `sha256:<64 lowercase hexadecimal characters>`.

The supported interchange subset rejects duplicate object keys, non-finite
numbers, negative zero, integers outside JavaScript's safe-integer range,
surrogate code points, and values not representable as JSON. Producers must
emit object keys in Unicode code-point order, arrays in source order, no
insignificant whitespace, and the ECMAScript JSON number representation used
by RFC 8785. Course numeric values are bounded finite values rounded to at most
six decimal places so the Python and TypeScript implementations have one byte
representation.

Hash preimages are:

- `policy_sha256`: the exact UTF-8 bytes of `student_policy.py`, including LF
  line endings. A UTF-8 BOM, CRLF line endings, or any byte outside the
  scaffold therefore changes the identity and is rejected by the policy
  surface guard before execution.
- `scenario_anchor_sha256`: the complete `scenario_anchor` object.
- `scenario_sha256`: the complete scenario object with only
  `scenario_sha256` omitted. It therefore includes `scenario_anchor` and
  `scenario_anchor_sha256`.
- `receipt_sha256`: the complete freeze receipt with only `receipt_sha256`
  omitted.
- `run_id`: the complete result with only `run_id` omitted.
- `endpoint_replay_input_id`: canonical
  `{contract_version,scenario_anchor_sha256,scenario_sha256,lab_id,case_id,seed,
  policy_sha256,predecessor_policy_sha256,freeze_receipt_sha256}`.
- `endpoint_replay_id`: canonical
  `{endpoint_replay_contract_version,endpoint_replay_input_id,run_id,
  scenario_anchor_sha256,scenario_sha256}`.

Filenames, timestamps, absolute paths, usernames, hostnames, locale-dependent
labels, and upload names never enter a preimage. Importers recompute every
content address and fail closed before changing session or workbook state.
