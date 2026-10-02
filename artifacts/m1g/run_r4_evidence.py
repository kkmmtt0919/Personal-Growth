"""M1-g R4 证据：实库审计、source→passage→claim→evidence 追溯核验，
并在真实数据上复核三项上游缺陷（partial 渲染 / 抽取模型名未持久化 / caught 判定截断依赖）。

纪律：
* 真实库只读 + 标准 QG1 审计（audit 只追加 audit_log 一行，脚本用逐表 payload
  哈希前后对照证明证据数据零变化）。
* 故障注入只在 sqlite3 backup API 生成的**副本**上做，副本用完即弃。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from evkg.attack import run_damage_selftest
from evkg.attack.auditor import audit_store
from evkg.domain import EvidenceLink, Polarity
from evkg.evidence.dossier import claim_dossier, render_claim_markdown
from evkg.store import KnowledgeStore

HERE = Path(__file__).resolve().parent
TMP = HERE / "tmp"
OUT = HERE / "r4_evidence.json"
REAL_DB = Path("D:/projects/Personal Growth/data/growth.db")


def table_hashes(db_path: Path, exclude: set[str]) -> dict[str, str]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    result: dict[str, str] = {}
    for name in names:
        if name in exclude:
            continue
        digest = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {name} ORDER BY rowid"):
            digest.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        result[name] = digest.hexdigest()[:16]
    conn.close()
    return result


def consistent_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    source = sqlite3.connect(str(src))
    target = sqlite3.connect(str(dst))
    source.backup(target)
    target.close()
    source.close()


def traceability(store: KnowledgeStore) -> dict:
    """逐主张走 claim → evidence → passage → source，全部按存储原值核对。"""
    claims = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM claims ORDER BY id")]
    passages = {row[0]: json.loads(row[1]) for row in store.db.execute("SELECT id, payload FROM passages")}
    sources = {row[0]: json.loads(row[1]) for row in store.db.execute("SELECT id, payload FROM sources")}
    evidence = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM evidence ORDER BY id")]
    ledger = {
        row[0]: row[1]
        for row in store.db.execute("SELECT passage_id, status FROM extraction_passages")
    }
    out: dict = {"claims": [], "checks": {}}
    for claim in claims:
        rows = [row for row in evidence if row["claim_id"] == claim["id"]]
        chain = []
        for link in rows:
            passage = passages.get(link["passage_id"])
            source = sources.get(passage["source_id"]) if passage else None
            quote = link.get("quote") or ""
            chain.append(
                {
                    "evidence_id": link["id"],
                    "polarity": link.get("polarity"),
                    "confidence": link.get("confidence"),
                    "passage_id": link["passage_id"],
                    "passage_exists": passage is not None,
                    "quote_verbatim_in_passage": bool(passage) and quote in passage["text"],
                    "source_id": source["id"] if source else None,
                    "source_kind": source.get("kind") if source else None,
                    "source_title": source.get("title") if source else None,
                    "growth_evidence_type": (source.get("metadata") or {}).get("growth_evidence_type") if source else None,
                    "growth_channel": (source.get("metadata") or {}).get("growth_channel") if source else None,
                    "has_locator": bool(passage and passage.get("locator")),
                }
            )
        passage_ids_exist = all(pid in passages for pid in claim.get("passage_ids", []))
        out["claims"].append(
            {
                "claim_id": claim["id"],
                "statement": claim["statement"],
                "status": claim["status"],
                "score": (claim.get("confidence") or {}).get("score"),
                "assessment_status": (claim.get("confidence") or {}).get("assessment_status"),
                "metadata_keys": sorted((claim.get("metadata") or {}).keys()),
                "passage_ids_all_exist": passage_ids_exist,
                "evidence_rows": len(rows),
                "chain": chain,
            }
        )
    out["checks"] = {
        "all_quotes_verbatim": all(
            link["quote_verbatim_in_passage"] for claim in out["claims"] for link in claim["chain"]
        ),
        "all_evidence_have_source": all(
            link["source_id"] for claim in out["claims"] for link in claim["chain"]
        ),
        "all_evidence_labeled": all(
            link["growth_evidence_type"] and link["growth_channel"]
            for claim in out["claims"]
            for link in claim["chain"]
        ),
        "all_claims_have_evidence": all(claim["evidence_rows"] > 0 for claim in out["claims"]),
        "extraction_ledger_complete_passages": sum(1 for status in ledger.values() if status == "complete"),
        "passages_total": len(passages),
        "ledger_covers_all_passages": len(ledger) == len(passages)
        and all(status == "complete" for status in ledger.values()),
    }
    return out


def defect_partial_rendering(real_db: Path) -> dict:
    """在副本上给 partial 证据行打哨兵，验证上游渲染器是否把它丢掉。

    直接检查 reasoning 会误判：攻击史章节会渲染 verdict 的 reasoning（与复核意见
    可能同文）。因此把**证据行自身**的 quote 改成唯一哨兵，并设一条 supports 行
    作阳性对照 —— 哨兵出现 ⟺ 该证据行被渲染。
    """
    scratch = TMP / "r4_partial_scratch.db"
    consistent_copy(real_db, scratch)
    store = KnowledgeStore(str(scratch))
    claims = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM claims ORDER BY id")]
    out = []
    for claim in claims:
        rows = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM evidence WHERE claim_id=?", (claim["id"],))]
        partials = [row for row in rows if row.get("polarity") == "partial"]
        supports = [row for row in rows if row.get("polarity") == "supports"]
        if not partials:
            out.append(
                {
                    "claim_id": claim["id"],
                    "partial_rows": 0,
                    "skipped": "该主张没有 partial 证据行，无法在本主张上复现",
                }
            )
            continue
        sentinel_partial = f"R4-PARTIAL-SENTINEL-{claim['id'][-8:]}"
        sentinel_control = f"R4-SUPPORT-CONTROL-{claim['id'][-8:]}"
        for row in partials:
            row["quote"] = sentinel_partial
            store.db.execute("UPDATE evidence SET payload=? WHERE id=?", (json.dumps(row, ensure_ascii=False), row["id"]))
        if supports:
            supports[0]["quote"] = sentinel_control
            store.db.execute(
                "UPDATE evidence SET payload=? WHERE id=?",
                (json.dumps(supports[0], ensure_ascii=False), supports[0]["id"]),
            )
        store.db.commit()
        dossier = claim_dossier(store, claim["id"])
        markdown = render_claim_markdown(dossier)
        still_in_evidence = any(row["id"] in [item["id"] for item in dossier["evidence"]] for row in partials)
        out.append(
            {
                "claim_id": claim["id"],
                "partial_rows": len(partials),
                "partial_row_still_in_structured_dossier": still_in_evidence,
                "bucketed_supports": len(dossier["supports"]),
                "bucketed_refutes": len(dossier["refutes"]),
                "partial_sentinel_in_markdown": sentinel_partial in markdown,
                "support_control_sentinel_in_markdown": sentinel_control in markdown,
            }
        )
    store.db.close()
    scratch.unlink(missing_ok=True)
    reproduced = any(
        item.get("partial_rows", 0) > 0
        and item.get("support_control_sentinel_in_markdown") is True
        and item.get("partial_sentinel_in_markdown") is False
        for item in out
    )
    return {
        "per_claim": out,
        "defect_reproduced": reproduced,
        "verdict": "阳性对照被渲染而 partial 哨兵未被渲染 → 上游 render_claim_markdown 静默丢弃 partial 证据行",
    }


def defect_model_name(store: KnowledgeStore) -> dict:
    batches = [json.loads(row[0]) for row in store.db.execute("SELECT payload FROM extraction_batches")]
    claim_meta = [json.loads(row[0]).get("metadata", {}) for row in store.db.execute("SELECT payload FROM claims")]
    tables = [row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    reading_steps = store.db.execute("SELECT COUNT(*) FROM v2_reading_steps").fetchone()[0] if "v2_reading_steps" in tables else None
    extraction_model_keys = [
        key
        for meta in claim_meta
        for key in meta
        if key in {"extraction_model", "extractor_model", "extraction_provider", "extract_model"}
    ]
    verifier_model_keys = [key for meta in claim_meta for key in meta if key == "verifier_model"]
    return {
        "extraction_batch_payload_keys": sorted({key for item in batches for key in item}),
        "claim_metadata_keys": sorted({key for meta in claim_meta for key in meta}),
        "extraction_model_recorded": bool(extraction_model_keys),
        "verifier_model_recorded": bool(verifier_model_keys),
        "v2_reading_steps_rows": reading_steps,
        "code_sites": [
            "evkg/extract.py:86-92 —— gateway.structured() 返回 ModelResult(provider,model,...)，_call 只返回 result.value，模型身份在此丢弃",
            "evkg/extract.py:182 —— claim.metadata 只写 {model_claim_id, review_state}",
            "evkg/extract.py:257-260 —— 批账本 payload 只写计数，无模型名",
            "evkg/attack/verifier.py:130 —— 对照：复核步骤把 result.model 写入 metadata.verifier_model（同一种做法抽取步骤没做）",
            "evkg/store.py:586 —— 唯一带 model 列的 v2_reading_steps 未被 extract_corpus 使用",
        ],
        "defect_reproduced": not extraction_model_keys,
    }


def defect_caught_truncation(clean_db: Path) -> dict:
    """在副本上先放 12 条伪造引文，再跑内置自测：违规数确实上升，但 caught 判 missed。"""
    dirty_db = TMP / "r4_scratch_dirty.db"
    consistent_copy(clean_db, dirty_db)
    store = KnowledgeStore(str(dirty_db))
    claim_id = store.db.execute("SELECT id FROM claims ORDER BY id LIMIT 1").fetchone()[0]
    passage_id = store.db.execute("SELECT id FROM passages ORDER BY id LIMIT 1").fetchone()[0]
    for index in range(12):
        store.save_evidence(
            EvidenceLink(
                id=f"ev_r4fake_{index:02d}",
                claim_id=claim_id,
                passage_id=passage_id,
                polarity=Polarity.SUPPORTS,
                quote=f"R4 注入的伪造引文 {index}，不可能出现在原文中",
                reasoning="R4 截断复现用",
                confidence=0.5,
            ),
            "r4_repro",
        )
    store.db.commit()
    store.db.close()
    result = run_damage_selftest(str(dirty_db))
    report = audit_store(str(dirty_db))
    samples = report["checks"]["evidence_quote_not_in_passage"]["sample"]

    clean_copy_db = TMP / "r4_scratch_clean.db"
    consistent_copy(clean_db, clean_copy_db)
    clean_result = run_damage_selftest(str(clean_copy_db))

    return {
        "dirty_store": {
            "pre_existing_violations": 12,
            "selftest_status": result.get("status"),
            "quote_violations_after_injection": result.get("quote_violations_after_injection"),
            "audit_status_during_injection": result.get("audit_status_during_injection"),
            "injected_evidence_in_sample": result.get("injected_evidence") in " ".join(samples),
            "sample_size_cap": len(samples),
        },
        "clean_store": {
            "selftest_status": clean_result.get("status"),
            "quote_violations_after_injection": clean_result.get("quote_violations_after_injection"),
        },
        "defect_reproduced": result.get("status") == "missed"
        and (result.get("quote_violations_after_injection") or 0) > 0,
        "mechanism": "auditor 只保留前 10 行 sample；run_damage_selftest 用 evidence_id in sample 判定 caught",
    }


def main() -> dict:
    TMP.mkdir(parents=True, exist_ok=True)
    before = table_hashes(REAL_DB, exclude={"audit_log"})
    store = KnowledgeStore(str(REAL_DB))
    counts = store.counts()
    audit_rows_before = store.db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    audit = audit_store(str(REAL_DB))
    audit_rows_after = store.db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    store.db.close()
    after = table_hashes(REAL_DB, exclude={"audit_log"})

    store = KnowledgeStore(str(REAL_DB))
    report = {
        "real_db": str(REAL_DB),
        "counts": counts,
        "audit_status": audit["status"],
        "audit_total_violations": audit["total_violations"],
        "audit_checks_all_zero": all(item["violations"] == 0 for item in audit["checks"].values()),
        "evidence_tables_unchanged_by_audit": before == after,
        "audit_log_rows_added_by_audit": audit_rows_after - audit_rows_before,
        "traceability": traceability(store),
        "defect_partial_rendering": defect_partial_rendering(REAL_DB),
        "defect_model_name": defect_model_name(store),
    }
    store.db.close()
    report["defect_caught_truncation"] = defect_caught_truncation(REAL_DB)

    shutil.rmtree(TMP, ignore_errors=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
