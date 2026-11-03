param([switch]$Lan)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$lumioPython = Join-Path $PSScriptRoot '.venv-offline\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $lumioPython)) { throw 'Offline environment is not installed.' }
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:GRADIO_ANALYTICS_ENABLED = 'False'
if ($Lan) { & $lumioPython server.py --offline --lan } else { & $lumioPython server.py --offline }
