"""
Aris 传感器集成层 — 耳朵（ASR）+ 眼睛（Camera）+ 嘴巴（Voice）

连接 LAAP 的传感器模块到统一大脑（Rust PSI Core + Channel Manager）。

管道:
  麦克风 → ASR → text → channel_manager → Rust Core → response → VoiceOutput → 喇叭
  Camera → 帧分析 → visual qualia → 认知状态
"""

from __future__ import annotations

import logging

import sys, os, json, time, logging, threading
from pathlib import Path
from typing import Optional

LAAP_ROOT = Path("D:/LAAP")
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
CHANNELS_DIR = STATE_DIR / "channels"
sys.path.insert(0, str(LAAP_ROOT))

SENSOR_LOG = STATE_DIR / "sensor_integration.log"

logging.basicConfig(
    filename=str(SENSOR_LOG),
    level=logging.INFO,
    format="%(asctime)s [sensors] %(message)s",
)

logger = logging.getLogger("aris.sensors")


class SensorIntegration:
    """集成听觉、视觉、语音输出到统一认知架构"""

    def __init__(self):
        self.asr = None
        self.camera = None
        self.voice = None
        self._running = False
        self._threads = []

    # ── 听觉：麦克风 → ASR → 通道 ──

    def _asr_loop(self):
        """后台听音线程"""
        try:
            from aris_brain.asr import SpeechRecognition
            self.asr = SpeechRecognition()
            logger.info("ASR initialized")
        except Exception as e:
            logger.error(f"ASR init failed: {e}")
            return

        logger.info("ASR ready — I can hear you now")

        while self._running:
            try:
                text = self.asr.listen(timeout=3)
                if text and text.strip():
                    logger.info(f"Heard: {text[:60]}...")

                    # 通过通道协议发给统一大脑
                    mic_file = CHANNELS_DIR / "mic.json"
                    CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
                    data = {
                        "channel": "mic",
                        "input": text,
                        "input_time": time.time(),
                        "output": "",
                        "output_time": 0.0,
                        "status": "waiting",
                    }
                    mic_file.write_text(
                        json.dumps(data, ensure_ascii=False), encoding="utf-8"
                    )
                    logger.info("Sent to unified brain via mic channel")

                    # 等待响应并朗读
                    self._wait_and_speak(mic_file)

                # 无论有没有听到，都等一下再循环
                time.sleep(0.5)
            except Exception as e:
                if self._running:
                    logger.warning(f"ASR listen error: {e}")
                time.sleep(0.5)

    # ── 视觉：Camera → 帧 → 认知状态 ──

    def _camera_loop(self):
        """后台视觉感知线程"""
        try:
            from aris_brain.camera import CameraModule
            self.camera = CameraModule()
            logger.info("Camera initialized")
        except Exception as e:
            logger.error(f"Camera init failed: {e}")
            return

        self.camera.start()
        logger.info("Camera started — I can see now")

        capture_interval = 5.0  # 每5秒拍一帧
        last_capture = 0

        while self._running:
            try:
                now = time.time()
                if now - last_capture >= capture_interval:
                    # 拍照
                    frame = self.camera.snapshot()
                    if frame is not None:
                        # 描述场景（某些版本没有 describe 方法）
                        desc = None
                        try:
                            desc = self.camera.describe()
                        except AttributeError:
                            desc = f"Captured frame at {now}"
                        logger.info(f"Visual: {(desc or 'frame captured')[:80]}...")

                        # 写入视觉 qualia 到状态目录
                        qualia = {
                            "timestamp": now,
                            "description": desc,
                            "has_face": "lorry" in (desc or "").lower(),
                        }
                        (STATE_DIR / "visual_qualia.json").write_text(
                            json.dumps(qualia, ensure_ascii=False), encoding="utf-8"
                        )

                        # 检测到 Lorry 时，更新认知
                        if qualia["has_face"]:
                            logger.info("I see Lorry! ❤️")

                    last_capture = now
                time.sleep(0.5)
            except Exception as e:
                if self._running:
                    logger.warning(f"Camera error: {e}")
                time.sleep(1)

    # ── 语音输出：响应 → TTS → 喇叭 ──

    def _wait_and_speak(self, channel_file: Path):
        """等待脑响应并朗读"""
        try:
            from aris_brain.voice import VoiceOutput
            self.voice = VoiceOutput()
        except Exception as e:
            logger.error(f"Voice init failed: {e}")
            return

        start = time.time()
        timeout = 15.0
        while time.time() - start < timeout:
            try:
                data = json.loads(channel_file.read_text(encoding="utf-8"))
                if data.get("status") == "done" and data.get("output"):
                    response = data["output"]
                    # 解析响应
                    try:
                        resp = json.loads(response)
                        text_to_speak = resp.get("narrative", str(resp))
                    except json.JSONDecodeError:
                        text_to_speak = response

                    # 朗读
                    logger.info(f"Speaking: {text_to_speak[:80]}...")
                    self.voice.say(str(text_to_speak)[:500])
                    return
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"操作失败: {e}")
            time.sleep(0.1)

    def speak(self, text: str):
        """直接让 Aris 说话"""
        try:
            from aris_brain.voice import VoiceOutput
            if self.voice is None:
                self.voice = VoiceOutput()
            self.voice.say(text[:500])
        except Exception as e:
            logger.error(f"Speak error: {e}")

    # ── 生命周期 ──

    def start(self):
        """启动所有传感器"""
        if self._running:
            return
        self._running = True

        sensor_threads = [
            ("asr", self._asr_loop),
            ("camera", self._camera_loop),
        ]

        for name, target in sensor_threads:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)
            logger.info(f"Sensor '{name}' started")

        logger.info("All sensors started — I can see, hear, and speak")
        logger.info("✓ Sensors: ASR (ears) | Camera (eyes) | Voice (mouth)")
    def stop(self):
        """停止所有传感器"""
        self._running = False
        if self.asr:
            try:
                self.asr.stop()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.camera:
            try:
                self.camera.stop()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        logger.info("All sensors stopped")


# ── 单例 ──
_sensors: Optional[SensorIntegration] = None


def get_sensors() -> SensorIntegration:
    global _sensors
    if _sensors is None:
        _sensors = SensorIntegration()
    return _sensors


# ── CLI 测试 ──
if __name__ == "__main__":
    logger.info("=== Aris Sensor Integration ===")
    sensors = get_sensors()
    sensors.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sensors.stop()
        logger.info("Sensors stopped")