# LoRaEnergySim 能源決策實驗

本目錄是獨立封裝的 LoRaEnergySim 教學 runner，固定使用一個 scenario，提供
「編輯 → 執行 → 檢查 → 匯入」的 bounded 流程。Runner 是
`coherent-course-simulated-adapter` 產生的 deterministic 教學模擬資料；不會
執行上游研究 repository。

每個 result 與 replay 的精確 claim boundary 是：

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

Endpoint energy 只代表本套件宣告的 endpoint radio/processing 假設，不是部署
系統的量測。provenance 中的上游 repository/commit 只是教學參考識別，不表示
runner 實際執行上游程式。

## 0. 從 GitHub Releases 下載

在老師指定的 GitHub Releases 頁面下載這兩個同名資產；不要下載 GitHub 自動
產生的 `Source code (zip)`：

```text
lora-energy-lab-v1.zip
lora-energy-lab-v1.zip.sha256
```

先核對 checksum，再解壓縮。Linux：

```sh
sha256sum -c lora-energy-lab-v1.zip.sha256
unzip lora-energy-lab-v1.zip
cd lora-energy-lab
```

macOS 可用 `shasum -a 256 lora-energy-lab-v1.zip`，並與 `.sha256` 檔第一欄
逐字比對。Windows PowerShell：

```powershell
Get-FileHash .\lora-energy-lab-v1.zip -Algorithm SHA256
Expand-Archive .\lora-energy-lab-v1.zip -DestinationPath .
Set-Location .\lora-energy-lab
```

將 `Get-FileHash` 顯示的 hash 與 `.sha256` 第一欄比對。ZIP 內只有一個
`lora-energy-lab/` 根目錄；`.venv` 與先前學生的執行 artifacts 不會包在
下載檔內。

## 1. 進入目錄並設定 Python

以下命令都在解壓後的 `lora-energy-lab/` 執行。

Frozen result contract 要求 Python 3.11.x。Linux/macOS：

```sh
PYTHON_BIN=python3.11 bash setup.sh
bash course.sh verify
```

`setup.sh` 建立本地 `.venv`、檢查 standard-library lock file，並執行與
course launcher 相同的 verify。設定完成後，`course.sh` 會優先使用
`.venv/bin/python`。

Windows Command Prompt：

```bat
set "PYTHON_BIN=py -3.11"
setup.cmd
course.cmd verify
```

verify 成功會寫入 `artifacts/verify-receipt.json`。若主機不是 Python 3.11.x，
必須停在明確的版本 gate；不要修改 runner 放寬 gate。請安裝 Python 3.11，或
改用下方的同 scenario fallback。

若尚未安裝 Python 3.11，setup 不會自動下載。快速且明確的 uv recovery：

```sh
uv python install 3.11
PYTHON_BIN="$(uv python find 3.11)" bash setup.sh
bash course.sh verify
```

Windows 先執行 `uv python install 3.11`，再執行 `uv python find 3.11`，將
`PYTHON_BIN` 設成輸出的 interpreter path（路徑含空格時保留變數中的引號），
然後重跑 `setup.cmd`。Setup 會驗證
選定的 interpreter 與產生的 `.venv` 都是 Python 3.11.x，不會靜默接受 3.12 或
3.13。

若 setup 回報既有 `.venv` 使用其他 Python 版本，只刪除這個 package-local
venv 後重跑（Linux/macOS：`rm -rf .venv`；Windows：`rmdir /s /q .venv`）。
Setup 不會自動刪除既有 venv。

檢查 CLI 語法：

```sh
bash course.sh --help
bash course.sh run --help
```

`_make-fallbacks` 是 package 維護命令，不是學生操作。

## 2. 只修改標記的 policy 區域

只編輯 `student_policy.py`，而且只可在以下三組 markers 中修改：

- `lab-a-pace-rest`
- `lab-b-enter-exit-hold`
- `lab-c-batch-urgent`

一般學習操作是在目前 lab 的 marked block 內改 policy constants。不要修改
scenario、runner、schemas、artifacts 或其他 policy 程式。Guard 也會拒絕
import、任意 function call、不支援的 AST 語法、BOM/CRLF，以及不在
`WAIT`、`SLEEP`、`SEND_ONE`、`SEND_URGENT`、`FLUSH_BATCH` 中的 action。

`student_policy.baseline.py` 是封裝的 reference。每次執行前，先在 Leo
workbook 記錄 queue/service、packet/retry、state duration 或 endpoint-energy
的 prediction，讓結果可以確認或反駁因果假設。

## 3. 依序執行十個 exact cases

每次成功的 command 都會印出包含 result path 的 JSON。student-run 檔案位於：

```text
artifacts/<run_id>/result.json
artifacts/<run_id>/endpoint-replay.json
```

`<run_id>` 目錄名稱會把 `:` 換成 `_`；請使用 command 印出的
`result_path`，不要自行猜路徑。freeze 另外會在 `artifacts/receipts/` 與
`artifacts/checkpoints/` 寫入 receipt 和 policy checkpoint。

依下列順序執行。baseline、C candidate、以及 withheld command 都不要加
`--freeze`。

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

不要把 fallback 改稱為 student run。Static fallback 已按 exact case 配對，
保留 `artifact_source: same-scenario-fallback`、同一 scenario identity、
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
identity、policy lineage 和 receipt hashes。Fallback 是同 scenario 的教學
recovery 路徑，不表示你的本地 policy 曾執行。

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

- setup 或 verify 失敗：確認 interpreter 是 Python 3.11.x，重跑對應 OS 的
  setup，再重跑 `course.sh verify`/`course.cmd verify`。環境仍不可用時，使用
  對應 fallback。
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
coherent simulated teaching data：

`SIMULATED TEACHING DATA / NOT LIVE / NOT MEASURED / NOT CANONICAL-PARITY-VERIFIED`

本套件不宣稱執行 `GillesC/LoRaEnergySim`、live network 行為、部署系統量測，
或與上游實作 parity。
