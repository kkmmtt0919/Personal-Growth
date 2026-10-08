import base64

import pytest
from fastapi.testclient import TestClient
from growth_os.agent import FakeGateway
from growth_os.api.onboarding import (
    create_local_onboarding_app,
    create_onboarding_app,
    seed_onboarding,
)
from growth_os.assessment import trace_task
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from growth_os.store.submission_journal import SubmissionJournal
from test_onboarding_api import confirmed_session


@pytest.mark.parametrize("dimension", ["understanding", "practice"])
def test_new_goal_task_evidence_reassessment_replay_reopen(tmp_path, monkeypatch, dimension):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    with TestClient(create_local_onboarding_app()) as client:
        base = confirmed_session(client, "journey_request")
        state = client.post(base + "/capabilities").json()
        node = next(node for node in state["capabilities"] if node["depth"] == 3)
        plan = base + f"/capabilities/{node['id']}/tasks"
        result = client.post(plan, json={"dimension": dimension})
        assert result.status_code == 200, result.text
        task = result.json()["task"]
        assert all(item["level"] is None and item["status"] == "insufficient_evidence"
                   for item in result.json()["assessment"]["dimensions"].values())
        replay = client.post(plan, json={"dimension": dimension}).json()
        assert replay["replayed"] and replay["task"]["id"] == task["id"]
        action = f"/api/tasks/{task['id']}/actions"
        assert client.post(action, json={"action": "activate"}).status_code == 200
        assert client.post(action, json={"action": "block", "reason": "补充材料"}).status_code == 200
        assert client.post(action, json={"action": "resume"}).status_code == 200
        text = "# 核对记录\n说明具体内容与例子，记录核对步骤及尚未验证的局限。"
        payload = {"request_id": "journey_submission"}
        if dimension == "understanding":
            endpoint = f"/api/tasks/{task['id']}/submissions"
            payload["probe_answer"] = text
        else:
            endpoint = f"/api/tasks/{task['id']}/files"
            payload.update(filename="成果.md", content_base64=base64.b64encode(text.encode()).decode())
        response = client.post(endpoint, json=payload)
        assert response.status_code == 200, response.text
        outcome = response.json()
        assert outcome["task"]["status"] == "done"
        assert all(outcome["attribution"]["guard"].values())
        assert client.post(endpoint, json=payload).json() == outcome
        evidence = client.get(f"/api/evidence/{node['id']}").json()
        assert len(evidence["supports"]) == 1
        assert "核对步骤" in evidence["supports"][0]["quote"]["text"]
        goal_id = state["goal"]["id"]
        assert client.get(f"/api/growth-loop/{goal_id}").json()["tasks"][0]["attribution"] == outcome["attribution"]
    with TestClient(create_local_onboarding_app()) as client:
        assert client.post(endpoint, json=payload).json() == outcome
        assert client.get(f"/api/growth-loop/{goal_id}").json()["tasks"][0]["attribution"] == outcome["attribution"]
    with GrowthStore(str(tmp_path / "onboarding.db")) as store:
        evidence = adapter.open_store(tmp_path / "onboarding.db")
        try:
            trace = trace_task(store, evidence, task_id=task["id"])
            assert trace["complete"]
            assert store.get_task(trace["task_id"])["goal_id"] == goal_id
            assert len(store.list_task_submissions(task_id=task["id"])) == 1
            assert store.db.execute("SELECT COUNT(*) FROM g_agent_runs WHERE agent='task_generation'").fetchone()[0] == 1
        finally:
            evidence.db.close()


def test_foreign_parent_and_invalid_dimension_rejected(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    with TestClient(create_local_onboarding_app()) as client:
        base = confirmed_session(client, "journey_first")
        nodes = client.post(base + "/capabilities").json()["capabilities"]
        root = next(node for node in nodes if node["depth"] == 1)
        leaf = next(node for node in nodes if node["depth"] == 3)
        other = confirmed_session(client, "journey_second")
        assert client.post(other + f"/capabilities/{leaf['id']}/tasks", json={"dimension": "practice"}).status_code == 404
        assert client.post(base + f"/capabilities/{root['id']}/tasks", json={"dimension": "practice"}).status_code == 409
        path = base + f"/capabilities/{leaf['id']}/tasks"
        assert client.post(path, json={"dimension": "bad"}).status_code == 422
        assert client.post(path, json={"dimension": "practice"}, headers={"Origin": "https://foreign.example"}).status_code == 403


def test_failed_task_proposal_preserves_baseline_and_manual_retry(tmp_path):
    with GrowthStore(str(tmp_path / "failure.db")) as store:
        store.upsert_user("local", "用户")
        client = TestClient(create_onboarding_app(store))
        base = confirmed_session(client, "journey_failure")
        node = next(node for node in client.post(base + "/capabilities").json()["capabilities"] if node["depth"] == 3)
        evidence = adapter.open_store(tmp_path / "failure.db")
        journal = SubmissionJournal(tmp_path / "requests.db")
        gateway = FakeGateway(fail_with={"task_generation": RuntimeError("injected")})
        try:
            client = TestClient(create_onboarding_app(store, gateway=gateway, evidence_store=evidence,
                                                    journal=journal, directory=tmp_path))
            path = base + f"/capabilities/{node['id']}/tasks"
            assert client.post(path, json={"dimension": "understanding"}).status_code == 502
            assert store.list_tasks() == []
            assert len(store.list_gaps(capability_id=node["id"], status="open")) == 2
            gateway.fail_with.clear()
            gateway.responses["task_generation"] = {"title": "说明概念", "objective": "提交具体例子",
                "deliverable_type": "probe_answer", "est_minutes": 30, "acceptance_type": "probe_rubric",
                "acceptance": "提交概念解释、具体例子与局限说明"}
            assert client.post(path, json={"dimension": "understanding"}).status_code == 200
            assert len(gateway.calls) == 2
        finally:
            evidence.db.close()
            journal.close()


@pytest.mark.asyncio
async def test_shared_lock_rejects_goal_changes_during_submission(tmp_path):
    import asyncio

    import httpx
    from growth_os.assessment import BINDING_TASK

    with GrowthStore(str(tmp_path / "concurrency.db")) as store:
        store.upsert_user("local", "用户")
        setup = TestClient(create_onboarding_app(store))
        base = confirmed_session(setup, "journey_concurrent")
        node = next(node for node in setup.post(base + "/capabilities").json()["capabilities"] if node["depth"] == 3)
        evidence = adapter.open_store(tmp_path / "concurrency.db")
        journal = SubmissionJournal(tmp_path / "requests.db")
        entered, release = asyncio.Event(), asyncio.Event()

        class WaitingGateway(FakeGateway):
            async def structured(self, **kwargs):
                if kwargs["task"] == BINDING_TASK:
                    entered.set()
                    await release.wait()
                return await super().structured(**kwargs)

        gateway = WaitingGateway(responses={"task_generation": {"title": "解释概念", "objective": "提供具体例子",
            "deliverable_type": "probe_answer", "est_minutes": 30, "acceptance_type": "probe_rubric",
            "acceptance": "提供概念说明、具体例子与局限记录"}}, fail_with={BINDING_TASK: RuntimeError("injected")})
        app = create_onboarding_app(store, gateway=gateway, evidence_store=evidence, journal=journal, directory=tmp_path)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                plan = base + f"/capabilities/{node['id']}/tasks"
                task = (await client.post(plan, json={"dimension": "understanding"})).json()["task"]
                store.activate_task(task["id"])
                url = f"/api/tasks/{task['id']}/submissions"
                first = asyncio.create_task(client.post(url, json={"request_id": "concurrent_submit", "probe_answer": "具体内容"}))
                await asyncio.wait_for(entered.wait(), timeout=5)
                try:
                    assert (await client.post(plan, json={"dimension": "practice"})).status_code == 409
                    assert (await client.post("/api/onboarding/goals", json={"request_id": "concurrent_new", "text": "新目标"})).status_code == 409
                    assert (await client.post(f"/api/tasks/{task['id']}/actions", json={"action": "block", "reason": "等待"})).status_code == 409
                finally:
                    release.set()
                assert (await first).status_code == 422
                assert store.get_task(task["id"])["status"] == "active"
        finally:
            evidence.db.close()
            journal.close()
