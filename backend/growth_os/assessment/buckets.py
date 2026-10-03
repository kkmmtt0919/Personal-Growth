"""M4-b：证据分桶（PRD §10 的四项 + 反向证据单列）。

| 桶 | 来源（`growth_evidence_type`） | 说明 |
|---|---|---|
| knowledge | `uploaded_doc`、`chat_assertion`（弱） | 笔记 / 论文 / 自述解释 |
| behavior | `probe_result` | 系统现场出题、用户作答 |
| practice | `repo_artifact` | GitHub / ZIP 项目代码 |
| task | `task_submission` | M5 起产生（M4 阶段可为空） |
| 反向 reverse | attack `refutes` / `disputed` | 只压低、不抬升（M4-c 接入） |

**没有桶的类型一律不进绑定**（fail-closed）：`external_ref`（JD / 论文 / 官方文档）
是外部领域参考，不属于"用户的证据"，映射为 `None` 而不是硬塞进知识桶。

映射是**确定性**的、可离线回归 —— 这是 M4-b 闸门的第 5 步；`M4-c` 之后反向证据
在此基础上单独结算，不改动本表。
"""

from __future__ import annotations

BUCKETS = ("knowledge", "behavior", "practice", "task")
"""四个证据桶（PRD §10 的"知识 + 行为 + 实践 + 任务"四项）。"""

EVIDENCE_BUCKET: dict[str, str | None] = {
    "uploaded_doc": "knowledge",
    "chat_assertion": "knowledge",  # 弱证据：可入桶，但不得单独支撑高等级（M4-c 定级时结算）
    "probe_result": "behavior",
    "repo_artifact": "practice",
    "task_submission": "task",
    "external_ref": None,  # 领域参考：不能作为用户能力证据（M3 通道策略同源）
}
"""六个既有证据类型到桶的完整映射（新增类型必须先扩表 + 测试，不得静默落空）。"""


def bucket_for(evidence_type: str | None) -> str | None:
    """某个证据类型进哪个桶；未知类型或领域参考返回 None（fail-closed）。"""
    return EVIDENCE_BUCKET.get(str(evidence_type)) if evidence_type else None


def claim_buckets(entry: dict) -> tuple[set[str], list[str]]:
    """一条主张的（桶集合, 未映射类型清单）。

    逐条证据读 `source.metadata.growth_evidence_type`；出现未映射/未知类型时
    放进第二个返回值 —— 闸门据此拒绝（宁可拒绝，也不静默丢证据）。
    """
    buckets: set[str] = set()
    unmapped: list[str] = []
    for link in entry.get("evidence") or []:
        evidence_type = ((link.get("source") or {}).get("metadata") or {}).get(
            "growth_evidence_type"
        )
        bucket = bucket_for(evidence_type)
        if bucket is None:
            unmapped.append(str(evidence_type))
        else:
            buckets.add(bucket)
    if not entry.get("evidence"):
        unmapped.append("evidence 缺失")
    return buckets, unmapped
