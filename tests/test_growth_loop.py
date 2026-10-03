"""M5-c / AC5：gap → 生成任务 → 提交 → 新证据 → 重评 → 等级变化（离线等价运行）。

对应 `M5-PLAN.md` §10 AC5（端到端 ≥1 能力等级变化 + 归因链可反查）的**离线**部分；
G5 的真实运行由 `artifacts/g5/run_growth_loop.py`（M5-d）承担。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from growth_os.agent import FakeGateway
from growth_os.assessment import BINDING_TASK, TaskLoop, trace_task
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from growth_os.tasks import TASK_GATE_STAGES, TASK_GENERATION_TASK, TaskGenerator, TaskProposal
from task_loop_fixtures import GOAL_ID, make_binding_proposer, seed_scenario


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "growth-loop.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
        scenario = seed_scenario(store, estore, tmp_path)
        yield {"store": store, "estore": estore, "scenario": scenario, "tmp": tmp_path}
    finally:
        estore.db.close()
        store.close()


def offline_proposer(index: int, system: str, user: str):
    """确定性提议（形状与 M5-b 对例一致）：实践缺口 → 可验收的小任务。"""
    return TaskProposal.model_validate(
        {
            "title": "写一个 10 条样本的检索评测集",
            "objective": "产出一份 Markdown 评测集，覆盖 10 条检索样本与判定标准",
            "deliverable_type": "markdown",
            "est_minutes": 60,
            "acceptance_type": "artifact_check",
            "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
        }
    )


def test_gap_to_level_change_end_to_end_offline(env):
    store, estore = env["store"], env["estore"]
    practice_gap = env["scenario"]["gaps"]["practice"]

    # ① gap → 任务（M5-b：LLM 提议 + 七步闸门；离线对例）
    generator = TaskGenerator(
        store=store,
        gateway=FakeGateway(responses={TASK_GENERATION_TASK: offline_proposer}),
        goal_id=GOAL_ID,
    )
    report = asyncio.run(generator.propose_many([practice_gap["id"]]))
    decision = report["decisions"][0]
    assert decision["accepted"] is True
    assert tuple(decision["stages_passed"]) == TASK_GATE_STAGES
    task_id = decision["task_id"]
    assert store.get_task(task_id)["status"] == "proposed"

    # 任务只是 proposed：此时等级/缺口/证据都没变（完成前不产生任何评定）
    assert store.get_capability(env["scenario"]["capability"])["current_level_practice"] == 3
    assert store.get_gap(practice_gap["id"])["status"] == "open"
    assert store.list_task_submissions(task_id=task_id) == []

    # ② 提交 → 闭环（单入口：入库 → claim → 绑定 → 重评 → 归因）
    store.activate_task(task_id)
    artifact = env["tmp"] / "eval-set.md"
    artifact.write_text(
        "# 检索评测集\n\n10 条样本与判定标准：\n1. 查询→期望文档→判定\n", encoding="utf-8"
    )
    loop = TaskLoop(
        store=store,
        evidence_store=estore,
        gateway=FakeGateway(
            responses={
                BINDING_TASK: make_binding_proposer(path=env["scenario"]["capability_path"])
            }
        ),
        submission_dir=env["tmp"] / "submissions",
        report_directory=env["tmp"] / "reports",
    )
    outcome = asyncio.run(loop.complete_task(task_id, artifact_path=artifact, note="离线端到端"))

    # ③ 判定：≥1 个能力等级变化 + 缺口关闭 + 归因链可反查 + 支撑集差异恰为新增 claim
    attribution = outcome["attribution"]
    assert outcome["status"] == "level_changed"
    assert attribution["before"]["practice"]["level"] == 3
    assert attribution["after"]["practice"]["level"] == 4
    assert attribution["gaps"]["closed_gap_ids"] == [practice_gap["id"]]
    assert attribution["support"]["added_claim_ids"] == [attribution["claim"]["claim_id"]]
    assert attribution["assessment"]["report_paths"], "重评报告必须落盘（可解释输出）"
    traceable = trace_task(store, estore, task_id=task_id)
    assert traceable["complete"] is True
    assert store.get_task(task_id)["status"] == "done"

    # 等级变化可在能力解释报告里逐字回溯（M4-d 报告路径已由归因产物给出）
    report_path = Path(next(iter(attribution["assessment"]["report_paths"].values())))
    assert report_path.is_file()
