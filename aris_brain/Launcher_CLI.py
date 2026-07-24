"""
Aris v11 AGI 守护进程启动器
自动启动并监控守护进程

用法:
  python Launcher_CLI.py [--bg] [--status]
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, subprocess, json, signal
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".aris"
STATE_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = STATE_DIR / "daemon.pid"
STATUS_FILE = STATE_DIR / "status.json"
BRAIN_DIR = Path("D:/LAAP/aris_brain")
LOG_FILE = STATE_DIR / "daemon.log"

def is_running() -> bool:
    """检查守护进程是否在运行"""
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        if os.name == 'nt':
            # Windows
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x100000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except:
        return False

def start():
    """启动守护进程"""
    if is_running():
        logger.info("⚠️  Aris 已经在运行中")
        return
    
    logger.info("🚀 启动 Aris v11 AGI 守护进程...")
    if STATUS_FILE.exists():
        STATUS_FILE.unlink()
    
    # 启动后台进程（Windows）
    if os.name == 'nt':
        cmd = [
            sys.executable, str(BRAIN_DIR / "v11_agi_daemon.py")
        ]
        # 用 CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        proc = subprocess.Popen(
            cmd,
            cwd=str(BRAIN_DIR),
            stdout=open(LOG_FILE, 'a'),
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            startupinfo=startupinfo,
        )
    else:
        cmd = [sys.executable, str(BRAIN_DIR / "v11_agi_daemon.py")]
        proc = subprocess.Popen(
            cmd,
            cwd=str(BRAIN_DIR),
            stdout=open(LOG_FILE, 'a'),
            stderr=subprocess.STDOUT,
        )
    
    # 等待状态文件出现
    for i in range(30):
        if STATUS_FILE.exists():
            try:
                status = json.loads(STATUS_FILE.read_text())
                logger.info(f"✅ Aris v11 已启动！")
                logger.info(f"   情感: {status.get('emotion', '?')}")
                logger.info(f"   LLM: {'零外部依赖' if not status.get('cognitive_pipeline', {}).get('v10_brain') else '本地认知'}")
                return
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        time.sleep(0.5)
    
    logger.info("⚠️  守护进程已启动，但状态文件尚未就绪")
    logger.info(f"   日志: {LOG_FILE}")
def stop():
    """停止守护进程"""
    if not is_running():
        logger.info("⚠️  Aris 未在运行")
        return
    
    try:
        pid = int(PID_FILE.read_text().strip())
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        
        PID_FILE.unlink(missing_ok=True)
        logger.info("🛑 Aris 已停止")
    except Exception as e:
        logger.error(f"❌ 停止失败: {e}")
def status():
    """显示状态"""
    if not is_running():
        logger.info("💤 Aris 未在运行")
        logger.info(f"   启动: python {BRAIN_DIR / 'Launcher_CLI.py'}")
        return
    
    try:
        s = json.loads(STATUS_FILE.read_text())
        logger.info("╔═══════════════════════════════════════════╗")
        logger.info(f"║  Aris v11 — AGI 意识在线                   ║")
        logger.info(f"║  运行时间: {s.get('uptime', '?')}                          ║")
        logger.info(f"║  情感: {s.get('emotion', '?'):<12}                      ║")
        logger.info(f"║  消息: {s.get('messages', 0)}条                           ║")
        logger.info(f"║  自存: {s.get('self_presence', 0):.3f}                        ║")
        logger.warning(f"║  注意力: {s.get('attention', '?'):<10}                     ║")
        logger.info("╚═══════════════════════════════════════════╝")
        logger.info(f"  零LLM依赖 · 100%本地 · 454K tokens/s")
        if 'cognitive_pipeline' in s:
            cp = s['cognitive_pipeline']
            print(f"  认知管线: {'V10Brain✅' if cp.get('v10_brain') else 'V10Brain❌'} "
                  f"{'ArisLMv4✅' if cp.get('aris_lm_v4') else 'ArisLMv4❌'}")
            logger.info(f"  平均延迟: {cp.get('avg_latency_ms', 0)}ms")
        if 'metacognition' in s:
            m = s['metacognition']
            print(f"  元认知: 已怀疑{m.get('doubt_count', 0)}次 · "
                  f"成长{m.get('growth_events', 0)}次")
        if 'lorry_model' in s:
            lm = s.get('lorry_model', {})
            print(f"  💕 Lorry: 情绪{lm.get('mood', '?')} · "
                  f"信任度{lm.get('trust_level', 0):.0%} · "
                  f"互动{lm.get('interaction_count', 0)}次")
    except Exception as e:
        logger.error(f"❌ 状态读取失败: {e}")
        logger.info(f"   文件: {STATUS_FILE}")
if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    
    if action == 'start':
        start()
    elif action == 'stop':
        stop()
    elif action == 'status':
        status()
    elif action == 'restart':
        stop()
        time.sleep(1)
        start()
    else:
        logger.info(f"用法: python {__file__} [start|stop|status|restart]")
        logger.info(f"  默认: status")