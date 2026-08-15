# -*- coding: utf-8 -*-
"""Write themes.py / autostart.py as UTF-8 using only ASCII in this file."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def u(codes):
    return "".join(chr(int(c, 16)) for c in codes.split())


# Russian fragments
hyphen = u("2014")
po_umolch = u("043f 043e 0020 0443 043c 043e 043b 0447 0430 043d 0438 044e")
avto_off = u("0410 0432 0442 043e 0437 0430 043f 0443 0441 043a 0020 0432 044b 043a 043b 044e 0447 0435 043d")
ne_ud_off = u("041d 0435 0020 0443 0434 0430 043b 043e 0441 044c 0020 0432 044b 043a 043b 044e 0447 0438 0442 044c 0020 0430 0432 0442 043e 0437 0430 043f 0443 0441 043a")
yarlyk = u("0410 0432 0442 043e 0437 0430 043f 0443 0441 043a 003a 0020 044f 0440 043b 044b 043a 0020 043d 0435 0020 0441 043e 0437 0434 0430 043b 0441 044f")
avto_on = (
    u("0410 0432 0442 043e 0437 0430 043f 0443 0441 043a 0020 0432 043a 043b 044e 0447 0451 043d 0020 0028 043f 0430 043f 043a 0430 0020")
    + u("00ab")
    + u("0410 0432 0442 043e 0437 0430 0433 0440 0443 0437 043a 0430")
    + u("00bb")
    + ")"
)
ne_ud_on = u("041d 0435 0020 0443 0434 0430 043b 043e 0441 044c 0020 0432 043a 043b 044e 0447 0438 0442 044c 0020 0430 0432 0442 043e 0437 0430 043f 0443 0441 043a")

themes = f'''# -*- coding: utf-8 -*-
"""Multi-theme palettes for VacancyRadar (hybrid UI)."""
from __future__ import annotations

from copy import deepcopy
from typing import Dict

THEME_IDS = ("04", "01", "02", "03")
THEME_LABELS = {{
    "04": "04 {hyphen} Hybrid ({po_umolch})",
    "01": "01 {hyphen} Graphite Split",
    "02": "02 {hyphen} Compact Pro",
    "03": "03 {hyphen} Slate Master-Detail",
}}

PALETTES: Dict[str, Dict[str, str]] = {{
    "04": {{
        "BG": "#1c2128", "BG_PANEL": "#252b33", "BG_ELEVATED": "#2e3640", "BG_INPUT": "#181c22",
        "BORDER": "#4a5562", "BORDER_SOFT": "#3a4450", "TEXT": "#e8edf2", "TEXT_DIM": "#a8b3c0",
        "TEXT_MUTED": "#7d8a99", "ACCENT": "#6ec8b8", "ACCENT_DIM": "#3d7a70", "DANGER": "#d47878",
        "OK": "#7bc47f", "WARN": "#e6c35c", "INVITE": "#7eb6f0", "INVITE_BG": "#1e3348",
        "WHITE_FG": "#f5f7fa", "WHITE_STRIPE": "#e8edf2", "GRAY_APPLY": "#9aa3ad",
        "GRAY_APPLY_BG": "#2a3038", "GRAY_STRIPE": "#6b7280", "POINTER_FG": "#8dff9a",
        "POINTER_BG": "#1f5c32", "POINTER_STRIPE": "#3dff6a", "NEW_STRIPE": "#dfe6ee", "RADIUS": "12",
    }},
    "01": {{
        "BG": "#121820", "BG_PANEL": "#1a222c", "BG_ELEVATED": "#24303c", "BG_INPUT": "#0e141a",
        "BORDER": "#3d4a57", "BORDER_SOFT": "#2c3844", "TEXT": "#eef3f7", "TEXT_DIM": "#9aabba",
        "TEXT_MUTED": "#6f8191", "ACCENT": "#20c997", "ACCENT_DIM": "#147a5c", "DANGER": "#e07a7a",
        "OK": "#6fd68a", "WARN": "#e6c35c", "INVITE": "#6eb6ff", "INVITE_BG": "#16324a",
        "WHITE_FG": "#ffffff", "WHITE_STRIPE": "#ffffff", "GRAY_APPLY": "#8b97a3",
        "GRAY_APPLY_BG": "#232b33", "GRAY_STRIPE": "#6a7682", "POINTER_FG": "#9affb0",
        "POINTER_BG": "#185a30", "POINTER_STRIPE": "#45ff7a", "NEW_STRIPE": "#f0f4f8", "RADIUS": "14",
    }},
    "02": {{
        "BG": "#121212", "BG_PANEL": "#181818", "BG_ELEVATED": "#222222", "BG_INPUT": "#0a0a0a",
        "BORDER": "#3a3a3a", "BORDER_SOFT": "#2a2a2a", "TEXT": "#eaeaea", "TEXT_DIM": "#9e9e9e",
        "TEXT_MUTED": "#6e6e6e", "ACCENT": "#34d399", "ACCENT_DIM": "#1a7a55", "DANGER": "#f87171",
        "OK": "#4ade80", "WARN": "#facc15", "INVITE": "#60a5fa", "INVITE_BG": "#0f2744",
        "WHITE_FG": "#fafafa", "WHITE_STRIPE": "#fafafa", "GRAY_APPLY": "#a1a1aa",
        "GRAY_APPLY_BG": "#27272a", "GRAY_STRIPE": "#71717a", "POINTER_FG": "#86efac",
        "POINTER_BG": "#14532d", "POINTER_STRIPE": "#4ade80", "NEW_STRIPE": "#f4f4f5", "RADIUS": "6",
    }},
    "03": {{
        "BG": "#0f172a", "BG_PANEL": "#1e293b", "BG_ELEVATED": "#334155", "BG_INPUT": "#0b1220",
        "BORDER": "#475569", "BORDER_SOFT": "#334155", "TEXT": "#e2e8f0", "TEXT_DIM": "#94a3b8",
        "TEXT_MUTED": "#64748b", "ACCENT": "#60a5fa", "ACCENT_DIM": "#1d4ed8", "DANGER": "#f87171",
        "OK": "#4ade80", "WARN": "#fbbf24", "INVITE": "#a78bfa", "INVITE_BG": "#2e1065",
        "WHITE_FG": "#f8fafc", "WHITE_STRIPE": "#f8fafc", "GRAY_APPLY": "#94a3b8",
        "GRAY_APPLY_BG": "#1e293b", "GRAY_STRIPE": "#64748b", "POINTER_FG": "#86efac",
        "POINTER_BG": "#166534", "POINTER_STRIPE": "#4ade80", "NEW_STRIPE": "#f1f5f9", "RADIUS": "10",
    }},
}}


def get_palette(theme_id: str) -> Dict[str, str]:
    tid = str(theme_id or "04")
    if tid not in PALETTES:
        tid = "04"
    return deepcopy(PALETTES[tid])


def build_qss(p: Dict[str, str]) -> str:
    r = p.get("RADIUS", "12")
    return (
        "* {{ font-family: \\"Segoe UI\\", \\"Arial\\", sans-serif; font-size: 16px; color: {t}; }}\\n"
        "QMainWindow, QWidget {{ background-color: {bg}; color: {t}; }}\\n"
        "QLabel {{ color: {t}; font-size: 16px; background: transparent; }}\\n"
        "QLabel#sectionTitle {{ font-size: 19px; font-weight: 700; color: {t}; padding: 6px 0 10px 0; }}\\n"
        "QLabel#hotkeyBadge {{ font-size: 22px; font-weight: 700; color: {a}; padding: 10px 16px; "
        "background-color: {be}; border: 2px solid {ad}; border-radius: {r}px; }}\\n"
        "QLabel#statsValue {{ font-size: 20px; font-weight: 700; color: {a}; }}\\n"
        "QLabel#mutedLabel {{ font-size: 15px; color: {tm}; }}\\n"
        "QLabel#legendChip {{ font-size: 15px; font-weight: 700; padding: 8px 14px; border-radius: 8px; "
        "border: 2px solid {b}; }}\\n"
        "QGroupBox {{ font-size: 17px; font-weight: 700; color: {t}; border: 1px solid {b}; "
        "border-radius: {r}px; margin-top: 16px; padding-top: 20px; padding-left: 14px; "
        "padding-right: 14px; padding-bottom: 12px; background-color: {bp}; }}\\n"
        "QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 14px; "
        "padding: 0 8px; color: {a}; }}\\n"
        "QScrollArea {{ background-color: {bg}; border: none; }}\\n"
        "QScrollArea > QWidget > QWidget {{ background-color: {bg}; }}\\n"
        "QListWidget {{ background-color: {bi}; border: 1px solid {b}; border-radius: {r}px; "
        "padding: 8px; font-size: 18px; outline: none; }}\\n"
        "QListWidget::item {{ padding: 14px 12px 14px 14px; margin: 4px 2px; border-radius: 10px; "
        "border: 1px solid transparent; min-height: 52px; }}\\n"
        "QListWidget::item:selected {{ border: 2px solid {a}; }}\\n"
        "QListWidget::item:hover:!selected {{ border: 1px solid {b}; }}\\n"
        "QTextEdit {{ background-color: {bi}; border: 1px solid {b}; border-radius: {r}px; "
        "padding: 12px; font-size: 17px; selection-background-color: {ad}; }}\\n"
        "QCheckBox {{ font-size: 17px; spacing: 12px; padding: 8px 2px; color: {t}; background: transparent; }}\\n"
        "QCheckBox::indicator {{ width: 24px; height: 24px; border-radius: 7px; border: 2px solid {b}; "
        "background: {bi}; }}\\n"
        "QCheckBox::indicator:checked {{ background-color: {a}; border-color: {a}; }}\\n"
        "QComboBox {{ background-color: {be}; color: {t}; border: 1px solid {b}; border-radius: 10px; "
        "padding: 10px 12px; font-size: 16px; min-height: 28px; }}\\n"
        "QComboBox QAbstractItemView {{ background-color: {bp}; color: {t}; "
        "selection-background-color: {ad}; }}\\n"
        "QPushButton {{ background-color: {be}; color: {t}; border: 1px solid {b}; border-radius: {r}px; "
        "padding: 12px 18px; font-size: 16px; font-weight: 600; min-height: 26px; }}\\n"
        "QPushButton:hover {{ border: 2px solid {a}; }}\\n"
        "QPushButton:disabled {{ color: {tm}; border-color: {bs}; }}\\n"
        "QPushButton#primaryBtn {{ background-color: {ad}; border: 2px solid {a}; color: #f2fffc; }}\\n"
        "QPushButton#okBtn {{ background-color: #2d4a32; border: 2px solid {ok}; }}\\n"
        "QPushButton#dangerBtn {{ background-color: #4a2e2e; border: 2px solid {dg}; }}\\n"
        "QPushButton#warnBtn {{ background-color: #4a4020; border: 2px solid {wn}; }}\\n"
        "QPushButton#ghostBtn {{ background-color: transparent; border: 1px dashed {b}; }}\\n"
        "QStatusBar {{ background-color: {bp}; color: {td}; font-size: 15px; border-top: 1px solid {bs}; "
        "padding: 6px 12px; }}\\n"
        "QSplitter::handle {{ background-color: {bs}; width: 4px; margin: 8px 4px; border-radius: 2px; }}\\n"
        "QScrollBar:vertical {{ background: {bg}; width: 16px; margin: 2px; border: none; }}\\n"
        "QScrollBar::handle:vertical {{ background: {b}; min-height: 40px; border-radius: 8px; }}\\n"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}\\n"
        "QMessageBox {{ background-color: {bp}; }}\\n"
        "QMessageBox QLabel {{ font-size: 17px; color: {t}; min-width: 420px; }}\\n"
    ).format(
        t=p["TEXT"], bg=p["BG"], a=p["ACCENT"], be=p["BG_ELEVATED"], ad=p["ACCENT_DIM"],
        r=r, tm=p["TEXT_MUTED"], b=p["BORDER"], bp=p["BG_PANEL"], bi=p["BG_INPUT"],
        bs=p["BORDER_SOFT"], ok=p["OK"], dg=p["DANGER"], wn=p["WARN"], td=p["TEXT_DIM"],
    )
'''

autostart = f'''# -*- coding: utf-8 -*-
"""Windows autostart helper for VacancyRadar."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "VacancyRadar"


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_shortcut_path() -> Path:
    return _startup_dir() / f"{{APP_NAME}}.lnk"


def is_autostart_enabled() -> bool:
    return startup_shortcut_path().exists()


def _target_command() -> tuple[str, str, str]:
    root = Path(__file__).resolve().parent.parent
    bat = root / "Start VacancyRadar.bat"
    if bat.exists():
        return str(bat), "", str(root)
    py = sys.executable or "python"
    return py, f'"{{root / "main.py"}}"', str(root)


def set_autostart(enabled: bool) -> str:
    path = startup_shortcut_path()
    if not enabled:
        try:
            if path.exists():
                path.unlink()
            return "{avto_off}"
        except Exception as e:
            return f"{ne_ud_off}: {{e}}"

    try:
        _startup_dir().mkdir(parents=True, exist_ok=True)
        target, args, workdir = _target_command()
        ps = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{{path}}');"
            f"$s.TargetPath='{{target}}';"
            f"$s.Arguments='{{args}}';"
            f"$s.WorkingDirectory='{{workdir}}';"
            f"$s.WindowStyle=7;"
            f"$s.Save()"
        )
        import subprocess

        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if not path.exists():
            return "{yarlyk}"
        return "{avto_on}"
    except Exception as e:
        return f"{ne_ud_on}: {{e}}"
'''

(ROOT / "radar" / "themes.py").write_text(themes, encoding="utf-8")
(ROOT / "radar" / "autostart.py").write_text(autostart, encoding="utf-8")
print("OK themes", (ROOT / "radar" / "themes.py").stat().st_size)
print("OK autostart", (ROOT / "radar" / "autostart.py").stat().st_size)
