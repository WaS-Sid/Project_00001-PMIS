@echo off
REM Double-click this file to launch the PMIS starter (will open a new PowerShell window)
set SCRIPT_DIR=%~dp0scripts
set START_SCRIPT=%SCRIPT_DIR%\start_stack.ps1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy Bypass','-File','%START_SCRIPT%'"
