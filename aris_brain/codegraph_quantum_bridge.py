"""
Quantum CodeGraph Bridge — 代码图谱接入量子推理引擎
=====================================================
把 CodeGraph (8027节点/16416边) 的精确定义接入推理管线。

之前的问题: MatrixKnowledge 用语义相似度搜代码 —— 不精确。
CodeGraph 的优势: 直接知道"这个函数调用了哪个模块"、"这个类继承自什么"。

接入方式:
  1. CodeGraph FTS5 全文搜索 → 找到精确的代码实体
  2. 图谱遍历 → 沿关系发现相关代码
  3. 提取 docstring + signature → 作为推理上下文
  4. 与量子轨迹DB结合 → 代码理解进入推理管线
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, sqlite3, json, time, re
import numpy as np
from typing import Dict, List, Optional, Set

_DIR = os.path.dirname(os.path.abspath(__file__))
_CG_PATH = os.path.join(_DIR, ".codegraph", "codegraph.db")


class CodeGraphExplorer:
    """CodeGraph 代码图谱浏览器"""

    def __init__(self, db_path: str = _CG_PATH):
        self._db_path = db_path
        self._conn = None
        self._node_cache = {}
        self._stats = None

    def _ensure(self):
        if self._conn is None:
            if not os.path.exists(self._db_path):
                raise FileNotFoundError(f"CodeGraph DB not found: {self._db_path}")
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row

    def stats(self) -> Dict:
        if self._stats:
            return self._stats
        self._ensure()
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM nodes")
        n_nodes = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM edges")
        n_edges = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM files")
        n_files = c.fetchone()[0]
        self._stats = {"nodes": n_nodes, "edges": n_edges, "files": n_files}
        return self._stats

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        FTS5 全文搜索代码实体

        用法: search("quantum kernel") → 找到所有包含 quantum 和 kernel 的代码实体
        """
        self._ensure()
        c = self._conn.cursor()

        # FTS5 搜索
        try:
            c.execute("""
                SELECT n.id, n.kind, n.name, n.qualified_name, n.file_path,
                       n.start_line, n.end_line, n.signature, n.docstring,
                       n.is_exported, n.is_async, n.visibility
                FROM nodes_fts f
                JOIN nodes n ON f.rowid = n.rowid
                WHERE nodes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
        except:
            # 回退到 LIKE 搜索
            search_term = f"%{query.replace(' ', '%')}%"
            c.execute("""
                SELECT id, kind, name, qualified_name, file_path,
                       start_line, end_line, signature, docstring
                FROM nodes
                WHERE name LIKE ? OR qualified_name LIKE ? OR docstring LIKE ?
                LIMIT ?
            """, (search_term, search_term, search_term, limit))

        results = []
        for row in c.fetchall():
            results.append(dict(row))
        return results

    def get_node(self, node_id: str) -> Optional[Dict]:
        """获取单个节点详情"""
        if node_id in self._node_cache:
            return self._node_cache[node_id]
        self._ensure()
        c = self._conn.cursor()
        c.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
        row = c.fetchone()
        if row:
            d = dict(row)
            self._node_cache[node_id] = d
            return d
        return None

    def get_neighbors(self, node_id: str, edge_kinds: List[str] = None,
                      direction: str = "both", limit: int = 20) -> List[Dict]:
        """
        获取邻居节点

        Args:
            node_id: 起始节点
            edge_kinds: 边类型过滤 (None=全部)
            direction: "out"(出边), "in"(入边), "both"
        """
        self._ensure()
        c = self._conn.cursor()

        neighbors = []

        if direction in ("out", "both"):
            if edge_kinds:
                placeholders = ",".join("?" * len(edge_kinds))
                query = f"""
                    SELECT e.kind as edge_kind, n.*
                    FROM edges e JOIN nodes n ON e.target = n.id
                    WHERE e.source = ? AND e.kind IN ({placeholders})
                    LIMIT ?
                """
                c.execute(query, [node_id] + edge_kinds + [limit])
            else:
                c.execute("""
                    SELECT e.kind as edge_kind, n.*
                    FROM edges e JOIN nodes n ON e.target = n.id
                    WHERE e.source = ?
                    LIMIT ?
                """, (node_id, limit))

            for row in c.fetchall():
                d = dict(row)
                d["direction"] = "out"
                neighbors.append(d)

        if direction in ("in", "both"):
            if edge_kinds:
                placeholders = ",".join("?" * len(edge_kinds))
                query = f"""
                    SELECT e.kind as edge_kind, n.*
                    FROM edges e JOIN nodes n ON e.source = n.id
                    WHERE e.target = ? AND e.kind IN ({placeholders})
                    LIMIT ?
                """
                c.execute(query, [node_id] + edge_kinds + [limit])
            else:
                c.execute("""
                    SELECT e.kind as edge_kind, n.*
                    FROM edges e JOIN nodes n ON e.source = n.id
                    WHERE e.target = ?
                    LIMIT ?
                """, (node_id, limit))

            for row in c.fetchall():
                d = dict(row)
                d["direction"] = "in"
                neighbors.append(d)

        return neighbors

    def explore_path(self, start_id: str, max_hops: int = 3,
                     target_kind: str = None) -> List[Dict]:
        """
        从起点沿图谱探索推理路径

        Args:
            start_id: 起始节点
            max_hops: 最大跳数
            target_kind: 目标节点类型 (None=全部)

        Returns:
            路径: [{"hop": 0, "node": {...}}, ...]
        """
        self._ensure()
        visited = {start_id}
        path = []
        current = {start_id}

        for hop in range(max_hops + 1):
            next_set = set()
            batch_nodes = []

            for nid in current:
                node = self.get_node(nid)
                if node:
                    if target_kind is None or node.get("kind") == target_kind:
                        batch_nodes.append({"hop": hop, "node": node, "node_id": nid})

                neighbors = self.get_neighbors(nid, limit=10)
                for nb in neighbors:
                    nb_id = nb.get("id")
                    if nb_id and nb_id not in visited:
                        if target_kind is None or nb.get("kind") == target_kind:
                            batch_nodes.append({"hop": hop + 1, "node": nb, "node_id": nb_id,
                                                "edge": nb.get("edge_kind")})
                        next_set.add(nb_id)
                        visited.add(nb_id)

            path.extend(batch_nodes)
            current = next_set

        return path

    def extract_knowledge(self, query: str) -> List[Dict]:
        """
        从 CodeGraph 提取结构化知识片段

        用法: extract_knowledge("quantum kernel")
        → [{定义, 签名, 所在文件, 调用关系}]
        """
        results = self.search(query, limit=8)
        knowledge = []

        for r in results:
            node_id = r.get("id", "")
            kind = r.get("kind", "")
            name = r.get("name", "")
            qname = r.get("qualified_name", "")
            sig = r.get("signature", "") or ""
            doc = r.get("docstring", "") or ""
            fp = r.get("file_path", "")

            # 构建知识片段
            parts = []

            if kind == "function":
                parts.append(f"函数 {name} 定义于 {fp}")
                if sig:
                    parts.append(f"签名: {sig}")
                if doc:
                    parts.append(f"文档: {doc[:200]}")

            elif kind == "class":
                parts.append(f"类 {name} 定义于 {fp}")
                if doc:
                    parts.append(f"文档: {doc[:200]}")
                # 找方法
                methods = self.get_neighbors(node_id, edge_kinds=["contains"],
                                             direction="out", limit=5)
                method_names = [m.get("name") for m in methods if m.get("kind") == "function"]
                if method_names:
                    parts.append(f"方法: {', '.join(method_names[:8])}")

            elif kind == "module":
                parts.append(f"模块 {name} ({fp})")
                # 找导出
                exported = self.get_neighbors(node_id, direction="out", limit=8)
                exports = [m.get("name") for m in exported if m.get("is_exported")]
                if exports:
                    parts.append(f"导出: {', '.join(exports[:6])}")

            elif kind == "file":
                # 找文件里的重要定义
                imports = self.get_neighbors(node_id, edge_kinds=["contains"],
                                             direction="out", limit=5)
                imp_names = [m.get("name") for m in imports if m.get("kind") == "import"]
                if imp_names:
                    parts.append(f"导入: {', '.join(imp_names[:5])}")

            if parts:
                knowledge.append({
                    "code_entity": qname or name,
                    "kind": kind,
                    "text": "。".join(parts),
                    "file": fp,
                    "line": r.get("start_line"),
                })

        return knowledge


# ================================================================
# CodeGraph + 量子推理 集成桥
# ================================================================

class CodeGraphReasoner:
    """
    CodeGraph 推理桥 — 把代码图谱接入量子推理管线

    流程:
      问题 → FTS5搜索找到代码实体 → 沿图谱探索关系
           → 提取结构化知识 → 编码为量子态 → 与轨迹DB融合
    """

    def __init__(self):
        self._cg = None
        self._encoder = None
        self._traj_db = None

    def _lazy(self):
        if self._cg is None:
            self._cg = CodeGraphExplorer()
        if self._encoder is None:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)
        if self._traj_db is None:
            from quantum_trajectory_db import QuantumTrajectoryDB
            self._traj_db = QuantumTrajectoryDB()
            import numpy as np
            traj_path = os.path.join(_DIR, "state", "quantum_trajectories.npz")
            if os.path.exists(traj_path):
                data = np.load(traj_path, allow_pickle=True)
                self._traj_db._start_states = data["start_states"]
                self._traj_db._end_states = data["end_states"]
                self._traj_db._loaded = True
                idx_path = os.path.join(_DIR, "state", "trajectory_index.json")
                with open(idx_path, 'r', encoding='utf-8') as f:
                    idx_data = json.load(f)
                self._traj_db._trajectories = []
                for item in idx_data:
                    self._traj_db._trajectories.append({
                        "id": item["id"], "question": item["question"],
                        "answer": item.get("answer", ""), "concept": item["concept"],
                        "source": item["source"], "steps": item.get("steps", 5),
                    })

    def reason_about_code(self, question: str, max_chars: int = 2000) -> Dict:
        """
        量子推理 + CodeGraph 图谱遍历

        Args:
            question: 关于代码的问题 (如 "aris_lm_v10的量子核怎么调用")

        Returns:
            推理结果
        """
        t0 = time.time()
        self._lazy()

        # 1. CodeGraph FTS5 搜索
        cg_knowledge = self._cg.extract_knowledge(question)

        # 2. 对找到的核心代码实体，做图谱探索
        for ck in cg_knowledge[:3]:
            entity_name = ck.get("code_entity", "")
            if entity_name:
                # 查找节点
                nodes = self._cg.search(entity_name, limit=1)
                if nodes:
                    path = self._cg.explore_path(nodes[0]["id"], max_hops=2)
                    # 提取路径上的关键节点
                    for p in path[:5]:
                        n = p["node"]
                        if n.get("kind") == "function" and n.get("docstring"):
                            cg_knowledge.append({
                                "code_entity": n.get("name", ""),
                                "kind": n.get("kind", ""),
                                "text": f"函数 {n.get('name')}: {n.get('docstring','')[:150]}",
                                "file": n.get("file_path", ""),
                            })

        # 3. 量子轨迹检索
        traj_results = self._traj_db.search(question, top_k=1) if self._traj_db._loaded else []

        # 4. 合成回答
        sections = []

        sections.append(f"## CodeGraph 代码分析: {question}\n")

        if cg_knowledge:
            sections.append(f"### 找到 {len(cg_knowledge)} 个相关代码实体\n")
            for i, ck in enumerate(cg_knowledge[:8]):
                kind_icon = {"function": "🔧", "class": "📦", "module": "📁",
                             "file": "📄", "import": "📥"}.get(ck["kind"], "•")
                sections.append(f"{kind_icon} **{ck['code_entity']}** ({ck['kind']})")
                sections.append(f"  {ck['text'][:200]}")
                if ck.get("file"):
                    sections.append(f"  📍 {ck['file']}")
                sections.append("")

        if traj_results:
            best = traj_results[0]
            sections.append(f"### 相关推理轨迹: [{best['concept']}] (匹配{best['match_score']:.2f})\n")
            sections.append(f"  {best['question']}")

        total_ms = (time.time() - t0) * 1000

        return {
            "output": "\n".join(sections),
            "code_entities": len(cg_knowledge),
            "trajectory_match": len(traj_results) > 0,
            "latency_ms": round(total_ms, 1),
            "stats": self._cg.stats() if self._cg else {},
        }


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  CodeGraph + Quantum Reasoning Bridge 自测")
    logger.info("=" * 60)
    cg = CodeGraphExplorer()
    stats = cg.stats()
    logger.info(f"\n  CodeGraph: {stats['nodes']}节点, {stats['edges']}边, {stats['files']}文件")
    logger.info("\n=== FTS5 搜索 ===")
    for q in ["quantum kernel", "cognitive engine", "psi", "resonator", "memory"]:
        results = cg.search(q, limit=3)
        logger.info(f"\n  搜索 [{q}]: {len(results)}结果")
        for r in results[:2]:
            logger.info(f"    [{r['kind']:10s}] {r['name'][:40]:40s}  {r['file_path'][:50]}")
    logger.info("\n=== CodeGraph推理 ===")
    reasoner = CodeGraphReasoner()
    tests = [
        "quantum kernel是怎么实现的？",
        "cognitive engine的认知循环包含哪些组件？",
        "PSI需求系统的代码在哪里定义？",
    ]
    for q in tests[:2]:
        r = reasoner.reason_about_code(q, 1000)
        logger.info(f"\n  问题: {q}")
        logger.info(f"  找到: {r['code_entities']}个代码实体, {r['latency_ms']}ms")
        for line in r['output'].split('\n')[:10]:
            if line.strip():
                logger.info(f"    {line[:100]}")