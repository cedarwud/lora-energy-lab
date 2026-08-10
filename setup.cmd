@echo off
setlocal
set "ROOT_DIR=%~dp0"
if not defined PYTHON_BIN set "PYTHON_BIN=py -3.11"

rem Do not broaden this to py -3: the frozen result contract requires 3.11.x.
call %PYTHON_BIN% -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.11.x is unavailable through "%PYTHON_BIN%".
  call %PYTHON_BIN% --version 2>&1
  echo Install it explicitly, for example: uv python install 3.11
  echo Then set PYTHON_BIN to the path printed by: uv python find 3.11
  exit /b 2
)

if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
  "%ROOT_DIR%.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
  if errorlevel 1 (
    echo ERROR: existing %ROOT_DIR%.venv uses a Python version other than 3.11.x.
    echo Remove that venv deliberately, then rerun setup.cmd.
    exit /b 2
  )
) else (
  call %PYTHON_BIN% -m venv "%ROOT_DIR%.venv"
  if errorlevel 1 exit /b 2
)
"%ROOT_DIR%.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --require-hashes --no-deps -r "%ROOT_DIR%requirements-lock.txt"
if errorlevel 1 exit /b %errorlevel%
"%ROOT_DIR%.venv\Scripts\python.exe" "%ROOT_DIR%verify_setup.py"
