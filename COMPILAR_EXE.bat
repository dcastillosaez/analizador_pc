@echo off
title PC Guardian - Compilador EXE

cd /d "%~dp0"

echo.
echo [PC Guardian] Generador de ejecutable portable
echo ------------------------------------------------
echo.

echo [1/4] Instalando PyInstaller...
python -m pip install pyinstaller
if %errorlevel% neq 0 (
    echo ERROR: No se pudo instalar PyInstaller.
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando dependencias del proyecto...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Fallo al instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [3/4] Cerrando instancias en ejecucion...
taskkill /F /IM PCGuardian.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul
tasklist /FI "IMAGENAME eq PCGuardian.exe" 2>nul | find /I "PCGuardian.exe" >nul
if not errorlevel 1 (
    echo.
    echo ERROR: PCGuardian.exe sigue en ejecucion y no se ha podido cerrar.
    echo        Pasa cuando la app corre elevada y este script no.
    echo        Cierrala desde el Administrador de tareas abierto como
    echo        administrador y vuelve a lanzar este script.
    pause
    exit /b 1
)

echo.
echo [4/4] Compilando EXE (puede tardar varios minutos)...
python -m analyzer._version
echo.

python -m PyInstaller --noconfirm --onefile --windowed --name "PCGuardian" --version-file "version_info.txt" --add-data "templates;templates" --add-data "static;static" --hidden-import "analyzer.hardware" --hidden-import "analyzer.startup" --hidden-import "analyzer.security" --hidden-import "analyzer.drivers" --hidden-import "analyzer.updates" --hidden-import "analyzer.protection" --hidden-import "analyzer.network" --hidden-import "analyzer.maintenance" --hidden-import "winreg" --hidden-import "psutil" --hidden-import "flask" app.py

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
