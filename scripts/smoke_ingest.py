"""M1-b 冒烟：把真实文件作为证据入库，验证双轨记录可用。

语料是三份**真实**文件（不是编造样例）：
  1. mytset-rag/README.md          → repo_artifact / user_evidence
  2. mytset-rag/.../RagService.java → repo_artifact / user_evidence（代码路由）
  3. evkg/README.md                 → external_ref / domain_reference

第 1、2 份是"关于用户实践能力"的证据；第 3 份是**工具文档**，语义上不是用户
能力证据，因此标为 domain_reference —— 用它来验证通道过滤真的能把两者分开。

用法（仓库根目录）：
    uv run python -X utf8 scripts/smoke_ingest.py
    uv run python -X utf8 scripts/smoke_ingest.py --db data/other.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter  # noqa: E402

# (相对路径, 证据类型, 通道, 说明)
CORPUS = [
    ("README.md", "repo_artifact", "user_evidence", "项目自述文档（实践证据）"),
    (
        "src/main/java/com/hw/service/RagService.java",
        "repo_artifact",
        "user_evidence",
        "代码本体（代码路由，实践证据）",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/growth.db", help="知识库路径")
    parser.add_argument("--project-repo", default="../mytset-rag", help="用户项目仓库")
    parser.add_argument("--evkg-repo", default="../evkg", help="evkg 仓库（用作领域参考）")
    args = parser.parse_args()

    project_repo = (REPO_ROOT / args.project_repo).resolve()
    evkg_repo = (REPO_ROOT / args.evkg_repo).resolve()
    db_path = (REPO_ROOT / args.db).resolve()

    profile = adapter.configure()
    store = adapter.open_store(db_path)

    report: dict = {
        "profile": profile.name,
        "db": str(db_path),
        "passages_boundary": profile.splitting.boundary[:40] + "…",
        "ingested": [],
        "total_counts": {},
        "tag_integrity": [],
        "channel_filter": {},
        "idempotency": {},
    }

    # --- 入库 -------------------------------------------------------------
    jobs: list[tuple[Path, str, str, str]] = [
        (project_repo / rel, etype, channel, note) for rel, etype, channel, note in CORPUS
    ]
    # 领域参考：evkg 自己的 README，语义上确实是"工具文档"而非用户能力证据
    jobs.append((evkg_repo / "README.md", "external_ref", "domain_reference", "工具文档（领域参考）"))

    for path, etype, channel, note in jobs:
        if not path.is_file():
            print(f"[跳过] 文件不存在: {path}", file=sys.stderr)
            continue
        result = adapter.ingest_document(
            path, store=store, evidence_type=etype, channel=channel
        )
        report["ingested"].append(
            {
                "file": str(path.relative_to(REPO_ROOT.parent)).replace("\\", "/"),
                "note": note,
                "source_id": result.source_id,
                "route": result.route,
                "kind": result.kind,
                "evidence_type": result.evidence_type,
                "channel": result.channel,
                "passage_count": result.passage_count,
            }
        )

    report["total_counts"] = adapter.counts(store)

    # --- 关键校验 1：成长标签与 evkg 的 assessment 是否**共存** -----------
    # 这是"双轨记录"从设计变成事实的地方。assessment 被覆盖的话，
    # extract.py:105-106 会让置信度退化成"未知来源 0.25"。
    for item in report["ingested"]:
        meta = adapter.source_metadata(store, item["source_id"])
        assessment = meta.get("assessment") or {}
        report["tag_integrity"].append(
            {
                "source_id": item["source_id"],
                "has_growth_evidence_type": "growth_evidence_type" in meta,
                "has_growth_channel": "growth_channel" in meta,
                "assessment_preserved": bool(assessment),
                "assessment_baseline": assessment.get("baseline_score"),
                "assessment_rationale": (assessment.get("rationale") or "")[:32] + "…",
                "ok": all(
                    [
                        "growth_evidence_type" in meta,
                        "growth_channel" in meta,
                        bool(assessment),
                    ]
                ),
            }
        )

    # --- 关键校验 2：按通道过滤（R2 未验证的另一半） ----------------------
    for channel in ("user_evidence", "domain_reference"):
        ids = adapter.sources_by_channel(store, channel)
        report["channel_filter"][channel] = {"count": len(ids), "source_ids": ids}

    # --- 附加：幂等性（重复调用不应产生新行） ----------------------------
    before = adapter.counts(store)["sources"]
    first = report["ingested"][0]
    repeat = adapter.ingest_document(
        project_repo / CORPUS[0][0],
        store=store,
        evidence_type="repo_artifact",
        channel="user_evidence",
    )
    after = adapter.counts(store)["sources"]
    report["idempotency"] = {
        "sources_before": before,
        "sources_after": after,
        "same_source_id": repeat.source_id == first["source_id"],
        "no_new_rows": before == after,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    # --- 判定 -------------------------------------------------------------
    ok = (
        all(t["ok"] for t in report["tag_integrity"])
        and report["channel_filter"]["user_evidence"]["count"] > 0
        and report["channel_filter"]["domain_reference"]["count"] > 0
        and report["idempotency"]["no_new_rows"]
        and report["idempotency"]["same_source_id"]
        and len(report["ingested"]) >= 3
    )
    print(f"\n=== M1-b 冒烟判定: {'PASS' if ok else 'FAIL'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
