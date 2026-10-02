"""M1-c：抽取（passage → 能力断言）。

先在小样本上试跑并人工检查质量，再跑全量。检查重点是我在 b.5a 写进成长领域包的
两条抽取约束是否被遵守：

  · 「严禁升级」：计划学 / 了解过 / 只是看过 ≠ 具备能力
  · 「不作能力推断」：原文说"某个项目用了什么技术"，不等于"用户具备该技术能力"，
     除非原文同时明确了用户在该项目中的角色或贡献

用法：
    uv run --env-file .env python -X utf8 artifacts/m1b5/run_extract.py <db> [max_passages]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter


async def main() -> int:
    from evkg.extract import extract_corpus
    from evkg.store import KnowledgeStore

    db = sys.argv[1] if len(sys.argv) > 1 else str(REPO_ROOT / "data" / "growth.db")
    max_passages = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    adapter.configure()
    store = KnowledgeStore(db)
    print(f"库: {db}")
    print(f"待抽取 passage: {store.counts()['passages']}   限制: {max_passages or '不限'}\n")

    result = await extract_corpus(db, max_passages=max_passages, batch_size=20, concurrency=2)
    print("=== 抽取结果 ===")
    for key, value in result.items():
        if key != "details":
            print(f"  {key}: {value}")

    store = KnowledgeStore(db)
    counts = store.counts()
    print(f"\n库计数: claims={counts['claims']} entities={counts['entities']} "
          f"events={counts['events']} evidence={counts['evidence']}")

    claims = store.get_claims()
    if claims:
        print(f"\n=== 抽出的主张（{len(claims)} 条）===")
        passages = {row[0]: row[1] for row in store.db.execute("SELECT id, payload FROM passages")}
        sources = {s.id: s for s in store.get_sources()}
        import json as _json
        for claim in claims[:40]:
            first_pid = claim.passage_ids[0] if claim.passage_ids else None
            payload = _json.loads(passages.get(first_pid, "{}")) if first_pid else {}
            source_id = payload.get("source_id")
            src = sources.get(source_id)
            score = claim.confidence.score
            print(f"\n  [{claim.id}] {claim.subject} | {claim.predicate} | {claim.object}")
            print(f"    陈述: {claim.statement}")
            print(f"    分数: {score if score is not None else 'None（未分级）'}  "
                  f"状态: {claim.confidence.assessment_status}  来源: "
                  f"{src.kind.value if src else '?'}/{src.metadata.get('growth_evidence_type', '?') if src else '?'}")
            snippet = (payload.get("text") or "").replace("\n", " ")[:110]
            print(f"    依据: {snippet}…")

    audit = adapter.audit(db)
    print(f"\nQG1: status={audit['status']} violations={audit['total_violations']}")
    store.db.close()
    return 0 if audit["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
