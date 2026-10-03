"""M4 能力审计（Assessment）—— L2 自有语义层。

已落地：

* **M4-a**：模型契约与 provenance 前置 —— `claim/evidence → assessment draft
  → audit artifact` 的最小闭环；
* **M4-b**：证据绑定与分桶 —— `claim → LLM 提议 → 确定性闸门 → g_capability_claims`，
  proposal / reject / accept 全量留档；
* **M4-c**：评级与反向证据 —— 两维度（理解 / 实践）星级规则引擎 + attack 结算
  + `rated` 写入路径（历史保留）；
* **M4-d**：可解释输出 —— 能力评估报告（支持 / 不足 / 攻击结果 + 逐字引文）
  + 维度化 `current_level` 回填与重建校验。

**不做**：缺口表（`g_gaps`）与 G3 实验（M4-e）、任务（M5）、Memory（M6）、UI（M8）。
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
from .rater import AssessmentRater
from .report import REPORT_LIMITATIONS, build_report, render_report, write_report
from .rules import (
    BUCKET_DIMENSION,
    DIMENSIONS,
    LEVEL_RANGE,
    PRACTICE,
    PRACTICE_SIGNAL_KEY,
    PRACTICE_SIGNALS,
    RATED,
    REVERSE_CAPS,
    RULES_CONTRACT_VERSION,
    UNDERSTANDING,
    ClaimContribution,
    contribution_for,
    rate_capability,
    rate_contributions,
)

__all__ = [
    "ADMISSIBLE",
    "BINDING_SYSTEM",
    "BINDING_TASK",
    "BUCKETS",
    "BUCKET_DIMENSION",
    "CHAIN_INCOMPLETE",
    "CONTRACT_VERSION",
    "DIMENSIONS",
    "DOMAIN_REFERENCE",
    "DRAFT",
    "EVIDENCE_BUCKET",
    "GATE_STAGES",
    "INSUFFICIENT",
    "LEVEL_RANGE",
    "NOT_ADMISSIBLE",
    "OVERREACH",
    "PENDING_DECLARATION",
    "PLAN",
    "PRACTICE",
    "PRACTICE_SIGNALS",
    "PRACTICE_SIGNAL_KEY",
    "RATED",
    "REPORT_LIMITATIONS",
    "REVERSE_CAPS",
    "RULES_CONTRACT_VERSION",
    "UNDERSTANDING",
    "AssessmentDrafter",
    "AssessmentError",
    "AssessmentRater",
    "BindingError",
    "BindingGate",
    "BindingProposalSet",
    "ChainCheck",
    "ClaimBinder",
    "ClaimClassification",
    "ClaimContribution",
    "GateDecision",
    "ProposalItem",
    "bucket_for",
    "build_audit",
    "build_binding_artifact",
    "build_report",
    "check_chain",
    "claim_buckets",
    "classify_claim",
    "contribution_for",
    "proposal_id_for",
    "rate_capability",
    "rate_contributions",
    "render_binding_prompt",
    "render_report",
    "write_audit",
    "write_binding_artifact",
    "write_report",
]
