# Acid Talent — detener servicios locales
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Deteniendo contenedores..." -ForegroundColor Yellow
docker compose down
Write-Host "Listo." -ForegroundColor Green
Start-Sleep -Seconds 1
