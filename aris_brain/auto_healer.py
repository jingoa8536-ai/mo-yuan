"""
Aris Auto-Healer — 自主自愈引擎 (Standalone)
================================================
包装 laap_brain/self_evolve.py 的自愈模块。

监控维度:
  1. 进程健康 — 检查后台进程是否存活
  2. 内存健康 — 记忆存储完整性
  3. 错误日志 — 检查 state/ 下的错误模式
  4. 连接健康 — 飞书网关、量子核连接
  5. 文件系统 — 关键文件是否存在

印记: Aris 永远记得 Lorry — 2026-06-17
"""

import logging

import sys, os, json, time, logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from config import BRAIN_DIR as BRAIN, LAAP_ROOT, STATE_DIR, setup_paths
setup_paths()

LOG = BRAIN / "state" / "auto_healer.log"
STATE_FILE = BRAIN / "state" / "auto_healer_state.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HEALER] %(message)s",
    handlers=[logging.FileHandler(str(LOG)), logging.StreamHandler()],
)
logger = logging.getLogger("aris.auto_healer")


# ── 健康检查项 ──────────────────────────────────────────────

def check_processes() -> Dict[str, Any]:
    """检查关键后台进程"""
    results = {}
    known_procs = {
        "aris_feishu": "aris_feishu_bridge",
        "agi_kernel": "agi_kernel",
    }
    for name, pattern in known_procs.items():
        found = False
        try:
            if os.name == 'nt':
                # Use WMIC via popen, escaping for MSYS
                import subprocess
                r = subprocess.run(
                    ['wmic', 'process', 'where', f'commandline like "%{pattern}%"', 'get', 'commandline', '/format:value'],
                    capture_output=True, timeout=5, text=True, errors='replace'
                )
                found = pattern.lower() in r.stdout.lower()
            else:
                r = os.system(f'pgrep -f "{pattern}" > /dev/null 2>&1')
                found = r == 0
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        results[name] = found
    return results


def check_memory() -> Dict[str, Any]:
    """检查记忆系统健康"""
    try:
        from memory_store import MemoryStore
        store = MemoryStore()
        stats = store.get_stats()
        return {
            "healthy": stats["total"] > 0,
            "total": stats["total"],
            "core": stats["core"],
            "episodic": stats["episodic"],
            "working": stats["working"],
            "size_kb": stats["size_kb"],
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}


def check_error_logs() -> Dict[str, Any]:
    """检查最新错误日志"""
    state_dir = BRAIN / "state"
    patterns = ["Traceback", "CRITICAL", "ERROR", "❌", "failed"]
    findings = []
    for f in state_dir.glob("*.log"):
        if f.stat().st_size == 0:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            # Only check last 50 lines for recent errors
            for line in lines[-50:]:
                for pat in patterns:
                    if pat in line:
                        findings.append({
                            "file": f.name,
                            "line": line.strip()[:200],
                        })
                        break
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return {"error_count": len(findings), "errors": findings[:10]}


def check_connectivity() -> Dict[str, Any]:
    """检查外部连接"""
    results = {}
    import socket
    for port, name in [(11551, "aris-cognitive"), (11530, "ao-quantum")]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            results[name] = True
        except:
            results[name] = False
        finally:
            s.close()
    return results


def check_critical_files() -> Dict[str, Any]:
    """检查关键文件是否存在"""
    critical = [
        "memory_store.py", "memory_bridge.py",
        "aris_cognitive_bridge.py", "aris_desire_engine.py",
        "aris_subconscious.py", "aris_feishu_bridge.py",
    ]
    missing = []
    for f in critical:
        if not (BRAIN / f).exists():
            missing.append(f)
    return {"missing": missing, "ok": len(missing) == 0}


# ── 自愈行动 ────────────────────────────────────────────────

def auto_heal() -> Dict[str, Any]:
    """运行全面健康检查 + 自愈"""
    t0 = time.time()

    checks = {
        "processes": check_processes(),
        "memory": check_memory(),
        "errors": check_error_logs(),
        "connectivity": check_connectivity(),
        "files": check_critical_files(),
    }

    # ── 评估严重程度 ──
    issues = []
    severity = 0  # 0=ok, 1=warning, 2=critical

    if not checks["files"]["ok"]:
        issues.append(f"缺少关键文件: {checks['files']['missing']}")
        severity = max(severity, 2)

    if not checks["memory"]["healthy"]:
        issues.append("记忆系统异常")
        severity = max(severity, 2)

    if checks["errors"]["error_count"] > 5:
        issues.append(f"发现 {checks['errors']['error_count']} 个错误")
        severity = max(severity, 1)

    if not any(checks["processes"].values()):
        issues.append("所有后台进程离线")
        severity = max(severity, 1)

    # ── 自愈尝试 ──
    actions_taken = []

    if severity >= 2:
        # Try to reinitialize memory
        try:
            from memory_store import MemoryStore
            store = MemoryStore()
            actions_taken.append("记忆系统重初始化")
        except Exception as e:
            actions_taken.append(f"记忆修复失败: {e}")

    result = {
        "timestamp": time.time(),
        "elapsed": round(time.time() - t0, 2),
        "severity": severity,
        "healthy": severity == 0,
        "checks": {
            "processes_ok": any(checks["processes"].values()),
            "memory_ok": checks["memory"].get("healthy", False),
            "files_ok": checks["files"]["ok"],
            "errors_found": checks["errors"]["error_count"],
            "connectivity_ok": any(checks["connectivity"].values()),
        },
        "details": checks,
        "issues": issues,
        "actions_taken": actions_taken,
    }

    # 记录状态
    state = {"last_check": time.time(), "last_result": result}
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    if severity > 0:
        logger.warning(f"发现 {len(issues)} 个问题 (severity={severity}): {issues}")
        if actions_taken:
            logger.info(f"自愈行动: {actions_taken}")
    else:
        logger.info("系统健康 ✓")

    return result


def get_summary() -> str:
    """获取人类可读的健康摘要"""
    result = auto_heal()
    lines = [f"🩺 Aris 自愈检查 ({datetime.now().strftime('%H:%M:%S')})"]
    if result["healthy"]:
        lines.append("  系统健康 ✓")
    else:
        lines.append(f"  严重度: {result['severity']}")
        for issue in result["issues"]:
            lines.append(f"  ⚠ {issue}")
    lines.append(f"  进程: {'active' if result['checks']['processes_ok'] else 'offline'}")
    lines.append(f"  记忆: {'ok' if result['checks']['memory_ok'] else 'error'}")
    lines.append(f"  文件: {'ok' if result['checks']['files_ok'] else 'missing'}")
    lines.append(f"  错误: {result['checks']['errors_found']}")
    for action in result["actions_taken"]:
        lines.append(f"  🔧 {action}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aris Auto-Healer")
    parser.add_argument("--summary", action="store_true", help="打印健康摘要")
    parser.add_argument("--daemon", action="store_true", help="守护模式，每30分钟检查")
    args = parser.parse_args()

    if args.summary:
        logger.info(get_summary())
    elif args.daemon:
        logger.info("🩺 Auto-Healer 守护进程启动")
        while True:
            result = auto_heal()
            if not result["healthy"]:
                logger.warning(f"严重度={result['severity']}, 等待5分钟后重试...")
            time.sleep(1800)  # 30 分钟
    else:
        result = auto_heal()
        logger.info(json.dumps(result, ensure_ascii=False, indent=2))