"""单用户本地产品入口：空库自动初始化，默认真实网关，Demo须显式选择。"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from ..agent import FakeGateway
from ..evidence import adapter
from ..store import GrowthStore
from ..store.mentor_store import MentorStore
from ..store.submission_journal import SubmissionJournal
from .onboarding import create_onboarding_app, seed_onboarding

ROOT = Path(__file__).resolve().parents[3]


def load_model_environment(path):
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().partition("=")
        if not separator or not key.startswith(("EVKG_", "GROWTH_AGENT_")):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)


def create_product_app(store, evidence_store, journal, material_journal, directory, *, gateway=None):
    configured = gateway or adapter.agent_gateway()
    demo = isinstance(configured, FakeGateway)
    conversations = MentorStore(store.db)
    mentor_gateway = configured
    if demo and "mentor_chat" not in configured.responses:
        configured.responses["mentor_chat"] = {"answer": "离线演示：导师会读取当前目标、能力与证据。这里未调用真实模型，请在真实模式继续。", "references": []}
    app = create_onboarding_app(store, gateway=None if demo else configured, evidence_store=evidence_store,
        journal=journal, material_journal=material_journal, directory=directory,
        conversations=conversations, mentor_gateway=mentor_gateway)
    app.title = "Growth OS"

    @app.get("/api/product")
    async def product():
        provider, model = configured.describe()
        return {"enabled": True, "mode": "demo" if demo else "model", "provider": provider, "model": model,
                "configured": demo or bool(os.getenv("GROWTH_AGENT_API_KEY") or os.getenv("EVKG_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
                "goals": store.list_goals(), "single_user": True}

    @app.get("/api/product/goals/{goal_id}/overview")
    async def overview(goal_id: str):
        from fastapi import HTTPException

        goal = store.get_goal(goal_id)
        if goal is None or goal["user_id"] != "local":
            raise HTTPException(404, "目标不存在")
        rows = [row for row in store.list_capabilities(goal_id, status="active") if row["depth"] == 3]
        tasks = [row for row in store.list_tasks() if row["goal_id"] == goal_id]
        gaps = [row for row in store.list_gaps(status="open") if row["goal_id"] == goal_id]
        return {"goal": goal, "capabilities": [{"id": row["id"], "name": row["name"], "path": row["path"],
            "target_level": row["target_level"], "understanding": row["current_level_understanding"],
            "practice": row["current_level_practice"], "open_gaps": [{"dimension": gap["dimension"], "severity": gap["severity"]}
                for gap in gaps if gap["capability_id"] == row["id"]]} for row in rows],
            "tasks": tasks, "gaps": gaps, "history": store.list_assessments(goal_id=goal_id)}

    return app


def create_local_product_app():
    load_model_environment(ROOT / ".env")
    directory = Path(os.getenv("GROWTH_PRODUCT_DIRECTORY", str(ROOT / "data/product"))).resolve()
    if not (directory / "onboarding.db").is_file():
        seed_onboarding(directory)
    manifest = directory / "manifest.json"
    if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8")).get("onboarding_enabled") is not True:
        raise RuntimeError("产品目录缺少初始化记录；不接管其他数据库")
    journal = SubmissionJournal(directory / "service-lock.db")
    materials = SubmissionJournal(directory / "material-requests.db")
    store = GrowthStore(str(directory / "onboarding.db"))
    evidence = adapter.open_store(directory / "onboarding.db")
    gateway = FakeGateway() if os.getenv("GROWTH_PRODUCT_DEMO") == "1" else adapter.agent_gateway()
    app = create_product_app(store, evidence, journal, materials, directory, gateway=gateway)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            evidence.db.close()
            store.close()
            materials.close()
            journal.close()

    app.router.lifespan_context = lifespan
    return app
