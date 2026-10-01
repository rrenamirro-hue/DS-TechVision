param([Parameter(Mandatory = $true)][string]$LanIP)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Ejecuta primero Iniciar_DS_TechVision.ps1 para crear el entorno.' }
& $python -m app.generate_tls --ip $LanIP
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el certificado HTTPS.' }
$ca = Join-Path $env:LOCALAPPDATA 'DataSystems\DS_TechVision\certs\ca-cert.cer'
Write-Host "Certificado CA para instalar en Android: $ca" -ForegroundColor Cyan
Write-Host 'No se solicito ni almaceno ninguna contraseña en PowerShell.' -ForegroundColor Green
