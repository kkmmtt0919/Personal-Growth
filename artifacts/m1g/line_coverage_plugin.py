"""R3 用：不安装任何新依赖的行级覆盖插件（sys.settrace，只读，跑完写 JSON）。

用法：
    PYTHONPATH=artifacts/m1g python -m pytest -p line_coverage_plugin

统计口径：AST 中带行号的语句节点（含 docstring / def / class 行），偏保守地
高估分母；被 settrace 捕获到的行计为已执行。仅用于回答"哪些路径根本没跑到"。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path("D:/projects/Personal Growth")
EVKG_SRC = Path("D:/projects/evkg/src")
OUT = ROOT / "artifacts" / "m1g" / "r3_coverage.json"

_covered: dict[str, set[int]] = {}
_watched: dict[str, str] = {}


def _statement_lines(path: Path) -> set[int]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    return {node.lineno for node in ast.walk(tree) if isinstance(node, ast.stmt) and node.lineno}


def _tracer(frame, event, arg):
    if event == "call":
        filename = frame.f_code.co_filename
        key = _watched.get(filename)
        if key is not None:
            _covered.setdefault(key, set()).add(frame.f_lineno)
        return _tracer
    if event == "line":
        filename = frame.f_code.co_filename
        key = _watched.get(filename)
        if key is not None:
            _covered.setdefault(key, set()).add(frame.f_lineno)
    return _tracer


def pytest_configure(config):
    targets = list((ROOT / "backend" / "growth_os").rglob("*.py")) + list(EVKG_SRC.rglob("*.py"))
    for path in targets:
        key = str(path.resolve())
        _watched[str(path.resolve())] = key
        _watched[str(path)] = key
        _covered.setdefault(key, set())
    sys.settrace(_tracer)


def pytest_unconfigure(config):
    sys.settrace(None)
    rows = []
    for key, covered in _covered.items():
        path = Path(key)
        total = _statement_lines(path)
        if not total:
            continue
        hit = len(total & covered)
        rows.append(
            {
                "file": str(path).replace(str(EVKG_SRC), "evkg/src").replace(str(ROOT), "").lstrip("\\/"),
                "statements": len(total),
                "covered": hit,
                "percent": round(100.0 * hit / len(total), 1),
                "uncovered_lines": sorted(total - covered) if "backend" in key else None,
            }
        )
    rows.sort(key=lambda item: (item["percent"], item["file"]))
    report = {"note": "AST 语句行近似口径；pyproject 的 addopts 会影响收集范围", "files": rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[R3 coverage] wrote", OUT)
    for item in rows:
        print(f"  {item['percent']:6.1f}%  {item['covered']:4d}/{item['statements']:4d}  {item['file']}")
