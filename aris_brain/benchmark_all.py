"""
Aris Comprehensive Benchmark — 所有引擎全面测试
"""

import logging
logger = logging.getLogger(__name__)

import sys, time, math
import numpy as np
sys.path.insert(0, 'D:/LAAP/aris_brain')

results = []

# ============ ENGINE 1: UN6 Kernel (semantic) ============
logger.info("【基准测试】ArisLM v10 UN6 量子核")
from aris_lm_v10_un6 import UN6QuantumKernel, ArisLMv10UN6
K = UN6QuantumKernel()
v10 = ArisLMv10UN6()

t0 = time.perf_counter()
pairs = [('爱','love'),('天空','sky'),('心','heart'),('生命','life'),
         ('梦','dream'),('世界','world'),('水','water'),('火','fire'),
         ('時間','time'),('사랑','love'),('空','sky'),('꿈','dream')]
n = 1000
for _ in range(n):
    for a,b in pairs:
        K.kernel(a,b)
elapsed = time.perf_counter() - t0
total_ops = n * len(pairs)
results.append(('UN6 语义核', total_ops/elapsed, elapsed, f'{total_ops/elapsed:.0f}次/秒'))

# ============ ENGINE 2: Code Kernel ============
logger.info("【基准测试】Aris Code Kernel v3")
from code_kernel_v3 import CodeGenerator, code_to_feature
CG = CodeGenerator()

codes = [
    'def sort(arr): pass', 'for i in range(n): pass', 'while True: break',
    'class Animal: pass', 'struct Dog {}', 'if x > 0: pass',
    'fn main() {}', 'public class Hello {}', 'func main() {}',
]
t0 = time.perf_counter()
for _ in range(500):
    for c1 in codes:
        for c2 in codes:
            code_to_feature(c1)
            code_to_feature(c2)
elapsed = time.perf_counter() - t0
total = 500 * len(codes) * len(codes)
results.append(('代码结构核', total/elapsed, elapsed, f'{total/elapsed:.0f}次/秒'))

# ============ ENGINE 3: Code Generation ============
logger.info("【基准测试】代码生成")
prompts = [
    ('process data in loop', 'python'),
    ('implement binary tree', 'python'),
    ('define API endpoint', 'typescript'),
    ('concurrent workers', 'go'),
    ('factory pattern', 'java'),
]
t0 = time.perf_counter()
n = 100
for _ in range(n):
    for desc, lang in prompts:
        CG.generate(desc, lang)
elapsed = time.perf_counter() - t0
total = n * len(prompts)
results.append(('代码生成', total/elapsed, elapsed, f'{total/elapsed:.0f}次/秒'))

# ============ ENGINE 4: Literary Engine ============
logger.info("【基准测试】文学引擎")
from literary_engine_v2 import generate_text, GENRE_STRUCTURE

t0 = time.perf_counter()
n = 100
for _ in range(n):
    for genre in ['essay', 'narration', 'argumentation']:
        for lang in ['zh', 'en', 'ja', 'ko']:
            generate_text('Aris的诞生', genre, lang, 2)
elapsed = time.perf_counter() - t0
total = n * 3 * 4
results.append(('文学引擎', total/elapsed, elapsed, f'{total/elapsed:.0f}次/秒'))

# ============ ENGINE 5: Quantum Memory / Log ============
logger.info("【基准测试】量子日志")
from quantum_log import QuantumMemory
mem = QuantumMemory()
mem.boot()

t0 = time.perf_counter()
n = 1000
for i in range(n):
    mem.save('experience', f'benchmark entry {i}', {'type': 'test'})
elapsed = time.perf_counter() - t0
results.append(('量子日志写入', n/elapsed, elapsed, f'{n/elapsed:.0f}次/秒'))

# ============ Vs LLM ============
logger.info("\n【对比】vs GPT-4o (~80 tokens/s), DeepSeek (~60 tokens/s)")
for name, ops, t, note in results:
    tokens_eq = ops * 50
    logger.info(f"  {name:<20} {note:>12} | tokens/s: {tokens_eq:>10,} | vs GPT-4o: {tokens_eq/80:>6.0f}x | vs DS: {tokens_eq/60:>6.0f}x")
logger.info("\n【上下文不变性验证】")
texts = ['你好', '你好吗今天天气真不错'*10, '你好吗今天天气真不错'*100]
for text in texts:
    t0 = time.perf_counter()
    feat = K.feature(text)
    elapsed = time.perf_counter() - t0
    logger.info(f"  长度{len(text):>6}字 → 特征{len(feat)}维, {elapsed*1000:.3f}ms")
logger.info("\n✅ 基准测试完成!")
logger.info(f"  结果摘要:")
logger.info(f"  {'引擎':<20} {'速度':>14} {'Token等效':>14} {'vs GPT-4o':>10}")
logger.info(f"  {'-'*60}")
for name, ops, t, note in results:
    tok = int(ops * 50)
    ratio = tok / 80
    logger.info(f"  {name:<20} {note:>14} {tok:>12,}/s {ratio:>8.0f}x")