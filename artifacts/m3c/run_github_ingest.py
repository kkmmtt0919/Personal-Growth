"""M3-c 真实冒烟：GitHub **公共**仓库接入（无凭据、无 LLM、只用 git 浅克隆）。

做三件事：

1. 对给定公共仓库（默认 `kkmmtt0919/mytset-rag`）做**真实**浅克隆并逐文件入库（唯一入口）；
2. **跑两轮**验证幂等（同一 ref 应命中同一批 `source_id`）；
3. 在临时库上跑 `audit_store`，并核对归属/通道/仓库来源 metadata 是否贯穿，最后删临时库。

产物只记结构性事实（文件路径、计数、技术栈、source_id、SHA），**不写文件内容**。
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from evkg.attack.auditor import audit_store
from growth_os.evidence import adapter
from growth_os.evidence.attribution import attribution_of, can_support_user_claim
from growth_os.evidence.github import ingest_repo

OUT = HERE / "github-ingest-result.json"


def _sample_metadata(store, source_id: str) -> dict:
    metadata = adapter.source_metadata(store, source_id)
    return {
        "evidence_type": metadata.get("growth_evidence_type"),
        "channel": metadata.get("growth_channel"),
        "attribution": attribution_of(metadata),
        "can_support_user_claim": can_support_user_claim(
            attribution_of(metadata), metadata.get("growth_channel")
        ),
        "github_repo": metadata.get("growth_github_repo"),
        "github_ref": metadata.get("growth_github_ref"),
        "github_sha": metadata.get("growth_github_sha"),
        "github_path": metadata.get("growth_github_path"),
        "github_url": metadata.get("growth_github_url"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-c GitHub 公共仓库真实冒烟")
    parser.add_argument("repo", nargs="?", default="kkmmtt0919/mytset-rag")
    parser.add_argument("--ref", default=None)
    parser.add_argument("--attribution", default="user_declared")
    parser.add_argument("--channel", default="user_evidence")
    parser.add_argument("--evidence-type", default="repo_artifact")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "github-smoke.db"
    db.unlink(missing_ok=True)
    clone_root = workdir / "clones"

    store = adapter.open_store(db)
    first = ingest_repo(
        args.repo,
        store=store,
        evidence_type=args.evidence_type,
        channel=args.channel,
        attribution=args.attribution,
        ref=args.ref,
        workdir=clone_root,
    )
    second = ingest_repo(
        args.repo,
        store=store,
        evidence_type=args.evidence_type,
        channel=args.channel,
        attribution=args.attribution,
        ref=args.ref,
        workdir=clone_root,
    )
    audit = audit_store(str(db))
    sample = next((item for item in first.ok if item.path.lower().startswith("readme")), first.ok[0])
    sample_metadata = _sample_metadata(store, sample.source_id)

    report = {
        "smoke": "M3-c GitHub 公共仓库接入（git 浅克隆，无凭据、无 LLM）",
        "repo": first.repo,
        "ref": first.ref,
        "sha": first.sha,
        "clone_dir": first.workdir,
        "files_total": first.files_total,
        "files_selected": first.files_selected,
        "tech_stack": first.tech_stack,
        "entries": {
            "ok": [{"path": item.path, "source_id": item.source_id, "passages": item.passage_count} for item in first.ok],
            "skipped": [{"path": item.path, "reason": item.reason} for item in first.skipped],
            "failed": [{"path": item.path, "reason": item.reason} for item in first.failed],
        },
        "counts": audit["counts"],
        "audit": {"status": audit["status"], "total_violations": audit["total_violations"],
                  "checks_all_zero": all(item["violations"] == 0 for item in audit["checks"].values())},
        "idempotent_same_ref": [item.source_id for item in first.ok] == [item.source_id for item in second.ok],
        "sample_metadata": sample_metadata,
        "checks": {
            "cloned_public_without_credentials": bool(first.sha),
            "files_ingested": len(first.ok) > 0,
            "audit_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
            "idempotent_same_ref": [item.source_id for item in first.ok] == [item.source_id for item in second.ok],
            "labels_propagated": sample_metadata["evidence_type"] == args.evidence_type
            and sample_metadata["channel"] == args.channel
            and sample_metadata["attribution"] == args.attribution,
            "repo_provenance_recorded": bool(sample_metadata["github_sha"]) and bool(sample_metadata["github_path"]),
        },
    }
    report["all_checks_passed"] = all(report["checks"].values())

    store.db.close()
    # 临时库含仓库内容：跑完即删。`audit_store` 内部打开的连接不会关闭（M1-g 记录过的上游问题），
    # Windows 上会锁住文件 —— gc 后重试一次，仍失败则如实记录（并在下一步人工清理）。
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

    print(json.dumps({k: report[k] for k in (
        "repo", "ref", "sha", "files_total", "files_selected", "tech_stack",
        "audit", "idempotent_same_ref", "sample_metadata", "checks", "all_checks_passed", "temp_db_deleted",
    )}, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
