@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python main.py
if errorlevel 1 pause
