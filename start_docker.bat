@echo off
echo ===============================================
echo Kurumsal AI Asistani - Docker ile Baslatma
echo ===============================================

echo.
echo [1/2] Mevcut konteynerler temizleniyor...
docker compose -f docker/docker-compose.yml down

echo.
echo [2/2] Docker konteynerleri baslatiliyor (Ilk seferde uzun surebilir)...
docker compose -f docker/docker-compose.yml up --build -d

echo.
echo [INFO] Sistem arka planda baslatiliyor.
echo Backend Logs: docker compose -f docker/docker-compose.yml logs -f api
echo.
echo Frontend: http://localhost (Port 80 üzerinden Nginx ile)
echo Backend:  http://localhost:8000
echo.
echo Durdurmak icin: docker compose -f docker/docker-compose.yml down
pause
