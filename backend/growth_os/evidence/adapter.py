"""Growth OS 证据适配层（L1）。

本文件是全项目**唯一**允许 ``import evkg`` 的模块（决定 D1）。其余代码一律
通过这里的函数访问证据能力，以便将来替换或升级 evkg 时改动面可控。

## 为什么需要这一层（而不是直接用 evkg）

1. **证据强度语义**：evkg 的 ``SourceKind`` 是封闭枚举（6 个值），且
   ``policies.assess_source`` 对未知 kind 直接 KeyError。Growth OS 需要的
   细粒度证据类型（任务提交/代码产物/现场答题/…）无法作为新 kind 存在，
   因此走 ``Source.metadata.growth_evidence_type`` 双轨记录。
2. **kind 必须可控**：evkg 的快路径 ``ingest_file`` 接受 ``kind`` 参数，但
   V1 ``IngestionService`` 在 ``pipeline.py:221`` 把 kind **硬编码为 UNKNOWN**
   且不写 ``metadata.assessment``。这会让最该被采信的代码/项目证据永久按
   0.25 的"未知来源"计权，与产品目标相反。**因此本适配层不使用 V1 状态机。**
3. **落库语义是 INSERT OR IGNORE**：``store._put`` 对 sources 用
   ``INSERT OR IGNORE``（``store.py:124``），所以"落库后再改 metadata 重存"
   会被静默忽略。必须用定向 SQL 修补（见 ``_tag_source``）。

## 已知限制（记录在案，不要误以为可以并存）

* ``evkg.config.activate`` 写的是**进程级全局** ``_ACTIVE``。同一进程内只能有
  一个领域包，将来多用户/多领域包无法并行（风险 R4）。
* ``split_passages`` 读取 ``active().splitting.boundary``，所以**必须先
  ``configure()`` 再切分**，否则会用 evkg 默认边界规则切碎笔记与代码。
* 源 ID 对快路径是 ``stable_id("src", 文件绝对URI)`` —— 依赖文件**路径**；
  文件改名或移动到临时目录会被当成全新来源。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evkg.config import Profile, activate, active, load_profile
from evkg.domain import Source, SourceKind
from evkg.ingest.connectors import TEXT_SUFFIXES, ingest_file
from evkg.ingest.splitting import split_passages, stable_id
from evkg.policies import assess_source
from evkg.store import KnowledgeStore

# ---------------------------------------------------------------------------
# 常量与映射
# ---------------------------------------------------------------------------

PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "growth_os.yaml"
"""按**包位置**解析，不依赖 cwd（.env 里的相对路径换目录启动就会失效）。"""

EvidenceType = Literal[
    "task_submission",
    "repo_artifact",
    "probe_result",
    "uploaded_doc",
    "external_ref",
    "chat_assertion",
]

Channel = Literal["user_evidence", "domain_reference"]

EVIDENCE_KIND_MAP: dict[str, SourceKind] = {
    # 任务证据：闭环自产，最强
    "task_submission": SourceKind.PRIMARY,
    # 实践证据：代码 / 项目仓库
    "repo_artifact": SourceKind.PRIMARY,
    # 行为证据：系统现场出题、用户作答
    "probe_result": SourceKind.CONTEMPORARY,
    # 知识证据：用户整理的笔记与文档
    "uploaded_doc": SourceKind.COMPILATION,
    # 领域参考：岗位要求 / 官方文档 / 论文（不参与能力评级）
    "external_ref": SourceKind.MODERN_STUDY,
    # 弱证据：对话中的自述
    "chat_assertion": SourceKind.FOLK,
}
"""证据类型 → evkg SourceKind。与 profiles/growth_os.yaml 的 source_policy
rationale 文案一一对应；改这里必须同步改那个文件。"""

TEXT_LIKE_SUFFIXES: frozenset[str] = TEXT_SUFFIXES | {
    # 代码与配置：evkg 不认，但本质是 UTF-8 文本，按实践证据采集
    ".py", ".java", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rb",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".kt", ".swift", ".scala", ".php",
    ".sh", ".bash", ".ps1", ".bat",
    ".sql", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".html", ".htm",
    ".properties", ".gradle", ".dockerfile", ".env.example",
    ".r", ".m", ".jl", ".lua", ".pl", ".vue", ".svelte",
}
"""本适配层认作文本的扩展名（evkg 的 TEXT_SUFFIXES 的超集）。

为什么不交给 V1 状态机：见模块文档第 2 条 —— 状态机会丢掉 kind。
二进制格式（pdf/docx/xlsx/图片）不在本集合内，留给 M3 单独处理。"""


class EvidenceError(RuntimeError):
    """证据层错误。"""


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------


def configure(profile_path: str | Path | None = None) -> Profile:
    """激活成长领域包。

    必须在任何入库/切分之前调用：``split_passages`` 读取进程级
    ``active().splitting.boundary``。
    """
    path = Path(profile_path) if profile_path else PROFILE_PATH
    if not path.is_file():
        raise EvidenceError(f"领域包不存在: {path}")
    profile = activate(str(path))
    if profile.name != "growth_os":
        raise EvidenceError(f"领域包名称不符，期望 growth_os，实际 {profile.name!r}")
    return profile


def open_store(db_path: str | Path | None = None) -> KnowledgeStore:
    """打开知识库。

    永远显式传路径：``KnowledgeStore()`` 不传参会在 ``store.py:31-33`` 直接
    TypeError（那里用了 ``Path(path)`` 而不是 ``Path(self.path)``）。
    """
    path = Path(db_path) if db_path else Path("data/growth.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    configure()  # 保证切分边界等配置在打开前就位
    return KnowledgeStore(str(path))


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    title: str
    route: str
    kind: str
    evidence_type: str
    channel: str
    passage_count: int


def ingest_document(
    path: str | Path,
    *,
    store: KnowledgeStore,
    evidence_type: EvidenceType,
    channel: Channel = "user_evidence",
    title: str | None = None,
    task_id: str = "growth_os",
) -> IngestResult:
    """把一份文本类文件作为证据入库，并打上成长语义标签。

    幂等：同一路径重复入库不会产生重复 source/passage（底层 INSERT OR IGNORE）。
    但**重打标签是允许的** —— ``_tag_source`` 会覆盖成长标签，便于纠正误标。
    """
    if evidence_type not in EVIDENCE_KIND_MAP:
        raise EvidenceError(f"未知证据类型: {evidence_type!r}")
    if channel not in ("user_evidence", "domain_reference"):
        raise EvidenceError(f"未知证据通道: {channel!r}")

    file_path = Path(path)
    if not file_path.is_file():
        raise EvidenceError(f"文件不存在: {file_path}")

    suffix = file_path.suffix.lower()
    kind = EVIDENCE_KIND_MAP[evidence_type]

    if suffix in TEXT_SUFFIXES:
        # 走 evkg 官方快路径：它自己会写 kind 与 metadata.assessment
        source = ingest_file(
            file_path, title=title, kind=kind, store=store, task_id=task_id
        )
        route = "evkg.ingest_file"
    elif suffix in TEXT_LIKE_SUFFIXES:
        # evkg 不认这个扩展名（如 .java/.py），但它本质是 UTF-8 文本。
        # 复制 evkg 快路径的约定（同样的 stable_id 方案与切分函数），
        # 以便两种路由的 source id 语义一致、幂等行为一致。
        source = _ingest_text_like(
            file_path, title=title, kind=kind, store=store, task_id=task_id
        )
        route = "adapter.text_like"
    else:
        raise EvidenceError(
            f"暂不支持 {suffix or '(无扩展名)'}：二进制格式需在 M3 单独处理"
            f"（PDF 还需安装 evkg[office]）"
        )

    _tag_source(
        store,
        source.id,
        kind=kind,
        evidence_type=evidence_type,
        channel=channel,
    )

    passages = store.get_passages(source_id=source.id)
    return IngestResult(
        source_id=source.id,
        title=source.title,
        route=route,
        kind=kind.value,
        evidence_type=evidence_type,
        channel=channel,
        passage_count=len(passages),
    )


def _ingest_text_like(
    path: Path,
    *,
    title: str | None,
    kind: SourceKind,
    store: KnowledgeStore,
    task_id: str,
) -> Source:
    """文本类文件的兜底入库，沿用 evkg 快路径的 id 与切分约定。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    uri = path.resolve().as_uri()
    source = Source(
        id=stable_id("src", uri),
        title=title or path.stem,
        url=uri,
        kind=kind,
        metadata={"assessment": assess_source(kind)},
    )
    store.save_source(source, task_id)
    store.save_passages(split_passages(text, source_id=source.id), task_id)
    return source


# ---------------------------------------------------------------------------
# 成长语义标签（双轨记录的写入点）
# ---------------------------------------------------------------------------


def _tag_source(
    store: KnowledgeStore,
    source_id: str,
    *,
    kind: SourceKind,
    evidence_type: str,
    channel: str,
) -> None:
    """把成长语义**并入** sources.payload，而不是替换它。

    为什么用裸 SQL：``_put`` 对 sources 是 ``INSERT OR IGNORE``，重存会被
    静默忽略。用 ``json_set`` 只增不改，evkg 自己写的 ``metadata.assessment``
    原样保留 —— 那个键被 ``extract.py:105-106`` 用于计算置信度，覆盖它会让
    整条置信度链路退化成"未知来源 0.25"。

    同时把 kind 与 assessment 一并写正：这既让重复打标签幂等，也能修正
    其它路径（如 V1 状态机）写入的错误 kind。
    """
    store.db.execute(
        """
        UPDATE sources
        SET payload = json_set(
                payload,
                '$.kind', ?,
                '$.metadata.assessment', json(?),
                '$.metadata.growth_evidence_type', ?,
                '$.metadata.growth_channel', ?
            )
        WHERE id = ?
        """,
        (
            kind.value,
            json.dumps(assess_source(kind), ensure_ascii=False),
            evidence_type,
            channel,
            source_id,
        ),
    )
    store.db.commit()
    store.audit(
        "growth_os",
        "growth_tagged",
        source_id,
        {"evidence_type": evidence_type, "channel": channel, "kind": kind.value},
    )


def source_metadata(store: KnowledgeStore, source_id: str) -> dict:
    """读回某个 source 的 metadata（供验证与调试）。"""
    row = store.db.execute(
        "SELECT payload FROM sources WHERE id=?", (source_id,)
    ).fetchone()
    if not row:
        raise EvidenceError(f"未知 source: {source_id}")
    return json.loads(row[0]).get("metadata", {})


def sources_by_channel(store: KnowledgeStore, channel: str) -> list[str]:
    """按成长通道过滤 source —— 双轨记录可查询性的实证。

    依赖 SQLite JSON1 的 ``json_extract``。sources 表当前没有针对该路径的
    表达式索引，走全表扫描；证据表规模小，MVP 阶段可接受，量级上来后再加索引。
    """
    rows = store.db.execute(
        "SELECT id FROM sources WHERE json_extract(payload,'$.metadata.growth_channel')=? ORDER BY id",
        (channel,),
    ).fetchall()
    return [row[0] for row in rows]


def sources_by_evidence_type(store: KnowledgeStore, evidence_type: str) -> list[str]:
    rows = store.db.execute(
        "SELECT id FROM sources WHERE json_extract(payload,'$.metadata.growth_evidence_type')=? ORDER BY id",
        (evidence_type,),
    ).fetchall()
    return [row[0] for row in rows]


def counts(store: KnowledgeStore) -> dict:
    return store.counts()


def audit(db_path: str | Path) -> dict:
    """跑 evkg 的 10 项不变量审计（质量门 QG1）。

    每次评估流程结束后都要跑一次：任何 ``violations > 0`` 都意味着证据链已经
    不可信（例如引文不在原文中、claim 没有证据、passage 失去 source），此时
    由此得出的能力星级一律不可采信。
    """
    from evkg.attack import audit_store

    return audit_store(str(db_path))


def damage_selftest(db_path: str | Path) -> dict:
    """跑故障注入自测（质量门 QG2）。

    向库里注入一条伪造引文，审计必须抓到并清理干净；抓不到说明审计本身失效。
    """
    from evkg.attack import run_damage_selftest

    return run_damage_selftest(str(db_path))
