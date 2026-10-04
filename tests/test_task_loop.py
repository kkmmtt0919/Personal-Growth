"""M5-c：任务提交闭环（TaskLoop）—— 唯一入口 / 单入口证据 / 归因 / 三联条件守卫。

冻结口径（`M5-PLAN.md` v1.0 §6，用户 2026-10-03 确认）：

* `TaskLoop.complete_task(task_id, submission)` 是**唯一入口**；`source_id` 不由调用方提供；
* **done 在链尾**：②–⑤ 任一步失败 → 任务留在 `active`（可幂等重跑）；
* 证据类型由 `deliverable_type` 决定；归属/通道写死（`user_evidence` / `user_declared`）；
* 材料 claim 确定性模板（零 LLM）；绑定 ≤1 次调用；重评只经 M4-e 编排；
* **三联条件**：等级变化必须同时具备 before + 新证据 provenance + after，否则 `LoopGuardError`。
"""

from __future__ import annotations

import ast
import asyncio
import zipfile
from pathlib import Path

import pytest
from growth_os.agent import FakeGateway
from growth_os.assessment import (
    BINDING_TASK,
    LoopGuardError,
    TaskLoop,
    TaskLoopError,
    trace_task,
    verify_attribution,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from task_loop_fixtures import create_active_task, make_binding_proposer, seed_scenario

GOAL_ID = "goal_m5c"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m5c.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
        scenario = seed_scenario(store, estore, tmp_path)
        task_id = create_active_task(store, scenario["gaps"]["practice"])

        def make_loop(gateway, **overrides) -> TaskLoop:
            options = {
                "store": store,
                "evidence_store": estore,
                "gateway": gateway,
                "submission_dir": tmp_path / "submissions",
                "report_directory": tmp_path / "reports",
            }
            options.update(overrides)
            return TaskLoop(**options)

        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "scenario": scenario,
            "task_id": task_id,
            "make_loop": make_loop,
            "tmp": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def write_artifact(path: Path, text: str = "# 评测集\n\n10 条样本与判定标准：\n1. …\n") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def run_loop(env, *, gateway=None, task_id=None, **submission):
    gateway = gateway or FakeGateway(
        responses={BINDING_TASK: make_binding_proposer(path=env["scenario"]["capability_path"])}
    )
    loop = env["make_loop"](gateway)
    return asyncio.run(
        loop.complete_task(task_id or env["task_id"], **submission)
    )


# ---------------------------------------------------------------------------
# 1. 主链：提交 → 证据 → claim → 绑定 → 重评 → 归因
# ---------------------------------------------------------------------------


def test_happy_path_level_changed_and_gap_closed(env):
    artifact = write_artifact(env["tmp"] / "eval-set.md")
    report = run_loop(env, artifact_path=artifact, note="第一次提交")

    attribution = report["attribution"]
    assert report["status"] == "level_changed"
    assert attribution["level_changed_dimensions"] == ["practice"]
    assert attribution["before"]["practice"]["level"] == 3
    assert attribution["after"]["practice"]["level"] == 4
    assert attribution["submission"]["evidence_type"] == "task_submission"
    assert attribution["claim"]["scope"] == "material"
    assert attribution["binding"]["bound_on_task_capability"] is True
    assert attribution["binding"]["accepted_proposal_ids"]
    assert attribution["binding"]["decisions"], "绑定裁决必须全量留档"
    assert attribution["gaps"]["closed_gap_ids"] == [env["scenario"]["gaps"]["practice"]["id"]]
    assert attribution["guard"] == {
        "new_source_present": True,
        "new_claim_present": True,
        "binding_on_task_capability": True,
        "trace_complete": True,
        "before_present:practice": True,
        "after_present:practice": True,
    }
    assert report["task"]["status"] == "done"
    assert env["store"].get_task(env["task_id"])["status"] == "done"

    # 缺口关闭 + 回填等级 + 理解缺口保持 open（反向验证：不会全能力自动提升）
    assert env["store"].get_gap(env["scenario"]["gaps"]["practice"]["id"])["status"] == "closed"
    assert env["store"].get_gap(env["scenario"]["gaps"]["understanding"]["id"])["status"] == "open"
    capability = env["store"].get_capability(env["scenario"]["capability"])
    assert capability["current_level_practice"] == 4
    assert capability["current_level_understanding"] == 2


def test_single_entry_and_frozen_mapping(env):
    artifact = write_artifact(env["tmp"] / "eval-set.md")
    report = run_loop(env, artifact_path=artifact)
    source_id = report["attribution"]["submission"]["source_id"]

    metadata = adapter.source_metadata(env["estore"], source_id)
    assert metadata["growth_evidence_type"] == "task_submission"
    assert metadata["growth_channel"] == "user_evidence"
    assert metadata["growth_attribution"] == "user_declared"
    assert metadata["growth_task_id"] == env["task_id"]

    # 一次提交 = 一条 submission + 一条材料 claim（幂等键由内容派生）
    assert len(env["store"].list_task_submissions(task_id=env["task_id"])) == 1
    claims = [
        entry
        for entry in adapter.claims_overview(env["estore"])
        if (entry["claim"].get("metadata") or {}).get("growth_task_id") == env["task_id"]
    ]
    assert len(claims) == 1
    assert claims[0]["claim"]["metadata"]["growth_claim_scope"] == "material"


def test_probe_answer_uses_probe_result_and_lifts_understanding(env):
    gap = env["scenario"]["gaps"]["understanding"]
    task_id = create_active_task(
        env["store"],
        gap,
        title="现场作答：RAG 检索流程五问",
        objective="产出一份现场作答记录，覆盖切分、向量化、召回、重排、评测五个环节",
        deliverable_type="probe_answer",
        acceptance_type="probe_rubric",
        acceptance="提交作答正文，按五个环节逐项核对要点是否完整",
    )
    report = run_loop(
        env,
        task_id=task_id,
        probe_answer="一、切分：按语义段落切分……\n二、向量化：……\n",
    )
    attribution = report["attribution"]
    assert attribution["submission"]["evidence_type"] == "probe_result"
    assert attribution["level_changed_dimensions"] == ["understanding"]
    assert attribution["before"]["understanding"]["level"] == 2
    assert attribution["after"]["understanding"]["level"] == 3
    assert attribution["gaps"]["closed_gap_ids"] == [], "理解距目标 4 仍差 1 级，缺口保持 open"
    assert attribution["submission"]["materialized_path"], "probe 文本必须物化为受控文件后入库"
    assert Path(attribution["submission"]["materialized_path"]).is_file()


def test_archive_primary_source_selection_and_entry_provenance(env):
    env["store"].abandon_task(env["task_id"], "改用 archive 交付物（测试场景切换）")
    archive = env["tmp"] / "deliverable.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("a-small.md", "# 说明\n\n一句话。\n")
        bundle.writestr(
            "b-big.md",
            "# 主交付物\n\n" + "\n\n".join(f"第 {index} 段：检索评测说明。" for index in range(1, 12)),
        )
    task_id = create_active_task(
        env["store"],
        env["scenario"]["gaps"]["practice"],
        title="搭建并调优一个可运行的最小 RAG 问答系统",
        objective="产出一个 ZIP 归档（含 README 与可运行脚本）",
        deliverable_type="archive",
        acceptance_type="test_run",
        acceptance="解压后一键运行，5 个测试问题均返回结果",
    )
    report = run_loop(env, task_id=task_id, artifact_path=archive)
    submission = report["attribution"]["submission"]
    assert submission["archive"]["primary_entry"] == "b-big.md"
    assert submission["archive"]["ok"] == 2 and submission["archive"]["failed"] == 0
    assert len(submission["source_ids"]) == 2
    primary, other = submission["source_id"], next(
        item for item in submission["source_ids"] if item != submission["source_id"]
    )
    assert len(env["estore"].get_passages(source_id=primary)) >= len(
        env["estore"].get_passages(source_id=other)
    ), "主条目 = passage 数最多的 ok 条目（确定性选取）"
    assert report["attribution"]["claim"]["passage_ids"]
    assert report["status"] == "level_changed"


# ---------------------------------------------------------------------------
# 2. 唯一入口与前置校验
# ---------------------------------------------------------------------------


def test_complete_task_requires_active_and_matching_submission(env):
    artifact = write_artifact(env["tmp"] / "eval-set.md")
    proposed = env["store"].create_task(
        {
            "gap_id": env["scenario"]["gaps"]["understanding"]["id"],
            "title": "现场作答：RAG 五问",
            "objective": "产出一份现场作答记录",
            "deliverable_type": "probe_answer",
            "est_minutes": 30,
            "acceptance_type": "probe_rubric",
            "acceptance": "提交作答正文并按要点核对",
            "generated_by_run_id": "m5c_test",
        }
    )
    with pytest.raises(TaskLoopError, match="只有 active"):
        run_loop(env, task_id=proposed, artifact_path=artifact)

    # 交付物形态 ↔ deliverable_type 匹配（markdown 任务不接受 probe 文本）
    with pytest.raises(TaskLoopError, match="只接受 artifact_path"):
        run_loop(env, probe_answer="现场作答文本")

    # probe 任务不接受 artifact / 需要作答文本
    env["store"].activate_task(proposed)
    probe_task = proposed
    with pytest.raises(TaskLoopError, match="只接受作答文本"):
        run_loop(env, task_id=probe_task, artifact_path=artifact)
    with pytest.raises(TaskLoopError, match="需要作答文本"):
        run_loop(env, task_id=probe_task, probe_answer="   ")

    # 文件不存在 → 写库前 fail-closed
    with pytest.raises(TaskLoopError, match="提交文件不存在"):
        run_loop(env, artifact_path=env["tmp"] / "missing.md")


def test_binding_missed_records_without_level_change(env):
    db = env["tmp"] / "m5c-other.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
        scenario = seed_scenario(store, estore, env["tmp"], second_capability=True)
        task_id = create_active_task(store, scenario["gaps"]["practice"])
        other_path = store.get_capability(scenario["other_capability"])["path"]
        gateway = FakeGateway({BINDING_TASK: make_binding_proposer(path=other_path)})
        loop = TaskLoop(
            store=store,
            evidence_store=estore,
            gateway=gateway,
            submission_dir=env["tmp"] / "other-submissions",
        )
        artifact = write_artifact(env["tmp"] / "other-eval.md")
        report = asyncio.run(loop.complete_task(task_id, artifact_path=artifact))

        assert report["status"] == "binding_missed"
        assert report["assessment"] is None, "未绑定到任务能力点时不写 assessment"
        assert report["attribution"]["level_changed"] is False
        assert report["attribution"]["guard"]["trace_complete"] is False
        assert store.get_capability(scenario["capability"])["current_level_practice"] == 3
        assert store.get_task(task_id)["status"] == "done", "提交本身已完成（done 不等于提升）"
        assert store.list_capability_claims(capability_id=scenario["other_capability"])
    finally:
        estore.db.close()
        store.close()


def test_failure_leaves_active_and_retry_is_idempotent(env):
    artifact = write_artifact(env["tmp"] / "eval-set.md")
    broken = FakeGateway(fail_with={BINDING_TASK: RuntimeError("网关不可用")})
    with pytest.raises(TaskLoopError, match="绑定提议调用失败"):
        run_loop(env, gateway=broken, artifact_path=artifact)

    # 失败 → done 未落定；提交记录未写；证据与 claim 已入库（可重跑）
    assert env["store"].get_task(env["task_id"])["status"] == "active"
    assert env["store"].list_task_submissions(task_id=env["task_id"]) == []
    sources_before = len(env["estore"].get_sources())

    report = run_loop(env, artifact_path=artifact)
    assert report["status"] == "level_changed"
    assert env["store"].get_task(env["task_id"])["status"] == "done"
    assert len(env["store"].list_task_submissions(task_id=env["task_id"])) == 1
    assert len(env["estore"].get_sources()) == sources_before, "重跑入库幂等（同内容命中同一 source）"
    claims = [
        entry
        for entry in adapter.claims_overview(env["estore"])
        if (entry["claim"].get("metadata") or {}).get("growth_task_id") == env["task_id"]
    ]
    assert len(claims) == 1, "重跑 claim 幂等（内容派生 id）"


# ---------------------------------------------------------------------------
# 3. 归因、守卫与只读反查
# ---------------------------------------------------------------------------


def test_trace_task_reverse_query(env):
    before = trace_task(env["store"], env["estore"], task_id=env["task_id"])
    assert before["complete"] is False and before["task_status"] == "active"

    artifact = write_artifact(env["tmp"] / "eval-set.md")
    report = run_loop(env, artifact_path=artifact)
    source_id = report["attribution"]["submission"]["source_id"]

    after = trace_task(env["store"], env["estore"], task_id=env["task_id"])
    assert after["complete"] is True
    assert after["task_status"] == "done"
    assert after["gap"]["id"] == env["scenario"]["gaps"]["practice"]["id"]
    assert after["source_ids"] == [source_id]
    assert after["claims"] and after["claims"][0]["sources"] == [source_id]
    assert after["bindings"] and after["assessments"]


def test_verify_attribution_three_part_condition():
    base = {
        "submission": {"source_id": "src_x"},
        "claim": {"claim_id": "clm_x"},
        "binding": {"bound_on_task_capability": True},
        "trace": {"complete": True},
        "before": {"practice": {"status": "rated", "level": 3}},
        "after": {"practice": {"status": "rated", "level": 4}},
        "level_changed_dimensions": ["practice"],
    }
    guard = verify_attribution(base)
    assert guard["new_source_present"] and guard["new_claim_present"]
    assert guard["before_present:practice"] and guard["after_present:practice"]

    # 缺 before → 三联条件不成立
    with pytest.raises(LoopGuardError, match="三联条件"):
        verify_attribution({**base, "before": {"practice": None}})
    # 缺新证据 provenance（trace 不完整）→ 报错
    with pytest.raises(LoopGuardError, match="三联条件"):
        verify_attribution({**base, "trace": {"complete": False}})
    # 绑定不在任务能力点却报变化 → 报错
    with pytest.raises(LoopGuardError, match="三联条件"):
        verify_attribution({**base, "binding": {"bound_on_task_capability": False}})
    # 无变化：链不完整也不报错（"没变化"不是错误）
    no_change = verify_attribution(
        {**base, "level_changed_dimensions": [], "trace": {"complete": False}}
    )
    assert no_change["trace_complete"] is False
    # 等级下降 → 异常
    with pytest.raises(LoopGuardError, match="下降"):
        verify_attribution({**base, "after": {"practice": {"status": "rated", "level": 2}}})


# ---------------------------------------------------------------------------
# 4. 守卫：本模块不得直写等级/评定/桥表；不新增表与事件种类
# ---------------------------------------------------------------------------


def test_loop_never_writes_levels_or_bindings_directly():
    import growth_os.assessment.task_loop as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "link_capability_claim",
        "save_assessment",
        "save_assessment_draft",
        "apply_assessment_levels",
        "apply_gaps",
    }
    assert called & forbidden == set(), f"task_loop 不得直写评定/桥表：{sorted(called & forbidden)}"


def test_no_new_tables_and_frozen_event_kinds(env):
    tables = {
        row[0]
        for row in env["store"].db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {name for name in tables if name.startswith("g_")} == {
        "g_users",
        "g_goals",
        "g_goal_clarifications",
        "g_capabilities",
        "g_capability_claims",
        "g_assessments",
        "g_agent_runs",
        "g_gaps",
        "g_tasks",
        "g_task_submissions",
        "g_events",
        "g_memories",
        "g_growth_snapshots",
    }, "M5-c 之后仅允许 M6 的记忆表"
    artifact = write_artifact(env["tmp"] / "eval-set.md")
    run_loop(env, artifact_path=artifact)
    assert {event["kind"] for event in env["store"].list_events()} == {"task_status_changed"}
