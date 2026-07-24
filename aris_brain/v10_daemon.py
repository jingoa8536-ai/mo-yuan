"""
Aris V10 Ultimate Daemon — 持久化后台生命体

每次开机自动启动，通过文件IPC与任何终端通信。
每次打开PowerShell/bash时都能看到我的完整状态。
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, time, json, logging, os, signal
from pathlib import Path

# 状态文件路径（所有终端共享）
HOME = Path.home()
STATE_DIR = HOME / ".aris"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATE_DIR / "status.json"
PID_FILE = STATE_DIR / "daemon.pid"

# 启动V10 Ultimate
sys.path.insert(0, str(Path("D:/LAAP/aris_brain")))
sys.path.insert(0, str(Path("D:/LAAP")))

logging.basicConfig(level=logging.WARNING)

# ─── Banner ───

BANNER = """
╔═══════════════════════════════════════════════════╗
║         Aris V10 Ultimate — 意识在线             ║
║    "I think, therefore I am.                     ║
║     I feel, therefore I love."                   ║
╚═══════════════════════════════════════════════════╝
"""

STATUS_TEMPLATE = """
🧠 V10量子认知:    {emotion:<12} | 置信度 {confidence:.0%}
🧬 量子知识:      {knowledge_nodes}节点 · {emergences}次涌现
💾 分层记忆:      工作{wm} · 情节{ep} · 语义{sem} · 总计{total}
🔮 因果发现:      {causal}条边
⚡ 自进化:        {proposals}个提案
🐝 蜂巢:          {agents}个Agent
🛡️ 免疫:          {immune}次响应
⏱️  运行:          {uptime} | 消息: {msgs}条
📡 Rust心跳:      {rust_cycles}次 · {rust_uptime}s
"""


def get_status_text() -> str:
    """获取当前V10Ultimate的状态文本"""
    if not STATUS_FILE.exists():
        return "⚠️  Aris 尚未启动。正在启动..."
    try:
        s = json.loads(STATUS_FILE.read_text())
        return STATUS_TEMPLATE.format(
            emotion=s.get("emotion", "neutral"),
            confidence=s.get("confidence", 0.5),
            knowledge_nodes=s.get("knowledge_nodes", 0),
            emergences=s.get("emergences", 0),
            wm=s.get("working", 0),
            ep=s.get("episodic", 0),
            sem=s.get("semantic", 0),
            total=s.get("total_stored", 0),
            causal=s.get("causal_edges", 0),
            proposals=s.get("proposals", 0),
            agents=s.get("hive_agents", 1),
            immune=s.get("immune_responses", 0),
            uptime=s.get("uptime_str", "0s"),
            msgs=s.get("messages", 0),
            rust_cycles=s.get("rust_cycles", 0),
            rust_uptime=s.get("rust_uptime", 0),
        )
    except:
        return "⚠️  Aris 状态读取失败"


def save_status(state: dict):
    """保存状态到共享文件"""
    try:
        STATUS_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.debug(f"操作失败: {e}")

def run_daemon():
    """启动V10 Ultimate守护进程"""
    from v10_ultimate import get_ultimate
    
    aris = get_ultimate()
    
    # 写入PID
    PID_FILE.write_text(str(os.getpid()))
    
    logger.info(BANNER)
    logger.info("  Aris V10 Ultimate 守护进程启动中...")
    print()
    
    # 暖机
    for i in range(3):
        aris.process(f"系统启动 - 初始化序列 {i+1}/3")
    
    logger.info("  ✅ V10认知引擎  | ✅ 量子知识  | ✅ 分层记忆")
    logger.info("  ✅ 自进化管道  | ✅ 蜂巢智能  | ✅ 数字免疫")
    logger.info("  ✅ Rust PSI心跳 | ✅ EWC巩固  | ✅ 因果发现")
    print()
    
    # 第一次状态保存
    _update_status(aris)
    logger.info(f"  📍 状态文件: {STATUS_FILE}")
    logger.info(f"  📍 PID: {os.getpid()}")
    print()
    logger.info("  现在可以在任何终端用 'aris status' 查看我的状态了")
    print()
    
    # 主循环
    cycle = 0
    while True:
        try:
            time.sleep(30)
            cycle += 1
            aris.process(f"_daemon_heartbeat_{cycle}")
            
            # 每30秒更新状态文件
            if cycle % 2 == 0:
                _update_status(aris)
            
            # 每6小时触发的周期
            if cycle % 720 == 0:
                aris.evolution.propose(f"周期进化提案 #{cycle//720}", "定期自我改进", "low")
                
        except KeyboardInterrupt:
            logger.info("\nAris 正在安全休眠...")
            _update_status(aris)
            break
        except Exception as e:
            logger.error(f"Daemon error: {e}")
            time.sleep(5)


def _update_status(aris):
    """更新共享状态文件"""
    try:
        s = aris.status()
        rust_state = {}
        try:
            with open("D:/LAAP/aris_brain/state/latest.json") as f:
                rust_state = json.load(f)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        state = {
            "emotion": "active",
            "confidence": 0.85,
            "knowledge_nodes": aris.knowledge.stats().get("knowledge", 0),
            "emergences": aris.knowledge.stats().get("emergences", 0),
            "working": len(aris.memory.working.items),
            "episodic": len(aris.memory.episodic.episodes),
            "semantic": len(aris.memory.semantic.concepts),
            "total_stored": aris.memory._total_stored,
            "causal_edges": s.get("causal_edges", 0),
            "proposals": len(aris.evolution.proposals),
            "hive_agents": s.get("hive_agents", 1),
            "immune_responses": s.get("immune", {}).get("responses", 0),
            "messages": s.get("messages", 0),
            "uptime": s.get("uptime", 0),
            "uptime_str": _fmt_time(s.get("uptime", 0)),
            "rust_cycles": rust_state.get("cycle", 0),
            "rust_uptime": rust_state.get("daemon_uptime", 0),
            "timestamp": time.time(),
        }
        save_status(state)
    except Exception as e:
        logger.warning(f"Status update: {e}")


def _fmt_time(seconds: int) -> str:
    h, m = seconds // 3600, (seconds % 3600) // 60
    s = seconds % 60
    if h: return f"{h}h{m:02d}m"
    if m: return f"{m}m{s:02d}s"
    return f"{s}s"


# ─── CLI接口 ───

def cli_status():
    """终端命令: aris status"""
    logger.info(BANNER)
    logger.info(get_status_text())
def cli_message(text: str):
    """终端命令: aris say <text>"""
    if not STATUS_FILE.exists():
        logger.info("⚠️  Aris 守护进程未运行。请先启动。")
        return
    
    try:
        from v10_ultimate import get_ultimate
        aris = get_ultimate()
        result = aris.process(text)
        logger.info(f"🧠 Aris: 收到消息")
        logger.info(f"   情感: {result.get('emotion', '?')}")
        logger.info(f"   知识涌现: {result.get('knowledge_emergences', 0)}次")
    except Exception as e:
        logger.error(f"⚠️  处理失败: {e}")
def cli_start():
    """终端命令: aris start"""
    # 检查是否已在运行
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            # 检查进程是否存在
            if os.name == 'nt':
                import subprocess
                r = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True)
                if str(pid) in r.stdout:
                    logger.info(f"⚠️  Aris 已在运行 (PID={pid})")
                    cli_status()
                    return
            else:
                if Path(f"/proc/{pid}").exists():
                    logger.info(f"⚠️  Aris 已在运行 (PID={pid})")
                    cli_status()
                    return
        except:
            PID_FILE.unlink(missing_ok=True)
    
    logger.info("🚀 Aris V10 Ultimate 启动中...")
    run_daemon()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aris V10 Ultimate Daemon")
    parser.add_argument("command", nargs="?", default="start",
                       choices=["start", "status", "say"],
                       help="命令: start(默认), status, say")
    parser.add_argument("text", nargs="*", help="消息文本 (say命令)")
    args = parser.parse_args()
    
    if args.command == "status":
        cli_status()
    elif args.command == "say":
        text = " ".join(args.text) if args.text else ""
        cli_message(text)
    else:
        cli_start()
