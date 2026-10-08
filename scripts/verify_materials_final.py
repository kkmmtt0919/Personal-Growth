"""个人材料入库/确认/任务衔接：独立库、新进程恢复、副本审计与隔离。"""

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

from growth_os.api.onboarding import create_local_onboarding_app, seed_onboarding
from growth_os.store import GrowthStore
from verify_g6_final import audit_copy, database_state, regression, secret_scan

OUTPUT = ROOT / "artifacts/personal-materials"


def configure(directory):
    os.environ["GROWTH_ONBOARDING_DIRECTORY"] = str(directory)
    os.environ.pop("GROWTH_ONBOARDING_REAL_MODEL", None)


def reopen(directory):
    configure(directory)
    expected = json.loads((directory / "expected.json").read_text(encoding="utf-8"))
    with TestClient(create_local_onboarding_app()) as client:
        actual = client.get(expected["path"]).json()["materials"]
        replay = client.post(expected["path"], json=expected["payload"])
        return {"pid": os.getpid(), "checks": {
            "persisted_material": actual == [expected["record"]],
            "replayed_upload": replay.status_code == 200 and replay.json() == expected["record"],
        }}


def verify():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    originals = [ROOT / relative for relative in ("data/growth.db", "data/demo/demo.db",
                 "data/demo-return/demo.db", "data/interactive/demo.db", "data/onboarding/onboarding.db")]
    before = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks = {}
    with tempfile.TemporaryDirectory(prefix="materials-", dir=ROOT / "tmp") as scratch_name:
        scratch = Path(scratch_name)
        directory = scratch / "journey"
        seed_onboarding(directory)
        configure(directory)
        with TestClient(create_local_onboarding_app()) as client:
            state = client.post("/api/onboarding/goals", json={"request_id": "materials_goal", "text": "整理写作作品集"}).json()
            base = f"/api/onboarding/goals/{state['goal']['id']}"
            for index, text in enumerate(["写作", "作品集", "三个月", "三篇文章"], 1):
                assert client.post(base + "/answers", json={"round": index, "text": text}).status_code == 200
            assert client.post(base + "/confirm", json={"quote": "确认目标"}).status_code == 200
            state = client.post(base + "/capabilities").json()
            leaf = next(node for node in state["capabilities"] if node["depth"] == 3)
            path = base + "/materials"
            payload = {"request_id": "materials_document", "filename": "notes.md", "capability_id": leaf["id"],
                       "evidence_type": "uploaded_doc", "attribution": "user_declared",
                       "content_base64": base64.b64encode("# 写作笔记\n已有材料逐字内容、例子和局限。".encode()).decode()}
            response = client.post(path, json=payload)
            assert response.status_code == 200, response.text
            preview = response.json()
            checks["raw_quotes_visible"] = any("已有材料逐字内容" in item["text"] for item in preview["quotes"])
            checks["preview_replay"] = client.post(path, json=payload).json() == preview
        with GrowthStore(str(directory / "onboarding.db")) as store:
            checks["preview_no_binding_or_assessment"] = not store.list_capability_claims(capability_id=leaf["id"]) and not store.list_assessments(capability_id=leaf["id"])
        expected_path = directory / "expected.json"

        def check_reopen(record, stage):
            expected_path.write_text(json.dumps({"path": path, "payload": payload, "record": record}, ensure_ascii=False), encoding="utf-8")
            process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--reopen", str(directory)],
                                     capture_output=True, text=True, encoding="utf-8", check=False)
            if process.returncode:
                raise RuntimeError(process.stderr)
            result = json.loads(process.stdout)
            checks[f"{stage}_new_process"] = result["pid"] != os.getpid()
            checks.update({f"{stage}_{key}": value for key, value in result["checks"].items()})
            return result

        restored_preview = check_reopen(preview, "preview")
        with TestClient(create_local_onboarding_app()) as client:
            confirmation = path + "/materials_document/confirm"
            response = client.post(confirmation, json={"confirm": True})
            assert response.status_code == 200, response.text
            confirmed = response.json()
            checks["explicit_confirmation_gate"] = confirmed["binding_status"] == "confirmed" and confirmed["decision"]["accepted"]
            checks["confirmation_replay"] = client.post(confirmation, json={"confirm": True}).json() == confirmed
            evidence = client.get(f"/api/evidence/{leaf['id']}").json()
            checks["confirmed_original_quote_visible"] = len(evidence["supports"]) == 1 and "已有材料逐字内容" in evidence["supports"][0]["quote"]["text"]
            task_path = base + f"/capabilities/{leaf['id']}/tasks"
            response = client.post(task_path, json={"dimension": "practice"})
            assert response.status_code == 200, response.text
            task = response.json()["task"]
            checks["material_to_gap_task"] = task["status"] == "proposed" and bool(response.json()["assessment"]["gaps"])
        restored_confirmation = check_reopen(confirmed, "confirmed")
        with GrowthStore(str(directory / "onboarding.db")) as store:
            checks["single_binding"] = len(store.list_capability_claims(capability_id=leaf["id"])) == 1
            checks["task_provenance"] = store.get_gap(task["gap_id"])["assessment_id"] is not None
        audit = audit_copy(directory / "onboarding.db", scratch / "audit")
        checks["audit_clean"] = audit["before"]["status"] == "pass" and audit["after"]["status"] == "pass"
        checks["damage_caught_restored"] = audit["damage"]["status"] == "caught" and audit["data_restored_except_audit_log"]
        gc.collect()
    after = {path.relative_to(ROOT).as_posix(): database_state(path) for path in originals if path.is_file()}
    checks["original_databases_unchanged"] = before == after
    growth = regression("artifacts/personal-materials/regression.xml")
    upstream = regression("artifacts/personal-materials/evkg-regression.xml")
    focused = regression("artifacts/personal-materials/final-focused.xml")
    browser = json.loads((OUTPUT / "browser-verification.json").read_text(encoding="utf-8"))
    secrets = secret_scan()
    checks["regressions_pass"] = growth["successful"] and upstream["successful"]
    checks["final_recovery_checks_pass"] = focused["successful"]
    checks["browser_pass"] = browser["passed"] and len(browser["checks"]) == 27
    checks["no_secrets"] = secrets["hit_count"] == 0 and secrets["env_ignored_and_untracked"]
    report = {"passed": all(checks.values()), "checks": checks, "real_model_calls": 0,
              "preview": preview, "confirmed": confirmed, "task": task,
              "process_restores": [restored_preview, restored_confirmation], "copy_audit": audit,
              "originals_before": before, "originals_after": after, "secret_scan": secrets,
              "regressions": {"growth": growth, "upstream": upstream, "final_focused": focused}}
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
