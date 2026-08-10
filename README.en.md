# LoRaEnergySim energy-decision lab

This folder is a separately packaged learner runner for one fixed LoRaEnergySim
scenario. It provides a bounded edit → run → inspect → import loop. The runner
is deterministic course simulation data from the
`coherent-course-simulated-adapter`; it does not execute the upstream research
repository.

The claim boundary on every result and replay is exactly:

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

Endpoint energy is the package's stated endpoint radio/processing assumption.
It is not a measurement of a deployed system. The upstream repository and
commit in provenance identify the teaching reference only; they do not mean
that this runner executed upstream code.

## 0. Download from GitHub Releases

Download both named assets from the GitHub Releases page supplied by the
instructor. Do not use GitHub's automatically generated `Source code (zip)`:

```text
lora-energy-lab-v1.zip
lora-energy-lab-v1.zip.sha256
```

Verify the checksum before extracting. On Linux:

```sh
sha256sum -c lora-energy-lab-v1.zip.sha256
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

On macOS, run `shasum -a 256 lora-energy-lab-v1.zip` and compare it exactly
with the first field in the `.sha256` file. On Windows PowerShell:

```powershell
Get-FileHash .\lora-energy-lab-v1.zip -Algorithm SHA256
Expand-Archive .\lora-energy-lab-v1.zip -DestinationPath .
Set-Location .\lora-energy-lab
```

Compare the displayed hash with the first field in the `.sha256` file. The ZIP
contains one `lora-energy-lab/` root and excludes `.venv` and previous
learner-generated artifacts.

## 1. Start in this folder

Run the commands from the extracted `lora-energy-lab/` directory.

The frozen result contract requires Python 3.11.x. On Linux/macOS:

```sh
PYTHON_BIN=python3.11 bash setup.sh
bash course.sh verify
```

`setup.sh` creates the local `.venv`, checks the standard-library lock file,
and runs the same verification used by the course launcher. After setup,
`course.sh` automatically prefers `.venv/bin/python`.

On Windows Command Prompt:

```bat
set "PYTHON_BIN=py -3.11"
setup.cmd
course.cmd verify
```

The successful verification writes `artifacts/verify-receipt.json`. A host
Python other than 3.11.x must stop at the explicit version gate; do not edit
the runner to bypass it. Use an installed Python 3.11 interpreter or the
same-scenario fallback below.

If Python 3.11 is not installed, setup does not download it automatically.
The fast, explicit uv recovery is:

```sh
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)" bash setup.sh
bash course.sh verify
```

On Windows, run `uv python install 3.11`, then run `uv python find 3.11`, set
`PYTHON_BIN` to the printed interpreter path (keep surrounding quotes in the
variable if the path contains spaces), and rerun `setup.cmd`. The setup
script always verifies the selected interpreter and the resulting `.venv` as
Python 3.11.x; it does not silently accept 3.12 or 3.13.

If setup reports that an existing `.venv` uses another Python version, remove
only that package-local venv deliberately (`rm -rf .venv`, or `rmdir /s /q
.venv` on Windows) and rerun setup. Setup never deletes an existing venv
automatically.

Useful syntax checks are:

```sh
bash course.sh --help
bash course.sh run --help
```

`_make-fallbacks` is a package-maintenance command, not a learner command.

## 2. Edit only the marked policy blocks

Edit only `student_policy.py`, and only between these markers:

- `lab-a-pace-rest`
- `lab-b-enter-exit-hold`
- `lab-c-batch-urgent`

The normal learner edit is changing policy constants inside the active marked
block. Do not edit the scenario, runner, schemas, artifacts, or the other
policy code. The guard also rejects imports, arbitrary calls, unsupported AST
syntax, BOM/CRLF files, and actions outside `WAIT`, `SLEEP`, `SEND_ONE`,
`SEND_URGENT`, and `FLUSH_BATCH`.

`student_policy.baseline.py` is the packaged reference. Keep a prediction in
your Leo workbook before each run: queue/service, packet/retry, state duration,
or endpoint-energy change that the result could confirm or falsify.

## 3. Run the ten exact cases

Each successful command prints a JSON object containing the result path. The
student-run files are written under:

```text
artifacts/<run_id>/result.json
artifacts/<run_id>/endpoint-replay.json
```

The `<run_id>` directory name replaces `:` with `_`; use the printed
`result_path` rather than guessing it. A freeze also writes a receipt and a
policy checkpoint under `artifacts/receipts/` and `artifacts/checkpoints/`.

Run the cases in this order. Do not add `--freeze` to a baseline, candidate C,
or withheld command.

### Lab A — baseline, candidate, withheld

Start from the packaged baseline policy:

```sh
bash course.sh run --lab A --case baseline
```

Edit only `lab-a-pace-rest`, then freeze the candidate:

```sh
bash course.sh run --lab A --case candidate --freeze
```

Leave the frozen A policy in `student_policy.py`, then run the withheld case:

```sh
bash course.sh run --lab A --case hidden
```

The freeze checkpoint is `artifacts/checkpoints/lab-a-frozen.json` with its
policy source beside it as `lab-a-frozen.py`.

### Lab B — Trace A baseline, candidate, withheld Trace B

With the frozen Lab A policy still active:

```sh
bash course.sh run --lab B --case trace-a-baseline
```

Edit only `lab-b-enter-exit-hold`, then freeze the Trace A candidate:

```sh
bash course.sh run --lab B --case trace-a-candidate --freeze
```

Leave that B freeze active and run withheld Trace B:

```sh
bash course.sh run --lab B --case trace-b
```

The B checkpoint is `artifacts/checkpoints/lab-b-frozen.json` with
`lab-b-frozen.py` beside it.

### Lab C — baseline, candidate, revision, withheld surprise

With the frozen Lab B policy still active:

```sh
bash course.sh run --lab C --case baseline
```

Edit only `lab-c-batch-urgent` and run the candidate. This command does not
create a freeze:

```sh
bash course.sh run --lab C --case candidate
```

The candidate source is checkpointed as
`artifacts/checkpoints/lab-c-candidate.py`. Make one further legal Lab C edit
relative to that candidate and freeze the revision:

```sh
bash course.sh run --lab C --case revision --freeze
```

Leave the C revision policy active and run the withheld surprise case:

```sh
bash course.sh run --lab C --case surprise
```

The revision checkpoint is `artifacts/checkpoints/lab-c-frozen.json` with
`lab-c-frozen.py` beside it.

## 4. If a run cannot be produced: same-scenario fallback

Do not relabel a fallback as a student run. The static fallback artifacts are
already paired by exact case and preserve `artifact_source:
same-scenario-fallback`, the same scenario identity, predecessor lineage, and
freeze receipt where the case contract requires one.

Use the matching `result.json` below; keep its sibling
`endpoint-replay.json` with the same run ID:

| case | fallback result |
|---|---|
| A baseline | `fallback_artifacts/baseline-A/result.json` |
| A candidate | `fallback_artifacts/candidate-A/result.json` |
| A hidden | `fallback_artifacts/hidden-A/result.json` |
| B Trace A baseline | `fallback_artifacts/trace-a-baseline-B/result.json` |
| B Trace A candidate | `fallback_artifacts/trace-a-candidate-B/result.json` |
| B Trace B | `fallback_artifacts/trace-b-B/result.json` |
| C baseline | `fallback_artifacts/baseline-C/result.json` |
| C candidate | `fallback_artifacts/candidate-C/result.json` |
| C revision | `fallback_artifacts/revision-C/result.json` |
| C surprise | `fallback_artifacts/surprise-C/result.json` |

`fallback_artifacts/manifest.json` records all ten labels, result/replay
paths, scenario identity, policy lineage, and receipt hashes. A fallback is a
teaching recovery path for the same scenario; it is not evidence that your
local policy executed.

## 5. Import into Leo and preserve the workbook

Open Leo at `/course`. In the result-import control, choose
the generated `artifacts/<run_id>/result.json`, or the matching fallback
`result.json` when using recovery. Do not upload or execute `student_policy.py`.
Leo validates the result and materializes its endpoint replay; keep the paired
`endpoint-replay.json` available for the same run identity and audit trail.

Import the cases in lab order so the workbook can retain baseline, candidate,
freeze, and withheld lineage. Check that the displayed scenario ID and run ID
match the selected file. An identity, schema, unit, policy, or provenance
mismatch must leave the workbook unchanged; correct the named artifact or
switch to the matching same-scenario fallback.

Use the workbook's Save/Export control to save the Energy Decision Workbook.
Close or reload `/course`, then use its Open/Reopen control to load that saved
workbook. Confirm that the same scenario and imported run/replay records return.
Missing evidence must remain visibly incomplete; never create a completion
claim by editing JSON by hand.

## 6. Recovery checklist

- Setup or verify fails: confirm the interpreter is Python 3.11.x, rerun the
  OS-appropriate setup command, then rerun `course.sh verify`/`course.cmd
  verify`. If the environment remains unavailable, use the matching fallback.
- Policy guard fails: inspect the named error, restore UTF-8/LF formatting,
  remove imports/calls, and change only the active marked block.
- A freeze is missing: run the preceding candidate command with `--freeze`
  while that exact policy is active. Withheld cases never create a new freeze.
- A later lab says the policy or predecessor is wrong: keep the required
  freeze checkpoint active and do not mix a different lab's edit into it.
- Leo import fails: do not hand-edit result or replay JSON. Preserve the
  error, use the matching fallback pair, and retry the import.
- A workbook is lost: reopen the saved export. If no saved workbook exists,
  restart with the same scenario and mark the missing evidence incomplete.

## 7. Claim ceiling

This package claims only deterministic, coherent simulated teaching data under
the fixed scenario and declared endpoint-energy assumptions:

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

It does not claim execution of `GillesC/LoRaEnergySim`, live network behavior,
deployed-system measurement, or parity with an upstream implementation.
