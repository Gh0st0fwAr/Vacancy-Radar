# Логи по дизайну (recall)

Когда пользователь говорит «логи по дизайну» / «давай логи по дизайну» / design Clear Check:

1. Читай указатель: `VacancyRadar/data/analysis/LATEST_DESIGN_LOG.json`
2. Затем JSON/MD из полей `path_json` / `path_md` (агент-формат).
3. HTML (`path_html`) — human-readable разбор прогона.
4. Рекомендации по поиску: `path_recommendations_html` → `search_system_recommendations.html`

Пересчёт прогона: `PYTHONPATH=. python tools/analyze_design_clearcheck.py`
