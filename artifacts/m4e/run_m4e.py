"""M4-e 冒烟：统一编排 + 缺口 `g_gaps` + G3 A/B/C + G2 追溯。

模式（用户 2026-10-03 冻结）：

* **offline**（默认）：M2 真实会话的目标/能力树 + 真实对话摘录 + 受控构造笔记与仓库摘要
  （如实标注 `growth_constructed`）；绑定走**真实闸门**的确定性提议；攻击裁决用与 evkg
  真实 attack **同 payload 形状**的注入式记录。不联网、不调用任何模型。
* **real**（需 `M4_ALLOW_REAL_MODEL=1`）：独立实验库 + 真实仓库材料（浅克隆，记录 sha）+
  真实 attack（`run_attack`：deterministic / verifier / adversarial / audit）+ LLM 绑定提议；
  预算：绑定 ≤2、verifier ≤8、adversarial ≤7，**合计 ≤17 HTTP，零额外重试**，fail-stop。

数据边界：真实库 `data/growth.db` 全程只读（逐表内容哈希 + 计数对锚），实验库跑完即删。
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
sys.path.insert(0, str(REPO / "artifacts" / "m3e"))

from evkg.attack import run_attack
from evkg.attack.auditor import audit_store
from growth_os.assessment import (
    PRACTICE,
    UNDERSTANDING,
    BindingGate,
    assess_capability,
    build_binding_artifact,
    classify_claim,
)
from growth_os.evidence import adapter
from growth_os.evidence.dossier import build as build_dossier
from growth_os.evidence.dossier import render as render_dossier
from growth_os.evidence.reference import ingest_reference_document
from growth_os.store import GrowthStore
from run_material_claims import TOPICS
from test_traceability import trace_assessment

GOAL_ID = "goal_m2_real"
SESSION = REPO / "artifacts" / "m2" / "session-real.json"
REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
JD_FIXTURE = REPO / "artifacts" / "m3d" / "fixtures" / "jd_sample.md"
REPO_URL = "kkmmtt0919/mytset-rag"
GATE_G2 = REPO / "artifacts" / "gates" / "G2"
GATE_G3 = REPO / "artifacts" / "gates" / "G3"

LEAF_PATHS = {
    "rag": "AI Agent 核心技术/工具与执行/RAG 系统搭建与调优",
    "tool": "Agent 开发/工具与框架/自定义工具集成与 MCP",
    "vector": "AI Agent 核心技术/Agent 架构设计/记忆机制（短期、长期、向量检索）",
}

CHAT_EXCERPT = """# M2 真实会话摘录（对话材料）

用户（第 1 轮）：找一份 AI 应用工程师的工作
用户（第 2 轮）：六个月
用户（第 3 轮）：完成两个可演示的 Agent 项目并通过 20 道面试题
用户（第 4 轮）：好，就以这个为目标
"""
"""真实对话材料：M2 真实会话（session-real.json）的原文摘录，归属 `user_asserted`。

**不含**任何"我会 X"式的能力自述 —— 不伪造用户没说过的话（G3-A 的弱臂由此保持诚实：
声明是真实的，缺的是可核验的产物证据）。
"""

NOTE_TEXT = """# 学习笔记：RAG 检索流程整理（受控构造样本）

整理 RAG 检索流程：文档切分 → 向量化 → 向量库检索 → 结果拼接进上下文。
向量库使用 ChromaDB，检索服务用 Python 封装，工具调用通过 MCP 注册。
"""
"""受控构造的笔记（本机无真实笔记，用户已冻结：构造必须如实标注）。

由它起评理解维度（`uploaded_doc`）——它是**构造证据**，不是用户真实笔记；
G3 的弱臂本质上测的是"有知识材料、无实践产物"的分离结论。
"""

REPO_DIGEST_TEXT = """# 仓库摘要（受控构造样本，离线模式专用）

README：项目包含 RAG 检索服务（RagService）与向量检索（ChromaDB、VectorSearch）。
Java 服务端源码：package com.hw; public class RagService; @RestController。
MCP 工具注册与调用：ToolRegistry 注册 HttpTool，工具注册表见 McpController。
测试用例生成：TestCaseService 生成测试用例（TestCase）。
"""
"""离线模式的"仓库材料"（构造 + 标注）。真实模式改用真实仓库浅克隆。"""

_ANCHOR_TABLES = (
    "sources",
    "passages",
    "entities",
    "entity_aliases",
    "events",
    "claims",
    "evidence",
    "relations",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 种子：M2 真实目标 + 真实能力树（截取 3 条叶子 + 祖先）
# ---------------------------------------------------------------------------


def seed_goal_and_tree(store: GrowthStore) -> dict:
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
    wanted = set(LEAF_PATHS.values())
    kept: dict[str, dict] = {}
    for row in session["capabilities"]:
        path = row["path"]
        if path in wanted or any(leaf.startswith(f"{path}/") for leaf in wanted):
            kept[path] = row
    by_path = {path: row["id"] for path, row in kept.items()}
    for path in sorted(kept, key=lambda item: kept[item]["depth"]):
        row = kept[path]
        parent_path = "/".join(path.split("/")[:-1])
        store.upsert_capability(
            {
                "id": row["id"],
                "goal_id": GOAL_ID,
                "parent_id": by_path.get(parent_path) if row["depth"] > 1 else None,
                "name": row["name"],
                "path": path,
                "depth": row["depth"],
                "target_level": row["target_level"],
                "origin": "generated",
                "verification_status": "unverified",
                "source_note": (
                    "M2 真实会话首版能力树截取（artifacts/m2/session-real.json）；"
                    "LLM 生成、未校验外部来源"
                ),
            }
        )
    return {key: by_path[path] for key, path in LEAF_PATHS.items()}


# ---------------------------------------------------------------------------
# 材料与主张
# ---------------------------------------------------------------------------


def ingest_text(
    store,
    workdir: Path,
    *,
    filename: str,
    content: str,
    evidence_type: str,
    attribution: str | None,
    extra: dict | None = None,
) -> str:
    target = workdir / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target,
        store=store,
        evidence_type=evidence_type,
        attribution=attribution,
        extra_metadata=extra,
    )
    return ingested.source_id


def claim_for_source(
    store,
    source_id: str,
    *,
    subject: str,
    statement: str,
    metadata: dict | None = None,
    per_claim: int = 1,
) -> str:
    passage_ids = [item.id for item in store.get_passages(source_id=source_id)]
    return adapter.create_material_claim(
        store,
        subject=subject,
        predicate="包含",
        object="相关内容",
        statement=statement,
        passage_ids=passage_ids[:per_claim],
        metadata=metadata,
    )["claim_id"]


def build_repo_claims(store, source_ids: set[str], label: str) -> list[dict]:
    """确定性主题 → claim（**只取指定来源集合的 passage**；与 M3-e / M4-b 同源的关键词表）。

    限定来源是必须的：不限定会让笔记/对话段落也被主题命中，把知识桶段落混进
    实践证据（证据类型聚合按来源判定）。
    """
    passages = [item for item in store.get_passages() if item.source_id in source_ids]
    results: list[dict] = []
    for topic, keywords in TOPICS:
        hits = [item for item in passages if any(key in item.text for key in keywords)]
        if not hits:
            continue
        claim = adapter.create_material_claim(
            store,
            subject=f"{label} 项目材料",
            predicate="包含",
            object=topic,
            statement=f"项目材料中出现{topic}（依据所引原文段落）",
            passage_ids=[item.id for item in hits[:2]],
            metadata={"growth_source_kind": "repo_material", "growth_claim_topic": topic},
        )
        results.append({"claim_id": claim["claim_id"], "topic": topic})
    return results


def pick_topic(claims: list[dict], keyword: str) -> str:
    for item in claims:
        if keyword in item["topic"]:
            return item["claim_id"]
    raise AssertionError(f"未找到含 {keyword!r} 的主题 claim：{[item['topic'] for item in claims]}")


def bind_via_gate(
    store,
    evidence_store,
    *,
    capability_id: str,
    capability_path: str,
    claim_id: str,
    run_id: str,
    index: int,
    rationale: str,
    proposer: str,
) -> dict:
    gate = BindingGate(
        store=store, evidence_store=evidence_store, goal_id=GOAL_ID
    )
    decision = gate.evaluate(
        {"claim_id": claim_id, "capability_path": capability_path, "rationale": rationale},
        run_id=run_id,
        index=index,
        proposer=proposer,
    )
    return {
        "proposal_id": decision.proposal_id,
        "claim_id": decision.claim_id,
        "capability_path": decision.capability_path,
        "capability_id": decision.capability_id,
        "accepted": decision.accepted,
        "gate_stage": decision.gate_stage,
        "reject_reason": decision.reject_reason,
        "stages_passed": list(decision.stages_passed),
    }


def inject_attack(store, claim_id: str, verdict: str, *, reason: str) -> None:
    """注入与 evkg 真实 adversarial **同 payload 形状**的裁决（离线等价物，如实标注）。"""
    store.db.execute(
        "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    payload = {
        "probe": {"target_claim_id": claim_id, "angle": "注入式等价物", "question": "注入式质疑"},
        "verdict": {
            "target_claim_id": claim_id,
            "verdict": verdict,
            "reasoning": reason,
            "missing_evidence": [],
        },
    }
    store.db.execute(
        "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
        (f"rep_{claim_id}_{verdict}", "m4e-offline", "adversarial", claim_id, json.dumps(payload, ensure_ascii=False)),
    )
    store.db.commit()


# ---------------------------------------------------------------------------
# 数据边界
# ---------------------------------------------------------------------------


def anchor_check() -> dict:
    anchor = _load_json(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    hashes = {table: digest(table) for table in _ANCHOR_TABLES}
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in _ANCHOR_TABLES
    }
    g_tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'g_%'"
        ).fetchall()
    ]
    conn.close()
    return {
        "content_hashes_match": all(
            hashes[table] == anchor["table_content_sha256"][table] for table in _ANCHOR_TABLES
        ),
        "counts_match": counts == anchor["table_counts"],
        "counts": counts,
        "g_tables_in_real_db": sorted(g_tables),
    }


# ---------------------------------------------------------------------------
# 断言辅助
# ---------------------------------------------------------------------------


def dimension(body: dict, name: str) -> dict:
    return body["dimensions"][name]


def dimension_rationale(body: dict, name: str) -> str:
    return body["report"]["dimensions"][name]["rationale"]


def gap_map(result: dict) -> dict:
    return {item["dimension"]: item for item in result["gaps"]}


def supports_claim_ids(result: dict) -> set[str]:
    return {
        item["claim_id"]
        for item in result["report"]["supports"]
    }


def excluded_claim_ids(result: dict) -> set[str]:
    return {item["claim_id"] for item in result["report"]["excluded"]}


def walk_traces(store, evidence_store) -> list[dict]:
    return [
        trace_assessment(store, evidence_store, row["id"])
        for row in store.list_assessments()
        if row["status"] in ("rated", "insufficient_evidence")
    ]


def write_reports_reference(result: dict) -> dict:
    return {key: str(value) for key, value in (result.get("report_paths") or {}).items()}


# ---------------------------------------------------------------------------
# offline
# ---------------------------------------------------------------------------


def run_offline() -> dict:
    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "m4e-offline.db"
    db.unlink(missing_ok=True)
    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    checks: dict[str, bool] = {}
    detail: dict = {}
    result: dict | None = None
    try:
        tree = seed_goal_and_tree(store)
        rag, tool, vector = tree["rag"], tree["tool"], tree["vector"]
        detail["tree"] = tree

        # ── 轮 A：弱证据（真实对话摘录 + 受控构造笔记）───────────────────
        chat_src = ingest_text(
            estore,
            workdir,
            filename="chat-real-excerpt.md",
            content=CHAT_EXCERPT,
            evidence_type="chat_assertion",
            attribution="user_asserted",
            extra={"growth_source_kind": "m2_real_session_excerpt"},
        )
        chat_claim = claim_for_source(
            estore,
            chat_src,
            subject="对话材料",
            statement="对话材料中记录用户的目标与时间安排（M2 真实会话摘录）",
        )
        note_src = ingest_text(
            estore,
            workdir,
            filename="note-rag-constructed.md",
            content=NOTE_TEXT,
            evidence_type="uploaded_doc",
            attribution="user_declared",
            extra={
                "growth_source_kind": "constructed_note",
                "growth_constructed": True,
                "growth_constructed_note": "本机无真实笔记；受控构造，仅用于 G3 弱臂（用户已冻结）",
            },
        )
        note_claim = claim_for_source(
            estore,
            note_src,
            subject="笔记材料",
            statement="笔记材料中整理了 RAG 检索流程与向量库、工具调用要点（受控构造样本）",
        )
        inject_attack(estore, note_claim, "sustained", reason="注入式等价物：材料口径陈述守住")

        decisions_a = [
            bind_via_gate(
                store, estore,
                capability_id=rag,
                capability_path=LEAF_PATHS["rag"],
                claim_id=chat_claim,
                run_id="m4e_offline_a",
                index=0,
                rationale="（离线确定性提议）对话材料 → RAG 能力点",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=rag,
                capability_path=LEAF_PATHS["rag"],
                claim_id=note_claim,
                run_id="m4e_offline_a",
                index=1,
                rationale="（离线确定性提议）笔记材料 → RAG 能力点",
                proposer="offline_deterministic",
            ),
        ]
        round_a = assess_capability(
            store, estore, capability_id=rag, report_directory=reports, report_stem="g3-a-rag"
        )
        detail["round_a"] = {
            "decisions": decisions_a,
            "dimensions": {k: (v["status"], v["level"]) for k, v in round_a["dimensions"].items()},
            "gaps": {k: (v["severity"], v["current_level"]) for k, v in gap_map(round_a).items()},
        }

        # ── 轮 B：强证据（构造仓库摘要 + MCP/向量主题主张）──────────────
        repo_src = ingest_text(
            estore,
            workdir,
            filename="repo-digest-constructed.md",
            content=REPO_DIGEST_TEXT,
            evidence_type="repo_artifact",
            attribution="user_declared",
            extra={
                "growth_source_kind": "constructed_repo_digest",
                "growth_constructed": True,
                "growth_constructed_note": "离线模式的构造仓库摘要；真实模式改用真实仓库（记录 sha）",
            },
        )
        repo_claims = build_repo_claims(estore, {repo_src}, "构造仓库摘要（离线）")
        detail["repo_claims"] = repo_claims
        assert len(repo_claims) >= 3, "构造摘要必须触发 ≥3 个主题（离线场景前提）"
        rag_repo_claim = pick_topic(repo_claims, "RAG")
        tool_repo_claim = pick_topic(repo_claims, "MCP")
        vector_repo_claim = pick_topic(repo_claims, "向量")

        jd_source = ingest_reference_document(JD_FIXTURE, store=estore)
        jd_claim = claim_for_source(
            estore,
            jd_source.source_id,
            subject="外部参考材料（合成 JD）",
            statement="JD 材料中列出 RAG 相关岗位要求（外部参考，不是用户能力）",
        )

        # 攻击（注入式等价物）：RAG 主题 weakened → 封顶 ≤3；MCP 主题 broken → 剔除
        inject_attack(estore, rag_repo_claim, "weakened", reason="注入式等价物：证据强度不足，部分支持")
        inject_attack(estore, tool_repo_claim, "broken", reason="注入式等价物：材料存在 ≠ 用户独立实现")

        decisions_b = [
            bind_via_gate(
                store, estore,
                capability_id=rag,
                capability_path=LEAF_PATHS["rag"],
                claim_id=rag_repo_claim,
                run_id="m4e_offline_b",
                index=0,
                rationale="（离线确定性提议）RAG 主题 → RAG 能力点",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=tool,
                capability_path=LEAF_PATHS["tool"],
                claim_id=tool_repo_claim,
                run_id="m4e_offline_b",
                index=1,
                rationale="（离线确定性提议）`MCP` 主题 → 工具集成能力点",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=vector,
                capability_path=LEAF_PATHS["vector"],
                claim_id=vector_repo_claim,
                run_id="m4e_offline_b",
                index=2,
                rationale="（离线确定性提议）向量检索主题 → 记忆/向量能力点",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=rag,
                capability_path=LEAF_PATHS["rag"],
                claim_id=jd_claim,
                run_id="m4e_offline_b",
                index=3,
                rationale="（离线确定性提议，预期被拒）JD 材料 → 用户能力点",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=tool,
                capability_path=LEAF_PATHS["tool"],
                claim_id=note_claim,
                run_id="m4e_offline_b",
                index=4,
                rationale="（离线确定性提议）同一笔记材料 → 工具集成能力点（跨能力复用）",
                proposer="offline_deterministic",
            ),
            bind_via_gate(
                store, estore,
                capability_id=vector,
                capability_path=LEAF_PATHS["vector"],
                claim_id=note_claim,
                run_id="m4e_offline_b",
                index=5,
                rationale="（离线确定性提议）同一笔记材料 → 记忆/向量能力点（跨能力复用）",
                proposer="offline_deterministic",
            ),
        ]
        round_b = {
            "rag": assess_capability(store, estore, capability_id=rag, report_directory=reports, report_stem="g3-b-rag"),
            "tool": assess_capability(store, estore, capability_id=tool, report_directory=reports, report_stem="g3-b-tool"),
            "vector": assess_capability(store, estore, capability_id=vector, report_directory=reports, report_stem="g3-b-vector"),
        }
        detail["round_b"] = {
            "decisions": decisions_b,
            "dimensions": {
                key: {k: (v["status"], v["level"]) for k, v in body["dimensions"].items()}
                for key, body in round_b.items()
            },
            "gaps": {
                key: {k: (v["severity"], v["current_level"]) for k, v in gap_map(body).items()}
                for key, body in round_b.items()
            },
        }

        # ── G3 判定 ────────────────────────────────────────────────────
        a_understanding = dimension(round_a, UNDERSTANDING)
        a_practice = dimension(round_a, PRACTICE)
        b_understanding = dimension(round_b["rag"], UNDERSTANDING)
        b_practice = dimension(round_b["rag"], PRACTICE)
        rag_supports = supports_claim_ids(round_b["rag"])
        tool_practice = dimension(round_b["tool"], PRACTICE)

        classification_jd = classify_claim(
            {entry["claim"]["id"]: entry for entry in adapter.claims_overview(estore)}[jd_claim]
        )
        injection_decisions = {
            item["claim_id"]: item["accepted"] for item in [*decisions_a, *decisions_b]
        }
        report_excluded_reasons = {item["claim_id"]: item["reason"] for item in round_b["rag"]["report"]["excluded"]}

        checks.update(
            {
                # 1) 编排顺序与 fail-stop（由 pipeline 返回值与测试共同锁定）
                "pipeline_level_verification_consistent": all(
                    body["level_verification"]["consistent"] for body in [round_a, *round_b.values()]
                ),
                "pipeline_gap_verification_consistent": all(
                    body["gap_verification"]["consistent"] for body in [round_a, *round_b.values()]
                ),
                # 2) g_gaps 派生
                "gap_a_practice_is_evidence_gap": gap_map(round_a)[PRACTICE]["severity"] == "evidence_gap",
                "gap_b_rag_practice_level_gap_1": gap_map(round_b["rag"])[PRACTICE]["severity"] == "level_gap_1",
                "gap_b_rag_understanding_2plus": gap_map(round_b["rag"])[UNDERSTANDING]["severity"] == "level_gap_2plus",
                "gap_b_tool_practice_evidence_gap": gap_map(round_b["tool"])[PRACTICE]["severity"] == "evidence_gap",
                # 3) 唯一写路径（测试锁定 AST；运行器核对 provenance）
                "gap_rows_carry_assessment_id": all(
                    item["assessment_id"].startswith("asm_") for item in round_b["rag"]["gaps"]
                ),
                # 4/5) 攻击 → 结算
                "weakened_caps_practice_at_3": "封顶 ≤3" in dimension_rationale(round_b["rag"], PRACTICE),
                "broken_excludes_claim": tool_repo_claim in excluded_claim_ids(round_b["tool"])
                or tool_repo_claim in report_excluded_reasons,
                "broken_makes_practice_insufficient": tool_practice["status"] == "insufficient_evidence",
                # 6) G3-A
                "g3a_understanding_ge_2": a_understanding["status"] == "rated" and a_understanding["level"] >= 2,
                "g3a_practice_not_ge_2": not (a_practice["status"] == "rated" and a_practice["level"] >= 2),
                "g3a_mentions_missing_practice": any(
                    "实践" in str(item) for item in round_a["report"]["dimensions"][PRACTICE]["why_not_higher"]
                )
                and "实践" in a_practice["status"] + gap_map(round_a)[PRACTICE]["rationale"],
                # 7) G3-B
                "g3b_practice_ge_2": b_practice["status"] == "rated" and b_practice["level"] >= 2,
                "g3b_understanding_not_lower": (b_understanding["level"] or 0) >= (a_understanding["level"] or 0),
                "g3b_above_a_operational": (
                    (b_practice["status"] == "rated" and b_practice["level"] >= 2)
                    and not (a_practice["status"] == "rated" and a_practice["level"] >= 2)
                ),
                # 8) G3-C
                "g3c_jd_classified_domain_reference": classification_jd.kind == "domain_reference",
                "g3c_jd_rejected_by_gate": injection_decisions[jd_claim] is False,
                "g3c_jd_not_in_supports": jd_claim not in rag_supports,
                # 附：待验证声明被闸门拒绝（用户声明 ≠ 证据）
                "chat_declaration_rejected_by_gate": injection_decisions[chat_claim] is False,
            }
        )
        detail["gate_decisions"] = {
            "round_a": decisions_a,
            "round_b": decisions_b,
            "jd_classification": {"kind": classification_jd.kind, "reasons": list(classification_jd.reasons)},
        }

        # ── G2 追溯 ───────────────────────────────────────────────────
        traces = walk_traces(store, estore)
        complete = [item for item in traces if item["complete"]]
        walkable = [item for item in traces if item["walkable"]]
        checks["g2_at_least_five_traceable"] = len(complete) >= 5
        checks["g2_all_traced_verbatim"] = all(
            all(claim["quote_verbatim"] for claim in item["claims"]) for item in complete
        )
        detail["g2"] = {
            "traceable": len(complete),
            "walkable": len(walkable),
            "assessments_total": len(traces),
        }

        # ── 数据边界 + 质量门 ─────────────────────────────────────────
        audit = audit_store(str(db))
        anchors = anchor_check()
        checks["audit_store_pass"] = audit.get("status") == "pass" and not audit.get("violations")
        checks["real_db_untouched"] = anchors["content_hashes_match"] and anchors["counts_match"]
        checks["real_db_has_no_g_tables"] = anchors["g_tables_in_real_db"] == []
        detail["audit"] = {"status": audit.get("status"), "violations": audit.get("violations")}
        detail["real_db_anchors"] = anchors

        result = {
            "mode": "offline",
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
        result["temp_db_deleted"] = _remove_db(db)

    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# real
# ---------------------------------------------------------------------------


def run_real() -> dict:
    from evkg.attack import verify_claims
    from evkg.attack.adversarial import run_adversarial
    from goal_flow_fixtures import HttpBudgetExceeded, HttpRequestBudget
    from growth_os.assessment import ClaimBinder
    from growth_os.evidence.github import ingest_repo

    if os.getenv("M4_ALLOW_REAL_MODEL") != "1":
        print("拒绝发起真实模型调用（未设 M4_ALLOW_REAL_MODEL=1）。")
        print("真实运行命令：M4_ALLOW_REAL_MODEL=1 uv run --env-file .env python artifacts/m4e/run_m4e.py --mode real")
        raise SystemExit(2)

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "g3-experiment.db"
    db.unlink(missing_ok=True)
    reports = GATE_G3 / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    os.environ["EVKG_HTTP_RETRIES"] = "1"  # 零额外重试：1 次应用层调用 == 1 个 HTTP 请求
    stages: dict[str, dict] = {}
    checks: dict[str, bool] = {}
    detail: dict = {}
    result: dict | None = None
    try:
        tree = seed_goal_and_tree(store)
        rag, tool, vector = tree["rag"], tree["tool"], tree["vector"]
        detail["tree"] = tree

        # ── 材料（真实优先；构造如实标注）──────────────────────────────
        # 材料顺序：笔记先于对话（便于阅读；注意 evkg `get_claims()` 按 id 排序，
        # verifier / adversarial 的覆盖目标由 id 顺序决定，不由这里的创建顺序决定）。
        note_src = ingest_text(
            estore, workdir,
            filename="note-rag-constructed.md",
            content=NOTE_TEXT,
            evidence_type="uploaded_doc",
            attribution="user_declared",
            extra={
                "growth_source_kind": "constructed_note",
                "growth_constructed": True,
                "growth_constructed_note": "本机无真实笔记；受控构造，仅用于 G3 弱臂（用户已冻结）",
            },
        )
        note_claim = claim_for_source(
            estore, note_src,
            subject="笔记材料",
            statement="笔记材料中整理了 RAG 检索流程与向量库、工具调用要点（受控构造样本）",
        )
        chat_src = ingest_text(
            estore,
            workdir,
            filename="chat-real-excerpt.md",
            content=CHAT_EXCERPT,
            evidence_type="chat_assertion",
            attribution="user_asserted",
            extra={"growth_source_kind": "m2_real_session_excerpt"},
        )
        chat_claim = claim_for_source(
            estore, chat_src,
            subject="对话材料",
            statement="对话材料中记录用户的目标与时间安排（M2 真实会话摘录）",
        )
        repo_report = ingest_repo(
            REPO_URL,
            store=estore,
            evidence_type="repo_artifact",
            channel="user_evidence",
            attribution="user_declared",
            workdir=workdir / "clones",
        )
        repo_claims = build_repo_claims(
            estore, {entry.source_id for entry in repo_report.ok if entry.source_id}, REPO_URL
        )
        jd_source = ingest_reference_document(JD_FIXTURE, store=estore)
        jd_claim = claim_for_source(
            estore, jd_source.source_id,
            subject="外部参考材料（合成 JD）",
            statement="JD 材料中列出 RAG 相关岗位要求（外部参考，不是用户能力）",
        )
        inputs = {
            "goal": {"id": GOAL_ID, "source": "artifacts/m2/session-real.json（真实会话）"},
            "chat": {"source_id": chat_src, "kind": "m2_real_session_excerpt", "constructed": False,
                     "attribution": "user_asserted"},
            "note": {"source_id": note_src, "kind": "constructed_note", "constructed": True,
                     "attribution": "user_declared"},
            "repo": {"url": REPO_URL, "sha": repo_report.sha, "files_selected": repo_report.files_selected,
                     "files_total": repo_report.files_total, "constructed": False, "attribution": "user_declared"},
            "jd": {"fixture": "artifacts/m3d/fixtures/jd_sample.md", "constructed": True,
                   "channel": "domain_reference"},
        }

        # ── 轮 A：绑定（1 次 LLM）→ 真实 attack → 编排 ──────────────────
        # 预算调整（实施中发现，如实登记）：evkg `run_adversarial` 的 `max_probes` 只限制
        # **目标 claim 数**，模型可对同一 claim 返回多条 probe，裁决调用数 = probe 数
        # （冻结表假设"1 目标 = 1 probe"不成立；实测 1 个目标返回 3–4 条 probe）。
        # 为使真实运行落在总预算 ≤17 内：两轮 adversarial 各针对 1 个目标（上限 4 / 5）；
        # verifier A=1、verifier B=5；总预算与零额外重试不变。
        # 另注（实测）：evkg `get_claims()` 按 **id 排序**（非插入顺序），
        # verifier / adversarial 的覆盖目标是确定的但不等于"指定的那条"。
        gateway = adapter.agent_gateway()
        budget = HttpRequestBudget(cap=1).install()
        try:
            binder_a = ClaimBinder(
                store=store, evidence_store=estore, gateway=gateway, goal_id=GOAL_ID,
                id_factory=lambda: "m4e_real_bind_a",
            )
            binding_a = asyncio.run(binder_a.propose([note_claim, chat_claim]))
        finally:
            budget.uninstall()
        stages["binding_a"] = {"requests": budget.requests}
        checks["binding_a_single_http"] = budget.requests == 1

        budget = HttpRequestBudget(cap=1).install()
        try:
            verifier_a = asyncio.run(verify_claims(str(db), max_claims=1))
        finally:
            budget.uninstall()
        stages["verifier_a"] = {"requests": budget.requests, "verified": verifier_a.get("verified")}
        checks["verifier_a_within_budget"] = budget.requests <= 1

        budget = HttpRequestBudget(cap=4).install()
        try:
            adversarial_a = asyncio.run(run_adversarial(str(db), max_probes=1))
            adversarial_a_completed = True
        except HttpBudgetExceeded as error:
            adversarial_a = {"status": "budget_truncated", "error": str(error)}
            adversarial_a_completed = False
        finally:
            budget.uninstall()
        stages["adversarial_a"] = {
            "requests": budget.requests, "probes": adversarial_a.get("probes"),
            "completed": adversarial_a_completed,
        }
        checks["adversarial_a_within_budget"] = budget.requests <= 4
        checks["adversarial_a_completed"] = adversarial_a_completed

        attack_a = json.loads(json.dumps(asyncio.run(run_attack(str(db), modules=("deterministic", "audit"))), default=str))
        round_a = assess_capability(
            store, estore, capability_id=rag, report_directory=reports, report_stem="g3-a-rag"
        )

        # ── 轮 B：绑定（1 次 LLM）→ 真实 attack → 编排 ──────────────────
        candidates_b = [note_claim, chat_claim, *[item["claim_id"] for item in repo_claims], jd_claim]
        budget = HttpRequestBudget(cap=1).install()
        try:
            binder_b = ClaimBinder(
                store=store, evidence_store=estore, gateway=gateway, goal_id=GOAL_ID,
                id_factory=lambda: "m4e_real_bind_b",
            )
            binding_b = asyncio.run(binder_b.propose(candidates_b))
        finally:
            budget.uninstall()
        stages["binding_b"] = {"requests": budget.requests}
        checks["binding_b_single_http"] = budget.requests == 1

        budget = HttpRequestBudget(cap=5).install()
        try:
            verifier_b = asyncio.run(verify_claims(str(db), max_claims=5))
        finally:
            budget.uninstall()
        stages["verifier_b"] = {"requests": budget.requests, "verified": verifier_b.get("verified")}
        checks["verifier_b_within_budget"] = budget.requests <= 5

        budget = HttpRequestBudget(cap=5).install()
        try:
            adversarial_b = asyncio.run(run_adversarial(str(db), max_probes=1))
            adversarial_b_completed = True
        except HttpBudgetExceeded as error:
            adversarial_b = {"status": "budget_truncated", "error": str(error)}
            adversarial_b_completed = False
        finally:
            budget.uninstall()
        stages["adversarial_b"] = {
            "requests": budget.requests, "probes": adversarial_b.get("probes"),
            "completed": adversarial_b_completed,
        }
        checks["adversarial_b_within_budget"] = budget.requests <= 5
        checks["adversarial_b_completed"] = adversarial_b_completed

        attack_b = json.loads(json.dumps(asyncio.run(run_attack(str(db), modules=("deterministic", "audit"))), default=str))
        round_b = {
            "rag": assess_capability(store, estore, capability_id=rag, report_directory=reports, report_stem="g3-b-rag"),
            "tool": assess_capability(store, estore, capability_id=tool, report_directory=reports, report_stem="g3-b-tool"),
            "vector": assess_capability(store, estore, capability_id=vector, report_directory=reports, report_stem="g3-b-vector"),
        }
        total_http = sum(item["requests"] for item in stages.values())
        checks["total_http_within_budget_17"] = total_http <= 17
        detail["budget_adjustment"] = {
            "discovery": (
                "evkg run_adversarial 的 max_probes 只限制目标 claim 数；模型可对同一 claim "
                "返回多条 probe，裁决调用数 = probe 数（冻结表假设的 1 目标 = 1 probe 不成立；"
                "实测 1 个目标返回 ≥3 条 probe）。"
            ),
            "adjustment": (
                "两轮 adversarial 各针对 1 个目标（上限 A=4 / B=5，含 1 次 probe 生成）；"
                "verifier A=1、verifier B=5（覆盖目标按 claim id 顺序确定）；"
                "总预算 ≤17 与零额外重试不变。"
            ),
            "coverage": "第二轮 verifier 覆盖 5 条主张、adversarial 每轮 1 条目标；实际目标见 attack.json。",
            "requires_user_confirmation": True,
        }

        # ── G3 判定（口径：A 实践 <2 等价"不存在 ≥2 等级"；B ≥2；C 不进 supports）──
        a_understanding = dimension(round_a, UNDERSTANDING)
        a_practice = dimension(round_a, PRACTICE)
        b_understanding = dimension(round_b["rag"], UNDERSTANDING)
        b_practice = dimension(round_b["rag"], PRACTICE)
        overview = {entry["claim"]["id"]: entry for entry in adapter.claims_overview(estore)}
        classification_jd = classify_claim(overview[jd_claim])
        rag_supports = supports_claim_ids(round_b["rag"])

        checks.update(
            {
                "g3a_understanding_ge_2": a_understanding["status"] == "rated" and (a_understanding["level"] or 0) >= 2,
                "g3a_practice_not_ge_2": not (a_practice["status"] == "rated" and (a_practice["level"] or 0) >= 2),
                "g3b_practice_ge_2": b_practice["status"] == "rated" and (b_practice["level"] or 0) >= 2,
                "g3b_understanding_not_lower": (b_understanding["level"] or 0) >= (a_understanding["level"] or 0),
                "g3c_jd_classified_domain_reference": classification_jd.kind == "domain_reference",
                "g3c_jd_not_in_supports": jd_claim not in rag_supports,
                "pipeline_level_verification_consistent": all(
                    body["level_verification"]["consistent"] for body in [round_a, *round_b.values()]
                ),
                "pipeline_gap_verification_consistent": all(
                    body["gap_verification"]["consistent"] for body in [round_a, *round_b.values()]
                ),
                "gap_a_practice_is_evidence_gap": gap_map(round_a)[PRACTICE]["severity"] == "evidence_gap",
            }
        )

        # ── G2 追溯 + audit + 数据边界 ─────────────────────────────────
        traces = walk_traces(store, estore)
        complete = [item for item in traces if item["complete"]]
        walkable = [item for item in traces if item["walkable"]]
        checks["g2_at_least_five_traceable"] = len(complete) >= 5
        checks["g2_all_traced_verbatim"] = all(
            all(claim["quote_verbatim"] for claim in item["claims"]) for item in complete
        )
        audit = audit_store(str(db))
        anchors = anchor_check()
        checks["audit_store_pass"] = audit.get("status") == "pass" and not audit.get("violations")
        checks["real_db_untouched"] = anchors["content_hashes_match"] and anchors["counts_match"]
        checks["real_db_has_no_g_tables"] = anchors["g_tables_in_real_db"] == []

        # ── 门证据归档 ────────────────────────────────────────────────
        _write_gate_g2(store, estore, str(db), complete, traces, walkable, audit)
        comparison = _write_gate_g3(
            store=store,
            detail={
                "inputs": inputs,
                "tree": tree,
                "stages": stages,
                "total_http": total_http,
                "binding_a": build_binding_artifact(binding_a, mode="real", db_path=str(db)),
                "binding_b": build_binding_artifact(binding_b, mode="real", db_path=str(db)),
                "verifier_a": verifier_a,
                "verifier_b": verifier_b,
                "adversarial_a": adversarial_a,
                "adversarial_b": adversarial_b,
                "attack_a": attack_a,
                "attack_b": attack_b,
                "round_a": _round_view(round_a),
                "round_b": {key: _round_view(body) for key, body in round_b.items()},
                "jd_classification": {"kind": classification_jd.kind, "reasons": list(classification_jd.reasons)},
                "checks": checks,
            },
        )
        detail["gate_comparison"] = comparison
        detail["stages"] = stages
        detail["g2"] = {
            "traceable": len(complete),
            "walkable": len(walkable),
            "assessments_total": len(traces),
        }
        detail["real_db_anchors"] = anchors
        detail["audit"] = {"status": audit.get("status"), "violations": audit.get("violations")}

        result = {
            "mode": "real",
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
        result["temp_db_deleted"] = _remove_db(db)

    (HERE / "result-real.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def _remove_db(path: Path, attempts: int = 5) -> bool:
    """删除临时库；Windows 上 evkg 的残留连接可能短暂持有句柄，重试几次。"""
    import time

    for _ in range(attempts):
        gc.collect()
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            time.sleep(0.5)
            continue
        if not path.exists():
            return True
    return not path.exists()


def _round_view(body: dict) -> dict:
    return {
        "dimensions": {
            key: {"status": value["status"], "level": value["level"],
                  "assessment_id": value["assessment_id"], "rationale": value.get("rationale")}
            for key, value in body["dimensions"].items()
        },
        "levels": body["levels"],
        "gaps": body["gaps"],
        "level_verification": body["level_verification"]["consistent"],
        "gap_verification": body["gap_verification"]["consistent"],
        "report": body["report"],
        "report_paths": body["report_paths"],
    }


def _write_gate_g2(
    store, estore, db_path: str, complete: list[dict], traces: list[dict], walkable: list[dict], audit: dict
) -> None:
    GATE_G2.mkdir(parents=True, exist_ok=True)
    sample = complete[:5]
    (GATE_G2 / "traceability.json").write_text(
        json.dumps(
            {
                "gate": "G2",
                "requirement": "随机抽 5 条 assessment：assessment → claim → evidence → passage → source 逐跳 + 引文逐字",
                "sampling": "全量遍历可追溯评定行（确定性遍历，非人工挑选），取前 5 条为抽样",
                "assessments_total": len(traces),
                "traceable_total": len(complete),
                "walkable_total": len(walkable),
                "sample_count": len(sample),
                "all_traceable_complete": all(item["complete"] for item in complete),
                "sample": sample,
                "all": complete,
                "note": (
                    "insufficient_evidence 行按设计没有支撑集（'证据不足'本身是结论）——"
                    "其追溯走 trace_path=capability_bindings（该能力点绑定的主张集合），"
                    "用于证明'不足'判断是对真实、链路完整的已绑定证据做出的。"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (GATE_G2 / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    dossiers = GATE_G2 / "dossiers"
    dossiers.mkdir(exist_ok=True)
    rendered = []
    for trace in sample:
        for claim in trace["claims"]:
            dossier = build_dossier(
                estore, claim["claim_id"], db_path=db_path, generated_by="artifacts/m4e/run_m4e.py"
            )
            text = render_dossier(dossier)
            path = dossiers / f"{claim['claim_id']}.md"
            path.write_text(text, encoding="utf-8")
            rendered.append(path.name)
    (GATE_G2 / "README.md").write_text(
        "# G2 · 证据可追溯性门\n\n"
        f"- 判定：**{'通过' if len(complete) >= 5 and all(item['complete'] for item in complete) else '未通过'}**\n"
        f"- 抽样：{len(sample)} 条 assessment（来自 {len(complete)} 条可追溯评定行 / 共 {len(traces)} 条评定行；确定性遍历）\n"
        "- 逐跳：assessment → claim → evidence → passage → source，引文逐字（`quote_verbatim`）\n"
        "- 追溯路径：`supports`（rated 行）/ `capability_bindings`（insufficient_evidence 行）\n"
        "- 质量门：`audit_store` → "
        f"{audit.get('status')} / {len(audit.get('violations') or [])} violations\n"
        f"- dossier（{len(rendered)} 份）：`dossiers/`\n"
        "- 运行：`artifacts/m4e/run_m4e.py --mode real`（结果见 `result-real.json`）\n",
        encoding="utf-8",
    )


def _write_gate_g3(*, store, detail: dict) -> dict:
    GATE_G3.mkdir(parents=True, exist_ok=True)
    (GATE_G3 / "inputs.json").write_text(
        json.dumps(detail["inputs"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (GATE_G3 / "rounds.json").write_text(
        json.dumps(
            {
                "round_a": detail["round_a"],
                "round_b": detail["round_b"],
                "checks": detail["checks"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (GATE_G3 / "attack.json").write_text(
        json.dumps(
            {
                "stages": detail["stages"],
                "total_http": detail["total_http"],
                "binding_a": detail["binding_a"],
                "binding_b": detail["binding_b"],
                "verifier_a": detail["verifier_a"],
                "verifier_b": detail["verifier_b"],
                "adversarial_a": detail["adversarial_a"],
                "adversarial_b": detail["adversarial_b"],
                "attack_a": detail["attack_a"],
                "attack_b": detail["attack_b"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    a = detail["round_a"]["dimensions"]
    b = detail["round_b"]["rag"]["dimensions"]
    comparison = {
        "gate": "G3",
        "criteria": {
            "primary": "A: practice 不存在 ≥2 等级（insufficient_evidence 也算符合）；B: practice ≥ 2",
            "observation": "B 实际等级 ≥3 作为增强观察项（不作门条件）",
            "negative_control": "JD（domain_reference）不得进入 supports",
        },
        "round_a": {"understanding": a["understanding"]["level"], "practice": a["practice"]["level"],
                    "practice_status": a["practice"]["status"]},
        "round_b": {"understanding": b["understanding"]["level"], "practice": b["practice"]["level"],
                    "practice_status": b["practice"]["status"]},
        "passed": bool(
            detail["checks"].get("g3a_understanding_ge_2")
            and detail["checks"].get("g3a_practice_not_ge_2")
            and detail["checks"].get("g3b_practice_ge_2")
        ),
        "observation_b_practice_ge_3": (
            b["practice"]["status"] == "rated" and (b["practice"]["level"] or 0) >= 3
        ),
    }
    (GATE_G3 / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (GATE_G3 / "README.md").write_text(
        "# G3 · 能力审计门（A/B 对照 + C 负对照）\n\n"
        f"- 判定：**{'通过' if comparison['passed'] else '未通过'}**\n"
        f"- A（弱证据）：理解 {a['understanding']['level']} / 实践 "
        f"{a['practice']['level'] if a['practice']['level'] is not None else '证据不足'}（{a['practice']['status']}）\n"
        f"- B（强证据）：理解 {b['understanding']['level']} / 实践 "
        f"{b['practice']['level'] if b['practice']['level'] is not None else '证据不足'}（{b['practice']['status']}）\n"
        f"- C（负对照）：JD → {detail['jd_classification']['kind']}（不进入 supports）\n"
        f"- 增强观察：B 实践 ≥3 = {comparison['observation_b_practice_ge_3']}\n"
        f"- 真实运行预算：{detail['total_http']} HTTP 请求（上限 17，零额外重试）\n"
        "- 材料清单（真实 / 构造标注）：`inputs.json`；两轮记录：`rounds.json`；攻击与预算：`attack.json`\n",
        encoding="utf-8",
    )
    return comparison


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-e 冒烟（offline / real）")
    parser.add_argument("--mode", choices=("offline", "real"), default="offline")
    args = parser.parse_args()
    result = run_offline() if args.mode == "offline" else run_real()
    print(json.dumps({"mode": result["mode"], "checks": result["checks"], "passed": result["all_checks_passed"]},
                     ensure_ascii=False, indent=2))
    return 0 if result["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
