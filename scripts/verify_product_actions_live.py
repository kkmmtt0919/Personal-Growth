"""在U1旅程的独立副本验证真实任务生成与目标调整，不修改U1库。"""
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from verify_g6_final import ROOT, audit_copy, database_state

sys.path.insert(0, str(ROOT / "backend"))
from growth_os.api.product import create_local_product_app, load_model_environment


def verify():
    output = ROOT / "artifacts/product/actions-live"
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads((ROOT / "artifacts/product/live/result.json").read_text(encoding="utf-8"))
    database = ROOT / source["directory"] / "onboarding.db"
    before = database_state(database)
    directory = ROOT / "tmp" / ("product-actions-live-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    directory.mkdir()
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as original, sqlite3.connect(directory / "onboarding.db") as copied:
        original.backup(copied)
    (directory / "manifest.json").write_text('{"onboarding_enabled":true}', encoding="utf-8")
    load_model_environment(ROOT / ".env")
    os.environ.pop("GROWTH_PRODUCT_DEMO", None)
    os.environ["GROWTH_PRODUCT_DIRECTORY"] = str(directory)
    os.environ["EVKG_HTTP_RETRIES"] = "1"
    os.environ["EVKG_HTTP_TIMEOUT"] = "90"
    goal_id = source["goal"]["id"]
    capability_id = source["results"]["submission"]["binding"]["decisions"][0]["capability_id"]
    checks, results = {}, {}
    with TestClient(create_local_product_app()) as client:
        goal_before = client.get(f"/api/goals/{goal_id}").json()
        nodes_before = client.get(f"/api/onboarding/goals/{goal_id}").json()["capabilities"]
        leaf = next(node for node in nodes_before if node["id"] == capability_id)
        print("live actions: task proposal", flush=True)
        path = f"/api/onboarding/goals/{goal_id}/capabilities/{capability_id}/tasks"
        response = client.post(path, json={"dimension": "practice"})
        assert response.status_code == 200, response.text
        results["task"] = task = response.json()["task"]
        checks["real_task_proposed_not_active"] = task["status"] == "proposed"
        checks["repeat_reuses_task"] = client.post(path, json={"dimension": "practice"}).json()["task"]["id"] == task["id"]
        target = 5 if leaf["target_level"] != 5 else 4
        adjustment = {"request_id": "live_requirement_adjust", "target_level": target, "expected_target_level": leaf["target_level"],
                      "note": "用户确认将这项重点能力对照更高岗位要求", "confirm": True}
        path = f"/api/product/goals/{goal_id}/capabilities/{capability_id}/adjust"
        response = client.post(path, json=adjustment)
        assert response.status_code == 200, response.text
        results["adjustment"] = changed = response.json()["capability"]
        checks["manual_target_adjustment"] = changed["target_level"] == target and changed["origin"] == "adjusted"
        checks["current_grades_preserved"] = all(changed[key] == leaf[key] for key in ("current_level_understanding", "current_level_practice"))
        print("live actions: revised goal", flush=True)
        payload = {"request_id": "live_goal_revision", "text": "我调整为AI测试工程师方向，目的是为求职准备测试作品集，周期六个月。可衡量成果是完成两个AI应用的测试项目，每个有测试代码、结果报告和失败用例。每周仍可投入六小时。", "confirm": True}
        path = f"/api/product/goals/{goal_id}/revisions"
        response = client.post(path, json=payload)
        assert response.status_code == 200, response.text
        state = response.json()["state"]
        child_id = state["goal"]["id"]
        base = f"/api/onboarding/goals/{child_id}"
        for _ in range(2):
            if state["goal"]["status"] == "proposed":
                break
            assert state["pending"]
            state = client.post(base + "/answers", json={"round": state["pending"]["round"], "text": payload["text"]}).json()
        assert state["goal"]["status"] == "proposed", state
        checks["revised_goal_requires_confirmation"] = state["goal"]["source_quote"] is None and not state["capabilities"]
        checks["parent_lineage"] = state["revision_of"]["goal_id"] == goal_id
        checks["original_goal_kept"] = client.get(f"/api/goals/{goal_id}").json() == goal_before
        checks["revision_replay"] = client.post(path, json=payload).json()["replayed"] is True
        assert client.post(base + "/confirm", json={"quote": "我确认调整为六个月完成两个AI应用测试项目的目标"}).status_code == 200
        print("live actions: revised capability tree", flush=True)
        response = client.post(base + "/capabilities")
        assert response.status_code == 200, response.text
        results["revision"] = response.json()
        new_leaves = [node for node in results["revision"]["capabilities"] if node["depth"] == 3]
        checks["new_target_model"] = len(new_leaves) >= 12
        checks["no_grade_inheritance"] = all(node["current_level_understanding"] is None and node["current_level_practice"] is None for node in new_leaves)
    with TestClient(create_local_product_app()) as client:
        checks["actions_reopened"] = len(client.get(f"/api/product/goals/{goal_id}/actions").json()["actions"]) == 2
        checks["lineage_reopened"] = client.get(base).json()["revision_of"]["goal_id"] == goal_id
    with sqlite3.connect(f"file:{directory.as_posix()}/onboarding.db?mode=ro", uri=True) as connection:
        runs = [dict(zip(["id", "provider", "model"], row)) for row in connection.execute("SELECT id,provider,model FROM g_agent_runs ORDER BY rowid")]
    new_runs = [row for row in runs if row["id"] not in {run["id"] for run in source["runs"]}]
    # U1浏览器第三轮没有包含在原始API轨迹列表中，单独剔除它。
    browser = json.loads((ROOT / "artifacts/product/browser-live/browser-verification.json").read_text(encoding="utf-8"))
    existing = {turn["response"]["run_id"] for turn in browser["turns"]}
    new_runs = [row for row in new_runs if row["id"] not in existing]
    checks["bounded_real_calls"] = 3 <= len(new_runs) <= 5 and all(row["provider"] != "fake" for row in new_runs)
    checks["u1_database_unchanged"] = database_state(database) == before
    audit = audit_copy(directory / "onboarding.db", directory / "audit-copy")
    checks["audit_pass_damage_caught"] = audit["before"]["status"] == "pass" and audit["after"]["status"] == "pass" and audit["damage"]["status"] == "caught" and audit["data_restored_except_audit_log"]
    report = {"passed": all(checks.values()), "checks": checks, "results": results, "runs": new_runs, "model_calls": len(new_runs), "directory": str(directory), "audit": audit}
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": len(checks), "model_calls": len(new_runs), "directory": str(directory)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(verify())
