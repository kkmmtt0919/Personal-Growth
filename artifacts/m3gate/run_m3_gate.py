"""M3 Gate：把 ROADMAP 完成条件 1–5 与质量门在同一个临时库里端到端重验。

只做验证，不新增产品入口、不调用任何模型 API：
* 条件 1  PDF 与 Markdown 均产出 passages **且可检索**（FTS 重建 + 查询命中）
* 条件 2  代码 ZIP 能抽取技术栈证据（code-kind passages 带 language/行范围 locator）
* 条件 3  公共仓库产出技术栈清单 + ≥3 条材料口径 claim（材料口径，不是能力结论）
* 条件 4  未授权/私有仓库不被读取（无凭据、禁交互、快速失败）；账本与产物无明文密钥
* 条件 5  JD 只进 domain_reference、不产生用户断言
* 质量门  audit_store pass/0；真实库逐表内容哈希与计数对 M3-a 锚点一致

产物：`m3-gate-result.json`；临时库跑完即删。
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "artifacts" / "m3e"))

from evkg.attack.auditor import audit_store
from evkg.index import rebuild_index, search
from growth_os.evidence import adapter
from growth_os.evidence.archive import ingest_archive
from growth_os.evidence.attribution import attribution_of, can_support_user_claim
from growth_os.evidence.github import (
    clone_env,
    ingest_repo,
    materialize_repo,
)
from growth_os.evidence.reference import (
    extract_reference_profile,
    ingest_reference_document,
)
from run_material_claims import build_material_claims

OUT = HERE / "m3-gate-result.json"
REAL_DB = REPO / "data" / "growth.db"
PLACEHOLDER_MARKERS = ("your-", "your_", "xxx", "example", "placeholder", "change-me", "changeme", "redacted", "<")
"""占位符不算密钥：目标是"别把真密钥写进被跟踪的文件"，模板里的占位符正是要鼓励的写法。"""


ANCHORS = REPO / "artifacts" / "m3a" / "evidence-anchors.json"
PDF_FIXTURE = Path(
    r"C:\Users\Lenovo\Desktop\26毕业论文通知\26毕业论文通知\关于做好2027届本科生毕业论文（设计）工作的通知.pdf"
)
JD_FIXTURE = REPO / "artifacts" / "m3d" / "fixtures" / "jd_sample.md"
MARKDOWN_NOTE = "我在练习 Agent 的工具调用与上下文管理，计划学习 Agent Evaluation。"

SECRET_PATTERNS = (
    r"(?i)(api[_-]?key|token|secret)[ 	]*[:=][ 	]*[\"']?[A-Za-z0-9_\-]{20,}",
    r"\bsk-[A-Za-z0-9]{16,}",
    r"\bghp_[A-Za-z0-9]{20,}",
)


def _markdown_condition(store, tmp: Path) -> dict:
    note = tmp / "note.md"
    note.write_text(MARKDOWN_NOTE, encoding="utf-8")
    result = adapter.ingest_document(note, store=store, evidence_type="uploaded_doc", attribution="user_declared")
    return {"source_id": result.source_id, "passages": result.passage_count}


def _pdf_condition(store, tmp: Path) -> dict:
    """PDF 走 V1 状态机（产品侧的适配入口尚未建，见 M3-PLAN §5 的 PDF 支持边界）。"""
    import asyncio

    from evkg.ingest.pipeline import IngestionService

    copy = tmp / "fixture.pdf"
    shutil.copy2(PDF_FIXTURE, copy)
    service = IngestionService(store)
    job = asyncio.run(service.submit(copy, options={"source_kind": "compilation"}))
    job = asyncio.run(service.run(job))
    source = store.get_source_for_ingestion_job(job.id)
    passages = store.get_passages(source_id=source.id) if source else []
    # 取原文里一个 ≥3 字的真实词条作为检索词（从材料本身派生，不预设）
    query = ""
    for item in passages:
        match = re.search(r"[\u4e00-\u9fff]{4}", item.text)
        if match:
            query = match.group(0)
            break
    return {"job_status": job.status.value, "source_id": source.id if source else None,
            "passages": len(passages), "query": query}


def _zip_condition(store, tmp: Path) -> dict:
    archive = tmp / "code.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("README.md", "# 代码包\n\n用于验证 ZIP 技术栈证据。\n")
        bundle.writestr("src/lib.py", "def search(q):\n    return q.strip()\n")
        bundle.writestr("src/Service.java", "public class Service {\n    int x = 1;\n}\n")
    report = ingest_archive(archive, store=store, evidence_type="repo_artifact",
                            attribution="user_declared", workdir=tmp / "unzip")
    languages = set()
    for item in report.ok:
        if item.source_id:
            for passage in store.get_passages(source_id=item.source_id):
                languages.add(passage.locator.get("language"))
    languages.discard(None)
    return {"ok": len(report.ok), "skipped": len(report.skipped), "languages": sorted(languages)}


def _github_condition(store, tmp: Path, repo: str) -> dict:
    report = ingest_repo(repo, store=store, evidence_type="repo_artifact",
                         channel="user_evidence", attribution="user_declared", workdir=tmp / "clones")
    claims = build_material_claims(store, repo)
    return {"files": len(report.ok), "tech_stack_terms": sorted(report.tech_stack), "claims": len(claims)}


def _unauthorized_condition(tmp: Path) -> dict:
    """私有/不存在的仓库必须快速失败（无凭据、无交互），且不产生任何数据。"""
    env = clone_env()
    guard_ok = env.get("GIT_TERMINAL_PROMPT") == "0" and env.get("GIT_ASKPASS") == "echo"
    try:
        materialize_repo("kkmmtt0919/definitely-not-a-real-repo-xyz", None, tmp / "nope")
        failed_fast = False
        error = "克隆竟然成功了？"
    except adapter.EvidenceError as error_obj:
        failed_fast = True
        error = str(error_obj)[:160]
    return {"clone_env_disables_prompts": guard_ok, "private_or_missing_fails_fast": failed_fast, "error": error}


def _reference_condition(store) -> dict:
    result = ingest_reference_document(JD_FIXTURE, store=store)
    metadata = adapter.source_metadata(store, result.source_id)
    profile = extract_reference_profile(store, result.source_id)
    return {
        "channel": metadata.get(adapter.GROWTH_CHANNEL),
        "cannot_support_user_claim": can_support_user_claim(
            attribution_of(metadata), metadata.get(adapter.GROWTH_CHANNEL)
        )
        is False,
        "in_user_evidence": result.source_id in adapter.sources_by_channel(store, "user_evidence"),
        "tech_terms": len(profile["tech_terms"]),
    }


def _tracked_files() -> list[Path]:
    """只扫 **git 跟踪** 的文件 —— 那才是"仓库里有没有明文密钥"的真实边界
    （`data/`、`.env`、`artifacts/**/tmp/`、`*.bak` 都已 gitignore，不属于提交物）。"""
    import subprocess

    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout.splitlines()
    return [REPO / item for item in listed if item.strip()]


def _secret_scan() -> dict:
    hits = []
    scanned = 0
    for path in _tracked_files():
        if not path.is_file() or path.suffix.lower() in {".db", ".png", ".jpg", ".zip", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for pattern in SECRET_PATTERNS:
            for match in re.finditer(pattern, text):
                value = match.group(0)
                if any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
                    continue  # 占位符放行：模板里本就该写占位符
                hits.append({"file": str(path.relative_to(REPO)), "match": value[:24]})
    return {"scanned_files": scanned, "hits": hits[:5], "hit_count": len(hits)}


def _real_db_anchors() -> dict:
    anchor = json.loads(ANCHORS.read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(REAL_DB))
    conn.row_factory = sqlite3.Row

    def digest(table: str) -> str:
        d = hashlib.sha256()
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            d.update(json.dumps(list(row), ensure_ascii=False, sort_keys=True).encode())
        return d.hexdigest()

    tables = tuple(anchor["table_content_sha256"])
    same = all(digest(t) == anchor["table_content_sha256"][t] for t in tables)
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()
    return {"content_hashes_match": same, "counts_match": counts == anchor["table_counts"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="M3 Gate 端到端验证")
    parser.add_argument("repo", nargs="?", default="kkmmtt0919/mytset-rag")
    args = parser.parse_args()
    if not PDF_FIXTURE.is_file():
        raise SystemExit(f"PDF 素材不存在: {PDF_FIXTURE}")

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    db = workdir / "m3-gate.db"
    db.unlink(missing_ok=True)
    store = adapter.open_store(db)

    markdown = _markdown_condition(store, workdir)
    pdf = _pdf_condition(store, workdir)
    code_zip = _zip_condition(store, workdir)
    github = _github_condition(store, workdir, args.repo)
    unauthorized = _unauthorized_condition(workdir)
    reference = _reference_condition(store)

    index = rebuild_index(str(db))
    hits = {
        "markdown": search(str(db), "上下文管理"),
        "pdf": search(str(db), pdf["query"]) if pdf["query"] else {"passages": [], "claims": []},
        "github": search(str(db), "RagService"),
    }
    audit = audit_store(str(db))
    secrets = _secret_scan()
    anchors = _real_db_anchors()

    checks = {
        "cond1_markdown_passages": markdown["passages"] > 0,
        "cond1_pdf_passages": pdf["passages"] > 0,
        "cond1_markdown_searchable": len(hits["markdown"]["passages"]) > 0 or len(hits["markdown"]["claims"]) > 0,
        "cond1_pdf_searchable": len(hits["pdf"]["passages"]) > 0,
        "cond2_zip_code_evidence": code_zip["ok"] >= 2 and {"python", "java"} <= set(code_zip["languages"]),
        "cond3_github_tech_stack": len(github["tech_stack_terms"]) >= 3,
        "cond3_at_least_3_claims": github["claims"] >= 3,
        "cond3_github_searchable": len(hits["github"]["passages"]) > 0 or len(hits["github"]["claims"]) > 0,
        "cond4_no_credentials_used": unauthorized["clone_env_disables_prompts"]
        and unauthorized["private_or_missing_fails_fast"],
        "cond4_no_plaintext_secrets": secrets["hit_count"] == 0,
        "cond5_jd_domain_reference": reference["channel"] == "domain_reference"
        and reference["cannot_support_user_claim"]
        and not reference["in_user_evidence"],
        "quality_audit_pass": audit["status"] == "pass" and audit["total_violations"] == 0,
        "quality_real_db_untouched": anchors["content_hashes_match"] and anchors["counts_match"],
    }
    report = {
        "gate": "M3 · 证据接入（完成条件 1–5 + 质量门）",
        "conditions": {
            "1_pdf_and_markdown_searchable": {"markdown": markdown, "pdf": pdf, "index": index,
                                              "hits": {k: {"passages": len(v["passages"]), "claims": len(v["claims"]), "mode": v.get("mode")} for k, v in hits.items()}},
            "2_code_zip": code_zip,
            "3_public_repo": github,
            "4_unauthorized_and_secrets": {"unauthorized": unauthorized, "secrets": secrets},
            "5_jd_domain_reference": reference,
        },
        "quality": {"audit": {"status": audit["status"], "violations": audit["total_violations"]},
                    "real_db_anchors": anchors},
        "checks": checks,
    }
    report["all_checks_passed"] = all(checks.values())

    store.db.close()
    gc.collect()
    deleted = False
    for _ in range(2):
        try:
            db.unlink(missing_ok=True)
            deleted = True
            break
        except PermissionError:
            gc.collect()
    report["temp_db_deleted"] = deleted
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"checks": checks, "all_checks_passed": report["all_checks_passed"],
                      "temp_db_deleted": deleted}, ensure_ascii=False, indent=2))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
