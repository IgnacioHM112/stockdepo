@echo off
chcp 65001 >nul
title Configurar StockDepo en esta Notebook
cd /d "%~dp0"

echo ============================================================
echo   Configuracion rapida de StockDepo en la Notebook
echo ============================================================
echo.

REM 1. Crear acceso directo en el Escritorio
echo [1/2] Creando acceso directo "StockDepo" en el Escritorio...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\StockDepo.lnk'); $s.TargetPath = '%~dp0iniciar.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'StockDepo - Enfocados Mendoza'; $s.Save()"
echo       Listo: ya tenes el icono "StockDepo" en el Escritorio.
echo.

REM 2. Abrir puerto 8000 en el Firewall de Windows (requiere permisos de Administrador)
echo [2/2] Habilitando el puerto 8000 en el Firewall para entrar desde los celulares...
netsh advfirewall firewall show rule name="StockDepo LAN (Puerto 8000)" >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process netsh -ArgumentList 'advfirewall firewall add rule name=\"StockDepo LAN (Puerto 8000)\" dir=in action=allow protocol=TCP localport=8000' -Verb RunAs"
  echo       Se solicito permiso de Administrador para habilitar el acceso por Wi-Fi.
) else (
  echo       La regla del Firewall ya estaba creada.
)

echo.
echo ============================================================
echo   ¡Todo listo! Ya podes abrir StockDepo desde el Escritorio
echo   o haciendo doble clic en iniciar.bat.
echo ============================================================
pause
