import pytest
from fastapi.testclient import TestClient
from growth_os.api.product import create_product_app
from test_product_mentor import confirmed_session
from test_product_mentor import scenario as mentor_scenario


@pytest.fixture
def scenario(tmp_path):
    yield from mentor_scenario.__wrapped__(tmp_path)


def prepared(scenario):
    client, store = scenario[:2]
    base = confirmed_session(client, "actions_original_goal")
    state = client.post(base + "/capabilities").json()
    leaf = next(node for node in state["capabilities"] if node["depth"] == 3)
    return client, store, state, leaf


def test_revision_preserves_original_and_lineage(scenario):
    client, store, state, _ = prepared(scenario)
    goal_id = state["goal"]["id"]
    before = store.get_goal(goal_id)
    path = f"/api/product/goals/{goal_id}/revisions"
    payload = {"request_id": "revision_original", "text": "六个月转向AI测试工程师，完成两份测试报告", "confirm": True}
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    child = response.json()["state"]
    assert child["goal"]["id"] != goal_id and child["goal"]["status"] != "confirmed"
    assert child["revision_of"]["goal_id"] == goal_id
    assert child["revision_of"]["quote"] == payload["text"]
    assert child["capabilities"] == []
    assert store.get_goal(goal_id) == before
    assert store.list_capabilities(goal_id) == state["capabilities"]
    runs = store.db.execute("SELECT COUNT(*) FROM g_agent_runs").fetchone()[0]
    assert client.post(path, json=payload).json()["replayed"] is True
    assert store.db.execute("SELECT COUNT(*) FROM g_agent_runs").fetchone()[0] == runs
    assert len(client.get(f"/api/product/goals/{goal_id}/actions").json()["actions"]) == 1
    assert client.post(path, json={**payload, "text": "不同调整"}).status_code == 409
    assert client.post(f"/api/onboarding/goals/{child['goal']['id']}/capabilities").status_code == 409


def test_adjustment_records_history_without_grade_write(scenario):
    client, store, state, leaf = prepared(scenario)
    goal_id = state["goal"]["id"]
    path = f"/api/product/goals/{goal_id}/capabilities/{leaf['id']}/adjust"
    payload = {"request_id": "adjust_target_one", "target_level": 5, "expected_target_level": 3,
               "note": "用户希望对照高级岗位要求", "confirm": True}
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    updated = response.json()["capability"]
    assert updated["target_level"] == 5 and updated["origin"] == "adjusted"
    assert updated["current_level_understanding"] is None and updated["current_level_practice"] is None
    assert store.list_assessments(goal_id=goal_id) == []
    assert client.post(path, json=payload).json() == response.json()
    assert client.post(path, json={**payload, "request_id": "stale_adjustment"}).status_code == 409
    second = {**payload, "request_id": "adjust_target_two", "target_level": 4, "expected_target_level": 5, "note": "阶段目标先达到四级"}
    assert client.post(path, json=second).status_code == 200
    actions = client.get(f"/api/product/goals/{goal_id}/actions").json()["actions"]
    assert [(row["payload"]["before"], row["payload"]["target_level"]) for row in actions] == [(3, 5), (5, 4)]
    assert client.post(path, json=payload).json() == response.json()
    assert store.get_capability(leaf["id"])["target_level"] == 4


@pytest.mark.parametrize("changes", [{"confirm": False}, {"target_level": 6}, {"target_level": True}, {"note": " "}, {"current_level": 5}])
def test_adjustment_invalid_input_is_rejected(scenario, changes):
    client, store, state, leaf = prepared(scenario)
    payload = {"request_id": "invalid_adjustment", "target_level": 5, "expected_target_level": 3, "note": "调整理由", "confirm": True, **changes}
    response = client.post(f"/api/product/goals/{state['goal']['id']}/capabilities/{leaf['id']}/adjust", json=payload)
    assert response.status_code == 422
    assert store.get_capability(leaf["id"]) == leaf


def test_scope_and_confirmation_guards(scenario):
    client, _, state, leaf = prepared(scenario)
    goal_id = state["goal"]["id"]
    payload = {"request_id": "revision_guarded", "text": "调整后的目标", "confirm": True}
    assert client.post(f"/api/product/goals/{goal_id}/revisions", json={**payload, "confirm": False}).status_code == 422
    assert client.post(f"/api/product/goals/{goal_id}/revisions", json={**payload, "text": " "}).status_code == 422
    assert client.post(f"/api/product/goals/{goal_id}/revisions", json=payload, headers={"Origin": "https://foreign.invalid"}).status_code == 403
    draft = client.post("/api/onboarding/goals", json={"request_id": "draft_revision_guard", "text": "尚未澄清"}).json()["goal"]["id"]
    assert client.post(f"/api/product/goals/{draft}/revisions", json=payload).status_code == 409
    adjustment = {"request_id": "cross_goal_adjust", "target_level": 4, "expected_target_level": 3, "note": "越界", "confirm": True}
    other = confirmed_session(client, "another_confirmed_goal")
    other_id = client.get(other).json()["goal"]["id"]
    assert client.post(f"/api/product/goals/{other_id}/capabilities/{leaf['id']}/adjust", json=adjustment).status_code == 404


def test_revision_failure_keeps_draft_and_manual_resume(scenario):
    _, store, state, _ = prepared(scenario)
    _, _, evidence, _, journal, materials, directory = scenario

    class Unavailable:
        def describe(self):
            return "fixture", "unavailable"

        async def structured(self, **kwargs):
            raise RuntimeError("injected question failure")

    client = TestClient(create_product_app(store, evidence, journal, materials, directory, gateway=Unavailable()))
    goal_id = state["goal"]["id"]
    payload = {"request_id": "failed_revision", "text": "调整到新的工程目标", "confirm": True}
    path = f"/api/product/goals/{goal_id}/revisions"
    assert client.post(path, json=payload).status_code == 502
    result = client.post(path, json=payload)
    assert result.status_code == 200 and result.json()["state"]["needs_retry"]
    assert store.get_goal(goal_id) == state["goal"]
    assert len([row for row in store.list_goals() if row["title"] == payload["text"]]) == 1


def test_adjustment_recovers_after_history_completion_failure(scenario, monkeypatch):
    client, store, state, leaf = prepared(scenario)
    from growth_os.store.product_actions import ProductActionStore

    save = ProductActionStore.save
    failed = False

    def interrupt(self, *args, **kwargs):
        nonlocal failed
        result = args[4] if len(args) > 4 else kwargs.get("result")
        if result and not failed:
            failed = True
            raise RuntimeError("injected interrupted action journal")
        return save(self, *args, **kwargs)

    monkeypatch.setattr(ProductActionStore, "save", interrupt)
    payload = {"request_id": "recover_adjustment", "target_level": 5, "expected_target_level": 3, "note": "保存理由", "confirm": True}
    path = f"/api/product/goals/{state['goal']['id']}/capabilities/{leaf['id']}/adjust"
    assert client.post(path, json=payload).status_code == 502
    assert store.get_capability(leaf["id"])["target_level"] == 5
    result = client.post(path, json=payload)
    assert result.status_code == 200
    assert len(client.get(f"/api/product/goals/{state['goal']['id']}/actions").json()["actions"]) == 1
