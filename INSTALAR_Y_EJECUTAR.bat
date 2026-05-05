@echo off
title PC Guardian - Instalador

:: Solicitar elevacion si no somos administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Solicitando permisos de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo.
echo [PC Guardian] Herramienta de Diagnostico para Windows 10/11
echo -------------------------------------------------------------
echo.

:: Comprobar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python no esta instalado. Descargando Python 3.12...
    echo     Esto puede tardar unos minutos segun tu conexion.
    echo.
    curl -L -o "%TEMP%\python_setup.exe" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
    if %errorlevel% neq 0 (
        echo ERROR: No se pudo descargar Python. Comprueba tu conexion.
        pause
        exit /b 1
    )
    echo Instalando Python...
    "%TEMP%\python_setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    del "%TEMP%\python_setup.exe"
    echo.
    echo Python instalado. Cierra esta ventana y vuelve a ejecutar el .bat.
    pause
    exit /b 0
) else (
    for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo [OK] %%V detectado.
)

:: Instalar dependencias
echo.
echo [*] Instalando dependencias (Flask, psutil)...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Fallo al instalar dependencias.
    pause
    exit /b 1
)

:: Lanzar
echo.
echo [*] Iniciando PC Guardian en http://127.0.0.1:47832
echo [*] El navegador se abrira automaticamente.
echo [*] Cierra esta ventana para apagar la aplicacion.
echo.
python app.py
pause
