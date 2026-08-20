# Wake agent after 1 hour to re-check stats_watcher dump
Start-Sleep -Seconds 3600
Write-Output 'AGENT_LOOP_WAKE_stats_check {"prompt":"Check VacancyRadar data/stats_watcher.txt latest dump. If last-hour SEARCH/SCORING/LETTERS/tokens still non-zero while idle, alert user in Russian with dump summary. If all zeros, briefly say last hour is clean. Note if main.py and radar_stats_watcher.py still run."}'
