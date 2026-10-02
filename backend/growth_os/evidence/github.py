"""GitHub **公共仓库**接入（M3-c）：浅克隆 → 逐文件走唯一入口。

设计边界（用户 2026-10-02 锁定的 7 条）：

1. 仅接入 GitHub **公共**仓库；2. **不以 OAuth 为前置**；3. 复用 `adapter.ingest_document` 单入口；
4. attribution / channel 策略**贯穿**该路径；5. 仓库来源信息通过 `extra_metadata` 传递、不绕过保留键；
6. 不做私有仓库授权 / 完整 UI / 能力评估；7. 之后仍要进 M3 Gate（本模块只负责"证据接进来"）。

**为什么用 git 浅克隆而不是 REST API**（实测决定）：

* 无凭据的 GitHub API 配额（60 次/小时/IP）在本机**已耗尽**（`403` 且 `x-ratelimit-remaining: 0`）；
* git 协议无需凭据、不受该配额限制，还能精确拿到某一 ref 的内容与**提交 SHA**（可追溯的关键）；
* 私有仓库/不存在的仓库会在无凭据下**快速失败**（`GIT_TERMINAL_PROMPT=0`，不会卡住等输入）。
* 代价：拿不到只有 API 才提供的元数据（stars/语言统计等）—— 本步不需要。

**身份稳定性**：材料落到 `<workdir>/<owner>-<name>-<ref>/`（ref 默认 `default`），
因此同一仓库同一 ref 重复接入会命中同一批 `source_id`（内容变化由 `content_hash` 表达）。
仓库真实提交 SHA 写进每条来源的 metadata，而不是写进路径 —— 避免每次提交都产生新来源。
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import adapter
from .archive import CODE_FILENAMES, CODE_SUFFIXES, TEXT_SUFFIXES

DEFAULT_WORKDIR = "data/github"
"""克隆缓存目录（`data/` 已 gitignore）。可用 `GROWTH_GITHUB_DIR` 覆盖。"""

SKIP_DIR_PARTS = {
    ".git",
    "node_modules",
    "vendor",
    "third_party",
    "dist",
    "build",
    "target",
    "out",
    "__pycache__",
    ".venv",
    "venv",
    "site-packages",
    ".idea",
    ".vscode",
    "coverage",
}
"""整目录跳过（依赖与产物不是"用户写了什么"的证据）。"""

TECH_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "pipfile"),
    "node": ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"),
    "typescript": ("tsconfig.json",),
    "java": ("pom.xml", "build.gradle", "settings.gradle", "build.gradle.kts"),
    "go": ("go.mod", "go.sum"),
    "rust": ("cargo.toml",),
    "ruby": ("gemfile",),
    "php": ("composer.json",),
    "docker": ("dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"),
    "github_actions": (".github/workflows/",),
    "make": ("makefile",),
    "cmake": ("cmakelists.txt",),
    "jupyter": (".ipynb",),
}
"""文件名/路径 → 技术栈标记（**确定性**规则；命中即记录触发路径作为证据）。"""

TIMEOUT_SECONDS = 180
CLONE_ENV_EXTRA = {
    # 私有仓库或无凭据仓库：立即失败，绝不阻塞等待输入
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "echo",
}


@dataclass(frozen=True)
class RepoLimits:
    max_files: int = 20
    max_file_bytes: int = 200 * 1024
    max_total_bytes: int = 1024 * 1024


@dataclass
class FileResult:
    path: str
    status: str  # ok | skipped | failed
    reason: str | None = None
    source_id: str | None = None
    passage_count: int = 0


@dataclass
class RepoIngestReport:
    repo: str
    ref: str
    sha: str
    workdir: str
    files_total: int = 0
    files_selected: int = 0
    tech_stack: dict[str, list[str]] = field(default_factory=dict)
    entries: list[FileResult] = field(default_factory=list)

    @property
    def ok(self) -> list[FileResult]:
        return [item for item in self.entries if item.status == "ok"]

    @property
    def skipped(self) -> list[FileResult]:
        return [item for item in self.entries if item.status == "skipped"]

    @property
    def failed(self) -> list[FileResult]:
        return [item for item in self.entries if item.status == "failed"]

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "ref": self.ref,
            "sha": self.sha,
            "workdir": self.workdir,
            "files_total": self.files_total,
            "files_selected": self.files_selected,
            "tech_stack": self.tech_stack,
            "ok": len(self.ok),
            "skipped": len(self.skipped),
            "failed": len(self.failed),
            "entries": [item.__dict__ for item in self.entries],
        }


@dataclass(frozen=True)
class MaterializedRepo:
    root: Path
    sha: str
    files: list[str]


def parse_repo_reference(text: str) -> tuple[str, str]:
    """接受 `owner/name` 或 GitHub URL（可带 `.git`；`/tree/<ref>` 的 ref 会被忽略）。"""
    raw = (text or "").strip()
    if not raw:
        raise adapter.EvidenceError("仓库引用为空")
    raw = re.sub(r"^https?://(www\.)?github\.com/", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\.git$", "", raw, flags=re.IGNORECASE)
    raw = raw.split("/tree/")[0].rstrip("/")
    parts = [part for part in raw.split("/") if part]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise adapter.EvidenceError(f"无法解析为 owner/name 形式的仓库: {text!r}")
    return parts[0], parts[1]


def run_command(args: list[str], *, timeout: int = TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """跑一个子进程并把输出解成文本。

    `errors="replace"` 是必须的：中文 Windows 上 git 的报错输出并不总是 UTF-8，
    严格解码会在 reader 线程里抛 `UnicodeDecodeError`（实测踩到），把"仓库不存在"
    这种可解释的失败变成难以诊断的崩溃。
    """
    return subprocess.run(
        args, env=clone_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def clone_env() -> dict[str, str]:
    """git 子进程环境：禁用交互提示（公共仓库无凭据也能工作，私有仓库立即失败）。"""
    return {**os.environ, **CLONE_ENV_EXTRA}


def force_remove_tree(path: Path) -> None:
    """删除目录，先清掉只读位。

    Windows 上 `git clone` 会把 `.git/objects/pack/*.idx` 等设为**只读**，
    `shutil.rmtree` 会以 `PermissionError: [WinError 5]` 失败（实测踩到）。
    删不掉时给出可操作的错误，而不是抛一个裸的 OSError。
    """
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IWRITE)
            except OSError:
                continue
    try:
        shutil.rmtree(path)
    except OSError as error:
        raise adapter.EvidenceError(f"无法清理旧克隆目录（可能被占用）: {path}（{error}）") from error


def materialize_repo(repo: str, ref: str | None, dest: Path, *, timeout: int = TIMEOUT_SECONDS) -> MaterializedRepo:
    """默认材料化实现：`git clone --depth 1`。"仅公共仓库"由"无凭据 + 不交互"保证。"""
    owner, name = parse_repo_reference(repo)
    if dest.exists():
        force_remove_tree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--depth", "1", "--single-branch", "--quiet"]
    if ref:
        command += ["--branch", ref]
    command += [f"https://github.com/{owner}/{name}.git", str(dest)]
    try:
        done = run_command(command, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise adapter.EvidenceError(f"克隆超时（>{timeout}s）: {owner}/{name}") from error
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        hint = "（私有仓库或不存在：本步只支持公共仓库，不接 OAuth）" if "could not read" in (done.stderr or "").lower() else ""
        raise adapter.EvidenceError(f"克隆失败: {owner}/{name} rc={done.returncode} {detail[-1] if detail else ''} {hint}".strip())
    sha = run_command(["git", "-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    files = run_command(["git", "-C", str(dest), "ls-files"]).stdout.splitlines()
    return MaterializedRepo(root=dest, sha=sha, files=[item for item in (line.strip() for line in files) if item])


def is_supported(path: str) -> bool:
    """能否入库：README 一律收；其余按后缀/文件名白名单（与 archive.py 共用同一份表）。"""
    name = Path(path).name.lower()
    if name.startswith("readme"):
        return True
    if name in CODE_FILENAMES:
        return True
    return Path(name).suffix.lower() in (TEXT_SUFFIXES | CODE_SUFFIXES)


def select_files(files: list[str], limits: RepoLimits, *, root: Path) -> tuple[list[str], list[FileResult]]:
    """挑出要入库的文件；被跳过的**逐条给出原因**（不静默丢弃）。"""
    selected: list[str] = []
    skipped: list[FileResult] = []
    total_bytes = 0
    ordered = sorted(files, key=lambda item: (not Path(item).name.lower().startswith("readme"), item))
    for path in ordered:
        if any(part in SKIP_DIR_PARTS for part in Path(path).parts[:-1]):
            skipped.append(FileResult(path, "skipped", "依赖/产物目录"))
            continue
        if not is_supported(path):
            skipped.append(FileResult(path, "skipped", "格式不在文本/代码白名单"))
            continue
        if len(selected) >= limits.max_files:
            skipped.append(FileResult(path, "skipped", f"文件数超上限 {limits.max_files}"))
            continue
        size = (root / path).stat().st_size
        if size > limits.max_file_bytes:
            skipped.append(FileResult(path, "skipped", f"单文件过大（{size} 字节）"))
            continue
        if total_bytes + size > limits.max_total_bytes:
            skipped.append(FileResult(path, "skipped", "总量超上限"))
            continue
        selected.append(path)
        total_bytes += size
    return selected, skipped


def detect_tech_stack(files: list[str]) -> dict[str, list[str]]:
    """确定性技术栈清单：命中即记录触发路径（作为证据）。"""
    found: dict[str, list[str]] = defaultdict(list)
    for path in files:
        lowered = path.lower()
        name = Path(lowered).name
        language = adapter.code_language_for(path)
        if language:
            found[language].append(path)
        for tech, markers in TECH_MARKERS.items():
            if any(marker in lowered if marker.endswith("/") else marker == name for marker in markers):
                found[tech].append(path)
    return {tech: sorted(set(paths)) for tech, paths in sorted(found.items()) if paths}


def ingest_repo(
    repo: str,
    *,
    store,
    evidence_type: str = "repo_artifact",
    channel: str = "user_evidence",
    attribution: str | None = None,
    ref: str | None = None,
    workdir: str | Path | None = None,
    limits: RepoLimits | None = None,
    materializer=None,
) -> RepoIngestReport:
    """浅克隆一个**公共**仓库，把选中的文件逐条送进 `adapter.ingest_document`。

    `materializer` 是测试接缝（离线回归用假实现）；默认走 git 浅克隆。
    """
    owner, name = parse_repo_reference(repo)
    full_name = f"{owner}/{name}"
    active_limits = limits or RepoLimits()
    base = Path(workdir or os.getenv("GROWTH_GITHUB_DIR", DEFAULT_WORKDIR))
    ref_key = re.sub(r"[^A-Za-z0-9_.-]", "-", ref or "default")
    dest = base / f"{owner}-{name}-{ref_key}"

    materialized = (materializer or materialize_repo)(full_name, ref, dest)
    report = RepoIngestReport(
        repo=full_name,
        ref=ref or "default",
        sha=materialized.sha,
        workdir=str(materialized.root),
        files_total=len(materialized.files),
        tech_stack=detect_tech_stack(materialized.files),
    )
    selected, skipped = select_files(materialized.files, active_limits, root=materialized.root)
    report.entries.extend(skipped)
    report.files_selected = len(selected)

    for path in selected:
        file_path = materialized.root / path
        try:
            result = adapter.ingest_document(
                file_path,
                store=store,
                evidence_type=evidence_type,
                channel=channel,
                attribution=attribution,
                title=f"{full_name}:{path}",
                extra_metadata={
                    "growth_github_repo": full_name,
                    "growth_github_ref": ref or "default",
                    "growth_github_sha": materialized.sha,
                    "growth_github_path": path,
                    "growth_github_url": f"https://github.com/{full_name}/blob/{materialized.sha}/{path}",
                },
            )
        except Exception as error:  # noqa: BLE001 - 单文件失败必须可见，不中断整个仓库
            report.entries.append(FileResult(path, "failed", f"{type(error).__name__}: {error}"))
            continue
        report.entries.append(FileResult(path, "ok", None, result.source_id, result.passage_count))
    return report
