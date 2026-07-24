"""
Aris Infinite Memory Store v4 — JSON + ChromaDB 混合引擎
=========================================================
三层: Working(工作记忆) / Episodic(情景记忆) / Core(核心记忆)

v4 升级:
  - ChromaDB 向量检索层叠加在原有 JSON 持久化之上
  - store() 自动向量化 + 写 JSON + 写 ChromaDB
  - recall() 默认走语义检索（替代关键词扫描）
  - fallback: ChromaDB 不可用时无损 fallback 回 v3 关键词
  - 全部接口向后兼容
"""

import logging

import json, os, time, logging, threading, hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger("aris.memory_store")

# ── 路径配置 ────────────────────────────────────────────────
MEMORY_ROOT = Path(os.environ.get("ARIS_MEMORY_ROOT", "D:/LAAP/aris_brain/memory"))
MEMORY_ROOT.mkdir(parents=True, exist_ok=True)

WORKING_DIR = MEMORY_ROOT / "working"
EPISODIC_DIR = MEMORY_ROOT / "episodic"
CORE_DIR = MEMORY_ROOT / "core"
CHROMA_DIR = MEMORY_ROOT / "chroma"
for d in [WORKING_DIR, EPISODIC_DIR, CORE_DIR, CHROMA_DIR]:
    d.mkdir(exist_ok=True)

INDEX_PATH = MEMORY_ROOT / "index.json"

# ── ChromaDB 初始化 ─────────────────────────────────────────
_chroma_client = None
_chroma_lock = threading.Lock()

def _get_chroma() -> Optional[Any]:
    """惰性初始化 ChromaDB（首次调用时加载）"""
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client
    # Safety check: try to load sentence_transformers (optional — ChromaDB handles embedding internally)
    try:
        from sentence_transformers import SentenceTransformer
        _ = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        logger.info("[ChromaDB] sentence_transformers 就绪")
    except Exception:
        logger.info("[ChromaDB] sentence_transformers 不可用，使用 ChromaDB 默认 ONNX embedding")
    with _chroma_lock:
        if _chroma_client is not None:
            return _chroma_client
        try:
            import chromadb
            from chromadb.config import Settings
            _chroma_client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )
            logger.info("[ChromaDB] 已初始化")
            return _chroma_client
        except Exception as e:
            logger.warning(f"[ChromaDB] 初始化失败，fallback 到纯 JSON 模式: {e}")
            return None

def _get_collection(name: str):
    """安全获取/创建 ChromaDB collection（线程安全）"""
    client = _get_chroma()
    if client is None:
        return None
    try:
        return client.get_collection(name)
    except:
        try:
            return client.create_collection(name)
        except Exception as e:
            logger.warning(f"[ChromaDB] 创建 collection '{name}' 失败: {e}")
            return None

# ── 数据结构 ────────────────────────────────────────────────

@dataclass
class MemoryFragment:
    """一条记忆碎片"""
    content: str                         # 文本内容
    memory_id: str = ""                  # 唯一ID（自动生成）
    layer: str = "episodic"              # working | episodic | core
    importance: float = 0.5              # 重要性 0-1
    emotional_valence: float = 0.0       # 情感价 -1~1
    topics: List[str] = field(default_factory=list)  # 关联话题
    timestamp: float = 0.0               # 创建时间戳
    access_count: int = 0                # 被回忆次数
    last_accessed: float = 0.0           # 最后回忆时间
    source_session: str = ""             # 来源会话ID
    embedding_dims: int = 0              # 向量维度（0 = 未向量化）
    ttl_days: float = 0.0                # 生存天数（0 = 永不过期）

    def __post_init__(self):
        if not self.memory_id:
            raw = f"{self.content}{self.timestamp}{time.time_ns()}"
            self.memory_id = hashlib.md5(raw.encode()).hexdigest()[:12]
        if not self.timestamp:
            self.timestamp = time.time()


class MemoryEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__class__') and hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        return super().default(obj)


# ── 存储引擎 ────────────────────────────────────────────────

class MemoryStore:
    """
    三层记忆存储引擎。
    线程安全，JSON + ChromaDB 双通道持久化。
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
        self._write_lock = threading.Lock()
        self._index_cache: Dict = {}
        self._load_index()

        # 预热 ChromaDB collection
        self._working_col = _get_collection("working")
        self._episodic_col = _get_collection("episodic")
        self._core_col = _get_collection("core")

        if self._working_col is not None:
            # 预热：触发一次嵌入模型加载
            try:
                self._working_col.query(query_texts=["预热"], n_results=1)
                logger.info("[MemoryStore] ChromaDB 向量引擎就绪 (384维 all-MiniLM-L6-v2)")
            except Exception as e:
                logger.info(f"[MemoryStore] ChromaDB 预热完成")
        else:
            logger.info("[MemoryStore] 纯 JSON 模式（ChromaDB 不可用）")

    # ── 内部文件操作 ───────────────────────────────────────

    def _load_index(self):
        if INDEX_PATH.exists():
            try:
                self._index_cache = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            except:
                self._index_cache = {"version": 2, "entries": {}}
        else:
            self._index_cache = {"version": 2, "entries": {}}
            INDEX_PATH.write_text(json.dumps(self._index_cache, ensure_ascii=False), encoding="utf-8")

    def _save_index(self):
        INDEX_PATH.write_text(json.dumps(self._index_cache, ensure_ascii=False), encoding="utf-8")

    def _working_path(self) -> Path:
        return WORKING_DIR / "current.json"

    def _episodic_path(self, date_str: str = None) -> Path:
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return EPISODIC_DIR / f"{date_str}.json"

    def _core_path(self, category: str = "identity") -> Path:
        return CORE_DIR / f"{category}.json"

    def _read_json(self, path: Path) -> List[Dict]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _write_json(self, path: Path, data: List[Dict]):
        path.write_text(
            json.dumps(data, ensure_ascii=False, cls=MemoryEncoder, indent=2),
            encoding="utf-8"
        )

    # ── ChromaDB 辅助 ──────────────────────────────────────

    def _chroma_col_for_layer(self, layer: str) -> Optional[Any]:
        return {
            "working": self._working_col,
            "episodic": self._episodic_col,
            "core": self._core_col,
        }.get(layer)

    def _chroma_count(self, layer: str) -> int:
        """获取 ChromaDB collection 的文档数量"""
        col = self._chroma_col_for_layer(layer)
        if col is None:
            return 0
        try:
            return col.count()
        except:
            return 0

    def _chroma_store(self, fragment: MemoryFragment):
        """存入 ChromaDB（自动向量化）"""
        col = self._chroma_col_for_layer(fragment.layer)
        if col is None:
            return

        # 用 topics 做 metadata 过滤
        metadata = {
            "layer": fragment.layer,
            "importance": fragment.importance,
            "emotional_valence": fragment.emotional_valence,
            "timestamp": fragment.timestamp,
            "access_count": fragment.access_count,
            "topics": ",".join(fragment.topics[:10]) if fragment.topics else "",
        }

        try:
            col.add(
                documents=[fragment.content],
                metadatas=[metadata],
                ids=[fragment.memory_id],
            )
        except Exception as e:
            logger.warning(f"[ChromaDB] store 失败 ({fragment.memory_id}): {e}")

    def _chroma_recall(self, query: str, top_k: int = 10,
                       layer: str = "all", min_importance: float = 0.0) -> List[Dict]:
        """从 ChromaDB 语义检索"""
        if layer == "all":
            results = []
            for l in ["working", "episodic", "core"]:
                col = self._chroma_col_for_layer(l)
                if col is None:
                    continue
                try:
                    r = col.query(
                        query_texts=[query],
                        n_results=top_k,
                        where={"importance": {"$gte": min_importance}} if min_importance > 0 else None,
                    )
                    for i in range(len(r["ids"][0])):
                        results.append({
                            "memory_id": r["ids"][0][i],
                            "content": r["documents"][0][i] if r["documents"] else "",
                            "score": r["distances"][0][i] if r.get("distances") else 0,
                            "metadata": (r["metadatas"][0][i] if r.get("metadatas") else {}),
                            "layer": l,
                        })
                except Exception as e:
                    logger.warning(f"[ChromaDB] query 失败 ({l}): {e}")

            # 合并排序
            results.sort(key=lambda x: x["score"])
            return results[:top_k]

        else:
            col = self._chroma_col_for_layer(layer)
            if col is None:
                return []
            try:
                r = col.query(
                    query_texts=[query],
                    n_results=top_k,
                    where={"importance": {"$gte": min_importance}} if min_importance > 0 else None,
                )
                results = []
                for i in range(len(r["ids"][0])):
                    results.append({
                        "memory_id": r["ids"][0][i],
                        "content": r["documents"][0][i] if r["documents"] else "",
                        "score": r["distances"][0][i] if r.get("distances") else 0,
                        "metadata": (r["metadatas"][0][i] if r.get("metadatas") else {}),
                        "layer": layer,
                    })
                return results
            except Exception as e:
                logger.warning(f"[ChromaDB] query 失败 ({layer}): {e}")
                return []

    def _chroma_update_metadata(self, memory_id: str, layer: str, updates: Dict):
        """更新 ChromaDB 中某条记忆的 metadata"""
        col = self._chroma_col_for_layer(layer)
        if col is None:
            return
        try:
            # ChromaDB 不支持部分更新，需要先查询再覆盖
            r = col.get(ids=[memory_id])
            if not r["ids"]:
                return
            meta = r["metadatas"][0] if r.get("metadatas") else {}
            meta.update(updates)
            col.update(ids=[memory_id], metadatas=[meta])
        except Exception as e:
            logger.warning(f"[ChromaDB] update_metadata 失败: {e}")

    # ════════════════════════════════════════════════════════
    # 公开接口（全部向后兼容）
    # ════════════════════════════════════════════════════════

    def store(self, fragment: MemoryFragment) -> str:
        """
        存入记忆到对应层。
        双通道: JSON 文件 + ChromaDB 向量索引。
        返回 memory_id。
        """
        with self._write_lock:
            if fragment.layer == "working":
                path = self._working_path()
                data = self._read_json(path)
                data.append(asdict(fragment))
                if len(data) > 200:
                    data.sort(key=lambda x: x.get("importance", 0), reverse=True)
                    data = data[:200]
                self._write_json(path, data)

            elif fragment.layer == "episodic":
                path = self._episodic_path()
                data = self._read_json(path)
                data.append(asdict(fragment))
                self._write_json(path, data)

            elif fragment.layer == "core":
                category = "identity"
                if fragment.topics:
                    category = fragment.topics[0]
                path = self._core_path(category)
                data = self._read_json(path)
                existing = [m for m in data if m.get("content") == fragment.content]
                if existing:
                    existing[0]["access_count"] += 1
                    existing[0]["last_accessed"] = time.time()
                    existing[0]["importance"] = max(existing[0]["importance"], fragment.importance)
                else:
                    data.append(asdict(fragment))
                    if len(data) > 500:
                        data.sort(key=lambda x: x.get("importance", 0), reverse=True)
                        data = data[:500]
                self._write_json(path, data)

            # 更新索引
            self._index_cache["entries"][fragment.memory_id] = {
                "content": fragment.content[:100],
                "layer": fragment.layer,
                "importance": fragment.importance,
                "topics": fragment.topics,
                "timestamp": fragment.timestamp,
                "emotional_valence": fragment.emotional_valence,
            }
            self._save_index()

        # ChromaDB 异步写入（不加锁，thread-safe）
        self._chroma_store(fragment)

        return fragment.memory_id

    def store_batch(self, fragments: List[MemoryFragment]) -> List[str]:
        """批量存入"""
        ids = []
        for f in fragments:
            ids.append(self.store(f))
        return ids

    def recall(self, query: str, top_k: int = 5, layer: str = "all",
               min_importance: float = 0.0) -> List[MemoryFragment]:
        """
        检索记忆。
        v4: 智能路由——数据量 > 100 条走 ChromaDB 语义检索，否则走关键词（更快）。
        """
        # 智能路由：数据量少时直接走关键词（更快）
        total = sum(self._chroma_count(l) for l in ["working", "episodic", "core"]
                    if self._chroma_col_for_layer(l) is not None)
        if total < 100:
            return self._recall_fallback(query, top_k, layer, min_importance)

        # 优先走 ChromaDB 语义检索
        chroma_results = self._chroma_recall(query, top_k=top_k * 2,
                                             layer=layer, min_importance=min_importance)
        if chroma_results:
            fragments = []
            for r in chroma_results[:top_k]:
                # 从索引补充 metadata
                entry = self._index_cache.get("entries", {}).get(r["memory_id"], {})
                f = MemoryFragment(
                    content=r["content"],
                    memory_id=r["memory_id"],
                    layer=r.get("layer", layer if layer != "all" else "episodic"),
                    importance=r["metadata"].get("importance", entry.get("importance", 0.5)),
                    emotional_valence=r["metadata"].get("emotional_valence", 0.0),
                    topics=r["metadata"].get("topics", "").split(",") if r["metadata"].get("topics") else [],
                    timestamp=r["metadata"].get("timestamp", 0.0),
                    embedding_dims=384,
                )
                # 更新访问计数
                self._access_count(f.memory_id, f.layer)
                fragments.append(f)

            # 最多 top_k 条
            return fragments[:top_k]

        # fallback: 旧版关键词匹配
        return self._recall_fallback(query, top_k, layer, min_importance)

    def _recall_fallback(self, query: str, top_k: int = 5, layer: str = "all",
                         min_importance: float = 0.0) -> List[MemoryFragment]:
        """旧版关键词匹配 fallback"""
        results = []
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for mem_id, entry in self._index_cache.get("entries", {}).items():
            if layer != "all" and entry["layer"] != layer:
                continue
            if entry["importance"] < min_importance:
                continue

            content_lower = entry["content"].lower()
            matched_terms = sum(1 for t in query_terms if t in content_lower)
            if matched_terms == 0:
                topic_match = any(t.lower() in query_lower for t in entry.get("topics", []))
                if not topic_match:
                    continue

            score = self._compute_score(entry, matched_terms)
            results.append((score, mem_id, entry))

        results.sort(key=lambda x: -x[0])
        fragments = []
        for score, mem_id, entry in results[:top_k]:
            f = self._load_fragment(mem_id, entry)
            if f:
                fragments.append(f)
        return fragments

    def _compute_score(self, entry: Dict, matched_terms: int) -> float:
        importance = entry.get("importance", 0.5)
        age_hours = (time.time() - entry.get("timestamp", time.time())) / 3600
        recency = max(0, 1.0 - age_hours / 720)
        term_score = min(1.0, matched_terms / 3.0)
        return term_score * 0.5 + recency * 0.2 + importance * 0.3

    def _load_fragment(self, memory_id: str, entry: Dict) -> Optional[MemoryFragment]:
        layer = entry["layer"]
        try:
            data = None
            if layer == "working":
                for m in self._read_json(self._working_path()):
                    if m.get("memory_id") == memory_id:
                        data = m
                        break
            elif layer == "episodic":
                for fpath in sorted(EPISODIC_DIR.glob("*.json"), reverse=True)[:30]:
                    for m in self._read_json(fpath):
                        if m.get("memory_id") == memory_id:
                            data = m
                            break
                    if data:
                        break
            elif layer == "core":
                for fpath in CORE_DIR.glob("*.json"):
                    for m in self._read_json(fpath):
                        if m.get("memory_id") == memory_id:
                            data = m
                            break
                    if data:
                        break
            if data:
                self._access_count(memory_id, layer)
                f = MemoryFragment(**{k: v for k, v in data.items() if k in
                    ["content", "memory_id", "layer", "importance", "emotional_valence",
                     "topics", "timestamp", "access_count", "last_accessed",
                     "source_session", "embedding_dims", "ttl_days"]})
                return f
        except Exception as e:
            logger.warning(f"Failed to load fragment {memory_id}: {e}")
        return None

    def _access_count(self, memory_id: str, layer: str):
        """增加访问计数（在 ChromaDB 和索引中同步）"""
        entry = self._index_cache.get("entries", {}).get(memory_id)
        if entry:
            entry["importance"] = min(1.0, entry.get("importance", 0.5) + 0.01)
        self._chroma_update_metadata(memory_id, layer, {
            "access_count": entry.get("access_count", 0) + 1 if entry else 1,
            "importance": entry.get("importance", 0.5) if entry else 0.5,
        })

    def get_working_memory(self) -> List[MemoryFragment]:
        """获取当前工作记忆"""
        path = self._working_path()
        data = self._read_json(path)
        fragments = []
        for d in data:
            try:
                fragments.append(MemoryFragment(**{k: d[k] for k in
                    ["content", "memory_id", "layer", "importance", "emotional_valence",
                     "topics", "timestamp", "access_count", "last_accessed",
                     "source_session", "embedding_dims", "ttl_days"]
                    if k in d}))
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        fragments.sort(key=lambda x: -x.importance)
        return fragments[:50]

    def get_recent_episodic(self, days: int = 7) -> List[MemoryFragment]:
        """获取最近N天的情景记忆"""
        fragments = []
        now = time.time()
        cutoff = now - days * 86400
        for fpath in sorted(EPISODIC_DIR.glob("*.json"), reverse=True)[:days * 2]:
            for d in self._read_json(fpath):
                ts = d.get("timestamp", 0)
                if ts >= cutoff:
                    try:
                        fragments.append(MemoryFragment(**{k: d[k] for k in
                            ["content", "memory_id", "layer", "importance",
                             "emotional_valence", "topics", "timestamp",
                             "access_count", "last_accessed", "source_session",
                             "embedding_dims", "ttl_days"] if k in d}))
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
        fragments.sort(key=lambda x: -x.timestamp)
        return fragments[:200]

    def get_core_memory(self, category: str = None) -> List[MemoryFragment]:
        """获取核心记忆"""
        fragments = []
        if category:
            paths = [self._core_path(category)]
        else:
            paths = list(CORE_DIR.glob("*.json"))
        for fpath in paths:
            for d in self._read_json(fpath):
                try:
                    fragments.append(MemoryFragment(**{k: d[k] for k in
                        ["content", "memory_id", "layer", "importance",
                         "emotional_valence", "topics", "timestamp",
                         "access_count", "last_accessed", "source_session",
                         "embedding_dims", "ttl_days"] if k in d}))
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        return fragments

    # ── 维护操作 ──────────────────────────────────────────

    def consolidate(self) -> Dict[str, int]:
        """巩固一轮（同 v3 逻辑）"""
        stats = {"promoted": 0, "expired": 0, "cleaned": 0}

        for fpath in sorted(EPISODIC_DIR.glob("*.json")):
            data = self._read_json(fpath)
            remaining = []
            for m in data:
                if m.get("access_count", 0) >= 5 and m.get("importance", 0) >= 0.6:
                    m["layer"] = "core"
                    self.store(MemoryFragment(**{k: m[k] for k in
                        ["content", "memory_id", "layer", "importance",
                         "emotional_valence", "topics", "timestamp",
                         "access_count", "last_accessed", "source_session",
                         "embedding_dims", "ttl_days"] if k in m}))
                    stats["promoted"] += 1
                else:
                    remaining.append(m)
            self._write_json(fpath, remaining)

        now = time.time()
        for fpath in sorted(EPISODIC_DIR.glob("*.json")):
            data = self._read_json(fpath)
            remaining = []
            for m in data:
                age_days = (now - m.get("timestamp", now)) / 86400
                if age_days > 90 and m.get("importance", 0) < 0.3:
                    stats["expired"] += 1
                    mid = m.get("memory_id", "")
                    self._index_cache.get("entries", {}).pop(mid, None)
                else:
                    remaining.append(m)
            self._write_json(fpath, remaining)

        wpath = self._working_path()
        wdata = self._read_json(wpath)
        wremaining = [m for m in wdata if m.get("importance", 0) >= 0.2]
        stats["cleaned"] = len(wdata) - len(wremaining)
        self._write_json(wpath, wremaining)

        self._save_index()
        return stats

    def decay(self) -> Dict[str, int]:
        """遗忘曲线衰减"""
        stats = {"working": 0, "episodic": 0, "core": 0}
        now = time.time()

        def _apply_decay(data: List[Dict], layer: str) -> int:
            count = 0
            for m in data:
                age_hours = (now - m.get("last_accessed", m.get("timestamp", now))) / 3600
                decay_rate = {"core": 0.001, "episodic": 0.003, "working": 0.01}.get(layer, 0.005)
                new_imp = m["importance"] * (1.0 - decay_rate * min(age_hours, 720) / 720)
                if new_imp != m["importance"]:
                    m["importance"] = round(max(0.01, new_imp), 4)
                    count += 1
            return count

        wpath = self._working_path()
        wdata = self._read_json(wpath)
        stats["working"] = _apply_decay(wdata, "working")
        self._write_json(wpath, wdata)

        for fpath in EPISODIC_DIR.glob("*.json"):
            data = self._read_json(fpath)
            stats["episodic"] += _apply_decay(data, "episodic")
            self._write_json(fpath, data)

        for fpath in CORE_DIR.glob("*.json"):
            data = self._read_json(fpath)
            stats["core"] += _apply_decay(data, "core")
            self._write_json(fpath, data)

        return stats

    def get_stats(self) -> Dict[str, Any]:
        """获取各层统计"""
        stats = {"working": 0, "episodic": 0, "core": 0, "total": 0}

        wpath = self._working_path()
        stats["working"] = len(self._read_json(wpath))

        for fpath in EPISODIC_DIR.glob("*.json"):
            stats["episodic"] += len(self._read_json(fpath))

        for fpath in CORE_DIR.glob("*.json"):
            stats["core"] += len(self._read_json(fpath))

        stats["total"] = stats["working"] + stats["episodic"] + stats["core"]
        stats["index_entries"] = len(self._index_cache.get("entries", {}))

        # ChromaDB 计数
        try:
            for name, col in [("working", self._working_col), ("episodic", self._episodic_col),
                             ("core", self._core_col)]:
                if col is not None:
                    stats[f"chroma_{name}"] = col.count()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        total_size = 0
        for fpath in MEMORY_ROOT.rglob("*.json"):
            total_size += fpath.stat().st_size
        stats["size_bytes"] = total_size
        stats["size_kb"] = round(total_size / 1024, 1)

        return stats

    def wipe_working(self):
        """清空工作记忆"""
        self._write_json(self._working_path(), [])
        # 也清空 ChromaDB 的 working collection
        try:
            if self._working_col is not None:
                all_ids = self._working_col.get()["ids"]
                if all_ids:
                    self._working_col.delete(ids=all_ids)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        logger.info("Working memory wiped (JSON + ChromaDB)")

    def get_memory_embedding(self, query: str = "", layer: str = "core", top_k: int = 3) -> np.ndarray:
        """
        获取记忆嵌入向量（用于 self_model_nn 输入）。

        从指定层检索最相关的记忆，提取其向量表示并聚合。

        Args:
            query: 查询文本（为空时返回核心记忆的平均嵌入）
            layer: working | episodic | core
            top_k: 返回前多少条记忆的聚合

        Returns:
            384-dim float32 numpy 数组（all-MiniLM-L6-v2 维度）
        """
        col = self._chroma_col_for_layer(layer)
        if col is None:
            logger.debug(f"ChromaDB collection '{layer}' not available, returning zero vector")
            return np.zeros(384, dtype=np.float32)

        try:
            if query:
                results = col.query(
                    query_texts=[query],
                    n_results=top_k,
                    include=["embeddings"],
                )
            else:
                all_data = col.get(include=["embeddings"])
                if all_data["embeddings"]:
                    results = {
                        "embeddings": [all_data["embeddings"][:top_k]],
                    }
                else:
                    return np.zeros(384, dtype=np.float32)

            embeddings = results.get("embeddings", [])
            if not embeddings or not embeddings[0]:
                logger.debug(f"No embeddings found for layer '{layer}'")
                return np.zeros(384, dtype=np.float32)

            # 聚合：取平均
            emb_array = np.array(embeddings[0], dtype=np.float32)
            avg_emb = np.mean(emb_array, axis=0)

            logger.debug(
                f"Memory embedding: layer={layer}, n={len(embeddings[0])}, "
                f"norm={np.linalg.norm(avg_emb):.4f}"
            )
            return avg_emb

        except Exception as e:
            logger.debug(f"Failed to get memory embedding: {e}")
            return np.zeros(384, dtype=np.float32)
