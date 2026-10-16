@echo off
cd /d "%~dp0"
if exist "dist\WorldBuilder048\WorldBuilder048.exe" (
  start "" "dist\WorldBuilder048\WorldBuilder048.exe"
  exit /b 0
)
if exist "dist\WorldBuilder047v2\WorldBuilder047v2.exe" (
  start "" "dist\WorldBuilder047v2\WorldBuilder047v2.exe"
  exit /b 0
)
if exist ".venv-desktop\Scripts\pythonw.exe" (
  start "" ".venv-desktop\Scripts\pythonw.exe" "tools\run_desktop.py"
  exit /b 0
)
echo Build the client first: .venv-desktop\Scripts\python.exe tools\build_desktop.py --name WorldBuilder048
pause
