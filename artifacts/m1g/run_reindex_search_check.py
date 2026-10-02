"""M1 完成条件的最后两项：`init` 与 `reindex` 的实际输出。

ROADMAP M1 完成条件第 1 条要求跑通 `init → ingest → extract → attack → reindex → dossier`。
R3 覆盖实测显示 `init`（cli 0%）与 `reindex`（index/search 0%）从未被跑过。本脚本补齐：

* `evkg init` CLI → 临时空库上产出 schema 与空计数；
* `rebuild_index` → 模式与计数；
* `search` 对真实语料的命中（只记 id/计数，不复制原文）；
* 索引后 `audit_store` 仍 pass（索引不得破坏不变量）；
* 重复重建幂等；
* 真实库哈希前后一致（不触碰）。
"""

from __future__ import annotations

import gc
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from evkg.attack.auditor import audit_store
from evkg.index import rebuild_index, search
from evkg.store import KnowledgeStore

HERE = Path(__file__).resolve().parent
TMP = HERE / "tmp"
OUT = HERE / "reindex_search_evidence.json"
REAL_DB = Path("D:/projects/Personal Growth/data/growth.db")

QUERIES = ["RAG", "ChromaDB", "Dubbo", "检索服务", "计划学习"]


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def consistent_copy(src: Path, dst: Path) -> None:
    dst.unlink(missing_ok=True)
    source = sqlite3.connect(str(src))
    target = sqlite3.connect(str(dst))
    source.backup(target)
    target.close()
    source.close()


def main() -> dict:
    TMP.mkdir(parents=True, exist_ok=True)
    before = sha256_file(REAL_DB)

    # --- init：CLI 在临时空库上建 schema ---
    init_db = TMP / "init_probe.db"
    init_db.unlink(missing_ok=True)
    proc = subprocess.run(
        [sys.executable, "-m", "evkg", "--db", str(init_db), "init"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(TMP),
        check=False,
    )
    init_result = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else None
    init_tables = 0
    if init_db.is_file():
        conn = sqlite3.connect(str(init_db))
        init_tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        conn.close()

    copy = TMP / "reindex_copy.db"
    consistent_copy(REAL_DB, copy)

    first = rebuild_index(str(copy))
    second = rebuild_index(str(copy))
    store = KnowledgeStore(str(copy))
    fts_rows = store.db.execute("SELECT COUNT(*) FROM passages_fts").fetchone()[0]
    fts_claims = store.db.execute("SELECT COUNT(*) FROM claims_fts").fetchone()[0]
    audit = audit_store(str(copy))
    store.db.close()

    hits = []
    for query in QUERIES:
        result = search(str(copy), query, limit=5)
        hits.append(
            {
                "query": query,
                "mode": result["mode"],
                "expanded_surfaces": result["expanded_surfaces"],
                "passage_hits": len(result["passages"]),
                "passage_ids": [item.get("passage_id") for item in result["passages"][:5]],
                "claim_hits": len(result["claims"]),
                "claim_ids": [item.get("id") for item in result["claims"][:5]],
                "entity_hits": len(result["entities"]),
            }
        )
    store = KnowledgeStore(str(copy))
    audit_after = audit_store(str(copy))
    store.db.close()

    # evkg 的 KnowledgeStore 没有 close()/上下文管理器：audit_store/search 内部打开的
    # 连接只能靠 GC 释放，Windows 上会锁住文件（本脚本首次运行即踩到 WinError 32）。
    gc.collect()
    try:
        copy.unlink(missing_ok=True)
        copy_released = True
    except PermissionError:
        copy_released = False
    after = sha256_file(REAL_DB)
    report = {
        "real_db": str(REAL_DB),
        "init_cli": {
            "exit_code": proc.returncode,
            "stdout": init_result,
            "schema_tables_created": init_tables,
            "stderr": proc.stderr.strip()[:300],
        },
        "rebuild_index_first": first,
        "rebuild_index_second": second,
        "idempotent": first == second,
        "fts_passage_rows": fts_rows,
        "fts_claim_rows": fts_claims,
        "audit_after_index": {"status": audit["status"], "violations": audit["total_violations"]},
        "audit_after_index_pass2": {"status": audit_after["status"], "violations": audit_after["total_violations"]},
        "queries": hits,
        "queries_with_hits": sum(1 for item in hits if item["passage_hits"] or item["claim_hits"]),
        "query_mode_all_fts": all(item["mode"] == "fts" for item in hits),
        "copy_deleted_after_run": copy_released,
        "real_db_sha256_before": before,
        "real_db_sha256_after": after,
        "real_db_untouched": before == after,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
