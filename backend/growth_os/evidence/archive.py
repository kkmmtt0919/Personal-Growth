"""本地材料的容器级封装（M3-b）：ZIP → 逐条目走**唯一入口**。

职责边界（用户 2026-10-02 指定，见 `docs/M3-PLAN.md` §5.1）：

* 本模块**不 import evkg**，也不解析/切分任何内容 —— 每个可入库的条目都交给
  `adapter.ingest_document`（唯一入口），因此 **M3-a 的归属（`attribution`）
  与通道（`channel`）策略不可能被绕过**；
* 归档处理只做三件事：**安全解包**（防路径穿越、防 zip bomb）、**逐条目标注来源**
  （归档路径 + 条目名写进 source metadata）、**逐条目汇总结果**（成功 / 跳过 / 失败
  都要可见，不静默丢弃）；
* 越权校验的接线与历史主张处理**不在本模块**（留 M3-e）。

一个刻意选择：条目先解包到**稳定目录**（`<archive stem>-<内容哈希前 8 位>`），
这样同一份归档重复入库会命中同一批 `source_id`（M1-b.5c 的逻辑身份语义），
而不是因为临时目录每次都不同而制造重复来源。代价：归档改名等同新来源
（与"路径即身份"的既有约定一致），且旧目录不自动清理（见"已知限制"）。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import adapter

DEFAULT_EXTRACT_DIR = "data/extracted"
"""解包缓存目录（`data/` 已被 gitignore）。可用 `GROWTH_EXTRACT_DIR` 覆盖。"""

MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ENTRIES = 200
MAX_ENTRY_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
"""默认上限：宁可跳过并报告，也不让一个恶意/超大归档把库和磁盘拖垮。"""

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".text", ".csv", ".json", ".log"}
CODE_SUFFIXES = {
    ".java", ".kt", ".scala", ".groovy", ".py", ".rb", ".php", ".pl", ".lua",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".go", ".rs",
    ".swift", ".m", ".cs", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".sh",
    ".bash", ".zsh", ".ps1", ".bat", ".sql", ".r", ".jl", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".properties", ".gradle", ".css", ".scss", ".less",
}
CODE_FILENAMES = {
    "dockerfile", "makefile", "jenkinsfile", "rakefile", "gemfile", "procfile",
    "vagrantfile", "cmakelists.txt", ".editorconfig", ".env.example", ".env.sample",
}
"""与 evkg 的路由表保持一致（此处只用于**预筛与报告**，真正的路由仍由
`adapter.ingest_document` → evkg `ingest_path` 决定；两边不一致时以 evkg 为准）。"""


@dataclass(frozen=True)
class ArchiveLimits:
    max_archive_bytes: int = MAX_ARCHIVE_BYTES
    max_entries: int = MAX_ENTRIES
    max_entry_bytes: int = MAX_ENTRY_BYTES
    max_total_bytes: int = MAX_TOTAL_BYTES


@dataclass
class EntryResult:
    entry: str
    status: str  # ok | skipped | failed
    reason: str | None = None
    source_id: str | None = None
    passage_count: int = 0


@dataclass
class ArchiveReport:
    archive: str
    extracted_dir: str
    entries: list[EntryResult] = field(default_factory=list)

    @property
    def ok(self) -> list[EntryResult]:
        return [item for item in self.entries if item.status == "ok"]

    @property
    def skipped(self) -> list[EntryResult]:
        return [item for item in self.entries if item.status == "skipped"]

    @property
    def failed(self) -> list[EntryResult]:
        return [item for item in self.entries if item.status == "failed"]

    def to_dict(self) -> dict:
        return {
            "archive": self.archive,
            "extracted_dir": self.extracted_dir,
            "ok": len(self.ok),
            "skipped": len(self.skipped),
            "failed": len(self.failed),
            "entries": [item.__dict__ for item in self.entries],
        }


def _looks_ingestible(entry: str) -> bool:
    """粗筛：只用于"要不要解包尝试"，不是路由判定。"""
    name = Path(entry).name.lower()
    if name in CODE_FILENAMES:
        return True
    return Path(name).suffix.lower() in (TEXT_SUFFIXES | CODE_SUFFIXES)


def _safe_relative(entry: str) -> str | None:
    """把 zip 条目名规整成安全的相对路径；不安全返回 None。"""
    normalized = entry.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized.split("/")[0]:
        return None  # 绝对路径 / 盘符
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        return None  # 目录穿越
    return "/".join(parts)


def _stable_extract_dir(archive: Path, workdir: Path) -> Path:
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:8]
    return workdir / f"{archive.stem}-{digest}"


def ingest_archive(
    path: str | Path,
    *,
    store,
    evidence_type: str,
    channel: str = "user_evidence",
    attribution: str | None = None,
    workdir: str | Path | None = None,
    limits: ArchiveLimits | None = None,
) -> ArchiveReport:
    """把一个 ZIP 归档里的可入库条目逐条送进 `adapter.ingest_document`。

    每个条目都会在报告里留下一条结果（ok / skipped / failed），**包括跳过的原因**。
    单个条目失败不影响其他条目，但整份报告的 `failed` 必须被调用方看见。
    """
    archive = Path(path)
    if not archive.is_file():
        raise adapter.EvidenceError(f"归档不存在: {archive}")
    if not zipfile.is_zipfile(archive):
        raise adapter.EvidenceError(f"不是有效的 ZIP 归档: {archive}")

    active_limits = limits or ArchiveLimits()
    size = archive.stat().st_size
    if size > active_limits.max_archive_bytes:
        raise adapter.EvidenceError(
            f"归档过大（{size} 字节 > 上限 {active_limits.max_archive_bytes}）: {archive}"
        )

    root_dir = Path(workdir or os.getenv("GROWTH_EXTRACT_DIR", DEFAULT_EXTRACT_DIR))
    extract_dir = _stable_extract_dir(archive, root_dir)
    report = ArchiveReport(archive=str(archive), extracted_dir=str(extract_dir))

    total_bytes = 0
    with zipfile.ZipFile(archive) as bundle:
        names = sorted(bundle.namelist())
        if len(names) > active_limits.max_entries:
            for entry in names[active_limits.max_entries :]:
                report.entries.append(
                    EntryResult(entry, "skipped", f"条目数超上限 {active_limits.max_entries}")
                )
            names = names[: active_limits.max_entries]

        for entry in names:
            if entry.endswith("/"):
                report.entries.append(EntryResult(entry, "skipped", "目录条目"))
                continue
            relative = _safe_relative(entry)
            if relative is None:
                report.entries.append(EntryResult(entry, "skipped", "路径不安全（绝对路径或包含 ..）"))
                continue
            if not _looks_ingestible(relative):
                report.entries.append(
                    EntryResult(entry, "skipped", "格式不在本地文本/代码范围（PDF 等富格式属 B-g2/V1 状态机）")
                )
                continue
            info = bundle.getinfo(entry)
            if info.file_size > active_limits.max_entry_bytes:
                report.entries.append(
                    EntryResult(entry, "skipped", f"单条目过大（{info.file_size} 字节）")
                )
                continue
            if total_bytes + info.file_size > active_limits.max_total_bytes:
                report.entries.append(EntryResult(entry, "skipped", "解包总量超上限"))
                continue

            target = (extract_dir / relative).resolve()
            if not str(target).startswith(str(extract_dir.resolve()) + os.sep):
                report.entries.append(EntryResult(entry, "skipped", "解包目标越出工作目录"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(entry) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            total_bytes += info.file_size

            try:
                result = adapter.ingest_document(
                    target,
                    store=store,
                    evidence_type=evidence_type,
                    channel=channel,
                    attribution=attribution,
                    title=f"{archive.name}:{relative}",
                    extra_metadata={
                        "growth_archive_path": str(archive),
                        "growth_archive_entry": relative,
                    },
                )
            except Exception as error:  # noqa: BLE001 - 逐条目失败必须可见，不中断整份归档
                report.entries.append(
                    EntryResult(entry, "failed", f"{type(error).__name__}: {error}")
                )
                continue
            report.entries.append(
                EntryResult(entry, "ok", None, result.source_id, result.passage_count)
            )
    return report
