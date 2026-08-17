@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Folder: %CD%
python -c "from radar.config import CONFIG_PATH, load_config; c=load_config(); print('Config:', CONFIG_PATH); print('Profile:', c.get('candidate_role')); print('Chrome port:', c.get('chrome_debug_port')); print('Threshold:', c.get('score_threshold'))"
if errorlevel 1 (
  echo Failed to read config.
  pause
  exit /b 1
)
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
