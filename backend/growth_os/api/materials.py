"""已有个人材料：入库与绑定预览、显式确认后通过既有闸门重评。"""

import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..agent import AgentContext, AgentRuntime, FakeGateway
from ..assessment.binding import BindingGate, ProposalItem
from ..assessment.pipeline import assess_capability
from ..evidence import adapter
from ..evidence.archive import CODE_FILENAMES, CODE_SUFFIXES
from .interactive import MAX_FILE_BYTES, MAX_UPLOAD_BODY


class MaterialUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=MAX_UPLOAD_BODY)
    capability_id: str = Field(min_length=1, max_length=100)
    evidence_type: Literal["uploaded_doc", "repo_artifact"]
    attribution: Literal["user_declared", "unknown"]


class ConfirmMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


def register_material_routes(app, *, store, evidence_store, journal, directory, lock):
    def goal(goal_id):
        row = store.get_goal(goal_id)
        if row is None or row["user_id"] != "local":
            raise HTTPException(404, "目标不存在")
        if row["status"] != "confirmed":
            raise HTTPException(409, "请先确认目标")
        return row

    def capability(goal_id, capability_id):
        row = store.get_capability(capability_id)
        if row is None or row["goal_id"] != goal_id:
            raise HTTPException(404, "目标能力点不存在")
        if row["depth"] != 3 or row["status"] != "active":
            raise HTTPException(409, "请选择有效的第三层能力点")
        return row

    @app.get("/api/onboarding/goals/{goal_id}/materials")
    async def materials(goal_id: str):
        goal(goal_id)
        return {"materials": journal.completed_results("material:" + goal_id)}

    @app.post("/api/onboarding/goals/{goal_id}/materials")
    async def upload(goal_id: str, request: Request):
        goal(goal_id)
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_UPLOAD_BODY:
                raise HTTPException(413, "材料过大，最多支持2 MB")
            body.extend(chunk)
        try:
            payload = MaterialUpload.model_validate_json(body)
            content = base64.b64decode(payload.content_base64, validate=True)
        except (ValidationError, ValueError, binascii.Error) as error:
            raise HTTPException(422, "材料格式无效") from error
        if not content or len(content) > MAX_FILE_BYTES:
            raise HTTPException(413 if content else 422, "请选择非空材料，最多2 MB")
        filename = payload.filename
        if any(char in filename for char in ("/", "\\", ":", "\x00")) or filename in (".", ".."):
            raise HTTPException(422, "文件名不能包含路径")
        suffix = Path(filename).suffix.lower()
        code = suffix in CODE_SUFFIXES or filename.lower() in CODE_FILENAMES
        if suffix not in (".md", ".markdown", ".txt") and not code:
            raise HTTPException(422, "仅支持Markdown、TXT与代码材料")
        if code and payload.evidence_type != "repo_artifact":
            raise HTTPException(422, "代码请选择项目产物类型")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise HTTPException(422, "材料须使用UTF-8编码") from error
        if not text.strip() or "\x00" in text:
            raise HTTPException(422, "请选择非空文本材料")
        digest = hashlib.sha256(payload.model_dump_json(exclude={"request_id"}).encode()).hexdigest()
        scope = "material:" + goal_id
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            previous = journal.get(payload.request_id)
            if previous:
                if previous[:2] != (scope, digest):
                    raise HTTPException(409, "请求标识已用于其他材料")
                if previous[2] == "completed":
                    return json.loads(previous[3])
                if previous[2] in ("running", "interrupted"):
                    raise HTTPException(409, "上次入库被中断，请核对材料后恢复")
            target = capability(goal_id, payload.capability_id)
            journal.save(payload.request_id, scope, digest, "running")
            folder = Path(directory) / "materials" / hashlib.sha256(goal_id.encode()).hexdigest() / digest
            artifact = folder / (filename.lower() if filename.lower() in CODE_FILENAMES else "material" + suffix)
            try:
                folder.mkdir(parents=True, exist_ok=True)
                artifact.write_bytes(content)
                source = adapter.ingest_document(artifact, store=evidence_store, evidence_type=payload.evidence_type,
                    attribution=payload.attribution, title=filename, extra_metadata={"growth_goal_id": goal_id})
                passages = evidence_store.get_passages(source_id=source.source_id)
                claim = adapter.create_material_claim(evidence_store, subject="上传材料", predicate="包含",
                    object="用户选择的材料内容", statement=f"上传材料《{filename}》包含待核对的材料内容。",
                    passage_ids=[item.id for item in passages[:3]])
                proposal = {"claim_id": claim["claim_id"], "capability_path": target["path"],
                            "rationale": "用户选择此能力点；材料内容与能力的相关性待用户确认，未判断材料质量"}
                runtime = AgentRuntime(store=store, gateway=FakeGateway(responses={"material_preview": proposal}), agent="material_preview")
                outcome = await runtime.call_model_with_run(system="记录用户选择的绑定候选；不写绑定、不评级。",
                    user=json.dumps(proposal, ensure_ascii=False), schema=ProposalItem, task="material_preview",
                    context=AgentContext(goal_id=goal_id, correlation_id=payload.request_id))
                record = {"request_id": payload.request_id, "goal_id": goal_id, "filename": filename,
                          "source_id": source.source_id, "evidence_type": payload.evidence_type,
                          "attribution": payload.attribution, "capability_id": target["id"],
                          "proposal": proposal, "run_id": outcome.run_id, "binding_status": "preview",
                          "quotes": [{"text": item.text, "locator": item.locator} for item in passages[:3]],
                          "passage_count": source.passage_count}
                journal.save(payload.request_id, scope, digest, "completed", record)
                return record
            except Exception as error:
                journal.save(payload.request_id, scope, digest, "failed")
                raise HTTPException(422, "材料入库或预览未完成；请核对后手动重试") from error

    @app.post("/api/onboarding/goals/{goal_id}/materials/{request_id}/confirm")
    async def confirm(goal_id: str, request_id: str, payload: ConfirmMaterial):
        goal(goal_id)
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            row = journal.get(request_id)
            if row is None or row[0] != "material:" + goal_id or row[2] != "completed":
                raise HTTPException(404, "材料预览不存在")
            record = json.loads(row[3])
            if record["binding_status"] == "confirmed":
                return record
            capability(goal_id, record["capability_id"])
            existing = store.list_capability_claims(capability_id=record["capability_id"], role="supports")
            accepted = any(link["claim_id"] == record["proposal"]["claim_id"] for link in existing)
            if not accepted:
                decision = BindingGate(store=store, evidence_store=evidence_store, goal_id=goal_id,
                    candidate_claim_ids=[record["proposal"]["claim_id"]]).evaluate(record["proposal"],
                    run_id=record["run_id"], index=0, proposer="user_selected/explicit_confirmation")
                record["decision"] = decision.to_dict()
                journal.save(request_id, row[0], row[1], "completed", record)
                if not decision.accepted:
                    raise HTTPException(422, "绑定未通过闸门：" + (decision.reject_reason or "请核对材料"))
            record["binding_status"] = "bound_pending_assessment"
            journal.save(request_id, row[0], row[1], "completed", record)
            try:
                record["assessment"] = assess_capability(store, evidence_store, capability_id=record["capability_id"])
            except Exception as error:
                raise HTTPException(502, "绑定已保留，重评未完成；请手动重试") from error
            record["binding_status"] = "confirmed"
            journal.save(request_id, row[0], row[1], "completed", record)
            return record
