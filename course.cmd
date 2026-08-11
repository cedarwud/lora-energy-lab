@echo off
setlocal
rem Recovery commands: status, restore --checkpoint <role>, reset-policy.
set "ROOT_DIR=%~dp0"
if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
  "%ROOT_DIR%.venv\Scripts\python.exe" "%ROOT_DIR%run_lab.py" %*
) else (
  py -3 "%ROOT_DIR%run_lab.py" %*
)
