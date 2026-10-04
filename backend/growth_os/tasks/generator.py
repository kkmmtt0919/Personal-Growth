"""M5-b：任务生成器 —— `gap → LLM 提议 → 七步闸门 → g_tasks(proposed)`。

用户 2026-10-03 冻结的三条实现约束：

1. **Generator 不直接拥有 `create_task` 权限** —— 唯一写库位置是闸门第 7 步
   （`LLM output ≠ database mutation`，与 M4-b ClaimBinder 同构）；
2. **accepted task 的 provenance 必须完整** —— 闸门第 2 步强制缺口有 `assessment_id`
   （`task_id → gap_id → assessment_id → claim/evidence` 的反查入口）；
3. **禁止任务排序字段** —— 排序/难度/学习价值（`priority` / `difficulty` / `learning_value` …）
   不允许进入 schema；M5-b 只解决「gap exists → task exists」。

预算（M5-b 冻结）：**per-gap 1 次调用**，`propose_many` 的目标集由调用方给出（运行器按
severity 排序取前 2）—— 单次运行 ≤2 HTTP、零额外重试。
"""

from __future__ import annotations

from ..agent.gateway import StructuredGateway
from ..agent.runtime import AgentContext, AgentRuntime
from .gate import TaskGate, TaskGenerationError, TaskProposal

TASK_GENERATION_TASK = "task_generation"

TASK_GENERATION_SYSTEM = """你是 Growth OS 的任务设计器。你只做一件事：
针对给定的**能力缺口**，设计一个**能产出新证据、可被验收**的小任务。

硬规则：
- 只描述"做什么 / 产出什么 / 怎么验"，不得评价用户能力，不得给出难度、优先级或期望等级；
- 任务必须产生可核验的产物（或现场作答），不得是"去学习 X"这类不可验收的表述；
- 无法为该缺口设计可验收任务时，给出 decline_reason 并留空其余字段的虚构内容。

deliverable_type 与 acceptance_type 只能从给定枚举中选择。"""


def render_task_prompt(gap: dict, capability: dict, *, memories: list[dict] | None = None) -> str:
    """把缺口上下文渲染成生成提示（只含事实：缺口、能力点、允许的枚举与维度约束）。"""
    import json

    from ..store import DIMENSION_DELIVERABLE_TYPES

    payload = {
        "gap": {
            "id": gap["id"],
            "dimension": gap["dimension"],
            "severity": gap["severity"],
            "current_level": gap["current_level"],
            "target_level": gap["target_level"],
            "rationale": gap["rationale"],
        },
        "capability": {
            "path": capability["path"],
            "target_level": capability["target_level"],
        },
        "deliverable_type_required": list(DIMENSION_DELIVERABLE_TYPES[gap["dimension"]]),
        "acceptance_type_options": ["artifact_check", "test_run", "probe_rubric"],
        "est_minutes_range": [10, 600],
        "confirmed_memories": [
            {"id": item["id"], "key": item["memory_key"], "value": item["value"], "source_kind": item["source_kind"], "source_id": item["source_id"]}
            for item in memories or []
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=1) + (
        "\n请为该缺口设计一个任务：给出 title / objective / deliverable_type（必须取 "
        "deliverable_type_required 中的一个）/ est_minutes / acceptance_type / acceptance；"
        "无法设计可验收任务时给出 decline_reason。"
    )


class TaskGenerator:
    """一次生成 = 一次结构化调用 + 七步闸门；Generator 自己不写库。"""

    def __init__(
        self,
        *,
        store,
        gateway: StructuredGateway,
        goal_id: str,
        user_id: str = "local",
        id_factory=None,
    ) -> None:
        self.store = store
        self.goal_id = goal_id
        self.user_id = user_id
        self.runtime = AgentRuntime(
            store=store, gateway=gateway, agent="task_generation", user_id=user_id, id_factory=id_factory
        )

    async def propose(self, gap_id: str) -> dict:
        gap = self.store.get_gap(gap_id)
        if gap is None:
            raise TaskGenerationError(f"未知缺口: {gap_id}")
        capability = self.store.get_capability(gap["capability_id"])
        if capability is None:
            raise TaskGenerationError(f"缺口引用的能力点不存在: {gap['capability_id']}")
        from ..memory import MemoryService

        memories = [item for item in MemoryService(self.store).active_view(layer="profile")]

        outcome = await self.runtime.call_model_with_run(
            system=TASK_GENERATION_SYSTEM,
            user=render_task_prompt(gap, capability, memories=memories),
            schema=TaskProposal,
            task=TASK_GENERATION_TASK,
            context=AgentContext(
                user_id=self.user_id,
                goal_id=self.goal_id,
                correlation_id=self.goal_id,
                notes={"缺口维度": gap["dimension"], "缺口严重度": gap["severity"]},
            ),
        )
        proposal = outcome.result.value
        gate = TaskGate(store=self.store, goal_id=self.goal_id, user_id=self.user_id)
        decision = gate.evaluate(
            proposal.model_dump(),
            gap_id=gap_id,
            run_id=outcome.run_id,
            index=0,
            proposer=f"{outcome.result.provider}/{outcome.result.model}",
        )
        return {
            "run_id": outcome.run_id,
            "provider": outcome.result.provider,
            "model": outcome.result.model,
            "goal_id": self.goal_id,
            "gaps": [
                {
                    "gap_id": gap["id"],
                    "capability_id": gap["capability_id"],
                    "dimension": gap["dimension"],
                    "severity": gap["severity"],
                    "assessment_id": gap["assessment_id"],
                    "status": gap["status"],
                }
            ],
            "proposals": [
                {**proposal.model_dump(), "proposal_id": decision.proposal_id, "run_id": outcome.run_id}
            ],
            "decisions": [decision.to_dict()],
        }

    async def propose_many(self, gap_ids: list[str]) -> dict:
        """按给定顺序逐个缺口提议（每个缺口 1 次调用）；汇总为一份运行报告。"""
        if not gap_ids:
            raise TaskGenerationError("propose_many 需要至少一个缺口")
        runs = [await self.propose(gap_id) for gap_id in gap_ids]
        merged = {
            "run_id": "+".join(run["run_id"] for run in runs),
            "provider": runs[0]["provider"],
            "model": runs[0]["model"],
            "goal_id": self.goal_id,
            "gaps": [item for run in runs for item in run["gaps"]],
            "proposals": [item for run in runs for item in run["proposals"]],
            "decisions": [item for run in runs for item in run["decisions"]],
            "per_gap_runs": [{"run_id": run["run_id"], "gaps": [g["gap_id"] for g in run["gaps"]]} for run in runs],
        }
        return merged
