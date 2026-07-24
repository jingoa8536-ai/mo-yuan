"""
模拟场景测试脚本：
1. 情感波动：PSI情感从平静→兴奋→焦虑→恐惧→恢复
2. 突发需求：突然产生高优先级需求（安全保护、能力提升）
3. 垃圾数据攻击：PSI发送大量无效/重复/超大洞见
4. PSI突然停止：模拟PSI崩溃或网络中断
5. RateBuffer验证：验证缓冲机制是否正常工作

运行方式：python test_simulation_scenario.py
"""

import sys
import time
import threading
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("test_simulation")

print('=' * 70)
print('模拟场景测试：情感波动 + 突发需求 + 垃圾数据攻击')
print('=' * 70)

try:
    from core.cognitive_integration import (
        RateBuffer,
        EmergenceInsight,
        get_integration,
        get_context,
        start_integration,
        stop_integration,
        process_pending_insights,
    )
    from core.harness import ConsciousnessHarness
except ImportError as e:
    print(f'导入失败: {e}')
    sys.exit(1)


class PSISimulator:
    """模拟PSI行为"""

    def __init__(self, buffer: RateBuffer):
        self._buffer = buffer
        self._running = True
        self._thread = None
        self._emotion_level = 0.5
        self._emotion_direction = 1
        self._spam_mode = False
        self._spam_count = 0
        self._normal_insights_sent = 0

    def start(self):
        """启动模拟PSI"""
        self._running = True
        self._thread = threading.Thread(target=self._simulate, daemon=True)
        self._thread.start()
        logger.info("[PSI] 模拟PSI已启动")

    def stop(self):
        """停止模拟PSI"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[PSI] 模拟PSI已停止")

    def trigger_emotion_spike(self, intensity: float = 0.9):
        """触发情感峰值"""
        self._emotion_level = intensity
        logger.info(f"[PSI] 情感峰值触发: {intensity}")

    def trigger_urgent_need(self, need_type: str = "safety"):
        """触发紧急需求"""
        insight = EmergenceInsight(
            id=f"urgent_{int(time.time())}",
            content=f"紧急需求: {need_type}保护机制需要立即增强！",
            confidence=0.95,
            type="need",
            source="psi_simulation",
            priority="high",
            tags=["urgent", need_type],
            related_needs={need_type: 0.9},
        )
        self._buffer.add(insight)
        logger.info(f"[PSI] 紧急需求已发送: {need_type}")

    def start_spam_attack(self, duration: int = 5):
        """启动垃圾数据攻击"""
        self._spam_mode = True
        logger.info(f"[PSI] 垃圾数据攻击开始，持续{duration}秒")

        def stop_spam():
            time.sleep(duration)
            self._spam_mode = False
            logger.info(f"[PSI] 垃圾数据攻击结束，共发送{self._spam_count}条垃圾数据")

        threading.Thread(target=stop_spam, daemon=True).start()

    def _simulate(self):
        """主模拟循环"""
        while self._running:
            try:
                self._update_emotion()

                if self._spam_mode:
                    self._send_spam_insights()
                else:
                    self._send_normal_insights()

                time.sleep(0.01)
            except Exception as e:
                logger.error(f"[PSI] 模拟异常: {e}")

    def _update_emotion(self):
        """更新情感状态"""
        self._emotion_level += self._emotion_direction * 0.02
        if self._emotion_level >= 0.9 or self._emotion_level <= 0.1:
            self._emotion_direction *= -1

    def _send_normal_insights(self):
        """发送正常洞见"""
        if random.random() < 0.3:
            self._normal_insights_sent += 1

            insight_types = [
                ("insight", "medium"),
                ("pattern", "medium"),
                ("self_correction", "high"),
                ("need", "medium"),
                ("emotion", "low"),
            ]

            insight_type, priority = random.choice(insight_types)

            content_templates = {
                "insight": [
                    "发现新的代码优化模式",
                    "检测到潜在的安全漏洞",
                    "识别出重复的代码逻辑",
                    "建议重构现有架构",
                    "发现更好的算法实现",
                ],
                "pattern": [
                    "检测到知识干涉模式: 安全",
                    "检测到知识干涉模式: 性能",
                    "检测到知识干涉模式: 架构",
                    "检测到知识干涉模式: 设计",
                ],
                "self_correction": [
                    "预测误差超过阈值，需要修正",
                    "模型偏差检测，需要重新校准",
                    "置信度下降，需要验证",
                ],
                "need": [
                    f"能力需求增强: 当前情感{self._emotion_level:.2f}",
                    "自主性需求未满足",
                    "关联性需求增强",
                ],
                "emotion": [
                    f"情感变化: 当前兴奋度{self._emotion_level:.2f}",
                    f"情感波动: 方向{'上升' if self._emotion_direction > 0 else '下降'}",
                ],
            }

            content = random.choice(content_templates.get(insight_type, ["未知洞见"]))

            insight = EmergenceInsight(
                id=f"sim_{int(time.time())}_{self._normal_insights_sent}",
                content=content,
                confidence=random.uniform(0.5, 0.95),
                type=insight_type,
                source="psi_simulation",
                priority=priority,
                tags=[insight_type],
            )

            added = self._buffer.add(insight)
            if not added and self._normal_insights_sent % 50 == 0:
                logger.debug(f"[PSI] 洞见被丢弃（缓冲区满或限流）")

    def _send_spam_insights(self):
        """发送垃圾数据"""
        spam_types = [
            ("empty", ""),
            ("repeating", "重复内容重复内容重复内容"),
            ("huge", "x" * 10001),
            ("invalid_confidence", "无效置信度"),
            ("null", None),
            ("random", ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=100))),
        ]

        spam_type, content = random.choice(spam_types)

        if spam_type == "null":
            self._buffer.add(None)
            self._spam_count += 1
            return

        insight = EmergenceInsight(
            id=f"spam_{int(time.time())}_{self._spam_count}",
            content=content,
            confidence=2.5 if spam_type == "invalid_confidence" else random.uniform(0.1, 0.9),
            type="spam",
            source="psi_spam",
            priority="low",
        )

        self._buffer.add(insight)
        self._spam_count += 1


def run_simulation():
    """运行完整模拟"""
    print('\n[1/5] 初始化测试环境')
    harness = ConsciousnessHarness(workdir=r"D:\LAAP")
    integration = get_integration()
    buffer = integration._buffer

    simulator = PSISimulator(buffer)
    simulator.start()

    print('\n[2/5] 情感波动阶段（5秒）')
    print('-' * 50)
    for i in range(5):
        time.sleep(1)
        stats = buffer.stats()
        print(f'  第{i+1}秒 - 缓冲: {stats["pending"]}, 已处理: {stats["total_processed"]}, '
              f'已丢弃: {stats["dropped"]}, 无效: {stats["total_invalid"]}')

    print('\n[3/5] 突发需求阶段')
    print('-' * 50)
    simulator.trigger_emotion_spike(0.9)
    simulator.trigger_urgent_need("safety")
    simulator.trigger_urgent_need("competence")

    time.sleep(2)
    stats = buffer.stats()
    print(f'  紧急需求后 - 缓冲: {stats["pending"]}, 高优先级: {stats["by_priority"]["high"]}')

    insights = process_pending_insights(batch_size=10)
    print(f'  处理洞见数: {len(insights)}')
    for insight in insights:
        if insight.priority == "high":
            print(f'    - [高优先级] {insight.content[:60]}')

    print('\n[4/5] 垃圾数据攻击阶段（5秒）')
    print('-' * 50)
    simulator.start_spam_attack(duration=5)

    for i in range(5):
        time.sleep(1)
        stats = buffer.stats()
        print(f'  第{i+1}秒 - 缓冲: {stats["pending"]}, 已处理: {stats["total_processed"]}, '
              f'已丢弃: {stats["dropped"]}, 无效: {stats["total_invalid"]}, '
              f'断路器触发: {stats["circuit_breaker_tripped"]}')

    print('\n[5/5] PSI停止 + Harness继续运行')
    print('-' * 50)
    simulator.stop()

    print('  PSI已停止，Harness继续处理剩余洞见...')
    for i in range(3):
        insights = process_pending_insights(batch_size=5)
        print(f'  处理剩余洞见: {len(insights)}个')
        time.sleep(1)

    stats = buffer.stats()
    print(f'\n  最终统计:')
    print(f'    总添加: {stats["total_added"]}')
    print(f'    总处理: {stats["total_processed"]}')
    print(f'    总丢弃: {stats["dropped"]}')
    print(f'    总过期: {stats["total_expired"]}')
    print(f'    总无效: {stats["total_invalid"]}')

    print('\n[最终] 运行Harness主循环')
    print('-' * 50)
    result = harness.run("创建一个简单的Python工具函数")
    print(f'  任务状态: {result["status"]}')
    print(f'  认知上下文: {result["cognitive_context"]}')
    print(f'  处理洞见数: {result["insights_processed"]}')

    stop_integration()
    print('\n模拟测试完成!')


if __name__ == "__main__":
    try:
        run_simulation()
    except KeyboardInterrupt:
        print('\n测试被中断')
        sys.exit(0)
    except Exception as e:
        print(f'\n测试异常: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)