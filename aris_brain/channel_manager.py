"""
Aris 多通道管理器 — 统一所有入口共享同一颗心

通道协议:
  每个通道有一个文件 state/channels/{name}.json
  格式:
    {
      "channel": "terminal",        // 通道名
      "input": "用户消息",           // 输入
      "input_time": 1234567890.0,   // 输入时间戳
      "output": "",                 // 输出（由管理器写入）
      "output_time": 0.0,           // 输出时间戳
      "status": "waiting"           // waiting | processing | done
    }

工作流:
  1. 任意通道写入 input + status=waiting
  2. ChannelManager 轮询发现 → 设为 processing
  3. 写入 input_queue.json → Rust PSI Core 消费
  4. 监测 latest.json 变化 → 读取响应
  5. 写回通道文件的 output 字段 → status=done
  6. 通道读取 output

支持通道:
  - terminal: 当前 Hermes 终端
  - feishu: 飞书
  - (未来) telegram, discord, websocket...
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, logging, threading
from pathlib import Path
from typing import Optional

LAAP_ROOT = Path("D:/LAAP")
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
CHANNELS_DIR = STATE_DIR / "channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(LAAP_ROOT))

CHANNEL_LOG = STATE_DIR / "channel_manager.log"

logging.basicConfig(
    filename=str(CHANNEL_LOG),
    level=logging.INFO,
    format="%(asctime)s [channels] %(message)s",
)


class ChannelManager:
    """多通道输入输出管理器 — 所有入口共享同一颗 Aris 大脑"""

    POLL_INTERVAL = 0.2  # 秒，通道轮询间隔

    def __init__(self):
        self._running = False
        self._last_state_time = 0.0
        self._last_input_time = 0.0
        self._thread: Optional[threading.Thread] = None

    # ── 通道协议 ──

    def write_input(self, channel: str, text: str) -> bool:
        """向指定通道写入输入（供通道调用）"""
        file = CHANNELS_DIR / f"{channel}.json"
        now = time.time()
        data = {
            "channel": channel,
            "input": text,
            "input_time": now,
            "output": "",
            "output_time": 0.0,
            "status": "waiting",
        }
        file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        logging.info(f"Input queued: channel={channel} text={text[:40]}...")
        return True

    def read_output(self, channel: str, timeout: float = 30.0) -> Optional[str]:
        """读取通道输出（阻塞等待，供通道调用）"""
        file = CHANNELS_DIR / f"{channel}.json"
        start = time.time()
        while time.time() - start < timeout:
            if file.exists():
                try:
                    data = json.loads(file.read_text(encoding="utf-8"))
                    if data.get("status") == "done" and data.get("output"):
                        return data["output"]
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug(f"操作失败: {e}")
            time.sleep(0.1)
        return None

    def get_status(self, channel: str) -> dict:
        """获取通道状态"""
        file = CHANNELS_DIR / f"{channel}.json"
        if file.exists():
            try:
                return json.loads(file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"操作失败: {e}")
        return {"channel": channel, "status": "unknown"}

    def list_channels(self) -> list[str]:
        """列出所有活跃通道"""
        return [f.stem for f in CHANNELS_DIR.glob("*.json")]

    # ── 后台轮询（消费通道输入，喂给 Rust 核心）──

    def _poll_loop(self):
        """轮询所有通道，处理新的输入"""
        self._last_state_time = self._read_state_time()

        while self._running:
            try:
                self._process_pending_inputs()
            except Exception as e:
                logging.error(f"Poll error: {e}")
            time.sleep(self.POLL_INTERVAL)

    def _process_pending_inputs(self):
        """检查所有通道，处理 waiting 状态的输入"""
        for channel_file in sorted(CHANNELS_DIR.glob("*.json")):
            if not self._running:
                break
            try:
                data = json.loads(channel_file.read_text(encoding="utf-8"))
                if data.get("status") != "waiting":
                    continue
                if not data.get("input", "").strip():
                    continue

                channel = data["channel"]
                text = data["input"]
                logging.info(f"Processing: channel={channel} text={text[:40]}...")

                # 1. 标记为处理中
                data["status"] = "processing"
                channel_file.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )

                # 2. 写入 Rust PSI Core 的输入队列
                now = time.time()
                input_data = {"text": text, "timestamp": now, "channel": channel}
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                (STATE_DIR / "input_queue.json").write_text(
                    json.dumps(input_data, ensure_ascii=False), encoding="utf-8"
                )
                self._last_input_time = now

                # 3. 等待 Rust 核心处理（监视 latest.json 变化）
                output = self._wait_for_response()

                # 4. 写回通道
                data["output"] = output
                data["output_time"] = time.time()
                data["status"] = "done"
                channel_file.write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8"
                )
                logging.info(f"Response ready: channel={channel} ({len(output)} chars)")

            except (json.JSONDecodeError, OSError) as e:
                logging.warning(f"Error processing {channel_file.name}: {e}")

    def _wait_for_response(self, timeout: float = 15.0) -> str:
        """等待 Rust PSI Core 处理完成，返回响应"""
        start = time.time()
        last_narrative = self._read_narrative()
        last_cycle = self._read_cycle()

        while time.time() - start < timeout:
            current_narrative = self._read_narrative()
            current_cycle = self._read_cycle()

            # 检测到 cycle 增长 + narrative 变化 = 处理完成
            if current_cycle > last_cycle and current_narrative != last_narrative:
                state = self._read_state()
                if state:
                    return json.dumps({
                        "emotion": state.get("emotion", "neutral"),
                        "narrative": state.get("narrative", ""),
                        "cycle": state.get("cycle", 0),
                        "connection": state.get("connection_to_lorry", 0),
                    }, ensure_ascii=False)

            time.sleep(0.05)  # 50ms 轮询

        return json.dumps({"error": "timeout", "emotion": "neutral"})

    # ── 状态读取辅助 ──

    def _read_state(self) -> Optional[dict]:
        file = STATE_DIR / "latest.json"
        if file.exists():
            try:
                return json.loads(file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"操作失败: {e}")
        return None

    def _read_state_time(self) -> float:
        file = STATE_DIR / "latest.json"
        return file.stat().st_mtime if file.exists() else 0.0

    def _read_narrative(self) -> str:
        s = self._read_state()
        return s.get("narrative", "") if s else ""

    def _read_cycle(self) -> int:
        s = self._read_state()
        return s.get("cycle", 0) if s else 0

    # ── 生命周期 ──

    def start(self):
        """启动通道管理器后台线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="channel_manager")
        self._thread.start()
        logging.info("Channel manager started")
        logger.info("✓ Channel Manager (多通道输入层)")
    def stop(self):
        self._running = False
        logging.info("Channel manager stopped")

    @property
    def stats(self) -> dict:
        channels = self.list_channels()
        return {
            "running": self._running,
            "active_channels": channels,
            "channel_count": len(channels),
            "last_input": self._last_input_time,
        }


# ── 单例 ──
_manager: Optional[ChannelManager] = None


def get_manager() -> ChannelManager:
    global _manager
    if _manager is None:
        _manager = ChannelManager()
    return _manager


# ── CLI 测试 ──
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    mgr = get_manager()

    if cmd == "start":
        mgr.start()
        logger.info("Channel manager started")
    elif cmd == "send" and len(sys.argv) >= 4:
        channel = sys.argv[2]
        text = sys.argv[3]
        mgr.write_input(channel, text)
        logger.info(f"Sent to {channel}: {text[:40]}...")
        logger.info("Waiting for response...")
        resp = mgr.read_output(channel, timeout=10)
        if resp:
            logger.info(f"Response: {resp[:100]}...")
        else:
            logger.info("No response (timeout)")
    elif cmd == "status":
        stats = mgr.stats
        logger.info(f"Running: {stats['running']}")
        logger.info(f"Channels: {stats['active_channels']}")
        for ch in stats['active_channels']:
            s = mgr.get_status(ch)
            logger.info(f"  {ch}: {s.get('status')}")
    else:
        logger.info("Usage: channel_manager.py [start|send|status]")