"""M5-c：任务提交闭环（TaskLoop）—— 提交物 → 证据 → claim → 绑定 → 重评 → 归因。

用户 2026-10-03 确认的边界（`M5-PLAN.md` v1.0 §6）：

```text
TaskLoop.complete_task(task_id, submission)
 ① 前置校验：task 存在 ∧ active；提交物形态 ↔ deliverable_type 匹配
 ② 单入口入库（adapter / archive 容器级封装；归属与通道写死）
 ③ 材料 claim（确定性模板；越权前置；一条；幂等）
 ④ 绑定（ClaimBinder → 八步闸门；≤1 HTTP；后置条件 = 任务能力点 ≥1 accepted）
 ⑤ 重评（assess_capability；M4-e 编排；fail-stop）
 ⑥ 落定（store.complete_task + 归因产物 + 守卫）
```

纪律：

* **唯一入口**：`g_task_submissions` 只由本链写入；`source_id` 不是调用契约的一部分
  （它由证据链内部产生）——调用方只能给提交物；
* **done 在链尾**：②–⑤ 任一步失败 → 任务留在 `active`，可幂等重跑；`done` 是闭环结果，
  不是提交动作的结果；
* **完成 ≠ 提升**：等级只由 M4-e 编排写；本模块不得直呼 `link_capability_claim` /
  `save_assessment` / `apply_assessment_levels`（由测试的 AST 守卫锁定）；
* **三联条件**：等级变化必须同时具备 before assessment + 新证据 provenance
  （source → claim → binding）+ after assessment，缺一即 `LoopGuardError`（fail-stop）；
  本链只产生支持性证据，等级下降视为异常。
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ..evidence import adapter
from ..evidence.archive import ingest_archive
from ..store import ASSESSMENT_DIMENSIONS, DELIVERABLE_EVIDENCE_TYPE
from .binding import BindingError, ClaimBinder
from .pipeline import PipelineError, assess_capability

LOOP_CONTRACT_VERSION = "m5c-1"

DEFAULT_SUBMISSION_DIR = "data/task_submissions"

CLAIM_PASSAGE_LIMIT = 3
"""材料 claim 引用 passage 的上限（单文件：前 ≤3 条）。"""

PRIMARY_PASSAGE_LIMIT = 2
"""archive 提交时主来源最多引用 2 条，其余来源各 1 条，总计 ≤ `CLAIM_PASSAGE_LIMIT`。"""

RATED_STATUSES = ("rated", "insufficient_evidence")
"""当前视图状态（草案不算；与 `GrowthStore.latest_assessment` 同谓词）。"""


class TaskLoopError(RuntimeError):
    """闭环入参或运行前提不成立（fail-stop；任务留在 active，可重跑）。"""


class LoopGuardError(TaskLoopError):
    """闭环后置校验失败（fail-stop）：归因不成立或等级变化说不清。"""

    def __init__(self, message: str, *, attribution: dict | None = None) -> None:
        super().__init__(message)
        self.attribution = attribution


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TaskLoopError(message)


def _level_key(row: dict | None) -> tuple:
    """（状态, 等级）二元组：判定"等级变化"用（assessment_id 变化只代表证据集变化）。"""
    if row is None:
        return (None, None)
    return (row.get("status"), row.get("level"))


class TaskLoop:
    """提交即完成：一次调用 = 一条固定链（无手工步骤、无自动重试）。"""

    def __init__(
        self,
        *,
        store,
        evidence_store,
        gateway,
        user_id: str = "local",
        submission_dir: str | Path | None = None,
        report_directory: str | Path | None = None,
        id_factory=None,
    ) -> None:
        self.store = store
        self.evidence_store = evidence_store
        self.gateway = gateway
        self.user_id = user_id
        self.submission_dir = Path(submission_dir or DEFAULT_SUBMISSION_DIR)
        self.report_directory = Path(report_directory) if report_directory is not None else None
        self.id_factory = id_factory

    # -- 主链 -------------------------------------------------------------

    async def complete_task(
        self,
        task_id: str,
        *,
        artifact_path: str | Path | None = None,
        probe_answer: str | None = None,
        note: str | None = None,
    ) -> dict:
        """提交即完成（**唯一入口**）：固定链 ①–⑥，任一步失败即 fail-stop。

        失败时任务留在 `active`（可幂等重跑）；`done` 只在全链完成后落定。
        """
        # ① 前置校验
        task = self.store.get_task(task_id)
        _require(task is not None, f"未知任务: {task_id}")
        _require(
            task["status"] == "active",
            f"只有 active 任务可以提交（当前 {task['status']}）—— 先 activate",
        )
        gap = self.store.get_gap(task["gap_id"])
        _require(gap is not None, f"任务引用的缺口不存在: {task['gap_id']}")
        capability = self.store.get_capability(task["capability_id"])
        _require(capability is not None, f"任务引用的能力点不存在: {task['capability_id']}")
        _require(capability["status"] == "active", f"能力点非 active（{capability['status']}）")
        artifact, probe = self._validate_submission(task, artifact_path, probe_answer)

        before = self._snapshot(task["capability_id"])
        before_claims = self._bound_claim_ids(task["capability_id"])
        before_gaps = self._gap_snapshot(task["capability_id"])

        # ② 单入口入库（证据类型由 deliverable_type 决定；归属/通道写死）
        ingest = self._ingest(task, artifact, probe)

        # ③ 材料 claim（确定性模板；越权前置）
        claim = self._create_claim(task, ingest)

        # ④ 绑定（≤1 HTTP；后置条件 = 任务能力点 ≥1 accepted）
        binding = await self._bind(task, claim["claim_id"])

        # ⑤ 重评（仅当绑定落在任务能力点；否则记 binding_missed，不写 assessment）
        assessment = None
        if binding["bound_on_task_capability"]:
            assessment = self._assess(task, binding)

        # ⑥ 落定（done 是闭环结果，不是提交动作的结果）
        done = self.store.complete_task(
            task_id, source_id=ingest["source_id"], note=self._note(note, ingest)
        )

        after = self._snapshot(task["capability_id"])
        after_claims = self._bound_claim_ids(task["capability_id"])
        trace = trace_task(self.store, self.evidence_store, task_id=task_id)
        attribution = self._build_attribution(
            task=task,
            gap=gap,
            ingest=ingest,
            claim=claim,
            binding=binding,
            before=before,
            after=after,
            before_claims=before_claims,
            after_claims=after_claims,
            before_gaps=before_gaps,
            after_gaps=self._gap_snapshot(task["capability_id"]),
            assessment=assessment,
            trace=trace,
        )
        guard = verify_attribution(attribution)
        attribution["guard"] = guard
        attribution["status"] = self._status(attribution)
        return {
            "contract": LOOP_CONTRACT_VERSION,
            "status": attribution["status"],
            "task": done,
            "attribution": attribution,
            "binding": binding,
            "assessment": assessment,
        }

    # -- ① 提交物校验 ------------------------------------------------------

    def _validate_submission(self, task: dict, artifact_path, probe_answer):
        deliverable = task["deliverable_type"]
        if deliverable == "probe_answer":
            _require(artifact_path is None, "probe_answer 提交只接受作答文本（不要 artifact_path）")
            text = str(probe_answer or "").strip()
            _require(bool(text), "probe_answer 提交需要作答文本（现场作答即提交物）")
            return None, text
        _require(probe_answer is None, f"{deliverable} 提交只接受 artifact_path（不要 probe_answer）")
        _require(artifact_path is not None, f"{deliverable} 提交需要 artifact_path")
        path = Path(artifact_path)
        _require(path.is_file(), f"提交文件不存在: {path}")
        if deliverable == "archive":
            _require(zipfile.is_zipfile(path), f"不是有效的 ZIP 归档: {path}")
        return path, None

    # -- ② 单入口入库 ------------------------------------------------------

    def _ingest(self, task: dict, artifact: Path | None, probe: str | None) -> dict:
        deliverable = task["deliverable_type"]
        evidence_type = DELIVERABLE_EVIDENCE_TYPE[deliverable]
        extra = {"growth_task_id": task["id"]}

        if deliverable == "probe_answer":
            target = self.submission_dir / f"{task['id']}.probe.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(probe, encoding="utf-8")
            result = self._ingest_one(
                target, evidence_type, extra, title=f"{task['title']}｜现场作答"
            )
            passage_ids = self._passage_ids(result.source_id, CLAIM_PASSAGE_LIMIT)
            return {
                "source_id": result.source_id,
                "source_ids": [result.source_id],
                "evidence_type": evidence_type,
                "passage_ids": passage_ids,
                "archive": None,
                "materialized_path": str(target),
            }

        if deliverable == "archive":
            report = ingest_archive(
                artifact,
                store=self.evidence_store,
                evidence_type=evidence_type,
                channel="user_evidence",
                attribution="user_declared",
                workdir=self.submission_dir / "extracted",
            )
            if not report.ok:
                raise TaskLoopError("归档中没有可入库条目（全部跳过或失败）—— fail-closed")
            if report.failed:
                reasons = "；".join(
                    f"{item.entry}: {item.reason}" for item in report.failed[:3]
                )
                raise TaskLoopError(
                    f"归档有 {len(report.failed)} 条入库失败（fail-stop）：{reasons}"
                )
            primary = min(report.ok, key=lambda item: (-item.passage_count, item.entry))
            return {
                "source_id": primary.source_id,
                "source_ids": [item.source_id for item in report.ok if item.source_id],
                "evidence_type": evidence_type,
                "passage_ids": self._archive_passage_ids(report.ok, primary),
                "archive": {
                    "ok": len(report.ok),
                    "skipped": len(report.skipped),
                    "failed": 0,
                    "primary_entry": primary.entry,
                },
                "materialized_path": None,
            }

        result = self._ingest_one(artifact, evidence_type, extra, title=f"{task['title']}｜提交")
        return {
            "source_id": result.source_id,
            "source_ids": [result.source_id],
            "evidence_type": evidence_type,
            "passage_ids": self._passage_ids(result.source_id, CLAIM_PASSAGE_LIMIT),
            "archive": None,
            "materialized_path": None,
        }

    def _ingest_one(self, path, evidence_type: str, extra: dict, *, title: str):
        try:
            return adapter.ingest_document(
                path,
                store=self.evidence_store,
                evidence_type=evidence_type,
                channel="user_evidence",
                attribution="user_declared",
                extra_metadata=extra,
                title=title,
                task_id=extra["growth_task_id"],
            )
        except adapter.EvidenceError as error:
            raise TaskLoopError(f"提交入库被拒（单入口 fail-closed）：{error}") from error

    def _passage_ids(self, source_id: str, limit: int) -> list[str]:
        return [item.id for item in self.evidence_store.get_passages(source_id=source_id)][:limit]

    def _archive_passage_ids(self, ok: list, primary) -> list[str]:
        ordered = [primary] + [item for item in ok if item.source_id != primary.source_id]
        selected: list[str] = []
        for index, item in enumerate(ordered):
            if len(selected) >= CLAIM_PASSAGE_LIMIT:
                break
            limit = PRIMARY_PASSAGE_LIMIT if index == 0 else 1
            for passage_id in self._passage_ids(item.source_id, limit):
                if passage_id not in selected:
                    selected.append(passage_id)
        return selected[:CLAIM_PASSAGE_LIMIT]

    # -- ③ 材料 claim ------------------------------------------------------

    def _create_claim(self, task: dict, ingest: dict) -> dict:
        statement = (
            f"提交材料（{task['deliverable_type']}）包含任务「{task['title']}」的产出物："
            f"{task['objective']}"
        )
        try:
            return adapter.create_material_claim(
                self.evidence_store,
                subject="提交材料",
                predicate="包含",
                object=f"任务产出物（{task['deliverable_type']}）",
                statement=statement,
                passage_ids=list(ingest["passage_ids"]),
                metadata={"growth_task_id": task["id"]},
                task_id=task["id"],
            )
        except adapter.EvidenceError as error:
            raise TaskLoopError(f"材料 claim 被拒（越权前置 fail-closed）：{error}") from error

    # -- ④ 绑定 ------------------------------------------------------------

    async def _bind(self, task: dict, claim_id: str) -> dict:
        capability_id = task["capability_id"]
        existing = [
            link
            for link in self.store.list_capability_claims(capability_id=capability_id)
            if link["claim_id"] == claim_id
        ]
        if existing:  # 幂等重跑：该 claim 已绑定到任务能力点，不再调用模型
            return {
                "mode": "already_bound",
                "bound_on_task_capability": True,
                "run_id": None,
                "provider": None,
                "model": None,
                "accepted_proposal_ids": [],
                "decisions": [],
                "reason": "重复运行：该 claim 已绑定到任务能力点（幂等）",
                "rationale": existing[0]["rationale"],
            }
        binder = ClaimBinder(
            store=self.store,
            evidence_store=self.evidence_store,
            gateway=self.gateway,
            goal_id=task["goal_id"],
            user_id=self.user_id,
            id_factory=self.id_factory,
        )
        try:
            report = await binder.propose([claim_id])
        except BindingError as error:
            raise TaskLoopError(f"绑定提议无法进行：{error}") from error
        except Exception as error:
            raise TaskLoopError(
                f"绑定提议调用失败（fail-stop，可重跑）：{type(error).__name__}: {error}"
            ) from error
        accepted = [
            decision
            for decision in report["decisions"]
            if decision["accepted"] and decision.get("capability_id") == capability_id
        ]
        return {
            "mode": "proposed",
            "bound_on_task_capability": bool(accepted),
            "run_id": report["run_id"],
            "provider": report["provider"],
            "model": report["model"],
            "accepted_proposal_ids": [decision["proposal_id"] for decision in accepted],
            "decisions": [
                {
                    "proposal_id": decision["proposal_id"],
                    "accepted": decision["accepted"],
                    "gate_stage": decision["gate_stage"],
                    "capability_id": decision.get("capability_id"),
                    "reject_reason": decision.get("reject_reason"),
                }
                for decision in report["decisions"]
            ],
            "reason": (
                None
                if accepted
                else "本次提议没有把新 claim 绑定到任务能力点（binding_missed）"
            ),
            "rationale": accepted[0]["rationale"] if accepted else None,
        }

    # -- ⑤ 重评 ------------------------------------------------------------

    def _assess(self, task: dict, binding: dict) -> dict:
        try:
            return assess_capability(
                self.store,
                self.evidence_store,
                capability_id=task["capability_id"],
                report_directory=self.report_directory,
                report_stem=f"loop-{task['id']}",
                generated_by=binding.get("run_id"),
            )
        except PipelineError as error:
            raise TaskLoopError(f"重评编排 fail-stop：{error}") from error

    # -- 快照与归因 --------------------------------------------------------

    def _snapshot(self, capability_id: str) -> dict:
        snapshot: dict[str, dict | None] = {}
        for dimension in ASSESSMENT_DIMENSIONS:
            row = self.store.latest_assessment(capability_id, dimension)
            snapshot[dimension] = (
                None
                if row is None
                else {
                    "assessment_id": row["id"],
                    "level": row["level"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                }
            )
        return snapshot

    def _bound_claim_ids(self, capability_id: str) -> list[str]:
        return sorted(
            {link["claim_id"] for link in self.store.list_capability_claims(capability_id=capability_id)}
        )

    def _gap_snapshot(self, capability_id: str) -> list[dict]:
        return [
            {
                "id": gap["id"],
                "dimension": gap["dimension"],
                "severity": gap["severity"],
                "status": gap["status"],
            }
            for gap in self.store.list_gaps(capability_id=capability_id)
        ]

    @staticmethod
    def _note(note: str | None, ingest: dict) -> str | None:
        parts = [str(note).strip()] if note and str(note).strip() else []
        if ingest.get("archive"):
            archive = ingest["archive"]
            parts.append(
                f"archive ok/skipped/failed={archive['ok']}/{archive['skipped']}/{archive['failed']}"
                f"；主条目={archive['primary_entry']}"
            )
        if ingest.get("materialized_path"):
            parts.append(f"probe 物化={ingest['materialized_path']}")
        return "｜".join(parts) or None

    def _build_attribution(
        self,
        *,
        task: dict,
        gap: dict,
        ingest: dict,
        claim: dict,
        binding: dict,
        before: dict,
        after: dict,
        before_claims: list[str],
        after_claims: list[str],
        before_gaps: list[dict],
        after_gaps: list[dict],
        assessment: dict | None,
        trace: dict,
    ) -> dict:
        assessment_changed = [
            dimension for dimension in after if before.get(dimension) != after.get(dimension)
        ]
        level_changed = [
            dimension
            for dimension in after
            if _level_key(before.get(dimension)) != _level_key(after.get(dimension))
        ]
        closed_gap_ids = [
            gap["id"]
            for gap in after_gaps
            if gap["status"] == "closed"
            and next((item for item in before_gaps if item["id"] == gap["id"]), {}).get("status")
            != "closed"
        ]
        return {
            "contract": LOOP_CONTRACT_VERSION,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "task_id": task["id"],
            "gap_id": task["gap_id"],
            "capability_id": task["capability_id"],
            "dimension": gap["dimension"],
            "submission": {
                "source_id": ingest["source_id"],
                "source_ids": list(ingest["source_ids"]),
                "evidence_type": ingest["evidence_type"],
                "channel": "user_evidence",
                "attribution": "user_declared",
                "archive": ingest.get("archive"),
                "materialized_path": ingest.get("materialized_path"),
            },
            "claim": {
                "claim_id": claim["claim_id"],
                "scope": "material",
                "passage_ids": list(claim["passage_ids"]),
            },
            "binding": binding,
            "before": before,
            "after": after,
            "assessment_changed_dimensions": assessment_changed,
            "level_changed_dimensions": level_changed,
            "level_changed": bool(level_changed),
            "support": {
                "before_claim_ids": before_claims,
                "after_claim_ids": after_claims,
                "added_claim_ids": sorted(set(after_claims) - set(before_claims)),
            },
            "gaps": {
                "before": before_gaps,
                "after": after_gaps,
                "closed_gap_ids": closed_gap_ids,
            },
            "assessment": (
                None
                if assessment is None
                else {
                    "contract": assessment["contract"],
                    "assessment_ids": assessment["assessment_ids"],
                    "report_paths": assessment.get("report_paths", {}),
                }
            ),
            "trace": trace,
        }

    @staticmethod
    def _status(attribution: dict) -> str:
        if not attribution["binding"]["bound_on_task_capability"]:
            return "binding_missed"
        return "level_changed" if attribution["level_changed"] else "no_level_change"


def verify_attribution(attribution: dict) -> dict:
    """三联条件校验（确定性、纯函数，可单测）：变化必须可归因，否则 `LoopGuardError`。

    * 有等级变化 → 必须同时存在 before assessment + 新证据 provenance
      （source → claim → binding）+ after assessment + 全链反查完整；
    * 无等级变化 → 不做额外约束（"没变化"不是错误）；
    * 本链只产生支持性证据 → 等级下降视为异常。
    """
    submission = attribution.get("submission") or {}
    claim = attribution.get("claim") or {}
    binding = attribution.get("binding") or {}
    trace = attribution.get("trace") or {}
    guard = {
        "new_source_present": bool(submission.get("source_id")),
        "new_claim_present": bool(claim.get("claim_id")),
        "binding_on_task_capability": bool(binding.get("bound_on_task_capability")),
        "trace_complete": bool(trace.get("complete")),
    }
    level_changed = list(attribution.get("level_changed_dimensions") or [])
    if level_changed:
        for dimension in level_changed:
            before = (attribution.get("before") or {}).get(dimension)
            after = (attribution.get("after") or {}).get(dimension)
            guard[f"before_present:{dimension}"] = before is not None
            guard[f"after_present:{dimension}"] = after is not None
        three_part = (
            guard["new_source_present"]
            and guard["new_claim_present"]
            and guard["binding_on_task_capability"]
            and guard["trace_complete"]
            and all(
                guard[f"before_present:{dimension}"] and guard[f"after_present:{dimension}"]
                for dimension in level_changed
            )
        )
        if not three_part:
            raise LoopGuardError(
                "等级变化无法归因（三联条件不成立）："
                + json.dumps(guard, ensure_ascii=False, sort_keys=True),
                attribution=attribution,
            )
        for dimension in level_changed:
            before = attribution["before"][dimension]
            after = attribution["after"][dimension]
            if (after.get("level") or 0) < (before.get("level") or 0):
                raise LoopGuardError(
                    f"{dimension} 等级下降（本链只产生支持性证据，下降视为异常）"
                    f"：{before.get('level')} → {after.get('level')}",
                    attribution=attribution,
                )
    return guard


def trace_task(store, evidence_store, *, task_id: str) -> dict:
    """只读反查：`task → submission → source → claim → binding → assessment`（G5 反查用）。

    不做任何写入、不做等级判断；`complete` 为真当且仅当全链每一跳都存在。
    """
    task = store.get_task(task_id)
    if task is None:
        return {
            "contract": LOOP_CONTRACT_VERSION,
            "task_id": task_id,
            "complete": False,
            "reason": "未知任务",
        }
    gap = store.get_gap(task["gap_id"])
    submissions = store.list_task_submissions(task_id=task_id)
    source_ids = sorted({str(row["source_id"]) for row in submissions})
    source_set = set(source_ids)
    claims: list[dict] = []
    for entry in adapter.claims_overview(evidence_store):
        linked = {
            str((link.get("source") or {}).get("id")) for link in entry.get("evidence") or []
        }
        if linked & source_set:
            claims.append(
                {
                    "claim_id": entry["claim"]["id"],
                    "statement": entry["claim"].get("statement"),
                    "sources": sorted(linked & source_set),
                }
            )
    claim_ids = {item["claim_id"] for item in claims}
    bindings = [
        link
        for link in store.list_capability_claims(capability_id=task["capability_id"])
        if link["claim_id"] in claim_ids
    ]
    assessments = [
        row
        for row in store.list_assessments(capability_id=task["capability_id"])
        if row["status"] in RATED_STATUSES
    ]
    complete = bool(
        task["status"] == "done"
        and gap is not None
        and source_ids
        and claims
        and bindings
        and assessments
    )
    return {
        "contract": LOOP_CONTRACT_VERSION,
        "task_id": task_id,
        "task_status": task["status"],
        "gap_id": task["gap_id"],
        "gap": gap,
        "submissions": submissions,
        "source_ids": source_ids,
        "claims": claims,
        "bindings": bindings,
        "assessments": [
            {
                "id": row["id"],
                "dimension": row["dimension"],
                "status": row["status"],
                "level": row["level"],
                "created_at": row["created_at"],
            }
            for row in assessments
        ],
        "complete": complete,
    }


def build_loop_artifact(report: dict, *, mode: str, db_path: str) -> dict:
    """把一次闭环运行整理成只读审计产物（归因链 + 绑定裁决 + 状态）。"""
    return {
        "artifact": "m5c-task-loop",
        "mode": mode,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "read_only": True,
        "contract": LOOP_CONTRACT_VERSION,
        "status": report["status"],
        "task": report["task"],
        "attribution": report["attribution"],
        "binding": report["binding"],
        "assessment": report["assessment"],
    }


def write_loop_artifact(path: str | Path, artifact: dict) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)
