@echo off
setlocal enabledelayedexpansion

title H4CARE / PharmaTrust - Windows Ecosystem Launcher

:: ===================================================================================
::  H4CARE / PHARMATRUST - SCRIPT KHOI DONG HE THONG TOAN DIEN TREN WINDOWS
:: ===================================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "FORCE_SEED=0"
if "%~1"=="--seed" set "FORCE_SEED=1"
if "%~1"=="--reset" set "FORCE_SEED=1"
if "%~1"=="-s" set "FORCE_SEED=1"

set "IS_FIRST_RUN=0"
if not exist "pharmatrust.db" set "IS_FIRST_RUN=1"
if "!FORCE_SEED!"=="1" set "IS_FIRST_RUN=1"

echo ===================================================================================
if "!IS_FIRST_RUN!"=="1" (
    echo        H4CARE / PHARMATRUST - KHOI TAO CSDL LAN DAU TIEN / SEED DU LIEU
) else (
    echo        H4CARE / PHARMATRUST - KHOI DONG TOC DO CAO - FAST LAUNCH ~2-3s
)
echo ===================================================================================
echo   [1] Cua Hang Truc Tuyen - Storefront:       http://localhost:3000
echo   [2] Cong Quan Tri Vien va Quan Ly Kho:      http://localhost:5173
echo   [3] Backend API Documentation Swagger:      http://localhost:8000/docs
echo   [4] Backend Health Check:                   http://localhost:8000/api/v1/health
echo ===================================================================================
echo.

:: 1. Chuyen ve thu muc goc du an
echo [1/16] Thu muc goc du an: %ROOT%

:: 2. Kiem tra Python 3.11, 3.12 hoac 3.13 va tao .venv neu chua ton tai
echo [2/16] Kiem tra phien ban Python - Yeu cau: 3.11, 3.12 hoac 3.13...
if not exist ".venv\Scripts\python.exe" (
    echo   - Chua tim thay moi truong ao .venv. Dang kiem tra Python he thong...
    set "SYSTEM_PY="
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        python -c "import sys; sys.exit(0 if (sys.version_info.major == 3 and sys.version_info.minor in (11, 12, 13)) else 1)" >nul 2>nul
        if !errorlevel! equ 0 (
            set "SYSTEM_PY=python"
        )
    )
    if not defined SYSTEM_PY (
        where py >nul 2>nul
        if !errorlevel! equ 0 (
            py -3.13 -c "import sys; sys.exit(0)" >nul 2>nul
            if !errorlevel! equ 0 (
                set "SYSTEM_PY=py -3.13"
            ) else (
                py -3.12 -c "import sys; sys.exit(0)" >nul 2>nul
                if !errorlevel! equ 0 (
                    set "SYSTEM_PY=py -3.12"
                ) else (
                    py -3.11 -c "import sys; sys.exit(0)" >nul 2>nul
                    if !errorlevel! equ 0 (
                        set "SYSTEM_PY=py -3.11"
                    )
                )
            )
        )
    )
    if not defined SYSTEM_PY (
        call :error_exit "2" "Kiem tra Python" "Yeu cau Python 3.11, 3.12 hoac 3.13 tren may"
    )
    echo   - Dang tao moi truong ao .venv...
    !SYSTEM_PY! -m venv .venv
    if !errorlevel! neq 0 (
        call :error_exit "2" "Khoi tao .venv" "Tao moi truong ao that bai"
    )
)

.venv\Scripts\python.exe -c "import sys; v = sys.version_info; sys.exit(0 if (v.major == 3 and v.minor in (11, 12, 13)) else 1)" >nul 2>nul
if !errorlevel! neq 0 (
    call :error_exit "2" "Kiem tra Python trong .venv" "Moi truong .venv hien tai khong phai Python 3.11, 3.12 hoac 3.13"
)
for /f "delims=" %%v in ('.venv\Scripts\python.exe -c "import sys; print(f'Python {sys.version.split()[0]}')"') do echo   - Phien ban Python hop le: %%v

:: 3. Kiem tra Node.js 20 tro len
echo.
echo [3/16] Kiem tra phien ban Node.js - Yeu cau: 20 tro len...
where node >nul 2>nul
if !errorlevel! neq 0 (
    call :error_exit "3" "Kiem tra Node.js" "Khong tim thay Node.js trong bien moi truong PATH"
)
node -e "const v = parseInt(process.versions.node.split('.')[0], 10); if (isNaN(v) || v < 20) process.exit(1);" >nul 2>nul
if !errorlevel! neq 0 (
    call :error_exit "3" "Kiem tra Node.js" "Yeu cau Node.js 20 tro len"
)
for /f "delims=" %%v in ('node -v') do echo   - Phien ban Node.js hop le: %%v

:: 4. Kich hoat moi truong ao
echo.
echo [4/16] Kich hoat moi truong ao .venv...
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    call :error_exit "4" "Kich hoat .venv" "call .venv\Scripts\activate.bat"
)

:: 5. Cai dat hoac cap nhat requirements backend
echo.
echo [5/16] Kiem tra va cai dat dependencies Backend...
.venv\Scripts\python.exe -c "import alembic, fastapi, sqlalchemy, pydantic_settings, uvicorn" >nul 2>nul
if !errorlevel! neq 0 (
    echo   - Phat hien thieu goi backend hoac moi truong moi. Dang cai dat qua pip...
    .venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
    if !errorlevel! neq 0 (
        call :error_exit "5" "Cai dat dependencies Backend" "pip install requirements.txt that bai"
    )
) else (
    echo   - Dependencies Backend da san sang.
)

:: 6. Cai dependencies cho apps/storefront va apps/web
echo.
echo [6/16] Kiem tra va cai dat dependencies Frontend Storefront va Admin Web...
if not exist "apps\storefront\node_modules" (
    echo   - Dang cai dat dependencies apps\storefront...
    cd /d "%ROOT%apps\storefront"
    call npm install
    if !errorlevel! neq 0 (
        cd /d "%ROOT%"
        call :error_exit "6" "Cai dat dependencies apps\storefront" "npm install tai apps\storefront that bai"
    )
    cd /d "%ROOT%"
) else (
    echo   - Dependencies apps\storefront da ton tai.
)

if not exist "apps\web\node_modules" (
    echo   - Dang cai dat dependencies apps\web...
    cd /d "%ROOT%apps\web"
    call npm install
    if !errorlevel! neq 0 (
        cd /d "%ROOT%"
        call :error_exit "6" "Cai dat dependencies apps\web" "npm install tai apps\web that bai"
    )
    cd /d "%ROOT%"
) else (
    echo   - Dependencies apps\web da ton tai.
)

:: 7. Tao .env tu .env.example neu chua ton tai (khong ghi de)
echo.
echo [7/16] Kiem tra tep cau hinh moi truong .env...
if not exist ".env" (
    echo   - Chua co tep .env. Dang tao .env tu .env.example...
    copy ".env.example" ".env" >nul
    if !errorlevel! neq 0 (
        call :error_exit "7" "Khoi tao .env" "copy .env.example .env that bai"
    )
    echo   - Da tao .env thanh cong tu .env.example.
) else (
    echo   - Tep .env da ton tai - giu nguyen, khong ghi de.
)

:: 8. Kiem tra trang thai va giai phong cac cong mang (8000, 5173, 3000)
echo.
echo [8/16] Kiem tra trang thai va giai phong cac cong mang (8000, 5173, 3000)...
.venv\Scripts\python.exe apps\api\scripts\check_and_free_ports.py
if !errorlevel! neq 0 (
    call :error_exit "8" "Giai phong cong mang" "Khong the giai phong cac cong 8000, 5173, 3000"
)

:: 9. Chay Alembic migration
echo.
echo [9/16] Chay Alembic database migrations upgrade head...
set PYTHONPATH=%ROOT%apps\api
.venv\Scripts\python.exe apps\api\scripts\run_migrations.py
if !errorlevel! neq 0 (
    call :error_exit "9" "Alembic upgrade head" "Alembic migration that bai"
)

:: 10. Kiem tra chi co 1 Alembic head
echo.
echo [10/16] Kiem tra revision heads cua Alembic...
.venv\Scripts\python.exe apps\api\scripts\check_alembic_heads.py
if !errorlevel! neq 0 (
    call :error_exit "10" "Kiem tra Alembic heads" "He thong Alembic co khac 1 head revision"
)

:: 11 & 12. Chay dong bo schema va Seed du lieu (chi chay khi CSDL chua co hoac khi co co --seed)
if "!IS_FIRST_RUN!"=="1" (
    echo.
    echo [11/16] Chay dong bo schema an toan migrate_schema.py...
    .venv\Scripts\python.exe apps\api\app\db\migrate_schema.py
    if !errorlevel! neq 0 (
        call :error_exit "11" "Dong bo schema SQLite" "migrate_schema.py that bai"
    )

    echo.
    echo [12/16] Chay Seeder du lieu demo idempotent: Tai khoan, Vai tro, Kho hang...
    set DEMO_MODE=true
    .venv\Scripts\python.exe apps\api\scripts\seed_demo_data.py
    if !errorlevel! neq 0 (
        call :error_exit "12" "Seed du lieu demo" "seed_demo_data.py that bai"
    )
) else (
    echo.
    echo [11-12/16] CSDL da san sang - Bo qua Seed de khoi dong sieu toc ~2-3s.
    echo            - Meo: Dung start.bat --seed neu ban muon nap lai toan bo du lieu mau.
)

:: 13. Khoi dong Backend tai cong 8000
echo.
echo [13/16] Khoi dong Backend FastAPI tai cong 8000...
start "PharmaTrust Backend :8000" cmd /k "cd /d "%ROOT%" && call "%ROOT%.venv\Scripts\activate.bat" && set PYTHONPATH=%ROOT%apps\api && "%ROOT%.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000"

:: 14. Cho Backend Health Check thanh cong
echo.
echo [14/16] Cho Backend Health Check phan hoi...
.venv\Scripts\python.exe apps\api\scripts\wait_for_health.py
if !errorlevel! neq 0 (
    call :error_exit "14" "Backend Health Check" "Backend khong phan hoi tren cong 8000 sau 35 giay"
)

:: 15. Khoi dong Admin Web Portal tai cong 5173
echo.
echo [15/16] Khoi dong Admin Web Portal tai cong 5173...
start "PharmaTrust Admin Web :5173" cmd /k "cd /d "%ROOT%apps\web" && npm run dev -- --host 0.0.0.0 --port 5173"

:: 16. Khoi dong Storefront Next.js tai cong 3000 va kiem tra website san sang
echo.
echo [16/16] Khoi dong Storefront Next.js tai cong 3000 va kiem tra website san sang...
start "PharmaTrust Storefront :3000" cmd /k "cd /d "%ROOT%apps\storefront" && set NEXT_PUBLIC_DEMO_MODE=true && npm run dev -- -p 3000"

.venv\Scripts\python.exe apps\api\scripts\wait_for_services.py --timeout 15

echo.
echo ===================================================================================
echo                      HE THONG H4CARE DA SAN SANG HOAT DONG!
echo ===================================================================================
echo   1. Giao Dien Mua Thuoc Khach Hang: http://localhost:3000
echo   2. Cong Quan Tri va Quan Ly Kho:   http://localhost:5173
echo   3. Tai Lieu API Swagger Backend:   http://localhost:8000/docs
echo   4. Kiem Tra Tinh Trang He Thong:   http://localhost:8000/api/v1/health
echo -----------------------------------------------------------------------------------
echo   DANH SACH TAI KHOAN DEMO CHUAN:
echo   * Quan Tri Toan Quyen Admin:        admin@pharmatrust.vn         / Admin@123456
echo   * Quan Ly Kho HCM:                  manager.hcm@pharmatrust.vn   / Warehouse@2026
echo   * Nhan Vien Kho HCM:                staff.hcm@pharmatrust.vn     / Staff@2026
echo   * Quan Ly Kho Ha Noi:               manager.hn@pharmatrust.vn    / Warehouse@2026
echo   * Nhan Vien Kho Ha Noi:             staff.hn@pharmatrust.vn      / Staff@2026
echo   * Khach Hang Mua Thuoc:             buyer@pharmatrust.vn         / Buyer@123456
echo ===================================================================================
echo Ba cua so Command Prompt doc lap da mo san sang giu log truc tiep.
echo Cac website da phan hoi san sang. Dang tu dong mo Google Chrome...
ping 127.0.0.1 -n 2 >nul

start chrome http://localhost:3000 2>nul || start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://localhost:3000 2>nul || start http://localhost:3000
start chrome http://localhost:5173 2>nul || start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://localhost:5173 2>nul || start http://localhost:5173
exit /b 0

:: ===================================================================================
::  HAM XU LY KHI CO LOI
:: ===================================================================================
:error_exit
echo.
echo ===================================================================================
echo [THAT BAI] Buoc %~1 gap su co: %~2
echo Lenh gay loi: %~3
echo ===================================================================================
echo He thong da tam dung de ban kiem tra thong diep loi chi tiet o tren.
echo.
pause
exit /b 1
