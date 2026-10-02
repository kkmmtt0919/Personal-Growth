"""M3-b：本地材料 ingestion（MD / TXT / 代码 / ZIP）的测试。

覆盖用户指定的四项：**格式识别、内容提取、来源定位、失败处理**，
外加两条边界验证：

* 归属（`attribution`）与通道（`channel`）在整条链路上保留；
* ZIP 走的是**唯一入口** `adapter.ingest_document`（无旁路）。

越权校验接线与 M1-c 历史主张处理不在本文件范围（留 M3-e）。
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from growth_os.evidence import adapter
from growth_os.evidence.archive import ArchiveLimits, ingest_archive
from growth_os.evidence.attribution import (
    ATTRIBUTION_METADATA_KEY,
    attribution_of,
    can_support_user_claim,
)

MARKDOWN = """# 我的学习笔记

我在练习 Agent 的工具调用，记录一下今天学到的内容。

下一步计划学习 Agent Evaluation。
"""

TEXT = """第一行是标题
第二行是内容

第三段用来验证按空行切分。
"""

CODE = '''def search(query: str) -> list[str]:
    results = []
    for item in query.split():
        if item:
            results.append(item.lower())
    return results
'''

BINARY_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 32


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "local.db")


@pytest.fixture()
def materials(tmp_path: Path) -> dict[str, Path]:
    note = tmp_path / "note.md"
    note.write_text(MARKDOWN, encoding="utf-8")
    plain = tmp_path / "plain.txt"
    plain.write_text(TEXT, encoding="utf-8")
    code = tmp_path / "lib.py"
    code.write_text(CODE, encoding="utf-8")
    return {"note": note, "plain": plain, "code": code}


# ---------------------------------------------------------------------------
# 1. 格式识别（路由）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix", [".md", ".markdown", ".txt", ".text", ".csv", ".json", ".log"]
)
def test_text_formats_route_to_text_path(store, tmp_path, suffix):
    doc = tmp_path / f"sample{suffix}"
    doc.write_text("一段材料。\n\n另一段材料。\n", encoding="utf-8")
    result = adapter.ingest_document(doc, store=store, evidence_type="uploaded_doc")
    assert result.kind == "compilation"  # uploaded_doc → COMPILATION（文本路径）
    assert result.passage_count >= 1


@pytest.mark.parametrize("suffix", [".py", ".java", ".ts", ".sh", ".yaml", ".toml"])
def test_code_formats_route_to_code_path(store, tmp_path, suffix):
    doc = tmp_path / f"sample{suffix}"
    doc.write_text("key: value\n  nested: 1\n", encoding="utf-8")
    result = adapter.ingest_document(doc, store=store, evidence_type="repo_artifact")
    assert result.kind == "code"  # 源码/配置 → CODE（读取路径决定）


def test_extensionless_build_file_is_code(store, tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.12\nRUN pip install uv\n", encoding="utf-8")
    result = adapter.ingest_document(dockerfile, store=store, evidence_type="repo_artifact")
    assert result.kind == "code"


@pytest.mark.parametrize("name", ["paper.pdf", "doc.docx", "sheet.xlsx", "page.html", "shot.png"])
def test_unsupported_formats_are_rejected_with_product_error(store, tmp_path, name):
    doc = tmp_path / name
    doc.write_bytes(b"placeholder")
    with pytest.raises(adapter.EvidenceError):
        adapter.ingest_document(doc, store=store, evidence_type="uploaded_doc")


# ---------------------------------------------------------------------------
# 2. 内容提取
# ---------------------------------------------------------------------------


def test_markdown_content_is_extracted_and_normalized(store, materials):
    result = adapter.ingest_document(materials["note"], store=store, evidence_type="uploaded_doc")
    passages = store.get_passages(source_id=result.source_id)
    joined = " ".join(item.text for item in passages)
    assert "工具调用" in joined and "Agent Evaluation" in joined
    # 文本路径会折叠空白（evkg 既有行为）：段落内的换行变成空格
    assert any("我在练习 Agent 的工具调用" in item.text for item in passages)


def test_code_content_keeps_indentation(store, materials):
    result = adapter.ingest_document(materials["code"], store=store, evidence_type="repo_artifact")
    passages = store.get_passages(source_id=result.source_id)
    body = "\n".join(item.text for item in passages)
    assert "    results = []" in body  # 四个空格缩进被保留
    assert "\n" in body  # 没有被压成一行


# ---------------------------------------------------------------------------
# 3. 来源定位
# ---------------------------------------------------------------------------


def test_text_passages_carry_ordinal_locator(store, materials):
    result = adapter.ingest_document(materials["plain"], store=store, evidence_type="uploaded_doc")
    passages = store.get_passages(source_id=result.source_id)
    assert [item.ordinal for item in passages] == list(range(len(passages)))
    assert all("ordinal" in item.locator for item in passages)
    assert passages[0].text.startswith("第一行是标题")


def test_code_locator_round_trips_to_the_original_file(store, materials):
    """M1-b.5a 的不变量在 M3-b 的链路上仍然成立：locator 必须能切回原文。"""
    result = adapter.ingest_document(materials["code"], store=store, evidence_type="repo_artifact")
    raw_lines = materials["code"].read_text(encoding="utf-8").splitlines()
    for passage in store.get_passages(source_id=result.source_id):
        locator = passage.locator
        assert locator["path"].endswith("lib.py")
        assert locator["language"] == "python"
        start, end = locator["line_start"], locator["line_end"]
        assert "\n".join(raw_lines[start - 1 : end]) == passage.text


# ---------------------------------------------------------------------------
# 4. ZIP：成功、跳过、失败、安全
# ---------------------------------------------------------------------------


def _build_zip(tmp_path: Path, entries: dict[str, bytes], name: str = "materials.zip") -> Path:
    archive = tmp_path / name
    with zipfile.ZipFile(archive, "w") as bundle:
        for entry, payload in entries.items():
            bundle.writestr(entry, payload)
    return archive


def test_zip_ingests_supported_entries_and_skips_the_rest(store, tmp_path):
    archive = _build_zip(
        tmp_path,
        {
            "README.md": MARKDOWN.encode("utf-8"),
            "src/lib.py": CODE.encode("utf-8"),
            "assets/logo.png": BINARY_PNG,
            "docs/": b"",  # 目录条目
            "paper.pdf": b"%PDF-1.4 fake",
        },
    )
    report = ingest_archive(
        archive,
        store=store,
        evidence_type="repo_artifact",
        attribution="user_declared",
        workdir=tmp_path / "extracted",
    )
    by_entry = {item.entry: item for item in report.entries}
    assert by_entry["README.md"].status == "ok"
    assert by_entry["src/lib.py"].status == "ok"
    assert by_entry["src/lib.py"].source_id is not None
    assert by_entry["assets/logo.png"].status == "skipped"
    assert "格式" in by_entry["assets/logo.png"].reason
    assert by_entry["docs/"].status == "skipped"
    assert by_entry["paper.pdf"].status == "skipped"
    assert "B-g2" in by_entry["paper.pdf"].reason  # 富格式明确指向后续步骤
    assert (len(report.ok), len(report.skipped), len(report.failed)) == (2, 3, 0)
    assert report.to_dict()["ok"] == 2


def test_zip_entries_are_located_in_the_archive(store, tmp_path):
    """来源定位：条目要能说清"来自哪个归档的哪个文件"。"""
    archive = _build_zip(tmp_path, {"src/lib.py": CODE.encode("utf-8")})
    report = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=tmp_path / "extracted"
    )
    entry = report.ok[0]
    metadata = adapter.source_metadata(store, entry.source_id)
    assert metadata["growth_archive_path"].endswith("materials.zip")
    assert metadata["growth_archive_entry"] == "src/lib.py"
    source = store.get_source(entry.source_id)
    assert source.title == "materials.zip:src/lib.py"
    extracted = Path(report.extracted_dir) / "src" / "lib.py"
    assert extracted.read_text(encoding="utf-8") == CODE


def test_zip_reingest_reuses_the_same_sources(store, tmp_path):
    """稳定解包目录 → 同一份归档重复入库命中同一批 source_id（幂等）。"""
    archive = _build_zip(tmp_path, {"README.md": MARKDOWN.encode("utf-8")})
    first = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=tmp_path / "extracted"
    )
    second = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=tmp_path / "extracted"
    )
    assert first.ok[0].source_id == second.ok[0].source_id
    assert store.counts()["sources"] == 1


def test_zip_rejects_unsafe_paths_without_writing_outside(store, tmp_path):
    archive = _build_zip(tmp_path, {"../evil.py": b"print('x')\n", "/abs/evil.py": b"print('y')\n"})
    workdir = tmp_path / "extracted"
    report = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=workdir
    )
    assert all(item.status == "skipped" for item in report.entries)
    assert all("路径不安全" in item.reason for item in report.entries)
    assert not (tmp_path / "evil.py").exists()
    assert not workdir.exists() or not any(workdir.rglob("evil.py"))


def test_zip_enforces_entry_size_and_count_limits(store, tmp_path):
    archive = _build_zip(
        tmp_path,
        {"big.py": b"x = 1\n" * 500, "ok.py": b"y = 2\n"},
    )
    limits = ArchiveLimits(max_entry_bytes=100, max_entries=1, max_total_bytes=1000)
    report = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=tmp_path / "ex", limits=limits
    )
    reasons = " ".join(item.reason or "" for item in report.entries)
    assert "单条目过大" in reasons
    assert "条目数超上限" in reasons
    assert report.failed == []


def test_zip_rejects_non_zip_and_oversized_archive(store, tmp_path):
    not_zip = tmp_path / "note.md"
    not_zip.write_text("不是压缩包", encoding="utf-8")
    with pytest.raises(adapter.EvidenceError, match="不是有效的 ZIP"):
        ingest_archive(not_zip, store=store, evidence_type="uploaded_doc")

    archive = _build_zip(tmp_path, {"a.py": b"x = 1\n"})
    with pytest.raises(adapter.EvidenceError, match="归档过大"):
        ingest_archive(
            archive,
            store=store,
            evidence_type="uploaded_doc",
            limits=ArchiveLimits(max_archive_bytes=10),
        )


def test_empty_zip_reports_zero_entries(store, tmp_path):
    archive = _build_zip(tmp_path, {})
    report = ingest_archive(
        archive, store=store, evidence_type="uploaded_doc", workdir=tmp_path / "ex"
    )
    assert (len(report.ok), len(report.skipped), len(report.failed)) == (0, 0, 0)
    assert store.counts()["sources"] == 0


def test_entry_failure_does_not_abort_the_archive(store, tmp_path, monkeypatch):
    """单条目失败要留档且不影响其他条目（不静默丢弃）。"""
    archive = _build_zip(tmp_path, {"good.py": b"x = 1\n", "bad.py": b"y = 2\n"})
    real_ingest = adapter.ingest_document

    def flaky(path, **kwargs):
        if Path(path).name == "bad.py":
            raise adapter.EvidenceError("注入的失败")
        return real_ingest(path, **kwargs)

    monkeypatch.setattr(adapter, "ingest_document", flaky)
    report = ingest_archive(
        archive, store=store, evidence_type="repo_artifact", workdir=tmp_path / "ex"
    )
    assert [item.status for item in report.entries] == ["failed", "ok"]
    assert "注入的失败" in report.failed[0].reason


# ---------------------------------------------------------------------------
# 5. 归属 / 通道贯穿（用户指定的边界验证）
# ---------------------------------------------------------------------------


def test_attribution_and_channel_survive_zip_ingestion(store, tmp_path):
    archive = _build_zip(tmp_path, {"README.md": MARKDOWN.encode("utf-8"), "src/lib.py": CODE.encode("utf-8")})
    report = ingest_archive(
        archive,
        store=store,
        evidence_type="repo_artifact",
        channel="user_evidence",
        attribution="user_declared",
        workdir=tmp_path / "ex",
    )
    for entry in report.ok:
        metadata = adapter.source_metadata(store, entry.source_id)
        assert metadata["growth_evidence_type"] == "repo_artifact"
        assert metadata["growth_channel"] == "user_evidence"
        assert metadata[ATTRIBUTION_METADATA_KEY] == "user_declared"
        assert attribution_of(metadata) == "user_declared"
        assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is True


def test_domain_reference_zip_cannot_support_user_claims(store, tmp_path):
    """同一份归档走 domain_reference 通道 → 标签保留，但不能支撑用户断言。"""
    archive = _build_zip(tmp_path, {"jd.md": MARKDOWN.encode("utf-8")})
    report = ingest_archive(
        archive,
        store=store,
        evidence_type="external_ref",
        channel="domain_reference",
        attribution="user_declared",
        workdir=tmp_path / "ex",
    )
    metadata = adapter.source_metadata(store, report.ok[0].source_id)
    assert metadata["growth_channel"] == "domain_reference"
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is False


def test_reserved_metadata_keys_cannot_be_overridden(store, materials):
    for key in ("growth_evidence_type", "growth_channel", "growth_attribution"):
        with pytest.raises(adapter.EvidenceError, match="保留键"):
            adapter.ingest_document(
                materials["note"],
                store=store,
                evidence_type="uploaded_doc",
                extra_metadata={key: "hacked"},
            )


def test_zip_uses_the_single_entry_without_bypass(store, tmp_path, monkeypatch):
    """无旁路：归档路径必须逐条目调用 `adapter.ingest_document`。"""
    archive = _build_zip(
        tmp_path,
        {"a.py": b"a = 1\n", "b.md": b"# b\n", "skip.png": BINARY_PNG},
    )
    calls: list[dict] = []
    real_ingest = adapter.ingest_document

    def spy(path, **kwargs):
        calls.append({"path": str(path), **kwargs})
        return real_ingest(path, **kwargs)

    monkeypatch.setattr(adapter, "ingest_document", spy)
    ingest_archive(
        archive,
        store=store,
        evidence_type="repo_artifact",
        channel="user_evidence",
        attribution="user_declared",
        workdir=tmp_path / "ex",
    )
    assert len(calls) == 2  # 只有两个可入库条目
    assert all(call["attribution"] == "user_declared" for call in calls)
    assert all(call["channel"] == "user_evidence" for call in calls)
    assert all(call["extra_metadata"]["growth_archive_entry"] for call in calls)
