@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ======================================================================
echo          PHARMATRUST / H4CARE - KHOI DONG FRONTEND WEB
echo ======================================================================
echo   [1] Giao dien Storefront (Next.js): http://localhost:3000
echo   [2] Giao dien Admin Data Hub (Vite): http://localhost:5173
echo ======================================================================
echo.

where node >nul 2>&1

echo [1/2] Dang khoi dong Next.js Storefront tren cong 3000...
start "H4CARE-Storefront-3000" cmd /k "title H4CARE Storefront :3000 && cd /d "%~dp0apps\storefront" && npm run dev -- -p 3000"

echo [2/2] Dang khoi dong Vite Admin Data Hub tren cong 5173...
start "PharmaTrust-Admin-5173" cmd /k "title PharmaTrust Admin :5173 && cd /d "%~dp0apps\web" && npm run dev"

echo.
echo [OK] Ca hai giao dien Frontend da duoc khoi chay!
echo   - Khach hang: http://localhost:3000
echo   - Quan tri:   http://localhost:5173
echo.
echo Dang tu dong mo Google Chrome vao Storefront va Admin...
ping 127.0.0.1 -n 3 >nul
start chrome http://localhost:3000 2>nul || start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://localhost:3000 2>nul || start http://localhost:3000
start chrome http://localhost:5173 2>nul || start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" http://localhost:5173 2>nul || start http://localhost:5173
exit /b 0
