"""M4-e：缺口 `g_gaps` —— 派生规则 / 唯一写路径 / 重建校验。

冻结口径（用户 2026-10-03）：

* 只表达「target - current + rubric 缺口」，不承担能力诊断 / 潜力判断 / 学习建议；
* 只从**已存在的评定行**派生（无评定 → 不产生缺口）；
* `insufficient_evidence` → `evidence_gap`（缺可核验证据，不判定为低能力）；
* `rated` 低于目标 → `level_gap_1`（差 1）/ `level_gap_2plus`（差 ≥2）；
* 唯一写路径 = `apply_gaps`；重算后不再成立的行置 `closed`（保留历史）。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from growth_os.assessment import AssessmentRater
from growth_os.evidence import adapter
from growth_os.store import GAP_SEVERITIES, GrowthStore, GrowthStoreError
from growth_os.store import growth_store as growth_store_module

GOAL_ID = "goal_m4e_gaps"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4e-gaps.db"
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
            {"goal_id": GOAL_ID, "path": "AI Agent", "name": "AI Agent", "depth": 1, "target_level": 3}
        )
        group = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "AI Agent/工具与执行",
                "name": "工具与执行",
                "depth": 2,
                "parent_id": domain,
                "target_level": 3,
            }
        )

        def add_capability(name: str, target_level: int = 3) -> str:
            return store.upsert_capability(
                {
                    "goal_id": GOAL_ID,
                    "path": f"AI Agent/工具与执行/{name}",
                    "name": name,
                    "depth": 3,
                    "parent_id": group,
                    "target_level": target_level,
                }
            )

        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "add_capability": add_capability,
            "tmp": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def add_claim(env, *, filename: str, content: str, evidence_type: str) -> str:
    target = env["tmp"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution="user_declared"
    )
    passage_ids = [item.id for item in env["estore"].get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        env["estore"],
        subject="材料",
        predicate="包含",
        object="相关内容",
        statement=f"材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
    )["claim_id"]


def bind(env, capability_id: str, claim_id: str) -> None:
    env["store"].link_capability_claim(
        capability_id, claim_id, role="supports", rationale="测试绑定（等价 M4-b 闸门写入）"
    )


def rate(env, capability_id: str) -> None:
    AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(
        capability_id=capability_id
    )


# ---------------------------------------------------------------------------
# 1. 派生规则
# ---------------------------------------------------------------------------


def test_insufficient_evidence_becomes_evidence_gap(env):
    cap = env["add_capability"]("证据不足", target_level=4)
    chat = add_claim(env, filename="e-chat.md", content="# 对话\n\n我熟悉 RAG。\n", evidence_type="chat_assertion")
    bind(env, cap, chat)
    rate(env, cap)

    gaps = env["store"].expected_gaps(cap)
    assert {item["dimension"] for item in gaps} == {"understanding", "practice"}
    for item in gaps:
        assert item["severity"] == "evidence_gap"
        assert item["current_level"] is None
        assert "证据不足，不判定为低能力" in item["rationale"]
        assert item["assessment_id"].startswith("asm_")


def test_level_gap_severity_by_distance(env):
    cap = env["add_capability"]("差距分级", target_level=4)
    notes = add_claim(env, filename="e-notes.md", content="# 笔记\n\nRAG 检索流程整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="e-repo.md", content="# 项目\n\n实现了 RAG 检索。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    rate(env, cap)

    gaps = {item["dimension"]: item for item in env["store"].expected_gaps(cap)}
    assert gaps["understanding"]["severity"] == "level_gap_2plus"  # 2 → 目标 4
    assert gaps["understanding"]["current_level"] == 2
    assert gaps["practice"]["severity"] == "level_gap_1"  # 3 → 目标 4
    assert gaps["practice"]["current_level"] == 3
    assert "目标 4 级" in gaps["practice"]["rationale"]


def test_no_gap_when_target_met(env):
    cap = env["add_capability"]("达标无缺口", target_level=3)
    notes = add_claim(env, filename="e-notes2.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="e-repo2.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    rate(env, cap)

    dimensions = {item["dimension"] for item in env["store"].expected_gaps(cap)}
    assert dimensions == {"understanding"}  # 实践 3 = 目标 3 → 无缺口；理解 2 < 3 → 有缺口


def test_no_assessment_no_gap(env):
    cap = env["add_capability"]("未评定")
    repo = add_claim(env, filename="e-repo3.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)

    assert env["store"].expected_gaps(cap) == []
    result = env["store"].apply_gaps(cap)
    assert result == {"gaps": [], "closed": []}
    assert env["store"].list_gaps(capability_id=cap) == []


def test_recompute_closes_stale_gap(env):
    cap = env["add_capability"]("重算关闭", target_level=3)
    notes = add_claim(env, filename="e-notes3.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    rate(env, cap)
    env["store"].apply_gaps(cap)
    before = {item["dimension"]: item["severity"] for item in env["store"].list_gaps(capability_id=cap)}
    assert before["practice"] == "evidence_gap"

    repo = add_claim(env, filename="e-repo4.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    rate(env, cap)
    result = env["store"].apply_gaps(cap)

    open_gaps = {item["dimension"]: item["severity"] for item in env["store"].list_gaps(capability_id=cap, status="open")}
    assert set(open_gaps) == {"understanding"}  # 实践 3 = 目标 3 → 缺口关闭
    closed = {item["dimension"] for item in env["store"].list_gaps(capability_id=cap, status="closed")}
    assert "practice" in closed
    assert result["closed"] == [f"gap_{cap}_practice"]


def test_verify_gaps_detects_tamper(env):
    cap = env["add_capability"]("篡改检测", target_level=4)
    notes = add_claim(env, filename="e-notes4.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    rate(env, cap)
    env["store"].apply_gaps(cap)
    assert env["store"].verify_gaps(cap)["consistent"] is True

    env["store"].db.execute(
        "UPDATE g_gaps SET severity='level_gap_1' WHERE capability_id=? AND dimension='understanding'",
        (cap,),
    )
    env["store"].db.commit()
    check = env["store"].verify_gaps(cap)
    assert check["consistent"] is False
    stored = {item["dimension"]: item for item in check["stored"]}
    assert stored["understanding"]["severity"] == "level_gap_1"


# ---------------------------------------------------------------------------
# 2. 措辞纪律（gap != recommendation）
# ---------------------------------------------------------------------------


def test_rationale_is_comparison_plus_rubric_gap_only(env):
    cap = env["add_capability"]("措辞纪律", target_level=5)
    notes = add_claim(env, filename="e-notes5.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    rate(env, cap)

    for item in env["store"].expected_gaps(cap):
        rationale = item["rationale"]
        for forbidden in ("建议", "推荐", "应该", "潜力", "学习计划", "提升到"):
            assert forbidden not in rationale, f"缺口措辞越界: {rationale}"
        assert "缺口：" in rationale, "必须携带 rubric.gaps 原文"


# ---------------------------------------------------------------------------
# 3. 唯一写路径 + 状态词表
# ---------------------------------------------------------------------------


def test_gaps_have_single_write_path():
    """AST 扫描：`INSERT INTO g_gaps` / `UPDATE g_gaps` 只允许出现在 apply_gaps 内。"""
    source = Path(growth_store_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    writers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        if "INSERT INTO g_gaps" in segment or "UPDATE g_gaps" in segment:
            writers.add(node.name)
    assert writers == {"apply_gaps"}, f"g_gaps 存在其他写入路径: {sorted(writers)}"


def test_gap_severity_vocabulary_is_frozen():
    assert GAP_SEVERITIES == ("evidence_gap", "level_gap_1", "level_gap_2plus")


def test_unknown_status_rejected(env):
    with pytest.raises(GrowthStoreError, match="未知缺口状态"):
        env["store"].list_gaps(status="done")


def test_gap_rows_carry_provenance(env):
    """缺口行必须能回到评定行（assessment_id + goal_id + user_id）。"""
    cap = env["add_capability"]("来源可回溯", target_level=4)
    chat = add_claim(env, filename="e-chat2.md", content="# 对话\n\n自述。\n", evidence_type="chat_assertion")
    bind(env, cap, chat)
    rate(env, cap)
    env["store"].apply_gaps(cap)

    for row in env["store"].list_gaps(capability_id=cap):
        assert row["goal_id"] == GOAL_ID
        assert row["user_id"] == "local"
        assessment = env["store"].get_assessment(row["assessment_id"])
        assert assessment is not None
        assert assessment["dimension"] == row["dimension"]
        assert json.loads(assessment["rubric_json"])["contract"]
