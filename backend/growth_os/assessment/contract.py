"""M4-a 评估契约：证据准入的**确定性**判定（不做星级、不做 LLM）。

边界（`M4-PLAN.md` v1.0 §9，用户指定）：本步只做模型契约 ——
`draft` / `insufficient_evidence` 两种状态 + 准入判定；**不做星级算法**、
不做 LLM、不做 UI、不接 G3 实验。

三层归属不合并（§3）：source attribution（材料归属）→ claim scope（材料口径）→
capability ownership（本层的评估对象）。准入合取链（§3.2）：

1. 通道 `user_evidence`；
2. 归属 `user_declared`（`user_asserted` 只能作待验证声明；`unknown` 不进）；
3. claim 是材料口径（`growth_claim_scope=material`）；
4. 证据链完整：`claim → evidence → passage → source`，且引文逐字；
5. 不越权；未被攻击推翻（`broken`）——**攻击裁决接入随 M4-c，本契约先留字段**
   （`classify_claim` 的 kind 集合预留扩展，不假装已覆盖）。

所有函数都是纯函数、确定性、可离线回归 —— 这是 G2/G3 要求的"定级不依赖模型随机性"
的最后闸门。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence.attribution import (
    DOMAIN_REFERENCE_CHANNEL,
    USER_EVIDENCE_CHANNEL,
    attribution_of,
)
from ..evidence.claims import check_overreach

CONTRACT_VERSION = "m4a-1"

# -- 分类结果（四类矩阵 + 契约自身的失败态）--------------------------------

ADMISSIBLE = "admissible"
OVERREACH = "overreach"
CHAIN_INCOMPLETE = "chain_incomplete"
PENDING_DECLARATION = "pending_declaration"
DOMAIN_REFERENCE = "domain_reference"
PLAN = "plan"
NOT_ADMISSIBLE = "not_admissible"

MATERIAL_SCOPE = "material"

PLAN_MARKERS = ("计划", "打算", "准备学习", "未来规划", "规划学习", "尚未开始")
"""计划/学习目标表述（用户冻结矩阵第 4 行）：**不是能力证据**。

只在**非材料口径**的主张上判定 —— 材料里引述一份"规划文档"仍然是材料内容，
不因此被排除（那是材料口径的证据，属知识桶）。
"""


@dataclass(frozen=True)
class ChainCheck:
    """`claim → evidence → passage → source` 的逐跳检查结果。"""

    complete: bool
    evidence_rows: int
    passages: int
    sources: int
    quote_verbatim: bool
    missing: tuple[str, ...]


@dataclass(frozen=True)
class ClaimClassification:
    kind: str
    reasons: tuple[str, ...]
    chain: ChainCheck | None = None

    @property
    def admissible(self) -> bool:
        return self.kind == ADMISSIBLE


def check_chain(entry: dict) -> ChainCheck:
    """逐跳检查证据链 + 引文逐字（与 G2 的追溯口径一致）。"""
    evidence = list(entry.get("evidence") or [])
    missing: list[str] = []
    passages = 0
    sources = 0
    quote_verbatim = True
    for link in evidence:
        passage_text = link.get("passage_text") or ""
        if passage_text:
            passages += 1
        else:
            missing.append("passage 缺失")
        if (link.get("source") or {}).get("id"):
            sources += 1
        else:
            missing.append("source 缺失")
        quote = link.get("quote") or ""
        if not quote or quote not in passage_text:
            quote_verbatim = False
    if not evidence:
        missing.append("evidence 缺失")
    return ChainCheck(
        complete=bool(evidence) and not missing and quote_verbatim,
        evidence_rows=len(evidence),
        passages=passages,
        sources=sources,
        quote_verbatim=quote_verbatim,
        missing=tuple(dict.fromkeys(missing)),
    )


def classify_claim(entry: dict) -> ClaimClassification:
    """把一条主张分入（准入 / 越权 / 链不完整 / 待验证 / 领域参考 / 计划 / 不可准入）。

    `entry` 是 `claims_overview` 的一条（含 claim 与 evidence）；只给 claim 时，
    材料口径的主张会因缺少证据链被判 `chain_incomplete`（fail-closed，不误放行）。
    """
    claim = entry.get("claim") or {}
    metadata = claim.get("metadata") or {}

    report = check_overreach(
        statement=claim.get("statement", ""),
        subject=claim.get("subject"),
        predicate=claim.get("predicate"),
    )
    if report.overreach:
        return ClaimClassification(OVERREACH, tuple(report.reasons))

    if metadata.get("growth_claim_scope") != MATERIAL_SCOPE:
        text = " ".join(str(claim.get(key) or "") for key in ("subject", "predicate", "statement"))
        hits = [marker for marker in PLAN_MARKERS if marker in text]
        if hits:
            return ClaimClassification(
                PLAN,
                ("计划/学习目标表述（命中：" + "、".join(hits[:3]) + "）不是能力证据",),
            )
        return ClaimClassification(
            PENDING_DECLARATION,
            ("非材料口径：用户单方声明只能作为待验证声明，不得单独支撑结论",),
        )

    chain = check_chain(entry)
    if not chain.complete:
        return ClaimClassification(
            CHAIN_INCOMPLETE, ("证据链不完整：" + "、".join(chain.missing),), chain
        )

    channels: set[str] = set()
    attributions: set[str] = set()
    for link in entry.get("evidence") or []:
        source_meta = ((link.get("source") or {}).get("metadata")) or {}
        channels.add(str(source_meta.get("growth_channel")))
        attributions.add(attribution_of(source_meta))
    if DOMAIN_REFERENCE_CHANNEL in channels:
        return ClaimClassification(
            DOMAIN_REFERENCE, ("domain_reference 通道的材料不能支撑用户能力",), chain
        )
    if channels != {USER_EVIDENCE_CHANNEL}:
        return ClaimClassification(
            NOT_ADMISSIBLE,
            (f"通道不是 user_evidence（实际：{sorted(channels)}）",),
            chain,
        )
    if attributions != {"user_declared"}:
        kind = PENDING_DECLARATION if attributions == {"user_asserted"} else NOT_ADMISSIBLE
        return ClaimClassification(
            kind, (f"归属不是 user_declared（实际：{sorted(attributions)}）",), chain
        )
    return ClaimClassification(ADMISSIBLE, ("通道 / 归属 / 材料口径 / 证据链全部通过",), chain)
