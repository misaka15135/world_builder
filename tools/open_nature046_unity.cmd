@echo off
set "NATURE046_PROJECT=%~dp0..\adapters\unity\style042_project"
set "NATURE046_EDITOR=%~1"
if not defined NATURE046_EDITOR set "NATURE046_EDITOR=%UNITY_EDITOR%"
if not defined NATURE046_EDITOR set "NATURE046_EDITOR=D:\Unity\6000.3.24f1\Editor\Unity.exe"
if not exist "%NATURE046_PROJECT%\Assets\Generated\Nature046\ArcaneNature046.unity" (
  echo Nature046 has not been prepared. See docs/12_nature046_organic_map.md.
  pause
  exit /b 1
)
if not exist "%NATURE046_EDITOR%" (
  echo Add style042_project in Unity Hub, then open ArcaneNature046.unity.
  pause
  exit /b 1
)
start "" "%NATURE046_EDITOR%" -projectPath "%NATURE046_PROJECT%" -executeMethod WorldBuilderCityBuilder.OpenNature
