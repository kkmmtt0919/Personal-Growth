"""G6-b：独立受控库，种子进程退出连接后由新进程读取并验证返回 API。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from growth_os.api.local import create_local_app
from growth_os.demo import seed_demo
from growth_os.store import GrowthStore

OUTPUT = Path(__file__).parent / "g6b-result.json"


def verify(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    context = manifest["return_context"]
    store = GrowthStore(str(directory / "demo.db"))
    try:
        before = list(store.db.iterdump())
        snapshots = [store.get_snapshot(context[key])
                     for key in ("baseline_snapshot_id", "current_snapshot_id")]
        os.environ["GROWTH_DEMO_DIRECTORY"] = str(directory)
        with TestClient(create_local_app()) as client:
            response = client.get(f"/api/return-demo/{manifest['goal_id']}")
            if response.status_code != 200:
                raise ValueError(f"返回 API 失败：{response.status_code}")
            body = response.json()
            forbidden = client.post(f"/api/return-demo/{manifest['goal_id']}", json={})
        report = body["report"]
        change = report["summary"]["changes"][0]
        gap = store.get_gap(report["next_steps"][0]["gap_id"])
        memory = store.get_memory(report["preferences"][0]["memory_id"])
        checks = {
            "new_process_reads_persistent_state": os.getpid() != context["seed_process_id"],
            "both_snapshots_persisted": all(snapshots),
            "practice_3_to_4": (change["before_level"], change["after_level"]) == (3, 4)
            and change["dimension"] == "practice",
            "understanding_stays_2": report["current_state"][0]["understanding"] == 2,
            "next_step_cites_open_understanding_gap": gap["status"] == "open"
            and gap["dimension"] == "understanding",
            "preference_persisted_and_cited": memory["source_id"]
            == report["preferences"][0]["source_id"] == "statement_demo_constructed_preference",
            "before_after_assessment_sources_exist": bool(store.get_assessment(change["before_assessment_id"]))
            and bool(store.get_assessment(change["after_assessment_id"])),
            "read_api_has_no_writes": before == list(store.db.iterdump()),
            "post_rejected": forbidden.status_code == 405,
            "simulation_explicit": body["constructed"] is True and body["simulated_return"] is True,
        }
        return {
            "stage": "G6-b", "constructed": True, "model_requests": 0,
            "full_g6_accepted": False, "seed_process_id": context["seed_process_id"],
            "return_process_id": os.getpid(), "directory": str(directory),
            "checks": checks, "all_checks_passed": all(checks.values()),
            "response": body, "snapshots": snapshots,
            "snapshot_diff": report["summary"]["changes"],
            "source_code": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                            for path in ["backend/growth_os/demo.py", "backend/growth_os/api/local.py",
                                         "backend/growth_os/agent/return_summary.py",
                                         "artifacts/gates/G6/run_g6b.py",
                                         "frontend/src/components/ReturnSummary.tsx"]},
        }
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="受控隔天返回：新进程持久化验证")
    parser.add_argument("--directory", type=Path, default=ROOT / "data" / "demo-return")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    directory = args.directory.resolve()
    if args.verify_only:
        result = verify(directory)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result["checks"], ensure_ascii=False))
        raise SystemExit(0 if result["all_checks_passed"] else 1)
    if not (directory / "demo.db").exists():
        asyncio.run(seed_demo(directory, include_return=True))
    # seed_demo 的 finally 已关闭两种存储；子进程只能从磁盘和 manifest 获取来源。
    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--verify-only",
                             "--directory", str(directory)], env=env, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
