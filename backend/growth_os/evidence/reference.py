"""外部参考通道（`domain_reference`）：JD / 岗位要求等。

边界（用户 2026-10-02 指定的 M3-d 六条）：

1. JD **只能**作为 `domain_reference`；2. **不得进入** `user_evidence`；
3. **不得支撑**用户能力声明；4. 技术栈/岗位要求**可以**抽取为外部参考；
5. capability claim 留 **M3-e**；6. 不接 UI、不做匹配评分、不做能力差距分析。

这三条"不得"由**结构**保证，而不是靠调用方自觉：

* **通道硬编码**：`ingest_reference_document()` **没有** `channel` / `evidence_type` 参数 ——
  调用方无法把它写进 `user_evidence`（要那样做只能绕过本模块，用适配层的通用入口）；
* **消费侧兜底**：`can_support_user_claim()`（M3-a）要求通道为 `user_evidence` 且归属为
  `user_declared`，因此参考材料的通道一票否决；
* **抽取只读**：`extract_reference_profile()` 只读 passage，不写 claim / evidence / entity，
  也不做任何评分或差距分析（边界 4 允许"抽取为外部参考"，不代表可以得出能力结论）。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import adapter

REFERENCE_CHANNEL = "domain_reference"
REFERENCE_EVIDENCE_TYPE = "external_ref"
REFERENCE_KIND_KEY = "growth_reference_kind"
"""参考类型标签（如 `job_description`），走 `extra_metadata`；非保留键，不覆盖成长标签。"""

TECH_TERMS: tuple[str, ...] = (
    # 语言 / 运行时
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "sql", "shell",
    # 框架 / 服务端
    "fastapi", "django", "flask", "spring boot", "spring", "mybatis", "grpc", "rest", "graphql", "mcp",
    # 前端
    "react", "vue", "vite", "node.js", "webpack",
    # 数据 / 存储
    "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "kafka", "chromadb", "milvus", "faiss",
    "向量数据库", "向量检索", "知识图谱",
    # AI / LLM
    "llm", "大模型", "agent", "rag", "langchain", "llamaindex", "prompt", "微调", "fine-tuning",
    "pytorch", "tensorflow", "transformer", "embedding",
    # 工程 / 运维
    "docker", "kubernetes", "k8s", "ci/cd", "jenkins", "git", "linux", "nginx",
)
"""确定性词表：命中即记录（含所在 passage）。只用于**外部参考**的结构化，不参与评级。"""

REQUIREMENT_MARKERS: tuple[str, ...] = (
    "任职要求", "岗位要求", "职位要求", "职责", "要求", "熟悉", "掌握", "具备", "了解", "精通",
    "experience with", "proficient", "familiar",
)
"""被视作"要求条目"的标记词（中英）。"""


def ingest_reference_document(
    path: str | Path,
    *,
    store,
    reference_kind: str = "job_description",
    attribution: str | None = "user_declared",
    title: str | None = None,
) -> adapter.IngestResult:
    """把一份**外部参考**材料入库（通道锁定为 `domain_reference`）。

    `attribution` 描述的是"这份材料是不是用户交出来的"（此处默认 `user_declared`：用户确实把它给了我们），
    但**通道**才是决定它能不能支撑用户能力断言的那一票 —— 见 `can_support_user_claim()`。
    """
    return adapter.ingest_document(
        path,
        store=store,
        evidence_type=REFERENCE_EVIDENCE_TYPE,
        channel=REFERENCE_CHANNEL,
        attribution=attribution,
        extra_metadata={REFERENCE_KIND_KEY: reference_kind},
        title=title,
    )


def _find_terms(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for term in TECH_TERMS:
        if term.isascii():
            # ASCII 词用边界匹配，避免 "go" 命中 "google"
            if re.search(rf"(?<![a-z0-9+#.]){re.escape(term)}(?![a-z0-9+#])", lowered):
                hits.append(term)
        elif term in text:
            hits.append(term)
    return sorted(hits)


def extract_reference_profile(store, source_id: str) -> dict:
    """从一份参考材料里抽取「技术栈词 + 要求条目」，每条都带 **passage 证据**。

    只读：不写 claim / evidence / entity，也不产出任何评分或差距（边界 5/6）。
    """
    metadata = adapter.source_metadata(store, source_id)
    if metadata.get(adapter.GROWTH_CHANNEL) != REFERENCE_CHANNEL:
        raise adapter.EvidenceError(
            f"只对 domain_reference 材料做参考抽取；该来源通道为 {metadata.get(adapter.GROWTH_CHANNEL)!r}"
        )
    passages = store.get_passages(source_id=source_id)
    terms: dict[str, list[str]] = {}
    requirements: list[dict] = []
    for passage in passages:
        for term in _find_terms(passage.text):
            terms.setdefault(term, []).append(passage.id)
        if any(marker in passage.text for marker in REQUIREMENT_MARKERS):
            requirements.append({"passage_id": passage.id, "ordinal": passage.ordinal, "text": passage.text})
    return {
        "source_id": source_id,
        "reference_kind": metadata.get(REFERENCE_KIND_KEY),
        "channel": metadata.get(adapter.GROWTH_CHANNEL),
        "passage_count": len(passages),
        "tech_terms": {term: sorted(set(ids)) for term, ids in sorted(terms.items())},
        "requirement_lines": sorted(requirements, key=lambda item: item["ordinal"]),
    }
