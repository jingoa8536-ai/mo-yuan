"""
Knowledge Base Expander — 知识库扩充器
=======================================
从 1259 条 → 目标 10 万+ 条

数据来源:
  1. LAAP全代码库 (3508 .py文件, 663053行) → 按函数/类/段落分块
  2. LAAP设计文档 (所有 .md 文件) → 按段落分块
  3. 论文语料 (43篇 + 可扩展) → 按摘要+方法分块
  4. CodeGraph 提取 (8027节点) → 代码实体知识

分块策略:
  - 代码: 每个函数/类定义 = 一个知识条目 (含 docstring + 签名 + 文件路径)
  - 文档: 每个段落 (以 ## 或空行分隔) = 一个知识条目
  - 论文: 每个摘要 + 方法段落 = 一个知识条目
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, re, time, json, glob
import numpy as np
from pathlib import Path
from write_utils import atomic_write_json

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class KnowledgeBaseExpander:
    """知识库批量扩充器"""

    def __init__(self):
        self._entries = []
        self._seen_hashes = set()

    def _hash(self, text: str) -> str:
        return hashlib.md5(text[:100].encode()).hexdigest()[:16]

    def _add(self, text: str, source: str = "", meta: dict = None):
        """去重添加"""
        h = self._hash(text)
        if h in self._seen_hashes or len(text) < 20:
            return
        self._seen_hashes.add(h)
        self._entries.append({
            "text": text[:500],
            "source": source,
            "meta": meta or {},
        })

    def ingest_python_files(self, root_dir: str, max_per_file: int = 20):
        """从 Python 源码提取知识"""
        total = 0
        py_files = glob.glob(os.path.join(root_dir, "**", "*.py"), recursive=True)
        logger.info(f"  扫描 Python: {len(py_files)} 文件...")
        for fp in py_files:
            try:
                lines = open(fp, 'r', encoding='utf-8', errors='ignore').readlines()
            except:
                continue

            rel_path = os.path.relpath(fp, root_dir)
            entries_from_file = 0
            current_class = ""
            current_func = ""
            current_doc = ""
            in_docstring = False

            for i, line in enumerate(lines):
                s = line.strip()
                if not s:
                    continue

                # 找函数定义
                m_func = re.match(r'def\s+(\w+)\s*\(', s)
                if m_func:
                    func_name = m_func.group(1)
                    current_func = f"{current_class}.{func_name}" if current_class else func_name
                    current_doc = ""
                    in_docstring = True
                    continue

                # 找类定义
                m_cls = re.match(r'class\s+(\w+)', s)
                if m_cls:
                    current_class = m_cls.group(1)
                    current_func = ""
                    current_doc = ""
                    in_docstring = True
                    continue

                # 收集 docstring
                if in_docstring:
                    if '"""' in s or "'''" in s:
                        in_docstring = False
                        if current_doc and current_func:
                            entry = f"{current_func}: {current_doc[:300]}。文件: {rel_path}"
                            self._add(entry, rel_path,
                                     {"type": "function", "name": current_func, "line": i+1})
                            entries_from_file += 1
                        elif current_doc and current_class and not current_func:
                            entry = f"类 {current_class}: {current_doc[:300]}。文件: {rel_path}"
                            self._add(entry, rel_path,
                                     {"type": "class", "name": current_class, "line": i+1})
                            entries_from_file += 1
                        current_doc = ""
                    else:
                        current_doc += " " + s.strip(' "\'')

                if entries_from_file >= max_per_file:
                    break

            total += entries_from_file

        logger.info(f"  代码知识: {total} 条")
    def ingest_markdown_files(self, root_dir: str):
        """从 Markdown 文档提取知识"""
        total = 0
        md_files = glob.glob(os.path.join(root_dir, "**", "*.md"), recursive=True)
        # 排除 node_modules
        md_files = [f for f in md_files if 'node_modules' not in f and '__pycache__' not in f]
        logger.info(f"  扫描 Markdown: {len(md_files)} 文件...")
        for fp in md_files:
            try:
                content = open(fp, 'r', encoding='utf-8', errors='ignore').read()
            except:
                continue

            rel_path = os.path.relpath(fp, root_dir)

            # 按段落分块 (## 或 两个换行)
            paragraphs = re.split(r'\n\s*\n', content)
            for para in paragraphs:
                para = para.strip()
                if len(para) < 30 or para.startswith('```'):
                    continue
                # 跳过目录/链接
                if re.match(r'^[\s#*-]*(目录|Table|Contents)', para):
                    continue
                # 跳过纯链接列表
                link_count = len(re.findall(r'\[.*?\]\(.*?\)', para))
                if link_count > 5:
                    continue

                # 清洗 Markdown 语法
                clean = re.sub(r'#{1,6}\s*', '', para)
                clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
                clean = re.sub(r'[*_~`]{1,3}', '', clean)
                clean = re.sub(r'\|.*?\|', '', clean)  # 简化表格
                clean = clean.strip()

                if len(clean) > 30:
                    self._add(clean[:400], rel_path, {"type": "document"})
                    total += 1

        logger.info(f"  文档知识: {total} 条")
    def ingest_paper_corpus(self):
        """从论文语料提取知识"""
        cfg_file = os.path.join(_DIR, "corpus", "papers", "paper_cache.json")
        if not os.path.exists(cfg_file):
            logger.info("  论文: 未找到缓存")
            return

        with open(cfg_file, 'r', encoding='utf-8') as f:
            papers = json.load(f)

        total = 0
        for paper in papers:
            title = paper.get("title", "")[:200]
            summary = paper.get("summary", "")[:500]
            aid = paper.get("arxiv_id", "")
            authors = ", ".join(paper.get("authors", [])[:2])

            if title and len(title) > 10:
                self._add(f"论文 {aid}: {title}。{summary[:300]}",
                         aid, {"type": "paper", "title": title, "authors": authors})
                total += 1

            # 分句添加
            sentences = re.split(r'(?<=[。.])\s*', summary)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) > 40:
                    self._add(sent, aid, {"type": "paper_sentence", "title": title})
                    total += 1

        logger.info(f"  论文知识: {total} 条")
    def ingest_codegraph(self):
        """从 CodeGraph 提取代码实体知识"""
        cg_path = os.path.join(_DIR, ".codegraph", "codegraph.db")
        if not os.path.exists(cg_path):
            logger.info("  CodeGraph: 未找到")
            return

        import sqlite3
        conn = sqlite3.connect(cg_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # 提取有 docstring 的函数和类
        c.execute("""
            SELECT kind, name, qualified_name, file_path, docstring, signature
            FROM nodes
            WHERE kind IN ('function', 'class', 'module')
              AND docstring IS NOT NULL AND docstring != ''
            LIMIT 5000
        """)

        total = 0
        for row in c.fetchall():
            d = dict(row)
            kind = d.get("kind", "")
            name = d.get("name", "")
            doc = d.get("docstring", "")[:300]
            fp = d.get("file_path", "")
            sig = d.get("signature", "") or ""

            if name and doc:
                entry = f"{kind} {name}"
                if sig:
                    entry += f"({sig})"
                entry += f": {doc}。定义于 {fp}"
                self._add(entry, fp, {"type": "codegraph", "kind": kind, "name": name})
                total += 1

        conn.close()
        logger.info(f"  CodeGraph知识: {total} 条")
    def expand_all(self, laap_root: str = "D:/LAAP"):
        """全量扩充"""
        t0 = time.time()
        logger.info("=" * 60)
        logger.info("  知识库扩充器 — 1259 → 目标 100K+")
        logger.info("=" * 60)
        logger.info("\n[1] Python 源码...")
        for subdir in ["aris_brain", "laap", "docs"]:
            d = os.path.join(laap_root, subdir)
            if os.path.exists(d):
                self.ingest_python_files(d)

        # 2. Markdown 文档
        logger.info("\n[2] Markdown 文档...")
        for subdir in ["aris_brain", "laap", "docs", "brotherhood"]:
            d = os.path.join(laap_root, subdir)
            if os.path.exists(d):
                self.ingest_markdown_files(d)

        # 3. 论文语料
        logger.info("\n[3] 论文语料...")
        self.ingest_paper_corpus()

        # 4. CodeGraph
        logger.info("\n[4] CodeGraph...")
        self.ingest_codegraph()

        logger.info(f"\n  总条目: {len(self._entries)}")
        logger.info(f"  耗时: {(time.time()-t0):.0f}s")
        return self._entries

    def build_matrix(self):
        """构建知识矩阵并保存"""
        from v7_encoder import get_encoder
        encoder = get_encoder(1024)

        logger.info(f"\n  编码 {len(self._entries)} 条知识...")
        batch_size = 200
        all_vecs = []
        for i in range(0, len(self._entries), batch_size):
            batch = self._entries[i:i+batch_size]
            texts = [e["text"][:300] for e in batch]
            vecs = encoder.encode_batch(texts)
            all_vecs.append(vecs)
            if (i + batch_size) % 2000 == 0:
                logger.info(f"    已编码: {i + batch_size}/{len(self._entries)}")
        matrix = np.vstack(all_vecs).astype(np.float32)
        # 归一化
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        matrix = matrix / norms

        # 保存
        state_dir = os.path.join(_DIR, "state")
        os.makedirs(state_dir, exist_ok=True)
        np.savez_compressed(
            os.path.join(state_dir, "kb_matrix_expanded.npz"),
            matrix=matrix
        )
        atomic_write_json({
            "texts": [e["text"] for e in self._entries],
            "metas": [e.get("meta", {}) for e in self._entries],
            "sources": [e.get("source", "") for e in self._entries],
        }, os.path.join(state_dir, "kb_index_expanded.json"))

        size_kb = os.path.getsize(os.path.join(state_dir, "kb_matrix_expanded.npz")) // 1024
        logger.info(f"\n  ✅ 已保存: {len(self._entries)}条, {matrix.shape}, {size_kb}KB")
        return matrix


if __name__ == "__main__":
    import hashlib
    expander = KnowledgeBaseExpander()
    entries = expander.expand_all("D:/LAAP")
    matrix = expander.build_matrix()
