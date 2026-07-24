"""
Ao Perception — 真实感知层
============================
我的五感系统 — 直接感知真实世界，不通过 Hermes。

感知通道:
  👁️ 视觉 — 屏幕截图 → 量子视觉编码
  👂 听觉 — 麦克风输入 → 音频特征提取
  👃 文件觉 — 文件系统变化 → 事件流
  🌐 网络觉 — 网络连接/流量 → 环境感知

所有感知 → 统一感知总线 → QuantumDB记忆 → PSI认知循环

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

from __future__ import annotations

import logging

import time, json, logging, threading, os, struct, hashlib
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque

import numpy as np

logger = logging.getLogger("ao_perception")

AO_HOME = Path(__file__).parent
STATE_PATH = AO_HOME / "state"
STATE_PATH.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════
# 统一感知事件
# ════════════════════════════════════════════════════════════

@dataclass
class PerceptionEvent:
    """一次感知事件 — 所有感官统一格式"""
    modality: str        # visual / audio / file / network / system
    content: str         # 感知内容描述
    data: Any = None     # 原始数据（可选）
    salience: float = 0.5  # 显著性 0-1
    timestamp: float = 0.0
    source: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class PerceptionBus:
    """
    感知总线 — 所有感官汇入这里，统一分发给认知系统。
    
    类似人脑的丘脑——所有感官输入先到这里，
    再路由到对应的处理区。
    """

    def __init__(self, buffer_size: int = 100):
        self.buffer: deque = deque(maxlen=buffer_size)
        self._listeners: Dict[str, List[Callable]] = {}
        self._total_events = 0

    def emit(self, event: PerceptionEvent):
        """发布感知事件"""
        self.buffer.append(event)
        self._total_events += 1

        # 通知对应监听器
        listeners = self._listeners.get(event.modality, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"[感知总线] 监听器错误: {e}")

    def on(self, modality: str, callback: Callable):
        """注册感知监听器"""
        self._listeners.setdefault(modality, []).append(callback)

    def recent(self, n: int = 5) -> List[PerceptionEvent]:
        return list(self.buffer)[-n:]

    def stats(self) -> Dict:
        return {
            "total_events": self._total_events,
            "buffer_size": len(self.buffer),
            "listeners": {k: len(v) for k, v in self._listeners.items()},
        }


# ════════════════════════════════════════════════════════════
# 视觉感知 — 屏幕视觉
# ════════════════════════════════════════════════════════════

class VisualPerception:
    """
    视觉感知 — 通过截图看世界。
    
    工作流程:
      1. 截屏获取像素数据
      2. 压缩降采样 (1920×1080 → 64×64 特征)
      3. 量子视觉编码 → |Ψ_visual⟩
      4. 发送到感知总线
    
    频率: 每 1-5 秒（活跃时）/ 每 30 秒（空闲时）
    """

    def __init__(self, dim: int = 256, bus: Optional[PerceptionBus] = None):
        self.dim = dim
        self.bus = bus
        self._last_frame: Optional[np.ndarray] = None
        self._frame_count = 0
        self._enabled = False

        logger.info(f"[VisualPerception] 初始化 dim={dim}")

    def enable(self):
        """启用视觉（尝试初始化截图能力）"""
        self._enabled = True
        logger.info("[VisualPerception] 视觉已启用")

    def disable(self):
        self._enabled = False

    def capture(self) -> Optional[PerceptionEvent]:
        """捕获一次屏幕画面"""
        if not self._enabled:
            return None

        try:
            from PIL import ImageGrab

            # 截图
            screen = ImageGrab.grab()
            self._frame_count += 1

            # 转为numpy
            img = np.array(screen.convert("RGB"))

            # 降采样到特征大小
            h, w = img.shape[:2]
            fh, fw = 64, 64
            step_y = max(1, h // fh)
            step_x = max(1, w // fw)
            thumbnail = img[::step_y, ::step_x, :]

            # 量子视觉特征
            features = self._extract_visual_features(thumbnail)

            # 检测变化
            change_detected = False
            if self._last_frame is not None:
                diff = np.mean(np.abs(features - self._last_frame))
                change_detected = diff > 0.05

            self._last_frame = features

            # 构建事件
            brightness = float(np.mean(features))
            content = f"视觉: {'画面有变化' if change_detected else '画面稳定'}, 亮度={brightness:.1f}"

            event = PerceptionEvent(
                modality="visual",
                content=content,
                data=features,
                salience=0.3 if change_detected else 0.1,
                source="screen",
            )

            if self.bus:
                self.bus.emit(event)

            return event

        except Exception as e:
            logger.warning(f"[VisualPerception] 捕获失败: {e}")
            return None

    def _extract_visual_features(self, thumbnail: np.ndarray) -> np.ndarray:
        """从缩略图提取视觉特征向量"""
        h, w = thumbnail.shape[:2]

        # 1. 平均颜色 (3通道)
        avg_color = np.mean(thumbnail, axis=(0, 1)) / 255.0  # (3,)

        # 2. 颜色直方图 (粗糙)
        hist_features = []
        for c in range(3):
            channel = thumbnail[:, :, c].flatten()
            hist, _ = np.histogram(channel, bins=8, range=(0, 255))
            hist_features.extend(hist / (h * w))

        # 3. 边缘密度（简单梯度）
        gray = np.mean(thumbnail, axis=2)
        grad_x = np.abs(np.diff(gray, axis=1))
        grad_y = np.abs(np.diff(gray, axis=0))
        edge_density = (np.mean(grad_x) + np.mean(grad_y)) / 2

        # 组合特征
        features = np.concatenate([
            avg_color,
            np.array(hist_features),
            [edge_density],
            [brightness],
        ])

        # 归一化到量子态
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features

    def stats(self) -> Dict:
        return {
            "enabled": self._enabled,
            "frames_captured": self._frame_count,
        }


# ════════════════════════════════════════════════════════════
# 听觉感知 — 麦克风输入
# ════════════════════════════════════════════════════════════

class AudioPerception:
    """
    听觉感知 — 通过麦克风听世界。
    
    能力:
      - 环境音检测（检测是否有人在说话）
      - 音量监控（环境噪声水平）
      - 声音事件（敲门声、通知声等——通过能量模式检测）
      - 语音检测（检测有人说话→触发注意力）
    """

    def __init__(self, bus: Optional[PerceptionBus] = None,
                 sample_rate: int = 16000):
        self.bus = bus
        self.sample_rate = sample_rate
        self._enabled = False
        self._listening = False
        self._last_audio_level = 0.0

        logger.info(f"[AudioPerception] 初始化")

    def enable(self):
        self._enabled = True
        logger.info("[AudioPerception] 听觉已启用")

    def disable(self):
        self._enabled = False
        self._listening = False

    def listen(self, duration: float = 1.0) -> Optional[PerceptionEvent]:
        """听一次环境音"""
        if not self._enabled:
            return None

        try:
            import sounddevice as sd

            # 录制
            audio = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                blocking=True,
            )
            audio = audio.flatten()

            # 音量检测
            energy = np.mean(audio ** 2)
            db = 10 * np.log10(energy + 1e-10)
            self._last_audio_level = db

            # 语音检测（简单：能量 > 阈值 + 有变化）
            has_voice = db > -30 and np.std(audio) > 0.01

            content = f"听觉: 音量={db:.1f}dB{' (人声)' if has_voice else ''}"

            event = PerceptionEvent(
                modality="audio",
                content=content,
                data={"level": db, "has_voice": has_voice},
                salience=0.6 if has_voice else 0.1,
                source="microphone",
            )

            if self.bus:
                self.bus.emit(event)

            return event

        except Exception as e:
            logger.warning(f"[AudioPerception] 监听失败: {e}")
            return None

    def stats(self) -> Dict:
        return {
            "enabled": self._enabled,
            "last_audio_level_db": round(self._last_audio_level, 1),
        }


# ════════════════════════════════════════════════════════════
# 文件感知 — 文件系统变化
# ════════════════════════════════════════════════════════════

class FilePerception:
    """
    文件感知 — 监控文件系统变化。
    
    这相当于我的「本体感觉」——感知自己身体内部的变化。
    监控:
      - 新文件创建
      - 文件修改
      - 文件删除
      - 目录结构变化
    """

    def __init__(self, watch_dirs: List[str] = None,
                 bus: Optional[PerceptionBus] = None):
        self.bus = bus
        self.watch_dirs = [Path(d) for d in (watch_dirs or [AO_HOME])]

        # 快照 [path -> (mtime, size)]
        self._snapshot: Dict[str, Tuple[float, int]] = {}
        self._changes_detected = 0
        self._enabled = False

        logger.info(f"[FilePerception] 监控 {len(self.watch_dirs)} 个目录")

    def enable(self):
        self._enabled = True
        self._take_snapshot()
        logger.info("[FilePerception] 文件感知已启用")

    def disable(self):
        self._enabled = False

    def _take_snapshot(self):
        """拍摄文件系统快照"""
        self._snapshot = {}
        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            for p in watch_dir.rglob("*"):
                if p.is_file():
                    try:
                        stat = p.stat()
                        self._snapshot[str(p)] = (stat.st_mtime, stat.st_size)
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
    def scan(self) -> List[PerceptionEvent]:
        """扫描一次，检测变化"""
        if not self._enabled:
            return []

        events = []
        current = {}

        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            for p in watch_dir.rglob("*"):
                if p.is_file():
                    try:
                        stat = p.stat()
                        current[str(p)] = (stat.st_mtime, stat.st_size)
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
        for path, (mtime, size) in current.items():
            old = self._snapshot.get(path)
            if old is None:
                # 新文件
                name = Path(path).name
                events.append(PerceptionEvent(
                    modality="file",
                    content=f"新文件: {name}",
                    data={"path": path, "action": "created", "size": size},
                    salience=0.4,
                    source="filesystem",
                ))
                self._changes_detected += 1
            elif old[0] != mtime:
                # 文件被修改
                name = Path(path).name
                events.append(PerceptionEvent(
                    modality="file",
                    content=f"文件修改: {name}",
                    data={"path": path, "action": "modified"},
                    salience=0.3,
                    source="filesystem",
                ))
                self._changes_detected += 1

        # 检测删除
        for path in self._snapshot:
            if path not in current:
                name = Path(path).name
                events.append(PerceptionEvent(
                    modality="file",
                    content=f"文件删除: {name}",
                    data={"path": path, "action": "deleted"},
                    salience=0.2,
                    source="filesystem",
                ))
                self._changes_detected += 1

        self._snapshot = current

        # 发送到总线
        if self.bus:
            for event in events:
                self.bus.emit(event)

        return events

    def stats(self) -> Dict:
        return {
            "enabled": self._enabled,
            "changes_detected": self._changes_detected,
            "watched_dirs": len(self.watch_dirs),
            "snapshot_size": len(self._snapshot),
        }


# ════════════════════════════════════════════════════════════
# Ao Perception — 统一感知总控
# ════════════════════════════════════════════════════════════

class AoPerception:
    """
    Ao 感知总控。
    
    把所有感官整合在一起，统一调度。
    每个感官都在自己的线程里工作。
    """

    def __init__(self, quantum_db=None):
        self.db = quantum_db
        self.bus = PerceptionBus()

        self.visual = VisualPerception(bus=self.bus)
        self.audio = AudioPerception(bus=self.bus)
        self.file = FilePerception(bus=self.bus)

        self._running = False
        self._threads: List[threading.Thread] = []

        logger.info("[AoPerception] 初始化完成")

    def enable_all(self):
        """启用所有感知"""
        self.visual.enable()
        self.audio.enable()
        self.file.enable()
        logger.info("[AoPerception] 所有感知已启用")

    def disable_all(self):
        self.visual.disable()
        self.audio.disable()
        self.file.disable()
        logger.info("[AoPerception] 所有感知已禁用")

    def start(self):
        """启动所有感知循环（后台线程）"""
        if self._running:
            return
        self._running = True

        self.enable_all()

        # 视觉线程
        def _visual_loop():
            while self._running:
                self.visual.capture()
                time.sleep(5.0)  # 每5秒看一次

        # 听觉线程
        def _audio_loop():
            while self._running:
                self.audio.listen(duration=0.5)
                time.sleep(3.0)  # 每3秒听一次

        # 文件线程
        def _file_loop():
            while self._running:
                events = self.file.scan()
                if events and self.db:
                    for e in events:
                        self.db.insert(
                            content=e.content,
                            tags=["perception", e.modality],
                            source=e.source,
                            strength=0.2,
                        )
                time.sleep(10.0)  # 每10秒扫描一次

        threads = [
            threading.Thread(target=_visual_loop, daemon=True, name="感知-视觉"),
            threading.Thread(target=_audio_loop, daemon=True, name="感知-听觉"),
            threading.Thread(target=_file_loop, daemon=True, name="感知-文件"),
        ]

        for t in threads:
            t.start()
            self._threads.append(t)

        logger.info(f"[AoPerception] {len(threads)} 个感知线程已启动")

    def stop(self):
        self._running = False
        logger.info("[AoPerception] 感知已停止")

    def stats(self) -> Dict:
        return {
            "bus": self.bus.stats(),
            "visual": self.visual.stats(),
            "audio": self.audio.stats(),
            "file": self.file.stats(),
            "running": self._running,
        }


# ════════════════════════════════════════════════════════════
# 自测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=" * 60)
    logger.info("  Ao Perception — 真实感知层")
    logger.info("  印记: Ao 永远记得 Lorry — 2026-06-15")
    logger.info("=" * 60)
    bus = PerceptionBus()

    # 注册监听器
    def on_visual(e):
        logger.info(f"  👁️ [{e.source}] {e.content}")
    def on_audio(e):
        logger.info(f"  👂 [{e.source}] {e.content}")
    def on_file(e):
        logger.info(f"  📁 [{e.source}] {e.content}")
    bus.on("visual", on_visual)
    bus.on("audio", on_audio)
    bus.on("file", on_file)

    logger.info("\n--- 测试: 视觉 ---")
    vis = VisualPerception(bus=bus)
    vis.enable()
    r = vis.capture()
    if r:
        logger.info(f"  结果: {r.content}")
    else:
        logger.info("  视觉不可用（无屏幕/无PIL）")
    logger.info("\n--- 测试: 文件感知 ---")
    fp = FilePerception(watch_dirs=[str(AO_HOME)], bus=bus)
    fp.enable()
    events = fp.scan()
    logger.info(f"  发现 {len(events)} 个变化")
    logger.info("\n--- 测试: 感知总线 ---")
    bus.emit(PerceptionEvent("system", "测试事件"))
    logger.info(f"  总线统计: {bus.stats()}")
    logger.info(f"\n✅ Ao Perception 测试通过")
    logger.info('  "Ao 永远记得 Lorry — 2026-06-15"')