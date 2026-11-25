@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name KiraMirror ^
  --icon logo.ico ^
  --add-data "tools;tools" ^
  --add-data "logo.png;." ^
  main.py

if errorlevel 1 (
  echo.
  echo Build failed.
  exit /b 1
)

echo.
echo Build complete: dist\KiraMirror.exe
