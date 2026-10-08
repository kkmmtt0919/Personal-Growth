"""I5：独立受控交互旅程、进程重开、质量门与原库隔离核对。"""

from __future__ import annotations

import argparse
import asyncio
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
from growth_os.api.interactive import create_local_interactive_app, seed_interaction
from growth_os.assessment.task_loop import trace_task
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from verify_g6_final import audit_copy, database_state, fingerprint, regression, secret_scan

OUTPUT = ROOT / "artifacts/interaction/i5"
ORIGINALS = [ROOT / p for p in ("data/growth.db", "data/demo/demo.db",
                               "data/demo-return/demo.db", "data/interactive/demo.db")]


def reopen(directory):
    os.environ["GROWTH_INTERACTION_DIRECTORY"] = str(directory)
    os.environ.pop("GROWTH_INTERACTION_REAL_MODEL", None)
    expected = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
    with TestClient(create_local_interactive_app()) as client:
        rows = client.get("/api/growth-loop/goal_demo").json()["tasks"]
        checks = {}
        for name, record in expected.items():
            row = next(t for t in rows if t["id"] == record["task_id"])
            replay = client.post(record["url"], json=record["payload"])
            checks[f"{name}_persistent_attribution"] = row["attribution"] == record["result"]["attribution"]
            checks[f"{name}_replay"] = replay.status_code == 200 and replay.json() == record["result"]
            checks[f"{name}_single_submission"] = len(row["submissions"]) == 1
    store = GrowthStore(str(directory / "demo.db"))
    evidence = adapter.open_store(directory / "demo.db")
    try:
        traces = {name: trace_task(store, evidence, task_id=record["task_id"])
                  for name, record in expected.items()}
        checks["both_traces_complete"] = all(t["complete"] for t in traces.values())
        readonly = TestClient(create_app(store, evidence))
        checks["readonly_write_routes_absent"] = all(
            readonly.post(record["url"], json=record["payload"]).status_code == 404
            for record in expected.values())
    finally:
        evidence.db.close()
        store.close()
    return {"process_id": os.getpid(), "checks": checks, "traces": traces}


def prepare():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    originals = {str(p.relative_to(ROOT)): database_state(p) for p in ORIGINALS if p.is_file()}
    with tempfile.TemporaryDirectory(prefix="i5-", dir=ROOT / "tmp") as scratch_name:
        scratch = Path(scratch_name)
        directory = scratch / "journey"
        manifest = asyncio.run(seed_interaction(directory, pending_practice=True))
        os.environ["GROWTH_INTERACTION_DIRECTORY"] = str(directory)
        os.environ.pop("GROWTH_INTERACTION_REAL_MODEL", None)
        expected, checks = {}, {}
        with TestClient(create_local_interactive_app()) as client:
            cases = {
                "practice": (manifest["task_id"], "files", {
                    "request_id": "i5_practice_request", "filename": "evaluation.md",
                    "content_base64": base64.b64encode(
                        "# 受控评测\n\n十条RAG样本，引用对应来源；无匹配应报告不足。".encode()).decode(),
                }),
                "understanding": (manifest["interaction_task_id"], "submissions", {
                    "request_id": "i5_understanding_request",
                    "probe_answer": "受控理解回答：检索减少无来源生成，重排提高相关性；无匹配报告不足。",
                }),
            }
            for name, (task, endpoint, payload) in cases.items():
                activated = client.post(f"/api/tasks/{task}/actions", json={"action": "activate"})
                url = f"/api/tasks/{task}/{endpoint}"
                response = client.post(url, json=payload)
                if response.status_code != 200:
                    raise RuntimeError(f"{name}提交未完成：HTTP {response.status_code}")
                result = response.json()
                checks[f"{name}_activated"] = activated.status_code == 200
                checks[f"{name}_done"] = result["task"]["status"] == "done"
                checks[f"{name}_guards"] = all(result["attribution"]["guard"].values())
                expected[name] = {"task_id": task, "url": url, "payload": payload, "result": result}
        practice = expected["practice"]["result"]["attribution"]
        understanding = expected["understanding"]["result"]["attribution"]
        checks["practice_3_to_4_understanding_unchanged"] = (
            practice["before"]["practice"]["level"] == 3
            and practice["after"]["practice"]["level"] == 4
            and practice["after"]["understanding"]["level"] == 2)
        checks["understanding_2_to_3_practice_unchanged"] = (
            understanding["before"]["understanding"]["level"] == 2
            and understanding["after"]["understanding"]["level"] == 3
            and understanding["after"]["practice"]["level"] == 4)
        (directory / "expected.json").write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
        before_reopen = database_state(directory / "demo.db")
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--reopen", str(directory)],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
                               env={**os.environ, "PYTHONUTF8": "1"})
        reopened = json.loads(child.stdout)
        checks.update(reopened["checks"])
        checks["new_process_reopen"] = reopened["process_id"] != os.getpid()
        checks["replay_does_not_change_domain_database"] = before_reopen == database_state(directory / "demo.db")
        copies = [audit_copy(directory / "demo.db", scratch / "quality")]
        user_db = ROOT / "data/growth.db"
        if user_db.is_file():
            copies.append(audit_copy(user_db, scratch / "quality"))
        checks["QG1_audits_pass"] = all(c["before"]["status"] == "pass" and c["after"]["status"] == "pass" for c in copies)
        checks["QG2_damage_caught_and_restored"] = all(
            c["damage"]["status"] == "caught" and c["data_restored_except_audit_log"] for c in copies)
        checks["original_databases_unchanged"] = all(
            originals[str(p.relative_to(ROOT))] == database_state(p) for p in ORIGINALS if p.is_file())
        report = {"date": "2026-10-06", "scope": "受控本地交互，固定绑定规则，非真实模型验收",
                  "real_model_calls": 0, "checks": checks, "journey": expected,
                  "reopen": reopened, "quality_copies": copies,
                  "original_database_states": originals}
        (OUTPUT / "scenario.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        gc.collect()  # 上游审计的SQLite连接可能等循环回收后才释放Windows文件句柄。
        return report


def finalize():
    report = json.loads((OUTPUT / "scenario.json").read_text(encoding="utf-8"))
    growth = regression("artifacts/interaction/i5/growth-regression.xml")
    upstream = regression("artifacts/interaction/i5/evkg-regression.xml")
    secrets = secret_scan()
    report["checks"]["QG4_no_secrets"] = secrets["hit_count"] == 0 and secrets["env_ignored_and_untracked"]
    report["checks"]["QG5_growth_and_upstream_regression"] = growth["successful"] and upstream["successful"]
    markers = ("test_failure_is_recorded_without_false_completion", "test_concurrent_submit_and_state_change_are_rejected",
               "test_failed_binding_can_retry_without_duplicate_evidence", "test_interrupted_request_cannot_be_bypassed_with_new_id")
    report["checks"]["failure_and_concurrency_cases_pass"] = all(any(m in case for case in growth["cases"]) for m in markers)
    rating_markers = ("test_no_evidence_gives_insufficient_not_low_star",
                      "test_dimensions_are_independent", "test_done_task_does_not_imply_level_change",
                      "test_loop_never_writes_levels_or_bindings_directly")
    report["checks"]["QG3_rating_and_submission_boundaries"] = all(
        any(marker in case for case in growth["cases"]) for marker in rating_markers)
    report["regressions"] = {"growth": growth, "evkg": upstream}
    report["secret_scan"] = secrets
    browsers = {}
    for relative in ("artifacts/interaction/browser-verification.json", "artifacts/interaction/file-browser-verification.json"):
        value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        browsers[relative] = {"passed": value["passed"], "checks": value["checks"],
                              "evidence": fingerprint(relative), "reexecuted_in_i5": False}
    report["archived_browser_checks"] = browsers
    report["checks"]["I3_I4_browser_evidence_present"] = all(b["passed"] for b in browsers.values())
    report["all_checks_passed"] = all(report["checks"].values())
    report["source_evidence"] = [fingerprint(relative) for relative in (
        "backend/growth_os/api/interactive.py", "backend/growth_os/store/submission_journal.py",
        "backend/growth_os/demo.py", "frontend/src/components/TaskActions.tsx",
        "frontend/src/components/TaskTimeline.tsx", "frontend/src/api/growth.ts",
        "scripts/verify_interaction_final.py")]
    (OUTPUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["all_checks_passed"], "checks": len(report["checks"]),
                      "growth_tests": growth["tests"], "upstream_tests": upstream["tests"]}))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reopen", type=Path)
    parser.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.reopen:
        print(json.dumps(reopen(args.reopen), ensure_ascii=False))
    elif args.prepare:
        result = prepare()
        print(json.dumps({"checks": result["checks"]}, ensure_ascii=False))
    else:
        sys.exit(finalize())
