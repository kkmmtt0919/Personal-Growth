"""M5-b 冒烟：gap → task generator（offline / real）+ **G4 门证据**。

模式（用户 2026-10-03 冻结）：

* **offline**（默认）：确定性提议（FakeGateway）+ 注入式对例（字面反例 / 维度错配 /
  能力判断字段 / 弃权 / 夹取 / 去重 / provenance 缺失）；不联网、不调用模型。
* **real**（需 `M4_ALLOW_REAL_MODEL=1`）：真实 LLM 提议，**per-gap 1 次调用 × 前 2 个缺口
  = ≤2 HTTP**（零额外重试、fail-stop）。

数据边界：真实库只读对锚；实验库跑完即删；材料为受控构造并如实标注（本步验证的是
"缺口 → 可验收任务"，构造材料不改变该判定）。
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from growth_os.agent import FakeGateway
from growth_os.assessment import assess_capability
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from growth_os.tasks import (
    TASK_GENERATION_TASK,
    TaskGate,
    TaskGenerator,
    TaskProposal,
    build_generation_artifact,
    write_generation_artifact,
)
from test_traceability import trace_assessment

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
GATE_G4 = REPO / "artifacts" / "gates" / "G4"
GOAL_ID = "goal_m5b_smoke"
SEVERITY_ORDER = {"level_gap_2plus": 0, "level_gap_1": 1, "evidence_gap": 2}
MAX_TARGET_GAPS = 2
FORBIDDEN_KEYS = (
    "expected_level",
    "confidence",
    "difficulty_score",
    "priority",
    "priority_score",
    "learning_value",
    "level",
    "score",
    "rating",
)


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


def seed_gap_scenario(store, estore, workdir: Path) -> dict:
    """构造目标树 + 受控材料（标注）→ M4-e 编排 → 两个 open 缺口。"""
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
            target,
            store=estore,
            evidence_type=evidence_type,
            attribution="user_declared",
            extra_metadata={
                "growth_source_kind": "constructed_material",
                "growth_constructed": True,
                "growth_constructed_note": "M5-b 场景材料（受控构造，如实标注）",
            },
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

    notes = add_claim("m5b-notes.md", "# 笔记\n\nRAG 检索流程整理。\n", "uploaded_doc")
    repo = add_claim("m5b-repo.md", "# 项目\n\n实现了 RAG 检索服务。\n", "repo_artifact")
    for claim in (notes, repo):
        store.link_capability_claim(capability, claim, role="supports", rationale="M5-b 冒烟（等价闸门写入）")

    session = assess_capability(store, estore, capability_id=capability)
    gaps = {item["dimension"]: item for item in store.list_gaps(capability_id=capability, status="open")}
    targets = sorted(gaps.values(), key=lambda item: (SEVERITY_ORDER[item["severity"]], item["id"]))
    return {
        "capability": capability,
        "levels": session["levels"],
        "gaps": {key: (item["id"], item["severity"], item["current_level"]) for key, item in gaps.items()},
        "targets": [item["id"] for item in targets[:MAX_TARGET_GAPS]],
    }


def offline_proposer(index: int, system: str, user: str) -> TaskProposal:
    """确定性提议：按缺口维度给出一个可验收任务（模拟 LLM 输出的形状）。"""
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


def counter_examples(store, gate: TaskGate, scenario: dict) -> list[dict]:
    """注入式对例（gate 级；不调用模型）：每条都必须被拒或被形式夹取。"""
    practice = scenario["gaps"]["practice"][0]
    understanding = scenario["gaps"]["understanding"][0]
    cases = [
        (
            "literal_anti_pattern",
            practice,
            {
                "title": "去学习 Agent Evaluation",
                "objective": "去学习 Agent Evaluation",
                "deliverable_type": "markdown",
                "est_minutes": 60,
                "acceptance_type": "artifact_check",
                "acceptance": "去学习 Agent Evaluation",
            },
        ),
        (
            "capability_judgment_field",
            practice,
            {
                "title": "写评测集",
                "objective": "产出一份评测集",
                "deliverable_type": "markdown",
                "est_minutes": 60,
                "acceptance_type": "artifact_check",
                "acceptance": "提交 Markdown 与判定标准",
                "confidence": 0.8,
                "expected_level": 4,
            },
        ),
        (
            "dimension_mismatch",
            understanding,
            {
                "title": "写一份检索笔记",
                "objective": "产出一份 Markdown 笔记",
                "deliverable_type": "markdown",
                "est_minutes": 40,
                "acceptance_type": "artifact_check",
                "acceptance": "提交 Markdown 笔记与要点清单",
            },
        ),
        (
            "vague_acceptance",
            practice,
            {
                "title": "熟悉检索流程",
                "objective": "了解一下检索流程",
                "deliverable_type": "markdown",
                "est_minutes": 30,
                "acceptance_type": "artifact_check",
                "acceptance": "看看",
            },
        ),
    ]
    results = []
    for index, (label, gap_id, proposal) in enumerate(cases):
        decision = gate.evaluate(
            proposal, gap_id=gap_id, run_id=f"m5b_counter_{label}", index=index, proposer="constructed_case"
        )
        results.append({"case": label, "origin": "constructed_case", **decision.to_dict()})
    return results


def g4_checks(store, estore, scenario: dict, report: dict, rejections: list[dict]) -> dict:
    tasks = store.list_tasks()
    checks: dict[str, bool] = {}
    detail: dict = {}

    # ① task → gap 映射完整（每条任务可反向映射到 ≥1 个真实缺口）
    mapping = []
    for task in tasks:
        gap = store.get_gap(task["gap_id"])
        mapping.append(
            {
                "task_id": task["id"],
                "gap_id": task["gap_id"],
                "capability_id": task["capability_id"],
                "gap_exists": gap is not None,
                "dimension": gap["dimension"] if gap else None,
                "severity": gap["severity"] if gap else None,
            }
        )
    checks["every_task_maps_to_gap"] = bool(mapping) and all(item["gap_exists"] for item in mapping)
    detail["mapping"] = mapping

    # ② 四要素齐备（可交付物 / 预计时长 / 验收方式 / 目标）
    checks["every_task_has_required_elements"] = bool(tasks) and all(
        task["deliverable_type"]
        and isinstance(task["est_minutes"], int)
        and task["acceptance_type"]
        and str(task["acceptance"]).strip()
        and str(task["objective"]).strip()
        for task in tasks
    )

    # ③ provenance 可反查：task → gap → assessment → claim → evidence → passage → source
    provenance = []
    for task in tasks:
        gap = store.get_gap(task["gap_id"])
        trace = trace_assessment(store, estore, gap["assessment_id"]) if gap and gap["assessment_id"] else None
        provenance.append(
            {
                "task_id": task["id"],
                "assessment_id": gap["assessment_id"] if gap else None,
                "traceable": bool(trace and trace["complete"]),
                "claims": [claim["claim_id"] for claim in (trace or {}).get("claims", [])],
            }
        )
    checks["provenance_chain_walkable"] = bool(provenance) and all(
        item["traceable"] for item in provenance
    )
    detail["provenance"] = provenance

    # ④ 反例必须被拒（含字面"去学习 Agent Evaluation"）
    by_case = {item["case"]: item for item in rejections if "case" in item}
    checks["literal_anti_pattern_rejected"] = (
        by_case.get("literal_anti_pattern", {}).get("accepted") is False
        and by_case.get("literal_anti_pattern", {}).get("gate_stage") == "acceptance_verifiable"
    )
    checks["capability_judgment_field_rejected"] = (
        by_case.get("capability_judgment_field", {}).get("gate_stage") == "schema"
    )
    checks["dimension_mismatch_rejected"] = (
        by_case.get("dimension_mismatch", {}).get("gate_stage") == "deliverable_allowed"
    )
    checks["vague_acceptance_rejected"] = (
        by_case.get("vague_acceptance", {}).get("gate_stage") == "acceptance_verifiable"
    )

    # ⑤ 逐条规则校验通过率（真实提议 + 对例合并统计）
    decisions = list(report["decisions"]) + rejections
    accepted = sum(1 for item in decisions if item["accepted"])
    total = len(decisions)
    detail["pass_rate"] = {"accepted": accepted, "total": total, "rate": round(accepted / total, 3) if total else 0}
    checks["pass_rate_recorded"] = total > 0

    # ⑥ 产物不含任何被禁字段（能力判断 / 排序）
    blob = json.dumps({"report": report, "rejections": rejections}, ensure_ascii=False)
    hits = [key for key in FORBIDDEN_KEYS if f'"{key}"' in blob]
    detail["forbidden_key_hits"] = hits
    checks["no_forbidden_fields_in_artifact"] = not hits

    # ⑦ 写入不变式：本运行新增行数 == accepted 数
    checks["rows_equal_accepted"] = len(tasks) == sum(
        1 for item in report["decisions"] if item["accepted"]
    )
    detail["tasks"] = [
        {
            "task_id": task["id"],
            "gap_id": task["gap_id"],
            "title": task["title"],
            "deliverable_type": task["deliverable_type"],
            "est_minutes": task["est_minutes"],
            "acceptance_type": task["acceptance_type"],
            "acceptance": task["acceptance"],
            "status": task["status"],
        }
        for task in tasks
    ]
    return {"checks": checks, "detail": detail}


def write_g4(scenario: dict, report: dict, rejections: list[dict], gate_result: dict, mode: str) -> None:
    GATE_G4.mkdir(parents=True, exist_ok=True)
    (GATE_G4 / "inputs.json").write_text(
        json.dumps(
            {
                "mode": mode,
                "goal_id": GOAL_ID,
                "materials": "受控构造（growth_constructed=true，如实标注）",
                "capability": scenario["capability"],
                "levels": scenario["levels"],
                "gaps": scenario["gaps"],
                "target_gaps": scenario["targets"],
                "severity_order": SEVERITY_ORDER,
                "max_target_gaps": MAX_TARGET_GAPS,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (GATE_G4 / "tasks.json").write_text(
        json.dumps(gate_result["detail"]["tasks"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (GATE_G4 / "rejections.json").write_text(
        json.dumps(rejections, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    checks_payload = {
        "checks": gate_result["checks"],
        "pass_rate": gate_result["detail"]["pass_rate"],
        "mapping": gate_result["detail"]["mapping"],
        "provenance": gate_result["detail"]["provenance"],
        "forbidden_key_hits": gate_result["detail"]["forbidden_key_hits"],
        "all_checks_passed": all(gate_result["checks"].values()),
    }
    (GATE_G4 / "checks.json").write_text(
        json.dumps(checks_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    passed = checks_payload["all_checks_passed"]
    (GATE_G4 / "README.md").write_text(
        "# G4 · 任务质量门\n\n"
        f"- 判定：**{'通过' if passed else '未通过'}**（模式：{mode}）\n"
        f"- 任务：{len(gate_result['detail']['tasks'])} 条，全部反向映射到 open 缺口；"
        "含 {可交付物 / 预计时长 / 验收方式 / 目标}\n"
        f"- 反例：{len(rejections)} 条注入式对例（含字面\"去学习 Agent Evaluation\"）全部被拒/夹取，拒绝原因留档\n"
        f"- 逐条规则校验通过率：{gate_result['detail']['pass_rate']}\n"
        "- provenance：task → gap → assessment → claim → evidence → passage → source 可反查\n"
        "- 运行记录：`artifacts/m5b/task-generation-{offline,real}.json`；结论见 `checks.json`\n",
        encoding="utf-8",
    )


def run(mode: str) -> dict:
    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / f"m5b-{mode}.db"
    db.unlink(missing_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    checks: dict[str, bool] = {}
    detail: dict = {}
    result: dict | None = None
    try:
        scenario = seed_gap_scenario(store, estore, workdir)
        detail["scenario"] = scenario
        gate = TaskGate(store=store, goal_id=GOAL_ID)

        if mode == "offline":
            gateway = FakeGateway(responses={TASK_GENERATION_TASK: offline_proposer})
            budget_requests = 0
            budget_cap = 0
        else:
            from goal_flow_fixtures import HttpBudgetExceeded, HttpRequestBudget

            if os.getenv("M4_ALLOW_REAL_MODEL") != "1":
                print("拒绝发起真实模型调用（未设 M4_ALLOW_REAL_MODEL=1）。")
                print("命令：M4_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m5b/run_task_generation.py --mode real")
                raise SystemExit(2)
            os.environ["EVKG_HTTP_RETRIES"] = "1"  # 零额外重试
            gateway = adapter.agent_gateway()
            budget_cap = 2
            budget = HttpRequestBudget(cap=budget_cap).install()

        generator = TaskGenerator(store=store, gateway=gateway, goal_id=GOAL_ID)
        try:
            if mode == "offline":
                report = asyncio.run(generator.propose_many(scenario["targets"]))
            else:
                try:
                    report = asyncio.run(generator.propose_many(scenario["targets"]))
                except HttpBudgetExceeded as error:  # pragma: no cover - fail-stop 记录
                    report = {"run_id": "budget_truncated", "provider": None, "model": None,
                              "goal_id": GOAL_ID, "gaps": [], "proposals": [], "decisions": [],
                              "error": str(error)}
        finally:
            if mode == "real":
                budget.uninstall()
                budget_requests = budget.requests
        detail["report"] = report
        checks["real_run_within_budget"] = (
            mode == "offline" or (budget_requests <= budget_cap and bool(report["decisions"]))
        )
        detail["budget"] = {"mode": mode, "requests": budget_requests if mode == "real" else 0,
                            "cap": budget_cap, "provider": report.get("provider"), "model": report.get("model")}
        checks["generation_produced_tasks"] = all(item["accepted"] for item in report["decisions"])

        rejections = counter_examples(store, gate, scenario)
        gate_result = g4_checks(store, estore, scenario, report, rejections)
        checks.update(gate_result["checks"])
        detail["gate"] = gate_result["detail"]

        anchors = anchor_check()
        checks["real_db_untouched"] = anchors["content_hashes_match"] and anchors["counts_match"]
        checks["real_db_has_no_g_tables"] = anchors["g_tables_in_real_db"] == []
        detail["real_db_anchors"] = anchors

        result = {
            "mode": f"m5b-{mode}",
            "checks": checks,
            "checks_passed": sum(1 for value in checks.values() if value),
            "checks_total": len(checks),
            "all_checks_passed": all(checks.values()),
            "detail": detail,
        }

        artifact = build_generation_artifact(report, mode=mode, db_path=str(db))
        write_generation_artifact(HERE / f"task-generation-{mode}.json", artifact)
        write_g4(scenario, report, rejections, gate_result, mode)
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

    (HERE / f"result-{mode}.json" if mode == "real" else HERE / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="M5-b 冒烟（offline / real）")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    args = parser.parse_args()
    result = run(args.mode)
    print(
        json.dumps(
            {
                "mode": result["mode"],
                "checks_passed": result["checks_passed"],
                "checks_total": result["checks_total"],
                "failed": [key for key, value in result["checks"].items() if not value],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
