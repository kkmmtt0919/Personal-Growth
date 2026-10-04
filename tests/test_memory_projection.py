"""M6-b：state/history 可从同一来源重建。"""

from pathlib import Path

from growth_os.memory import MemoryProjection
from growth_os.store import GrowthStore


def test_projection_recreates_same_view(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "projection.db"))
    try:
        store.upsert_user("local", "本地用户")
        store.save_goal({"id": "goal_m6", "user_id": "local", "title": "目标", "direction": "AI", "purpose": "求职", "horizon": "六个月", "measurable_result": "完成项目", "status": "confirmed", "source_quote": "确认"})
        capability = store.upsert_capability({"goal_id": "goal_m6", "path": "RAG", "name": "RAG", "depth": 1, "target_level": 4})
        store.db.execute("INSERT INTO g_gaps(id,user_id,goal_id,capability_id,dimension,current_level,target_level,severity,rationale,status) VALUES(?,?,?,?,?,?,?,?,?,?)", ("gap_p", "local", "goal_m6", capability, "practice", 3, 4, "level_gap_1", "实践不足", "open"))
        store.db.commit()
        assessment = store.save_assessment({"capability_id": capability, "dimension": "practice", "status": "rated", "level": 3, "claim_ids": ["clm_1"], "rubric": {"contract": "m4c-1"}, "rationale": "已有实践证据"})
        task = store.create_task({"gap_id": "gap_p", "title": "写评测集", "objective": "产出评测集", "deliverable_type": "markdown", "est_minutes": 30, "acceptance_type": "artifact_check", "acceptance": "提交评测集并核对样本", "generated_by_run_id": "m6"})
        store.activate_task(task)
        projection = MemoryProjection(store)
        first = projection.project()
        check = projection.verify()
        assert check["consistent"] is True
        assert any(item["memory_key"] == "current_task" for item in first["state"])
        assert first["snapshots"][0]["id"] == projection.project()["snapshots"][0]["id"]
        assert assessment in first["snapshots"][0]["scores_json"]
    finally:
        store.close()
