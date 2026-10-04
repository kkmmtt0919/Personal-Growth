"""M6-b：由已治理来源确定性投影 state 与 history。"""

from __future__ import annotations

import hashlib
import json

from .service import MemoryService

PROJECTED_STATE_KEYS = ("current_task", "open_gaps", "understood", "not_understood")


def snapshot_id_for(assessment_ids: list[str]) -> str:
    raw = ",".join(sorted(assessment_ids))
    return "snap_" + hashlib.sha256(raw.encode()).hexdigest()[:20]


class MemoryProjection:
    def __init__(self, store) -> None:
        self.store = store
        self.memory = MemoryService(store)

    def project(self, *, user_id: str = "local") -> dict:
        self._project_state(user_id)
        snapshots = self._project_history(user_id)
        return {"state": self.memory.active_view(layer="state"), "snapshots": snapshots}

    def clear_projected(self) -> None:
        self.store.clear_projected_memory()

    def _project_state(self, user_id: str) -> None:
        active = self.store.list_tasks(status="active")
        if active:
            task = active[0]
            self.memory.remember(layer="state", key="current_task", value={"task_id": task["id"], "title": task["title"]}, source_kind="task", source_id=task["id"], user_id=user_id)
        for gap in self.store.list_gaps(status="open"):
            key = "understood" if gap["dimension"] == "understanding" else "not_understood"
            self.memory.remember(layer="state", key=key, value={"gap_id": gap["id"], "dimension": gap["dimension"], "severity": gap["severity"]}, source_kind="gap", source_id=gap["id"], user_id=user_id)
        open_ids = sorted(gap["id"] for gap in self.store.list_gaps(status="open"))
        if open_ids:
            self.memory.remember(layer="state", key="open_gaps", value={"gap_ids": open_ids}, source_kind="gap", source_id=open_ids[0], user_id=user_id)

    def _project_history(self, user_id: str) -> list[dict]:
        rows = [
            row for row in self.store.list_assessments()
            if row["status"] in ("rated", "insufficient_evidence")
        ]
        if not rows:
            return []
        scores = [
            {"assessment_id": row["id"], "capability_id": row["capability_id"], "dimension": row["dimension"], "level": row["level"], "status": row["status"], "created_at": row["created_at"]}
            for row in sorted(rows, key=lambda item: item["id"])
        ]
        identifier = snapshot_id_for([item["assessment_id"] for item in scores])
        self.store.insert_snapshot({"id": identifier, "user_id": user_id, "taken_on": max(item["created_at"] for item in scores), "scores_json": json.dumps(scores, ensure_ascii=False, sort_keys=True)})
        self.memory.remember(layer="history", key="growth_snapshot", value={"snapshot_id": identifier, "assessment_ids": [item["assessment_id"] for item in scores]}, source_kind="assessment", source_id=scores[0]["assessment_id"], user_id=user_id)
        return self.store.list_snapshots()

    def verify(self) -> dict:
        before = self._signature()
        self.clear_projected()
        self.project()
        after = self._signature()
        return {"consistent": before == after, "before": before, "after": after}

    def _signature(self) -> dict:
        memories = [
            (row["layer"], row["memory_key"], row["source_kind"], row["source_id"], row["value_json"])
            for row in self.store.list_memories(status="active") if row["layer"] in ("state", "history")
        ]
        snapshots = [(row["id"], row["scores_json"]) for row in self.store.list_snapshots()]
        return {"memories": sorted(memories), "snapshots": sorted(snapshots)}
