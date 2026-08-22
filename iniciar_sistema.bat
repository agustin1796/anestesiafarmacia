@echo off
title Sistema de Control de Opioides HCM
echo ================================================================
echo   Iniciando Sistema Rapido de Control de Opioides
echo   Hospital Central de Mendoza
echo ================================================================

cd /d "%~dp0"

:: Activar entorno virtual si existe en la carpeta superior
if exist "..\venv\Scripts\activate.bat" (
    call "..\venv\Scripts\activate.bat"
)

:: Esperar 2 segundos y abrir el navegador en 127.0.0.1:8000
start "" "http://127.0.0.1:8000"

:: Iniciar servidor FastAPI con Uvicorn
python main.py
pause
