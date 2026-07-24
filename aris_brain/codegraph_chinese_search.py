"""
CodeGraph Chinese Search Optimizer — 中文搜索优化
=================================================
CodeGraph FTS5 用英文分词，中文查不到。解决方案：

1. 中→英术语映射表
2. 双语查询扩展 (中文 → 扩展出英文同义词)
3. 中文拼音匹配 (如果有)
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, re, json, sqlite3

_DIR = os.path.dirname(os.path.abspath(__file__))
_CG_PATH = os.path.join(_DIR, ".codegraph", "codegraph.db")

# 核心代码库的中→英术语映射
CN_TO_EN_MAP = {
    "量子核": ["quantum kernel", "quantum", "UN6", "kernel"],
    "量子": ["quantum", "QuantumKernel", "quantum_psi"],
    "认知引擎": ["cognitive engine", "cognitive_engine", "cognitive"],
    "认知": ["cognitive", "cognition", "CognitiveCycle", "CognitiveEngine"],
    "段落合成": ["paragraph", "synthesizer", "synthesize", "paragraph_synthesizer"],
    "推理": ["reason", "reasoning", "reasoner", "inference"],
    "语义": ["semantic", "semantics", "SemanticEncoder", "semantic_engine"],
    "编码器": ["encoder", "encode", "Encoder", "v7_encoder"],
    "马尔科夫": ["markov", "markov chain", "MarkovChain", "markov_generator"],
    "谐振": ["resonator", "resonate", "PsiResonator", "resonance"],
    "记忆": ["memory", "MemoryStore", "memory_store", "memory_hook"],
    "知识库": ["knowledge", "Knowledge", "knowledge_base", "matrix_knowledge"],
    "知识": ["knowledge", "kb", "knowledge_retriever"],
    "管线": ["pipeline", "pipe", "Pipeline"],
    "融合": ["fusion", "fuse", "FusionEngine", "fusion_synthesizer"],
    "解码": ["decode", "decoder", "Decoder", "vqvae_decoder"],
    "代码": ["code", "codebase", "CodeGraph"],
    "注意力": ["attention", "Attention", "semantic_attention"],
    "需求": ["needs", "Needs", "SemanticNeeds", "need"],
    "情感": ["emotion", "Emotion", "emotional", "emotional_engine"],
    "内省": ["introspect", "metacogni", "introspection", "Meta"],
    "PSI": ["psi", "PSI", "QuantumPSI", "psi_"],
    "UN6": ["un6", "UN6", "aris_lm_v10_un6"],
    "V12": ["v12", "V12", "aris_v12"],
    "V7": ["v7", "V7", "v7_encoder"],
}

def expand_query_cn(query: str) -> str:
    """中文查询 → 扩展英文查询"""
    parts = [query]
    
    for cn_term, en_terms in CN_TO_EN_MAP.items():
        if cn_term in query:
            parts.append(" ".join(en_terms))
    
    return " OR ".join(parts)


class CodeGraphChinese:
    """带中文搜索优化的 CodeGraph 浏览器"""
    
    def __init__(self, db_path: str = _CG_PATH):
        self._db_path = db_path
        self._conn = None
    
    def _ensure(self):
        if self._conn is None:
            if not os.path.exists(self._db_path):
                return False
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return True
    
    def search_cn(self, query: str, limit: int = 10) -> list:
        """中文优化搜索"""
        if not self._ensure():
            return []
        
        expanded = expand_query_cn(query)
        c = self._conn.cursor()
        results = []
        
        # 尝试 FTS5 搜索
        try:
            c.execute("""
                SELECT n.id, n.kind, n.name, n.qualified_name, n.file_path,
                       n.start_line, n.docstring, n.signature
                FROM nodes_fts f JOIN nodes n ON f.rowid = n.rowid
                WHERE nodes_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (expanded, limit))
            for row in c.fetchall():
                results.append(dict(row))
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        if not results:
            en_terms = []
            for cn_term, en_list in CN_TO_EN_MAP.items():
                if cn_term in query:
                    en_terms.extend(en_list)
            
            for term in en_terms[:5]:
                like_pattern = f"%{term}%"
                c.execute("""
                    SELECT id, kind, name, file_path, start_line, docstring, signature
                    FROM nodes
                    WHERE name LIKE ? OR qualified_name LIKE ? OR docstring LIKE ?
                    LIMIT 5
                """, (like_pattern, like_pattern, like_pattern))
                for row in c.fetchall():
                    d = dict(row)
                    if d['id'] not in [r.get('id') for r in results]:
                        results.append(d)
        
        return results[:limit]
    
    def extract_knowledge_cn(self, query: str, top_k: int = 5) -> list:
        """中文搜索 → 提取知识片段"""
        nodes = self.search_cn(query, limit=top_k * 2)
        knowledge = []
        seen = set()
        
        for n in nodes:
            nid = n.get('id', '')
            if nid in seen:
                continue
            seen.add(nid)
            
            kind = n.get('kind', '')
            name = n.get('name', '')
            doc = n.get('docstring', '') or ''
            fp = n.get('file_path', '')
            sig = n.get('signature', '') or ''
            
            parts = []
            if kind == 'function':
                parts.append(f"函数 {name}")
                if sig: parts.append(f"签名: {sig}")
                if doc: parts.append(f"文档: {doc[:200]}")
            elif kind == 'class':
                parts.append(f"类 {name}")
                if doc: parts.append(f"文档: {doc[:200]}")
            else:
                if doc:
                    parts.append(f"{name}: {doc[:200]}")
            
            if parts:
                knowledge.append({
                    'code_entity': name,
                    'kind': kind,
                    'text': '。'.join(parts),
                    'file': fp,
                })
                if len(knowledge) >= top_k:
                    break
        
        return knowledge


if __name__ == "__main__":
    cg = CodeGraphChinese()
    
    tests = ["量子核", "认知引擎", "段落合成", "语义编码器", "记忆系统"]
    for q in tests:
        results = cg.search_cn(q, limit=3)
        kn = cg.extract_knowledge_cn(q, top_k=2)
        logger.info(f"\n搜索 [{q}]: {len(results)}个代码实体, {len(kn)}条知识")
        for k in kn[:1]:
            logger.info(f"  [{k['kind']:10s}] {k['code_entity'][:30]:30s} {k['text'][:80]}")