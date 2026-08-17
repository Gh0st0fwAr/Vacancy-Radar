# -*- coding: utf-8 -*-
"""Candidate profile text injected into Cursor scoring prompts.

Canonical resume file: cvddv.pdf (next to VacancyRadar folder).
NOT resume.txt / rezume.txt.

Shared rubric with IDE Cursor: cursor_bridge/SCORING_CONTEXT.md
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# VacancyRadar/radar/this file -> parents[1]=VacancyRadar, parents[2]=workspace root
_WORKSPACE = Path(__file__).resolve().parents[2]
_VR_ROOT = Path(__file__).resolve().parents[1]
RESUME_PDF = _WORKSPACE / "cvddv.pdf"
SCORING_CONTEXT_PATH = _VR_ROOT / "cursor_bridge" / "SCORING_CONTEXT.md"

GITHUB_URL = "https://github.com/Gh0st0fwAr"
PORTFOLIO_URL = "https://gh0st0fwar.github.io/"

NMS_EXCERPT = """
NMS / Elevate NMS (Comtech EF Data / Komtek, 4+ years commercial):
- Enterprise SPA for satellite network monitoring and configuration (~90+ Vue components).
- Production stack FACT: Vue 2.6, Vue Router 3, Webpack 4, axios, vue-i18n, Ag-Grid, Leaflet,
  ApexCharts/Dygraphs, SCSS; Options API / mixins. NOT a full Vue3/Pinia/TS monorepo in production.
- Real modules: network object tree + virtualization, role dashboards (Network/VNO/Station/Controller),
  dynamic dashboard widgets, FormGenerator from JSON API schemas, Scheduler, Spectrum Analyzer,
  Problem Investigator, world map topology, real-time telemetry graphs.
- Built NMS frontend from scratch at Istar (2019-2021), continued at Comtech (2021-2025).
- Vue 3 + TypeScript + Pinia: strong in pets (DevPulse, Scheduler, Nuxt Notes) and portfolio demos;
  do NOT claim the entire commercial NMS codebase is Vue 3 / Pinia / strict TS.
""".strip()


@lru_cache(maxsize=1)
def _extract_pdf_text(path_str: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path_str)
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()


def load_resume_text(max_chars: int = 14000) -> str:
    """Load FULL resume from cvddv.pdf only."""
    path = RESUME_PDF
    text = ""
    if path.exists():
        try:
            text = _extract_pdf_text(str(path))
        except Exception:
            text = ""
    if not text.strip():
        text = (
            "Daniil Virin - Middle frontend, 6+ years Vue. Remote only. "
            f"Portfolio: {PORTFOLIO_URL}. GitHub: {GITHUB_URL}. "
            f"(WARNING: failed to read resume PDF at {path})"
        )
    text = text.strip()
    if len(text) > max_chars:
        text = text[: max_chars - 20] + "\n...[truncated]..."
    return text


def load_scoring_context() -> str:
    """Shared IDE + SDK scoring rubric (must stay in sync with SCORING_CONTEXT.md)."""
    if SCORING_CONTEXT_PATH.exists():
        try:
            return SCORING_CONTEXT_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return (
        f"Resume: cvddv.pdf. Portfolio: {PORTFOLIO_URL}. GitHub: {GITHUB_URL}. "
        "Remote only. Vue strong; Nuxt Junior. Salary: >=140k strong, >=120k ok, "
        "missing OK if fit ~70+."
    )


def links_dict() -> dict[str, str]:
    """Canonical links for Cursor SDK scoring payload."""
    return {
        "portfolioUrl": PORTFOLIO_URL,
        "githubUrl": GITHUB_URL,
        "resumePath": str(RESUME_PDF),
    }


def build_candidate_block() -> str:
    resume = load_resume_text()
    rubric = load_scoring_context()
    return (
        "=== CANDIDATE (trust this block; score vacancy FIT against it) ===\n"
        "Resume source: cvddv.pdf (authoritative)\n"
        f"Resume file path: {RESUME_PDF}\n"
        f"Portfolio (live demos — score FIT against this too): {PORTFOLIO_URL}\n"
        f"Portfolio (same site, alternate casing): https://Gh0st0fwAr.github.io/\n"
        f"GitHub (profile + projects): {GITHUB_URL}\n"
        "\n"
        "IMPORTANT:\n"
        "- Portfolio URLs and GitHub ARE scoring context (Vue demos / repos direction).\n"
        "- Full resume text from cvddv.pdf is embedded below — treat it as read.\n"
        "- Do NOT crawl/clone portfolio SOURCE repo as proof of skill; use demos + GitHub names.\n"
        "- Do NOT fail scoring because URLs cannot be fetched online.\n"
        "- Judge FIT yourself from this context + vacancy text. Do NOT apply Python rules-engine point formulas.\n"
        "\n"
        "=== SCORING GUIDANCE (soft; not a point spreadsheet) ===\n"
        f"{rubric}\n"
        "=== END GUIDANCE ===\n"
        "\n"
        "FULL RESUME (from cvddv.pdf):\n"
        f"{resume}\n"
        "\n"
        "NMS EXCERPT (commercial truth):\n"
        f"{NMS_EXCERPT}\n"
        "=== END CANDIDATE ==="
    )
