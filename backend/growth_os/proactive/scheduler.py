"""M7-b：每日调度、同日幂等和失败即停。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .analyzer import ProactiveAnalyzer


class UtcClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ProactiveScheduler:
    def __init__(self, store, *, clock=None, user_id: str = "local") -> None:
        self.store = store
        self.clock = clock or UtcClock()
        self.user_id = user_id

    def trigger(self) -> dict:
        moment = self.clock.now()
        analysis_date = moment.astimezone(UTC).date().isoformat()
        existing = self.store.get_proactive_run(analysis_date, self.user_id)
        if existing is not None:
            return {"reused": True, "run": self.audit(existing)}
        try:
            result = ProactiveAnalyzer(self.store, now=moment, user_id=self.user_id).run_daily()
        except Exception as error:
            self.store.write_event("proactive_run_failed", {"analysis_date": analysis_date, "error": f"{type(error).__name__}: {error}"})
            self._save(analysis_date, "error", error=f"{type(error).__name__}: {error}")
            raise
        self._save(analysis_date, "ok", result=result)
        return {"reused": False, "run": self.audit(self.store.get_proactive_run(analysis_date, self.user_id))}

    def _save(self, analysis_date: str, status: str, *, result: dict | None = None, error: str | None = None) -> None:
        identifier = "par_" + hashlib.sha256(f"{self.user_id}|{analysis_date}".encode()).hexdigest()[:16]
        self.store.insert_proactive_run({"id": identifier, "user_id": self.user_id, "analysis_date": analysis_date, "status": status, "result_json": json.dumps(result, ensure_ascii=False, sort_keys=True) if result else None, "error": error})

    @staticmethod
    def audit(row: dict) -> dict:
        """把一次调度记录整理成可追溯审计，不重新执行检测。"""
        result = json.loads(row["result_json"]) if row["result_json"] else {}
        events = result.get("events", [])
        return {
            "analysis_date": row["analysis_date"],
            "status": row["status"],
            "event_kinds": [item["kind"] for item in events],
            "notification_ids": result.get("notifications", []),
            "error": row["error"],
            "goal_regeneration": "not_implemented",
        }

    @staticmethod
    def _decode(row: dict) -> dict:
        return json.loads(row["result_json"]) if row["result_json"] else {"status": row["status"], "error": row["error"]}
