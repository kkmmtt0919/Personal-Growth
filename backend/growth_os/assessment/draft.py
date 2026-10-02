"""M4-a：`claim/evidence → assessment draft` 的最小闭环（无 LLM、无星级）。

流程（`M4-PLAN.md` v1.0 §9）：

```text
claim（候选，调用方给出）
   ↓  classify_claim（确定性准入闸门，§3.2 合取链）
supports / excluded（每条排除都带原因）
   ↓
g_assessments（draft | insufficient_evidence；level 恒为 NULL）
   ↓
g_capability_claims（只写通过准入的绑定，rationale 必填）
```

调用方给出的 `claim_ids` 就是本步的"映射提议"（M4-a 无 LLM；LLM 提议在 M4-b）——
**提议能否落库由确定性闸门决定**，这正是 §6 冻结的"LLM 提议 + 规则闸门"里的闸门半边。
"""

from __future__ import annotations

from ..evidence import adapter
from .contract import ADMISSIBLE, CONTRACT_VERSION, classify_claim

DRAFT = "draft"
INSUFFICIENT = "insufficient_evidence"


class AssessmentError(RuntimeError):
    """assessment 草案阶段的输入不合法。"""


class AssessmentDrafter:
    """把候选主张按准入闸门整理成 assessment 草案。"""

    def __init__(self, *, store, evidence_store, user_id: str = "local") -> None:
        self.store = store
        self.evidence_store = evidence_store
        self.user_id = user_id

    def draft(self, *, capability_id: str, claim_ids: list[str]) -> dict:
        """对某个能力点起草评估（幂等：同一证据集重复运行命中同一行）。"""
        capability = self.store.get_capability(capability_id)
        if capability is None:
            raise AssessmentError(f"未知能力点: {capability_id}")
        if capability.get("status") != "active":
            raise AssessmentError(
                "只对 active 能力点起草评估（history + current view：superseded/archived 节点不参与）"
            )

        overview = {
            entry["claim"]["id"]: entry for entry in adapter.claims_overview(self.evidence_store)
        }
        unknown = [claim_id for claim_id in claim_ids if claim_id not in overview]
        if unknown:
            raise AssessmentError(f"引用了未知 claim: {unknown}")

        supports: list[str] = []
        excluded: list[dict] = []
        for claim_id in claim_ids:
            result = classify_claim(overview[claim_id])
            if result.kind == ADMISSIBLE:
                supports.append(claim_id)
            else:
                excluded.append(
                    {"claim_id": claim_id, "kind": result.kind, "reasons": list(result.reasons)}
                )

        status = DRAFT if supports else INSUFFICIENT
        if supports:
            rationale = (
                f"证据准入通过 {len(supports)} 条；等级待评定"
                "（M4-a 只产出草案，不产出星级）"
            )
        else:
            detail = "；".join(
                f"{item['claim_id']}：{item['reasons'][0]}" for item in excluded
            ) or "未提供候选主张"
            rationale = f"证据不足（evidence insufficient）：{detail}"

        rubric = {
            "contract": CONTRACT_VERSION,
            "supports": supports,
            "excluded": excluded,
            "level_status": "not_rated_in_m4a",
        }
        assessment = self.store.save_assessment_draft(
            {
                "user_id": self.user_id,
                "goal_id": capability["goal_id"],
                "capability_id": capability_id,
                "status": status,
                "rubric": rubric,
                "rationale": rationale,
                "claim_ids": supports,
            }
        )
        for claim_id in supports:
            self.store.link_capability_claim(
                capability_id,
                claim_id,
                role="supports",
                rationale=f"M4-a 确定性准入通过（contract {CONTRACT_VERSION}）",
            )
        return {
            "assessment_id": assessment,
            "capability_id": capability_id,
            "goal_id": capability["goal_id"],
            "status": status,
            "level": None,
            "supports": supports,
            "excluded": excluded,
            "rationale": rationale,
            "rubric": rubric,
        }
