"""G6-a：确定性、只读的用户返回摘要；每项结论引用已持久化来源。"""

from __future__ import annotations

import json
from datetime import UTC, datetime

DIMENSIONS = {"understanding": "理解", "practice": "实践"}
PREFERENCE_KEYS = {"preference", "preferences", "learning_style", "learning_preference"}


class ReturnSummaryError(ValueError):
    """请求来源不匹配、快照失效或数据无法核验。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReturnSummaryError(message)


def parse_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ReturnSummaryError("快照时间无效") from error
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class GrowthReturnAgent:
    """输出变化、下一步和偏好；不调用模型，也不产生任何存储写入。"""

    def __init__(self, store) -> None:
        self.store = store

    def summarize(
        self, *, goal_id: str, current_snapshot_id: str,
        baseline_snapshot_id: str | None = None, user_id: str = "local",
        returned_at: datetime | None = None,
    ) -> dict:
        moment = returned_at or datetime.now(UTC)
        require(moment.tzinfo is not None, "返回时间必须带时区")
        goal = self.store.get_goal(goal_id)
        require(goal is not None and goal["user_id"] == user_id, "目标不存在或不属于该用户")
        require(goal["status"] == "confirmed", "只能为已确认目标生成返回摘要")
        capabilities = self.store.list_capabilities(goal_id, status="active")
        current = self._snapshot(current_snapshot_id, user_id, goal_id)
        require(parse_time(current["taken_on"]) <= moment, "当前快照晚于返回时间")
        current_ids = current["assessment_ids"]
        baseline = None
        if baseline_snapshot_id is not None:
            baseline = self._snapshot(baseline_snapshot_id, user_id, goal_id)
            require(set(baseline["assessment_ids"]) <= set(current_ids), "基线不是当前快照的历史子集")
            require(parse_time(baseline["taken_on"]) <= parse_time(current["taken_on"]),
                    "基线快照晚于当前快照")
        changes = []
        state = []
        for capability in capabilities:
            require(self.store.verify_gaps(capability["id"])["consistent"], "当前缺口与评定不一致")
            levels = {}
            for dimension, label in DIMENSIONS.items():
                latest = self.store.latest_assessment(capability["id"], dimension)
                now = self.store.latest_assessment(
                    capability["id"], dimension, assessment_ids=current_ids)
                require((latest or {}).get("id") == (now or {}).get("id"),
                        "当前快照已过时，缺少最新评定")
                levels[dimension] = now["level"] if now else None
                if baseline is None:
                    continue
                before = self.store.latest_assessment(
                    capability["id"], dimension, assessment_ids=baseline["assessment_ids"])
                before_level = before["level"] if before else None
                after_level = now["level"] if now else None
                if before_level == after_level and (before or {}).get("status") == (now or {}).get("status"):
                    continue
                status = ("evidence_added" if before_level is None and after_level is not None
                          else "insufficient_evidence" if after_level is None
                          else "level_increased" if after_level > before_level
                          else "level_decreased")
                text = (f"{capability['name']}：{label} "
                        f"{before_level if before_level is not None else '未评估'} → "
                        f"{after_level if after_level is not None else '证据不足'}")
                changes.append({
                    "capability_id": capability["id"], "dimension": dimension,
                    "before_level": before_level, "after_level": after_level,
                    "status": status, "text": text,
                    "before_assessment_id": (before or {}).get("id"),
                    "after_assessment_id": (now or {}).get("id"),
                    "baseline_snapshot_id": baseline_snapshot_id,
                    "current_snapshot_id": current_snapshot_id,
                })
            state.append({"capability_id": capability["id"], "name": capability["name"],
                          "target_level": capability["target_level"], **levels})
        steps = self._next_steps(goal_id, user_id, {cap["id"] for cap in capabilities})
        preferences = self._preferences(user_id)
        summary_status = "baseline_missing" if baseline is None else "changed" if changes else "unchanged"
        text = ("未记录上次快照，无法比较变化。" if baseline is None
                else "；".join(change["text"] for change in changes) if changes
                else "与上次快照相比，理解和实践等级没有变化。")
        return {
            "contract": "g6-return-1", "mode": "deterministic_read_only",
            "user_id": user_id, "goal_id": goal_id, "goal_title": goal["title"],
            "returned_at": moment.isoformat(),
            "baseline_snapshot_id": baseline_snapshot_id, "current_snapshot_id": current_snapshot_id,
            "summary": {"status": summary_status, "text": text, "changes": changes},
            "current_state": state, "next_steps": steps,
            "next_step_text": "；".join(step["text"] for step in steps) if steps else "当前没有开放缺口或待执行任务。",
            "preferences": preferences,
            "preference_text": "；".join(item["text"] for item in preferences) if preferences else "尚未记录长期学习偏好。",
        }

    def _snapshot(self, identifier: str, user_id: str, goal_id: str) -> dict:
        row = self.store.get_snapshot(identifier)
        require(row is not None and row["user_id"] == user_id, "快照不存在或不属于该用户")
        try:
            scores = json.loads(row["scores_json"])
        except (TypeError, ValueError) as error:
            raise ReturnSummaryError("快照内容无效") from error
        require(isinstance(scores, list) and bool(scores), "快照缺少评定")
        ids = []
        target_present = False
        for score in scores:
            require(isinstance(score, dict), "快照评定内容无效")
            assessment = self.store.get_assessment(score.get("assessment_id"))
            require(assessment is not None and assessment["user_id"] == user_id,
                    "快照引用未知或跨用户评定")
            require(assessment["status"] in ("rated", "insufficient_evidence"), "快照不能引用草案")
            for key in ("capability_id", "dimension", "level", "status", "created_at"):
                require(score.get(key) == assessment[key], "快照与评定来源不一致")
            require(parse_time(assessment["created_at"]) <= parse_time(row["taken_on"]),
                    "快照包含晚于快照时间的评定")
            target_present |= assessment["goal_id"] == goal_id
            ids.append(assessment["id"])
        require(target_present, "快照不包含目标的评定")
        require(len(ids) == len(set(ids)), "快照含重复评定")
        return {**row, "assessment_ids": ids}

    def _next_steps(self, goal_id: str, user_id: str, capability_ids: set[str]) -> list[dict]:
        tasks = [task for task in self.store.list_tasks()
                 if task["goal_id"] == goal_id and task["user_id"] == user_id
                 and task["capability_id"] in capability_ids
                 and task["status"] in ("active", "proposed", "blocked")]
        steps = []
        linked_gap_ids = set()
        for task in tasks:
            gap = self.store.get_gap(task["gap_id"])
            require(gap is not None and gap["goal_id"] == goal_id and gap["user_id"] == user_id,
                    "任务缺口来源不匹配")
            if gap["status"] != "open":
                steps.append({"kind": "review_task", "gap_id": gap["id"], "task_id": task["id"],
                              "assessment_id": gap["assessment_id"],
                              "text": f"核对任务是否仍需执行：{task['title']}；原证据缺口已关闭。"})
                continue
            linked_gap_ids.add(gap["id"])
            action = "先解除阻塞" if task["status"] == "blocked" else "确认任务" if task["status"] == "proposed" else "继续任务"
            steps.append({"kind": "existing_task", "gap_id": gap["id"], "task_id": task["id"],
                          "assessment_id": gap["assessment_id"],
                          "text": f"{action}：{task['title']}；验收：{task['acceptance']}"})
        for gap in self.store.list_gaps(status="open"):
            if gap["goal_id"] != goal_id or gap["user_id"] != user_id or gap["capability_id"] not in capability_ids:
                continue
            if gap["id"] not in linked_gap_ids:
                steps.append({"kind": "evidence_gap", "gap_id": gap["id"], "task_id": None,
                              "assessment_id": gap["assessment_id"],
                              "text": f"下一步补充{DIMENSIONS[gap['dimension']]}证据：{gap['rationale']}"})
        return steps

    def _preferences(self, user_id: str) -> list[dict]:
        preferences = []
        for row in self.store.list_memories(layer="profile", status="active"):
            if row["user_id"] != user_id or row["memory_key"] not in PREFERENCE_KEYS:
                continue
            require(row["source_kind"] == "user_statement"
                    and row["source_id"].startswith("statement_"), "偏好缺少用户陈述来源")
            try:
                value = json.loads(row["value_json"])
            except (TypeError, ValueError) as error:
                raise ReturnSummaryError("偏好内容无效") from error
            require(isinstance(value, dict) and isinstance(value.get("text"), str)
                    and bool(value["text"].strip()), "偏好缺少明确文本")
            preferences.append({"memory_id": row["id"], "key": row["memory_key"],
                                "text": value["text"], "source_kind": row["source_kind"],
                                "source_id": row["source_id"]})
        return preferences
