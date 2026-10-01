$ErrorActionPreference = 'Stop'
$adb = Get-Command adb -ErrorAction SilentlyContinue
if (-not $adb) { throw 'ADB no esta disponible en PATH. Instala Android Platform Tools.' }
& $adb.Source devices
if ($LASTEXITCODE -ne 0) { throw 'ADB no pudo enumerar dispositivos.' }
& $adb.Source reverse tcp:8522 tcp:8522
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear adb reverse tcp:8522.' }
Write-Host 'ADB reverse activo. En Chrome Android abre https://localhost:8522' -ForegroundColor Cyan
