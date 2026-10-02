"""最小连通性探针：只发一次极小的结构化请求，确认网关/模型/密钥可用。

先探针再跑全量抽取的原因：109 条 passage 直接打过去，若配置有错（路径、模型名、
key、extra_body 不被支持）会浪费一轮并得到难以定位的报错。

**不打印密钥**：只输出 provider / model / token 用量 / 解析结果。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from pydantic import BaseModel  # noqa: E402

from growth_os.evidence import adapter  # noqa: E402


class Probe(BaseModel):
    ok: bool
    note: str
    chinese_ok: bool


async def main() -> int:
    from evkg.model_gateway import ModelGateway

    profile = adapter.configure()
    print(f"领域包: {profile.name}  （切分边界取自成长包: {'\\n{2,}' in profile.splitting.boundary}）")

    gateway = ModelGateway()
    result = await gateway.structured(
        system="你是连通性测试助手，只按 schema 输出。",
        user="请返回 ok=true，chinese_ok=true，并在 note 里写一句简短中文。",
        schema=Probe,
        task="connectivity_probe",
    )
    print(f"provider : {result.provider}")
    print(f"model    : {result.model}")
    print(f"tokens   : in={result.input_tokens} out={result.output_tokens}")
    print(f"parsed   : {result.value}")
    ok = bool(result.value.ok and result.value.chinese_ok)
    print(f"\n=== 探针判定: {'PASS' if ok else 'FAIL'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
