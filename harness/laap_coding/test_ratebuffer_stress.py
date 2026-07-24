"""
RateBuffer压力测试：验证异常处理和防御机制
"""

import sys
import time
import threading
import random
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("test_ratebuffer")

print('=' * 70)
print('RateBuffer压力测试：异常处理和防御机制')
print('=' * 70)

try:
    from core.cognitive_integration import RateBuffer, EmergenceInsight
except ImportError as e:
    print(f'导入失败: {e}')
    sys.exit(1)


def test_normal_operation():
    """测试正常操作"""
    print('\n[1/6] 正常操作测试')
    buffer = RateBuffer(max_size=10, batch_size=3)

    for i in range(15):
        insight = EmergenceInsight(
            id=f"normal_{i}",
            content=f"正常洞见{i}",
            confidence=0.8,
            type="insight",
            source="test",
            priority="medium",
        )
        buffer.add(insight)

    stats = buffer.stats()
    print(f'  缓冲大小: {stats["pending"]}')
    print(f'  已添加: {stats["total_added"]}')
    print(f'  已丢弃: {stats["dropped"]}')

    batch = buffer.get_batch()
    print(f'  批量获取: {len(batch)}个')

    assert stats["pending"] == 10, "缓冲大小不正确"
    assert len(batch) == 3, "批量获取数量不正确"
    print('  ✓ 通过')


def test_garbage_data():
    """测试垃圾数据过滤"""
    print('\n[2/6] 垃圾数据过滤测试')
    buffer = RateBuffer(max_size=10)

    garbage_types = [
        None,
        "not an insight object",
        EmergenceInsight(id="", content="", confidence=0.5, type="test", source="test"),
        EmergenceInsight(id="test", content="", confidence=0.5, type="test", source="test"),
        EmergenceInsight(id="test", content="x" * 10001, confidence=0.5, type="test", source="test"),
        EmergenceInsight(id="test", content="test", confidence=2.5, type="test", source="test"),
        EmergenceInsight(id="test", content="test", confidence=-0.5, type="test", source="test"),
    ]

    for garbage in garbage_types:
        buffer.add(garbage)

    stats = buffer.stats()
    print(f'  无效洞见数: {stats["total_invalid"]}')
    print(f'  缓冲大小: {stats["pending"]}')

    assert stats["total_invalid"] == len(garbage_types), "无效洞见计数不正确"
    assert stats["pending"] == 0, "缓冲中不应该有洞见"
    print('  ✓ 通过')


def test_priority_filtering():
    """测试优先级过滤"""
    print('\n[3/6] 优先级过滤测试')
    buffer = RateBuffer(max_size=5)

    for i in range(10):
        priority = "high" if i % 3 == 0 else "low"
        insight = EmergenceInsight(
            id=f"prio_{i}",
            content=f"洞见{i}",
            confidence=0.8,
            type="insight",
            source="test",
            priority=priority,
        )
        buffer.add(insight)

    stats = buffer.stats()
    print(f'  高优先级洞见数: {stats["by_priority"]["high"]}')
    print(f'  低优先级洞见数: {stats["by_priority"]["low"]}')
    print(f'  已丢弃: {stats["dropped"]}')

    assert stats["by_priority"]["high"] >= 2, "高优先级洞见应该被保留"
    print('  ✓ 通过')


def test_circuit_breaker():
    """测试断路器机制"""
    print('\n[4/6] 断路器机制测试')
    buffer = RateBuffer(max_size=5, max_drops_per_second=10)

    def spam_insights():
        for i in range(50):
            insight = EmergenceInsight(
                id=f"spam_{i}",
                content=f"垃圾洞见{i}",
                confidence=0.1,
                type="spam",
                source="test",
                priority="low",
            )
            buffer.add(insight)
            time.sleep(0.05)

    thread = threading.Thread(target=spam_insights, daemon=True)
    thread.start()
    thread.join()

    stats = buffer.stats()
    print(f'  断路器触发: {stats["circuit_breaker_tripped"]}')
    print(f'  已丢弃: {stats["dropped"]}')
    print(f'  缓冲大小: {stats["pending"]}')

    if stats["circuit_breaker_tripped"]:
        print('  等待断路器重置...')
        time.sleep(6)
        test_insight = EmergenceInsight(id="test_reset", content="test", confidence=0.8, type="test", source="test")
        buffer.add(test_insight)
        stats = buffer.stats()
        print(f'  断路器重置后状态: {stats["circuit_breaker_tripped"]}')
        assert not stats["circuit_breaker_tripped"], "断路器应该已重置"

    print('  ✓ 通过')


def test_ttl_expiration():
    """测试TTL过期机制"""
    print('\n[5/6] TTL过期测试')
    buffer = RateBuffer(max_size=10, ttl_seconds=1.0)

    for i in range(5):
        insight = EmergenceInsight(
            id=f"ttl_{i}",
            content=f"洞见{i}",
            confidence=0.8,
            type="insight",
            source="test",
            priority="medium",
        )
        buffer.add(insight)

    print(f'  添加后缓冲大小: {buffer.size()}')

    time.sleep(2)
    stats = buffer.stats()
    print(f'  2秒后缓冲大小: {buffer.size()}')
    print(f'  过期洞见数: {stats["total_expired"]}')

    assert buffer.size() == 0, "洞见应该已过期"
    assert stats["total_expired"] >= 5, "过期洞见计数不正确"
    print('  ✓ 通过')


def test_concurrent_access():
    """测试并发访问"""
    print('\n[6/6] 并发访问测试')
    buffer = RateBuffer(max_size=100, ttl_seconds=60)

    def producer():
        for i in range(1000):
            insight = EmergenceInsight(
                id=f"concurrent_{i}",
                content=f"并发洞见{i}",
                confidence=0.8,
                type="insight",
                source="test",
                priority="medium",
            )
            buffer.add(insight)
            time.sleep(0.001)

    def consumer():
        while buffer.has_pending():
            buffer.get_batch()
            time.sleep(0.005)

    producer_thread = threading.Thread(target=producer, daemon=True)
    consumer_thread = threading.Thread(target=consumer, daemon=True)

    producer_thread.start()
    consumer_thread.start()

    producer_thread.join(timeout=10)
    time.sleep(1)
    while buffer.has_pending():
        buffer.get_batch()
        time.sleep(0.1)

    stats = buffer.stats()
    print(f'  总添加: {stats["total_added"]}')
    print(f'  总处理: {stats["total_processed"]}')
    print(f'  缓冲剩余: {stats["pending"]}')
    print(f'  已丢弃: {stats["dropped"]}')
    print(f'  已过期: {stats["total_expired"]}')
    print(f'  无效: {stats["total_invalid"]}')

    assert stats["pending"] == 0, "不应该有剩余洞见"
    total_accounted = stats["total_processed"] + stats["total_expired"] + stats["pending"] + stats["dropped"]
    print(f'  总核对: {total_accounted}')
    assert total_accounted == stats["total_added"], "总数核对不正确"
    print('  ✓ 通过')


if __name__ == "__main__":
    try:
        test_normal_operation()
        test_garbage_data()
        test_priority_filtering()
        test_circuit_breaker()
        test_ttl_expiration()
        test_concurrent_access()

        print('\n' + '=' * 70)
        print('所有RateBuffer压力测试通过!')
        print('=' * 70)
        sys.exit(0)
    except AssertionError as e:
        print(f'\n测试失败: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n测试异常: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)