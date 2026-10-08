"""M4-d：能力解释报告 + `current_level` 回填 —— 验收测试。

按用户 2026-10-03 冻结的 9 项验收序列：

1. report 六项组成完整；2. support evidence 可回溯到 claim + quote；3. confidence 隔离；
4. excluded / reverse evidence 展示正确；5. current_level rebuild 一致；
6. 无评级 NULL/unassessed；7. draft 不影响 current view；8. audit_store pass/0；
9. artifacts 双份（JSON + Markdown）完整。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from growth_os.assessment import (
    PRACTICE,
    UNDERSTANDING,
    AssessmentDrafter,
    AssessmentRater,
    build_report,
    render_report,
    write_report,
)
from growth_os.evidence import adapter
from growth_os.store import ASSESSMENT_DIMENSIONS, GrowthStore, GrowthStoreError

GOAL_ID = "goal_m4d"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4d.db"
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

        def add_capability(name: str) -> str:
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

        yield {"db": db, "store": store, "estore": estore, "add_capability": add_capability, "tmp": tmp_path}
    finally:
        estore.db.close()
        store.close()


def add_claim(env, *, filename: str, content: str, evidence_type: str) -> str:
    target = env["tmp"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution="user_declared"
    )
    passage_ids = [item.id for item in env["estore"].get_passages(source_id=ingested.source_id)]
    return adapter.create_material_claim(
        env["estore"],
        subject="项目材料",
        predicate="包含",
        object="相关内容",
        statement=f"项目材料中包含相关内容（{filename}）",
        passage_ids=passage_ids[:1],
    )["claim_id"]


def bind(env, capability_id: str, claim_id: str) -> None:
    env["store"].link_capability_claim(
        capability_id, claim_id, role="supports", rationale="M4-b 闸门通过（等价写入）"
    )


def inject_attack(env, claim_id: str, verdict: str) -> None:
    env["estore"].db.execute(
        "CREATE TABLE IF NOT EXISTS attack_reports (id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
        " kind TEXT NOT NULL, target_id TEXT NOT NULL, payload TEXT NOT NULL,"
        " created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    payload = {
        "probe": {"target_claim_id": claim_id, "angle": "注入式测试", "question": "注入式测试质疑"},
        "verdict": {
            "target_claim_id": claim_id,
            "verdict": verdict,
            "reasoning": "注入式反例（测试）",
            "missing_evidence": ["用户角色说明"],
        },
    }
    env["estore"].db.execute(
        "INSERT INTO attack_reports(id,task_id,kind,target_id,payload) VALUES(?,?,?,?,?)",
        (f"rep_{claim_id}_{verdict}", "t", "adversarial", claim_id, json.dumps(payload, ensure_ascii=False)),
    )
    env["estore"].db.commit()


def add_refuting_evidence(env, claim_id: str) -> None:
    from evkg.domain import EvidenceLink, Polarity

    claim = next(item for item in env["estore"].get_claims() if item.id == claim_id)
    passage_id = claim.passage_ids[0]
    passage = next(item for item in env["estore"].get_passages() if item.id == passage_id)
    env["estore"].save_evidence(
        EvidenceLink(
            id=f"evr_{claim_id}",
            claim_id=claim_id,
            passage_id=passage_id,
            polarity=Polarity.REFUTES,
            quote=passage.text,
            reasoning="注入式反向证据",
            confidence=None,
        )
    )


def rate(env, capability_id: str) -> dict:
    return AssessmentRater(store=env["store"], evidence_store=env["estore"]).rate(
        capability_id=capability_id
    )


# ---------------------------------------------------------------------------
# 1. report 组成完整
# ---------------------------------------------------------------------------


def test_report_has_all_required_sections(env):
    cap = env["add_capability"]("报告组成")
    notes = add_claim(env, filename="n.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="r.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    rate(env, cap)
    env["store"].apply_assessment_levels(cap)

    report = build_report(env["store"], env["estore"], capability_id=cap)
    for key in (
        "capability",
        "dimensions",
        "supports",
        "gaps",
        "reverse_evidence",
        "excluded",
        "rule_version",
    ):
        assert key in report, f"缺少报告组成：{key}"
    for dimension in ASSESSMENT_DIMENSIONS:
        body = report["dimensions"][dimension]
        for field in ("level", "status", "rationale", "why_not_higher"):
            assert field in body, f"{dimension} 缺少字段：{field}"
    assert report["dimensions"][UNDERSTANDING]["level"] == 2
    assert report["dimensions"][PRACTICE]["level"] == 3
    assert report["rule_version"] == "m4c-1"
    assert report["read_only"] is True


# ---------------------------------------------------------------------------
# 2. support evidence 可回溯
# ---------------------------------------------------------------------------


def test_support_evidence_walks_back_to_source_quote(env):
    cap = env["add_capability"]("可回溯")
    repo = add_claim(env, filename="trace.md", content="# 项目\n\n实现了 RAG 检索服务。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    rate(env, cap)

    report = build_report(env["store"], env["estore"], capability_id=cap)
    support = next(item for item in report["supports"] if item["claim_id"] == repo)
    assert support["present"] is True
    assert support["statement"]
    assert support["binding_rationale"], "必须保留绑定理由"
    assert support["quotes"], "必须有逐字引文"
    quotes = support["quotes"]
    assert all(item["quote_verbatim"] is True for item in quotes)
    assert all(item["source_id"] for item in quotes)
    # 引文必须真的来自库中 passage
    for item in quotes:
        passage = next(
            p for p in env["estore"].get_passages() if p.id == item["passage_id"]
        )
        assert item["quote"] in passage.text


# ---------------------------------------------------------------------------
# 3. confidence 隔离
# ---------------------------------------------------------------------------


def test_report_does_not_leak_model_scores(env):
    cap = env["add_capability"]("分数隔离")
    repo = add_claim(env, filename="c.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    rate(env, cap)
    report = build_report(env["store"], env["estore"], capability_id=cap)
    dumped = json.dumps(report, ensure_ascii=False)
    assert "confidence" not in dumped, "报告不得携带分级分数（D6）"

    source = (
        Path(__file__).resolve().parents[1] / "backend/growth_os/assessment/report.py"
    ).read_text(encoding="utf-8")
    offenders = [
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and node.attr == "confidence"
    ]
    assert offenders == [], f"报告渲染器不得读取分级分数：{offenders}"


# ---------------------------------------------------------------------------
# 4. excluded / reverse evidence 展示正确
# ---------------------------------------------------------------------------


def test_excluded_and_reverse_evidence_rendered(env):
    cap = env["add_capability"]("反向展示")
    notes = add_claim(env, filename="er-n.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo_keep = add_claim(env, filename="er-r1.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    repo_broken = add_claim(env, filename="er-r2.md", content="# 项目2\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo_keep)
    bind(env, cap, repo_broken)
    add_refuting_evidence(env, repo_keep)
    inject_attack(env, repo_broken, "broken")
    rate(env, cap)

    report = build_report(env["store"], env["estore"], capability_id=cap)
    # 反向证据：refutes 封顶记录 + 证据行 + 裁决
    reverse = next(item for item in report["reverse_evidence"] if item["claim_id"] == repo_keep)
    assert reverse["cap"] == 2
    assert reverse["refuting_evidence"], "必须展示 refutes 证据行"
    # 已排除：broken 主张 + 裁决理由 + 未确认项
    excluded = next(item for item in report["excluded"] if item["claim_id"] == repo_broken)
    assert "broken" in excluded["reason"]
    broken_attack = next(a for a in excluded["attacks"] if a["verdict"] == "broken")
    assert broken_attack["reasoning"] and broken_attack["missing_evidence"]

    markdown = render_report(report)
    assert "## 四、反向证据" in markdown and "## 五、已排除的证据" in markdown
    assert "`broken`" in markdown
    assert "逐字=True" in markdown


def test_evidence_api_reports_attacks_and_reverse_evidence_without_writes(env):
    from fastapi.testclient import TestClient
    from growth_os.api import create_app

    cap = env["add_capability"]("只读攻击详情")
    keep = add_claim(env, filename="api-keep.md", content="# 项目\n\n实现检索。\n", evidence_type="repo_artifact")
    broken = add_claim(env, filename="api-broken.md", content="# 项目\n\n实现重排。\n", evidence_type="repo_artifact")
    bind(env, cap, keep)
    bind(env, cap, broken)
    add_refuting_evidence(env, keep)
    inject_attack(env, broken, "broken")
    rate(env, cap)
    before = list(env["store"].db.iterdump())
    env["store"].db.execute("PRAGMA query_only=ON")
    env["estore"].db.execute("PRAGMA query_only=ON")
    response = TestClient(create_app(env["store"], env["estore"])).get(f"/api/evidence/{cap}")
    assert response.status_code == 200
    report = response.json()["report"]
    assert broken not in {item["claim_id"] for item in response.json()["supports"]}
    assert report["read_only"] is True
    assert any(item["claim_id"] == keep and item["refuting_evidence"] for item in report["reverse_evidence"])
    assert any(item["claim_id"] == broken for item in report["excluded"])
    review = next(item for item in report["attack_reviews"] if item["claim_id"] == broken)
    assert review["attacks"][0]["verdict"] == "broken"
    assert review["attacks"][0]["reasoning"]
    assert report["limitations"]
    assert list(env["store"].db.iterdump()) == before


def test_sustained_attack_stays_visible_without_reverse_evidence(env):
    cap = env["add_capability"]("维持裁决")
    claim = add_claim(env, filename="sustained.md", content="# 项目\n\n实现检索。\n", evidence_type="repo_artifact")
    bind(env, cap, claim)
    inject_attack(env, claim, "sustained")
    rate(env, cap)
    report = build_report(env["store"], env["estore"], capability_id=cap)
    assert report["reverse_evidence"] == []
    assert report["attack_reviews"][0]["attacks"][0]["verdict"] == "sustained"


# ---------------------------------------------------------------------------
# 5. current_level rebuild 一致
# ---------------------------------------------------------------------------


def test_current_level_rebuild_consistency(env):
    cap = env["add_capability"]("重建一致")
    notes = add_claim(env, filename="rb-n.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="rb-r.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)
    rate(env, cap)

    applied = env["store"].apply_assessment_levels(cap)
    assert applied == {"understanding": 2, "practice": 3, "status": "assessed"}
    check = env["store"].verify_assessment_levels(cap)
    assert check["consistent"] is True

    row = env["store"].get_capability(cap)
    assert row["current_level_understanding"] == 2 and row["current_level_practice"] == 3
    assert row["current_level_status"] == "assessed"
    assert row["current_level"] is None, "legacy 列保持 NULL（deprecated）"

    # 人为篡改 → 重建校验必须发现不一致
    env["store"].db.execute(
        "UPDATE g_capabilities SET current_level_practice=5 WHERE id=?", (cap,)
    )
    env["store"].db.commit()
    assert env["store"].verify_assessment_levels(cap)["consistent"] is False

    # 重新回填 → 恢复一致
    env["store"].apply_assessment_levels(cap)
    assert env["store"].verify_assessment_levels(cap)["consistent"] is True

    # 结论变化 → 重新回填后列值跟随（broken 剔除实践证据）
    inject_attack(env, repo, "broken")
    rate(env, cap)
    env["store"].apply_assessment_levels(cap)
    row = env["store"].get_capability(cap)
    assert row["current_level_practice"] is None and row["current_level_understanding"] == 2
    assert row["current_level_status"] == "assessed", "部分评估状态（理解有、实践无）"


def test_backfill_is_the_only_write_path(env):
    cap = env["add_capability"]("写路径")
    with pytest.raises(GrowthStoreError, match="current_level_understanding"):
        env["store"].upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "LLM 基础/检索增强/写路径",
                "name": "写路径",
                "depth": 3,
                "target_level": 3,
                "current_level_understanding": 3,
            }
        )
    with pytest.raises(GrowthStoreError, match="current_level"):
        env["store"].upsert_capability(
            {
                "goal_id": GOAL_ID,
                "path": "LLM 基础/检索增强/写路径",
                "name": "写路径",
                "depth": 3,
                "target_level": 3,
                "current_level": 3,
            }
        )
    assert cap  # 上一行的能力点不受影响


# ---------------------------------------------------------------------------
# 6. 无评级 → NULL / unassessed
# ---------------------------------------------------------------------------


def test_no_rating_gives_null_and_unassessed(env):
    cap = env["add_capability"]("无评级")
    applied = env["store"].apply_assessment_levels(cap)
    assert applied == {"understanding": None, "practice": None, "status": "unassessed"}
    row = env["store"].get_capability(cap)
    assert row["current_level_understanding"] is None and row["current_level_practice"] is None
    assert row["current_level_status"] == "unassessed"
    assert env["store"].verify_assessment_levels(cap)["consistent"] is True

    report = build_report(env["store"], env["estore"], capability_id=cap)
    for dimension in ASSESSMENT_DIMENSIONS:
        assert report["dimensions"][dimension]["level"] is None
        assert report["dimensions"][dimension]["status"] == "unassessed"


# ---------------------------------------------------------------------------
# 7. draft 不影响 current view
# ---------------------------------------------------------------------------


def test_draft_does_not_affect_current_view(env):
    cap = env["add_capability"]("草案不影响")
    repo = add_claim(env, filename="d.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    draft = AssessmentDrafter(store=env["store"], evidence_store=env["estore"]).draft(
        capability_id=cap, claim_ids=[repo]
    )
    env["store"].apply_assessment_levels(cap)
    row = env["store"].get_capability(cap)
    assert row["current_level_status"] == "unassessed", "草案不算评定结果"
    assert row["current_level_practice"] is None

    rate(env, cap)
    env["store"].apply_assessment_levels(cap)
    row = env["store"].get_capability(cap)
    assert row["current_level_status"] == "assessed" and row["current_level_practice"] == 3
    assert env["store"].get_assessment(draft["assessment_id"])["status"] == "draft", "草案保留"


# ---------------------------------------------------------------------------
# 8. audit_store / 9. 产物双份
# ---------------------------------------------------------------------------


def test_audit_store_passes_after_backfill_and_report(env):
    cap = env["add_capability"]("审计")
    repo = add_claim(env, filename="a.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    rate(env, cap)
    env["store"].apply_assessment_levels(cap)
    build_report(env["store"], env["estore"], capability_id=cap)
    result = adapter.audit(env["db"])
    assert result["status"] == "pass" and result["total_violations"] == 0


def test_write_report_produces_json_and_markdown(env):
    cap = env["add_capability"]("产物双份")
    notes = add_claim(env, filename="w.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    rate(env, cap)
    env["store"].apply_assessment_levels(cap)
    report = build_report(env["store"], env["estore"], capability_id=cap)

    paths = write_report(report, directory=env["tmp"] / "out", stem="report-test")
    assert Path(paths["json"]).is_file() and Path(paths["markdown"]).is_file()
    data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert data["capability"]["id"] == cap
    markdown = Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "LLM 基础/检索增强/产物双份" in markdown
    assert "## 七、本报告不能成立的结论" in markdown
