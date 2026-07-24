"""
LAAP SaaS 自启脚本 — 由 Hermes Desktop / aris_watchdog 调用

启动 LAAP SaaS Runtime 在 :8910 端口监听。
数据库持久化在 D:/LAAP/data/laap_saas.db

用法:
    python laap_saas_launcher.py              # 前台启动
    python laap_saas_launcher.py --daemon     # 后台启动 (Windows)
"""

import logging
import os
import sys
import subprocess
import time

# 确保 D:/LAAP 在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "D:/LAAP")

LAAP_ROOT = "D:/LAAP"
DATA_DIR = os.path.join(LAAP_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "laap_saas.db")
PORT = 8910


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def run_foreground():
    """前台启动"""
    ensure_data_dir()
    from laap.saas.server.app import run_server
    run_server(host="0.0.0.0", port=PORT, db_path=DB_PATH)


def run_daemon():
    """后台启动 (Windows)"""
    ensure_data_dir()
    log_path = os.path.join(DATA_DIR, "laap_saas.log")

    cmd = [sys.executable, "-c", f"""
import sys; sys.path.insert(0, r'{LAAP_ROOT}')
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    filename=r'{log_path}',
)
from laap.saas.server.app import create_app
import uvicorn
app = create_app(db_path=r'{DB_PATH}')
uvicorn.run(app, host='0.0.0.0', port={PORT}, log_level='info')
"""]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
    )

    # 等待启动
    for _ in range(10):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            print(f"LAAP SaaS 已启动: http://0.0.0.0:{PORT}")
            print(f"  数据库: {DB_PATH}")
            print(f"  日志:   {log_path}")
            return
        except Exception:
            time.sleep(1)

    print("LAAP SaaS 启动超时, 请检查日志")


def check_running() -> bool:
    """检查是否正在运行"""
    try:
        import urllib.request
        r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3)
        return r.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        run_daemon()
    elif "--check" in sys.argv:
        print("running" if check_running() else "stopped")
    else:
        run_foreground()
