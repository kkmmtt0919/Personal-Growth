"""M4-e：统一编排 `assess_capability` —— 顺序 / fail-stop / 幂等 / 离线。

冻结口径（用户 2026-10-03）：

```text
rate → report → apply_assessment_levels → verify_assessment_levels
     → apply_gaps → verify_gaps
```

* 编排纯确定性、**无 LLM、无网络、无隐式副作用**；
* `verify_*` 失败即 fail-stop（不继续写缺口、不返回"看起来成功"的结果）；
* 幂等：同证据集重复运行 → 同评定行与同缺口行。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from growth_os.assessment import (
    PIPELINE_VERSION,
    PipelineError,
    assess_capability,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore

GOAL_ID = "goal_m4e_pipeline"


@pytest.fixture()
def env(tmp_path: Path):
    db = tmp_path / "m4e-pipe.db"
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


def add_claim(env, *, filename: str, content: str, evidence_type: str) -> str:
    target = env["tmp"] / filename
    target.write_text(content, encoding="utf-8")
    ingested = adapter.ingest_document(
        target, store=env["estore"], evidence_type=evidence_type, attribution="user_declared"
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
# 1. 全链：rate → report → apply → verify → gaps → verify
# ---------------------------------------------------------------------------


def test_full_chain_produces_rating_backfill_and_gaps(env):
    cap = env["add_capability"]("全链", target_level=4)
    notes = add_claim(env, filename="p-notes.md", content="# 笔记\n\nRAG 检索流程整理。\n", evidence_type="uploaded_doc")
    repo = add_claim(env, filename="p-repo.md", content="# 项目\n\n实现了 RAG 检索。\n", evidence_type="repo_artifact")
    bind(env, cap, notes)
    bind(env, cap, repo)

    out = assess_capability(
        env["store"],
        env["estore"],
        capability_id=cap,
        report_directory=env["tmp"] / "reports",
        report_stem="cap-pipeline",
    )

    assert out["contract"] == PIPELINE_VERSION
    assert {key: (body["status"], body["level"]) for key, body in out["dimensions"].items()} == {
        "understanding": ("rated", 2),
        "practice": ("rated", 3),
    }
    assert out["levels"] == {"understanding": 2, "practice": 3, "status": "assessed"}
    assert out["level_verification"]["consistent"] is True
    assert out["gap_verification"]["consistent"] is True

    stored = env["store"].get_capability(cap)
    assert stored["current_level_understanding"] == 2
    assert stored["current_level_practice"] == 3
    assert stored["current_level_status"] == "assessed"
    assert stored["current_level"] is None

    gaps = {item["dimension"]: item for item in out["gaps"]}
    assert gaps["understanding"]["severity"] == "level_gap_2plus"
    assert gaps["practice"]["severity"] == "level_gap_1"

    paths = out["report_paths"]
    assert Path(paths["json"]).exists() and Path(paths["markdown"]).exists()
    report = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert report["read_only"] is True
    assert report["capability"]["current_level_practice"] == 3


def test_report_derives_from_assessments_not_backfill_cache(env):
    """report 在 apply 之前生成 —— 必须从评定行重算，不得写回填缓存里的旧值。"""
    cap = env["add_capability"]("报告派生", target_level=4)
    repo = add_claim(env, filename="p-repo2.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)

    # 人为把回填缓存改成错误值（模拟"报告若读缓存就会写旧值"的场景）
    env["store"].db.execute(
        "UPDATE g_capabilities SET current_level_practice=1, current_level_status='assessed' WHERE id=?",
        (cap,),
    )
    env["store"].db.commit()

    out = assess_capability(env["store"], env["estore"], capability_id=cap)
    assert out["report"]["capability"]["current_level_practice"] == 3
    assert out["report"]["capability"]["current_level_status"] == "assessed"
    # 回填本身把缓存修复为派生值
    assert env["store"].get_capability(cap)["current_level_practice"] == 3


# ---------------------------------------------------------------------------
# 2. fail-stop
# ---------------------------------------------------------------------------


def test_fail_stop_when_level_backfill_inconsistent(env, monkeypatch):
    cap = env["add_capability"]("回填失败即停", target_level=4)
    notes = add_claim(env, filename="p-notes2.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)

    def broken_verify(self, capability_id):
        return {"consistent": False, "expected": {"understanding": 2}, "stored": {}}

    monkeypatch.setattr(GrowthStore, "verify_assessment_levels", broken_verify)
    with pytest.raises(PipelineError, match="回填重建校验不一致"):
        assess_capability(env["store"], env["estore"], capability_id=cap)

    # fail-stop：缺口不写（评定行已写，因为 rate 先于校验）
    assert env["store"].list_gaps(capability_id=cap) == []
    assert env["store"].list_assessments(capability_id=cap)


def test_fail_stop_when_gap_verification_inconsistent(env, monkeypatch):
    cap = env["add_capability"]("缺口失败即停", target_level=4)
    notes = add_claim(env, filename="p-notes3.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)

    def broken_verify(self, capability_id):
        return {"consistent": False, "expected": [], "stored": [{"id": "x"}]}

    monkeypatch.setattr(GrowthStore, "verify_gaps", broken_verify)
    with pytest.raises(PipelineError, match="缺口重建校验不一致"):
        assess_capability(env["store"], env["estore"], capability_id=cap)


# ---------------------------------------------------------------------------
# 3. 幂等 + 历史保留
# ---------------------------------------------------------------------------


def test_pipeline_is_idempotent(env):
    cap = env["add_capability"]("幂等", target_level=4)
    notes = add_claim(env, filename="p-notes4.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)

    first = assess_capability(env["store"], env["estore"], capability_id=cap)
    second = assess_capability(env["store"], env["estore"], capability_id=cap)

    assert first["assessment_ids"] == second["assessment_ids"]
    assert first["levels"] == second["levels"]
    assert [item["id"] for item in first["gaps"]] == [item["id"] for item in second["gaps"]]
    assert len(env["store"].list_assessments(capability_id=cap)) == 2  # 两维度各一行
    assert len(env["store"].list_gaps(capability_id=cap)) == 2


def test_history_preserved_when_evidence_changes_level(env):
    cap = env["add_capability"]("历史保留", target_level=4)
    notes = add_claim(env, filename="p-notes5.md", content="# 笔记\n\n整理。\n", evidence_type="uploaded_doc")
    bind(env, cap, notes)
    first = assess_capability(env["store"], env["estore"], capability_id=cap)
    assert first["dimensions"]["practice"]["status"] == "insufficient_evidence"

    repo = add_claim(env, filename="p-repo3.md", content="# 项目\n\n实现。\n", evidence_type="repo_artifact")
    bind(env, cap, repo)
    second = assess_capability(env["store"], env["estore"], capability_id=cap)

    history = {
        row["id"]: (row["dimension"], row["status"], row["level"])
        for row in env["store"].list_assessments(capability_id=cap)
    }
    old_practice = first["dimensions"]["practice"]["assessment_id"]
    new_practice = second["dimensions"]["practice"]["assessment_id"]
    assert old_practice in history and history[old_practice] == ("practice", "insufficient_evidence", None)
    assert new_practice in history and history[new_practice] == ("practice", "rated", 3)
    assert env["store"].latest_assessment(cap, "practice")["id"] == new_practice


# ---------------------------------------------------------------------------
# 4. 编排保持离线（无 LLM / 无网络）
# ---------------------------------------------------------------------------


def test_pipeline_module_stays_offline():
    import growth_os.assessment.pipeline as pipeline_module

    source = Path(pipeline_module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "gateway",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "random",
        "confidence",
    ):
        assert forbidden not in source, f"编排模块混入非确定性/网络依赖: {forbidden}"

    # 结构检查：包内相对导入只允许 rater / report（评定与报告），不得接 bind/attack 的 LLM 路径
    tree = ast.parse(source)
    relative: set[tuple[int, str]] = set()
    absolute: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            relative.add((node.level, node.module or ""))
        else:
            absolute.add(node.module or "")
    assert relative == {(1, "rater"), (1, "report")}, f"编排包内依赖越界: {sorted(relative)}"
    assert absolute <= {"__future__", "pathlib"}, f"编排外部依赖越界: {sorted(absolute)}"
