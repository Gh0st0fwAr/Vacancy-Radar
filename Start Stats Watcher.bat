@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title VacancyRadar Stats Watcher
echo Passive stats watcher - does NOT call Cursor / spend tokens.
echo Log file: data\stats_watcher.txt
echo Hourly dump of last-hour search/score/letter timings and tokens.
echo Close this window to stop.
echo.
python tools\radar_stats_watcher.py %*
if errorlevel 1 pause
