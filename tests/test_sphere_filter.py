# -*- coding: utf-8 -*-
from radar.sphere_filter import (
    build_sphere_prompt_block,
    hard_reject_out_of_sphere,
    normalize_sphere_category,
)


def test_normalize_developer():
    assert normalize_sphere_category("Разработчик") == "developer"
    assert normalize_sphere_category("Frontend developer") == "developer"
    assert normalize_sphere_category("QA engineer") == "qa"


def test_reject_sales_for_developer():
    ok, reasons = hard_reject_out_of_sphere(
        "Менеджер по продажам AI-продуктов",
        "",
        sphere="Разработчик",
    )
    assert ok is True
    assert reasons


def test_reject_smm_for_developer():
    ok, _ = hard_reject_out_of_sphere("SMM-менеджер", "", sphere="Разработчик")
    assert ok is True


def test_keep_vue_for_developer():
    ok, _ = hard_reject_out_of_sphere(
        "Frontend-разработчик (Vue 3 / TypeScript)",
        "",
        sphere="Разработчик",
    )
    assert ok is False


def test_empty_sphere_no_reject():
    ok, _ = hard_reject_out_of_sphere("Менеджер по продажам", "", sphere="")
    assert ok is False


def test_sphere_prompt_block():
    text = build_sphere_prompt_block("Разработчик")
    assert "Разработчик" in text
    assert "developer" in text.lower() or "Normalized" in text
