@echo off
chcp 65001 >nul
echo.
echo ══════════════════════════════════════════════
echo   CompanyAI Desktop — Build Script
echo ══════════════════════════════════════════════
echo.

:: Proje kök dizinine git
cd /d "%~dp0\.."

:: Sanal ortam kontrolü
if exist "desktop\venv\Scripts\activate.bat" (
    echo [1/4] Sanal ortam bulundu, aktif ediliyor...
    call desktop\venv\Scripts\activate.bat
) else (
    echo [1/4] Sanal ortam olusturuluyor...
    python -m venv desktop\venv
    call desktop\venv\Scripts\activate.bat
)

:: Bağımlılıkları yükle
echo [2/4] Bagimliliklar yukleniyor...
pip install --quiet pywebview[cef] pyinstaller

:: Build
echo [3/4] PyInstaller ile .exe olusturuluyor...
pyinstaller desktop\companyai.spec --noconfirm --clean

:: Sonuç
echo.
if exist "dist\CompanyAI.exe" (
    echo ══════════════════════════════════════════════
    echo   ✅ BUILD BASARILI!
    echo   Dosya: dist\CompanyAI.exe
    echo ══════════════════════════════════════════════
    echo.
    echo   Boyut:
    for %%I in (dist\CompanyAI.exe) do echo     %%~zI bytes (%%~I)
    echo.
) else (
    echo ══════════════════════════════════════════════
    echo   ❌ BUILD BASARISIZ — Loglari kontrol edin
    echo ══════════════════════════════════════════════
)

pause
