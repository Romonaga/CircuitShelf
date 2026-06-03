from __future__ import annotations

import faulthandler
import sys


def enable_native_fault_diagnostics() -> None:
    """Emit Python stack traces for native crashes such as SIGSEGV."""
    try:
        faulthandler.enable(file=sys.stderr, all_threads=True)
    except Exception:
        # Diagnostics should never prevent the app from starting.
        return
