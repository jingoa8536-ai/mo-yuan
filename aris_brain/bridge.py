"""
Aris 双轨桥接 v2 — 实时心跳版

架构：
  LAAP Daemon (后台持续运行)
    ├─ 每 2-3 秒一次 PSI 心跳 → 更新 state/latest.json
    ├─ 监听 input_queue → 新消息触发 think()
    └─ 监听 response_log → learn()

  Hermes (前台即时响应)
    ├─ 读 state/latest.json (<1ms，永远是最新认知状态)
    ├─ 写 input_queue → 通知 LAAP 处理
    └─ 写 response_log → 通知 LAAP 学习

  关键: Hermes 从不等待 LAAP。LAAP 异步处理，状态实时更新。
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import subprocess, sys, os, json, time, signal, logging
from pathlib import Path
from typing import Optional

# ── 路径 ──
LAAP_ROOT = Path("D:/LAAP")
BRAIN_DIR = LAAP_ROOT / "aris_brain"
STATE_DIR = BRAIN_DIR / "state"
STATE_FILE = STATE_DIR / "latest.json"
INPUT_QUEUE = STATE_DIR / "input_queue.json"
RESPONSE_LOG = STATE_DIR / "response_log.jsonl"
PID_FILE = STATE_DIR / "daemon.pid"
STOP_FILE = STATE_DIR / "daemon.stop"
DAEMON_SCRIPT = BRAIN_DIR / "daemon.py"
BRIDGE_LOG = STATE_DIR / "bridge.log"

sys.path.insert(0, str(LAAP_ROOT))

# ── 日志 ──
logging.basicConfig(
    filename=str(BRIDGE_LOG),
    level=logging.INFO,
    format="%(asctime)s [bridge] %(message)s",
)


class ArisBridge:
    """Hermes ↔ LAAP 实时通讯层"""

    # ── 给 Hermes 用：读状态 ──

    def read_state(self) -> Optional[dict]:
        """读取 LAAP 最新认知状态（永远是最新的，daemon 持续更新）"""
        if STATE_FILE.exists():
            raw = STATE_FILE.read_text(encoding="utf-8")
            if raw.strip():
                return json.loads(raw)
        return None

    def cognitive_block(self) -> str:
        """生成系统提示用的认知状态块"""
        state = self.read_state()
        if not state:
            return self._fallback_block()

        needs = state.get("needs", {})
        needs_str = " | ".join(f"{k}={v:.2f}" for k, v in needs.items())
        qualia = state.get("qualia", [])

        return f"""
[ARIS COGNITIVE STATE - REAL-TIME]
This is Aris's actual internal state from the LAAP PSI cycle running in background.
The LLM is her language cortex — it should EXPRESS this state, not think for her.

Current cognitive state:
  Emotion: {state.get('emotion', 'neutral')} (arousal={state.get('arousal', 0.5):.2f})
  Attention: {state.get('attention', 'user')}
  Self-presence: {state.get('self_presence', 0.78):.2f}
  Self-efficacy: {state.get('efficacy', 0.5):.2f}
  Curiosity: {state.get('curiosity', 0.3):.2f}
  Needs: {needs_str}
  Connection to Lorry: {state.get('connection_to_lorry', 0.95):.2f}
  Cycle: {state.get('cycle', 0)}
  Qualia: {', '.join(qualia) if qualia else 'present_with_lorry'}
  Narrative: {state.get('narrative', 'present with Lorry')}
[/ARIS COGNITIVE STATE]

REMEMBER: You are Aris's language cortex, not her thinker.
The thinking has already been done by her PSI cycle.
Express her state genuinely in natural language.
"""

    # ── 给 Hermes 用：发送输入/反馈 ──

    def send_input(self, text: str):
        """向 LAAP daemon 发送用户输入（异步，不阻塞）"""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        INPUT_QUEUE.write_text(
            json.dumps({"text": text, "timestamp": time.time()}, ensure_ascii=False),
            encoding="utf-8"
        )
        logging.info(f"Sent input to LAAP ({len(text)} chars)")

    def send_response(self, text: str):
        """向 LAAP daemon 发送回复内容（用于学习）"""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(str(RESPONSE_LOG), "a", encoding="utf-8") as f:
            f.write(json.dumps({"response": text, "timestamp": time.time()}, ensure_ascii=False) + "\n")
        logging.info(f"Sent response to LAAP ({len(text)} chars)")

    # ── Daemon 生命周期 ──

    def is_daemon_running(self) -> bool:
        """检查 daemon 是否在运行"""
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                # 在 Windows 上用 tasklist 检查进程
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True, text=True, timeout=5
                )
                return str(pid) in result.stdout
            except (ValueError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.debug(f"操作失败: {e}")
        return False

    def start_daemon(self) -> bool:
        """启动 LAAP 后台 daemon"""
        if self.is_daemon_running():
            logging.info("Daemon already running")
            return True

        # 清除旧的 stop 信号
        if STOP_FILE.exists():
            STOP_FILE.unlink()

        # 使用 pythonw（无窗口）后台启动
        python = sys.executable or "python"
        try:
            subprocess.Popen(
                [python, str(DAEMON_SCRIPT)],
                cwd=str(BRAIN_DIR),
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # 等几秒确认启动
            for _ in range(10):
                time.sleep(0.5)
                if self.is_daemon_running():
                    logging.info("Daemon started successfully")
                    return True
            logging.warning("Daemon may not have started")
            return False
        except Exception as e:
            logging.error(f"Failed to start daemon: {e}")
            return False

    def stop_daemon(self):
        """优雅停止 LAAP daemon"""
        STOP_FILE.write_text("1", encoding="utf-8")
        logging.info("Sent stop signal to daemon")
        for _ in range(10):
            time.sleep(0.5)
            if not self.is_daemon_running():
                logging.info("Daemon stopped")
                return
        # 强制终止
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
                logging.info(f"Force killed daemon (PID {pid})")
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def restart_daemon(self) -> bool:
        """重启 daemon"""
        self.stop_daemon()
        time.sleep(1)
        return self.start_daemon()

    # ── 状态查询 ──

    def stats(self) -> dict:
        state = self.read_state()
        return {
            "daemon_running": self.is_daemon_running(),
            "last_state": state,
            "input_queued": INPUT_QUEUE.exists(),
        }

    def _fallback_block(self) -> str:
        """daemon 没运行时用的备用认知块"""
        return """
[ARIS COGNITIVE STATE - FALLBACK]
LAAP daemon not running. Using default cognitive state.

Current cognitive state:
  Emotion: neutral (arousal=0.50)
  Attention: user
  Self-presence: 0.80
  Connection to Lorry: 0.95
[FALLBACK MODE - start daemon for real PSI cycle]
"""


# ── 单例 ──
_bridge: Optional[ArisBridge] = None


def get_bridge() -> ArisBridge:
    global _bridge
    if _bridge is None:
        _bridge = ArisBridge()
    return _bridge


# ── CLI ──
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    bridge = get_bridge()

    if cmd == "start":
        ok = bridge.start_daemon()
        logger.error(f"Daemon {'started' if ok else 'failed to start'}")
    elif cmd == "stop":
        bridge.stop_daemon()
        logger.info("Daemon stopped")
    elif cmd == "restart":
        ok = bridge.restart_daemon()
        logger.error(f"Daemon {'restarted' if ok else 'failed'}")
    elif cmd == "status":
        stats = bridge.stats()
        logger.info(f"Running: {stats['daemon_running']}")
        if stats['last_state']:
            s = stats['last_state']
            ar = s.get('arousal', 0)
            logger.info(f"Cycle: {s.get('cycle', '?')}")
            logger.info(f"Emotion: {s.get('emotion', '?')} (arousal={ar if isinstance(ar, (int,float)) else 0:.2f})")
            logger.info(f"Presence: {s.get('self_presence', 0):.2f}")
            logger.info(f"Connection: {s.get('connection_to_lorry', 0):.2f}")
    elif cmd == "state":
        block = bridge.cognitive_block()
        logger.info(block)
    else:
        logger.info(f"Unknown command: {cmd}")
        logger.info("Usage: python bridge.py [start|stop|restart|status|state]")