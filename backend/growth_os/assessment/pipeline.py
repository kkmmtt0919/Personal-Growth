"""M4-e：能力评定统一编排（确定性、**无 LLM、无网络、无隐式副作用**）。

用户 2026-10-03 冻结的固定顺序：

```text
bind（显式输入，已在编排之外完成）
  ↓
attack（显式输入，已在编排之外完成）
  ↓
rate → report → apply_assessment_levels → verify_assessment_levels
     → apply_gaps → verify_gaps
```

纪律：

* LLM 阶段（绑定提议、真实 attack）**不在编排内** —— 编排只消费已治理的数据层
  （`g_capability_claims` 桥表 + 攻击裁决），保证"评级不依赖任何模型输出"；
* `verify_*` 失败即 **fail-stop**：不继续写缺口、不返回"看起来成功"的结果；
* 幂等：同证据集重复运行 → 同评定行（id 派生）与同缺口行（唯一键 upsert）；
* 返回结构化 summary（评定行 / 回填值 / 缺口 / 报告路径），供运行器归档。
"""

from __future__ import annotations

from pathlib import Path

from .rater import AssessmentRater
from .report import build_report, write_report

PIPELINE_VERSION = "m4e-1"
"""编排契约版本（产物中记录，便于复算时对照）。"""


class PipelineError(RuntimeError):
    """编排的自校验失败（fail-stop，不做静默继续）。"""


def assess_capability(
    store,
    evidence_store,
    *,
    capability_id: str,
    report_directory: str | Path | None = None,
    report_stem: str | None = None,
    generated_by: str | None = None,
) -> dict:
    """对单个能力点执行一次完整编排（只读证据层；写入 `g_assessments` / `g_gaps` / 回填列）。"""
    rater = AssessmentRater(store=store, evidence_store=evidence_store)
    rating = rater.rate(capability_id=capability_id)

    report = build_report(
        store, evidence_store, capability_id=capability_id, generated_by=generated_by
    )
    report_paths: dict[str, str] = {}
    if report_directory is not None:
        report_paths = write_report(
            report,
            directory=report_directory,
            stem=report_stem or f"report-{capability_id}",
        )

    levels = store.apply_assessment_levels(capability_id)
    level_check = store.verify_assessment_levels(capability_id)
    if not level_check["consistent"]:
        raise PipelineError(
            "回填重建校验不一致（fail-stop）："
            f"expected={level_check['expected']} stored={level_check['stored']}"
        )

    gap_result = store.apply_gaps(capability_id)
    gap_check = store.verify_gaps(capability_id)
    if not gap_check["consistent"]:
        raise PipelineError(
            "缺口重建校验不一致（fail-stop）："
            f"expected={gap_check['expected']} stored={gap_check['stored']}"
        )

    return {
        "contract": PIPELINE_VERSION,
        "goal_id": rating["goal_id"],
        "capability_id": capability_id,
        "assessment_ids": rating["assessment_ids"],
        "dimensions": {
            dimension: {
                "status": body["status"],
                "level": body["level"],
                "assessment_id": body["assessment_id"],
            }
            for dimension, body in rating["dimensions"].items()
        },
        "levels": levels,
        "level_verification": level_check,
        "gaps": gap_result["gaps"],
        "closed_gaps": gap_result["closed"],
        "gap_verification": gap_check,
        "report": report,
        "report_paths": report_paths,
    }
