"""M6-a：记忆契约与审计写入。

Memory 是可回放的状态记录，不是能力判断：

* 应用代码只能通过 `MemoryService.remember` 写入；
* 每条记录必须带可解析来源；
* 相同来源与内容回放得到同一条 active 记录；
* 更新保留旧行并标记 `superseded`。
"""

from __future__ import annotations

import hashlib
import json

from ..store import GrowthStoreError

MEMORY_LAYERS = ("profile", "state", "history")
MEMORY_SOURCE_KINDS = ("user_statement", "task", "gap", "assessment")
MEMORY_STATUSES = ("active", "superseded")
ACHIEVEMENT_MARKERS = ("掌握", "具备", "精通", "完成了", "会了")


class MemoryError(RuntimeError):
    """记忆契约不成立。"""


def memory_id_for(user_id: str, layer: str, key: str, source_kind: str, source_id: str, value: dict) -> str:
    raw = json.dumps(
        {
            "user_id": user_id,
            "layer": layer,
            "key": key,
            "source_kind": source_kind,
            "source_id": source_id,
            "value": value,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "mem_" + hashlib.sha256(raw.encode()).hexdigest()[:20]


class MemoryService:
    def __init__(self, store) -> None:
        self.store = store

    def remember(
        self,
        *,
        layer: str,
        key: str,
        value: dict,
        source_kind: str,
        source_id: str,
        user_id: str = "local",
    ) -> dict:
        self._validate(layer, key, value, source_kind, source_id)
        self._require_source(source_kind, source_id)
        identifier = memory_id_for(user_id, layer, key, source_kind, source_id, value)
        existing = self.store.get_memory(identifier)
        if existing is not None:
            return self._view(existing)

        current = self.store.list_memories(layer=layer, memory_key=key, status="active")
        supersedes = current[0]["id"] if current else None
        if supersedes:
            self.store.mark_memory_superseded(supersedes)
        row = {
            "id": identifier,
            "user_id": user_id,
            "layer": layer,
            "memory_key": key,
            "value_json": json.dumps(value, ensure_ascii=False, sort_keys=True),
            "status": "active",
            "source_kind": source_kind,
            "source_id": source_id,
            "supersedes_id": supersedes,
        }
        self.store.insert_memory(row)
        self.store.write_event(
            "memory_changed",
            {"memory_id": identifier, "layer": layer, "key": key, "supersedes_id": supersedes, "source_kind": source_kind, "source_id": source_id},
        )
        return self._view(self.store.get_memory(identifier))

    def active_view(self, *, layer: str | None = None) -> list[dict]:
        return [self._view(row) for row in self.store.list_memories(layer=layer, status="active")]

    def replay(self, *, layer: str, key: str, source_kind: str, source_id: str) -> dict:
        rows = self.store.list_memories(layer=layer, memory_key=key, source_kind=source_kind, source_id=source_id, status="active")
        if len(rows) != 1:
            raise MemoryError(f"来源无法重放成唯一记忆：{layer}/{key}/{source_id}")
        return self._view(rows[0])

    def _validate(self, layer: str, key: str, value: dict, source_kind: str, source_id: str) -> None:
        if layer not in MEMORY_LAYERS:
            raise MemoryError(f"未知记忆层：{layer}")
        if layer == "history" and source_kind != "assessment":
            raise MemoryError("history 只能由 assessment 投影")
        if source_kind not in MEMORY_SOURCE_KINDS:
            raise MemoryError(f"未知记忆来源：{source_kind}")
        if not key.strip() or not source_id.strip() or not isinstance(value, dict) or not value:
            raise MemoryError("记忆需要 key、value 和 source_id")
        if any(marker in json.dumps(value, ensure_ascii=False) for marker in ACHIEVEMENT_MARKERS):
            raise MemoryError("记忆不得写成能力成就")

    def _require_source(self, source_kind: str, source_id: str) -> None:
        if source_kind == "task" and self.store.get_task(source_id) is None:
            raise MemoryError(f"记忆引用的任务不存在：{source_id}")
        if source_kind == "gap" and self.store.get_gap(source_id) is None:
            raise MemoryError(f"记忆引用的缺口不存在：{source_id}")
        if source_kind == "assessment" and self.store.get_assessment(source_id) is None:
            raise MemoryError(f"记忆引用的评定不存在：{source_id}")
        if source_kind == "user_statement" and not source_id.startswith("statement_"):
            raise MemoryError("用户陈述来源必须使用 statement_ 标识")

    @staticmethod
    def _view(row: dict) -> dict:
        return {**row, "value": json.loads(row["value_json"])}


def assert_service_is_only_writer() -> None:
    """供测试调用的说明性守卫；真实 AST 检查在测试里执行。"""
    if GrowthStoreError is None:  # pragma: no cover
        raise MemoryError("store 不可用")
