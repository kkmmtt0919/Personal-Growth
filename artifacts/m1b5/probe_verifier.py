"""核对独立复核模型是否**真正生效**（而不只是"配了变量"）。

用户明确要求：`independent=True` 不足以证明模型独立 —— 它只检查变量是否被设置。
因此本脚本做三件事：

1. 分别向**主网关**与**复核网关**各发一次真实结构化请求；
2. 打印两者的**实际 provider / 模型名 / base_url**（来自返回体与配置解析），
   而不是只打印环境变量；
3. 断言三者（independent 标志、模型名差异、base_url 差异）同时成立，
   否则判定为"配置未生效"。

**不打印任何密钥。**
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from growth_os.evidence import adapter
from pydantic import BaseModel


class Ping(BaseModel):
    ok: bool
    who: str


async def _probe(gateway, label: str) -> dict:
    result = await gateway.structured(
        system="你是连通性测试助手，只按 schema 输出。",
        user="ok 填 true，who 填你自己的模型名。",
        schema=Ping,
        task=f"verifier_probe_{label}",
    )
    return {
        "label": label,
        "provider": result.provider,
        "model": result.model,
        "base_url": gateway._cfg("BASE_URL", "-"),
        "chat_path": gateway._cfg("CHAT_PATH", "-"),
        "reply_who": result.value.who,
        "tokens": (result.input_tokens, result.output_tokens),
    }


async def main() -> int:
    from evkg.attack.verifier import verifier_gateway
    from evkg.model_gateway import ModelGateway

    adapter.configure()

    main_info = await _probe(ModelGateway(), "main")
    verify_gateway, independent = verifier_gateway()
    verifier_info = await _probe(verify_gateway, "verifier")

    width = 12
    print(f"{'':<{width}} {'主网关':<34} {'复核网关':<34}")
    for key in ("provider", "model", "base_url", "chat_path", "reply_who", "tokens"):
        print(f"{key:<{width}} {main_info[key]!s:<34} {verifier_info[key]!s:<34}")

    checks = [
        ("verifier_gateway() 报告 independent=True", independent is True),
        ("复核模型名与主模型不同", verifier_info["model"] != main_info["model"]),
        ("复核 base_url 与主模型不同", verifier_info["base_url"] != main_info["base_url"]),
        ("复核网关确有真实响应（非回落）", bool(verifier_info["reply_who"])),
    ]
    print()
    ok = True
    for name, passed in checks:
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    print(f"\n=== 独立复核核对: {'真正独立' if ok else '未生效或非独立'} ===")
    if not ok:
        print("注意：若 independent=True 但模型名相同，说明只设了变量而模型没换 —— ")
        print("      evkg 的 independent 只检查『有没有 overrides』，不比模型是否真的不同。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
