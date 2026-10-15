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
Write-Host "  [1] Web Ban Hang Khach Hang:    http://localhost:3000" -ForegroundColor Yellow
Write-Host "  [2] Admin Portal (Storefront):  http://localhost:3000/admin" -ForegroundColor Yellow
Write-Host "  [3] Admin Doc Lap:              http://localhost:8000" -ForegroundColor Yellow
Write-Host "  [4] API Documentation (Swagger):http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Kiem tra Python 3.11/3.12 va Node.js 20+
Write-Host "[1/7] Kiem tra phien ban moi truong (Python 3.11+ & Node.js 20+)..." -ForegroundColor White

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
Write-Host "[2/7] Kich hoat moi truong Python .venv..." -ForegroundColor White
$env:VIRTUAL_ENV = "$PSScriptRoot\.venv"
$env:PATH = "$PSScriptRoot\.venv\Scripts;$env:PATH"

# 3. Kiem tra dependencies
Write-Host "[3/7] Kiem tra dependencies..." -ForegroundColor White
$alembicExe = "$PSScriptRoot\.venv\Scripts\alembic.exe"
if (-not (Test-Path $alembicExe)) {
    Write-Host "  -> Dang cai dat dependencies backend..." -ForegroundColor Yellow
    & "$venvPython" -m pip install -r "$PSScriptRoot\apps\api\requirements.txt"
}
if (-not (Test-Path "$PSScriptRoot\apps\storefront\node_modules")) {
    Write-Host "  -> Dang cai dat dependencies storefront (npm install)..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\apps\storefront"
    & npm install
    Pop-Location
}

# 4. Chay Migration Alembic
Write-Host "[4/7] Chay Alembic Database Migrations (upgrade head)..." -ForegroundColor White
$env:PYTHONPATH = "$PSScriptRoot\apps\api"
& "$alembicExe" -c "$PSScriptRoot\apps\api\alembic.ini" upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Error "[LOI] Migration that bai! Vui long kiem tra file CSDL pharmatrust.db."
    exit 1
}

# 5. Seed du lieu Demo Idempotent (neu bat DEMO_MODE hoac CSDL chua co san pham)
Write-Host "[5/7] Kiem tra va khoi tao du lieu mau (Demo Seeder)..." -ForegroundColor White
if (-not $SkipSeed) {
    $env:DEMO_MODE = "true"
    & "$venvPython" "$PSScriptRoot\apps\api\scripts\seed_demo_data.py"
}

# 6. Chay Backend API tai cong 8000
Write-Host "[6/7] Khoi dong Backend FastAPI tai cong 8000..." -ForegroundColor White
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title PharmaTrust Backend :8000 && cd /d `"$PSScriptRoot`" && `"$venvPython`" -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000"

# 7. Chay Frontend Storefront tai cong 3000
Write-Host "[7/7] Khoi dong Storefront Next.js tai cong 3000..." -ForegroundColor White
Start-Process -FilePath "cmd.exe" -ArgumentList "/k title PharmaTrust Storefront :3000 && cd /d `"$PSScriptRoot\apps\storefront`" && set NEXT_PUBLIC_DEMO_MODE=true && npm run dev -- -p 3000"

Start-Sleep -Seconds 3
if (-not $Headless) {
    Start-Process "http://localhost:3000"
}

Write-Host "`n[HOAN TAT] He thong da khoi dong thanh cong tren Windows!" -ForegroundColor Green
Write-Host "Log duoc hien thi rieng biet tai 2 cua so Command Prompt de khong bi nuot log." -ForegroundColor Gray
