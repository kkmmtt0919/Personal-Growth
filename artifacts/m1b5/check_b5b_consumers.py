"""b.5b 下游消费者检查：score=None 的 claim 不能把渲染/检索/审计搞崩。

覆盖我在改动前识别出的 6 个消费者：
  extract（构造）、store.save_claim（relations 列）、dossier 渲染、
  index/search 与 web 的 ORDER BY、adversarial 的筛选排序、audit_store 不变量。
"""

from __future__ import annotations

import asyncio
import json

from pathlib import Path

from evkg.attack import audit_store
from evkg.attack.adversarial import claim_score
from evkg.domain import (
    Claim,
    ClaimStatus,
    Confidence,
    EvidenceLink,
    Passage,
    Polarity,
    Source,
    SourceKind,
)
from evkg.evidence.dossier import claim_dossier, render_claim_markdown
from evkg.index import rebuild_index, search
from evkg.store import KnowledgeStore

QUOTE = "我用 FastAPI 和 ChromaDB 做了一个检索问答项目，代码在 GitHub 上。"


def build(db: str) -> str:
    store = KnowledgeStore(db)
    try:
        # 来源故意**不写** metadata.assessment，模拟「未分级」
        source = Source(id="src_unassessed", title="未分级来源", kind=SourceKind.UNKNOWN, metadata={})
        store.save_source(source)
        passage = Passage(
            id="p_1",
            source_id=source.id,
            ordinal=0,
            text=QUOTE,
            locator={"ordinal": 0},
            text_hash="h",
        )
        store.save_passages([passage])
        claim = Claim(
            id="clm_none",
            subject="用户",
            predicate="实现过",
            object="RAG 检索问答",
            statement="用户实现过一个检索问答项目",
            status=ClaimStatus.EXTRACTED,
            confidence=Confidence(
                score=None,
                source_reliability=None,
                extraction_quality=0.9,
                resolution_quality=0.25,
                corroboration=0.0,
                contradiction_penalty=0.0,
                assessment_status="unassessed",
                rationale="来源尚未分级，未参与可靠性加权",
            ),
            passage_ids=[passage.id],
            metadata={"review_state": "pending"},
        )
        store.save_claim(claim)
        store.save_evidence(
            EvidenceLink(
                id="ev_1",
                claim_id=claim.id,
                passage_id=passage.id,
                polarity=Polarity.SUPPORTS,
                quote=QUOTE,
                reasoning="候选主张的原文绑定，尚未完成审查",
                confidence=None,
            )
        )
        return claim.id
    finally:
        store.db.close()


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    workdir = Path(__file__).resolve().parent / "_consumer_check"
    workdir.mkdir(exist_ok=True)
    db = str(workdir / "t.db")
    if Path(db).exists():
        Path(db).unlink()

    claim_id = build(db)

    store = KnowledgeStore(db)
    try:
        loaded = [c for c in store.get_claims() if c.id == claim_id][0]
        results.append(("claim 读回且 score 为 None", loaded.confidence.score is None,
                        f"score={loaded.confidence.score} status={loaded.confidence.assessment_status}"))

        # relations.confidence 列写入 NULL
        row = store.db.execute("SELECT confidence FROM relations WHERE claim_id=?", (claim_id,)).fetchone()
        results.append(("relations.confidence 允许 NULL", row is not None and row[0] is None,
                        f"值={row[0] if row else 'no row'}"))

        # dossier 渲染
        dossier = claim_dossier(store, claim_id)
        md = render_claim_markdown(dossier)
        results.append(("dossier 渲染不崩", bool(md) and claim_id in md, f"{len(md)} 字符"))

        # adversarial 的 None 守卫（真实执行需要模型，此处验证守卫本身）
        results.append(("adversarial.claim_score 对 None 不抛错", claim_score(loaded) == 0.0,
                        f"claim_score={claim_score(loaded)}"))

        # 存储状态（17 个索引 + 查询计划断言）
        status = store.storage_status()
        results.append(("storage_status 通过", "error" not in json.dumps(status, ensure_ascii=False).lower(),
                        str(status)[:70]))
    finally:
        store.db.close()

    # 索引检索（含 ORDER BY json_extract(confidence.score)）
    rebuild_index(db)
    found = search(db, "ChromaDB")
    results.append(("索引检索不崩", "claims" in found, f"keys={sorted(found.keys())[:4]}"))

    # audit_store 不变量
    audit = audit_store(db)
    results.append(("audit_store 仍 pass", audit["status"] == "pass",
                    f"violations={audit['total_violations']} checks={len(audit['checks'])}"))

    ok = True
    for name, passed, detail in results:
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  —  {detail}")
    print(f"\n=== b.5b 下游消费者检查: {'全部通过' if ok else '有失败'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
