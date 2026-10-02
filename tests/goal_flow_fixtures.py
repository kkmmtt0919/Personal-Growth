"""M2 演练与测试共用的确定性替身（**不是产品代码**）。

存在的理由（M2-d 尝试 1 的教训）：第一次真实会话失败，根因是演练脚本把"用户回答"
与"提问轮次"硬绑定 —— 真实模型的提问顺序一变，回答就错位；而 fake gateway 又在最后一轮
凭空补齐了用户从未提供的信息，把这个缺陷掩盖了。所以这里的替身遵守两条纪律：

1. **用户侧按语义回答，不按轮次回答**：每个要素维护独立答案，按问题语义匹配；
   匹配不到就返回明确的未匹配状态，**不编造**。
2. **模型侧只复述用户真正提供过的信息**：`scripted_turns()` 产出的每轮 `proposed`
   只包含此前用户确实回答过的要素，绝不凭空补齐。

关键词冲突用**显式优先级**处理（measurable > horizon > direction > purpose）：
"你希望在多长时间内找到一份 AI 应用工程师的工作？" 同时命中时间/方向/目的，
按优先级判为时间周期 —— 这是有测试锁定的行为，不是碰巧。
"""

from __future__ import annotations

from dataclasses import dataclass

from growth_os.goal import MAX_ROUNDS, ClarificationLimitReached, GoalAgent

ELEMENT_ORDER = ("direction", "purpose", "horizon", "measurable_result")

ELEMENT_ANSWERS = {
    "direction": "应用方向（偏 AI 应用，不是算法或基础设施）",
    "purpose": "找一份 AI 应用工程师的工作",
    "horizon": "六个月",
    "measurable_result": "完成两个可演示的 Agent 项目并通过 20 道面试题",
}

QUESTION_CATALOG = {
    "direction": ["你更偏向应用、算法还是基础设施？", "你想往哪个技术方向走？"],
    "purpose": ["主要目标是就业、项目能力，还是长期研究？", "你为什么要达到这个目标？"],
    "horizon": ["你希望多长时间内实现这个目标？", "时间周期大概是多久？"],
    "measurable_result": ["达到什么样的结果才算实现目标？", "有什么可衡量的验收标准？"],
}

MARKERS = {
    "measurable_result": ("可衡量", "衡量", "验收", "指标", "达标", "量化", "证明", "结果"),
    "horizon": ("多长时间", "多久", "时间", "周期", "期限", "什么时候", "几个月"),
    "direction": ("方向", "偏向", "哪一类", "应用", "算法", "基础设施", "领域"),
    "purpose": ("目的", "为了什么", "就业", "求职", "研究", "工作", "目标"),
}
PRECEDENCE = ("measurable_result", "horizon", "direction", "purpose")
"""冲突时的判定顺序：先看"可衡量"，再看"时间"，再看"方向"，最后"目的"。"""

UNMATCHED_REPLY = "（脚本用户没有匹配到该问题对应的信息，请换一个更具体的问法）"
"""未匹配时的回答：明确表态"没匹配到"，不编造内容。"""

CONFIRM_QUESTION = "那么把你的目标定义为上面四项，是否以此为当前目标？"
CONFIRM_QUOTE = "好，就以这个为目标"


@dataclass(frozen=True)
class SimulatedAnswer:
    text: str
    matched: bool
    field: str | None


class SimulatedUser:
    """确定性用户：按问题语义给出对应要素的答案。"""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = {**ELEMENT_ANSWERS, **(answers or {})}

    def classify(self, question: str) -> str | None:
        text = question or ""
        for field in PRECEDENCE:
            if any(marker in text for marker in MARKERS[field]):
                return field
        return None

    def answer(self, question: str) -> SimulatedAnswer:
        field = self.classify(question)
        if field is None:
            return SimulatedAnswer(text=UNMATCHED_REPLY, matched=False, field=None)
        return SimulatedAnswer(text=self.answers[field], matched=True, field=field)


def scripted_turns(user: SimulatedUser, *, max_questions: int = 6) -> list[dict]:
    """构造一段确定性的"模型按缺失要素提问"对话。

    每轮的 `proposed` **只包含此前用户真正回答过的要素**（修正 fake 的真实性）：
    第一轮 `proposed=None`，此后逐项累积，最后一轮才给出四要素齐全的确认提议。
    所需轮数 = 4 个要素问题 + 1 个确认问题 = 5 轮（≤6，符合 G1 的硬上限）。
    """
    known: dict[str, str] = {}
    turns: list[dict] = []
    for field in ELEMENT_ORDER:
        question = QUESTION_CATALOG[field][0]
        turns.append({"question": question, "proposed": dict(known) or None, "ready_to_confirm": False})
        simulated = user.answer(question)
        if not simulated.matched or simulated.field != field:
            raise AssertionError(f"目录问题未被语义匹配到正确要素: {question!r} -> {simulated}")
        known[field] = simulated.text
    if len(turns) + 1 > max_questions:
        raise AssertionError("要素数量超出轮次上限，无法在 6 轮内产出完整提议")
    turns.append({"question": CONFIRM_QUESTION, "proposed": dict(known), "ready_to_confirm": True})
    return turns


def stubborn_question_turns(question: str, count: int = 8) -> list[dict]:
    """永远只提问、从不给出完整提议的模型（用于"轮次耗尽"用例）。"""
    return [{"question": question, "proposed": None, "ready_to_confirm": False} for _ in range(count)]


def proposal_without_consent_turns(user: SimulatedUser) -> list[dict]:
    """四要素齐全但模型始终不置 `ready_to_confirm` —— 不得自动确认。

    共 6 轮：前 5 轮与正常对话相同，只是把最后一轮的 `ready_to_confirm` 改回 False，
    再补一轮"还需要补充吗"。驱动循环会因轮次耗尽而明确失败，而不是自行确认。
    """
    turns = scripted_turns(user)
    turns[-1] = {**turns[-1], "ready_to_confirm": False}
    turns.append(
        {
            "question": "你还有需要补充的信息吗？",
            "proposed": dict(turns[-1]["proposed"]),
            "ready_to_confirm": False,
        }
    )
    return turns


async def drive_clarification(
    agent: GoalAgent,
    user: SimulatedUser,
    *,
    goal_id: str,
    user_text: str,
    max_rounds: int = MAX_ROUNDS,
) -> dict:
    """澄清驱动（runner 与测试共用的唯一实现）。

    纪律：最多 `max_rounds` 轮问答；**只有 `ready_to_confirm` 为真才确认**；
    轮次耗尽或回答未匹配一律如实记录/失败，**绝不自动补齐四要素**。
    """
    turn = await agent.start(user_text, goal_id=goal_id)
    rounds: list[dict] = []

    def record(current, answer, matched, field):
        rounds.append(
            {
                "round": current.round,
                "question": current.question,
                "proposed": current.proposed,
                "ready_to_confirm": current.ready_to_confirm,
                "answer": answer,
                "answer_matched": matched,
                "answer_field": field,
            }
        )

    record(turn, None, None, None)
    while not turn.ready_to_confirm:
        answered = sum(1 for item in rounds if item["answer"])
        if answered >= max_rounds:
            raise ClarificationLimitReached(
                f"已回答 {answered} 轮仍未得到完整提议；停止，不自动补齐四要素"
            )
        simulated = user.answer(turn.question)
        rounds[-1]["answer"] = simulated.text
        rounds[-1]["answer_matched"] = simulated.matched
        rounds[-1]["answer_field"] = simulated.field
        turn = await agent.answer(goal_id, simulated.text)
        record(turn, None, None, None)

    rounds[-1]["answer"] = CONFIRM_QUOTE
    rounds[-1]["answer_matched"] = True
    rounds[-1]["answer_field"] = "confirmation"
    goal = agent.confirm(goal_id, quote=CONFIRM_QUOTE)
    return {"rounds": rounds, "goal": goal, "rounds_used": len(rounds)}
