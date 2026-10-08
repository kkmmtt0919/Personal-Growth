"""独立本地交互实验；任务状态操作复用既有状态机。"""

from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..agent import FakeGateway
from ..assessment import BINDING_TASK, TaskLoop
from ..demo import seed_demo
from ..evidence import adapter
from ..evidence.archive import CODE_FILENAMES, CODE_SUFFIXES
from ..store import GrowthStore
from ..store.submission_journal import SubmissionJournal
from .app import create_app

INTERACTION_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "interactive"
ORIGINS = [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
           for port in (4173, 5173)]
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BODY = 3 * 1024 * 1024


class TaskAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["activate", "block", "resume", "abandon"]
    reason: str | None = Field(default=None, max_length=2000)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    probe_answer: str = Field(min_length=1, max_length=50000)


class FileSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=MAX_UPLOAD_BODY)



def create_interactive_app(store, evidence_store, *, loop_reports=None, task_loop=None, journal=None, operation_lock=None):
    reports = dict(loop_reports or {})
    if journal:
        reports.update(journal.reports())
    app = create_app(store, evidence_store, loop_reports=reports)
    app.title = "Growth OS Local Interaction"
    lock = operation_lock if operation_lock is not None else asyncio.Lock()

    @app.middleware("http")
    async def local_writes(request: Request, call_next):
        # 浏览器跨站请求不能操作本地库；无 Origin 的本地 API 客户端仍可使用。
        if request.method == "POST" and request.headers.get("origin") not in (None, *ORIGINS):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={"detail": "仅允许本地页面操作"})
        return await call_next(request)

    @app.get("/api/interaction")
    async def interaction():
        return {"enabled": True, "actions": ["activate", "block", "resume", "abandon"],
                "submission_enabled": task_loop is not None, "constructed": True}

    async def complete_submission(task_id, request_id, digest, *, answer=None, file_content=None, filename=None):
        if task_loop is None or journal is None:
            raise HTTPException(503, "提交服务未配置")
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            previous = journal.get(request_id)
            if previous:
                if previous[:2] != (task_id, digest):
                    raise HTTPException(409, "同一请求标识不能用于不同提交")
                if previous[2] == "completed":
                    return json.loads(previous[3])
                if previous[2] in ("interrupted", "running"):
                    raise HTTPException(409, "上次提交被中断，请核对任务与证据后再提交")
            task = store.get_task(task_id)
            if task is None:
                raise HTTPException(404, "任务不存在")
            if task["status"] != "active":
                raise HTTPException(409, "只有进行中的任务可提交，请刷新任务状态")
            if answer is not None and task["deliverable_type"] != "probe_answer":
                raise HTTPException(422, "该任务需要提交实践文件")
            artifact = None
            if file_content is not None:
                suffix = Path(filename).suffix.lower()
                kind = task["deliverable_type"]
                allowed = (kind == "markdown" and suffix in (".md", ".markdown", ".txt")
                           or kind == "code" and (suffix in CODE_SUFFIXES or filename.lower() in CODE_FILENAMES)
                           or kind == "archive" and suffix == ".zip")
                if not allowed:
                    raise HTTPException(422, "文件类型与任务交付物不匹配")
                if kind != "archive":
                    try:
                        text = file_content.decode("utf-8-sig")
                    except UnicodeDecodeError as error:
                        raise HTTPException(422, "文档与代码文件须使用 UTF-8 编码") from error
                    if not text.strip() or "\x00" in text:
                        raise HTTPException(422, "请提交非空文本文件")
                # 路径只由服务器产生；保留特殊代码文件名以沿用已有路由。
                folder = task_loop.submission_dir / "uploads" / hashlib.sha256(task_id.encode()).hexdigest() / digest
                artifact = folder / (filename.lower() if filename.lower() in CODE_FILENAMES else "artifact" + suffix)
            if journal.has_interrupted(task_id):
                raise HTTPException(409, "该任务有中断提交，需核对证据后恢复")
            journal.save(request_id, task_id, digest, "running")
            try:
                if artifact:
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    artifact.write_bytes(file_content)
                outcome = await task_loop.complete_task(task_id, probe_answer=answer, artifact_path=artifact)
                journal.save(request_id, task_id, digest, "completed", outcome)
                reports[task_id] = outcome["attribution"]
                return outcome
            except Exception as error:
                journal.save(request_id, task_id, digest, "failed")
                raise HTTPException(422, "提交链未完成，请刷新任务状态并核对证据；可手动重试") from error

    @app.post("/api/tasks/{task_id}/submissions")
    async def submit(task_id: str, payload: Submission):
        if not payload.probe_answer.strip():
            raise HTTPException(422, "请填写理解回答")
        digest = hashlib.sha256(payload.probe_answer.encode()).hexdigest()
        return await complete_submission(task_id, payload.request_id, digest, answer=payload.probe_answer)

    @app.post("/api/tasks/{task_id}/files")
    async def upload(task_id: str, request: Request):
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_UPLOAD_BODY:
                raise HTTPException(413, "文件过大，最多支持 2 MB")
            body.extend(chunk)
        try:
            payload = FileSubmission.model_validate_json(body)
            content = base64.b64decode(payload.content_base64, validate=True)
        except (ValidationError, ValueError, binascii.Error) as error:
            raise HTTPException(422, "文件提交格式无效") from error
        if not content:
            raise HTTPException(422, "请提交非空文件")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, "文件过大，最多支持 2 MB")
        if any(c in payload.filename for c in ("/", "\\", ":", "\x00")) or payload.filename in (".", ".."):
            raise HTTPException(422, "文件名不能包含路径")
        suffix = Path(payload.filename).suffix.lower()
        route = payload.filename.lower() if payload.filename.lower() in CODE_FILENAMES else suffix
        digest = hashlib.sha256(b"file\0" + route.encode() + b"\0" + content).hexdigest()
        return await complete_submission(task_id, payload.request_id, digest,
                                         file_content=content, filename=payload.filename)

    @app.post("/api/tasks/{task_id}/actions")
    async def task_action(task_id: str, payload: TaskAction):
        if lock.locked():
            raise HTTPException(409, "提交处理中，请稍后操作")
        async with lock:
            task = store.get_task(task_id)
            if task is None:
                raise HTTPException(404, "任务不存在")
            expected = {"activate": ("proposed",), "block": ("active",),
                        "resume": ("blocked",), "abandon": ("proposed", "active", "blocked")}
            if task["status"] not in expected[payload.action]:
                raise HTTPException(409, "任务状态已改变，请刷新后操作")
            if payload.action in ("block", "abandon") and not (payload.reason or "").strip():
                raise HTTPException(422, "请填写原因")
            if payload.action == "activate":
                result = store.activate_task(task_id)
            elif payload.action == "block":
                result = store.block_task(task_id, payload.reason)
            elif payload.action == "resume":
                result = store.unblock_task(task_id)
            else:
                result = store.abandon_task(task_id, payload.reason)
            return {"task": result}

    app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    return app


async def seed_interaction(directory: Path, *, pending_practice: bool = False) -> dict:
    """创建全新实验，拒绝覆盖已有数据库。"""
    manifest = await seed_demo(directory, stop_before_submission=pending_practice)
    store = GrowthStore(str(directory.resolve() / "demo.db"))
    try:
        gap = next(g for g in store.list_gaps(capability_id=manifest["capability_id"], status="open")
                   if g["dimension"] == "understanding")
        task = store.create_task({
            "gap_id": gap["id"], "title": "解释 RAG 检索与评测的设计选择",
            "objective": "产出说明检索、重排、引用与失败案例的理解回答",
            "deliverable_type": "probe_answer", "est_minutes": 30,
            "acceptance_type": "probe_rubric", "acceptance": "提交设计说明与可核对的失败案例",
            "generated_by_run_id": "interaction_constructed_seed",
        })
        manifest.update({"interaction_enabled": True, "interaction_task_id": task})
        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
    finally:
        store.close()


def create_local_interactive_app():
    directory = Path(os.getenv("GROWTH_INTERACTION_DIRECTORY", str(INTERACTION_DIRECTORY))).resolve()
    manifest_path = directory / "manifest.json"
    database = directory / "demo.db"
    if not manifest_path.is_file() or not database.is_file():
        raise RuntimeError("请先运行 python -m growth_os.api.interactive")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("constructed") is not True or manifest.get("interaction_enabled") is not True:
        raise RuntimeError("仅接受独立交互实验库，请勿使用原只读 Demo")
    store = GrowthStore(str(database))
    evidence = adapter.open_store(database)
    journal = SubmissionJournal(directory / "requests.db")
    if os.getenv("GROWTH_INTERACTION_REAL_MODEL") == "1":
        gateway = adapter.agent_gateway()
    else:
        capability = store.get_capability(manifest["capability_id"])

        def propose(index, system, user):
            claim = re.search(r"clm_[0-9a-f]{6,}", user)
            if claim is None:
                raise ValueError("绑定提示缺少主张")
            return {"proposals": [{"claim_id": claim.group(0), "capability_path": capability["path"],
                                   "rationale": "受控交互实验：固定能力路径，不代表模型判断"}]}

        gateway = FakeGateway(responses={BINDING_TASK: propose})
    loop = TaskLoop(store=store, evidence_store=evidence, gateway=gateway,
                    submission_dir=directory / "submissions", report_directory=directory / "reports")
    app = create_interactive_app(store, evidence, loop_reports=manifest["loop_reports"],
                                 task_loop=loop, journal=journal)

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            evidence.db.close()
            store.close()
            journal.close()

    app.router.lifespan_context = lifespan
    return app


def main():
    parser = argparse.ArgumentParser(description="创建独立任务交互实验库（零网络调用）")
    parser.add_argument("--directory", type=Path, default=INTERACTION_DIRECTORY)
    parser.add_argument("--with-practice", action="store_true", help="创建尚未提交的实践任务，验证文件上传")
    args = parser.parse_args()
    manifest = asyncio.run(seed_interaction(args.directory, pending_practice=args.with_practice))
    print(json.dumps({"directory": str(args.directory.resolve()),
                      "task_id": manifest["interaction_task_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
