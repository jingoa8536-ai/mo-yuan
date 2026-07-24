"""
LAAP Coding CLI — 入口
=====================

用法：
  laap-coding dev             启动交互式开发模式
  laap-coding fix <描述>      修复 bug
  laap-coding implement <描述> 实现功能
  laap-coding review <路径>    代码审查
  laap-coding test <路径>      生成/运行测试
  laap-coding status          查看引擎状态
  laap-coding init            初始化工作区

设计原则（来自 Hermes 精华）：
  - 单命令入口，子命令扁平
  - 零配置默认值，但支持覆盖
  - 快速启动（< 100ms）
  - Token 消耗透明可见
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("laap.coding")


def main():
    """LAAP Coding CLI 入口。"""
    parser = argparse.ArgumentParser(
        prog="laap-coding",
        description="LAAP Development Harness — 最省 token 的编程框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  laap-coding dev                         启动交互模式
  laap-coding fix "ModuleNotFoundError in src/main.py"
  laap-coding implement "user login API"
  laap-coding review src/auth.py
  laap-coding status                      查看引擎状态
        """,
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 格式输出（适合管道）",
    )
    parser.add_argument(
        "--budget", "-b",
        type=int,
        default=2000,
        help="Token 预算上限 (默认 2000)",
    )
    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=".",
        help="工作目录 (默认当前目录)",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # dev — 交互式开发模式
    dev_parser = subparsers.add_parser("dev", help="启动交互式开发模式")

    # fix — 修复 bug
    fix_parser = subparsers.add_parser("fix", help="修复代码 bug")
    fix_parser.add_argument("description", nargs="*", help="Bug 描述")
    fix_parser.add_argument("--file", "-f", type=str, help="目标文件")

    # implement — 实现功能
    impl_parser = subparsers.add_parser("implement", help="实现新功能",
                                        aliases=["impl", "add"])
    impl_parser.add_argument("description", nargs="*", help="功能描述")
    impl_parser.add_argument("--file", "-f", type=str, help="目标文件")

    # review — 代码审查
    review_parser = subparsers.add_parser("review", help="代码审查")
    review_parser.add_argument("path", nargs="?", default=".", help="审查路径")
    review_parser.add_argument("--depth", "-d", type=int, default=2, help="审查深度")

    # test — 测试
    test_parser = subparsers.add_parser("test", help="生成/运行测试")
    test_parser.add_argument("path", nargs="?", default=".", help="测试路径")
    test_parser.add_argument("--gen", action="store_true", help="生成测试代码")

    # status — 引擎状态
    subparsers.add_parser("status", help="查看引擎状态")

    # init — 初始化
    init_parser = subparsers.add_parser("init", help="初始化工作区")
    init_parser.add_argument("--template", "-t", type=str, default="python",
                            help="项目模板 (python/js/rust)")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if not args.command:
        parser.print_help()
        return 1

    # 路由子命令
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
        from engine import HarnessEngine
    except ImportError:
        print("❌ 无法加载引擎模块")
        return 1

    engine = HarnessEngine(
        workdir=Path(args.workdir).resolve(),
        token_budget=args.budget,
        json_output=args.json,
    )

    handlers = {
        "dev": engine.run_dev,
        "fix": engine.run_fix,
        "implement": engine.run_implement,
        "impl": engine.run_implement,
        "add": engine.run_implement,
        "review": engine.run_review,
        "test": engine.run_test,
        "status": engine.run_status,
        "init": engine.run_init,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"未知命令: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
