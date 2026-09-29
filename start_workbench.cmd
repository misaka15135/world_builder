@echo off
cd /d "%~dp0"
python tools\run_workbench.py --open
if errorlevel 1 pause
