import json

import pytest
from fastapi.testclient import TestClient
from growth_os.agent import FakeGateway
from growth_os.api.onboarding import seed_onboarding
from growth_os.api.product import (
    create_local_product_app,
    create_product_app,
    load_model_environment,
)
from growth_os.evidence import adapter
from growth_os.memory import MemoryService
from growth_os.store import GrowthStore
from growth_os.store.submission_journal import SubmissionJournal
from test_onboarding_api import confirmed_session


@pytest.fixture
def scenario(tmp_path):
    seed_onboarding(tmp_path)
    store = GrowthStore(str(tmp_path / "onboarding.db"))
    evidence = adapter.open_store(tmp_path / "onboarding.db")
    journal = SubmissionJournal(tmp_path / "requests.db")
    materials = SubmissionJournal(tmp_path / "materials.db")
    gateway = FakeGateway(responses={"mentor_chat": {"answer": "当前没有充分能力证据，可以先补材料。", "references": []}})
    app = create_product_app(store, evidence, journal, materials, tmp_path, gateway=gateway)
    try:
        yield TestClient(app), store, evidence, gateway, journal, materials, tmp_path
    finally:
        evidence.db.close()
        store.close()
        journal.close()
        materials.close()


def test_empty_home_real_goal_overview_and_chat_no_domain_mutation(scenario):
    client, store, _, gateway, _, _, _ = scenario
    assert client.get("/api/product").json()["goals"] == []
    assert client.get("/api/product/goals/missing/overview").status_code == 404
    base = confirmed_session(client, "personal_product_goal")
    state = client.post(base + "/capabilities").json()
    goal_id = state["goal"]["id"]
    overview = client.get(f"/api/product/goals/{goal_id}/overview").json()
    assert len(overview["capabilities"]) == 12 and overview["tasks"] == []
    before = {"goal": store.get_goal(goal_id), "capabilities": store.list_capabilities(goal_id), "tasks": store.list_tasks()}
    url = f"/api/mentor/{goal_id}"
    payload = {"request_id": "mentor_request", "text": "我该先做什么？"}
    response = client.post(url, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert client.post(url, json=payload).json() == response.json()
    assert len(gateway.calls) == 1
    assert client.post(url, json={**payload, "text": "其他内容"}).status_code == 409
    assert before == {"goal": store.get_goal(goal_id), "capabilities": store.list_capabilities(goal_id), "tasks": store.list_tasks()}
    assert store.list_assessments(goal_id=goal_id) == []


def test_preferences_followup_and_goal_scope(scenario):
    client, store, _, gateway, _, _, _ = scenario
    base = confirmed_session(client, "mentor_context_goal")
    state = client.post(base + "/capabilities").json()
    goal_id = state["goal"]["id"]
    other = confirmed_session(client, "hidden_other_goal")
    other_id = client.get(other).json()["goal"]["id"]
    assert client.post("/api/product/preferences", json={"text": "偏好代码实践，先看架构"}).status_code == 200
    gateway.responses["mentor_chat"] = {"answer": "建议先从一个小实践开始。", "references": [goal_id]}
    url = f"/api/mentor/{goal_id}"
    assert client.post(url, json={"request_id": "context_first", "text": "我该怎么开始"}).status_code == 200
    assert client.post(url, json={"request_id": "context_second", "text": "接着具体一点"}).status_code == 200
    context = json.loads(gateway.calls[-1]["user"])
    assert context["conversation"][0]["user"] == "我该怎么开始"
    assert context["context"]["memory"][0]["value"]["text"] == "偏好代码实践，先看架构"
    assert len(context["context"]["capabilities"]) == 12
    assert all(node["understanding"] is None and node["practice"] is None for node in context["context"]["capabilities"])
    assert other_id not in gateway.calls[-1]["user"]
    assert client.get(f"/api/mentor/{other_id}").json()["turns"] == []
    assert len(MemoryService(store).active_view(layer="profile")) == 1


def test_failure_manual_retry_and_bad_references(scenario):
    client, store, _, gateway, _, _, _ = scenario
    base = confirmed_session(client, "mentor_failure_goal")
    goal_id = client.get(base).json()["goal"]["id"]
    url = f"/api/mentor/{goal_id}"
    payload = {"request_id": "failure_message", "text": "解释差距"}
    gateway.fail_with["mentor_chat"] = RuntimeError("injected")
    assert client.post(url, json=payload).status_code == 502
    assert client.get(url).json()["turns"][0]["status"] == "failed"
    gateway.fail_with.clear()
    gateway.responses["mentor_chat"] = {"answer": "伪造来源", "references": ["clm_forged"]}
    assert client.post(url, json=payload).status_code == 502
    assert client.get(url).json()["turns"][0]["response"] is None
    gateway.responses["mentor_chat"] = {"answer": "缺少证据，请先补材料。", "references": [goal_id]}
    assert client.post(url, json=payload).status_code == 200
    assert len(client.get(url).json()["turns"]) == 1
    assert len(gateway.calls) == 3
    assert store.get_goal(goal_id)["status"] == "confirmed"


def test_restart_chat_and_automatic_empty_product_initialization(tmp_path, monkeypatch):
    monkeypatch.setenv("GROWTH_PRODUCT_DIRECTORY", str(tmp_path))
    monkeypatch.setenv("GROWTH_PRODUCT_DEMO", "1")
    with TestClient(create_local_product_app()) as client:
        assert client.get("/api/product").json()["goals"] == []
        base = confirmed_session(client, "restart_product")
        goal_id = client.get(base).json()["goal"]["id"]
        url = f"/api/mentor/{goal_id}"
        payload = {"request_id": "restart_mentor", "text": "明天继续什么"}
        expected = client.post(url, json=payload).json()
    with TestClient(create_local_product_app()) as client:
        assert client.get(url).json()["turns"] == [expected]
        assert client.post(url, json=payload).json() == expected
        assert len(client.get("/api/product").json()["goals"]) == 1


def test_environment_does_not_replace_existing_config_or_export_unrelated(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text('GROWTH_AGENT_MODEL="fixture-model"\nEVKG_MODEL=ignored\nUNRELATED=value\nEVKG_EMPTY=\n', encoding="utf-8")
    monkeypatch.setenv("EVKG_MODEL", "already-set")
    monkeypatch.delenv("GROWTH_AGENT_MODEL", raising=False)
    load_model_environment(path)
    import os

    assert os.getenv("EVKG_MODEL") == "already-set"
    assert os.getenv("GROWTH_AGENT_MODEL") == "fixture-model"
    assert os.getenv("UNRELATED") is None
    monkeypatch.delenv("GROWTH_AGENT_MODEL")


def test_blank_forged_origin_and_missing_goal_rejected(scenario):
    client, _, _, gateway, _, _, _ = scenario
    base = confirmed_session(client, "mentor_invalid_goal")
    goal_id = client.get(base).json()["goal"]["id"]
    url = f"/api/mentor/{goal_id}"
    payload = {"request_id": "invalid_request", "text": "问题"}
    assert client.post(url, json={**payload, "text": "  "}).status_code == 422
    assert client.post(url, json={**payload, "level": 5}).status_code == 422
    assert client.post(url, json=payload, headers={"Origin": "https://foreign.example"}).status_code == 403
    assert client.post("/api/mentor/missing", json=payload).status_code == 404
    assert gateway.calls == []


def test_model_failure_never_returns_demo_answer(scenario):
    client, store, evidence, _, journal, materials, directory = scenario
    base = confirmed_session(client, "live_mode_goal")
    goal_id = client.get(base).json()["goal"]["id"]

    class Unavailable:
        def describe(self):
            return "configured", "fixture-unavailable"

        async def structured(self, **kwargs):
            raise RuntimeError("injected live failure")

    client = TestClient(create_product_app(store, evidence, journal, materials, directory, gateway=Unavailable()))
    assert client.get("/api/product").json()["mode"] == "model"
    response = client.post(f"/api/mentor/{goal_id}", json={"request_id": "live_failure", "text": "下一步是什么"})
    assert response.status_code == 502
    assert client.get(f"/api/mentor/{goal_id}").json()["turns"][0]["response"] is None


@pytest.mark.asyncio
async def test_shared_lock_during_mentor_reply(scenario):
    import asyncio

    import httpx

    setup, store, evidence, _, journal, materials, directory = scenario
    base = confirmed_session(setup, "mentor_locked_goal")
    goal_id = setup.get(base).json()["goal"]["id"]
    entered, release = asyncio.Event(), asyncio.Event()

    class WaitingGateway(FakeGateway):
        async def structured(self, **kwargs):
            entered.set()
            await release.wait()
            return await super().structured(**kwargs)

    gateway = WaitingGateway(responses={"mentor_chat": {"answer": "建议先补材料。", "references": []}})
    app = create_product_app(store, evidence, journal, materials, directory, gateway=gateway)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = asyncio.create_task(client.post(f"/api/mentor/{goal_id}", json={"request_id": "locked_message", "text": "下一步"}))
        await asyncio.wait_for(entered.wait(), timeout=5)
        try:
            assert (await client.post("/api/product/preferences", json={"text": "偏好实践"})).status_code == 409
            assert (await client.post(base + "/capabilities")).status_code == 409
            assert (await client.post(f"/api/mentor/{goal_id}", json={"request_id": "second_message", "text": "另一条"})).status_code == 409
        finally:
            release.set()
        assert (await first).status_code == 200
