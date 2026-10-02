"""Goal Agent：把一句模糊目标澄清成 confirmed goal（PRD §16，`M2-PLAN.md` §2.1）。

状态机（ARCHITECTURE §5.3）：`draft → clarifying ⇄ proposed → confirmed`

三条硬约束（都有测试锁定）：

1. **≤6 轮**：一轮 = 一次「提问 + 回答」。第 7 个问题不会发出 —— 第 6 轮用尽后
   再想提问会抛 `ClarificationLimitReached`，而不是静默继续追问（AC10）。
2. **显式确认**：`proposed` 状态不会自动变成 `confirmed`；必须有显式的
   `confirm(quote=...)`，且 `quote` 是用户确认的原话（AC1 的 G1 证据之一）。
3. **未确认不得进入能力分析**：`require_confirmed_goal()` 是唯一入口，四要素不全或
   状态不是 `confirmed` 一律拒绝（AC2）。

模型只负责"问什么"与"提炼四要素"，不负责状态迁移 —— 状态由本模块决定并落库，
这样"未确认不得进入能力分析"就落在代码里，而不是靠提示词自律。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..agent import AgentContext, AgentRuntime, RunOutcome
from ..store import GOAL_ELEMENTS, GrowthStore, GrowthStoreError

MAX_ROUNDS = 6
TASK_NAME = "goal_clarification"
"""轮次上限（PRD §16 / G1 的「≤6 轮」）。改这个值必须同步改测试与验收记录。"""

CLARIFICATION_SYSTEM = """你是目标澄清员。用户不会填表，只会用自然语言描述想成为什么样的人。

规则：
1. 每轮只问一个最关键的问题，不要把多个问题塞进一句。
2. 不要替用户编造目标；四要素（方向 direction / 目的 purpose / 时间周期 horizon /
   可衡量结果 measurable_result）只能来自用户已表达的内容，缺失就继续问。
3. 当四要素齐全时，给出完整提议并把 ready_to_confirm 置为 true，同时把这一轮的
   question 写成请用户确认的问句（例如"是否以此为当前目标？"）。
4. 轮数有限（见 user 消息里的剩余轮数）；剩余轮数用尽前仍不齐全时，如实说明还缺什么，
   不得用默认值补齐。
5. 用户表述含糊时追问澄清，不要自行假设。"""


class GoalStateError(GrowthStoreError):
    """目标状态不允许当前操作（例如未确认就生成能力模型）。"""


class ClarificationLimitReached(GoalStateError):
    """已用完澄清轮数，不得再提问。"""


class GoalElements(BaseModel):
    direction: str | None = None
    purpose: str | None = None
    horizon: str | None = None
    measurable_result: str | None = None

    def missing(self) -> list[str]:
        return [field for field in GOAL_ELEMENTS if not str(getattr(self, field) or "").strip()]

    def complete(self) -> bool:
        return not self.missing()

    def as_goal_fields(self) -> dict[str, str | None]:
        return {field: getattr(self, field) for field in GOAL_ELEMENTS}


class ClarificationTurn(BaseModel):
    """模型在一轮里的输出：一个提问 + 可能的完整提议。"""

    question: str
    proposed: GoalElements | None = None
    ready_to_confirm: bool = False
    rationale: str | None = None


@dataclass(frozen=True)
class GoalTurnResult:
    goal_id: str
    status: str
    round: int
    question: str
    proposed: dict[str, Any] | None
    ready_to_confirm: bool
    rounds_left: int
    run_id: str
    missing: list[str]


def require_confirmed_goal(store: GrowthStore, goal_id: str) -> dict:
    """能力分析的前置门：只有 confirmed 且四要素齐全的目标才放行（AC2）。

    这是**唯一**入口 —— 能力模型生成、后续的任务生成都必须先过这里，
    而不是各自重复判断（重复的判断迟早会漏掉一处）。
    """
    goal = store.get_goal(goal_id)
    if goal is None:
        raise GoalStateError(f"未知目标: {goal_id}")
    if goal["status"] != "confirmed":
        raise GoalStateError(
            f"目标尚未确认（当前状态 {goal['status']}），不得进入能力分析；"
            "请先完成澄清并显式确认（PRD §16 硬约束）"
        )
    missing = [field for field in GOAL_ELEMENTS if not str(goal.get(field) or "").strip()]
    if missing:
        raise GoalStateError(f"已确认目标缺少四要素: {', '.join(missing)}")
    return goal


def render_clarification_prompt(goal: dict, history: list[dict], rounds_left: int) -> str:
    """把当前目标、问答历史与剩余轮数交给模型。"""
    lines = [f"用户原始表述：{goal['title']}"]
    current = {field: goal.get(field) for field in GOAL_ELEMENTS}
    rendered = "；".join(
        f"{field}={value}" if value else f"{field}=（未确定）" for field, value in current.items()
    )
    lines.append(f"目前已确定的四要素：{rendered}")
    lines.append("已完成问答：")
    answered = [item for item in history if item["answer"]]
    if not answered:
        lines.append("（尚未开始）")
    for item in answered:
        lines.append(f"  第 {item['round']} 轮 问：{item['question']}")
        lines.append(f"           答：{item['answer']}")
    lines.append(f"剩余轮数：{rounds_left}（用尽后不得再提问）")
    return "\n".join(lines)


class GoalAgent:
    """澄清会话的驱动器：提问 → 记录回答 → 提议 → 显式确认。"""

    def __init__(
        self,
        *,
        store: GrowthStore,
        runtime: AgentRuntime,
        user_id: str = "local",
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.user_id = user_id

    # -- 对外流程 ---------------------------------------------------------

    async def start(self, user_text: str, *, goal_id: str) -> GoalTurnResult:
        """用户说出模糊目标 → 建 draft 并问第一轮。"""
        if not str(user_text or "").strip():
            raise GoalStateError("用户原始表述不能为空")
        if self.store.get_goal(goal_id) is not None:
            raise GoalStateError(f"目标已存在: {goal_id}")
        self.store.save_goal(
            {
                "id": goal_id,
                "user_id": self.user_id,
                "title": user_text.strip(),
                "status": "draft",
            }
        )
        return await self._advance(goal_id)

    async def answer(self, goal_id: str, text: str) -> GoalTurnResult:
        """回答当前未答的问题，然后推进到下一轮（或给出提议）。"""
        goal = self._require_goal(goal_id)
        if goal["status"] != "clarifying":
            raise GoalStateError(f"当前状态 {goal['status']} 不接受回答（应为 clarifying）")
        history = self.store.list_clarifications(goal_id)
        open_round = next((item for item in reversed(history) if not item["answer"]), None)
        if open_round is None:
            raise GoalStateError("没有待回答的问题")
        if not str(text or "").strip():
            raise GoalStateError("回答不能为空")
        self.store.add_clarification(goal_id, open_round["round"], open_round["question"], text.strip())
        return await self._advance(goal_id)

    def confirm(self, goal_id: str, *, quote: str) -> dict:
        """显式确认：只有 `proposed` 才能确认，且必须保留用户原话。

        这里不调用模型 —— 确认是状态迁移，不该花一次 API 调用，也不该让模型"代用户同意"。
        """
        goal = self._require_goal(goal_id)
        if goal["status"] != "proposed":
            raise GoalStateError(f"当前状态 {goal['status']} 不能确认（应先由澄清给出完整提议）")
        if not str(quote or "").strip():
            raise GoalStateError("确认必须保留用户原话（source_quote）")
        # 把确认原话补记到那个确认问句上，让会话轨迹是完整往返（G1 证据要求）。
        history = self.store.list_clarifications(goal_id)
        open_round = next((item for item in reversed(history) if not item["answer"]), None)
        if open_round is not None:
            self.store.add_clarification(
                goal_id, open_round["round"], open_round["question"], quote.strip()
            )
        # 存储层会再校验一次四要素：两层都拒绝不完整的"确认"（PRD §16 硬约束）。
        self.store.save_goal({**goal, "status": "confirmed", "source_quote": quote.strip()})
        return self._require_goal(goal_id)

    # -- 内部 -------------------------------------------------------------

    def _require_goal(self, goal_id: str) -> dict:
        goal = self.store.get_goal(goal_id)
        if goal is None:
            raise GoalStateError(f"未知目标: {goal_id}")
        return goal

    async def _advance(self, goal_id: str) -> GoalTurnResult:
        goal = self._require_goal(goal_id)
        history = self.store.list_clarifications(goal_id)
        rounds_used = sum(1 for item in history if item["answer"])
        if rounds_used >= MAX_ROUNDS:
            raise ClarificationLimitReached(
                f"已达 {MAX_ROUNDS} 轮上限，不再提问。"
                f"当前状态 {goal['status']}：如已有完整提议请显式确认；否则需重新开始澄清会话。"
            )
        rounds_left = MAX_ROUNDS - rounds_used
        outcome = await self._ask(goal, history, rounds_left)
        turn = outcome.result.value
        proposed_fields = turn.proposed.as_goal_fields() if turn.proposed else {}
        # 增量累积：本轮没提到的要素保留此前已确定的值，不得被 None 擦掉。
        merged = {
            field: (proposed_fields.get(field) or goal.get(field)) for field in GOAL_ELEMENTS
        }
        missing = [field for field in GOAL_ELEMENTS if not str(merged.get(field) or "").strip()]
        # 就绪 = 模型声明可以确认 **且** 累积后的目标确实四要素齐全
        # （模型不必每轮重述全部要素；判定以库里的累积状态为准）。
        ready = bool(turn.proposed and turn.ready_to_confirm and not missing)

        next_round = len(history) + 1
        self.store.add_clarification(goal_id, next_round, turn.question, None)
        self.store.save_goal(
            {
                **goal,
                "status": "proposed" if ready else "clarifying",
                **merged,
            }
        )
        return GoalTurnResult(
            goal_id=goal_id,
            status="proposed" if ready else "clarifying",
            round=next_round,
            question=turn.question,
            proposed=merged if ready else (proposed_fields or None),
            ready_to_confirm=ready,
            rounds_left=rounds_left - 1,
            run_id=outcome.run_id,
            missing=[] if ready else missing,
        )

    async def _ask(self, goal: dict, history: list[dict], rounds_left: int) -> RunOutcome:
        context = AgentContext(
            user_id=self.user_id,
            goal_id=goal["id"],
            correlation_id=goal["id"],
            notes={"当前目标": goal["title"]},
        )
        return await self.runtime.call_model_with_run(
            system=CLARIFICATION_SYSTEM,
            user=render_clarification_prompt(goal, history, rounds_left),
            schema=ClarificationTurn,
            task=TASK_NAME,
            context=context,
        )
