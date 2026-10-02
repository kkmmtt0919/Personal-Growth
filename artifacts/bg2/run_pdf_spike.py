"""B-g2：PDF spike（**独立验证**，不是 M3-b 的扩展）。

三项验证（`docs/M3-PLAN.md` v1.0 §5）：

1. 真实**中文** PDF 能否通过 V1 状态机入库（产出 passages）；
2. `audit_store` 是否通过（不变量 0 violation）；
3. locator 能否定位并核对原文 —— **若归一化导致无法逐字还原，必须如实记录**。

纪律：

* 用户文档**只读**（先复制到临时目录），产物只记录**结构性事实**（页数、字符数、计数、
  locator 形状、核对结论），**不把正文写入 artifacts**；临时库用完即删；
* 纯本地（pypdf + 规则），不调用任何模型 API；
* 不新增产品入口：本脚本直接驱动 evkg 的 `IngestionService`（V1 状态机）；
  是否把 V1 接入适配层是后续步骤的事，本次只做验证。
* **两轮**：`as-is` = 当前 evkg 代码（缺陷已在上游 `db2de3a` 修复：`Reader(io.BytesIO(content))`）；
  `diagnostic_equivalent` = 脚本内保留的等价实现（用于交叉印证"上游那一行修复就是关键"，
  并防止将来回归）。两轮应当一致 —— 不一致即是回归信号。

用法：`python artifacts/bg2/run_pdf_spike.py "<pdf 路径>" [--label 说明]`
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "backend"))

from evkg.attack.auditor import audit_store
from evkg.ingest.pipeline import IngestionService
from evkg.store import KnowledgeStore

OUT = HERE / "pdf-spike-result.json"



def _classify(ch: str) -> str:
    if "一" <= ch <= "鿿":
        return "cjk"
    if ch.isspace():
        return "space"
    if ch.isdigit():
        return "digit"
    if ch.isalpha():
        return "latin_letter"
    if ch.isprintable():
        return "punct_or_symbol"
    return "other"


def _char_diff_summary(reference: str, candidate: str) -> dict:
    """归一化文本与"段落拼接"的差异摘要（**只统计类别，不输出任何正文**）。"""
    import difflib
    from collections import Counter

    only_in_normalized: Counter = Counter()
    only_in_passages: Counter = Counter()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, reference, candidate, autojunk=False
    ).get_opcodes():
        if tag in ("delete", "replace"):
            only_in_normalized.update(_classify(ch) for ch in reference[i1:i2])
        if tag in ("insert", "replace"):
            only_in_passages.update(_classify(ch) for ch in candidate[j1:j2])
    return {
        "normalized_chars": len(reference),
        "passages_chars": len(candidate),
        "missing_from_passages_by_class": dict(only_in_normalized),
        "extra_in_passages_by_class": dict(only_in_passages),
    }

def _pdf_reference(path: Path) -> dict:
    """用 pypdf 直接抽取作为参照（与 V1 的 PdfReader 同一库 —— 说明见结论）。"""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return {
        "pages": len(pages),
        "chars_total": len(text),
        "cjk_chars": cjk,
        "cjk_ratio": round(cjk / max(1, len(text)), 3),
        "empty_pages": sum(1 for item in pages if not item.strip()),
    }


class _PdfReaderFixed:
    """诊断用：与 evkg `PdfReader` 等价，只把 `Reader(content)` 改成 `Reader(io.BytesIO(content))`。"""

    processor_version = "1"

    def supports(self, media_type: str, name: str) -> bool:
        return media_type == "application/pdf" or Path(name).suffix.lower() == ".pdf"

    async def read(self, content: bytes, *, name: str, media_type: str, asset_id: str):
        import io

        from evkg.domain import RecognitionResult, RecognitionSpan
        from pypdf import PdfReader as Reader

        pages = [page.extract_text() or "" for page in Reader(io.BytesIO(content)).pages]
        spans = [
            RecognitionSpan(text=page, page=index + 1, confidence=0.9, source="pdf")
            for index, page in enumerate(pages)
        ]
        text = "\n\n".join(pages)
        return RecognitionResult(
            id=f"rec_{asset_id}",
            raw_asset_id=asset_id,
            text=text,
            spans=spans,
            language="und",
            processor="pdf",
            processor_version=self.processor_version,
            confidence=0.9,
            needs_review=not bool(text.strip()),
        )


def _fixed_readers() -> list:
    from evkg.ingest.providers import (
        CodeReader,
        HtmlReader,
        OfficeReader,
        PlainTextReader,
        UrlReader,
    )

    return [UrlReader(), HtmlReader(), OfficeReader(), _PdfReaderFixed(), CodeReader(), PlainTextReader()]


async def _drive_v1(pdf: Path, db: Path, *, fixed: bool = False) -> dict:
    store = KnowledgeStore(str(db))
    service = IngestionService(store, readers=_fixed_readers()) if fixed else IngestionService(store)
    job = await service.submit(pdf, options={"source_kind": "compilation"})
    raised = None
    try:
        job = await service.run(job)
    except Exception as error:  # noqa: BLE001 - 失败会被 V1 记录在库里，这里只做容错以便读取记录
        raised = f"{type(error).__name__}: {error}"
        job = store.get_ingestion_job(job.id)

    source = store.get_source_for_ingestion_job(job.id)
    passages = store.get_passages(source_id=source.id) if source else []
    locator_shapes = Counter(tuple(sorted(item.locator)) for item in passages)

    normalized_rows = store.db.execute(
        "SELECT payload FROM normalized_documents WHERE job_id=?", (job.id,)
    ).fetchall()
    normalized = json.loads(normalized_rows[0][0]) if normalized_rows else {}
    normalized_text = normalized.get("text", "")

    recognition_rows = store.db.execute(
        "SELECT payload FROM recognition_results WHERE job_id=?", (job.id,)
    ).fetchall()
    recognition = json.loads(recognition_rows[0][0]) if recognition_rows else {}
    spans = recognition.get("spans", [])

    passages_in_normalized = sum(1 for item in passages if item.text in normalized_text)
    covered = sum(len(item.text) for item in passages)
    compact_normalized = re.sub(r"\s+", "", normalized_text)
    compact_passages = re.sub(r"\s+", "", "".join(item.text for item in passages))
    space_joined = " ".join(item.text for item in passages)
    diff = _char_diff_summary(compact_normalized, compact_passages)
    questions = store.get_questions(job.id)

    errors = [
        json.loads(row[0])
        for row in store.db.execute("SELECT payload FROM processing_errors WHERE job_id=?", (job.id,))
    ]
    result = {
        "job": {
            "id": job.id,
            "status": job.status.value,
            "error": job.error,
            "raised_to_caller": raised,
            "recorded_processing_errors": errors,
        },
        "source": {
            "id": source.id if source else None,
            "kind": source.kind.value if source else None,
            "metadata_keys": sorted((source.metadata or {}).keys()) if source else [],
            "content_hash": (source.content_hash or "")[:12] if source else None,
        },
        "passages": {
            "count": len(passages),
            "locator_shapes": {"+".join(shape): count for shape, count in locator_shapes.items()},
            "all_in_normalized_text": passages_in_normalized == len(passages),
            "coverage_of_normalized": round(covered / max(1, len(normalized_text)), 3),
            "max_chars": max((len(item.text) for item in passages), default=0),
            "compact_equals_normalized": compact_passages == compact_normalized,
            "space_join_equals_normalized": space_joined == normalized_text.strip(),
            "char_diff_vs_normalized": diff,
        },
        "normalized": {"chars": len(normalized_text), "keys": sorted(normalized.keys())},
        "recognition": {
            "spans": len(spans),
            "span_keys": sorted(spans[0].keys()) if spans else [],
            "pages_with_text": sum(1 for span in spans if (span.get("text") or "").strip()),
        },
        "clarification": {"questions": len(questions), "blocking": sum(1 for q in questions if q.blocking)},
    }
    store.db.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="B-g2 PDF spike（只读验证）")
    parser.add_argument("pdf")
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    source_pdf = Path(args.pdf)
    if not source_pdf.is_file():
        raise SystemExit(f"PDF 不存在: {source_pdf}")

    workdir = HERE / "tmp"
    workdir.mkdir(parents=True, exist_ok=True)
    local_copy = workdir / "fixture.pdf"
    shutil.copy2(source_pdf, local_copy)  # 只读原件：复制后再读
    db_a = workdir / "spike-a.db"
    db_b = workdir / "spike-b.db"
    for path in (db_a, db_b):
        path.unlink(missing_ok=True)

    report = {
        "spike": "B-g2 PDF（V1 状态机）",
        "label": args.label,
        "source_file": str(source_pdf),
        "file_size": source_pdf.stat().st_size,
        "is_zip_disguised": zipfile.is_zipfile(local_copy),
        "reference_pypdf": _pdf_reference(local_copy),
    }
    report["run_as_is"] = asyncio.run(_drive_v1(local_copy, db_a))
    report["run_diagnostic_equivalent"] = asyncio.run(_drive_v1(local_copy, db_b, fixed=True))
    a, b = report["run_as_is"], report["run_diagnostic_equivalent"]
    report["rounds_agree"] = (
        a["job"]["status"] == b["job"]["status"]
        and a["passages"]["count"] == b["passages"]["count"]
        and a["source"]["id"] == b["source"]["id"]
    )

    audit = audit_store(str(db_b))
    report["audit"] = {
        "status": audit["status"],
        "total_violations": audit["total_violations"],
        "checks_all_zero": all(item["violations"] == 0 for item in audit["checks"].values()),
        "counts": audit["counts"],
    }

    # 第三项：locator 可核对性判定（如实记录，不美化）
    locators = report["run_as_is"]["passages"]["locator_shapes"]
    page_level = any("page" in shape for shape in locators)
    report["defect_history"] = {
        "where": "evkg/src/evkg/ingest/providers.py: PdfReader.read",
        "what": "把 bytes 直接传给 pypdf.PdfReader；pypdf 需要流/路径",
        "error": "AttributeError: 'bytes' object has no attribute 'seek'",
        "why_never_noticed": "evkg 测试对 PDF 零覆盖；同文件 OfficeReader 反而正确地用了 io.BytesIO",
        "fix": "Reader(content) → Reader(io.BytesIO(content))（1 行）",
        "status": "fixed_upstream @ db2de3a（并补 tests/test_pdf_reader.py 6 项真实读取测试）",
        "scope_discipline": "只改这一行 + 补测试；未动 locator 设计 / V1 状态机 / completeness / audit_store",
    }
    report["open_issue_separate"] = {
        "id": "page-level locator",
        "summary": "passage locator 仍只有 ordinal；识别 span 带 page/bbox 但未写入 locator。"
                   "这是独立上游项（清单第 14 项），不因 bytes 缺陷修复而被视为通过。",
    }
    report["locator_verdict"] = {
        "locator_keys": locators,
        "page_level_locator": page_level,
        "verbatim_against_raw_pdf": False,
        "reason": (
            "passages 由 `split_passages` 生成，locator 只有 ordinal（归一化文本内的序号）；"
            "识别阶段虽然拿到了页码 span，但没有写进 locator，因此**无法自动定位回 PDF 页/坐标**。"
            "文本还经过 normalize_document（空白折叠、重排行），因此对原始 PDF 也不保证逐字还原。"
        ),
        "mitigations": [
            "库内保留 raw_asset（原始字节）与 recognition spans（含页码）与 normalized_document，可人工核对",
            "passage 文本是归一化文本的分区（可对回归一化文本逐字核对）",
        ],
    }
    # 清理：evkg 的 audit_store/部分读取路径不关连接（M1-g 记录过），Windows 上可能仍被占用。
    # 删除失败要如实记录，而不是假装清理完成。
    gc.collect()
    deleted = {}
    for path in (db_a, db_b):
        try:
            path.unlink(missing_ok=True)
            deleted[path.name] = True
        except PermissionError:
            deleted[path.name] = False
    report["temp_db_deleted"] = deleted
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if all(deleted.values()):
        shutil.rmtree(workdir, ignore_errors=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
