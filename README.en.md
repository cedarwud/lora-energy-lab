# LoRaEnergySim energy-decision lab

This folder is a separately packaged local runner for one fixed LoRaEnergySim
scenario. It provides a bounded edit → run → inspect → import loop. The runner
is deterministic simulation data from the
`coherent-course-simulated-adapter`; it does not execute the upstream research
repository.

The claim boundary on every result and replay is exactly:

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

Endpoint energy is the package's stated endpoint radio/processing assumption.
It is not a measurement of a deployed system. The upstream repository and
commit in provenance identify the reference only; they do not mean
that this runner executed upstream code.

## 0. Download and extract the GitHub Release

Download `lora-energy-lab-v1.zip` from the project's GitHub Releases page. Do
not use GitHub's automatically generated `Source code (zip)`. Use the commands
for your operating system; do not mix PowerShell, Command Prompt, and POSIX
shell syntax.

### Windows (PowerShell)

```powershell
Expand-Archive .\lora-energy-lab-v1.zip -DestinationPath .
Set-Location .\lora-energy-lab
```

### Linux

Run `command -v unzip` first. If it prints no path, Ubuntu/WSL Ubuntu can
install it with:

```sh
sudo apt update
sudo apt install -y unzip
```

On another distribution, install `unzip` with its package manager. Then
extract the archive:

```sh
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

### macOS

```sh
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

The ZIP contains one `lora-energy-lab/` root and excludes `.venv` and previous
locally generated artifacts.

## 1. Install Python, create the venv, then install

Run every command below from the extracted `lora-energy-lab/` directory. The
frozen result contract **accepts only Python 3.11.x**. A `python`, `python3`, or
`py -3` command that selects another version is not a substitute. Do not edit
the runner to bypass the version gate.

The complete order is: install or locate Python 3.11 → confirm `venv` support
→ create `.venv` → activate `.venv` → install the locked requirements →
verify.

`venv` is a Python standard-library module, not a third-party package to
install with `pip install venv`. Standard Windows, macOS, and uv-managed Python
installations normally include it. Some Linux distributions package it
separately. See the [Python 3.11 venv documentation](https://docs.python.org/3.11/library/venv.html).

### Windows (PowerShell)

#### 1. Install or locate Python 3.11

Check the Python Launcher first:

```powershell
py -3.11 --version
$python311 = (py -3.11 -c "import sys; print(sys.executable)").Trim()
```

If this reports `Python 3.11.x`, continue to the next step. If 3.11 is not
available, install uv using one of the official methods in the
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
winget install --id=astral-sh.uv -e
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reopen PowerShell if directed by the installer, then install Python 3.11 and
capture its interpreter path:

```powershell
uv --version
uv python install 3.11
$python311 = (uv python find 3.11).Trim()
& $python311 --version
```

#### 2. Confirm venv support, create it, and activate it

Standard Windows Python and uv-managed Python include `venv`:

```powershell
& $python311 -m venv --help
& $python311 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -c "import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)"
```

#### 3. Install and verify inside the activated venv

```powershell
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r .\requirements-lock.txt
.\course.cmd verify
```

If PowerShell blocks `Activate.ps1`, do not weaken the system-wide execution
policy. Open Command Prompt in this package directory and perform activation,
installation, and verification in that same window:

```bat
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
course.cmd verify
```

### Linux (including WSL)

#### 1. Check first, then install Python 3.11 if needed

WSL uses the Linux distribution installed inside it; WSL is not a separate
package repository. Check for an existing Python 3.11 first:

```sh
command -v python3.11
python3.11 --version
```

If both commands succeed and report `Python 3.11.x`, select that interpreter:

```sh
PYTHON_BIN="$(command -v python3.11)"
```

If 3.11 is absent, use uv to install the exact version. The default Ubuntu
24.04 repositories, including WSL Ubuntu 24.04, do not provide `python3.11` or
`python3.11-venv`, so do not keep retrying those apt packages. Use apt only to
install the `curl` prerequisite:

```sh
sudo apt update
sudo apt install -y curl
```

On another Linux distribution, install `curl` with that distribution's package
manager if it is missing. Then install uv from the official
[uv installation guide](https://docs.astral.sh/uv/getting-started/installation/):

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

The installer normally updates the shell configuration. If a later terminal
still cannot find `uv`, follow the PATH instruction printed by the installer.
Install Python 3.11 and save its path:

```sh
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)"
"$PYTHON_BIN" --version
```

#### 2. Confirm venv support, create it, and activate it

```sh
"$PYTHON_BIN" -m venv --help
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python --version
python -c 'import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)'
```

Only successful creation of `.venv` proves that venv support is complete. If a
distribution Python reports missing `venv` or `ensurepip` here, remove the
incomplete `.venv`, return to the previous step, select the uv-managed Python,
and create it again. The uv-managed Python includes everything needed; no
separate venv application is required.

#### 3. Install and verify inside the activated venv

```sh
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
bash course.sh verify
```

### macOS

#### 1. Install or locate Python 3.11

Check first; do not assume the macOS `python3` command is Python 3.11:

```sh
command -v python3.11
python3.11 --version
```

If Python 3.11 is absent and Homebrew is available, install the maintained
[`python@3.11` formula](https://formulae.brew.sh/formula/python%403.11):

```sh
brew install python@3.11
PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
"$PYTHON_BIN" --version
```

If Homebrew is not used, install uv instead:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reopen the shell or follow the installer's PATH instruction, then run:

```sh
uv --version
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)"
"$PYTHON_BIN" --version
```

If the correct version was already present, set:

```sh
PYTHON_BIN="$(command -v python3.11)"
```

#### 2. Confirm venv support, create it, and activate it

Homebrew and uv Python installations include `venv`:

```sh
"$PYTHON_BIN" -m venv --help
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python --version
python -c 'import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)'
```

#### 3. Install and verify inside the activated venv

```sh
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
bash course.sh verify
```

### Setup-script shortcut (use instead of the manual flow)

If the individual create-and-activate steps are not needed, the packaged setup
script checks Python 3.11, creates `.venv`, performs the same locked install,
and verifies it. This is an equivalent alternative; do not repeat it after
finishing the manual flow above.

Windows with `py -3.11`:

```powershell
.\setup.cmd
```

Windows with the `$python311` path returned by uv:

```powershell
$env:PYTHON_BIN = '"' + $python311 + '"'
.\setup.cmd
Remove-Item Env:PYTHON_BIN
```

Linux/macOS with a system or Homebrew Python:

```sh
PYTHON_BIN=python3.11 bash setup.sh
```

Linux/macOS with uv-managed Python:

```sh
PYTHON_BIN="$(uv python find 3.11)" bash setup.sh
```

### What verify proves and what comes next

The manual `course.cmd verify` / `course.sh verify` commands perform the same
check as `python verify_setup.py`; use only one of them. `setup.cmd` and
`setup.sh` already run verify as their final step, so a successful setup does
not need a second verification.

Verify confirms that:

- the interpreter is exactly Python 3.11.x;
- the scenario identity and hashes can be loaded;
- the packaged baseline policy is unchanged and the policy-marker structure
  is valid;
- the requirements-lock hash, policy API, engine mode, and claim boundary can
  be recorded.

On success, `artifacts/verify-receipt.json` is only a receipt that the current
environment is `READY`. It is not a case result and does not mean the full
workflow is complete. After seeing `"status":"READY"`:

1. Keep `.venv` active after the manual flow. After the setup shortcut, the
   course launcher selects `.venv` directly; activate it with the command above
   if an interactive environment is desired. Then follow section 2 and edit
   only the designated region of `student_policy.py`.
2. Run the cases in section 3. Those commands produce the `result.json` and
   `endpoint-replay.json` files that contain the data to inspect.
3. Inspect the result and import `result.json` into Leo as described in section
   5.

The package currently has a standard-library-only runtime, so
`requirements-lock.txt` has no third-party runtime dependency. The
locked-install step remains part of the fixed setup contract.

### Deactivation and recreation

Leave an activated environment with:

```text
deactivate
```

If an existing `.venv` uses another Python version, confirm that the current
directory is this package root, remove only the package-local venv, and repeat
this section. Setup never removes an existing venv automatically.

Windows PowerShell:

```powershell
Remove-Item -LiteralPath .\.venv -Recurse -Force
```

Windows Command Prompt:

```bat
rmdir /s /q .venv
```

Linux/macOS:

```sh
rm -rf -- .venv
```

Use the matching launcher for CLI syntax checks. Windows PowerShell:

```powershell
.\course.cmd --help
.\course.cmd run --help
```

Linux/macOS:

```sh
bash course.sh --help
bash course.sh run --help
```

`_make-fallbacks` is a package-maintenance command, not a normal operation.

## 2. Edit only the marked policy blocks

Edit only `student_policy.py`, and only between these markers:

- `lab-a-pace-rest`
- `lab-b-enter-exit-hold`
- `lab-c-batch-urgent`

The normal edit is changing policy constants inside the active marked
block. Do not edit the scenario, runner, schemas, artifacts, or the other
policy code. The guard also rejects imports, arbitrary calls, unsupported AST
syntax, BOM/CRLF files, and actions outside `WAIT`, `SLEEP`, `SEND_ONE`,
`SEND_URGENT`, and `FLUSH_BATCH`.

`student_policy.baseline.py` is the packaged reference. Keep a prediction in
your Leo workbook before each run: queue/service, packet/retry, state duration,
or endpoint-energy change that the result could confirm or falsify.

## 3. Run the ten exact cases

Each successful command prints a JSON object containing the result path. The
locally generated files are written under:

```text
artifacts/<run_id>/result.json
artifacts/<run_id>/endpoint-replay.json
```

The `<run_id>` directory name replaces `:` with `_`; use the printed
`result_path` rather than guessing it. A freeze also writes a receipt and a
policy checkpoint under `artifacts/receipts/` and `artifacts/checkpoints/`.

Run the cases in this order. Do not add `--freeze` to a baseline, candidate C,
or withheld command.

### Choose the launcher for the operating system

The ten examples below show the Linux/macOS form. On Windows, keep the same
arguments and replace only the launcher:

| Operating system/shell | Form shown below | Command to run |
|---|---|---|
| Linux/macOS | `bash course.sh run ...` | `bash course.sh run ...` |
| Windows PowerShell | `bash course.sh run ...` | `.\course.cmd run ...` |
| Windows Command Prompt | `bash course.sh run ...` | `course.cmd run ...` |

For example, Lab A baseline in Windows PowerShell is:

```powershell
.\course.cmd run --lab A --case baseline
```

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

Do not describe a fallback as an actual execution of the local policy. The
static fallback artifacts are already paired by exact case and preserve `artifact_source:
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
recovery path for the same scenario; it is not evidence that your
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

### Runner recovery commands

Run these commands from the extracted `lora-energy-lab/` directory. Within
that directory, `restore` and `reset-policy` persistently replace only the
active `student_policy.py`; none of the three commands deletes, rewrites, or
regenerates results, replays, receipts, or checkpoints under `artifacts/`. A
successful JSON response explicitly includes `artifacts_untouched: true`.

First inspect whether the current policy is valid and which recovery checkpoints
passed their full validation:

```sh
bash course.sh status
```

On Windows Command Prompt:

```bat
course.cmd status
```

To return to a known policy stage, use a role listed by `status`:

```sh
bash course.sh restore --checkpoint <role>
```

```bat
course.cmd restore --checkpoint <role>
```

Available roles are:

| role | purpose |
|---|---|
| `release-default` | Packaged baseline; the target of `reset-policy` |
| `lab-a-frozen` | Lab A candidate freeze for hidden A and the following Lab B |
| `lab-b-frozen` | Lab B Trace A candidate freeze for Trace B and Lab C |
| `lab-c-candidate` | First Lab C candidate source; no freeze receipt, for recovery before revision |
| `lab-c-frozen` | Lab C revision freeze for the surprise case |

To return only to the packaged baseline, use:

```sh
bash course.sh reset-policy
```

```bat
course.cmd reset-policy
```

`reset-policy` is equivalent to `restore --checkpoint release-default`. Use it
when the active policy is invalid, another lab's marked block was mixed in, or
the run should restart; it does not clear existing results or workbooks.

`status` reports a missing or corrupt checkpoint/receipt, a scenario/lock/policy
hash mismatch, or another unavailable role as `available: false` with an error;
it does not change the active policy or any artifact. `restore` and
`reset-policy` fail closed for an unknown or unavailable role, any hash
mismatch, or failed post-restore policy API validation: they print `ERROR` and
exit non-zero. If post-write validation fails, the runner attempts to atomically
restore the exact pre-command `student_policy.py` bytes; it does not continue
with an unvalidated policy.

- Setup or verify fails: confirm that the interpreter is Python 3.11.x, then
  either repeat the manual flow in section 1 or rerun the OS-appropriate setup
  script. A successful setup already means verify succeeded. If the environment
  remains unavailable, use the matching fallback.
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

This package claims only deterministic, coherent simulated data under the
fixed scenario and declared endpoint-energy assumptions. Its exact claim
boundary is:

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

It does not claim execution of `GillesC/LoRaEnergySim`, live network behavior,
deployed-system measurement, or parity with an upstream implementation.
