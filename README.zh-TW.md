# LoRaEnergySim 能源決策實驗

本目錄是獨立封裝的 LoRaEnergySim runner，固定使用一個 scenario，提供
「編輯 → 執行 → 檢查 → 匯入」的 bounded 流程。Runner 是
`coherent-course-simulated-adapter` 產生的 deterministic 模擬資料；不會
執行上游研究 repository。

每個 result 與 replay 的精確 claim boundary 是：

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

Endpoint energy 只代表本套件宣告的 endpoint radio/processing 假設，不是部署
系統的量測。provenance 中的上游 repository/commit 只是參考識別，不表示
runner 實際執行上游程式。

## 0. 從 GitHub Releases 下載並解壓縮

從專案的 GitHub Releases 頁面下載 `lora-energy-lab-v1.zip`；不要下載 GitHub
自動產生的 `Source code (zip)`。請依作業系統使用對應命令，不要混用
PowerShell、Command Prompt 與 POSIX shell 語法。

### Windows（PowerShell）

```powershell
Expand-Archive .\lora-energy-lab-v1.zip -DestinationPath .
Set-Location .\lora-energy-lab
```

### Linux

先執行 `command -v unzip`。若沒有輸出，Ubuntu／WSL Ubuntu 可先安裝：

```sh
sudo apt update
sudo apt install -y unzip
```

其他 distribution 請使用其 package manager 安裝 `unzip`。然後解壓縮：

```sh
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

### macOS

```sh
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

ZIP 內只有一個 `lora-energy-lab/` 根目錄；`.venv` 與先前在本機產生的
artifacts 不會包在下載檔內。

## 1. 依序安裝 Python、建立 venv 並安裝

以下命令都要在解壓後的 `lora-energy-lab/` 執行。Frozen result contract **只接受
Python 3.11.x**；`python`、`python3` 或 `py -3` 若指向其他版本都不符合要求。
不要修改 runner 放寬版本 gate。

完整順序是：安裝或找到 Python 3.11 → 確認 `venv` 支援 → 建立 `.venv` →
啟用 `.venv` → 安裝 locked requirements → verify。

`venv` 是 Python standard library 的 module，不是要用 `pip install venv` 安裝的
第三方套件。Windows、macOS 與 uv 管理的 Python 通常已包含它；Debian/Ubuntu
則可能另外封裝成 `python3.11-venv`。可參考 [Python 3.11 venv 官方文件](https://docs.python.org/3.11/library/venv.html)。

### Windows（PowerShell）

#### 1. 安裝或找到 Python 3.11

先檢查 Python Launcher：

```powershell
py -3.11 --version
$python311 = (py -3.11 -c "import sys; print(sys.executable)").Trim()
```

若顯示 `Python 3.11.x`，繼續下一步。若找不到 3.11，先依
[uv 官方安裝說明](https://docs.astral.sh/uv/getting-started/installation/)安裝 uv；以下兩種方式擇一：

```powershell
winget install --id=astral-sh.uv -e
```

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

依 installer 提示重開 PowerShell，然後安裝 Python 3.11 並取得其路徑：

```powershell
uv --version
uv python install 3.11
$python311 = (uv python find 3.11).Trim()
& $python311 --version
```

#### 2. 確認 venv、建立並啟用環境

標準 Windows Python 與 uv-managed Python 都已包含 `venv`；先確認 module 可用，
再建立 `.venv`：

```powershell
& $python311 -m venv --help
& $python311 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -c "import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)"
```

#### 3. 在已啟用的 venv 中安裝並驗證

```powershell
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r .\requirements-lock.txt
.\course.cmd verify
```

若 PowerShell 不允許執行 `Activate.ps1`，不必放寬全系統 execution policy。改在
本 package 目錄開啟 Command Prompt，並在同一個視窗完成 activation、安裝與
verify：

```bat
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
course.cmd verify
```

### Linux（包含 WSL）

#### 1. 先檢查，再視需要安裝 Python 3.11

WSL 會使用其中安裝的 Linux distribution，不是獨立的套件來源。先檢查目前是否
已有可用的 Python 3.11：

```sh
command -v python3.11
python3.11 --version
```

若兩行成功且顯示 `Python 3.11.x`，先選用該 interpreter：

```sh
PYTHON_BIN="$(command -v python3.11)"
```

若找不到 3.11，使用 uv 安裝精確版本。Ubuntu 24.04（包括 WSL Ubuntu 24.04）
的預設 repository 沒有 `python3.11` 與 `python3.11-venv`，所以不必再嘗試那兩個
apt 套件；只用 apt 安裝 uv 所需的 `curl`：

```sh
sudo apt update
sudo apt install -y curl
```

其他 Linux distribution 若沒有 `curl`，請先用該 distribution 的 package
manager 安裝。接著依
[uv 官方安裝說明](https://docs.astral.sh/uv/getting-started/installation/)安裝 uv：

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

installer 通常會更新 shell 設定；若之後新開的 terminal 仍找不到 `uv`，依
installer 顯示的 PATH 提示處理。接著安裝精確的 Python 3.11 並記住路徑：

```sh
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)"
"$PYTHON_BIN" --version
```

#### 2. 確認 venv、建立並啟用環境

```sh
"$PYTHON_BIN" -m venv --help
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python --version
python -c 'import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)'
```

成功建立 `.venv` 才代表 venv 支援完整可用。若選用的 distribution Python 在
這一步回報缺少 `venv` 或 `ensurepip`，刪除未完成的 `.venv`，回到上一步改用
uv-managed Python 再建立。uv-managed Python 已包含所需功能，不必安裝另一個
venv 應用程式。

#### 3. 在已啟用的 venv 中安裝並驗證

```sh
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
bash course.sh verify
```

### macOS

#### 1. 安裝或找到 Python 3.11

先檢查，不要假設 macOS 的 `python3` 就是 3.11：

```sh
command -v python3.11
python3.11 --version
```

若尚未安裝且已有 Homebrew，使用維護中的
[`python@3.11` formula](https://formulae.brew.sh/formula/python%403.11)：

```sh
brew install python@3.11
PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
"$PYTHON_BIN" --version
```

不使用 Homebrew 時，可改用 uv：

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

依 installer 提示重開 shell 或更新 PATH，然後執行：

```sh
uv --version
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)"
"$PYTHON_BIN" --version
```

若一開始就已經有正確版本，設定：

```sh
PYTHON_BIN="$(command -v python3.11)"
```

#### 2. 確認 venv、建立並啟用環境

Homebrew 與 uv 的 Python 已包含 `venv`：

```sh
"$PYTHON_BIN" -m venv --help
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python --version
python -c 'import sys; assert sys.prefix != sys.base_prefix; print(sys.executable)'
```

#### 3. 在已啟用的 venv 中安裝並驗證

```sh
python -m pip install --disable-pip-version-check --require-hashes --no-deps -r requirements-lock.txt
bash course.sh verify
```

### Setup script 快速流程（與上方手動流程二選一）

若不需要逐步手動建立及啟用，package 內的 setup script 會自動檢查 3.11、建立
`.venv`、執行相同的 locked install 與 verify。不要在完成上方手動流程後再重複
執行；這是另一條等價路徑。

Windows 使用 `py -3.11` 時：

```powershell
.\setup.cmd
```

Windows 使用前面由 uv 找到的 `$python311` 時：

```powershell
$env:PYTHON_BIN = '"' + $python311 + '"'
.\setup.cmd
Remove-Item Env:PYTHON_BIN
```

Linux/macOS 使用系統或 Homebrew Python：

```sh
PYTHON_BIN=python3.11 bash setup.sh
```

Linux/macOS 使用 uv-managed Python：

```sh
PYTHON_BIN="$(uv python find 3.11)" bash setup.sh
```

### Verify 的目的與接下來的流程

手動流程中的 `course.cmd verify`／`course.sh verify` 會執行與
`python verify_setup.py` 相同的檢查，三者擇一即可。`setup.cmd`／`setup.sh` 已在
最後自動執行 verify，成功後不必再驗證第二次。

Verify 會確認：

- interpreter 確實是 Python 3.11.x；
- scenario identity 與 hash 可以載入；
- 封裝的 baseline policy 未被修改，policy markers 結構正確；
- `requirements-lock.txt` 的 hash、policy API、engine mode 與 claim boundary 可記錄。

成功時寫入的 `artifacts/verify-receipt.json` 只是一份「目前環境 READY」的收據，
不是案例執行結果，也不代表整個流程已完成。看到 `"status":"READY"` 後：

1. 手動流程保持 `.venv` 啟用；若使用 setup shortcut，course launcher 會直接選用
   `.venv`，也可先用本節的 activation 命令進入環境。接著前往第 2 節，只修改
   `student_policy.py` 的指定區域。
2. 依第 3 節執行案例；每個案例才會產生要分析的 `result.json` 與
   `endpoint-replay.json`。
3. 檢查結果，並依第 5 節將 `result.json` 匯入 Leo。

本 package 目前只使用 standard library，所以 `requirements-lock.txt` 沒有第三方
runtime dependency；locked install 仍是固定 setup contract 的一部分。

### 離開環境與重建

離開已啟用的環境：

```text
deactivate
```

若既有 `.venv` 使用其他 Python 版本，確認目前位於本 package 根目錄，只刪除這個
package-local venv 後重做本節流程。Setup 不會自動刪除既有 venv。

Windows PowerShell：

```powershell
Remove-Item -LiteralPath .\.venv -Recurse -Force
```

Windows Command Prompt：

```bat
rmdir /s /q .venv
```

Linux/macOS：

```sh
rm -rf -- .venv
```

檢查 CLI 語法時也要使用對應 launcher。Windows PowerShell：

```powershell
.\course.cmd --help
.\course.cmd run --help
```

Linux/macOS：

```sh
bash course.sh --help
bash course.sh run --help
```

`_make-fallbacks` 是 package 維護命令，不是一般操作。

## 2. 只修改標記的 policy 區域

只編輯 `student_policy.py`，而且只可在以下三組 markers 中修改：

- `lab-a-pace-rest`
- `lab-b-enter-exit-hold`
- `lab-c-batch-urgent`

一般操作是在目前 lab 的 marked block 內改 policy constants。不要修改
scenario、runner、schemas、artifacts 或其他 policy 程式。Guard 也會拒絕
import、任意 function call、不支援的 AST 語法、BOM/CRLF，以及不在
`WAIT`、`SLEEP`、`SEND_ONE`、`SEND_URGENT`、`FLUSH_BATCH` 中的 action。

`student_policy.baseline.py` 是封裝的 reference。每次執行前，先在 Leo
workbook 記錄 queue/service、packet/retry、state duration 或 endpoint-energy
的 prediction，讓結果可以確認或反駁因果假設。

## 3. 依序執行十個 exact cases

每次成功的 command 都會印出包含 result path 的 JSON。本機 runner 產生的檔案位於：

```text
artifacts/<run_id>/result.json
artifacts/<run_id>/endpoint-replay.json
```

`<run_id>` 目錄名稱會把 `:` 換成 `_`；請使用 command 印出的
`result_path`，不要自行猜路徑。freeze 另外會在 `artifacts/receipts/` 與
`artifacts/checkpoints/` 寫入 receipt 和 policy checkpoint。

依下列順序執行。baseline、C candidate、以及 withheld command 都不要加
`--freeze`。

### 依作業系統選擇 launcher

下列十個案例以 Linux/macOS 的 `bash course.sh ...` 顯示。Windows 使用相同參數，
只替換 launcher：

| 作業系統／shell | 文件中的命令 | 實際命令 |
|---|---|---|
| Linux/macOS | `bash course.sh run ...` | `bash course.sh run ...` |
| Windows PowerShell | `bash course.sh run ...` | `.\course.cmd run ...` |
| Windows Command Prompt | `bash course.sh run ...` | `course.cmd run ...` |

例如 Windows PowerShell 的 Lab A baseline 是：

```powershell
.\course.cmd run --lab A --case baseline
```

### Lab A：baseline、candidate、withheld

先使用封裝的 baseline policy：

```sh
bash course.sh run --lab A --case baseline
```

只修改 `lab-a-pace-rest`，再 freeze candidate：

```sh
bash course.sh run --lab A --case candidate --freeze
```

保持 frozen A policy 不變，執行 withheld：

```sh
bash course.sh run --lab A --case hidden
```

freeze checkpoint 是 `artifacts/checkpoints/lab-a-frozen.json`，旁邊的
`lab-a-frozen.py` 是對應 frozen policy source。

### Lab B：Trace A baseline、candidate、withheld Trace B

保持 frozen Lab A policy：

```sh
bash course.sh run --lab B --case trace-a-baseline
```

只修改 `lab-b-enter-exit-hold`，再 freeze Trace A candidate：

```sh
bash course.sh run --lab B --case trace-a-candidate --freeze
```

保持 B freeze，執行 withheld Trace B：

```sh
bash course.sh run --lab B --case trace-b
```

B checkpoint 是 `artifacts/checkpoints/lab-b-frozen.json`，旁邊有
`lab-b-frozen.py`。

### Lab C：baseline、candidate、revision、withheld surprise

保持 frozen Lab B policy：

```sh
bash course.sh run --lab C --case baseline
```

只修改 `lab-c-batch-urgent`，執行 candidate；這一步不建立 freeze：

```sh
bash course.sh run --lab C --case candidate
```

candidate source 會 checkpoint 到 `artifacts/checkpoints/lab-c-candidate.py`。
再相對於該 candidate 做一次合法的 Lab C marked-block 修改，然後 freeze
revision：

```sh
bash course.sh run --lab C --case revision --freeze
```

保持 C revision policy，執行 withheld surprise：

```sh
bash course.sh run --lab C --case surprise
```

revision checkpoint 是 `artifacts/checkpoints/lab-c-frozen.json`，旁邊有
`lab-c-frozen.py`。

## 4. 無法產生 run 時：同 scenario fallback

不要把 fallback 說成本機 policy 的實際執行結果。Static fallback 已按 exact case
配對，保留 `artifact_source: same-scenario-fallback`、同一 scenario identity、
predecessor lineage，以及 contract 要求的 freeze receipt。

使用下列對應的 `result.json`，並保留同目錄、相同 run ID 的
`endpoint-replay.json`：

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

`fallback_artifacts/manifest.json` 記錄十個 label、result/replay path、scenario
identity、policy lineage 和 receipt hashes。Fallback 是同 scenario 的 recovery
路徑，不表示你的本地 policy 曾執行。

## 5. 匯入 Leo 並保存 workbook

開啟 Leo 的 `/course` route。在 result 匯入控制項選擇產生的
`artifacts/<run_id>/result.json`；使用 recovery 時選擇對應的 fallback
`result.json`。不要上傳或執行 `student_policy.py`。Leo 會驗證 result 並
materialize endpoint replay；請保留配對的 `endpoint-replay.json`，以維持相同
run identity 和 audit trail。

依 Lab 順序匯入，讓 workbook 保留 baseline、candidate、freeze、withheld
lineage。確認畫面中的 scenario ID、run ID 與檔案相同。若 identity、schema、
unit、policy 或 provenance 不一致，workbook 不應改變；修正指定 artifact，或
改用相同 scenario 的 fallback。

使用 workbook 的 Save/Export 控制項保存 Energy Decision Workbook。關閉或
重新載入 `/course`，再使用 Open/Reopen 控制項載入保存的 workbook。確認同一
scenario 與已匯入的 run/replay records 回來。證據不完整時必須保持 incomplete；
不可手改 JSON 製造完成狀態。

## 6. 失敗 recovery 清單

- setup 或 verify 失敗：確認 interpreter 是 Python 3.11.x，然後選擇重做第 1 節
  的手動流程，或重新執行對應 OS 的 setup script。Setup 成功本身就代表 verify
  已成功；環境仍不可用時，使用對應 fallback。
- Policy guard 失敗：依錯誤訊息修正 UTF-8/LF、移除 import/call，只改目前
  active marked block。
- 缺少 freeze：在正確 policy active 時，執行前一個 candidate 的
  `--freeze` 命令。Withheld 永遠不建立新 freeze。
- 後續 lab 的 policy/predecessor 錯誤：保持所需 freeze checkpoint active，
  不要把另一個 lab 的修改混入。
- Leo 匯入失敗：不要手改 result 或 replay JSON。保留錯誤訊息，改用對應的
  fallback pair 再匯入。
- Workbook 遺失：開啟保存的 export。若沒有保存檔，使用同一 scenario 重新
  開始，並把缺少的證據標為 incomplete。

## 7. Claim ceiling

本套件只宣稱固定 scenario 與明示 endpoint-energy 假設下的 deterministic、
coherent simulated data；固定 claim boundary 是：

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

本套件不宣稱執行 `GillesC/LoRaEnergySim`、live network 行為、部署系統量測，
或與上游實作 parity。
