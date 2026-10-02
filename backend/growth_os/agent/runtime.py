"""最小 Agent 运行时（决定 D4：自建薄运行时，不引入框架）。

M2 只需要三样东西，多了不做：

* `ToolRegistry` —— 工具注册与调用（M2-b 起 Goal Agent 用）；
* `AgentContext` —— 上下文装配（目标/会话标识/说明块），供提示词拼装；
* `AgentRuntime` —— 执行一次结构化模型调用，并把**实际生效的 provider/model**、
  状态、错误、耗时写入 `g_agent_runs`（补充约束 C2）。

设计约束（来自 `M2-PLAN.md` §3.3）：

* 运行时只依赖 `StructuredGateway` Protocol —— 测试注入 `FakeGateway` 即可离线跑；
* 成功路径的 provider/model 取自 `GatewayResult`（实际返回值）；失败路径取自
  `gateway.describe()` 并标注 `model_source="config_on_error"`；
* 失败也必须落库（M1-g 的教训：失败信息只留在控制台等于没有记录）。
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from ..store import GrowthStore
from .gateway import GatewayResult, StructuredGateway

T = TypeVar("T", bound=BaseModel)

MAX_TEXT_CHARS = 4000
"""单条运行记录里 input/output 的截断上限：证据留档要够用，但不能无界增长。"""


class ToolNotFound(KeyError):
    """请求了未注册的工具。"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    func: Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self.tools:
            raise ValueError(f"工具已注册: {spec.name}")
        self.tools[spec.name] = spec

    def names(self) -> list[str]:
        return sorted(self.tools)

    def get(self, name: str) -> ToolSpec:
        if name not in self.tools:
            raise ToolNotFound(name)
        return self.tools[name]

    def call(self, name: str, /, **kwargs: Any) -> Any:
        return self.get(name).func(**kwargs)


@dataclass
class AgentContext:
    """送进模型前的上下文装配（M2 只做最小版：结构化字段 + 说明块）。"""

    user_id: str = "local"
    goal_id: str | None = None
    correlation_id: str | None = None
    notes: dict[str, str] = field(default_factory=dict)

    def add_note(self, key: str, text: str) -> None:
        self.notes[key] = text

    def render(self) -> str:
        if not self.notes:
            return ""
        blocks = [f"[{key}]\n{value}" for key, value in self.notes.items()]
        return "\n\n".join(blocks)


def _truncate(text: str) -> str:
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS] + f"\n……（截断，共 {len(text)} 字符）"


@dataclass(frozen=True)
class RunOutcome:
    """一次运行的完整结果：网关返回值 + 运行号。

    运行号需要回传给上层（例如能力树写入 `g_capabilities.generated_by_run_id`，
    以满足 AC9 的 `capability → goal → agent_run` 可追溯），因此不能只返回
    `GatewayResult`。
    """

    run_id: str
    result: GatewayResult


class AgentRuntime:
    """跑一次模型调用并留痕；不负责提示词与业务逻辑（那是各 Agent 的事）。"""

    def __init__(
        self,
        *,
        store: GrowthStore,
        gateway: StructuredGateway,
        agent: str,
        user_id: str = "local",
        id_factory: Callable[[], str] | None = None,
        timer: Callable[[], float] | None = None,
    ) -> None:
        self.store = store
        self.gateway = gateway
        self.agent = agent
        self.user_id = user_id
        self.tools = ToolRegistry()
        self.id_factory = id_factory or (lambda: "run_" + uuid.uuid4().hex[:16])
        self.timer = timer or time.perf_counter

    async def call_model(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        task: str,
        context: AgentContext | None = None,
    ) -> GatewayResult:
        """执行一次结构化调用；成功与失败都会写入 `g_agent_runs`。"""
        outcome = await self.call_model_with_run(
            system=system, user=user, schema=schema, task=task, context=context
        )
        return outcome.result

    async def call_model_with_run(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        task: str,
        context: AgentContext | None = None,
    ) -> RunOutcome:
        """同上，但把运行号一并返回（供写入可追溯字段）。"""
        ctx = context or AgentContext(user_id=self.user_id)
        run_id = self.id_factory()
        started = self.timer()
        try:
            result = await self.gateway.structured(system=system, user=user, schema=schema, task=task)
        except Exception as error:
            # 失败必须落库后再抛给调用方 —— 只留在控制台的错误等于没有记录（C2）。
            provider, model = self.gateway.describe()
            self.store.save_run(
                {
                    "id": run_id,
                    "user_id": self.user_id,
                    "agent": self.agent,
                    "status": "error",
                    "provider": provider,
                    "model": model,
                    "model_source": "config_on_error",
                    "goal_id": ctx.goal_id,
                    "correlation_id": ctx.correlation_id,
                    "input": _truncate(user),
                    "error": f"{type(error).__name__}: {error}",
                    "latency_ms": int((self.timer() - started) * 1000),
                }
            )
            raise
        latency_ms = int((self.timer() - started) * 1000)
        tokens = None
        if result.input_tokens is not None or result.output_tokens is not None:
            tokens = (result.input_tokens or 0) + (result.output_tokens or 0)
        self.store.save_run(
            {
                "id": run_id,
                "user_id": self.user_id,
                "agent": self.agent,
                "status": "ok",
                "provider": result.provider,
                "model": result.model,
                "model_source": "result",
                "goal_id": ctx.goal_id,
                "correlation_id": ctx.correlation_id,
                "input": _truncate(user),
                "output": _truncate(_dump(result.value)),
                "tokens": tokens,
                "latency_ms": latency_ms,
            }
        )
        return RunOutcome(run_id=run_id, result=result)


def _dump(value: Any) -> str:
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
