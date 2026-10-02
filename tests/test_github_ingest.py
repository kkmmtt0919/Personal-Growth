"""M3-c：GitHub 公共仓库接入的离线测试（假材料化，不触网）。

覆盖：仓库引用解析、文件选择与限额（跳过必须有原因）、技术栈清单（确定性）、
**单入口无旁路**（spy 断言）、归属/通道贯穿、单文件失败不中断、同 ref 重复接入幂等、
克隆失败的产品错误、以及"禁用交互提示"的克隆环境（公共仓库无凭据可用、私有仓库快速失败）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from growth_os.evidence import adapter, github
from growth_os.evidence.attribution import (
    ATTRIBUTION_METADATA_KEY,
    attribution_of,
    can_support_user_claim,
)
from growth_os.evidence.github import RepoLimits, ingest_repo, parse_repo_reference

TREE = {
    "README.md": "# MYtest\n\n一个用于验证的示例项目，包含 RAG 检索与测试用例生成。\n",
    "requirements.txt": "fastapi>=0.115\nchromadb>=0.4\n",
    "src/service.py": "def search(q):\n    return q.strip()\n",
    "src/ui.ts": "export const run = () => 1;\n",
    "Dockerfile": "FROM python:3.12\n",
    "docs/guide.md": "# 指南\n\n这里是使用说明。\n",
    "node_modules/dep/index.js": "module.exports = 1;\n",
    "assets/logo.png": "\x89PNG-binary",
    "big.py": "x = 1\n" * 5000,
}


def _fake_materializer(sha: str = "c417a096927dbf1f36b1ae1e39fb61b356732d87"):
    """把预置文件树写到 dest，返回 (root, sha, files)。"""

    def materialize(repo: str, ref: str | None, dest: Path) -> github.MaterializedRepo:
        if dest.exists():
            import shutil

            shutil.rmtree(dest)
        for relative, content in TREE.items():
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return github.MaterializedRepo(root=dest, sha=sha, files=sorted(TREE))

    return materialize


@pytest.fixture()
def store(tmp_path: Path):
    return adapter.open_store(tmp_path / "github.db")


# ---------------------------------------------------------------------------
# 1. 仓库引用解析
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("kkmmtt0919/mytset-rag", ("kkmmtt0919", "mytset-rag")),
        ("https://github.com/kkmmtt0919/mytset-rag", ("kkmmtt0919", "mytset-rag")),
        ("https://github.com/kkmmtt0919/mytset-rag.git", ("kkmmtt0919", "mytset-rag")),
        ("https://github.com/psf/requests/tree/main", ("psf", "requests")),
        ("  psf/requests  ", ("psf", "requests")),
    ],
)
def test_parse_repo_reference_accepts_common_forms(text, expected):
    assert parse_repo_reference(text) == expected


@pytest.mark.parametrize("text", ["", "just-a-name", "a/b/c", "https://github.com/", "own er/na me"])
def test_parse_repo_reference_rejects_bad_input(text):
    with pytest.raises(adapter.EvidenceError):
        parse_repo_reference(text)


# ---------------------------------------------------------------------------
# 2. 文件选择与限额（跳过必须有原因）
# ---------------------------------------------------------------------------


def test_selection_prefers_readme_and_skips_noise(tmp_path):
    materialized = _fake_materializer()("x", None, tmp_path / "clone")
    selected, skipped = github.select_files(materialized.files, RepoLimits(), root=materialized.root)

    assert selected[0] == "README.md"  # README 优先
    assert "src/service.py" in selected and "Dockerfile" in selected
    reasons = {item.path: item.reason for item in skipped}
    assert reasons["node_modules/dep/index.js"] == "依赖/产物目录"
    assert reasons["assets/logo.png"] == "格式不在文本/代码白名单"


def test_selection_enforces_count_limit(tmp_path):
    materialized = _fake_materializer()("x", None, tmp_path / "clone")
    limits = RepoLimits(max_files=2, max_file_bytes=10_000, max_total_bytes=100_000)
    selected, skipped = github.select_files(materialized.files, limits, root=materialized.root)

    assert len(selected) == 2
    reasons = " ".join(item.reason or "" for item in skipped)
    assert "文件数超上限" in reasons


def test_selection_enforces_size_and_total_limits(tmp_path):
    materialized = _fake_materializer()("x", None, tmp_path / "clone")
    limits = RepoLimits(max_files=20, max_file_bytes=300, max_total_bytes=100_000)
    selected, skipped = github.select_files(materialized.files, limits, root=materialized.root)

    assert "big.py" not in selected  # 单文件超 300 字节被挡下
    reasons = {item.path: item.reason for item in skipped}
    assert "单文件过大" in (reasons.get("big.py") or "")


# ---------------------------------------------------------------------------
# 3. 技术栈清单（确定性、带证据路径）
# ---------------------------------------------------------------------------


def test_tech_stack_detection_is_deterministic_and_evidenced():
    """检测覆盖**全部跟踪文件**（含未入库的大文件）—— 清单要准，不必与入库选择一致。"""
    stack = github.detect_tech_stack(sorted(TREE))
    assert stack["python"] == ["big.py", "requirements.txt", "src/service.py"]
    assert stack["typescript"] == ["src/ui.ts"]
    assert stack["docker"] == ["Dockerfile"]
    assert stack == github.detect_tech_stack(sorted(TREE))  # 同输入同输出


# ---------------------------------------------------------------------------
# 4. 端到端（离线）：单入口 / 归属通道 / 失败隔离 / 幂等
# ---------------------------------------------------------------------------


def test_ingest_goes_through_the_single_entry(store, tmp_path, monkeypatch):
    calls: list[dict] = []
    real_ingest = adapter.ingest_document

    def spy(path, **kwargs):
        calls.append({"path": str(path), **kwargs})
        return real_ingest(path, **kwargs)

    monkeypatch.setattr(adapter, "ingest_document", spy)
    report = ingest_repo(
        "kkmmtt0919/mytset-rag",
        store=store,
        attribution="user_declared",
        workdir=tmp_path / "gh",
        materializer=_fake_materializer(),
    )
    assert len(calls) == report.files_selected == len(report.ok)
    assert all(call["channel"] == "user_evidence" for call in calls)
    assert all(call["attribution"] == "user_declared" for call in calls)
    assert all("growth_github_sha" in call["extra_metadata"] for call in calls)


def test_attribution_channel_and_repo_metadata_survive(store, tmp_path):
    report = ingest_repo(
        "kkmmtt0919/mytset-rag",
        store=store,
        attribution="user_declared",
        workdir=tmp_path / "gh",
        materializer=_fake_materializer(),
    )
    readme = next(item for item in report.ok if item.path == "README.md")
    metadata = adapter.source_metadata(store, readme.source_id)
    assert metadata["growth_evidence_type"] == "repo_artifact"
    assert metadata["growth_channel"] == "user_evidence"
    assert metadata[ATTRIBUTION_METADATA_KEY] == "user_declared"
    assert metadata["growth_github_repo"] == "kkmmtt0919/mytset-rag"
    assert metadata["growth_github_path"] == "README.md"
    assert metadata["growth_github_sha"] == report.sha
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is True
    source = store.get_source(readme.source_id)
    assert source.title == "kkmmtt0919/mytset-rag:README.md"


def test_domain_reference_repo_cannot_support_user_claims(store, tmp_path):
    report = ingest_repo(
        "psf/requests",
        store=store,
        evidence_type="external_ref",
        channel="domain_reference",
        attribution="unknown",
        workdir=tmp_path / "gh",
        materializer=_fake_materializer(),
    )
    metadata = adapter.source_metadata(store, report.ok[0].source_id)
    assert metadata["growth_channel"] == "domain_reference"
    assert can_support_user_claim(attribution_of(metadata), metadata["growth_channel"]) is False
    assert adapter.sources_by_channel(store, "user_evidence") == []


def test_reingest_same_ref_reuses_sources(store, tmp_path):
    kwargs = {"store": store, "attribution": "user_declared", "workdir": tmp_path / "gh"}
    first = ingest_repo("kkmmtt0919/mytset-rag", materializer=_fake_materializer(), **kwargs)
    second = ingest_repo("kkmmtt0919/mytset-rag", materializer=_fake_materializer(), **kwargs)

    assert [item.source_id for item in first.ok] == [item.source_id for item in second.ok]
    assert store.counts()["sources"] == len(first.ok)  # 没有制造重复来源


def test_single_file_failure_does_not_abort(store, tmp_path, monkeypatch):
    real_ingest = adapter.ingest_document

    def flaky(path, **kwargs):
        if str(path).endswith("service.py"):
            raise adapter.EvidenceError("注入的失败")
        return real_ingest(path, **kwargs)

    monkeypatch.setattr(adapter, "ingest_document", flaky)
    report = ingest_repo(
        "kkmmtt0919/mytset-rag",
        store=store,
        attribution="user_declared",
        workdir=tmp_path / "gh",
        materializer=_fake_materializer(),
    )
    failed = {item.path for item in report.failed}
    assert failed == {"src/service.py"}
    assert "注入的失败" in report.failed[0].reason
    assert len(report.ok) >= 3  # 其余文件照常入库


def test_clone_failure_raises_product_error(store, tmp_path):
    def broken(repo, ref, dest):
        raise adapter.EvidenceError("克隆失败: owner/name rc=128 （私有仓库或不存在：本步只支持公共仓库，不接 OAuth）")

    with pytest.raises(adapter.EvidenceError, match="只支持公共仓库"):
        ingest_repo(
            "owner/private-repo",
            store=store,
            attribution="user_declared",
            workdir=tmp_path / "gh",
            materializer=broken,
        )


def test_clone_environment_disables_interactive_prompts():
    """公共仓库无需凭据；私有/不存在仓库必须立即失败，不能卡在输入提示上。"""
    env = github.clone_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"] == "echo"
