import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from growth_os.api.app import create_app
from growth_os.api.interactive import (
    SubmissionJournal,
    create_interactive_app,
    create_local_interactive_app,
    seed_interaction,
)
from growth_os.evidence import adapter
from growth_os.store import GrowthStore


@pytest.fixture
def scenario(tmp_path):
    manifest = asyncio.run(seed_interaction(tmp_path))
    store = GrowthStore(str(tmp_path / "demo.db"))
    evidence = adapter.open_store(tmp_path / "demo.db")
    try:
        yield TestClient(create_interactive_app(store, evidence)), store, evidence, manifest
    finally:
        evidence.db.close()
        store.close()


def test_actions_keep_assessments_and_submissions_unchanged(scenario):
    client, store, _, manifest = scenario
    task_id = manifest["interaction_task_id"]
    before = list(store.db.execute("SELECT * FROM g_assessments"))
    submissions = store.list_task_submissions()
    for action, status in [("activate", "active"), ("block", "blocked"),
                           ("resume", "active"), ("abandon", "abandoned")]:
        response = client.post(f"/api/tasks/{task_id}/actions",
                               json={"action": action, "reason": "时间安排变化"})
        assert response.status_code == 200
        assert response.json()["task"]["status"] == status
    assert list(store.db.execute("SELECT * FROM g_assessments")) == before
    assert store.list_task_submissions() == submissions
    assert client.post(f"/api/tasks/{task_id}/actions", json={"action": "activate"}).status_code == 409


def test_action_conflicts_and_invalid_payloads(scenario):
    client, store, _, manifest = scenario
    task_id = manifest["interaction_task_id"]
    url = f"/api/tasks/{task_id}/actions"
    assert client.post(url, json={"action": "resume"}).status_code == 409
    assert client.post(url, json={"action": "done", "source_id": "forged"}).status_code == 422
    assert client.post(url, json={"action": "abandon", "reason": "  "}).status_code == 422
    assert client.post(url, json={"action": "activate"}).status_code == 200
    assert client.post(url, json={"action": "activate"}).status_code == 409
    assert client.post(url, json={"action": "block"}).status_code == 422
    assert store.get_task(task_id)["status"] == "active"
    assert client.post("/api/tasks/missing/actions", json={"action": "activate"}).status_code == 404
    done = manifest["task_id"]
    assert client.post(f"/api/tasks/{done}/actions", json={"action": "abandon", "reason": "x"}).status_code == 409


def test_external_origin_rejected_and_original_api_readonly(scenario):
    client, store, evidence, manifest = scenario
    url = f"/api/tasks/{manifest['interaction_task_id']}/actions"
    assert client.post(url, json={"action": "activate"},
                       headers={"Origin": "https://external.example"}).status_code == 403
    assert store.get_task(manifest["interaction_task_id"])["status"] == "proposed"
    readonly = TestClient(create_app(store, evidence))
    assert readonly.get("/api/interaction").status_code == 404
    assert readonly.post(url, json={"action": "activate"}).status_code == 404
    assert client.get("/api/interaction").json()["submission_enabled"] is False


def test_seed_refuses_overwrite(tmp_path):
    asyncio.run(seed_interaction(tmp_path))
    before = (tmp_path / "demo.db").read_bytes()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["interaction_enabled"] is True
    with pytest.raises(ValueError, match="已存在"):
        asyncio.run(seed_interaction(tmp_path))
    assert (tmp_path / "demo.db").read_bytes() == before


def test_submission_replays_after_restart_and_exposes_both_dimensions(tmp_path, monkeypatch):
    manifest = asyncio.run(seed_interaction(tmp_path))
    monkeypatch.setenv("GROWTH_INTERACTION_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_INTERACTION_REAL_MODEL", raising=False)
    task = manifest["interaction_task_id"]
    url = f"/api/tasks/{task}/submissions"
    payload = {"request_id": "request_test_001", "probe_answer": "RAG 先检索再生成，重排提升相关性；无匹配应报告不足。"}
    with TestClient(create_local_interactive_app()) as client:
        assert client.get("/api/interaction").json()["submission_enabled"] is True
        assert client.post(url, json=payload).status_code == 409
        client.post(f"/api/tasks/{task}/actions", json={"action": "activate"})
        response = client.post(url, json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["task"]["status"] == "done"
        assert result["attribution"]["before"]["understanding"]["level"] == 2
        assert result["attribution"]["after"]["understanding"]["level"] == 3
        assert result["attribution"]["after"]["practice"]["level"] == 4
        assert client.post(url, json=payload).json() == result
        assert client.post(url, json={**payload, "probe_answer": "另一份回答"}).status_code == 409
    with TestClient(create_local_interactive_app()) as client:
        assert client.post(url, json=payload).json() == result
        body = client.get("/api/growth-loop/goal_demo").json()
        row = next(t for t in body["tasks"] if t["id"] == task)
        assert row["attribution"] == result["attribution"]
        assert len(row["submissions"]) == 1


def test_interrupted_request_cannot_be_bypassed_with_new_id(tmp_path, monkeypatch):
    manifest = asyncio.run(seed_interaction(tmp_path))
    task = manifest["interaction_task_id"]
    store = GrowthStore(str(tmp_path / "demo.db"))
    store.activate_task(task)
    store.close()
    journal = SubmissionJournal(tmp_path / "requests.db")
    journal.save("interrupted_req", task, "digest", "running")
    journal.close()
    monkeypatch.setenv("GROWTH_INTERACTION_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_INTERACTION_REAL_MODEL", raising=False)
    with TestClient(create_local_interactive_app()) as client:
        assert client.post(f"/api/tasks/{task}/submissions", json={
            "request_id": "new_request_id", "probe_answer": "理解回答"}).status_code == 409


def test_failure_is_recorded_without_false_completion(scenario, tmp_path):
    from growth_os.agent import FakeGateway
    from growth_os.assessment import BINDING_TASK, TaskLoop

    _, store, evidence, manifest = scenario
    task = manifest["interaction_task_id"]
    store.activate_task(task)
    gateway = FakeGateway(fail_with={BINDING_TASK: RuntimeError("injected")})
    loop = TaskLoop(store=store, evidence_store=evidence, gateway=gateway,
                    submission_dir=tmp_path / "submissions")
    journal = SubmissionJournal(tmp_path / "requests.db")
    try:
        client = TestClient(create_interactive_app(store, evidence, task_loop=loop, journal=journal))
        url = f"/api/tasks/{task}/submissions"
        payload = {"request_id": "failure_request", "probe_answer": "检索与重排的设计说明"}
        assert client.post(url, json=payload).status_code == 422
        assert store.get_task(task)["status"] == "active"
        assert store.list_task_submissions(task_id=task) == []
        assert journal.get(payload["request_id"])[2] == "failed"
        assert len(gateway.calls) == 1
        assert client.post(url, json={**payload, "source_id": "forged"}).status_code == 422
        assert len(gateway.calls) == 1
    finally:
        journal.close()


def test_journal_rejects_second_writer(tmp_path):
    journal = SubmissionJournal(tmp_path / "requests.db")
    try:
        with pytest.raises(RuntimeError, match="单进程"):
            SubmissionJournal(tmp_path / "requests.db")
    finally:
        journal.close()


@pytest.mark.asyncio
async def test_concurrent_submit_and_state_change_are_rejected(scenario, tmp_path):
    import httpx
    from growth_os.agent import FakeGateway
    from growth_os.assessment import BINDING_TASK, TaskLoop

    _, store, evidence, manifest = scenario
    task = manifest["interaction_task_id"]
    store.activate_task(task)
    entered, release = asyncio.Event(), asyncio.Event()

    class WaitingGateway(FakeGateway):
        async def structured(self, **kwargs):
            entered.set()
            await release.wait()
            return await super().structured(**kwargs)

    gateway = WaitingGateway(fail_with={BINDING_TASK: RuntimeError("injected")})
    loop = TaskLoop(store=store, evidence_store=evidence, gateway=gateway,
                    submission_dir=tmp_path / "submissions")
    journal = SubmissionJournal(tmp_path / "requests.db")
    app = create_interactive_app(store, evidence, task_loop=loop, journal=journal)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            url = f"/api/tasks/{task}/submissions"
            payload = {"request_id": "concurrent_request", "probe_answer": "理解回答"}
            first = asyncio.create_task(client.post(url, json=payload))
            await asyncio.wait_for(entered.wait(), timeout=5)
            assert (await client.post(url, json=payload)).status_code == 409
            assert (await client.post(f"/api/tasks/{task}/actions", json={"action": "block", "reason": "x"})).status_code == 409
            release.set()
            assert (await first).status_code == 422
            assert len(gateway.calls) == 1
    finally:
        release.set()
        journal.close()
