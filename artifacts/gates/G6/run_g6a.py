"""G6-a 受控演练：真实任务闭环 + 只读返回输出；不是完整 G6 判定。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

from growth_os.agent import FakeGateway
from growth_os.agent.return_summary import GrowthReturnAgent
from growth_os.assessment import BINDING_TASK, TaskLoop
from growth_os.evidence import adapter
from growth_os.memory import MemoryProjection, MemoryService
from growth_os.store import GrowthStore
from task_loop_fixtures import create_active_task, make_binding_proposer, seed_scenario


async def run(directory: Path) -> dict:
    store = GrowthStore(str(directory / "scenario.db"))
    evidence = adapter.open_store(directory / "scenario.db")
    try:
        scenario = seed_scenario(store, evidence, directory, leaf_only=True)
        memory = MemoryService(store).remember(
            layer="profile", key="learning_style", value={"text": "喜欢代码实践，先看架构再看源码"},
            source_kind="user_statement", source_id="statement_g6a_constructed_preference")
        baseline = MemoryProjection(store).project()["snapshots"][0]["id"]
        task = create_active_task(store, scenario["gaps"]["practice"])
        submission = directory / "evaluation.md"
        submission.write_text("# 受控评测报告\n\n十条检索样本与判定标准。\n", encoding="utf-8")
        loop = TaskLoop(store=store, evidence_store=evidence,
                        gateway=FakeGateway({BINDING_TASK: make_binding_proposer(
                            path=scenario["capability_path"])}),
                        submission_dir=directory / "submissions")
        outcome = await loop.complete_task(task, artifact_path=submission)
        MemoryProjection(store).project()
        current = next(row["id"] for row in store.list_snapshots() if row["id"] != baseline)
        before_read = list(store.db.iterdump())
        store.db.execute("PRAGMA query_only=ON")
        response = GrowthReturnAgent(store).summarize(
            goal_id=scenario["goal_id"], baseline_snapshot_id=baseline,
            current_snapshot_id=current, returned_at=datetime.now(UTC) + timedelta(days=1))
        checks = {
            "practice_3_to_4": response["summary"]["changes"][0]["before_level"] == 3
            and response["summary"]["changes"][0]["after_level"] == 4,
            "understanding_unchanged": response["current_state"][0]["understanding"] == 2,
            "next_step_cites_open_gap": response["next_steps"][0]["gap_id"]
            == scenario["gaps"]["understanding"]["id"],
            "preference_cites_memory": response["preferences"][0]["memory_id"] == memory["id"],
            "response_has_no_writes": list(store.db.iterdump()) == before_read,
            "loop_guard_all_true": all(outcome["attribution"]["guard"].values()),
        }
        return {"stage": "G6-a", "constructed": True, "model_requests": 0,
                "method": "现有受控任务闭环；次日时钟注入；本阶段未关闭后重新打开连接",
                "full_g6_accepted": False, "checks": checks,
                "all_checks_passed": all(checks.values()), "response": response,
                "snapshots": [store.get_snapshot(baseline), store.get_snapshot(current)],
                "source_code": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                for path in ["backend/growth_os/agent/return_summary.py",
                                             "backend/growth_os/store/growth_store.py",
                                             "artifacts/gates/G6/run_g6a.py"]}}
    finally:
        evidence.db.close()
        store.close()


def main() -> None:
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="g6a-", dir=scratch) as directory:
        result = asyncio.run(run(Path(directory)))
    (Path(__file__).parent / "g6a-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": result["checks"], "full_g6_accepted": False}, ensure_ascii=False))
    if not result["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
