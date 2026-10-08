"""独立首次使用实验：目标澄清、显式确认与手动能力树生成。"""

import argparse
import asyncio
import hashlib
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..agent import AgentRuntime, FakeGateway
from ..assessment import BINDING_TASK, TaskLoop
from ..assessment.pipeline import assess_capability
from ..evidence import adapter
from ..goal import MAX_ROUNDS, GoalAgent, GoalStateError
from ..goal.capability_model import CapabilityModelGenerator, CapabilityTreeShapeError
from ..store import GrowthStore
from ..store.submission_journal import SubmissionJournal
from ..tasks.generator import TaskGenerator
from .interactive import ORIGINS, create_interactive_app
from .materials import register_material_routes
from .mentor import register_mentor_routes
from .product_actions import register_product_actions

DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "onboarding"
QUESTIONS = {
    "direction": "你希望发展的具体方向是什么？",
    "purpose": "这个目标主要为了什么？",
    "horizon": "你准备在多长时间内达成？",
    "measurable_result": "你希望产出什么可以核对的成果？",
}


def template_tree():
    """仅用于演示结构，不声称适配用户目标或提供经过验证的等级。"""
    nodes = []
    for domain, groups in {
        "目标基础": {"概念梳理": ["术语整理", "关系说明"], "资料阅读": ["来源记录", "观点对照"]},
        "实践交付": {"方案设计": ["需求描述", "步骤规划"], "成果制作": ["原型制作", "成果整理"]},
        "验证复盘": {"成果核对": ["验收条件", "结果检查"], "过程复盘": ["问题记录", "改进计划"]},
    }.items():
        for path in [domain, *[f"{domain}/{group}" for group in groups],
                     *[f"{domain}/{group}/{leaf}" for group, leaves in groups.items() for leaf in leaves]]:
            parts = path.split("/")
            nodes.append({"path": path, "name": parts[-1], "depth": len(parts),
                          "parent_path": "/".join(parts[:-1]) or None, "target_level": 3,
                          "source_note": "固定结构演示模板；尚未核对与目标的相关性；目标等级为占位值"})
    return {"nodes": nodes}


class StartGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=4000)


class AnswerGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round: int = Field(ge=1, le=MAX_ROUNDS)
    text: str = Field(min_length=1, max_length=4000)


class ConfirmGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str = Field(min_length=1, max_length=4000)


class PlanTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension: Literal["understanding", "practice"]


def journey_gateway(store, evidence_store):
    def bind(index, system, user):
        claim_id = re.search(r"clm_[0-9a-f]{6,}", user).group(0)
        entry = next(item for item in adapter.claims_overview(evidence_store) if item["claim"]["id"] == claim_id)
        task_ids = {item["source"]["metadata"].get("growth_task_id") for item in entry["evidence"]}
        task_ids.discard(None)
        if len(task_ids) != 1:
            raise ValueError("缺少唯一任务来源")
        task = store.get_task(task_ids.pop())
        capability = store.get_capability(task["capability_id"])
        return {"proposals": [{"claim_id": claim_id, "capability_path": capability["path"],
                               "rationale": "固定实验规则：按任务来源关联能力点，未判断回答或产物质量"}]}

    return FakeGateway(responses={BINDING_TASK: bind})


def create_onboarding_app(store, *, gateway=None, evidence_store=None, journal=None, directory=None, material_journal=None, conversations=None, mentor_gateway=None):
    lock = asyncio.Lock()
    action_store = None
    if evidence_store is not None and journal is not None:
        loop = TaskLoop(store=store, evidence_store=evidence_store,
                        gateway=gateway or journey_gateway(store, evidence_store),
                        submission_dir=Path(directory) / "submissions", report_directory=Path(directory) / "reports")
        app = create_interactive_app(store, evidence_store, task_loop=loop, journal=journal, operation_lock=lock)
    else:
        app = FastAPI()
    app.title = "Growth OS Onboarding Experiment"
    if conversations is not None:
        register_mentor_routes(app, store=store, evidence_store=evidence_store, conversations=conversations,
                               gateway=mentor_gateway or gateway, lock=lock)
    if material_journal is not None:
        register_material_routes(app, store=store, evidence_store=evidence_store, journal=material_journal,
                                 directory=directory, lock=lock)

    def snapshot(goal_id):
        goal = store.get_goal(goal_id)
        if goal is None or goal["user_id"] != "local":
            raise HTTPException(404, "目标不存在")
        history = store.list_clarifications(goal_id)
        pending = next((item for item in reversed(history) if not item["answer"]), None)
        return {"goal": goal, "history": history, "pending": pending,
                "rounds_left": max(0, MAX_ROUNDS - len(history)),
                "needs_retry": goal["status"] in ("draft", "clarifying") and pending is None,
                "capabilities": store.list_capabilities(goal_id),
                "mode": "model" if gateway else "fixed_questions",
                "revision_of": action_store.parent_of(goal_id) if action_store else None}

    def agent(goal_id):
        def proposal(index, system, user):
            history = store.list_clarifications(goal_id)
            elements = {field: next((item["answer"] for item in history
                                    if item["question"] == question and item["answer"]), None)
                        for field, question in QUESTIONS.items()}
            missing = next((field for field in QUESTIONS if not elements[field]), None)
            return {"question": QUESTIONS[missing] if missing else "请核对四要素，并填写你的确认原话。",
                    "proposed": elements, "ready_to_confirm": missing is None}

        configured = gateway or FakeGateway(responses={"goal_clarification": proposal})
        return GoalAgent(store=store, runtime=AgentRuntime(store=store, gateway=configured, agent="goal"))

    if conversations is not None:
        action_store = register_product_actions(app, store=store, snapshot=snapshot, agent=agent, lock=lock)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.method == "POST" and request.headers.get("origin") not in (None, *ORIGINS):
            return JSONResponse(status_code=403, content={"detail": "仅允许本地页面操作"})
        return await call_next(request)

    @app.get("/api/onboarding")
    async def sessions():
        return {"mode": "model" if gateway else "fixed_questions", "goals": store.list_goals(),
                "max_rounds": MAX_ROUNDS}

    @app.get("/api/onboarding/goals/{goal_id}")
    async def state(goal_id: str):
        return snapshot(goal_id)

    async def change(goal_id, operation):
        if lock.locked():
            raise HTTPException(409, "目标正在处理，请稍后重试")
        async with lock:
            try:
                await operation()
            except GoalStateError as error:
                raise HTTPException(409, str(error)) from error
            except Exception as error:
                raise HTTPException(502, "提问失败，已保留目标和已答内容；请刷新后手动恢复提问") from error
            return snapshot(goal_id)

    @app.post("/api/onboarding/goals")
    async def start(payload: StartGoal):
        if not payload.text.strip():
            raise HTTPException(422, "请填写目标")
        goal_id = "goal_" + hashlib.sha256(payload.request_id.encode()).hexdigest()[:24]
        previous = store.get_goal(goal_id)
        if previous:
            if previous["title"] != payload.text.strip():
                raise HTTPException(409, "请求标识已用于其他目标")
            return snapshot(goal_id)
        return await change(goal_id, lambda: agent(goal_id).start(payload.text, goal_id=goal_id))

    @app.post("/api/onboarding/goals/{goal_id}/answers")
    async def answer(goal_id: str, payload: AnswerGoal):
        current = snapshot(goal_id)
        previous = next((item for item in current["history"] if item["round"] == payload.round), None)
        if previous and previous["answer"]:
            if previous["answer"] != payload.text.strip():
                raise HTTPException(409, "该轮已记录其他回答")
            return current
        if not payload.text.strip():
            raise HTTPException(422, "请填写回答")
        if current["goal"]["status"] != "clarifying" or not current["pending"] or current["pending"]["round"] != payload.round:
            raise HTTPException(409, "问题已改变，请刷新后回答")
        return await change(goal_id, lambda: agent(goal_id).answer(goal_id, payload.text))

    @app.post("/api/onboarding/goals/{goal_id}/resume")
    async def resume(goal_id: str):
        snapshot(goal_id)
        return await change(goal_id, lambda: agent(goal_id).resume(goal_id))

    @app.post("/api/onboarding/goals/{goal_id}/confirm")
    async def confirm(goal_id: str, payload: ConfirmGoal):
        current = snapshot(goal_id)
        if current["goal"]["status"] == "confirmed":
            if current["goal"]["source_quote"] != payload.quote.strip():
                raise HTTPException(409, "该目标已用其他原话确认")
            return current

        async def commit():
            agent(goal_id).confirm(goal_id, quote=payload.quote)

        return await change(goal_id, commit)

    @app.post("/api/onboarding/goals/{goal_id}/capabilities")
    async def generate_capabilities(goal_id: str):
        snapshot(goal_id)
        if lock.locked():
            raise HTTPException(409, "目标正在处理，请稍后重试")
        async with lock:
            current = snapshot(goal_id)
            if current["goal"]["status"] != "confirmed":
                raise HTTPException(409, "请先确认目标")
            if current["capabilities"]:
                return current
            configured = gateway or FakeGateway(responses={"capability_model": template_tree()})
            try:
                await CapabilityModelGenerator(store=store, gateway=configured).generate(goal_id)
            except CapabilityTreeShapeError as error:
                raise HTTPException(422, "能力树结构未通过校验，未保存；可手动重试") from error
            except Exception as error:
                raise HTTPException(502, "能力生成未完成，请刷新核对保存状态后手动重试") from error
            return snapshot(goal_id)

    @app.post("/api/onboarding/goals/{goal_id}/capabilities/{capability_id}/tasks")
    async def plan_task(goal_id: str, capability_id: str, payload: PlanTask):
        current = snapshot(goal_id)
        capability = store.get_capability(capability_id)
        if capability is None or capability["goal_id"] != goal_id:
            raise HTTPException(404, "目标能力点不存在")
        if current["goal"]["status"] != "confirmed" or capability["depth"] != 3 or capability["status"] != "active":
            raise HTTPException(409, "仅允许已确认目标中的有效能力点")
        if evidence_store is None or journal is None:
            raise HTTPException(503, "证据与任务服务未配置")
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            assessment = assess_capability(store, evidence_store, capability_id=capability_id)
            gaps = [gap for gap in store.list_gaps(capability_id=capability_id, status="open")
                    if gap["dimension"] == payload.dimension]
            if not gaps:
                raise HTTPException(409, "该维度当前没有可生成任务的缺口")
            gap = gaps[0]
            existing = [task for task in store.list_tasks() if task["gap_id"] == gap["id"]
                        and task["status"] in ("proposed", "active", "blocked")]
            if existing:
                return {"task": existing[0], "assessment": assessment, "replayed": True}
            practice = payload.dimension == "practice"
            proposal = {"title": f"{'产物' if practice else '理解'}证据：{capability['name']}",
                        "objective": f"围绕{capability['path']}提交可核对的{'Markdown产物及验证记录' if practice else '概念说明、具体例子与局限'}",
                        "deliverable_type": "markdown" if practice else "probe_answer", "est_minutes": 30,
                        "acceptance_type": "artifact_check" if practice else "probe_rubric",
                        "acceptance": "提交包含具体内容、核对步骤与局限的记录；固定模板未判断质量"}
            configured = gateway or FakeGateway(responses={"task_generation": proposal})
            try:
                result = await TaskGenerator(store=store, gateway=configured, goal_id=goal_id).propose(gap["id"])
            except Exception as error:
                raise HTTPException(502, "任务提议未完成，评定记录已保留；请手动重试") from error
            decision = result["decisions"][0]
            if not decision["accepted"]:
                raise HTTPException(422, "任务提议未通过闸门，未创建任务")
            return {"task": store.get_task(decision["task_id"]), "assessment": assessment, "replayed": False}

    app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    return app


def seed_onboarding(directory):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "onboarding.db"
    if database.exists():
        raise ValueError("实验库已存在，不覆盖原数据")
    with GrowthStore(str(database)) as store:
        store.upsert_user("local", "首次使用实验用户")
    (directory / "manifest.json").write_text(json.dumps({"onboarding_enabled": True}), encoding="utf-8")


def create_local_onboarding_app():
    directory = Path(os.getenv("GROWTH_ONBOARDING_DIRECTORY", str(DIRECTORY))).resolve()
    manifest = directory / "manifest.json"
    if not (directory / "onboarding.db").is_file() or not manifest.is_file():
        raise RuntimeError("请先运行 python -m growth_os.api.onboarding")
    if json.loads(manifest.read_text(encoding="utf-8")).get("onboarding_enabled") is not True:
        raise RuntimeError("仅接受独立首次使用实验库")
    # 请求账本同时持有进程锁并保存任务提交结果；目标问答由领域状态核验幂等性。
    lease = SubmissionJournal(directory / "service-lock.db")
    store = GrowthStore(str(directory / "onboarding.db"))
    evidence = adapter.open_store(directory / "onboarding.db")
    materials = SubmissionJournal(directory / "material-requests.db")
    gateway = adapter.agent_gateway() if os.getenv("GROWTH_ONBOARDING_REAL_MODEL") == "1" else None
    app = create_onboarding_app(store, gateway=gateway, evidence_store=evidence, journal=lease,
                                material_journal=materials, directory=directory)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            store.close()
            evidence.db.close()
            lease.close()
            materials.close()

    app.router.lifespan_context = lifespan
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建独立首次使用实验库")
    parser.add_argument("--directory", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    seed_onboarding(args.directory)
    print(str(args.directory.resolve()))
