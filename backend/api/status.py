from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Request


def create_router(
    *,
    require_admin_user: Callable[[Request], tuple[Any, Any]],
    build_runtime_status: Callable[[], dict],
    sanitize_for_json: Callable[[Any], Any],
    get_last_trace: Callable[[], Any],
    flush_trace_log: Callable[[], None],
    current_trace_log_file: Callable[[], str],
    tail_text_file: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/trace")
    async def trace():
        return sanitize_for_json(get_last_trace())

    @router.get("/api/status")
    async def status():
        return build_runtime_status()

    @router.get("/api/status/log-tail")
    async def status_log_tail(req: Request, lines: int = Query(200, ge=20, le=1000)):
        _, error = require_admin_user(req)
        if error:
            return error

        flush_trace_log()
        tail = tail_text_file(current_trace_log_file(), max_lines=lines)
        return {
            "path": tail.path,
            "exists": tail.exists,
            "sizeBytes": tail.size_bytes,
            "lines": tail.lines,
            "truncated": tail.truncated,
            "error": tail.error,
            "lineCount": len(tail.lines),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

    return router
