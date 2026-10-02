"""M2-b：Goal Agent 与澄清状态机的测试。

覆盖验收项：

* **AC1** —— ≤6 轮内产出含四要素的 confirmed goal；
* **AC2** —— 未确认（或四要素不全）不得进入能力分析；
* **AC10** —— 第 7 轮必须失败，不得静默继续追问。

全部用 `FakeGateway` 脚本化响应驱动，离线、无密钥（补充约束 C3）。
"""

from __future__ import annotations

import asyncio
import itertools

import pytest
from growth_os.agent import AgentRuntime, FakeGateway
from growth_os.goal import (
    MAX_ROUNDS,
    ClarificationLimitReached,
    GoalAgent,
    GoalStateError,
    require_confirmed_goal,
)
from growth_os.store import GrowthStore

FULL_PROPOSAL = {
    "direction": "AI 应用工程",
    "purpose": "求职",
    "horizon": "六个月",
    "measurable_result": "完成两个可演示项目并通过 20 道面试题",
}


def _agent(store: GrowthStore, responses: list[dict], *, agent_name: str = "goal") -> GoalAgent:
    counter = itertools.count(1)
    runtime = AgentRuntime(
        store=store,
        gateway=FakeGateway(
            responses={"goal_clarification": responses},
            provider="fake-provider",
            model="fake-model-x",
        ),
        agent=agent_name,
        id_factory=lambda: f"run_{next(counter):03d}",
    )
    return GoalAgent(store=store, runtime=runtime)


def _question(text: str) -> dict:
    return {"question": text, "proposed": None, "ready_to_confirm": False}


def _proposal(question: str, **overrides) -> dict:
    return {
        "question": question,
        "proposed": {**FULL_PROPOSAL, **overrides},
        "ready_to_confirm": True,
    }


@pytest.fixture()
def store(tmp_path):
    with GrowthStore(str(tmp_path / "goal.db")) as instance:
        yield instance


def test_first_turn_asks_one_question_and_links_the_run(store):
    agent = _agent(store, [_question("你更偏向应用、算法还是基础设施？")])
    turn = asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))

    assert turn.status == "clarifying" and turn.round == 1
    assert turn.rounds_left == MAX_ROUNDS - 1
    assert turn.missing == ["direction", "purpose", "horizon", "measurable_result"]
    goal = store.get_goal("goal_1")
    assert goal["status"] == "clarifying" and goal["title"] == "我想成为 AI 工程师"
    clarifications = store.list_clarifications("goal_1")
    assert len(clarifications) == 1 and clarifications[0]["answer"] is None
    run = store.get_run(turn.run_id)
    assert run["agent"] == "goal" and run["goal_id"] == "goal_1"
    assert run["provider"] == "fake-provider" and run["model"] == "fake-model-x"
    assert "剩余轮数：6" in run["input"]


def test_converges_within_six_rounds_and_confirms(store):
    """AC1：三轮澄清 + 一次确认，四要素齐全，≤6 轮。"""
    agent = _agent(
        store,
        [
            _question("你更偏向应用还是算法？"),
            _question("目标是就业、项目能力还是研究？"),
            _proposal("那么把你的目标定义为「六个月内达到 AI 应用工程师的项目与求职能力」，是否以此为目标？"),
        ],
    )
    asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    asyncio.run(agent.answer("goal_1", "应用"))
    turn = asyncio.run(agent.answer("goal_1", "找工作，六个月"))
    assert turn.status == "proposed" and turn.ready_to_confirm
    assert turn.proposed == FULL_PROPOSAL
    assert store.get_goal("goal_1")["status"] == "proposed"

    with pytest.raises(GoalStateError, match="尚未确认"):
        require_confirmed_goal(store, "goal_1")  # 提议 ≠ 确认

    goal = agent.confirm("goal_1", quote="就以这个为目标吧")
    assert goal["status"] == "confirmed"
    assert goal["source_quote"] == "就以这个为目标吧"
    rounds = store.list_clarifications("goal_1")
    assert len(rounds) <= MAX_ROUNDS
    # 确认问句的答案就是用户确认的原话 —— 轨迹是完整往返（G1 证据要求）。
    assert all(item["answer"] for item in rounds)
    assert rounds[-1]["answer"] == "就以这个为目标吧"
    assert require_confirmed_goal(store, "goal_1")["direction"] == "AI 应用工程"


def test_seventh_round_is_rejected_not_silently_continued(store):
    """AC10：6 轮用尽后再回答必须失败，且不得产生第 7 个问题。"""
    agent = _agent(store, [_question(f"第 {index} 个问题？") for index in range(1, 8)])
    asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    for index in range(1, MAX_ROUNDS):
        turn = asyncio.run(agent.answer("goal_1", f"回答 {index}"))
        assert turn.round == index + 1
    assert len(store.list_clarifications("goal_1")) == MAX_ROUNDS

    with pytest.raises(ClarificationLimitReached, match="上限"):
        asyncio.run(agent.answer("goal_1", "第六个回答"))
    assert len(store.list_clarifications("goal_1")) == MAX_ROUNDS  # 未新增第 7 轮
    assert len(agent.runtime.gateway.calls) == MAX_ROUNDS  # 第 7 个问题从未发给模型
    assert store.get_goal("goal_1")["status"] == "clarifying"
    assert store.counts()["g_goal_clarifications"] == MAX_ROUNDS


def test_confirmation_requires_proposal_and_quote(store):
    agent = _agent(store, [_question("先问一个问题")])
    asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    with pytest.raises(GoalStateError, match="不能确认"):
        agent.confirm("goal_1", quote="就这样")

    agent2 = _agent(store, [_proposal("是否以此为目标？", direction=None)])
    # direction 缺失 → 不是完整提议
    turn = asyncio.run(agent2.start("我想成为 AI 工程师", goal_id="goal_2"))
    assert turn.status == "clarifying" and "direction" in turn.missing


def test_partial_proposal_does_not_wipe_established_elements(store):
    """增量累积：后续轮次没提到的要素不得被 None 擦掉。"""
    first = {"question": "时间周期？", "proposed": {"direction": "AI 应用工程", "purpose": "求职"}}
    second = _proposal("是否以此为目标？", direction=None, purpose=None)
    agent = _agent(store, [first, second])
    asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    turn = asyncio.run(agent.answer("goal_1", "六个月，做完两个项目"))
    goal = store.get_goal("goal_1")
    assert turn.status == "proposed"
    assert goal["direction"] == "AI 应用工程" and goal["purpose"] == "求职"
    assert goal["horizon"] == "六个月"


def test_state_machine_rejects_out_of_order_calls(store):
    agent = _agent(store, [_question("第一个问题？"), _question("第二个问题？")])
    asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    with pytest.raises(GoalStateError, match="已存在"):
        asyncio.run(agent.start("重复开始", goal_id="goal_1"))
    asyncio.run(agent.answer("goal_1", "回答"))
    with pytest.raises(GoalStateError, match="不能为空"):
        asyncio.run(agent.answer("goal_1", "   "))
    with pytest.raises(GoalStateError, match="未知目标"):
        asyncio.run(agent.answer("goal_missing", "x"))
    with pytest.raises(GoalStateError, match="未知目标"):
        require_confirmed_goal(store, "goal_missing")


def test_guard_also_rejects_incomplete_confirmed_rows(store):
    """防御纵深：即使库被手工改出"confirmed 但四要素不全"的行，门也必须拦住。"""
    store.save_goal(
        {
            "id": "goal_broken",
            "user_id": "local",
            "title": "手工破坏",
            "status": "draft",
        }
    )
    store.db.execute(
        "UPDATE g_goals SET status='confirmed', direction=NULL WHERE id='goal_broken'"
    )
    store.db.commit()
    with pytest.raises(GoalStateError, match="四要素"):
        require_confirmed_goal(store, "goal_broken")


def test_every_turn_is_persisted_with_its_run(store):
    """可追溯性：每轮澄清都能追到产生它的运行记录（AC9 上半）。"""
    agent = _agent(store, [_question("问题一？"), _proposal("是否以此为目标？")])
    first = asyncio.run(agent.start("我想成为 AI 工程师", goal_id="goal_1"))
    second = asyncio.run(agent.answer("goal_1", "应用"))
    runs = store.list_runs(goal_id="goal_1", agent="goal")
    assert [run["id"] for run in runs] == [first.run_id, second.run_id]
    assert all(run["status"] == "ok" and run["model_source"] == "result" for run in runs)
    assert first.run_id != second.run_id
