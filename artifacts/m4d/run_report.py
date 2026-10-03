"""M4-d 冒烟：能力解释报告 + `current_level` 回填（离线，不调用任何模型）。

场景（沿用 M4-c 的素材，用户 2026-10-03 冻结的验收序列）：

1. 弱 → 强：笔记/自述 → 补项目材料；每次评定后**显式回填**并做重建校验；
2. 反向证据：实践侧 `refutes` 封顶 2 → `broken` 剔除 → 回填跟随（实践 NULL、状态 assessed）；
3. 无证据：两维度 NULL / `unassessed`；草案不影响当前视图；
4. 产物：每个能力点 JSON + Markdown 双份（"为什么是这个星级"）。

纪律：报告只从**已存储评定行 + 证据链**派生；"为什么不是更高"只来自 `rubric.gaps`；
不携带任何模型分值（D6）。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from evkg.attack.auditor import audit_store
from growth_os.assessment import (
    AssessmentDrafter,
    AssessmentRater,
    build_report,
    write_report,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
GOAL_ID = "goal_m4d_smoke"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_goal_and_tree(store: GrowthStore) -> dict:
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
        {"goal_id": GOAL_ID, "path": "LLM 基础", "name": "LLM 基础", "depth": 1, "target_level": 3}
    )
    group = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "LLM 基础/检索增强",
            "name": "检索增强",
            "depth": 2,
            "parent_id": domain,
            "target_level": 3,
        }
    )

    def add(name: str) -> str:
        return store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": f"LLM 基础/检索增强/{name}",
                "name": name,
                "depth": 3,
                "parent_id": group,
                "target_level": 3,
            }
        )

    return {"rag": add("RAG 实现"), "reverse": add("反向证据演示"), "empty": add("空能力点")}


def add_claim(store, tmp: Path, *, filename: str, content: str, evidence_type: str) -> str:
    target = tmp / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=store, evidence_type=evidence_type, attribution="user_declared"
    )
    passage_ids = [item.id for item in store.get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        store,
        subject="项目材料",
        predicate="包含",
        object="相关内容",
        statement=f"项目材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
    )["claim_id"]


def inject_attack(store, claim_id: str, verdict: str) -> None:
    store.db.execute(
        "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    payload = {
        "probe": {"target_claim_id": claim_id, "angle": "注入式", "question": "注入式质疑"},
        "verdict": {
            "target_claim_id": claim_id,
            "verdict": verdict,
            "reasoning": "注入式反例（M4-d 只验证已存在裁决的呈现与回填）",
            "missing_evidence": ["用户本人角色说明"],
        },
    }
    store.db.execute(
        "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
        (f"rep_{claim_id}_{verdict}", "m4d", "adversarial", claim_id, json.dumps(payload, ensure_ascii=False)),
    )
    store.db.commit()


def real_db_anchors_match() -> dict:
    anchor = _load_json(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    matched = all(digest(table) == anchor["table_content_sha256"][table] for table in tables)
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    conn.close()
    return {"content_hashes_match": matched, "counts_match": counts == anchor["table_counts"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-d 解释报告与回填冒烟（离线）")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "report.db"
    db.unlink(missing_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    caps = seed_goal_and_tree(store)
    rater = AssessmentRater(store=store, evidence_store=estore)

    # ── 场景 1：弱 → 强（两维度）─────────────────────────────────
    chat = add_claim(estore, workdir, filename="chat.md", content="# 对话\n\n我熟悉 RAG。\n", evidence_type="chat_assertion")
    notes = add_claim(estore, workdir, filename="notes.md", content="# 笔记\n\nRAG 检索流程整理。\n", evidence_type="uploaded_doc")
    store.link_capability_claim(caps["rag"], chat, rationale="M4-b 闸门通过（等价写入）")
    store.link_capability_claim(caps["rag"], notes, rationale="M4-b 闸门通过（等价写入）")
    rater.rate(capability_id=caps["rag"])
    weak_applied = store.apply_assessment_levels(caps["rag"])
    weak_check = store.verify_assessment_levels(caps["rag"])
    weak_report = build_report(store, estore, capability_id=caps["rag"], generated_by="artifacts/m4d/run_report.py")
    weak_paths = write_report(weak_report, directory=HERE, stem="report-weak-to-strong")

    repo = add_claim(estore, workdir, filename="repo.md", content="# 项目\n\n实现了 RAG 检索服务。\n", evidence_type="repo_artifact")
    store.link_capability_claim(caps["rag"], repo, rationale="M4-b 闸门通过（等价写入）")
    rater.rate(capability_id=caps["rag"])
    strong_applied = store.apply_assessment_levels(caps["rag"])
    strong_check = store.verify_assessment_levels(caps["rag"])
    strong_report = build_report(store, estore, capability_id=caps["rag"], generated_by="artifacts/m4d/run_report.py")
    strong_paths = write_report(strong_report, directory=HERE, stem="report-evaluated")

    # ── 场景 2：反向证据 → 回填跟随 ──────────────────────────────
    r_notes = add_claim(estore, workdir, filename="r-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    r_repo = add_claim(estore, workdir, filename="r-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    store.link_capability_claim(caps["reverse"], r_notes, rationale="M4-b 闸门通过（等价写入）")
    store.link_capability_claim(caps["reverse"], r_repo, rationale="M4-b 闸门通过（等价写入）")
    rater.rate(capability_id=caps["reverse"])

    from evkg.domain import EvidenceLink, Polarity

    repo_claim = next(item for item in estore.get_claims() if item.id == r_repo)
    passage = next(item for item in estore.get_passages() if item.id == repo_claim.passage_ids[0])
    estore.save_evidence(
        EvidenceLink(
            id=f"evr_{r_repo}",
            claim_id=r_repo,
            passage_id=passage.id,
            polarity=Polarity.REFUTES,
            quote=passage.text,
            reasoning="注入式反向证据（M4-d）",
            confidence=None,
        )
    )
    rater.rate(capability_id=caps["reverse"])
    refuted_applied = store.apply_assessment_levels(caps["reverse"])
    refuted_check = store.verify_assessment_levels(caps["reverse"])
    refuted_report = build_report(store, estore, capability_id=caps["reverse"], generated_by="artifacts/m4d/run_report.py")
    reverse_paths = write_report(refuted_report, directory=HERE, stem="report-reverse-evidence")

    inject_attack(estore, r_repo, "broken")
    rater.rate(capability_id=caps["reverse"])
    broken_applied = store.apply_assessment_levels(caps["reverse"])
    reverse_check = store.verify_assessment_levels(caps["reverse"])
    broken_report = build_report(store, estore, capability_id=caps["reverse"], generated_by="artifacts/m4d/run_report.py")
    excluded_paths = write_report(broken_report, directory=HERE, stem="report-excluded")

    # ── 场景 3：无证据 + 草案不影响当前视图 ─────────────────────
    draft_src = add_claim(estore, workdir, filename="draft-only.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    store.link_capability_claim(caps["empty"], draft_src, rationale="M4-b 闸门通过（等价写入）")
    draft = AssessmentDrafter(store=store, evidence_store=estore).draft(
        capability_id=caps["empty"], claim_ids=[draft_src]
    )
    empty_applied = store.apply_assessment_levels(caps["empty"])
    empty_check = store.verify_assessment_levels(caps["empty"])
    empty_report = build_report(store, estore, capability_id=caps["empty"], generated_by="artifacts/m4d/run_report.py")
    empty_paths = write_report(empty_report, directory=HERE, stem="report-no-evidence")

    # ── 边界与审计 ───────────────────────────────────────────────
    evidence_counts = estore.counts()
    audit = audit_store(str(db))
    anchors = real_db_anchors_match()

    strong_dump = json.dumps(strong_report, ensure_ascii=False)
    refuted_markdown = Path(reverse_paths["markdown"]).read_text(encoding="utf-8")
    broken_markdown = Path(excluded_paths["markdown"]).read_text(encoding="utf-8")
    checks = {
        "report_sections_complete": all(
            key in strong_report
            for key in ("capability", "dimensions", "supports", "gaps", "reverse_evidence", "excluded", "rule_version")
        ),
        "weak_understanding_2_practice_null": weak_applied
        == {"understanding": 2, "practice": None, "status": "assessed"},
        "strong_practice_3": strong_applied["practice"] == 3
        and strong_applied["understanding"] == 2,
        "quotes_walk_back": all(
            quote["quote_verbatim"] and quote["source_id"]
            for support in strong_report["supports"]
            for quote in support.get("quotes") or []
        )
        and bool(strong_report["supports"]),
        "no_model_scores_in_report": "confidence" not in strong_dump,
        "reverse_evidence_rendered": "## 四、反向证据" in refuted_markdown
        and "封顶 ≤2" in refuted_markdown,
        "excluded_rendered": "## 五、已排除的证据" in broken_markdown and "broken" in broken_markdown,
        "refutes_capped_practice_2": refuted_applied["practice"] == 2,
        "broken_backfill_follows": broken_applied["practice"] is None
        and broken_applied["understanding"] == 2
        and broken_applied["status"] == "assessed",
        "rebuild_consistent": all(
            item["consistent"]
            for item in (weak_check, strong_check, refuted_check, reverse_check, empty_check)
        ),
        "no_rating_null_unassessed": empty_applied
        == {"understanding": None, "practice": None, "status": "unassessed"},
        "draft_not_in_current_view": store.get_assessment(draft["assessment_id"])["status"] == "draft"
        and empty_applied["status"] == "unassessed",
        "audit_store_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "real_db_untouched": anchors["content_hashes_match"] and anchors["counts_match"],
        "artifacts_written": all(
            Path(paths["json"]).is_file() and Path(paths["markdown"]).is_file()
            for paths in (weak_paths, strong_paths, reverse_paths, excluded_paths, empty_paths)
        ),
    }
    report = {
        "smoke": "M4-d 能力解释报告 + current_level 回填（离线）",
        "db": str(db),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "backfill": {
            "weak": weak_applied,
            "strong": strong_applied,
            "reverse_after_refutes": refuted_applied,
            "reverse_after_broken": broken_applied,
            "no_evidence": empty_applied,
        },
        "rebuild_checks": {
            "weak": weak_check,
            "strong": strong_check,
            "reverse": reverse_check,
            "no_evidence": empty_check,
        },
        "report_paths": {
            "weak": weak_paths,
            "strong": strong_paths,
            "reverse_refuted": reverse_paths,
            "reverse_broken": excluded_paths,
            "no_evidence": empty_paths,
        },
        "evidence_counts": evidence_counts,
        "audit_store": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "real_db_anchors": anchors,
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    (HERE / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "all_checks_passed": report["all_checks_passed"],
        "checks": checks,
        "report_paths": report["report_paths"],
        "result": str(HERE / "result.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    estore.db.close()
    store.close()
    gc.collect()
    if not args.keep_temp:
        deleted = False
        for _ in range(3):
            try:
                db.unlink(missing_ok=True)
                deleted = True
                break
            except PermissionError:
                gc.collect()
        report["temp_db_deleted"] = deleted
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
