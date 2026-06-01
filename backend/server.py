from __future__ import annotations

import os
from typing import Any

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_react_app(app: Any, *, react_dist_dir: str, logger: Any = None) -> None:
    dist_dir = os.path.abspath(react_dist_dir)
    index_html = os.path.join(dist_dir, "index.html")
    assets_dir = os.path.join(dist_dir, "assets")
    index_headers = {"Cache-Control": "no-store"}
    if not os.path.exists(index_html):
        if logger:
            logger.warning(f"React dist not found at {dist_dir}; API will run without static UI.")
        return
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="react-assets")

    @app.get("/")
    async def react_index():
        return FileResponse(index_html, headers=index_headers)

    @app.get("/{full_path:path}")
    async def react_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            return {"error": "Not found"}
        return FileResponse(index_html, headers=index_headers)


def start_app_server(app: Any, *, host: str, port: int) -> None:
    uv_config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(uv_config)
    server.run()
