"""M3-d 真实冒烟：外部参考通道（JD / `domain_reference`）。

做四件事：

1. 把合成 JD 样本作为**外部参考**入库（通道由模块结构锁定）；
2. 抽取参考画像（技术词 + 要求条目，均带 passage 证据）；
3. 核对六条边界：`domain_reference` / 不在 `user_evidence` / 不能支撑用户断言 / 抽取只读 /
   不产生 claim / 不做评分或差距；
4. 在临时库上跑 `audit_store`，随后删除临时库（台账只留结构性事实，不写 JD 正文）。
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
from growth_os.evidence.reference import (
    REFERENCE_CHANNEL,
    REFERENCE_KIND_KEY,
    extract_reference_profile,
    ingest_reference_document,
)

OUT = HERE / "reference-ingest-result.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="M3-d JD/domain_reference 真实冒烟")
    parser.add_argument("jd", nargs="?", default=str(HERE / "fixtures" / "jd_sample.md"))
    args = parser.parse_args()

    jd = Path(args.jd)
    if not jd.is_file():
        raise SystemExit(f"JD 样本不存在: {jd}")

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "reference-smoke.db"
    db.unlink(missing_ok=True)

    store = adapter.open_store(db)
    result = ingest_reference_document(jd, store=store, reference_kind="job_description")
    metadata = adapter.source_metadata(store, result.source_id)
    counts_before = store.counts()
    profile = extract_reference_profile(store, result.source_id)
    counts_after = store.counts()
    audit = audit_store(str(db))

    boundary = {
        "channel_is_domain_reference": metadata.get(adapter.GROWTH_CHANNEL) == REFERENCE_CHANNEL,
        "not_in_user_evidence": adapter.sources_by_channel(store, "user_evidence") == [],
        "listed_in_domain_reference": result.source_id in adapter.sources_by_channel(store, "domain_reference"),
        "cannot_support_user_claim": can_support_user_claim(
            attribution_of(metadata), metadata.get(adapter.GROWTH_CHANNEL)
        )
        is False,
        "attribution_recorded": attribution_of(metadata),
        "extraction_is_read_only": counts_after == counts_before,
        "no_capability_claims_created": counts_after["claims"] == 0
        and counts_after["evidence"] == 0
        and counts_after["entities"] == 0,
        "reference_kind_recorded": metadata.get(REFERENCE_KIND_KEY) == "job_description",
    }
    report = {
        "smoke": "M3-d 外部参考通道（JD / domain_reference）",
        "material": {"path": str(jd), "note": "合成 JD 样本（本机无现成真实 JD；政策边界验证不依赖文本真实性）"},
        "source": {"id": result.source_id, "title": result.title, "kind": result.kind, "passages": result.passage_count},
        "profile_summary": {
            "tech_terms": sorted(profile["tech_terms"]),
            "tech_term_count": len(profile["tech_terms"]),
            "requirement_line_count": len(profile["requirement_lines"]),
            "all_terms_have_passage_evidence": all(profile["tech_terms"].values()),
        },
        "counts": counts_after,
        "audit": {
            "status": audit["status"],
            "total_violations": audit["total_violations"],
            "checks_all_zero": all(item["violations"] == 0 for item in audit["checks"].values()),
        },
        "boundary_checks": boundary,
        "all_checks_passed": all(boundary.values()) and audit["status"] == "pass",
    }

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
