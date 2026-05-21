# Acid Talent — arranque local en Windows
# Uso: clic derecho > Ejecutar con PowerShell
#       o desde una terminal: powershell -ExecutionPolicy Bypass -File .\start-local.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Acid Talent — Deploy local" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# === 1) Validar entorno ===
function Test-Command($name) {
  return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

$hasDocker = Test-Command "docker"
$hasNpm = Test-Command "npm"
$hasNode = Test-Command "node"

if (-not $hasNpm -or -not $hasNode) {
  Write-Host "[X] Falta Node/npm. Instalalo desde https://nodejs.org/ (LTS)." -ForegroundColor Red
  Read-Host "Presioná Enter para salir"
  exit 1
}

Write-Host "[OK] Node $(node -v) / npm $(npm -v)" -ForegroundColor Green

# === 2) Crear backend/.env si no existe ===
$backendEnv = Join-Path $root "backend\.env"
if (-not (Test-Path $backendEnv)) {
  $exampleEnv = Join-Path $root ".env.example"
  if (Test-Path $exampleEnv) {
    Copy-Item $exampleEnv $backendEnv
    # Ajustar host de DB para que apunte al servicio docker
    (Get-Content $backendEnv) -replace "localhost:5432", "db:5432" | Set-Content $backendEnv
    Write-Host "[OK] backend/.env creado a partir de .env.example" -ForegroundColor Green
  } else {
    Write-Host "[!] No encontré .env.example, creando backend/.env mínimo." -ForegroundColor Yellow
    @"
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/acid_talent
JWT_SECRET=change-me-local
ACCESS_TOKEN_EXPIRE_MINUTES=480
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=no-reply@acidtalent.local
"@ | Set-Content $backendEnv
  }
}

# === 3) Levantar backend + db con docker-compose si está Docker ===
if ($hasDocker) {
  Write-Host ""
  Write-Host "[1/3] Levantando Postgres + Backend con Docker..." -ForegroundColor Cyan
  try {
    docker compose up -d db backend | Out-Host
  } catch {
    Write-Host "[X] Falló docker compose. Verificá que Docker Desktop esté corriendo." -ForegroundColor Red
    Read-Host "Presioná Enter para salir"
    exit 1
  }
  Write-Host "[OK] Backend en http://localhost:8000" -ForegroundColor Green
} else {
  Write-Host "[!] Docker no encontrado. Levantá el backend manualmente en localhost:8000." -ForegroundColor Yellow
  Write-Host "    Si no lo levantás, el frontend va a fallar al loguearse." -ForegroundColor Yellow
}

# === 4) Instalar deps del frontend si faltan ===
Write-Host ""
Write-Host "[2/3] Verificando dependencias del frontend..." -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend")
if (-not (Test-Path "node_modules")) {
  Write-Host "    Ejecutando npm install (puede tardar varios minutos la primera vez)..." -ForegroundColor Gray
  npm install | Out-Host
}
Write-Host "[OK] Dependencias listas" -ForegroundColor Green

# === 5) Arrancar Vite ===
Write-Host ""
Write-Host "[3/3] Arrancando Vite (frontend)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Abriendo http://localhost:5173" -ForegroundColor Green
Write-Host "  Para detener: Ctrl+C en esta ventana." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"
npm run dev
