"""M4-a：**独立审计产物** —— 只读，不写回证据存储（M3-e 决定，用户冻结）。

回答两个问题：

1. 每条 assessment 草案的支撑主张是否逐跳可追溯（链路核验 + 引文逐字 + provenance）；
2. 库里每条主张在准入契约下会被分成什么（越权 / 计划 / 待验证 / 领域参考 / 可准入）——
   这是历史越权主张的**机器化审计**形态：结论落在 artifact 文件里，**不改原始库**。

产物是 JSON（`artifacts/m4a/assessment-audit.json`），包含 `read_only: true` 与
`mutated_evidence_store: false` 两个显式声明；真实库的扫描由运行脚本以
`sqlite3 mode=ro` 驱动（包内不直接开库，边界守卫只管到包）。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..evidence import adapter
from .contract import CONTRACT_VERSION, check_chain, classify_claim


def _provenance(claim: dict) -> dict:
    """抽取 provenance（C5）：记录了什么就显示什么，缺的如实说明缺。"""
    metadata = claim.get("metadata") or {}
    if metadata.get("extractor_model"):
        return {
            "recorded": True,
            "provider": metadata.get("extractor_provider"),
            "model": metadata.get("extractor_model"),
            "prompt_hash": metadata.get("extractor_prompt_hash"),
            "profile": metadata.get("extractor_profile"),
        }
    if metadata.get("growth_claim_scope") == "material":
        return {
            "recorded": False,
            "note": "不适用：材料口径断言由适配层确定性构造，没有抽取阶段",
        }
    return {
        "recorded": False,
        "note": "未记录：该主张产生于 C5（抽取 provenance）修复之前，不拿当前配置冒充历史事实",
    }


def _chain_dict(chain) -> dict:
    return asdict(chain)


def build_audit(store, evidence_store, *, db_path: str, user_id: str = "local") -> dict:
    """装配审计产物（只读；调用方负责写文件与销毁临时库）。"""
    overview = {
        entry["claim"]["id"]: entry for entry in adapter.claims_overview(evidence_store)
    }

    assessments: list[dict] = []
    for row in store.list_assessments():
        capability = store.get_capability(row["capability_id"]) or {}
        rubric = json.loads(row.get("rubric_json") or "{}")
        supports: list[dict] = []
        for link in store.list_capability_claims(capability_id=row["capability_id"]):
            entry = overview.get(link["claim_id"])
            if entry is None:
                supports.append(
                    {
                        "claim_id": link["claim_id"],
                        "role": link["role"],
                        "present": False,
                        "reasons": ["claim 不在当前证据库中（引用失效）"],
                    }
                )
                continue
            classification = classify_claim(entry)
            chain = classification.chain or check_chain(entry)
            supports.append(
                {
                    "claim_id": link["claim_id"],
                    "role": link["role"],
                    "present": True,
                    "classification": classification.kind,
                    "admissible": classification.admissible,
                    "reasons": list(classification.reasons),
                    "chain": _chain_dict(chain),
                    "provenance": _provenance(entry["claim"]),
                }
            )
        assessments.append(
            {
                "assessment_id": row["id"],
                "user_id": row["user_id"],
                "goal_id": row["goal_id"],
                "capability_id": row["capability_id"],
                "capability_path": capability.get("path"),
                "capability_status": capability.get("status"),
                "status": row["status"],
                "level": row["level"],
                "rationale": row["rationale"],
                "rubric": rubric,
                "supports": supports,
            }
        )

    claims_scan = []
    for claim_id, entry in overview.items():
        classification = classify_claim(entry)
        claims_scan.append(
            {
                "claim_id": claim_id,
                "classification": classification.kind,
                "admissible": classification.admissible,
                "reasons": list(classification.reasons),
                "statement": (entry["claim"].get("statement") or "")[:160],
                "provenance": _provenance(entry["claim"]),
            }
        )

    return {
        "artifact": "m4a-assessment-audit",
        "contract": CONTRACT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "user_id": user_id,
        "read_only": True,
        "mutated_evidence_store": False,
        "assessment_count": len(assessments),
        "assessments": assessments,
        "claims_scan": claims_scan,
    }


def write_audit(path: str | Path, artifact: dict) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return str(target)
