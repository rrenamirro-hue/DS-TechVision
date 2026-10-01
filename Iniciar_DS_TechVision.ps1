param([string]$LanIP, [switch]$UsbAdb)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path '.venv\Scripts\python.exe')) { py -3 -m venv .venv }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Fallo al instalar dependencias' }

$expected = @('imageRUNNER_1643iF_1643i_SM_r6_211104.pdf', 'imageRUNNER_1643iF_1643i_PC_r9_250929.pdf')
foreach ($filename in $expected) {
    if (-not (Test-Path (Join-Path 'data\manuals' $filename))) { throw "Falta data\manuals\$filename" }
}

if (-not $LanIP) {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -Type Unicast |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and ($_.IPAddress -like '10.*' -or $_.IPAddress -like '192.168.*' -or $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[01])\.') } |
        Sort-Object InterfaceMetric | Select-Object -First 1
    if (-not $candidate) { throw 'No se encontro una IPv4 privada. Ejecuta: .\Iniciar_DS_TechVision.ps1 -LanIP 192.168.x.x' }
    $LanIP = $candidate.IPAddress
}

& $python -m app.auth_setup
if ($LASTEXITCODE -ne 0) { throw 'Fallo al preparar autenticacion' }
& $python -m app.generate_tls --ip $LanIP
if ($LASTEXITCODE -ne 0) { throw 'Fallo al preparar HTTPS' }
& $python -m app.ingest
if ($LASTEXITCODE -ne 0) { throw 'Fallo la indexacion' }
& $python -m app.vision_ingest
if ($LASTEXITCODE -ne 0) { throw 'Fallo al preparar referencias visuales OEM' }
& $python -c "from app.continuous_vision import build_visual_index; result = build_visual_index(); print('VISUAL_INDEX_' + result['state'] + ': ' + str(len(result['reference_ids'])) + ' referencias / ' + str(result['embedding_dimension']) + ' dimensiones')"
if ($LASTEXITCODE -ne 0) { throw 'Fallo la indexacion visual' }

$secureRoot = Join-Path $env:LOCALAPPDATA 'DataSystems\DS_TechVision'
$certRoot = Join-Path $secureRoot 'certs'
$serverKey = Join-Path $certRoot 'server-key.pem'
$serverCert = Join-Path $certRoot 'server-cert.pem'
$caCert = Join-Path $certRoot 'ca-cert.cer'
$bindIP = $LanIP
$accessHost = $LanIP
if ($UsbAdb) {
    $adb = Get-Command adb -ErrorAction SilentlyContinue
    if (-not $adb) { throw 'ADB no esta disponible en PATH.' }
    & $adb.Source reverse tcp:8522 tcp:8522
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar adb reverse para el puerto 8522.' }
    $bindIP = '127.0.0.1'
    $accessHost = 'localhost'
}
Write-Host "DS TechVision: https://${accessHost}:8522" -ForegroundColor Cyan
Write-Host "CA para Android: $caCert" -ForegroundColor Cyan
Write-Host "Servidor enlazado solamente a $bindIP. No reenvies el puerto en el router." -ForegroundColor Yellow
& $python -m uvicorn app.main:app --host $bindIP --port 8522 --ssl-keyfile $serverKey --ssl-certfile $serverCert
