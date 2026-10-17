@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ======================================================================
echo          PHARMATRUST / H4CARE - KHOI DONG BACKEND API (:8000)
echo ======================================================================
echo.

where python >nul 2>&1

set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

set "PYTHONPATH=%~dp0apps\api;%PYTHONPATH%"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Kiem tra va khoi tao co so du lieu SQLite neu chua co
if not exist "%~dp0pharmatrust.db" (
    echo [THONG BAO] Co so du lieu chua ton tai. Dang khoi tao va nap du lieu mau...
    "%PYTHON_EXE%" -m app.seed
    if errorlevel 1 (
        echo [CANH BAO] Nap du lieu mau that bai. Tiep tuc khoi dong server...
    ) else (
        echo [OK] Co so du lieu da duoc khoi tao thanh cong!
    )
    echo.
)

echo [1/1] Dang khoi dong FastAPI Backend tai http://localhost:8000 ...
echo       - Swagger UI:   http://localhost:8000/docs
echo       - Health check: http://localhost:8000/api/v1/health
echo ======================================================================
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --app-dir apps\api --reload --host 0.0.0.0 --port 8000

pause
