"""Growth Agent 模式 A 工具（M5-a；M5-c 提交闭环接线）。

对应 `ARCHITECTURE.md` §5.3：

```text
模式 A（有任务）：list_gaps · create_task · complete_task · write_event
```

设计纪律（`M5-PLAN.md` v1.0，用户冻结）：

* 工具是**薄封装**：只做参数校验与转发，不在这里写业务规则（契约在 `GrowthStore`，
  生成器的 LLM 提议 + 七步闸门在 M5-b，提交→重评闭环在 `TaskLoop`）；
* **`complete_task` 的唯一入口 = `TaskLoop.complete_task`（M5-c）**：`source_id` 不是调用契约
  的一部分（它由证据链内部产生）——调用方只能给提交物（`artifact_path` / `probe_answer`）；
  工具层不再做跨表族 source 校验（那是 loop 的入库步骤）；
* **Task 不是能力判断**：工具不产出等级/分值，也不修改 assessment。
"""

from __future__ import annotations

import asyncio

from .runtime import ToolRegistry, ToolSpec

GROWTH_TOOL_NAMES = ("list_gaps", "create_task", "complete_task", "write_event")
"""M5-a 冻结的工具名（ARCHITECTURE §5.3 模式 A）。"""


def register_growth_tools(
    registry: ToolRegistry,
    *,
    store,
    evidence_store,
    gateway=None,
    submission_dir=None,
    id_factory=None,
) -> ToolRegistry:
    """把模式 A 四工具注册进运行时（已注册的名称会由 registry 拒绝，不静默覆盖）。

    `gateway` 供 `complete_task` 的绑定提议使用（闭环是异步的；工具层是同步注册表，
    见 `complete_task` 的同步桥接说明）。
    """

    def list_gaps(status: str = "open") -> list[dict]:
        return store.list_gaps(status=status)

    def create_task(**payload) -> dict:
        """创建任务（`proposed`）。契约校验在 `GrowthStore.create_task`；
        LLM 提议 + 七步闸门（M5-b）在生成器侧，不在这里。"""
        identifier = store.create_task(payload)
        return store.get_task(identifier)

    def complete_task(
        task_id: str,
        *,
        artifact_path: str | None = None,
        probe_answer: str | None = None,
        note: str | None = None,
    ) -> dict:
        """完成任务的唯一入口（提交即完成 → 闭环）。

        委托 `TaskLoop.complete_task`（M5-c）：单入口入库 → 材料 claim → 绑定闸门 →
        重评 → 归因。**`source_id` 不再出现在调用契约里**（由证据链内部产生）。
        等级变化不在本工具内发生，也不由本工具决定。
        """
        # 局部导入：`assessment` 包反向依赖 `agent`（运行时），顶层导入会成环。
        from ..assessment import task_loop as loop_module

        if gateway is None:
            raise ValueError("complete_task 需要 gateway（TaskLoop 的绑定提议需要模型网关）")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = loop_module.TaskLoop(
                store=store,
                evidence_store=evidence_store,
                gateway=gateway,
                submission_dir=submission_dir,
                id_factory=id_factory,
            )
            return asyncio.run(
                loop.complete_task(
                    task_id, artifact_path=artifact_path, probe_answer=probe_answer, note=note
                )
            )
        raise loop_module.TaskLoopError(
            "complete_task 是异步闭环：事件循环内请直接 await TaskLoop.complete_task(...)"
        )

    def write_event(kind: str, payload: dict | None = None, severity: str = "info") -> dict:
        identifier = store.write_event(kind, payload or {}, severity=severity)
        return {"event_id": identifier, "kind": kind}

    registry.register(ToolSpec(name="list_gaps", func=list_gaps, description="列出缺口（默认 open）"))
    registry.register(ToolSpec(name="create_task", func=create_task, description="创建任务（proposed）"))
    registry.register(
        ToolSpec(
            name="complete_task",
            func=complete_task,
            description="完成任务的唯一入口（提交物经闭环入库；source_id 由系统产生）",
        )
    )
    registry.register(ToolSpec(name="write_event", func=write_event, description="写一条事件"))
    return registry
