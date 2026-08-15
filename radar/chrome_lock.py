# -*- coding: utf-8 -*-
"""Chrome exclusive lock for search/stats so they don't fight over one tab."""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

_lock = threading.Lock()


@contextmanager
def chrome_exclusive(timeout: float = 90.0):
    got = _lock.acquire(timeout=timeout)
    if not got:
        raise TimeoutError("Chrome занят другой операцией Radar. Повторите чуть позже.")
    try:
        yield
    finally:
        _lock.release()


def chrome_busy() -> bool:
    return _lock.locked()
