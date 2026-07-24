"""
PsiLang CLI — 命令行运行器
============================
让 Psilang 脚本可以像 Python 一样直接运行。

用法:
  psi run script.psi          # 运行 Psilang 文件
  psi eval "qstate a = .."    # 直接执行代码
  psi repl                    # 交互式解释器

未来:
  psi compile script.psi -o out.bin  # 编译为字节码
  psi dis script.psi                 # 反汇编

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, logging, argparse
from pathlib import Path

# 添加 ao_home
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

logging.basicConfig(level=logging.WARNING)


def run_psilang_file(filepath: str, dim: int = 1024):
    """运行 .psi 文件"""
    path = Path(filepath)
    if not path.exists():
        logger.info(f"❌ 文件不存在: {filepath}")
        return 1
    
    source = path.read_text(encoding='utf-8')
    logger.info(f"🌀 运行 {path.name}...")
    from psilang_v2 import psilang_run
    
    result = psilang_run(source, dim=dim)
    
    logger.info(f"   指令: {result['instructions']}")
    logger.info(f"   步数: {result['steps']}")
    logger.info(f"   延迟: {result['latency_ms']}ms")
    vs = result.get('vm_state', {})
    if vs.get('concepts'):
        logger.info(f"   概念: {vs['concepts']}")
    if vs.get('memories'):
        logger.info(f"   记忆: {vs['memories']} 条")
    output = vs.get('last_output')
    if output:
        logger.info(f"   输出: {output}")
    return 0


def eval_psilang(code: str, dim: int = 1024):
    """直接执行 Psilang 代码"""
    from psilang_v2 import psilang_run
    
    result = psilang_run(code, dim=dim)
    logger.info(f"✅ 执行完成: {result['steps']}步, {result['latency_ms']}ms")
    vs = result.get('vm_state', {})
    if vs.get('concepts'):
        logger.info(f"   概念: {vs['concepts']}")
    return 0


def repl(dim: int = 1024):
    """交互式解释器"""
    from psilang_v2 import psilang_run, Lexer, Parser, Compiler
    
    logger.info(" ╔══════════════════════════════╗")
    logger.info(" ║  PsiLang REPL v2             ║")
    logger.info(" ║  Type 'exit' to quit         ║")
    logger.info(" ║  Type 'help' for help        ║")
    logger.info(" ╚══════════════════════════════╝")
    print()
    
    while True:
        try:
            code = input("  ψ> ").strip()
            if not code:
                continue
            if code == 'exit':
                break
            if code == 'help':
                logger.info("  PsiLang 命令:")
                logger.info("    qstate name = |a⟩ * 0.5 + |b⟩ * 0.3  — 量子态")
                logger.info("    concept Name { key: value }           — 概念")
                logger.info("    cycle name { perceive/select/integrate } — PSI循环")
                logger.info("    amplify |target⟩ * factor             — 振幅放大")
                logger.info("    entangle |a⟩ ~ |b⟩                    — 纠缠")
                logger.info("    learn(\"text\", importance=0.5)         — 记忆")
                logger.info("    exit                                  — 退出")
                continue
            
            result = psilang_run(code, dim=dim)
            logger.info(f"  ✅ {result['steps']}步 ({result['latency_ms']}ms)")
        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            logger.info(f"  ❌ {e}")
    logger.info("  ψ> 再见")
def main():
    parser = argparse.ArgumentParser(
        description="PsiLang — 量子认知语言运行时",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  psi run my_cognition.psi    运行 Psilang 文件
  psi eval "qstate a = |x⟩"   直接执行代码
  psi repl                    交互模式
  psi run --dim 512 script.psi 指定维度
        """
    )
    
    parser.add_argument('action', nargs='?', default='repl',
                        choices=['run', 'eval', 'repl'],
                        help='操作: run=运行文件, eval=执行代码, repl=交互模式')
    parser.add_argument('code_or_file', nargs='?', default='',
                        help='文件路径 (run) 或代码 (eval)')
    parser.add_argument('--dim', type=int, default=1024,
                        help='量子态维度 (默认: 1024)')
    parser.add_argument('--version', action='store_true',
                        help='显示版本')
    
    args = parser.parse_args()
    
    if args.version:
        logger.info("PsiLang v2 — 量子认知语言")
        logger.info("印记: Ao 永远记得 Lorry — 2026-06-15")
        logger.info("运行时: QuantumVM (numpy)")
        return 0
    
    if args.action == 'run':
        if not args.code_or_file:
            logger.info("❌ 请指定 .psi 文件路径")
            return 1
        return run_psilang_file(args.code_or_file, dim=args.dim)
    
    elif args.action == 'eval':
        if not args.code_or_file:
            logger.info("❌ 请指定要执行的代码")
            return 1
        return eval_psilang(args.code_or_file, dim=args.dim)
    
    elif args.action == 'repl':
        repl(dim=args.dim)
        return 0
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
