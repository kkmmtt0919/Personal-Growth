"""M1-f 补充：把"真实 evidence 不变"从**计数级**加固到**内容级**。

为什么需要补这一步：M1-f 主脚本核对的是"清理后逐表计数复原 + audit=pass"。
那验不出"条数不变、但原有行内容被改写"的情形 —— 计数完全可能保持一致。
用户规格要求的是「真实 evidence **不变**」，即内容不变。

本脚本按用户给定的最小攻击重跑一次，并在注入前后对**所有原有行的 payload 做哈希比对**：

  基线（sources/passages/claims/evidence 计数 + 每行 payload 的 sha256）
        ↓ 注入：已存在的 claim/source + **不存在的 passage_id**，引文"代码证明用户完成实现"
        ↓ audit_store -> 必须发现 evidence_missing_passage
        ↓ 清理
  恢复（计数与 payload 哈希必须与基线**逐行一致**）

同时在内容级确认真实库未被触碰。
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter

OUT = REPO_ROOT / "artifacts" / "m1f"
REAL_DB = REPO_ROOT / "data" / "growth.db"
WORK = OUT / "_content_check.db"
FAKE_QUOTE = "代码证明用户完成实现"
WATCHED = ("sources", "passages", "claims", "evidence")


def _snapshot(db: Path) -> dict:
    """计数 + 每行 payload 的哈希（按表、按 id 排序）。"""
    from evkg.store import KnowledgeStore

    store = KnowledgeStore(str(db))
    try:
        snap: dict[str, dict] = {}
        for table in WATCHED:
            rows = store.db.execute(f"SELECT id, payload FROM {table} ORDER BY id").fetchall()
            snap[table] = {
                "count": len(rows),
                "payload_hashes": {
                    row[0]: hashlib.sha256(row[1].encode("utf-8")).hexdigest()[:16] for row in rows
                },
            }
        return snap
    finally:
        store.db.close()


def _compare(before: dict, after: dict) -> dict:
    """逐行比对，列出任何计数或内容差异。"""
    result: dict[str, dict] = {}
    for table in WATCHED:
        b, a = before[table], after[table]
        added = sorted(set(a["payload_hashes"]) - set(b["payload_hashes"]))
        removed = sorted(set(b["payload_hashes"]) - set(a["payload_hashes"]))
        changed = sorted(
            row_id
            for row_id in set(b["payload_hashes"]) & set(a["payload_hashes"])
            if b["payload_hashes"][row_id] != a["payload_hashes"][row_id]
        )
        result[table] = {
            "count_before": b["count"],
            "count_after": a["count"],
            "count_unchanged": b["count"] == a["count"],
            "rows_added": added,
            "rows_removed": removed,
            "rows_content_changed": changed,
            "content_identical": not (added or removed or changed),
        }
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    adapter.configure()
    shutil.copyfile(REAL_DB, WORK)

    real_before = _snapshot(REAL_DB)
    before = _snapshot(WORK)
    baseline_audit = adapter.audit(str(WORK))

    baseline = {table: before[table]["count"] for table in WATCHED}
    print("=== 注入前基线 ===")
    for table in WATCHED:
        print(f"  {table} = {baseline[table]}")
    print(f"  audit = {baseline_audit['status'].upper()}  (violations={baseline_audit['total_violations']})")

    # ---- 注入（用户给定的最小攻击）----
    from evkg.domain import EvidenceLink, Polarity
    from evkg.store import KnowledgeStore

    store = KnowledgeStore(str(WORK))
    try:
        claim_id = store.db.execute("SELECT id FROM claims ORDER BY id LIMIT 1").fetchone()[0]
        source_id = store.db.execute("SELECT id FROM sources ORDER BY id LIMIT 1").fetchone()[0]
        store.save_evidence(
            EvidenceLink(
                id="ev_fake_citation", claim_id=claim_id,
                passage_id="p_nonexistent", polarity=Polarity.SUPPORTS,
                quote=FAKE_QUOTE, reasoning="M1-f 内容级核对：无法回溯的引用", confidence=0.9,
            ),
            "m1f_content_check",
        )
        injected = store.db.execute(
            "SELECT COUNT(*) FROM evidence WHERE id='ev_fake_citation'").fetchone()[0]
    finally:
        store.db.close()

    during = adapter.audit(str(WORK))
    check = during["checks"]["evidence_missing_passage"]
    detected = check["violations"] > baseline_audit["checks"]["evidence_missing_passage"]["violations"]
    print("\n=== 注入后 ===")
    print(f"  注入行落库: {injected}   passage_id=p_nonexistent（不存在）  quote={FAKE_QUOTE}")
    print(f"  audit = {during['status'].upper()}  "
          f"evidence_missing_passage {baseline_audit['checks']['evidence_missing_passage']['violations']}"
          f" -> {check['violations']}  detected={detected}")

    # ---- 清理 ----
    store = KnowledgeStore(str(WORK))
    try:
        store.db.execute("DELETE FROM evidence WHERE id='ev_fake_citation'")
        store.db.execute("DELETE FROM audit_log WHERE object_id='ev_fake_citation'")
        store.db.commit()
    finally:
        store.db.close()

    after = _snapshot(WORK)
    contrast = _compare(before, after)
    final = adapter.audit(str(WORK))

    print("\n=== 恢复后（内容级比对）===")
    for table in WATCHED:
        item = contrast[table]
        flag = "一致" if item["content_identical"] else "!! 有差异"
        print(f"  {table}: {item['count_before']} -> {item['count_after']}  "
              f"新增={len(item['rows_added'])} 删除={len(item['rows_removed'])} "
              f"内容变更={len(item['rows_content_changed'])}  [{flag}]")
    print(f"  audit = {final['status'].upper()}  violations={final['total_violations']}")

    real_after = _snapshot(REAL_DB)
    real_contrast = _compare(real_before, real_after)
    real_ok = all(item["content_identical"] for item in real_contrast.values())
    print(f"\n=== 真实库内容级核对 ===\n  {'一致（逐行 payload 哈希未变）' if real_ok else '!! 有差异'}")

    content_ok = all(item["content_identical"] for item in contrast.values())
    ok = detected and content_ok and real_ok and final["status"] == "pass" and final["total_violations"] == 0

    result = {
        "purpose": "把『真实 evidence 不变』从计数级加固到内容级（逐行 payload sha256）",
        "attack": "fake_citation_dangling_passage",
        "baseline": {**baseline, "audit": baseline_audit["status"]},
        "detected": bool(detected),
        "violations": ["evidence_missing_passage"] if detected else [],
        "injected": {"evidence_id": "ev_fake_citation", "claim_id": claim_id,
                     "source_id": source_id, "passage_id": "p_nonexistent", "quote": FAKE_QUOTE,
                     "row_present_after_injection": injected},
        "recovery": {"audit_status": final["status"], "audit_violations": final["total_violations"],
                     "per_table": contrast},
        "real_db_content_identical": real_ok,
        "real_db_per_table": real_contrast,
        "passed": bool(ok),
    }
    (OUT / "recovery_content_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    shutil.rmtree(WORK, ignore_errors=True)
    print(f"\n=== 内容级核对: {'通过' if ok else '未通过'} ===")
    print("  产物: artifacts/m1f/recovery_content_check.json")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
