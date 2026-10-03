"""Agent 层：网关接缝 + 最小运行时（决定 D4）。"""

from .gateway import FakeGateway, GatewayResult, StructuredGateway
from .runtime import (
    AgentContext,
    AgentRuntime,
    RunOutcome,
    ToolNotFound,
    ToolRegistry,
    ToolSpec,
)
from .tools import GROWTH_TOOL_NAMES, register_growth_tools

__all__ = [
    "GROWTH_TOOL_NAMES",
    "AgentContext",
    "AgentRuntime",
    "FakeGateway",
    "GatewayResult",
    "RunOutcome",
    "StructuredGateway",
    "ToolNotFound",
    "ToolRegistry",
    "ToolSpec",
    "register_growth_tools",
]
