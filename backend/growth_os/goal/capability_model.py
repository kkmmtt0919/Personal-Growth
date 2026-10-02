"""能力树生成：`confirmed goal` → 三层能力模型（`M2-PLAN.md` 决策 1/4）。

结构要求（有测试锁定）：**最多 3 层**（领域 → 能力组 → 能力点）、**≥3 个领域**、
**≥12 个能力点**。不满足就整体拒绝，不写半棵树 —— 半个能力模型比没有更难发现。

四条语义（来自冻结计划）：

1. **`target_level` 是目标要求，不是用户现状**：写入时 `current_level` 恒为 NULL、
   `current_level_status` 恒为 `unassessed`（存储层强制，见 `growth_store`）。
2. **未校验必须可见**：`verification_status` 一律 `unverified`，`source_note` 会被
   追加"未校验"标记 —— **模型不能把 LLM 生成说成已验证的行业标准**。
3. **人工调整受保护**：`origin=adjusted` 的行在重新生成时保留目标值与调整理由，
   并在返回的报告里列在 `protected_adjusted`（让"被保护了什么"可见）。
4. **可追溯**：每个节点写入 `generated_by_run_id`，可沿
   `capability → goal → agent_run` 走通（AC9）。

生成只做一件事：调模型 → 校验形状 → 落库。提示词不承担校验职责。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..agent import AgentContext, AgentRuntime, StructuredGateway
from ..store import TARGET_LEVEL_RANGE, GrowthStore, GrowthStoreError, capability_id
from .agent import require_confirmed_goal

MAX_DEPTH = 3
MIN_DOMAINS = 3
MIN_CAPABILITIES = 12
TASK_NAME = "capability_model"

UNVERIFIED_MARK = "unverified（LLM 生成，未校验外部来源）"
"""`source_note` 必须携带的标记 —— 决策 1 的"不得伪装已验证"。"""

CAPABILITY_SYSTEM = f"""你是能力模型构建者。给定一个已确认的目标，产出一棵三层能力树：
第 1 层是领域（domain），第 2 层是能力组，第 3 层是能力点。

硬性要求：
1. **必须用满三层，第三层才算能力点**：
   - 第 1 层：至少 {MIN_DOMAINS} 个领域；
   - 第 2 层：每个领域下至少 2 个能力组；
   - 第 3 层：每个能力组下至少 2 个能力点，**第三层总数 ≥ {MIN_CAPABILITIES}**
     （最少 3×2×2 = 12）；每个能力点的 path 必须含**两个**「/」。
   - 合格示例："LLM 基础/Prompt 工程/结构化输出设计" —— 第三层的"结构化输出设计"才是能力点。
   - 反例（不合格）："LLM 基础/Prompt 工程" —— 这只是能力组，不能算能力点。
2. 每个节点的 path 用「/」连接，父节点必须同时给出。
   **节点名内部不得出现「/」或「／」**（它们只能作为层级分隔符）；
   需要并列时用「、」或「或」，例如用 `框架使用（LangChain、LlamaIndex）`，
   不要写 `框架使用（LangChain/LlamaIndex）`（后者会被拆成两层，导致整棵树被拒绝）。
3. target_level 是该能力对**目标的要求等级**（{TARGET_LEVEL_RANGE[0]}–{TARGET_LEVEL_RANGE[1]}），
   不是用户当前水平 —— 用户现状尚未评估，不得填写。
4. source_note 如实说明你的依据来源；你**不能**声称某个来源已经过核实 ——
   生成结果一律标记为未校验。
5. 输出前自检：数一数第三层节点是否 ≥ {MIN_CAPABILITIES}、层数是否恰好 3 层，
   以及每个 path 中「/」的个数是否**恰好等于 2**（三层 = 两个分隔符）。
   不要输出与目标无关的通用技能凑数；宁可少而准，但必须满足数量下限。"""


class CapabilityModelError(GrowthStoreError):
    """能力模型生成过程中的错误。"""


class CapabilityTreeShapeError(CapabilityModelError):
    """模型产出的树不满足冻结的结构要求（整体拒绝，不写半棵树）。"""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("能力树不满足结构要求：" + "；".join(issues))


class CapabilityNode(BaseModel):
    """一个能力节点：路径即身份（`name` / `depth` 由路径推导，避免自相矛盾）。"""

    path: str
    target_level: int
    source_note: str | None = None

    @property
    def segments(self) -> list[str]:
        return [part.strip() for part in self.path.split("/") if part.strip()]

    @property
    def name(self) -> str:
        return self.segments[-1]

    @property
    def depth(self) -> int:
        return len(self.segments)

    @property
    def parent_path(self) -> str | None:
        return "/".join(self.segments[:-1]) or None


class CapabilityTree(BaseModel):
    nodes: list[CapabilityNode]


@dataclass(frozen=True)
class GenerationReport:
    goal_id: str
    run_id: str
    domains: int
    groups: int
    capabilities: int
    protected_adjusted: list[dict[str, Any]]
    written: list[str]


def validate_shape(nodes: list[CapabilityNode]) -> list[str]:
    """返回结构问题清单（空 = 通过）。校验先于写入。"""
    issues: list[str] = []
    if not nodes:
        return ["能力树为空"]
    paths = [node.path for node in nodes]
    duplicates = {path for path in paths if paths.count(path) > 1}
    if duplicates:
        issues.append(f"重复路径: {sorted(duplicates)[:3]}")
    known = set(paths)
    for node in nodes:
        if not node.segments:
            issues.append("存在空路径节点")
            continue
        if node.depth > MAX_DEPTH:
            issues.append(f"层数超限（{node.depth}）: {node.path}")
        if node.depth > 1 and node.parent_path not in known:
            issues.append(f"缺少父节点: {node.path}")
        if not (TARGET_LEVEL_RANGE[0] <= node.target_level <= TARGET_LEVEL_RANGE[1]):
            issues.append(f"target_level 越界（{node.target_level}）: {node.path}")
        if node.name in {"", "-"}:
            issues.append(f"节点名不合法: {node.path}")
    domains = sum(1 for node in nodes if node.depth == 1)
    capabilities = sum(1 for node in nodes if node.depth == MAX_DEPTH)
    if domains < MIN_DOMAINS:
        issues.append(f"领域数不足：{domains} < {MIN_DOMAINS}")
    if capabilities < MIN_CAPABILITIES:
        issues.append(f"能力点数不足：{capabilities} < {MIN_CAPABILITIES}")
    return issues


def render_capability_prompt(goal: dict, external_refs: list[str]) -> str:
    lines = [
        "已确认目标：",
        f"  标题：{goal['title']}",
        f"  方向：{goal['direction']}",
        f"  目的：{goal['purpose']}",
        f"  时间周期：{goal['horizon']}",
        f"  可衡量结果：{goal['measurable_result']}",
        f"  用户原话：{goal.get('source_quote') or '-'}",
    ]
    if external_refs:
        lines.append("外部参考（用户提供的领域资料）：")
        lines.extend(f"  - {item}" for item in external_refs)
    else:
        lines.append("外部参考：无（本次仅凭模型知识生成，结果将标记为未校验）")
    return "\n".join(lines)


class CapabilityModelGenerator:
    """一次生成的完整流程：校验前置门 → 调模型 → 校验形状 → 落库。"""

    def __init__(
        self,
        *,
        store: GrowthStore,
        gateway: StructuredGateway,
        user_id: str = "local",
        id_factory=None,
    ) -> None:
        self.store = store
        self.runtime = AgentRuntime(
            store=store, gateway=gateway, agent="capability_model", user_id=user_id, id_factory=id_factory
        )

    async def generate(self, goal_id: str, *, external_refs: list[str] | None = None) -> GenerationReport:
        goal = require_confirmed_goal(self.store, goal_id)  # AC2：未确认一律拒绝
        outcome = await self.runtime.call_model_with_run(
            system=CAPABILITY_SYSTEM,
            user=render_capability_prompt(goal, list(external_refs or [])),
            schema=CapabilityTree,
            task=TASK_NAME,
            context=AgentContext(
                user_id=self.runtime.user_id,
                goal_id=goal_id,
                correlation_id=goal_id,
                notes={"目标": goal["title"]},
            ),
        )
        nodes = outcome.result.value.nodes
        issues = validate_shape(nodes)
        if issues:
            # 整体拒绝：不写半棵树（部分写入的能力模型比没有更难发现）。
            raise CapabilityTreeShapeError(issues)

        protected: list[dict[str, Any]] = []
        written: list[str] = []
        for node in nodes:
            capability = capability_id(goal_id, node.path, node.name)
            existing = self.store.get_capability(capability)
            if existing is not None and existing["origin"] == "adjusted":
                protected.append(
                    {
                        "id": capability,
                        "path": node.path,
                        "stored": existing["target_level"],
                        "proposed": node.target_level,
                    }
                )
            base = (node.source_note or "模型未提供来源说明").strip()
            self.store.upsert_capability(
                {
                    "id": capability,
                    "goal_id": goal_id,
                    "parent_id": capability_id(goal_id, node.parent_path, node.parent_path.split("/")[-1])
                    if node.parent_path
                    else None,
                    "name": node.name,
                    "path": node.path,
                    "depth": node.depth,
                    "target_level": node.target_level,
                    "verification_status": "unverified",
                    "source_note": f"{base}；校验状态：{UNVERIFIED_MARK}",
                    "generated_by_run_id": outcome.run_id,
                }
            )
            written.append(capability)

        rows = self.store.list_capabilities(goal_id)
        return GenerationReport(
            goal_id=goal_id,
            run_id=outcome.run_id,
            domains=sum(1 for row in rows if row["depth"] == 1),
            groups=sum(1 for row in rows if row["depth"] == 2),
            capabilities=sum(1 for row in rows if row["depth"] == MAX_DEPTH),
            protected_adjusted=protected,
            written=written,
        )

    def adjust(self, capability: str, target_level: int, note: str) -> None:
        """人工调整（`origin=adjusted` + 修改来源）—— 生成器不碰这个动作。"""
        self.store.adjust_capability(capability, target_level, note)
