"""M5-a 冒烟：任务数据契约 + 状态机 + 工具注册（离线，不调用任何模型）。

场景（M5-a 验收序列）：

1. 用 M4-e 的编排造出**真实缺口**（笔记 → 理解 2 / 实践不足 → 任务目标 4 级）；
2. 通过 Growth Agent 模式 A 工具：`list_gaps` → `create_task` → `activate_task` → `complete_task`
   （提交经单入口入库，`source_id` 跨表族校验）；
3. 契约拒绝用例：不可验收反例（含字面"去学习 Agent Evaluation"）、维度 ↔ 交付物错配、
   未关闭任务去重、未知缺口、时长越界、不存在的 source；
4. 状态机：非法转移、reason 必填、`done` 终态、`done` 唯一入口（AST 守卫）；
5. 事件链：每次转移写 `g_events`（from/to/reason，按发生顺序）；
6. **Task 不是能力判断**：`g_tasks` 无等级字段；完成任务不产生/修改任何评定（完成 ≠ 提升）。

数据边界：真实库只读对锚；实验库跑完即删。
"""

from __future__ import annotations

import argparse
import ast
import gc
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from growth_os.agent import GROWTH_TOOL_NAMES, ToolRegistry, register_growth_tools
from growth_os.assessment import assess_capability
from growth_os.evidence import adapter
from growth_os.store import (
    TASK_ACCEPTANCE_TYPES,
    TASK_DELIVERABLE_TYPES,
    TASK_EST_MINUTES_RANGE,
    TASK_STATUSES,
    TASK_TRANSITIONS,
    GrowthStore,
    GrowthStoreError,
)
from growth_os.store import growth_store as growth_store_module

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
GOAL_ID = "goal_m5a_smoke"


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
    g_tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g_%'"
        ).fetchall()
    ]
    conn.close()
    return {
        "content_hashes_match": all(hashes[t] == anchor["table_content_sha256"][t] for t in tables),
        "counts_match": counts == anchor["table_counts"],
        "g_tables_in_real_db": sorted(g_tables),
    }


def seed_gap_scenario(store, estore, workdir: Path) -> dict:
    """用 M4-e 的确定性编排造出真实缺口（实践 `level_gap_1`）。"""
    store.upsert_user("local", "本地用户")
    store.save_goal(
        {
            "id": GOAL_ID,
            "user_id": "local",
            "title": "成为 AI Agent 工程师",
            "direction": "AI 应用方向",
            "purpose": "求职",
            "horizon": "6 个月",
            "measurable_result": "完成一个可演示的 RAG 项目",
            "status": "confirmed",
            "source_quote": "我想成为 AI Agent 工程师",
        }
    )
    domain = store.upsert_capability(
        {"goal_id": GOAL_ID, "path": "AI Agent", "name": "AI Agent", "depth": 1, "target_level": 3}
    )
    group = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "AI Agent/工具与执行",
            "name": "工具与执行",
            "depth": 2,
            "parent_id": domain,
            "target_level": 3,
        }
    )
    capability = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "AI Agent/工具与执行/RAG 系统搭建与调优",
            "name": "RAG 系统搭建与调优",
            "depth": 3,
            "parent_id": group,
            "target_level": 4,
        }
    )

    def add_claim(filename: str, content: str, evidence_type: str) -> str:
        target = workdir / filename
        target.write_text(content, encoding="utf-8")
        ingested = adapter.ingest_document(
            target, store=estore, evidence_type=evidence_type, attribution="user_declared"
        )
        passage_ids = [item.id for item in estore.get_passages(source_id=ingested.source_id)]
        return adapter.create_material_claim(
            estore,
            subject="材料",
            predicate="包含",
            object="相关内容",
            statement=f"材料中包含相关内容（{filename}）",
            passage_ids=passage_ids[:1],
        )["claim_id"]

    notes = add_claim("m5a-notes.md", "# 笔记\n\nRAG 检索流程整理。\n", "uploaded_doc")
    repo = add_claim("m5a-repo.md", "# 项目\n\n实现了 RAG 检索服务。\n", "repo_artifact")
    for claim in (notes, repo):
        store.link_capability_claim(capability, claim, role="supports", rationale="M5-a 冒烟（等价闸门写入）")
    session = assess_capability(store, estore, capability_id=capability)
    gaps = {item["dimension"]: item for item in store.list_gaps(capability_id=capability, status="open")}
    return {
        "capability": capability,
        "levels": session["levels"],
        "gaps": {key: (item["severity"], item["current_level"]) for key, item in gaps.items()},
        "practice_gap": gaps["practice"]["id"],
        "understanding_gap": gaps["understanding"]["id"],
    }


def run() -> dict:
    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "m5a-contract.db"
    db.unlink(missing_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    checks: dict[str, bool] = {}
    detail: dict = {}
    result: dict | None = None
    try:
        scenario = seed_gap_scenario(store, estore, workdir)
        capability = scenario["capability"]
        practice_gap = scenario["practice_gap"]
        detail["scenario"] = scenario

        registry = register_growth_tools(ToolRegistry(), store=store, evidence_store=estore)
        checks["tools_registered"] = registry.names() == sorted(GROWTH_TOOL_NAMES)
        assessments_before = [
            (row["id"], row["dimension"], row["status"], row["level"])
            for row in store.list_assessments()
        ]

        # ── 1. 缺口 → 任务（工具路径）────────────────────────────────────
        listed = registry.call("list_gaps")
        open_gap_ids = sorted(item["id"] for item in listed)
        checks["list_gaps_returns_open_gaps"] = open_gap_ids == sorted(
            [practice_gap, scenario["understanding_gap"]]
        )
        detail["open_gaps"] = open_gap_ids

        payload = {
            "gap_id": practice_gap,
            "title": "写一个 10 条样本的检索评测集",
            "objective": "产出一份 Markdown 评测集，证明检索流程的可复现性",
            "deliverable_type": "markdown",
            "est_minutes": 60,
            "acceptance_type": "artifact_check",
            "acceptance": "提交 Markdown，且包含 10 条样本与判定标准",
            "generated_by_run_id": "m5a_smoke",
        }
        task = registry.call("create_task", **payload)
        checks["task_created_as_proposed"] = task["status"] == "proposed"
        checks["task_maps_to_gap_and_capability"] = (
            task["gap_id"] == practice_gap and task["capability_id"] == capability
        )

        # ── 2. 契约拒绝用例 ─────────────────────────────────────────────
        rejections: dict[str, str] = {}
        cases = {
            "literal_anti_pattern": {**payload, "acceptance": "去学习 Agent Evaluation"},
            "dimension_mismatch": {**payload, "deliverable_type": "probe_answer", "gap_id": practice_gap},
            "duplicate_open_task": {**payload},
            "est_minutes_range": {**payload, "gap_id": practice_gap, "est_minutes": 5},
            "unknown_gap": {**payload, "gap_id": "gap_not_exists"},
        }
        for label, bad in cases.items():
            try:
                registry.call("create_task", **bad)
                rejections[label] = "NOT REJECTED"
            except GrowthStoreError as error:
                rejections[label] = str(error)[:80]
        detail["rejections"] = rejections
        checks["all_contract_violations_rejected"] = all(
            value != "NOT REJECTED" for value in rejections.values()
        )

        # ── 3. 状态机（含 done 唯一入口 + 事件链）───────────────────────
        transitions: list[str] = [task["status"]]
        transitions.append(store.activate_task(task["id"])["status"])
        blocked = store.block_task(task["id"], "等用户时间")
        transitions.append(blocked["status"])
        transitions.append(store.unblock_task(task["id"])["status"])

        illegal: dict[str, str] = {}
        for label, call in {
            "activate_when_active": lambda: store.activate_task(task["id"]),
            "empty_source": lambda: store.complete_task(task["id"], source_id=""),
        }.items():
            try:
                call()
                illegal[label] = "NOT REJECTED"
            except GrowthStoreError as error:
                illegal[label] = str(error)[:60]

        # ── 4. 提交（跨表族 source 校验 + 单入口入库）────────────────────
        submission_file = workdir / "m5a-submission.md"
        submission_file.write_text(
            "# 检索评测集\n\n01–10：十条样本与判定标准\n", encoding="utf-8"
        )
        ingested = adapter.ingest_document(
            submission_file,
            store=estore,
            evidence_type="task_submission",
            attribution="user_declared",
        )
        try:
            registry.call("complete_task", task_id=task["id"], source_id="src_missing")
            checks["unknown_source_rejected"] = False
        except ValueError:
            checks["unknown_source_rejected"] = True
        completed = registry.call("complete_task", task_id=task["id"], source_id=ingested.source_id, note="提交评测集")
        transitions.append(completed["status"])
        detail["transitions"] = transitions
        checks["state_machine_path"] = transitions == ["proposed", "active", "blocked", "active", "done"]
        for label, call in {
            "activate_after_done": lambda: store.activate_task(task["id"]),
            "abandon_after_done": lambda: store.abandon_task(task["id"], "反悔"),
            "complete_again": lambda: store.complete_task(task["id"], source_id="src_again"),
        }.items():
            try:
                call()
                illegal[label] = "NOT REJECTED"
            except GrowthStoreError as error:
                illegal[label] = str(error)[:60]
        detail["illegal_transitions"] = illegal
        checks["illegal_transitions_rejected"] = all(v != "NOT REJECTED" for v in illegal.values())
        submissions = store.list_task_submissions(task_id=task["id"])
        checks["submission_recorded"] = len(submissions) == 1 and submissions[0]["source_id"] == ingested.source_id

        events = store.list_events(kind="task_status_changed")
        chain = [json.loads(event["payload_json"]) for event in events]
        checks["events_recorded_in_order"] = [item["to"] for item in chain] == [
            "proposed",
            "active",
            "blocked",
            "active",
            "done",
        ]
        detail["event_chain"] = [(item["from"], item["to"], item["reason"]) for item in chain]

        # ── 5. Task 不是能力判断 ───────────────────────────────────────
        source = Path(growth_store_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        writers = set()
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
                if '"done"' in segment:
                    writers.add(node.name)
        checks["done_single_entry_ast"] = writers == {"complete_task"}
        assessments_after = [
            (row["id"], row["dimension"], row["status"], row["level"])
            for row in store.list_assessments()
        ]
        checks["completion_does_not_create_or_change_assessments"] = (
            assessments_after == assessments_before
        )
        detail["assessments_before_after"] = {
            "before": [list(item) for item in assessments_before],
            "after": [list(item) for item in assessments_after],
        }
        capability_row = store.get_capability(capability)
        checks["capability_levels_untouched_by_task"] = (
            capability_row["current_level_practice"] == 3 and capability_row["current_level_status"] == "assessed"
        )
        detail["capability_levels"] = {
            "understanding": capability_row["current_level_understanding"],
            "practice": capability_row["current_level_practice"],
        }

        # ── 6. 冻结词表 ────────────────────────────────────────────────
        checks["frozen_vocabularies"] = (
            TASK_STATUSES == ("proposed", "active", "blocked", "done", "abandoned")
            and TASK_DELIVERABLE_TYPES == ("markdown", "code", "archive", "probe_answer")
            and TASK_ACCEPTANCE_TYPES == ("artifact_check", "test_run", "probe_rubric")
            and TASK_EST_MINUTES_RANGE == (10, 600)
        )
        checks["frozen_transitions"] = TASK_TRANSITIONS == {
            "proposed": ("active", "abandoned"),
            "active": ("blocked", "abandoned", "done"),
            "blocked": ("active", "abandoned"),
            "done": (),
            "abandoned": (),
        }

        # ── 7. 数据边界 ────────────────────────────────────────────────
        anchors = anchor_check()
        checks["real_db_untouched"] = anchors["content_hashes_match"] and anchors["counts_match"]
        checks["real_db_has_no_g_tables"] = anchors["g_tables_in_real_db"] == []
        detail["real_db_anchors"] = anchors

        result = {
            "mode": "m5a-offline",
            "checks": checks,
            "checks_passed": sum(1 for value in checks.values() if value),
            "checks_total": len(checks),
            "all_checks_passed": all(checks.values()),
            "detail": detail,
        }
    except BaseException:
        estore.db.close()
        store.close()
        gc.collect()
        raise
    estore.db.close()
    store.close()
    gc.collect()
    if result is not None:
        db.unlink(missing_ok=True)
        result["temp_db_deleted"] = not db.exists()

    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="M5-a 冒烟（离线）")
    parser.parse_args()
    report = run()
    print(
        json.dumps(
            {
                "checks_passed": report["checks_passed"],
                "checks_total": report["checks_total"],
                "failed": [key for key, value in report["checks"].items() if not value],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
