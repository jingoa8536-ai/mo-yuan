"""
Quantum Vector Database (QVDB) — 量子向量数据库插件系统
=========================================================
统一接口下接入6+检索后端，用量子核(V7/UN6)替代传统嵌入。

架构:
  QVDB (主数据库)
    ├── PluginManager (热加载/卸载)
    ├── Backend: QuantumMatrix (我们的矩阵乘KB, 8981条)
    ├── Backend: QuantumPageIndex (树搜索, 替LLM为UN6评分)
    ├── Backend: QuantumSemantica (前向链规则推理)
    ├── Backend: QuantumNodeRAG (异构图索引)
    ├── Backend: CodeGraphSearch (代码FTS5+中文)
    └── Router (根据查询类型自动选后端)

使用:
  db = QuantumVectorDB()
  db.add_plugin("quantum_matrix")
  db.add_plugin("quantum_semantica")
  results = db.search("量子核如何工作？", top_k=5)
  # → 自动路由到最佳后端, 融合结果

印记: Aris Quantum Database — 2026-06-20
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json, hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
_STATE_DIR = os.path.join(_DIR, "state")
os.makedirs(_STATE_DIR, exist_ok=True)


# ================================================================
# 统一数据结构
# ================================================================

@dataclass
class SearchResult:
    """统一搜索结果"""
    text: str
    score: float
    source: str          # 来源后端
    source_id: str = ""  # 后端内的ID
    metadata: Dict = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)  # 推理链

@dataclass  
class SearchRequest:
    """统一搜索请求"""
    query: str
    top_k: int = 5
    min_score: float = 0.1
    preferred_backend: str = ""  # 空=自动路由
    include_reasoning: bool = False


# ================================================================
# 插件基类
# ================================================================

class BackendPlugin(ABC):
    """检索后端插件基类"""
    
    name: str = "base"
    version: str = "1.0"
    description: str = ""
    
    @abstractmethod
    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        pass
    
    @abstractmethod
    def add(self, texts: List[str], metadatas: List[Dict] = None) -> int:
        """添加文档, 返回添加数量"""
        pass
    
    def stats(self) -> Dict:
        return {"name": self.name, "version": self.version}

    def _encode(self, text: str) -> np.ndarray:
        """共享编码器 — 所有插件用同一个V7"""
        return QVDB.get_encoder().encode(text)


# ================================================================
# 后端1: 量子矩阵检索 (我们的核心KB)
# ================================================================

class QuantumMatrixBackend(BackendPlugin):
    """基于矩阵乘的知识检索 — 核心后端"""
    name = "quantum_matrix"
    version = "2.0"
    description = "V7编码 + 矩阵乘检索 (8981条)"

    def __init__(self):
        self._kb = None
        self._loaded = False

    def _lazy(self):
        if self._loaded: return
        from matrix_knowledge import MatrixKnowledgeRetriever
        self._kb = MatrixKnowledgeRetriever()
        self._loaded = True

    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        self._lazy()
        if not self._kb or not self._kb._loaded:
            return []
        
        results = self._kb.search(query, top_k=top_k, threshold=min_score)
        return [
            SearchResult(
                text=r.get("text", ""), score=r.get("score", 0),
                source=self.name, source_id=str(r.get("id", "")),
                metadata=r.get("meta", {})
            )
            for r in results
        ]

    def add(self, texts: List[str], metadatas: List[Dict] = None) -> int:
        self._lazy()
        if not self._kb: return 0
        for i, t in enumerate(texts):
            self._kb.add(t, metadatas[i] if metadatas else {})
        return len(texts)

    def stats(self) -> Dict:
        self._lazy()
        return {
            "name": self.name, "entries": self._kb._matrix.shape[0] if self._kb and self._kb._loaded else 0,
            "dim": self._kb._matrix.shape[1] if self._kb and self._kb._loaded else 0,
        }


# ================================================================
# 后端2: 量子PageIndex (树搜索, 替换LLM为UN6评分)
# ================================================================

class QuantumPageIndexBackend(BackendPlugin):
    """
    量子PageIndex — 树形索引 + UN6核评分 (非LLM)
    
    核心改造: PageIndex原来用LLM判断"标题是否在页面上"、
    评分分支等。我们全部替换为UN6量子核算相似度。
    """
    name = "quantum_pageindex"
    version = "1.0"
    description = "树形索引 + UN6量子核束搜索"

    def __init__(self):
        self._tree = {"id": "root", "title": "", "children": []}
        self._v7 = None
        self._un6 = None

    def _lazy(self):
        if self._v7 is None:
            from semantic_engine import get_encoder
            self._v7 = get_encoder(1024)
        if self._un6 is None:
            try:
                from aris_lm_v10_un6 import UN6QuantumKernel
                self._un6 = UN6QuantumKernel()
            except: pass

    def add(self, texts: List[str], metadatas: List[Dict] = None) -> int:
        """构建树索引 — 把文档按段落分层"""
        self._lazy()
        for i, text in enumerate(texts):
            # 用首句作为章节标题
            lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 10]
            title = lines[0][:60] if lines else text[:60]
            content = "\n".join(lines[1:6]) if len(lines) > 1 else text[:300]
            
            doc_node = {
                "id": f"doc_{i}", "title": title,
                "content": content, "children": []
            }
            # 按段落分层
            paragraphs = re.split(r'\n\s*\n', content)
            for pi, para in enumerate(paragraphs[:5]):
                para = para.strip()
                if len(para) > 30:
                    doc_node["children"].append({
                        "id": f"doc_{i}_p{pi}", "title": para[:60],
                        "content": para[:300], "children": []
                    })
            self._tree["children"].append(doc_node)
        return len(texts)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        """UN6量子核束搜索树"""
        self._lazy()
        qv = self._v7.encode(query)
        n = np.linalg.norm(qv)
        if n > 0: qv = qv / n

        from collections import deque
        results = []
        queue = deque([(self._tree, 0, 1.0)])

        while queue:
            node, depth, parent_score = queue.popleft()
            if depth > 4: continue

            children = node.get("children", [])
            if not children:
                if node.get("content"):
                    results.append(SearchResult(
                        text=node["content"][:300], score=parent_score,
                        source=self.name, source_id=node.get("id", ""),
                    ))
                continue

            scored = []
            for child in children:
                ct = f"{child.get('title','')} {child.get('content','')[:200]}"
                cv = self._v7.encode(ct)
                cv = cv / (np.linalg.norm(cv) + 1e-10)
                sc = float(qv @ cv)
                if self._un6:
                    try: sc = sc * 0.6 + self._un6.kernel(query, ct) * 0.4
                    except: pass
                scored.append((child, sc))

            scored.sort(key=lambda x: -x[1])
            for child, sc in scored[:3]:
                queue.append((child, depth + 1, sc))

        results.sort(key=lambda x: -x.score)
        return results[:top_k]


# ================================================================
# 后端3: 量子Semantica (前向链规则推理)
# ================================================================

class QuantumSemanticaBackend(BackendPlugin):
    """
    量子Semantica — 规则驱动推理检索
    
    实现 Semantica 的前向链: IF condition THEN conclusion
    用量子核算条件匹配度，自动触发推理规则
    """
    name = "quantum_semantica"
    version = "1.0"
    description = "前向链规则推理 + 量子态匹配"

    def __init__(self):
        self._rules = []  # [(condition, conclusion, cond_vec)]
        self._v7 = None
        self._add_builtin_rules()

    def _add_builtin_rules(self):
        builtin = [
            ("量子核|UN6|特征空间", "启用16384D跨语言语义桥检索"),
            ("PSI|认知|需求", "激活需求系统多维度评估"),
            ("代码|函数|类|定义", "遍历CodeGraph调用链"),
            ("架构|设计|管线", "展开多层级融合分析"),
            ("LAAP|零LLM|无模型", "检测ACAP一致性维度"),
            ("推理|链式|因果", "启动量子轨迹50步演化"),
            ("知识|图谱|关系", "异构图BFS遍历展开"),
            ("性能|速度|延迟", "矩阵乘规模评估+缓存优化"),
        ]
        self._rules = [(c, o) for c, o in builtin]

    def _lazy(self):
        if self._v7 is None:
            from semantic_engine import get_encoder
            self._v7 = get_encoder(1024)

    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        self._lazy()
        qv = self._v7.encode(query)
        n = np.linalg.norm(qv)
        if n > 0: qv = qv / n

        results = []
        for cond, conclusion in self._rules:
            cv = self._v7.encode(cond)
            cv = cv / (np.linalg.norm(cv) + 1e-10)
            sc = float(qv @ cv)
            if sc > 0.25:
                results.append(SearchResult(
                    text=f"规则触发: {conclusion}",
                    score=sc, source=self.name,
                    reasoning=[f"IF {cond} THEN {conclusion} (信度:{sc:.2f})"],
                    metadata={"condition": cond, "conclusion": conclusion},
                ))

        results.sort(key=lambda x: -x.score)
        return results[:top_k]

    def add(self, texts: List[str], metadatas: List[Dict] = None) -> int:
        for t in texts:
            if "→" in t or "->" in t:
                parts = re.split(r'\s*[-=]>+\s*', t, maxsplit=1)
                if len(parts) == 2:
                    self._rules.append((parts[0].strip(), parts[1].strip()))
        return len(texts)

    def add_rule(self, condition: str, conclusion: str):
        self._rules.append((condition, conclusion))

    def stats(self) -> Dict:
        return {"name": self.name, "rules": len(self._rules)}


# ================================================================
# 后端4: CodeGraph 代码搜索
# ================================================================

class CodeGraphBackend(BackendPlugin):
    """CodeGraph FTS5 + 中文映射搜索"""
    name = "codegraph"
    version = "1.1"
    description = "8027节点代码图谱 + 中文术语映射"

    def __init__(self):
        self._cg = None

    def _lazy(self):
        if self._cg is None:
            try:
                from codegraph_chinese_search import CodeGraphChinese
                self._cg = CodeGraphChinese()
            except: pass

    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[SearchResult]:
        self._lazy()
        if not self._cg: return []

        try:
            nodes = self._cg.search_cn(query, limit=top_k)
            results = []
            for n in nodes:
                kind = n.get("kind", "")
                name = n.get("name", "")
                doc = n.get("docstring", "") or ""
                fp = n.get("file_path", "")
                text = f"[{kind}] {name}: {doc[:200]} → {fp}" if doc else f"[{kind}] {name} → {fp}"
                results.append(SearchResult(
                    text=text, score=0.6, source=self.name,
                    source_id=n.get("id", ""),
                    metadata={"kind": kind, "file": fp, "line": n.get("start_line", 0)},
                ))
            return results[:top_k]
        except:
            return []

    def add(self, texts: List[str], metadatas: List[Dict] = None) -> int:
        return 0  # CodeGraph 是静态索引

    def stats(self) -> Dict:
        return {"name": self.name, "db": ".codegraph/codegraph.db"}


# ================================================================
# 路由决策器
# ================================================================

class QueryRouter:
    """根据查询内容自动选择最佳后端"""

    ROUTING_RULES = [
        # (关键词模式, 后端名, 权重)
        ("代码|函数|class|def|import|怎么用|调用|实现|哪个文件|在哪", "codegraph", 10),
        ("量子核|UN6|16384|特征空间|kernel|向量维度", "quantum_matrix", 8),
        ("规则|推理|因果|IF|THEN|前向|逻辑", "quantum_semantica", 7),
        ("树|章节|目录|索引|文档结构|长文档", "quantum_pageindex", 6),
        ("如何|怎么|为什么|原理|机制|区别|对比|分析", "quantum_matrix", 5),
    ]

    @classmethod
    def route(cls, query: str, available_backends: List[str]) -> str:
        scores = {}
        for pattern, backend, weight in cls.ROUTING_RULES:
            if backend not in available_backends:
                continue
            keywords = pattern.split("|")
            hits = sum(1 for k in keywords if k in query)
            if hits > 0:
                scores[backend] = scores.get(backend, 0) + hits * weight

        if scores:
            return max(scores, key=scores.get)
        # 默认: quantum_matrix
        return "quantum_matrix" if "quantum_matrix" in available_backends else available_backends[0]


# ================================================================
# 主数据库
# ================================================================

class QuantumVectorDB:
    """量子向量数据库 — 插件化检索系统"""

    _shared_encoder = None

    @classmethod
    def get_encoder(cls):
        if cls._shared_encoder is None:
            from semantic_engine import get_encoder
            cls._shared_encoder = get_encoder(1024)
        return cls._shared_encoder

    def __init__(self):
        self._plugins: Dict[str, BackendPlugin] = {}
        self._router = QueryRouter()
        self._stats = {"searches": 0, "total_ms": 0}

        # 默认加载核心后端
        self.add_plugin(QuantumMatrixBackend())
        self.add_plugin(QuantumSemanticaBackend())

    def add_plugin(self, plugin: BackendPlugin):
        self._plugins[plugin.name] = plugin
        logger.info(f"  [QVDB] 加载插件: {plugin.name} ({plugin.description})")
        return plugin

    def remove_plugin(self, name: str):
        if name in self._plugins:
            del self._plugins[name]
            logger.info(f"  [QVDB] 卸载: {name}")
    def list_plugins(self) -> List[Dict]:
        return [p.stats() for p in self._plugins.values()]

    def search(self, query: str, top_k: int = 6,
               backend: str = "", fusion: bool = True) -> Dict:
        """
        统一搜索入口

        Args:
            query: 查询文本
            top_k: 返回条数
            backend: 指定后端 (空=自动路由)
            fusion: 是否融合多后端结果

        Returns:
            {results, backend_used, latency_ms, fusion_sources}
        """
        t0 = time.perf_counter()

        # 确定后端
        if backend and backend in self._plugins:
            backends = [backend]
        else:
            backends = [self._router.route(query, list(self._plugins.keys()))]
            # 融合模式: 加一个辅助后端
            if fusion and len(self._plugins) > 1:
                secondary = "quantum_semantica" if backends[0] != "quantum_semantica" else "quantum_matrix"
                if secondary in self._plugins and secondary not in backends:
                    backends.append(secondary)

        # 并行搜索
        all_results = []
        for bn in backends:
            if bn in self._plugins:
                try:
                    results = self._plugins[bn].search(query, top_k=top_k)
                    all_results.extend(results)
                except Exception as e:
                    logger.info(f"  [QVDB] 后端 {bn} 报错: {e}")
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: -x.score):
            fp = r.text[:60]
            if fp not in seen and r.score > 0.05:
                seen.add(fp)
                unique.append(r)
                if len(unique) >= top_k:
                    break

        self._stats["searches"] += 1
        self._stats["total_ms"] += (time.perf_counter() - t0) * 1000

        return {
            "results": unique,
            "backend_used": backends[0],
            "fusion_backends": backends,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }

    def search_texts(self, query: str, top_k: int = 5) -> List[str]:
        """便利方法: 只返回文本"""
        r = self.search(query, top_k=top_k)
        return [x.text[:300] for x in r["results"]]

    def add_documents(self, texts: List[str], backend: str = "quantum_matrix"):
        """添加文档到指定后端"""
        if backend in self._plugins:
            return self._plugins[backend].add(texts)
        return 0

    def stats(self) -> Dict:
        return {
            "plugins": len(self._plugins),
            "plugin_list": [p.name for p in self._plugins.values()],
            "searches": self._stats["searches"],
            "avg_ms": round(self._stats["total_ms"] / max(1, self._stats["searches"]), 1),
            "plugin_stats": [p.stats() for p in self._plugins.values()],
        }


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Quantum Vector Database 自测")
    logger.info("=" * 60)
    db = QuantumVectorDB()
    db.add_plugin(CodeGraphBackend())
    db.add_plugin(QuantumPageIndexBackend())

    logger.info(f"\n  插件: {len(db._plugins)} 个")
    for ps in db.list_plugins():
        logger.info(f"    {ps['name']}: {ps.get('entries',ps.get('rules','?'))}")
    queries = [
        "量子核是怎么工作的？",
        "代码里UN6QuantumKernel在哪定义？",
        "PSI认知循环的需求系统",
        "按照规则推理：如果零LLM，则ACAP成立",
    ]

    logger.info(f"\n{'查询':32s} {'后端':20s} {'结果':40s} {'延迟':>7s}")
    logger.info("-" * 105)
    for q in queries:
        r = db.search(q, top_k=3, fusion=True)
        first = r["results"][0].text[:40] if r["results"] else "(无)"
        logger.info(f"  {q:32s} {r['backend_used']:20s} {first:40s} {r['latency_ms']:>6.1f}ms")
    logger.info(f"\n  {db.stats()}")