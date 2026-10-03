"""M4-b：claim ↔ capability 绑定（LLM 提议 + 确定性闸门 + 映射落库）。

边界（`M4-PLAN.md` v1.0 §6；用户 2026-10-02 冻结）：

* **LLM 仅作为候选绑定提议器**：可提议能力类别、解释、关联关系；
  **不得决定用户能力等级、不得补充不存在证据、不得修改 attribution**；
* **确定性闸门负责最终准入**：八步固定顺序 ——
  `schema → claim_exists → capability_exists → capability_active →
  bucket_allowed → attribution_unchanged → duplicate → persisted`；
  **失败不落库**，每一步的结论都写进决策对象；
* **proposal / reject / accept 全量留档**：供 `artifacts/m4b/` 只读产物使用
  （字段：`proposal_id` / `reject_reason` / `gate_stage` / `timestamp` / `run_id`）；
* proposal schema 只有 `claim_id` / `capability_path` / `rationale`
  （`run_id` 由运行记录补），**禁止置信度 / 等级 / 分值字段** ——
  `extra="forbid"`，模型加了也进不来（schema 阶段直接拒绝）。

验收重点不是"LLM 能不能映射"，而是证明：
**LLM 可以参与知识结构构建，但不能越过确定性治理边界。**
`propose()` 只返回决策与落库结果；LLM 输出**没有**任何直接落库路径。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from ..agent import AgentContext, AgentRuntime, StructuredGateway
from ..evidence import adapter
from .buckets import claim_buckets
from .contract import classify_claim

BINDING_TASK = "claim_binding"

GATE_STAGES = (
    "schema",
    "claim_exists",
    "capability_exists",
    "capability_active",
    "bucket_allowed",
    "attribution_unchanged",
    "duplicate",
    "persisted",
)
"""闸门固定顺序（用户 2026-10-02 指定）；`persisted` 只在全部通过后到达。"""


class BindingError(RuntimeError):
    """绑定阶段的输入不合法（候选集/目标树问题，非闸门拒绝）。"""


class ProposalItem(BaseModel):
    """LLM 提议的最小形状 —— 多一个字段都进不来（含 confidence / level / score）。"""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    capability_path: str
    rationale: str


class BindingProposalSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[ProposalItem] = []


def proposal_id_for(run_id: str, index: int, claim_id: str, capability_path: str) -> str:
    seed = f"{run_id}:{index}:{claim_id}:{capability_path}"
    return "prp_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class GateDecision:
    proposal_id: str
    claim_id: str
    capability_path: str
    rationale: str
    accepted: bool
    gate_stage: str
    reject_reason: str | None
    capability_id: str | None
    run_id: str
    timestamp: str
    stages_passed: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["stages_passed"] = list(self.stages_passed)
        return payload


class BindingGate:
    """八步确定性闸门：提议 → 裁决（通过才落库）。"""

    def __init__(
        self,
        *,
        store,
        evidence_store,
        goal_id: str,
        user_id: str = "local",
        candidate_claim_ids: list[str] | None = None,
    ) -> None:
        self.store = store
        self.evidence_store = evidence_store
        self.goal_id = goal_id
        self.user_id = user_id
        self.candidate_claim_ids = (
            set(candidate_claim_ids) if candidate_claim_ids is not None else None
        )
        self._overview: dict[str, dict] | None = None

    # -- 辅助 -------------------------------------------------------------

    def _claims(self) -> dict[str, dict]:
        if self._overview is None:
            self._overview = {
                entry["claim"]["id"]: entry
                for entry in adapter.claims_overview(self.evidence_store)
            }
        return self._overview

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _decision(
        self,
        *,
        proposal_id: str,
        claim_id: str,
        capability_path: str,
        rationale: str,
        accepted: bool,
        gate_stage: str,
        reject_reason: str | None,
        capability_id: str | None,
        run_id: str,
        stages_passed: list[str],
    ) -> GateDecision:
        return GateDecision(
            proposal_id=proposal_id,
            claim_id=claim_id,
            capability_path=capability_path,
            rationale=rationale,
            accepted=accepted,
            gate_stage=gate_stage,
            reject_reason=reject_reason,
            capability_id=capability_id,
            run_id=run_id,
            timestamp=self._now(),
            stages_passed=tuple(stages_passed),
        )

    # -- 闸门 -------------------------------------------------------------

    def evaluate(
        self,
        proposal: dict,
        *,
        run_id: str,
        index: int = 0,
        proposer: str | None = None,
    ) -> GateDecision:
        """对一条提议执行八步闸门；任何一步失败都立即返回（不落库）。"""
        raw = dict(proposal)
        claim_id = str(raw.get("claim_id") or "")
        capability_path = str(raw.get("capability_path") or "")
        rationale = str(raw.get("rationale") or "")
        proposal_id = proposal_id_for(run_id, index, claim_id, capability_path)
        passed: list[str] = []

        # 1) schema：只允许三个字段；缺字段 / 多字段（如 confidence）都在这里被拒
        try:
            item = ProposalItem.model_validate(raw)
        except ValidationError as error:
            detail = "；".join(
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in error.errors()[:3]
            )
            return self._decision(
                proposal_id=proposal_id,
                claim_id=claim_id,
                capability_path=capability_path,
                rationale=rationale,
                accepted=False,
                gate_stage="schema",
                reject_reason=f"提议 schema 不合法：{detail}",
                capability_id=None,
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("schema")

        # 2) claim 存在（且不越出本次候选集）
        entry = self._claims().get(item.claim_id)
        if entry is None:
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="claim_exists",
                reject_reason="claim 不在证据库中",
                capability_id=None,
                run_id=run_id,
                stages_passed=passed,
            )
        if self.candidate_claim_ids is not None and item.claim_id not in self.candidate_claim_ids:
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="claim_exists",
                reject_reason="claim 不在本次候选集中（提议越界）",
                capability_id=None,
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("claim_exists")

        # 3) 能力点存在（路径逐字命中目标树）
        capability = self.store.get_capability_by_path(self.goal_id, item.capability_path)
        if capability is None:
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="capability_exists",
                reject_reason="capability_path 不在目标树中（不得杜撰路径）",
                capability_id=None,
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("capability_exists")

        # 4) 能力点必须处于当前视图（history + current view）
        if capability.get("status") != "active":
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="capability_active",
                reject_reason=f"能力点不是 active（当前 {capability.get('status')}），不参与当前视图",
                capability_id=capability["id"],
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("capability_active")

        # 5) 证据分桶允许（未映射类型一律拒绝，不静默丢证据）
        buckets, unmapped = claim_buckets(entry)
        if unmapped:
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="bucket_allowed",
                reject_reason=f"存在不可入桶的证据类型：{unmapped}",
                capability_id=capability["id"],
                run_id=run_id,
                stages_passed=passed,
            )
        if not buckets:
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="bucket_allowed",
                reject_reason="没有可用的证据桶",
                capability_id=capability["id"],
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("bucket_allowed")

        # 6) 归属/准入复核：LLM 不得（也无法）改动 attribution —— 闸门重跑 M4-a 合取链
        classification = classify_claim(entry)
        if not classification.admissible:
            reason = classification.reasons[0] if classification.reasons else classification.kind
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="attribution_unchanged",
                reject_reason=f"准入复核未通过：{classification.kind}（{reason}）",
                capability_id=capability["id"],
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("attribution_unchanged")

        # 7) 去重（同一能力点与主张只允许一条绑定记录）
        existing = self.store.list_capability_claims(capability_id=capability["id"])
        if any(link["claim_id"] == item.claim_id for link in existing):
            return self._decision(
                proposal_id=proposal_id,
                claim_id=item.claim_id,
                capability_path=item.capability_path,
                rationale=item.rationale,
                accepted=False,
                gate_stage="duplicate",
                reject_reason="该主张已绑定到此能力点（幂等：重复提议不再落库）",
                capability_id=capability["id"],
                run_id=run_id,
                stages_passed=passed,
            )
        passed.append("duplicate")

        # 8) 落库（只有到这里才写 g_capability_claims）
        note = (
            "M4-b LLM 提议 + 确定性闸门通过"
            f"｜run={run_id}"
            f"｜proposer={proposer or 'unknown'}"
            f"｜理由：{item.rationale}"
        )
        self.store.link_capability_claim(
            capability["id"], item.claim_id, role="supports", rationale=note
        )
        passed.append("persisted")
        return self._decision(
            proposal_id=proposal_id,
            claim_id=item.claim_id,
            capability_path=item.capability_path,
            rationale=item.rationale,
            accepted=True,
            gate_stage="persisted",
            reject_reason=None,
            capability_id=capability["id"],
            run_id=run_id,
            stages_passed=passed,
        )


BINDING_SYSTEM = """你是证据绑定提议者（只提议，不裁决）。给定材料口径主张与目标能力树的 active 能力点，为每条主张提议至多一个最相关的能力点绑定。

硬性要求：
1. capability_path 必须**逐字**来自给出的路径列表，不得杜撰、改写或拼接；
2. 只允许输出 claim_id / capability_path / rationale 三个字段 —— **禁止输出任何置信度、等级、分值、评分字段**（出现即被拒）；
3. 不确定就**不提议**（该主张不出现在 proposals 里），不要为了凑数硬绑；
4. rationale 用一句话说明"这条材料内容与这个能力点的关联"，用**材料口径**表述，不得写成"用户具备/掌握/实现了…"；
5. 输出严格 JSON，不要 markdown。"""


def render_binding_prompt(claims: list[dict], capabilities: list[dict]) -> str:
    """组装提议输入：候选主张（材料口径）+ active 能力点路径（三层树只列能力点）。"""
    lines = ["材料口径主张（claim_id 只能从这里选）："]
    for entry in claims:
        claim = entry["claim"]
        lines.append(f"- {claim['id']}：{claim['statement']}")
    lines.append("")
    lines.append("目标能力树（active 能力点；capability_path 必须逐字来自这里）：")
    for row in capabilities:
        lines.append(f"- {row['path']}")
    lines.append("")
    lines.append("为每条主张提议至多一个最相关的能力点；不相关就不提议。输出严格 JSON。")
    return "\n".join(lines)


class ClaimBinder:
    """一次提议运行：LLM 产出候选 → 八步闸门裁决 → 只有通过者落库。"""

    def __init__(
        self,
        *,
        store,
        evidence_store,
        gateway: StructuredGateway,
        goal_id: str,
        user_id: str = "local",
        id_factory=None,
    ) -> None:
        self.store = store
        self.evidence_store = evidence_store
        self.goal_id = goal_id
        self.user_id = user_id
        self.runtime = AgentRuntime(
            store=store, gateway=gateway, agent="claim_binding", user_id=user_id, id_factory=id_factory
        )

    async def propose(self, claim_ids: list[str]) -> dict:
        overview = {
            entry["claim"]["id"]: entry
            for entry in adapter.claims_overview(self.evidence_store)
        }
        unknown = [claim_id for claim_id in claim_ids if claim_id not in overview]
        if unknown:
            raise BindingError(f"候选集中有未知 claim: {unknown}")
        capabilities = self.store.list_capabilities(self.goal_id, status="active")
        if not capabilities:
            raise BindingError("目标树没有 active 能力点，无法提议")
        leaf_count = sum(1 for row in capabilities if row["depth"] == 3)

        outcome = await self.runtime.call_model_with_run(
            system=BINDING_SYSTEM,
            user=render_binding_prompt([overview[cid] for cid in claim_ids], capabilities),
            schema=BindingProposalSet,
            task=BINDING_TASK,
            context=AgentContext(
                user_id=self.user_id,
                goal_id=self.goal_id,
                correlation_id=self.goal_id,
                notes={
                    "候选主张数": str(len(claim_ids)),
                    "active 能力点数": str(leaf_count),
                },
            ),
        )
        proposals = outcome.result.value.proposals
        gate = BindingGate(
            store=self.store,
            evidence_store=self.evidence_store,
            goal_id=self.goal_id,
            user_id=self.user_id,
            candidate_claim_ids=list(claim_ids),
        )
        proposer = f"{outcome.result.provider}/{outcome.result.model}"
        decisions = [
            gate.evaluate(item.model_dump(), run_id=outcome.run_id, index=index, proposer=proposer)
            for index, item in enumerate(proposals)
        ]
        return {
            "run_id": outcome.run_id,
            "provider": outcome.result.provider,
            "model": outcome.result.model,
            "goal_id": self.goal_id,
            "candidates": list(claim_ids),
            "proposals": [
                {**item.model_dump(), "proposal_id": decisions[index].proposal_id, "run_id": outcome.run_id}
                for index, item in enumerate(proposals)
            ],
            "decisions": [decision.to_dict() for decision in decisions],
            "accepted": [d.proposal_id for d in decisions if d.accepted],
            "rejected": [d.proposal_id for d in decisions if not d.accepted],
        }


def build_binding_artifact(report: dict, *, mode: str, db_path: str) -> dict:
    """把一次提议运行整理成只读审计产物（proposal / reject / accept 全量）。"""
    return {
        "artifact": "m4b-binding-proposals",
        "mode": mode,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "read_only": True,
        "run_id": report["run_id"],
        "provider": report["provider"],
        "model": report["model"],
        "goal_id": report["goal_id"],
        "candidates": report["candidates"],
        "proposals": report["proposals"],
        "decisions": report["decisions"],
        "accepted_count": len(report["accepted"]),
        "rejected_count": len(report["rejected"]),
    }


def write_binding_artifact(path: str | Path, artifact: dict) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(target)
