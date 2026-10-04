"""G5：gap → 真实任务生成 → 提交 → 新证据 → 重评 → 能力变化（单条命令）。

冻结口径（`M5-PLAN.md` §7/§12，用户 2026-10-03 确认）：

* 主轴：实践 3 → 4，`level_gap_1` 关闭；理解缺口保持 open（反向验证）；
* 单能力点树（只给绑定提示一个路径，避免 M5-c 记录过的多层选错）；
* 预算：生成 ≤2 + 绑定 ≤1 = **≤3 HTTP**；零额外重试、fail-stop；
* 全程无手工 SQL / 改库 / 中途补步骤；提交物为受控构造并如实标注。

offline 只验证运行器判定（0 HTTP）；G5 门证据必须来自 `--mode real`。
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from growth_os.agent import FakeGateway
from growth_os.assessment import (
    BINDING_TASK,
    TaskLoop,
    trace_task,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from growth_os.tasks import TASK_GENERATION_TASK, TaskGenerator, TaskProposal
from task_loop_fixtures import GOAL_ID, make_binding_proposer, seed_scenario

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
GATE = REPO / "artifacts" / "gates" / "G5"
SUBMISSION = HERE / "submission" / "rag-eval-set.md"
HTTP_CAP = 3


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_check() -> dict:
    anchor = _load(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    hashes = {table: digest(table) for table in tables}
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    g_tables = sorted(
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g_%'"
        ).fetchall()
    )
    conn.close()
    return {
        "content_hashes_match": all(hashes[t] == anchor["table_content_sha256"][t] for t in tables),
        "counts_match": counts == anchor["table_counts"],
        "g_tables_in_real_db": g_tables,
    }


def offline_proposer(index: int, system: str, user: str):
    if '"probe_answer"' in user:
        return TaskProposal.model_validate(
            {
                "title": "现场作答：RAG 检索流程五问",
                "objective": "产出一份现场作答记录，覆盖切分、向量化、召回、重排、评测五个环节",
                "deliverable_type": "probe_answer",
                "est_minutes": 25,
                "acceptance_type": "probe_rubric",
                "acceptance": "提交作答正文，按五个环节逐项核对要点是否完整",
            }
        )
    return TaskProposal.model_validate(
        {
            "title": "写一个 10 条样本的检索评测集",
            "objective": "产出一份 Markdown 评测集，覆盖 10 条检索样本与判定标准",
            "deliverable_type": "markdown",
            "est_minutes": 60,
            "acceptance_type": "artifact_check",
            "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
        }
    )


def run(mode: str) -> dict:
    workdir = HERE / "tmp" / mode
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "g5.db"
    db.unlink(missing_ok=True)
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    budget = None
    try:
        scenario = seed_scenario(store, estore, workdir, leaf_only=True)
        practice = scenario["gaps"]["practice"]
        understanding = scenario["gaps"]["understanding"]
        if mode == "offline":
            gateway = FakeGateway(
                responses={
                    TASK_GENERATION_TASK: offline_proposer,
                    BINDING_TASK: make_binding_proposer(path=scenario["capability_path"]),
                }
            )
        else:
            from goal_flow_fixtures import HttpRequestBudget

            if os.getenv("M5_ALLOW_REAL_MODEL") != "1" and os.getenv("M4_ALLOW_REAL_MODEL") != "1":
                print("拒绝发起真实模型调用（未设 M5_ALLOW_REAL_MODEL=1 或 M4_ALLOW_REAL_MODEL=1）。")
                raise SystemExit(2)
            os.environ["EVKG_HTTP_RETRIES"] = "1"
            gateway = adapter.agent_gateway()
            budget = HttpRequestBudget(cap=HTTP_CAP).install()

        generator = TaskGenerator(store=store, gateway=gateway, goal_id=GOAL_ID)
        generation = asyncio.run(generator.propose_many([practice["id"]]))
        decision = generation["decisions"][0]
        task_id = decision["task_id"]
        store.activate_task(task_id)
        loop = TaskLoop(
            store=store,
            evidence_store=estore,
            gateway=gateway,
            submission_dir=workdir / "submissions",
            report_directory=GATE / "reports",
        )
        outcome = asyncio.run(
            loop.complete_task(task_id, artifact_path=SUBMISSION, note="G5 端到端")
        )
        attribution = outcome["attribution"]
        trace = trace_task(store, estore, task_id=task_id)
        audit = adapter.audit(db)
        gaps = {item["id"]: item for item in store.list_gaps(capability_id=scenario["capability"])}
        requests = 0 if budget is None else budget.requests
        checks = {
            "generation_accepted": decision["accepted"] is True,
            "practice_3_to_4": attribution["before"]["practice"]["level"] == 3
            and attribution["after"]["practice"]["level"] == 4,
            "practice_gap_closed": gaps[practice["id"]]["status"] == "closed",
            "understanding_gap_open": gaps[understanding["id"]]["status"] == "open",
            "understanding_unchanged": attribution["before"]["understanding"]["level"]
            == attribution["after"]["understanding"]["level"] == 2,
            "new_source_present": bool(attribution["submission"]["source_id"]),
            "trace_complete": trace["complete"] is True,
            "guard_all_true": all(attribution["guard"].values()),
            "audit_pass": audit.get("status") == "pass" and not (
                audit.get("violations") or audit.get("total_violations")
            ),
            "within_budget": requests <= HTTP_CAP and (mode == "offline" or requests > 0),
            "single_capability_tree": len(store.list_capabilities(GOAL_ID, status="active")) == 1,
        }
        result = {
            "mode": f"g5-{mode}",
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "checks": checks,
            "checks_passed": sum(1 for value in checks.values() if value),
            "checks_total": len(checks),
            "all_checks_passed": all(checks.values()),
            "detail": {
                "requests": requests,
                "cap": HTTP_CAP,
                "provider": generation.get("provider"),
                "model": generation.get("model"),
                "task_id": task_id,
                "task": store.get_task(task_id),
                "before": attribution["before"],
                "after": attribution["after"],
                "submission": attribution["submission"],
                "claim": attribution["claim"],
                "binding": attribution["binding"],
                "gaps": attribution["gaps"],
                "guard": attribution["guard"],
                "trace": trace,
                "audit": {"status": audit.get("status"), "violations": audit.get("violations")},
                "real_db_anchors": anchor_check(),
                "constructed_submission": True,
            },
        }
    finally:
        if budget is not None:
            budget.uninstall()
        estore.db.close()
        store.close()
        gc.collect()
        db.unlink(missing_ok=True)

    target = HERE / ("result-real.json" if mode == "real" else "result.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if mode == "real" and result["all_checks_passed"]:
        write_gate(result)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "checks_passed": result["checks_passed"],
                "checks_total": result["checks_total"],
                "failed": [key for key, value in result["checks"].items() if not value],
                "requests": result["detail"]["requests"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def write_gate(result: dict) -> None:
    GATE.mkdir(parents=True, exist_ok=True)
    detail = result["detail"]
    payloads = {
        "inputs.json": {
            "mode": "real",
            "goal_id": GOAL_ID,
            "materials": "受控构造（growth_constructed=true，如实标注）",
            "submission": str(SUBMISSION.relative_to(REPO)),
            "tree": "单能力点（避免多层绑定选错）",
            "budget_cap": HTTP_CAP,
        },
        "before-after.json": {"before": detail["before"], "after": detail["after"]},
        "attribution.json": {
            "task_id": detail["task_id"],
            "submission": detail["submission"],
            "claim": detail["claim"],
            "binding": {
                "provider": detail["binding"]["provider"],
                "model": detail["binding"]["model"],
                "run_id": detail["binding"]["run_id"],
                "accepted_proposal_ids": detail["binding"]["accepted_proposal_ids"],
            },
            "gaps": detail["gaps"],
            "guard": detail["guard"],
            "trace_complete": detail["trace"]["complete"],
        },
        "checks.json": {
            "checks": result["checks"],
            "requests": detail["requests"],
            "audit": detail["audit"],
            "real_db_anchors": detail["real_db_anchors"],
            "all_checks_passed": result["all_checks_passed"],
        },
    }
    for name, payload in payloads.items():
        (GATE / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (GATE / "README.md").write_text(
        "# G5 · 成长闭环门\n\n"
        f"- 判定：**{'通过' if result['all_checks_passed'] else '未通过'}**（模式 real）\n"
        f"- 链路：gap → 真实任务生成 → activate → 提交 → 单入口证据 → 材料 claim → "
        "绑定闸门 → M4-e 重评 → 归因\n"
        f"- 主轴：实践 {detail['before']['practice']['level']} → "
        f"{detail['after']['practice']['level']}；实践缺口关闭；理解缺口保持 open\n"
        f"- 预算：{detail['requests']}/{HTTP_CAP} HTTP（零额外重试）\n"
        f"- provenance：trace_task complete={detail['trace']['complete']}\n"
        "- 提交物：受控构造并标注（验证闭环机制，不代表用户本人完成任务）\n"
        "- 运行记录：`artifacts/g5/result-real.json`\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="G5 成长闭环（offline / real）")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    args = parser.parse_args()
    result = run(args.mode)
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
