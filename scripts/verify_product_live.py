"""真实产品旅程，使用独立空库与明确调用上限；不操作个人原库。"""

import base64
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from growth_os.api.product import create_local_product_app, load_model_environment
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from verify_g6_final import database_state

OUTPUT = ROOT / "artifacts/product/live"


def verify():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    load_model_environment(ROOT / ".env")
    os.environ["EVKG_HTTP_RETRIES"] = "1"
    os.environ["EVKG_HTTP_TIMEOUT"] = "90"
    os.environ.pop("GROWTH_PRODUCT_DEMO", None)
    directory = ROOT / "tmp" / ("product-live-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    os.environ["GROWTH_PRODUCT_DIRECTORY"] = str(directory)
    originals = [ROOT / relative for relative in ("data/growth.db", "data/demo/demo.db", "data/demo-return/demo.db",
                 "data/interactive/demo.db", "data/onboarding/onboarding.db", "data/product/onboarding.db")]
    before = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks, results = {}, {}
    with TestClient(create_local_product_app()) as client:
        info = client.get("/api/product").json()
        assert info["mode"] == "model" and info["configured"] and info["goals"] == [], "模型配置或空库前提未满足"
        checks["empty_personal_product"] = True
        text = "我希望在三个月内成为能独立开发RAG应用的AI应用工程师，目的是为求职准备作品集。可衡量成果是完成一个有引用、测试和评测报告的本地知识问答应用。每周可投入六小时，偏好先看架构再做代码实践。"
        print("live: clarify goal", flush=True)
        response = client.post("/api/onboarding/goals", json={"request_id": "live_product_goal", "text": text})
        assert response.status_code == 200, response.text
        state = response.json()
        base = f"/api/onboarding/goals/{state['goal']['id']}"
        for _ in range(2):
            if state["goal"]["status"] == "proposed":
                break
            assert state["pending"], "目标未进入可回答状态"
            response = client.post(base + "/answers", json={"round": state["pending"]["round"], "text": text + "请按这些明确约束提议目标，暂不增加范围。"})
            assert response.status_code == 200, response.text
            state = response.json()
        assert state["goal"]["status"] == "proposed", "三次真实澄清预算内未收敛"
        assert client.post(base + "/confirm", json={"quote": "确认三个月内完成有引用、测试和评测报告的RAG应用"}).status_code == 200
        print("live: generate personalized capability tree", flush=True)
        response = client.post(base + "/capabilities")
        assert response.status_code == 200, response.text
        state = response.json()
        goal_id = state["goal"]["id"]
        nodes = [row for row in state["capabilities"] if row["depth"] == 3]
        checks["personalized_tree_shape"] = len(nodes) >= 12
        checks["unassessed_and_unverified"] = all(row["current_level_understanding"] is None and row["current_level_practice"] is None and row["verification_status"] == "unverified" for row in nodes)
        assert client.post("/api/product/preferences", json={"text": "偏好先看架构再做代码实践，每周六小时"}).status_code == 200
        print("live: mentor conversation and followup", flush=True)
        for index, question in enumerate(["按我的时间和偏好，我现在该先做什么？请明确现有证据的局限。", "沿着上一条建议，设计一个第一周能完成的小项目。引用已有记录，并说明哪些只是建议。"]):
            payload = {"request_id": f"live_mentor_{index}", "text": question}
            response = client.post(f"/api/mentor/{goal_id}", json=payload)
            assert response.status_code == 200, response.text
            result = response.json()
            results[f"mentor_{index}"] = result
            checks[f"mentor_{index}_live"] = result["response"]["provider"] != "fake" and len(result["response"]["answer"]) > 30
            checks[f"mentor_{index}_replay"] = client.post(f"/api/mentor/{goal_id}", json=payload).json() == result
        checks["mentor_did_not_create_tasks"] = client.get(f"/api/growth-loop/{goal_id}").json()["tasks"] == []
        print("live: task proposal and evidence submission", flush=True)
        leaf = next((row for row in nodes if "检索" in row["path"]), nodes[0])
        response = client.post(base + f"/capabilities/{leaf['id']}/tasks", json={"dimension": "understanding"})
        assert response.status_code == 200, response.text
        task = response.json()["task"]
        assert client.post(f"/api/tasks/{task['id']}/actions", json={"action": "activate"}).status_code == 200
        answer = f"围绕{leaf['path']}：先定义检索目标，再用固定小语料构建测试集。比较关键词检索与向量检索，记录召回率、引用正确率和失败例。检索结果不等于答案可靠，应逐条核对引用。此材料只说明方案，未声称已执行实验或证明能力。"
        payload = {"request_id": "live_task_submission"}
        if task["deliverable_type"] == "probe_answer":
            url = f"/api/tasks/{task['id']}/submissions"
            payload["probe_answer"] = answer
        else:
            url = f"/api/tasks/{task['id']}/files"
            payload.update(filename="explanation.md", content_base64=base64.b64encode(answer.encode()).decode())
        response = client.post(url, json=payload)
        assert response.status_code == 200, response.text
        results["submission"] = response.json()
        checks["live_submission_guard"] = all(results["submission"]["attribution"]["guard"].values())
        checks["bound_on_task_capability"] = results["submission"]["binding"]["bound_on_task_capability"]
        checks["task_done"] = client.get(f"/api/growth-loop/{goal_id}").json()["tasks"][0]["status"] == "done"
        checks["original_quote_visible"] = bool(client.get(f"/api/evidence/{leaf['id']}").json()["supports"])
    with TestClient(create_local_product_app()) as client:
        checks["reopened_dialogue"] = len(client.get(f"/api/mentor/{goal_id}").json()["turns"]) == 2
        checks["reopened_submission_replay"] = client.post(url, json=payload).json() == results["submission"]
    with GrowthStore(str(directory / "onboarding.db")) as store:
        runs = [dict(row) for row in store.db.execute("SELECT * FROM g_agent_runs")]
        checks["bounded_live_calls"] = 6 <= len(runs) <= 10 and all(row["provider"] != "fake" for row in runs)
    after = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks["original_databases_unchanged"] = before == after
    audit = adapter.audit(directory / "onboarding.db")
    checks["audit_clean"] = audit["status"] == "pass"
    report = {"passed": all(checks.values()), "checks": checks, "directory": str(directory), "goal": state["goal"],
              "capabilities": nodes, "results": results, "runs": runs, "audit": audit, "model_calls": len(runs),
              "originals_before": before, "originals_after": after}
    (OUTPUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": len(checks), "model_calls": len(runs), "directory": str(directory)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(verify())
