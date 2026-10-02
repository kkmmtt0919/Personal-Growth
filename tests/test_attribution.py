"""M3-a：归属层与消费规则的测试。

锁定三件事（`docs/M3-PLAN.md` v1.0 §3 + 决策 4/5）：

1. 取值严格限定为三种，非法取值被拒（不静默兜底）；
2. 归属只进 `Source.metadata`，可原样读回；未声明按 `unknown` 处理（fail-closed）；
3. **消费规则**：只有 `user_declared` 且通道为 `user_evidence` 才能支撑用户能力断言；
   `domain_reference` 无论归属如何都只能作外部参考，`user_asserted` 不得单独支撑结论。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from growth_os.evidence import adapter
from growth_os.evidence.attribution import (
    ATTRIBUTION_METADATA_KEY,
    ATTRIBUTIONS,
    AttributionError,
    attribution_of,
    can_support_user_claim,
    is_external_reference,
    validate_attribution,
)

DOC_TEXT = """# 示例材料

这是一份用于验证归属层的最小材料。它包含一句实践描述与一句计划描述。

计划学习 Agent Evaluation。
"""

JD_TEXT = """# AI 应用工程师（岗位要求）

任职要求：
- 熟悉 RAG 检索增强生成与向量数据库；
- 具备 Agent 编排与工具调用经验。
"""


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "attribution.db")


@pytest.fixture()
def docs(tmp_path: Path) -> dict[str, Path]:
    owned = tmp_path / "my_note.md"
    owned.write_text(DOC_TEXT, encoding="utf-8")
    jd = tmp_path / "jd.md"
    jd.write_text(JD_TEXT, encoding="utf-8")
    return {"owned": owned, "jd": jd}


# ---------------------------------------------------------------------------
# 1. 取值与词汇表
# ---------------------------------------------------------------------------


def test_only_three_attribution_values_exist():
    assert ATTRIBUTIONS == ("user_declared", "user_asserted", "unknown")
    assert ATTRIBUTION_METADATA_KEY == "growth_attribution"


@pytest.mark.parametrize("value", ["mine", "USER_DECLARED", "", "declared", "unknown "])
def test_invalid_attribution_value_is_rejected(value):
    with pytest.raises(AttributionError, match="未知归属取值"):
        validate_attribution(value)


def test_attribution_of_fails_closed():
    """缺失 / 非法 / 空 metadata 一律按 unknown —— 绝不能默认成"用户声明过"。"""
    assert attribution_of(None) == "unknown"
    assert attribution_of({}) == "unknown"
    assert attribution_of({ATTRIBUTION_METADATA_KEY: "mine"}) == "unknown"
    assert attribution_of({ATTRIBUTION_METADATA_KEY: "user_declared"}) == "user_declared"
    assert attribution_of({ATTRIBUTION_METADATA_KEY: "user_asserted"}) == "user_asserted"


# ---------------------------------------------------------------------------
# 2. 落库与读回：只进 Source.metadata
# ---------------------------------------------------------------------------


def test_ingest_writes_attribution_into_source_metadata(store, docs):
    result = adapter.ingest_document(
        docs["owned"],
        store=store,
        evidence_type="uploaded_doc",
        attribution="user_declared",
    )
    assert result.attribution == "user_declared"
    metadata = adapter.source_metadata(store, result.source_id)
    assert metadata[ATTRIBUTION_METADATA_KEY] == "user_declared"
    assert metadata["growth_channel"] == "user_evidence"
    assert attribution_of(metadata) == "user_declared"


def test_ingest_without_attribution_records_nothing_and_reads_as_unknown(store, docs):
    result = adapter.ingest_document(docs["owned"], store=store, evidence_type="uploaded_doc")
    assert result.attribution is None
    metadata = adapter.source_metadata(store, result.source_id)
    assert ATTRIBUTION_METADATA_KEY not in metadata
    assert attribution_of(metadata) == "unknown"


def test_ingest_rejects_invalid_attribution_with_product_error(store, docs):
    with pytest.raises(adapter.EvidenceError, match="未知归属取值"):
        adapter.ingest_document(
            docs["owned"], store=store, evidence_type="uploaded_doc", attribution="mine"
        )


def test_attribution_stays_in_metadata_and_does_not_break_existing_tags(store, docs):
    """归属是**增量**：不得影响既有的 evidence_type / channel / assessment。"""
    result = adapter.ingest_document(
        docs["owned"],
        store=store,
        evidence_type="uploaded_doc",
        channel="user_evidence",
        attribution="user_asserted",
    )
    metadata = adapter.source_metadata(store, result.source_id)
    assert metadata["growth_evidence_type"] == "uploaded_doc"
    assert metadata["growth_channel"] == "user_evidence"
    assert "assessment" in metadata and metadata["assessment"]["baseline_score"] == 0.68


# ---------------------------------------------------------------------------
# 3. 消费规则（本步的核心）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attribution", "channel", "expected"),
    [
        ("user_declared", "user_evidence", True),
        # 用户声明过、但通道是领域参考 → 仍然只能作外部参考（与关系）
        ("user_declared", "domain_reference", False),
        # 只有口头声称，没有产物 → 不得单独支撑结论
        ("user_asserted", "user_evidence", False),
        ("user_asserted", "domain_reference", False),
        # 未声明 / 第三方材料 → 永远不能
        ("unknown", "user_evidence", False),
        ("unknown", "domain_reference", False),
        (None, "user_evidence", False),
        (None, "domain_reference", False),
        ("user_declared", None, False),
        # 非法值也不得被误判成可支撑
        ("mine", "user_evidence", False),
    ],
)
def test_can_support_user_claim_matrix(attribution, channel, expected):
    assert can_support_user_claim(attribution, channel) is expected


def test_domain_reference_material_cannot_enter_user_claims(store, docs):
    """JD/岗位资料走 domain_reference：即使由用户上传，也不进入用户能力断言。"""
    result = adapter.ingest_document(
        docs["jd"],
        store=store,
        evidence_type="external_ref",
        channel="domain_reference",
        attribution="unknown",
    )
    metadata = adapter.source_metadata(store, result.source_id)
    assert is_external_reference(metadata["growth_channel"])
    assert attribution_of(metadata) == "unknown"
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is False
    # 通道过滤能把领域资料与用户证据分开（M1-b 的能力，此处回归确认）
    assert adapter.sources_by_channel(store, "domain_reference") == [result.source_id]
    assert adapter.sources_by_channel(store, "user_evidence") == []


def test_user_declared_material_can_support(store, docs):
    result = adapter.ingest_document(
        docs["owned"],
        store=store,
        evidence_type="repo_artifact",
        attribution="user_declared",
    )
    metadata = adapter.source_metadata(store, result.source_id)
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is True
    assert adapter.sources_by_channel(store, "user_evidence") == [result.source_id]


def test_user_asserted_needs_corroboration(store, docs):
    """用户口头声称只能作弱证据：可与产物互补，但本身不得单独支撑结论。"""
    asserted = adapter.ingest_document(
        docs["owned"],
        store=store,
        evidence_type="chat_assertion",
        attribution="user_asserted",
    )
    metadata = adapter.source_metadata(store, asserted.source_id)
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is False
    # 弱证据的来源类型仍按领域包给出低基线（M1-a 已锁定 0.35）
    assert metadata["assessment"]["baseline_score"] == 0.35
