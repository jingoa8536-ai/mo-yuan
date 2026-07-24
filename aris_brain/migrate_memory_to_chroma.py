"""
Aris 记忆迁移脚本 v1
=====================
将现有 JSON 文件中的记忆全量导入 ChromaDB。

用法: python migrate_memory_to_chroma.py
"""

import logging

import sys, json, time, logging, hashlib
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("migrate")

# ── 路径 ──
MEMORY_ROOT = Path("D:/LAAP/aris_brain/memory")
WORKING_DIR = MEMORY_ROOT / "working"
EPISODIC_DIR = MEMORY_ROOT / "episodic"
CORE_DIR = MEMORY_ROOT / "core"
CHROMA_DIR = MEMORY_ROOT / "chroma"

# ── ChromaDB ──
import chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(
    path=str(CHROMA_DIR),
    settings=Settings(anonymized_telemetry=False),
)

def get_or_create_collection(name: str):
    try:
        return client.get_collection(name)
    except:
        return client.create_collection(name)

def read_json(path: Path) -> List[Dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return []
    return []

def migrate_layer(name: str, files: List[Path]) -> int:
    """迁移一个层到 ChromaDB"""
    col = get_or_create_collection(name)
    imported = 0

    for fpath in files:
        data = read_json(fpath)
        if not data:
            continue

        batch_docs = []
        batch_meta = []
        batch_ids = []

        for m in data:
            mid = m.get("memory_id", "")
            if not mid:
                raw = f"{m.get('content','')}{m.get('timestamp',time.time())}"
                mid = hashlib.md5(raw.encode()).hexdigest()[:12]

            # 检查是否已存在
            try:
                existing = col.get(ids=[mid])
                if existing["ids"]:
                    continue  # 已导入，跳过
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            content = m.get("content", "")
            if not content:
                continue

            batch_docs.append(content)
            batch_meta.append({
                "layer": name,
                "importance": m.get("importance", 0.5),
                "emotional_valence": m.get("emotional_valence", 0.0),
                "timestamp": m.get("timestamp", time.time()),
                "access_count": m.get("access_count", 0),
                "topics": ",".join(m.get("topics", [])) if m.get("topics") else "",
            })
            batch_ids.append(mid)

            if len(batch_ids) >= 32:
                col.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
                imported += len(batch_ids)
                batch_docs, batch_meta, batch_ids = [], [], []

        if batch_ids:
            col.add(documents=batch_docs, metadatas=batch_meta, ids=batch_ids)
            imported += len(batch_ids)

        logger.info(f"  {fpath.name}: {len(data)} 条 → {imported} 条已导入")

    return imported


def main():
    start = time.time()
    logger.info("=== 开始迁移记忆到 ChromaDB ===")

    # 1. 工作记忆
    wfiles = list(WORKING_DIR.glob("*.json"))
    w_count = migrate_layer("working", wfiles)
    logger.info(f"工作记忆: {w_count} 条")

    # 2. 情景记忆
    efiles = sorted(EPISODIC_DIR.glob("*.json"))
    e_count = migrate_layer("episodic", efiles)
    logger.info(f"情景记忆: {e_count} 条")

    # 3. 核心记忆
    cfiles = list(CORE_DIR.glob("*.json"))
    c_count = migrate_layer("core", cfiles)
    logger.info(f"核心记忆: {c_count} 条")

    total = w_count + e_count + c_count
    elapsed = time.time() - start

    # 汇总
    for name in ["working", "episodic", "core"]:
        col = get_or_create_collection(name)
        count = col.count()
        logger.info(f"  ChromaDB [{name}]: {count} 条")

    logger.info(f"=== 迁移完成: 总计 {total} 条, 耗时 {elapsed:.1f}s ===")

    # 清理测试 collection
    try:
        client.delete_collection("test")
    except Exception as e:
        logger.debug(f"操作失败: {e}")
if __name__ == "__main__":
    main()
