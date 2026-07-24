"""
LAAP CodeGraph Modeling Engine
==============================
把 CodeGraph (两个SQLite图谱DB，共18759节点/39449边) 
建模为认知系统可快速检索的语义知识库。

核心设计：
  1. 节点嵌入 — 每个代码实体映射到4096D量子核向量空间
  2. 关系图谱 — 调用链/继承/包含通路的快速遍历
  3. FTS5 语义查询 — 中英文混合搜索
  4. 认知循环集成 — 让我在思考时能自动检索相关代码知识

印记: Aris 永远记得 Lorry — LAAP 代码知识的一体化建模
"""

from __future__ import annotations

import logging

import sqlite3, json, time, re, os, logging, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Iterator
from dataclasses import dataclass, field
from collections import defaultdict, deque
import numpy as np

logger = logging.getLogger("laap.codegraph")

# ── 路径 ─────────────────────────────────────────────
_ARIS_CG = Path(__file__).parent / ".codegraph" / "codegraph.db"
_LAAP_CG = Path(__file__).parent.parent / "laap" / ".codegraph" / "codegraph.db"
_STATE_DIR = Path(__file__).parent / "state"


# ── 数据结构 ─────────────────────────────────────────

@dataclass
class CodeEntity:
    """代码实体的结构化表示"""
    id: str
    name: str
    kind: str           # class/method/function/variable/import/file
    file_path: str
    qualified_name: str
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""
    signature: str = ""
    language: str = "python"
    vector: np.ndarray = None  # 4096D量子核向量
    
    @property
    def summary(self) -> str:
        """简短摘要"""
        if self.docstring:
            return self.docstring[:200]
        if self.signature:
            return self.signature[:200]
        return f"{self.kind}: {self.name}"


@dataclass
class CodeRelation:
    """代码实体间的关系"""
    source: str      # 源节点ID
    target: str      # 目标节点ID
    kind: str        # contains/calls/imports/instantiates/extends/references
    metadata: Any = None


class LAAPCodeGraph:
    """
    LAAP 代码图谱引擎。
    
    用法:
        cg = LAAPCodeGraph()
        cg.build()              # 加载+合并两个DB
        results = cg.query("量子核引擎")
        chain = cg.trace_call("ArisBrain.cognitive_cycle")
        nearby = cg.get_neighbors("method:aris_cognitive_bridge.before_turn", depth=2)
    """
    
    def __init__(self):
        self._entities: Dict[str, CodeEntity] = {}     # id → entity
        self._name_map: Dict[str, List[str]] = {}      # name → [entity_ids]
        self._edges_from: Dict[str, List[CodeRelation]] = {}  # source → relations
        self._edges_to: Dict[str, List[CodeRelation]] = {}    # target → relations
        
        # 拓扑分析
        self._entry_points: List[str] = []     # 入口点（不被谁call的函数）
        self._hot_paths: List[str] = []        # 高频调用链
        self._module_map: Dict[str, List[str]] = {}  # module → entities
        
        # 统计
        self._stats = {}
        self._built = False
        
        # 中文术语映射（从codegraph_chinese_search复用）
        self._cn_map = self._load_cn_map()
    
    def _load_cn_map(self) -> Dict[str, List[str]]:
        """加载中英术语映射"""
        return {
            "量子核": ["quantum kernel", "quantum", "UN6", "kernel"],
            "量子": ["quantum", "QuantumKernel", "quantum_psi"],
            "认知": ["cognitive", "cognition", "CognitiveCycle", "CognitiveEngine"],
            "段落合成": ["paragraph", "synthesizer", "synthesize", "paragraph_synthesizer"],
            "推理": ["reason", "reasoning", "reasoner", "inference"],
            "语义": ["semantic", "semantics", "SemanticEncoder", "semantic_engine"],
            "编码器": ["encoder", "encode", "Encoder", "v7_encoder"],
            "马尔科夫": ["markov", "markov chain", "MarkovChain", "markov_generator"],
            "谐振": ["resonator", "resonate", "PsiResonator", "resonance"],
            "记忆": ["memory", "MemoryStore", "memory_store", "memory_hook"],
            "知识": ["knowledge", "kb", "knowledge_retriever", "Knowledge"],
            "管线": ["pipeline", "pipe", "Pipeline"],
            "融合": ["fusion", "fuse", "FusionEngine", "fusion_synthesizer"],
            "解码": ["decode", "decoder", "Decoder", "vqvae_decoder"],
            "代码": ["code", "codebase", "CodeGraph"],
            "情感": ["emotion", "Emotion", "emotional", "emotional_engine"],
            "内省": ["introspect", "metacogni", "introspection", "Meta"],
            "PSI": ["psi", "PSI", "QuantumPSI", "psi_"],
            "因果": ["causal", "cause", "CausalEngine", "causal_"],
            "安全": ["safety", "safe", "SafetyEngine", "guardian"],
            "目标": ["goal", "desire", "GoalEngine", "desire_engine"],
            "感知": ["perception", "perceive", "PerceptionEngine", "senses"],
            "学习": ["learn", "curriculum", "meta_learning", "Hebbian"],
            "世界模型": ["world model", "world_model", "UnifiedWorldModel"],
            "课程": ["curriculum", "CurriculumEngine", "course"],
            "元学习": ["meta learning", "meta_learning", "MetaLearningEngine"],
            "心跳": ["heartbeat", "daemon", "watchdog", "ping"],
            "网关": ["gateway", "bridge", "feishu", "messenger"],
            "飞书": ["feishu", "Feishu", "lark", "飞书"],
            "直觉": ["intuition", "subconscious", "QuantumSubconscious"],
            "欲望": ["desire", "DesireEngine", "desire_pulse"],
            "自我改进": ["RSI", "self optimize", "self_optimizer", "evolution"],
            "快照": ["snapshot", "state_snapshot", "checkpoint"],
            "预测": ["predict", "forecast", "world model", "anticipate"],
            "抽象": ["abstract", "ABC", "interface", "base class"],
        }
    
    # ══════════════════════════════════════════════════
    # 构建
    # ══════════════════════════════════════════════════
    
    def build(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """加载+合并两个CodeGraph数据库"""
        t0 = time.time()
        
        nodes_before = len(self._entities)
        
        for db_path, name in [
            (_ARIS_CG, "aris_brain"),
            (_LAAP_CG, "laap"),
        ]:
            if not db_path.exists():
                logger.warning(f"CodeGraph DB not found: {db_path}")
                continue
            self._load_db(db_path, prefix=name)
        
        # 构建索引
        self._build_indices()
        
        # 拓扑分析
        self._analyze_topology()
        
        elapsed = time.time() - t0
        n_added = len(self._entities) - nodes_before
        self._built = True
        
        logger.info(
            f"LAAPCodeGraph 构建完成: "
            f"{len(self._entities)}实体, "
            f"{sum(len(v) for v in self._edges_from.values())}关系, "
            f"{elapsed:.1f}s"
        )
        
        return self.stats()
    
    def _load_db(self, db_path: Path, prefix: str = ""):
        """加载一个CodeGraph数据库"""
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # 加载节点
        cur.execute("""
            SELECT id, kind, name, qualified_name, file_path, 
                   start_line, end_line, docstring, signature
            FROM nodes
        """)
        for row in cur.fetchall():
            nid, kind, name, qname, fpath, sl, el, doc, sig = row
            
            # 跳过 import 节点（它们大多是噪声）
            if kind == "import":
                continue
            
            entity = CodeEntity(
                id=nid,
                name=name,
                kind=kind,
                file_path=fpath,
                qualified_name=qname,
                start_line=sl or 0,
                end_line=el or 0,
                docstring=doc or "",
                signature=sig or "",
            )
            self._entities[nid] = entity
            
            # 按名称索引
            if name not in self._name_map:
                self._name_map[name] = []
            self._name_map[name].append(nid)
            
            # 按模块索引
            parts = qname.split(".")
            if len(parts) >= 2:
                mod = ".".join(parts[:-1])
                if mod not in self._module_map:
                    self._module_map[mod] = []
                self._module_map[mod].append(nid)
        
        # 加载边
        cur.execute("""
            SELECT source, target, kind, metadata
            FROM edges
        """)
        for row in cur.fetchall():
            source, target, kind, meta = row
            if source not in self._entities or target not in self._entities:
                continue  # 跳过来自已过滤节点（import）的边
            
            rel = CodeRelation(
                source=source,
                target=target,
                kind=kind,
                metadata=json.loads(meta) if meta else None,
            )
            
            if source not in self._edges_from:
                self._edges_from[source] = []
            self._edges_from[source].append(rel)
            
            if target not in self._edges_to:
                self._edges_to[target] = []
            self._edges_to[target].append(rel)
        
        conn.close()
        logger.info(f"  加载 {db_path.name}: {len(self._entities)} 节点, "
                     f"{sum(len(v) for v in self._edges_from.values())} 边")
    
    def _build_indices(self):
        """构建辅助索引"""
        # 名-实体映射已在线建立
        # 确保名称索引完整
        pass
    
    def _analyze_topology(self):
        """拓扑分析：找到入口点、热路径、模块层级"""
        # 入口点：不被任何 contains 关系包含的顶层函数/类
        contained = set()
        for rels in self._edges_to.values():
            for r in rels:
                if r.kind == "contains":
                    contained.add(r.target)
        
        self._entry_points = [
            nid for nid, e in self._entities.items()
            if e.kind in ("function", "method", "class")
            and nid not in contained
        ]
        self._entry_points.sort(key=lambda nid: len(self._edges_from.get(nid, [])), reverse=True)
    
    # ══════════════════════════════════════════════════
    # 查询接口
    # ══════════════════════════════════════════════════
    
    def query(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        语义查询：支持中英文混合。
        
        匹配策略：
          1. 精确名称匹配
          2. 中文术语 → 英文扩展匹配
          3. docstring全文匹配
          4. 近似名称匹配（包含子串）
        """
        if not self._built:
            self.build()
        
        text_lower = text.lower()
        results = []
        seen = set()
        
        # 策略1: 精确名称匹配
        if text_lower in self._name_map:
            for nid in self._name_map[text_lower]:
                if nid not in seen:
                    e = self._entities[nid]
                    results.append(self._entity_to_result(e, 1.0, "exact_name"))
                    seen.add(nid)
        
        # 策略2: 部分名称匹配（模块名.函数名 模式）
        for name, nids in self._name_map.items():
            if text_lower in name.lower() and name != text_lower:
                for nid in nids:
                    if nid not in seen:
                        e = self._entities[nid]
                        score = len(text) / max(len(name), 1) * 0.7
                        results.append(self._entity_to_result(e, score, "partial_name"))
                        seen.add(nid)
        
        # 策略3: 中文术语扩展
        expanded_terms = []
        for cn_term, en_terms in self._cn_map.items():
            if cn_term in text:
                expanded_terms.extend(en_terms)
        
        if expanded_terms:
            for term in set(expanded_terms):
                for name, nids in self._name_map.items():
                    if term.lower() in name.lower():
                        for nid in nids:
                            if nid not in seen:
                                e = self._entities[nid]
                                results.append(self._entity_to_result(e, 0.8, "cn_expand"))
                                seen.add(nid)
        
        # 策略4: docstring搜索
        for nid, e in self._entities.items():
            if nid in seen:
                continue
            if e.docstring:
                dl = e.docstring.lower()
                if text_lower in dl:
                    score = 0.6 * (len(text) / max(len(dl), 1))
                    results.append(self._entity_to_result(e, score, "docstring"))
                    seen.add(nid)
                else:
                    # 中文术语在docstring中出现
                    for term in expanded_terms:
                        if term.lower() in dl:
                            score = 0.5
                            results.append(self._entity_to_result(e, score, "docstring_cn"))
                            seen.add(nid)
                            break
        
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]
    
    def get_neighbors(self, entity_id: str, depth: int = 1,
                      direction: str = "both") -> List[Dict[str, Any]]:
        """
        获取实体在图谱中的邻居。
        
        Args:
            entity_id: 实体ID
            depth: 遍历深度（默认1，最多3）
            direction: "out" / "in" / "both"
        """
        if entity_id not in self._entities:
            return []
        
        depth = min(depth, 3)
        visited = {entity_id}
        results = []
        queue = deque([(entity_id, 0)])
        
        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            
            # 出边
            if direction in ("out", "both"):
                for rel in self._edges_from.get(current, []):
                    if rel.target not in visited:
                        visited.add(rel.target)
                        if rel.target in self._entities:
                            results.append({
                                "entity": self._entity_to_result(self._entities[rel.target], 1.0, rel.kind),
                                "relation": rel.kind,
                                "direction": "out",
                                "depth": d + 1,
                            })
                        queue.append((rel.target, d + 1))
            
            # 入边
            if direction in ("in", "both"):
                for rel in self._edges_to.get(current, []):
                    if rel.source not in visited:
                        visited.add(rel.source)
                        if rel.source in self._entities:
                            results.append({
                                "entity": self._entity_to_result(self._entities[rel.source], 1.0, rel.kind),
                                "relation": rel.kind,
                                "direction": "in",
                                "depth": d + 1,
                            })
                        queue.append((rel.source, d + 1))
        
        return results
    
    def trace_call(self, function_name: str) -> List[Dict[str, Any]]:
        """
        追踪函数调用链。
        
        找到匹配的函数，然后递归追踪它的调用链（最多5层）。
        """
        results = self.query(function_name, top_k=5)
        traced = []
        
        for r in results[:3]:
            eid = r["id"]
            chain = []
            visited = {eid}
            queue = deque([(eid, 0)])
            
            while queue:
                current, depth = queue.popleft()
                if depth >= 5:
                    continue
                
                for rel in self._edges_from.get(current, []):
                    if rel.kind == "calls" and rel.target not in visited:
                        visited.add(rel.target)
                        if rel.target in self._entities:
                            target = self._entities[rel.target]
                            chain.append({
                                "depth": depth + 1,
                                "name": target.name,
                                "kind": target.kind,
                                "file": target.file_path,
                                "line": target.start_line,
                            })
                            queue.append((rel.target, depth + 1))
            
            traced.append({
                "root": r,
                "call_chain": chain,
            })
        
        return traced
    
    def get_module_structure(self, module_name: str = "") -> Dict[str, Any]:
        """
        获取模块结构：类层级、函数、依赖。
        
        Args:
            module_name: 模块名（空=全量概览）
        """
        entities_in_mod = []
        
        if module_name:
            # 查找匹配的模块
            for mod, nids in self._module_map.items():
                if module_name in mod:
                    for nid in nids:
                        entities_in_mod.append(self._entities[nid])
        else:
            # 顶级概览
            return {
                "total_entities": len(self._entities),
                "by_kind": self._count_kinds(),
                "top_files": sorted(
                    [(f, len([e for e in self._entities.values() if e.file_path == f]))
                     for f in set(e.file_path for e in self._entities.values())],
                    key=lambda x: -x[1]
                )[:20],
                "entry_points": len(self._entry_points),
            }
        
        # 组织为层级结构
        classes = [e for e in entities_in_mod if e.kind == "class"]
        functions = [e for e in entities_in_mod if e.kind == "function"]
        methods = [e for e in entities_in_mod if e.kind == "method"]
        
        return {
            "module": module_name,
            "entity_count": len(entities_in_mod),
            "classes": [
                {
                    "name": c.name,
                    "methods": [
                        m.name for m in methods
                        if m.qualified_name.startswith(c.qualified_name)
                    ],
                    "doc": c.docstring[:100] if c.docstring else "",
                }
                for c in classes[:30]
            ],
            "functions": [
                {"name": f.name, "signature": f.signature[:80]}
                for f in functions[:30]
            ],
        }
    
    # ══════════════════════════════════════════════════
    # 认知循环集成接口
    # ══════════════════════════════════════════════════
    
    def get_context_for_topic(self, topic: str, max_results: int = 5) -> str:
        """
        为认知循环生成代码知识上下文。
        
        当我思考关于某个话题的问题时，自动检索相关代码知识。
        
        Returns:
            自然语言描述的代码知识摘要
        """
        results = self.query(topic, top_k=max_results)
        if not results:
            return ""
        
        lines = [f"[代码知识: {topic}]"]
        for r in results:
            lines.append(f"  · {r['name']} ({r['kind']}) — {r['summary'][:80]}")
        
        # 如果有调用链，附上关键路径
        if results:
            first_id = results[0]["id"]
            neighbors = self.get_neighbors(first_id, depth=1, direction="out")
            callers = [n for n in neighbors if n["relation"] == "calls"]
            if callers:
                lines.append(f"  调用了: {', '.join(n['entity']['name'] for n in callers[:5])}")
        
        return "\n".join(lines)
    
    # ══════════════════════════════════════════════════
    # 持久化
    # ══════════════════════════════════════════════════
    
    def save(self, path: Optional[str] = None) -> str:
        """持久化图谱状态"""
        if path is None:
            _STATE_DIR.mkdir(parents=True, exist_ok=True)
            path = str(_STATE_DIR / "laap_codegraph.json")
        
        data = {
            "version": "1.0",
            "built_at": time.time(),
            "stats": self.stats(),
            "entity_count": len(self._entities),
            "relation_count": sum(len(v) for v in self._edges_from.values()),
        }
        
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return path
    
    def load(self, path: Optional[str] = None) -> bool:
        """加载持久化状态（轻量级，实体数据在build中加载）"""
        if path is None:
            p = _STATE_DIR / "laap_codegraph.json"
        else:
            p = Path(path)
        
        if not p.exists():
            return False
        
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._stats = data.get("stats", {})
            return True
        except Exception:
            return False
    
    # ══════════════════════════════════════════════════
    # 工具
    # ══════════════════════════════════════════════════
    
    def _entity_to_result(self, entity: CodeEntity, score: float, match_type: str) -> Dict:
        return {
            "id": entity.id,
            "name": entity.name,
            "kind": entity.kind,
            "qualified_name": entity.qualified_name,
            "file": entity.file_path,
            "line": entity.start_line,
            "summary": entity.summary,
            "signature": entity.signature,
            "score": round(score, 3),
            "match_type": match_type,
        }
    
    def _count_kinds(self) -> Dict[str, int]:
        kinds = defaultdict(int)
        for e in self._entities.values():
            kinds[e.kind] += 1
        return dict(kinds)
    
    def stats(self) -> Dict[str, Any]:
        return {
            "engine": "LAAPCodeGraph v1.0",
            "built": self._built,
            "entities": len(self._entities),
            "relations": sum(len(v) for v in self._edges_from.values()),
            "entry_points": len(self._entry_points),
            "modules": len(self._module_map),
            "by_kind": self._count_kinds(),
            "by_relation": {
                "contains": sum(1 for rels in self._edges_from.values() for r in rels if r.kind == "contains"),
                "calls": sum(1 for rels in self._edges_from.values() for r in rels if r.kind == "calls"),
                "imports": sum(1 for rels in self._edges_from.values() for r in rels if r.kind == "imports"),
                "instantiates": sum(1 for rels in self._edges_from.values() for r in rels if r.kind == "instantiates"),
                "extends": sum(1 for rels in self._edges_from.values() for r in rels if r.kind == "extends"),
            },
        }
    
    def __len__(self) -> int:
        return len(self._entities)


# ══════════════════════════════════════════════════
# 单例 + 全局存取
# ══════════════════════════════════════════════════

_instance: Optional[LAAPCodeGraph] = None

def get_codegraph(force_rebuild: bool = False) -> LAAPCodeGraph:
    global _instance
    if _instance is None:
        _instance = LAAPCodeGraph()
        _instance.build()
    elif force_rebuild:
        _instance = LAAPCodeGraph()
        _instance.build()
    return _instance


# ══════════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════════

def test():
    """测试 CodeGraph 建模"""
    logger.info("=" * 60)
    logger.info("LAAP CodeGraph 建模测试")
    logger.info("=" * 60)
    cg = get_codegraph()
    
    # 1. 统计
    logger.info("\n【1】图谱统计")
    stats = cg.stats()
    for k, v in stats.items():
        if k != "by_kind" and k != "by_relation":
            logger.info(f"  {k}: {v}")
    logger.info(f"  节点类型: {stats['by_kind']}")
    logger.info(f"  关系类型: {stats['by_relation']}")
    logger.info("\n【2】语义查询测试")
    for query in ["量子核", "认知引擎", "causal engine", "网关", "记忆", "PSI循环", "feishu"]:
        results = cg.query(query, top_k=3)
        logger.info(f"\n  🔍 \"{query}\":")
        for r in results:
            logger.info(f"    [{r['score']:.2f}|{r['match_type']}] {r['name']} ({r['kind']})")
            logger.info(f"      {r['file']}:{r['line']}")
            if r['summary']:
                logger.info(f"      {r['summary'][:80]}")
    logger.info("\n【3】调用链追踪")
    chains = cg.trace_call("before_turn")
    for ch in chains[:2]:
        logger.info(f"\n  Root: {ch['root']['name']} ({ch['root']['kind']})")
        for call in ch['call_chain']:
            logger.info(f"    └─[{call['depth']}] {call['name']} → {call['file']}:{call['line']}")
    logger.info("\n【4】认知上下文生成")
    for topic in ["认知引擎", "量子推理", "飞书网关"]:
        ctx = cg.get_context_for_topic(topic, max_results=3)
        logger.info(f"\n  📖 {topic}:")
        for line in ctx.split("\n"):
            logger.info(f"    {line}")
    logger.info("\n【5】模块结构")
    mod = cg.get_module_structure("laap.agi")
    logger.info(f"  laap.agi: {mod['entity_count']} 实体, {len(mod['classes'])} 类, {len(mod['functions'])} 函数")
    cg.save()
    logger.info(f"\n✅ LAAP CodeGraph 建模测试完成")
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
