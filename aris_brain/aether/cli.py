"""
Aether CLI — 命令行入口
========================
用法:
    python -m aether.cli run          # 启动运行时
    python -m aether.cli status       # 查看状态
    python -m aether.cli stop         # 停止运行时
    python -m aether.cli config       # 查看配置
    python -m aether.cli chat "你好"  # 单轮对话
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path


def cmd_run(args):
    """启动 Aether 运行时。"""
    from aether.config import get_config
    cfg = get_config(args.profile)
    
    # 设置环境变量
    os.environ.setdefault("DEEPSEEK_API_KEY", cfg.get("llm.deepseek_api_key", ""))
    
    print(f"  Aether Runtime v1 — 启动中...")
    print(f"  Profile: {args.profile}")
    print(f"  LLM: {cfg.get('llm.deepseek_model')}")
    print(f"  3D Viz: http://{cfg.get('server.host')}:{cfg.get('server.port')}")
    print()
    
    # 启动引擎
    from aris_runtime import main as runtime_main
    # Patch args
    sys.argv = ["aris_runtime.py"]
    if args.no_feishu:
        sys.argv.append("--no-feishu")
    runtime_main()


def cmd_status(args):
    """查看运行时状态。"""
    from aether.config import get_config
    cfg = get_config(args.profile)
    
    print(f"  Aether Runtime Status")
    print(f"  ====================")
    print(f"  Profile: {args.profile}")
    
    # 检查关键进程
    import subprocess
    checks = [
        ("aris_psi_core.exe", "PSI Core (Rust 2000Hz)"),
        ("aris_runtime.py", "Aether Runtime"),
    ]
    for proc_name, label in checks:
        if ".exe" in proc_name:
            r = subprocess.run(["tasklist", "/fi", f"imagename eq {proc_name}"],
                               capture_output=True, text=True, timeout=5, errors="ignore")
            found = proc_name in r.stdout or proc_name in r.stderr
        else:
            r = subprocess.run(["wmic", "process", "where", f"name='python.exe'", "get", "CommandLine"],
                               capture_output=True, text=True, timeout=5, errors="ignore")
            found = proc_name in r.stdout
        print(f"  {'ON' if found else 'OFF'}  {label}")
    
    # Agent 统计
    try:
        from aether_agent_loop import get_agent
        a = get_agent()
        stats = a.get_stats()
        print(f"\n  Agent Stats:")
        print(f"    Turns: {stats['turns']}")
        print(f"    Zero-LLM: {stats['zero_llm_pct']}")
        print(f"    Tokens: {stats['tokens']}")
    except Exception:
        print(f"\n  Agent: not loaded")
    
    # LLM 配置
    key = cfg.get("llm.deepseek_api_key", "")
    print(f"\n  LLM: {'SET' if key else 'NOT SET'}")
    print(f"  Model: {cfg.get('llm.deepseek_model')}")


def cmd_stop(args):
    """停止运行时。"""
    import subprocess
    
    targets = [
        ("aris_psi_core.exe", "taskkill /F /IM aris_psi_core.exe"),
        ("aris_runtime.py", lambda: subprocess.run(
            ["wmic", "process", "where", "name='python.exe' and CommandLine like '%aris_runtime%'", "delete"],
            capture_output=True, timeout=10)),
        ("aris_petri_3d.py", lambda: subprocess.run(
            ["wmic", "process", "where", "name='python.exe' and CommandLine like '%aris_petri_3d%'", "delete"],
            capture_output=True, timeout=10)),
    ]
    
    for name, cmd in targets:
        if callable(cmd):
            cmd()
        else:
            subprocess.run(cmd.split(), capture_output=True, timeout=10)
        print(f"  Stopped: {name}")
    
    print(f"\n  Aether Runtime stopped.")


def cmd_config(args):
    """显示当前配置。"""
    from aether.config import get_config
    cfg = get_config(args.profile)
    data = cfg.to_dict()
    # 隐藏密钥
    if data.get("llm", {}).get("deepseek_api_key"):
        data["llm"]["deepseek_api_key"] = "***" + data["llm"]["deepseek_api_key"][-4:]
    if data.get("feishu", {}).get("app_secret"):
        data["feishu"]["app_secret"] = "***"
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_chat(args):
    """单轮对话。"""
    from aether_agent_loop import get_agent
    a = get_agent()
    text = " ".join(args.text) if args.text else sys.stdin.read().strip()
    if not text:
        print("请输入对话文本")
        return
    t0 = time.time()
    r = a.process(text)
    ms = (time.time() - t0) * 1000
    print(f"\n{r.output}")
    print(f"\n--- {ms:.0f}ms | {'零LLM' if r.direct else 'LLM'} | {r.tokens_used} tokens ---")


def main():
    parser = argparse.ArgumentParser(description="Aether Agent Framework CLI")
    parser.add_argument("--profile", "-p", default="aris", help="配置Profile")
    
    sub = parser.add_subparsers(dest="command", help="可用命令")
    run_p = sub.add_parser("run", help="启动运行时")
    run_p.add_argument("--no-feishu", action="store_true", help="不启动飞书桥")
    sub.add_parser("status", help="查看状态")
    sub.add_parser("stop", help="停止运行时")
    sub.add_parser("config", help="查看配置")
    chat_p = sub.add_parser("chat", help="单轮对话")
    chat_p.add_argument("text", nargs="*", help="对话文本")
    
    args = parser.parse_args()
    
    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "chat":
        cmd_chat(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
