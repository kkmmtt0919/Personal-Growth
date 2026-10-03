"""M5：任务域（契约在 `store`，生成器与闸门在本包）。

* `gate`：七步确定性闸门（`TaskProposal` / `TaskGate` / 留档）；
* `generator`：`gap → LLM 提议 → 闸门 → g_tasks(proposed)`（Generator 不直接写库）。

M5-c 的 `submission → evidence → claim → binding → assessment` 闭环将落在 `loop.py`。
"""

from .gate import (
    DECLINED_STAGE,
    FORBIDDEN_TASK_FIELDS,
    TASK_GATE_STAGES,
    TaskGate,
    TaskGateDecision,
    TaskGenerationError,
    TaskProposal,
    build_generation_artifact,
    proposal_id_for,
    write_generation_artifact,
)
from .generator import (
    TASK_GENERATION_SYSTEM,
    TASK_GENERATION_TASK,
    TaskGenerator,
    render_task_prompt,
)

__all__ = [
    "DECLINED_STAGE",
    "FORBIDDEN_TASK_FIELDS",
    "TASK_GATE_STAGES",
    "TASK_GENERATION_SYSTEM",
    "TASK_GENERATION_TASK",
    "TaskGate",
    "TaskGateDecision",
    "TaskGenerationError",
    "TaskGenerator",
    "TaskProposal",
    "build_generation_artifact",
    "proposal_id_for",
    "render_task_prompt",
    "write_generation_artifact",
]
