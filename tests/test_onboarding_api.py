import json

import pytest
from fastapi.testclient import TestClient
from growth_os.agent import FakeGateway
from growth_os.api.onboarding import (
    create_local_onboarding_app,
    create_onboarding_app,
    seed_onboarding,
)
from growth_os.goal import require_confirmed_goal
from growth_os.store import GrowthStore


def confirmed_session(client, request_id):
    state = client.post("/api/onboarding/goals", json={"request_id": request_id, "text": request_id}).json()
    base = f"/api/onboarding/goals/{state['goal']['id']}"
    for index, text in enumerate(["写作", "作品集", "三个月", "三篇文章"], 1):
        assert client.post(base + "/answers", json={"round": index, "text": text}).status_code == 200
    assert client.post(base + "/confirm", json={"quote": "确认写作目标"}).status_code == 200
    return base


def test_capability_generation_replay_isolation_and_reopen(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    with TestClient(create_local_onboarding_app()) as client:
        draft = client.post("/api/onboarding/goals", json={"request_id": "draft_tree", "text": "草稿"}).json()
        draft_base = f"/api/onboarding/goals/{draft['goal']['id']}"
        assert client.post(draft_base + "/capabilities").status_code == 409
        base = confirmed_session(client, "tree_request_one")
        result = client.post(base + "/capabilities")
        assert result.status_code == 200, result.text
        state = result.json()
        nodes = state["capabilities"]
        assert len(nodes) == 21
        assert sum(node["depth"] == 3 for node in nodes) == 12
        assert all(node["current_level"] is None and node["verification_status"] == "unverified" for node in nodes)
        assert all("演示模板" in node["source_note"] and node["generated_by_run_id"] for node in nodes)
        assert client.post(base + "/capabilities").json() == state
        other = confirmed_session(client, "tree_request_two")
        assert client.get(other).json()["capabilities"] == []
        assert client.get(draft_base).json()["capabilities"] == []
    with TestClient(create_local_onboarding_app()) as client:
        assert client.get(base).json() == state
        assert client.post(base + "/capabilities").json() == state
    with GrowthStore(str(tmp_path / "onboarding.db")) as store:
        assert store.db.execute("SELECT COUNT(*) FROM g_agent_runs WHERE agent='capability_model'").fetchone()[0] == 1


def test_invalid_tree_has_no_partial_writes_and_can_retry(tmp_path):
    from growth_os.api.onboarding import template_tree

    with GrowthStore(str(tmp_path / "tree.db")) as store:
        store.upsert_user("local", "用户")
        client = TestClient(create_onboarding_app(store))
        base = confirmed_session(client, "tree_failure")
        gateway = FakeGateway(responses={"capability_model": {"nodes": []}})
        client = TestClient(create_onboarding_app(store, gateway=gateway))
        assert client.post(base + "/capabilities").status_code == 422
        assert client.get(base).json()["capabilities"] == []
        gateway.responses["capability_model"] = template_tree()
        assert client.post(base + "/capabilities").status_code == 200
        assert len(gateway.calls) == 2


def test_four_elements_confirmation_and_reopen(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    payload = {"request_id": "onboarding_request", "text": "我想做 AI 应用工程"}
    with TestClient(create_local_onboarding_app()) as client:
        response = client.post("/api/onboarding/goals", json=payload)
        assert response.status_code == 200
        state = response.json()
        goal_id = state["goal"]["id"]
        base = f"/api/onboarding/goals/{goal_id}"
        assert client.post("/api/onboarding/goals", json=payload).json() == state
        assert client.post("/api/onboarding/goals", json={**payload, "text": "其他目标"}).status_code == 409
        assert client.post(base + "/confirm", json={"quote": "确认"}).status_code == 409
        for index, answer in enumerate(["AI应用开发", "求职", "六个月", "完成两个可演示项目"], 1):
            response = client.post(base + "/answers", json={"round": index, "text": answer})
            assert response.status_code == 200, response.text
            state = response.json()
            assert client.post(base + "/answers", json={"round": index, "text": answer}).json() == state
            assert client.post(base + "/answers", json={"round": index, "text": "修改历史回答"}).status_code == 409
        assert state["goal"]["status"] == "proposed"
        assert state["goal"]["source_quote"] is None
        quote = "我确认以六个月内完成两个AI应用项目为目标"
        confirmed = client.post(base + "/confirm", json={"quote": quote})
        assert confirmed.status_code == 200
        assert confirmed.json()["goal"]["status"] == "confirmed"
        assert confirmed.json()["goal"]["source_quote"] == quote
        assert client.post(base + "/confirm", json={"quote": quote}).json() == confirmed.json()
    with TestClient(create_local_onboarding_app()) as client:
        assert client.get(base).json() == confirmed.json()
        assert len(client.get("/api/onboarding").json()["goals"]) == 1
    with GrowthStore(str(tmp_path / "onboarding.db")) as store:
        assert require_confirmed_goal(store, goal_id)["direction"] == "AI应用开发"
        assert len(store.list_clarifications(goal_id)) == 5
        assert len(store.list_capabilities(goal_id)) == 0
        runs = store.db.execute("SELECT COUNT(*) FROM g_agent_runs").fetchone()[0]
        assert runs == 5


def test_failed_question_preserves_answers_and_manual_resume(tmp_path):
    store = GrowthStore(str(tmp_path / "failure.db"))
    store.upsert_user("local", "本地用户")
    gateway = FakeGateway(responses={"goal_clarification": [
        {"question": "你的方向是什么？"}, {"question": "你的目的是什么？"},
    ]})
    try:
        client = TestClient(create_onboarding_app(store, gateway=gateway))
        state = client.post("/api/onboarding/goals", json={"request_id": "failure_request", "text": "成为工程师"}).json()
        base = f"/api/onboarding/goals/{state['goal']['id']}"
        gateway.fail_with["goal_clarification"] = RuntimeError("injected")
        assert client.post(base + "/answers", json={"round": 1, "text": "AI应用"}).status_code == 502
        current = client.get(base).json()
        assert current["needs_retry"] is True
        assert current["history"][0]["answer"] == "AI应用"
        assert client.post(base + "/answers", json={"round": 1, "text": "AI应用"}).json() == current
        assert len(gateway.calls) == 2
        gateway.fail_with.clear()
        recovered = client.post(base + "/resume", json={})
        assert recovered.status_code == 200
        assert recovered.json()["pending"]["round"] == 2
        assert len(gateway.calls) == 3
        assert client.post(base + "/resume", json={}).status_code == 409
        assert len(gateway.calls) == 3
    finally:
        store.close()


def test_limit_and_invalid_requests(tmp_path):
    store = GrowthStore(str(tmp_path / "limit.db"))
    store.upsert_user("local", "本地用户")
    gateway = FakeGateway(responses={"goal_clarification": {"question": "请补充目标"}})
    try:
        client = TestClient(create_onboarding_app(store, gateway=gateway))
        start = {"request_id": "limit_request", "text": "目标"}
        assert client.post("/api/onboarding/goals", json=start, headers={"Origin": "https://outside.example"}).status_code == 403
        state = client.post("/api/onboarding/goals", json=start).json()
        base = f"/api/onboarding/goals/{state['goal']['id']}"
        assert client.post(base + "/answers", json={"round": 2, "text": "跳过问题"}).status_code == 409
        assert client.post(base + "/answers", json={"round": 1, "text": "  "}).status_code == 422
        assert client.post(base + "/confirm", json={"quote": "确认", "status": "confirmed"}).status_code == 422
        for round_ in range(1, 6):
            assert client.post(base + "/answers", json={"round": round_, "text": "补充"}).status_code == 200
        assert client.post(base + "/answers", json={"round": 6, "text": "补充"}).status_code == 409
        assert len(gateway.calls) == 6
        assert client.post(base + "/resume", json={}).status_code == 409
        assert len(gateway.calls) == 6
        assert client.get("/api/onboarding/goals/missing").status_code == 404
    finally:
        store.close()


def test_seed_refuses_overwrite_and_parallel_service(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    before = (tmp_path / "onboarding.db").read_bytes()
    with pytest.raises(ValueError, match="不覆盖"):
        seed_onboarding(tmp_path)
    assert (tmp_path / "onboarding.db").read_bytes() == before
    assert json.loads((tmp_path / "manifest.json").read_text())["onboarding_enabled"] is True
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    with TestClient(create_local_onboarding_app()), pytest.raises(RuntimeError, match="单进程"):
        create_local_onboarding_app()
