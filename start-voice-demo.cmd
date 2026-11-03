@echo off
rem Runs start-voice-demo.ps1 without changing the system's script execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-voice-demo.ps1" %*
