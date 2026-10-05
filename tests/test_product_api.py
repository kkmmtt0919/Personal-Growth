"""M8-a：只读 API 契约。"""

from pathlib import Path

from fastapi.testclient import TestClient
from growth_os.api import create_app
from growth_os.evidence import adapter
from growth_os.store import GrowthStore


def test_read_api_exposes_dashboard_evidence_and_loop(tmp_path: Path):
    db = tmp_path / "api.db"
    store = GrowthStore(str(db))
    evidence = adapter.open_store(db)
    try:
        store.upsert_user("local", "本地用户")
        store.save_goal({"id": "goal_demo", "user_id": "local", "title": "AI Agent Engineer", "direction": "AI", "purpose": "求职", "horizon": "六个月", "measurable_result": "完成项目", "status": "confirmed", "source_quote": "确认"})
        capability = store.upsert_capability({"goal_id": "goal_demo", "path": "RAG", "name": "RAG系统搭建", "depth": 1, "target_level": 4})
        store.save_assessment({"capability_id": capability, "dimension": "practice", "status": "rated", "level": 3, "claim_ids": ["clm_demo"], "rubric": {"contract": "m4c-1"}, "rationale": "已有项目证据"})
        store.apply_assessment_levels(capability)
        store.db.execute("INSERT INTO g_gaps(id,user_id,goal_id,capability_id,dimension,current_level,target_level,severity,rationale,status) VALUES(?,?,?,?,?,?,?,?,?,?)", ("gap_demo", "local", "goal_demo", capability, "practice", 3, 4, "level_gap_1", "缺少Agent Evaluation实践", "open"))
        store.db.commit()
        task = store.create_task({"gap_id": "gap_demo", "title": "实现Agent评测实验", "objective": "产出评测实验", "deliverable_type": "markdown", "est_minutes": 60, "acceptance_type": "artifact_check", "acceptance": "提交评测报告并核对指标"})
        source = tmp_path / "evidence.md"
        source.write_text("使用 ChromaDB 完成向量检索。\n", encoding="utf-8")
        ingested = adapter.ingest_document(source, store=evidence, evidence_type="repo_artifact", attribution="user_declared")
        passage = evidence.get_passages(source_id=ingested.source_id)[0]
        material = adapter.create_material_claim(evidence, subject="材料", predicate="包含", object="向量检索", statement="材料包含向量检索实现", passage_ids=[passage.id])
        store.link_capability_claim(capability, material["claim_id"], role="supports", rationale="证明完成向量检索实现")
        client = TestClient(create_app(store, evidence))
        assert client.get("/api/goals/goal_demo").json()["title"] == "AI Agent Engineer"
        capability_body = client.get(f"/api/capabilities/{capability}").json()
        listed = client.get("/api/goals/goal_demo/capabilities").json()
        assert listed["capabilities"][0]["practice"] == 3
        assert listed["capabilities"][0]["open_gaps"][0]["severity"] == "level_gap_1"
        assert capability_body["practice"] == 3
        assert capability_body["gaps"] == ["缺少Agent Evaluation实践"]
        evidence_body = client.get(f"/api/evidence/{capability}").json()
        support = evidence_body["supports"][0]
        assert support["binding_reason"] == "证明完成向量检索实现"
        assert support["quote"]["text"] == "使用 ChromaDB 完成向量检索。"
        assert support["source"]["type"] == "repo_artifact"
        loop = client.get("/api/growth-loop/goal_demo").json()
        assert loop["tasks"][0]["id"] == task
        assert client.get("/api/goals/missing").status_code == 404
        assert not hasattr(client.app.state, "write_api")
    finally:
        evidence.close() if hasattr(evidence, "close") else evidence.db.close()
        store.close()
