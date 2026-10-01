"""M1-b：证据适配层的回归测试。

设计说明：本文件用 tmp_path 里的小样本做**可移植**的确定性测试；对真实仓库
（mytset-rag）的验证由 scripts/smoke_ingest.py 承担，并在下面用 skipif 挂一个
真实材料的补充用例。两者分工：这里保证行为不变，冒烟保证真实材料可用。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from growth_os.evidence import adapter

REAL_JAVA = (
    Path(__file__).resolve().parents[1].parent
    / "mytset-rag"
    / "src"
    / "main"
    / "java"
    / "com"
    / "hw"
    / "service"
    / "RagService.java"
)

README_TEXT = """# 示例项目

这是一个用于验证的示例项目，使用 FastAPI 与 ChromaDB 实现检索问答。

## 已知不足

rerank 部分我只是看过论文，还没有自己实现过，因此缺少实践证据。

## 计划

接下来计划学习 Agent Evaluation，并补齐评测集。
"""

CODE_TEXT = """package com.example;

public class Demo {
    public String search(String query) {
        return "result for " + query;
    }
}
"""


@pytest.fixture()
def store(tmp_path: Path):
    """每个用例独立的知识库，避免相互污染。"""
    return adapter.open_store(tmp_path / "test.db")


@pytest.fixture()
def files(tmp_path: Path) -> dict[str, Path]:
    readme = tmp_path / "README.md"
    readme.write_text(README_TEXT, encoding="utf-8")
    code = tmp_path / "Demo.java"
    code.write_text(CODE_TEXT, encoding="utf-8")
    binary = tmp_path / "paper.pdf"
    binary.write_bytes(b"%PDF-1.4 not really a pdf")
    return {"readme": readme, "code": code, "binary": binary}


# ---------------------------------------------------------------------------
# 1. 基本入库与路由选择
# ---------------------------------------------------------------------------


def test_configure_activates_growth_profile():
    profile = adapter.configure()
    assert profile.name == "growth_os"
    # 切分边界必须来自成长领域包（split_passages 读进程级 active()）
    assert profile.splitting.boundary != type(profile.splitting).model_fields[
        "boundary"
    ].default


def test_markdown_uses_evkg_fast_path(store, files):
    result = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    assert result.route == "evkg.ingest_file"
    assert result.kind == "primary"
    assert result.passage_count > 0


def test_code_file_uses_evkg_code_route(store, files):
    """源码走 evkg 的 ingest_code_file（b.5a 起），不再是适配层自造的 text_like。"""
    result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    assert result.route == "evkg.ingest_code_file"
    assert result.kind == "code"
    assert result.passage_count > 0


def test_code_kind_change_is_score_neutral(store, files):
    """把源码从 primary 改判为 code 不得改变评分 —— 只是语义更准。

    旧数据不能被"顺手升级"：code 与 primary 的基线都是 0.82。
    """
    code_result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    doc_result = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    code_meta = adapter.source_metadata(store, code_result.source_id)
    doc_meta = adapter.source_metadata(store, doc_result.source_id)

    assert code_meta["assessment"]["baseline_score"] == 0.82
    assert doc_meta["assessment"]["baseline_score"] == 0.82
    assert code_result.kind == "code" and doc_result.kind == "primary"


def test_code_passages_carry_line_range_locator(store, files):
    """M4 要能点回『RagService.java L42-L58』，locator 必须带行范围。"""
    result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    passages = store.get_passages(source_id=result.source_id)
    assert passages
    for passage in passages:
        assert "line_start" in passage.locator
        assert "line_end" in passage.locator
        assert passage.locator["language"] == "java"
        assert passage.locator["path"].endswith("Demo.java")


def test_code_locators_round_trip_to_original_file(store, files):
    """核心不变式：拿 locator 切回原始文件，必须逐字等于 passage.text。"""
    result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    on_disk = files["code"].read_text(encoding="utf-8")
    lines = on_disk.split("\n")
    for passage in store.get_passages(source_id=result.source_id):
        start, end = passage.locator["line_start"], passage.locator["line_end"]
        assert "\n".join(lines[start - 1 : end]) == passage.text


def test_code_indentation_is_preserved(store, files):
    """文本切分会压平缩进；源码必须保留，否则代码读不出结构。"""
    result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    joined = "\n".join(item.text for item in store.get_passages(source_id=result.source_id))
    assert "        return" in joined, "缩进被抹平了"


def test_extensionless_build_files_are_handled(store, tmp_path):
    """Dockerfile/Makefile 这类无扩展名文件不能被漏掉（旧兜底路由覆盖过它们）。"""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.12-slim\n\nRUN pip install uv\n", encoding="utf-8")
    result = adapter.ingest_document(
        dockerfile, store=store, evidence_type="repo_artifact"
    )
    assert result.route == "evkg.ingest_code_file"
    assert result.kind == "code"
    passages = store.get_passages(source_id=result.source_id)
    assert passages and passages[0].locator["language"] == "dockerfile"


def test_binary_suffix_is_rejected(store, files):
    """二进制格式留给 M3，不应静默当成文本读进来。"""
    with pytest.raises(adapter.EvidenceError, match="暂不支持"):
        adapter.ingest_document(
            files["binary"], store=store, evidence_type="repo_artifact"
        )


def test_unknown_evidence_type_is_rejected(store, files):
    with pytest.raises(adapter.EvidenceError, match="未知证据类型"):
        adapter.ingest_document(
            files["readme"], store=store, evidence_type="not_a_real_type"  # type: ignore[arg-type]
        )


def test_unknown_channel_is_rejected(store, files):
    with pytest.raises(adapter.EvidenceError, match="未知证据通道"):
        adapter.ingest_document(
            files["readme"], store=store, evidence_type="repo_artifact", channel="bogus"  # type: ignore[arg-type]
        )


def test_missing_file_is_rejected(store, tmp_path):
    with pytest.raises(adapter.EvidenceError, match="文件不存在"):
        adapter.ingest_document(
            tmp_path / "nope.md", store=store, evidence_type="repo_artifact"
        )


# ---------------------------------------------------------------------------
# 2. ★ 双轨记录：成长标签与 evkg 的 assessment 必须共存
# ---------------------------------------------------------------------------


def test_growth_tags_coexist_with_assessment(store, files):
    """本步最关键的断言。

    evkg 的 ``ingest_file`` 会写 ``metadata.assessment``，而它被
    ``extract.py:105-106`` 用于计算置信度。若适配层用整体替换的方式写
    metadata，就会把 assessment 抹掉，让置信度静默退化成"未知来源 0.25"。
    """
    result = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    meta = adapter.source_metadata(store, result.source_id)

    assert meta["growth_evidence_type"] == "repo_artifact"
    assert meta["growth_channel"] == "user_evidence"
    assert "assessment" in meta, "evkg 的 assessment 被覆盖了"
    assert meta["assessment"]["baseline_score"] == 0.82


def test_code_route_also_preserves_assessment(store, files):
    """兜底路由是自己构造 Source 的，同样必须带上 assessment。"""
    result = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    meta = adapter.source_metadata(store, result.source_id)
    assert meta["assessment"]["baseline_score"] == 0.82
    assert meta["growth_evidence_type"] == "repo_artifact"


@pytest.mark.parametrize(
    ("evidence_type", "expected_baseline", "expected_kind"),
    [
        ("task_submission", 0.82, "primary"),
        ("repo_artifact", 0.82, "primary"),
        ("probe_result", 0.78, "contemporary"),
        ("uploaded_doc", 0.68, "compilation"),
        ("external_ref", 0.62, "modern_study"),
        ("chat_assertion", 0.35, "folk"),
    ],
)
def test_evidence_type_maps_to_expected_baseline(
    store, files, evidence_type, expected_baseline, expected_kind
):
    """证据强度分层的落地：类型 → kind → baseline。

    这张表是 PRD §10「证据优先级」的实现基础，不能悄悄漂移。
    """
    result = adapter.ingest_document(
        files["readme"], store=store, evidence_type=evidence_type
    )
    meta = adapter.source_metadata(store, result.source_id)
    assert result.kind == expected_kind
    assert meta["assessment"]["baseline_score"] == expected_baseline


def test_assessment_rationale_comes_from_growth_profile(store, files):
    """baseline 正确还不够 —— rationale 必须也是成长语义的，不是 evkg 默认的。"""
    result = adapter.ingest_document(
        files["readme"], store=store, evidence_type="chat_assertion"
    )
    meta = adapter.source_metadata(store, result.source_id)
    assert "自述" in meta["assessment"]["rationale"]


# ---------------------------------------------------------------------------
# 3. 通道过滤（R2 的收口）
# ---------------------------------------------------------------------------


def test_channel_filter_separates_evidence_from_reference(store, files):
    """把"用户的证据"与"领域参考"分开。

    不分通道的后果：岗位 JD 里写"AI 工程师需要会 RAG"，会被误读成
    "用户会 RAG"，直接击穿 PRD §33 的证据可追溯性。
    """
    user = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact", channel="user_evidence"
    )
    ref = adapter.ingest_document(
        files["readme"], store=store, evidence_type="external_ref", channel="domain_reference"
    )

    assert adapter.sources_by_channel(store, "user_evidence") == [user.source_id]
    assert adapter.sources_by_channel(store, "domain_reference") == [ref.source_id]


def test_filter_by_evidence_type(store, files):
    first = adapter.ingest_document(
        files["code"], store=store, evidence_type="repo_artifact"
    )
    adapter.ingest_document(files["readme"], store=store, evidence_type="uploaded_doc")

    assert adapter.sources_by_evidence_type(store, "repo_artifact") == [first.source_id]


# ---------------------------------------------------------------------------
# 4. 幂等与重打标签
# ---------------------------------------------------------------------------


def test_reingest_is_idempotent(store, files):
    """底层是 INSERT OR IGNORE，重复入库不应产生新行。"""
    first = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    counts_before = adapter.counts(store)

    second = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    counts_after = adapter.counts(store)

    assert first.source_id == second.source_id
    assert counts_before["sources"] == counts_after["sources"]
    assert counts_before["passages"] == counts_after["passages"]


def test_retag_replaces_growth_labels_but_keeps_assessment(store, files):
    """重打标签必须生效（INSERT OR IGNORE 下唯一可行的修补方式）。"""
    result = adapter.ingest_document(
        files["readme"], store=store, evidence_type="repo_artifact"
    )
    adapter.ingest_document(
        files["readme"], store=store, evidence_type="external_ref", channel="domain_reference"
    )

    meta = adapter.source_metadata(store, result.source_id)
    assert meta["growth_evidence_type"] == "external_ref"
    assert meta["growth_channel"] == "domain_reference"
    assert meta["assessment"]["baseline_score"] == 0.62
    # 重打标签不应产生第二行
    assert adapter.counts(store)["sources"] == 1


def test_source_metadata_raises_for_unknown_source(store):
    with pytest.raises(adapter.EvidenceError, match="未知 source"):
        adapter.source_metadata(store, "src_does_not_exist")


# ---------------------------------------------------------------------------
# 5. 真实材料（本地存在时才跑）
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_JAVA.is_file(), reason="本机没有 mytset-rag 仓库")
def test_real_java_file_ingests(store):
    result = adapter.ingest_document(
        REAL_JAVA, store=store, evidence_type="repo_artifact"
    )
    assert result.route == "evkg.ingest_code_file"
    assert result.kind == "code"
    assert result.passage_count > 0
    passages = store.get_passages(source_id=result.source_id)
    joined = " ".join(p.text for p in passages)
    assert "class" in joined or "public" in joined, "切分后应保留代码文本"
