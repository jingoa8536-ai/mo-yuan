#!/usr/bin/env python3
"""
Aris Feishu 网关看门狗 — 定期检查网关存活，死了自动重启
===========================================================
由 Herems cron 每 5 分钟调用一次。
当检测到网关进程已死 → 自动重启。
"""

import logging

import json, os, sys, time, subprocess, logging
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────
HERMES_HOME = Path(os.environ.get(
    "HERMES_HOME",
    os.path.join(os.environ.get("USERPROFILE", "C:\\Users\\user"),
                 "AppData\\Local\\hermes")
))

PROFILE = "aris"
STATE_FILE = HERMES_HOME / "profiles" / PROFILE / "gateway_state.json"
LOG_FILE = HERMES_HOME / "gateway-stderr.log"
HERMES_BIN = os.path.join(
    "D:\\hermes-agent-main (1)\\hermes-agent-main\\.venv\\Scripts\\hermes"
)

STARTUP_DIR = Path("D:\\LAAP\\aris_brain")
STARTUP_BAT = STARTUP_DIR / "ArisAGI_startup.bat"

# 日志
LOG_DIR = Path(os.path.expanduser("~/.aris"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Watchdog] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("feishu_watchdog")


def get_gateway_pid() -> int | None:
    """从状态文件读取网关 PID。"""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        pid = state.get("pid")
        if pid:
            return int(pid)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError) as e:
        logger.debug(f"操作失败: {e}")
    return None


def is_process_alive(pid: int) -> bool:
    """检查 Windows 进程是否存活。"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        # 回退到 tasklist
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True, timeout=5
            )
            return str(pid) in result.stdout
        except Exception:
            return False


def is_gateway_healthy() -> bool:
    """综合判断网关是否活着。"""
    pid = get_gateway_pid()
    if pid is None:
        logger.warning(f"  状态文件无有效 PID")
        return False

    if not is_process_alive(pid):
        logger.warning(f"  PID {pid} 进程已死")
        return False

    # 检查最近是否有连续崩溃
    try:
        if LOG_FILE.exists():
            log_text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            # 最近 100 行内的 Fatal/Error
            recent_lines = log_text.splitlines()[-100:]
            fatal_count = sum(1 for l in recent_lines if "FATAL" in l or "CRITICAL" in l)
            if fatal_count >= 5:
                logger.warning(f"  最近 100 行日志有 {fatal_count} 条致命错误，标记为不健康")
                return False
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return True


def restart_gateway():
    """重启 Hermes 网关。"""
    logger.info("🔄 正在重启 Feishu 网关...")

    # 方法1: 用 hermes gateway run --replace
    try:
        subprocess.run(
            [HERMES_BIN, "gateway", "run", "--replace"],
            cwd=str(STARTUP_DIR),
            timeout=30,
            capture_output=True, text=True
        )
        logger.info("  hermes gateway run --replace 完成")
        return True
    except subprocess.TimeoutExpired:
        logger.warning("  hermes gateway 启动超时(30s)，可能在后台运行中")
        # 超时可能意味着它成功启动了但没退出
        return True
    except Exception as e:
        logger.error(f"  hermes gateway 启动失败: {e}")

    # 方法2: 回退到 startup.bat 方式
    logger.info("  ⚠ 尝试回退方案: 调用 startup.bat")
    try:
        subprocess.Popen(
            ["wscript.exe", str(STARTUP_DIR / "ArisAGI_startup.vbs")],
            cwd=str(STARTUP_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info("  已通过 VBS 触发启动")
        return True
    except Exception as e:
        logger.error(f"  回退方案也失败: {e}")

    return False


def wait_for_gateway(timeout: int = 30):
    """等待网关启动并连上飞书。"""
    logger.info(f"  等待网关就绪（最长 {timeout}s）...")
    for i in range(timeout):
        time.sleep(1)
        pid = get_gateway_pid()
        if pid and is_process_alive(pid):
            # 检查飞书状态
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                feishu = state.get("platforms", {}).get("feishu", {})
                if feishu.get("state") == "connected":
                    logger.info(f"  ✅ 飞书网关已就绪 (PID {pid}, 飞书已连接)")
                    return True
                else:
                    feishu_state = feishu.get("state", "unknown")
                    logger.info(f"  飞书状态: {feishu_state} (PID {pid}) — 等待中...")
            except Exception:
                logger.info(f"  等待状态文件更新... ({i+1}s)")
        else:
            logger.info(f"  等待进程产生... ({i+1}s)")
    return False


def main():
    logger.info("🔍 检查 Feishu 网关状态...")

    if is_gateway_healthy():
        pid = get_gateway_pid()
        logger.info(f"  ✅ 网关健康 (PID {pid})，无需操作")
        return 0

    # 不健康 → 重启
    logger.warning("  ⚠️  网关不健康，准备重启")

    if not restart_gateway():
        logger.error("  ❌ 所有重启方案失败！")
        return 1

    # 等待就绪
    if wait_for_gateway(timeout=45):
        logger.info("  ✅ 看门狗完成，网关已恢复")
        return 0
    else:
        logger.warning("  ⚠️  网关已启动但飞书尚未连接（可能还需时间）")
        return 0


if __name__ == "__main__":
    sys.exit(main())
