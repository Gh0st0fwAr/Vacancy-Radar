# design-clear-check-2026-08-19-2034

aliases: ['логи по дизайну', 'давай логи по дизайну', 'design logs', 'clear check дизайн', 'настя дизайн лог']
summary: {'added': '1', 'checked': '354', 'serp_pages': '20', 'deep': '254', 'elapsed_sec': '1110.3', 'load_line': '20:36:08 К загрузке текста: 254 карточек (пропущено 100)', 'cursor_scored': 124, 'secondary_drop_before_cursor_est': 130, 'serp_sphere_reject': 19, 'reject_log_lines': 211}
hh_text: дизайнер OR designer OR графический дизайнер OR иллюстратор

## Answers
### q1_managers
- Dual SERP: sphere seeds + Desirable OR (маркетплейс/WB/Ozon/Figma/гибрид/Москва) тянут менеджеров из description.
- Reject слишком узкий: «менеджер по продажам» есть, голого «менеджер»/«руководитель» без design-исключения нет.
- Sphere designer = thin blacklist (dev/salesy), не allowlist роли дизайнера.
- В Cursor-батче менеджерских title: 45; title-гейты сейчас всё ещё пропускают 45.

### q2_nondesign
- Нет positive allowlist по title для sphere=Дизайнер.
- Без design-сигнала в title: 102 / 124 Cursor-скоров.
- Desirable-ключи про локацию/формат/маркетплейс ≠ роль дизайнера.
- Undesirable (frontend) не режет SERP — только мягко влияет на Cursor.

### q3_low_scores
- Cursor scored 124 из deep=254; ~130 отсеялись secondary reject/sphere после полного текста без SDK.
- Из Cursor: ≤35% = 115, <20% = 98, ≥70% = 1 — Cursor в основном прав, но поздно.
- Primary/secondary смотрят keyword+blacklist, не «обязан быть дизайн».
- Title-killable текущими правилами среди low: 0/115 — значит большинство low легальны для нынешних гейтов.

### q4_speedup
- Allowlist title до deep: дизайн-сигнал обязателен.
- Reject: менеджер/руководитель/маркетолог/SMM/рекрутер/координатор/оператор без design-слова.
- Desirable: убрать Москва/гибрид/115000/на руки/голый маркетплейс; Desirable SERP → search_field=name.
- References: 3–5 живых FIT карточек; в профиле якоря «карточки WB/Ozon, инфографика, Figma/PS».
- Снизить deep_score_max пока префильтр слабый; pre-Cursor title gate.

## Histogram
{'0-9': 89, '10-19': 9, '20-29': 11, '30-39': 6, '40-49': 1, '50-59': 6, '60-69': 1, '70-79': 1}
## Low sample
- 0% ['managerish', 'devish'] | Tech Lead / Руководитель команды разработки Python | kw=False sph=False
- 0% ['other'] | Врач-неонатолог | kw=False sph=False
- 0% ['other'] | Медицинский специалист в контакт-центр | kw=False sph=False
- 0% ['other'] | Оператор колл-центра | kw=False sph=False
- 0% ['other'] | Оператор сервиса доставки | kw=False sph=False
- 0% ['other'] | Юрист-Адвокат | kw=False sph=False
- 2% ['other'] | Senior Application Security Engineer | kw=False sph=False
- 2% ['other'] | Преподаватель по химии | kw=False sph=False
- 3% ['other'] | Lead AI Engineer, Databricks | kw=False sph=False
- 3% ['other'] | ML-инженер | kw=False sph=False
- 3% ['other'] | Амбассадор по банкротству | kw=False sph=False
- 3% ['other'] | Бустер по обучению и прокачке персонажей | kw=False sph=False
- 3% ['other'] | Ведущий инженер-конструктор по фасадам (СПК и НВФ) | kw=False sph=False
- 3% ['other'] | Ведущий/Главный специалист Открытия счетов | kw=False sph=False
- 3% ['managerish'] | Лид-менеджер | kw=False sph=False
- 3% ['managerish'] | Менеджер в финансовый маркетплейс (без опыта) | kw=False sph=False
- 3% ['managerish', 'salesish'] | Менеджер по B2B продажам (Телеком, входящие заявки) | kw=False sph=False
- 3% ['managerish', 'salesish'] | Менеджер по продаже недвижимости | kw=False sph=False
- 3% ['other'] | Младший специалист по тестированию (Junior QA) | kw=False sph=False
- 3% ['other'] | Оператор call-центра | kw=False sph=False
- 3% ['other'] | Преподаватель по русскому языку | kw=False sph=False
- 3% ['managerish'] | Руководитель проектов по монтажу стеллажного оборудования | kw=False sph=False
- 3% ['other'] | Специалист по таможенному оформлению | kw=False sph=False
- 3% ['other'] | Учитель на курс по перечневым олимпиадам по математике | kw=False sph=False
- 3% ['managerish'] | Финансовый менеджер/контролер (IT-стартап, PropTech) | kw=False sph=False
- 3% ['other'] | Эксперт по валютному контролю | kw=False sph=False
- 3% ['other'] | Эксперт по валютному контролю | kw=False sph=False
- 4% ['managerish'] | Ассистент менеджера по работе с клиентами | kw=False sph=False
- 5% ['other'] | Head of product | kw=False sph=False
- 5% ['other'] | Senior Business Analyst (DaVinci) | kw=False sph=False
- 5% ['managerish'] | Senior Digital Marketing Manager / Head of Marketing (USA Market) | kw=False sph=False
- 5% ['other'] | Академический ассистент по научным публикациям | kw=False sph=False
- 5% ['other'] | Аналитик данных (Data Analyst) | kw=False sph=False
- 5% ['managerish'] | Бридер-менеджер/Менеджер по работе с питомниками и заводчиками | kw=False sph=False
- 5% ['other'] | Инженер-проектировщик автоматического пожаротушения (АПТ) | kw=False sph=False
- 5% ['other'] | Логист (Wildberries/Ozon/Lamoda/Детский мир) | kw=False sph=False
- 5% ['managerish'] | Менеджер первых записей студии танцев и фитнеса 128bpm | kw=False sph=False
- 5% ['managerish'] | Менеджер по закупкам (байер) Одежда/обувь | kw=False sph=False
- 5% ['managerish'] | Менеджер по продвижению ювелирных изделий | kw=False sph=False
- 5% ['managerish'] | Менеджер по развитию сервиса студии танцев и фитнеса 128bpm | kw=False sph=False