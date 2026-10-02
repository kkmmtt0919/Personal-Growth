"""M4-a 冒烟：`claim/evidence → assessment draft → audit artifact`（离线，无 LLM）。

三件事：

1. **最小闭环**：临时库里 seed confirmed goal + 能力点 → 材料入库（user_declared）→
   材料口径 claim → 确定性准入 → assessment **草案**（无星级）；
2. **边界核对**：评估层零写回证据库（逐表计数不变）、幂等、`audit_store` pass/0、
   状态语义（有可准入证据 = draft；只有待验证声明 = insufficient_evidence）；
3. **历史主张的只读审计**：对真实库跑 `sqlite3 mode=ro` 扫描，机器化清单写入
   **独立 artifact**（M3-e 决定：不写回原始 evidence store）。

产物：`assessment-audit.json`、`historical-claims-audit.json`（本目录）。
"""

from __future__ import annotations

import argparse
import gc
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from evkg.attack.auditor import audit_store

from growth_os.assessment import AssessmentDrafter, build_audit, classify_claim, write_audit
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

GOAL_ID = "goal_m4a_smoke"
REAL_DB = REPO / "data" / "growth.db"

MATERIAL = "# 项目笔记\n\n项目实现了 RAG 检索服务，并使用 ChromaDB 做向量检索。\n"
CHAT = "# 对话记录\n\n用户自述：我熟悉 RAG。\n"

MATERIAL_CLAIM = {
    "subject": "项目材料",
    "predicate": "包含",
    "object": "RAG 检索实现",
    "statement": "项目材料中包含 RAG 检索实现相关内容",
    "evidence_type": "uploaded_doc",
    "attribution": "user_declared",
}
ASSERTED_CLAIM = {
    "subject": "对话材料",
    "predicate": "包含",
    "object": "RAG 自述",
    "statement": "对话材料中包含用户熟悉 RAG 的自述",
    "evidence_type": "chat_assertion",
    "attribution": "user_asserted",
}


def seed_goal(store: GrowthStore) -> None:
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


def add_capability(store: GrowthStore, path: str, depth: int, parent_id: str | None = None) -> str:
    return store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": path,
            "name": path.split("/")[-1],
            "depth": depth,
            "parent_id": parent_id,
            "target_level": 3,
        }
    )


def add_claim(store, tmp: Path, spec: dict, filename: str, content: str) -> str:
    target = tmp / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target,
        store=store,
        evidence_type=spec["evidence_type"],
        attribution=spec["attribution"],
    )
    passage_ids = [item.id for item in store.get_passages(source_id=ingested.source_id)]
    created = adapter.create_material_claim(
        store,
        subject=spec["subject"],
        predicate=spec["predicate"],
        object=spec["object"],
        statement=spec["statement"],
        passage_ids=passage_ids[:1],
    )
    return created["claim_id"]


def historical_scan(db: Path) -> dict:
    """真实库历史主张的只读机器化审计（零写入，独立 artifact）。"""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, status, payload FROM claims ORDER BY id").fetchall()
    conn.close()
    items = []
    for claim_id, status, payload in rows:
        claim = json.loads(payload)
        result = classify_claim({"claim": claim, "evidence": []})
        items.append(
            {
                "claim_id": claim_id,
                "status": status,
                "classification": result.kind,
                "admissible": result.admissible,
                "reasons": list(result.reasons),
                "statement": (claim.get("statement") or "")[:160],
            }
        )
    return {
        "mode": "read_only (sqlite mode=ro)",
        "claims_total": len(rows),
        "items": items,
        "mutated_real_db": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-a 最小闭环冒烟")
    parser.add_argument("--keep-temp", action="store_true", help="保留临时库以便排查")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "assessment-loop.db"
    db.unlink(missing_ok=True)

    gstore = GrowthStore(str(db))
    estore = adapter.open_store(db)

    seed_goal(gstore)
    domain = add_capability(gstore, "LLM 基础", 1)
    group_a = add_capability(gstore, "LLM 基础/检索增强", 2, domain)
    cap_a = add_capability(gstore, "LLM 基础/检索增强/RAG 实现", 3, group_a)
    group_b = add_capability(gstore, "LLM 基础/工程实践", 2, domain)
    cap_b = add_capability(gstore, "LLM 基础/工程实践/测试设计", 3, group_b)

    claim_a = add_claim(estore, workdir, MATERIAL_CLAIM, "notes.md", MATERIAL)
    claim_b = add_claim(estore, workdir, ASSERTED_CLAIM, "chat.md", CHAT)

    drafter = AssessmentDrafter(store=gstore, evidence_store=estore)
    before = estore.counts()
    draft_a = drafter.draft(capability_id=cap_a, claim_ids=[claim_a])
    draft_b = drafter.draft(capability_id=cap_b, claim_ids=[claim_b])
    again = drafter.draft(capability_id=cap_a, claim_ids=[claim_a])
    artifact = build_audit(gstore, estore, db_path=str(db))
    after = estore.counts()
    audit = audit_store(str(db))

    forward = write_audit(HERE / "assessment-audit.json", artifact)
    historical = historical_scan(REAL_DB)
    historical_path = write_audit(HERE / "historical-claims-audit.json", historical)

    entry_a = next(
        item for item in artifact["assessments"] if item["assessment_id"] == draft_a["assessment_id"]
    )
    scan = {item["claim_id"]: item for item in artifact["claims_scan"]}
    checks = {
        "draft_has_support": draft_a["status"] == "draft" and draft_a["supports"] == [claim_a],
        "draft_level_is_null": draft_a["level"] is None and draft_b["level"] is None,
        "insufficient_without_admissible": draft_b["status"] == "insufficient_evidence"
        and draft_b["excluded"][0]["kind"] == "pending_declaration",
        "draft_idempotent": again["assessment_id"] == draft_a["assessment_id"],
        "evidence_store_untouched": after == before,
        "chain_complete_in_artifact": entry_a["supports"][0]["chain"]["complete"] is True,
        "artifact_read_only": artifact["read_only"] is True
        and artifact["mutated_evidence_store"] is False,
        "claims_scan_classifies": scan[claim_a]["classification"] == "admissible"
        and scan[claim_b]["classification"] == "pending_declaration",
        "audit_store_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "historical_scan_read_only": historical["mutated_real_db"] is False
        and historical["claims_total"] == 2,
        "historical_overreach_and_plan": {
            item["classification"] for item in historical["items"]
        }
        == {"overreach", "plan"},
    }
    report = {
        "smoke": "M4-a 最小闭环 + 历史主张只读审计",
        "db": str(db),
        "goal_id": GOAL_ID,
        "capabilities": {"trade": cap_a, "no_evidence": cap_b},
        "drafts": {
            "with_material_evidence": draft_a,
            "without_admissible_evidence": draft_b,
        },
        "bridge_links": gstore.list_capability_claims(),
        "evidence_counts_before": before,
        "evidence_counts_after": after,
        "audit_store": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "artifact": forward,
        "artifact_checks": checks,
        "historical_claims_audit": historical_path,
        "historical_scan": historical,
    }
    report["all_checks_passed"] = all(checks.values())

    estore.db.close()
    gstore.close()
    gc.collect()
    if not args.keep_temp:
        deleted = False
        for _ in range(2):
            try:
                db.unlink(missing_ok=True)
                deleted = True
                break
            except PermissionError:
                gc.collect()
        report["temp_db_deleted"] = deleted

    (HERE / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
