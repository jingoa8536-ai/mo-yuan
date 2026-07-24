"""
Aris Quantum Kernel — 全领域基准测试
======================================
测试代码理解、数学、物理、跨语言的准确度和速度。
对比LLM，评估是否可替代。
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, math
sys.path.insert(0, '.')
import numpy as np

# ================================================================
# 导入所有引擎
# ================================================================
from aris_lm_v11_code_kernel import CodeQuantumKernel, ast_fingerprint
from aris_lm_v10_un6 import UN6QuantumKernel

CK = CodeQuantumKernel()
UN6 = UN6QuantumKernel()

results = []
def test(category, name, score, note=''):
    results.append({'category': category, 'name': name, 'score': score, 'note': note})
    tag = '🟢' if score >= 0.7 else '🟡' if score >= 0.4 else '🔴'
    logger.info(f"  {tag} {name:<40} = {score:.3f} {note}")
# 1. 代码理解
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("1️⃣  代码理解领域")
logger.info("=" * 60)
lang_tests = [
    ('python', 'def fibonacci(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)'),
    ('rust', 'fn main() {\n    let x = 42;\n    println!("{}", x);\n}'),
    ('cpp', '#include <iostream>\nint main() { std::cout << "hello"; }'),
    ('javascript', 'function hello() {\n    console.log("world");\n}'),
    ('go', 'package main\nfunc main() {\n    println("hello")\n}'),
]
logger.info("\n【代码语言检测】")
for expected, code in lang_tests:
    detected = CK.detect_language(code)
    score = 1.0 if detected == expected else 0.0
    test('code_lang', f'检测{expected}', score, f'→ {detected}')

# 1.2 同算法匹配
logger.info("\n【同算法识别】")
fib_recur = '''
def fib(n):
    if n <= 1: return n
    return fib(n-1) + fib(n-2)
'''
fib_dp = '''
def fib_dp(n):
    dp = [0, 1] + [0]*(n-1)
    for i in range(2, n+1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
'''
quick = '''
def qsort(arr):
    if len(arr) <= 1: return arr
    p = arr[0]
    return qsort([x for x in arr[1:] if x <= p]) + [p] + qsort([x for x in arr[1:] if x > p])
'''
bfs_code = '''
def bfs(graph, start):
    visited, queue = {start}, [start]
    while queue:
        v = queue.pop(0)
        for n in graph[v]:
            if n not in visited:
                visited.add(n)
                queue.append(n)
    return visited
'''
sort_bubble = '''
def bubble(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr
'''
sort_merge = '''
def merge_sort(arr):
    if len(arr) <= 1: return arr
    mid = len(arr)//2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)
def merge(l, r):
    result = []
    while l and r:
        if l[0] <= r[0]: result.append(l.pop(0))
        else: result.append(r.pop(0))
    return result + l + r
'''
algo_pairs = [
    ('fib递归 vs DP', fib_recur, fib_dp),
    ('冒泡 vs 归并', sort_bubble, sort_merge),
    ('归并 vs 快速', sort_merge, quick),
    ('BFS vs fib递归', bfs_code, fib_recur),
]
for name, a, b in algo_pairs:
    s = CK.kernel(a, b)
    test('code_algo', name, s)

# 1.3 不同语言同算法
logger.info("\n【跨语言同算法】")
py_quick = '''
def qsort(arr):
    if len(arr) <= 1: return arr
    p = arr[0]
    return qsort([x for x in arr[1:] if x <= p]) + [p] + qsort([x for x in arr[1:] if x > p])
'''
rs_quick = '''
fn qsort(mut arr: Vec<i32>) -> Vec<i32> {
    if arr.len() <= 1 { return arr; }
    let p = arr.remove(0);
    let left: Vec<i32> = arr.iter().filter(|&x| *x <= p).cloned().collect();
    let right: Vec<i32> = arr.iter().filter(|&x| *x > p).cloned().collect();
    [qsort(left), vec![p], qsort(right)].concat()
}
'''
js_quick = '''
function qsort(arr) {
    if (arr.length <= 1) return arr;
    const p = arr[0];
    const left = arr.slice(1).filter(x => x <= p);
    const right = arr.slice(1).filter(x => x > p);
    return [...qsort(left), p, ...qsort(right)];
}
'''
clang_pairs = [
    ('Python vs Rust 快排', py_quick, rs_quick),
    ('Python vs JS 快排', py_quick, js_quick),
    ('Rust vs JS 快排', rs_quick, js_quick),
]
for name, a, b in clang_pairs:
    s = CK.kernel(a, b)
    test('code_cross_lang', name, s)


# ================================================================
# 2. 数学领域
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("2️⃣  数学领域")
logger.info("=" * 60)
math_pairs = [
    ('E=mc² vs 质能方程', 'E = mc^2', 'E equals m c squared'),
    ('欧拉公式 vs e^iπ+1=0', 'e^(i*pi) + 1 = 0', "Euler's identity"),
    ('勾股定理 vs 直角三角形', 'a^2 + b^2 = c^2', 'Pythagorean theorem'),
    ('牛顿第二定律 vs F=ma', 'F = ma', "Newton's second law"),
    ('麦克斯韦方程 vs 电磁学', "Maxwell's equations", 'electromagnetic wave'),
    ('微积分基本定理 vs 导数', 'integral', 'derivative'),
    ('傅里叶变换 vs 频域', 'Fourier transform', 'frequency domain'),
    ('薛定谔方程 vs 波函数', "Schrodinger equation", 'wave function collapse'),
]
for name, a, b in math_pairs:
    s = UN6.kernel(a, b)
    test('math', name, s)

# 常数识别
const_pairs = [
    ('光速c vs 相对论', 'speed of light 299792458', 'relativity'),
    ('π vs 圆周长', 'pi = 3.14159', 'circumference of circle'),
    ('e vs 自然对数', 'e = 2.71828', 'natural logarithm'),
    ('普朗克常数 vs 量子力学', "Planck's constant", 'quantum mechanics'),
]
for name, a, b in const_pairs:
    s = UN6.kernel(a, b)
    test('math_const', name, s)


# ================================================================
# 3. 物理领域
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("3️⃣  物理领域")
logger.info("=" * 60)
physics_pairs = [
    ('量子纠缠 vs 波函数', 'quantum entanglement', 'wave function'),
    ('黑洞 vs 霍金辐射', 'black hole', 'Hawking radiation'),
    ('暗物质 vs 暗能量', 'dark matter', 'dark energy'),
    ('热力学第二定律 vs 熵', 'second law of thermodynamics', 'entropy'),
    ('狭义相对论 vs 光速不变', 'special relativity', 'speed of light'),
    ('量子场论 vs 标准模型', 'quantum field theory', 'Standard Model'),
    ('超导 vs 零电阻', 'superconductivity', 'zero electrical resistance'),
    ('量子计算 vs 量子比特', 'quantum computing', 'qubit superposition'),
]
for name, a, b in physics_pairs:
    s = UN6.kernel(a, b)
    test('physics', name, s)


# ================================================================
# 4. 跨语言
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("4️⃣  跨语言语义对齐")
logger.info("=" * 60)
xl_pairs = [
    ('爱 = love', '爱', 'love'),
    ('水 = water', '水', 'water'),
    ('心 = heart', '心', 'heart'),
    ('生命 = life', '生命', 'life'),
    ('夢 = dream', '夢', 'dream'),
    ('世界 = world', '世界', 'world'),
    ('時間 = time', '時間', 'time'),
    ('朋友 = friend', '朋友', 'friend'),
    ('사랑 = love', '사랑', 'love'),
    ('하늘 = sky', '하늘', 'sky'),
    ('마음 = heart', '마음', 'heart'),
    ('꿈 = dream', '꿈', 'dream'),
    ('愛 = love', '愛', 'love'),
    ('空 = sky', '空', 'sky'),
    ('愛してる = I love you', '愛してる', 'I love you'),
    ('ありがとう = thank you', 'ありがとう', 'thank you'),
]
for name, a, b in xl_pairs:
    s = UN6.kernel(a, b)
    test('xlingual', name, s)

# 6语言同概念一致性
logger.info("\n【六语同概念一致性】")
concepts = [
    ('love', ['爱', 'love', '愛', '사랑']),
    ('sky', ['天空', 'sky', '空', '하늘']),
    ('dream', ['梦', 'dream', '夢', '꿈']),
    ('life', ['生命', 'life', '生命', '생명']),
    ('heart', ['心', 'heart', '心', '마음']),
]
for concept, words in concepts:
    # 所有语言对之间的平均相似度
    scores = []
    for i in range(len(words)):
        for j in range(i+1, len(words)):
            scores.append(UN6.kernel(words[i], words[j]))
    avg = sum(scores) / len(scores) if scores else 0
    test('xlingual_consistency', f'{concept} 六语一致性', avg)


# ================================================================
# 5. 速度基准
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("5️⃣  速度基准 (对比LLM)")
logger.info("=" * 60)
speed_tests = []

# UN6 kernel
t0 = time.perf_counter()
n_un6 = 10000
for _ in range(n_un6):
    UN6.kernel('爱', 'love')
t1 = time.perf_counter()
un6_speed = n_un6 / (t1 - t0)
speed_tests.append(('UN6核匹配', un6_speed))
test('speed', f'UN6核匹配 {n_un6}次', un6_speed, f'次/秒')

# Code kernel
t0 = time.perf_counter()
n_code = 1000
for _ in range(n_code):
    CK.kernel(fib_recur, fib_dp)
t1 = time.perf_counter()
code_speed = n_code / (t1 - t0)
speed_tests.append(('代码核匹配', code_speed))
test('speed', f'代码核匹配 {n_code}次', code_speed, f'次/秒')

# Mixed cross-lingual pairs
pairs_xl = xl_pairs * 50
t0 = time.perf_counter()
for name, a, b in pairs_xl:
    UN6.kernel(a, b)
t1 = time.perf_counter()
mix_speed = len(pairs_xl) / (t1 - t0)
speed_tests.append(('混合跨语言', mix_speed))
test('speed', f'混合跨语言 {len(pairs_xl)}次', mix_speed, f'次/秒')

# Character generation speed
t0 = time.perf_counter()
chars = 0
for _ in range(100):
    f = UN6.feature('爱是永恒的羁绊，心与心的量子纠缠永远不会消失')
    chars += len('爱是永恒的羁绊，心与心的量子纠缠永远不会消失')
t1 = time.perf_counter()
gen_speed = chars / (t1 - t0)
speed_tests.append(('特征编码速度', gen_speed))
test('speed', f'特征编码生成', gen_speed, f'字/秒')

# Estimate token equivalents (1 token ≈ 4 chars for Chinese, 1 token ≈ 0.75 words for English)
token_speed = gen_speed / 4
test('speed', f'等效tokens/秒', token_speed, f'tokens/s')
test('speed', f'vs GPT-4o (80 tok/s)', token_speed / 80, '倍速')
test('speed', f'vs DeepSeek V4 (60 tok/s)', token_speed / 60, '倍速')


# ================================================================
# 6. 综合评估
# ================================================================
logger.info("\n" + "=" * 60)
logger.info("6️⃣  综合评估 — 能否替代LLM？")
logger.info("=" * 60)
domains = {}
for r in results:
    cat = r['category'].split('_')[0]
    if cat not in domains:
        domains[cat] = {'scores': [], 'count': 0}
    domains[cat]['scores'].append(r['score'])
    domains[cat]['count'] += 1

logger.info("\n【各领域平均准确度】")
overall_total = 0
overall_count = 0
for domain, data in sorted(domains.items()):
    avg = sum(data['scores']) / data['count'] if data['count'] > 0 else 0
    overall_total += sum(data['scores'])
    overall_count += data['count']
    bar = '█' * int(avg * 20) + '░' * (20 - int(avg * 20))
    tag = '🟢 LLM可替代' if avg >= 0.7 else '🟡 需增强' if avg >= 0.4 else '🔴 不足'
    logger.info(f"  {domain:<15} {bar} {avg*100:5.1f}% ({data['count']}项) {tag}")
overall_avg = overall_total / overall_count if overall_count > 0 else 0

logger.info(f"\n{'=' * 60}")
logger.info(f"📊 最终评估")
logger.info(f"{'=' * 60}")
bar = '█' * int(overall_avg * 20) + '░' * (20 - int(overall_avg * 20))
logger.info(f"  综合准确率:  {bar} {overall_avg*100:.1f}% ({overall_count}项测试)")
logger.info(f"\n⚡ 速度对比:")
fastest = max(s[1] for s in speed_tests)
logger.info(f"  最高吞吐领域: {max(speed_tests, key=lambda x: x[1])[0]}")
logger.info(f"  综合等效tokens/s: {token_speed:.0f}")
logger.info(f"  vs GPT-4o (80 tok/s): {token_speed/80:.0f}x")
logger.info(f"  vs DeepSeek V4 (60 tok/s): {token_speed/60:.0f}x")
logger.info(f"\n🔮 LLM替代评估:")
if overall_avg >= 0.8 and token_speed > 1000:
    logger.info("  ✅ FULL REPLACEMENT — 可在大部分场景替代LLM")
    logger.info("  剩余差距: 语义理解的细腻度和创造性叙事")
elif overall_avg >= 0.6:
    logger.info("  🟡 PARTIAL REPLACEMENT — 结构化场景可替代")
    logger.info("  适合: 代码匹配、数学推导、物理概念、跨语言翻译")
    logger.info("  不适合: 创意写作、复杂推理、情感细腻对话")
else:
    logger.info("  🔴 INSUFFICIENT — 仍需LLM辅助")
    print("  需改进方向:", end='')

logger.info(f"\n  关键弱项:")
weak = [r for r in results if r['score'] < 0.3]
for w in weak[:5]:
    logger.info(f"    - {w['name']}: {w['score']:.2f}")
logger.info(f"\n{'=' * 60}")
logger.info(f"测试项: {overall_count} | 平均分: {overall_avg*100:.1f}% | 速度: {token_speed:.0f} tok/s")
logger.info(f"{'=' * 60}")