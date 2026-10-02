"""M1-f：故障注入自测（damage selftest）。

范围严格限定：**验证 Evidence Graph 面对"看似合理但实际伪造"的数据污染时，
能否发现、拒绝并恢复一致状态。** 不做完整安全测试，也不碰 M1-e 的渲染问题、
抽取模型 metadata、归属层（那些分别属输出质量与 M2/M4 产品语义）。

## 为什么有三段而不是一段

只跑 evkg 内置的 `run_damage_selftest` 有个测量盲区：它把
**注入 → 审计 → 清理** 全放在一个函数里，`finally` 一执行注入就没了。
因此在它返回之后再去数违规条数，只能看到已清理的状态（0 条），
**无法独立验证"注入期间确实产生了违规"** —— 只能采信它自己的 `caught` 结论。

所以本脚本分三段：

  A.  跑内置 `run_damage_selftest`，记录它自己的结论 + 核对清理与恢复。
  A'. 自行做一次**同类型**受控注入（存在的 passage + 伪造引文），
      由本脚本自己前后测量 `evidence_quote_not_in_passage` 的违规条数。
  B.  自行做一次**用户指定类型**的受控注入（不存在的 passage_id），
      前后测量 `evidence_missing_passage`。

A' 与 B 是**独立可验证**的：注入前 0 条、注入后 ≥1 条、清理后回到 0 条，
全部由本脚本自己测量，不依赖被测函数的自述。

两个受控场景打的是**不同不变量**：A' 打引文保真，B 打引用完整性。

**在真实库的副本上执行**，并核对真实库未被触碰。若审计没抓到，如实记录
`detected: false` —— missed 本身就是这一步的价值，不做任何修补。

用法：
    uv run --env-file .env python -X utf8 artifacts/m1f/run_damage.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter

OUT = REPO_ROOT / "artifacts" / "m1f"
REAL_DB = REPO_ROOT / "data" / "growth.db"
WORK = OUT / "_damage_work.db"

# 用户建议的最小攻击用的引文：看起来合理，但引用的 passage 根本不存在
FAKE_QUOTE = "代码证明用户完成实现"
# A' 用的伪造引文：passage 存在，但引文不在这段文本里
FABRICATED_QUOTE = "这段文字从未出现在任何原始材料中 controlled-injection"


def _table_counts(db: Path) -> dict[str, int]:
    """逐表计数（含 audit_log），用于核对清理是否彻底。"""
    from evkg.store import KnowledgeStore

    store = KnowledgeStore(str(db))
    try:
        names = [
            row[0]
            for row in store.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        return {name: store.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in sorted(names)}
    finally:
        store.db.close()


def _diff(before: dict[str, int], after: dict[str, int]) -> dict[str, list[int]]:
    return {
        key: [before.get(key, 0), after.get(key, 0)]
        for key in sorted(set(before) | set(after))
        if before.get(key, 0) != after.get(key, 0)
    }


def _audit(db: Path, check: str) -> dict:
    report = adapter.audit(str(db))
    item = report["checks"][check]
    return {
        "status": report["status"],
        "total_violations": report["total_violations"],
        "check_violations": item["violations"],
        "check_sample": item["sample"],
    }


def _controlled_injection(work: Path, *, kind: str) -> dict:
    """受控注入：自己注入、自己测量、自己清理，全程由本脚本观测。

    kind = "fabricated_quote"  -> passage 存在、引文不存在（打引文保真）
    kind = "dangling_passage"  -> passage 不存在（打引用完整性）
    """
    from evkg.domain import EvidenceLink, Polarity
    from evkg.store import KnowledgeStore

    check = "evidence_quote_not_in_passage" if kind == "fabricated_quote" else "evidence_missing_passage"
    evidence_id = f"ev_controlled_{kind}"

    store = KnowledgeStore(str(work))
    try:
        claim_id = store.db.execute("SELECT id FROM claims ORDER BY id LIMIT 1").fetchone()[0]
        passage_row = store.db.execute("SELECT id FROM passages ORDER BY id LIMIT 1").fetchone()
        source_row = store.db.execute("SELECT id FROM sources ORDER BY id LIMIT 1").fetchone()
        source_id = source_row[0] if source_row else None
        if kind == "fabricated_quote":
            passage_id, quote = passage_row[0], FABRICATED_QUOTE
        else:
            passage_id, quote = "p_this_passage_does_not_exist", FAKE_QUOTE
    finally:
        store.db.close()

    before_counts = _table_counts(work)
    before = _audit(work, check)

    # ---- 注入 ----
    store = KnowledgeStore(str(work))
    try:
        store.save_evidence(
            EvidenceLink(
                id=evidence_id,
                claim_id=claim_id,
                passage_id=passage_id,
                polarity=Polarity.SUPPORTS,
                quote=quote,
                reasoning="M1-f 受控注入：数据看起来合理，但不满足不变量",
                confidence=0.9,
            ),
            "m1f_injection",
        )
        present = store.db.execute("SELECT COUNT(*) FROM evidence WHERE id=?", (evidence_id,)).fetchone()[0]
    finally:
        store.db.close()

    during = _audit(work, check)
    detected = during["check_violations"] > before["check_violations"]
    named = any(evidence_id in str(sample) for sample in during["check_sample"])

    # ---- 清理 ----
    store = KnowledgeStore(str(work))
    try:
        store.db.execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
        store.db.execute("DELETE FROM audit_log WHERE object_id=?", (evidence_id,))
        store.db.commit()
    finally:
        store.db.close()

    after_counts = _table_counts(work)
    final = _audit(work, check)
    delta = _diff(before_counts, after_counts)

    return {
        "attack": f"controlled_{kind}",
        "injected_data_type": (
            "已存在的 passage + 伪造引文（引文不在该 passage 文本中）"
            if kind == "fabricated_quote"
            else "已存在的 claim/source + **不存在的 passage_id**，引文看似合理"
        ),
        "targeted_invariant": check,
        "injected": {
            "evidence_id": evidence_id,
            "claim_id": claim_id,
            "source_id": source_id,
            "passage_id": passage_id,
            "quote": quote,
            "row_present_after_injection": present,
        },
        # 用户要求的三类留档形状
        "detected": bool(detected),
        "violations": [check] if detected else [],
        # 独立交叉验证（全部由本脚本自己测量）
        "cross_check": {
            "check_violations_before": before["check_violations"],
            "check_violations_during": during["check_violations"],
            "violation_count_increased": detected,
            "injected_id_named_in_audit_sample": named,
            "audit_status_during_injection": during["status"],
            "audit_total_violations_during": during["total_violations"],
        },
        "recovery": {
            "audit_status_after_cleanup": final["status"],
            "audit_total_violations_after_cleanup": final["total_violations"],
            "targeted_check_violations_after_cleanup": final["check_violations"],
            "counts_delta_excluding_audit_log": {k: v for k, v in delta.items() if k != "audit_log"},
            "counts_delta_raw": delta,
            "counts_delta_note": "audit_log 的增量来自本流程自身的审计/写入记录；其余表必须零差异",
        },
    }


def scenario_a_builtin(work: Path) -> dict:
    """A：evkg 内置自测（注入→审计→清理都在函数内部，故其违规为瞬时）。"""
    from evkg.attack import run_damage_selftest

    before_counts = _table_counts(work)
    raw = run_damage_selftest(str(work))
    after_counts = _table_counts(work)
    final = _audit(work, "evidence_quote_not_in_passage")
    delta = _diff(before_counts, after_counts)

    return {
        "scenario": "A_evkg_builtin",
        "targeted_invariant": "evidence_quote_not_in_passage",
        "injected_data_type": "存在的 passage + 伪造引文（由 evkg 内部注入并清理）",
        "raw_selftest": raw,
        "detected": raw.get("status") == "caught",
        "violations": ["evidence_quote_not_in_passage"] if raw.get("status") == "caught" else [],
        "measurement_caveat": (
            "内置函数把注入→审计→清理放在同一调用内，其 finally 会立即删除注入行。"
            "因此**无法在函数外部观测到注入期间的违规条数**，只能采信它自报的 caught。"
            "为不依赖自述，另加受控注入 A' 做独立测量。"
        ),
        "recovery": {
            "audit_status_after_cleanup": final["status"],
            "audit_total_violations_after_cleanup": final["total_violations"],
            "counts_delta_excluding_audit_log": {k: v for k, v in delta.items() if k != "audit_log"},
            "counts_delta_raw": delta,
        },
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    adapter.configure()

    shutil.copyfile(REAL_DB, WORK)
    real_before = _table_counts(REAL_DB)
    print(f"工作副本: {WORK.relative_to(REPO_ROOT)}（真实库的副本，真实库不参与注入）")
    print(f"真实库基线: {json.dumps({k: v for k, v in real_before.items() if v}, ensure_ascii=False)}\n")

    a = scenario_a_builtin(WORK)
    print("=== A. evkg 内置 run_damage_selftest ===")
    print(f"  注入: {a['injected_data_type']}")
    print(f"  自报: status={a['raw_selftest'].get('status')}  "
          f"injected_claim={a['raw_selftest'].get('injected_claim')}  "
          f"quote_violations={a['raw_selftest'].get('quote_violations_after_injection')}")
    print(f"  清理后: audit={a['recovery']['audit_status_after_cleanup']} "
          f"violations={a['recovery']['audit_total_violations_after_cleanup']}")
    print(f"  清理残留（除 audit_log）: {a['recovery']['counts_delta_excluding_audit_log'] or '无'}")

    controlled = [_controlled_injection(WORK, kind=k) for k in ("fabricated_quote", "dangling_passage")]
    for item in controlled:
        label = "A'. 受控注入：伪造引文（独立测量）" if "fabricated" in item["attack"] else \
                "B. 受控注入：passage_id 不存在（用户指定场景）"
        cross = item["cross_check"]
        print(f"\n=== {label} ===")
        print(f"  注入: {item['injected_data_type']}")
        print(f"  注入行确实落库: {item['injected']['row_present_after_injection']}")
        print(f"  打的不变量: {item['targeted_invariant']}")
        print(f"  违规条数: {cross['check_violations_before']} -> {cross['check_violations_during']} "
              f"(增加={cross['violation_count_increased']}, 审计样本点名注入行={cross['injected_id_named_in_audit_sample']})")
        print(f"  审计状态(注入期间): {cross['audit_status_during_injection']}  "
              f"总违规={cross['audit_total_violations_during']}")
        print(f"  detected={item['detected']}  violations={item['violations']}")
        print(f"  清理后: audit={item['recovery']['audit_status_after_cleanup']} "
              f"总数={item['recovery']['audit_total_violations_after_cleanup']} "
              f"目标不变量={item['recovery']['targeted_check_violations_after_cleanup']}")
        print(f"  清理残留（除 audit_log）: {item['recovery']['counts_delta_excluding_audit_log'] or '无'}")

    real_after = _table_counts(REAL_DB)
    real_delta = _diff(real_before, real_after)
    print(f"\n=== 真实库是否被触碰 ===\n  差异: {real_delta or '无（逐表计数一致）'}")

    all_scenarios = [a, *controlled]
    results = {
        "work_copy": str(WORK.relative_to(REPO_ROOT)),
        "real_db": str(REAL_DB.relative_to(REPO_ROOT)),
        "real_db_untouched": real_delta == {},
        "real_db_delta": real_delta,
        "scenario_a_builtin": a,
        "controlled_injections": controlled,
    }
    (OUT / "damage_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 用户要求的三类留档（严格按其形状）
    (OUT / "caught.json").write_text(json.dumps(
        [{"attack": s["scenario"] if "scenario" in s else s["attack"],
          "detected": s["detected"], "violations": s["violations"]} for s in all_scenarios],
        ensure_ascii=False, indent=2), encoding="utf-8")
    missed = [
        {"attack": s["scenario"] if "scenario" in s else s["attack"], "detected": False}
        for s in all_scenarios if not s["detected"]
    ]
    (OUT / "missed.json").write_text(json.dumps(missed, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "recovery.json").write_text(json.dumps(
        {(s["scenario"] if "scenario" in s else s["attack"]): s["recovery"] for s in all_scenarios},
        ensure_ascii=False, indent=2), encoding="utf-8")

    ok = all(s["detected"] for s in all_scenarios)
    ok &= all(s["recovery"]["audit_status_after_cleanup"] == "pass" for s in all_scenarios)
    ok &= all(s["recovery"]["audit_total_violations_after_cleanup"] == 0 for s in all_scenarios)
    ok &= all(not s["recovery"]["counts_delta_excluding_audit_log"] for s in all_scenarios)
    ok &= real_delta == {}
    print(f"\n=== M1-f 判定: {'通过' if ok else '未通过'} ===")
    print("  产物: artifacts/m1f/{damage_result,caught,missed,recovery}.json")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
