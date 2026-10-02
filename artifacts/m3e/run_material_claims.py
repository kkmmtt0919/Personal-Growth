"""M3-e 冒烟：材料口径断言 + audit + provenance + 历史主张的只读标记。

四件事：

1. 用 M3-c 的公共仓库链路把证据接进来（临时库；无 LLM、无凭据）；
2. 由证据**确定性地**构造 ≥3 条**材料口径** claim（ROADMAP 完成条件 3 的 claim 部分，
   表述形如"项目材料中出现 X 相关内容"，不涉及用户能力）；
3. 核对：`audit_store` = pass/0；provenance（claim → evidence → passage → source）逐跳可走通；
   所有 claim `score=None`、越权校验 0 命中；
4. **对真实库的历史主张做只读 dry-run 标记**（`mode=ro`，零写入）：报告哪些主张会被判越权、
   原因是什么 —— 是否在真实库上就地标注，留给用户决定。
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
from growth_os.evidence import adapter
from growth_os.evidence.claims import check_overreach
from growth_os.evidence.github import ingest_repo

OUT = HERE / "material-claims-result.json"
REAL_DB = REPO / "data" / "growth.db"

TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RAG 检索服务相关实现", ("RagService", "RAG", "检索服务", "检索增强")),
    ("Java 服务端源码", ("public class", "package com.", "@RestController", "Spring")),
    ("MCP 工具注册与调用相关实现", ("MCP", "Mcp", "ToolRegistry", "工具注册")),
    ("测试用例生成相关内容", ("TestCase", "测试用例", "TestCaseService")),
    ("向量检索与向量库依赖", ("向量", "ChromaDB", "VectorSearch", "向量库")),
)
"""确定性主题 → 触发的关键词组（只用于**选证据**，不参与任何能力判断）。"""


def build_material_claims(store, repo: str, *, per_claim: int = 2) -> list[dict]:
    passages = store.get_passages()
    results: list[dict] = []
    for topic, keywords in TOPICS:
        hits = [item for item in passages if any(key in item.text for key in keywords)]
        if not hits:
            continue
        chosen = hits[:per_claim]
        results.append(
            adapter.create_material_claim(
                store,
                subject=f"{repo} 项目材料",
                predicate="包含",
                object=f"{topic}",
                statement=f"项目材料中出现{topic}（依据所引原文段落）",
                passage_ids=[item.id for item in chosen],
                metadata={"growth_source_kind": "github_public_repo", "growth_claim_topic": topic},
            )
        )
    return results


def historical_overreach_dry_run(db: Path) -> dict:
    """只读扫描：真实库里哪些主张会被越权校验判为越权（零写入）。"""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, status, payload FROM claims ORDER BY id").fetchall()
    conn.close()
    flagged, clean = [], []
    for claim_id, status, payload in rows:
        claim = json.loads(payload)
        report = check_overreach(
            statement=claim.get("statement", ""),
            subject=claim.get("subject"),
            predicate=claim.get("predicate"),
        )
        item = {
            "claim_id": claim_id,
            "status": status,
            "subject": claim.get("subject"),
            "predicate": claim.get("predicate"),
            "reasons": list(report.reasons),
        }
        (flagged if report.overreach else clean).append(item)
    return {
        "mode": "read_only (sqlite mode=ro)",
        "claims_total": len(rows),
        "overreach_flagged": flagged,
        "clean": clean,
        "mutated_real_db": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-e 材料口径断言冒烟")
    parser.add_argument("repo", nargs="?", default="kkmmtt0919/mytset-rag")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "material-claims.db"
    db.unlink(missing_ok=True)

    store = adapter.open_store(db)
    repo_report = ingest_repo(
        args.repo,
        store=store,
        evidence_type="repo_artifact",
        channel="user_evidence",
        attribution="user_declared",
        workdir=workdir / "clones",
    )
    claims = build_material_claims(store, args.repo)
    audit = audit_store(str(db))

    stored_claims = store.get_claims()
    scopes = [
        {
            "claim_id": claim.id,
            "status": claim.status.value,
            "score": claim.confidence.score,
            "assessment_status": claim.confidence.assessment_status,
            "scope": claim.metadata.get("growth_claim_scope"),
            "topic": claim.metadata.get("growth_claim_topic"),
            "passages": len(claim.passage_ids),
        }
        for claim in stored_claims
    ]
    overreach_hits = [
        claim.id
        for claim in stored_claims
        if check_overreach(statement=claim.statement, subject=claim.subject, predicate=claim.predicate).overreach
    ]
    provenance_ok = True
    for claim in stored_claims:
        dossier = adapter.claim_dossier(store, claim.id)
        if not dossier or not dossier["evidence"]:
            provenance_ok = False
            continue
        for link in dossier["evidence"]:
            if link["quote"] not in link["passage_text"] or not link["source"]["id"]:
                provenance_ok = False

    checks = {
        "repo_ingested": len(repo_report.ok) > 0,
        "at_least_3_material_claims": len(claims) >= 3,
        "audit_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "all_claims_material_scoped": all(item["scope"] == "material" for item in scopes),
        "no_overreach_in_stored_claims": overreach_hits == [],
        "scores_unassessed": all(item["score"] is None for item in scopes),
        "provenance_walkable": provenance_ok,
    }
    report = {
        "smoke": "M3-e 材料口径断言 + audit + provenance + 历史主张只读标记",
        "repo": {"name": args.repo, "sha": repo_report.sha, "files_ingested": len(repo_report.ok),
                 "passages": sum(item.passage_count for item in repo_report.ok)},
        "tech_stack": repo_report.tech_stack,
        "claims": scopes,
        "audit": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "historical_claim_dry_run": historical_overreach_dry_run(REAL_DB),
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    store.db.close()
    gc.collect()
    deleted = False
    for _ in range(2):
        try:
            db.unlink(missing_ok=True)
            deleted = True
            break
        except PermissionError:
            gc.collect()
    report["temp_db_deleted"] = deleted
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
