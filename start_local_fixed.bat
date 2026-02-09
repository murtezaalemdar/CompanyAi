@echo off
title Kurumsal AI Asistani - Baslatiliyor...
color 0A

echo ===============================================
echo Kurumsal AI Asistani - Windows Baslatma Scripti
echo ===============================================

echo.
echo [1/4] Python kontrol ediliyor...
python --version
if %errorlevel% neq 0 (
    color 0C
    echo [HATA] Python bulunamadi! Lutfen Python yukleyin ve PATH'e ekleyin.
    pause
    exit
)

echo.
echo [2/4] Bagimliliklar yukleniyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [HATA] Kutuphane yuklemesinde hata olustu!
    echo Lutfen 'Microsoft C++ Build Tools' yuklu oldugundan emin olun.
    pause
    exit
)

echo.
echo [3/4] Backend baslatiliyor...
set DATABASE_URL=sqlite+aiosqlite:///./companyai.db
start "Backend API" cmd /k "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo.
echo [4/4] Frontend baslatiliyor...
cd frontend
if not exist node_modules (
    echo Node modulleri yukleniyor...
    call npm install
)
start "Frontend Dashboard" cmd /k "npm run dev"

echo.
echo [BILGI] Sistem baslatildi!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Docs:     http://localhost:8000/docs
echo.
echo Pencereleri kapatarak durdurabilirsiniz.
pause
