# Same-scenario fallback

The JSON files in this directory are deterministic teaching artifacts for the
same frozen scenario and carry `artifact_source: same-scenario-fallback`.
There is one result and one endpoint replay for each exact case directory:

`baseline-A`, `candidate-A`, `hidden-A`, `trace-a-baseline-B`,
`trace-a-candidate-B`, `trace-b-B`, `baseline-C`, `candidate-C`,
`revision-C`, and `surprise-C`.

The `receipts/` directory contains the A/B/C frozen-stage receipts. Withheld
results echo their corresponding receipt and predecessor policy hashes. Cases
whose contract `expected_freeze_role` is null retain a nullable freeze field;
this includes the baseline controls and the unfrozen C candidate. They are not
live measurements and do not claim upstream execution. The manifest records
each artifact's scenario, content identity, and lineage.
