param([switch]$Lan)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$lumioPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $lumioPython)) {
    throw 'Python environment missing. Install Python 3.12+, run: python -m venv .venv, then .venv\Scripts\python.exe -m pip install -r requirements.txt'
}
if ($Lan) { & $lumioPython server.py --lan } else { & $lumioPython server.py }
