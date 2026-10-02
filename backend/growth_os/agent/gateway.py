"""模型网关接缝：Growth OS 的 Agent 只依赖这里的 Protocol，不依赖任何厂商 SDK。

为什么要有这一层（`M2-PLAN.md` §3.3 / 补充约束 C3）：

* **离线回归**：M1-g 的覆盖实测显示 LLM 路径没有自动化测试（extract 0%）。
  M2 起，Agent 的测试通过注入 `FakeGateway` 实现确定性、无网络、无密钥的回归；
  真实模型运行只用于生成效果验证并单独留档。
* **不泄漏上游类型**：本模块的 `GatewayResult` 是 Growth OS 自己的类型；evkg 的
  `ModelResult` 由适配层转换（否则 `agent/` 就得 import evkg，违反 D1）。
* **运行记录可追溯**（C2）：`GatewayResult` 携带实际生效的 provider/model；
  失败路径由 `describe()` 给出当时配置，并明确标注 `config_on_error`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

UNCONFIGURED_TASK = "FakeGateway 没有为 task={task!r} 配置响应"


@dataclass(frozen=True)
class GatewayResult:
    """一次结构化模型调用的结果。

    `provider` / `model` 是**实际生效**的值（来自网关返回值），不是配置读取值 ——
    运行记录必须用它，见 `M2-PLAN.md` 补充约束 C2。
    """

    value: Any
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@runtime_checkable
class StructuredGateway(Protocol):
    """Agent 运行时依赖的最小接口（evkg ModelGateway 的一个子集）。"""

    def describe(self) -> tuple[str, str]:
        """返回当前配置下的 (provider, model)。仅用于失败路径的记录标注。"""
        ...

    async def structured(self, *, system: str, user: str, schema: type[T], task: str) -> GatewayResult:
        ...


class FakeGateway:
    """确定性网关：按 `task` 返回预设响应；不触网、不需要密钥。

    * `responses`：`task -> payload`（payload 可以是 schema 实例，或可直接校验的 dict）
    * `fail_with`：`task -> Exception`，用于验证失败路径也会落库（C2）
    * `calls`：记录每次调用的 task/system/user，供测试断言（例如"只调用了一次"）
    """

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        *,
        fail_with: dict[str, Exception] | None = None,
        provider: str = "fake",
        model: str = "fake-deterministic",
    ) -> None:
        self.responses = dict(responses or {})
        self.fail_with = dict(fail_with or {})
        self.provider = provider
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def describe(self) -> tuple[str, str]:
        return self.provider, self.model

    async def structured(self, *, system: str, user: str, schema: type[T], task: str) -> GatewayResult:
        self.calls.append({"task": task, "system": system, "user": user})
        if task in self.fail_with:
            raise self.fail_with[task]
        if task not in self.responses:
            raise KeyError(UNCONFIGURED_TASK.format(task=task))
        payload = self.responses[task]
        value = payload if isinstance(payload, schema) else schema.model_validate(payload)
        return GatewayResult(
            value=value,
            provider=self.provider,
            model=self.model,
            input_tokens=len(system) + len(user),
            output_tokens=len(str(payload)),
        )
