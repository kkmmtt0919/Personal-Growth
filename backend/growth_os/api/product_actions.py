import hashlib
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..store.product_actions import ProductActionStore


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=4000)
    confirm: Literal[True]


class Adjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    target_level: int = Field(ge=1, le=5, strict=True)
    expected_target_level: int = Field(ge=1, le=5, strict=True)
    note: str = Field(min_length=1, max_length=2000)
    confirm: Literal[True]


def register_product_actions(app, *, store, snapshot, agent, lock):
    actions = ProductActionStore(store.db)

    def confirmed(goal_id):
        state = snapshot(goal_id)
        if state["goal"]["status"] != "confirmed":
            raise HTTPException(409, "请先确认当前目标")
        return state

    def replay(request_id, kind, goal_id, payload):
        previous = actions.get(request_id)
        if previous and (previous["kind"] != kind or previous["goal_id"] != goal_id or previous["payload"] != payload):
            raise HTTPException(409, "请求标识已用于其他操作")
        return previous

    @app.get("/api/product/goals/{goal_id}/actions")
    async def history(goal_id: str):
        snapshot(goal_id)
        return {"actions": actions.history(goal_id)}

    @app.post("/api/product/goals/{goal_id}/revisions")
    async def revise(goal_id: str, payload: Revision):
        confirmed(goal_id)
        text = payload.text.strip()
        if not text:
            raise HTTPException(422, "请填写调整后的目标")
        intent = {"text": text}
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            previous = replay(payload.request_id, "goal_revision", goal_id, intent)
            new_id = "goal_" + hashlib.sha256(f"revision/{goal_id}/{payload.request_id}".encode()).hexdigest()[:24]
            if previous and store.get_goal(new_id):
                return {"parent_goal_id": goal_id, "state": snapshot(new_id), "replayed": True}
            actions.save(payload.request_id, "goal_revision", goal_id, intent, {"goal_id": new_id})
            try:
                await agent(new_id).start(text, goal_id=new_id)
            except Exception as error:
                raise HTTPException(502, "调整目标的提问未完成；原目标已保留，请从已保存目标继续或重试") from error
            return {"parent_goal_id": goal_id, "state": snapshot(new_id), "replayed": False}

    @app.post("/api/product/goals/{goal_id}/capabilities/{capability_id}/adjust")
    async def adjust(goal_id: str, capability_id: str, payload: Adjustment):
        confirmed(goal_id)
        note = payload.note.strip()
        if not note:
            raise HTTPException(422, "请填写调整理由")
        capability = store.get_capability(capability_id)
        if capability is None or capability["goal_id"] != goal_id:
            raise HTTPException(404, "能力点不存在")
        if capability["depth"] != 3 or capability["status"] != "active":
            raise HTTPException(409, "只能调整有效能力点的目标要求")
        intent = {"capability_id": capability_id, "before": payload.expected_target_level,
                  "target_level": payload.target_level, "note": note}
        if lock.locked():
            raise HTTPException(409, "另一项操作正在处理，请稍后重试")
        async with lock:
            previous = replay(payload.request_id, "capability_adjustment", goal_id, intent)
            if previous and previous["result"]:
                return previous["result"]
            # 未完成的操作可在重开后恢复；不同请求不得覆盖后来发生的修改。
            applied = previous and capability["target_level"] == payload.target_level and capability["adjustment_note"] == note
            if not applied and capability["target_level"] != payload.expected_target_level:
                raise HTTPException(409, "目标要求已改变，请刷新核对后再确认")
            actions.save(payload.request_id, "capability_adjustment", goal_id, intent)
            try:
                if not applied:
                    store.adjust_capability(capability_id, payload.target_level, note)
                result = {"capability": store.get_capability(capability_id), "action_id": payload.request_id}
                actions.save(payload.request_id, "capability_adjustment", goal_id, intent, result)
            except Exception as error:
                raise HTTPException(502, "操作未完成，请刷新核对当前要求并重试；已保留调整意图与原评定") from error
            return result

    return actions
