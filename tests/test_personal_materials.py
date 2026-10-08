import base64

import pytest
from fastapi.testclient import TestClient
from growth_os.api.onboarding import create_local_onboarding_app, seed_onboarding
from growth_os.evidence import adapter
from growth_os.store import GrowthStore
from test_onboarding_api import confirmed_session


@pytest.fixture
def session(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    with TestClient(create_local_onboarding_app()) as client:
        base = confirmed_session(client, "material_goal")
        nodes = client.post(base + "/capabilities").json()["capabilities"]
        leaf = next(node for node in nodes if node["depth"] == 3)
        yield client, base, leaf, tmp_path


def payload(node, **changes):
    return {"request_id": "personal_material", "filename": "笔记.md", "capability_id": node["id"],
            "evidence_type": "uploaded_doc", "attribution": "user_declared",
            "content_base64": base64.b64encode("# 原有材料\n具体内容、例子与局限记录。".encode()).decode(), **changes}


@pytest.mark.parametrize(("filename", "kind", "text"), [
    ("笔记.md", "uploaded_doc", "# 原有笔记\n保留这段逐字引用内容。"),
    ("成果.txt", "repo_artifact", "原有成果的具体内容、核对步骤及局限。"),
    ("example.py", "repo_artifact", "def add(a, b):\n    return a + b\n"),
])
def test_preview_no_binding_confirm_replay_restart(session, filename, kind, text):
    client, base, leaf, directory = session
    data = payload(leaf, filename=filename, evidence_type=kind, content_base64=base64.b64encode(text.encode()).decode())
    path = base + "/materials"
    response = client.post(path, json=data)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["binding_status"] == "preview"
    assert any(text.splitlines()[-1].strip() in quote["text"] for quote in preview["quotes"])
    assert client.post(path, json=data).json() == preview
    assert client.get(f"/api/evidence/{leaf['id']}").json()["supports"] == []
    with GrowthStore(str(directory / "onboarding.db")) as store:
        assert store.list_capability_claims(capability_id=leaf["id"]) == []
        assert store.list_assessments(capability_id=leaf["id"]) == []
    confirmation = path + "/personal_material/confirm"
    assert client.post(confirmation, json={"confirm": False}).status_code == 422
    assert client.post(confirmation, json={"confirm": True, "level": 5}).status_code == 422
    response = client.post(confirmation, json={"confirm": True})
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["binding_status"] == "confirmed" and confirmed["decision"]["accepted"]
    assert client.post(confirmation, json={"confirm": True}).json() == confirmed
    assert len(client.get(f"/api/evidence/{leaf['id']}").json()["supports"]) == 1
    # 重启入口单独在以下测试核对，避免夹具服务持锁时打开第二服务。
    assert client.get(path).json()["materials"] == [confirmed]


def test_preview_and_confirmation_survive_restart(tmp_path, monkeypatch):
    seed_onboarding(tmp_path)
    monkeypatch.setenv("GROWTH_ONBOARDING_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_ONBOARDING_REAL_MODEL", raising=False)
    with TestClient(create_local_onboarding_app()) as client:
        base = confirmed_session(client, "material_restart")
        leaf = next(node for node in client.post(base + "/capabilities").json()["capabilities"] if node["depth"] == 3)
        path = base + "/materials"
        preview = client.post(path, json=payload(leaf)).json()
    with TestClient(create_local_onboarding_app()) as client:
        assert client.get(path).json()["materials"] == [preview]
        confirmed = client.post(path + "/personal_material/confirm", json={"confirm": True}).json()
    with TestClient(create_local_onboarding_app()) as client:
        assert client.get(path).json()["materials"] == [confirmed]
        assert client.post(path, json=payload(leaf)).json() == confirmed
        assert client.post(path + "/personal_material/confirm", json={"confirm": True}).json() == confirmed


def test_unknown_attribution_rejected_without_binding_or_rating(session):
    client, base, leaf, directory = session
    path = base + "/materials"
    assert client.post(path, json=payload(leaf, attribution="unknown")).status_code == 200
    response = client.post(path + "/personal_material/confirm", json={"confirm": True})
    assert response.status_code == 422, response.text
    assert client.get(path).json()["materials"][0]["decision"]["accepted"] is False
    with GrowthStore(str(directory / "onboarding.db")) as store:
        assert store.list_capability_claims(capability_id=leaf["id"]) == []
        assert store.list_assessments(capability_id=leaf["id"]) == []


@pytest.mark.parametrize("change", [
    {"filename": "../材料.md"}, {"filename": "资料.pdf"}, {"content_base64": "not-base64"},
    {"content_base64": base64.b64encode(b"\xff").decode()}, {"content_base64": base64.b64encode(b"   ").decode()},
    {"filename": "main.py"}, {"source_id": "forged"},
])
def test_invalid_upload_not_written(session, change):
    client, base, leaf, directory = session
    assert client.post(base + "/materials", json=payload(leaf, **change)).status_code == 422
    assert client.get(base + "/materials").json()["materials"] == []
    evidence = adapter.open_store(directory / "onboarding.db")
    try:
        assert adapter.claims_overview(evidence) == []
    finally:
        evidence.db.close()


def test_cross_goal_scope_request_conflict_and_limits(session):
    client, base, leaf, _ = session
    other = confirmed_session(client, "material_other")
    assert client.post(other + "/materials", json=payload(leaf)).status_code == 404
    assert client.post(base + "/materials", json=payload(leaf)).status_code == 200
    assert client.post(base + "/materials", json=payload(leaf, filename="另一份.md")).status_code == 409
    assert client.post(other + "/materials/personal_material/confirm", json={"confirm": True}).status_code == 404
    assert client.post(base + "/materials", json=payload(leaf), headers={"Origin": "https://foreign.example"}).status_code == 403
    assert client.post(base + "/materials", content=b"x" * (3 * 1024 * 1024 + 1)).status_code == 413


def test_failed_reassessment_preserves_binding_and_retry_no_duplicate(session, monkeypatch):
    from growth_os.api import materials

    client, base, leaf, directory = session
    path = base + "/materials"
    assert client.post(path, json=payload(leaf)).status_code == 200
    original = materials.assess_capability

    def fail(*args, **kwargs):
        raise RuntimeError("injected")

    monkeypatch.setattr(materials, "assess_capability", fail)
    confirmation = path + "/personal_material/confirm"
    assert client.post(confirmation, json={"confirm": True}).status_code == 502
    assert client.get(path).json()["materials"][0]["binding_status"] == "bound_pending_assessment"
    with GrowthStore(str(directory / "onboarding.db")) as store:
        assert len(store.list_capability_claims(capability_id=leaf["id"])) == 1
        assert store.list_assessments(capability_id=leaf["id"]) == []
    monkeypatch.setattr(materials, "assess_capability", original)
    assert client.post(confirmation, json={"confirm": True}).json()["binding_status"] == "confirmed"
    with GrowthStore(str(directory / "onboarding.db")) as store:
        assert len(store.list_capability_claims(capability_id=leaf["id"])) == 1
