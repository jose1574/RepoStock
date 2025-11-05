@echo off
setlocal enableextensions

REM Build RepoStock with PyInstaller using the provided spec (robusto para venv y rutas)

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

REM Detectar Python preferentemente desde un venv local
set "PYTHON_EXE="
if exist "%SCRIPT_DIR%venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"

REM Si no hay venv, usar el lanzador py si existe
if not defined PYTHON_EXE where py >nul 2>&1 && set "PYTHON_EXE=py"

REM Último recurso: python en PATH
if not defined PYTHON_EXE where python >nul 2>&1 && set "PYTHON_EXE=python"

if not defined PYTHON_EXE (
  echo No se encontró Python. Asegura tener Python en PATH o un venv en .venv/ o venv/.
  popd
  exit /b 1
)

REM Verificar PyInstaller disponible; si usamos py/python, invocar como módulo
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo PyInstaller no está instalado en este entorno. Instalalo con:
  echo   %PYTHON_EXE% -m pip install pyinstaller
  popd
  exit /b 1
)

echo Ejecutando build con %PYTHON_EXE% ...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean app.spec
set ERR=%ERRORLEVEL%
popd

if not %ERR%==0 (
  echo.
  echo Hubo un error durante el build. Codigo: %ERR%
  exit /b %ERR%
)

echo.
echo Build completado. Ejecutable en dist\RepoStock\RepoStock.exe
echo.
echo Nota:
echo - Se incluye la carpeta install\ con el instalador de wkhtmltopdf.
echo - Si al generar PDF aparece error de wkhtmltopdf, ejecuta ese instalador una vez.
echo.
echo Para compilar el servicio de Windows, ejecuta:
echo   %PYTHON_EXE% -m PyInstaller --noconfirm --clean service.spec
echo Luego instala el servicio con privilegios de administrador:
echo   dist\RepoStockService\RepoStockService.exe install
echo   dist\RepoStockService\RepoStockService.exe start
echo Para detener y quitar:
echo   dist\RepoStockService\RepoStockService.exe stop
echo   dist\RepoStockService\RepoStockService.exe remove
echo.
echo Listo.
exit /b 0
