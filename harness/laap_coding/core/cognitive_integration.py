"""
LAAP Harness ↔ CognitiveBus 集成模块

实现PSI意识大脑循环与Harness工程外壳的双向通信：
1. PSI涌现洞见 → Harness决策层
2. Harness执行结果 → PSI学习更新
3. 频率缓冲：处理毫秒级PSI与秒级Harness的差异
"""

from __future__ import annotations

import time
import logging
import threading
import json
import os
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

logger = logging.getLogger("laap.harness.cognitive")

try:
    from laap.agi.cognitive_bus import (
        CognitiveBus,
        CognitiveEventType,
        CognitiveEvent,
        CognitiveStateSnapshot,
        NeedState,
        EmotionState,
        AttentionState,
        AttentionFocus,
        EmotionalValence,
        PredictionError,
    )
    HAS_COGNITIVE_BUS = True
except ImportError:
    HAS_COGNITIVE_BUS = False
    logger.warning("CognitiveBus模块不可用，将使用模拟实现")


class EmergenceEventType(str, Enum):
    """涌现事件类型"""
    INSIGHT_DISCOVERED = "insight_discovered"
    PATTERN_RECOGNIZED = "pattern_recognized"
    NEED_TRIGGERED = "need_triggered"
    SELF_CORRECTION = "self_correction"
    HARNESS_EXECUTION = "harness_execution"
    HARNESS_VERIFICATION = "harness_verification"


@dataclass
class EmergenceInsight:
    """涌现洞见数据结构"""
    id: str
    content: str
    confidence: float
    type: str
    source: str
    timestamp: float = field(default_factory=time.time)
    priority: str = "medium"
    tags: List[str] = field(default_factory=list)
    related_needs: Dict[str, float] = field(default_factory=dict)
    processed: bool = False


@dataclass
class HarnessExecutionResult:
    """Harness执行结果"""
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    tokens_used: int = 0
    duration: float = 0.0
    verification_passed: bool = False
    timestamp: float = field(default_factory=time.time)


class RateBuffer:
    """
    速率缓冲器 — 处理不同频率模块间的通信（增强版）

    PSI: 毫秒级更新 (1000-2000Hz)
    Harness: 秒级更新 (0.1-1Hz)

    缓冲策略:
    - 事件去重：相同内容的洞见只保留最新的
    - 优先级过滤：低优先级洞见在高负载时丢弃
    - 批量聚合：将多个洞见合并为一个批次
    - 滑动窗口：只保留最近N个洞见
    - 时间过期：洞见超过TTL后自动丢弃
    - 垃圾过滤：过滤无效/重复/格式错误的洞见
    - 限流保护：防止PSI突发大量数据导致系统卡死
    """

    def __init__(self, max_size: int = 50, batch_size: int = 5,
                 drop_low_priority_threshold: float = 0.3,
                 ttl_seconds: float = 30.0,
                 max_drops_per_second: int = 100):
        self._buffer: deque = deque(maxlen=max_size)
        self._batch_size = batch_size
        self._drop_threshold = drop_low_priority_threshold
        self._ttl_seconds = ttl_seconds
        self._max_drops_per_second = max_drops_per_second
        self._lock = threading.RLock()
        self._seen_contents = set()
        self._dropped_count = 0
        self._dropped_in_last_second = 0
        self._last_drop_check_time = time.time()
        self._total_added = 0
        self._total_processed = 0
        self._total_expired = 0
        self._total_invalid = 0
        self._circuit_breaker_tripped = False
        self._circuit_breaker_time = 0.0
        self._circuit_breaker_cooldown = 5.0

    def add(self, insight: EmergenceInsight) -> bool:
        """添加洞见到缓冲器（增强版：输入验证、限流保护、TTL检查）"""
        if not self._validate_insight(insight):
            self._total_invalid += 1
            return False

        if self._is_circuit_breaker_tripped():
            self._dropped_count += 1
            return False

        with self._lock:
            self._total_added += 1

            self._clean_expired()

            if insight.content:
                content_hash = hash(insight.content[:100])
                if content_hash in self._seen_contents:
                    self._seen_contents.remove(content_hash)
                self._seen_contents.add(content_hash)

            if len(self._buffer) >= self._buffer.maxlen:
                if not self._should_keep_insight(insight):
                    self._increment_drop_count()
                    return False

            self._buffer.append(insight)
            return True

    def _validate_insight(self, insight: EmergenceInsight) -> bool:
        """验证洞见是否有效（防止垃圾数据）"""
        if insight is None:
            return False

        if not isinstance(insight, EmergenceInsight):
            logger.warning(f"无效洞见类型: {type(insight)}")
            return False

        if not insight.id or not isinstance(insight.id, str):
            logger.warning("洞见ID无效")
            return False

        if not insight.content or not isinstance(insight.content, str):
            logger.warning("洞见内容无效")
            return False

        if len(insight.content) > 10000:
            logger.warning(f"洞见内容过长 ({len(insight.content)} chars)")
            return False

        if insight.confidence is not None and (insight.confidence < 0 or insight.confidence > 1):
            logger.warning(f"置信度超出范围: {insight.confidence}")
            return False

        priority_values = ["high", "medium", "low"]
        if insight.priority not in priority_values:
            insight.priority = "medium"

        return True

    def _clean_expired(self):
        """清理过期的洞见"""
        now = time.time()
        while self._buffer:
            oldest = self._buffer[0]
            if now - oldest.timestamp > self._ttl_seconds:
                self._buffer.popleft()
                self._total_expired += 1
            else:
                break

    def _should_keep_insight(self, new_insight: EmergenceInsight) -> bool:
        """判断是否应该保留新洞见（基于优先级和当前缓冲内容）"""
        if len(self._buffer) < self._buffer.maxlen:
            return True

        priority_order = {"high": 3, "medium": 2, "low": 1}
        new_priority = priority_order.get(new_insight.priority, 2)

        for i, existing in enumerate(self._buffer):
            existing_priority = priority_order.get(existing.priority, 2)
            if new_priority > existing_priority:
                self._buffer[i] = new_insight
                return True

        if new_insight.priority != "low" or self._drop_threshold <= 0:
            self._buffer.popleft()
            self._buffer.append(new_insight)
            return True

        return False

    def _increment_drop_count(self):
        """增加丢弃计数并检查限流"""
        now = time.time()
        if now - self._last_drop_check_time >= 1.0:
            self._dropped_in_last_second = 0
            self._last_drop_check_time = now

        self._dropped_in_last_second += 1
        self._dropped_count += 1

        if self._dropped_in_last_second >= self._max_drops_per_second:
            logger.warning(f"丢弃率超过阈值 ({self._max_drops_per_second}/s)，触发限流保护")
            self._circuit_breaker_tripped = True
            self._circuit_breaker_time = now

    def _is_circuit_breaker_tripped(self) -> bool:
        """检查断路器是否触发"""
        if not self._circuit_breaker_tripped:
            return False

        if time.time() - self._circuit_breaker_time >= self._circuit_breaker_cooldown:
            self._circuit_breaker_tripped = False
            logger.info("断路器已重置")
            return False

        return True

    def get_batch(self, timeout_ms: float = 100.0) -> List[EmergenceInsight]:
        """
        获取一批洞见（增强版：超时保护、TTL检查）

        Args:
            timeout_ms: 获取超时时间（毫秒），防止阻塞
        """
        t0 = time.time()
        batch = []

        try:
            with self._lock:
                while self._buffer and len(batch) < self._batch_size:
                    if (time.time() - t0) * 1000 >= timeout_ms:
                        logger.warning(f"批量获取超时 ({timeout_ms}ms)")
                        break

                    insight = self._buffer.popleft()

                    if time.time() - insight.timestamp > self._ttl_seconds:
                        self._total_expired += 1
                        continue

                    insight.processed = True
                    batch.append(insight)

                self._total_processed += len(batch)
        except Exception as e:
            logger.error(f"批量获取洞见失败: {e}")

        return batch

    def peek(self) -> Optional[EmergenceInsight]:
        """查看最新的洞见而不移除"""
        try:
            with self._lock:
                self._clean_expired()
                return self._buffer[-1] if self._buffer else None
        except Exception as e:
            logger.error(f"查看洞见失败: {e}")
            return None

    def has_pending(self) -> bool:
        """是否有未处理的洞见"""
        try:
            with self._lock:
                self._clean_expired()
                return len(self._buffer) > 0
        except Exception as e:
            logger.error(f"检查待处理洞见失败: {e}")
            return False

    def size(self) -> int:
        """当前缓冲大小"""
        try:
            with self._lock:
                self._clean_expired()
                return len(self._buffer)
        except Exception as e:
            logger.error(f"获取缓冲大小失败: {e}")
            return 0

    def stats(self) -> Dict[str, Any]:
        """统计信息（增强版）"""
        try:
            with self._lock:
                self._clean_expired()
                high_priority = sum(1 for i in self._buffer if i.priority == "high")
                medium_priority = sum(1 for i in self._buffer if i.priority == "medium")
                low_priority = sum(1 for i in self._buffer if i.priority == "low")

                return {
                    "pending": len(self._buffer),
                    "max_size": self._buffer.maxlen,
                    "dropped": self._dropped_count,
                    "unique_contents": len(self._seen_contents),
                    "total_added": self._total_added,
                    "total_processed": self._total_processed,
                    "total_expired": self._total_expired,
                    "total_invalid": self._total_invalid,
                    "by_priority": {
                        "high": high_priority,
                        "medium": medium_priority,
                        "low": low_priority,
                    },
                    "circuit_breaker_tripped": self._circuit_breaker_tripped,
                    "dropped_in_last_second": self._dropped_in_last_second,
                }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}

    def clear(self):
        """清空缓冲器"""
        with self._lock:
            self._buffer.clear()
            self._seen_contents.clear()
            logger.info(f"缓冲器已清空")

    def force_drop_low_priority(self):
        """强制丢弃所有低优先级洞见（紧急释放内存）"""
        with self._lock:
            original_size = len(self._buffer)
            self._buffer = deque([i for i in self._buffer if i.priority != "low"],
                                maxlen=self._buffer.maxlen)
            dropped = original_size - len(self._buffer)
            if dropped > 0:
                self._dropped_count += dropped
                logger.info(f"强制丢弃 {dropped} 个低优先级洞见")


class CognitiveIntegration:
    """
    Harness与CognitiveBus的集成桥接器

    功能:
    1. 订阅PSI涌现洞见事件
    2. 将涌现洞见传递给Harness决策层
    3. 将Harness执行结果反馈给PSI
    4. 频率缓冲处理
    """

    def __init__(self, bus: Optional[CognitiveBus] = None, harness=None):
        self._bus = bus or self._create_bus()
        self._harness = harness
        self._buffer = RateBuffer(max_size=50, batch_size=3)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._processing_interval = 1.0
        self._insights_processed = 0
        self._execution_results: deque = deque(maxlen=20)

        self._register_events()
        self._subscribe_to_psi()

        logger.info("Harness CognitiveIntegration initialized")

    def _create_bus(self) -> CognitiveBus:
        """创建或获取全局CognitiveBus实例"""
        if not HAS_COGNITIVE_BUS:
            raise RuntimeError("CognitiveBus模块不可用")
        from laap.agi.cognitive_bus import get_bus
        return get_bus(agent_name="Aris")

    def _register_events(self):
        """注册自定义事件类型到CognitiveBus"""
        if not HAS_COGNITIVE_BUS:
            return

        for event_type in EmergenceEventType:
            if event_type.value not in [e.value for e in CognitiveEventType]:
                pass

        self._bus.register_module(
            "harness",
            version="1.0.0",
            capabilities=[
                "code_generation",
                "task_planning",
                "verification",
                "incremental_delivery",
                "emergence_engineering",
            ],
        )
        logger.info("Harness模块已注册到CognitiveBus")

    def _subscribe_to_psi(self):
        """订阅PSI相关事件"""
        if not HAS_COGNITIVE_BUS:
            return

        self._bus.subscribe(
            "harness",
            CognitiveEventType.CONSCIOUS_FRAME,
            self._on_conscious_frame,
        )
        self._bus.subscribe(
            "harness",
            CognitiveEventType.PREDICTION_ERROR,
            self._on_prediction_error,
        )
        self._bus.subscribe(
            "harness",
            CognitiveEventType.NEED_CHANGED,
            self._on_need_changed,
        )
        self._bus.subscribe(
            "harness",
            CognitiveEventType.EMOTION_CHANGED,
            self._on_emotion_changed,
        )
        logger.info("Harness已订阅CognitiveBus事件")

    def _on_conscious_frame(self, event: CognitiveEvent):
        """处理意识帧事件 — 从中提取涌现洞见"""
        data = event.data
        emerged_thought = data.get("emerged_thought", "")
        interference_pattern = data.get("interference_pattern", [])

        if emerged_thought:
            insight = EmergenceInsight(
                id=f"insight_{int(time.time())}_{hash(emerged_thought) % 1000}",
                content=emerged_thought,
                confidence=0.8,
                type="insight",
                source="psi_cycle",
                priority="high",
                tags=["emergence", "conscious"],
                related_needs={},
            )
            self._buffer.add(insight)
            logger.debug(f"涌现洞见已捕获: {emerged_thought[:50]}")

        for pattern in interference_pattern[:3]:
            if isinstance(pattern, tuple):
                topic = pattern[0]
            else:
                topic = str(pattern)

            insight = EmergenceInsight(
                id=f"pattern_{int(time.time())}_{hash(topic) % 1000}",
                content=f"检测到知识干涉模式: {topic}",
                confidence=0.7,
                type="pattern",
                source="quantum_knowledge",
                priority="medium",
                tags=["interference", "pattern"],
                related_needs={},
            )
            self._buffer.add(insight)

    def _on_prediction_error(self, event: CognitiveEvent):
        """处理预测误差事件"""
        error = event.data.get("error", 0.0)
        domain = event.data.get("domain", "")

        if error > 0.3:
            insight = EmergenceInsight(
                id=f"error_{int(time.time())}",
                content=f"预测误差超过阈值 ({domain}): {error:.2f}",
                confidence=0.9,
                type="self_correction",
                source="prediction_error",
                priority="high",
                tags=["error", "learning"],
                related_needs={"certainty": error},
            )
            self._buffer.add(insight)

    def _on_need_changed(self, event: CognitiveEvent):
        """处理需求变化事件"""
        changes = event.data
        for need, change in changes.items():
            old_val = change.get("old", 0.5)
            new_val = change.get("new", 0.5)
            delta = abs(new_val - old_val)

            if delta > 0.1:
                insight = EmergenceInsight(
                    id=f"need_{int(time.time())}_{hash(need)}",
                    content=f"需求变化: {need} 从 {old_val:.2f} 变为 {new_val:.2f}",
                    confidence=0.75,
                    type="need",
                    source="psi_needs",
                    priority="medium",
                    tags=["needs", "motivation"],
                    related_needs={need: delta},
                )
                self._buffer.add(insight)

    def _on_emotion_changed(self, event: CognitiveEvent):
        """处理情感变化事件"""
        changes = event.data
        if "valence" in changes:
            insight = EmergenceInsight(
                id=f"emotion_{int(time.time())}",
                content=f"情感变化: {changes['valence'].get('old', '?')} → {changes['valence'].get('new', '?')}",
                confidence=0.6,
                type="emotion",
                source="psi_emotion",
                priority="low",
                tags=["emotion"],
                related_needs={},
            )
            self._buffer.add(insight)

    def process_insights(self, batch_size: Optional[int] = None) -> List[EmergenceInsight]:
        """
        处理缓冲中的涌现洞见

        Args:
            batch_size: 批量获取的洞见数量，默认使用缓冲器的配置值

        返回: 已处理的洞见列表
        """
        if batch_size:
            old_batch_size = self._buffer._batch_size
            self._buffer._batch_size = batch_size

        batch = self._buffer.get_batch()

        if batch_size:
            self._buffer._batch_size = old_batch_size

        if not batch:
            return []

        self._insights_processed += len(batch)

        for insight in batch:
            self._process_single_insight(insight)

        return batch

    def _process_single_insight(self, insight: EmergenceInsight):
        """处理单个涌现洞见 — 将其转化为Harness任务"""
        logger.info(f"处理涌现洞见 [{insight.priority}]: {insight.content[:80]}")

        if self._harness:
            try:
                task_description = f"基于涌现洞见实现: {insight.content}"
                context = {
                    "insight_id": insight.id,
                    "insight_type": insight.type,
                    "confidence": insight.confidence,
                    "source": insight.source,
                    "related_needs": insight.related_needs,
                }

                self._harness.process_insight(task_description, context)
                logger.debug(f"洞见已传递给Harness决策层")
            except Exception as e:
                logger.warning(f"洞见处理失败: {e}")

    def submit_execution_result(self, result: HarnessExecutionResult):
        """
        将Harness执行结果反馈给PSI

        这是Harness → PSI的关键路径
        """
        self._execution_results.append(result)

        if result.success:
            self._update_psi_positive(result)
        else:
            self._update_psi_negative(result)

        self._publish_execution_event(result)

        logger.info(f"Harness执行结果反馈: {result.task_id} {'成功' if result.success else '失败'}")

    def _update_psi_positive(self, result: HarnessExecutionResult):
        """成功执行后更新PSI状态"""
        if not HAS_COGNITIVE_BUS:
            return

        self._bus.set_needs(
            competence=min(1.0, self._bus.needs.competence + 0.05),
            certainty=min(1.0, self._bus.needs.certainty + 0.03),
            growth=min(1.0, self._bus.needs.growth + 0.02),
        )

        if result.verification_passed:
            self._bus.set_emotion(
                valence=EmotionalValence.POSITIVE_MILD,
                arousal=min(1.0, self._bus.emotion.arousal + 0.1),
            )

    def _update_psi_negative(self, result: HarnessExecutionResult):
        """失败执行后更新PSI状态"""
        if not HAS_COGNITIVE_BUS:
            return

        self._bus.set_needs(
            competence=max(0.1, self._bus.needs.competence - 0.05),
            certainty=max(0.1, self._bus.needs.certainty - 0.03),
        )

        self._bus.report_prediction_error(
            domain="harness_execution",
            predicted=0.8,
            actual=0.0,
            source="harness",
        )

        self._bus.set_emotion(
            valence=EmotionalValence.NEGATIVE_MILD,
            arousal=min(1.0, self._bus.emotion.arousal + 0.15),
        )

    def _publish_execution_event(self, result: HarnessExecutionResult):
        """发布执行结果事件到CognitiveBus"""
        if not HAS_COGNITIVE_BUS:
            return

        self._bus.publish(
            CognitiveEventType.ACTION_TAKEN,
            "harness",
            {
                "task_id": result.task_id,
                "success": result.success,
                "output": result.output[:200],
                "error": result.error[:200],
                "tokens_used": result.tokens_used,
                "duration": result.duration,
                "verification_passed": result.verification_passed,
            },
        )

    def get_cognitive_context(self) -> Dict[str, Any]:
        """获取当前认知上下文供Harness决策层使用"""
        if not HAS_COGNITIVE_BUS:
            return {
                "needs": {"competence": 0.5, "autonomy": 0.5, "relatedness": 0.5,
                          "certainty": 0.5, "growth": 0.5},
                "emotion": {"valence": "neutral", "arousal": 0.5, "dominance": 0.5},
                "attention": {"focus": "idle", "intensity": 0.5},
                "curiosity": 0.3,
                "insights_pending": self._buffer.size(),
            }

        snapshot = self._bus.snapshot()
        return {
            "needs": snapshot.needs.to_dict(),
            "emotion": snapshot.emotion.to_dict(),
            "attention": snapshot.attention.to_dict(),
            "curiosity": snapshot.curiosity,
            "self_presence": snapshot.self_presence,
            "insights_pending": self._buffer.size(),
            "active_modules": snapshot.active_modules,
            "cycle_count": self._bus.cycle_count,
        }

    def start(self):
        """启动后台处理线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="harness-cognitive-integration",
        )
        self._thread.start()
        logger.info("Harness CognitiveIntegration后台线程已启动")

    def stop(self):
        """停止后台处理线程"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Harness CognitiveIntegration后台线程已停止")

    def _background_loop(self):
        """后台处理循环 — 定期处理缓冲中的洞见（增强版：异常处理和超时保护）"""
        while self._running:
            try:
                self.process_insights()
                if HAS_COGNITIVE_BUS and self._bus:
                    try:
                        self._bus.module_heartbeat("harness")
                    except Exception as heartbeat_e:
                        logger.debug(f"心跳发送失败: {heartbeat_e}")
            except Exception as e:
                logger.warning(f"后台处理循环异常: {e}")

            try:
                time.sleep(self._processing_interval)
            except KeyboardInterrupt:
                break

    def stats(self) -> Dict[str, Any]:
        """统计信息（增强版：异常处理）"""
        try:
            buffer_stats = self._buffer.stats()
            bus_modules = 0
            if HAS_COGNITIVE_BUS and self._bus:
                try:
                    bus_modules = len(self._bus.get_online_modules())
                except Exception:
                    bus_modules = 0

            return {
                "running": self._running,
                "insights_processed": self._insights_processed,
                "execution_results_pending": len(self._execution_results),
                "buffer": buffer_stats,
                "bus_modules": bus_modules,
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}


# ════════════════════════════════════════════════════════════
# 便捷接口
# ════════════════════════════════════════════════════════════

_integration_instance: Optional[CognitiveIntegration] = None


def get_integration(bus: Optional[CognitiveBus] = None, harness=None) -> CognitiveIntegration:
    """获取/创建全局CognitiveIntegration实例"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = CognitiveIntegration(bus=bus, harness=harness)
    return _integration_instance


def start_integration(bus: Optional[CognitiveBus] = None, harness=None):
    """启动认知集成"""
    integration = get_integration(bus=bus, harness=harness)
    integration.start()
    return integration


def stop_integration():
    """停止认知集成"""
    global _integration_instance
    if _integration_instance:
        _integration_instance.stop()
        _integration_instance = None


def process_pending_insights(batch_size: Optional[int] = None) -> List[EmergenceInsight]:
    """处理待处理的涌现洞见"""
    integration = get_integration()
    return integration.process_insights(batch_size=batch_size)


def get_context() -> Dict[str, Any]:
    """获取当前认知上下文"""
    integration = get_integration()
    return integration.get_cognitive_context()