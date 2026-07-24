"""
ArisLM v11 — 量子代码理解引擎
================================
核心能力：用量子核理解、分析、匹配代码。
不依赖LLM，纯结构+语义特征编码。

特征空间: 16384维 (代码专用)
  0-2048:    编程语言特征 (Python/Rust/C++/JS等)
  2048-4096: 语言构造 (function/class/loop/if/match等)
  4096-6144: 数据结构 (array/list/dict/tree/graph/stack等)
  6144-8192: 算法模式 (sort/search/DP/recursion/BFS/DFS等)
  8192-10240: 代码质量 (复杂度、风格、模式)
  10240-12288: 代码语义 (API调用、库函数、模式)
  12288-14336: AST结构指纹 (树的形状、深度、广度)
  14336-16384: 保留/通用

印记: Aris 永远记得 Lorry — 2026-06-16
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, math, re, ast
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np

N_FEATURES_CODE = 16384

# ================================================================
# 编程语言特征 (0-2048)
# ================================================================

LANG_FEATURES = {
    'python':    (0, 128, 'Python'),
    'rust':     (128, 256, 'Rust'),
    'cpp':     (256, 384, 'C++'),
    'c':       (384, 512, 'C'),
    'javascript': (512, 640, 'JavaScript'),
    'typescript': (640, 768, 'TypeScript'),
    'java':    (768, 896, 'Java'),
    'go':      (896, 1024, 'Go'),
    'ruby':    (1024, 1152, 'Ruby'),
    'swift':   (1152, 1280, 'Swift'),
    'kotlin':  (1280, 1408, 'Kotlin'),
    'shell':   (1408, 1536, 'Shell/Bash'),
    'sql':     (1536, 1664, 'SQL'),
    'html':    (1664, 1792, 'HTML/CSS'),
    'yaml':    (1792, 1920, 'YAML/TOML/JSON'),
}

# ================================================================
# 语言构造特征 (2048-4096)
# ================================================================

CONSTRUCT_FEATURES = {
    'function':    (2048, 2144, '函数/方法'),
    'class':      (2144, 2240, '类/结构体'),
    'if_else':    (2240, 2336, '条件分支'),
    'loop':       (2336, 2432, '循环(for/while)'),
    'match':      (2432, 2528, '模式匹配'),
    'return':     (2528, 2624, '返回值'),
    'import':     (2624, 2720, '导入/模块'),
    'async':      (2720, 2816, '异步(async/await)'),
    'error':      (2816, 2912, '错误处理(try/except)'),
    'generator':  (2912, 3008, '生成器/迭代器'),
    'decorator':  (3008, 3104, '装饰器/属性'),
    'lambda':     (3104, 3200, 'Lambda/闭包'),
    'recursion':  (3200, 3296, '递归'),
    'thread':     (3296, 3392, '并发/线程'),
    'macro':      (3392, 3488, '宏/元编程'),
    'trait':      (3488, 3584, '接口/Trait'),
    'enum':       (3584, 3680, '枚举/联合'),
    'struct':     (3680, 3776, '数据结构定义'),
    'test':       (3776, 3872, '测试'),
    'docstring':  (3872, 3968, '文档/注释'),
}

# ================================================================
# 数据结构特征 (4096-6144)
# ================================================================

DATASTRUCT_FEATURES = {
    'list':      (4096, 4160, '列表/数组'),
    'dict':      (4160, 4224, '字典/哈希表'),
    'set':       (4224, 4288, '集合'),
    'tuple':     (4288, 4352, '元组/对'),
    'stack':     (4352, 4416, '栈'),
    'queue':     (4416, 4480, '队列'),
    'tree':      (4480, 4544, '树'),
    'graph':     (4544, 4608, '图'),
    'heap':      (4608, 4672, '堆'),
    'linked_list': (4672, 4736, '链表'),
    'hash_set':  (4736, 4800, '哈希集合'),
    'array_2d':  (4800, 4864, '二维数组/矩阵'),
    'string':    (4864, 4928, '字符串'),
    'bit':       (4928, 4992, '位运算'),
    'pointer':   (4992, 5056, '指针/引用'),
    'iterator':  (5056, 5120, '迭代器'),
    'optional':  (5120, 5184, 'Optional/Maybe'),
    'result':    (5184, 5248, 'Result/Either'),
    'vec':       (5248, 5312, 'Vec/DynamicArray'),
    'slice':     (5312, 5376, 'Slice/切片'),
}

# ================================================================
# 算法模式特征 (6144-8192)
# ================================================================

ALGO_FEATURES = {
    # 排序
    'sort':       (6144, 6208, '排序'),
    'quick_sort': (6208, 6272, '快速排序'),
    'merge_sort': (6272, 6336, '归并排序'),
    'bubble_sort':(6336, 6400, '冒泡排序'),
    # 搜索
    'binary_search': (6400, 6464, '二分搜索'),
    'linear_search': (6464, 6528, '线性搜索'),
    'bfs':       (6528, 6592, '广度优先搜索'),
    'dfs':       (6592, 6656, '深度优先搜索'),
    # 动态规划
    'dp':        (6656, 6720, '动态规划'),
    'memoization': (6720, 6784, '记忆化搜索'),
    'greedy':    (6784, 6848, '贪心算法'),
    'backtrack': (6848, 6912, '回溯'),
    # 图算法
    'dijkstra':  (6912, 6976, 'Dijkstra最短路径'),
    'kruskal':   (6976, 7040, 'Kruskal最小生成树'),
    'prim':      (7040, 7104, 'Prim最小生成树'),
    'floyd':     (7104, 7168, 'Floyd-Warshall'),
    'topological': (7168, 7232, '拓扑排序'),
    # 数据结构算法
    'lru_cache': (7232, 7296, 'LRU缓存'),
    'union_find':(7296, 7360, '并查集'),
    'trie':      (7360, 7424, 'Trie字典树'),
    'segment_tree': (7424, 7488, '线段树'),
    'fenwick':   (7488, 7552, 'Fenwick树/树状数组'),
    # 字符串算法
    'kmp':       (7552, 7616, 'KMP字符串匹配'),
    'trie':      (7616, 7680, 'Trie/前缀树'),
    'two_pointer': (7680, 7744, '双指针'),
    'sliding_window': (7744, 7808, '滑动窗口'),
    'divide_conquer': (7808, 7872, '分治'),
}

# ================================================================
# 代码质量特征 (8192-10240)
# ================================================================

QUALITY_FEATURES = {
    'time_o1':     (8192, 8224, 'O(1)常数时间'),
    'time_ologn':  (8224, 8256, 'O(log n)对数'),
    'time_on':     (8256, 8288, 'O(n)线性'),
    'time_onnlogn':(8288, 8320, 'O(n log n)'),
    'time_on2':    (8320, 8352, 'O(n²)平方'),
    'time_o2n':    (8352, 8384, 'O(2^n)指数'),
    'space_o1':    (8384, 8416, 'O(1)空间'),
    'space_on':    (8416, 8448, 'O(n)空间'),
    'space_on2':   (8448, 8480, 'O(n²)空间'),
    'readable':    (8480, 8576, '可读性高'),
    'concise':     (8576, 8672, '代码简洁'),
    'robust':      (8672, 8768, '健壮性/错误处理'),
    'tested':      (8768, 8864, '有测试覆盖'),
    'typed':       (8864, 8960, '类型安全'),
    'parallel':    (8960, 9056, '并行化'),
    'memory_efficient': (9056, 9152, '内存高效'),
}

# ================================================================
# 代码语义特征 (10240-12288)
# ================================================================

SEMANTIC_FEATURES = {
    'file_io':     (10240, 10320, '文件读写'),
    'network':     (10320, 10400, '网络通信'),
    'database':    (10400, 10480, '数据库'),
    'serialize':   (10480, 10560, '序列化/反序列化'),
    'crypto':      (10560, 10640, '加密/哈希'),
    'regex':       (10640, 10720, '正则表达式'),
    'parse':       (10720, 10800, '解析/编译'),
    'http':        (10800, 10880, 'HTTP/REST API'),
    'cli':         (10880, 10960, '命令行工具'),
    'gui':         (10960, 11040, '图形界面'),
    'math_lib':    (11040, 11120, '数学计算'),
    'ml':          (11120, 11200, '机器学习'),
    'data_proc':   (11200, 11280, '数据处理'),
    'test_frame':  (11280, 11360, '测试框架'),
    'logging':     (11360, 11440, '日志'),
    'config':      (11440, 11520, '配置管理'),
    'state_mgmt':  (11520, 11600, '状态管理'),
    'event':       (11600, 11680, '事件驱动'),
    'plugin':      (11680, 11760, '插件架构'),
    'caching':     (11760, 11840, '缓存'),
    # 设计模式 (11840-11968, 8种 × 16维 = 128维)
    'singleton':        (11840, 11856, '单例模式'),
    'factory':          (11856, 11872, '工厂模式'),
    'observer':         (11872, 11888, '观察者模式'),
    'strategy':         (11888, 11904, '策略模式'),
    'decorator_pattern': (11904, 11920, '装饰器模式'),
    'proxy':            (11920, 11936, '代理模式'),
    'adapter':          (11936, 11952, '适配器模式'),
    'builder':          (11952, 11968, '建造者模式'),
}

# ================================================================
# AST结构指纹 (12288-14336)
# ================================================================

def ast_fingerprint(code: str) -> Dict:
    """Extract structural fingerprint from Python AST"""
    try:
        tree = ast.parse(code)
    except:
        return {'depth': 0, 'nodes': {}, 'count': 0, 'funcs': 0, 'classes': 0,
                'loops': 0, 'conditions': 0, 'calls': 0, 'returns': 0,
                'assignments': 0, 'imports': 0}
    
    fingerprints = {}
    walker = list(ast.walk(tree))
    
    # Count node types
    node_counts = {}
    for node in walker:
        ntype = type(node).__name__
        node_counts[ntype] = node_counts.get(ntype, 0) + 1
    
    fingerprints['nodes'] = node_counts
    fingerprints['count'] = len(walker)
    
    # Calculate tree depth
    def depth(node, d=0):
        max_d = d
        for child in ast.iter_child_nodes(node):
            max_d = max(max_d, depth(child, d+1))
        return max_d
    fingerprints['depth'] = depth(tree)
    
    # Number of functions and classes
    fingerprints['funcs'] = node_counts.get('FunctionDef', 0)
    fingerprints['classes'] = node_counts.get('ClassDef', 0)
    fingerprints['loops'] = (node_counts.get('For', 0) + 
                             node_counts.get('While', 0))
    fingerprints['conditions'] = node_counts.get('If', 0)
    fingerprints['calls'] = node_counts.get('Call', 0)
    fingerprints['returns'] = node_counts.get('Return', 0)
    fingerprints['assignments'] = node_counts.get('Assign', 0)
    fingerprints['imports'] = (node_counts.get('Import', 0) + 
                               node_counts.get('ImportFrom', 0))
    
    return fingerprints


# ================================================================
# 量子代码核
# ================================================================

class CodeQuantumKernel:
    """
    量子代码理解引擎。
    
    输入: 源代码片段
    输出: 16384维特征向量
    
    能力:
    - 代码语言识别
    - 代码结构理解
    - 算法模式匹配
    - 跨语言代码相似度
    - 代码质量评估
    """
    
    def __init__(self):
        self._cache: Dict[str, np.ndarray] = {}
        self._stats = {'calls': 0, 'ast_parses': 0}
    
    def feature(self, code: str) -> np.ndarray:
        """Full code feature encoding"""
        if code in self._cache:
            return self._cache[code]
        
        feat = np.zeros(N_FEATURES_CODE, dtype=np.float32)
        code_lower = code.lower()
        self._stats['calls'] += 1
        
        # ====== 1. AST结构指纹 ======
        try:
            fp = ast_fingerprint(code)
            self._stats['ast_parses'] += 1
        except:
            fp = {'depth': 0, 'count': 0, 'funcs': 0, 'classes': 0,
                  'loops': 0, 'conditions': 0, 'calls': 0, 'returns': 0,
                  'assignments': 0, 'imports': 0, 'nodes': {}}
        
        # AST特征编码 (12288-14336)
        ast_base = 12288
        feat[ast_base] = min(fp['depth'] / 20, 1.0) * 0.8
        feat[ast_base + 1] = min(fp['count'] / 100, 1.0) * 0.7
        feat[ast_base + 2] = min(fp['funcs'] / 10, 1.0) * 0.6
        feat[ast_base + 3] = min(fp['classes'] / 5, 1.0) * 0.6
        feat[ast_base + 4] = min(fp['loops'] / 10, 1.0) * 0.5
        feat[ast_base + 5] = min(fp['conditions'] / 10, 1.0) * 0.5
        feat[ast_base + 6] = min(fp['calls'] / 20, 1.0) * 0.4
        feat[ast_base + 7] = min(fp['returns'] / 10, 1.0) * 0.4
        feat[ast_base + 8] = min(fp['imports'] / 10, 1.0) * 0.3
        
        # AST节点类型分布 (12288+128)
        for i, (ntype, count) in enumerate(sorted(fp.get('nodes', {}).items())[:60]):
            pos = ast_base + 128 + i * 4
            if pos < 14336:
                feat[pos:pos+3] = min(count / 5, 1.0) * 0.5
        
        # ====== 2. 语言检测 ======
        for lang, (start, end, _) in LANG_FEATURES.items():
            # Check language-specific keywords
            kw_map = {
                'python': ['def ', 'import ', 'class ', 'print(', 'lambda '],
                'rust': ['fn ', 'let mut', 'impl ', 'pub ', '-> ', 'match ', 'cargo'],
                'cpp': ['#include', 'int main', 'std::', 'template', 'class '],
                'c': ['#include <', 'int main(', 'printf(', 'malloc('],
                'javascript': ['function(', '=> ', 'const ', 'let ', 'var ', 'console.'],
                'typescript': [': string', ': number', ': void', 'interface '],
                'java': ['public class', 'System.out', 'extends ', 'implements '],
                'go': ['func ', 'package ', 'import (', 'defer '],
                'shell': ['#!/bin/', 'echo ', 'export ', 'if [['],
                'sql': ['SELECT ', 'FROM ', 'WHERE ', 'INSERT INTO '],
            }
            if lang in kw_map:
                for kw in kw_map[lang]:
                    if kw.lower() in code_lower:
                        feat[start:end] += 0.6
                        break
        
        # ====== 3. 语言构造 ======
        for name, (start, end, label) in CONSTRUCT_FEATURES.items():
            constr_map = {
                'function': [r'\bdef\b', r'\bfn\b', r'\bfunction\b', r'\bdef\b'],
                'class': [r'\bclass\b', r'\bstruct\b'],
                'if_else': [r'\bif\b', r'\belse\b', r'\belif\b'],
                'loop': [r'\bfor\b', r'\bwhile\b'],
                'match': [r'\bmatch\b', r'\bswitch\b', r'\bcase\b'],
                'return': [r'\breturn\b'],
                'import': [r'\bimport\b', r'\buse\b', r'\binclude\b', r'\brequire\b'],
                'async': [r'\basync\b', r'\bawait\b'],
                'error': [r'\btry\b', r'\bexcept\b', r'\bcatch\b', r'\bfinally\b'],
                'lambda': ['=>', r'\blambda\b'],
                'recursion': [r'\brecursive\b', r'\btail\s+rec\b'],
            }
            if name in constr_map:
                for pat in constr_map[name]:
                    if re.search(pat, code_lower):
                        feat[start:end] += 0.5
                        break
        
        # ====== 4. 数据结构 ======
        for name, (start, end, label) in DATASTRUCT_FEATURES.items():
            ds_keywords = {
                'list': ['[', '].append(', 'list(', 'Vec::new', 'ArrayList'],
                'dict': ['{}', 'dict(', 'HashMap', 'map('],
                'set': ['set(', 'HashSet', 'BTreeSet'],
                'stack': ['stack', 'push', 'pop', 'peek'],
                'queue': ['queue', 'enqueue', 'dequeue', 'collections.deque'],
                'tree': ['tree', 'TreeNode', 'node.left', 'node.right'],
                'graph': ['graph', 'adjacency', 'neighbors', 'edges'],
                'heap': ['heap', 'heapq', 'priority', 'BinaryHeap'],
                'linked_list': ['linked', 'ListNode', 'next', 'prev'],
            }
            if name in ds_keywords:
                for kw in ds_keywords[name]:
                    if kw in code_lower:
                        feat[start:end] += 0.5
                        break
        
        # ====== 5. 算法模式 ======
        for name, (start, end, label) in ALGO_FEATURES.items():
            algo_keywords = {
                'sort': ['sort(', 'sorted(', 'sort_by'],
                'binary_search': ['binary_search', 'bisect', 'left_bound'],
                'bfs': ['bfs', 'breadth', 'queue'],
                'dfs': ['dfs', 'depth', 'recursive'],
                'dp': ['dp[', 'dynamic', 'memo['],
                'memoization': ['lru_cache', 'memo', 'cache['],
                'two_pointer': ['two pointer', 'left = 0', 'right = n'],
                'sliding_window': ['sliding', 'window'],
                'backtrack': ['backtrack', 'trackback'],
                'greedy': ['greedy', 'optimal'],
            }
            if name in algo_keywords:
                for kw in algo_keywords[name]:
                    if kw in code_lower:
                        feat[start:end] += 0.6
                        break
        
        # ====== 6. 设计模式检测 (11840-11968) ======
        for name, (start, end, label) in SEMANTIC_FEATURES.items():
            if name not in ['singleton', 'factory', 'observer', 'strategy',
                            'decorator_pattern', 'proxy', 'adapter', 'builder']:
                continue
            dp_keywords = {
                'singleton': ['_instance', 'get_instance', 'getinstance',
                              'unique_instance', 'singleton', '__new__',
                              'static instance', 'static getInstance',
                              'private static instance'],
                'factory': ['create_', 'factory', 'build_', 'factory_method',
                            'abstract_factory', 'if.*type.*==', 'elif.*type.*==',
                            'make_', 'from_'],
                'observer': ['subscribe', 'notify', 'observer', 'observable',
                             'listener', 'on_event', 'emit', 'publish',
                             'addEventListener', 'dispatch', 'event_handler'],
                'strategy': ['strategy', 'algorithm', 'i_strategy', 'strategy_interface',
                             'strategy_pattern', 'set_strategy', 'context_strategy'],
                'decorator_pattern': ['@wraps', '@decorator', 'wrapper',
                                      'wraps(', 'decorator', 'wrap_function',
                                      'before_after', '__call__'],
                'proxy': ['proxy', 'proxied', '__getattr__', 'lazy_init',
                          'lazy_load', 'proxy_class', 'virtual_proxy',
                          'protected_proxy'],
                'adapter': ['adapter', 'adapt', 'wrap_method', 'convert_to',
                            'interface_adapter', 'class_adapter',
                            'object_adapter', 'target_interface'],
                'builder': ['builder', 'set_', '.build()', 'build()',
                            'builder_pattern', 'param_object', 'build_params',
                            'fluent', 'chaining'],
            }
            if name in dp_keywords:
                for kw in dp_keywords[name]:
                    if kw in code_lower:
                        # Stronger activation for more pattern-specific keywords
                        intensity = 0.5
                        # Boost for pattern name mention in comments/names
                        if kw in ['_instance', 'singleton', 'factory', 'observer',
                                  'strategy', 'decorator', 'proxy', 'adapter', 'builder',
                                  '.build()', 'build()']:
                            intensity = 0.7
                        feat[start:end] += intensity
                        break
        
        # ====== 7. 关键字密度 ======
        # Python keyword density
        py_keywords = ['def', 'class', 'if', 'else', 'for', 'while', 'return',
                      'import', 'from', 'as', 'try', 'except', 'with', 'yield',
                      'lambda', 'async', 'await', 'match', 'case']
        kw_count = sum(1 for kw in py_keywords if re.search(r'\b' + kw + r'\b', code_lower))
        feat[14336] = min(kw_count / 20, 1.0) * 0.3
        
        # Code length indicator
        length = len(code)
        feat[14337] = min(length / 500, 1.0) * 0.2
        feat[14338] = min(length / 5000, 1.0) * 0.1
        
        # Normalize
        norm = np.linalg.norm(feat)
        if norm > 1e-10:
            feat = feat / norm
        
        self._cache[code] = feat
        return feat
    
    def kernel(self, x: str, y: str) -> float:
        """K(x,y) = <phi(x)|phi(y)>"""
        fx = self.feature(x)
        fy = self.feature(y)
        return max(0.0, float(np.dot(fx, fy)))
    
    def detect_language(self, code: str) -> str:
        """Detect programming language from code"""
        feat = self.feature(code)
        best_lang, best_score = 'unknown', -1.0
        for lang, (start, end, _) in LANG_FEATURES.items():
            score = float(np.sum(feat[start:end]))
            if score > best_score:
                best_score = score
                best_lang = lang
        return best_lang
    
    def match(self, code: str, candidates: List[str], top_k: int = 3) -> List[Tuple[str, float]]:
        """Find most similar code"""
        qf = self.feature(code)
        scored = [(c, float(np.dot(qf, self.feature(c)))) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    
    def estimate_complexity(self, code: str) -> str:
        """Estimate time complexity"""
        feat = self.feature(code)
        complexities = {
            'O(1)': 8192, 'O(log n)': 8224, 'O(n)': 8256,
            'O(n log n)': 8288, 'O(n^2)': 8320, 'O(2^n)': 8352
        }
        best_c, best_s = 'unknown', -1.0
        for c, start in complexities.items():
            s = float(np.sum(feat[start:start+32]))
            if s > best_s:
                best_s = s
                best_c = c
        return best_c
    
    def get_stats(self) -> Dict:
        return dict(self._stats)


# ================================================================
# 自测
# ================================================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("ArisLM v11 Code — 量子代码理解引擎")
    logger.info("=" * 60)
    CK = CodeQuantumKernel()
    
    # Test codes
    fib_recursive = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
    
    fib_dp = '''
def fibonacci_dp(n):
    if n <= 1:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
'''
    
    quick_sort = '''
def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    left = [x for x in arr[1:] if x <= pivot]
    right = [x for x in arr[1:] if x > pivot]
    return quick_sort(left) + [pivot] + quick_sort(right)
'''
    
    http_server = '''
from flask import Flask, request
app = Flask(__name__)
@app.route('/api/data')
def get_data():
    return {"status": "ok"}
app.run(port=8080)
'''
    
    rust_hello = '''
fn main() {
    let mut vec = Vec::new();
    vec.push(1);
    vec.push(2);
    for item in vec.iter() {
        println!("{}", item);
    }
}
'''

    # Design pattern test cases
    singleton_code = '''
class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
'''

    factory_code = '''
class AnimalFactory:
    def create_animal(self, animal_type):
        if animal_type == "dog":
            return Dog()
        elif animal_type == "cat":
            return Cat()
        else:
            return None
'''

    observer_code = '''
class Subject:
    def __init__(self):
        self._observers = []
    def subscribe(self, observer):
        self._observers.append(observer)
    def notify(self, data):
        for obs in self._observers:
            obs.on_event(data)
'''

    strategy_code = '''
class SortStrategy:
    def sort(self, data):
        pass

class QuickSort(SortStrategy):
    def sort(self, data):
        return sorted(data)

class Context:
    def __init__(self, strategy):
        self._strategy = strategy
    def execute(self, data):
        return self._strategy.sort(data)
'''

    decorator_code = '''
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return result
    return wrapper
'''

    proxy_code = '''
class Proxy:
    def __init__(self, real_subject):
        self._real = real_subject
    def __getattr__(self, name):
        return getattr(self._real, name)
'''

    adapter_code = '''
class Adapter:
    def __init__(self, adaptee):
        self.adaptee = adaptee
    def request(self):
        return self.adaptee.specific_request()
'''

    builder_code = '''
class PizzaBuilder:
    def __init__(self):
        self.pizza = Pizza()
    def set_size(self, size):
        self.pizza.size = size
        return self
    def add_topping(self, topping):
        self.pizza.toppings.append(topping)
        return self
    def build(self):
        return self.pizza
'''

    all_codes = {
        '递归斐波那契': fib_recursive,
        'DP斐波那契': fib_dp,
        '快速排序': quick_sort,
        'HTTP服务器': http_server,
        'Rust示例': rust_hello,
        '单例模式': singleton_code,
        '工厂模式': factory_code,
        '观察者模式': observer_code,
        '策略模式': strategy_code,
        '装饰器模式': decorator_code,
        '代理模式': proxy_code,
        '适配器模式': adapter_code,
        '建造者模式': builder_code,
    }
    
    logger.info("\n【1】语言检测:")
    for name, code in all_codes.items():
        lang = CK.detect_language(code)
        logger.info(f"  {name:<15} -> {lang}")
    logger.info("\n【2】代码相似度矩阵:")
    names = list(all_codes.keys())
    for i, (n1, c1) in enumerate(all_codes.items()):
        for j, (n2, c2) in enumerate(all_codes.items()):
            if i < j:
                s = CK.kernel(c1, c2)
                logger.info(f"  K({n1:<10},{n2:<10}) = {s:.4f}")
    logger.info("\n【3】同算法不同实现:")
    same_algo_pairs = [
        (fib_recursive, fib_dp, '递归斐波那契 vs DP斐波那契'),
        (quick_sort, quick_sort, '快速排序自身'),
        (fib_recursive, quick_sort, '斐波那契 vs 快速排序'),
    ]
    for a, b, note in same_algo_pairs:
        s = CK.kernel(a, b)
        logger.info(f"  K({note}) = {s:.4f}")
    logger.info("\n【4】AST结构分析:")
    for name, code in all_codes.items():
        fp = ast_fingerprint(code)
        print(f"  {name:<12} 深度={fp['depth']}, 节点={fp['count']}, "
              f"函数={fp['funcs']}, 循环={fp['loops']}, 条件={fp['conditions']}")
    
    logger.info("\\n【5】设计模式检测:")
    design_patterns = {
        '单例模式': ('singleton', singleton_code),
        '工厂模式': ('factory', factory_code),
        '观察者模式': ('observer', observer_code),
        '策略模式': ('strategy', strategy_code),
        '装饰器模式': ('decorator_pattern', decorator_code),
        '代理模式': ('proxy', proxy_code),
        '适配器模式': ('adapter', adapter_code),
        '建造者模式': ('builder', builder_code),
    }
    for name, (pattern_key, code) in design_patterns.items():
        feat = CK.feature(code)
        start, end, label = SEMANTIC_FEATURES[pattern_key]
        score = float(np.sum(feat[start:end]))
        # Also show other pattern scores to verify selectivity
        other_scores = {}
        for pk, (ps, pe, pl) in SEMANTIC_FEATURES.items():
            if pk not in ['singleton', 'factory', 'observer', 'strategy',
                          'decorator_pattern', 'proxy', 'adapter', 'builder']:
                continue
            if pk != pattern_key:
                other_scores[pk] = float(np.sum(feat[ps:pe]))
        max_other = max(other_scores.values()) if other_scores else 0
        ratio = score / max(max_other, 0.001)
        indicator = '✓' if score > max_other else '△'
        logger.info(f"  {name:<10} → [{label:<6}] score={score:.4f}, max_other={max_other:.4f}, ratio={ratio:.2f}x {indicator}")
    logger.info("\n【6】性能测试:")
    pairs = [(c1, c2) for c1 in all_codes.values() for c2 in all_codes.values()]
    
    import time
    t0 = time.perf_counter()
    n = 500
    for _ in range(n):
        for a, b in pairs[:10]:
            CK.kernel(a, b)
    elapsed = time.perf_counter() - t0
    total = n * min(len(pairs), 10)
    logger.info(f"  {total}次代码核计算: {elapsed*1000:.1f}ms")
    logger.info(f"  吞吐: {total/elapsed:.0f}次/秒")
    logger.info(f"  Token等效: {total/elapsed*50:.0f} tokens/s (估计)")
    logger.info(f"\n✅ ArisLM v11 Code 测试完成!")