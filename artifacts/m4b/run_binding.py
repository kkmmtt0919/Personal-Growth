"""M4-b 冒烟：`claim → LLM 提议 → 确定性闸门 → g_capability_claims`（+ 只读产物）。

两种模式：

* **offline（默认）**：自足临时库 + `FakeGateway` —— 确定性回归（无网络、无密钥），
  含"通过 / 路径杜撰 / 归属不通过 / 桶不通过"四类提议与幂等复跑；
* **real**（需 `M4_ALLOW_REAL_MODEL=1`）：真实公共仓库材料 + M2 真实会话能力树 +
  **1 次**真实模型结构化调用。两层预算：应用层 1 次调用 / 传输层 HTTP 硬上限 1 +
  零额外重试（`EVKG_HTTP_RETRIES=1`）；失败即停，**不允许任何自动写库 fallback**。

产物（本目录）：`binding-<mode>.json`（proposal / reject / accept 全量）与
`result-<mode>.json`（完整运行报告 + 检查清单 + 数据边界）。

边界（用户 2026-10-02 冻结）：LLM 只提议；确定性闸门裁决；失败不落库；
星级 / 攻击 / 解释输出 / G3 / UI 均不在本步。
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from evkg.attack.auditor import audit_store
from growth_os.agent import FakeGateway
from growth_os.assessment import (
    BINDING_TASK,
    ClaimBinder,
    build_binding_artifact,
    classify_claim,
    write_binding_artifact,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

REAL_DB = REPO / "data" / "growth.db"
SESSION = REPO / "artifacts" / "m2" / "session-real.json"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
REPO_URL = "kkmmtt0919/mytset-rag"
GOAL_ID = "goal_m2_real"

TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RAG 检索服务相关实现", ("RagService", "RAG", "检索服务", "检索增强")),
    ("Java 服务端源码", ("public class", "package com.", "@RestController", "Spring")),
    ("MCP 工具注册与调用相关实现", ("MCP", "Mcp", "ToolRegistry", "工具注册")),
    ("测试用例生成相关内容", ("TestCase", "测试用例", "TestCaseService")),
    ("向量检索与向量库依赖", ("向量", "ChromaDB", "VectorSearch", "向量库")),
)
"""确定性主题 → 关键词（只用于**选证据**，不参与任何能力判断；与 M3-e 同源）。"""

CHAT_NOTE = (
    "# 对话记录（构造样本）\n\n"
    "用户自述：我熟悉 RAG，做过检索相关的项目。\n"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 能力树种子（offline 自足 / real 用 M2 真实会话首版树）
# ---------------------------------------------------------------------------


def seed_goal_and_small_tree(store: GrowthStore, *, goal_id: str) -> dict:
    store.upsert_user("local", "本地用户")
    store.save_goal(
        {
            "id": goal_id,
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

    def add(path: str, depth: int, parent: str | None = None) -> str:
        return store.upsert_capability(
            {
                "goal_id": goal_id,
                "path": path,
                "name": path.split("/")[-1],
                "depth": depth,
                "parent_id": parent,
                "target_level": 3,
            }
        )

    domain = add("LLM 基础", 1)
    group = add("LLM 基础/检索增强", 2, domain)
    cap_rag = add("LLM 基础/检索增强/RAG 实现", 3, group)
    group2 = add("LLM 基础/工程实践", 2, domain)
    cap_test = add("LLM 基础/工程实践/测试设计", 3, group2)
    return {
        "rag": {"id": cap_rag, "path": "LLM 基础/检索增强/RAG 实现"},
        "test": {"id": cap_test, "path": "LLM 基础/工程实践/测试设计"},
    }


def seed_tree_from_real_session(store: GrowthStore) -> dict:
    """把 M2 真实会话的**首版能力树**（31 个三层点）种进临时库（不改真实库）。"""
    session = _load_json(SESSION)
    goal = session["goal"]
    store.upsert_user(goal["user_id"], "本地用户")
    store.save_goal(
        {
            "id": goal["id"],
            "user_id": goal["user_id"],
            "title": goal["title"],
            "direction": goal["direction"],
            "purpose": goal["purpose"],
            "horizon": goal["horizon"],
            "measurable_result": goal["measurable_result"],
            "status": "confirmed",
            "source_quote": goal["source_quote"],
        }
    )
    first_written = set(session["capability_report_first"]["written"])
    rows = [row for row in session["capabilities"] if row["id"] in first_written]
    by_path = {row["path"]: row["id"] for row in rows}
    for row in sorted(rows, key=lambda item: item["depth"]):
        parent_path = "/".join(row["path"].split("/")[:-1])
        parent_id = by_path.get(parent_path) if row["depth"] > 1 else None
        store.upsert_capability(
            {
                "id": row["id"],
                "goal_id": goal["id"],
                "parent_id": parent_id,
                "name": row["name"],
                "path": row["path"],
                "depth": row["depth"],
                "target_level": row["target_level"],
                "origin": "generated",
                "verification_status": "unverified",
                "source_note": (
                    f"M2 真实会话首版能力树（{SESSION.name}，原始 run={row.get('generated_by_run_id')}）；"
                    "校验状态：unverified（LLM 生成，未校验外部来源）"
                ),
            }
        )
    return {"seeded": len(rows), "leaf": sum(1 for row in rows if row["depth"] == 3)}


# ---------------------------------------------------------------------------
# 材料与主张
# ---------------------------------------------------------------------------


def material_claim_for(store, *, subject: str, statement: str, source_id: str) -> str:
    passage_ids = [item.id for item in store.get_passages(source_id=source_id)]
    return adapter.create_material_claim(
        store,
        subject=subject,
        predicate="包含",
        object="相关内容",
        statement=statement,
        passage_ids=passage_ids[:1],
    )["claim_id"]


def build_topic_claims(store, repo: str) -> list[dict]:
    passages = store.get_passages()
    results: list[dict] = []
    for topic, keywords in TOPICS:
        hits = [item for item in passages if any(key in item.text for key in keywords)]
        if not hits:
            continue
        claim = adapter.create_material_claim(
            store,
            subject=f"{repo} 项目材料",
            predicate="包含",
            object=topic,
            statement=f"项目材料中出现{topic}（依据所引原文段落）",
            passage_ids=[item.id for item in hits[:2]],
            metadata={"growth_source_kind": "github_public_repo", "growth_claim_topic": topic},
        )
        results.append({"claim_id": claim["claim_id"], "topic": topic})
    return results


def ingest_chat_note(store, workdir: Path) -> str:
    target = workdir / "chat-note.md"
    target.write_text(CHAT_NOTE, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=store, evidence_type="chat_assertion", attribution="user_asserted"
    )
    return material_claim_for(
        store,
        subject="对话材料",
        statement="对话材料中包含用户熟悉 RAG 的自述（构造样本）",
        source_id=ingested.source_id,
    )


# ---------------------------------------------------------------------------
# 运行：offline / real
# ---------------------------------------------------------------------------


def _candidate_summary(estore, claim_ids: list[str]) -> list[dict]:
    overview = {entry["claim"]["id"]: entry for entry in adapter.claims_overview(estore)}
    return [
        {
            "claim_id": claim_id,
            "classification": classify_claim(overview[claim_id]).kind if claim_id in overview else "missing",
            "statement": (overview[claim_id]["claim"].get("statement") or "")[:100]
            if claim_id in overview
            else None,
        }
        for claim_id in claim_ids
    ]


def run_offline() -> dict:
    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "binding-offline.db"
    db.unlink(missing_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    caps = seed_goal_and_small_tree(store, goal_id="goal_m4b_offline")
    goal_id = "goal_m4b_offline"

    notes = workdir / "notes-offline.md"
    notes.write_text("# 笔记\n\n项目实现了 RAG 检索服务与向量库集成。\n", encoding="utf-8")
    declared = adapter.ingest_document(
        notes, store=estore, evidence_type="uploaded_doc", attribution="user_declared"
    )
    claim_ok = material_claim_for(
        estore,
        subject="项目材料",
        statement="项目材料中包含 RAG 检索实现相关内容",
        source_id=declared.source_id,
    )

    chat = workdir / "chat-offline.md"
    chat.write_text("# 对话记录\n\n我说过我熟悉 RAG。\n", encoding="utf-8")
    asserted = adapter.ingest_document(
        chat, store=estore, evidence_type="chat_assertion", attribution="user_asserted"
    )
    claim_asserted = material_claim_for(
        estore,
        subject="对话材料",
        statement="对话材料中包含用户熟悉 RAG 的自述",
        source_id=asserted.source_id,
    )

    jd = workdir / "jd-offline.md"
    jd.write_text("# 岗位要求\n\n要求具备 RAG 工程经验。\n", encoding="utf-8")
    reference = adapter.ingest_document(
        jd,
        store=estore,
        evidence_type="external_ref",
        channel="domain_reference",
        attribution="user_declared",
    )
    claim_ref = material_claim_for(
        estore,
        subject="岗位材料",
        statement="岗位材料中包含 RAG 工程经验要求",
        source_id=reference.source_id,
    )

    payload = {
        "proposals": [
            {
                "claim_id": claim_ok,
                "capability_path": caps["rag"]["path"],
                "rationale": "材料内容与该能力点直接相关",
            },
            {
                "claim_id": claim_ok,
                "capability_path": "杜撰/路径/不存在",
                "rationale": "路径不存在，应在 capability_exists 阶段被拒",
            },
            {
                "claim_id": claim_asserted,
                "capability_path": caps["test"]["path"],
                "rationale": "自述不得进入绑定，应在归属复核阶段被拒",
            },
            {
                "claim_id": claim_ref,
                "capability_path": caps["rag"]["path"],
                "rationale": "岗位要求不是用户证据，应在分桶阶段被拒",
            },
        ]
    }
    gateway = FakeGateway(
        responses={BINDING_TASK: [payload, payload]},
        provider="fake-provider",
        model="fake-model-x",
    )
    binder = ClaimBinder(
        store=store, evidence_store=estore, gateway=gateway, goal_id=goal_id
    )
    candidates = [claim_ok, claim_asserted, claim_ref]
    before = estore.counts()
    first = asyncio.run(binder.propose(candidates))
    second = asyncio.run(binder.propose(candidates))
    after = estore.counts()
    audit = audit_store(str(db))

    artifact = build_binding_artifact(first, mode="offline-fake", db_path=str(db))
    artifact_path = write_binding_artifact(HERE / "binding-offline.json", artifact)

    links = store.list_capability_claims()
    runs = store.list_runs(agent="claim_binding")
    stages = sorted(decision["gate_stage"] for decision in first["decisions"])
    duplicate_stages = [d["gate_stage"] for d in second["decisions"]]
    checks = {
        "gate_stages_expected": stages
        == ["attribution_unchanged", "bucket_allowed", "capability_exists", "persisted"],
        "one_accepted_three_rejected": len(first["accepted"]) == 1 and len(first["rejected"]) == 3,
        "llm_output_has_no_direct_write": len(links) == 1 and links[0]["claim_id"] == claim_ok,
        "evidence_store_untouched": after == before,
        "second_run_all_rejected": second["accepted"] == []
        and duplicate_stages.count("duplicate") == 1,
        "reject_records_complete": all(
            decision["proposal_id"]
            and decision["reject_reason"]
            and decision["gate_stage"]
            and decision["timestamp"]
            and decision["run_id"] == first["run_id"]
            for decision in first["decisions"]
            if not decision["accepted"]
        ),
        "run_recorded_from_result": len(runs) == 2
        and all(run["model_source"] == "result" and run["provider"] == "fake-provider" for run in runs),
        "audit_store_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "artifact_read_only": artifact["read_only"] is True,
    }
    report = {
        "mode": "offline-fake",
        "db": str(db),
        "goal_id": goal_id,
        "capabilities": caps,
        "candidates": _candidate_summary(estore, candidates),
        "run": first,
        "second_run": second,
        "bridge_links": links,
        "runs": runs,
        "evidence_counts_before": before,
        "evidence_counts_after": after,
        "audit_store": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "artifact": artifact_path,
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    estore.db.close()
    store.close()
    gc.collect()
    db.unlink(missing_ok=True)
    return report


def _copy_real_db(target: Path) -> None:
    source = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def real_db_anchors_match() -> dict:
    anchor = _load_json(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        import hashlib

        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    matched = all(digest(table) == anchor["table_content_sha256"][table] for table in tables)
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    conn.close()
    return {
        "content_hashes_match": matched,
        "counts_match": counts == anchor["table_counts"],
        "counts": counts,
    }


def run_real() -> dict:
    from goal_flow_fixtures import HttpRequestBudget
    from growth_os.evidence.github import force_remove_tree, ingest_repo

    if os.getenv("M4_ALLOW_REAL_MODEL") != "1":
        print("拒绝发起真实模型调用（未设 M4_ALLOW_REAL_MODEL=1）。")
        print("如需 M4-b 的真实运行证据，请确认成本与配置后设置该变量，")
        print("并确保 EVKG_* / GROWTH_AGENT_* 已加载（例如：uv run --env-file .env ...）。")
        raise SystemExit(2)

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "binding-real.db"
    db.unlink(missing_ok=True)
    _copy_real_db(db)  # 真实库 → 副本（mode=ro 读取，真实库零写入）

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    tree = seed_tree_from_real_session(store)

    repo_report = ingest_repo(
        REPO_URL,
        store=estore,
        evidence_type="repo_artifact",
        channel="user_evidence",
        attribution="user_declared",
        workdir=workdir / "clones",
    )
    topic_claims = build_topic_claims(estore, REPO_URL)
    chat_claim = ingest_chat_note(estore, workdir)
    candidates = [item["claim_id"] for item in topic_claims] + [chat_claim]

    os.environ["EVKG_HTTP_RETRIES"] = "1"  # 零额外重试：1 次应用层调用 == 1 个 HTTP 请求
    budget = HttpRequestBudget(cap=1).install()
    try:
        gateway = adapter.agent_gateway()
        binder = ClaimBinder(
            store=store,
            evidence_store=estore,
            gateway=gateway,
            goal_id=GOAL_ID,
            id_factory=lambda: "m4b_real_run_001",
        )
        run = asyncio.run(binder.propose(candidates))
    finally:
        budget.uninstall()

    audit = audit_store(str(db))
    artifact = build_binding_artifact(run, mode="real", db_path=str(db))
    artifact_path = write_binding_artifact(HERE / "binding-real.json", artifact)

    links = store.list_capability_claims()
    runs = store.list_runs(agent="claim_binding")
    anchors = real_db_anchors_match()
    checks = {
        "single_structured_call": len(runs) == 1,
        "single_http_request": budget.requests == 1,
        "run_recorded_from_result": bool(runs)
        and runs[0]["model_source"] == "result"
        and runs[0]["status"] == "ok",
        "llm_output_has_no_direct_write": len(links) == len(run["accepted"]),
        "accepted_has_full_reason": all(
            "run=" in link["rationale"] and "理由：" in link["rationale"] for link in links
        ),
        "audit_store_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "real_db_untouched": anchors["content_hashes_match"] and anchors["counts_match"],
        "artifact_read_only": artifact["read_only"] is True,
    }
    report = {
        "mode": "real",
        "db": str(db),
        "goal_id": GOAL_ID,
        "tree": tree,
        "repo": {
            "name": REPO_URL,
            "sha": repo_report.sha,
            "files_ingested": len(repo_report.ok),
            "tech_stack": repo_report.tech_stack,
        },
        "candidates": _candidate_summary(estore, candidates),
        "budget": {"application_calls": 1, "http_requests": budget.requests, "http_cap": budget.cap},
        "run": run,
        "bridge_links": links,
        "runs": runs,
        "audit_store": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "real_db_anchors": anchors,
        "artifact": artifact_path,
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    estore.db.close()
    store.close()
    gc.collect()
    for _ in range(3):
        try:
            db.unlink(missing_ok=True)
            force_remove_tree(workdir / "clones")  # Windows：git pack 只读，先去只读位再删
            break
        except (PermissionError, OSError):
            gc.collect()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-b 绑定冒烟（offline / real）")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    args = parser.parse_args()

    report = run_offline() if args.mode == "offline" else run_real()
    out = HERE / f"result-{report['mode']}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "mode": report["mode"],
        "all_checks_passed": report["all_checks_passed"],
        "checks": report["checks"],
        "accepted": len(report["run"]["accepted"]),
        "rejected": len(report["run"]["rejected"]),
        "gate_stages": sorted(decision["gate_stage"] for decision in report["run"]["decisions"]),
        "artifact": report.get("artifact"),
        "result": str(out),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
