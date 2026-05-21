@echo off
REM Acid Talent - arranque local
REM Doble-click para ejecutar

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -NoExit -File ".\start-local.ps1"
