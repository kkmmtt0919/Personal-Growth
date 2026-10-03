"""M4-e · G2：assessment → claim → evidence → passage → source 逐跳追溯。

G2 判定（`ACCEPTANCE_GATES.md`）：随机抽 ≥5 条 assessment，每条都能沿链路追溯到原文，
且引文逐字；评估后 `audit_store` 保持 `pass/0`。

这里的 `trace_assessment` 是**只读**校验：不写任何库、不做等级判断 —— 只回答
"这条评定引用的每条主张，链路是否完整、引文是否逐字、来源标签是否齐备"。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from growth_os.assessment import AssessmentRater, check_chain, classify_claim
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

GOAL_ID = "goal_m4e_trace"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4e-trace.db"
    store = GrowthStore(str(db))
    estore = adapter.open_store(db)
    try:
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
            {"goal_id": GOAL_ID, "path": "AI Agent", "name": "AI Agent", "depth": 1, "target_level": 3}
        )
        group = store.upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "AI Agent/工具与执行",
                "name": "工具与执行",
                "depth": 2,
                "parent_id": domain,
                "target_level": 3,
            }
        )

        def add_capability(name: str, target_level: int = 3) -> str:
            return store.upsert_capability(
                {
                    "goal_id": GOAL_ID,
                    "path": f"AI Agent/工具与执行/{name}",
                    "name": name,
                    "depth": 3,
                    "parent_id": group,
                    "target_level": target_level,
                }
            )

        yield {
            "db": db,
            "store": store,
            "estore": estore,
            "add_capability": add_capability,
            "tmp": tmp_path,
        }
    finally:
        estore.db.close()
        store.close()


def add_claim(env, *, filename: str, content: str, evidence_type: str, attribution: str = "user_declared") -> str:
    target = env["tmp"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution=attribution
    )
    passage_ids = [item.id for item in env["estore"].get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        env["estore"],
        subject="材料",
        predicate="包含",
        object="相关内容",
        statement=f"材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
    )["claim_id"]


def bind(env, capability_id: str, claim_id: str) -> None:
    env["store"].link_capability_claim(
        capability_id, claim_id, role="supports", rationale="测试绑定（等价 M4-b 闸门写入）"
    )


# ---------------------------------------------------------------------------
# 追溯器（G2 的自动化判定；只读）
# ---------------------------------------------------------------------------


def trace_assessment(store, evidence_store, assessment_id: str) -> dict:
    """把一条评定行追溯回原文（G2 的自动化判定；只读）。

    追溯路径（`trace_path`）：

    * `supports`：`rated` 行 —— 走 rubric 记录的支撑主张；
    * `capability_bindings`：`insufficient_evidence` 行按设计**没有支撑集**
      （"证据不足"正是结论），此时走该能力点当前绑定的主张集合 ——
      它证明"不足"这个判断是对着真实、链路完整的已绑定证据做出的；
    * `none`：既无支撑也无绑定 —— 无从追溯（G2 抽样不采纳）。
    """
    row = store.get_assessment(assessment_id)
    if row is None:
        raise KeyError(f"未知评定行: {assessment_id}")
    rubric = json.loads(row["rubric_json"]) if row.get("rubric_json") else {}
    supports = [item["claim_id"] for item in rubric.get("supports") or []]
    if supports:
        claim_ids, trace_path = supports, "supports"
    else:
        claim_ids = [
            link["claim_id"]
            for link in store.list_capability_claims(
                capability_id=row["capability_id"], role="supports"
            )
        ]
        trace_path = "capability_bindings" if claim_ids else "none"
    overview = {entry["claim"]["id"]: entry for entry in adapter.claims_overview(evidence_store)}

    claims: list[dict] = []
    for claim_id in claim_ids:
        entry = overview.get(claim_id)
        if entry is None:
            claims.append(
                {
                    "claim_id": claim_id,
                    "complete": False,
                    "classification": "missing",
                    "admissible": False,
                    "chain_complete": False,
                    "quote_verbatim": False,
                    "evidence_rows": 0,
                    "missing": ["claim 不在证据库"],
                    "sources": [],
                    "channels": [],
                    "statement": None,
                }
            )
            continue
        classification = classify_claim(entry)
        chain = check_chain(entry)
        evidence = list(entry.get("evidence") or [])
        sources = sorted(
            {
                (link.get("source") or {}).get("id")
                for link in evidence
                if (link.get("source") or {}).get("id")
            }
        )
        channels = sorted(
            {
                str(((link.get("source") or {}).get("metadata") or {}).get("growth_channel"))
                for link in evidence
            }
        )
        claims.append(
            {
                "claim_id": claim_id,
                "complete": bool(classification.admissible and chain.complete),
                "classification": classification.kind,
                "admissible": classification.admissible,
                "chain_complete": chain.complete,
                "quote_verbatim": chain.quote_verbatim,
                "evidence_rows": chain.evidence_rows,
                "missing": list(chain.missing),
                "sources": sources,
                "channels": channels,
                "statement": entry["claim"].get("statement"),
            }
        )
    return {
        "assessment_id": assessment_id,
        "capability_id": row["capability_id"],
        "dimension": row["dimension"],
        "status": row["status"],
        "level": row["level"],
        "trace_path": trace_path,
        "walkable": bool(claims),
        "complete": bool(claims) and all(item["complete"] for item in claims),
        "claims": claims,
    }


def walk_all(store, evidence_store) -> list[dict]:
    return [
        trace_assessment(store, evidence_store, row["id"])
        for row in store.list_assessments()
        if row["status"] in ("rated", "insufficient_evidence")
    ]


def _build_three_capabilities(env) -> list[str]:
    """3 个能力点 × (笔记 + 项目) → 6 条可追溯的 rated 行（足够 G2 抽 5 条的样本量）。"""
    capabilities = []
    for index, name in enumerate(("RAG 检索", "工具调用", "上下文管理")):
        cap = env["add_capability"](name, target_level=3)
        notes = add_claim(
            env,
            filename=f"t-notes-{index}.md",
            content=f"# 笔记 {index}\n\n{name} 的流程整理。\n",
            evidence_type="uploaded_doc",
        )
        repo = add_claim(
            env,
            filename=f"t-repo-{index}.md",
            content=f"# 项目 {index}\n\n实现了 {name} 相关功能。\n",
            evidence_type="repo_artifact",
        )
        bind(env, cap, notes)
        bind(env, cap, repo)
        AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(capability_id=cap)
        capabilities.append(cap)
    return capabilities


# ---------------------------------------------------------------------------
# 1. G2 主判定
# ---------------------------------------------------------------------------


def test_g2_at_least_five_assessments_walk_to_source(env):
    _build_three_capabilities(env)
    traces = walk_all(env["store"], env["estore"])
    complete = [item for item in traces if item["complete"]]

    assert len(complete) >= 5, f"可追溯样本不足: {len(complete)}"
    for trace in complete:
        assert trace["trace_path"] == "supports"
        for claim in trace["claims"]:
            assert claim["classification"] == "admissible"
            assert claim["chain_complete"] is True
            assert claim["quote_verbatim"] is True
            assert claim["evidence_rows"] >= 1
            assert claim["sources"], "每条主张必须能回到来源"
            assert claim["channels"] == ["user_evidence"]


def test_g2_insufficient_rows_trace_via_capability_bindings(env):
    """`insufficient_evidence` 行没有支撑集（这是结论本身）—— 追溯走能力点的绑定集合；
    链路本身仍然完整（可采纳、逐字），缺的是「这个维度起评所需的证据」。"""
    cap = env["add_capability"]("仅自述", target_level=3)
    chat = add_claim(env, filename="t-chat.md", content="# 对话\n\n自述。\n", evidence_type="chat_assertion")
    bind(env, cap, chat)
    AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(capability_id=cap)

    traces = {
        item["dimension"]: item
        for item in walk_all(env["store"], env["estore"])
        if item["capability_id"] == cap
    }
    practice = traces["practice"]
    assert practice["status"] == "insufficient_evidence"
    assert practice["trace_path"] == "capability_bindings"
    assert practice["walkable"] is True
    assert practice["complete"] is True, "链路完整（证据可采纳且逐字）——不足的结论由此可复核"
    assert practice["claims"][0]["classification"] == "admissible"
    assert practice["claims"][0]["quote_verbatim"] is True


def test_g2_trace_surfaces_inadmissible_binding(env):
    """绑定的是待验证声明（`user_asserted`）→ 追溯不完整，并如实暴露原因。"""
    cap = env["add_capability"]("待验证声明", target_level=3)
    chat = add_claim(
        env,
        filename="t-chat2.md",
        content="# 对话\n\n用户自述。\n",
        evidence_type="chat_assertion",
        attribution="user_asserted",
    )
    bind(env, cap, chat)
    AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(capability_id=cap)

    traces = {
        item["dimension"]: item
        for item in walk_all(env["store"], env["estore"])
        if item["capability_id"] == cap
    }
    practice = traces["practice"]
    assert practice["trace_path"] == "capability_bindings"
    assert practice["walkable"] is True
    assert practice["complete"] is False, "待验证声明不是可采纳证据 → 追溯不完整"
    assert practice["claims"][0]["classification"] == "pending_declaration"


def test_g2_row_without_claims_is_not_walkable(env):
    """无支撑、也无绑定的评定行 → `none`，不得计入 G2 抽样。"""
    cap = env["add_capability"]("空能力点", target_level=3)
    AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(capability_id=cap)

    traces = [
        item
        for item in walk_all(env["store"], env["estore"])
        if item["capability_id"] == cap
    ]
    assert traces and all(item["trace_path"] == "none" for item in traces)
    assert all(item["walkable"] is False for item in traces)


# ---------------------------------------------------------------------------
# 2. 追溯器不是空转（缺环 / 篡改必须被发现）
# ---------------------------------------------------------------------------


def test_missing_evidence_rows_break_the_chain(env):
    _build_three_capabilities(env)
    victim = walk_all(env["store"], env["estore"])[0]
    claim_id = victim["claims"][0]["claim_id"]

    env["estore"].db.execute("DELETE FROM evidence WHERE claim_id=?", (claim_id,))
    env["estore"].db.commit()

    broken = trace_assessment(env["store"], env["estore"], victim["assessment_id"])
    assert broken["complete"] is False
    assert broken["claims"][0]["chain_complete"] is False
    assert "evidence 缺失" in broken["claims"][0]["missing"]


def test_non_verbatim_quote_breaks_the_chain(env):
    _build_three_capabilities(env)
    victim = walk_all(env["store"], env["estore"])[0]
    claim_id = victim["claims"][0]["claim_id"]

    rows = env["estore"].db.execute(
        "SELECT id, payload FROM evidence WHERE claim_id=?", (claim_id,)
    ).fetchall()
    for row_id, payload in rows:
        data = json.loads(payload)
        data["quote"] = "被篡改的引文（不逐字）"
        env["estore"].db.execute(
            "UPDATE evidence SET payload=? WHERE id=?", (json.dumps(data, ensure_ascii=False), row_id)
        )
    env["estore"].db.commit()

    broken = trace_assessment(env["store"], env["estore"], victim["assessment_id"])
    assert broken["complete"] is False
    assert broken["claims"][0]["quote_verbatim"] is False
