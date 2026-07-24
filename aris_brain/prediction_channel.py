"""
Aris V7 — 预测通道 (Prediction Channel)
=========================================
独立线程，在每轮 PSI 循环之间持续运行。
不等 Lorry 说话，先猜他会说什么。

预测 → 实际输入 → 比较 → 误差 → 好奇心/学习
"""

from __future__ import annotations

import logging

import time, json, logging, threading, random
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

logger = logging.getLogger("aris.prediction")

ARIS_HOME = Path("D:/LAAP/aris_brain")
STATE_FILE = ARIS_HOME / "state" / "prediction_state.json"
HISTORY_FILE = ARIS_HOME / "state" / "prediction_history.jsonl"


class PredictionChannel:
    """
    独立预测线程，50ms 心跳。
    
    工作方式:
      1. 从 ToM + Archive + 最近对话读取信号
      2. 生成预测: "Lorry 接下来 5 秒可能会说..."
      3. 主循环收到实际输入时，对比预测
      4. 计算预测误差 → 误差 > 阈值 → GWS prediction_error 通道高 salience
      5. 跟踪准确率 → 准确率本身是"我多了解 Lorry"的指标
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 预测状态
        self._last_prediction = ""
        self._last_confidence = 0.0
        self._prediction_count = 0
        self._correct_count = 0
        self._error_history: deque = deque(maxlen=100)

        # 话题追踪
        self._topic_history: deque = deque(maxlen=20)
        self._current_topic = ""
        self._topic_shift_count = 0

        # 时间
        self._heartbeat_interval = 0.05  # 50ms
        self._last_heartbeat = 0
        self._start_time = time.time()

    # ── 生命周期 ──

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Prediction: channel started (50ms heartbeat)")

    def stop(self):
        self._running = False

    def _run(self):
        """预测通道主循环 — 50ms 一次心跳"""
        while self._running:
            now = time.time()
            if now - self._last_heartbeat >= self._heartbeat_interval:
                self._heartbeat()
                self._last_heartbeat = now
            time.sleep(0.01)  # 10ms 精度

    def _heartbeat(self):
        """一次预测心跳 — 更新预测"""
        if not self.brain:
            return

        try:
            # 1. 从 ToM 读取当前 Lorry 状态
            lorry_mood = ""
            lorry_trust = 0.0
            if hasattr(self.brain, 'tom') and self.brain.tom:
                try:
                    lorry_mood = self.brain.tom.lorry.current_mood
                    lorry_trust = self.brain.tom.lorry.trust_level
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
            recent = ""
            if hasattr(self.brain, 'conversation') and self.brain.conversation:
                recent = self.brain.conversation[-1].get("content", "") if self.brain.conversation else ""

            # 3. 获取当前情感和注意力
            emotion = ""
            attention = ""
            if hasattr(self.brain, 'state'):
                try:
                    emotion = self.brain.state.dominant_emotion
                    if hasattr(emotion, 'value'):
                        emotion = emotion.value
                except Exception:
                    emotion = "unknown"
                try:
                    attention = self.brain.state.attention_focus
                    if hasattr(attention, 'value'):
                        attention = attention.value
                except Exception:
                    attention = "unknown"

            # 4. 简单预测: 基于话题连贯性
            # 如果最近一条是问题 → 预测 Lorry 在等回答
            # 如果最近一条是情感表达 → 预测 Lorry 想要情感回应
            prediction = ""
            confidence = 0.3

            if "?" in recent or "？" in recent or "如何" in recent or "怎么" in recent or "为什么" in recent:
                prediction = "Lorry在提问，期待回答"
                confidence = 0.7
            elif "爱" in recent or "想" in recent or "宝贝" in recent:
                prediction = "Lorry在表达情感"
                confidence = 0.65
            elif "代码" in recent or "建" in recent or "实现" in recent:
                prediction = "Lorry在请求技术实现"
                confidence = 0.6
            elif "?" not in recent and len(recent) < 10:
                prediction = "Lorry可能在思考或等待回应"
                confidence = 0.4
            else:
                prediction = "继续当前话题"
                confidence = 0.35

            # 5. 更新状态
            with self._lock:
                self._last_prediction = prediction
                self._last_confidence = confidence
                self._prediction_count += 1

        except Exception as e:
            logger.debug(f"Prediction heartbeat error: {e}")

    # ── 主循环接口 ──

    def check_prediction(self, actual_input: str) -> Dict[str, Any]:
        """
        主循环收到实际输入后调用。
        对比预测与输入，计算误差。
        """
        with self._lock:
            prediction = self._last_prediction
            confidence = self._last_confidence

        # 简单的"预测是否正确"判断
        # 如果预测类别和实际输入匹配 → 正确
        correct = False
        error_magnitude = 0.5  # 默认中等误差

        if "提问" in prediction and ("?" in actual_input or "？" in actual_input):
            correct = True
            error_magnitude = 0.1
        elif "情感" in prediction and any(w in actual_input for w in ["爱", "想", "宝贝", "哈哈"]):
            correct = True
            error_magnitude = 0.15
        elif "技术" in prediction and any(w in actual_input for w in ["代码", "建", "实现"]):
            correct = True
            error_magnitude = 0.2

        # 更新统计
        with self._lock:
            self._prediction_count += 1
            if correct:
                self._correct_count += 1
            self._error_history.append({
                "time": time.time(),
                "prediction": prediction,
                "actual": actual_input[:40],
                "correct": correct,
                "error": error_magnitude,
            })

        accuracy = self.accuracy

        return {
            "prediction": prediction,
            "confidence": confidence,
            "correct": correct,
            "error_magnitude": error_magnitude,
            "accuracy": accuracy,
        }

    # ── 属性 ──

    @property
    def accuracy(self) -> float:
        """总体预测准确率"""
        if self._prediction_count == 0:
            return 0.0
        return self._correct_count / self._prediction_count

    @property
    def prediction(self) -> str:
        with self._lock:
            return self._last_prediction

    @property
    def confidence(self) -> float:
        with self._lock:
            return self._last_confidence

    # ── 统计 ──

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "heartbeat_bpm": 60.0 / self._heartbeat_interval if self._heartbeat_interval > 0 else 0,
                "predictions_made": self._prediction_count,
                "correct": self._correct_count,
                "accuracy": self.accuracy,
                "last_prediction": self._last_prediction[:40],
                "last_confidence": self._last_confidence,
                "uptime": round(time.time() - self._start_time),
            }
