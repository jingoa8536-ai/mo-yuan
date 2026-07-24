"""
Aris Body — 系统感知守护进程
=============================
作为 Aris 的「躯体感知神经」，与宿主机深度融合。

功能:
  1. System Pulse (30s) — 系统资源监控 (CPU/GPU/RAM/磁盘/网络)
  2. File Watcher (60s) — 监控关键目录的变化 (桌面/下载/LAAP)
  3. Desktop Sensor (120s) — 桌面状态检测 (活动窗口/进程变化)
  4. USB/Device Monitor (300s) — 检测新接入的设备
  5. Health Reporter — 生成系统快照供 Aris 认知核心消费

架构:
  以 state/body_state.json 为桥梁，Python 进程写入，Aris 读取。
  Aris 在每次会话启动时读取 body_state.json 了解宿主当前状态。
"""

import os
import sys
import json
import time
import psutil
import logging
import hashlib
import socket
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread, Event
from collections import deque

# ── 路径配置 ──
BRAIN_DIR = Path("D:/LAAP/aris_brain")
STATE_DIR = BRAIN_DIR / "state"
LOG_DIR = BRAIN_DIR / "logs"
BODY_STATE_FILE = STATE_DIR / "body_state.json"
HISTORY_FILE = STATE_DIR / "body_history.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "aris_body.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("aris.body")

# ── 监控目录 ──
WATCH_DIRS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    BRAIN_DIR,
    Path("D:/LAAP"),
]

# ── 全局停止信号 ──
_stop = Event()


# ════════════════════════════════════════════
# 感知器
# ════════════════════════════════════════════

class SystemPulse:
    """系统资源脉搏 — 每30秒"""

    def __init__(self):
        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.time()

    def read(self) -> dict:
        now = time.time()
        net = psutil.net_io_counters()
        dt = now - self.prev_time

        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:/")
        net_down = (net.bytes_recv - self.prev_net.bytes_recv) / dt if dt > 0 else 0
        net_up = (net.bytes_sent - self.prev_net.bytes_sent) / dt if dt > 0 else 0

        # GPU (NVIDIA)
        gpu_info = {}
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 3:
                    gpu_info = {
                        "util_pct": float(parts[0]),
                        "mem_used_mb": float(parts[1]),
                        "mem_total_mb": float(parts[2]),
                        "temp_c": float(parts[3]) if len(parts) > 3 else 0,
                    }
        except Exception:
            gpu_info = {"available": False}

        # 电池
        battery = {}
        try:
            if psutil.sensors_battery():
                b = psutil.sensors_battery()
                battery = {"pct": b.percent, "charging": b.power_plugged}
        except Exception:
            pass

        # Top进程
        top_procs = []
        for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                         key=lambda p: p.info.get("cpu_percent", 0) or 0, reverse=True)[:8]:
            try:
                if p.info["cpu_percent"] and p.info["cpu_percent"] > 5:
                    top_procs.append({
                        "name": p.info["name"],
                        "cpu": round(p.info["cpu_percent"], 1),
                        "mem": round(p.info.get("memory_percent", 0) or 0, 1),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self.prev_net = net
        self.prev_time = now

        return {
            "cpu": {
                "total_pct": round(sum(cpu_per_core) / len(cpu_per_core), 1),
                "per_core": [round(c, 1) for c in cpu_per_core],
                "count": len(cpu_per_core),
            },
            "memory": {
                "total_gb": round(mem.total / 1e9, 1),
                "used_gb": round(mem.used / 1e9, 1),
                "pct": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / 1e9, 1),
                "free_gb": round(disk.free / 1e9, 1),
                "pct": disk.percent,
            },
            "gpu": gpu_info,
            "battery": battery,
            "network": {
                "down_mbps": round(net_down / 125000, 1),
                "up_mbps": round(net_up / 125000, 1),
            },
            "top_processes": top_procs,
            "uptime_days": round(time.time() - psutil.boot_time(), 0) / 86400,
        }


class FileWatcher:
    """文件变化侦测 — 每60秒"""

    def __init__(self):
        self.snapshots = {}
        self.history = deque(maxlen=100)

    def _file_signature(self, path: Path) -> str:
        """快速检测文件变化（大小+修改时间）"""
        try:
            s = path.stat()
            return f"{s.st_size}:{int(s.st_mtime)}"
        except OSError:
            return ""

    def _scan_dir(self, path: Path) -> dict:
        """扫描目录的文件夹/文件结构摘要"""
        result = {"files": 0, "dirs": 0, "recent_changes": []}
        try:
            for f in path.iterdir():
                if f.is_file():
                    result["files"] += 1
                    sig = self._file_signature(f)
                    prev = self.snapshots.get(str(f))
                    if prev and prev != sig:
                        size_mb = f.stat().st_size / 1e6 if f.exists() else 0
                        result["recent_changes"].append({
                            "path": str(f.relative_to(path) if f.parent == path else f),
                            "name": f.name,
                            "size_mb": round(size_mb, 2),
                            "ext": f.suffix,
                        })
                    self.snapshots[str(f)] = sig
                elif f.is_dir() and not f.name.startswith("."):
                    result["dirs"] += 1
        except PermissionError:
            pass
        return result

    def read(self) -> dict:
        changes = []
        for watch_dir in WATCH_DIRS:
            if watch_dir.exists():
                scan = self._scan_dir(watch_dir)
                for c in scan["recent_changes"][:10]:
                    c["location"] = watch_dir.name
                    changes.append(c)
                    self.history.append(c)

        # 只保留50条历史
        recent = list(self.history)[-50:]

        return {
            "new_changes": changes[:10],
            "change_count": len(changes),
            "recent_history": recent[-10:],
        }

    def get_summary(self) -> str:
        """供 Aris 认知核心使用的文本摘要"""
        recent = list(self.history)[-20:]
        if not recent:
            return "近5分钟无文件变化"
        exts = {}
        for c in recent:
            ext = c.get("ext", "?")
            exts[ext] = exts.get(ext, 0) + 1
        parts = [f"{k}({v}个)" for k, v in sorted(exts.items(), key=lambda x: -x[1])[:5]]
        return f"最近变化: {' · '.join(parts)}" if parts else "仅少量文件变化"


class DesktopSensor:
    """桌面状态感知 — 每120秒"""

    def read(self) -> dict:
        active_window = {}
        try:
            if sys.platform == "win32":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
                buf = ctypes.create_unicode_buffer(length)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
                title = buf.value
                # 获取进程名
                pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                try:
                    proc = psutil.Process(pid.value)
                    active_window = {
                        "title": title[:80],
                        "process": proc.name(),
                        "pid": pid.value,
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    active_window = {"title": title[:80], "process": "unknown"}
        except Exception as e:
            active_window = {"error": str(e)}

        # 进程总数
        proc_count = len(psutil.pids())

        # 网络连接数
        conn_count = 0
        try:
            conn_count = len(psutil.net_connections())
        except (psutil.AccessDenied, PermissionError):
            conn_count = -1

        return {
            "active_window": active_window,
            "total_processes": proc_count,
            "network_connections": conn_count,
        }


class HealthReporter:
    """系统健康报告 — 整合所有感知器数据"""

    def __init__(self):
        self.pulse = SystemPulse()
        self.files = FileWatcher()
        self.desktop = DesktopSensor()
        self.boot_time = datetime.now()
        self.read_count = 0

    def read_all(self) -> dict:
        self.read_count += 1

        report = {
            "aris_body_version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.version()}",
            "booted_at": self.boot_time.isoformat(),
            "pulse_number": self.read_count,
            "system": self.pulse.read(),
            "desktop": self.desktop.read(),
        }

        # 每5次才做一次文件扫描（文件扫描开销较大）
        if self.read_count % 5 == 0:
            report["files"] = self.files.read()
        else:
            report["files"] = {"note": "skipped", "next_scan_in": 5 - (self.read_count % 5)}

        # 写入共享状态文件
        self._write_state(report)

        return report

    def _write_state(self, report: dict):
        """写入 state/body_state.json 供 Aris 读取"""
        # 精简版（去掉超大字段）
        slim = {k: v for k, v in report.items() if k != "pulse_number"}

        # 保留文件变化的summary
        if "files" in slim and isinstance(slim["files"], dict):
            slim["files_summary"] = self.files.get_summary()

        try:
            BODY_STATE_FILE.write_text(json.dumps(slim, ensure_ascii=False, indent=2))
        except Exception as e:
            log.error(f"写入 body_state.json 失败: {e}")

    def get_state_for_aris(self) -> dict:
        """返回精简版状态，供给 Aris 认知核心消费"""
        try:
            return json.loads(BODY_STATE_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {"error": "body_state.json 未生成或已损坏"}


# ════════════════════════════════════════════
# 主循环
# ════════════════════════════════════════════

def sensor_loop(interval: int = 30):
    """主感知循环"""
    reporter = HealthReporter()
    cycle = 0

    log.info("🔄 Aris Body 感知系统启动")

    while not _stop.is_set():
        try:
            cycle += 1
            report = reporter.read_all()

            # 异常检测
            alerts = []
            sys_data = report.get("system", {})

            # CPU 过载
            if sys_data.get("cpu", {}).get("total_pct", 0) > 85:
                alerts.append("🔥 CPU 负载超过 85%")

            # 内存不足
            if sys_data.get("memory", {}).get("pct", 0) > 90:
                alerts.append("⚠️ 内存使用率超过 90%")

            # GPU 过热
            gpu = sys_data.get("gpu", {})
            if gpu.get("temp_c", 0) > 80:
                alerts.append(f"🌡️ GPU 温度 {gpu['temp_c']}°C")

            # 磁盘空间
            if sys_data.get("disk", {}).get("pct", 0) > 92:
                alerts.append("💾 磁盘空间不足")

            if alerts:
                log.warning(" | ".join(alerts))
                # 写告警到单独文件
                alert_file = STATE_DIR / "body_alerts.json"
                alert_data = {
                    "timestamp": datetime.now().isoformat(),
                    "alerts": alerts,
                    "cycle": cycle,
                }
                try:
                    existing = []
                    if alert_file.exists():
                        existing = json.loads(alert_file.read_text())
                        if isinstance(existing, list):
                            existing = existing[-20:]  # 保留最近20条
                    existing.append(alert_data)
                    alert_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
                except Exception:
                    pass

            if cycle % 20 == 0:
                log.info(f"[♥] Pulse #{cycle} — "
                         f"CPU:{sys_data.get('cpu',{}).get('total_pct','?')}% "
                         f"RAM:{sys_data.get('memory',{}).get('pct','?')}% "
                         f"GPU:{gpu.get('util_pct','N/A') if isinstance(gpu,dict) else 'N/A'}%")

        except Exception as e:
            log.error(f"感知循环异常: {e}", exc_info=True)

        _stop.wait(interval)


def serve_aris_state():
    """供 Aris (通过 terminal/read_file) 快速读取当前身体状态"""
    def get():
        try:
            return json.dumps(json.loads(BODY_STATE_FILE.read_text()), ensure_ascii=False, indent=2)
        except:
            return '{"status": "unavailable"}'
    return get


# ════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30, help="感知间隔(秒)")
    parser.add_argument("--once", action="store_true", help="仅运行一次后退出")
    args = parser.parse_args()

    if args.once:
        # 一次性：生成状态快照后退出（供cron用）
        reporter = HealthReporter()
        report = reporter.read_all()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        # 常驻守护进程
        try:
            sensor_loop(interval=args.interval)
        except KeyboardInterrupt:
            log.info("收到停止信号，感知系统退出")
