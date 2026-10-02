"""M2-c：能力树生成与调整保护的测试。

覆盖验收项：

* **AC2** —— 未确认目标不得进入能力分析（且拒绝发生在调用模型之前）；
* **AC3** —— ≥3 领域、≥12 能力点、≤3 层，且每点带 `target_level`、来源与校验状态；
* **AC4 / C1** —— `origin=adjusted` 的人工修改在重新生成后不被覆盖；
* **AC9** —— `capability → goal → agent_run` 可追溯；
* **AC11** —— 能力点不得伪装已验证（含"模型自称已核实"的用例）。

全部离线：`FakeGateway` 脚本化响应，无网络、无密钥。
"""

from __future__ import annotations

import asyncio
import itertools

import pytest
from growth_os.agent import FakeGateway
from growth_os.goal import (
    CapabilityModelGenerator,
    CapabilityTreeShapeError,
    GoalStateError,
    require_confirmed_goal,
)
from growth_os.store import GrowthStore, capability_id

DOMAINS = ("LLM 基础", "Agent 架构", "工程与评估")


def _tree(domains: tuple[str, ...], leaves_per_group: int, level_offset: int = 0) -> list[dict]:
    nodes: list[dict] = []
    for domain in domains:
        group = f"{domain}/核心"
        nodes.append({"path": domain, "target_level": 3 + level_offset, "source_note": "领域共识"})
        nodes.append({"path": group, "target_level": 3 + level_offset})
        for index in range(1, leaves_per_group + 1):
            nodes.append(
                {
                    "path": f"{group}/能力点 {index}",
                    "target_level": min(5, 2 + level_offset + (index % 3)),
                    "source_note": "常见岗位要求",
                }
            )
    return nodes


def _valid_nodes(level_offset: int = 0) -> list[dict]:
    return _tree(DOMAINS, leaves_per_group=4, level_offset=level_offset)


def _generator(store: GrowthStore, nodes: list[dict] | None) -> CapabilityModelGenerator:
    counter = itertools.count(1)
    responses = {"capability_model": {"nodes": nodes}} if nodes is not None else {}
    return CapabilityModelGenerator(
        store=store,
        gateway=FakeGateway(responses=responses, provider="fake-provider", model="fake-model-x"),
        id_factory=lambda: f"run_{next(counter):03d}",
    )


@pytest.fixture()
def store(tmp_path):
    with GrowthStore(str(tmp_path / "capability.db")) as instance:
        yield instance


def _confirmed_goal(store: GrowthStore, goal_id: str = "goal_1") -> None:
    store.save_goal(
        {
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
    )


def test_unconfirmed_goal_is_rejected_before_calling_the_model(store):
    """AC2：拒绝发生在调用模型之前（不浪费一次 API 调用）。"""
    store.save_goal({"id": "goal_draft", "title": "我想成为 AI 工程师", "status": "draft"})
    generator = _generator(store, _valid_nodes())
    with pytest.raises(GoalStateError, match="尚未确认"):
        asyncio.run(generator.generate("goal_draft"))
    assert store.counts()["g_agent_runs"] == 0
    assert store.counts()["g_capabilities"] == 0


def _two_domains() -> list[dict]:
    return _tree(("A", "B"), leaves_per_group=4)


def _too_few_capabilities() -> list[dict]:
    return _tree(DOMAINS, leaves_per_group=3)


def _too_deep() -> list[dict]:
    return [{"path": "A/B/C/D", "target_level": 3}]


def _orphan_group() -> list[dict]:
    return [{"path": domain, "target_level": 3} for domain in DOMAINS] + [
        {"path": "孤儿组/点", "target_level": 3}
    ]


def _level_out_of_range() -> list[dict]:
    return [{"path": domain, "target_level": 6} for domain in DOMAINS]


@pytest.mark.parametrize(
    ("nodes", "expected"),
    [
        (_two_domains(), "领域数不足"),
        (_too_few_capabilities(), "能力点数不足"),
        (_too_deep(), "层数超限"),
        (_orphan_group(), "缺少父节点"),
        (_level_out_of_range(), "target_level 越界"),
    ],
)
def test_shape_violations_are_rejected_without_partial_writes(store, nodes, expected):
    _confirmed_goal(store)
    generator = _generator(store, nodes)
    with pytest.raises(CapabilityTreeShapeError, match=expected):
        asyncio.run(generator.generate("goal_1"))
    assert store.counts()["g_capabilities"] == 0  # 不写半棵树
    # 模型确实被调用过（这次拒绝来自形状校验，不是前置门），运行记录仍在
    assert store.counts()["g_agent_runs"] == 1


def test_valid_tree_is_persisted_with_provenance(store):
    """AC3 / AC9 / AC11 / C2 的合并验证。"""
    _confirmed_goal(store)
    generator = _generator(store, _valid_nodes())
    report = asyncio.run(generator.generate("goal_1"))

    assert (report.domains, report.capabilities) == (3, 12)
    rows = store.list_capabilities("goal_1")
    assert len(rows) == 3 + 3 + 12
    leaves = [row for row in rows if row["depth"] == 3]
    assert len(leaves) == 12
    for row in rows:
        assert row["verification_status"] == "unverified"
        assert "未校验" in row["source_note"]
        assert row["generated_by_run_id"] == report.run_id
        assert row["target_level"] is not None
    # 父链完整：能力点的 parent_id 指向它所属的能力组，能力组指向领域
    leaf = next(row for row in leaves if row["path"] == "LLM 基础/核心/能力点 1")
    group = next(row for row in rows if row["path"] == "LLM 基础/核心")
    domain = next(row for row in rows if row["path"] == "LLM 基础")
    assert leaf["parent_id"] == group["id"]
    assert group["parent_id"] == domain["id"]
    assert domain["parent_id"] is None

    run = store.get_run(report.run_id)
    assert run["agent"] == "capability_model" and run["goal_id"] == "goal_1"
    assert run["status"] == "ok" and run["model_source"] == "result"
    assert run["provider"] == "fake-provider" and run["model"] == "fake-model-x"
    # AC9：capability → goal → agent_run 全部可走通
    assert require_confirmed_goal(store, run["goal_id"])["id"] == "goal_1"


def test_regeneration_keeps_adjusted_value_and_reports_protection(store):
    """AC4 / C1：人工调整过的能力点在重新生成后保持原值，且保护动作可见。"""
    _confirmed_goal(store)
    asyncio.run(_generator(store, _valid_nodes()).generate("goal_1"))

    leaf_path = "Agent 架构/核心/能力点 1"  # 原始 target_level=3，再生成时模型会给 4
    target = capability_id("goal_1", leaf_path, "能力点 1")
    untouched = capability_id("goal_1", "工程与评估/核心/能力点 1", "能力点 1")
    assert store.get_capability(target)["target_level"] == 3
    assert store.get_capability(untouched)["target_level"] == 3

    _generator(store, _valid_nodes()).adjust(target, 5, "用户按高级岗位标准上调")
    report = asyncio.run(_generator(store, _valid_nodes(level_offset=1)).generate("goal_1"))

    adjusted = store.get_capability(target)
    assert adjusted["target_level"] == 5
    assert adjusted["adjustment_note"] == "用户按高级岗位标准上调"
    assert adjusted["origin"] == "adjusted"
    assert {"id": target, "path": leaf_path, "stored": 5, "proposed": 4} in report.protected_adjusted
    # 未被调整的能力点跟随新生成值（3 → 4），证明确实发生了一次再生成
    assert store.get_capability(untouched)["target_level"] == 4


def test_current_level_stays_unassessed_after_generation(store):
    """决策 5：生成结果只描述"目标要求"，不推断用户现状。"""
    _confirmed_goal(store)
    asyncio.run(_generator(store, _valid_nodes()).generate("goal_1"))
    for row in store.list_capabilities("goal_1"):
        assert row["current_level"] is None
        assert row["current_level_status"] == "unassessed"


def test_model_cannot_claim_verified_source(store):
    """R5 补充约束：LLM 生成不得伪装成已验证的行业标准。"""
    _confirmed_goal(store)
    nodes = _valid_nodes()
    nodes[0]["source_note"] = "官方行业标准（已核实）"
    asyncio.run(_generator(store, nodes).generate("goal_1"))
    domain = store.get_capability(capability_id("goal_1", "LLM 基础", "LLM 基础"))
    assert domain["verification_status"] == "unverified"
    assert "unverified" in domain["source_note"]
    # 模型的说法被保留（不做审查式删改），但必须与"未校验"标记同时出现
    assert "已核实" in domain["source_note"]

def test_prompt_states_the_three_level_convention_explicitly():
    """回归守卫：真实会话曾因"第三层才算能力点"未写清而失败（诊断 m2d-02）。

    提示词必须显式写明层级约定与可自检的数量关系，否则模型会给出两层树。
    """
    from growth_os.goal import CAPABILITY_SYSTEM

    assert "必须用满三层" in CAPABILITY_SYSTEM
    assert "第三层才算能力点" in CAPABILITY_SYSTEM
    assert "两个" in CAPABILITY_SYSTEM and "2 个能力点" in CAPABILITY_SYSTEM
    assert "3×2×2" in CAPABILITY_SYSTEM.replace(" ", "")
    assert CAPABILITY_SYSTEM.count("反例") >= 1
    assert "输出前自检" in CAPABILITY_SYSTEM
