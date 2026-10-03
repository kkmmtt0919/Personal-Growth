"""M5-a：任务状态机（`proposed → active → blocked/done/abandoned`）。

冻结口径（`M5-PLAN.md` v1.0 §5）：

* 合法转移表写死；非法转移报错（不静默兜底）；
* **`done` 唯一入口 = `complete_task`**（提交即完成）；M5-c 起应用层唯一提交入口是
  `TaskLoop.complete_task`（收提交物；`source_id` 由证据链内部产生，不属于调用契约）；
* `blocked` / `abandoned` 必填 reason；`done` / `abandoned` 是终态；
* 每次转移写 `g_events`（`kind=task_status_changed`，含 from/to/reason）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from growth_os.agent import ToolRegistry, register_growth_tools
from growth_os.evidence import adapter
from growth_os.store import TASK_TRANSITIONS, GrowthStore, GrowthStoreError
from growth_os.store import growth_store as growth_store_module

GOAL_ID = "goal_m5a_sm"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m5a-sm.db"
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
        capability = store.upsert_capability(
            {"goal_id": GOAL_ID, "path": "RAG", "name": "RAG", "depth": 1, "target_level": 4}
        )
        store.db.execute(
            "INSERT INTO g_gaps(id, user_id, goal_id, capability_id, dimension, current_level,"
            " target_level, severity, rationale, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("gap_sm", "local", GOAL_ID, capability, "practice", 3, 4, "level_gap_1", "测试缺口", "open"),
        )
        store.db.commit()
        yield {"store": store, "estore": estore, "capability": capability, "tmp": tmp_path}
    finally:
        estore.db.close()
        store.close()


def new_task(env) -> str:
    return env["store"].create_task(
        {
            "gap_id": "gap_sm",
            "title": "写一个检索评测集",
            "objective": "产出一个 10 条样本的评测集（Markdown）",
            "deliverable_type": "markdown",
            "est_minutes": 45,
            "acceptance_type": "artifact_check",
            "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
            "generated_by_run_id": "m5a_sm_test",
        }
    )


# ---------------------------------------------------------------------------
# 1. 合法 / 非法转移
# ---------------------------------------------------------------------------


def test_legal_transitions(env):
    task = new_task(env)
    assert env["store"].get_task(task)["status"] == "proposed"

    assert env["store"].activate_task(task)["status"] == "active"
    assert env["store"].block_task(task, "等用户时间")["status"] == "blocked"
    assert env["store"].get_task(task)["blocked_reason"] == "等用户时间"
    assert env["store"].unblock_task(task)["status"] == "active"
    assert env["store"].complete_task(task, source_id="src_1")["status"] == "done"
    assert env["store"].get_task(task)["status"] == "done"


def test_illegal_transitions_are_rejected(env):
    task = new_task(env)
    with pytest.raises(GrowthStoreError, match="非法状态转移"):
        env["store"].block_task(task, "还没激活")
    with pytest.raises(GrowthStoreError, match="只有 active 任务可以完成"):
        env["store"].complete_task(task, source_id="src_1")
    env["store"].activate_task(task)
    env["store"].complete_task(task, source_id="src_1")
    for call in (
        lambda: env["store"].activate_task(task),
        lambda: env["store"].abandon_task(task, "反悔"),
        lambda: env["store"].block_task(task, "卡住"),
    ):
        with pytest.raises(GrowthStoreError, match="非法状态转移"):
            call()
    with pytest.raises(GrowthStoreError, match="只有 active 任务可以完成"):
        env["store"].complete_task(task, source_id="src_2")


def test_reason_required_for_block_and_abandon(env):
    task = new_task(env)
    env["store"].activate_task(task)
    with pytest.raises(GrowthStoreError, match="必须给出 reason"):
        env["store"].block_task(task, "   ")
    assert env["store"].abandon_task(task, "目标变了")["status"] == "abandoned"
    assert env["store"].get_task(task)["abandoned_reason"] == "目标变了"


def test_abandon_from_proposed_and_blocked(env):
    first = new_task(env)
    assert env["store"].abandon_task(first, "不需要了")["status"] == "abandoned"

    second = env["store"].create_task(
        {
            "gap_id": "gap_sm",
            "title": "再来一个评测集",
            "objective": "产出 second 版本评测集",
            "deliverable_type": "markdown",
            "est_minutes": 30,
            "acceptance_type": "artifact_check",
            "acceptance": "提交 Markdown 与变更说明",
            "generated_by_run_id": "m5a_sm_test",
        }
    )
    env["store"].activate_task(second)
    env["store"].block_task(second, "暂停")
    assert env["store"].abandon_task(second, "改做别的")["status"] == "abandoned"


# ---------------------------------------------------------------------------
# 2. done 唯一入口
# ---------------------------------------------------------------------------


def test_only_complete_task_can_set_done(env):
    """AST 守卫：`done` 字面量只允许出现在 `complete_task` 内（其余方法不可能置 done）。"""
    source = Path(growth_store_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    writers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if '"done"' in segment:
                writers.add(node.name)
    assert writers == {"complete_task"}, f"done 存在其他写入路径: {sorted(writers)}"


def test_complete_task_requires_source_and_active(env):
    task = new_task(env)
    with pytest.raises(GrowthStoreError, match="先 activate"):
        env["store"].complete_task(task, source_id="src_1")
    env["store"].activate_task(task)
    with pytest.raises(GrowthStoreError, match="需要 source_id"):
        env["store"].complete_task(task, source_id="   ")
    result = env["store"].complete_task(task, source_id="src_1", note="提交")
    assert result["source_id"] == "src_1"
    assert len(env["store"].list_task_submissions(task_id=task)) == 1


def test_duplicate_submission_is_idempotent(env):
    task = new_task(env)
    env["store"].activate_task(task)
    env["store"].complete_task(task, source_id="src_1")
    # done 后不能再提交（状态机拦截）
    with pytest.raises(GrowthStoreError, match="只有 active 任务可以完成"):
        env["store"].complete_task(task, source_id="src_2")
    assert len(env["store"].list_task_submissions(task_id=task)) == 1


# ---------------------------------------------------------------------------
# 3. 事件链
# ---------------------------------------------------------------------------


def test_every_transition_writes_an_event(env):
    task = new_task(env)
    env["store"].activate_task(task)
    env["store"].block_task(task, "卡住")
    env["store"].unblock_task(task)
    env["store"].complete_task(task, source_id="src_1")

    events = env["store"].list_events(kind="task_status_changed")
    chain = []
    for event in events:
        payload = event["payload_json"]
        import json

        data = json.loads(payload)
        chain.append((data["from"], data["to"], data["reason"]))
    assert chain == [
        (None, "proposed", None),
        ("proposed", "active", None),
        ("active", "blocked", "卡住"),
        ("blocked", "active", None),
        ("active", "done", None),
    ]


def test_transitions_table_is_frozen():
    assert TASK_TRANSITIONS == {
        "proposed": ("active", "abandoned"),
        "active": ("blocked", "abandoned", "done"),
        "blocked": ("active", "abandoned"),
        "done": (),
        "abandoned": (),
    }


def test_write_event_validates_kind_and_returns_identifier(env):
    with pytest.raises(GrowthStoreError, match="kind"):
        env["store"].write_event("  ", {})
    first = env["store"].write_event("task_status_changed", {"note": "a"})
    second = env["store"].write_event("task_status_changed", {"note": "b"})
    assert first != second
    assert len(env["store"].list_events()) == 2


# ---------------------------------------------------------------------------
# 4. 工具层不产生能力判断
# ---------------------------------------------------------------------------


def test_store_completion_does_not_touch_assessments(env):
    """M5-a 原语层：`GrowthStore.complete_task` 不产生/修改任何评定（完成 ≠ 提升）。

    工具层的提交入口自 M5-c 起是 `TaskLoop` 闭环（提交物 → 证据 → claim → 绑定 → 重评，
    见 `test_task_loop.py`）；本用例锁定**原语层**边界 —— 闭环不得把评定写入下移到这里。
    """
    registry = register_growth_tools(
        ToolRegistry(), store=env["store"], evidence_store=env["estore"]
    )
    task = registry.call(
        "create_task",
        gap_id="gap_sm",
        title="写一个检索评测集",
        objective="产出一个 10 条样本的评测集（Markdown）",
        deliverable_type="markdown",
        est_minutes=45,
        acceptance_type="artifact_check",
        acceptance="提交 Markdown，且包含 10 条样本与判定标准",
        generated_by_run_id="m5a_sm_test",
    )
    env["store"].activate_task(task["id"])
    env["store"].complete_task(task["id"], source_id="src_sm", note="原语直接完成（不触发重评）")

    assert env["store"].list_assessments() == [], "任务完成不得产生/修改评定（完成 ≠ 提升）"
    capability = env["store"].get_capability(env["capability"])
    assert capability["current_level_status"] == "unassessed"
    assert capability["current_level_practice"] is None
