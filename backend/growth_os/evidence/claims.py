"""越权校验（M3-a 的校验边界）：**"存在证据" ≠ "证明能力"**。

用途：给定一条待写入的主张（claim 的三元组 + 陈述），判断它是否**越权** ——
是否从"材料里有什么"跳成了"用户具备/完成/独立完成什么"。规则见
`docs/M3-PLAN.md` v1.0 §1（用户写死的硬规则）。

边界（用户明确指定）：
* M3-a **只提供检查器与测试**；
* 把它接进写入路径（拒绝、或改写为材料口径）是 **M3-e** 的工作 ——
  本步不提前改抽取/写入流程，也不追改历史数据（M1-c 那条被 M4 推翻的用户口径主张
  留在原处，作为 M3-e 的处理对象）。

判断依据是 claim 的**三元组**，不是陈述的字面：同一条陈述若主语是材料，
就是合规的（"原文描述的项目实现了 RAG 检索服务"），主语是用户则越权
（"用户实现过 RAG 检索服务"）—— 这正是 M1-c 实测到的分界。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

USER_SUBJECT_MARKERS = ("用户", "本人", "我")
"""主语指向用户本人的标记。"""

ACHIEVEMENT_MARKERS = (
    "具备",
    "掌握",
    "精通",
    "擅长",
    "熟练",
    "会用",
    "能独立",
    "实现过",
    "独立实现",
    "完成过",
    "独立完成",
    "负责过",
    "主导",
    "设计过",
    "优化过",
    "做过",
    "写过",
    "开发过",
    "搭建过",
    "部署过",
    "上线过",
    "落地过",
)
"""能力/成就类结论词。这类结论需要"证据够不够"的判定（M4），M3 不得直接产出。"""

LEVEL_PATTERN = re.compile(r"(?:星级|[1-5]\s*/\s*5|[1-5]\s*星|等级\s*[1-5]|水平\s*[1-5])")
"""能力等级/星级表述：属于 M4；出现在用户口径的陈述里即越权。"""


@dataclass(frozen=True)
class OverreachReport:
    overreach: bool
    reasons: tuple[str, ...]


def check_overreach(
    *, statement: str, subject: str | None = None, predicate: str | None = None
) -> OverreachReport:
    """判断一条主张是否越权。**纯函数、确定性**（不用模型判断，可离线回归）。

    返回 `OverreachReport`：`overreach=True` 时 `reasons` 说明命中原因。
    检查偏保守（宁可多报）：这是"拒绝写入"方向的门槛，不是评分器。
    """
    text = statement or ""
    who = subject or ""
    reasons: list[str] = []

    user_scoped = any(marker in who for marker in USER_SUBJECT_MARKERS) or any(
        text.startswith(marker) for marker in USER_SUBJECT_MARKERS
    )
    hits = [marker for marker in ACHIEVEMENT_MARKERS if marker in (predicate or "") or marker in text]
    if user_scoped and hits:
        reasons.append("把材料内容跳成用户的能力/成就结论（命中：" + "、".join(hits[:3]) + "）")
    if user_scoped and LEVEL_PATTERN.search(text):
        reasons.append("为用户给出能力等级/星级表述（能力等级属于 M4 判定）")
    return OverreachReport(overreach=bool(reasons), reasons=tuple(reasons))
