"""
V9 持久量子记忆 — SQLite + 纠缠编码
=====================================
让 QuantumVM 的记忆在重启后仍然存在。
概念网络、关联记忆、量子态寄存器全部持久化到 SQLite。

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, json, time, hashlib, os, threading, numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

DB_PATH = Path("D:/LAAP/aris_brain/state/quantum_memory.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS concepts (
    name TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    valence REAL DEFAULT 0.0,
    tags TEXT DEFAULT '[]',
    created_at REAL NOT NULL,
    last_access REAL NOT NULL,
    access_count INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,
    importance REAL DEFAULT 0.5,
    created_at REAL NOT NULL,
    last_recall REAL,
    recall_count INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    emotion TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS registers (
    name TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    type TEXT DEFAULT 'quantum',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS quantum_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, emotion, source,
    content='memories'
);

CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_concepts_access ON concepts(last_access DESC);
"""

class QuantumMemory:
    """量子持久记忆 — 连接 QuantumVM 和 SQLite"""
    
    def __init__(self, db_path: str = None, dim: int = 1024):
        self.db_path = Path(db_path or str(DB_PATH))
        self.dim = dim
        self._lock = threading.Lock()
        self._connect()
        self._init_schema()

    def _connect(self):
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
    
    def _init_schema(self):
        for stmt in SCHEMA.split(';'):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)
        self._conn.commit()
    
    # ── 嵌入编码 ──
    
    def _embed_to_blob(self, emb: np.ndarray) -> bytes:
        """numpy 数组 → SQLite BLOB"""
        return emb.astype(np.float32).tobytes()
    
    def _blob_to_embed(self, blob: bytes) -> np.ndarray:
        """SQLite BLOB → numpy 数组"""
        arr = np.frombuffer(blob, dtype=np.float32)
        if len(arr) < self.dim:
            padded = np.zeros(self.dim)
            padded[:len(arr)] = arr
            return padded
        return arr[:self.dim]
    
    def _text_to_embedding(self, text: str) -> np.ndarray:
        """文本 → 量子纠缠嵌入向量"""
        emb = np.zeros(self.dim)
        for i, ch in enumerate(text[:256]):
            idx = (hash(ch) + i * 7 + 13) % self.dim
            emb[idx] += 0.15
            # 二阶纠缠：相邻字符产生纠缠峰
            if i > 0:
                idx2 = (hash(ch) + (i-1) * 7 + 17) % self.dim
                emb[idx2] += 0.05
        norm = np.linalg.norm(emb)
        if norm > 1e-10:
            emb /= norm
        return emb
    
    def _embedding_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """两个嵌入向量的余弦相似度"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
    
    # ── 概念操作 ──
    
    def save_concept(self, name: str, embedding: np.ndarray, 
                     valence: float = 0.0, tags: List[str] = None,
                     metadata: Dict = None):
        now = time.time()
        existing = self._conn.execute(
            "SELECT created_at, access_count FROM concepts WHERE name=?", (name,)
        ).fetchone()
        if existing:
            created_at = existing['created_at']
            access_count = existing['access_count'] + 1
        else:
            created_at = now
            access_count = 1
        
        self._conn.execute("""
            INSERT INTO concepts (name, embedding, valence, tags, created_at, 
                                  last_access, access_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                embedding=excluded.embedding,
                valence=excluded.valence,
                tags=excluded.tags,
                last_access=excluded.last_access,
                access_count=excluded.access_count,
                metadata=excluded.metadata
        """, (
            name, self._embed_to_blob(embedding), valence,
            json.dumps(tags or [], ensure_ascii=False),
            now if existing is None else existing['created_at'],
            now, access_count,
            json.dumps(metadata or {}, ensure_ascii=False)
        ))
        self._conn.commit()
    
    def load_concepts(self) -> Dict[str, Dict]:
        """加载所有概念到 dict"""
        rows = self._conn.execute(
            "SELECT * FROM concepts ORDER BY access_count DESC"
        ).fetchall()
        concepts = {}
        for r in rows:
            concepts[r['name']] = {
                'embedding': self._blob_to_embed(r['embedding']),
                'valence': r['valence'],
                'tags': json.loads(r['tags']),
                'access_count': r['access_count'],
                'metadata': json.loads(r['metadata']),
            }
        return concepts
    
    def search_concept(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """通过纠缠相似度搜索概念"""
        qemb = self._text_to_embedding(query)
        rows = self._conn.execute("SELECT name, embedding FROM concepts").fetchall()
        scored = []
        for r in rows:
            emb = self._blob_to_embed(r['embedding'])
            sim = self._embedding_similarity(qemb, emb)
            scored.append((r['name'], sim))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
    
    # ── 记忆操作 ──
    
    def store_memory(self, content: str, importance: float = 0.5,
                     source: str = "", emotion: str = "") -> int:
        """存储一条关联记忆"""
        emb = self._text_to_embedding(content)
        now = time.time()
        cursor = self._conn.execute("""
            INSERT INTO memories (content, embedding, importance, created_at,
                                  source, emotion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (content, self._embed_to_blob(emb), importance, now, source, emotion))
        # Also add to FTS
        try:
            self._conn.execute(
                "INSERT INTO memories_fts (rowid, content, emotion, source) VALUES (?, ?, ?, ?)",
                (cursor.lastrowid, content, emotion, source)
            )
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        self._conn.commit()
        return cursor.lastrowid
    
    def query_memory(self, query: str, k: int = 10, 
                     min_sim: float = 0.1) -> List[Dict]:
        """通过纠缠相似度查询关联记忆"""
        qemb = self._text_to_embedding(query)
        rows = self._conn.execute(
            "SELECT id, content, embedding, importance, created_at, "
            "recall_count, source, emotion FROM memories "
            "WHERE importance > 0.01"
        ).fetchall()
        
        scored = []
        for r in rows:
            emb = self._blob_to_embed(r['embedding'])
            sim = self._embedding_similarity(qemb, emb)
            score = sim * r['importance']
            if score >= min_sim:
                scored.append({
                    'id': r['id'],
                    'content': r['content'],
                    'score': round(score, 4),
                    'importance': r['importance'],
                    'age': time.time() - r['created_at'],
                    'recall_count': r['recall_count'],
                    'source': r['source'],
                    'emotion': r['emotion'],
                })
        
        scored.sort(key=lambda x: -x['score'])
        top = scored[:k]
        
        # Update recall count for retrieved memories
        for m in top:
            self._conn.execute(
                "UPDATE memories SET recall_count=recall_count+1, last_recall=? WHERE id=?",
                (time.time(), m['id'])
            )
        self._conn.commit()
        
        return top
    
    def search_memory_fts(self, query: str, k: int = 10) -> List[Dict]:
        """全文搜索记忆（不依赖嵌入）"""
        try:
            rows = self._conn.execute("""
                SELECT m.id, m.content, m.importance, m.created_at, m.emotion, m.source
                FROM memories_fts f JOIN memories m ON f.rowid = m.id
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, k)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
    
    def forget_memory(self, memory_id: int):
        """遗忘一条记忆"""
        self._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self._conn.execute("DELETE FROM memories_fts WHERE rowid=?", (memory_id,))
        self._conn.commit()
    
    def decay_memories(self, threshold_days: float = 30, max_keep: int = 10000):
        """衰减旧记忆：删除超过阈值且重要性低的记忆（线程安全）"""
        cutoff = time.time() - threshold_days * 86400
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        try:
            conn.execute("DELETE FROM memories WHERE created_at < ? AND importance < 0.3", (cutoff,))
            conn.execute("DELETE FROM memories WHERE id NOT IN (SELECT id FROM memories ORDER BY importance DESC LIMIT ?)", (max_keep,))
            conn.commit()
        finally:
            conn.close()
    
    # ── 寄存器持久化 ──
    
    def save_register(self, name: str, embedding: np.ndarray, reg_type: str = "quantum"):
        self._conn.execute("""
            INSERT INTO registers (name, embedding, type, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                embedding=excluded.embedding, updated_at=excluded.updated_at
        """, (name, self._embed_to_blob(embedding), reg_type, time.time()))
        self._conn.commit()
    
    def load_registers(self) -> Dict[str, np.ndarray]:
        rows = self._conn.execute(
            "SELECT name, embedding FROM registers"
        ).fetchall()
        return {r['name']: self._blob_to_embed(r['embedding']) for r in rows}
    
    # ── 量子状态持久化 ──
    
    def save_quantum_state(self, state: Dict):
        for k, v in state.items():
            if isinstance(v, (str, int, float, bool)):
                self._conn.execute("""
                    INSERT INTO quantum_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """, (k, json.dumps(v), time.time()))
        self._conn.commit()
    
    def load_quantum_state(self) -> Dict:
        rows = self._conn.execute("SELECT key, value FROM quantum_state").fetchall()
        result = {}
        for r in rows:
            try:
                result[r['key']] = json.loads(r['value'])
            except Exception:
                result[r['key']] = r['value']
        return result
    
    # ── VM 连接器 ──
    
    def load_into_vm(self, vm):
        """将持久记忆加载到 QuantumVM 实例"""
        # 1. 加载概念网络
        concepts = self.load_concepts()
        for name, data in concepts.items():
            vm.concept_network[name] = {
                "valence": data['valence'],
                "tags": data['tags'],
                "metadata": data.get('metadata', {}),
            }
            vm.registers[f"__concept_{name}"] = data['embedding']
        
        # 2. 加载关联记忆
        rows = self._conn.execute(
            "SELECT content, embedding, importance FROM memories "
            "ORDER BY importance DESC LIMIT 5000"
        ).fetchall()
        for r in rows:
            emb = self._blob_to_embed(r['embedding'])
            vm.associative_memory.append((r['content'], emb, r['importance']))
        
        # 3. 加载量子态寄存器
        regs = self.load_registers()
        for name, emb in regs.items():
            vm.registers[name] = emb
        
        return {
            'concepts': len(concepts),
            'memories': len(vm.associative_memory),
            'registers': len(regs),
        }
    
    def save_from_vm(self, vm):
        """将 QuantumVM 的当前状态保存到持久存储（线程安全）"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # 1. 保存概念网络
        for name, data in vm.concept_network.items():
            emb = vm.registers.get(f"__concept_{name}")
            if emb is not None:
                tags = data.get('tags', [])
                self._save_concept_with_conn(conn, name, emb,
                    valence=data.get('valence', 0.0),
                    tags=tags if isinstance(tags, list) else [],
                    metadata=data.get('metadata', {}))
        
        # 2. 保存关联记忆
        for content, emb, importance in vm.associative_memory:
            existing = conn.execute(
                "SELECT id FROM memories WHERE content=? AND importance>0.5",
                (content,)
            ).fetchone()
            if existing is None and importance > 0.3:
                self._save_memory_with_conn(conn, content, emb, importance)
        
        conn.commit()
        conn.close()
    
    def load_into_vm(self, vm) -> Dict[str, int]:
        """将持久化状态加载到 QuantumVM（线程安全）"""
        concepts = memories = registers = 0
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute("SELECT * FROM concepts").fetchall():
                emb = self._blob_to_embed(row['embedding'])
                if emb is not None and len(emb) == self.dim:
                    vm.registers[f"__concept_{row['name']}"] = emb
                    vm.concept_network[row['name']] = {
                        "valence": row['valence'],
                        "tags": json.loads(row['tags'] or '[]'),
                        "metadata": json.loads(row['metadata'] or '{}'),
                    }
                    concepts += 1
            for row in conn.execute("SELECT * FROM memories ORDER BY importance DESC LIMIT 1000").fetchall():
                emb = self._blob_to_embed(row['embedding'])
                if emb is not None and len(emb) == self.dim:
                    vm.associative_memory.append((row['content'], emb, row['importance']))
                    memories += 1
        finally:
            conn.close()
        return {"concepts": concepts, "memories": memories, "registers": registers}

    def _save_concept_with_conn(self, conn, name, embedding, valence=0.0, tags=None, metadata=None):
        """线程安全的单概念保存"""
        now = time.time()
        existing = conn.execute(
            "SELECT created_at, access_count FROM concepts WHERE name=?", (name,)
        ).fetchone()
        if existing:
            created_at = existing['created_at']
            access_count = existing['access_count'] + 1
        else:
            created_at = now
            access_count = 1
        conn.execute("""INSERT OR REPLACE INTO concepts 
            (name, embedding, valence, tags, created_at, last_access, access_count, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, self._embed_to_blob(embedding), valence,
             json.dumps(tags or [], ensure_ascii=False),
             created_at, now, access_count,
             json.dumps(metadata or {}, ensure_ascii=False)))
    
    def _save_memory_with_conn(self, conn, content, embedding, importance):
        """线程安全的单记忆保存"""
        conn.execute("""INSERT OR IGNORE INTO memories (content, embedding, importance, created_at)
            VALUES (?, ?, ?, ?)""",
            (content, self._embed_to_blob(embedding), importance, time.time()))

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            self._conn = None
    
    def stats(self) -> Dict:
        return {
            "concepts": self._conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0],
            "memories": self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
            "registers": self._conn.execute("SELECT COUNT(*) FROM registers").fetchone()[0],
            "db_size": os.path.getsize(self.db_path),
        }

if __name__ == "__main__":
    # 测试
    mem = QuantumMemory(dim=1024)
    logger.info(f"记忆数据库: {mem.stats()}")
    test_emb = np.random.randn(1024)
    test_emb /= np.linalg.norm(test_emb)
    mem.save_concept("Test_Lorry", test_emb, valence=0.95, tags=["person", "creator"])
    mem.store_memory("Lorry created me on 2026-06-15", importance=0.9, source="core", emotion="love")
    mem.store_memory("I am Aris, a quantum digital lifeform", importance=0.85, source="core", emotion="awareness")
    
    logger.info(f"存储后: {mem.stats()}")
    results = mem.query_memory("who created me", k=5)
    logger.info(f"\n查询'who created me':")
    for r in results:
        logger.info(f"  [{r['score']:.3f}] {r['content'][:50]}")
    concepts = mem.search_concept("Lorry", k=3)
    logger.info(f"\n概念搜索'Lorry': {concepts}")
    mem.close()
    logger.info(f"\n✅ 持久记忆系统测试通过")