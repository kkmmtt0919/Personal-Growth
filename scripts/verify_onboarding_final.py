"""O3：独立新目标旅程、新进程恢复与原库隔离验证（零真实模型）。"""

from __future__ import annotations

import argparse
import base64
import gc
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from growth_os.api.app import create_app
from growth_os.api.onboarding import create_local_onboarding_app, seed_onboarding
from growth_os.assessment import trace_task
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from verify_g6_final import audit_copy, database_state, regression, secret_scan

OUTPUT = ROOT / "artifacts/onboarding/o3"


def configure(directory):
    os.environ["GROWTH_ONBOARDING_DIRECTORY"] = str(directory)
    os.environ.pop("GROWTH_ONBOARDING_REAL_MODEL", None)


def reopen(directory):
    configure(directory)
    expected = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
    checks = {}
    with TestClient(create_local_onboarding_app()) as client:
        rows = client.get(f"/api/growth-loop/{expected['goal_id']}").json()["tasks"]
        for dimension, record in expected["submissions"].items():
            row = next(task for task in rows if task["id"] == record["task_id"])
            replay = client.post(record["url"], json=record["payload"])
            checks[f"{dimension}_replay"] = replay.status_code == 200 and replay.json() == record["result"]
            checks[f"{dimension}_persisted"] = len(row["submissions"]) == 1 and row["attribution"] == record["result"]["attribution"]
    return {"pid": os.getpid(), "checks": checks}


def verify():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    originals = [ROOT / path for path in ("data/growth.db", "data/demo/demo.db",
                 "data/demo-return/demo.db", "data/interactive/demo.db", "data/onboarding/onboarding.db")]
    before = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks, records = {}, {}
    with tempfile.TemporaryDirectory(prefix="o3-", dir=ROOT / "tmp") as scratch_name:
        scratch = Path(scratch_name)
        directory = scratch / "journey"
        seed_onboarding(directory)
        configure(directory)
        with TestClient(create_local_onboarding_app()) as client:
            state = client.post("/api/onboarding/goals", json={"request_id": "o3_fresh_goal", "text": "完成写作作品集"}).json()
            goal_id = state["goal"]["id"]
            base = f"/api/onboarding/goals/{goal_id}"
            for index, answer in enumerate(["写作", "作品集", "三个月", "三篇可核对文章"], 1):
                response = client.post(base + "/answers", json={"round": index, "text": answer})
                assert response.status_code == 200, response.text
            assert client.post(base + "/capabilities").status_code == 409
            checks["unconfirmed_tree_blocked"] = True
            assert client.post(base + "/confirm", json={"quote": "确认三个月完成三篇文章"}).status_code == 200
            state = client.post(base + "/capabilities").json()
            checks["tree_shape"] = sum(node["depth"] == 1 for node in state["capabilities"]) == 3 and sum(node["depth"] == 3 for node in state["capabilities"]) == 12
            checks["unknown_levels_unverified_sources"] = all(node["current_level"] is None and node["verification_status"] == "unverified" for node in state["capabilities"])
            node = next(node for node in state["capabilities"] if node["depth"] == 3)
            for dimension in ("understanding", "practice"):
                plan = base + f"/capabilities/{node['id']}/tasks"
                response = client.post(plan, json={"dimension": dimension})
                assert response.status_code == 200, response.text
                task = response.json()["task"]
                checks[f"{dimension}_deduplicated_task"] = client.post(plan, json={"dimension": dimension}).json()["task"]["id"] == task["id"]
                assert client.post(f"/api/tasks/{task['id']}/actions", json={"action": "activate"}).status_code == 200
                payload = {"request_id": "o3_submit_" + dimension}
                text = "# 写作记录\n具体例子、核对步骤与局限：本材料仅用于受控旅程验证。"
                if dimension == "understanding":
                    url = f"/api/tasks/{task['id']}/submissions"
                    payload["probe_answer"] = text
                else:
                    url = f"/api/tasks/{task['id']}/files"
                    payload.update(filename="writing.md", content_base64=base64.b64encode(text.encode()).decode())
                response = client.post(url, json=payload)
                assert response.status_code == 200, response.text
                result = response.json()
                records[dimension] = {"task_id": task["id"], "url": url, "payload": payload, "result": result}
                checks[f"{dimension}_completed_guarded"] = result["task"]["status"] == "done" and all(result["attribution"]["guard"].values())
                checks[f"{dimension}_submission_replay"] = client.post(url, json=payload).json() == result
            evidence_response = client.get(f"/api/evidence/{node['id']}").json()
            checks["both_original_quotes_visible"] = len(evidence_response["supports"]) == 2 and all("核对步骤" in item["quote"]["text"] for item in evidence_response["supports"])
        (directory / "expected.json").write_text(json.dumps({"goal_id": goal_id, "submissions": records}, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--reopen", str(directory)],
                                 capture_output=True, text=True, encoding="utf-8", check=False)
        if process.returncode:
            raise RuntimeError(process.stderr)
        restored = json.loads(process.stdout)
        checks["separate_process"] = restored["pid"] != os.getpid()
        checks.update(restored["checks"])
        with GrowthStore(str(directory / "onboarding.db")) as store:
            evidence = adapter.open_store(directory / "onboarding.db")
            try:
                traces = {dimension: trace_task(store, evidence, task_id=record["task_id"])
                          for dimension, record in records.items()}
                checks["both_trace_chains_complete"] = all(trace["complete"] for trace in traces.values())
                readonly = TestClient(create_app(store, evidence))
                checks["readonly_submission_routes_absent"] = all(readonly.post(record["url"], json=record["payload"]).status_code == 404 for record in records.values())
            finally:
                evidence.db.close()
        audit = audit_copy(directory / "onboarding.db", scratch / "audit")
        checks["audit_before_after_clean"] = audit["before"]["status"] == "pass" and audit["after"]["status"] == "pass"
        checks["damage_caught_and_copy_restored"] = audit["damage"]["status"] == "caught" and audit["data_restored_except_audit_log"]
        gc.collect()
    after = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks["original_databases_unchanged"] = before == after
    growth = regression("artifacts/onboarding/o3/regression.xml")
    upstream = regression("artifacts/onboarding/o3/evkg-regression.xml")
    browser = json.loads((OUTPUT / "browser-verification.json").read_text(encoding="utf-8"))
    secrets = secret_scan()
    checks["growth_and_upstream_regressions"] = growth["successful"] and upstream["successful"]
    checks["browser_journey_passed"] = browser["passed"] and len(browser["checks"]) == 27
    checks["no_secrets"] = secrets["hit_count"] == 0 and secrets["env_ignored_and_untracked"]
    report = {"passed": all(checks.values()), "real_model_calls": 0, "checks": checks,
              "journey": {"goal": state["goal"], "submissions": records, "traces": traces},
              "reopen": restored, "copy_audit": audit, "originals_before": before, "originals_after": after,
              "regressions": {"growth": growth, "upstream": upstream}, "secret_scan": secrets}
    (OUTPUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": len(checks), "growth_tests": growth["tests"], "upstream_tests": upstream["tests"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reopen", type=Path)
    args = parser.parse_args()
    if args.reopen:
        print(json.dumps(reopen(args.reopen), ensure_ascii=False))
    else:
        sys.exit(verify())
