@echo off
title PC Guardian - Compilador EXE

cd /d "%~dp0"

echo.
echo [PC Guardian] Generador de ejecutable portable
echo ------------------------------------------------
echo.

echo [1/3] Instalando PyInstaller...
python -m pip install pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: No se pudo instalar PyInstaller.
    pause
    exit /b 1
)

echo.
echo [2/3] Instalando dependencias del proyecto...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Fallo al instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [3/3] Compilando EXE (puede tardar varios minutos)...
echo.

python -m PyInstaller --noconfirm --onefile --windowed --name "PCGuardian" --add-data "templates;templates" --add-data "static;static" --hidden-import "analyzer.hardware" --hidden-import "analyzer.startup" --hidden-import "analyzer.security" --hidden-import "analyzer.drivers" --hidden-import "analyzer.updates" --hidden-import "analyzer.protection" --hidden-import "analyzer.network" --hidden-import "analyzer.maintenance" --hidden-import "winreg" --hidden-import "psutil" --hidden-import "flask" app.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: La compilacion fallo. Revisa los mensajes anteriores.
    pause
    exit /b 1
)

echo.
echo ------------------------------------------------
echo OK: EXE generado en:  dist\PCGuardian.exe
echo.
echo Copia ese archivo a cualquier PC con Windows
echo 10/11 y ejecutalo directamente. No necesita
echo Python ni ninguna instalacion adicional.
echo ------------------------------------------------
echo.
pause
