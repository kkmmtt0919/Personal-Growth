"""M4 能力审计（Assessment）—— L2 自有语义层。

已落地：

* **M4-a**：模型契约与 provenance 前置 —— `claim/evidence → assessment draft
  → audit artifact` 的最小闭环；
* **M4-b**：证据绑定与分桶 —— `claim → LLM 提议 → 确定性闸门 → g_capability_claims`，
  proposal / reject / accept 全量留档。

**不做**：星级算法（M4-c）、攻击/反向证据（M4-c）、解释输出（M4-d）、G3 实验（M4-e）、UI。
"""

from .audit import build_audit, write_audit
from .binding import (
    BINDING_SYSTEM,
    BINDING_TASK,
    GATE_STAGES,
    BindingError,
    BindingGate,
    BindingProposalSet,
    ClaimBinder,
    GateDecision,
    ProposalItem,
    build_binding_artifact,
    proposal_id_for,
    render_binding_prompt,
    write_binding_artifact,
)
from .buckets import BUCKETS, EVIDENCE_BUCKET, bucket_for, claim_buckets
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
    "BINDING_SYSTEM",
    "BINDING_TASK",
    "BUCKETS",
    "CHAIN_INCOMPLETE",
    "CONTRACT_VERSION",
    "DOMAIN_REFERENCE",
    "DRAFT",
    "EVIDENCE_BUCKET",
    "GATE_STAGES",
    "INSUFFICIENT",
    "NOT_ADMISSIBLE",
    "OVERREACH",
    "PENDING_DECLARATION",
    "PLAN",
    "AssessmentDrafter",
    "AssessmentError",
    "BindingError",
    "BindingGate",
    "BindingProposalSet",
    "ChainCheck",
    "ClaimBinder",
    "ClaimClassification",
    "GateDecision",
    "ProposalItem",
    "bucket_for",
    "build_audit",
    "build_binding_artifact",
    "check_chain",
    "claim_buckets",
    "classify_claim",
    "proposal_id_for",
    "render_binding_prompt",
    "write_audit",
    "write_binding_artifact",
]
