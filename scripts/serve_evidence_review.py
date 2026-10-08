"""仅用于浏览器验收：独立受控夹具与真实只读API，不修改产品数据。"""

import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from fastapi.middleware.cors import CORSMiddleware
from growth_os.api import create_app
from test_assessment_report import add_claim, add_refuting_evidence, bind, env, inject_attack, rate


def create_review_fixture():
    scratch = tempfile.TemporaryDirectory(prefix="evidence-review-", dir=ROOT / "tmp")
    fixture = env.__wrapped__(Path(scratch.name))
    state = next(fixture)
    capability = state["add_capability"]("受控攻击复核场景")
    keep = add_claim(state, filename="keep.md", content="# 受控项目\n\n实现检索。\n", evidence_type="repo_artifact")
    broken = add_claim(state, filename="broken.md", content="# 受控项目\n\n实现重排。\n", evidence_type="repo_artifact")
    bind(state, capability, keep)
    bind(state, capability, broken)
    add_refuting_evidence(state, keep)
    inject_attack(state, broken, "broken")
    rate(state, capability)
    state["store"].apply_assessment_levels(capability)
    state["add_capability"]("受控无攻击场景")
    app = create_app(state["store"], state["estore"])
    app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:4173"], allow_methods=["GET"])

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            fixture.close()
            scratch.cleanup()

    app.router.lifespan_context = lifespan
    return app
