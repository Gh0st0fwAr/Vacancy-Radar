# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from radar import cursor_score as cs
from radar.candidate_profile import (
    GITHUB_URL,
    PORTFOLIO_URL,
    RESUME_PDF,
    build_candidate_block,
    links_dict,
    load_resume_text,
)


def test_resume_is_cvddv_pdf():
    assert RESUME_PDF.name == "cvddv.pdf"
    assert RESUME_PDF.exists()


def test_load_resume_from_pdf():
    text = load_resume_text()
    assert "Vue" in text
    assert "WARNING: failed" not in text
    assert len(text) > 500


def test_candidate_block_has_resume_and_links():
    block = build_candidate_block()
    assert "cvddv.pdf" in block
    assert "gh0st0fwar.github.io" in block
    assert "Gh0st0fwAr" in block


def test_links_dict_for_sdk_payload():
    links = links_dict()
    assert links["portfolioUrl"] == PORTFOLIO_URL == "https://gh0st0fwar.github.io/"
    assert links["githubUrl"] == GITHUB_URL == "https://github.com/Gh0st0fwAr"


def test_via_cursor_payload_includes_links():
    captured = {}

    def fake_run(cmd, **kwargs):
        path = cmd[2]
        with open(path, encoding="utf-8") as f:
            captured.clear()
            captured.update(json.load(f))

        class R:
            stdout = json.dumps(
                {
                    "ok": True,
                    "score": 70,
                    "accept": True,
                    "reasons": ["ok"],
                    "elapsed_ms": 1,
                }
            )
            stderr = ""
            returncode = 0

        return R()

    with patch.object(cs, "_api_key", return_value="k"):
        with patch.object(cs, "subprocess") as sp:
            sp.run.side_effect = fake_run
            out = cs._via_cursor(
                title="Vue",
                company="Co",
                description="remote Vue3",
                salary="",
                schedule="remote",
                experience="",
                threshold=65,
                cfg={"cursor_model": "composer-2.5"},
            )
    assert out and out.get("ok")
    assert captured["portfolioUrl"] == "https://gh0st0fwar.github.io/"
    assert captured["githubUrl"] == "https://github.com/Gh0st0fwAr"
    assert "candidateProfile" in captured
    assert "gh0st0fwar.github.io" in captured["candidateProfile"]
