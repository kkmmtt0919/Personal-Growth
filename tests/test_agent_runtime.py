"""M2-a：运行时与网关接缝的测试。

覆盖验收项：

* **AC7 / C3 —— 离线回归**：fake gateway + 无密钥 + httpx 阻断断言，全部不触网；
* **AC8 / C2 —— 运行记录可追溯**：成功时 provider/model 取自返回值，失败时标注
  `config_on_error` 并保留错误信息；两条路径都要落库。
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from growth_os.agent import (
    AgentContext,
    AgentRuntime,
    FakeGateway,
    GatewayResult,
    StructuredGateway,
    ToolNotFound,
    ToolRegistry,
    ToolSpec,
)
from growth_os.store import GrowthStore
from pydantic import BaseModel


class Answer(BaseModel):
    answer: str


@pytest.fixture()
def store(tmp_path):
    with GrowthStore(str(tmp_path / "runtime.db")) as instance:
        yield instance


def _runtime(store, gateway, **kwargs) -> AgentRuntime:
    return AgentRuntime(
        store=store,
        gateway=gateway,
        agent="goal",
        id_factory=lambda: "run_fixed",
        timer=iter([0.0, 0.25]).__next__,
        **kwargs,
    )


def test_success_records_model_actually_returned(store):
    gateway = FakeGateway(
        responses={"ask": {"answer": "ok"}}, provider="fake-provider", model="fake-model-x"
    )
    runtime = _runtime(store, gateway)
    result = asyncio.run(
        runtime.call_model(
            system="sys",
            user="usr",
            schema=Answer,
            task="ask",
            context=AgentContext(goal_id="goal_1", correlation_id="sess_1"),
        )
    )
    assert isinstance(result, GatewayResult) and result.value.answer == "ok"
    run = store.get_run("run_fixed")
    assert run["status"] == "ok"
    assert run["provider"] == "fake-provider" and run["model"] == "fake-model-x"
    assert run["model_source"] == "result"
    assert run["goal_id"] == "goal_1" and run["correlation_id"] == "sess_1"
    assert run["latency_ms"] == 250
    assert run["tokens"] == len("sys") + len("usr") + len(str({"answer": "ok"}))
    assert "ok" in run["output"]


def test_failure_is_recorded_with_config_label_and_error(store):
    gateway = FakeGateway(
        fail_with={"ask": RuntimeError("网关 400：该模型始终思考")},
        provider="fake-provider",
        model="fake-model-x",
    )
    runtime = _runtime(store, gateway)
    with pytest.raises(RuntimeError, match="始终思考"):
        asyncio.run(runtime.call_model(system="s", user="u", schema=Answer, task="ask"))
    run = store.get_run("run_fixed")
    assert run["status"] == "error"
    assert run["model_source"] == "config_on_error"
    assert run["provider"] == "fake-provider" and run["model"] == "fake-model-x"
    assert "RuntimeError" in run["error"] and "始终思考" in run["error"]


def test_runtime_is_offline_without_keys_and_without_network(store, monkeypatch):
    """AC7 的三保险：注入 fake + 无密钥 + httpx 被阻断。"""
    for name in ("EVKG_API_KEY", "OPENAI_API_KEY", "GROWTH_AGENT_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    class NetworkForbidden(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            # 测试替身：任何实例化都视为"发生了联网"，直接判失败。
            raise AssertionError("离线测试不得实例化 httpx 客户端")

    monkeypatch.setattr(httpx, "AsyncClient", NetworkForbidden)
    gateway = FakeGateway(responses={"ask": {"answer": "ok"}})
    runtime = _runtime(store, gateway)
    asyncio.run(runtime.call_model(system="s", user="u", schema=Answer, task="ask"))
    assert len(gateway.calls) == 1
    assert store.get_run("run_fixed")["status"] == "ok"


def test_fake_gateway_requires_configured_response():
    gateway = FakeGateway()
    with pytest.raises(KeyError, match="没有为 task"):
        asyncio.run(gateway.structured(system="s", user="u", schema=Answer, task="unknown"))


def test_fake_gateway_satisfies_protocol():
    assert isinstance(FakeGateway(), StructuredGateway)


def test_tool_registry_registers_and_calls():
    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", description="回显", func=lambda text: text.upper()))
    assert registry.names() == ["echo"]
    assert registry.call("echo", text="hi") == "HI"
    with pytest.raises(ValueError, match="已注册"):
        registry.register(ToolSpec(name="echo", description="重复", func=lambda: None))
    with pytest.raises(ToolNotFound):
        registry.call("missing")


def test_context_renders_notes():
    context = AgentContext(goal_id="goal_1")
    assert context.render() == ""
    context.add_note("目标", "六个月内达到 AI 应用工程师")
    context.add_note("约束", "每周 10 小时")
    rendered = context.render()
    assert "[目标]" in rendered and "每周 10 小时" in rendered


def test_adapter_gateway_uses_instance_overrides(monkeypatch):
    """适配层工厂：GROWTH_AGENT_* 映射为实例级 overrides，不写进程级配置。"""
    from growth_os.evidence import adapter

    monkeypatch.setenv("GROWTH_AGENT_MODEL", "growth-agent-model")
    monkeypatch.setenv("GROWTH_AGENT_LLM_PROVIDER", "openai_compatible")
    monkeypatch.delenv("GROWTH_AGENT_BASE_URL", raising=False)
    overrides = adapter.growth_agent_overrides()
    assert overrides == {"MODEL": "growth-agent-model", "LLM_PROVIDER": "openai_compatible"}
    gateway = adapter.agent_gateway()
    assert isinstance(gateway, StructuredGateway)
    assert gateway.describe() == ("openai_compatible", "growth-agent-model")
    # 空值不产生 override（回落 EVKG_* 的规则由 evkg 网关负责，这里只验证不越权写入）
    assert "API_KEY" not in overrides
