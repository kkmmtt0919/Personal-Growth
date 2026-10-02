"""目标域：Goal Agent（澄清状态机）与能力模型生成。"""

from .agent import (
    CLARIFICATION_SYSTEM,
    MAX_ROUNDS,
    ClarificationLimitReached,
    ClarificationTurn,
    GoalAgent,
    GoalElements,
    GoalStateError,
    GoalTurnResult,
    require_confirmed_goal,
)

__all__ = [
    "CLARIFICATION_SYSTEM",
    "MAX_ROUNDS",
    "ClarificationLimitReached",
    "ClarificationTurn",
    "GoalAgent",
    "GoalElements",
    "GoalStateError",
    "GoalTurnResult",
    "require_confirmed_goal",
]
