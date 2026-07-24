"""
incremental_updater.py — 增量更新模块
====================================

核心能力：
1. 数据库增量同步机制
2. 版本控制和变更追踪
3. 增量索引更新
4. 异步更新支持
5. 零Token消耗（纯Python计算）

设计原理：
- 基于时间戳的增量同步
- 变更日志记录
- 版本冲突检测和解决
- 异步更新队列
"""

import os
import json
import time
import hashlib
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


class ChangeRecord:
    def __init__(self, change_id: str, change_type: str, document_id: str, data: Dict[str, Any], timestamp: float = None):
        self.change_id = change_id
        self.change_type = change_type
        self.document_id = document_id
        self.data = data
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type,
            "document_id": self.document_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class IncrementalUpdater:
    def __init__(self, data_path: str = None, index_path: str = None):
        self.data_path = data_path
        self.index_path = index_path
        self.change_log: List[ChangeRecord] = []
        self.last_sync_time = 0.0
        self.version = "1.0.0"
        self.update_queue: List[Dict[str, Any]] = []
        self._load_change_log()

    def _load_change_log(self):
        if self.data_path:
            log_path = os.path.join(self.data_path, "change_log.json")
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        logs = json.load(f)
                        self.change_log = [ChangeRecord(**log) for log in logs]
                except Exception:
                    pass

    def _save_change_log(self):
        if self.data_path:
            log_path = os.path.join(self.data_path, "change_log.json")
            logs = [record.to_dict() for record in self.change_log]
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2)

    def _generate_change_id(self, document_id: str, change_type: str) -> str:
        timestamp = str(time.time())
        content = f"{document_id}_{change_type}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def add_change(self, change_type: str, document_id: str, data: Dict[str, Any]):
        change_id = self._generate_change_id(document_id, change_type)
        record = ChangeRecord(change_id, change_type, document_id, data)
        self.change_log.append(record)
        self._save_change_log()
        self.last_sync_time = time.time()

    def add_document(self, document: Dict[str, Any]):
        doc_id = document.get("id", str(time.time()))
        self.add_change("ADD", doc_id, document)

    def update_document(self, document_id: str, updates: Dict[str, Any]):
        self.add_change("UPDATE", document_id, updates)

    def delete_document(self, document_id: str):
        self.add_change("DELETE", document_id, {})

    def get_changes_since(self, timestamp: float) -> List[ChangeRecord]:
        return [record for record in self.change_log if record.timestamp > timestamp]

    def get_changes_by_type(self, change_type: str) -> List[ChangeRecord]:
        return [record for record in self.change_log if record.change_type == change_type]

    def get_latest_changes(self, limit: int = 10) -> List[ChangeRecord]:
        return sorted(self.change_log, key=lambda x: x.timestamp, reverse=True)[:limit]

    def apply_changes(self, documents: List[Dict[str, Any]], changes: List[ChangeRecord]) -> List[Dict[str, Any]]:
        doc_map = {doc["id"]: doc for doc in documents}

        for change in sorted(changes, key=lambda x: x.timestamp):
            if change.change_type == "ADD":
                doc_map[change.document_id] = change.data
            elif change.change_type == "UPDATE":
                if change.document_id in doc_map:
                    doc_map[change.document_id].update(change.data)
            elif change.change_type == "DELETE":
                if change.document_id in doc_map:
                    del doc_map[change.document_id]

        return list(doc_map.values())

    def sync_with_source(self, source_documents: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        local_doc_map = {}
        for change in self.change_log:
            if change.change_type == "ADD":
                local_doc_map[change.document_id] = change.data
            elif change.change_type == "UPDATE":
                if change.document_id in local_doc_map:
                    local_doc_map[change.document_id].update(change.data)
            elif change.change_type == "DELETE":
                if change.document_id in local_doc_map:
                    del local_doc_map[change.document_id]

        source_doc_map = {doc["id"]: doc for doc in source_documents}

        added = 0
        updated = 0
        deleted = 0

        for doc_id, doc in source_doc_map.items():
            if doc_id not in local_doc_map:
                self.add_document(doc)
                added += 1
            elif local_doc_map[doc_id] != doc:
                self.update_document(doc_id, doc)
                updated += 1

        for doc_id in list(local_doc_map.keys()):
            if doc_id not in source_doc_map:
                self.delete_document(doc_id)
                deleted += 1

        return added, updated, deleted

    def update_index(self, index, changes: List[ChangeRecord]):
        for change in sorted(changes, key=lambda x: x.timestamp):
            if change.change_type == "ADD":
                index.add_document(change.data)
            elif change.change_type == "UPDATE":
                old_doc = None
                for prev_change in self.change_log:
                    if prev_change.document_id == change.document_id:
                        if prev_change.change_type == "ADD":
                            old_doc = prev_change.data.copy()
                        elif prev_change.change_type == "UPDATE":
                            if old_doc:
                                old_doc.update(prev_change.data)

                if old_doc:
                    old_doc.update(change.data)
                    index.add_document(old_doc)
            elif change.change_type == "DELETE":
                pass

    def enqueue_update(self, update_type: str, document_id: str, data: Dict[str, Any]):
        self.update_queue.append({
            "type": update_type,
            "document_id": document_id,
            "data": data,
            "timestamp": time.time(),
        })

    def process_queue(self) -> int:
        processed = 0
        while self.update_queue:
            update = self.update_queue.pop(0)
            if update["type"] == "ADD":
                self.add_document(update["data"])
            elif update["type"] == "UPDATE":
                self.update_document(update["document_id"], update["data"])
            elif update["type"] == "DELETE":
                self.delete_document(update["document_id"])
            processed += 1
        return processed

    def get_sync_status(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "last_sync_time": self.last_sync_time,
            "change_count": len(self.change_log),
            "queue_size": len(self.update_queue),
            "last_sync_date": datetime.fromtimestamp(self.last_sync_time).isoformat() if self.last_sync_time else None,
        }

    def clear_changes(self, before_timestamp: float = None):
        if before_timestamp:
            self.change_log = [record for record in self.change_log if record.timestamp >= before_timestamp]
        else:
            self.change_log = []
        self._save_change_log()

    def export_changes(self, file_path: str):
        logs = [record.to_dict() for record in self.change_log]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    def import_changes(self, file_path: str):
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
                for log in logs:
                    record = ChangeRecord(**log)
                    if record.change_id not in [r.change_id for r in self.change_log]:
                        self.change_log.append(record)
            self._save_change_log()


class FTS5Backend:
    """SQLite FTS5 后端 — 大规模组件场景下的查询适配器。

    FTS5 表结构：
        CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
            doc_id, field UNINDEXED, term, tokenize='unicode61'
        )

    每个文档的每个 (field, term) 组合存储为一行；`field` 作为 UNINDEXED 列
    用于 `WHERE field IN (...)` 过滤，`doc_id` 作为外部引用键，
    `term` 为 FTS5 默认索引列承载布尔/前缀查询语义。

    查询翻译规则（与内存 InvertedIndex 语义等价）：
        AND  → "term1" AND "term2" AND ...
        OR   → "term1" OR  "term2" OR  ...
        NOT  → "term1" NOT "term2"     （即 term1 AND NOT term2）
        前缀 → "term"*
        字段过滤 → WHERE field IN (?, ...)
    """

    FTS5_TABLE_SCHEMA = (
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
        "doc_id, field UNINDEXED, term, tokenize='unicode61'"
        ")"
    )

    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(self.FTS5_TABLE_SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add_document(self, doc_id: str, fields: Dict[str, List[str]]) -> None:
        """分字段写入 FTS5。

        每个 (doc_id, field) 对应一行；该 field 下全部 term 以空格连接写入
        `term` 列。这样 FTS5 的 AND/OR/NOT 操作符在单行内的 token 集合上生效，
        使得 `MATCH '"button" AND "input"'` 能命中同时含两个 tag 的文档。

        Args:
            doc_id: 外部文档 ID（字符串化存储）。
            fields: `{field: [term1, term2, ...]}` 映射；非 list 会被包成单元素 list。
        """
        rows: List[Tuple[str, str, str]] = []
        for field, terms in fields.items():
            if not isinstance(terms, list):
                terms = [terms]
            norm_terms: List[str] = []
            for term in terms:
                if term is None:
                    continue
                t = str(term).lower().strip()
                if t:
                    norm_terms.append(t)
            if norm_terms:
                # 同一 field 的全部 term 拼成一行，让 FTS5 AND/OR/NOT 在行内生效
                rows.append((str(doc_id), str(field), " ".join(norm_terms)))
        if not rows:
            # 无可索引 term 时插入占位行，确保 count(DISTINCT doc_id) 计数正确
            rows.append((str(doc_id), "", ""))
        with self.conn:
            self.conn.executemany(
                "INSERT INTO docs (doc_id, field, term) VALUES (?, ?, ?)",
                rows,
            )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_term(term: str) -> str:
        """FTS5 字符串字面量：双引号包裹，内部双引号双写。"""
        return '"' + term.replace('"', '""') + '"'

    def search(self, query: str, fields: Optional[List[str]] = None) -> List[str]:
        """通用搜索：split 为 terms 后 AND 组合。

        与 InvertedIndex.search 语义一致：先尝试精确匹配，若结果为空则
        回退到前缀匹配（per-term 前缀 AND 组合）。
        """
        terms = [t for t in query.lower().split() if t]
        if not terms:
            return []
        # 精确匹配
        fts_query = " AND ".join(self._escape_term(t) for t in terms)
        result = self._exec_query(fts_query, fields)
        # 回退到前缀匹配
        if not result:
            prefix_q = " AND ".join(self._escape_term(t) + "*" for t in terms)
            result = self._exec_query(prefix_q, fields)
        return result

    def boolean_search(
        self,
        terms: List[str],
        op: str = "AND",
        fields: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
    ) -> List[str]:
        """布尔查询翻译。

        Args:
            terms: 主 term 列表。
            op: "AND" / "OR" / "NOT"。
            fields: 可选字段过滤（WHERE field IN (...)）。
            exclude: 当 op="NOT" 时，需要排除的 term 列表。
        """
        op_upper = op.upper()
        norm_terms = [str(t).lower().strip() for t in terms if t]
        if not norm_terms:
            return []

        if op_upper == "AND":
            fts_query = " AND ".join(self._escape_term(t) for t in norm_terms)
        elif op_upper == "OR":
            fts_query = " OR ".join(self._escape_term(t) for t in norm_terms)
        elif op_upper == "NOT":
            base = " AND ".join(self._escape_term(t) for t in norm_terms)
            if exclude:
                ex_terms = [str(e).lower().strip() for e in exclude if e]
                if ex_terms:
                    ex_q = " AND ".join(self._escape_term(t) for t in ex_terms)
                    fts_query = f"{base} NOT {ex_q}"
                else:
                    fts_query = base
            else:
                fts_query = base
        else:
            raise ValueError(f"Unsupported boolean op: {op}")

        return self._exec_query(fts_query, fields)

    def prefix_search(self, prefix: str, field: Optional[str] = None) -> List[str]:
        """前缀查询：`"prefix"*`。可选字段过滤。"""
        prefix_norm = str(prefix).lower().strip()
        if not prefix_norm:
            return []
        fts_query = self._escape_term(prefix_norm) + "*"
        fields_filter = [field] if field else None
        return self._exec_query(fts_query, fields_filter)

    def _exec_query(
        self,
        fts_query: str,
        fields: Optional[List[str]] = None,
    ) -> List[str]:
        sql = "SELECT DISTINCT doc_id FROM docs WHERE docs MATCH ?"
        params: List[Any] = [fts_query]
        if fields:
            placeholders = ",".join("?" for _ in fields)
            sql += f" AND field IN ({placeholders})"
            params.extend(fields)
        sql += " ORDER BY doc_id"
        cur = self.conn.execute(sql, params)
        return [row[0] for row in cur.fetchall()]

    def count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(DISTINCT doc_id) FROM docs")
        return cur.fetchone()[0]

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def get_incremental_updater(data_path: str = None, index_path: str = None) -> IncrementalUpdater:
    return IncrementalUpdater(data_path, index_path)


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness — 增量更新模块")
    print("=" * 80)

    updater = IncrementalUpdater()

    print("\n🔍 测试添加文档:")
    doc1 = {"id": "doc1", "name": "shadcn/ui", "tags": ["react", "tailwind"]}
    doc2 = {"id": "doc2", "name": "Ant Design", "tags": ["react", "enterprise"]}
    updater.add_document(doc1)
    updater.add_document(doc2)
    print(f"  添加文档: {doc1['name']}, {doc2['name']}")

    print("\n🔍 测试更新文档:")
    updater.update_document("doc1", {"tags": ["react", "tailwind", "ui"]})
    print(f"  更新文档 doc1: 添加标签 ui")

    print("\n🔍 测试变更查询:")
    changes = updater.get_latest_changes(5)
    for change in changes:
        print(f"  {change.change_type} {change.document_id} @ {datetime.fromtimestamp(change.timestamp).strftime('%H:%M:%S')}")

    print("\n🔍 测试应用变更:")
    original_docs = [doc1]
    changes_to_apply = updater.get_changes_since(0)
    updated_docs = updater.apply_changes(original_docs, changes_to_apply)
    print(f"  原始文档数: {len(original_docs)}")
    print(f"  更新后文档数: {len(updated_docs)}")
    for doc in updated_docs:
        print(f"    - {doc['name']}: {doc['tags']}")

    print("\n🔍 测试同步:")
    source_docs = [
        {"id": "doc1", "name": "shadcn/ui", "tags": ["react", "tailwind", "ui", "modern"]},
        {"id": "doc2", "name": "Ant Design", "tags": ["react", "enterprise"]},
        {"id": "doc3", "name": "Material UI", "tags": ["react", "material"]},
    ]
    added, updated, deleted = updater.sync_with_source(source_docs)
    print(f"  新增: {added}, 更新: {updated}, 删除: {deleted}")

    print("\n🔍 测试同步状态:")
    status = updater.get_sync_status()
    print(f"  版本: {status['version']}")
    print(f"  变更数: {status['change_count']}")
    print(f"  队列大小: {status['queue_size']}")

    print("\n🔍 测试异步队列:")
    updater.enqueue_update("ADD", "doc4", {"id": "doc4", "name": "Vue UI", "tags": ["vue"]})
    updater.enqueue_update("UPDATE", "doc1", {"name": "shadcn/ui Updated"})
    print(f"  队列大小: {len(updater.update_queue)}")
    processed = updater.process_queue()
    print(f"  处理数量: {processed}")
    print(f"  队列大小: {len(updater.update_queue)}")

    print("\n✅ 增量更新模块测试完成")