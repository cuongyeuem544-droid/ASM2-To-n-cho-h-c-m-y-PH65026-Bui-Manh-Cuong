@echo off
setlocal
cd /d "%~dp0"

:: ======================================================================
::  PHARMATRUST / H4CARE - SCRIPT GOI LAI START.BAT CHINH THUC
:: ======================================================================
echo ======================================================================
echo    PHARMATRUST / H4CARE - DANG CHUYEN TIEP SANG START.BAT CHINH THUC
echo ======================================================================
echo Quy trinh khoi dong Windows da duoc hop nhat vao start.bat.
echo Dang goi start.bat...
echo.

call "%~dp0start.bat" %*
exit /b %ERRORLEVEL%
