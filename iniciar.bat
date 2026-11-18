@echo off
chcp 65001 >nul
title StockDepo - Enfocados Mendoza
cd /d "%~dp0"

REM 1. Verificar si StockDepo ya esta activo o el puerto 8000 quedo tomado
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app\verificar_puerto.py >nul 2>&1
  if errorlevel 2 (
    echo [!] El puerto 8000 esta ocupado por un proceso anterior. Liberando...
    powershell -NoProfile -Command "$p = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }" >nul 2>&1
    ping 127.0.0.1 -n 2 >nul
  ) else if not errorlevel 1 (
    echo.
    echo ============================================================
    echo   StockDepo ya esta funcionando en esta computadora.
    echo   Abriendo en tu navegador: http://localhost:8000
    echo ============================================================
    echo.
    start "" http://localhost:8000
    ping 127.0.0.1 -n 3 >nul
    exit /b
  )
)

REM 2. Verificar si el entorno virtual existe y funciona en ESTA computadora
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, qrcode" >nul 2>&1
if errorlevel 1 (
  echo ============================================================
  echo  Preparando StockDepo en esta computadora por primera vez...
  echo ============================================================
  if exist ".venv" rmdir /s /q ".venv"
  python --version >nul 2>&1
  if errorlevel 1 (
    echo [!] Python no esta instalado. Intentando instalar Python automaticamente...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 goto :error
  )
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

echo.
echo  ============================================================
echo   StockDepo funcionando (Enfocados Mendoza)
echo   - Abriendo automaticamente en: http://localhost:8000
echo   - Para entrar desde los celulares: mira el codigo QR en Configuracion
echo   - Deja esta ventana abierta o minimizada mientras usen el sistema.
echo  ============================================================
echo.

".venv\Scripts\python.exe" -m app
pause
exit /b

:error
echo.
echo [!] Hubo un problema al preparar Python.
echo Descarga e instala Python desde https://www.python.org/downloads/
echo (IMPORTANTE: tilda la casilla "Add Python to PATH" al instalarlo)
pause
