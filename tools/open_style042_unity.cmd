@echo off
set "STYLE042_PROJECT=%~dp0..\adapters\unity\style042_project"
set "STYLE042_EDITOR=%~1"
if not defined STYLE042_EDITOR set "STYLE042_EDITOR=%UNITY_EDITOR%"
if not defined STYLE042_EDITOR set "STYLE042_EDITOR=D:\Unity\6000.3.24f1\Editor\Unity.exe"
if not exist "%STYLE042_EDITOR%" (
  echo Unity was not found. Add the style042_project folder in Unity Hub.
  echo Or pass the full Unity.exe path as the first argument to this file.
  pause
  exit /b 1
)
start "" "%STYLE042_EDITOR%" -projectPath "%STYLE042_PROJECT%" -executeMethod WorldBuilder042Builder.OpenAPI
