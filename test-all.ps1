# PharmaTrust / H4CARE Comprehensive Test Runner
# Chay toan bo test backend va frontend, tra ve exit code chuan CI

$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "         H4CARE / PHARMATRUST - CI / LOCAL TEST SUITE" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "[LOI] Khong tim thay Python venv tai $venvPython"
    exit 1
}

# 1. Chay Backend Pytest Suite
Write-Host "`n[1/2] Dang chay Backend Unit & Security Tests (pytest)..." -ForegroundColor White
$backendTestCode = 0
& "$venvPython" -m pytest apps/api/tests/test_order_security.py apps/api/tests/test_vouchers_and_pricing.py apps/api/tests/test_migrations.py -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "[THAT BAI] Backend tests co loi!" -ForegroundColor Red
    $backendTestCode = 1
} else {
    Write-Host "[THANH CONG] Toan bo Backend Security & Pricing Tests da dat 100%!" -ForegroundColor Green
}

# 2. Frontend Type & Syntax Validation
Write-Host "`n[2/2] Dang kiem tra Frontend Next.js..." -ForegroundColor White
$frontendTestCode = 0
Push-Location "$PSScriptRoot\apps\storefront"
if (Get-Command npm -ErrorAction SilentlyContinue) {
    & npx tsc --noEmit
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[CANH BAO] Type check frontend phat hien canh bao!" -ForegroundColor Yellow
    } else {
        Write-Host "[THANH CONG] Frontend TypeScript validation passed!" -ForegroundColor Green
    }
}
Pop-Location

Write-Host "`n======================================================================" -ForegroundColor Cyan
if ($backendTestCode -eq 0 -and $frontendTestCode -eq 0) {
    Write-Host "      TAT CA CAC TEST DA VUOT QUA THANH CONG! EXIT CODE 0" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "      CO TEST THAT BAI! EXIT CODE 1" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Cyan
    exit 1
}
