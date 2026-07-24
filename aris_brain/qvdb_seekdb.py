"""
QVDB SeekDB Plugin — 开源数据库集成
=====================================
接入 SeekDB (oceanbase) 作为 QVDB 后端。

同时提供数据集下载器用于扩充语料。

使用:
  from qvdb_seekdb import SeekDBPlugin
  from qvdb_seekdb import DatasetDownloader

  # 添加后端
  db.add_plugin(SeekDBPlugin())

  # 下载语料
  dl = DatasetDownloader()
  dl.download_fineweb_chinese(limit=500)
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, hashlib, subprocess
from typing import Dict, List, Optional
from write_utils import atomic_write_json
import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
_REPOS_DIR = os.path.join(os.path.dirname(_DIR), "repos")
_DATA_DIR = os.path.join(_DIR, "corpus", "datasets")

os.makedirs(_DATA_DIR, exist_ok=True)


# ================================================================
# SeekDB 后端
# ================================================================

class SeekDBPlugin:
    """SeekDB 向量检索引擎插件"""

    name = "seekdb"
    version = "1.0"
    description = "OceanBase SeekDB: MySQL兼容 + 向量+全文混合检索"

    def __init__(self):
        self._client = None
        self._loaded = False

    def _lazy(self):
        if self._loaded:
            return
        # 尝试导入 SeekDB SDK
        seekdb_path = os.path.join(_REPOS_DIR, "pyseekdb")
        if os.path.exists(seekdb_path) and seekdb_path not in sys.path:
            sys.path.insert(0, seekdb_path)
        try:
            from seekdb import SeekDBClient
            self._client = SeekDBClient()
            self._loaded = True
            logger.info("  SeekDB: SDK loaded")
        except ImportError:
            logger.info("  SeekDB: SDK not available, use pip install pyseekdb")
        except Exception as e:
            logger.info(f"  SeekDB: {e}")
    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List:
        self._lazy()
        if not self._client:
            return []
        # 调用 SeekDB 搜索
        try:
            results = self._client.search(query, limit=top_k)
            return [
                SearchResult(
                    text=r.get("text", ""), score=r.get("score", 0),
                    source=self.name, metadata=r.get("metadata", {}),
                ) for r in results
            ]
        except Exception as e:
            logger.error(f"  SeekDB search error: {e}")
            return []

    def add(self, texts, metadatas=None):
        self._lazy()
        if not self._client:
            return 0
        try:
            for i, t in enumerate(texts):
                meta = metadatas[i] if metadatas else {}
                self._client.insert({"text": t, "metadata": meta})
            return len(texts)
        except:
            return 0

    def stats(self) -> Dict:
        return {"name": self.name, "loaded": self._loaded}


# ================================================================
# 数据集下载器
# ================================================================

class DatasetDownloader:
    """
    开源数据集下载 & 语料扩充

    来源:
      - HuggingFace: Chinese-Fineweb-Edu, ChineseWebText
      - Awesome Public Datasets
    """

    def download_fineweb_chinese(self, limit: int = 500,
                                  split: str = "train") -> List[str]:
        """
        下载 Fineweb-Edu-Chinese 数据集

        用法:
          dl = DatasetDownloader()
          texts = dl.download_fineweb_chinese(limit=1000)
          # → 1000 条高质量中文教育文本
        """
        try:
            from datasets import load_dataset
        except ImportError:
            logger.info("  pip install datasets 后重试")
            return []

        logger.info(f"  下载 Fineweb-Edu-Chinese ({limit}条)...")
        try:
            ds = load_dataset(
                "opencsg/Fineweb-Edu-Chinese-V2.1",
                split=split,
                streaming=True,
            )
            texts = []
            for i, item in enumerate(ds):
                if i >= limit:
                    break
                text = item.get("text", "") or item.get("content", "")
                if text and len(text) > 50:
                    texts.append(text[:2000])
            logger.info(f"  下载完成: {len(texts)}条")
            return texts
        except Exception as e:
            logger.error(f"  下载失败: {e}")
            return []

    def download_from_hf(self, dataset_name: str, limit: int = 1000,
                          text_field: str = "text") -> List[str]:
        """通用 HuggingFace 数据集下载"""
        try:
            from datasets import load_dataset
        except ImportError:
            logger.info("  pip install datasets")
            return []

        logger.info(f"  下载 {dataset_name}...")
        try:
            ds = load_dataset(dataset_name, split="train", streaming=True)
            texts = []
            for i, item in enumerate(ds):
                if i >= limit:
                    break
                text = item.get(text_field, "")
                if isinstance(text, list):
                    text = " ".join(str(t) for t in text)
                if text and len(str(text)) > 50:
                    texts.append(str(text)[:2000])
            return texts
        except Exception as e:
            logger.info(f"  {e}")
            return []

    def save_to_corpus(self, texts: List[str], filename: str):
        """保存到语料目录"""
        path = os.path.join(_DATA_DIR, filename)
        with open(path, 'w', encoding='utf-8') as f:
            for t in texts:
                f.write(t.strip().replace('\n', ' ') + '\n')
        logger.info(f"  已保存: {path} ({len(texts)}行, {os.path.getsize(path)//1024}KB)")
# 自动整合回主 KB
# ================================================================

def integrate_dataset_to_kb(texts: List[str]):
    """把数据集文本编码加入知识矩阵"""
    from semantic_engine import get_encoder
    from matrix_knowledge import MatrixKnowledgeRetriever

    encoder = get_encoder(1024)
    kb = MatrixKnowledgeRetriever()

    if not kb._loaded:
        logger.info("  KB not loaded")
        return

    texts = [t[:300] for t in texts if len(t) > 50]
    logger.info(f"  编码 {len(texts)} 条...")
    vecs = []
    for t in texts:
        v = encoder.encode(t)
        v = v / (np.linalg.norm(v) + 1e-10)
        vecs.append(v)

    new_matrix = np.vstack(vecs).astype(np.float32)

    # 合并
    import json
    kb_path = os.path.join(_DIR, "state", "kb_matrix.npz")
    idx_path = os.path.join(_DIR, "state", "kb_index.json")

    old = np.load(kb_path)
    merged_matrix = np.vstack([old["matrix"], new_matrix])

    with open(idx_path, 'r', encoding='utf-8') as f:
        idx = json.load(f)

    idx["texts"].extend(texts)
    idx["metas"].extend([{"source": "fineweb_chinese"} for _ in texts])

    np.savez_compressed(kb_path, matrix=merged_matrix)
    atomic_write_json(idx, idx_path)

    logger.info(f"  ✅ KB 扩展: {len(idx['texts'])}条 ({merged_matrix.shape})")
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  QVDB SeekDB Plugin + Dataset Downloader")
    logger.info("=" * 60)
    dl = DatasetDownloader()
    texts = dl.download_fineweb_chinese(limit=50)
    if texts:
        dl.save_to_corpus(texts, "fineweb_chinese_sample.txt")
        logger.info(f"\n  示例:")
        for t in texts[:2]:
            logger.info(f"    {t[:150]}...")
    if texts and len(texts) >= 10:
        logger.info("\n  整合到知识矩阵...")
        integrate_dataset_to_kb(texts)
