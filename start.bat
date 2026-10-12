@echo off
setlocal enabledelayedexpansion

title PharmaTrust / H4CARE System Launcher

echo ======================================================================
echo          H4CARE / PHARMATRUST - KHOI DONG HE THONG (WINDOWS)
echo ======================================================================
echo   [1] Web Ban Hang Khach Hang:    http://localhost:3000
echo   [2] Admin Portal (Storefront):  http://localhost:3000/admin
echo   [3] Admin Doc Lap:              http://localhost:8000
echo   [4] API Documentation (Swagger):http://localhost:8000/docs
echo ======================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: 1. Kiem tra Python va Node.js
echo [1/7] Kiem tra phien ban moi truong...
if not exist ".venv\Scripts\python.exe" (
    echo [CANH BAO] Dang khoi tao moi truong ao .venv...
    python -m venv .venv
)

.venv\Scripts\python.exe -c "import sys; print(f'  - Python: {sys.version}')"
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [LOI] Khong tim thay Node.js trong PATH! Vui long cai dat Node.js 20+.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node -v') do echo   - Node.js: %%v

:: 2. Kich hoat moi truong .venv
echo [2/7] Kich hoat moi truong ao .venv...
call .venv\Scripts\activate.bat

:: 3. Kiem tra dependencies
echo [3/7] Kiem tra dependencies backend va frontend...
if not exist ".venv\Scripts\alembic.exe" (
    echo   - Dang cai dat dependencies backend...
    pip install -r apps\api\requirements.txt
)

if not exist "apps\storefront\node_modules" (
    echo   - Dang cai dat dependencies frontend (npm install)...
    cd /d "%ROOT%apps\storefront"
    call npm install
    cd /d "%ROOT%"
)

:: 4. Chay migration Alembic
echo [4/7] Chay Alembic Database Migrations (upgrade head)...
set PYTHONPATH=%ROOT%apps\api
.venv\Scripts\alembic.exe -c apps\api\alembic.ini upgrade head
if %ERRORLEVEL% neq 0 (
    echo [LOI] Migration that bai! Vui long kiem tra file pharmatrust.db
    pause
    exit /b 1
)

:: 5. Seed du lieu demo idempotent
echo [5/7] Seed du lieu demo idempotent...
set DEMO_MODE=true
.venv\Scripts\python.exe apps\api\scripts\seed_demo_data.py

:: 6. Chay Backend tai cong 8000
echo [6/7] Khoi dong Backend FastAPI tai cong 8000...
start "PharmaTrust Backend :8000" cmd /k "cd /d "%ROOT%" && call .venv\Scripts\activate.bat && set PYTHONPATH=%ROOT%apps\api && python -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000"

:: 7. Chay Frontend tai cong 3000
echo [7/7] Khoi dong Storefront Next.js tai cong 3000...
start "PharmaTrust Storefront :3000" cmd /k "cd /d "%ROOT%apps\storefront" && set NEXT_PUBLIC_DEMO_MODE=true && npm run dev -- -p 3000"

timeout /t 3 /nobreak >nul
start http://localhost:3000

echo.
echo [HOAN TAT] He thong dang hoat dong tai http://localhost:3000 va http://localhost:8000
echo Hai cua so Command Prompt da duoc mo de luu giu va theo doi log truc tiep.
pause
