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
from goal_flow_fixtures import (
    CONFIRM_QUESTION,
    ELEMENT_ANSWERS,
    ELEMENT_ORDER,
    QUESTION_CATALOG,
    UNMATCHED_REPLY,
    SimulatedUser,
    drive_clarification,
    proposal_without_consent_turns,
    scripted_turns,
    stubborn_question_turns,
)
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

# ---------------------------------------------------------------------------
# M2-d 修复：模拟用户的语义匹配 + 驱动循环的真实性
# ---------------------------------------------------------------------------


def _scripted_agent(store: GrowthStore, turns: list[dict]) -> GoalAgent:
    counter = itertools.count(1)
    runtime = AgentRuntime(
        store=store,
        gateway=FakeGateway(
            responses={"goal_clarification": turns}, provider="fake-provider", model="fake-model-x"
        ),
        agent="goal",
        id_factory=lambda: f"run_{next(counter):03d}",
    )
    return GoalAgent(store=store, runtime=runtime)


def test_simulated_user_prefers_unanswered_element_over_context_mentions():
    """优先"尚未回答过"的要素：问句里作为上下文出现的词不得抢走焦点。

    真实场景：方向与目的已答过之后，模型问"多长时间内找到工作"，
    末尾的"工作"是上下文，焦点是时间周期。
    """
    user = SimulatedUser()
    user.answered.update({"direction", "purpose"})
    assert user.classify("你希望在多长时间内找到一份 AI 应用工程师的工作？") == "horizon"

    fresh = SimulatedUser()
    assert fresh.classify("你更偏向应用、算法还是基础设施？") == "direction"
    assert fresh.classify("主要目标是就业、项目能力，还是长期研究？") == "purpose"
    assert fresh.classify("达到什么样的结果才算实现目标？") == "measurable_result"


def test_simulated_user_returns_explicit_unmatched_instead_of_inventing():
    user = SimulatedUser()
    answer = user.answer("你平时喜欢什么运动？")
    assert answer.matched is False and answer.field is None
    assert answer.text == UNMATCHED_REPLY
    for invented in ELEMENT_ANSWERS.values():
        assert invented not in answer.text


def test_simulated_user_is_deterministic_on_repeated_questions():
    user = SimulatedUser()
    question = "你希望多长时间内实现这个目标？"
    assert user.answer(question) == user.answer(question)


@pytest.mark.parametrize("field", ELEMENT_ORDER)
def test_every_catalog_question_matches_its_own_element(field):
    user = SimulatedUser()
    for question in QUESTION_CATALOG[field]:
        assert user.answer(question).field == field


def test_scripted_conversation_only_uses_user_provided_information(store):
    """fake 的真实性：最后一轮的完整提议只能由用户真正回答过的内容组成。"""
    user = SimulatedUser()
    proposed = [turn["proposed"] or {} for turn in scripted_turns(user)]
    keys = {key for item in proposed for key in item}
    values = [value for item in proposed for value in item.values()]
    assert values, "对话脚本应当包含模型对用户信息的复述"
    for answer in ELEMENT_ANSWERS.values():
        assert answer in values  # 复述的值必须逐字来自用户回答
    # 除四个要素外不得出现任何凭空补的字段
    assert keys <= set(ELEMENT_ORDER)


def test_out_of_order_questions_still_converge(store):
    """乱序提问：模型先问可衡量结果，最后才问方向 —— 语义匹配不受顺序影响。"""
    user = SimulatedUser()
    order = ("measurable_result", "horizon", "purpose", "direction")
    turns: list[dict] = []
    known: dict[str, str] = {}
    for field in order:
        question = QUESTION_CATALOG[field][0]
        turns.append({"question": question, "proposed": dict(known) or None, "ready_to_confirm": False})
        simulated = user.answer(question)
        assert simulated.field == field
        known[field] = simulated.text
    turns.append(
        {"question": CONFIRM_QUESTION, "proposed": dict(known), "ready_to_confirm": True}
    )
    agent = _scripted_agent(store, turns)
    result = asyncio.run(drive_clarification(agent, user, goal_id="goal_1", user_text="我想成为 AI 工程师"))

    goal = store.get_goal("goal_1")
    assert result["rounds_used"] <= MAX_ROUNDS
    assert goal["status"] == "confirmed"
    for field in ELEMENT_ORDER:
        assert goal[field] == ELEMENT_ANSWERS[field]  # 逐字段等于用户真正说过的内容
    assert all(item["answer_matched"] for item in result["rounds"] if item["answer"])


def test_repeated_question_costs_a_round_but_does_not_corrupt(store):
    """重复提问：用户重复同一答案、轮次照算，最终仍能收敛。"""
    user = SimulatedUser()
    horizon_question = QUESTION_CATALOG["horizon"][0]
    turns = [
        {"question": horizon_question, "proposed": None, "ready_to_confirm": False},
        {"question": horizon_question, "proposed": None, "ready_to_confirm": False},
        *[
            {"question": QUESTION_CATALOG[field][0], "proposed": None, "ready_to_confirm": False}
            for field in ("direction", "purpose", "measurable_result")
        ],
        {
            "question": CONFIRM_QUESTION,
            "proposed": {field: ELEMENT_ANSWERS[field] for field in ELEMENT_ORDER},
            "ready_to_confirm": True,
        },
    ]
    agent = _scripted_agent(store, turns)
    result = asyncio.run(drive_clarification(agent, user, goal_id="goal_1", user_text="我想成为 AI 工程师"))

    assert result["rounds_used"] == 6  # 重复的那轮被如实计入，恰好用满 6 轮上限
    assert result["rounds_used"] <= MAX_ROUNDS
    goal = store.get_goal("goal_1")
    assert goal["horizon"] == ELEMENT_ANSWERS["horizon"]
    assert goal["status"] == "confirmed"
    assert len(store.list_clarifications("goal_1")) == result["rounds_used"]


def test_six_round_exhaustion_stops_without_autofill(store):
    """六轮耗尽：明确失败；四要素不得被自动补齐。"""
    user = SimulatedUser()
    agent = _scripted_agent(store, stubborn_question_turns(QUESTION_CATALOG["horizon"][0]))
    with pytest.raises(ClarificationLimitReached):
        asyncio.run(drive_clarification(agent, user, goal_id="goal_1", user_text="我想成为 AI 工程师"))
    goal = store.get_goal("goal_1")
    assert goal["status"] == "clarifying"
    for field in ELEMENT_ORDER:
        assert goal[field] is None, f"四要素不得被自动补齐: {field}"
    assert store.counts()["g_goal_clarifications"] == MAX_ROUNDS


def test_complete_elements_without_ready_are_never_auto_confirmed(store):
    """四要素齐全但模型未置 ready_to_confirm：不得自动确认；轮次耗尽即失败。"""
    user = SimulatedUser()
    agent = _scripted_agent(store, proposal_without_consent_turns(user))
    with pytest.raises(ClarificationLimitReached):
        asyncio.run(drive_clarification(agent, user, goal_id="goal_1", user_text="我想成为 AI 工程师"))
    goal = store.get_goal("goal_1")
    assert goal["status"] != "confirmed"
    assert goal["source_quote"] is None
    assert goal["direction"] == ELEMENT_ANSWERS["direction"]  # 信息在，但没有"同意"

# ---------------------------------------------------------------------------
# 真实会话回归：把尝试 4/5 的真实问句逐条锁定（诊断 m2d-03 / m2d-04）
# ---------------------------------------------------------------------------


Q5_R1 = (
    "你说的“成为 AI Agent Engineer”，具体指哪种方向？"
    "比如偏向构建 Agent 产品、研究 Agent 架构，还是企业内部落地实施？"
)
Q5_R2 = (
    "你想在这个方向上达到目标，是为了什么目的？"
    "比如拿到 AI Agent 工程师的岗位、在现有工作中转型做 Agent 开发，还是做出自己的 Agent 产品？"
)
Q5_R3 = (
    "刚才问目的时，你的回答和方向重复了，能再说说你为什么想成为 AI Agent Engineer 吗？"
    "是为了换工作、在现有岗位上转型，还是做出自己的产品？"
)
Q5_R4 = (
    "如果这个方向已经定了，那能告诉我一个具体的动机场景吗？"
    "比如你希望在一年后的某一天，自己在做什么样的工作或做出什么样的东西？"
)
Q5_R5 = (
    "我想确认一下：除了“偏 AI 应用”之外，你能否说说背后更具体的期望？"
    "比如是为了找一份 Agent 开发的新工作，还是在现在的工作里转做 Agent 项目？"
)
Q5_R6 = (
    "这是最后一轮了，还缺目的、时间周期和可衡量结果，其中最关键的是："
    "你想成为 AI Agent Engineer 的根本原因是什么——是为了找新工作、"
    "在现有岗位转型，还是做出自己的产品？"
)
Q4_R2 = "你希望在多长时间内（比如半年、一年）拿到这份 AI 应用工程师的工作？"
Q4_R3 = (
    "在这六个月结束时，你希望用什么样的具体结果来衡量自己已达成目标"
    "（比如拿到 offer、完成若干个 Agent 项目作品集）？"
)


@pytest.mark.parametrize(
    ("question", "pre_answered", "expected"),
    [
        # 尝试 5 R1（举例从句里含"产品/研究"，主干焦点是方向）
        (Q5_R1, set(), "direction"),
        # 尝试 5 R2 —— 当时失败的那条：主干含上下文"在这个方向上"，焦点是"为了什么目的"
        (Q5_R2, {"direction"}, "purpose"),
        # 尝试 5 R3（模型指出回答重复后继续追问原因）
        (Q5_R3, {"direction", "purpose"}, "purpose"),
        # 尝试 5 R4（"动机场景"）
        (Q5_R4, {"direction", "purpose"}, "purpose"),
        # 尝试 5 R5（"期望"）
        (Q5_R5, {"direction", "purpose"}, "purpose"),
        # 尝试 5 R6（复合句：先列出还缺什么，最后才问焦点——而那个焦点 purpose 已经答过）
        # 期望：回答仍然缺失的要素，而不是被上下文里的 purpose 抢走焦点；
        # 按"位置最靠后"的消歧规则，两个缺失项里取"可衡量结果"。
        (Q5_R6, {"direction", "purpose"}, "measurable_result"),
        # 尝试 4 R2（不能末尾的"工作"带偏成目的；时间与可衡量未答 → 取时间）
        (Q4_R2, {"direction", "purpose"}, "horizon"),
        # 尝试 4 R3（可衡量结果）
        (Q4_R3, {"direction", "purpose", "horizon"}, "measurable_result"),
    ],
)
def test_real_transcript_questions_map_to_the_right_element(question, pre_answered, expected):
    user = SimulatedUser()
    user.answered.update(pre_answered)
    assert user.answer(question).field == expected


def test_inferred_answer_only_when_exactly_one_element_is_missing():
    """判断不了时：只剩一个未答要素才回答它（并标注 inferred），否则明确未匹配。"""
    user = SimulatedUser()
    user.answered.update({"direction", "purpose", "horizon"})
    answer = user.answer("你还有什么想补充的吗？")
    assert answer.matched and answer.field == "measurable_result" and answer.inferred

    partial = SimulatedUser()
    partial.answered.add("direction")
    blocked = partial.answer("你还有什么想补充的吗？")
    assert blocked.matched is False and blocked.text == UNMATCHED_REPLY
