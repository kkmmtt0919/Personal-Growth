"""M4-c 星级规则引擎（确定性；两个独立维度）。

用户 2026-10-03 冻结的口径：

* **维度不合并**：`knowledge + behavior → understanding`；`practice + task → practice`；
* 基线规则：

  | 维度 | 证据 | 等级 |
  |---|---|---|
  | 理解 | 仅 `chat_assertion` | insufficient_evidence |
  | 理解 | `uploaded_doc` | 2 |
  | 理解 | `uploaded_doc` + `probe_result` | 3 |
  | 实践 | 无实践证据 | insufficient_evidence |
  | 实践 | `repo_artifact` | 3 |
  | 实践 | `repo_artifact` + `task_submission` | 4 |
  | 实践 | 优化 / 诊断 / 设计取舍**显式信号** | 5 |

* **反向证据结算**：`broken` → 主张不计入；`refutes` / `disputed` → 该维度封顶 ≤2；
  `weakened` → 封顶 ≤3；**封顶只作用于该主张覆盖的维度**（不跨维度污染）；
* **D6 纪律**：不读取主张的分级分数作为定级输入；等级只由证据桶、显式信号与反向裁决决定；
* **不允许 LLM 给等级**：本模块是纯函数 + 只读输入，任何模型输出都必须先经过
  M4-b 的确定性闸门落到 `g_capability_claims`，才可能进入本引擎。

规则版本：`m4c-1`（变更必须先改本文件与 `tests/test_assessment_rules.py`）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..evidence import adapter
from .buckets import claim_buckets
from .contract import classify_claim

RULES_CONTRACT_VERSION = "m4c-1"

UNDERSTANDING = "understanding"
PRACTICE = "practice"
DIMENSIONS = (UNDERSTANDING, PRACTICE)

RATED = "rated"
INSUFFICIENT = "insufficient_evidence"
LEVEL_RANGE = (1, 5)

BUCKET_DIMENSION = {
    "knowledge": UNDERSTANDING,
    "behavior": UNDERSTANDING,
    "practice": PRACTICE,
    "task": PRACTICE,
}

PRACTICE_SIGNAL_KEY = "growth_practice_signal"
PRACTICE_SIGNALS = ("optimization", "diagnosis", "design_tradeoff")
"""level 5 的**显式承载**：优化 / 诊断 / 设计取舍。

**不允许**由项目规模、代码量、时间长度或任何模型分值推导 —— 只有携带该显式信号的
主张才可能把实践推到 5（未来的 M5 任务提交可以设置它）。"""

REVERSE_CAPS = {
    "refutes": 2,
    "disputed": 2,
    "weakened": 3,
}
"""反向证据封顶值（按维度作用；`broken` 不走封顶而是直接剔除主张）。"""


@dataclass(frozen=True)
class ClaimContribution:
    """一条已绑定主张对评级的贡献（纯数据，不含任何模型分值）。"""

    claim_id: str
    buckets: tuple[str, ...]
    evidence_types: tuple[str, ...]
    caps: dict[str, int]
    signals: tuple[str, ...]
    excluded_reason: str | None

    @property
    def dimensions(self) -> frozenset[str]:
        return frozenset(BUCKET_DIMENSION[bucket] for bucket in self.buckets)


def _verdicts(entry: dict) -> set[str]:
    found: set[str] = set()
    for attack in entry.get("attacks") or []:
        verdict = (attack.get("verdict") or {}).get("verdict") or attack.get("verdict")
        if verdict:
            found.add(str(verdict))
    return found


def _evidence_types(entry: dict) -> tuple[str, ...]:
    """该主张所引来源的细粒度证据类型（评级需要细粒度：自述 ≠ 笔记）。"""
    types = {
        str(((link.get("source") or {}).get("metadata") or {}).get("growth_evidence_type"))
        for link in entry.get("evidence") or []
    }
    return tuple(sorted(item for item in types if item and item != "None"))


def _has_refuting_evidence(entry: dict) -> bool:
    return any(str(link.get("polarity")) == "refutes" for link in entry.get("evidence") or [])


def _practice_signals(metadata: dict) -> tuple[str, ...]:
    value = metadata.get(PRACTICE_SIGNAL_KEY)
    if value is None:
        return ()
    items = value if isinstance(value, (list, tuple)) else [value]
    return tuple(str(item) for item in items if str(item) in PRACTICE_SIGNALS)


def _base_level(dimension: str, active: list[ClaimContribution]) -> int | None:
    """维度基线：**按能力点级证据集合聚合**（用户冻结的表；未列出的组合不给等级）。

    理解维度按细粒度类型判定：`chat_assertion`（自述）不能单独产生等级，
    必须由 `uploaded_doc`（笔记/文档）起评；`probe_result` 只在已有
    `uploaded_doc` 的前提下把基线抬到 3（"uploaded_doc + probe_result" 是
    证据集合的组合，不要求落在同一张主张上）。
    """
    evidence = {item for contribution in active for item in contribution.evidence_types}
    buckets = {item for contribution in active for item in contribution.buckets}
    signals = {item for contribution in active for item in contribution.signals}
    if dimension == UNDERSTANDING:
        if "uploaded_doc" not in evidence:
            return None
        return 3 if "probe_result" in evidence else 2
    if "task" in buckets:
        return 5 if signals else 4
    if "practice" in buckets:
        return 5 if signals else 3
    return None


def contribution_for(entry: dict) -> ClaimContribution:
    """把一条（已绑定的）主张折算成对评级的贡献；不能用的主张带排除原因。"""
    claim = entry.get("claim") or {}
    claim_id = str(claim.get("id") or "?")
    metadata = claim.get("metadata") or {}

    classification = classify_claim(entry)
    if not classification.admissible:
        reason = classification.reasons[0] if classification.reasons else classification.kind
        return ClaimContribution(
            claim_id, (), (), {}, (), f"准入复核未通过：{classification.kind}（{reason}）"
        )
    buckets, unmapped = claim_buckets(entry)
    if unmapped:
        return ClaimContribution(
            claim_id, (), (), {}, (), f"存在不可入桶的证据类型：{unmapped}"
        )
    verdicts = _verdicts(entry)
    if "broken" in verdicts:
        return ClaimContribution(
            claim_id, tuple(sorted(buckets)), (), {}, (), "攻击裁决 broken：主张不计入"
        )

    dimensions = {BUCKET_DIMENSION[bucket] for bucket in buckets}
    caps: dict[str, int] = {}
    if _has_refuting_evidence(entry):
        for dimension in dimensions:
            caps[dimension] = min(caps.get(dimension, 99), REVERSE_CAPS["refutes"])
    if str(claim.get("status")) == "disputed":
        for dimension in dimensions:
            caps[dimension] = min(caps.get(dimension, 99), REVERSE_CAPS["disputed"])
    if "weakened" in verdicts:
        for dimension in dimensions:
            caps[dimension] = min(caps.get(dimension, 99), REVERSE_CAPS["weakened"])

    return ClaimContribution(
        claim_id=claim_id,
        buckets=tuple(sorted(buckets)),
        evidence_types=_evidence_types(entry),
        caps=caps,
        signals=_practice_signals(metadata),
        excluded_reason=None,
    )


_GAPS = {
    (UNDERSTANDING, 2): "缺少行为证据（现场作答可通过 probe 补足到 3）",
    (PRACTICE, 3): "缺少任务证据（独立完成完整任务可到 4）",
    (PRACTICE, 4): "缺少优化 / 诊断 / 设计取舍的显式信号（可到 5）",
}


def _dimension_report(dimension: str, contributions: list[ClaimContribution]) -> dict:
    active = [
        item
        for item in contributions
        if item.excluded_reason is None and dimension in item.dimensions
    ]
    excluded = [
        {"claim_id": item.claim_id, "reason": item.excluded_reason}
        for item in contributions
        if item.excluded_reason
    ]
    label = "理解" if dimension == UNDERSTANDING else "实践"
    rubric: dict = {
        "contract": RULES_CONTRACT_VERSION,
        "dimension": dimension,
        "supports": [
            {
                "claim_id": item.claim_id,
                "buckets": list(item.buckets),
                "evidence_types": list(item.evidence_types),
                "cap": item.caps.get(dimension),
                "signals": list(item.signals),
            }
            for item in active
        ],
        "excluded": excluded,
        "reverse_evidence": [
            {"claim_id": item.claim_id, "cap": item.caps[dimension]}
            for item in active
            if dimension in item.caps
        ],
    }
    base = _base_level(dimension, active) if active else None
    if base is None:
        if not active:
            detail = "；".join(f"{item['claim_id']}：{item['reason']}" for item in excluded)
            rationale = f"证据不足（insufficient_evidence）：没有通过准入且可入桶的{label}证据"
            if detail:
                rationale += f"（已排除：{detail}）"
        else:
            rationale = (
                f"证据不足（insufficient_evidence）：{label}侧只有不足以起评的证据"
                "（如自述；需要可核对的材料或行为证据）"
            )
        rubric["gaps"] = [f"缺少可起评的{label}证据"]
        return {
            "dimension": dimension,
            "status": INSUFFICIENT,
            "level": None,
            "rationale": rationale,
            "rubric": rubric,
            "claim_ids": [],
        }

    caps = [item.caps[dimension] for item in active if dimension in item.caps]
    cap = min(caps) if caps else None
    level = min(base, cap) if cap is not None else base
    rationale = f"{label}：基线 {base}（{len(active)} 条已绑定主张）"
    if cap is not None and cap < base:
        rationale += f"；反向证据封顶 ≤{cap} → 最终 {level}"
    elif cap is not None:
        rationale += f"；反向证据封顶 ≤{cap}（未改变基线 {level}）"
    gaps = [text for (dim, threshold), text in _GAPS.items() if dim == dimension and level == threshold]
    if gaps:
        rubric["gaps"] = gaps
    return {
        "dimension": dimension,
        "status": RATED,
        "level": level,
        "rationale": rationale,
        "rubric": rubric,
        "claim_ids": [item.claim_id for item in active],
    }


def rate_contributions(contributions: list[ClaimContribution]) -> dict[str, dict]:
    """纯函数：贡献 → 两个维度的评定（同输入同输出，无时间戳、无随机性）。"""
    return {dimension: _dimension_report(dimension, contributions) for dimension in DIMENSIONS}


def rate_capability(store, evidence_store, *, capability_id: str) -> dict:
    """对某个能力点做一次评定（只读；写入由 `AssessmentRater` 负责）。

    只消费**已绑定**的主张（`g_capability_claims.role='supports'`）—— 评级建立在
    经 M4-b 闸门治理过的数据层上，不消费任何未治理的模型输出。
    """
    capability = store.get_capability(capability_id)
    if capability is None:
        raise KeyError(f"未知能力点: {capability_id}")
    if capability.get("status") != "active":
        raise ValueError("只对 active 能力点评定（history + current view）")

    overview = {
        entry["claim"]["id"]: entry
        for entry in adapter.claims_overview(evidence_store)
    }
    contributions: list[ClaimContribution] = []
    for link in store.list_capability_claims(capability_id=capability_id, role="supports"):
        entry = overview.get(link["claim_id"])
        if entry is None:
            contributions.append(
                ClaimContribution(
                    link["claim_id"], (), {}, {}, (), "claim 不在证据库中（引用失效）"
                )
            )
            continue
        contributions.append(contribution_for(entry))

    return {
        "contract": RULES_CONTRACT_VERSION,
        "goal_id": capability["goal_id"],
        "capability_id": capability_id,
        "dimensions": rate_contributions(contributions),
        "contributions": [asdict(item) for item in contributions],
    }
