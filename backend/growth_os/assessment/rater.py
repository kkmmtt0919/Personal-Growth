"""M4-c：评定写入服务 —— 把规则引擎的结论落成维度化的 `g_assessments` 行。

历史语义（用户 2026-10-03 冻结）：

```text
draft ──▶ rated ──▶ history preserved
```

* **不覆盖旧草案**：草案（M4-a/b）与评定（M4-c）是不同的行；
* **等级变化 = 新行**：id 由「对象 + 维度 + 证据集 + 状态 + 等级」派生 ——
  反向证据或新证据改变结论时保留旧行，当前视图用 `GrowthStore.latest_assessment` 查询；
* 重复运行同一结论 → 命中同一行（幂等）。
"""

from __future__ import annotations

from . import rules


class AssessmentRater:
    """对能力点执行一次评定并写入（理解 / 实践各一行）。"""

    def __init__(self, *, store, evidence_store, user_id: str = "local") -> None:
        self.store = store
        self.evidence_store = evidence_store
        self.user_id = user_id

    def rate(self, *, capability_id: str) -> dict:
        report = rules.rate_capability(
            self.store, self.evidence_store, capability_id=capability_id
        )
        written: list[str] = []
        for dimension, body in report["dimensions"].items():
            identifier = self.store.save_assessment(
                {
                    "user_id": self.user_id,
                    "goal_id": report["goal_id"],
                    "capability_id": capability_id,
                    "dimension": dimension,
                    "status": body["status"],
                    "level": body["level"],
                    "rubric": body["rubric"],
                    "rationale": body["rationale"],
                    "claim_ids": body["claim_ids"],
                }
            )
            body["assessment_id"] = identifier
            written.append(identifier)
        report["assessment_ids"] = written
        return report
