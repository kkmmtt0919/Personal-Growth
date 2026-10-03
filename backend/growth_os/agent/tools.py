"""Growth Agent 模式 A 工具（M5-a）：缺口 → 任务 → 提交 → 事件。

对应 `ARCHITECTURE.md` §5.3：

```text
模式 A（有任务）：list_gaps · create_task · complete_task · write_event
```

设计纪律（`M5-PLAN.md` v1.0，用户冻结）：

* 工具是**薄封装**：只做参数校验与转发，不在这里写业务规则（契约在 `GrowthStore`，
  生成器的 LLM 提议 + 七步闸门在 M5-b，提交→重评闭环在 M5-c）；
* `complete_task` 工具层负责**跨表族校验**（提交的 `source_id` 必须在证据层真实存在）——
  `GrowthStore` 只碰 `g_` 表，不读证据表族；
* **Task 不是能力判断**：工具不产出等级/分值，也不修改 assessment。
"""

from __future__ import annotations

from .runtime import ToolRegistry, ToolSpec

GROWTH_TOOL_NAMES = ("list_gaps", "create_task", "complete_task", "write_event")
"""M5-a 冻结的工具名（ARCHITECTURE §5.3 模式 A）。"""


def register_growth_tools(registry: ToolRegistry, *, store, evidence_store) -> ToolRegistry:
    """把模式 A 四工具注册进运行时（已注册的名称会由 registry 拒绝，不静默覆盖）。"""

    def list_gaps(status: str = "open") -> list[dict]:
        return store.list_gaps(status=status)

    def create_task(**payload) -> dict:
        """创建任务（`proposed`）。契约校验在 `GrowthStore.create_task`；
        LLM 提议 + 七步闸门（M5-b）在生成器侧，不在这里。"""
        identifier = store.create_task(payload)
        return store.get_task(identifier)

    def complete_task(task_id: str, *, source_id: str, note: str | None = None) -> dict:
        """完成任务的唯一入口（提交即完成）。

        工具层先校验 `source_id` 在**证据层**真实存在（跨表族一致性由应用层保证），
        再写提交记录并置 `done`。等级变化不在本工具内发生 —— 它属于
        `submission → evidence → claim → binding gate → assessment`（M5-c）。
        """
        if not str(source_id or "").strip():
            raise ValueError("complete_task 需要 source_id（提交必须产生证据来源）")
        known = {source.id for source in evidence_store.get_sources()}
        if source_id not in known:
            raise ValueError(f"source_id 不在证据库中: {source_id}")
        return store.complete_task(task_id, source_id=source_id, note=note)

    def write_event(kind: str, payload: dict | None = None, severity: str = "info") -> dict:
        identifier = store.write_event(kind, payload or {}, severity=severity)
        return {"event_id": identifier, "kind": kind}

    registry.register(ToolSpec(name="list_gaps", func=list_gaps, description="列出缺口（默认 open）"))
    registry.register(ToolSpec(name="create_task", func=create_task, description="创建任务（proposed）"))
    registry.register(
        ToolSpec(name="complete_task", func=complete_task, description="完成任务的唯一入口（需 source_id）")
    )
    registry.register(ToolSpec(name="write_event", func=write_event, description="写一条事件"))
    return registry
