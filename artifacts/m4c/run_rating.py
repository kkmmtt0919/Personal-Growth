"""M4-c 冒烟：星级规则引擎 + 反向证据结算（离线，不调用任何模型）。

场景（对应 `M4-PLAN.md` v1.0 与用户 2026-10-03 冻结口径）：

* **弱证据**：自述 + 笔记 → 理解 2、实践 `insufficient_evidence`（显式缺实践证据）；
* **强证据**：同一能力点补充项目材料 → 实践 3（相对弱场景 ≥ +2 的约定成立）；
* **反向证据**：注入 `refutes` / `broken` → 实践封顶 2 / 主张剔除，**理解维度不受污染**；
* **无证据**：空能力点 → 两维度均 `insufficient_evidence`（不是低星）；
* **确定性**：重复运行同一结论 → 同一批行（幂等）；结论变化 → 新行（历史保留）。

产物：`rating-artifact.json`（每能力点两维度的评级、rubric、行 id 与历史）与
`result.json`（完整报告 + 检查清单 + 数据边界）。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from evkg.attack.auditor import audit_store
from growth_os.assessment import (
    DIMENSIONS,
    INSUFFICIENT,
    PRACTICE,
    RATED,
    RULES_CONTRACT_VERSION,
    UNDERSTANDING,
    AssessmentRater,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

REAL_DB = REPO / "data" / "growth.db"
ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
GOAL_ID = "goal_m4c_smoke"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_goal_and_tree(store: GrowthStore) -> dict:
    store.upsert_user("local", "本地用户")
    store.save_goal(
        {
            "id": GOAL_ID,
            "user_id": "local",
            "title": "成为 AI Agent 工程师",
            "direction": "AI 应用方向",
            "purpose": "求职",
            "horizon": "6 个月",
            "measurable_result": "完成一个可演示的 RAG 项目",
            "status": "confirmed",
            "source_quote": "我想成为 AI Agent 工程师",
        }
    )
    domain = store.upsert_capability(
        {"goal_id": GOAL_ID, "path": "LLM 基础", "name": "LLM 基础", "depth": 1, "target_level": 3}
    )
    group = store.upsert_capability(
        {
            "goal_id": GOAL_ID,
            "path": "LLM 基础/检索增强",
            "name": "检索增强",
            "depth": 2,
            "parent_id": domain,
            "target_level": 3,
        }
    )

    def add(name: str) -> str:
        return store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": f"LLM 基础/检索增强/{name}",
                "name": name,
                "depth": 3,
                "parent_id": group,
                "target_level": 3,
            }
        )

    return {"rag": add("RAG 实现"), "reverse": add("反向证据演示"), "empty": add("空能力点")}


def add_claim(store, tmp: Path, *, filename: str, content: str, evidence_type: str) -> str:
    target = tmp / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=store, evidence_type=evidence_type, attribution="user_declared"
    )
    passage_ids = [item.id for item in store.get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        store,
        subject="项目材料",
        predicate="包含",
        object="相关内容",
        statement=f"项目材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
    )["claim_id"]


def inject_attack(store, claim_id: str, verdict: str) -> None:
    store.db.execute(
        "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    payload = {
        "probe": {"target_claim_id": claim_id, "angle": "注入式", "question": "注入式质疑"},
        "verdict": {
            "target_claim_id": claim_id,
            "verdict": verdict,
            "reasoning": "注入式反例（M4-c 只验证已有裁决如何影响评级）",
            "missing_evidence": [],
        },
    }
    store.db.execute(
        "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
        (f"rep_{claim_id}_{verdict}", "m4c", "adversarial", claim_id, json.dumps(payload, ensure_ascii=False)),
    )
    store.db.commit()


def summarize(store, capability_id: str) -> dict:
    dimensions = {}
    for dimension in DIMENSIONS:
        row = store.latest_assessment(capability_id, dimension)
        dimensions[dimension] = (
            {
                "assessment_id": row["id"],
                "status": row["status"],
                "level": row["level"],
                "rationale": row["rationale"],
                "rubric": json.loads(row["rubric_json"] or "{}"),
            }
            if row
            else None
        )
    history = [
        {
            "assessment_id": row["id"],
            "dimension": row["dimension"],
            "status": row["status"],
            "level": row["level"],
        }
        for row in store.list_assessments(capability_id=capability_id)
    ]
    return {"capability_id": capability_id, "dimensions": dimensions, "history": history}


def real_db_anchors_match() -> dict:
    anchor = _load_json(ANCHORS)
    conn = sqlite3.connect(f"file:{REAL_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        hasher = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            hasher.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return hasher.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    matched = all(digest(table) == anchor["table_content_sha256"][table] for table in tables)
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    conn.close()
    return {"content_hashes_match": matched, "counts_match": counts == anchor["table_counts"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="M4-c 评级冒烟（离线）")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "rating.db"
    db.unlink(missing_ok=True)

    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    caps = seed_goal_and_tree(store)
    rater = AssessmentRater(store=store, evidence_store=estore)

    # ── 场景 A：弱证据（自述 + 笔记）───────────────────────────────
    chat = add_claim(estore, workdir, filename="chat.md", content="# 对话\n\n我熟悉 RAG。\n", evidence_type="chat_assertion")
    notes = add_claim(estore, workdir, filename="notes.md", content="# 笔记\n\nRAG 检索流程整理。\n", evidence_type="uploaded_doc")
    store.link_capability_claim(caps["rag"], chat, rationale="M4-b 闸门通过（等价写入）")
    store.link_capability_claim(caps["rag"], notes, rationale="M4-b 闸门通过（等价写入）")
    weak = rater.rate(capability_id=caps["rag"])

    # ── 场景 B：补项目材料（强证据）────────────────────────────────
    repo = add_claim(estore, workdir, filename="repo.md", content="# 项目\n\n实现了 RAG 检索服务。\n", evidence_type="repo_artifact")
    store.link_capability_claim(caps["rag"], repo, rationale="M4-b 闸门通过（等价写入）")
    strong = rater.rate(capability_id=caps["rag"])

    # ── 确定性：重复运行同一结论 → 幂等 ───────────────────────────
    before_rows = len(store.list_assessments(capability_id=caps["rag"]))
    repeat = rater.rate(capability_id=caps["rag"])
    after_rows = len(store.list_assessments(capability_id=caps["rag"]))

    # ── 场景 C：反向证据（refutes → 实践 ≤2；broken → 主张剔除）──────
    r_notes = add_claim(estore, workdir, filename="r-notes.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    r_repo = add_claim(estore, workdir, filename="r-repo.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    store.link_capability_claim(caps["reverse"], r_notes, rationale="M4-b 闸门通过（等价写入）")
    store.link_capability_claim(caps["reverse"], r_repo, rationale="M4-b 闸门通过（等价写入）")
    reverse_base = rater.rate(capability_id=caps["reverse"])

    # 反向证据挂在**被质疑的主张**上（refutes 证据行）；不另造"支持型"主张
    from evkg.domain import EvidenceLink, Polarity

    repo_claim = next(item for item in estore.get_claims() if item.id == r_repo)
    repo_passage = next(item for item in estore.get_passages() if item.id == repo_claim.passage_ids[0])
    estore.save_evidence(
        EvidenceLink(
            id=f"evr_{r_repo}",
            claim_id=r_repo,
            passage_id=repo_passage.id,
            polarity=Polarity.REFUTES,
            quote=repo_passage.text,
            reasoning="注入式反向证据（M4-c）",
            confidence=None,
        )
    )
    reverse_refuted = rater.rate(capability_id=caps["reverse"])

    inject_attack(estore, r_repo, "broken")
    reverse_broken = rater.rate(capability_id=caps["reverse"])

    # ── 场景 D：无证据 ────────────────────────────────────────────
    empty = rater.rate(capability_id=caps["empty"])

    # ── 边界与审计 ───────────────────────────────────────────────
    evidence_counts = estore.counts()
    audit = audit_store(str(db))
    anchors = real_db_anchors_match()

    artifact = {
        "artifact": "m4c-rating",
        "contract": RULES_CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "db_path": str(db),
        "read_only": True,
        "notes": [
            "反向裁决为注入式（M4-c 只验证已存在裁决如何影响评级，不调用真实攻击模型）",
            "真实 attack 运行按用户决定留在 M4-e（G3 实验 + A/B 证据产出）",
        ],
        "capabilities": {
            "weak_and_strong": summarize(store, caps["rag"]),
            "reverse_evidence": summarize(store, caps["reverse"]),
            "no_evidence": summarize(store, caps["empty"]),
        },
    }
    artifact_path = HERE / "rating-artifact.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    weak_dims = weak["dimensions"]
    strong_dims = strong["dimensions"]
    refuted_dims = reverse_refuted["dimensions"]
    broken_dims = reverse_broken["dimensions"]
    empty_dims = empty["dimensions"]
    checks = {
        "weak_understanding_2": weak_dims[UNDERSTANDING]["level"] == 2,
        "weak_practice_insufficient": weak_dims[PRACTICE]["status"] == INSUFFICIENT
        and weak_dims[PRACTICE]["level"] is None,
        "strong_practice_3": strong_dims[PRACTICE]["level"] == 3,
        "strong_minus_weak_ge_2": (strong_dims[PRACTICE]["level"] or 0)
        - (weak_dims[PRACTICE]["level"] or 0)
        >= 2,
        "refutes_caps_practice_at_2": refuted_dims[PRACTICE]["level"] == 2,
        "refutes_leaves_understanding": refuted_dims[UNDERSTANDING]["level"] == 2,
        "broken_removes_support": broken_dims[PRACTICE]["status"] == INSUFFICIENT,
        "no_evidence_both_insufficient": all(
            empty_dims[dimension]["status"] == INSUFFICIENT and empty_dims[dimension]["level"] is None
            for dimension in DIMENSIONS
        ),
        "repeat_run_idempotent": before_rows == after_rows
        and set(repeat["assessment_ids"])
        == {
            strong_dims[UNDERSTANDING]["assessment_id"],
            strong_dims[PRACTICE]["assessment_id"],
        },
        "history_preserved": {
            row["status"]
            for row in store.list_assessments(capability_id=caps["rag"], dimension=PRACTICE)
        }
        == {INSUFFICIENT, RATED},
        "audit_store_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "real_db_untouched": anchors["content_hashes_match"] and anchors["counts_match"],
    }
    report = {
        "smoke": "M4-c 星级规则引擎 + 反向证据结算（离线）",
        "db": str(db),
        "rollout": {
            "weak": weak,
            "strong": strong,
            "reverse_base": reverse_base,
            "reverse_refuted": reverse_refuted,
            "reverse_broken": reverse_broken,
            "no_evidence": empty,
        },
        "evidence_counts": evidence_counts,
        "audit_store": {"status": audit["status"], "total_violations": audit["total_violations"]},
        "real_db_anchors": anchors,
        "artifact": str(artifact_path),
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    estore.db.close()
    store.close()
    gc.collect()
    if not args.keep_temp:
        deleted = False
        for _ in range(3):
            try:
                db.unlink(missing_ok=True)
                deleted = True
                break
            except PermissionError:
                gc.collect()
        report["temp_db_deleted"] = deleted

    (HERE / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "all_checks_passed": report["all_checks_passed"],
        "checks": checks,
        "artifact": str(artifact_path),
        "result": str(HERE / "result.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
