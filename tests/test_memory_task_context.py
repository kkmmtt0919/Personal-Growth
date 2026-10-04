"""M6-c：已确认 memory 进入任务上下文，但不改变七步闸门。"""

import asyncio
from pathlib import Path

from growth_os.agent import FakeGateway
from growth_os.memory import MemoryService
from growth_os.store import GrowthStore
from growth_os.tasks import TASK_GATE_STAGES, TASK_GENERATION_TASK, TaskGenerator, TaskProposal


def test_confirmed_memory_changes_context_but_not_gate(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "memory-task.db"))
    try:
        store.upsert_user("local", "本地用户")
        store.save_goal({"id": "goal_m6c", "user_id": "local", "title": "目标", "direction": "AI", "purpose": "求职", "horizon": "六个月", "measurable_result": "完成项目", "status": "confirmed", "source_quote": "确认"})
        capability = store.upsert_capability({"goal_id": "goal_m6c", "path": "RAG", "name": "RAG", "depth": 1, "target_level": 4})
        assessment = store.save_assessment({"capability_id": capability, "dimension": "practice", "status": "rated", "level": 3, "claim_ids": ["clm_1"], "rubric": {"contract": "m4c-1"}, "rationale": "已有实践"})
        store.db.execute("INSERT INTO g_gaps(id,user_id,goal_id,capability_id,dimension,current_level,target_level,severity,rationale,assessment_id,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("gap_p", "local", "goal_m6c", capability, "practice", 3, 4, "level_gap_1", "实践不足", assessment, "open"))
        store.db.commit()

        def proposer(index: int, system: str, user: str):
            objective = "产出 Markdown 评测集"
            if "喜欢代码实践" in user:
                objective += "；采用代码实践方式"
            return TaskProposal(title="写评测集", objective=objective, deliverable_type="markdown", est_minutes=30, acceptance_type="artifact_check", acceptance="提交评测集并核对十条样本")

        baseline = asyncio.run(TaskGenerator(store=store, gateway=FakeGateway({TASK_GENERATION_TASK: proposer}), goal_id="goal_m6c").propose("gap_p"))
        store.abandon_task(baseline["decisions"][0]["task_id"], "基线完成")
        memory = MemoryService(store).remember(layer="profile", key="preference", value={"text": "喜欢代码实践"}, source_kind="user_statement", source_id="statement_pref")
        with_memory = asyncio.run(TaskGenerator(store=store, gateway=FakeGateway({TASK_GENERATION_TASK: proposer}), goal_id="goal_m6c").propose("gap_p"))
        assert baseline["proposals"][0]["objective"] == "产出 Markdown 评测集"
        assert with_memory["proposals"][0]["objective"] == "产出 Markdown 评测集；采用代码实践方式"
        prompt = store.get_run(with_memory["run_id"])["input"]
        assert memory["id"] in prompt and memory["source_id"] in prompt
        assert "喜欢代码实践" not in store.get_run(baseline["run_id"])["input"]
        assert tuple(with_memory["decisions"][0]["stages_passed"]) == TASK_GATE_STAGES
    finally:
        store.close()
