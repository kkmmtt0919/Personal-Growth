"""M5-b：任务生成器（`gap → LLM 提议 → 七步闸门 → g_tasks(proposed)`）。

冻结口径（用户 2026-10-03，`M5-PLAN.md` v1.0 §4）：

* proposal schema 七字段、`extra="forbid"`；**禁止能力判断与排序字段**
  （expected_level / confidence / difficulty_score / priority / learning_value / level / score / rating）；
* 七步闸门固定顺序：schema → gap_taskable → deliverable_allowed → acceptance_verifiable
  → est_minutes_range → duplicate → persisted；
* **adjustment 只允许 `est_minutes` 形式夹取**（不改写 title/objective/acceptance）；
* **declined 是运行结果、不是任务状态**（不落 `g_tasks`）；
* **Generator 不直接拥有 create_task 权限**（唯一写库在闸门第 7 步；新增行数 == accepted 数）；
* provenance：闸门第 2 步强制缺口有 `assessment_id`。
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import growth_os.tasks.gate as gate_module
import growth_os.tasks.generator as generator_module
import pytest
from growth_os.agent import FakeGateway
from growth_os.assessment import assess_capability
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from growth_os.tasks import (
    DECLINED_STAGE,
    FORBIDDEN_TASK_FIELDS,
    TASK_GATE_STAGES,
    TASK_GENERATION_TASK,
    TaskGate,
    TaskGenerationError,
    TaskGenerator,
    TaskProposal,
)
from pydantic import ValidationError

GOAL_ID = "goal_m5b"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m5b.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
        store.upsert_user("local", "本地用户")
        store.save_goal(
            {
                "id": GOAL_ID,
                "user_id": "local",
                "title": "成为 AI Agent 工程师",
                "direction": "AI 应用方向",
                "purpose": "求职",
                "horizon": "6 个月",
                "measurable_result": "完成一个可演示的 RAG 项目",
                "status": "confirmed",
                "source_quote": "我想成为 AI Agent 工程师",
            }
        )
        domain = store.upsert_capability(
            {"goal_id": GOAL_ID, "path": "AI Agent", "name": "AI Agent", "depth": 1, "target_level": 3}
        )
        group = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "AI Agent/工具与执行",
                "name": "工具与执行",
                "depth": 2,
                "parent_id": domain,
                "target_level": 3,
            }
        )
        capability = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "AI Agent/工具与执行/RAG",
                "name": "RAG",
                "depth": 3,
                "parent_id": group,
                "target_level": 4,
            }
        )

        def add_claim(filename: str, content: str, evidence_type: str) -> str:
            target = tmp_path / filename
            target.write_text(content, encoding="utf-8")
            ingested = adapter.ingest_document(
                target, store=estore, evidence_type=evidence_type, attribution="user_declared"
            )
            passage_ids = [item.id for item in estore.get_passages(source_id=ingested.source_id)]
            return adapter.create_material_claim(
                estore,
                subject="材料",
                predicate="包含",
                object="相关内容",
                statement=f"材料中包含相关内容（{filename}）",
                passage_ids=passage_ids[:1],
            )["claim_id"]

        notes = add_claim("notes.md", "# 笔记\n\nRAG 检索流程整理。\n", "uploaded_doc")
        repo = add_claim("repo.md", "# 项目\n\n实现了 RAG 检索服务。\n", "repo_artifact")
        for claim in (notes, repo):
            store.link_capability_claim(capability, claim, role="supports", rationale="测试绑定")

        def make_gaps() -> dict:
            session = assess_capability(store, estore, capability_id=capability)
            gaps = {
                item["dimension"]: item
                for item in store.list_gaps(capability_id=capability, status="open")
            }
            return {"session": session, "practice": gaps["practice"], "understanding": gaps["understanding"]}

        yield {
            "store": store,
            "estore": estore,
            "capability": capability,
            "make_gaps": make_gaps,
            "tmp": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def good_proposal(**overrides) -> dict:
    payload = {
        "title": "写一个 10 条样本的检索评测集",
        "objective": "产出一份 Markdown 评测集，覆盖 10 条检索样本",
        "deliverable_type": "markdown",
        "est_minutes": 60,
        "acceptance_type": "artifact_check",
        "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
    }
    payload.update(overrides)
    return payload


def run_gate(env, gap_id: str, proposal: dict, *, index: int = 0):
    gate = TaskGate(store=env["store"], goal_id=GOAL_ID)
    return gate.evaluate(proposal, gap_id=gap_id, run_id="m5b_test", index=index, proposer="test")


# ---------------------------------------------------------------------------
# 1. schema 与禁止字段
# ---------------------------------------------------------------------------


def test_gate_stage_list_is_frozen():
    assert TASK_GATE_STAGES == (
        "schema",
        "gap_taskable",
        "deliverable_allowed",
        "acceptance_verifiable",
        "est_minutes_range",
        "duplicate",
        "persisted",
    )


@pytest.mark.parametrize("field", FORBIDDEN_TASK_FIELDS)
def test_forbidden_fields_are_rejected(field):
    payload = good_proposal(**{field: 1})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        TaskProposal.model_validate(payload)


def test_forbidden_names_live_only_in_the_constant():
    """静态检查：禁止字段名只允许出现在 `FORBIDDEN_TASK_FIELDS` 常量里（用户约束 ①③）。"""
    for module in (gate_module, generator_module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        constant_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "FORBIDDEN_TASK_FIELDS"
                for target in node.targets
            ):
                constant_node = node
        allowed_lines = set()
        if constant_node is not None:
            allowed_lines = set(range(constant_node.lineno, constant_node.end_lineno + 1))
        lines = source.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for name in FORBIDDEN_TASK_FIELDS:
                if f'"{name}"' in line or f"'{name}'" in line:
                    assert line_no in allowed_lines, (
                        f"{module.__name__}:{line_no} 出现禁止字段 {name}（只允许在 FORBIDDEN_TASK_FIELDS）"
                    )


def test_proposal_class_has_no_forbidden_fields():
    fields = set(TaskProposal.model_fields)
    assert fields == {
        "title",
        "objective",
        "deliverable_type",
        "est_minutes",
        "acceptance_type",
        "acceptance",
        "decline_reason",
    }
    assert not (fields & set(FORBIDDEN_TASK_FIELDS))


# ---------------------------------------------------------------------------
# 2. 七步闸门逐步对例
# ---------------------------------------------------------------------------


def test_happy_path_persists_task(env):
    gaps = env["make_gaps"]()
    before = len(env["store"].list_tasks())
    decision = run_gate(env, gaps["practice"]["id"], good_proposal())
    assert decision.accepted is True
    assert decision.gate_stage == "persisted"
    assert list(decision.stages_passed) == list(TASK_GATE_STAGES)
    assert decision.adjustment_note is None
    task = env["store"].get_task(decision.task_id)
    assert task["status"] == "proposed"
    assert task["gap_id"] == gaps["practice"]["id"]
    assert task["generated_by_run_id"] == "m5b_test"
    assert len(env["store"].list_tasks()) == before + 1


def test_schema_stage_rejects_extra_field(env):
    gaps = env["make_gaps"]()
    decision = run_gate(env, gaps["practice"]["id"], good_proposal(confidence=0.9))
    assert decision.accepted is False
    assert decision.gate_stage == "schema"
    assert "schema 不合法" in decision.reject_reason
    assert env["store"].list_tasks() == []


def test_gap_taskable_stage(env):
    gaps = env["make_gaps"]()
    unknown = run_gate(env, "gap_missing", good_proposal())
    assert unknown.gate_stage == "gap_taskable" and "未知缺口" in unknown.reject_reason

    gap_id = gaps["practice"]["id"]
    env["store"].db.execute("UPDATE g_gaps SET status='closed' WHERE id=?", (gap_id,))
    env["store"].db.commit()
    closed = run_gate(env, gap_id, good_proposal())
    assert closed.gate_stage == "gap_taskable" and "status=closed" in closed.reject_reason

    env["store"].db.execute("UPDATE g_gaps SET status='open' WHERE id=?", (gap_id,))
    env["store"].db.execute(
        "UPDATE g_capabilities SET status='superseded' WHERE id=?", (env["capability"],)
    )
    env["store"].db.commit()
    inactive = run_gate(env, gap_id, good_proposal())
    assert inactive.gate_stage == "gap_taskable" and "非 active" in inactive.reject_reason

    env["store"].db.execute(
        "UPDATE g_capabilities SET status='active' WHERE id=?", (env["capability"],)
    )
    env["store"].db.execute("UPDATE g_gaps SET assessment_id=NULL WHERE id=?", (gap_id,))
    env["store"].db.commit()
    no_provenance = run_gate(env, gap_id, good_proposal())
    assert no_provenance.gate_stage == "gap_taskable"
    assert "provenance 不完整" in no_provenance.reject_reason


def test_deliverable_and_acceptance_stages(env):
    gaps = env["make_gaps"]()
    practice = gaps["practice"]["id"]
    mismatch = run_gate(env, practice, good_proposal(deliverable_type="probe_answer"))
    assert mismatch.gate_stage == "deliverable_allowed"

    short = run_gate(env, practice, good_proposal(acceptance="看情况"))
    assert short.gate_stage == "acceptance_verifiable"

    literal = run_gate(env, practice, good_proposal(acceptance="去学习 Agent Evaluation"))
    assert literal.gate_stage == "acceptance_verifiable"
    assert "去学习" in literal.reject_reason

    understanding = gaps["understanding"]["id"]
    ok = run_gate(
        env,
        understanding,
        good_proposal(
            title="现场作答：RAG 检索流程",
            objective="产出一份现场作答记录",
            deliverable_type="probe_answer",
            acceptance_type="probe_rubric",
            acceptance="提交作答正文，按要点核对流程完整性",
        ),
    )
    assert ok.accepted is True


# ---------------------------------------------------------------------------
# 3. adjustment：只做形式夹取
# ---------------------------------------------------------------------------


def test_est_minutes_is_clamped_not_rejected(env):
    gaps = env["make_gaps"]()
    low = run_gate(env, gaps["practice"]["id"], good_proposal(est_minutes=5))
    assert low.accepted is True
    assert low.adjustment_note == "est_minutes clamped 5→10"
    assert env["store"].get_task(low.task_id)["est_minutes"] == 10

    # 同一缺口已有未关闭任务 → 再生成被 duplicate 拦下（同时验证高位夹取前的路径）
    high = run_gate(env, gaps["practice"]["id"], good_proposal(est_minutes=900))
    assert high.gate_stage == "duplicate"


def test_gate_never_rewrites_text(env):
    """闸门不发明内容：不可验收的表述只被拒绝，不被"润色"。"""
    gaps = env["make_gaps"]()
    decision = run_gate(env, gaps["practice"]["id"], good_proposal(objective="了解一下 RAG 检索"))
    assert decision.accepted is False
    assert decision.gate_stage == "acceptance_verifiable"
    assert env["store"].list_tasks() == []


# ---------------------------------------------------------------------------
# 4. duplicate 与 decline
# ---------------------------------------------------------------------------


def test_duplicate_predicate(env):
    gaps = env["make_gaps"]()
    gap_id = gaps["practice"]["id"]
    first = run_gate(env, gap_id, good_proposal())
    assert first.accepted

    duplicate = run_gate(env, gap_id, good_proposal(title="另一个评测集", objective="产出第二版评测集"))
    assert duplicate.gate_stage == "duplicate"
    assert first.task_id in duplicate.reject_reason

    # done / abandoned 不算重复 → 可再生成
    env["store"].activate_task(first.task_id)
    env["store"].complete_task(first.task_id, source_id="src_x")
    second = run_gate(env, gap_id, good_proposal(title="第二版评测集", objective="产出第二版检索评测集"))
    assert second.accepted is True
    assert second.task_id != first.task_id


def test_decline_records_reason_without_task(env):
    gaps = env["make_gaps"]()
    decision = run_gate(
        env,
        gaps["practice"]["id"],
        good_proposal(decline_reason="该缺口无法在当前材料下设计可验收任务"),
    )
    assert decision.accepted is False
    assert decision.gate_stage == DECLINED_STAGE
    assert "无法在当前材料下设计可验收任务" in decision.reject_reason
    assert env["store"].list_tasks() == []


# ---------------------------------------------------------------------------
# 5. Generator：不直接写库 + 每缺口一次调用
# ---------------------------------------------------------------------------


def test_generator_proposes_through_the_gate(env):
    gaps = env["make_gaps"]()
    gateway = FakeGateway(responses={TASK_GENERATION_TASK: TaskProposal.model_validate(good_proposal())})
    generator = TaskGenerator(store=env["store"], gateway=gateway, goal_id=GOAL_ID, id_factory=lambda: "run_m5b_1")
    report = asyncio.run(generator.propose(gaps["practice"]["id"]))

    assert report["run_id"] == "run_m5b_1"
    assert report["provider"] == "fake" and report["model"]
    assert len(report["decisions"]) == 1
    decision = report["decisions"][0]
    assert decision["accepted"] is True
    assert env["store"].get_task(decision["task_id"])["status"] == "proposed"
    runs = env["store"].list_runs(agent="task_generation")
    assert runs and runs[0]["model_source"] == "result" and runs[0]["status"] == "ok"


def test_generator_rejects_unknown_gap(env):
    gateway = FakeGateway(responses={TASK_GENERATION_TASK: TaskProposal.model_validate(good_proposal())})
    generator = TaskGenerator(store=env["store"], gateway=gateway, goal_id=GOAL_ID)
    with pytest.raises(TaskGenerationError, match="未知缺口"):
        asyncio.run(generator.propose("gap_missing"))


def test_propose_many_is_one_call_per_gap(env):
    gaps = env["make_gaps"]()

    def responder(index: int, system: str, user: str) -> TaskProposal:
        if "probe_answer" in user and "现场作答" in user:
            return TaskProposal.model_validate(
                good_proposal(
                    title="现场作答：RAG 检索流程",
                    objective="产出一份现场作答记录",
                    deliverable_type="probe_answer",
                    acceptance_type="probe_rubric",
                    acceptance="提交作答正文，按要点核对流程完整性",
                )
            )
        return TaskProposal.model_validate(good_proposal())

    gateway = FakeGateway(responses={TASK_GENERATION_TASK: responder})
    generator = TaskGenerator(store=env["store"], gateway=gateway, goal_id=GOAL_ID)
    report = asyncio.run(generator.propose_many([gaps["practice"]["id"], gaps["understanding"]["id"]]))
    assert len(report["decisions"]) == 2
    assert all(item["accepted"] for item in report["decisions"])
    assert len(env["store"].list_tasks()) == 2
    assert len(env["store"].list_runs(agent="task_generation")) == 2


def test_new_task_rows_equal_accepted_count(env):
    """写入不变式：本运行新增 `g_tasks` 行数 == accepted 数（LLM 无直接落库路径）。"""
    gaps = env["make_gaps"]()
    before = len(env["store"].list_tasks())
    decisions = [
        run_gate(env, gaps["practice"]["id"], good_proposal(), index=0),
        run_gate(env, gaps["practice"]["id"], good_proposal(confidence=0.9), index=1),
        run_gate(env, gaps["understanding"]["id"], good_proposal(deliverable_type="code"), index=2),
    ]
    accepted = sum(1 for item in decisions if item.accepted)
    assert len(env["store"].list_tasks()) - before == accepted
