"""M6-a：记忆契约、来源、重放与唯一写入路径。"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from growth_os.memory import MemoryError, MemoryService
from growth_os.store import EVENT_KINDS, GrowthStore

ROOT = Path(__file__).parents[1]


@pytest.fixture()
def env(tmp_path: Path):
    store = GrowthStore(str(tmp_path / "memory.db"))
    store.upsert_user("local", "本地用户")
    service = MemoryService(store)
    try:
        yield store, service
    finally:
        store.close()


def test_explicit_memory_is_replayable(env):
    store, service = env
    first = service.remember(layer="profile", key="learning_style", value={"text": "先看架构再看源码"}, source_kind="user_statement", source_id="statement_1")
    second = service.remember(layer="profile", key="learning_style", value={"text": "先看架构再看源码"}, source_kind="user_statement", source_id="statement_1")
    assert first["id"] == second["id"]
    assert len(store.list_memories(status="active")) == 1
    assert service.replay(layer="profile", key="learning_style", source_kind="user_statement", source_id="statement_1")["id"] == first["id"]


def test_update_keeps_history(env):
    _, service = env
    first = service.remember(layer="state", key="current_topic", value={"text": "Agent Runtime"}, source_kind="user_statement", source_id="statement_topic_1")
    second = service.remember(layer="state", key="current_topic", value={"text": "Memory"}, source_kind="user_statement", source_id="statement_topic_2")
    assert first["status"] == "active"
    assert service.active_view(layer="state")[0]["id"] == second["id"]
    assert service.store.get_memory(first["id"])["status"] == "superseded"
    assert second["supersedes_id"] == first["id"]


def test_missing_or_invalid_source_is_rejected(env):
    _, service = env
    with pytest.raises(MemoryError, match="任务不存在"):
        service.remember(layer="state", key="current_task", value={"task_id": "task_x"}, source_kind="task", source_id="task_x")
    with pytest.raises(MemoryError, match="能力成就"):
        service.remember(layer="profile", key="claim", value={"text": "用户掌握 RAG"}, source_kind="user_statement", source_id="statement_bad")
    with pytest.raises(MemoryError, match="不允许写入层"):
        service.remember(layer="history", key="scores", value={"level": 4}, source_kind="assessment", source_id="asm_x")


def test_memory_change_is_audited(env):
    store, service = env
    service.remember(layer="profile", key="preference", value={"text": "喜欢代码实践"}, source_kind="user_statement", source_id="statement_pref")
    events = store.list_events(kind="memory_changed")
    assert len(events) == 1
    assert "memory_changed" in EVENT_KINDS


def test_application_code_cannot_insert_memory_directly():
    offenders = []
    for path in (ROOT / "backend" / "growth_os").rglob("*.py"):
        if path.parts[-2:] == ("memory", "service.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "insert_memory":
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
