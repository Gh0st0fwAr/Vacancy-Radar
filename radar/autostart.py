# -*- coding: utf-8 -*-
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
    return _startup_dir() / f"{APP_NAME}.lnk"


def is_autostart_enabled() -> bool:
    return startup_shortcut_path().exists()


def _target_command() -> tuple[str, str, str]:
    root = Path(__file__).resolve().parent.parent
    bat = root / "Start VacancyRadar.bat"
    if bat.exists():
        return str(bat), "", str(root)
    py = sys.executable or "python"
    return py, f'"{root / "main.py"}"', str(root)


def set_autostart(enabled: bool) -> str:
    path = startup_shortcut_path()
    if not enabled:
        try:
            if path.exists():
                path.unlink()
            return 'Автозапуск выключен'
        except Exception as e:
            return f"Не удалось выключить автозапуск: {e}"

    try:
        _startup_dir().mkdir(parents=True, exist_ok=True)
        target, args, workdir = _target_command()
        ps = (
            f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{path}');"
            f"$s.TargetPath='{target}';"
            f"$s.Arguments='{args}';"
            f"$s.WorkingDirectory='{workdir}';"
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
            return 'Автозапуск: ярлык не создался'
        return 'Автозапуск включён (папка «Автозагрузка»)'
    except Exception as e:
        return f"Не удалось включить автозапуск: {e}"
