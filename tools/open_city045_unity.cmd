@echo off
set "CITY045_PROJECT=%~dp0..\adapters\unity\style042_project"
set "CITY045_EDITOR=%~1"
if not defined CITY045_EDITOR set "CITY045_EDITOR=%UNITY_EDITOR%"
if not defined CITY045_EDITOR set "CITY045_EDITOR=D:\Unity\6000.3.24f1\Editor\Unity.exe"
if not exist "%CITY045_PROJECT%\Assets\Generated\City\ArcaneCity.unity" (
  echo The city scene has not been prepared in this checkout.
  echo See docs/11_city045_arcane_map.md for generation and preparation.
  pause
  exit /b 1
)
if not exist "%CITY045_EDITOR%" (
  echo Add the style042_project folder in Unity Hub, then open ArcaneCity.unity.
  echo Or pass the full Unity.exe path as the first argument.
  pause
  exit /b 1
)
start "" "%CITY045_EDITOR%" -projectPath "%CITY045_PROJECT%" -executeMethod WorldBuilderCityBuilder.Open
