param([int]$Port = 7860)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv-offline\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Offline environment is not installed.' }
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:GRADIO_ANALYTICS_ENABLED = 'False'
# LumioSolutions Voice Studio on the local OmniVoice model, loopback only.
& $python (Join-Path $PSScriptRoot 'studio\server.py') --port $Port
