"""G6-a 的来源约束、维度差异与零写入反例。"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from growth_os.agent import FakeGateway
from growth_os.agent.return_summary import GrowthReturnAgent, ReturnSummaryError
from growth_os.api import create_app
from growth_os.assessment import BINDING_TASK, TaskLoop
from growth_os.evidence import adapter
from growth_os.memory import MemoryProjection, MemoryService
from growth_os.store import GrowthStore
from task_loop_fixtures import create_active_task, make_binding_proposer, seed_scenario


@pytest.fixture()
def env(tmp_path):
    store = GrowthStore(str(tmp_path / "return.db"))
    evidence = adapter.open_store(tmp_path / "return.db")
    try:
        scenario = seed_scenario(store, evidence, tmp_path, leaf_only=True)
        projection = MemoryProjection(store)
        baseline = projection.project()["snapshots"][0]["id"]
        task = create_active_task(store, scenario["gaps"]["practice"])
        yield {"store": store, "evidence": evidence, "scenario": scenario,
               "baseline": baseline, "task": task, "directory": tmp_path,
               "agent": GrowthReturnAgent(store)}
    finally:
        evidence.db.close()
        store.close()


def complete(env):
    artifact = env["directory"] / "submission.md"
    artifact.write_text("# 受控评测报告\n\n十条样本和判定标准。\n", encoding="utf-8")
    loop = TaskLoop(store=env["store"], evidence_store=env["evidence"],
                    gateway=FakeGateway({BINDING_TASK: make_binding_proposer(
                        path=env["scenario"]["capability_path"]) }),
                    submission_dir=env["directory"] / "submissions")
    outcome = asyncio.run(loop.complete_task(env["task"], artifact_path=artifact))
    MemoryProjection(env["store"]).project()
    current = next(row["id"] for row in env["store"].list_snapshots()
                   if row["id"] != env["baseline"])
    return current, outcome


def summarize(env, current=None, **options):
    payload = {"goal_id": env["scenario"]["goal_id"],
               "baseline_snapshot_id": env["baseline"],
               "current_snapshot_id": current or env["baseline"],
               "returned_at": datetime.now(UTC) + timedelta(days=1)}
    payload.update(options)
    return env["agent"].summarize(**payload)


def test_actual_loop_changes_practice_only_and_keeps_provenance(env):
    memory = MemoryService(env["store"]).remember(
        layer="profile", key="learning_style", value={"text": "喜欢代码实践"},
        source_kind="user_statement", source_id="statement_return_preference")
    current, outcome = complete(env)
    result = summarize(env, current)
    assert result["mode"] == "deterministic_read_only"
    assert result["summary"]["status"] == "changed"
    assert len(result["summary"]["changes"]) == 1
    change = result["summary"]["changes"][0]
    assert (change["dimension"], change["before_level"], change["after_level"]) == ("practice", 3, 4)
    assert change["after_assessment_id"] == outcome["attribution"]["after"]["practice"]["assessment_id"]
    assert change["before_assessment_id"] and change["baseline_snapshot_id"]
    assert result["current_state"][0]["understanding"] == 2
    assert result["preferences"][0]["memory_id"] == memory["id"]
    assert result["preferences"][0]["source_id"] == "statement_return_preference"
    assert result["next_steps"][0]["gap_id"] == env["scenario"]["gaps"]["understanding"]["id"]


def test_summary_is_read_only_even_with_query_only_storage(env):
    before = list(env["store"].db.iterdump())
    env["store"].db.execute("PRAGMA query_only=ON")
    result = summarize(env)
    assert result["summary"]["status"] == "unchanged"
    assert result["next_steps"]
    assert list(env["store"].db.iterdump()) == before


def test_missing_baseline_and_preferences_are_explicit(env):
    result = summarize(env, baseline_snapshot_id=None)
    assert result["summary"]["status"] == "baseline_missing"
    assert result["summary"]["changes"] == []
    assert "无法比较" in result["summary"]["text"]
    assert result["preferences"] == []
    assert "尚未记录" in result["preference_text"]


@pytest.mark.parametrize("status", ["active", "proposed", "blocked"])
def test_existing_task_is_referenced_without_generating_task(env, status):
    store = env["store"]
    if status == "blocked":
        store.block_task(env["task"], "等待材料")
    if status == "proposed":
        store.abandon_task(env["task"], "受控替换")
        from task_loop_fixtures import task_payload

        env["task"] = store.create_task(task_payload(env["scenario"]["gaps"]["practice"]["id"],
                                                    generated_by_run_id="return_proposed"))
    before = len(store.list_tasks())
    result = summarize(env)
    steps = [step for step in result["next_steps"] if step["task_id"] == env["task"]]
    assert len(steps) == 1
    assert steps[0]["kind"] == "existing_task"
    assert len(store.list_tasks()) == before
    assert ("先解除阻塞" if status == "blocked" else "确认任务" if status == "proposed"
            else "继续任务") in steps[0]["text"]


def test_done_task_does_not_imply_level_change(env):
    source = env["evidence"].get_passages()[0].source_id
    env["store"].complete_task(env["task"], source_id=source, note="受控存储反例，未经重评")
    result = summarize(env)
    assert result["summary"]["status"] == "unchanged"
    assert result["current_state"][0]["practice"] == 3
    assert all(step["task_id"] != env["task"] for step in result["next_steps"])


@pytest.mark.parametrize("options", [
    {"goal_id": "missing"}, {"current_snapshot_id": "missing"},
    {"baseline_snapshot_id": "missing"}, {"user_id": "other"},
    {"returned_at": datetime(2000, 1, 1, tzinfo=UTC)},
    {"returned_at": datetime(2026, 10, 5)},  # noqa: DTZ001 — 验证拒绝无时区输入
])
def test_unknown_sources_and_invalid_times_are_rejected(env, options):
    with pytest.raises(ReturnSummaryError):
        summarize(env, **options)


def test_stale_current_snapshot_and_reversed_snapshots_are_rejected(env):
    current, _ = complete(env)
    with pytest.raises(ReturnSummaryError, match="过时"):
        summarize(env)
    with pytest.raises(ReturnSummaryError, match="历史子集"):
        summarize(env, current=env["baseline"], baseline_snapshot_id=current)


@pytest.mark.parametrize("field,value", [("level", 5), ("dimension", "understanding")])
def test_tampered_snapshot_does_not_fabricate_growth(env, field, value):
    row = env["store"].get_snapshot(env["baseline"])
    scores = json.loads(row["scores_json"])
    scores[0][field] = ("practice" if scores[0][field] == "understanding" else "understanding") if field == "dimension" else value
    env["store"].insert_snapshot({**row, "id": "snap_tampered",
                                  "scores_json": json.dumps(scores)})
    with pytest.raises(ReturnSummaryError, match="不一致"):
        summarize(env, current="snap_tampered")


def test_snapshot_of_another_user_or_goal_is_rejected(env):
    store = env["store"]
    row = store.get_snapshot(env["baseline"])
    store.upsert_user("other", "其他用户")
    store.insert_snapshot({**row, "id": "snap_other", "user_id": "other"})
    with pytest.raises(ReturnSummaryError, match="不属于"):
        summarize(env, current="snap_other")
    store.save_goal({"id": "other_goal", "user_id": "local", "title": "其他目标",
                     "direction": "AI", "purpose": "学习", "horizon": "一个月",
                     "measurable_result": "产出报告", "status": "confirmed", "source_quote": "确认"})
    with pytest.raises(ReturnSummaryError, match="不包含目标"):
        summarize(env, goal_id="other_goal")


def test_insufficient_evidence_is_not_a_zero_or_an_improvement(env):
    store = env["store"]
    capability = env["scenario"]["capability"]
    store.save_assessment({"capability_id": capability, "dimension": "practice",
                           "status": "insufficient_evidence", "level": None,
                           "claim_ids": [], "rubric": {"contract": "m4c-1"},
                           "rationale": "受控反例：证据不可用"})
    store.apply_assessment_levels(capability)
    store.apply_gaps(capability)
    MemoryProjection(store).project()
    current = next(row["id"] for row in store.list_snapshots() if row["id"] != env["baseline"])
    result = summarize(env, current)
    change = result["summary"]["changes"][0]
    assert change["status"] == "insufficient_evidence"
    assert change["after_level"] is None
    assert "证据不足" in change["text"]


def test_only_active_explicit_preference_is_returned(env):
    memory = MemoryService(env["store"])
    memory.remember(layer="profile", key="preference", value={"text": "先读笔记"},
                    source_kind="user_statement", source_id="statement_old")
    latest = memory.remember(layer="profile", key="preference", value={"text": "先做实验"},
                             source_kind="user_statement", source_id="statement_new")
    result = summarize(env)
    assert [item["memory_id"] for item in result["preferences"]] == [latest["id"]]
    assert "先读笔记" not in result["preference_text"]


def test_return_api_is_get_only_and_rejects_invalid_snapshots(env):
    client = TestClient(create_app(env["store"], env["evidence"]))
    url = f"/api/return/{env['scenario']['goal_id']}"
    assert client.get(url).status_code == 422
    params = {"current_snapshot_id": env["baseline"], "baseline_snapshot_id": env["baseline"]}
    response = client.get(url, params=params)
    assert response.status_code == 200
    assert response.json()["summary"]["status"] == "unchanged"
    assert client.get(url, params={"current_snapshot_id": "missing"}).status_code == 422
    assert client.post(url, json=params).status_code == 405
