@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Installing Python packages from requirements.txt ...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Failed to install packages. Check that Python is on PATH and the PC is online.
  echo Manual: python -m pip install -r requirements.txt
  pause
  exit /b 1
)
python main.py
if errorlevel 1 pause
