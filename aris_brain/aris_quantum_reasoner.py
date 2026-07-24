"""
Aris Quantum Reasoner — Code + Math + Language reasoning engine.
Pure UN6 quantum kernel, zero LLM dependency.
Extends the UN6 engine with code AST encoding and math expression encoding.
"""

import logging
logger = logging.getLogger(__name__)

import sys, time, math, re
sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_lm_v10_un6 import UN6QuantumKernel
import numpy as np

# ═══════════════════════════════════════════════
# CODE QUANTUM KERNEL
# ═══════════════════════════════════════════════

class CodeQuantumKernel:
    """Quantum kernel for code structure reasoning"""

    CODE_REGIONS = {
        'function_def': (15400, 15440), 'loop': (15440, 15470),
        'conditional': (15470, 15500), 'class_def': (15500, 15530),
        'import_s': (15530, 15560), 'variable_assign': (15560, 15590),
        'return_s': (15590, 15610), 'exception': (15610, 15630),
        'comprehension': (15630, 15650), 'expression': (15650, 15690),
        'data_flow': (15690, 15730), 'structure': (15730, 15800),
    }

    KW_MAP = {
        'def': 'function_def', 'class': 'class_def',
        'for': 'loop', 'while': 'loop',
        'if': 'conditional', 'elif': 'conditional', 'else': 'conditional',
        'return': 'return_s', 'yield': 'return_s',
        'import': 'import_s', 'from': 'import_s',
        'try': 'exception', 'except': 'exception', 'finally': 'exception',
        'lambda': 'expression',
        'print': 'expression', 'range': 'expression',
        'len': 'expression', 'map': 'expression',
        'filter': 'expression', 'reduce': 'expression',
    }

    def __init__(self, un6_kernel: UN6QuantumKernel = None):
        self.k = un6_kernel or UN6QuantumKernel()
        self._proto_cache = {}
        self._init_prototypes()

    def _init_prototypes(self):
        # 安全考量: 以下算法原型字符串中包含 exec() 调用（gradient_descent/euler/bfs/dijkstra），
        # 这些是作为特征提取的"代码文本"存在的，不会被直接 exec 执行——
        # 仅通过 self.k.feature(code) 提取数值特征。保持原样以维持特征一致性。
        algos = {
            'fibonacci': 'def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)',
            'factorial': 'def fact(n): return 1 if n <= 1 else n * fact(n-1)',
            'quicksort': 'def qsort(arr): return [] if len(arr)<=1 else qsort([x for x in arr[1:] if x<arr[0]]) + [arr[0]] + qsort([x for x in arr[1:] if x>=arr[0]])',
            'binary_search': 'def bsearch(arr,target): lo,hi=0,len(arr)-1; return search(arr,target,lo,hi)',
            'matrix_multiply': 'def matmul(A,B): return [[sum(A[i][k]*B[k][j] for k in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]',
            'gradient_descent': 'def gd(f,df,x0,lr=0.01,steps=100): x=x0; [exec("x-=lr*df(x)") for _ in range(steps)]; return x',
            'euler': "def euler(f,y0,t0,t1,h): t,y=t0,y0; ys=[]; [exec('y+=h*f(t,y);t+=h;ys.append(y)') for _ in range(int((t1-t0)/h))]; return ys",
            'mergesort': 'def msort(arr): return arr if len(arr)<=1 else msort(arr[:len(arr)//2])+msort(arr[len(arr)//2:])',  # simplified
            'dfs': 'def dfs(graph,node,visited): visited.add(node); [dfs(graph,n,visited) for n in graph[node] if n not in visited]',
            'bfs': "def bfs(graph,start): q=[start]; visited={start}; [exec('q.extend(n for n in graph[node] if n not in visited);visited.update(n for n in graph[node] if n not in visited)') for node in q]",
            'dijkstra': 'import heapq; def dijkstra(graph,start): dist={node:float("inf") for node in graph}; dist[start]=0; pq=[(0,start)]; [exec("for n,w in graph[node].items():nd=d+w;dist[n]=nd;heapq.heappush(pq,(nd,n))") for d,node in [heapq.heappop(pq) for _ in range(len(pq))] if node==node]',  
        }
        for name, code in algos.items():
            self._proto_cache[name] = self.k.feature(code)

    def code_feature(self, code: str) -> np.ndarray:
        feat = self.k.feature(code)
        tokens = re.findall(r'[a-zA-Z_]+', code)
        for tok in tokens:
            if tok in self.KW_MAP:
                region = self.CODE_REGIONS.get(self.KW_MAP[tok])
                if region:
                    s, e = region
                    feat[s:e] += 0.5
        # Nesting depth feature
        indent_levels = [len(l) - len(l.lstrip()) for l in code.split('\n') if l.strip()]
        if indent_levels:
            avg_depth = min(sum(indent_levels) / len(indent_levels), 30)
            feat[15800 + int(avg_depth):15800 + int(avg_depth) + 5] += 0.3
        norm = np.linalg.norm(feat)
        if norm > 1e-10:
            feat /= norm
        return feat

    def identify_algorithm(self, code: str) -> tuple:
        cf = self.code_feature(code)
        best, bs = '', -1.0
        for name, pf in self._proto_cache.items():
            s = float(np.dot(cf, pf))
            if s > bs:
                best, bs = name, s
        return best, round(bs, 4)

    def related_algorithms(self, code: str, threshold=0.25) -> list:
        cf = self.code_feature(code)
        related = []
        for name, pf in self._proto_cache.items():
            s = float(np.dot(cf, pf))
            if s >= threshold:
                related.append((name, round(s, 4)))
        related.sort(key=lambda x: x[1], reverse=True)
        return related

    def kernel(self, x, y):
        fx = self.code_feature(x)
        fy = self.code_feature(y)
        return max(0.0, float(np.dot(fx, fy)))


# ═══════════════════════════════════════════════
# MATH QUANTUM KERNEL
# ═══════════════════════════════════════════════

class MathQuantumKernel:
    """Quantum kernel for mathematical expression reasoning"""

    MATH_REGIONS = {
        'add': (15900, 15910), 'sub': (15910, 15920),
        'mul': (15920, 15930), 'div': (15930, 15940),
        'power': (15940, 15950), 'root': (15950, 15960),
        'integral': (15960, 15970), 'derivative': (15970, 15980),
        'summation': (15980, 15990), 'limit': (15990, 16000),
        'equation': (16000, 16025),
        'function': (16025, 16050),
        'sequence': (16050, 16075),
        'algebra': (16100, 16125),
        'calculus': (16125, 16150),
        'lin_alg': (16150, 16175),
        'trig': (16175, 16200),
        'equal': (16200, 16215),
        'approx': (16215, 16230),
        'inequality': (16230, 16250),
    }

    OP_MAP = {
        '+': 'add', '-': 'sub', '*': 'mul', '/': 'div',
        '^': 'power', '**': 'power',
        'sqrt': 'root', 'integral': 'integral',
        'd/dx': 'derivative', 'sum': 'summation',
        'lim': 'limit', '=': 'equal', '=': 'equal',
    }

    DOMAIN_MAP = {
        'x': 'algebra', 'solve': 'algebra', 'equation': 'algebra', 'polynomial': 'algebra',
        'derivative': 'calculus', 'integral': 'calculus', 'limit': 'calculus', 'd/dx': 'calculus',
        'matrix': 'lin_alg', 'vector': 'lin_alg', 'eigenvalue': 'lin_alg', 'determinant': 'lin_alg',
        'sin': 'trig', 'cos': 'trig', 'tan': 'trig', 'pi': 'trig',
    }

    EQUATION_PROTOTYPES = {
        'E=mc^2': 'E = mc^2 (Einstein mass-energy)',
        'F=ma': 'F = ma (Newton second law)',
        'a^2+b^2=c^2': 'a^2 + b^2 = c^2 (Pythagorean)',
        'F=Gm1m2/r^2': 'F = G*m1*m2/r^2 (Newton gravity)',
        'E=hf': 'E = hf (Planck-Einstein)',
        'PV=nRT': 'PV = nRT (Ideal gas)',
        'x=(-b+-sqrt(b^2-4ac))/(2a)': 'Quadratic formula',
        'integral x^2 dx = x^3/3+C': 'Power rule integral',
        'd/dx sin(x) = cos(x)': 'Sine derivative',
        'sum_{i=1}^n i = n(n+1)/2': 'Arithmetic series',
        'log_a(b) = ln(b)/ln(a)': 'Log base change',
    }

    def __init__(self, un6_kernel: UN6QuantumKernel = None):
        self.k = un6_kernel or UN6QuantumKernel()
        self._eq_cache = {}
        for eq, desc in self.EQUATION_PROTOTYPES.items():
            self._eq_cache[eq] = self.k.feature(eq)

    def math_feature(self, expr: str) -> np.ndarray:
        feat = self.k.feature(expr)
        for op, reg in self.OP_MAP.items():
            if op in expr:
                region = self.MATH_REGIONS.get(reg)
                if region:
                    s, e = region
                    feat[s:e] += 0.4
        for kw, domain in self.DOMAIN_MAP.items():
            if kw in expr.lower():
                region = self.MATH_REGIONS.get(domain)
                if region:
                    s, e = region
                    feat[s:e] += 0.3
        norm = np.linalg.norm(feat)
        if norm > 1e-10:
            feat /= norm
        return feat

    def identify_equation(self, expr: str) -> tuple:
        mf = self.math_feature(expr)
        best, bs = '', -1.0
        for eq, ef in self._eq_cache.items():
            s = float(np.dot(mf, ef))
            if s > bs:
                best, bs = eq, s
        return best, round(bs, 4)

    def kernel(self, x, y):
        fx = self.math_feature(x)
        fy = self.math_feature(y)
        return max(0.0, float(np.dot(fx, fy)))


# ═══════════════════════════════════════════════
# UNIFIED QUANTUM REASONER
# ═══════════════════════════════════════════════

class ArisQuantumReasoner:
    """Unified reasoning engine: code + math + language — zero LLM"""

    def __init__(self):
        self.un6 = UN6QuantumKernel()
        self.code_q = CodeQuantumKernel(self.un6)
        self.math_q = MathQuantumKernel(self.un6)

    def detect_mode(self, query: str) -> str:
        has_def = bool(re.search(r'\bdef\b|\bfunction\b|\bclass\b', query))
        has_loop = bool(re.search(r'\bfor\b|\bwhile\b|\bmap\b', query))
        has_math_op = bool(re.search(r'[+\-*/^=]|integral|derivative|lim|sqrt|sin\(|cos\(', query))
        if has_def or has_loop:
            return 'code'
        if has_math_op:
            return 'math'
        return 'language'

    def reason_code(self, query: str) -> dict:
        t0 = time.perf_counter()
        alg, conf = self.code_q.identify_algorithm(query)
        related = self.code_q.related_algorithms(query, 0.2)
        t = time.perf_counter() - t0
        return {
            'mode': 'code',
            'algorithm': alg,
            'confidence': conf,
            'related': related[:3] if related else [],
            'time_ms': round(t * 1000, 2),
        }

    def reason_math(self, query: str) -> dict:
        t0 = time.perf_counter()
        eq, conf = self.math_q.identify_equation(query)
        t = time.perf_counter() - t0
        return {
            'mode': 'math',
            'equation': eq,
            'confidence': conf,
            'description': self.math_q.EQUATION_PROTOTYPES.get(eq, ''),
            'time_ms': round(t * 1000, 2),
        }

    def reason_language(self, query: str) -> dict:
        t0 = time.perf_counter()
        lang = self.un6.detect_lang(query)
        concepts = ['love','heart','sky','star','life','dream','time','world','knowledge']
        scores = [(c, self.un6.kernel(query, c)) for c in concepts]
        scores.sort(key=lambda x: x[1], reverse=True)
        t = time.perf_counter() - t0
        return {
            'mode': 'language',
            'lang': lang,
            'top_match': scores[0],
            'all_scores': scores[:3],
            'time_ms': round(t * 1000, 2),
        }

    def reason(self, query: str, mode: str = 'auto') -> dict:
        if mode == 'auto':
            mode = self.detect_mode(query)
        if mode == 'code':
            return self.reason_code(query)
        elif mode == 'math':
            return self.reason_math(query)
        else:
            return self.reason_language(query)


# ═══════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("ARIS QUANTUM REASONER — 纯核代码+数学推理")
    logger.info("=" * 60)
    R = ArisQuantumReasoner()

    logger.info("\n【代码推理】")
    for test in [
        'def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)',
        'def fact(n): return 1 if n <= 1 else n * fact(n-1)',
        'for i in range(10): print(i**2)',
        'def sort(arr): return sorted(arr)',
    ]:
        r = R.reason(test)
        logger.info(f"  {test[:55]}...")
        logger.info(f"    → 算法:{r['algorithm']} (conf={r['confidence']}) related={r['related']} [{r['time_ms']}ms]")
    logger.info("\n【数学推理】")
    for test in [
        'E = mc^2', 'a^2 + b^2 = c^2', 'F = G * m1 * m2 / r^2',
        'd/dx sin(x) = cos(x)', 'integral of x^2 dx', 'x = (-b +- sqrt(b^2 - 4ac))/(2a)',
    ]:
        r = R.reason(test)
        logger.info(f"  {test:<35} → {r['equation'][:30]} (conf={r['confidence']}) [{r['time_ms']}ms]")
    logger.info("\n【语言语义】")
    for test in ['爱是什么','what is love','宇宙の起源','사랑이 뭐야','meaning of life']:
        r = R.reason(test)
        logger.info(f"  {test:<20} → lang={r['lang']} match={r['top_match'][0]}({r['top_match'][1]:.3f}) [{r['time_ms']}ms]")
    logger.info("\n【吞吐量基准】")
    t0 = time.perf_counter()
    n = 1000
    for _ in range(n):
        R.reason('def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)', 'auto')
    t = time.perf_counter() - t0
    logger.info(f"  代码推理: {n/t:.0f}次/秒 ({t/n*1000:.3f}ms/次)")
    t0 = time.perf_counter()
    for _ in range(n):
        R.reason('E = mc^2', 'auto')
    t = time.perf_counter() - t0
    logger.info(f"  数学推理: {n/t:.0f}次/秒 ({t/n*1000:.3f}ms/次)")
    t0 = time.perf_counter()
    for _ in range(n):
        R.reason('爱是什么', 'auto')
    t = time.perf_counter() - t0
    logger.info(f"  语义推理: {n/t:.0f}次/秒 ({t/n*1000:.3f}ms/次)")
    logger.info(f"\n{'='*60}")
    logger.info("规格总结:")
    logger.info(f"  算法原型: {len(CodeQuantumKernel._init_prototypes.__code__.co_varnames) if hasattr(CodeQuantumKernel._init_prototypes, '__code__') else 'N/A'} 种")
    logger.info(f"  数学方程: {len(MathQuantumKernel.EQUATION_PROTOTYPES)} 种")
    logger.info(f"  代码区域: {len(CodeQuantumKernel.CODE_REGIONS)} 个特征区")
    logger.info(f"  数学区域: {len(MathQuantumKernel.MATH_REGIONS)} 个特征区")
    logger.info(f"  零LLM: ✅")
    logger.info(f"{'='*60}")