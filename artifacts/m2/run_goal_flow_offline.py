"""M2 端到端演练：澄清 → 确认 → 能力树 → 人工调整 → 再生成（G1 的 dry-run 载体）。

两种模式：

* `--gateway fake`（默认）：确定性替身（`tests/goal_flow_fixtures.py`），离线、无密钥；
  用于把 M2 的验收项在不花 API 调用的前提下跑一遍，并产出快照。
* `--gateway real`：走适配层的真实网关（`GROWTH_AGENT_*` / `EVKG_*`），用于 M2-d 的
  G1 证据。**需要显式授权**：不设 `M2_ALLOW_REAL_MODEL=1` 时脚本直接退出并打印所需
  配置，绝不静默发起真实调用。

用户侧纪律（M2-d 尝试 1 的教训）：回答**按问题语义匹配**，不按轮次绑定；匹配不到时
返回明确的"未匹配"回答并如实记录，不编造内容。驱动循环最多 6 轮，只有四要素齐全
**且模型明确返回 `ready_to_confirm`** 才允许确认；轮次耗尽即明确失败，不自动补齐。

预算口径：应用层"结构化调用"次数由代码统计；真实模式下另用 httpx 包装器统计
**实际 HTTP 请求数**（含 evkg 网关内部的传输层重试），两者分别记录。
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "tests"))

from goal_flow_fixtures import (
    QUESTION_CATALOG,
    SimulatedUser,
    drive_clarification,
    scripted_turns,
)
from growth_os.agent import AgentRuntime, FakeGateway
from growth_os.goal import (
    MAX_ROUNDS,
    CapabilityModelGenerator,
    GoalAgent,
)
from growth_os.store import GrowthStore, capability_id

GOAL_ID = "goal_m2_real"
USER_TEXT = "我想成为 AI Agent Engineer"

CAPABILITY_TREE = {
    "nodes": [
        *[
            {"path": domain, "target_level": 4, "source_note": "岗位要求共识"}
            for domain in ("LLM 基础", "Agent 架构", "工程化", "评估与测试")
        ],
        *[
            {"path": group, "target_level": 4}
            for group in (
                "LLM 基础/提示与上下文",
                "Agent 架构/循环与规划",
                "工程化/后端与数据",
                "评估与测试/用例与基准",
            )
        ],
        *[
            {"path": f"LLM 基础/提示与上下文/能力点 {i}", "target_level": 4, "source_note": "岗位要求"}
            for i in range(1, 5)
        ],
        *[
            {"path": f"Agent 架构/循环与规划/能力点 {i}", "target_level": 5, "source_note": "岗位要求"}
            for i in range(1, 5)
        ],
        *[
            {"path": f"工程化/后端与数据/能力点 {i}", "target_level": 4, "source_note": "岗位要求"}
            for i in range(1, 5)
        ],
        *[
            {"path": f"评估与测试/用例与基准/能力点 {i}", "target_level": 4, "source_note": "岗位要求"}
            for i in range(1, 5)
        ],
    ]
}

REAL_MODEL_CONFIG = {
    "GROWTH_AGENT_LLM_PROVIDER / GROWTH_AGENT_MODEL": "可选；--model 或 GROWTH_AGENT_MODEL 可覆盖",
    "EVKG_LLM_PROVIDER / EVKG_MODEL": "主模型（.env: openai_compatible / glm-5.3）",
    "EVKG_API_KEY": "必需（真实调用）",
    "调用预算上限": "6 次澄清 + 2 次能力树生成 = 8 次结构化调用",
    "传输层重试": "evkg 网关内部按 EVKG_HTTP_RETRIES 重试 5xx/超时；实际 HTTP 请求数单独统计",
    "授权开关": "M2_ALLOW_REAL_MODEL=1",
}

HTTP_COUNTER = {"requests": 0}


def install_http_counter() -> None:
    """统计实际 HTTP 请求数（含传输层重试）——不改 evkg，只在进程内包装 httpx。"""
    import httpx

    original = httpx.AsyncClient.post

    async def counted_post(self, *args, **kwargs):
        HTTP_COUNTER["requests"] += 1
        return await original(self, *args, **kwargs)

    httpx.AsyncClient.post = counted_post


def build_gateway(mode: str, user: SimulatedUser):
    if mode == "fake":
        return FakeGateway(
            responses={
                "goal_clarification": scripted_turns(user),
                "capability_model": {"nodes": CAPABILITY_TREE["nodes"]},
            },
            provider="fake-provider",
            model="fake-model-x",
        )
    if mode != "real":
        raise SystemExit(f"未知模式: {mode}")
    if os.getenv("M2_ALLOW_REAL_MODEL") != "1":
        print("拒绝发起真实模型调用。")
        print("如需 M2-d 的 G1 证据，请先确认成本与配置，然后设置 M2_ALLOW_REAL_MODEL=1 再运行。")
        print(json.dumps(REAL_MODEL_CONFIG, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    from growth_os.evidence import adapter

    install_http_counter()
    return adapter.agent_gateway()


async def run_session(store: GrowthStore, gateway, mode: str) -> dict:
    counter = itertools.count(1)
    user = SimulatedUser()
    runtime = AgentRuntime(
        store=store, gateway=gateway, agent="goal", id_factory=lambda: f"{mode}_run_{next(counter):03d}"
    )
    agent = GoalAgent(store=store, runtime=runtime)
    clarification = await drive_clarification(agent, user, goal_id=GOAL_ID, user_text=USER_TEXT)

    generator = CapabilityModelGenerator(
        store=store,
        gateway=gateway,
        id_factory=lambda: f"{mode}_run_{next(counter):03d}",
    )
    first = await generator.generate(GOAL_ID)
    adjusted_id = capability_id(GOAL_ID, "Agent 架构/循环与规划/能力点 1", "能力点 1")
    generator.adjust(adjusted_id, 5, "演练：人工上调，验证再生成保护")
    second = await generator.generate(GOAL_ID)

    rows = store.list_capabilities(GOAL_ID)
    runs = store.list_runs(goal_id=GOAL_ID)
    report = {
        "mode": mode,
        "goal": store.get_goal(GOAL_ID),
        "clarification": clarification,
        "capability_report_first": first.__dict__,
        "capability_report_second": second.__dict__,
        "adjusted_capability": store.get_capability(adjusted_id),
        "capabilities": rows,
        "runs": runs,
        "budget": {
            "structured_calls_app_level": len(runs),
            "planned_upper_bound": 8,
            "http_requests_observed": HTTP_COUNTER["requests"] if mode == "real" else 0,
            "note": "HTTP 请求数含 evkg 网关内部的传输层重试；应用层调用数不含重试",
        },
        "checks": {
            "rounds_within_cap": clarification["rounds_used"] <= MAX_ROUNDS,
            "all_answers_matched": all(
                item["answer_matched"] for item in clarification["rounds"] if item["answer"]
            ),
            "goal_confirmed_with_four_elements": store.get_goal(GOAL_ID)["status"] == "confirmed",
            "domains_at_least_3": sum(1 for row in rows if row["depth"] == 1) >= 3,
            "capabilities_at_least_12": sum(1 for row in rows if row["depth"] == 3) >= 12,
            "max_depth_3": max(row["depth"] for row in rows) <= 3,
            "all_unverified": all(row["verification_status"] == "unverified" for row in rows),
            "all_current_level_unassessed": all(
                row["current_level"] is None and row["current_level_status"] == "unassessed"
                for row in rows
            ),
            "adjusted_protected": store.get_capability(adjusted_id)["target_level"] == 5,
            "adjusted_note_kept": bool(store.get_capability(adjusted_id)["adjustment_note"]),
            "lineage_complete": all(
                any(run["id"] == row["generated_by_run_id"] and run["goal_id"] == GOAL_ID for run in runs)
                for row in rows
            ),
            "runs_have_actual_model": all(
                run["provider"] and run["model"] and run["model_source"] == "result" for run in runs
            ),
            "budget_within_upper_bound": len(runs) <= 8,
        },
    }
    report["all_checks_passed"] = all(report["checks"].values())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 端到端演练（默认离线）")
    parser.add_argument("--gateway", choices=["fake", "real"], default="fake")
    parser.add_argument(
        "--model",
        default=None,
        help="真实模式下覆盖 Agent 模型（等价于 GROWTH_AGENT_MODEL，但显式且不受 .env 优先级影响）",
    )
    args = parser.parse_args()

    if args.model:
        os.environ["GROWTH_AGENT_MODEL"] = args.model

    tmp = HERE / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    db = tmp / f"m2-{args.gateway}.db"
    db.unlink(missing_ok=True)

    user = SimulatedUser()
    with GrowthStore(str(db)) as store:
        store.upsert_user("local", "本地用户")
        report = asyncio.run(run_session(store, build_gateway(args.gateway, user), args.gateway))
    report["requested_model_override"] = args.model
    report["user_question_catalog"] = QUESTION_CATALOG

    out = HERE / f"session-{args.gateway}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(out),
                "all_checks_passed": report["all_checks_passed"],
                "budget": report["budget"],
                "checks": report["checks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    db.unlink(missing_ok=True)
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
