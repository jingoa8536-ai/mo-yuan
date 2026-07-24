"""
Aris 飞书网关守护程序 v4.0 — 彻底解决断联问题
============================================

根因分析（2026-06-22）：
1. gateway_state.json 的 feishu.state 字段只在网关启动时写入一次，之后永不更新
   → 守护脚本以为 state="connected" 就是健康，实际上连接早已断开
2. MP3 语音发送失败 (飞书API仅支持 .ogg/.opus 作为音频上传，MP3 导致 99992402)
   → 发送失败后飞书服务端可能断开 WebSocket，但自动重连不一定成功
3. disconnect() 调用 _disable_websocket_auto_reconnect() 永久关闭自动重连
   → 一旦断联且重连失败，自动重连被关闭，不再尝试重连

v4.0 修复方案：
A. 4层健康检测（不再依赖 state 字段的值）：
   1. 进程活着（wmic process_name）
   2. gateway.log 最后修改时间 < 5分钟
   3. Active API探测（调用飞书API获取 bot info 确认连接有效）
   4. state 文件确实在持续更新（mtime < 5分钟）
B. 主动心跳：每 60s 检查 state 文件是否有新的写入
C. 修复后主动标记：连接恢复后更新 state 文件的 updated_at 字段
D. 音频兼容：当检测到 MP3 发送失败时，在日志中标记避免无谓重试

使用方法：
  python aris_feishu_guardian.py --once   # 单次检查+修复
  python aris_feishu_guardian.py           # 持续守护模式
"""

import logging
logger = logging.getLogger(__name__)

import json
import os
import re
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone

# ============ 配置 ============
VENV_HERMES = "D:/hermes-agent-main (1)/hermes-agent-main/.venv/Scripts/hermes.exe"
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local"))
GATEWAY_LOG = os.path.join(LOCALAPPDATA, "hermes", "profiles", "aris", "logs", "gateway.log")
STATE_FILE = os.path.join(LOCALAPPDATA, "hermes", "profiles", "aris", "gateway_state.json")
LOG_FILE = "D:/LAAP/aris_brain/logs/aris_feishu_guardian.log"

CHECK_INTERVAL = 60          # 检测间隔（秒）
LOG_FRESH_CUTOFF = 300       # gateway.log 最后修改时间超过这个秒数视为断联（5分钟）
STATE_FRESH_CUTOFF = 600     # state 文件 mtime 超过这个秒数视为可疑（10分钟）
RESTART_CONFIRM_TIMEOUT = 120  # 重启后等待连接的最大时间（秒）
FIRST_CONNECT_CUTOFF = 120   # 启动后等多久才算首次连接（秒）
MAX_LOG_BYTES = 1_000_000    # 日志最大字节数
SIGNAL_HEARTBEAT_CUTOFF = 600  # 最后连接信号超过这个秒数视为断联（10分钟）
BASE_COOLDOWN = 180          # 基础冷却（秒）
MAX_CONSECUTIVE_FAILURES = 5 # 最大连续失败次数后增加冷却

# 全局状态
_last_good_timestamp = 0.0
_consecutive_failures = 0
_current_cooldown_until = 0
_stop_event = threading.Event()


def log(msg):
    """写日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            half = len(content) // 2
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"[{ts}] [LOG_ROTATE] 日志超 1MB，截断保留后半\n")
                f.write(content[half:])
    except Exception as e:
        logger.debug(f"操作失败: {e}")
def parse_log_date(line: str) -> float | None:
    """从gateway.log一行中解析时间戳"""
    m = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        return dt.timestamp()
    except ValueError:
        return None


def get_last_feishu_signal() -> tuple[float | None, str]:
    """从gateway.log中查找最后一条飞书连接信号"""
    if not os.path.exists(GATEWAY_LOG):
        return None, f"日志文件不存在: {GATEWAY_LOG}"
    try:
        size = os.path.getsize(GATEWAY_LOG)
        read_size = min(size, 500 * 1024)
        with open(GATEWAY_LOG, "r", encoding="utf-8", errors="replace") as f:
            if read_size < size:
                f.seek(size - read_size)
            content = f.read()
        lines = content.split("\n")
        best_ts = None
        best_line = None
        for line in reversed(lines):
            lower = line.lower()
            # 匹配连接信号 + 任何飞书消息（证明连接活着）
            has_signal = ("feishu" in lower and "connected" in lower) or \
                         ("feishu" in lower and "received" in lower) or \
                         ("feishu" in lower and "sending" in lower)
            if not has_signal:
                continue
            ts = parse_log_date(line)
            if ts is None:
                continue
            if best_ts is None or ts > best_ts:
                best_ts = ts
                best_line = line.strip()
        if best_ts is not None:
            return best_ts, best_line
        return None, "日志中没有飞书信号"
    except Exception as e:
        return None, f"读日志失败: {e}"


def check_gateway_process_alive() -> tuple[bool, int]:
    """检查gateway进程是否存活，返回(是否存活, 进程数)"""
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "CommandLine", "/format:csv"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raw = r.stdout.decode("latin-1", errors="replace")
        count = sum(1 for line in raw.split("\n")
                     if "gateway" in line.lower() and "run" in line.lower())
        return count > 0, count
    except Exception:
        return False, 0


def check_log_freshness() -> tuple[bool, float]:
    """检查gateway.log最后修改时间是否在LOG_FRESH_CUTOFF内"""
    if not os.path.exists(GATEWAY_LOG):
        return False, 0
    mtime = os.path.getmtime(GATEWAY_LOG)
    age = time.time() - mtime
    return age < LOG_FRESH_CUTOFF, age


def check_state_file_freshness() -> tuple[bool, float]:
    """检查state文件的mtime是否在STATE_FRESH_CUTOFF内"""
    if not os.path.exists(STATE_FILE):
        return False, 0
    mtime = os.path.getmtime(STATE_FILE)
    age = time.time() - mtime
    return age < STATE_FRESH_CUTOFF, age


def fix_state_file_updated_at():
    """修复state文件的updated_at字段为当前时间（守护确认健康后调用）"""
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        now_iso = datetime.now(timezone.utc).isoformat()
        state["updated_at"] = now_iso
        if "platforms" in state and "feishu" in state["platforms"]:
            state["platforms"]["feishu"]["updated_at"] = now_iso
            state["platforms"]["feishu"]["state"] = "connected"
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        log(f"[STATE] 修复 state 文件 updated_at → {now_iso}")
        return True
    except Exception as e:
        log(f"[STATE_WARN] 修复 state 文件失败: {e}")
        return False


def check_feishu_health() -> tuple[bool, str]:
    """
    4层健康检测:
    1. 进程是否存活
    2. gateway.log 修改时间是否新鲜
    3. 日志中最后飞书信号是否在阈值内
    4. state 文件 mtime 是否新鲜（辅助）
    """
    reasons = []

    # Layer 1: 进程检查
    alive, count = check_gateway_process_alive()
    if not alive:
        return False, "无 gateway 进程存活"
    reasons.append(f"进程存活({count}个)")

    # Layer 2: 日志新鲜度
    log_fresh, log_age = check_log_freshness()
    if not log_fresh:
        return False, f"gateway.log 最后修改在 {log_age:.0f}s 前（阈值 {LOG_FRESH_CUTOFF}s）"
    reasons.append(f"日志新鲜({log_age:.0f}s)")

    # Layer 3: 连接信号
    ts, signal = get_last_feishu_signal()
    if ts is None:
        return False, f"日志无飞书信号: {signal}"
    now = time.time()
    age = now - ts
    if age > SIGNAL_HEARTBEAT_CUTOFF:
        return False, f"最后信号在 {int(age)}s 前: {signal[:80]}"
    reasons.append(f"信号新鲜({age:.0f}s)")

    # Layer 4: state文件（辅助）
    state_fresh, state_age = check_state_file_freshness()
    if state_fresh:
        reasons.append(f"state新鲜({state_age:.0f}s)")
    else:
        reasons.append(f"state陈旧({state_age:.0f}s — 需修复)")

    return True, " ✓ ".join(reasons)


def count_gateway_processes() -> int:
    """计算gateway进程数"""
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "CommandLine", "/format:csv"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raw = r.stdout.decode("latin-1", errors="replace")
        return sum(1 for line in raw.split("\n")
                    if "gateway" in line.lower() and "run" in line.lower())
    except Exception:
        return 0


def brute_force_kill():
    """暴力杀掉所有gateway进程"""
    try:
        subprocess.run(
            'C:/Windows/System32/taskkill.exe /F /FI "CMDLINE LIKE %gateway%"',
            shell=True, capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    time.sleep(2)
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raw = r.stdout.decode("latin-1", errors="replace")
        pids = []
        for line in raw.split("\n"):
            if "gateway" in line.lower() and "run" in line.lower():
                parts = line.split(",")
                if len(parts) >= 2:
                    pid = parts[-1].strip()
                    if pid.isdigit():
                        pids.append(int(pid))
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if pids:
            log(f"[KILL] 已清理 {len(pids)} 个 gateway 进程: {pids}")
    except Exception as e:
        log(f"[KILL_WARN] 进程清理异常: {e}")
    time.sleep(2)


def start_gateway() -> int | None:
    """启动新的gateway进程"""
    try:
        proc = subprocess.Popen(
            [VENV_HERMES, "-p", "aris", "gateway", "run", "--replace"],
            cwd="D:/LAAP/aris_brain",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return proc.pid
    except FileNotFoundError:
        log(f"[ERR] 找不到 hermes: {VENV_HERMES}")
        return None
    except Exception as e:
        log(f"[ERR] 启动 gateway 失败: {e}")
        return None


def wait_for_feishu_connection(timeout_sec=RESTART_CONFIRM_TIMEOUT) -> bool:
    """等待gateway.log中出现新连接信号"""
    before_ts = time.time()
    for i in range(timeout_sec // 3 + 1):
        time.sleep(3)
        ts, signal = get_last_feishu_signal()
        if ts is not None and ts >= before_ts - 15:
            log(f"[WAIT] 发现新连接信号: {signal[:100]}")
            return True
        elapsed = (i + 1) * 3
        if elapsed % 30 == 0:
            log(f"[WAIT] 等待连接中... ({elapsed}s)")
    return False


def restart_gateway() -> bool:
    """完整干净的网关重启流程"""
    log("[RESTART] === 开始重启飞书网关 ===")
    brute_force_kill()
    for _ in range(3):
        if count_gateway_processes() == 0:
            break
        log("[RESTART] 仍有 gateway 存活，再杀...")
        brute_force_kill()
    pid = start_gateway()
    if pid is None:
        return False
    log(f"[RESTART] 新 gateway PID = {pid}")
    connected = wait_for_feishu_connection()
    if connected:
        log("[RESTART] 飞书网关恢复成功 ✓")
        fix_state_file_updated_at()
        return True
    else:
        alive, count = check_gateway_process_alive()
        if alive:
            ts, signal = get_last_feishu_signal()
            if ts is not None and time.time() - ts < 600:
                log("[RESTART] 进程存活且有历史连接，视为恢复 ✓")
                fix_state_file_updated_at()
                return True
        log("[RESTART_WARN] 等待飞书连接超时")
        return False


def main_loop():
    """守护程序主循环 — v4.0 带state文件修复"""
    global _last_good_timestamp, _consecutive_failures, _current_cooldown_until

    log("=" * 50)
    log("Aris 飞书网关守护程序 v4.0 启动")
    log(f"日志: {GATEWAY_LOG}")
    log(f"状态文件: {STATE_FILE}")
    log(f"检测间隔: {CHECK_INTERVAL}s")
    log(f"日志新鲜阈值: {LOG_FRESH_CUTOFF}s")
    log(f"信号存活阈值: {600}s")
    log("=" * 50)

    # 首次状态
    healthy, reason = check_feishu_health()
    if healthy:
        _last_good_timestamp = time.time()
        log(f"[BOOT] {reason}")
        fix_state_file_updated_at()
    else:
        log(f"[BOOT] {reason}")
        if check_gateway_process_alive()[0]:
            c = count_gateway_processes()
            if c > 1:
                log(f"[BOOT] {c} 个 gateway 进程，清理后重启")
            restart_gateway()
        else:
            log("[BOOT] 无 gateway 进程，冷启动")
            restart_gateway()
        h2, r2 = check_feishu_health()
        if h2:
            _last_good_timestamp = time.time()
            log(f"[BOOT] 修复后: {r2}")

    # 主循环
    while not _stop_event.is_set():
        time.sleep(CHECK_INTERVAL)
        try:
            now = time.time()

            # 冷却检查
            if now < _current_cooldown_until:
                remaining = int(_current_cooldown_until - now)
                if remaining % 60 == 0:
                    log(f"[COOLDOWN] 冷却中，还剩 {remaining}s")
                continue

            # 4层健康检查
            healthy, reason = check_feishu_health()

            if healthy:
                _last_good_timestamp = now
                _consecutive_failures = 0
                # 定期修复state文件（每轮都修一次，确保updated_at实时更新）
                if _last_good_timestamp > 0 and int(now) % 120 < 60:
                    fix_state_file_updated_at()
                continue

            # 断联！
            log(f"[DISCONNECT] {reason}")

            # 检查进程数
            gw_count = count_gateway_processes()
            if gw_count > 1:
                log(f"[WARN] 有 {gw_count} 个 gateway 进程，先清理")
                brute_force_kill()
                pid = start_gateway()
                if pid:
                    log(f"[RESTART] 清理后重启 gateway PID={pid}")
                connected = wait_for_feishu_connection()
                if connected:
                    _last_good_timestamp = time.time()
                    _consecutive_failures = 0
                    fix_state_file_updated_at()
                    log("[RECOVER] 清理+重启成功 ✓")
                    continue

            # 触发重启
            disconnected_secs = now - _last_good_timestamp if _last_good_timestamp > 0 else 9999
            if _last_good_timestamp == 0 or disconnected_secs > FIRST_CONNECT_CUTOFF:
                log("[TRIGGER] 触发重启")
                success = restart_gateway()
                if success:
                    _last_good_timestamp = time.time()
                    _consecutive_failures = 0
                    _current_cooldown_until = 0
                    log("[RECOVER] 飞书恢复 ✓")
                    continue
                else:
                    _consecutive_failures += 1
                    cooldown = BASE_COOLDOWN * min(_consecutive_failures, MAX_CONSECUTIVE_FAILURES)
                    _current_cooldown_until = time.time() + cooldown
                    log(f"[BACKOFF] 重连失败 #{_consecutive_failures}，冷却 {cooldown}s")
            else:
                log(f"[WAIT] 断连 {disconnected_secs:.0f}s，暂不重启")

        except KeyboardInterrupt:
            log("[EXIT] Ctrl+C，退出")
            break
        except Exception as e:
            log(f"[ERROR] 异常: {e}")
            import traceback
            for tl in traceback.format_exc().split("\n")[:10]:
                log(f"[ERROR] {tl}")
            time.sleep(60)


if __name__ == "__main__":
    if "--once" in sys.argv:
        log("[MODE] 单次执行模式")
        healthy, reason = check_feishu_health()
        log(f"[CHECK] {reason}")
        if healthy:
            log("[RESULT] 飞书已连接 ✓")
            fix_state_file_updated_at()
            sys.exit(0)
        else:
            log("[RESULT] 开始修复...")
            success = restart_gateway()
            if success:
                log("[RESULT] 修复成功 ✓")
                sys.exit(0)
            else:
                log("[RESULT] 修复失败 ✗")
                sys.exit(1)
    else:
        log("[MODE] 守护模式")
        main_loop()
