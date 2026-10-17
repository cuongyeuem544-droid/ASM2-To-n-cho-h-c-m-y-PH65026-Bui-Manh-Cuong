# PharmaTrust Unified Ecosystem Launcher for Windows
# Powershell Execution Script
[CmdletBinding()]
param(
    [switch]$SkipSeed,
    [switch]$Headless
)

$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "         H4CARE / PHARMATRUST - KHOI DONG HE THONG (WINDOWS)" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  [1] Web Ban Hang Khach Hang:       http://localhost:3000" -ForegroundColor Yellow
Write-Host "  [2] Cong Quan Tri Vien & Kho (Web): http://localhost:5173" -ForegroundColor Yellow
Write-Host "  [3] API Documentation (Swagger):   http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "  [4] API Health Check:              http://localhost:8000/api/v1/health" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Kiem tra Python 3.11/3.12 va Node.js 20+
Write-Host "[1/9] Kiem tra phien ban moi truong (Python 3.11+ & Node.js 20+)..." -ForegroundColor White

$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[CANH BAO] Chua tim thay .venv tai $venvPython. Dang kiem tra python he thong..." -ForegroundColor Yellow
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sysPy) {
        Write-Error "[LOI] Khong tim thay Python! Vui long cai dat Python 3.11 hoac 3.12."
        exit 1
    }
    & python -m venv "$PSScriptRoot\.venv"
}

$pyVer = & "$venvPython" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  -> Python version: $pyVer (Yeu cau: 3.11 hoac 3.12)" -ForegroundColor Gray

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Error "[LOI] Khong tim thay Node.js! Vui long cai dat Node.js version 20+."
    exit 1
}
$nodeVer = & node -v
Write-Host "  -> Node.js version: $nodeVer (Yeu cau: 20+)" -ForegroundColor Gray

# 2. Kich hoat moi truong ao .venv
Write-Host "[2/9] Kich hoat moi truong Python .venv..." -ForegroundColor White
$env:VIRTUAL_ENV = "$PSScriptRoot\.venv"
$env:PATH = "$PSScriptRoot\.venv\Scripts;$env:PATH"

# 3. Kiem tra file .env tu .env.example neu chua ton tai
Write-Host "[3/9] Kiem tra tap tin moi truong .env..." -ForegroundColor White
if (-not (Test-Path "$PSScriptRoot\.env")) {
    Write-Host "  -> Chua tim thay .env. Dang tao tu .env.example..." -ForegroundColor Yellow
    Copy-Item "$PSScriptRoot\.env.example" "$PSScriptRoot\.env"
}

# 4. Kiem tra dependencies
Write-Host "[4/9] Kiem tra dependencies backend va frontend..." -ForegroundColor White
$hasPkg = & "$venvPython" -c "import alembic, fastapi, sqlalchemy, pydantic_settings; print(1)" 2>$null
if ($hasPkg -ne "1") {
    Write-Host "  -> Phat hien thieu goi backend hoac moi truong moi. Dang cai dat qua pip..." -ForegroundColor Yellow
    & "$venvPython" -m pip install -r "$PSScriptRoot\apps\api\requirements.txt"
}
if (-not (Test-Path "$PSScriptRoot\apps\storefront\node_modules")) {
    Write-Host "  -> Dang cai dat dependencies storefront (npm install)..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\apps\storefront"
    & npm install
    Pop-Location
}
if (-not (Test-Path "$PSScriptRoot\apps\web\node_modules")) {
    Write-Host "  -> Dang cai dat dependencies web admin (npm install)..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\apps\web"
    & npm install
    Pop-Location
}

# 5. Chay Migration Alembic va kiem tra single head
Write-Host "[5/9] Chay Alembic Database Migrations (upgrade head)..." -ForegroundColor White
$env:PYTHONPATH = "$PSScriptRoot\apps\api"
& "$venvPython" "$PSScriptRoot\apps\api\scripts\run_migrations.py"
if ($LASTEXITCODE -ne 0) {
    Write-Error "[LOI] Migration that bai! Vui long kiem tra file CSDL pharmatrust.db."
    exit 1
}

# 6. Chay dong bo schema an toan va Seed du lieu Demo Idempotent
Write-Host "[6/9] Dong bo schema SQLite va Seeder du lieu demo..." -ForegroundColor White
& "$venvPython" "$PSScriptRoot\apps\api\app\db\migrate_schema.py"
if (-not $SkipSeed) {
    $env:DEMO_MODE = "true"
    & "$venvPython" "$PSScriptRoot\apps\api\scripts\seed_demo_data.py"
}

# 7. Chay Backend API tai cong 8000
Write-Host "[7/9] Khoi dong Backend FastAPI tai cong 8000..." -ForegroundColor White
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title PharmaTrust Backend :8000 && cd /d `"$PSScriptRoot`" && call .venv\Scripts\activate.bat && set PYTHONPATH=$PSScriptRoot\apps\api && `"$venvPython`" -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000"

# 8. Cho Backend Health Check san sang
Write-Host "[8/9] Cho Backend Health Check phan hoi (GET http://127.0.0.1:8000/api/v1/health)..." -ForegroundColor White
$backendReady = $false
for ($i = 0; $i -lt 35; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $backendReady = $true
            Write-Host "  -> [OK] Backend FastAPI da san sang va ket noi CSDL tot!" -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $backendReady) {
    Write-Error "[LOI] Backend khong phan hoi tren http://127.0.0.1:8000/api/v1/health sau 35 giay!"
    exit 1
}

# 9. Khoi dong Frontends (Admin Web tren 5173 va Storefront tren 3000)
Write-Host "[9/9] Khoi dong Admin Web (5173) va Storefront Next.js (3000)..." -ForegroundColor White
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title PharmaTrust Admin Web :5173 && cd /d `"$PSScriptRoot\apps\web`" && npm run dev -- --host 0.0.0.0 --port 5173"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title PharmaTrust Storefront :3000 && cd /d `"$PSScriptRoot\apps\storefront`" && set NEXT_PUBLIC_DEMO_MODE=true && npm run dev -- -p 3000"

Start-Sleep -Seconds 3
if (-not $Headless) {
    try {
        Start-Process "chrome.exe" "http://localhost:3000" -ErrorAction Stop
        Start-Process "chrome.exe" "http://localhost:5173" -ErrorAction Stop
    } catch {
        Start-Process "http://localhost:3000"
        Start-Process "http://localhost:5173"
    }
}

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "         HE THONG H4CARE DA KHOI DONG THANH CONG TREN WINDOWS!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  - Storefront:      http://localhost:3000" -ForegroundColor White
Write-Host "  - Admin Portal:    http://localhost:5173" -ForegroundColor White
Write-Host "  - Swagger API:     http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Health Check:    http://localhost:8000/api/v1/health" -ForegroundColor White
Write-Host "----------------------------------------------------------------------" -ForegroundColor Gray
Write-Host "  TAI KHOAN DEMO CHUAN:" -ForegroundColor White
Write-Host "  * Admin:           admin@pharmatrust.vn       / Admin@123456" -ForegroundColor Cyan
Write-Host "  * QL Kho HCM:      manager.hcm@pharmatrust.vn / Warehouse@2026" -ForegroundColor Cyan
Write-Host "  * NV Kho HCM:      staff.hcm@pharmatrust.vn   / Staff@2026" -ForegroundColor Cyan
Write-Host "  * QL Kho HN:       manager.hn@pharmatrust.vn  / Warehouse@2026" -ForegroundColor Cyan
Write-Host "  * NV Kho HN:       staff.hn@pharmatrust.vn    / Staff@2026" -ForegroundColor Cyan
Write-Host "  * Khach Hang:      buyer@pharmatrust.vn       / Buyer@123456" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Log duoc hien thi rieng biet tai 3 cua so Command Prompt de khong bi nuot log." -ForegroundColor Gray
