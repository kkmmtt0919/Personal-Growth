import asyncio
import hashlib

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..agent.mentor import answer_mentor
from ..memory import MemoryError, MemoryService


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=6000)


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)


def register_mentor_routes(app, *, store, evidence_store, conversations, gateway, lock):
    def require_goal(goal_id):
        goal = store.get_goal(goal_id)
        if goal is None or goal["user_id"] != "local":
            raise HTTPException(404, "目标不存在")
        return goal

    @app.get("/api/mentor/{goal_id}")
    async def history(goal_id: str):
        require_goal(goal_id)
        return {"turns": conversations.history(goal_id)}

    @app.post("/api/mentor/{goal_id}")
    async def message(goal_id: str, payload: ChatMessage):
        require_goal(goal_id)
        text = payload.text.strip()
        if not text:
            raise HTTPException(422, "请填写消息")
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            previous = conversations.get(payload.request_id)
            if previous and (previous["goal_id"] != goal_id or previous["text"] != text):
                raise HTTPException(409, "请求标识已用于其他消息")
            if previous and previous["status"] == "completed":
                return previous
            conversations.save(payload.request_id, goal_id, text, "running")
            try:
                result, context = await asyncio.wait_for(answer_mentor(store, evidence_store, gateway,
                    goal_id=goal_id, text=text, history=conversations.history(goal_id), request_id=payload.request_id), timeout=180)
            except Exception as error:
                conversations.save(payload.request_id, goal_id, text, "failed")
                raise HTTPException(502, "导师回复未完成，消息已保存；可手动重试，没有修改目标或能力") from error
            conversations.save(payload.request_id, goal_id, text, "completed", response=result, context=context)
            return conversations.get(payload.request_id)

    @app.get("/api/product/preferences")
    async def preferences():
        return {"preferences": MemoryService(store).active_view(layer="profile")}

    @app.post("/api/product/preferences")
    async def preference(payload: Preference):
        text = payload.text.strip()
        if not text:
            raise HTTPException(422, "请填写学习偏好")
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            try:
                return MemoryService(store).remember(layer="profile", key="learning_preference", value={"text": text},
                    source_kind="user_statement", source_id="statement_" + hashlib.sha256(text.encode()).hexdigest()[:20])
            except MemoryError as error:
                raise HTTPException(422, str(error)) from error
