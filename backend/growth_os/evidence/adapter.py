"""Growth OS 证据适配层（L1）。

本文件是全项目**唯一**允许 ``import evkg`` 的模块（决定 D1）。其余代码一律通过
这里的函数访问证据能力，以便将来替换或升级 evkg 时改动面可控。

## 这一层的边界（b.5d 起）

**只负责 Growth OS 自己的领域语义，不理解 evkg 的任何存储细节。**

| 归 Growth OS | 归 evkg |
|---|---|
| 证据类型 → 能力评级的角色（知识／行为／实践／任务） | 来源怎么读（reader） |
| `growth_evidence_type` / `growth_channel` 两个标签 | 段落怎么切（文本／代码两套切分器） |
| 哪些标签对应哪些 evkg kind | locator 怎么填、行号怎么算 |
| 能力评级与缺口计算 | `assessment` 怎么算、`content_hash` 怎么判 |
| 面向产品的错误类型（``EvidenceError``） | source 与 passage 的写入语义 |

具体地：本文件**不写任何裸 SQL**、不访问 ``store.db``、不判定文件后缀、
不组装 ``assessment``。这些在 b.5d 之前都是它自己做的（见 DECISIONS "M1-b.5d"），
现在由 evkg 的公共 API 承担：

* ``evkg.ingest.ingest_path`` —— 按内容类型自动路由，调用方只说"入库这个文件"
* ``evkg.store.KnowledgeStore.find_sources(metadata=...)`` —— 按标签检索
* ``ingest_path(..., metadata=...)`` —— 领域标签随入库一起写，与 evkg 自己的键合并

有一条测试守着这个边界（``tests/test_adapter_boundary.py``）：适配层源码里出现
``sqlite3`` / ``.db.execute`` / ``json_set`` / ``SELECT`` 之类就直接失败，
防止耦合随时间慢慢长回来。

## 已知限制（记录在案，不要误以为可以并存）

* ``evkg.config.activate`` 写的是**进程级全局** ``_ACTIVE``。同一进程内只能有
  一个领域包，将来多用户/多领域包无法并行（风险 R4）。
* ``activate`` / ``ingest_path`` 内部都会读 ``active()``，所以**必须先
  ``configure()`` 再入库**，否则会用 evkg 的默认领域配置。
* ``source_id`` 是**逻辑身份**（文件绝对路径），与内容无关；内容是否变化由
  ``Source.content_hash`` 表达。文件改名会被当成新来源（路径即身份）。
* locator 的行号相对**换行规范化后**的文本，可原样切回磁盘核对。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from evkg.config import Profile, activate
from evkg.domain import SourceKind
from evkg.ingest import ingest_path, logical_source_id
from evkg.store import KnowledgeStore

from ..agent.gateway import GatewayResult, StructuredGateway

# ---------------------------------------------------------------------------
# 常量与映射（这些是 Growth OS 的领域知识，不是 evkg 的）
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
    # 实践证据：项目文档与交付物。
    # **源码不走这里** —— 源码由 evkg 的读取路径判定为 SourceKind.CODE，语义更准，
    # 且 growth 领域包给 code 的基线与 primary 持平（0.82），因此改判是评分中性的。
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
"""证据类型 → evkg SourceKind。与 ``profiles/growth_os.yaml`` 的 source_policy
rationale 文案一一对应；改这里必须同步改那个文件。"""

GROWTH_EVIDENCE_TYPE = "growth_evidence_type"
GROWTH_CHANNEL = "growth_channel"


class EvidenceError(RuntimeError):
    """证据层错误（面向产品的错误类型，不把 evkg 的异常类型泄漏出去）。"""


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------


def configure(profile_path: str | Path | None = None) -> Profile:
    """激活成长领域包。

    必须在任何入库之前调用：evkg 的切分边界、代码语言表、来源策略都读进程级
    ``active()``。
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

    永远显式传路径：``KnowledgeStore()`` 不传参会在 ``store.py`` 直接 TypeError
    （那里用了 ``Path(path)`` 而不是 ``Path(self.path)``）。
    """
    path = Path(db_path) if db_path else Path("data/growth.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    configure()  # 保证领域配置在打开前就位
    return KnowledgeStore(str(path))


# ---------------------------------------------------------------------------
# 入库
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    title: str
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
    """把一份文件作为证据入库，并打上成长语义标签。

    适配层在这里做三件事，且只做这三件：校验**领域取值**、给出**领域标签**、
    把「入库这个文件」这件事交给 evkg。文件是源码还是文本、段落怎么切、
    locator 怎么填，全部由 ``ingest_path`` 决定。

    幂等：同一文件重复入库不会产生重复 source/passage；内容未变时 evkg 会判为
    ``unchanged``。重打标签（换 evidence_type）是允许的 —— 新标签覆盖同名旧值，
    其余键保留。
    """
    if evidence_type not in EVIDENCE_KIND_MAP:
        raise EvidenceError(f"未知证据类型: {evidence_type!r}")
    if channel not in ("user_evidence", "domain_reference"):
        raise EvidenceError(f"未知证据通道: {channel!r}")

    file_path = Path(path)
    if not file_path.is_file():
        raise EvidenceError(f"文件不存在: {file_path}")

    try:
        source = ingest_path(
            file_path,
            title=title,
            kind=EVIDENCE_KIND_MAP[evidence_type],
            metadata={GROWTH_EVIDENCE_TYPE: evidence_type, GROWTH_CHANNEL: channel},
            store=store,
            task_id=task_id,
        )
    except ValueError as exc:
        # 把 evkg 对"格式不支持"的判定翻译成产品侧错误类型
        raise EvidenceError(str(exc)) from exc

    return IngestResult(
        source_id=source.id,
        title=source.title,
        kind=source.kind.value,
        evidence_type=evidence_type,
        channel=channel,
        passage_count=len(store.get_passages(source_id=source.id)),
    )


# ---------------------------------------------------------------------------
# 读取与检索（全部走 evkg 的公共 API，不碰存储细节）
# ---------------------------------------------------------------------------


def source_metadata(store: KnowledgeStore, source_id: str) -> dict:
    """读回某个 source 的 metadata（供验证与调试）。"""
    source = store.get_source(source_id)
    if source is None:
        raise EvidenceError(f"未知 source: {source_id}")
    return dict(source.metadata)


def sources_by_channel(store: KnowledgeStore, channel: str) -> list[str]:
    """按成长通道过滤 source。

    这是 `user_evidence` 与 `domain_reference` 必须分开的落地处：不分开的话，
    岗位 JD 里写"AI 工程师需要会 RAG"会被误读成"用户会 RAG"。
    """
    hits = store.find_sources(metadata={GROWTH_CHANNEL: channel})
    return sorted(source.id for source in hits)


def sources_by_evidence_type(store: KnowledgeStore, evidence_type: str) -> list[str]:
    hits = store.find_sources(metadata={GROWTH_EVIDENCE_TYPE: evidence_type})
    return sorted(source.id for source in hits)


def counts(store: KnowledgeStore) -> dict:
    return store.counts()


def claim_dossier(store: KnowledgeStore, claim_id: str) -> dict | None:
    """取某条主张的结构化证据档案（evidence / attacks / review_trail / conflicts）。

    只做转发，不改写内容 —— 呈现层的领域语义（两个"独立"的区别、缺失证据的措辞、
    证据局限）属于 Growth OS，在 ``growth_os.evidence.dossier`` 里处理，不在这里。

    注意：**不要**直接用 evkg 的 ``render_claim_markdown`` 渲染 Growth OS 的档案。
    它只输出 polarity 为 ``supports`` / ``refutes`` 的证据行，**``partial`` 会落空** ——
    而本库里被推翻的那条主张恰恰是 `partial`（独立复核的结论），漏掉它就等于
    把"复核认为只有部分支持"这件事从档案里抹掉。
    """
    from evkg.evidence.dossier import claim_dossier as _claim_dossier

    return _claim_dossier(store, claim_id)


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


# ---------------------------------------------------------------------------
# Agent 模型网关（M2）
# ---------------------------------------------------------------------------

GROWTH_AGENT_ENV = {
    "GROWTH_AGENT_LLM_PROVIDER": "LLM_PROVIDER",
    "GROWTH_AGENT_MODEL": "MODEL",
    "GROWTH_AGENT_BASE_URL": "BASE_URL",
    "GROWTH_AGENT_API_KEY": "API_KEY",
    "GROWTH_AGENT_CHAT_PATH": "CHAT_PATH",
}
"""`GROWTH_AGENT_*` → 网关 overrides 的键映射（与 `.env.example` 的 B 段一致）。

留空的变量不产生 override，网关按 evkg 的规则回落到 `EVKG_*` —— 这样 Agent 推理
可以用与流水线不同的模型，而**不必触碰进程级全局配置**：overrides 是实例级的
（M1-g 已验证这条路径安全；进程级 profile 全局状态才是风险源）。
"""


def growth_agent_overrides() -> dict[str, str]:
    """收集 Growth OS Agent 的实例级网关配置。"""
    overrides = {
        target: value
        for source, target in GROWTH_AGENT_ENV.items()
        if (value := os.getenv(source))
    }
    return overrides


class GrowthAgentGateway:
    """把 evkg `ModelGateway` 的结果适配为 Growth OS 的 `GatewayResult`。

    存在的两条理由：
    1. **不泄漏上游类型** —— `agent/` 只认识 `GatewayResult`，换网关不必改 Agent；
    2. **失败路径也要有标签** —— 成功时 provider/model 取自返回值（实际生效）；
       失败时没有返回值，只能用当时的配置值，并如实标为 `config_on_error`
       （`M2-PLAN.md` 补充约束 C2 要求区分这两者）。
    """

    def __init__(self, gateway) -> None:
        self.gateway = gateway
        self.overrides = dict(gateway.overrides or {})

    def describe(self) -> tuple[str, str]:
        provider = self.overrides.get("LLM_PROVIDER") or os.getenv("EVKG_LLM_PROVIDER") or "anthropic"
        if "MODEL" in self.overrides:
            model = self.overrides["MODEL"]
        else:
            model = os.getenv("EVKG_MODEL") or (
                "claude-3-5-sonnet-latest" if provider == "anthropic" else "gpt-4o-mini"
            )
        return provider, model

    async def structured(self, *, system: str, user: str, schema, task: str) -> GatewayResult:
        result = await self.gateway.structured(system=system, user=user, schema=schema, task=task)
        return GatewayResult(
            value=result.value,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )


def agent_gateway() -> StructuredGateway:
    """构造 Growth OS Agent 的模型网关（实例级 overrides）。

    只在适配层 import evkg（决定 D1）；调用方拿到的是 `StructuredGateway`，
    测试可注入 `FakeGateway` 做完全离线的回归（补充约束 C3）。
    """
    from evkg.model_gateway import ModelGateway

    return GrowthAgentGateway(ModelGateway(growth_agent_overrides() or None))
