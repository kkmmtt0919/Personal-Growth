"""M7：确定性每日分析、冷却和通知开关。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from ..store import PROACTIVE_EVENT_KINDS

COOLDOWN = timedelta(days=7)


class ProactiveAnalyzer:
    def __init__(self, store, *, now: datetime | None = None, user_id: str = "local") -> None:
        self.store = store
        self.now = now or datetime.now(UTC)
        self.user_id = user_id

    def run_daily(self) -> dict:
        events = self.detect()
        if not self.store.proactive_enabled(self.user_id):
            return {"events": events, "notifications": []}
        notifications = []
        for event in events:
            if self._in_cooldown(event["kind"]):
                continue
            event_id = self.store.write_event(event["kind"], event["payload"])
            notification_id = "ntf_" + hashlib.sha256(f"{event_id}|local".encode()).hexdigest()[:16]
            self.store.insert_notification({"id": notification_id, "event_id": event_id, "channel": "local"})
            notifications.append(notification_id)
        return {"events": events, "notifications": notifications}

    def detect(self) -> list[dict]:
        found = []
        capabilities = []
        for goal in self.store.list_goals(self.user_id):
            if goal["status"] == "confirmed":
                capabilities.extend(self.store.list_capabilities(goal["id"], status="active"))
        for capability in capabilities:
            for dimension in ("understanding", "practice"):
                rows = [row for row in self.store.list_assessments(capability_id=capability["id"], dimension=dimension, status="rated")]
                if len(rows) >= 2 and (rows[-1]["level"] or 0) > (rows[-2]["level"] or 0):
                    found.append({"kind": "capability_evidence", "payload": {"assessment_id": rows[-1]["id"], "dimension": dimension}})
        recent_understanding = self._recent_assessments("understanding")
        recent_done = [task for task in self.store.list_tasks(status="done") if self._recent(task["updated_at"])]
        if recent_understanding and not recent_done:
            found.append({"kind": "practice_stalled", "payload": {"assessment_ids": [row["id"] for row in recent_understanding]}})
        for gap in self.store.list_gaps(status="open"):
            if gap["severity"] == "level_gap_2plus" and not self.store.list_tasks(gap_id=gap["id"]):
                found.append({"kind": "gap_without_task", "payload": {"gap_id": gap["id"]}})
        for goal in self.store.list_goals(self.user_id):
            if goal["status"] == "confirmed" and self._recent(goal["updated_at"]) and goal["created_at"] != goal["updated_at"]:
                found.append({"kind": "goal_changed", "payload": {"goal_id": goal["id"], "action": "regeneration_requested"}})
        unknown = {item["kind"] for item in found} - set(PROACTIVE_EVENT_KINDS)
        if unknown:
            raise RuntimeError(f"未知主动事件：{sorted(unknown)}")
        return found

    def _recent_assessments(self, dimension: str) -> list[dict]:
        return [row for row in self.store.list_assessments(dimension=dimension) if self._recent(row["created_at"])]

    def _recent(self, value: str) -> bool:
        try:
            moment = _parse_time(value)
        except ValueError:
            return False
        return self.now - timedelta(days=14) <= moment <= self.now

    def _in_cooldown(self, kind: str) -> bool:
        for event in reversed(self.store.list_events(kind=kind)):
            moment = _parse_time(event["created_at"])
            return self.now - moment < COOLDOWN
        return False


def _parse_time(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def dump_detection(events: list[dict]) -> str:
    return json.dumps(events, ensure_ascii=False, sort_keys=True)
