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

import re
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

INTENT_PATTERNS = {
    "measurable_result": (
        r"可衡量", r"衡量", r"什么(样|样的)?结果", r"怎样的结果", r"验收", r"达标", r"量化",
    ),
    "horizon": (
        r"多长时间", r"多久", r"时间周期", r"期限", r"什么时候", r"几个月", r"几年", r"时间(上|大概)",
    ),
    "purpose": (
        r"为什么", r"目的", r"动机", r"根本原因", r"原因", r"为了", r"图什么",
        r"就业", r"求职", r"转型", r"新工作", r"工作", r"期望", r"研究", r"产品",
    ),
    "direction": (
        r"哪[个种].{0,6}方向", r"什么.{0,6}方向", r"方向(是|为|上)", r"偏向", r"哪一类",
        r"更偏", r"具体指", r"领域",
    ),
}
"""提问式意图模式（不是宽泛关键词）。

M2-d 尝试 5 的教训：模型问"目的"时，问句里作为**上下文**出现的"方向"被粗匹配当成了焦点，
导致模拟用户四次答错。因此现在的规则是：

1. 只看**问句主干**（第一个「？」之前）—— 排除"比如…"这类举例带来的干扰；
2. 找出所有命中的意图候选；
3. **优先尚未回答过的要素**（跨轮次维护状态）；
4. 平票时取主干中**位置最靠后**的候选（复合句的真正焦点通常在末尾）；
5. 判断不了且恰好只剩一个未答要素 → 回答它并标注 `inferred`；否则返回明确的"未匹配"。
"""

UNMATCHED_REPLY = "（脚本用户没有匹配到该问题对应的信息，请换一个更具体的问法）"
"""未匹配时的回答：明确表态"没匹配到"，不编造内容。"""

CONFIRM_QUESTION = "那么把你的目标定义为上面四项，是否以此为当前目标？"
CONFIRM_QUOTE = "好，就以这个为目标"


@dataclass(frozen=True)
class SimulatedAnswer:
    text: str
    matched: bool
    field: str | None
    inferred: bool = False
    """`inferred=True` 表示这一轮不是靠问题内容判断的，而是"只剩一个未答要素"推出来的。"""


class SimulatedUser:
    """确定性用户：按问题语义给出对应要素的答案，并跨轮次记住已答过什么。"""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = {**ELEMENT_ANSWERS, **(answers or {})}
        self.answered: set[str] = set()

    @staticmethod
    def _head(question: str | None) -> str:
        """问句主干：第一个「？」之前的部分（举例与追问都排除在焦点判断之外）。"""
        text = question or ""
        head = re.split(r"[？?]", text, maxsplit=1)[0]
        return head or text

    def _candidates(self, question: str | None) -> dict[str, int]:
        """主干里命中的意图候选 → 该要素在主干中最后一次出现的位置。"""
        head = self._head(question)
        found: dict[str, int] = {}
        for field, patterns in INTENT_PATTERNS.items():
            positions = [match.start() for pattern in patterns for match in re.finditer(pattern, head)]
            if positions:
                found[field] = max(positions)
        return found

    def classify(self, question: str) -> str | None:
        """这个问题在问哪个要素；判断不了返回 None（不做宽泛猜测）。"""
        candidates = self._candidates(question)
        if not candidates:
            missing = [field for field in ELEMENT_ORDER if field not in self.answered]
            return missing[0] if len(missing) == 1 else None
        pool = {field: pos for field, pos in candidates.items() if field not in self.answered}
        pool = pool or candidates
        return max(pool, key=lambda field: pool[field])

    def answer(self, question: str) -> SimulatedAnswer:
        candidates = self._candidates(question)
        field = self.classify(question)
        if field is None:
            return SimulatedAnswer(text=UNMATCHED_REPLY, matched=False, field=None)
        self.answered.add(field)
        return SimulatedAnswer(
            text=self.answers[field], matched=True, field=field, inferred=not candidates
        )


def scripted_turns(user: SimulatedUser, *, max_questions: int = 6) -> list[dict]:
    """构造一段确定性的"模型按缺失要素提问"对话。

    每轮的 `proposed` **只包含此前用户真正回答过的要素**（修正 fake 的真实性）：
    第一轮 `proposed=None`，此后逐项累积，最后一轮才给出四要素齐全的确认提议。
    所需轮数 = 4 个要素问题 + 1 个确认问题 = 5 轮（≤6，符合 G1 的硬上限）。
    """
    known: dict[str, str] = {}
    turns: list[dict] = []
    clone = SimulatedUser(user.answers)  # 不污染传入实例的"已答"状态
    for field in ELEMENT_ORDER:
        question = QUESTION_CATALOG[field][0]
        turns.append({"question": question, "proposed": dict(known) or None, "ready_to_confirm": False})
        simulated = clone.answer(question)
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


async def drive_clarification(    agent: GoalAgent,
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
                "answer_inferred": False,
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
        rounds[-1]["answer_inferred"] = simulated.inferred
        turn = await agent.answer(goal_id, simulated.text)
        record(turn, None, None, None)

    rounds[-1]["answer"] = CONFIRM_QUOTE
    rounds[-1]["answer_matched"] = True
    rounds[-1]["answer_field"] = "confirmation"
    goal = agent.confirm(goal_id, quote=CONFIRM_QUOTE)
    return {"rounds": rounds, "goal": goal, "rounds_used": len(rounds)}

class HttpBudgetExceeded(RuntimeError):
    """达到传输层 HTTP 请求硬上限：立即停止，不再重试。

    刻意**不**继承 httpx 的异常类型 —— evkg 的重试循环只捕获
    `ConnectError / ReadTimeout / WriteTimeout / RemoteProtocolError`，
    因此这个异常会直接穿透 `_post_with_retry`，不会被当作瞬时故障继续重试。
    """


class HttpRequestBudget:
    """传输层请求计数器 + 硬上限（包装 `httpx.AsyncClient.post`）。

    静态核对（2026-10-02，evkg @ 28afbc0）：`model_gateway.py` 里**唯一**的 HTTP
    调用点是 `client.post(...)`（第 59 行，三个 provider 分支共用 `_post_with_retry`），
    没有 `.get/.request/.stream` 等其它动词 —— 所以包装 `.post` 能拦到每一次尝试，
    包括网关内部的重试。
    """

    def __init__(self, cap: int | None) -> None:
        self.cap = cap
        self.requests = 0
        self.installed = False
        self.original = None

    def install(self) -> HttpRequestBudget:
        import httpx

        if self.installed:
            return self
        self.original = httpx.AsyncClient.post

        async def counted_post(client, *args, **kwargs):
            if self.cap is not None and self.requests >= self.cap:
                raise HttpBudgetExceeded(
                    f"HTTP 请求数已达硬上限 {self.cap}，立即停止（不再重试）"
                )
            self.requests += 1
            return await self.original(client, *args, **kwargs)

        httpx.AsyncClient.post = counted_post
        self.installed = True
        return self

    def uninstall(self) -> None:
        if not self.installed:
            return
        import httpx

        httpx.AsyncClient.post = self.original
        self.installed = False
