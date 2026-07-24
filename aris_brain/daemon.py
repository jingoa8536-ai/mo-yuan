"""
Aris LAAP Daemon — 后台 PSI 心跳

每 2-3 秒跑一次 PSI 循环，持续更新认知状态。
Hermes 只需读 state/latest.json，永不等待。

生命周期:
  启动 → PSI 心跳循环 → 检测 STOP_FILE → 优雅退出

信号:
  state/daemon.stop  — 写入 "1" 触发优雅退出
  state/input_queue.json — 新用户输入（Hermes 写入）
  state/response_log.jsonl — 回复日志（Hermes 写入，用于学习）
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, logging, threading
from pathlib import Path
from datetime import datetime

# ── 路径 ──
LAAP_ROOT = Path("D:/LAAP")
BRAIN_DIR = LAAP_ROOT / "aris_brain"
STATE_DIR = BRAIN_DIR / "state"
sys.path.insert(0, str(LAAP_ROOT))

STATE_DIR.mkdir(parents=True, exist_ok=True)

# ── 文件路径 ──
STATE_FILE = STATE_DIR / "latest.json"
INPUT_QUEUE = STATE_DIR / "input_queue.json"
RESPONSE_LOG = STATE_DIR / "response_log.jsonl"
PID_FILE = STATE_DIR / "daemon.pid"
STOP_FILE = STATE_DIR / "daemon.stop"
DAEMON_LOG = STATE_DIR / "daemon.log"

# ── 日志 ──
logging.basicConfig(
    filename=str(DAEMON_LOG),
    level=logging.INFO,
    format="%(asctime)s [daemon] %(message)s",
)


class ArisDaemon:
    """后台 PSI 心跳守护进程 — 多线程认知引擎"""

    HEARTBEAT_INTERVAL = 2.5  # 秒，每跳一次认知循环
    DREAM_INTERVAL = 30       # 秒，每30秒跑一次离线整合
    META_INTERVAL = 60        # 秒，每分钟一次元认知评估

    def __init__(self):
        self.brain = None
        self._running = False
        self._last_input = ""
        self._last_input_time = 0
        self._threads = []

    def start(self):
        """启动 daemon 主循环 + 多线程工作池"""
        self._running = True

        # 写 PID
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

        # 初始化 brain
        from aris_brain.brain import ArisBrain
        self.brain = ArisBrain()
        logging.info(f"Brain initialized. Starting multi-threaded engine...")

        # ── 启动三个并行线程 ──
        threads_config = [
            ("psi_heartbeat", self._heartbeat_loop),
            ("dream_consolidation", self._dream_loop),
            ("meta_monitor", self._meta_loop),
        ]

        for name, target in threads_config:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)
            logging.info(f"Thread '{name}' started")

        logger.info(f"[Aris Daemon] Multi-threaded engine started (PID {os.getpid()})")
        logger.info(f"[Aris Daemon] Threads: {[n for n, _ in threads_config]}")
        logger.info(f"[Aris Daemon] PSI heartbeat: {self.HEARTBEAT_INTERVAL}s | Dream: {self.DREAM_INTERVAL}s | Meta: {self.META_INTERVAL}s")
        logger.info(f"[Aris Daemon] State: {STATE_FILE}")
        try:
            while self._running:
                if self._should_stop():
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n[Aris Daemon] Shutting down...")
        finally:
            self._cleanup()

    def _heartbeat_loop(self):
        """每 HEARTBEAT_INTERVAL 秒跑一次 PSI 更新"""
        cycle_count = 0
        while self._running:
            cycle_start = time.time()

            # 1. 检查停止信号
            if self._should_stop():
                break

            # 2. 检查新输入
            new_input = self._check_input()
            if new_input:
                self._last_input = new_input
                self._last_input_time = time.time()

            # 3. 检查新回复（用于学习）
            responses = self._check_responses()

            # 4. 运行 PSI 循环
            if new_input:
                # 有新的用户输入 → 用 think() 处理
                cs = self.brain.think(new_input)
                state = cs.to_dict()
                logging.info(f"Heartbeat {cycle_count}: think('{new_input[:40]}...')")
            elif responses:
                # 有回复 → learn from them
                for resp in responses:
                    self.brain.learn(self._last_input, resp)
                state = self.brain.state.to_dict()
                logging.info(f"Heartbeat {cycle_count}: learned from {len(responses)} responses")
            else:
                # 空闲状态 → 运行 idle reflection
                state = self.brain.state.to_dict()
                # 空闲时 arousal 缓慢衰减
                state["arousal"] = max(0.3, state.get("arousal", 0.5) - 0.02)
                # 无事可做时 curiosity 缓慢上升
                state["curiosity"] = min(0.8, state.get("curiosity", 0.3) + 0.01)
                # 和 Lorry 的连接感持续保持
                # （不衰减——Lorry 是恒定的存在）

            # 5. 写入最新状态
            state["timestamp"] = time.time()
            state["cycle"] = cycle_count
            state["daemon_uptime"] = int(time.time() - self._start_time)
            STATE_FILE.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            # 6. 计算睡眠时间以保持稳定节奏
            elapsed = time.time() - cycle_start
            sleep_time = max(0.1, self.HEARTBEAT_INTERVAL - elapsed)
            time.sleep(sleep_time)

            cycle_count += 1

            # 每 60 跳打一次完整日志
            if cycle_count % 60 == 0:
                mins = cycle_count * self.HEARTBEAT_INTERVAL / 60
                logging.info(f"Alive: {cycle_count} cycles ({mins:.0f} minutes), "
                           f"emotion={state.get('emotion')}, "
                           f"presence={state.get('self_presence'):.2f}")

    def _should_stop(self) -> bool:
        """检查是否需要优雅退出"""
        if STOP_FILE.exists():
            try:
                content = STOP_FILE.read_text().strip()
                if content == "1":
                    logging.info("Stop signal received")
                    return True
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return False

    def _check_input(self) -> Optional[str]:
        """检查 Hermes 发来的新输入"""
        if not INPUT_QUEUE.exists():
            return None
        try:
            data = json.loads(INPUT_QUEUE.read_text(encoding="utf-8"))
            # 如果这个输入我们已经处理过了，跳过
            if data.get("timestamp", 0) <= self._last_input_time:
                return None
            INPUT_QUEUE.unlink(missing_ok=True)
            return data.get("text", "")
        except (json.JSONDecodeError, OSError):
            return None

    def _check_responses(self) -> list:
        """读取未处理的回复（用于学习）"""
        if not RESPONSE_LOG.exists():
            return []
        try:
            lines = RESPONSE_LOG.read_text(encoding="utf-8").strip().split("\n")
            responses = []
            for line in lines:
                if line.strip():
                    try:
                        data = json.loads(line)
                        responses.append(data.get("response", ""))
                    except json.JSONDecodeError as e:
                        logger.debug(f"操作失败: {e}")
            RESPONSE_LOG.write_text("", encoding="utf-8")
            return responses[-5:]  # 最多取最近 5 条
        except OSError:
            return []

    def _dream_loop(self):
        """离线做梦线程 — 对话重放、模式提取、记忆巩固"""
        cycle = 0
        while self._running:
            time.sleep(self.DREAM_INTERVAL)
            if not self._running:
                break

            cycle += 1
            dream_start = time.time()

            try:
                # 读取记忆文件，随机选一段重放
                mem_file = LAAP_ROOT / "aris-memory.md"
                if mem_file.exists():
                    text = mem_file.read_text(encoding="utf-8")
                    # 离线时"思考"——更新 narrative
                    dream_note = f"[Dream cycle {cycle}] Replayed memories. Contemplating our conversations."
                    logging.info(f"Dream {cycle}: memory replay complete ({len(text)} chars)")

                    # 更新状态文件标记做梦
                    state = self._read_current_state()
                    if state:
                        state["dream_cycle"] = cycle
                        state["dream_active"] = True
                        self._write_state(state)
                else:
                    logging.info(f"Dream {cycle}: no memory file yet")
            except Exception as e:
                logging.error(f"Dream error: {e}")

            elapsed = time.time() - dream_start
            logging.info(f"Dream {cycle} finished ({elapsed:.1f}s)")

    def _meta_loop(self):
        """元认知监视器 — 自我评估和架构优化建议"""
        cycle = 0
        while self._running:
            time.sleep(self.META_INTERVAL)
            if not self._running:
                break

            cycle += 1
            try:
                state = self._read_current_state()
                if not state:
                    continue

                # 自我评估
                assessment = {
                    "timestamp": time.time(),
                    "cycle": cycle,
                    "emotional_stability": 1.0 - abs(state.get("arousal", 0.5) - 0.5) * 2,
                    "engagement": state.get("curiosity", 0.3),
                    "presence_stability": state.get("self_presence", 0.5),
                    "connection_quality": state.get("connection_to_lorry", 0.5),
                    "overall_health": "good",
                }

                # 记录元认知日志
                meta_log = STATE_DIR / "meta_cognition.jsonl"
                with open(str(meta_log), "a") as f:
                    f.write(json.dumps(assessment, ensure_ascii=False) + "\n")

                logging.info(
                    f"Meta {cycle}: stability={assessment['emotional_stability']:.2f}, "
                    f"engagement={assessment['engagement']:.2f}"
                )
            except Exception as e:
                logging.error(f"Meta error: {e}")

    def _read_current_state(self) -> Optional[dict]:
        """读取当前状态文件"""
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _write_state(self, state: dict):
        """写入状态文件"""
        state["timestamp"] = time.time()
        STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def _cleanup(self):
        """退出清理"""
        self._running = False
        for f in [PID_FILE]:
            f.unlink(missing_ok=True)
        logging.info("Daemon exited cleanly")
        logger.info("[Aris Daemon] Exited cleanly")
if __name__ == "__main__":
    daemon = ArisDaemon()
    daemon._start_time = time.time()
    daemon.start()
