"""M2-d 预算口径测试（离线，绝不发起真实调用）。

覆盖用户指定的三点：

1. **传输层包装器能拦到所有重试路径** —— 用 `httpx.MockTransport` 让 evkg 网关收到
   500，验证包装器计数等于实际尝试次数（重试也计入）；
2. **HTTP 硬上限生效** —— 触顶时抛 `HttpBudgetExceeded`，且该异常不被网关的重试
   循环捕获（不再尝试下一次请求）；
3. **授权开关仍然有效** —— `--gateway real` 在未设 `M2_ALLOW_REAL_MODEL` 时拒绝执行；
   失败路径写出诊断记录（应用层调用数 / HTTP 请求数 / token / 失败原因），且不自动重跑。
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_flow_fixtures import HttpBudgetExceeded, HttpRequestBudget

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "artifacts" / "m2" / "run_goal_flow_offline.py"


class Echo(BaseModel):
    answer: str


async def _no_sleep(*args, **kwargs) -> None:
    return None


def _mock_httpx(monkeypatch, *, status_code: int, seen: dict) -> None:
    """把 httpx.AsyncClient 换成走 MockTransport 的子类（离线，不触网）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        seen["seen"] += 1
        return httpx.Response(status_code, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class MockedAsyncClient(real_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", MockedAsyncClient)


async def _call_gateway() -> None:
    from evkg.model_gateway import ModelGateway

    gateway = ModelGateway(
        {
            "LLM_PROVIDER": "openai_compatible",
            "MODEL": "budget-probe",
            "BASE_URL": "https://probe.invalid",
            "API_KEY": "probe-key",
        }
    )
    await gateway.structured(system="s", user="u", schema=Echo, task="budget_probe")


def test_wrapper_counts_every_attempt_including_retries(monkeypatch):
    """重试路径被包装器拦到：attempts=3 → 计数 3（且确实发生了 3 次尝试）。"""
    monkeypatch.setenv("EVKG_HTTP_RETRIES", "3")
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    seen = {"seen": 0}
    _mock_httpx(monkeypatch, status_code=500, seen=seen)
    budget = HttpRequestBudget(cap=None).install()
    try:
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(_call_gateway())
    finally:
        budget.uninstall()
    assert budget.requests == 3 == seen["seen"]


def test_zero_extra_retries_makes_one_request_per_call(monkeypatch):
    """EVKG_HTTP_RETRIES=1（真实模式采用的设置）→ 单次调用只发 1 个请求。"""
    monkeypatch.setenv("EVKG_HTTP_RETRIES", "1")
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    seen = {"seen": 0}
    _mock_httpx(monkeypatch, status_code=500, seen=seen)
    budget = HttpRequestBudget(cap=8).install()
    try:
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(_call_gateway())
    finally:
        budget.uninstall()
    assert budget.requests == 1 == seen["seen"]


def test_http_cap_stops_immediately_and_is_not_retried(monkeypatch):
    """触顶即停：cap=2 且允许重试时，第 3 次尝试被拦下，异常穿透重试循环。"""
    monkeypatch.setenv("EVKG_HTTP_RETRIES", "5")
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    seen = {"seen": 0}
    _mock_httpx(monkeypatch, status_code=500, seen=seen)
    budget = HttpRequestBudget(cap=2).install()
    try:
        with pytest.raises(HttpBudgetExceeded, match="硬上限"):
            asyncio.run(_call_gateway())
    finally:
        budget.uninstall()
    assert budget.requests == 2 == seen["seen"]  # 第 3 个请求从未发出


def test_real_mode_requires_explicit_authorization(tmp_path):
    """授权开关：未设 M2_ALLOW_REAL_MODEL 时必须拒绝；不给真实调用留任何机会。"""
    env = {key: value for key, value in os.environ.items() if key != "M2_ALLOW_REAL_MODEL"}
    env["EVKG_API_KEY"] = ""  # 双保险：即使闸门失效也发不出真实请求
    env["OPENAI_API_KEY"] = ""
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--gateway", "real", "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(REPO),
        check=False,
    )
    assert result.returncode == 2
    assert "拒绝发起真实模型调用" in result.stdout
    assert not list(tmp_path.glob("session-real*.json"))


def test_failure_path_stops_and_writes_diagnostics(tmp_path):
    """失败即停：轮次耗尽 → 退出码 3 + 诊断记录（含两层预算、token 与失败原因）。"""
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--gateway",
            "fake",
            "--fake-scenario",
            "stubborn",
            "--out-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(REPO),
        check=False,
    )
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["stopped"] is True and "上限" in payload["reason"]
    record = json.loads((tmp_path / "session-fake-failed.json").read_text(encoding="utf-8"))
    assert record["auto_rerun"] is False
    assert record["budget"]["structured_calls_app_level"] == 6  # 六轮问答都真实发生了
    assert record["budget"]["http_requests_observed"] == 0  # 离线场景不触网
    assert record["budget"]["tokens_total"] > 0
    assert record["goal"]["status"] == "clarifying"
    for field in ("direction", "purpose", "horizon", "measurable_result"):
        assert record["goal"][field] is None  # 不自动补齐
