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

范围：`adapter.py` 的**内容**检查（不得有裸 SQL 等）+ **整个包**的导入检查
（只有 `adapter.py` 可以 import evkg）。后者把 D1「evkg 只允许在适配层被 import」
从约定变成可执行约束 —— M1-e 新增的 `dossier.py` 就是靠它保证不绕过适配层。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pydantic import BaseModel

BACKEND = Path(__file__).resolve().parents[1] / "backend"
ADAPTER = BACKEND / "growth_os" / "evidence" / "adapter.py"
PACKAGE = BACKEND / "growth_os"
STORE_DIR = PACKAGE / "store"
"""Growth OS 自有 `g_` 表族存储 —— 唯一允许使用 sqlite3 的目录（M2 起）。"""

TABLE_REF = re.compile(
    r"\b(?:FROM|INTO|JOIN|UPDATE|TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)"
)
SQL_KEYWORDS = {"set", "if", "not", "exists", "select", "values", "where"}
"""静态表名提取时允许出现的非表名标识符（宁可多报：新增关键字必须显式登记）。"""

ALLOWED_EVKG_MODULES = (
    "evkg.config",
    "evkg.domain",
    "evkg.ingest",
    "evkg.store",
    "evkg.attack",
    "evkg.evidence",
    "evkg.model_gateway",
)
"""允许从 evkg 导入的模块。这些都是公共入口所在；`evkg.ingest.connectors` 之类
实现细节文件不在其中。

新增条目前必须先确认它是**稳定的公共入口**，而不是"能用就行"的实现细节：
`evkg.evidence.dossier` 是证据档案的公开 API，故在列；
`evkg.model_gateway` 是决定 D3 指定复用的 `ModelGateway` 类所在模块（M2 起
Agent 推理也用它，且只用**实例级 overrides**），故在列；
`evkg.ingest.connectors` 只是实现文件，故不在列。"""

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


def _code_only(path: Path) -> str:
    """某个文件的可执行代码（无注释、无 docstring），重新生成后用于模式匹配。"""
    return ast.unparse(_strip_docstrings(ast.parse(path.read_text(encoding="utf-8"))))


def _modules_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


@pytest.mark.parametrize(("pattern", "why"), sorted(FORBIDDEN_IN_CODE.items()))
def test_adapter_code_has_no_storage_internals(pattern: str, why: str):
    code = _code_only(ADAPTER)
    hits = re.findall(pattern, code)
    assert not hits, f"{why}；命中 {len(hits)} 处：{sorted(set(hits))[:3]}"


def test_adapter_only_imports_allowed_evkg_modules():
    evkg_modules = [name for name in _modules_of(ADAPTER) if name.startswith("evkg")]
    assert evkg_modules, "适配层应当导入 evkg（它是唯一入口）"
    for name in evkg_modules:
        assert name.startswith(ALLOWED_EVKG_MODULES), f"导入了允许清单之外的 evkg 模块: {name}"


def test_adapter_does_not_import_sqlite_or_orm_libraries():
    modules = set(_modules_of(ADAPTER))
    for banned in ("sqlite3", "sqlalchemy", "peewee", "dataset"):
        assert banned not in modules, f"适配层不应依赖 {banned}"


def test_adapter_does_not_call_low_level_store_methods():
    """``passage_ids`` / ``purge_passages`` 属写入语义，是 evkg 内部；
    适配层只该用 get_source / get_passages / find_sources / save_* 这类公共入口。

    检查口径（2026-10-02 收紧为 `.<name>`）：本意是"不得**调用 store 的低层方法**"，
    即属性访问/调用；裸标识符要放行 —— 领域模型自带 `Claim.passage_ids` 字段、
    适配层的参数也可以叫这个名字。原来的裸子串匹配会误伤这类合法用法
    （M3-e 新增 `create_material_claim` 时实测踩到）。
    """
    code = _code_only(ADAPTER)
    for attribute in ("passage_ids", "purge_passages", "delete_passage", "storage_status"):
        assert f".{attribute}" not in code, f"适配层不应调用 store 的低层方法 {attribute}"


def test_adapter_exposes_only_public_helpers():
    """公开函数名不应以下划线开头（``_tag_source`` 之类应当已被删除）。"""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    private = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_")
    ]
    assert private == [], f"适配层不应再有私有辅助（曾经的 _tag_source 之类）：{private}"


# ---------------------------------------------------------------------------
# 包级：D1「evkg 只允许在适配层被 import」的可执行版本
# ---------------------------------------------------------------------------


def _package_modules() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if path.is_file())


def test_package_modules_were_found():
    """防止路径写错导致下面的检查变成空跑（空集合会让断言全部通过）。"""
    modules = _package_modules()
    assert len(modules) >= 3, f"未找到足够多的包模块，检查可能空跑: {modules}"
    assert any(path.name == "dossier.py" for path in modules), "预期包含 M1-e 新增的 dossier.py"


def test_only_adapter_imports_evkg():
    """D1 的可执行版本：整个 growth_os 包里只有 adapter.py 可以 import evkg。

    否则任何模块都能绕过适配层直接碰 evkg，边界就名存实亡。
    """
    offenders: list[str] = []
    for path in _package_modules():
        if path == ADAPTER:
            continue
        evkg_imports = [name for name in _modules_of(path) if name.startswith("evkg")]
        if evkg_imports:
            offenders.append(f"{path.relative_to(BACKEND)}: {evkg_imports}")
    assert offenders == [], "以下模块绕过了适配层直接 import evkg：" + "；".join(offenders)


def test_evidence_layer_does_not_touch_sqlite_directly():
    """**证据层**任何模块都不得直接依赖 sqlite3 或执行裸 SQL（不止 adapter）。

    M2 起有一处**有意的收窄**：`backend/growth_os/store/` 是 Growth OS 自有的
    `g_` 表族存储，它必须使用 sqlite3 与 SQL —— 那与 evkg 的存储细节无关。
    收窄由三项补偿检查约束（缺一即视为放宽 D1 边界）：

    * 本检查对 `evidence/` 全部模块保持全禁；
    * `test_growth_store_only_touches_g_tables`：自有存储只允许出现 `g_` 前缀表；
    * `test_m2_flow_does_not_write_evkg_tables`：跑完 M2 流程后证据表族必须为空。
    """
    offenders: list[str] = []
    for path in _package_modules():
        if STORE_DIR in path.parents:
            continue  # Growth OS 自有表族存储：见函数文档的收窄说明
        modules = set(_modules_of(path))
        if "sqlite3" in modules:
            offenders.append(f"{path.relative_to(BACKEND)}: import sqlite3")
            continue
        code = _code_only(path)
        for pattern in (r"\.db\s*\.\s*execute\s*\(", r"\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b"):
            if re.search(pattern, code):
                offenders.append(f"{path.relative_to(BACKEND)}: {pattern}")
    assert offenders == [], "证据层出现裸 SQL/sqlite3：" + "；".join(offenders)


def test_growth_store_only_touches_g_tables():
    """自有存储层只允许碰 `g_` 前缀的表（M2-PLAN §3.2 补偿 1）。

    静态提取 SQL 里 FROM/INTO/UPDATE/JOIN/CREATE TABLE 之后的标识符。SQL 关键字
    必须显式列在 `SQL_KEYWORDS` 里 —— 让检查偏向"多报"而不是"漏报"。
    """
    offenders: list[str] = []
    for path in sorted(STORE_DIR.rglob("*.py")):
        code = _code_only(path)
        for match in TABLE_REF.finditer(code):
            table = match.group(1)
            if table.startswith("g_") or table.casefold() in SQL_KEYWORDS:
                continue
            offenders.append(f"{path.relative_to(BACKEND)}: {table}")
    assert offenders == [], "自有存储访问了非 g_ 前缀的表：" + "；".join(offenders)


def test_m2_flow_does_not_write_evkg_tables(tmp_path):
    """跑完一段 M2 流程后，库里除 `g_` 表族外不得出现任何表（补偿 2）。

    这是功能断言，比静态检查更强：它证明 M2 的代码路径**没有**触碰证据层。
    本步的流程覆盖 store + runtime + fake gateway（M2-b/c 会扩展流程内容）。
    """
    import sqlite3

    from growth_os.agent import AgentContext, AgentRuntime, FakeGateway
    from growth_os.store import GrowthStore, capability_id

    class _Echo(BaseModel):
        answer: str

    db = tmp_path / "growth_only.db"
    with GrowthStore(str(db)) as store:
        store.upsert_user("local", "本地用户")
        store.save_goal(
            {
                "id": "goal_m2a",
                "user_id": "local",
                "title": "六个月内达到 AI 应用工程师的项目与求职能力",
                "direction": "AI 应用工程",
                "purpose": "求职",
                "horizon": "六个月",
                "measurable_result": "完成两个可演示项目并通过 20 道面试题",
                "status": "confirmed",
                "source_quote": "就以这个为目标吧",
            }
        )
        store.add_clarification("goal_m2a", 1, "更偏向应用还是算法？", "应用")
        capability = capability_id("goal_m2a", "LLM 基础", "Prompt")
        store.upsert_capability(
            {
                "id": capability,
                "goal_id": "goal_m2a",
                "name": "Prompt",
                "path": "LLM 基础/Prompt",
                "depth": 3,
                "target_level": 3,
                "generated_by_run_id": "run_probe",
            }
        )
        runtime = AgentRuntime(
            store=store,
            gateway=FakeGateway(responses={"probe": {"answer": "ok"}}, provider="fake", model="fake-1"),
            agent="probe",
            id_factory=lambda: "run_probe",
        )
        import asyncio

        asyncio.run(
            runtime.call_model(
                system="s",
                user="u",
                schema=_Echo,
                task="probe",
                context=AgentContext(goal_id="goal_m2a"),
            )
        )

    connection = sqlite3.connect(str(db))
    tables = [
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    ]
    connection.close()
    foreign = [name for name in tables if not name.startswith(("g_", "sqlite_"))]
    assert foreign == [], f"M2 流程写入了非 g_ 表（证据层被触碰）：{foreign}"
    # M2 的 5 张表 + M4-a 的 assessment 契约 2 张表（g_capability_claims / g_assessments）
    # + M4-e 的 g_gaps（缺口派生表）
    assert len([name for name in tables if name.startswith("g_")]) == 8

