"""M5-a：任务数据契约（`g_tasks` / `g_task_submissions` / `g_events`）。

冻结口径（`M5-PLAN.md` v1.0 §2/§3，用户确认）：

* **Task 不是能力判断**：`g_tasks` 不含 level / score / confidence 之类字段；
* 主缺口必填且 `open`；能力点必须 `active`（无缺口不生成任务）；
* 维度 ↔ 交付物：`understanding` 只允许 `probe_answer`；`practice` 只允许 `markdown/code/archive`；
* 交付物 → 证据类型：`markdown/code/archive → task_submission`；`probe_answer → probe_result`；
* `acceptance` 不得命中不可验收反例（"去学习 X"式）；
* `est_minutes` ∈ 10–600；同一缺口已有未关闭任务 → 不重复生成。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from growth_os.agent import GROWTH_TOOL_NAMES, ToolRegistry, register_growth_tools
from growth_os.evidence import adapter
from growth_os.store import (
    DELIVERABLE_EVIDENCE_TYPE,
    DIMENSION_DELIVERABLE_TYPES,
    TASK_ACCEPTANCE_TYPES,
    TASK_DELIVERABLE_TYPES,
    TASK_EST_MINUTES_RANGE,
    TASK_EVENT_KINDS,
    TASK_STATUSES,
    GrowthStore,
    GrowthStoreError,
)
from growth_os.store import growth_store as growth_store_module

GOAL_ID = "goal_m5a"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m5a.db"
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

        def add_gap(gap_id: str, dimension: str, severity: str = "level_gap_1") -> str:
            store.db.execute(
                "INSERT INTO g_gaps(id, user_id, goal_id, capability_id, dimension, current_level,"
                " target_level, severity, rationale, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (gap_id, "local", GOAL_ID, capability, dimension, 3 if dimension == "practice" else 2,
                 4 if dimension == "practice" else 3, severity, "测试缺口", "open"),
            )
            store.db.commit()
            return gap_id

        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "capability": capability,
            "add_gap": add_gap,
            "tmp": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def task_payload(gap_id: str, **overrides) -> dict:
    payload = {
        "gap_id": gap_id,
        "title": "写一个检索评测集",
        "objective": "产出一个 10 条样本的评测集（Markdown）",
        "deliverable_type": "markdown",
        "est_minutes": 60,
        "acceptance_type": "artifact_check",
        "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
        "generated_by_run_id": "m5a_test",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1. 表与冻结常量
# ---------------------------------------------------------------------------


def test_tables_and_frozen_vocabularies(env):
    tables = {
        row[0]
        for row in env["store"].db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"g_tasks", "g_task_submissions", "g_events"} <= tables
    assert TASK_STATUSES == ("proposed", "active", "blocked", "done", "abandoned")
    assert TASK_DELIVERABLE_TYPES == ("markdown", "code", "archive", "probe_answer")
    assert TASK_ACCEPTANCE_TYPES == ("artifact_check", "test_run", "probe_rubric")
    assert TASK_EST_MINUTES_RANGE == (10, 600)
    assert TASK_EVENT_KINDS == ("task_status_changed",)
    assert DELIVERABLE_EVIDENCE_TYPE == {
        "markdown": "task_submission",
        "code": "task_submission",
        "archive": "task_submission",
        "probe_answer": "probe_result",
    }
    assert DIMENSION_DELIVERABLE_TYPES == {
        "understanding": ("probe_answer",),
        "practice": ("markdown", "code", "archive"),
    }


def test_task_table_has_no_grade_fields():
    """Task 不是能力判断（用户约束 ①）：`g_tasks` schema 不得出现等级/分值字段。"""
    source = Path(growth_store_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    marker = "CREATE TABLE IF NOT EXISTS g_tasks"
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if marker not in node.value:
            continue
        schema = node.value.split(marker, 1)[1].split(");", 1)[0].lower()
        for forbidden in ("level", "score", "confidence", "rating"):
            assert forbidden not in schema, f"g_tasks 混入能力判断字段: {forbidden}"
        return
    raise AssertionError("未找到 g_tasks 建表语句")


# ---------------------------------------------------------------------------
# 2. 创建契约（拒绝用例）
# ---------------------------------------------------------------------------


def test_create_task_happy_path(env):
    gap = env["add_gap"]("gap_p1", "practice")
    identifier = env["store"].create_task(task_payload(gap))
    task = env["store"].get_task(identifier)
    assert task["status"] == "proposed"
    assert task["deliverable_type"] == "markdown"
    assert task["gap_id"] == gap
    assert task["capability_id"] == env["capability"]
    assert task["origin"] == "generated"


def test_create_task_requires_open_gap_and_active_capability(env):
    with pytest.raises(GrowthStoreError, match="未知缺口"):
        env["store"].create_task(task_payload("gap_missing"))

    gap = env["add_gap"]("gap_closed", "practice")
    env["store"].db.execute("UPDATE g_gaps SET status='closed' WHERE id=?", (gap,))
    env["store"].db.commit()
    with pytest.raises(GrowthStoreError, match="只对 open 缺口生成任务"):
        env["store"].create_task(task_payload(gap))

    env["store"].db.execute("UPDATE g_gaps SET status='open' WHERE id=?", (gap,))
    env["store"].db.execute(
        "UPDATE g_capabilities SET status='superseded' WHERE id=?", (env["capability"],)
    )
    env["store"].db.commit()
    with pytest.raises(GrowthStoreError, match="只对 active 能力点生成任务"):
        env["store"].create_task(task_payload(gap))


def test_dimension_deliverable_mapping_is_enforced(env):
    practice_gap = env["add_gap"]("gap_p2", "practice")
    with pytest.raises(GrowthStoreError, match="practice 缺口的交付物只允许"):
        env["store"].create_task(task_payload(practice_gap, deliverable_type="probe_answer"))

    understanding_gap = env["add_gap"]("gap_u1", "understanding")
    with pytest.raises(GrowthStoreError, match="understanding 缺口的交付物只允许"):
        env["store"].create_task(task_payload(understanding_gap, deliverable_type="markdown"))
    ok = env["store"].create_task(
        task_payload(understanding_gap, deliverable_type="probe_answer", acceptance_type="probe_rubric")
    )
    assert env["store"].get_task(ok)["deliverable_type"] == "probe_answer"


def test_unverifiable_tasks_are_rejected(env):
    gap = env["add_gap"]("gap_p3", "practice")
    with pytest.raises(GrowthStoreError, match="不可验收的表述"):
        env["store"].create_task(task_payload(gap, acceptance="去学习 Agent Evaluation"))
    with pytest.raises(GrowthStoreError, match="不可验收的表述"):
        env["store"].create_task(task_payload(gap, title="随便看看 RAG"))
    with pytest.raises(GrowthStoreError, match="验收方式"):
        env["store"].create_task(task_payload(gap, acceptance="看看"))


def test_est_minutes_and_enum_validation(env):
    gap = env["add_gap"]("gap_p4", "practice")
    with pytest.raises(GrowthStoreError, match="est_minutes"):
        env["store"].create_task(task_payload(gap, est_minutes=3))
    with pytest.raises(GrowthStoreError, match="est_minutes"):
        env["store"].create_task(task_payload(gap, est_minutes=True))
    with pytest.raises(GrowthStoreError, match="未知验收方式"):
        env["store"].create_task(task_payload(gap, acceptance_type="vibes"))
    with pytest.raises(GrowthStoreError, match="未知交付物类型"):
        env["store"].create_task(task_payload(gap, deliverable_type="ppt"))


def test_duplicate_open_task_per_gap_is_rejected(env):
    gap = env["add_gap"]("gap_p5", "practice")
    first = env["store"].create_task(task_payload(gap))
    with pytest.raises(GrowthStoreError, match="已有未关闭任务"):
        env["store"].create_task(task_payload(gap))
    env["store"].activate_task(first)
    with pytest.raises(GrowthStoreError, match="已有未关闭任务"):
        env["store"].create_task(task_payload(gap))


# ---------------------------------------------------------------------------
# 3. 提交与事件
# ---------------------------------------------------------------------------


def test_submission_rows_are_unique_and_events_are_ordered(env):
    gap = env["add_gap"]("gap_p6", "practice")
    identifier = env["store"].create_task(task_payload(gap))
    env["store"].activate_task(identifier)
    env["store"].complete_task(identifier, source_id="src_a", note="第一次提交")

    rows = env["store"].list_task_submissions(task_id=identifier)
    assert len(rows) == 1 and rows[0]["source_id"] == "src_a"

    events = env["store"].list_events(kind="task_status_changed")
    assert [(e["kind"],) for e in events] == [("task_status_changed",)] * 3
    payloads = [e["payload_json"] for e in events]
    assert '"to": "proposed"' in payloads[0]
    assert '"to": "active"' in payloads[1]
    assert '"to": "done"' in payloads[2], "事件必须按发生顺序（rowid）记录"


# ---------------------------------------------------------------------------
# 4. 工具层（ARCHITECTURE §5.3 模式 A）
# ---------------------------------------------------------------------------


def test_growth_tools_registered_and_cross_table_check(env):
    registry = register_growth_tools(
        ToolRegistry(), store=env["store"], evidence_store=env["estore"]
    )
    assert registry.names() == sorted(GROWTH_TOOL_NAMES)

    gap = env["add_gap"]("gap_p7", "practice")
    task = registry.call("create_task", **task_payload(gap))
    assert task["status"] == "proposed"
    assert [item["id"] for item in registry.call("list_gaps")] == [gap]

    env["store"].activate_task(task["id"])
    with pytest.raises(ValueError, match="source_id 不在证据库中"):
        registry.call("complete_task", task_id=task["id"], source_id="src_not_exists")

    target = env["tmp"] / "submission.md"
    target.write_text("# 评测集\n\n10 条样本\n", encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type="task_submission", attribution="user_declared"
    )
    result = registry.call("complete_task", task_id=task["id"], source_id=ingested.source_id)
    assert result["status"] == "done"
    assert env["store"].get_task(task["id"])["status"] == "done"
