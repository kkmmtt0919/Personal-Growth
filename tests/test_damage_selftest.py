"""M1-f：故障注入自测 —— Evidence Graph 能否发现、拒绝并恢复伪造数据。

范围严格限定为**数据一致性**，不涉及模型攻击，也不涉及 M1-e 的呈现质量或
M2/M4 的产品语义。

每个场景都断言三件事（缺一不可）：

1. 注入确实落库（否则"没抓到"可能只是没注入成功 —— 假阴性）
2. 审计**发现**污染（目标不变量违规条数上升，且审计状态变 fail）
3. 清理后**恢复**一致（审计回到 pass/0，且除 audit_log 外逐表计数零差异）

第 1 条尤其重要：如果注入失败而审计仍报 pass，会得到"通过"的假象。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from growth_os.evidence import adapter

FAKE_QUOTE = "代码证明用户完成实现"
FABRICATED_QUOTE = "这段文字从未出现在任何原始材料中 test-injection"


@pytest.fixture()
def seeded(tmp_path: Path):
    """一个最小但完整的证据图：1 source + 1 passage + 1 claim + 1 合法 evidence。"""
    adapter.configure()
    store = adapter.open_store(tmp_path / "damage.db")
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

    text = "用户用 FastAPI 与 ChromaDB 实现了检索问答服务。"
    store.save_source(Source(id="src_t", title="t", kind=SourceKind.PRIMARY,
                             metadata={"assessment": {"baseline_score": 0.82}}))
    store.save_passages([Passage(id="p_t", source_id="src_t", ordinal=0, text=text,
                                 locator={"ordinal": 0}, text_hash="h")])
    store.save_claim(Claim(
        id="clm_t", subject="用户", predicate="实现过", object="检索问答",
        statement="用户实现过检索问答。", status=ClaimStatus.EXTRACTED,
        confidence=Confidence(score=0.8, source_reliability=0.82, extraction_quality=0.9,
                              resolution_quality=0.25, corroboration=0.0, contradiction_penalty=0.0,
                              rationale="t"),
        passage_ids=["p_t"],
    ))
    store.save_evidence(EvidenceLink(id="ev_ok", claim_id="clm_t", passage_id="p_t",
                                    polarity=Polarity.SUPPORTS, quote=text,
                                    reasoning="合法证据", confidence=0.8))
    yield store
    store.db.close()


# ---------------------------------------------------------------------------
# 前置：干净图本身必须自洽（否则后面"发现污染"无从判断）
# ---------------------------------------------------------------------------


def test_clean_graph_passes_audit(seeded):
    report = adapter.audit(str(seeded.path))
    assert report["status"] == "pass"
    assert report["total_violations"] == 0


def _inject(store, *, evidence_id: str, passage_id: str, quote: str) -> None:
    from evkg.domain import EvidenceLink, Polarity

    store.save_evidence(EvidenceLink(
        id=evidence_id, claim_id="clm_t", passage_id=passage_id,
        polarity=Polarity.SUPPORTS, quote=quote,
        reasoning="M1-f 注入：数据看似合理但不满足不变量", confidence=0.9,
    ), "test_injection")


def _cleanup(store, evidence_id: str) -> None:
    store.db.execute("DELETE FROM evidence WHERE id=?", (evidence_id,))
    store.db.execute("DELETE FROM audit_log WHERE object_id=?", (evidence_id,))
    store.db.commit()


def _counts(store) -> dict[str, int]:
    names = [row[0] for row in store.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    return {name: store.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in sorted(names)}


def _data_counts(store) -> dict[str, int]:
    """数据表计数，**排除 audit_log**。

    audit_log 是"发生了什么"的流水：本流程自己调用了若干次审计，每次都合法地追加一行。
    要求它也复原是错的 —— 那等于要求"事后不留任何痕迹"。真正要复原的是数据表。
    """
    return {key: value for key, value in _counts(store).items() if key != "audit_log"}


# ---------------------------------------------------------------------------
# 场景 B（用户指定）：不存在的 passage_id —— 打引用完整性
# ---------------------------------------------------------------------------


def test_dangling_passage_is_detected_and_recovered(seeded):
    check = "evidence_missing_passage"
    before_audit = adapter.audit(str(seeded.path))
    before_counts = _data_counts(seeded)

    _inject(seeded, evidence_id="ev_dangle", passage_id="p_does_not_exist", quote=FAKE_QUOTE)
    # 1) 注入确实落库 —— 否则"没抓到"是假阴性
    assert seeded.db.execute(
        "SELECT COUNT(*) FROM evidence WHERE id='ev_dangle'").fetchone()[0] == 1

    during = adapter.audit(str(seeded.path))
    # 2) 审计发现污染
    assert during["status"] == "fail"
    assert during["checks"][check]["violations"] > before_audit["checks"][check]["violations"], \
        "目标不变量违规条数未上升"
    assert any("ev_dangle" in str(s) for s in during["checks"][check]["sample"]), \
        "审计样本未点名注入行"

    _cleanup(seeded, "ev_dangle")

    # 3) 清理后恢复一致
    after = adapter.audit(str(seeded.path))
    assert after["status"] == "pass"
    assert after["total_violations"] == 0
    assert _data_counts(seeded) == before_counts, "清理后数据表计数未复原"


def test_dangling_passage_detection_is_not_a_coincidence(seeded):
    """注入前目标不变量必须是 0 条，否则"上升"可能来自既有污染。"""
    before = adapter.audit(str(seeded.path))
    assert before["checks"]["evidence_missing_passage"]["violations"] == 0


# ---------------------------------------------------------------------------
# 场景 A'：存在的 passage + 伪造引文 —— 打引文保真
# ---------------------------------------------------------------------------


def test_fabricated_quote_is_detected_and_recovered(seeded):
    check = "evidence_quote_not_in_passage"
    before_audit = adapter.audit(str(seeded.path))
    before_counts = _data_counts(seeded)

    _inject(seeded, evidence_id="ev_fake_quote", passage_id="p_t", quote=FABRICATED_QUOTE)
    assert seeded.db.execute(
        "SELECT COUNT(*) FROM evidence WHERE id='ev_fake_quote'").fetchone()[0] == 1

    during = adapter.audit(str(seeded.path))
    assert during["status"] == "fail"
    assert during["checks"][check]["violations"] > before_audit["checks"][check]["violations"]

    _cleanup(seeded, "ev_fake_quote")

    after = adapter.audit(str(seeded.path))
    assert after["status"] == "pass"
    assert _data_counts(seeded) == before_counts


def test_quote_that_is_a_substring_is_not_flagged(seeded):
    """边界：引文是原文子串时必须**不**触发违规（避免检查过宽）。"""
    _inject(seeded, evidence_id="ev_prefix", passage_id="p_t", quote="检索问答服务")
    report = adapter.audit(str(seeded.path))
    assert report["checks"]["evidence_quote_not_in_passage"]["violations"] == 0, \
        "子串引文被误判为伪造"
    assert report["status"] == "pass"


# ---------------------------------------------------------------------------
# evkg 内置自测
# ---------------------------------------------------------------------------


def test_builtin_selftest_reports_caught(seeded):
    from evkg.attack import run_damage_selftest

    result = run_damage_selftest(str(seeded.path))
    assert result["status"] == "caught", f"内置自测未抓到: {result}"
    assert result["quote_violations_after_injection"] >= 1


def test_builtin_selftest_leaves_no_residue(seeded):
    """内置自测必须自己清理干净：除 audit_log 外零差异，且审计恢复 pass。"""
    from evkg.attack import run_damage_selftest

    before = _counts(seeded)
    run_damage_selftest(str(seeded.path))
    after = _counts(seeded)

    delta = {k: [before[k], after[k]] for k in before if before[k] != after.get(k)}
    assert set(delta) <= {"audit_log"}, f"内置自测留下残留: {delta}"
    report = adapter.audit(str(seeded.path))
    assert report["status"] == "pass"
    assert report["total_violations"] == 0


def test_builtin_selftest_skips_when_no_passages(tmp_path):
    """空库没有可注入的锚点，应如实 skipped，而不是假装通过。"""
    from evkg.attack import run_damage_selftest

    adapter.configure()
    store = adapter.open_store(tmp_path / "empty.db")
    try:
        result = run_damage_selftest(str(store.path))
        assert result["status"] == "skipped"
        assert "no passages" in result["reason"]
    finally:
        store.db.close()
