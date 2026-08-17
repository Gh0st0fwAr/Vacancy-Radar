# -*- coding: utf-8 -*-
"""Calibrate python rules against «Круг проверочный Настя»."""
from __future__ import annotations

import json
from pathlib import Path

from radar.scorer import score_vacancy

CFG_PATH = Path(__file__).resolve().parents[1] / "data" / "config.example.json"


def _profile() -> dict:
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


def _score(title: str, snippet: str, salary: str, schedule: str):
    cfg = _profile()
    return score_vacancy(
        title,
        snippet,
        salary_text=salary,
        schedule=schedule,
        salary_floor=int(cfg.get("salary_floor") or 90000),
        gate_threshold=int(cfg.get("score_threshold") or 70),
        profile=cfg,
    )


def test_round_order_and_threshold():
    cases = [
        (
            "ИИ Технологии",
            86,
            "Графический дизайнер / дизайнер маркетплейсов",
            "офис Москва карточки WB Ozon Яндекс Lamoda логотипы фирменный стиль "
            "предпечатная подготовка Photoshop Illustrator Figma CorelDRAW "
            "rich-контент упаковка этикетки листовки композиция типографика "
            "Adobe InDesign Midjourney Photoshop AI Magnific Kling 3D-мокапы Tilda "
            "анимация видео тестовое",
            "от 100 000 ₽ на руки",
            "офис",
        ),
        (
            "Decu.ru",
            84,
            "Дизайнер инфографики для маркетплейсов",
            "удалённо инфографика WB Ozon rich-контент полиграфия этикетки упаковка "
            "листовки презентации каталоги графические редакторы",
            "100 000 ₽ на руки",
            "удалённо",
        ),
        (
            "Канцпроф",
            82,
            "Дизайнер инфографики (маркетплейсы)",
            "офис Москва гибрид после ИС инфографика маркетплейсов предпечатная подготовка "
            "Illustrator Photoshop Figma CorelDRAW УТП ретушь фото ИИ-генерации обязательно "
            "в портфолио Rich-контент анимации через ИИ Shutterstock Adobe InDesign моушн",
            "оклад 85 000 ₽ на руки до 120 000 ₽",
            "офис",
        ),
        (
            "ЕСМ",
            76,
            "Дизайнер инфографики / графический дизайнер (маркетплейсы)",
            "офис Москва инфографика WB Ozon Figma Photoshop композиция цвет типографика "
            "логотипы брендбук вектор полиграфия упаковка ИИ генерация реальных предметов "
            "портфолио ИИ-фото Rich-контент адаптивный дизайн рассылки наружная реклама",
            "от 100 000 ₽ на руки",
            "офис",
        ),
        (
            "Инфинити",
            73,
            "Перформанс-дизайнер маркетплейсов (Wildberries)",
            "удалённо карточки WB Ozon Photoshop Figma инфографика обложки Midjourney "
            "Stable Diffusion Flux композитинг CTR openToCart A/B-тесты баннеры бренд-зона 3D",
            "от 120 000 ₽ база 60 000 ₽ + KPI",
            "удалённо",
        ),
        (
            "LETTA",
            70,
            "Графический дизайнер (создание карточек на маркетплейсах)",
            "удалённо Figma Photoshop e-commerce маркетплейсы графический дизайн "
            "шаблоны ТЗ нейронные сети баннеры POS лендинги презентации соцсети",
            "60 000 – 90 000 ₽ на руки",
            "удалённо",
        ),
    ]
    scored = []
    for name, target, title, snippet, salary, schedule in cases:
        sc, reasons, ok = _score(title, snippet, salary, schedule)
        scored.append((name, sc, target, ok, reasons))
        assert ok, (name, reasons)
        assert sc >= 70, (name, sc, reasons)
        assert abs(sc - target) <= 8, (name, sc, target, reasons)
    order = [x[1] for x in scored]
    assert order == sorted(order, reverse=True), scored


def test_universal_letter_is_feminine_and_has_portfolio():
    from unittest.mock import patch
    from radar.cover_letter import make_cover_letter

    cfg = _profile()
    with patch("radar.cover_letter.load_config", return_value=cfg):
        letter, src = make_cover_letter(
            "Дизайнер инфографики для маркетплейсов",
            force_local=True,
        )
    assert src == "local"
    assert "https://disk.yandex.ru/d/RsIjS0A_ANeRdg" in letter
    assert "aoi.riri@yandex.ru" in letter
    assert "Заинтересовала ваша вакансия Дизайнер инфографики для маркетплейсов." in letter
    assert "Готов ответить" not in letter
    assert "готова к тестовому" in letter.lower()
    assert "3+" in letter
    assert "Wildberries" in letter


def test_rejects_web_english_spb_lowpay_dev():
    web, _, ok_web = _score(
        "Веб-дизайнер",
        "Figma Photoshop офис Москва сайт лендинг",
        "50 000 – 60 000 ₽",
        "офис",
    )
    assert not ok_web or web < 70

    eng, reasons, ok_eng = _score(
        "Графический дизайнер",
        "офис Москва английский B1 B2 карточки маркетплейсов Photoshop Figma",
        "100 000 ₽",
        "офис",
    )
    assert eng < 70 or not ok_eng, reasons

    spb, reasons, ok_spb = _score(
        "Графический дизайнер",
        "офис Санкт-Петербург инфографика Photoshop Figma",
        "100 000 ₽",
        "офис",
    )
    assert ok_spb is False
    assert spb == 0, reasons

    low, _, ok_low = _score(
        "Дизайнер инфографики для маркетплейсов",
        "удалённо инфографика WB Ozon Photoshop Figma",
        "45 000 – 65 000 ₽",
        "удалённо",
    )
    assert low < 70

    dev, _, ok_dev = _score(
        "Frontend-разработчик",
        "удалённо Vue JavaScript",
        "160 000 ₽",
        "удалённо",
    )
    assert ok_dev is False or dev < 70
