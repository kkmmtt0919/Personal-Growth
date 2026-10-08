import asyncio
import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from growth_os.api.interactive import MAX_FILE_BYTES, create_local_interactive_app, seed_interaction
from growth_os.evidence import adapter
from growth_os.store import GrowthStore


def payload(content=b"# RAG evaluation\n\nTen samples with citations and failure cases.", filename="report.md"):
    return {"request_id": "file_request_001", "filename": filename,
            "content_base64": base64.b64encode(content).decode()}


def seed(tmp_path, monkeypatch, kind="markdown"):
    manifest = asyncio.run(seed_interaction(tmp_path, pending_practice=True))
    task = manifest["task_id"]
    store = GrowthStore(str(tmp_path / "demo.db"))
    try:
        if kind != "markdown":
            original = store.get_task(task)
            store.abandon_task(task, "测试另一种交付物")
            task = store.create_task({"gap_id": original["gap_id"], "title": "实现可核对的 RAG 评测实验",
                                     "objective": "产出评测实验与失败案例", "deliverable_type": kind,
                                     "est_minutes": 60, "acceptance_type": "artifact_check",
                                     "acceptance": "提交评测实验与失败案例"})
        store.activate_task(task)
    finally:
        store.close()
    monkeypatch.setenv("GROWTH_INTERACTION_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("GROWTH_INTERACTION_REAL_MODEL", raising=False)
    return manifest, task


@pytest.mark.parametrize("kind,filename", [("markdown", "report.md"), ("code", "eval.py"),
                                         ("code", "Dockerfile"), ("archive", "evaluation.zip")])
def test_file_chain_replays_after_restart_and_audits(tmp_path, monkeypatch, kind, filename):
    manifest, task = seed(tmp_path, monkeypatch, kind)
    content = b"# RAG evaluation\n\nTen samples and failure criteria."
    if kind == "archive":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("report.md", content)
        content = buffer.getvalue()
    request = payload(content, filename)
    url = f"/api/tasks/{task}/files"
    with TestClient(create_local_interactive_app()) as client:
        response = client.post(url, json=request)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["task"]["status"] == "done"
        assert result["attribution"]["before"]["practice"]["level"] == 3
        assert result["attribution"]["after"]["practice"]["level"] == 4
        assert result["attribution"]["after"]["understanding"]["level"] == 2
        assert all(result["attribution"]["guard"].values())
        assert client.post(url, json=request).json() == result
        assert client.post(url, json={**request, "content_base64": "YWJj"}).status_code == 409
    with TestClient(create_local_interactive_app()) as client:
        assert client.post(url, json=request).json() == result
        rows = client.get("/api/growth-loop/goal_demo").json()["tasks"]
        row = next(t for t in rows if t["id"] == task)
        assert len(row["submissions"]) == 1
        assert row["attribution"] == result["attribution"]
        evidence = client.get(f"/api/evidence/{manifest['capability_id']}").json()
        assert any(s["source"]["type"] == "task_submission" for s in evidence["supports"])
    assert adapter.audit(str(tmp_path / "demo.db"))["status"] == "pass"


@pytest.mark.parametrize("upload_payload,status", [
    (payload(filename="../../outside.md"), 422),
    (payload(filename="C:\\outside.md"), 422),
    (payload(filename="image.png"), 422),
    (payload(b"", "empty.md"), 422),
    (payload(b"\xff\xfe", "binary.md"), 422),
    (payload(b"nul\x00byte", "binary.md"), 422),
    ({**payload(), "content_base64": "not base64!!"}, 422),
    ({**payload(), "artifact_path": "C:/private.md"}, 422),
    ({**payload(), "source_id": "forged"}, 422),
    (payload(b"x" * (MAX_FILE_BYTES + 1)), 413),
])
def test_invalid_file_is_rejected_before_evidence_write(tmp_path, monkeypatch, upload_payload, status):
    _, task = seed(tmp_path, monkeypatch)
    with TestClient(create_local_interactive_app()) as client:
        before = (tmp_path / "demo.db").read_bytes()
        assert client.post(f"/api/tasks/{task}/files", json=upload_payload).status_code == status
        assert (tmp_path / "demo.db").read_bytes() == before
        assert not (tmp_path / "submissions" / "uploads").exists()


def test_body_limit_without_content_length(tmp_path, monkeypatch):
    _, task = seed(tmp_path, monkeypatch)
    with TestClient(create_local_interactive_app()) as client:
        assert client.post(f"/api/tasks/{task}/files", content=iter([b"x" * (3 * 1024 * 1024 + 1)])).status_code == 413


def test_bad_zip_fails_without_completing_task(tmp_path, monkeypatch):
    _, task = seed(tmp_path, monkeypatch, "archive")
    with TestClient(create_local_interactive_app()) as client:
        assert client.post(f"/api/tasks/{task}/files", json=payload(b"not a zip", "bad.zip")).status_code == 422
        rows = client.get("/api/growth-loop/goal_demo").json()["tasks"]
        row = next(t for t in rows if t["id"] == task)
        assert row["status"] == "active"
        assert row["submissions"] == []


def test_failed_binding_can_retry_without_duplicate_evidence(tmp_path, monkeypatch):
    import re

    from growth_os.agent import FakeGateway
    from growth_os.api.interactive import create_interactive_app
    from growth_os.assessment import BINDING_TASK, TaskLoop
    from growth_os.store.submission_journal import SubmissionJournal

    manifest, task = seed(tmp_path, monkeypatch)
    store = GrowthStore(str(tmp_path / "demo.db"))
    evidence = adapter.open_store(tmp_path / "demo.db")
    journal = SubmissionJournal(tmp_path / "requests.db")
    gateway = FakeGateway(fail_with={BINDING_TASK: RuntimeError("injected")})
    loop = TaskLoop(store=store, evidence_store=evidence, gateway=gateway,
                    submission_dir=tmp_path / "submissions")
    try:
        client = TestClient(create_interactive_app(store, evidence, task_loop=loop, journal=journal))
        url = f"/api/tasks/{task}/files"
        assert client.post(url, json=payload()).status_code == 422
        sources = {s.id for s in evidence.find_sources()}
        assert store.get_task(task)["status"] == "active"
        assert store.list_task_submissions(task_id=task) == []
        gateway.fail_with.clear()
        gateway.responses[BINDING_TASK] = lambda index, system, user: {"proposals": [{
            "claim_id": re.search(r"clm_[0-9a-f]{6,}", user).group(0),
            "capability_path": store.get_capability(manifest["capability_id"])["path"],
            "rationale": "受控重试验证",
        }]}
        assert client.post(url, json=payload()).status_code == 200
        assert {s.id for s in evidence.find_sources()} == sources
        assert len(store.list_task_submissions(task_id=task)) == 1
        assert len(gateway.calls) == 2
        assert client.post(url, json=payload()).status_code == 200
        assert len(gateway.calls) == 2
        assert adapter.audit(str(tmp_path / "demo.db"))["status"] == "pass"
    finally:
        evidence.db.close()
        store.close()
        journal.close()
