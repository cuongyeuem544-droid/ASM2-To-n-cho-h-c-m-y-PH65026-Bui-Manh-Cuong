@echo off
setlocal enabledelayedexpansion

title H4CARE Multi-Warehouse & RBAC System Launcher

echo ===================================================================================
echo               H4CARE / PHARMATRUST - KHOI DONG TOAN BO HE THONG (WINDOWS)
echo ===================================================================================
echo   [1] Cua Hang Truc Tuyen (Khach Hang):     http://localhost:3000
echo   [2] Cong Quan Tri Vien & Quan Ly Kho:      http://localhost:5173
echo   [3] Backend API Documentation (Swagger):   http://localhost:8000/docs
echo ===================================================================================
echo.

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: 1. Kiem tra phien ban Python va Node.js
echo [1/8] Kiem tra phien ban moi truong...
if not exist ".venv\Scripts\python.exe" (
    echo [CANH BAO] Dang tao moi truong ao Python .venv...
    python -m venv .venv
)

.venv\Scripts\python.exe -c "import sys; print(f'  - Python: {sys.version.split()[0]}')"
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [LOI] Khong tim thay Node.js trong PATH! Vui long cai dat Node.js 20+.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node -v') do echo   - Node.js: %%v

:: 2. Kich hoat moi truong .venv
echo.
echo [2/8] Kich hoat moi truong ao .venv...
call .venv\Scripts\activate.bat

:: 3. Kiem tra dependencies
echo.
echo [3/8] Kiem tra dependencies backend va frontend...
if not exist ".venv\Scripts\alembic.exe" (
    echo   - Dang cai dat dependencies backend...
    pip install -r apps\api\requirements.txt
)

if not exist "apps\storefront\node_modules" (
    echo   - Dang cai dat dependencies Storefront (npm install)...
    cd /d "%ROOT%apps\storefront"
    call npm install
    cd /d "%ROOT%"
)

if not exist "apps\web\node_modules" (
    echo   - Dang cai dat dependencies Admin Web (npm install)...
    cd /d "%ROOT%apps\web"
    call npm install
    cd /d "%ROOT%"
)

:: 4. Chay migration Alembic truoc khi seed va mo API
echo.
echo [4/8] Chay Alembic Database Migrations (upgrade head)...
set PYTHONPATH=%ROOT%apps\api
.venv\Scripts\alembic.exe -c apps\api\alembic.ini upgrade head
if %ERRORLEVEL% neq 0 (
    echo [LOI] Alembic Migration that bai! Vui long kiem tra database pharmatrust.db
    pause
    exit /b 1
)

:: Dong bo schema bo sung an toan
.venv\Scripts\python.exe apps\api\app\db\migrate_schema.py

:: 5. Seed du lieu demo idempotent (bao gom >= 20 kho duoc pham toan quoc)
echo.
echo [5/8] Khoi tao du lieu demo idempotent va he thong 20+ kho toan quoc...
set DEMO_MODE=true
.venv\Scripts\python.exe apps\api\scripts\seed_demo_data.py
if %ERRORLEVEL% neq 0 (
    echo [CANH BAO] Co canh bao khi seed du lieu demo.
)

:: 6. Khoi dong Backend tai cong 8000
echo.
echo [6/8] Khoi dong Backend FastAPI tai cong 8000...
start "PharmaTrust Backend :8000" cmd /k "cd /d "%ROOT%" && call .venv\Scripts\activate.bat && set PYTHONPATH=%ROOT%apps\api && python -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000"

:: 7. Khoi dong Admin Web (Vite) tai cong 5173
echo.
echo [7/8] Khoi dong Admin Web Portal tai cong 5173...
start "PharmaTrust Admin Web :5173" cmd /k "cd /d "%ROOT%apps\web" && npm run dev -- --host 0.0.0.0 --port 5173"

:: 8. Khoi dong Storefront (Next.js) tai cong 3000
echo.
echo [8/8] Khoi dong Storefront Next.js tai cong 3000...
start "PharmaTrust Storefront :3000" cmd /k "cd /d "%ROOT%apps\storefront" && set NEXT_PUBLIC_DEMO_MODE=true && npm run dev -- -p 3000"

timeout /t 3 /nobreak >nul

echo.
echo ===================================================================================
echo                      HE THONG H4CARE DA SAN SANG HOAT DONG!
echo ===================================================================================
echo   1. Giao Dien Mua Thuoc Khach Hang: http://localhost:3000
echo   2. Cong Quan Tri / Quan Ly Kho:    http://localhost:5173
echo   3. Tai Lieu API Swagger Backend:   http://localhost:8000/docs
echo -----------------------------------------------------------------------------------
echo   TAI KHOAN DANG NHAP HE THONG (Password chung: xem ben duoi):
echo   * Quan Tri Toan Quyen (Admin):      admin@pharmatrust.vn         / Admin@2026
echo   * Chuyen Vien Du Lieu (Reviewer):   reviewer@pharmatrust.vn      / Reviewer@2026
echo   * Quan Ly Kho HCM (Manager):        manager.hcm@pharmatrust.vn   / Warehouse@2026
echo   * Quan Ly Kho Ha Noi (Manager):     manager.hn@pharmatrust.vn    / Warehouse@2026
echo   * Nhan Vien Kho HCM (Staff):        staff.hcm@pharmatrust.vn     / Staff@2026
echo   * Khach Hang Mua Thuoc (Buyer):     buyer@pharmatrust.vn         / Buyer@2026
echo ===================================================================================
echo Ba cua so Command Prompt da duoc mo de luu giu va theo doi log truc tiep.
echo Nhan phim bat ky de mo trinh duyet...
pause >nul

start http://localhost:3000
start http://localhost:5173
