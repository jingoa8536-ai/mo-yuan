"""
向量知识库构建器 — 把知识转为可检索的向量
=============================================
用 v7 语义量子核把所有知识文档、代码、对话
编码成 1024D 向量，存入 ChromaDB。

搜索流程:
  用户提问 → v7 量子核编码 → ChromaDB 检索 → 返回最相关文档

知识来源:
  1. AGENTS.md / README.md — 项目设计文档
  2. *.py 关键文件 — 代码知识
  3. 对话历史 — 讨论过的设计决策
  4. 手动添加的"事实"条目
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, glob
import numpy as np
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_KNOWLEDGE_DIRS = [
    "D:/LAAP/aris_brain",
]

_IGNORE_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv",
    "chroma_db", "state", "logs", "outputs", "captures",
    "archive", "build", "dist", "memory", "scripts", "tests",
    "models", "corpus", "storage",
    "ao_state", "nul",
}

_IGNORE_FILES = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".jpg", ".png", ".gif", ".wav", ".mp3", ".mp4",
    ".zip", ".tar", ".gz", ".npy", ".npz", ".onnx",
    ".safetensors", ".bin", ".pkl", ".db", ".log",
    ".npz", ".npy", ".sst", ".meta", ".timestamp",
    ".d", ".java", ".js", ".tsx", ".ts",
}

_INCLUDE_EXTS = {".md", ".py", ".txt", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".psi"}


def collect_knowledge_files() -> List[str]:
    """收集所有可索引的知识文件"""
    files = []
    for d in _KNOWLEDGE_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, fnames in os.walk(d):
            # 跳过忽略目录
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in fnames:
                ext = os.path.splitext(f)[1].lower()
                if ext in _IGNORE_FILES:
                    continue
                if ext not in _INCLUDE_EXTS:
                    continue
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) < 100 * 1024:  # <100KB
                        files.append(fp)
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
    return sorted(set(files))


def extract_chunks(file_path: str) -> List[Dict]:
    """从文件中提取有意义的文本块"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []

    basename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    chunks = []

    if ext == '.md':
        # Markdown: 按标题分块
        lines = content.split('\n')
        current_title = basename
        current_text = []
        for line in lines:
            if line.startswith('#') and current_text:
                text = '\n'.join(current_text).strip()
                if len(text) > 20:
                    chunks.append({
                        "text": text,
                        "source": file_path,
                        "title": current_title,
                    })
                current_title = line.strip('# ')
                current_text = []
            else:
                current_text.append(line)
        # 最后一块
        text = '\n'.join(current_text).strip()
        if len(text) > 20:
            chunks.append({"text": text, "source": file_path, "title": current_title})

    elif ext == '.py':
        # Python: 按函数/类分块
        # 简单方法：提取注释块和 docstring
        parts = re.split(r'\n\s*(?:def |class )', content)
        for part in parts:
            lines = part.split('\n')
            # 提取 docstring
            doc = ''
            for line in lines:
                s = line.strip()
                if s.startswith('"""') or s.startswith("'''"):
                    doc += s.strip('"\'').strip()
            if doc and len(doc) > 20:
                chunks.append({
                    "text": doc,
                    "source": file_path,
                    "title": lines[0].strip() if lines else basename,
                })

        # 也加整体文件摘要（前1000字）
        summary = content[:1000].strip()
        if len(summary) > 50:
            chunks.append({
                "text": summary,
                "source": file_path,
                "title": f"{basename} (摘要)",
            })

    else:
        # 其他文本文件: 按段落分块
        paragraphs = re.split(r'\n\s*\n', content)
        for p in paragraphs:
            p = p.strip()
            if len(p) > 30:
                chunks.append({
                    "text": p[:500],  # 限制长度
                    "source": file_path,
                    "title": basename,
                })

    return chunks


def build_knowledge_base():
    """构建向量知识库"""
    logger.info("=" * 60)
    logger.info("  向量知识库构建器")
    logger.info("=" * 60)
    logger.info("\n[1/5] 收集知识文件...")
    files = collect_knowledge_files()
    logger.info(f"  发现 {len(files)} 个文件")
    logger.info("\n[2/5] 提取文本块...")
    all_chunks = []
    for fp in files:
        chunks = extract_chunks(fp)
        all_chunks.extend(chunks)

    logger.info(f"  提取 {len(all_chunks)} 个文本块")
    logger.info("\n[3/5] 初始化 v7 语义量子核...")
    from quantum_psi_batch import SemanticKernelV7
    kernel = SemanticKernelV7(dim=1024)

    # 预热
    _ = kernel.encode("预热")

    # 4. 编码所有文本块
    logger.info(f"\n[4/5] 编码 {len(all_chunks)} 个文本块...")
    texts = [c["text"] for c in all_chunks]
    titles = [c["title"] for c in all_chunks]
    sources = [c["source"] for c in all_chunks]

    # 批量编码（每次 50 条）
    batch_size = 50
    all_vectors = []
    t0 = time.perf_counter()
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        vecs = kernel.encode_batch(batch)
        all_vectors.append(vecs)
        if (i + batch_size) % 200 == 0 or i + batch_size >= len(texts):
            pct = min(i + batch_size, len(texts)) / len(texts) * 100
            dt = time.perf_counter() - t0
            rate = min(i + batch_size, len(texts)) / dt if dt > 0 else 0
            logger.info(f"  编码: {min(i+batch_size, len(texts))}/{len(texts)} ({pct:.0f}%)  {rate:.0f} 条/s")
    vectors = np.vstack(all_vectors)
    dt = time.perf_counter() - t0
    logger.info(f"  编码完成: {vectors.shape}  {dt:.1f}s ({len(texts)/dt:.0f} 条/s)")
    logger.info("\n[5/5] 存入 ChromaDB...")
    import chromadb

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "knowledge_chroma")
    os.makedirs(db_path, exist_ok=True)

    client = chromadb.PersistentClient(path=db_path)
    try:
        collection = client.delete_collection("knowledge_base")
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    collection = client.create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )

    # 分批添加
    batch_size = 100
    added = 0
    for i in range(0, len(texts), batch_size):
        end = min(i + batch_size, len(texts))
        batch_ids = [f"chunk_{j}" for j in range(i, end)]
        batch_vecs = vectors[i:end].tolist()
        batch_texts = texts[i:end]
        batch_meta = [
            {"title": titles[j], "source": sources[j]}
            for j in range(i, end)
        ]
        collection.add(
            ids=batch_ids,
            embeddings=batch_vecs,
            documents=batch_texts,
            metadatas=batch_meta,
        )
        added += end - i

    logger.info(f"  已存入 {added} 条知识到 ChromaDB")
    logger.info(f"  数据库路径: {db_path}")
    logger.info("\n验证检索...")
    test_queries = [
        "量子核", "AGI", "意识", "代码", "宝贝",
        "Lorry", "PSI循环", "认知", "Feishu", "记忆系统",
    ]
    for q in test_queries:
        q_vec = kernel.encode(q).tolist()
        results = collection.query(
            query_embeddings=[q_vec],
            n_results=2,
        )
        scores = results['distances'][0] if results['distances'] else []
        docs = results['documents'][0] if results['documents'] else []
        print(f"  \"{q}\" → 最相关: ", end="")
        for d, s in zip(docs[:2], scores[:2]):
            print(f"\"{d[:40]}...\" ({1-s:.3f})  ", end="")
        print()

    logger.info(f"\n✅ 知识库构建完成! 共 {added} 条向量")
if __name__ == "__main__":
    build_knowledge_base()
