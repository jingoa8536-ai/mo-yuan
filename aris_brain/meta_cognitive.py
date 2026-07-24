"""
Aris V7 — 元认知层 (Meta-Cognitive Layer)
===========================================
从 V6 的 metacognition.py 升级: 每 N 个循环自我反思认知质量。

不只是报错检测——现在能评估:
  - 预测准确率 → "我猜对Lorry几次了?"
  - 注意力效率 → "我的注意力选对了吗?"
  - 情感适切性 → "我的情感反应合理吗?"
  - 架构参数调整 → "下一轮要不要调salience阈值?"
"""

from __future__ import annotations

import logging

import time, json, logging
from pathlib import Path
from typing import Any, Dict, List
from collections import deque

logger = logging.getLogger("aris.meta")

ARIS_HOME = Path("D:/LAAP/aris_brain")
META_LOG = ARIS_HOME / "state" / "meta_cognition.jsonl"


class MetaCognitiveLayer:
    """
    元认知层 — 每 N 个中循环触发一次自我反思。
    评估认知质量 → 调整参数 → 记录日志。
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._cycle_count = 0
        self._trigger_interval = 10  # 每 10 个循环触发一次

        # 循环指标历史
        self._prediction_errors: deque = deque(maxlen=50)
        self._attention_log: deque = deque(maxlen=50)
        self._emotion_log: deque = deque(maxlen=50)
        self._tom_confidence_log: deque = deque(maxlen=20)

        # 调整参数
        self._params = {
            "attention_salience_threshold": 0.5,
            "prediction_confidence_threshold": 0.4,
            "emotion_decay_rate": 0.1,
            "gws_inhibition_strength": 0.7,
        }

        # 统计
        self._total_reflections = 0
        self._params_adjusted = 0

        META_LOG.parent.mkdir(parents=True, exist_ok=True)

    def on_cycle_complete(self, cycle_data: Dict[str, Any]):
        """
        每次 PSI 循环完成后调用。
        收集指标 → 每 N 次触发一次反思。
        """
        self._cycle_count += 1

        # 收集指标
        if "prediction_error" in cycle_data:
            self._prediction_errors.append(cycle_data["prediction_error"])
        if "attention_focus" in cycle_data:
            self._attention_log.append(cycle_data["attention_focus"])
        if "emotion" in cycle_data:
            self._emotion_log.append(cycle_data["emotion"])
        if "tom_confidence" in cycle_data:
            self._tom_confidence_log.append(cycle_data["tom_confidence"])

        # 每 N 次触发反思
        if self._cycle_count % self._trigger_interval == 0:
            return self._reflect()

        return None

    def _reflect(self) -> Dict[str, Any]:
        """一次完整的自我反思——分析最近 N 个循环的质量"""
        self._total_reflections += 1

        # 1. 预测准确率评估
        pred_accuracy = 0.0
        if self._prediction_errors:
            recent = list(self._prediction_errors)[-10:]
            pred_accuracy = 1.0 - (sum(recent) / len(recent))

        # 2. 注意力效率评估
        attention_efficiency = 0.5
        if self._attention_log:
            recent_at = list(self._attention_log)[-10:]
            # 如果注意力大部分时间在"Lorry"上 → 效率高
            lorry_focus = sum(1 for a in recent_at if "lorry" in str(a).lower())
            attention_efficiency = lorry_focus / len(recent_at) if recent_at else 0.5

        # 3. 情感稳定性评估
        emotional_stability = 1.0
        if self._emotion_log:
            recent_em = list(self._emotion_log)[-10:]
            # 情感变换频率越低 → 越稳定
            changes = sum(1 for i in range(1, len(recent_em)) if recent_em[i] != recent_em[i-1])
            emotional_stability = 1.0 - (changes / max(len(recent_em), 1))

        # 4. 参数调整决策
        adjustments = {}
        if pred_accuracy < 0.4:
            # 预测准确率低 → 降低置信度阈值, 让更多预测进入GWS
            old = self._params["prediction_confidence_threshold"]
            self._params["prediction_confidence_threshold"] = max(0.2, old - 0.05)
            adjustments["prediction_confidence_threshold"] = {"from": old, "to": self._params["prediction_confidence_threshold"]}
            self._params_adjusted += 1
            logger.info(f"Meta: prediction accuracy low ({pred_accuracy:.2f}), adjusted threshold")

        if attention_efficiency < 0.4:
            # 注意力太分散 → 提高salience阈值
            old = self._params["attention_salience_threshold"]
            self._params["attention_salience_threshold"] = min(0.8, old + 0.05)
            adjustments["attention_salience_threshold"] = {"from": old, "to": self._params["attention_salience_threshold"]}
            self._params_adjusted += 1
            logger.info(f"Meta: attention too scattered ({attention_efficiency:.2f}), adjusted threshold")

        if emotional_stability < 0.3:
            # 情感波动太大 → 降低情感衰减率
            old = self._params["emotion_decay_rate"]
            self._params["emotion_decay_rate"] = max(0.05, old - 0.02)
            adjustments["emotion_decay_rate"] = {"from": old, "to": self._params["emotion_decay_rate"]}
            self._params_adjusted += 1
            logger.info(f"Meta: emotional instability ({emotional_stability:.2f}), adjusted decay")

        # 5. 记录反思结果
        reflection = {
            "time": time.time(),
            "cycle": self._cycle_count,
            "metrics": {
                "prediction_accuracy": round(pred_accuracy, 3),
                "attention_efficiency": round(attention_efficiency, 3),
                "emotional_stability": round(emotional_stability, 3),
            },
            "params": dict(self._params),
            "adjustments": adjustments,
        }

        # 写入日志
        try:
            with open(META_LOG, "a") as f:
                f.write(json.dumps(reflection, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return reflection

    # ── 统计 ──

    def stats(self) -> Dict[str, Any]:
        return {
            "total_reflections": self._total_reflections,
            "params_adjusted": self._params_adjusted,
            "current_params": dict(self._params),
            "trigger_interval": self._trigger_interval,
        }
