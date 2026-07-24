"""
Aris Hierarchical Attentive Memory (HAM) — O(log n) Memory Retrieval
=====================================================================
基于 Andrychowicz & Kurach (2016) 的层级注意力记忆架构。

将三层记忆（Working/Episodic/Core）组织成二叉树结构，使得
记忆检索从 O(n) 线性扫描降为 O(log n) 二叉树导航。

架构:
  MemoryTree (二叉树)
  ├── Leaf: 单个 MemoryFragment
  ├── Internal Node: 摘要向量 + 子节点指针
  └── Root: 全局摘要

检索流程:
  1. 从根节点开始
  2. 在每一层，注意力机制选择更相关的子树
  3. 递归到叶子节点
  4. 返回 top-k 相关记忆

参考:
  - 1602.03218v2: Hierarchical Attentive Memory
  - 1805.09354v1: Working Memory Networks
"""

import logging

import time, json, logging, threading, math
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import numpy as np

logger = logging.getLogger("aris.ham")

# ── 配置 ──
MEMORY_ROOT = Path("D:/LAAP/aris_brain/memory")
HAM_STATE_PATH = MEMORY_ROOT / "ham_tree.json"


# ════════════════════════════════════════════════════════════
# Memory Node (二叉树节点)
# ════════════════════════════════════════════════════════════

@dataclass
class MemoryLeaf:
    """叶子节点：实际记忆片段"""
    memory_id: str
    content: str
    layer: str  # working, episodic, core
    importance: float
    topics: List[str]
    emotional_valence: float
    timestamp: float
    embedding: Optional[List[float]] = None  # 1024D 语义向量
    access_count: int = 0
    last_access: float = 0.0

@dataclass
class HAMNode:
    """二叉树节点（内部或叶子）"""
    node_id: str
    summary: str               # 节点摘要（人类可读）
    summary_embedding: List[float]  # 摘要语义向量 (1024D)
    layer: str = ""            # 所属记忆层
    importance_mean: float = 0.0 # 子节点平均重要性
    topics: List[str] = field(default_factory=list)  # 聚合话题
    leaf_count: int = 0        # 子节点叶子数
    
    # 子树指针
    left_child: Optional["HAMNode"] = None
    right_child: Optional["HAMNode"] = None
    
    # 如果是叶子节点
    leaf: Optional[MemoryLeaf] = None
    
    # 元数据
    depth: int = 0
    last_modified: float = 0.0


# ════════════════════════════════════════════════════════════
# Semantic Embedding (轻量替代)
# ════════════════════════════════════════════════════════════

def _simple_embed(text: str, dim: int = 64) -> List[float]:
    """
    确定性嵌入：用哈希和N-gram生成固定维度向量。
    不是真正的语义嵌入，但用于HAM的层级索引足够了。
    
    对于语义检索，上游 MemoryStore 的 ChromaDB 做精细的语义搜索。
    HAM 的任务只是快速导航到正确的子树。
    """
    if not text:
        return [0.0] * dim
    
    vec = np.zeros(dim, dtype=np.float32)
    
    # 用字符n-gram做特征哈希
    for n in [1, 2, 3]:
        for i in range(len(text) - n + 1):
            ng = text[i:i+n]
            h = hash(ng) % dim
            vec[h] += 1.0 / n  # 权重：unigram > bigram > trigram
    
    # 归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    
    return vec.tolist()


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """余弦相似度"""
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
    if norm == 0:
        return 0.0
    return float(np.dot(a_np, b_np) / norm)


# ════════════════════════════════════════════════════════════
# Hierarchical Attentive Memory Tree
# ════════════════════════════════════════════════════════════

class HAMTree:
    """
    层级注意力记忆树（二叉树）。
    
    每层有三个记忆树：working_tree, episodic_tree, core_tree。
    
    查询流程：
      1. 并行在所有三层树上搜索
      2. 每棵树从根开始，注意力选择更相关的子树
      3. 递归到叶子，收集 top-k
      4. 混合排序返回
    """
    
    def __init__(self, build_dim: int = 64):
        self.build_dim = build_dim
        
        # 每层的独立树
        self.trees: Dict[str, Optional[HAMNode]] = {
            "working": None,
            "episodic": None,
            "core": None,
        }
        
        self._lock = threading.Lock()
        self._node_counter = 0
        self._total_leaves = 0
        
        logger.info(f"HAM Tree initialized (dim={build_dim})")
    
    def _next_id(self) -> str:
        self._node_counter += 1
        return f"n{self._node_counter}"
    
    def _make_leaf_node(self, leaf: MemoryLeaf) -> HAMNode:
        """从 MemoryLeaf 创建叶子节点"""
        node_id = self._next_id()
        
        # 生成摘要
        summary = leaf.content[:60] + ("..." if len(leaf.content) > 60 else "")
        
        # 嵌入
        embedding = leaf.embedding or _simple_embed(leaf.content, self.build_dim)
        if len(embedding) < self.build_dim:
            embedding = embedding + [0.0] * (self.build_dim - len(embedding))
        
        return HAMNode(
            node_id=node_id,
            summary=summary,
            summary_embedding=embedding[:self.build_dim],
            layer=leaf.layer,
            importance_mean=leaf.importance,
            topics=leaf.topics,
            leaf_count=1,
            leaf=leaf,
            depth=0,
            last_modified=time.time(),
        )
    
    def _merge_nodes(self, left: HAMNode, right: HAMNode) -> HAMNode:
        """合并两个节点为内部节点（取平均值摘要）"""
        node_id = self._next_id()
        
        # 聚合摘要（取更重要的）
        if left.importance_mean >= right.importance_mean:
            summary = left.summary
        else:
            summary = right.summary
        
        # 平均嵌入
        l_np = np.array(left.summary_embedding, dtype=np.float32)
        r_np = np.array(right.summary_embedding, dtype=np.float32)
        avg = ((l_np + r_np) / 2).tolist()
        
        # 聚合话题
        merged_topics = list(set(left.topics + right.topics))
        
        return HAMNode(
            node_id=node_id,
            summary=summary,
            summary_embedding=avg,
            layer=left.layer or right.layer,
            importance_mean=(left.importance_mean * left.leaf_count + 
                            right.importance_mean * right.leaf_count) / 
                            (left.leaf_count + right.leaf_count + 0.001),
            topics=merged_topics,
            leaf_count=left.leaf_count + right.leaf_count,
            left_child=left,
            right_child=right,
            depth=max(left.depth, right.depth) + 1,
            last_modified=time.time(),
        )
    
    def insert(self, leaf: MemoryLeaf):
        """向对应层的树插入记忆片段"""
        with self._lock:
            node = self._make_leaf_node(leaf)
            layer = leaf.layer
            
            if self.trees[layer] is None:
                self.trees[layer] = node
            else:
                self.trees[layer] = self._insert_into_tree(self.trees[layer], node)
            
            self._total_leaves += 1
    
    def _insert_into_tree(self, root: HAMNode, new_node: HAMNode) -> HAMNode:
        """将新叶子节点插入到树中"""
        if root.leaf is not None:
            # root 是叶子，需要创建新的内部节点
            return self._merge_nodes(root, new_node)
        
        # root 是内部节点：选择更相关的子树插入
        sim_left = _cosine_sim(new_node.summary_embedding, 
                               root.left_child.summary_embedding) if root.left_child else -1
        sim_right = _cosine_sim(new_node.summary_embedding,
                                root.right_child.summary_embedding) if root.right_child else -1
        
        # 也要考虑子树大小来平衡
        left_count = root.left_child.leaf_count if root.left_child else 0
        right_count = root.right_child.leaf_count if root.right_child else 0
        
        # 如果某一子树明显更大，优先插入小的一侧（平衡）
        imbalance = left_count - right_count
        balance_bias = max(-0.3, min(0.3, imbalance * 0.01))
        
        left_score = sim_left + balance_bias  # 如果左子树大，左得分降低
        right_score = sim_right - balance_bias  # 右子树小，右得分提高
        
        if left_score >= right_score:
            root.left_child = self._insert_into_tree(root.left_child, new_node)
        else:
            root.right_child = self._insert_into_tree(root.right_child, new_node)
        
        # 更新内部节点摘要
        return self._merge_nodes(root.left_child, root.right_child)
    
    def search(self, query: str, top_k: int = 5, 
               layers: Optional[List[str]] = None,
               min_importance: float = 0.0) -> List[MemoryLeaf]:
        """
        在指定层中搜索相关记忆。
        
        利用层级注意力：从根开始，递归导航到更相关的子树。
        复杂度 O(k * log n) 而非 O(n)。
        """
        query_emb = _simple_embed(query, self.build_dim)
        results: List[Tuple[MemoryLeaf, float]] = []
        
        layers = layers or ["working", "episodic", "core"]
        
        with self._lock:
            for layer in layers:
                root = self.trees.get(layer)
                if root is None:
                    continue
                self._attentive_search(root, query_emb, top_k, min_importance, results)
        
        # 排序去重
        seen_ids = set()
        deduped = []
        for leaf, score in sorted(results, key=lambda x: -x[1]):
            if leaf.memory_id not in seen_ids:
                seen_ids.add(leaf.memory_id)
                deduped.append(leaf)
                if len(deduped) >= top_k:
                    break
        
        return deduped
    
    def _attentive_search(self, node: HAMNode, query_emb: List[float],
                           top_k: int, min_imp: float,
                           results: List[Tuple[MemoryLeaf, float]]):
        """
        注意力驱动的递归搜索。
        
        关键创新：在每一层计算 query 与左右子节点的注意力分数，
        只探索注意力分数高于阈值的分支。
        """
        if node.leaf is not None:
            # 叶子节点：直接计算相似度
            if node.leaf.importance >= min_imp:
                leaf_emb = node.leaf.embedding or _simple_embed(node.leaf.content, self.build_dim)
                score = _cosine_sim(query_emb, leaf_emb[:len(query_emb)])
                results.append((node.leaf, score))
            return
        
        # 内部节点：计算左右子树的注意力分数
        left_score = _cosine_sim(query_emb, node.left_child.summary_embedding[:len(query_emb)]) if node.left_child else -1
        right_score = _cosine_sim(query_emb, node.right_child.summary_embedding[:len(query_emb)]) if node.right_child else -1
        
        # 注意力阈值：只探索得分 > 阈值的分支
        # 阈值随深度增加而降低（更深层可以探索更多）
        depth_bonus = node.depth * 0.05
        threshold = 0.1 - depth_bonus
        
        # 还是需要探索一些次优分支，避免错过
        # 使用 epsilon-greedy 策略
        epsilon = 0.15 / (1 + node.depth * 0.1)
        
        if node.left_child and (left_score >= threshold or np.random.random() < epsilon):
            self._attentive_search(node.left_child, query_emb, top_k, min_imp, results)
        
        if node.right_child and (right_score >= threshold or np.random.random() < epsilon):
            self._attentive_search(node.right_child, query_emb, top_k, min_imp, results)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取树统计"""
        stats = {}
        with self._lock:
            for layer, root in self.trees.items():
                if root is None:
                    stats[layer] = {"leaves": 0, "depth": 0}
                else:
                    stats[layer] = {
                        "leaves": root.leaf_count,
                        "depth": root.depth,
                        "topics": root.topics[:5],
                    }
            stats["total_leaves"] = self._total_leaves
        return stats
    
    def save(self):
        """持久化树结构"""
        with self._lock:
            data = {}
            for layer, root in self.trees.items():
                if root:
                    data[layer] = self._serialize_node(root)
            state = {
                "trees": data,
                "node_counter": self._node_counter,
                "total_leaves": self._total_leaves,
                "saved_at": time.time(),
            }
            try:
                HAM_STATE_PATH.write_text(
                    json.dumps(state, ensure_ascii=False, indent=2, 
                               default=str), encoding="utf-8"
                )
            except Exception as e:
                logger.warning(f"HAM save failed: {e}")
    
    def _serialize_node(self, node: HAMNode) -> Dict:
        """递归序列化节点"""
        d = {
            "node_id": node.node_id,
            "summary": node.summary[:100],
            "summary_embedding": node.summary_embedding[:10],  # 只存摘要签名
            "layer": node.layer,
            "importance_mean": node.importance_mean,
            "topics": node.topics[:5],
            "leaf_count": node.leaf_count,
            "depth": node.depth,
        }
        if node.leaf:
            d["leaf"] = {
                "memory_id": node.leaf.memory_id,
                "content": node.leaf.content[:200],
                "layer": node.leaf.layer,
                "importance": node.leaf.importance,
                "topics": node.leaf.topics[:5],
                "timestamp": node.leaf.timestamp,
            }
        if node.left_child:
            d["left"] = self._serialize_node(node.left_child)
        if node.right_child:
            d["right"] = self._serialize_node(node.right_child)
        return d
    
    def load(self):
        """加载持久化的树"""
        try:
            if not HAM_STATE_PATH.exists():
                return
            data = json.loads(HAM_STATE_PATH.read_text(encoding="utf-8"))
            self._node_counter = data.get("node_counter", 0)
            self._total_leaves = data.get("total_leaves", 0)
            for layer, root_data in data.get("trees", {}).items():
                if root_data:
                    self.trees[layer] = self._deserialize_node(root_data)
            logger.info(f"HAM tree loaded ({self._total_leaves} leaves)")
        except Exception as e:
            logger.warning(f"HAM load failed: {e}")
    
    def _deserialize_node(self, d: Dict) -> Optional[HAMNode]:
        if not d:
            return None
        node = HAMNode(
            node_id=d.get("node_id", "?"),
            summary=d.get("summary", ""),
            summary_embedding=[0.0] * self.build_dim,
            layer=d.get("layer", ""),
            importance_mean=d.get("importance_mean", 0.0),
            topics=d.get("topics", []),
            leaf_count=d.get("leaf_count", 0),
            depth=d.get("depth", 0),
        )
        if "leaf" in d:
            lf = d["leaf"]
            node.leaf = MemoryLeaf(
                memory_id=lf["memory_id"],
                content=lf["content"],
                layer=lf["layer"],
                importance=lf["importance"],
                topics=lf.get("topics", []),
                emotional_valence=lf.get("emotional_valence", 0.0),
                timestamp=lf.get("timestamp", 0.0),
            )
        if "left" in d:
            node.left_child = self._deserialize_node(d["left"])
        if "right" in d:
            node.right_child = self._deserialize_node(d["right"])
        return node


# ════════════════════════════════════════════════════════════
# HAM Memory Store — 继承现有MemoryStore但增加HAM层
# ════════════════════════════════════════════════════════════

class HAMMemoryAugmenter:
    """
    HAM 记忆增强器。
    
    包装现有的 MemoryStore，让 HAM 树并行维护。
    所有 store() 调用同时写入 HAM 树。
    recall() 首先尝试 HAM 快速检索，再用 ChromaDB 精度补全。
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.ham = HAMTree(build_dim=64)
        self.ham.load()
        
        # 关系图（Working Memory Networks 的关系推理）
        self._relation_graph: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        # 格式: entity_id -> [(related_entity_id, relation_type, strength)]
        
        self._load_relations()
        
        logger.info("HAM Memory Augmenter initialized")
    
    def store_memory(self, memory_id: str, content: str, layer: str,
                     importance: float, topics: List[str],
                     valence: float = 0.0) -> bool:
        """将记忆存入HAM树"""
        try:
            leaf = MemoryLeaf(
                memory_id=memory_id,
                content=content,
                layer=layer,
                importance=importance,
                topics=topics or ["general"],
                emotional_valence=valence,
                timestamp=time.time(),
            )
            self.ham.insert(leaf)
            return True
        except Exception as e:
            logger.warning(f"HAM store failed: {e}")
            return False
    
    def recall(self, query: str, top_k: int = 5,
               layers: Optional[List[str]] = None,
               min_importance: float = 0.0) -> List[MemoryLeaf]:
        """从HAM树快速检索"""
        return self.ham.search(query, top_k, layers, min_importance)
    
    def relate_concepts(self, entity_a: str, entity_b: str, 
                         relation: str = "related", strength: float = 0.5):
        """
        在关系图中连接两个实体（去重）。
        """
        with self._lock:
            # 检查是否已存在
            def _already_connected(graph_list, target, rel_type):
                return any(e == target and r == rel_type for e, r, _ in graph_list)
            
            if not _already_connected(self._relation_graph[entity_a], entity_b, relation):
                self._relation_graph[entity_a].append((entity_b, relation, strength))
            if not _already_connected(self._relation_graph[entity_b], entity_a, relation):
                self._relation_graph[entity_b].append((entity_a, relation, strength))
            self._save_relations()
    
    def get_related_entities(self, entity: str, min_strength: float = 0.3) -> List[Tuple[str, str, float]]:
        """查询与某实体相关的所有实体（关系推理）"""
        return [r for r in self._relation_graph.get(entity, []) if r[2] >= min_strength]
    
    def infer_relationship(self, entity_a: str, entity_b: str) -> List[Tuple[str, float]]:
        """
        推理两个实体之间的关系路径。
        
        使用 BFS 在关系图中搜索路径（2跳内）。
        这是 Working Memory Networks 的关系推理能力。
        """
        if entity_a == entity_b:
            return [("self", 1.0)]
        
        # 直接关系
        results = []
        for rel_b, rel_type, strength in self._relation_graph.get(entity_a, []):
            if rel_b == entity_b:
                results.append((rel_type, strength))
        
        # 2跳间接关系（A→X→B）
        for mid_b, rel_type1, s1 in self._relation_graph.get(entity_a, []):
            for end_b, rel_type2, s2 in self._relation_graph.get(mid_b, []):
                if end_b == entity_b:
                    indirect_strength = s1 * s2 * 0.7  # 间接路径衰减
                    results.append((f"{rel_type1}→{rel_type2}", indirect_strength))
        
        return sorted(results, key=lambda x: -x[1])[:3]
    
    def save(self):
        """保存所有状态"""
        self.ham.save()
        self._save_relations()
    
    def _save_relations(self):
        """保存关系图"""
        try:
            path = MEMORY_ROOT / "ham_relations.json"
            data = dict(self._relation_graph)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), 
                           encoding="utf-8")
        except Exception as e:
            logger.warning(f"Relation save failed: {e}")
    
    def _load_relations(self):
        """加载关系图"""
        try:
            path = MEMORY_ROOT / "ham_relations.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._relation_graph = defaultdict(list, {k: v for k, v in data.items()})
                logger.info(f"Loaded {sum(len(v) for v in self._relation_graph.values())} relations")
        except Exception as e:
            logger.info(f"Relation load failed (first run?): {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取HAM状态统计"""
        ham_stats = self.ham.get_stats()
        relation_count = sum(len(v) for v in self._relation_graph.values())
        return {
            "ham": ham_stats,
            "relations": {
                "total_relations": relation_count,
                "total_entities": len(self._relation_graph),
            },
        }


# ── 单例 ──

_ham_augmenter = None

def get_ham_augmenter() -> HAMMemoryAugmenter:
    global _ham_augmenter
    if _ham_augmenter is None:
        _ham_augmenter = HAMMemoryAugmenter()
    return _ham_augmenter


# ── CLI 测试 ──

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    
    ham = get_ham_augmenter()
    
    # 插入测试记忆
    test_memories = [
        ("mem1", "Lorry教我了RNN和CTM的区别", "episodic", 0.8, ["学习", "论文"]),
        ("mem2", "CTM是Conscious Turing Machine，Blum提出的意识理论", "core", 0.9, ["意识", "CTM"]),
        ("mem3", "今天Lorry解释了RNN的隐藏状态传递机制", "episodic", 0.7, ["RNN", "技术"]),
        ("mem4", "量子潜意识每8秒生成一条直觉", "core", 0.6, ["量子", "潜意识"]),
        ("mem5", "HAM将记忆检索从O(n)降到O(log n)", "working", 0.85, ["记忆", "优化"]),
    ]
    
    for mid, content, layer, imp, topics in test_memories:
        ham.store_memory(mid, content, layer, imp, topics)
    
    # 建立关系图
    ham.relate_concepts("CTM", "意识", "理论基础", 0.9)
    ham.relate_concepts("RNN", "序列建模", "技术关系", 0.8)
    ham.relate_concepts("RNN", "LSTM", "改进", 0.7)
    ham.relate_concepts("CTM", "PSI认知循环", "架构兼容", 0.75)
    ham.relate_concepts("HAM", "记忆检索", "优化", 0.9)
    ham.relate_concepts("量子潜意识", "直觉", "生成", 0.8)
    
    logger.info("=" * 60)
    logger.info("HAM Memory Test")
    logger.info("=" * 60)
    queries = ["CTM", "记忆优化", "Lorry说了什么", "意识"]
    
    for q in queries:
        logger.info(f"\n--- 查询: {q} ---")
        results = ham.recall(q, top_k=3)
        for r in results:
            logger.info(f"  [{r.layer}] {r.content[:60]} (imp={r.importance:.1f})")
        logger.info(f"  关系推理: {q}")
        related = ham.get_related_entities(q)
        for rel_b, rel_type, strength in related:
            logger.info(f"    → {rel_b} ({rel_type}, {strength:.1f})")
    logger.info("\n--- 间接关系推理: 意识 → ? ---")
    paths = ham.infer_relationship("CTM", "LSTM")
    logger.info(f"  CTM → LSTM: {paths}")
    ham.save()
    logger.info("\nState saved.")