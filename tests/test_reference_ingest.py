"""M3-d：外部参考通道（JD / `domain_reference`）的离线测试。

锁定用户指定的 M3-d 六条边界，重点是"三条不得"由**结构**保证：

* 通道硬编码（本模块入口没有 `channel` / `evidence_type` 参数）；
* 消费侧兜底（`can_support_user_claim` 对参考材料一律 False）；
* 抽取只读（不写 claim / evidence / entity，不做评分与差距）。
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from growth_os.evidence import adapter
from growth_os.evidence.attribution import attribution_of, can_support_user_claim
from growth_os.evidence.reference import (
    REFERENCE_CHANNEL,
    REFERENCE_EVIDENCE_TYPE,
    REFERENCE_KIND_KEY,
    extract_reference_profile,
    ingest_reference_document,
)

JD_TEXT = """# AI 应用工程师（Agent 方向）

## 岗位职责

1. 负责 AI Agent 应用的架构设计与开发，落地工具调用与多步规划；
2. 基于 RAG 构建检索增强问答链路，完成向量检索优化。

## 任职要求

- 熟悉 Python，具备 FastAPI 或 Spring Boot 之一的服务端开发经验；
- 熟悉 LLM 应用开发，了解 LangChain / LlamaIndex 等框架；
- 掌握向量数据库（ChromaDB、Milvus 任一）与向量检索原理；
- 具备 Docker 与 CI/CD 实践经验，熟悉 Linux 环境。

## 加分项

- 了解 TypeScript 与 React 者优先。
"""


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "reference.db")


@pytest.fixture()
def jd(tmp_path: Path) -> Path:
    path = tmp_path / "jd.md"
    path.write_text(JD_TEXT, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. 通道锁定（结构保证）
# ---------------------------------------------------------------------------


def test_entry_has_no_channel_or_evidence_type_parameter():
    """入口签名里没有 channel / evidence_type —— 调用方无法把它写进 user_evidence。"""
    parameters = inspect.signature(ingest_reference_document).parameters
    assert "channel" not in parameters
    assert "evidence_type" not in parameters


def test_reference_ingest_lands_in_domain_reference_only(store, jd):
    result = ingest_reference_document(jd, store=store)
    metadata = adapter.source_metadata(store, result.source_id)

    assert metadata["growth_channel"] == REFERENCE_CHANNEL == "domain_reference"
    assert metadata["growth_evidence_type"] == REFERENCE_EVIDENCE_TYPE == "external_ref"
    assert metadata[REFERENCE_KIND_KEY] == "job_description"
    assert adapter.sources_by_channel(store, "domain_reference") == [result.source_id]
    assert adapter.sources_by_channel(store, "user_evidence") == []


def test_jd_cannot_support_user_claims(store, jd):
    """边界 1–3：即使归属是 `user_declared`，通道一票否决。"""
    result = ingest_reference_document(jd, store=store, attribution="user_declared")
    metadata = adapter.source_metadata(store, result.source_id)

    assert attribution_of(metadata) == "user_declared"  # 用户确实把材料给了我们
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is False
    assert store.counts()["claims"] == 0  # 不产出任何能力断言


# ---------------------------------------------------------------------------
# 2. 参考抽取（只读、带证据、确定性）
# ---------------------------------------------------------------------------


def test_extract_profile_lists_terms_and_requirements_with_passage_evidence(store, jd):
    result = ingest_reference_document(jd, store=store)
    profile = extract_reference_profile(store, result.source_id)

    assert profile["reference_kind"] == "job_description"
    assert profile["channel"] == "domain_reference"
    for term in ("python", "fastapi", "spring boot", "rag", "llm", "langchain", "chromadb", "docker", "ci/cd", "linux"):
        assert term in profile["tech_terms"], f"缺少技术词: {term}"

    passage_ids = {item.id for item in store.get_passages(source_id=result.source_id)}
    for term, ids in profile["tech_terms"].items():
        assert ids, f"{term} 没有证据 passage"
        assert set(ids) <= passage_ids
    assert profile["requirement_lines"], "应当识别出要求条目"
    assert all(item["passage_id"] in passage_ids for item in profile["requirement_lines"])
    assert profile == extract_reference_profile(store, result.source_id)  # 确定性


def test_extract_is_read_only(store, jd):
    """边界 5：抽取不写 claim / evidence / entity，也不做评分或差距。"""
    result = ingest_reference_document(jd, store=store)
    before = store.counts()
    extract_reference_profile(store, result.source_id)
    after = store.counts()
    assert after == before
    assert after["claims"] == 0 and after["evidence"] == 0 and after["entities"] == 0


def test_extract_refuses_non_reference_sources(store, tmp_path):
    """抽取只服务外部参考：对用户证据来源调用应当被拒绝（避免被当成通用读取器）。"""
    note = tmp_path / "note.md"
    note.write_text("# 我的笔记\n\n我在练习工具调用。\n", encoding="utf-8")
    result = adapter.ingest_document(note, store=store, evidence_type="uploaded_doc")
    with pytest.raises(adapter.EvidenceError, match="domain_reference"):
        extract_reference_profile(store, result.source_id)


def test_terms_use_word_boundaries_for_ascii(store, tmp_path):
    """ASCII 词不能误命中："go" 不应被 "google" 命中。"""
    doc = tmp_path / "jd2.md"
    doc.write_text("# 要求\n\n- 了解 Google Analytics 报表。\n", encoding="utf-8")
    result = ingest_reference_document(doc, store=store)
    profile = extract_reference_profile(store, result.source_id)
    assert "go" not in profile["tech_terms"]


def test_multiple_references_are_listed_separately(store, tmp_path):
    first = tmp_path / "jd_a.md"
    first.write_text("# 岗位 A\n\n- 熟悉 Python 与 FastAPI。\n", encoding="utf-8")
    second = tmp_path / "jd_b.md"
    second.write_text("# 岗位 B\n\n- 熟悉 Java 与 Spring Boot。\n", encoding="utf-8")
    a = ingest_reference_document(first, store=store)
    b = ingest_reference_document(second, store=store, reference_kind="job_description")

    assert adapter.sources_by_channel(store, "domain_reference") == sorted([a.source_id, b.source_id])
    assert adapter.sources_by_channel(store, "user_evidence") == []
    assert "python" in extract_reference_profile(store, a.source_id)["tech_terms"]
    assert "java" in extract_reference_profile(store, b.source_id)["tech_terms"]
