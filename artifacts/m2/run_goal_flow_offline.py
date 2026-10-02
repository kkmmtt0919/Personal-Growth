"""M2 端到端演练：澄清 → 确认 → 能力树 → 人工调整 → 再生成（G1 的 dry-run 载体）。

两种模式：

* `--gateway fake`（默认）：脚本化 `FakeGateway`，离线、无密钥、确定性；
  用于把 M2 的验收项在**不花 API 调用**的前提下跑一遍，并产出快照。
* `--gateway real`：走适配层的真实网关（`GROWTH_AGENT_*` / `EVKG_*`），
  用于 M2-d 的 G1 证据。**需要显式授权**：不设 `M2_ALLOW_REAL_MODEL=1`
  时脚本直接退出并打印所需配置，绝不静默发起真实调用。

产物：`artifacts/m2/session-<mode>.json`（会话轨迹 + 运行记录 + 能力树 + 自检结果）。
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
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from growth_os.agent import AgentRuntime, FakeGateway
from growth_os.goal import (
    MAX_ROUNDS,
    CapabilityModelGenerator,
    GoalAgent,
    require_confirmed_goal,
)
from growth_os.store import GrowthStore, capability_id

GOAL_ID = "goal_m2_offline"
USER_TEXT = "我想成为 AI Agent Engineer"
PURPOSE_TEXT = "找一份 AI 应用工程师的工作"

CLARIFICATION_SCRIPT = [
    {
        "question": "AI Agent Engineer 范围比较广。你更偏向应用、算法还是基础设施？",
        "proposed": None,
        "ready_to_confirm": False,
    },
    {
        "question": "主要目标是就业、项目能力，还是长期研究？时间上大概多久？",
        "proposed": None,
        "ready_to_confirm": False,
    },
    {
        "question": "那么我暂时把你的目标定义为「六个月内达到 AI 应用工程师的项目与求职能力」。是否以此为当前目标？",
        "proposed": {
            "direction": "AI 应用工程",
            "purpose": "求职",
            "horizon": "六个月",
            "measurable_result": "完成两个可演示的 Agent 项目并通过 20 道面试题",
        },
        "ready_to_confirm": True,
    },
]

CAPABILITY_TREES = [
    {
        "nodes": [
            *[
                {"path": domain, "target_level": 3, "source_note": "岗位要求共识"}
                for domain in ("LLM 基础", "Agent 架构", "工程化", "评估与测试")
            ],
            *[
                {"path": group, "target_level": 3}
                for group in ("LLM 基础/提示与上下文", "Agent 架构/循环与规划", "工程化/后端与数据", "评估与测试/用例与基准")
            ],
            # 4 个领域 × 4 个能力点 = 16
            *[
                {"path": f"LLM 基础/提示与上下文/能力点 {i}", "target_level": 3, "source_note": "岗位要求"}
                for i in range(1, 5)
            ],
            *[
                {"path": f"Agent 架构/循环与规划/能力点 {i}", "target_level": 4, "source_note": "岗位要求"}
                for i in range(1, 5)
            ],
            *[
                {"path": f"工程化/后端与数据/能力点 {i}", "target_level": 3, "source_note": "岗位要求"}
                for i in range(1, 5)
            ],
            *[
                {"path": f"评估与测试/用例与基准/能力点 {i}", "target_level": 3, "source_note": "岗位要求"}
                for i in range(1, 5)
            ],
        ]
    },
    {
        "nodes": [
            *[
                {"path": domain, "target_level": 4, "source_note": "岗位要求共识"}
                for domain in ("LLM 基础", "Agent 架构", "工程化", "评估与测试")
            ],
            *[
                {"path": group, "target_level": 4}
                for group in ("LLM 基础/提示与上下文", "Agent 架构/循环与规划", "工程化/后端与数据", "评估与测试/用例与基准")
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
    },
]

REAL_MODEL_CONFIG = {
    "GROWTH_AGENT_LLM_PROVIDER / GROWTH_AGENT_MODEL": "可选；留空回落到 EVKG_* 配置",
    "EVKG_LLM_PROVIDER / EVKG_MODEL": "主模型（当前 .env: openai_compatible / glm-5.3）",
    "EVKG_API_KEY": "必需（真实调用）",
    "调用次数（预估）": "目标澄清 3 次 + 能力树生成 2 次 = 5 次结构化调用（含 1 次再生成）",
    "授权开关": "M2_ALLOW_REAL_MODEL=1",
}


def build_gateway(mode: str):
    if mode == "fake":
        return FakeGateway(
            responses={
                "goal_clarification": list(CLARIFICATION_SCRIPT),
                "capability_model": list(CAPABILITY_TREES),
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

    return adapter.agent_gateway()


async def run_session(store: GrowthStore, gateway, mode: str) -> dict:
    counter = itertools.count(1)
    runtime = AgentRuntime(
        store=store, gateway=gateway, agent="goal", id_factory=lambda: f"{mode}_run_{next(counter):03d}"
    )
    agent = GoalAgent(store=store, runtime=runtime)

    turns = [await agent.start(USER_TEXT, goal_id=GOAL_ID)]
    turns.append(await agent.answer(GOAL_ID, "应用方向"))
    turns.append(await agent.answer(GOAL_ID, PURPOSE_TEXT))
    agent.confirm(GOAL_ID, quote="好，就以这个为目标")

    generator = CapabilityModelGenerator(
        store=store,
        gateway=gateway,
        id_factory=lambda: f"{mode}_run_{next(counter):03d}",
    )
    first = await generator.generate(GOAL_ID)
    adjusted_id = capability_id(GOAL_ID, "Agent 架构/循环与规划/能力点 1", "能力点 1")
    generator.adjust(adjusted_id, 5, "离线演练：人工上调，验证再生成保护")
    second = await generator.generate(GOAL_ID)

    rows = store.list_capabilities(GOAL_ID)
    runs = store.list_runs(goal_id=GOAL_ID)
    report = {
        "mode": mode,
        "goal": store.get_goal(GOAL_ID),
        "clarifications": store.list_clarifications(GOAL_ID),
        "turns": [turn.__dict__ for turn in turns],
        "capability_report_first": first.__dict__,
        "capability_report_second": second.__dict__,
        "adjusted_capability": store.get_capability(adjusted_id),
        "capabilities": rows,
        "runs": runs,
        "checks": {
            "rounds_within_cap": len(store.list_clarifications(GOAL_ID)) <= MAX_ROUNDS,
            "goal_confirmed_with_four_elements": require_confirmed_goal(store, GOAL_ID)["status"] == "confirmed",
            "domains_at_least_3": sum(1 for row in rows if row["depth"] == 1) >= 3,
            "capabilities_at_least_12": sum(1 for row in rows if row["depth"] == 3) >= 12,
            "max_depth_3": max(row["depth"] for row in rows) <= 3,
            "all_unverified": all(row["verification_status"] == "unverified" for row in rows),
            "all_current_level_unassessed": all(
                row["current_level"] is None and row["current_level_status"] == "unassessed" for row in rows
            ),
            "adjusted_protected": store.get_capability(adjusted_id)["target_level"] == 5,
            "adjusted_note_kept": store.get_capability(adjusted_id)["adjustment_note"]
            == "离线演练：人工上调，验证再生成保护",
            "lineage_complete": all(
                any(run["id"] == row["generated_by_run_id"] and run["goal_id"] == GOAL_ID for run in runs)
                for row in rows
            ),
            "runs_have_actual_model": all(
                run["provider"] and run["model"] and run["model_source"] == "result" for run in runs
            ),
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

    with GrowthStore(str(db)) as store:
        store.upsert_user("local", "本地用户")
        report = asyncio.run(run_session(store, build_gateway(args.gateway), args.gateway))
    report["requested_model_override"] = args.model

    out = HERE / f"session-{args.gateway}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out), "all_checks_passed": report["all_checks_passed"],
                      "checks": report["checks"]}, ensure_ascii=False, indent=2))
    db.unlink(missing_ok=True)
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
