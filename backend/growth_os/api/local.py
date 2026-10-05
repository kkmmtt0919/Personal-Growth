"""本地只读服务入口；Demo 数据需事先通过独立种子命令创建。"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.middleware.cors import CORSMiddleware

from ..demo import DEMO_DIRECTORY
from ..evidence import adapter
from ..store import GrowthStore
from .app import create_app


def create_local_app():
    directory = Path(os.getenv("GROWTH_DEMO_DIRECTORY", str(DEMO_DIRECTORY))).resolve()
    database = directory / "demo.db"
    manifest_file = directory / "manifest.json"
    if not database.is_file() or not manifest_file.is_file():
        raise RuntimeError("Demo 未就绪，请先运行 python -m growth_os.demo")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("constructed") is not True:
        raise RuntimeError("仅接受受控 Demo 数据")
    store = GrowthStore(str(database))
    evidence = adapter.open_store(database)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            evidence.db.close()
            store.close()

    return_context = manifest.get("return_context")
    if return_context:
        return_context = {**return_context, "goal_id": manifest["goal_id"]}
    app = create_app(store, evidence, loop_reports=manifest["loop_reports"],
                     return_context=return_context)
    app.router.lifespan_context = lifespan
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4173", "http://127.0.0.1:4173",
                       "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"], allow_headers=[],
    )
    return app
