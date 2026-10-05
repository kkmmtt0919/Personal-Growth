"""M8-a：只读产品 API。所有写操作继续走既有服务。"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException

from ..agent.return_summary import GrowthReturnAgent, ReturnSummaryError
from ..evidence import adapter
from ..store import GrowthStore


def create_app(store: GrowthStore, evidence_store=None, *, loop_reports=None, return_context=None) -> FastAPI:
    app = FastAPI(title="Growth OS Read API")

    @app.get("/api/return-demo/{goal_id}")
    def return_demo(goal_id: str) -> dict:
        if not return_context or return_context.get("goal_id") != goal_id:
            raise HTTPException(404, "该目标没有受控隔天返回场景")
        try:
            report = GrowthReturnAgent(store).summarize(
                goal_id=goal_id,
                current_snapshot_id=return_context["current_snapshot_id"],
                baseline_snapshot_id=return_context["baseline_snapshot_id"],
                returned_at=datetime.fromisoformat(return_context["returned_at"]),
            )
        except (ReturnSummaryError, KeyError, ValueError) as error:
            raise HTTPException(422, "返回场景无法核验") from error
        return {"constructed": True, "simulated_return": True, "report": report}

    @app.get("/api/return/{goal_id}")
    def return_summary(
        goal_id: str, current_snapshot_id: str, baseline_snapshot_id: str | None = None
    ) -> dict:
        try:
            return GrowthReturnAgent(store).summarize(
                goal_id=goal_id, current_snapshot_id=current_snapshot_id,
                baseline_snapshot_id=baseline_snapshot_id,
            )
        except ReturnSummaryError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/goals/{goal_id}")
    def goal(goal_id: str) -> dict:
        row = store.get_goal(goal_id)
        if row is None:
            raise HTTPException(404, "目标不存在")
        return {"id": row["id"], "title": row["title"], "status": row["status"]}

    @app.get("/api/goals/{goal_id}/capabilities")
    def capabilities(goal_id: str) -> dict:
        goal_row = store.get_goal(goal_id)
        if goal_row is None:
            raise HTTPException(404, "目标不存在")
        rows = []
        for capability_row in store.list_capabilities(goal_id, status="active"):
            gaps = store.list_gaps(capability_id=capability_row["id"], status="open")
            rows.append({
                "id": capability_row["id"],
                "name": capability_row["name"],
                "target_level": capability_row["target_level"],
                "understanding": capability_row["current_level_understanding"],
                "practice": capability_row["current_level_practice"],
                "open_gaps": [{"dimension": gap["dimension"], "severity": gap["severity"]} for gap in gaps],
            })
        return {"goal_id": goal_id, "goal_title": goal_row["title"], "capabilities": rows}

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
        dossiers = {item["claim"]["id"]: item for item in adapter.claims_overview(evidence_store)} if evidence_store else {}
        supports = []
        for link in links:
            dossier = dossiers.get(link["claim_id"], {})
            first = max(dossier.get("evidence") or [{}],
                        key=lambda item: len(item.get("quote") or ""))
            source = first.get("source") or {}
            passage = first.get("passage") or {}
            supports.append({
                "claim_id": link["claim_id"],
                "source": {"id": source.get("id"), "name": source.get("title"), "type": (source.get("metadata") or {}).get("growth_evidence_type")},
                "quote": {"text": first.get("quote"), "locator": passage.get("locator")},
                "binding_reason": link["rationale"],
            })
        return {
            "capability": row["name"],
            "assessment": {"practice": row["current_level_practice"], "understanding": row["current_level_understanding"]},
            "supports": supports,
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
                    "gap": store.get_gap(task["gap_id"]),
                    "objective": task["objective"],
                    "acceptance": task["acceptance"],
                    "capability_id": task["capability_id"],
                    "attribution": (loop_reports or {}).get(task["id"]),
                    "submissions": store.list_task_submissions(task_id=task["id"]),
                }
                for task in tasks
            ]
        }

    return app
