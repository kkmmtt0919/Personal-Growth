"""M3-e：材料口径断言的写入路径测试（越权校验在此接线）。

锁定三件事：

1. **越权表述被拒绝**（M1-c 那条历史主张的形状必须在写入前被拦下，且不写半条数据）；
2. **材料口径表述被接受**：逐字引用、`score=None`（未评估）、可追溯；
3. **可审计**：写入后 `audit_store` = pass/0，provenance（claim → evidence → passage → source）可走通。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from growth_os.evidence import adapter
from growth_os.evidence.claims import check_overreach


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "material.db")


@pytest.fixture()
def material(store, tmp_path) -> dict:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# MYtest\n\n项目包含 RAG 检索服务（RagService.java）与 ChromaDB 向量库。\n\n"
        "另含 MCP 工具注册与调用模块。\n",
        encoding="utf-8",
    )
    code = tmp_path / "RagService.java"
    code.write_text("public class RagService {\n    // 检索实现\n}\n", encoding="utf-8")
    readme_result = adapter.ingest_document(
        readme, store=store, evidence_type="repo_artifact", attribution="user_declared"
    )
    code_result = adapter.ingest_document(
        code, store=store, evidence_type="repo_artifact", attribution="user_declared"
    )
    return {
        "readme_source": readme_result.source_id,
        "code_source": code_result.source_id,
        "readme_passages": [item.id for item in store.get_passages(source_id=readme_result.source_id)],
        "code_passages": [item.id for item in store.get_passages(source_id=code_result.source_id)],
    }


# ---------------------------------------------------------------------------
# 1. 越权表述：写入前拒绝，且不写半条数据
# ---------------------------------------------------------------------------


def test_user_scoped_claim_is_rejected_before_any_write(store, material):
    """M1-c 那条历史主张的形状（subject=用户 + predicate=实现过）必须在写入前被拒。"""
    before = {key: value for key, value in store.counts().items() if key != "audit_log"}
    with pytest.raises(adapter.EvidenceError, match="越权"):
        adapter.create_material_claim(
            store,
            subject="用户",
            predicate="实现过",
            object="RAG 检索服务",
            statement="用户实现过 RAG 检索服务",
            passage_ids=material["readme_passages"],
        )
    after = {key: value for key, value in store.counts().items() if key != "audit_log"}
    assert after == before  # 一条 claim/evidence 都没写进去（audit_log 除外）


@pytest.mark.parametrize(
    ("subject", "predicate", "statement"),
    [
        ("用户", "具备", "用户具备 RAG 能力 4/5"),
        ("本人", "独立完成", "本人独立完成了该项目"),
        ("用户", "掌握", "用户掌握 Agent Memory 的实现"),
    ],
)
def test_various_overreach_shapes_are_rejected(store, material, subject, predicate, statement):
    with pytest.raises(adapter.EvidenceError):
        adapter.create_material_claim(
            store, subject=subject, predicate=predicate, object="X", statement=statement,
            passage_ids=material["readme_passages"][:1],
        )


# ---------------------------------------------------------------------------
# 2. 材料口径：接受、逐字引用、未评估
# ---------------------------------------------------------------------------


def test_material_scoped_claim_is_created_with_verbatim_quotes(store, material):
    result = adapter.create_material_claim(
        store,
        subject="MYtest 项目材料",
        predicate="包含",
        object="RAG 检索服务相关实现",
        statement="项目材料中出现 RAG 检索服务相关的实现内容（RagService.java、ChromaDB 依赖）",
        passage_ids=material["readme_passages"],
        metadata={"growth_source_kind": "github_public_repo"},
    )
    claim = next(item for item in store.get_claims() if item.id == result["claim_id"])
    assert claim.status.value == "evidence_linked"
    assert claim.confidence.score is None
    assert claim.confidence.assessment_status == "unassessed"
    assert claim.metadata["growth_claim_scope"] == "material"
    assert claim.metadata["growth_source_kind"] == "github_public_repo"

    dossier = adapter.claim_dossier(store, result["claim_id"])
    assert dossier is not None
    by_id = {item["id"]: item for item in dossier["evidence"]}
    for evidence_id, passage_id in zip(result["evidence_ids"], material["readme_passages"], strict=True):
        link = by_id[evidence_id]
        passage = next(item for item in store.get_passages() if item.id == passage_id)
        assert link["quote"] == passage.text  # 逐字引用
        assert link["quote"] in link["passage_text"]
        assert link["confidence"] is None  # 未评估，而不是某个数字


def test_self_report_wording_is_allowed(store, material, tmp_path):
    """材料口径的自述转述合规：`对话材料中出现用户自述…` 不是能力结论。"""
    chat = tmp_path / "chat.md"
    chat.write_text("对话记录：用户自述「我会 Agent Memory，但还没做过项目」。\n", encoding="utf-8")
    chat_source = adapter.ingest_document(
        chat, store=store, evidence_type="chat_assertion", attribution="user_asserted"
    )
    passage_ids = [item.id for item in store.get_passages(source_id=chat_source.source_id)]
    result = adapter.create_material_claim(
        store,
        subject="对话材料",
        predicate="包含",
        object="用户自述的 Agent Memory 描述",
        statement="对话材料中出现用户自述「我会 Agent Memory」，同时自述尚未做过项目",
        passage_ids=passage_ids,
    )
    assert check_overreach(
        statement="对话材料中出现用户自述「我会 Agent Memory」", subject="对话材料", predicate="包含"
    ).overreach is False
    assert any(item.id == result["claim_id"] for item in store.get_claims())


# ---------------------------------------------------------------------------
# 3. 幂等 / 可追溯 / 可审计
# ---------------------------------------------------------------------------


def test_creation_is_idempotent(store, material):
    kwargs = {
        "subject": "MYtest 项目材料",
        "predicate": "包含",
        "object": "RAG 检索服务相关实现",
        "statement": "项目材料中出现 RAG 检索服务相关的实现内容",
        "passage_ids": material["readme_passages"],
    }
    first = adapter.create_material_claim(store, **kwargs)
    before = {key: value for key, value in store.counts().items() if key != "audit_log"}
    second = adapter.create_material_claim(store, **kwargs)

    assert first["claim_id"] == second["claim_id"]
    after = {key: value for key, value in store.counts().items() if key != "audit_log"}
    assert after == before  # 数据表零新增（audit_log 本就该增长，不纳入比对）


def test_unknown_passage_is_rejected_without_writes(store, material):
    before = {key: value for key, value in store.counts().items() if key != "audit_log"}
    with pytest.raises(adapter.EvidenceError, match="未知 passage"):
        adapter.create_material_claim(
            store, subject="项目材料", predicate="包含", object="X",
            statement="项目材料中出现 X", passage_ids=["p_nonexistent"],
        )
    after = {key: value for key, value in store.counts().items() if key != "audit_log"}
    assert after == before


def test_claims_are_auditable_and_traceable(store, material):
    from evkg.attack import audit_store

    results = [
        adapter.create_material_claim(
            store,
            subject="MYtest 项目材料",
            predicate="包含",
            object=obj,
            statement=statement,
            passage_ids=passages,
            metadata={"growth_source_kind": "github_public_repo"},
        )
        for obj, statement, passages in (
            ("RAG 检索服务相关实现", "项目材料中出现 RAG 检索服务相关的实现内容", material["readme_passages"]),
            ("Java 服务端源码", "项目材料中出现 Java 类定义源码", material["code_passages"]),
            ("向量库依赖", "项目材料中出现 ChromaDB 向量库依赖描述", material["readme_passages"][:1]),
        )
    ]
    assert len({item["claim_id"] for item in results}) == 3

    report = audit_store(store.path)
    assert report["status"] == "pass" and report["total_violations"] == 0

    dossier = adapter.claim_dossier(store, results[0]["claim_id"])
    assert dossier is not None
    assert dossier["evidence"], "证据链不为空"
    for link in dossier["evidence"]:
        assert link["quote"] in link["passage_text"]  # claim → evidence → passage 逐字可回溯
        assert link["source"]["id"], "passage → source 可走通"
