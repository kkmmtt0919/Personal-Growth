"""M5-b：任务生成闸门（**七步确定性**）—— 提议 → 裁决（通过才落库）。

用户 2026-10-03 冻结（`M5-PLAN.md` v1.0 §4）：

```text
1 schema                 （extra="forbid"；能力判断与排序字段进不来）
2 gap_taskable           （缺口存在 ∧ open ∧ 能力点 active ∧ 有 assessment_id）
3 deliverable_allowed    （维度 ↔ 交付物枚举匹配）
4 acceptance_verifiable  （acceptance_type 枚举 + 文本 ≥8 字符 + 反例模式）
5 est_minutes_range      （10–600；越界只做**形式夹取**并记 adjustment_note）
6 duplicate              （同缺口存在 proposed/active/blocked 任务 → 拒）
7 persisted              （唯一写入点：store.create_task → status='proposed'）
```

纪律（与 M4-b 同构）：

* **闸门是 validator，不是第二个生成器**：只允许 `est_minutes` 形式夹取；
  **禁止**改写 title / objective / acceptance（不发明内容）；
* **declined 是运行结果、不是任务状态**：LLM 无法为该缺口设计可验收任务时给出
  `decline_reason` → 记 `declined` + reason，不落 `g_tasks`；
* **LLM 输出没有直接落库路径**：唯一写库位置是第 7 步；测试断言"新增行数 == accepted 数"；
* **Generator 不直接拥有 `create_task` 权限**：`generator → TaskProposal → gate → create_task()`。
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ..store import (
    DIMENSION_DELIVERABLE_TYPES,
    TASK_ACCEPTANCE_ANTI_PATTERNS,
    TASK_EST_MINUTES_RANGE,
)

TASK_GATE_STAGES = (
    "schema",
    "gap_taskable",
    "deliverable_allowed",
    "acceptance_verifiable",
    "est_minutes_range",
    "duplicate",
    "persisted",
)
"""七步闸门（固定顺序）。`declined` 不是闸门步骤，而是运行结果（LLM 弃权）。"""

DECLINED_STAGE = "declined"

FORBIDDEN_TASK_FIELDS = (
    "expected_level",
    "confidence",
    "difficulty_score",
    "priority",
    "priority_score",
    "learning_value",
    "level",
    "score",
    "rating",
)
"""禁止字段（用户 2026-10-03 冻结）：能力判断（约束 ①）与任务排序（实现约束 ③）。

由 `TaskProposal(extra="forbid")` 结构性拒绝；另有静态检查锁定"这些名字只出现在本常量里"。
"""


class TaskGenerationError(RuntimeError):
    """生成器入参或运行前提不成立。"""


class TaskProposal(BaseModel):
    """LLM 提议的最小形状 —— 多一个字段都进不来（含能力判断与排序字段）。"""

    model_config = ConfigDict(extra="forbid")

    title: str
    objective: str
    deliverable_type: Literal["markdown", "code", "archive", "probe_answer"]
    est_minutes: int
    acceptance_type: Literal["artifact_check", "test_run", "probe_rubric"]
    acceptance: str
    decline_reason: str | None = None


def proposal_id_for(run_id: str, index: int, gap_id: str) -> str:
    seed = f"{run_id}:{index}:{gap_id}"
    return "tpr_" + hashlib.sha256(seed.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class TaskGateDecision:
    proposal_id: str
    gap_id: str
    capability_id: str | None
    accepted: bool
    gate_stage: str
    reject_reason: str | None
    stages_passed: tuple[str, ...]
    task_id: str | None
    adjustment_note: str | None
    run_id: str
    timestamp: str
    proposer: str | None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["stages_passed"] = list(self.stages_passed)
        return payload


class TaskGate:
    """七步确定性闸门：提议 → 裁决（通过才落库）。"""

    def __init__(self, *, store, goal_id: str, user_id: str = "local") -> None:
        self.store = store
        self.goal_id = goal_id
        self.user_id = user_id

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _decision(
        self,
        *,
        proposal_id: str,
        gap_id: str,
        capability_id: str | None,
        accepted: bool,
        gate_stage: str,
        reject_reason: str | None,
        task_id: str | None,
        adjustment_note: str | None,
        run_id: str,
        stages_passed: list[str],
        proposer: str | None,
    ) -> TaskGateDecision:
        return TaskGateDecision(
            proposal_id=proposal_id,
            gap_id=gap_id,
            capability_id=capability_id,
            accepted=accepted,
            gate_stage=gate_stage,
            reject_reason=reject_reason,
            stages_passed=tuple(stages_passed),
            task_id=task_id,
            adjustment_note=adjustment_note,
            run_id=run_id,
            timestamp=self._now(),
            proposer=proposer,
        )

    def evaluate(
        self,
        proposal: dict,
        *,
        gap_id: str,
        run_id: str,
        index: int = 0,
        proposer: str | None = None,
    ) -> TaskGateDecision:
        """对一条提议执行七步闸门；任何一步失败都立即返回（不落库）。"""
        raw = dict(proposal)
        proposal_id = proposal_id_for(run_id, index, gap_id)
        passed: list[str] = []

        # 1) schema：只允许七字段；缺字段 / 多字段（能力判断、排序字段）都在这里被拒
        try:
            item = TaskProposal.model_validate(raw)
        except ValidationError as error:
            detail = "；".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in error.errors()[:3]
            )
            return self._decision(
                proposal_id=proposal_id,
                gap_id=gap_id,
                capability_id=None,
                accepted=False,
                gate_stage="schema",
                reject_reason=f"提议 schema 不合法：{detail}",
                task_id=None,
                adjustment_note=None,
                run_id=run_id,
                stages_passed=passed,
                proposer=proposer,
            )
        passed.append("schema")

        # 弃权（运行结果，不是任务状态）：LLM 明确表示无法设计可验收任务
        if item.decline_reason and item.decline_reason.strip():
            return self._decision(
                proposal_id=proposal_id,
                gap_id=gap_id,
                capability_id=None,
                accepted=False,
                gate_stage=DECLINED_STAGE,
                reject_reason=item.decline_reason.strip(),
                task_id=None,
                adjustment_note=None,
                run_id=run_id,
                stages_passed=passed,
                proposer=proposer,
            )

        # 2) gap_taskable：缺口存在 ∧ open ∧ 能力点 active ∧ provenance 完整（assessment_id）
        gap = self.store.get_gap(gap_id)
        if gap is None:
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=None, accepted=False,
                gate_stage="gap_taskable", reject_reason=f"未知缺口: {gap_id}",
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        capability_id = gap["capability_id"]
        if gap["status"] != "open":
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="gap_taskable",
                reject_reason=f"缺口不可生成任务（status={gap['status']}）",
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        capability = self.store.get_capability(capability_id)
        if capability is None or capability["status"] != "active":
            actual = capability["status"] if capability else "missing"
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="gap_taskable",
                reject_reason=f"能力点非 active（{actual}）",
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        if not str(gap["assessment_id"] or "").strip():
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="gap_taskable",
                reject_reason="缺口缺少评定来源（assessment_id 为空）—— provenance 不完整",
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        passed.append("gap_taskable")

        # 3) deliverable_allowed：维度 ↔ 交付物枚举匹配
        allowed = DIMENSION_DELIVERABLE_TYPES[gap["dimension"]]
        if item.deliverable_type not in allowed:
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="deliverable_allowed",
                reject_reason=(
                    f"{gap['dimension']} 缺口的交付物只允许 {allowed}：收到 {item.deliverable_type!r}"
                ),
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        passed.append("deliverable_allowed")

        # 4) acceptance_verifiable：文本可操作 + 不命中反例模式
        acceptance = item.acceptance.strip()
        if len(acceptance) < 8:
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="acceptance_verifiable",
                reject_reason="acceptance 必须写明可操作的验收方式（≥8 字符）",
                task_id=None, adjustment_note=None, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        for text, label in ((item.title, "title"), (item.objective, "objective"), (acceptance, "acceptance")):
            hit = next((marker for marker in TASK_ACCEPTANCE_ANTI_PATTERNS if marker in text), None)
            if hit is not None:
                return self._decision(
                    proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                    gate_stage="acceptance_verifiable",
                    reject_reason=(
                        f"{label} 命中不可验收反例 {hit!r}：任务必须定义产出物与验收方式，"
                        "而不是'去学习 X'（PRD §12）"
                    ),
                    task_id=None, adjustment_note=None, run_id=run_id,
                    stages_passed=passed, proposer=proposer,
                )
        passed.append("acceptance_verifiable")

        # 5) est_minutes_range：越界只做形式夹取（闸门不改写语义）
        low, high = TASK_EST_MINUTES_RANGE
        est_minutes = item.est_minutes
        adjustment_note = None
        if est_minutes < low:
            adjustment_note = f"est_minutes clamped {est_minutes}→{low}"
            est_minutes = low
        elif est_minutes > high:
            adjustment_note = f"est_minutes clamped {est_minutes}→{high}"
            est_minutes = high
        passed.append("est_minutes_range")

        # 6) duplicate：同缺口已有未关闭任务 → 拒（store 层同谓词兜底）
        for task in self.store.list_tasks(gap_id=gap_id):
            if task["status"] in ("proposed", "active", "blocked"):
                return self._decision(
                    proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                    gate_stage="duplicate",
                    reject_reason=(
                        f"该缺口已有未关闭任务（{task['id']}，{task['status']}）—— 不重复生成"
                    ),
                    task_id=None, adjustment_note=adjustment_note, run_id=run_id,
                    stages_passed=passed, proposer=proposer,
                )
        passed.append("duplicate")

        # 7) persisted：唯一写入点
        try:
            task_id = self.store.create_task(
                {
                    "gap_id": gap_id,
                    "title": item.title.strip(),
                    "objective": item.objective.strip(),
                    "deliverable_type": item.deliverable_type,
                    "est_minutes": est_minutes,
                    "acceptance_type": item.acceptance_type,
                    "acceptance": acceptance,
                    "origin": "generated",
                    "generated_by_run_id": run_id,
                }
            )
        except Exception as error:  # noqa: BLE001 - 契约兜底：把 store 的拒绝如实记入裁决
            return self._decision(
                proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=False,
                gate_stage="persisted",
                reject_reason=f"写入被契约拒绝：{type(error).__name__}: {error}",
                task_id=None, adjustment_note=adjustment_note, run_id=run_id,
                stages_passed=passed, proposer=proposer,
            )
        passed.append("persisted")
        return self._decision(
            proposal_id=proposal_id, gap_id=gap_id, capability_id=capability_id, accepted=True,
            gate_stage="persisted", reject_reason=None, task_id=task_id,
            adjustment_note=adjustment_note, run_id=run_id, stages_passed=passed, proposer=proposer,
        )


def build_generation_artifact(report: dict, *, mode: str, db_path: str) -> dict:
    """把一次生成运行整理成只读审计产物（proposal / reject / accept / decline 全量）。"""
    decisions = report["decisions"]
    return {
        "artifact": "m5b-task-generation",
        "mode": mode,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "read_only": True,
        "run_id": report["run_id"],
        "provider": report["provider"],
        "model": report["model"],
        "goal_id": report["goal_id"],
        "gaps": report["gaps"],
        "proposals": report["proposals"],
        "decisions": decisions,
        "accepted_count": sum(1 for item in decisions if item["accepted"]),
        "rejected_count": sum(
            1 for item in decisions if not item["accepted"] and item["gate_stage"] != DECLINED_STAGE
        ),
        "declined_count": sum(1 for item in decisions if item["gate_stage"] == DECLINED_STAGE),
    }


def write_generation_artifact(path, artifact: dict) -> str:
    import json
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)
