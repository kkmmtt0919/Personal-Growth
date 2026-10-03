"""M4-b：证据绑定（LLM 提议 + 确定性闸门 + 映射落库）——契约测试。

锁定用户 2026-10-02 冻结的边界：

* LLM **只提议**：proposal schema 仅 `claim_id` / `capability_path` / `rationale`，
  置信度/等级/分值字段一律进不来（`extra="forbid"`）；
* **确定性闸门八步固定顺序**，任何一步失败都不落库，且失败记录带
  `proposal_id` / `reject_reason` / `gate_stage` / `timestamp` / `run_id`；
* **LLM 输出没有直接落库路径**：桥表行数只可能等于通过闸门的提议数；
* 分桶映射确定性；`external_ref` 不入桶；幂等（重复提议 → duplicate 拒绝）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from growth_os.agent import FakeGateway
from growth_os.assessment import (
    BINDING_TASK,
    BUCKETS,
    BindingError,
    BindingGate,
    ClaimBinder,
    ProposalItem,
    bucket_for,
    build_binding_artifact,
    claim_buckets,
    write_binding_artifact,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from pydantic import ValidationError

GOAL_ID = "goal_m4b"


# ---------------------------------------------------------------------------
# 分桶映射
# ---------------------------------------------------------------------------


def test_bucket_mapping_is_explicit_and_fail_closed():
    assert bucket_for("uploaded_doc") == "knowledge"
    assert bucket_for("chat_assertion") == "knowledge"
    assert bucket_for("probe_result") == "behavior"
    assert bucket_for("repo_artifact") == "practice"
    assert bucket_for("task_submission") == "task"
    assert bucket_for("external_ref") is None, "领域参考不得作为用户证据进桶"
    assert bucket_for("unknown_type") is None
    assert bucket_for(None) is None
    assert set(BUCKETS) == {"knowledge", "behavior", "practice", "task"}


def test_claim_buckets_collects_and_flags_unmapped():
    def entry(evidence_type):
        return {
            "claim": {"id": "clm_x"},
            "evidence": [
                {
                    "passage_id": "p",
                    "source": {"id": "s", "metadata": {"growth_evidence_type": evidence_type}},
                }
            ],
        }

    assert claim_buckets(entry("repo_artifact")) == ({"practice"}, [])
    assert claim_buckets(entry("external_ref")) == (set(), ["external_ref"])
    assert claim_buckets({"claim": {"id": "clm_x"}, "evidence": []}) == (set(), ["evidence 缺失"])


# ---------------------------------------------------------------------------
# 测试环境：临时库（同一文件双表族）+ 一条可绑定材料 + 三个反面材料
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4b.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
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

        def add(path: str, depth: int, parent: str | None = None) -> str:
            return store.upsert_capability(
                {
                    "goal_id": GOAL_ID,
                    "path": path,
                    "name": path.split("/")[-1],
                    "depth": depth,
                    "parent_id": parent,
                    "target_level": 3,
                }
            )

        domain = add("LLM 基础", 1)
        group = add("LLM 基础/检索增强", 2, domain)
        cap_rag = add("LLM 基础/检索增强/RAG 实现", 3, group)
        group2 = add("LLM 基础/工程实践", 2, domain)
        cap_test = add("LLM 基础/工程实践/测试设计", 3, group2)
        paths = {
            "rag": "LLM 基础/检索增强/RAG 实现",
            "test": "LLM 基础/工程实践/测试设计",
        }

        def ingest(filename: str, content: str, **kwargs):
            target = tmp_path / filename
            target.write_text(content, encoding="utf-8")
            return adapter.ingest_document(target, store=estore, **kwargs)

        def material_claim(source, subject: str, statement: str) -> str:
            passage_ids = [item.id for item in estore.get_passages(source_id=source.source_id)]
            return adapter.create_material_claim(
                estore,
                subject=subject,
                predicate="包含",
                object="相关内容",
                statement=statement,
                passage_ids=passage_ids[:1],
            )["claim_id"]

        claim_ok = material_claim(
            ingest(
                "notes.md",
                "# 笔记\n\n项目实现了 RAG 检索服务与向量库集成。\n",
                evidence_type="uploaded_doc",
                attribution="user_declared",
            ),
            "项目材料",
            "项目材料中包含 RAG 检索实现相关内容",
        )
        claim_asserted = material_claim(
            ingest(
                "chat.md",
                "# 对话记录\n\n我说过我熟悉 RAG。\n",
                evidence_type="chat_assertion",
                attribution="user_asserted",
            ),
            "对话材料",
            "对话材料中包含用户熟悉 RAG 的自述",
        )
        claim_ref = material_claim(
            ingest(
                "jd.md",
                "# 岗位要求\n\n要求具备 RAG 工程经验。\n",
                evidence_type="external_ref",
                channel="domain_reference",
                attribution="user_declared",
            ),
            "岗位材料",
            "岗位材料中包含 RAG 工程经验要求",
        )
        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "caps": {"rag": cap_rag, "test": cap_test},
            "paths": paths,
            "claims": {"ok": claim_ok, "asserted": claim_asserted, "ref": claim_ref},
        }
    finally:
        estore.db.close()
        store.close()


def _proposal(env, path_key: str, claim_key: str = "ok") -> dict:
    return {
        "claim_id": env["claims"][claim_key],
        "capability_path": env["paths"][path_key],
        "rationale": "材料内容与该能力点直接相关",
    }


def _gate(env, candidates=None) -> BindingGate:
    return BindingGate(
        store=env["store"],
        evidence_store=env["estore"],
        goal_id=GOAL_ID,
        candidate_claim_ids=candidates
        if candidates is not None
        else list(env["claims"].values()),
    )


# ---------------------------------------------------------------------------
# 闸门八步：逐步拒绝对例 + 通过路径
# ---------------------------------------------------------------------------


def test_schema_stage_rejects_extra_evaluation_fields(env):
    """置信度/等级/分值字段出现在提议里 → schema 阶段拒绝（LLM 加不进来）。"""
    for extra in ({"confidence": 0.95}, {"level": "expert"}, {"score": 5}):
        decision = _gate(env).evaluate({**_proposal(env, "rag"), **extra}, run_id="run_test")
        assert not decision.accepted
        assert decision.gate_stage == "schema"
        assert "schema 不合法" in decision.reject_reason
        assert "not permitted" in decision.reject_reason


def test_schema_stage_rejects_missing_rationale(env):
    proposal = _proposal(env, "rag")
    proposal.pop("rationale")
    decision = _gate(env).evaluate(proposal, run_id="run_test")
    assert decision.gate_stage == "schema" and not decision.accepted


def test_claim_exists_stage(env):
    proposal = {**_proposal(env, "rag"), "claim_id": "clm_missing"}
    decision = _gate(env).evaluate(proposal, run_id="run_test")
    assert decision.gate_stage == "claim_exists"
    assert "不在证据库" in decision.reject_reason


def test_claim_outside_candidate_set_is_rejected(env):
    """提议越界（引用存在但不在本次候选集的主张）同样在 claim_exists 阶段拒绝。"""
    decision = _gate(env, candidates=[env["claims"]["ok"]]).evaluate(
        _proposal(env, "test", claim_key="asserted"), run_id="run_test"
    )
    assert decision.gate_stage == "claim_exists"
    assert "候选集" in decision.reject_reason


def test_capability_exists_stage(env):
    proposal = {**_proposal(env, "rag"), "capability_path": "不存在的/能力点/路径"}
    decision = _gate(env).evaluate(proposal, run_id="run_test")
    assert decision.gate_stage == "capability_exists"
    assert "目标树" in decision.reject_reason


def test_capability_active_stage(env):
    env["store"].set_capability_status(env["caps"]["test"], "superseded")
    decision = _gate(env).evaluate(_proposal(env, "test"), run_id="run_test")
    assert decision.gate_stage == "capability_active"
    assert "active" in decision.reject_reason


def test_bucket_allowed_stage(env):
    """external_ref（岗位要求）不入桶 —— 在归属复核之前就被拦下。"""
    decision = _gate(env).evaluate(_proposal(env, "rag", claim_key="ref"), run_id="run_test")
    assert decision.gate_stage == "bucket_allowed"
    assert "external_ref" in decision.reject_reason


def test_attribution_unchanged_stage(env):
    """user_asserted 的声明不能借 LLM 提议进入绑定。"""
    decision = _gate(env).evaluate(_proposal(env, "test", claim_key="asserted"), run_id="run_test")
    assert decision.gate_stage == "attribution_unchanged"
    assert "pending_declaration" in decision.reject_reason


def test_rejected_proposals_write_nothing(env):
    before = env["store"].list_capability_claims()
    _gate(env).evaluate({**_proposal(env, "rag"), "capability_path": "杜撰/路径"}, run_id="run_test")
    assert env["store"].list_capability_claims() == before


def test_accept_path_persists_with_full_reason(env):
    decision = _gate(env).evaluate(
        _proposal(env, "rag"), run_id="run_real_001", proposer="openai_compatible/glm-5.3-flash"
    )
    assert decision.accepted and decision.gate_stage == "persisted"
    assert decision.capability_id == env["caps"]["rag"]
    assert decision.stages_passed == (
        "schema",
        "claim_exists",
        "capability_exists",
        "capability_active",
        "bucket_allowed",
        "attribution_unchanged",
        "duplicate",
        "persisted",
    )
    links = env["store"].list_capability_claims(capability_id=env["caps"]["rag"])
    assert len(links) == 1
    note = links[0]["rationale"]
    assert "run_real_001" in note
    assert "openai_compatible/glm-5.3-flash" in note
    assert "理由：材料内容与该能力点直接相关" in note


def test_duplicate_stage_is_idempotent(env):
    gate = _gate(env)
    first = gate.evaluate(_proposal(env, "rag"), run_id="run_a")
    second = gate.evaluate(_proposal(env, "rag"), run_id="run_b")
    assert first.accepted and second.gate_stage == "duplicate" and not second.accepted
    assert len(env["store"].list_capability_claims(capability_id=env["caps"]["rag"])) == 1


# ---------------------------------------------------------------------------
# 提议 schema 本身：多一个字段都进不来
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra", [{"confidence": 0.95}, {"level": "expert"}, {"score": 5}])
def test_proposal_item_forbids_evaluation_fields(extra):
    with pytest.raises(ValidationError):
        ProposalItem.model_validate(
            {"claim_id": "clm_x", "capability_path": "a/b/c", "rationale": "r", **extra}
        )


# ---------------------------------------------------------------------------
# 离线闭环：FakeGateway → 提议 → 八步闸门 → 落库（LLM 无直接落库路径）
# ---------------------------------------------------------------------------


def _fake_payload(env) -> dict:
    return {
        "proposals": [
            _proposal(env, "rag"),  # 应通过
            {**_proposal(env, "rag"), "capability_path": "杜撰/路径/不存在"},  # 路径不存在
            _proposal(env, "test", claim_key="asserted"),  # 归属不通过
            _proposal(env, "rag", claim_key="ref"),  # 桶不通过
        ]
    }


def test_binder_offline_loop_gate_decides_everything(env):
    gateway = FakeGateway(
        responses={BINDING_TASK: [_fake_payload(env)]},
        provider="fake-provider",
        model="fake-model-x",
    )
    binder = ClaimBinder(
        store=env["store"],
        evidence_store=env["estore"],
        gateway=gateway,
        goal_id=GOAL_ID,
    )
    report = __import__("asyncio").run(binder.propose(list(env["claims"].values())))

    stages = sorted(decision["gate_stage"] for decision in report["decisions"])
    assert stages == ["attribution_unchanged", "bucket_allowed", "capability_exists", "persisted"]
    assert len(report["accepted"]) == 1 and len(report["rejected"]) == 3

    # LLM 输出没有直接落库路径：桥表行数 == 通过闸门的提议数
    links = env["store"].list_capability_claims()
    assert len(links) == 1 and links[0]["claim_id"] == env["claims"]["ok"]

    # 失败记录含用户指定的五个字段
    for decision in report["decisions"]:
        if decision["accepted"]:
            continue
        assert decision["proposal_id"].startswith("prp_")
        assert decision["reject_reason"] and decision["gate_stage"]
        assert decision["timestamp"] and decision["run_id"] == report["run_id"]

    # 运行记录：provider/model 取自实际返回值（C2）
    runs = env["store"].list_runs(agent="claim_binding")
    assert len(runs) == 1
    assert runs[0]["provider"] == "fake-provider" and runs[0]["model"] == "fake-model-x"
    assert runs[0]["model_source"] == "result" and runs[0]["status"] == "ok"

    # 产物形状 + 只读声明
    artifact = build_binding_artifact(report, mode="offline-fake", db_path=str(env["db"]))
    assert artifact["read_only"] is True
    assert artifact["accepted_count"] == 1 and artifact["rejected_count"] == 3
    assert len(artifact["proposals"]) == 4 and len(artifact["decisions"]) == 4


def test_binder_second_run_is_all_duplicates(env):
    gateway = FakeGateway(responses={BINDING_TASK: [_fake_payload(env), _fake_payload(env)]})
    binder = ClaimBinder(
        store=env["store"], evidence_store=env["estore"], gateway=gateway, goal_id=GOAL_ID
    )
    import asyncio

    first = asyncio.run(binder.propose(list(env["claims"].values())))
    second = asyncio.run(binder.propose(list(env["claims"].values())))
    assert len(first["accepted"]) == 1
    assert len(second["accepted"]) == 0
    duplicate = [d for d in second["decisions"] if d["gate_stage"] == "duplicate"]
    assert len(duplicate) == 1
    assert len(env["store"].list_capability_claims()) == 1


def test_binder_rejects_unknown_candidates_and_empty_tree(env):
    import asyncio

    binder = ClaimBinder(
        store=env["store"],
        evidence_store=env["estore"],
        gateway=FakeGateway(responses={BINDING_TASK: {"proposals": []}}),
        goal_id=GOAL_ID,
    )
    with pytest.raises(BindingError, match="未知 claim"):
        asyncio.run(binder.propose(["clm_missing"]))
    empty = ClaimBinder(
        store=env["store"],
        evidence_store=env["estore"],
        gateway=FakeGateway(responses={BINDING_TASK: {"proposals": []}}),
        goal_id="goal_without_tree",
    )
    with pytest.raises(BindingError, match="active"):
        asyncio.run(empty.propose([env["claims"]["ok"]]))


def test_write_binding_artifact(tmp_path, env):
    artifact = build_binding_artifact(
        {
            "run_id": "run_x",
            "provider": "p",
            "model": "m",
            "goal_id": GOAL_ID,
            "candidates": [],
            "proposals": [],
            "decisions": [],
            "accepted": [],
            "rejected": [],
        },
        mode="offline-fake",
        db_path=str(env["db"]),
    )
    target = write_binding_artifact(tmp_path / "out" / "binding.json", artifact)
    assert Path(target).is_file()
    assert '"read_only": true' in Path(target).read_text(encoding="utf-8")
