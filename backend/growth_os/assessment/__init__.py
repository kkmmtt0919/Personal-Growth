"""M4 能力审计（Assessment）—— L2 自有语义层。

当前范围（M4-a）：模型契约与 provenance 前置 —— `claim/evidence → assessment draft
→ audit artifact` 的最小闭环。**不做星级算法、不做 LLM、不做 UI**（`M4-PLAN.md` v1.0 §9）。
"""

from .audit import build_audit, write_audit
from .contract import (
    ADMISSIBLE,
    CHAIN_INCOMPLETE,
    CONTRACT_VERSION,
    DOMAIN_REFERENCE,
    NOT_ADMISSIBLE,
    OVERREACH,
    PENDING_DECLARATION,
    PLAN,
    ChainCheck,
    ClaimClassification,
    check_chain,
    classify_claim,
)
from .draft import DRAFT, INSUFFICIENT, AssessmentDrafter, AssessmentError

__all__ = [
    "ADMISSIBLE",
    "CHAIN_INCOMPLETE",
    "CONTRACT_VERSION",
    "DOMAIN_REFERENCE",
    "DRAFT",
    "INSUFFICIENT",
    "NOT_ADMISSIBLE",
    "OVERREACH",
    "PENDING_DECLARATION",
    "PLAN",
    "AssessmentDrafter",
    "AssessmentError",
    "ChainCheck",
    "ClaimClassification",
    "build_audit",
    "check_chain",
    "classify_claim",
    "write_audit",
]
