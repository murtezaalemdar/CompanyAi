@echo off
echo ===============================================
echo Kurumsal AI Asistani - Lokal Baslatma Scripti
echo ===============================================

echo.
echo [1/3] Backend baslatiliyor...
start "Backend API" cmd /k "pip install -r requirements.txt && uvicorn app.main:app --reload"

echo.
echo [2/3] Frontend baslatiliyor...
cd frontend
start "Frontend Dashboard" cmd /k "npm install && npm run dev"

echo.
echo [3/3] Sistem baslatildi!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Docs:     http://localhost:8000/docs
echo.
echo Pencereleri kapatarak durdurabilirsiniz.
pause
