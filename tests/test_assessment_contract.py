"""M4-a：Assessment 基础模型与 provenance 前置 —— 契约测试。

锁定用户冻结的 `M4-PLAN.md` v1.0：

* **草案契约**：只允许 `draft` / `insufficient_evidence`，`level` 恒为 NULL（无星级算法）；
* **准入闸门（四类矩阵 + 越权）**：`user_declared + user_evidence + 完整链路` → 进入；
  `user_asserted` → 待验证声明；`domain_reference` → 不能支撑；计划 → 不是能力证据；
* **生命周期**：history + current view（superseded 不删除、`adjusted` 不自动降级）；
* **最小闭环**：claim/evidence → assessment draft → 独立 audit artifact（只读、零写回证据库）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from growth_os.assessment import (
    ADMISSIBLE,
    CHAIN_INCOMPLETE,
    CONTRACT_VERSION,
    DOMAIN_REFERENCE,
    NOT_ADMISSIBLE,
    OVERREACH,
    PENDING_DECLARATION,
    PLAN,
    AssessmentDrafter,
    AssessmentError,
    build_audit,
    classify_claim,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore, GrowthStoreError

GOAL_ID = "goal_m4a"


# ---------------------------------------------------------------------------
# 构造工具：纯字典 entry（不必开库即可测准入闸门）
# ---------------------------------------------------------------------------


def _entry(
    *,
    statement: str = "项目材料中包含 RAG 检索实现",
    quote: str = "项目材料中包含 RAG 检索实现",
    passage_text: str | None = None,
    scope: str | None = "material",
    channel: str | None = "user_evidence",
    attribution: str | None = "user_declared",
    subject: str = "项目材料",
    predicate: str = "包含",
    with_evidence: bool = True,
) -> dict:
    passages = quote if passage_text is None else passage_text
    metadata: dict = {}
    if channel is not None:
        metadata["growth_channel"] = channel
    if attribution is not None:
        metadata["growth_attribution"] = attribution
    evidence = []
    if with_evidence:
        evidence.append(
            {
                "id": "ev_1",
                "claim_id": "clm_x",
                "passage_id": "p_1",
                "polarity": "supports",
                "quote": quote,
                "passage_text": passages,
                "passage_ordinal": 0,
                "source": {"id": "src_1", "metadata": metadata},
                "source_assessment": {},
            }
        )
    claim_metadata = {"growth_claim_scope": scope} if scope is not None else {}
    return {
        "type": "claim",
        "claim": {
            "id": "clm_x",
            "subject": subject,
            "predicate": predicate,
            "object": "RAG 检索实现",
            "statement": statement,
            "metadata": claim_metadata,
        },
        "evidence": evidence,
    }


# ---------------------------------------------------------------------------
# 1. 准入闸门：四类矩阵 + 越权 + 链完整性（确定性、纯函数）
# ---------------------------------------------------------------------------


def test_full_chain_is_admissible():
    result = classify_claim(_entry())
    assert result.kind == ADMISSIBLE and result.admissible
    assert result.chain is not None and result.chain.complete
    assert result.chain.quote_verbatim is True


def test_missing_evidence_is_chain_incomplete():
    result = classify_claim(_entry(with_evidence=False))
    assert result.kind == CHAIN_INCOMPLETE and not result.admissible
    assert "evidence 缺失" in result.reasons[0]


def test_quote_must_be_verbatim():
    result = classify_claim(
        _entry(quote="另一段不相干的文字", passage_text="项目材料中包含 RAG 检索实现")
    )
    assert result.kind == CHAIN_INCOMPLETE
    assert result.chain is not None and result.chain.quote_verbatim is False


def test_domain_reference_cannot_support_user_claim():
    result = classify_claim(_entry(channel="domain_reference"))
    assert result.kind == DOMAIN_REFERENCE and not result.admissible


def test_user_asserted_is_pending_declaration():
    result = classify_claim(_entry(attribution="user_asserted"))
    assert result.kind == PENDING_DECLARATION and not result.admissible


def test_unknown_attribution_fails_closed():
    result = classify_claim(_entry(attribution=None))
    assert result.kind == NOT_ADMISSIBLE and not result.admissible


def test_overreach_claim_is_rejected():
    result = classify_claim(
        _entry(subject="用户", predicate="实现过", statement="用户实现过 RAG 检索服务")
    )
    assert result.kind == OVERREACH and not result.admissible


def test_plan_claim_is_not_capability_evidence():
    result = classify_claim(
        _entry(
            scope=None,
            subject="用户",
            predicate="计划学习",
            statement="原文「未来规划」列出 MCP 扩展等计划事项，不代表已具备相应能力。",
        )
    )
    assert result.kind == PLAN and not result.admissible


def test_non_material_user_claim_is_pending_declaration():
    result = classify_claim(
        _entry(scope=None, subject="用户", predicate="了解", statement="用户了解向量检索概念")
    )
    assert result.kind == PENDING_DECLARATION


# ---------------------------------------------------------------------------
# 2. 存储契约：草案不变式 / 稳定 id / 桥表 / 生命周期
# ---------------------------------------------------------------------------


@pytest.fixture()
def gstore(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "m4a.db"))
    yield store
    store.close()


def _confirm_goal(store: GrowthStore) -> None:
    store.upsert_user("local", "本地用户")
    store.save_goal(
        {
            "id": GOAL_ID,
            "user_id": "local",
            "title": "成为 AI Agent 工程师",
            "direction": "AI 应用方向",
            "purpose": "求职",
            "horizon": "6 个月",
            "measurable_result": "完成一个可演示的 RAG 项目",
            "status": "confirmed",
            "source_quote": "我想成为 AI Agent 工程师",
        }
    )


def _add_capability(store: GrowthStore, path: str, depth: int, parent_id: str | None = None) -> str:
    return store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": path,
            "name": path.split("/")[-1],
            "depth": depth,
            "parent_id": parent_id,
            "target_level": 3,
        }
    )


def test_draft_forbids_level_and_unknown_status(gstore):
    _confirm_goal(gstore)
    capability = _add_capability(gstore, "LLM 基础", 1)
    base = {
        "goal_id": GOAL_ID,
        "capability_id": capability,
        "status": "draft",
        "rationale": "测试草案",
    }
    with pytest.raises(GrowthStoreError, match="星级"):
        gstore.save_assessment_draft({**base, "level": 3})
    with pytest.raises(GrowthStoreError, match="状态"):
        gstore.save_assessment_draft({**base, "status": "final"})
    with pytest.raises(GrowthStoreError, match="rationale"):
        gstore.save_assessment_draft({**base, "rationale": "  "})


def test_draft_requires_matching_capability_and_goal(gstore):
    _confirm_goal(gstore)
    capability = _add_capability(gstore, "LLM 基础", 1)
    with pytest.raises(GrowthStoreError, match="未知能力点"):
        gstore.save_assessment_draft(
            {"capability_id": "cap_missing", "status": "draft", "rationale": "x"}
        )
    with pytest.raises(GrowthStoreError, match="goal_id"):
        gstore.save_assessment_draft(
            {
                "goal_id": "goal_other",
                "capability_id": capability,
                "status": "draft",
                "rationale": "x",
            }
        )


def test_assessment_id_is_stable_and_evidence_scoped(gstore):
    _confirm_goal(gstore)
    capability = _add_capability(gstore, "LLM 基础", 1)
    base = {
        "goal_id": GOAL_ID,
        "capability_id": capability,
        "status": "draft",
        "rationale": "测试",
    }
    first = gstore.save_assessment_draft({**base, "claim_ids": ["clm_1"]})
    again = gstore.save_assessment_draft({**base, "claim_ids": ["clm_1"]})
    other = gstore.save_assessment_draft({**base, "claim_ids": ["clm_1", "clm_2"]})
    assert first == again, "同一证据集重复运行必须命中同一行（幂等）"
    assert other != first, "证据集变化 = 新的草案（历史保留）"
    assert len(gstore.list_assessments(capability_id=capability)) == 2


def test_bridge_requires_role_rationale_and_capability(gstore):
    _confirm_goal(gstore)
    capability = _add_capability(gstore, "LLM 基础", 1)
    with pytest.raises(GrowthStoreError, match="角色"):
        gstore.link_capability_claim(capability, "clm_1", role="maybe", rationale="x")
    with pytest.raises(GrowthStoreError, match="rationale"):
        gstore.link_capability_claim(capability, "clm_1", rationale="  ")
    with pytest.raises(GrowthStoreError, match="未知能力点"):
        gstore.link_capability_claim("cap_missing", "clm_1", rationale="x")
    gstore.link_capability_claim(capability, "clm_1", rationale="确定性准入通过")
    links = gstore.list_capability_claims(capability_id=capability)
    assert len(links) == 1 and links[0]["claim_id"] == "clm_1"


def test_supersede_missing_keeps_history_and_adjusted(gstore):
    _confirm_goal(gstore)
    keep = _add_capability(gstore, "领域A", 1)
    stale = _add_capability(gstore, "领域B", 1)
    adjusted = _add_capability(gstore, "领域C", 1)
    gstore.adjust_capability(adjusted, 5, "用户上调：这是当前重点")

    marked = gstore.supersede_missing(GOAL_ID, [keep], generation_id="gen_2")

    assert stale in marked and keep not in marked and adjusted not in marked
    active = {row["id"] for row in gstore.list_capabilities(GOAL_ID, status="active")}
    assert keep in active and adjusted in active and stale not in active
    # 不删除历史：superseded 行仍在，只是不再出现在当前视图
    assert gstore.get_capability(stale)["status"] == "superseded"
    assert gstore.get_capability(stale)["generation_id"] == "gen_2"
    everything = {row["id"] for row in gstore.list_capabilities(GOAL_ID)}
    assert {keep, stale, adjusted} <= everything


def test_existing_db_gets_lifecycle_columns(tmp_path):
    """旧库（无生命周期列）打开时补列，且旧行默认 active、不被动过。"""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE g_capabilities (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL,"
        " parent_id TEXT, name TEXT NOT NULL, path TEXT NOT NULL, depth INTEGER NOT NULL,"
        " target_level INTEGER, origin TEXT NOT NULL DEFAULT 'generated',"
        " verification_status TEXT NOT NULL DEFAULT 'unverified', source_note TEXT,"
        " adjustment_note TEXT, generated_by_run_id TEXT, current_level INTEGER,"
        " current_level_status TEXT NOT NULL DEFAULT 'unassessed', weight REAL,"
        " created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        " updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(goal_id, path))"
    )
    conn.execute(
        "INSERT INTO g_capabilities(id, goal_id, name, path, depth) "
        "VALUES('cap_old','g','旧节点','旧节点',1)"
    )
    conn.commit()
    conn.close()

    store = GrowthStore(str(path))
    try:
        row = store.get_capability("cap_old")
        assert row["status"] == "active" and row["generation_id"] is None
    finally:
        store.close()


def test_counts_include_assessment_tables(gstore):
    counts = gstore.counts()
    assert {"g_capability_claims", "g_assessments"} <= set(counts)
    assert counts["g_assessments"] == 0


# ---------------------------------------------------------------------------
# 3. 最小闭环：claim/evidence → draft → audit artifact（零写回证据库）
# ---------------------------------------------------------------------------


@pytest.fixture()
def loop(tmp_path: Path):
    """临时库里造：confirmed goal + 两条能力链 + 两份材料（declared / asserted）。"""
    db = tmp_path / "m4a.db"
    gstore = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
        _confirm_goal(gstore)
        domain = _add_capability(gstore, "LLM 基础", 1)
        group_a = _add_capability(gstore, "LLM 基础/检索增强", 2, domain)
        cap_a = _add_capability(gstore, "LLM 基础/检索增强/RAG 实现", 3, group_a)
        group_b = _add_capability(gstore, "LLM 基础/工程实践", 2, domain)
        cap_b = _add_capability(gstore, "LLM 基础/工程实践/测试设计", 3, group_b)

        material = tmp_path / "notes.md"
        material.write_text(
            "# 笔记\n\n项目实现了 RAG 检索服务与向量库集成。\n", encoding="utf-8"
        )
        declared = adapter.ingest_document(
            material,
            store=estore,
            evidence_type="uploaded_doc",
            attribution="user_declared",
        )
        declared_passages = [
            item.id for item in estore.get_passages(source_id=declared.source_id)
        ]
        claim_a = adapter.create_material_claim(
            estore,
            subject="项目材料",
            predicate="包含",
            object="RAG 检索实现",
            statement="项目材料中包含 RAG 检索实现相关内容",
            passage_ids=declared_passages[:1],
        )

        chat = tmp_path / "chat.md"
        chat.write_text("# 对话记录\n\n我说过我熟悉 RAG。\n", encoding="utf-8")
        asserted = adapter.ingest_document(
            chat,
            store=estore,
            evidence_type="chat_assertion",
            attribution="user_asserted",
        )
        asserted_passages = [
            item.id for item in estore.get_passages(source_id=asserted.source_id)
        ]
        claim_b = adapter.create_material_claim(
            estore,
            subject="对话材料",
            predicate="包含",
            object="RAG 自述",
            statement="对话材料中包含用户熟悉 RAG 的自述",
            passage_ids=asserted_passages[:1],
        )
        yield {
            "db": db,
            "gstore": gstore,
            "estore": estore,
            "cap_a": cap_a,
            "cap_b": cap_b,
            "claim_a": claim_a["claim_id"],
            "claim_b": claim_b["claim_id"],
            "assessments": [],
        }
    finally:
        estore.db.close()
        gstore.close()


def test_minimal_loop_draft_and_audit(loop):
    gstore, estore = loop["gstore"], loop["estore"]
    drafter = AssessmentDrafter(store=gstore, evidence_store=estore)

    before = estore.counts()
    draft_a = drafter.draft(capability_id=loop["cap_a"], claim_ids=[loop["claim_a"]])
    draft_b = drafter.draft(capability_id=loop["cap_b"], claim_ids=[loop["claim_b"]])
    artifact = build_audit(gstore, estore, db_path=str(loop["db"]))
    after = estore.counts()

    # ① 状态语义：有可准入证据 → draft；只有待验证声明 → evidence insufficient
    assert draft_a["status"] == "draft" and draft_a["level"] is None
    assert draft_a["supports"] == [loop["claim_a"]]
    assert draft_b["status"] == "insufficient_evidence" and draft_b["level"] is None
    assert draft_b["excluded"][0]["kind"] == PENDING_DECLARATION

    # ② 桥表只写通过准入的绑定
    links = gstore.list_capability_claims(capability_id=loop["cap_a"])
    assert [link["claim_id"] for link in links] == [loop["claim_a"]]

    # ③ 幂等：重复运行命中同一行
    again = drafter.draft(capability_id=loop["cap_a"], claim_ids=[loop["claim_a"]])
    assert again["assessment_id"] == draft_a["assessment_id"]
    assert len(gstore.list_assessments(capability_id=loop["cap_a"])) == 1

    # ④ 评估层零写入证据库
    assert after == before, "起草与审计不得向证据库写入任何一行"

    # ⑤ 独立 audit artifact：只读、逐跳可追溯、provenance 如实
    assert artifact["read_only"] is True and artifact["mutated_evidence_store"] is False
    assert artifact["contract"] == CONTRACT_VERSION
    by_id = {item["assessment_id"]: item for item in artifact["assessments"]}
    entry_a = by_id[draft_a["assessment_id"]]
    assert entry_a["status"] == "draft" and entry_a["level"] is None
    support = entry_a["supports"][0]
    assert support["classification"] == ADMISSIBLE
    assert support["chain"]["complete"] is True and support["chain"]["quote_verbatim"] is True
    assert support["provenance"]["recorded"] is False
    assert "不适用" in support["provenance"]["note"]
    scan = {item["claim_id"]: item for item in artifact["claims_scan"]}
    assert scan[loop["claim_a"]]["classification"] == ADMISSIBLE
    assert scan[loop["claim_b"]]["classification"] == PENDING_DECLARATION


def test_draft_rejects_unknown_claim_and_inactive_capability(loop):
    gstore, estore = loop["gstore"], loop["estore"]
    drafter = AssessmentDrafter(store=gstore, evidence_store=estore)
    with pytest.raises(AssessmentError, match="未知 claim"):
        drafter.draft(capability_id=loop["cap_a"], claim_ids=["clm_missing"])
    gstore.set_capability_status(loop["cap_a"], "superseded")
    with pytest.raises(AssessmentError, match="active"):
        drafter.draft(capability_id=loop["cap_a"], claim_ids=[])


def test_audit_reads_recorded_extractor_provenance(loop):
    """C5 的读取侧：库里记了抽取 provenance，audit artifact 必须显示它。"""
    from evkg.domain import Claim, ClaimStatus, Confidence, EvidenceLink, Polarity

    gstore, estore = loop["gstore"], loop["estore"]
    passage = estore.get_passages()[0]
    claim_id = "clm_with_extractor"
    estore.save_claim(
        Claim(
            id=claim_id,
            subject="项目材料",
            predicate="包含",
            object="检索实现",
            statement="项目材料中包含检索实现",
            status=ClaimStatus.EXTRACTED,
            confidence=Confidence(
                score=None,
                source_reliability=None,
                extraction_quality=0.5,
                resolution_quality=0.0,
                corroboration=0.0,
                contradiction_penalty=0.0,
                assessment_status="unassessed",
                rationale="测试",
            ),
            passage_ids=[passage.id],
            metadata={
                "extractor_provider": "openai_compatible",
                "extractor_model": "glm-5.3-flash",
                "extractor_prompt_hash": "abc123def4567890",
                "extractor_profile": "growth_os",
            },
        )
    )
    estore.save_evidence(
        EvidenceLink(
            id="ev_extractor",
            claim_id=claim_id,
            passage_id=passage.id,
            polarity=Polarity.SUPPORTS,
            quote=passage.text,
            reasoning="测试",
            confidence=None,
        )
    )

    artifact = build_audit(gstore, estore, db_path=str(loop["db"]))
    scan = {item["claim_id"]: item for item in artifact["claims_scan"]}
    provenance = scan[claim_id]["provenance"]
    assert provenance == {
        "recorded": True,
        "provider": "openai_compatible",
        "model": "glm-5.3-flash",
        "prompt_hash": "abc123def4567890",
        "profile": "growth_os",
    }
