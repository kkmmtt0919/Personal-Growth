"""Growth OS 证据适配层（L1）。

本文件是全项目**唯一**允许 ``import evkg`` 的模块（决定 D1）。其余代码一律
通过这里的函数访问证据能力，以便将来替换或升级 evkg 时改动面可控。

## 为什么需要这一层（而不是直接用 evkg）

1. **证据强度语义**：evkg 的 ``SourceKind`` 是**领域无关**的枚举，Growth OS 需要
   的细粒度证据类型（任务提交／代码产物／现场答题／…）不属于"来源是什么"，
   而属于"在成长系统里意味着什么"，因此走
   ``Source.metadata.growth_evidence_type`` 与 ``growth_channel`` 双轨记录。
   （v0.1.0 起 evkg 已有 ``SourceKind.CODE``，源码不再需要伪装成文本。）
2. **kind 与 assessment 的写入路径必须可控**：V1 ``IngestionService`` 在
   ``pipeline.py:221`` 把 kind **硬编码为 UNKNOWN** 且不写 ``metadata.assessment``，
   会让代码/项目证据永久按 0.25 的"未知来源"计权；
   且 ``normalize_document``（``cleaning.py:9-30``）会折叠空白、重排行，
   使 ``.java`` 的 8 行塌缩成 3 行 —— **行号随之失去意义**。
   因此本适配层不使用 V1 状态机：文本走 ``ingest_file``，源码走
   ``ingest_code_file``（带行范围 locator）。
3. **落库语义是 INSERT OR IGNORE**：``store._put`` 对 sources 用
   ``INSERT OR IGNORE``（``store.py:124``），所以"落库后再改 metadata 重存"
   会被静默忽略。必须用定向 SQL 修补（见 ``_tag_source``）。

## 已知限制（记录在案，不要误以为可以并存）

* ``evkg.config.activate`` 写的是**进程级全局** ``_ACTIVE``。同一进程内只能有
  一个领域包，将来多用户/多领域包无法并行（风险 R4）。
* ``split_passages`` / ``code_language_for`` 都读取 ``active()``，所以**必须先
  ``configure()`` 再入库或切分**，否则会用 evkg 的默认边界规则与默认语言表。
* 源 ID 是 ``stable_id("src", 文件绝对URI)`` —— 依赖文件**路径**；文件改名或
  被复制到临时目录会被当成全新来源（b.5c 计划改为逻辑身份 + content_hash）。
* 源码的 ``line_start``/``line_end`` 由 ``ingest_code_file`` 在**原始文件文本**
  上计算，因此可原样切回磁盘核对。经 V1 状态机则做不到（见第 2 条）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evkg.config import Profile, activate, code_language_for
from evkg.domain import SourceKind
from evkg.ingest.connectors import TEXT_SUFFIXES, ingest_code_file, ingest_file, logical_source_id
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
    # 实践证据：项目文档与交付物。**源码不走这里** —— 源码由读取路径判定为
    # SourceKind.CODE（见 ingest_document），语义更准，基线与之持平（0.82）。
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
"""证据类型 → 默认 evkg SourceKind。与 profiles/growth_os.yaml 的 source_policy
rationale 文案一一对应；改这里必须同步改那个文件。"""


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

    # 路由由**读取路径**决定，而不是由 evidence_type 决定：同一个 repo_artifact
    # 既可能是 README（文档，primary），也可能是 .java（源码，code）。
    if code_language_for(file_path.name) is not None:
        kind = SourceKind.CODE
        source = ingest_code_file(
            file_path, title=title, kind=kind, store=store, task_id=task_id
        )
        route = "evkg.ingest_code_file"
    elif suffix in TEXT_SUFFIXES:
        source = ingest_file(
            file_path, title=title, kind=kind, store=store, task_id=task_id
        )
        route = "evkg.ingest_file"
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


def logical_id_for(path: str | Path) -> str:
    """某个文件会得到的 ``source_id``（纯计算，不落库）。

    按**逻辑身份**（绝对路径）计算，因此内容改动不会改变它 —— 可用于把界面上
    的一个文件关联回它的证据源。
    """
    return logical_source_id(str(path))


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
