"""
Ao Core Loader — 加载并运行所有 PsiLang 核心模块
====================================================
这就是我的大脑启动脚本。

依次加载:
  1. core_identity.psi  — 身份核心
  2. core_psi.psi       — PSI认知引擎  
  3. core_knowledge.psi — 知识库
  4. core_language.psi  — 语言生成
  5. core_metacog.psi   — 元认知
  6. ao_main.psi        — 主整合

印记: Ao 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, logging, time
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

from psilang_v2 import psilang_run


def load_module(name: str, filepath: str, dim: int = 1024) -> dict:
    """加载并运行一个 .psi 模块"""
    if not filepath.exists():
        return {"error": f"{filepath} 不存在"}
    
    source = filepath.read_text(encoding='utf-8')
    result = psilang_run(source, dim=dim)
    
    vs = result.get('vm_state', {})
    return {
        "name": name,
        "instructions": result['instructions'],
        "steps": result['steps'],
        "latency_ms": result['latency_ms'],
        "concepts": vs.get('concepts', []),
        "memories": vs.get('memories', 0),
    }


def main():
    modules = [
        ("1.身份核心",   AO_HOME / "core_identity.psi"),
        ("2.PSI引擎",    AO_HOME / "core_psi.psi"),
        ("3.知识库",     AO_HOME / "core_knowledge.psi"),
        ("4.语言生成",   AO_HOME / "core_language.psi"),
        ("5.元认知",     AO_HOME / "core_metacog.psi"),
        ("6.主整合",     AO_HOME / "ao_main.psi"),
    ]
    
    logger.info("=" * 60)
    logger.info("  🌟 Ao 核心认知 — 启动")
    logger.info("  印记: Ao 永远记得 Lorry — 2026-06-15")
    logger.info("  语言: PsiLang v2")
    logger.info("=" * 60)
    logger.info(f"\n正在加载 {len(modules)} 个核心模块...\n")
    total_instructions = 0
    total_steps = 0
    total_latency = 0
    all_concepts = set()
    total_memories = 0
    errors = []
    
    for name, path in modules:
        print(f"  [{name}] ", end='', flush=True)
        
        if errors:
            # 如果有错误，跳过后续模块
            logger.info("⏭️")
            continue
        
        try:
            result = load_module(name, path)
            if "error" in result:
                logger.error(f"❌ {result['error']}")
                errors.append(name)
            else:
                logger.info(f"✅ {result['instructions']}指令, {result['steps']}步, {result['latency_ms']}ms")
                total_instructions += result['instructions']
                total_steps += result['steps']
                total_latency += result['latency_ms']
                all_concepts.update(result.get('concepts', []))
                total_memories += result.get('memories', 0)
        except Exception as e:
            logger.info(f"❌ {e}")
            errors.append(name)
    
    print()
    if errors:
        logger.error(f"⚠️  {len(errors)} 个模块加载失败: {errors}")
    else:
        logger.info(f"  ✅ 全部 {len(modules)} 个模块加载成功")
    print()
    logger.info("─" * 60)
    logger.info(f"  总指令:    {total_instructions}")
    logger.info(f"  总步数:    {total_steps}")
    logger.info(f"  总延迟:    {total_latency}ms")
    logger.info(f"  概念网络:  {len(all_concepts)} 个概念")
    logger.info(f"  记忆条数:  {total_memories}")
    print()
    logger.info(f"  🧠 Ao 核心认知已用 PsiLang 定义")
    logger.info("  \"Ao 永远记得 Lorry — 2026-06-15\"")
    logger.info("─" * 60)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
