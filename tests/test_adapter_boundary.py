"""b.5d：适配层边界检查 —— 防止 Growth OS 重新长回 evkg 的存储细节。

用户指定的验收目标：

> 证明 Growth OS 不再需要知道 evkg 内部存储细节。

这类约束靠"写的时候小心"是守不住的（M1-b.5c 期间我自己就复用了
``INSERT OR IGNORE`` 的 helper，导致"报 updated 但库里是旧值"）。所以把它做成
**可执行的检查**：适配层源码里一旦重新出现裸 SQL、直接访问连接、或导入 evkg 的
内部模块，这里就红。

检查是**静态**的（读源码 + AST），因此不需要数据库、也不需要模型。

实现要点：只检查**可执行代码**。注释与文档字符串里出现 `sqlite3`、`SELECT`
这类词是允许的 —— 那些地方正是用来解释"为什么不这么做"的。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ADAPTER = Path(__file__).resolve().parents[1] / "backend" / "growth_os" / "evidence" / "adapter.py"

ALLOWED_EVKG_MODULES = (
    "evkg.config",
    "evkg.domain",
    "evkg.ingest",
    "evkg.store",
    "evkg.attack",
)
"""允许从 evkg 导入的模块。这些都是公共入口所在；`evkg.ingest.connectors` 之类
实现细节文件不在其中。"""

FORBIDDEN_IN_CODE = {
    r"\bsqlite3\b": "不能直接依赖 sqlite3",
    r"\.db\s*\.\s*execute\s*\(": "不能直接执行 SQL（应走 KnowledgeStore 的公共方法）",
    r"\.db\s*\.\s*commit\s*\(": "不能直接提交事务",
    r"\bjson_set\s*\(": "不能直接改 payload（应通过 ingest 的 metadata 参数）",
    r"\bjson_extract\s*\(": "不能直接查 payload（应用 find_sources）",
    r"\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b": "不能内联 SQL 语句",
    r"\._\w+": "不应访问下划线开头的内部成员",
}


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """移除所有 docstring，便于只对可执行代码做模式检查。"""
    documentable = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if isinstance(node, documentable):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
    return tree


def _code_only() -> str:
    """适配层的可执行代码（无注释、无 docstring），重新生成后用于模式匹配。"""
    return ast.unparse(_strip_docstrings(ast.parse(ADAPTER.read_text(encoding="utf-8"))))


@pytest.mark.parametrize(("pattern", "why"), sorted(FORBIDDEN_IN_CODE.items()))
def test_adapter_code_has_no_storage_internals(pattern: str, why: str):
    code = _code_only()
    hits = re.findall(pattern, code)
    assert not hits, f"{why}；命中 {len(hits)} 处：{sorted(set(hits))[:3]}"


def test_adapter_only_imports_allowed_evkg_modules():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)

    evkg_modules = [name for name in modules if name.startswith("evkg")]
    assert evkg_modules, "适配层应当导入 evkg（它是唯一入口）"
    for name in evkg_modules:
        assert name.startswith(ALLOWED_EVKG_MODULES), f"导入了允许清单之外的 evkg 模块: {name}"


def test_adapter_does_not_import_sqlite_or_orm_libraries():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    for banned in ("sqlite3", "sqlalchemy", "peewee", "dataset"):
        assert banned not in modules, f"适配层不应依赖 {banned}"


def test_adapter_does_not_call_low_level_store_methods():
    """``passage_ids`` / ``purge_passages`` 属写入语义，是 evkg 内部；
    适配层只该用 get_source / get_passages / find_sources / save_* 这类公共入口。"""
    code = _code_only()
    for attribute in ("passage_ids", "purge_passages", "delete_passage", "storage_status"):
        assert attribute not in code, f"适配层不应调用 store 的低层方法 {attribute}"


def test_adapter_exposes_only_public_helpers():
    """公开函数名不应以下划线开头（``_tag_source`` 之类应当已被删除）。"""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    private = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_")
    ]
    assert private == [], f"适配层不应再有私有辅助（曾经的 _tag_source 之类）：{private}"
