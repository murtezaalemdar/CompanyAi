@echo off
echo ===============================================
echo Kurumsal AI Asistani - DEBUG MODU
echo ===============================================
echo.
echo Mevcut veritabani siliniyor (temiz baslangic icin)...
del companyai.db 2>npm

echo.
echo Sistem baslatiliyor...
python debug_server.py

pause
