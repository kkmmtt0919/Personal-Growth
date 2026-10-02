"""M2-a：`g_` 表族存储的语义测试。

这些用例锁定 `M2-PLAN.md` §3.1 的三条数据语义，它们是后续步骤（M2-b/c）
与验收项 AC4/AC5/AC10 的地基：

1. 稳定逻辑标识（再生成不累积）；
2. 人工调整受保护（C1）；
3. 未评估 ≠ 低等级（决定 5）。
"""

from __future__ import annotations

import pytest
from growth_os.store import GrowthStore, GrowthStoreError, capability_id


def _confirmed_goal(goal_id: str = "goal_1") -> dict:
    return {
        "id": goal_id,
        "user_id": "local",
        "title": "六个月内达到 AI 应用工程师的项目与求职能力",
        "direction": "AI 应用工程",
        "purpose": "求职",
        "horizon": "六个月",
        "measurable_result": "完成两个可演示项目并通过 20 道面试题",
        "status": "confirmed",
        "source_quote": "就以这个为目标吧",
    }


@pytest.fixture()
def store(tmp_path):
    with GrowthStore(str(tmp_path / "growth.db")) as instance:
        yield instance


def test_tables_are_created_and_counts_start_at_zero(store):
    assert store.counts() == {
        "g_users": 0,
        "g_goals": 0,
        "g_goal_clarifications": 0,
        "g_capabilities": 0,
        "g_capability_claims": 0,
        "g_assessments": 0,
        "g_agent_runs": 0,
    }


def test_confirmed_goal_requires_all_four_elements(store):
    payload = _confirmed_goal()
    payload["horizon"] = ""
    with pytest.raises(GrowthStoreError, match="horizon"):
        store.save_goal(payload)


def test_confirmed_goal_requires_source_quote(store):
    payload = _confirmed_goal()
    payload["source_quote"] = None
    with pytest.raises(GrowthStoreError, match="source_quote"):
        store.save_goal(payload)


def test_draft_goal_may_be_incomplete(store):
    store.save_goal({"id": "goal_draft", "title": "我想成为 AI 工程师", "status": "draft"})
    goal = store.get_goal("goal_draft")
    assert goal["status"] == "draft" and goal["direction"] is None


def test_confirmed_goal_cannot_be_emptied(store):
    """确认过的目标不能被清空：即使把状态改回 draft，四要素也必须保留。"""
    store.save_goal(_confirmed_goal())
    with pytest.raises(GrowthStoreError, match="direction"):
        store.save_goal({"id": "goal_1", "title": "改主意了", "status": "draft"})


def test_clarification_rounds_are_sequential(store):
    store.save_goal({"id": "goal_2", "title": "目标", "status": "clarifying"})
    assert store.next_round("goal_2") == 1
    store.add_clarification("goal_2", 1, "应用还是算法？", "应用")
    store.add_clarification("goal_2", 2, "就业还是研究？")
    store.add_clarification("goal_2", 2, "就业还是研究？", "就业")
    rounds = store.list_clarifications("goal_2")
    assert [item["round"] for item in rounds] == [1, 2]
    assert rounds[1]["answer"] == "就业"
    assert store.next_round("goal_2") == 3


def test_capability_id_is_stable_across_whitespace_and_case():
    assert capability_id("goal_1", "LLM 基础", "Prompt") == capability_id(
        "goal_1", "  llm   基础 ", "PROMPT"
    )
    assert capability_id("goal_1", "LLM 基础", "Prompt") != capability_id(
        "goal_1", "LLM 基础", "Planning"
    )


def test_capability_upsert_is_idempotent_and_does_not_accumulate(store):
    store.save_goal({"id": "goal_3", "title": "目标", "status": "clarifying"})
    payload = {
        "id": capability_id("goal_3", "LLM 基础", "Prompt"),
        "goal_id": "goal_3",
        "name": "Prompt",
        "path": "LLM 基础/Prompt",
        "depth": 3,
        "target_level": 3,
    }
    store.upsert_capability(payload)
    store.upsert_capability({**payload, "target_level": 4})
    assert store.counts()["g_capabilities"] == 1
    assert store.get_capability(payload["id"])["target_level"] == 4


def test_regeneration_keeps_adjusted_target_level_and_note(store):
    """C1 / AC4：再生成不得覆盖人工调整。"""
    store.save_goal({"id": "goal_4", "title": "目标", "status": "clarifying"})
    capability = capability_id("goal_4", "Agent 架构", "Planning")
    store.upsert_capability(
        {
            "id": capability,
            "goal_id": "goal_4",
            "name": "Planning",
            "path": "Agent 架构/Planning",
            "depth": 3,
            "target_level": 2,
        }
    )
    store.adjust_capability(capability, 5, "用户要求按高级岗位标准")
    store.upsert_capability(
        {
            "id": capability,
            "goal_id": "goal_4",
            "name": "Planning",
            "path": "Agent 架构/Planning",
            "depth": 3,
            "target_level": 1,
            "adjustment_note": None,
            "generated_by_run_id": "run_regen",
        }
    )
    row = store.get_capability(capability)
    assert row["target_level"] == 5
    assert row["adjustment_note"] == "用户要求按高级岗位标准"
    assert row["origin"] == "adjusted"
    assert row["generated_by_run_id"] == "run_regen"  # 生成来源更新，人工值不动


def test_adjust_requires_note_and_valid_range(store):
    store.save_goal({"id": "goal_5", "title": "目标", "status": "clarifying"})
    capability = capability_id("goal_5", "工程", "Python")
    store.upsert_capability(
        {
            "id": capability,
            "goal_id": "goal_5",
            "name": "Python",
            "path": "工程/Python",
            "depth": 3,
            "target_level": 3,
        }
    )
    with pytest.raises(GrowthStoreError, match="adjustment_note"):
        store.adjust_capability(capability, 4, "   ")
    with pytest.raises(GrowthStoreError, match="target_level"):
        store.adjust_capability(capability, 9, "超标")
    with pytest.raises(GrowthStoreError, match="未知能力点"):
        store.adjust_capability("cap_missing", 4, "不存在")


def test_target_level_range_is_enforced_on_upsert(store):
    """写入路径也要拒绝越界的目标等级（不只是 adjust 路径）。"""
    store.save_goal({"id": "goal_8", "title": "目标", "status": "clarifying"})
    for bad_level in (0, 6, -1):
        with pytest.raises(GrowthStoreError, match="target_level"):
            store.upsert_capability(
                {
                    "id": capability_id("goal_8", "工程", "Python"),
                    "goal_id": "goal_8",
                    "name": "Python",
                    "path": "工程/Python",
                    "depth": 3,
                    "target_level": bad_level,
                }
            )
    assert store.counts()["g_capabilities"] == 0


def test_current_level_cannot_be_filled_in_m2(store):
    """决定 5：M2 的现状一律「尚未评估」，不得写入任何数字。"""
    store.save_goal({"id": "goal_6", "title": "目标", "status": "clarifying"})
    with pytest.raises(GrowthStoreError, match="current_level"):
        store.upsert_capability(
            {
                "id": capability_id("goal_6", "工程", "Python"),
                "goal_id": "goal_6",
                "name": "Python",
                "path": "工程/Python",
                "depth": 3,
                "target_level": 3,
                "current_level": 3,
            }
        )
    store.upsert_capability(
        {
            "id": capability_id("goal_6", "工程", "Python"),
            "goal_id": "goal_6",
            "name": "Python",
            "path": "工程/Python",
            "depth": 3,
            "target_level": 3,
        }
    )
    row = store.get_capability(capability_id("goal_6", "工程", "Python"))
    assert row["current_level"] is None
    assert row["current_level_status"] == "unassessed"


def test_depth_must_fit_three_layer_tree(store):
    store.save_goal({"id": "goal_7", "title": "目标", "status": "clarifying"})
    with pytest.raises(GrowthStoreError, match="depth"):
        store.upsert_capability(
            {
                "id": "cap_bad",
                "goal_id": "goal_7",
                "name": "太深了",
                "path": "a/b/c/d",
                "depth": 4,
                "target_level": 2,
            }
        )


def test_run_record_requires_consistent_model_source(store):
    base = {"id": "run_1", "agent": "goal", "provider": "fake", "model": "fake-1"}
    with pytest.raises(GrowthStoreError, match="model_source"):
        store.save_run({**base, "status": "ok", "model_source": "config_on_error"})
    with pytest.raises(GrowthStoreError, match="provider"):
        store.save_run({**base, "provider": "", "status": "ok", "model_source": "result"})
    store.save_run({**base, "status": "ok", "model_source": "result", "output": "{}"})
    assert store.counts()["g_agent_runs"] == 1


def test_store_closes_cleanly_so_the_file_can_be_removed(tmp_path):
    """M1-g 记录过 evkg「无 close() 导致 Windows 锁库」，自有存储不得重蹈。"""
    db = tmp_path / "closable.db"
    with GrowthStore(str(db)) as instance:
        instance.upsert_user("local", "本地用户")
    db.unlink()  # 若无 close()，Windows 上这里会因文件被占用而失败
    assert not db.exists()
