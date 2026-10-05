"""本地演示的完整链路、数据隔离和跨端口只读访问。"""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from growth_os.api.local import create_local_app
from growth_os.demo import seed_demo


def test_demo_serves_verified_loop_and_preserves_existing_data(tmp_path, monkeypatch):
    manifest = asyncio.run(seed_demo(tmp_path))
    database = tmp_path / "demo.db"
    before = database.read_bytes()
    with pytest.raises(ValueError, match="已存在"):
        asyncio.run(seed_demo(tmp_path))
    assert database.read_bytes() == before
    monkeypatch.setenv("GROWTH_DEMO_DIRECTORY", str(tmp_path))
    with TestClient(create_local_app()) as client:
        capabilities = client.get("/api/goals/goal_demo/capabilities").json()["capabilities"]
        assert capabilities[0]["practice"] == 4
        evidence = client.get(f"/api/evidence/{manifest['capability_id']}").json()
        assert all(item["quote"]["text"] and item["source"]["name"]
                   for item in evidence["supports"])
        task = client.get("/api/growth-loop/goal_demo").json()["tasks"][0]
        assert task["status"] == "done"
        assert task["gap"]["status"] == "closed"
        assert task["attribution"]["before"]["practice"]["level"] == 3
        assert task["attribution"]["after"]["practice"]["level"] == 4
        assert all(task["attribution"]["guard"].values())
        response = client.get("/api/goals/goal_demo", headers={"Origin": "http://localhost:4173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:4173"
        assert client.post("/api/goals/goal_demo", json={}).status_code == 405
        assert not client.get("/api/goals/goal_demo", headers={"Origin": "https://example.com"}).headers.get("access-control-allow-origin")
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["constructed"]


def test_server_requires_seed_without_creating_database(tmp_path, monkeypatch):
    monkeypatch.setenv("GROWTH_DEMO_DIRECTORY", str(tmp_path))
    with pytest.raises(RuntimeError, match="Demo 未就绪"):
        create_local_app()
    assert not (tmp_path / "demo.db").exists()


def test_return_demo_reopens_storage_and_resolves_persistent_sources(tmp_path, monkeypatch):
    from growth_os.store import GrowthStore

    manifest = asyncio.run(seed_demo(tmp_path, include_return=True))
    monkeypatch.setenv("GROWTH_DEMO_DIRECTORY", str(tmp_path))
    # 种子存储已在 finally 关闭，此处服务重新打开同一库。
    store = GrowthStore(str(tmp_path / "demo.db"))
    try:
        before = list(store.db.iterdump())
        with TestClient(create_local_app()) as client:
            url = "/api/return-demo/goal_demo"
            response = client.get(url)
            assert response.status_code == 200
            body = response.json()
            assert body["constructed"] and body["simulated_return"]
            report = body["report"]
            assert report["baseline_snapshot_id"] == manifest["return_context"]["baseline_snapshot_id"]
            assert store.get_snapshot(report["current_snapshot_id"])
            change = report["summary"]["changes"][0]
            assert (change["before_level"], change["after_level"]) == (3, 4)
            assert store.get_assessment(change["after_assessment_id"])["level"] == 4
            assert store.get_gap(report["next_steps"][0]["gap_id"])["status"] == "open"
            assert store.get_memory(report["preferences"][0]["memory_id"])["source_id"] == report["preferences"][0]["source_id"]
            assert client.post(url, json={}).status_code == 405
            assert client.get("/api/return-demo/other").status_code == 404
        assert list(store.db.iterdump()) == before
    finally:
        store.close()


def test_legacy_demo_has_no_fabricated_return_summary(tmp_path, monkeypatch):
    asyncio.run(seed_demo(tmp_path))
    monkeypatch.setenv("GROWTH_DEMO_DIRECTORY", str(tmp_path))
    with TestClient(create_local_app()) as client:
        assert client.get("/api/return-demo/goal_demo").status_code == 404


def test_stale_return_context_is_rejected_after_reopen(tmp_path, monkeypatch):
    asyncio.run(seed_demo(tmp_path, include_return=True))
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["return_context"]["current_snapshot_id"] = manifest["return_context"]["baseline_snapshot_id"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("GROWTH_DEMO_DIRECTORY", str(tmp_path))
    with TestClient(create_local_app()) as client:
        assert client.get("/api/return-demo/goal_demo").status_code == 422
