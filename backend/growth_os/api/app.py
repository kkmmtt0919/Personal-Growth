"""M8-a：只读产品 API。所有写操作继续走既有服务。"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from ..store import GrowthStore


def create_app(store: GrowthStore) -> FastAPI:
    app = FastAPI(title="Growth OS Read API")

    @app.get("/api/goals/{goal_id}")
    def goal(goal_id: str) -> dict:
        row = store.get_goal(goal_id)
        if row is None:
            raise HTTPException(404, "目标不存在")
        return {"id": row["id"], "title": row["title"], "status": row["status"]}

    @app.get("/api/capabilities/{capability_id}")
    def capability(capability_id: str) -> dict:
        row = store.get_capability(capability_id)
        if row is None:
            raise HTTPException(404, "能力点不存在")
        gaps = store.list_gaps(capability_id=capability_id, status="open")
        return {
            "id": row["id"],
            "name": row["name"],
            "understanding": row["current_level_understanding"],
            "practice": row["current_level_practice"],
            "gaps": [gap["rationale"] for gap in gaps],
        }

    @app.get("/api/evidence/{capability_id}")
    def evidence(capability_id: str) -> dict:
        row = store.get_capability(capability_id)
        if row is None:
            raise HTTPException(404, "能力点不存在")
        links = store.list_capability_claims(capability_id=capability_id, role="supports")
        return {
            "capability": row["name"],
            "assessment": {"practice": row["current_level_practice"], "understanding": row["current_level_understanding"]},
            "supports": [{"claim_id": link["claim_id"], "binding_reason": link["rationale"]} for link in links],
            "gaps": [gap["rationale"] for gap in store.list_gaps(capability_id=capability_id, status="open")],
        }

    @app.get("/api/growth-loop/{goal_id}")
    def growth_loop(goal_id: str) -> dict:
        if store.get_goal(goal_id) is None:
            raise HTTPException(404, "目标不存在")
        tasks = [task for task in store.list_tasks() if task["goal_id"] == goal_id]
        return {
            "tasks": [
                {
                    "id": task["id"],
                    "title": task["title"],
                    "status": task["status"],
                    "submissions": store.list_task_submissions(task_id=task["id"]),
                }
                for task in tasks
            ]
        }

    return app
