"""归属层（M3-a）：一份材料"是不是关于用户本人的证据"，以及它能支撑什么。

设计纪律（`docs/M3-PLAN.md` v1.0 §3，用户定案）：

* 归属是**用户声明的记录**，不是系统推断的结论 —— 系统不得据其他线索自动升级归属；
* 三种取值严格限定：`user_declared` / `user_asserted` / `unknown`；
* **缺失或非法一律按 `unknown` 处理**（fail-closed：宁可"不能支撑"，也不越权支撑）；
* 只写入 `Source.metadata`，不新增 `g_attributions` 表（M3 决策 5）。

与 `growth_channel` 的分工：channel 说"这材料是关于用户的还是关于领域的"，
attribution 说"这材料是不是用户自己交出来的"。消费时两者是**与**关系：
`domain_reference` 通道的材料即使被用户声明过，也只能作外部参考。

本模块只回答"能不能支撑用户的能力断言"，**不回答"能支撑出几星"**（星级是 M4）。
"""

from __future__ import annotations

from typing import Any, Literal

Attribution = Literal["user_declared", "user_asserted", "unknown"]

ATTRIBUTIONS: tuple[str, ...] = ("user_declared", "user_asserted", "unknown")
"""严格限定的三种取值（M3-a）。新增取值必须先改 `M3-PLAN.md` 的决策与消费规则测试。"""

ATTRIBUTION_METADATA_KEY = "growth_attribution"
"""落库键名，与 `growth_evidence_type` / `growth_channel` 并列写在 `Source.metadata` 里。"""

USER_EVIDENCE_CHANNEL = "user_evidence"
DOMAIN_REFERENCE_CHANNEL = "domain_reference"


class AttributionError(RuntimeError):
    """归属取值非法（只允许 `ATTRIBUTIONS` 里的三种）。"""


def validate_attribution(value: str) -> str:
    """校验归属取值；非法即报错（不做静默兜底）。"""
    if value not in ATTRIBUTIONS:
        raise AttributionError(f"未知归属取值: {value!r}；只允许 {ATTRIBUTIONS}")
    return value


def attribution_of(metadata: dict[str, Any] | None) -> str:
    """从 metadata 读归属；**缺失或非法一律返回 `unknown`**（fail-closed）。

    这样做的理由：默认成 `user_declared` 会让"没声明"被读成"用户声明过"，
    正是归属层要防的越权；默认成 `unknown` 只会让材料更保守。
    """
    if not metadata:
        return "unknown"
    value = metadata.get(ATTRIBUTION_METADATA_KEY)
    return value if value in ATTRIBUTIONS else "unknown"


def can_support_user_claim(attribution: str | None, channel: str | None) -> bool:
    """这份材料能否支撑**关于用户本人**的能力断言。

    合取规则（两条都必须满足）：
      1. 通道是 `user_evidence` —— `domain_reference` 只能作外部参考（M3 决策 4/5）；
      2. 归属是 `user_declared` —— 用户口头声称（`user_asserted`）不得单独支撑结论；
         未声明/第三方（`unknown`）永远不能。
    """
    return attribution == "user_declared" and channel == USER_EVIDENCE_CHANNEL


def is_external_reference(channel: str | None) -> bool:
    """是否是外部领域参考（JD / 论文 / 官方文档；不参与用户能力断言）。"""
    return channel == DOMAIN_REFERENCE_CHANNEL
