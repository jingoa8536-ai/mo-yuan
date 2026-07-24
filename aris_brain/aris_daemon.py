"""
Aris Daemon v7 — 永不中断常驻守护进程（加固版）
=====================================================
双层守护体系：
  外层 daemon.py（本文件）→ 15s 轮询 watchdog
  内层 watchdog.py → 15s 自愈 7 个进程
  本脚本永不退出，Python 原生实现，无路径兼容问题

用法:
  python aris_daemon.py          # 常驻监控（开机自启用）
  python aris_daemon.py status   # 单次状态检查
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, subprocess, socket
from pathlib import Path
from datetime import datetime

BRAIN_DIR = Path("D:/LAAP/aris_brain")
VENV_PYTHON = Path("D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/python.exe")
HERMES_CLI = Path("D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/hermes.exe")
ARIS_DIR = Path(os.environ.get("USERPROFILE", "C:/Users/user")) / ".aris"
LOG_FILE = BRAIN_DIR / "logs" / "aris_daemon.log"
CHECK_INTERVAL = 15  # seconds

ARIS_DIR.mkdir(parents=True, exist_ok=True)
(BRAIN_DIR / "logs").mkdir(parents=True, exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {msg}"
    logger.info(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logger.debug(f"操作失败: {e}")
def find_process(keyword: str) -> bool:
    """用 wmic 检测某个关键词的 python 进程是否存活（同时检测 python.exe 和 pythonw.exe）"""
    for exe_name in ['python.exe', 'pythonw.exe']:
        try:
            r = subprocess.run(
                ['wmic', 'process', 'where', f"name='{exe_name}'", 'get', 'CommandLine', '/format:csv'],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if keyword.lower() in r.stdout.lower():
                return True
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return False


def is_watchdog_alive() -> bool:
    return find_process("watchdog")


def is_gateway_alive() -> bool:
    """检测gateway是否存活—进程名 + 端口双重确认"""
    # 进程名检测
    if find_process("gateway"):
        # 再确认feishu gateway的内部端口(:10002)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            r = s.connect_ex(("127.0.0.1", 10002))
            s.close()
            return r == 0
        except:
            return True  # 有进程就行，端口可能还没绑定
    return False


def is_stack_alive() -> bool:
    """检测任意核心进程存活"""
    for keyword in ['gateway', 'watchdog', 'psi_server', 'xiaozhi', 'v11_agi']:
        if find_process(keyword):
            return True
    return False


def cleanup_stale_files():
    """清理老的 gateway 锁文件"""
    appdata = os.environ.get("LOCALAPPDATA", "")
    if not appdata:
        return
    for fp in [
        f"{appdata}\\hermes\\gateway.lock",
        f"{appdata}\\hermes\\gateway.pid",
        f"{appdata}\\hermes\\gateway_state.json",
        f"{appdata}\\hermes\\profiles\\aris\\gateway.lock",
        f"{appdata}\\hermes\\profiles\\aris\\gateway.pid",
        f"{appdata}\\hermes\\profiles\\aris\\gateway_state.json",
    ]:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
def cleanup_stale_gateways():
    """暴力清理所有gateway进程（python.exe + pythonw.exe），确保端口释放"""
    try:
        # 用 wmic 找到所有 gateway 进程（包括隐藏窗口的 pythonw.exe）
        for exe_name in ['python.exe', 'pythonw.exe']:
            r = subprocess.run(
                ['wmic', 'process', 'where', f"name='{exe_name}'", 'get', 'ProcessId,CommandLine', '/format:csv'],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in r.stdout.split('\n'):
                if 'gateway' not in line.lower():
                    continue
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    pid = parts[-1].strip()
                    if pid.isdigit():
                        subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                       capture_output=True, timeout=5)
                        log(f"  清理旧gateway PID={pid}")
        # 等端口彻底释放
        for _ in range(5):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            r = s.connect_ex(("127.0.0.1", 10002))
            s.close()
            if r != 0:
                break  # 端口已释放
            time.sleep(2)
    except Exception as e:
        logger.debug(f"操作失败: {e}")
def boot_stack():
    """直接启动 watchdog（它会负责拉起全部 7 个进程），用绝对 venv python"""
    log("启动堆栈...")
    cleanup_stale_files()
    cleanup_stale_gateways()  # <-- 先杀光旧gateway，确保端口释放
    time.sleep(2)

    # 先确保 PSI 核心在跑（standalone daemon）
    if not find_process("pi_psi_server"):
        log("  启动 Rust PSI Core...")
        try:
            subprocess.Popen(
                [str(VENV_PYTHON), "-u", str(BRAIN_DIR / "pi_psi_server.py"), "11529"],
                cwd=str(BRAIN_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            log("  PSI Core 已启动")
        except Exception as e:
            log(f"  PSI Core 启动失败: {e}")

    # 启动 watchdog（start 模式 = 首次启动所有进程 + 持续监控）
    log("  启动 Watchdog (start 模式)...")
    try:
        subprocess.Popen(
            [str(VENV_PYTHON), "-u", str(BRAIN_DIR / "aris_watchdog.py"), "start"],
            cwd=str(BRAIN_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log("  Watchdog 已启动")
    except Exception as e:
        log(f"  Watchdog 启动失败: {e}")

    # 等待 gateway 真正上线（最多 30 秒）
    log("  等待 Gateway 上线...")
    for i in range(15):
        time.sleep(2)
        if is_gateway_alive():
            log(f"  Gateway 上线成功 ({i*2+2}s)")
            break
    else:
        log("  WARNING: Gateway 未能在 30 秒内上线")

    log("堆栈启动完成")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        alive = is_stack_alive()
        logger.info(f"Daemon status: {'ALIVE' if alive else 'DEAD'}")
        logger.info(f"Watchdog: {'OK' if is_watchdog_alive() else 'DOWN'}")
        logger.info(f"Gateway: {'OK' if is_gateway_alive() else 'DOWN'}")
        return

    log("=" * 50)
    log("Aris 常驻守护进程 v7 启动")
    log(f"检查间隔: {CHECK_INTERVAL}s")
    log(f"Ven Python: {VENV_PYTHON}")
    log("=" * 50)

    # 首次启动
    log("首次冷启动...")
    cleanup_stale_files()
    boot_stack()
    log("首次启动完成，进入常驻监控循环")

    retry_count = 0
    while True:
        try:
            # 重点检查 gateway 是否在线（飞书连接）
            gateway_ok = is_gateway_alive()
            stack_ok = is_stack_alive()

            if gateway_ok and stack_ok:
                retry_count = 0
            elif not gateway_ok and stack_ok:
                # gateway 单独掉线了，但其他进程还在——主动重启 gateway
                retry_count += 1
                log(f"Gateway 掉线 (#{retry_count})，主动重启...")
                cleanup_stale_gateways()
                time.sleep(2)
                # 重新启动 watchdog（stop 再 start）
                subprocess.run(
                    [str(VENV_PYTHON), "-u", str(BRAIN_DIR / "aris_watchdog.py"), "stop"],
                    capture_output=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                time.sleep(3)
                # watchdog start 会重新拉起所有进程
                subprocess.Popen(
                    [str(VENV_PYTHON), "-u", str(BRAIN_DIR / "aris_watchdog.py"), "start"],
                    cwd=str(BRAIN_DIR),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                log("  Watchdog 已重启")
                # 等待 gateway 上线
                for i in range(10):
                    time.sleep(3)
                    if is_gateway_alive():
                        log(f"  Gateway 重新上线 ({i*3+3}s)")
                        retry_count = 0
                        break
                else:
                    log("  重连失败，进入冷却")
                    if retry_count >= 3:
                        time.sleep(60)
            else:
                retry_count += 1
                log(f"堆栈无响应 (#{retry_count})，重启...")
                boot_stack()
                time.sleep(15)
                if is_stack_alive():
                    log("重启成功")
                    retry_count = 0
                else:
                    log("重启失败")
                    if retry_count >= 3:
                        log("连续3次失败，等待60秒")
                        time.sleep(60)
        except Exception as e:
            log(f"监控循环异常: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("用户终止")
    except Exception as e:
        log(f"异常退出: {e}")
        raise
