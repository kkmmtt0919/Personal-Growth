"""M4-c：评级与反向证据 —— QG3 决定性用例（`ACCEPTANCE_GATES.md` QG3）。

按用户 2026-10-03 冻结的口径与验收序组织：

1. **deterministic rule tests**：理解 / 实践两条阶梯；
2. **reverse evidence cases**：`broken` 剔除、`refutes` / `disputed` ≤2、`weakened` ≤3，
   且**封顶只作用于对应维度**（不跨维度污染）；
3. **no-evidence case**：无证据 → `insufficient_evidence`，不是低星；
4. **same-input same-output**：规则引擎无时间戳、无随机性，重复运行逐字段一致；
5. **confidence isolation**：定级不读主张的分级分数（功能对例 + 源码静态检查）。

另含写入路径契约：`rated` 校验、维度化、草案不被覆盖、等级变化产生新行（历史保留）。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from growth_os.assessment import (
    DIMENSIONS,
    INSUFFICIENT,
    PRACTICE,
    PRACTICE_SIGNAL_KEY,
    RATED,
    REVERSE_CAPS,
    RULES_CONTRACT_VERSION,
    UNDERSTANDING,
    AssessmentRater,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

GOAL_ID = "goal_m4c"


# ---------------------------------------------------------------------------
# 环境：goal + 三层树（可扩展的叶子节点）+ 材料/主张/绑定/注入辅助
# ---------------------------------------------------------------------------


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4c.db"
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
        domain = store.upsert_capability(
            {"goal_id": GOAL_ID, "path": "LLM 基础", "name": "LLM 基础", "depth": 1, "target_level": 3}
        )
        group = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "LLM 基础/检索增强",
                "name": "检索增强",
                "depth": 2,
                "parent_id": domain,
                "target_level": 3,
            }
        )

        def add_capability(name: str) -> str:
            return store.upsert_capability(
                {
                    "goal_id": GOAL_ID,
                    "path": f"LLM 基础/检索增强/{name}",
                    "name": name,
                    "depth": 3,
                    "parent_id": group,
                    "target_level": 3,
                }
            )

        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "add_capability": add_capability,
            "tmp_path": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def add_claim(env, *, filename: str, content: str, evidence_type: str, metadata: dict | None = None) -> str:
    """造一条材料口径主张（user_declared + user_evidence）。"""
    target = env["tmp_path"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution="user_declared"
    )
    passage_ids = [item.id for item in env["estore"].get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        env["estore"],
        subject="项目材料",
        predicate="包含",
        object="相关内容",
        statement=f"项目材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
        metadata=metadata,
    )["claim_id"]


def bind(env, capability_id: str, claim_id: str) -> None:
    env["store"].link_capability_claim(
        capability_id, claim_id, role="supports", rationale="测试绑定（经闸门路径的等价写入）"
    )


def latest(env, capability_id: str, dimension: str) -> dict:
    row = env["store"].latest_assessment(capability_id, dimension)
    assert row is not None, f"{capability_id}/{dimension} 应有评定行"
    return row


def inject_attack(env, claim_id: str, verdict: str) -> None:
    """注入式反例（不调用真实攻击模型；M4-c 只验证已存在裁决如何影响评级）。

    `attack_reports` 由攻击模块私有创建，测试夹具沿用既有先例（test_dossier）直接建表 + 造行。
    """
    env["estore"].db.execute(
        "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    payload = {
        "probe": {"target_claim_id": claim_id, "angle": "注入式测试", "question": "注入式测试质疑"},
        "verdict": {
            "target_claim_id": claim_id,
            "verdict": verdict,
            "reasoning": "注入式反例（测试）",
            "missing_evidence": [],
        },
    }
    env["estore"].db.execute(
        "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
        (f"rep_{claim_id}_{verdict}", "t_m4c", "adversarial", claim_id, json.dumps(payload, ensure_ascii=False)),
    )
    env["estore"].db.commit()


def add_crafted_claim(
    env,
    *,
    claim_id: str,
    passage_id: str,
    quote: str,
    score: float | None = None,
    status: str = "evidence_linked",
) -> None:
    """用 evkg 类型直接造主张（用于注入分数 / 状态等反例）。"""
    from evkg.domain import Claim, ClaimStatus, Confidence, EvidenceLink, Polarity

    env["estore"].save_claim(
        Claim(
            id=claim_id,
            subject="项目材料",
            predicate="包含",
            object="相关内容",
            statement="项目材料中包含相关内容（注入式）",
            status=ClaimStatus(status),
            confidence=Confidence(
                score=score,
                source_reliability=None,
                extraction_quality=1.0,
                resolution_quality=0.0,
                corroboration=0.0,
                contradiction_penalty=0.0,
                assessment_status="unassessed",
                rationale="测试用",
            ),
            passage_ids=[passage_id],
            metadata={"growth_claim_scope": "material"},
        )
    )
    env["estore"].save_evidence(
        EvidenceLink(
            id=f"ev_{claim_id}",
            claim_id=claim_id,
            passage_id=passage_id,
            polarity=Polarity.SUPPORTS,
            quote=quote,
            reasoning="测试用",
            confidence=score,
        )
    )


def add_refuting_evidence(env, claim_id: str) -> None:
    """给一条既有主张追加一条 `refutes` 证据行（反向证据挂在被质疑的主张上）。"""
    from evkg.domain import EvidenceLink, Polarity

    claim = next(item for item in env["estore"].get_claims() if item.id == claim_id)
    passage_id = claim.passage_ids[0]
    passage = next(item for item in env["estore"].get_passages() if item.id == passage_id)
    env["estore"].save_evidence(
        EvidenceLink(
            id=f"evr_{claim_id}",
            claim_id=claim_id,
            passage_id=passage_id,
            polarity=Polarity.REFUTES,
            quote=passage.text,
            reasoning="注入式反向证据",
            confidence=None,
        )
    )


def first_passage(env, evidence_type: str, filename: str, content: str) -> tuple[str, str]:
    """入库一份材料并返回 (passage_id, quote)。"""
    target = env["tmp_path"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution="user_declared"
    )
    passage = env["estore"].get_passages(source_id=ingested.source_id)[0]
    return passage.id, passage.text


def rater(env) -> AssessmentRater:
    return AssessmentRater(store=env["store"], evidence_store=env["estore"])


# ---------------------------------------------------------------------------
# 1. deterministic rule tests：两条阶梯
# ---------------------------------------------------------------------------


def test_understanding_ladder(env):
    cap = env["add_capability"]("RAG 实现")
    chat = add_claim(env, filename="chat.md", content="# 对话\n\n我熟悉 RAG。\n", evidence_type="chat_assertion")
    bind(env, cap, chat)

    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][UNDERSTANDING]["status"] == INSUFFICIENT
    assert report["dimensions"][UNDERSTANDING]["level"] is None, "自述不能单独产生等级"

    notes = add_claim(env, filename="notes.md", content="# 笔记\n\nRAG 检索流程整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][UNDERSTANDING]["level"] == 2

    probe = add_claim(env, filename="probe.md", content="# 现场作答\n\n能够解释重排序的作用。\n", evidence_type="probe_result")
    bind(env, cap, probe)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][UNDERSTANDING]["level"] == 3

    # 实践维度始终没有实践证据
    assert report["dimensions"][PRACTICE]["status"] == INSUFFICIENT
    assert report["dimensions"][PRACTICE]["level"] is None


def test_practice_ladder(env):
    cap = env["add_capability"]("实践阶梯")
    notes = add_claim(env, filename="p-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["status"] == INSUFFICIENT, "笔记不抬高实践"

    repo = add_claim(env, filename="repo.md", content="# 项目\n\n实现了检索服务。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 3

    task = add_claim(env, filename="task.md", content="# 任务交付\n\n独立完成评测集。\n", evidence_type="task_submission")
    bind(env, cap, task)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 4

    signal = add_claim(
        env,
        filename="task-opt.md",
        content="# 任务交付\n\n召回率 65%→92% 的优化对照。\n",
        evidence_type="task_submission",
        metadata={PRACTICE_SIGNAL_KEY: "optimization"},
    )
    bind(env, cap, signal)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 5, "显式优化信号才可到 5"
    assert any(
        "optimization" in support["signals"]
        for support in report["dimensions"][PRACTICE]["rubric"]["supports"]
    )


def test_level5_is_not_derivable_without_signal(env):
    cap = env["add_capability"]("无信号")
    repo = add_claim(env, filename="repo2.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    task = add_claim(env, filename="task2.md", content="# 任务\n\n完成。\n", evidence_type="task_submission")
    bind(env, cap, repo)
    bind(env, cap, task)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 4, "没有显式信号不得推导到 5"


def test_signal_without_practice_evidence_does_not_create_practice(env):
    cap = env["add_capability"]("信号无载体")
    notes = add_claim(
        env,
        filename="sig-notes.md",
        content="# 笔记\n\n优化思路整理。\n",
        evidence_type="uploaded_doc",
        metadata={PRACTICE_SIGNAL_KEY: "optimization"},
    )
    bind(env, cap, notes)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["status"] == INSUFFICIENT, "知识材料上的信号不制造实践证据"
    assert report["dimensions"][UNDERSTANDING]["level"] == 2


def test_dimensions_are_independent(env):
    cap = env["add_capability"]("维度独立")
    notes = add_claim(env, filename="iso-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="iso-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][UNDERSTANDING]["level"] == 2
    assert report["dimensions"][PRACTICE]["level"] == 3


# ---------------------------------------------------------------------------
# 2. reverse evidence cases
# ---------------------------------------------------------------------------


def test_broken_excludes_claim_and_falls_back(env):
    cap = env["add_capability"]("broken")
    repo = add_claim(env, filename="br-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    assert rater(env).rate(capability_id=cap)["dimensions"][PRACTICE]["level"] == 3

    inject_attack(env, repo, "broken")
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["status"] == INSUFFICIENT, "broken 的主张不计入"
    assert any("broken" in item["reason"] for item in report["dimensions"][PRACTICE]["rubric"]["excluded"])
    # 历史保留：旧 rated 行仍在，当前视图是 insufficient
    rows = env["store"].list_assessments(capability_id=cap, dimension=PRACTICE)
    assert {row["status"] for row in rows} == {RATED, INSUFFICIENT}
    assert latest(env, cap, PRACTICE)["status"] == INSUFFICIENT


def test_refutes_caps_practice_at_two_and_does_not_touch_understanding(env):
    cap = env["add_capability"]("refutes")
    notes = add_claim(env, filename="rf-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    passage_id, quote = first_passage(env, "repo_artifact", "rf-repo.md", "# 项目\n\n实现。\n")
    add_crafted_claim(env, claim_id="clm_rf_repo", passage_id=passage_id, quote=quote)
    add_refuting_evidence(env, "clm_rf_repo")
    bind(env, cap, notes)
    bind(env, cap, "clm_rf_repo")

    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == REVERSE_CAPS["refutes"] == 2
    assert report["dimensions"][UNDERSTANDING]["level"] == 2, "理解维度不被实践侧的反向证据污染"


def test_disputed_status_caps_at_two(env):
    cap = env["add_capability"]("disputed")
    passage_id, quote = first_passage(env, "repo_artifact", "dp-repo.md", "# 项目\n\n实现。\n")
    add_crafted_claim(
        env, claim_id="clm_dp_repo", passage_id=passage_id, quote=quote, status="disputed"
    )
    bind(env, cap, "clm_dp_repo")
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 2


def test_weakened_caps_at_three(env):
    cap = env["add_capability"]("weakened")
    task = add_claim(env, filename="wk-task.md", content="# 任务\n\n完成。\n", evidence_type="task_submission")
    bind(env, cap, task)
    assert rater(env).rate(capability_id=cap)["dimensions"][PRACTICE]["level"] == 4
    inject_attack(env, task, "weakened")
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == REVERSE_CAPS["weakened"] == 3


def test_cap_below_base_only(env):
    """封顶高于基线时不改变结果，但必须如实记录在 rubric 里。"""
    cap = env["add_capability"]("cap-noop")
    repo = add_claim(env, filename="nn-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    inject_attack(env, repo, "weakened")  # 封顶 3 == 基线 3
    report = rater(env).rate(capability_id=cap)
    assert report["dimensions"][PRACTICE]["level"] == 3
    assert report["dimensions"][PRACTICE]["rubric"]["reverse_evidence"], "封顶记录必须留档"


def test_sustained_verdict_changes_nothing(env):
    cap = env["add_capability"]("sustained")
    repo = add_claim(env, filename="st-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    inject_attack(env, repo, "sustained")
    assert rater(env).rate(capability_id=cap)["dimensions"][PRACTICE]["level"] == 3


# ---------------------------------------------------------------------------
# 3. no-evidence case
# ---------------------------------------------------------------------------


def test_no_evidence_gives_insufficient_not_low_star(env):
    cap = env["add_capability"]("空能力点")
    report = rater(env).rate(capability_id=cap)
    for dimension in DIMENSIONS:
        body = report["dimensions"][dimension]
        assert body["status"] == INSUFFICIENT and body["level"] is None
        assert "证据不足" in body["rationale"]
    for dimension in DIMENSIONS:
        row = latest(env, cap, dimension)
        assert row["status"] == INSUFFICIENT and row["level"] is None


# ---------------------------------------------------------------------------
# 4. same-input same-output
# ---------------------------------------------------------------------------


def test_same_input_same_output(env):
    cap = env["add_capability"]("确定性")
    notes = add_claim(env, filename="det-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="det-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    first = rater(env).rate(capability_id=cap)
    second = rater(env).rate(capability_id=cap)
    assert first == second, "规则引擎无时间戳、无随机性；重复运行必须逐字段一致"
    assert first["contract"] == RULES_CONTRACT_VERSION
    # 幂等：重复运行不新增行
    assert len(env["store"].list_assessments(capability_id=cap, dimension=UNDERSTANDING)) == 1
    assert len(env["store"].list_assessments(capability_id=cap, dimension=PRACTICE)) == 1


# ---------------------------------------------------------------------------
# 5. confidence isolation
# ---------------------------------------------------------------------------


def test_rating_ignores_claim_scores(env):
    cap = env["add_capability"]("分数隔离")
    passage_id, quote = first_passage(env, "repo_artifact", "ci-repo.md", "# 项目\n\n实现。\n")
    add_crafted_claim(env, claim_id="clm_ci_hi", passage_id=passage_id, quote=quote, score=0.99)
    bind(env, cap, "clm_ci_hi")
    high = rater(env).rate(capability_id=cap)["dimensions"][PRACTICE]

    other = env["add_capability"]("分数隔离低")
    passage_id2, quote2 = first_passage(env, "repo_artifact", "ci-repo2.md", "# 项目\n\n实现。\n")
    add_crafted_claim(env, claim_id="clm_ci_lo", passage_id=passage_id2, quote=quote2, score=0.05)
    bind(env, other, "clm_ci_lo")
    low = rater(env).rate(capability_id=other)["dimensions"][PRACTICE]

    assert high["level"] == low["level"] == 3, "定级与主张分数无关（D6）"

    def structure(rubric: dict) -> list[dict]:
        return [
            {key: value for key, value in support.items() if key != "claim_id"}
            for support in rubric["supports"]
        ]

    assert structure(high["rubric"]) == structure(low["rubric"])


def test_rules_source_does_not_touch_confidence():
    """静态检查：规则引擎源码中不得出现对分级分数的访问。"""
    source = (Path(__file__).resolve().parents[1] / "backend/growth_os/assessment/rules.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "confidence":
            offenders.append(node.attr)
        if isinstance(node, ast.Name) and node.id == "confidence":
            offenders.append(node.id)
    assert offenders == [], f"规则引擎不得读取分级分数：{offenders}"


# ---------------------------------------------------------------------------
# 写入路径契约：rated 校验 / 草案不被覆盖 / 等级变化产生新行
# ---------------------------------------------------------------------------


def test_rated_write_path_validations(env):
    from growth_os.store import GrowthStoreError

    cap = env["add_capability"]("校验")
    base = {
        "goal_id": GOAL_ID,
        "capability_id": cap,
        "dimension": UNDERSTANDING,
        "status": RATED,
        "level": 2,
        "rubric": {"contract": RULES_CONTRACT_VERSION},
        "rationale": "测试",
    }
    env["store"].save_assessment(base)
    with pytest.raises(GrowthStoreError, match="维度"):
        env["store"].save_assessment({**base, "dimension": "综合"})
    with pytest.raises(GrowthStoreError, match="rated"):
        env["store"].save_assessment({**base, "level": None})
    with pytest.raises(GrowthStoreError, match="rated"):
        env["store"].save_assessment({**base, "level": 6})
    with pytest.raises(GrowthStoreError, match="level"):
        env["store"].save_assessment({**base, "status": INSUFFICIENT, "level": 2})
    with pytest.raises(GrowthStoreError, match="rubric"):
        env["store"].save_assessment({**base, "rubric": {}})
    with pytest.raises(GrowthStoreError, match="rationale"):
        env["store"].save_assessment({**base, "rationale": " "})


def test_rating_does_not_overwrite_draft_and_level_change_creates_new_row(env):
    from growth_os.assessment import AssessmentDrafter

    cap = env["add_capability"]("历史语义")
    repo = add_claim(env, filename="hist-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)

    draft = AssessmentDrafter(store=env["store"], evidence_store=env["estore"]).draft(
        capability_id=cap, claim_ids=[repo]
    )
    rater(env).rate(capability_id=cap)
    assert env["store"].get_assessment(draft["assessment_id"])["status"] == "draft", "草案不被覆盖"

    first_row = latest(env, cap, PRACTICE)
    inject_attack(env, repo, "broken")
    rater(env).rate(capability_id=cap)
    rows = env["store"].list_assessments(capability_id=cap, dimension=PRACTICE)
    assert len(rows) == 2, "等级变化产生新行（历史保留）"
    assert latest(env, cap, PRACTICE)["id"] != first_row["id"]
    by_status = {row["status"]: row for row in rows}
    assert set(by_status) == {RATED, INSUFFICIENT}
    assert by_status[RATED]["level"] == 3 and by_status[INSUFFICIENT]["level"] is None
    assert latest(env, cap, PRACTICE)["status"] == INSUFFICIENT


def test_audit_store_passes_after_rating(env):
    cap = env["add_capability"]("审计")
    repo = add_claim(env, filename="audit-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    rater(env).rate(capability_id=cap)
    result = adapter.audit(env["db"])
    assert result["status"] == "pass" and result["total_violations"] == 0
