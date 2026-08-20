# -*- coding: utf-8 -*-
"""Dynamic hh.ru search URL from activity sphere and preference keywords."""
from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .sphere_filter import normalize_sphere_category

NEUTRAL_HH_SEARCH_URL = (
    "https://hh.ru/search/vacancy?"
    "search_field=name&search_field=description"
    "&schedule=remote"
    "&order_by=publication_time"
    "&search_period=2"
    "&items_on_page=50"
)

_SPHERE_SEEDS: Dict[str, List[str]] = {
    "developer": [
        "разработчик",
        "frontend",
        "backend",
        "fullstack",
        "developer",
    ],
    "designer": [
        "дизайнер",
        "designer",
        "графический дизайнер",
        "иллюстратор",
    ],
    "qa": ["QA", "тестировщик", "QA engineer"],
    "devops": ["DevOps", "SRE", "Kubernetes"],
    "analyst": ["аналитик", "analyst"],
    "pm": ["project manager", "product manager", "руководитель проекта"],
    "support": ["техподдержка", "technical support"],
}

_DEFAULT_QUERY_KEYS = {
    "order_by": "publication_time",
    "search_period": "2",
    "items_on_page": "50",
}


def sphere_seed_keywords(sphere: str) -> List[str]:
    """Map activity sphere to 3–8 HH search seed keywords."""
    cat = normalize_sphere_category(sphere)
    if cat:
        return list(_SPHERE_SEEDS.get(cat, []))
    raw = str(sphere or "").strip()
    if raw:
        return [raw]
    return []


def build_hh_search_url(
    *,
    sphere: str = "",
    desirable: Optional[List[str]] = None,
    base_url: Optional[str] = None,
) -> str:
    """Build HH search URL.

    If ``desirable`` is provided (even empty list means "use desirable path"),
    keywords come from desirable (for secondary SERP). If ``desirable`` is
    ``None``, use sphere seeds, else neutral.
    """
    from .preferences import normalize_keywords

    template = str(base_url or NEUTRAL_HH_SEARCH_URL).strip() or NEUTRAL_HH_SEARCH_URL
    parsed = urlparse(template)

    kws: List[str] = []
    if desirable is not None:
        kws = normalize_keywords(desirable)[:20]
    elif str(sphere or "").strip():
        kws = sphere_seed_keywords(sphere)

    text = " OR ".join(kws) if kws else ""

    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k != "text"
    ]
    if text:
        pairs.append(("text", text))

    fields = [v for k, v in pairs if k == "search_field"]
    if "name" not in fields:
        pairs.append(("search_field", "name"))
    if "description" not in fields:
        pairs.append(("search_field", "description"))

    has_schedule = any(k == "schedule" for k, _ in pairs)
    if not has_schedule:
        pairs.append(("schedule", "remote"))

    existing_keys = {k for k, _ in pairs}
    for key, value in _DEFAULT_QUERY_KEYS.items():
        if key not in existing_keys:
            pairs.append((key, value))

    return urlunparse(parsed._replace(query=urlencode(pairs, doseq=True)))


def sync_hh_search_url_to_config(cfg: Optional[dict] = None) -> str:
    """Rebuild primary cfg hh_search_url from activity sphere; persist config.

    Desirable keywords are NOT baked into the primary URL — they remain a
    secondary SERP seed via ``preferences.search_seed_urls``.
    """
    from .config import load_config, save_config
    from .user_profile import load_profile

    if cfg is None:
        cfg = load_config()
    else:
        cfg = dict(cfg)

    sphere = (load_profile().get("activity_sphere") or "").strip()
    url = build_hh_search_url(
        sphere=sphere,
        desirable=None,
        base_url=NEUTRAL_HH_SEARCH_URL,
    )
    cfg["hh_search_url"] = url
    save_config(cfg)
    return url
