$ErrorActionPreference = 'Stop'
$lumioRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$lumioListeners = Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue
foreach ($lumioListener in $lumioListeners) {
    $lumioProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($lumioListener.OwningProcess)"
    $lumioParent = Get-CimInstance Win32_Process -Filter "ProcessId = $($lumioProcess.ParentProcessId)"
    $lumioOwnCommand = $lumioProcess.CommandLine -and $lumioProcess.CommandLine.Contains($lumioRoot) -and $lumioProcess.CommandLine.Contains('server.py')
    # Windows venv launchers run a child with the bundled Python path. Verify
    # the launcher belongs to this exact checkout before stopping that child.
    $lumioExpectedLauncher = Join-Path $lumioRoot '.venv\Scripts\python.exe'
    $lumioTrustedLauncher = $lumioParent -and $lumioParent.ExecutablePath -eq $lumioExpectedLauncher -and $lumioParent.CommandLine.Contains('server.py') -and $lumioProcess.CommandLine.Contains('server.py')
    if ($lumioOwnCommand -or $lumioTrustedLauncher) {
        Stop-Process -Id $lumioProcess.ProcessId
        Write-Output 'Stopped the Lumio voice bridge.'
    } else {
        throw 'Port 8790 belongs to a different process; leaving it running.'
    }
}
if (-not $lumioListeners) { Write-Output 'Lumio is not running.' }
