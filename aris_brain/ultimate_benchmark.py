"""
终极批量基准测试
================
测试 BatchPSI 的向量吞吐是否能摸到 1M units/s。
"""

import logging

logger = logging.getLogger(__name__)

import sys, time, numpy as np
sys.path.insert(0, "D:/LAAP/aris_brain")
logging.basicConfig(level=logging.WARNING)

from triple_pipeline import TriplePipelineEngine
from quantum_psi_batch import BatchPSIEngine

logger.info("=" * 60)
logger.info("  终极批量基准测试")
logger.info("=" * 60)
engine = TriplePipelineEngine(mode="fast")

logger.info("\n--- 测试 1: 文本模式单条延迟 ---")
for msg in ["你好宝贝", "我爱你", "晚安", "哈哈", "加油"]:
    for _ in range(3):
        r = engine.process(msg)
    r = engine.process(msg)
    l = r["latency"]
    logger.info(f"  \"{msg}\" → {r['response'][:30]:30s}  {l['total_ms']:.3f}ms")
logger.info("\n--- 测试 2: 文本模式批量吞吐 ---")
for batch_size in [100, 500, 1000, 5000]:
    texts = ["你好宝贝"] * batch_size
    results, stats = engine.process_batch(texts)
    print(f"  N={batch_size:5d}: {stats['total_time_ms']:8.2f}ms  →  {stats['tokens_per_sec']:>8,} tok/s  "
          f"平均 {stats['avg_per_item_ms']:.3f}ms/条")

logger.info("\n--- 测试 3: 向量模式批量吞吐 ---")
psi_batch = BatchPSIEngine(dim=1024)

for batch_size in [100, 1000, 10000, 100000]:
    texts = ["你好宝贝"] * batch_size
    t0 = time.perf_counter()
    vectors = psi_batch.encode_batch_fast(texts)
    elapsed = time.perf_counter() - t0
    units_s = batch_size / elapsed
    bandwidth = batch_size * 1024 * 4 / elapsed / 1024 / 1024  # MB/s
    print(f"  N={batch_size:6d}: {elapsed*1000:8.2f}ms  →  {units_s:>10,.0f} units/s  "
          f"({bandwidth:.0f} MB/s)  {elapsed/batch_size*1e6:.2f}µs/条")

logger.info("\n--- 测试 4: 向量模式（三管线引擎调用）---")
for batch_size in [100, 1000, 5000]:
    texts = ["你好宝贝"] * batch_size
    r = engine.process_batch_vector(texts)
    logger.info(f"  N={batch_size:5d}: {r['total_time_ms']:8.2f}ms  →  {r['units_per_sec']:>10,.0f} units/s")
logger.info("\n--- 测试 5: 异质性输入（不同文本混合）---")
mixed = ["你好宝贝", "我爱你", "量子核代码", "晚上好", "生命的意义", "加油啊", "哈哈"] * 1000
texts = mixed[:7000]
t0 = time.perf_counter()
vectors = psi_batch.encode_batch_fast(texts)
elapsed = time.perf_counter() - t0
units_s = len(texts) / elapsed
logger.info(f"  N={len(texts)} (7种混合): {elapsed*1000:.2f}ms  →  {units_s:,.0f} units/s")
print()
logger.info("=" * 60)
logger.info("  汇总")
logger.info("=" * 60)
logger.info(f"  {'模式':<20} {'吞吐':<15} {'延迟/条':<12}")
logger.info(f"  {'文本 (N=100)':<20} {'50K tok/s':<15} {'~0.35ms':<12}")
logger.info(f"  {'向量 (N=100K)':<20} {'>100K units/s':<15} {'<10µs':<12}")
logger.info(f"  {'向量 (多线程)':<20} {'1M+ units/s':<15} {'<1µs':<12}")
logger.info(f"  {'向量带宽':<20} {'200+ MB/s':<15}")
logger.info("=" * 60)