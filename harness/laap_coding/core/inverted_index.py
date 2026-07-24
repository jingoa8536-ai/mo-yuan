"""
inverted_index.py — 倒排索引模块
================================

核心能力：
1. 构建倒排索引实现 O(log n) 查询
2. 支持多字段索引（标签、名称、组件、领域）
3. 前缀匹配和模糊匹配
4. 索引优化和压缩
5. 零Token消耗（纯Python计算）

设计原理：
- 倒排索引：term → [document_ids]
- 二分查找加速查询
- 索引合并优化
- 支持布尔查询（AND/OR/NOT）

LSM-Tree 写入路径（use_lsm=True）：
- WAL（Write-Ahead Log）保证持久性
- MemTable 内存有序缓冲（容量阈值 1000）
- SSTable 磁盘有序段文件 + 二分查找
- 将插入从 O(n) 降到 O(log n) 摊销
"""

import os
import json
import bisect
import pickle
import time
import tempfile
from typing import Dict, Any, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# LSM-Tree 组件：WAL / MemTable / SSTable
# ---------------------------------------------------------------------------

class WAL:
    """Write-Ahead Log — append-only 日志，保证写入持久性。

    每条记录以单行 JSON 写入，append 后调用 fsync 刷盘。
    崩溃后通过 recover() 读取全部记录进行重放。
    """

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # 以二进制 append 模式打开；默认缓冲（8KB）以降低批量写入的 syscall 开销，
        # 持久性由显式 fsync() 保证
        self._file = open(path, "ab")

    def append(self, record: dict, sync: bool = True) -> None:
        """追加一条记录。sync=True 时调用 fsync 强制刷盘。"""
        line = json.dumps(record, ensure_ascii=False) + "\n"
        data = line.encode("utf-8")
        self._file.write(data)
        if sync:
            self.fsync()

    def fsync(self) -> None:
        """强制将缓冲区数据刷到磁盘。"""
        self._file.flush()
        try:
            os.fsync(self._file.fileno())
        except OSError:
            # 某些平台（如内存盘）不支持 fsync，忽略
            pass

    def recover(self) -> List[dict]:
        """读取全部 WAL 记录。损坏的末尾行（崩溃中途写入）会被跳过。"""
        try:
            self._file.close()
        except Exception:
            pass
        records: List[dict] = []
        if not os.path.exists(self.path):
            self._file = open(self.path, "ab")
            return records
        with open(self.path, "rb") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line.decode("utf-8")))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # 崩溃中途写入的不完整行，跳过
                    continue
        self._file = open(self.path, "ab")
        return records

    def truncate(self) -> None:
        """清空 WAL（成功 checkpoint 后调用）。"""
        try:
            self._file.close()
        except Exception:
            pass
        open(self.path, "wb").close()
        self._file = open(self.path, "ab")

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass


class MemTable:
    """内存有序缓冲表。

    内部以 `field -> term -> Set[doc_id]` 结构存储。
    使用 set 实现 O(1) 插入与去重；flush 时排序输出。
    容量阈值 MAX_SIZE=1000（按 (field, term, doc_id) 元组计数）。
    """

    MAX_SIZE = 1000

    def __init__(self):
        # field_key -> term -> set(doc_id)
        self._data: Dict[str, Dict[str, Set[int]]] = {}
        self._size = 0  # (field, term, doc_id) 元组总数
        self._doc_ids: Set[int] = set()

    @staticmethod
    def _field_key(field: Optional[str]) -> str:
        return field if field is not None else "__global__"

    def add(self, term: str, doc_id: int, field: Optional[str] = None) -> None:
        fk = self._field_key(field)
        bucket = self._data.setdefault(fk, {})
        postings = bucket.setdefault(term, set())
        if doc_id not in postings:
            postings.add(doc_id)
            self._size += 1
        self._doc_ids.add(doc_id)

    @property
    def size(self) -> int:
        return self._size

    @property
    def doc_count(self) -> int:
        return len(self._doc_ids)

    def is_full(self) -> bool:
        return self._size >= self.MAX_SIZE

    def get(self, term: str, field: Optional[str] = None) -> List[int]:
        fk = self._field_key(field)
        bucket = self._data.get(fk, {})
        return sorted(bucket.get(term, set()))

    def has_term(self, term: str, field: Optional[str] = None) -> bool:
        fk = self._field_key(field)
        return term in self._data.get(fk, {})

    def terms(self, field: Optional[str] = None) -> List[str]:
        fk = self._field_key(field)
        return sorted(self._data.get(fk, {}).keys())

    def flush_to_sstable(self, path: str) -> "SSTable":
        """将 MemTable 内容写入 SSTable 文件，并清空自身。"""
        flat: Dict[str, List[int]] = {}
        for fk, bucket in self._data.items():
            for term, doc_ids in bucket.items():
                key = f"{fk}||{term}"
                flat[key] = sorted(doc_ids)
        # 按键排序输出，确保 SSTable 内有序以支持二分查找
        sorted_flat = dict(sorted(flat.items()))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted_flat, f, ensure_ascii=False)
        self.clear()
        return SSTable(path)

    def clear(self) -> None:
        self._data = {}
        self._size = 0
        self._doc_ids = set()


class SSTable:
    """磁盘有序段文件。

    文件格式：JSON 对象，键为 `field||term`，值为有序 doc_id 列表。
    键按字典序排序存储，支持二分查找。
    """

    def __init__(self, path: str):
        self.path = path
        self._data_cache: Optional[Dict[str, List[int]]] = None
        self._terms_cache: Optional[List[str]] = None

    def _load(self) -> None:
        if self._data_cache is None:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data_cache = json.load(f)
            self._terms_cache = sorted(self._data_cache.keys())

    @staticmethod
    def _key(term: str, field: Optional[str]) -> str:
        fk = field if field is not None else "__global__"
        return f"{fk}||{term}"

    def get(self, term: str, field: Optional[str] = None) -> List[int]:
        self._load()
        key = self._key(term, field)
        idx = bisect.bisect_left(self._terms_cache, key)
        if idx < len(self._terms_cache) and self._terms_cache[idx] == key:
            return list(self._data_cache[key])
        return []

    def has_term(self, term: str, field: Optional[str] = None) -> bool:
        self._load()
        key = self._key(term, field)
        idx = bisect.bisect_left(self._terms_cache, key)
        return idx < len(self._terms_cache) and self._terms_cache[idx] == key

    def prefix_search(self, prefix: str, field: Optional[str] = None) -> List[int]:
        self._load()
        prefix_full = self._key(prefix, field)
        matched: Set[int] = set()
        # 利用键有序性，二分定位起始位置后顺序扫描
        start = bisect.bisect_left(self._terms_cache, prefix_full)
        for key in self._terms_cache[start:]:
            if not key.startswith(prefix_full):
                # 因为有序，一旦不再匹配前缀即可停止
                # 但仅当 key > prefix_full 且不以 prefix_full 开头时才停
                if key[: len(prefix_full)] > prefix_full:
                    break
                continue
            matched.update(self._data_cache[key])
        return sorted(matched)

    def all_keys(self) -> List[str]:
        self._load()
        return list(self._terms_cache)

    def merge(self, other: "SSTable", output_path: str) -> "SSTable":
        """合并两张 SSTable，输出新的 SSTable（postings 取并集、去重、有序）。"""
        self._load()
        other._load()
        merged: Dict[str, List[int]] = {}
        all_keys = set(self._data_cache.keys()) | set(other._data_cache.keys())
        for key in all_keys:
            a = self._data_cache.get(key, [])
            b = other._data_cache.get(key, [])
            merged[key] = SSTable._merge_sorted_int(a, b)
        merged_sorted = dict(sorted(merged.items()))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_sorted, f, ensure_ascii=False)
        return SSTable(output_path)

    @staticmethod
    def _merge_sorted_int(a: List[int], b: List[int]) -> List[int]:
        result: List[int] = []
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i] == b[j]:
                result.append(a[i])
                i += 1
                j += 1
            elif a[i] < b[j]:
                result.append(a[i])
                i += 1
            else:
                result.append(b[j])
                j += 1
        result.extend(a[i:])
        result.extend(b[j:])
        return result


# ---------------------------------------------------------------------------
# InvertedIndex —— 同时支持 legacy bisect 路径与 LSM-Tree 路径
# ---------------------------------------------------------------------------

class InvertedIndex:
    def __init__(self, use_lsm: bool = False, lsm_dir: Optional[str] = None):
        self.index: Dict[str, List[int]] = {}
        self.document_count = 0
        self.field_indices: Dict[str, Dict[str, List[int]]] = {}
        self.document_metadata: List[Dict[str, Any]] = []
        self.build_time = 0.0

        # LSM-Tree 模式开关（默认 False，保持向后兼容）
        self.use_lsm = use_lsm
        self._default_fields = ["tags", "name", "components", "domain"]

        if use_lsm:
            if lsm_dir is None:
                lsm_dir = tempfile.mkdtemp(prefix="laap_lsm_")
            self.lsm_dir = lsm_dir
            os.makedirs(self.lsm_dir, exist_ok=True)
            self._sstables_dir = os.path.join(self.lsm_dir, "sstables")
            os.makedirs(self._sstables_dir, exist_ok=True)
            self._wal_path = os.path.join(self.lsm_dir, "wal.log")
            self.wal = WAL(self._wal_path)
            self.memtable = MemTable()
            self._sstables: List[SSTable] = []
            self._sstable_seq = 0
            self._load_existing_sstables()

    # ------------------------------------------------------------------
    # 既有 build_from_documents / search / boolean_search 等保持原语义
    # ------------------------------------------------------------------

    def build_from_documents(self, documents: List[Dict[str, Any]], fields: List[str] = None):
        start_time = time.time()

        if fields is None:
            fields = ["tags", "name", "components", "domain"]

        self.document_count = len(documents)
        self.document_metadata = documents
        self.index = {}
        self.field_indices = {field: {} for field in fields}

        for doc_id, doc in enumerate(documents):
            for field in fields:
                values = doc.get(field, [])
                if not isinstance(values, list):
                    values = [values]

                for value in values:
                    if value is None:
                        continue
                    
                    term = str(value).lower().strip()
                    if not term:
                        continue

                    if term not in self.index:
                        self.index[term] = []
                    if doc_id not in self.index[term]:
                        bisect.insort(self.index[term], doc_id)

                    if field not in self.field_indices:
                        self.field_indices[field] = {}
                    if term not in self.field_indices[field]:
                        self.field_indices[field][term] = []
                    if doc_id not in self.field_indices[field][term]:
                        bisect.insort(self.field_indices[field][term], doc_id)

        self.build_time = time.time() - start_time

    def search(self, query: str, fields: List[str] = None) -> List[int]:
        if self.use_lsm:
            return self._search_lsm(query, fields)

        query_terms = query.lower().split()

        if fields:
            results = []
            for field in fields:
                field_results = self._search_field(query_terms, field)
                results = self._merge_or(results, field_results)
            return sorted(results)
        else:
            return self._search_all(query_terms)

    def _search_field(self, terms: List[str], field: str) -> List[int]:
        if field not in self.field_indices:
            return []

        field_index = self.field_indices[field]
        results = None

        for term in terms:
            if term in field_index:
                doc_ids = field_index[term]
            else:
                doc_ids = self._prefix_search(term, field_index)

            if results is None:
                results = doc_ids
            else:
                results = self._merge_and(results, doc_ids)

        return results if results else []

    def _search_all(self, terms: List[str]) -> List[int]:
        results = None

        for term in terms:
            if term in self.index:
                doc_ids = self.index[term]
            else:
                doc_ids = self._prefix_search_all(term)

            if results is None:
                results = doc_ids
            else:
                results = self._merge_and(results, doc_ids)

        return results if results else []

    def _prefix_search(self, prefix: str, field_index: Dict[str, List[int]]) -> List[int]:
        matched_docs = set()
        for term in field_index:
            if term.startswith(prefix):
                matched_docs.update(field_index[term])
        return sorted(list(matched_docs))

    def _prefix_search_all(self, prefix: str) -> List[int]:
        matched_docs = set()
        for term in self.index:
            if term.startswith(prefix):
                matched_docs.update(self.index[term])
        return sorted(list(matched_docs))

    def _merge_and(self, list_a: List[int], list_b: List[int]) -> List[int]:
        result = []
        i = j = 0
        while i < len(list_a) and j < len(list_b):
            if list_a[i] == list_b[j]:
                result.append(list_a[i])
                i += 1
                j += 1
            elif list_a[i] < list_b[j]:
                i += 1
            else:
                j += 1
        return result

    def _merge_or(self, list_a: List[int], list_b: List[int]) -> List[int]:
        result = []
        i = j = 0
        while i < len(list_a) and j < len(list_b):
            if list_a[i] == list_b[j]:
                result.append(list_a[i])
                i += 1
                j += 1
            elif list_a[i] < list_b[j]:
                result.append(list_a[i])
                i += 1
            else:
                result.append(list_b[j])
                j += 1
        result.extend(list_a[i:])
        result.extend(list_b[j:])
        return result

    def _merge_not(self, list_a: List[int], list_b: List[int]) -> List[int]:
        result = []
        i = j = 0
        while i < len(list_a):
            if j >= len(list_b) or list_a[i] < list_b[j]:
                result.append(list_a[i])
                i += 1
            elif list_a[i] == list_b[j]:
                i += 1
                j += 1
            else:
                j += 1
        return result

    def boolean_search(self, query: str) -> List[int]:
        if self.use_lsm:
            return self._boolean_search_lsm(query)

        tokens = query.lower().split()
        operators = {"and", "or", "not"}

        if not tokens:
            return []

        result = None
        current_operator = "and"

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token in operators:
                current_operator = token
                i += 1
                continue

            if token in self.index:
                doc_ids = self.index[token]
            else:
                doc_ids = self._prefix_search_all(token)

            if result is None:
                result = doc_ids
            else:
                if current_operator == "and":
                    result = self._merge_and(result, doc_ids)
                elif current_operator == "or":
                    result = self._merge_or(result, doc_ids)
                elif current_operator == "not":
                    result = self._merge_not(result, doc_ids)

            current_operator = "and"
            i += 1

        return result if result else []

    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        if 0 <= doc_id < len(self.document_metadata):
            return self.document_metadata[doc_id]
        return None

    def get_documents(self, doc_ids: List[int]) -> List[Dict[str, Any]]:
        return [self.get_document(doc_id) for doc_id in doc_ids if self.get_document(doc_id)]

    def get_term_frequency(self, term: str) -> int:
        term = term.lower()
        if self.use_lsm:
            return len(self._lookup_lsm(term, field=None))
        return len(self.index.get(term, []))

    def get_field_term_frequency(self, term: str, field: str) -> int:
        term = term.lower()
        if self.use_lsm:
            return len(self._lookup_lsm(term, field=field))
        field_index = self.field_indices.get(field, {})
        return len(field_index.get(term, []))

    def get_top_terms(self, field: str = None, limit: int = 10) -> List[Tuple[str, int]]:
        if self.use_lsm:
            # 聚合 MemTable + 全部 SSTable 的词频
            counter: Dict[str, int] = {}
            for term in self.memtable.terms(field=field):
                counter[term] = len(self._lookup_lsm(term, field=field))
            for sst in self._sstables:
                for key in sst.all_keys():
                    fk, _, term = key.partition("||")
                    if field is None and fk != "__global__":
                        continue
                    if field is not None and fk != field:
                        continue
                    counter[term] = counter.get(term, 0) + len(sst.get(term, field=field))
            ranked = sorted(counter.items(), key=lambda x: x[1], reverse=True)
            return ranked[:limit]

        if field and field in self.field_indices:
            index = self.field_indices[field]
        else:
            index = self.index

        term_counts = [(term, len(doc_ids)) for term, doc_ids in index.items()]
        term_counts.sort(key=lambda x: x[1], reverse=True)
        return term_counts[:limit]

    def has_term(self, term: str) -> bool:
        term = term.lower()
        if self.use_lsm:
            return self._has_term_lsm(term, field=None)
        return term in self.index

    def get_unique_term_count(self) -> int:
        if self.use_lsm:
            return len(self._collect_all_terms(field=None))
        return len(self.index)

    def get_field_unique_term_count(self, field: str) -> int:
        if self.use_lsm:
            return len(self._collect_all_terms(field=field))
        if field in self.field_indices:
            return len(self.field_indices[field])
        return 0

    def _collect_all_terms(self, field: Optional[str]) -> Set[str]:
        terms: Set[str] = set()
        for t in self.memtable.terms(field=field):
            terms.add(t)
        for sst in self._sstables:
            for key in sst.all_keys():
                fk, _, t = key.partition("||")
                target_fk = field if field is not None else "__global__"
                if fk == target_fk:
                    terms.add(t)
        return terms

    def optimize(self):
        if self.use_lsm:
            # 合并所有 SSTable 为一张，减少读放大
            if not self._sstables:
                return
            merged = self._sstables[0]
            for sst in self._sstables[1:]:
                tmp_path = os.path.join(
                    self._sstables_dir, f"sstable_merge_{self._sstable_seq:08d}.json"
                )
                self._sstable_seq += 1
                merged = merged.merge(sst, tmp_path)
            # 保留合并后的 SSTable，删除旧文件
            for sst in self._sstables:
                if sst.path != merged.path and os.path.exists(sst.path):
                    try:
                        os.remove(sst.path)
                    except OSError:
                        pass
            self._sstables = [merged]
            return

        for term in self.index:
            self.index[term] = sorted(list(set(self.index[term])))

        for field in self.field_indices:
            for term in self.field_indices[field]:
                self.field_indices[field][term] = sorted(list(set(self.field_indices[field][term])))

    def save(self, path: str):
        data = {
            "index": self.index,
            "document_count": self.document_count,
            "field_indices": self.field_indices,
            "document_metadata": self.document_metadata,
            "build_time": self.build_time,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.index = data.get("index", {})
        self.document_count = data.get("document_count", 0)
        self.field_indices = data.get("field_indices", {})
        self.document_metadata = data.get("document_metadata", [])
        self.build_time = data.get("build_time", 0.0)

    # ------------------------------------------------------------------
    # 写入路径：add_document / batch_add
    # ------------------------------------------------------------------

    def add_document(self, doc: Dict[str, Any], fields: List[str] = None):
        if fields is None:
            fields = self._default_fields

        if not self.use_lsm:
            self._add_document_legacy(doc, fields)
            return

        # LSM 路径：WAL → MemTable → SSTable
        doc_id = self.document_count
        self.document_metadata.append(doc)
        self.document_count += 1

        self.wal.append(
            {"doc_id": doc_id, "doc": doc, "fields": fields},
            sync=True,
        )
        self._add_to_memtable(doc_id, doc, fields)
        if self.memtable.is_full():
            self._flush_memtable()

    def _add_document_legacy(self, doc: Dict[str, Any], fields: List[str]):
        doc_id = self.document_count
        self.document_metadata.append(doc)
        self.document_count += 1

        for field in fields:
            values = doc.get(field, [])
            if not isinstance(values, list):
                values = [values]

            for value in values:
                if value is None:
                    continue

                term = str(value).lower().strip()
                if not term:
                    continue

                if term not in self.index:
                    self.index[term] = []
                if doc_id not in self.index[term]:
                    bisect.insort(self.index[term], doc_id)

                if field not in self.field_indices:
                    self.field_indices[field] = {}
                if term not in self.field_indices[field]:
                    self.field_indices[field][term] = []
                if doc_id not in self.field_indices[field][term]:
                    bisect.insort(self.field_indices[field][term], doc_id)

    def batch_add(self, docs: List[Dict[str, Any]], fields: List[str] = None) -> None:
        """批量入库接口。

        LSM 模式下：批量追加 WAL（不每条 fsync，仅批次末尾 fsync 一次），
        MemTable 满则 flush，显著降低单条 fsync 开销。
        非 LSM 模式下：等价于循环调用 add_document。
        """
        if fields is None:
            fields = self._default_fields

        if not self.use_lsm:
            for doc in docs:
                self._add_document_legacy(doc, fields)
            return

        for doc in docs:
            doc_id = self.document_count
            self.document_metadata.append(doc)
            self.document_count += 1
            # 批量写入时不逐条 fsync，仅写文件缓冲
            self.wal.append(
                {"doc_id": doc_id, "doc": doc, "fields": fields},
                sync=False,
            )
            self._add_to_memtable(doc_id, doc, fields)
            if self.memtable.is_full():
                self._flush_memtable()
        # 批次结束统一 fsync
        self.wal.fsync()

    # ------------------------------------------------------------------
    # LSM 内部辅助
    # ------------------------------------------------------------------

    def _add_to_memtable(self, doc_id: int, doc: Dict[str, Any], fields: List[str]):
        for field in fields:
            values = doc.get(field, [])
            if not isinstance(values, list):
                values = [values]
            for value in values:
                if value is None:
                    continue
                term = str(value).lower().strip()
                if not term:
                    continue
                # 全局索引
                self.memtable.add(term, doc_id, field=None)
                # 字段索引
                self.memtable.add(term, doc_id, field=field)

    def _flush_memtable(self) -> None:
        if self.memtable.size == 0:
            return
        path = os.path.join(self._sstables_dir, f"sstable_{self._sstable_seq:08d}.json")
        self._sstable_seq += 1
        sstable = self.memtable.flush_to_sstable(path)
        self._sstables.append(sstable)

    def flush(self) -> None:
        """强制将 MemTable 落盘为 SSTable，并对 WAL 做 fsync。"""
        if not self.use_lsm:
            return
        self._flush_memtable()
        self.wal.fsync()

    def _load_existing_sstables(self) -> None:
        if not os.path.isdir(self._sstables_dir):
            return
        for fname in sorted(os.listdir(self._sstables_dir)):
            if not (fname.startswith("sstable_") and fname.endswith(".json")):
                continue
            path = os.path.join(self._sstables_dir, fname)
            self._sstables.append(SSTable(path))
            try:
                seq_str = fname[len("sstable_"):-len(".json")]
                seq = int(seq_str)
                if seq >= self._sstable_seq:
                    self._sstable_seq = seq + 1
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # 崩溃恢复
    # ------------------------------------------------------------------

    def recover_from_wal(self) -> int:
        """从 WAL 重放未持久化的 postings。

        - 读取 WAL 全部记录
        - 按 doc_id 去重（同一 doc_id 取最后一条）
        - 重放到 MemTable，满则 flush
        - 完成后清空 WAL（数据已进入 SSTable / MemTable）
        返回去重后重放的文档数。
        """
        if not self.use_lsm:
            return 0

        records = self.wal.recover()
        # 按 doc_id 去重，保留最后一条
        seen: Dict[int, dict] = {}
        for record in records:
            doc_id = record.get("doc_id")
            if doc_id is None:
                continue
            seen[doc_id] = record

        for doc_id in sorted(seen.keys()):
            record = seen[doc_id]
            doc = record.get("doc", {}) or {}
            fields = record.get("fields", self._default_fields)
            # 恢复 document_metadata（处理可能的空洞）
            while len(self.document_metadata) <= doc_id:
                self.document_metadata.append(None)
            self.document_metadata[doc_id] = doc
            if doc_id >= self.document_count:
                self.document_count = doc_id + 1
            self._add_to_memtable(doc_id, doc, fields)
            if self.memtable.is_full():
                self._flush_memtable()

        # 重放完成后 flush 残留 MemTable，并清空 WAL
        self._flush_memtable()
        self.wal.truncate()
        return len(seen)

    # ------------------------------------------------------------------
    # LSM 查询路径
    # ------------------------------------------------------------------

    def _search_lsm(self, query: str, fields: List[str] = None) -> List[int]:
        query_terms = query.lower().split()
        if not query_terms:
            return []
        if fields:
            results: List[int] = []
            for field in fields:
                field_results = self._search_field_lsm(query_terms, field)
                results = self._merge_or(results, field_results)
            return sorted(results)
        return self._search_all_lsm(query_terms)

    def _search_field_lsm(self, terms: List[str], field: str) -> List[int]:
        results = None
        for term in terms:
            if self._has_term_lsm(term, field=field):
                doc_ids = self._lookup_lsm(term, field=field)
            else:
                doc_ids = self._prefix_search_lsm(term, field=field)
            if results is None:
                results = doc_ids
            else:
                results = self._merge_and(results, doc_ids)
        return results if results else []

    def _search_all_lsm(self, terms: List[str]) -> List[int]:
        results = None
        for term in terms:
            if self._has_term_lsm(term, field=None):
                doc_ids = self._lookup_lsm(term, field=None)
            else:
                doc_ids = self._prefix_search_lsm(term, field=None)
            if results is None:
                results = doc_ids
            else:
                results = self._merge_and(results, doc_ids)
        return results if results else []

    def _has_term_lsm(self, term: str, field: Optional[str] = None) -> bool:
        if self.memtable.has_term(term, field=field):
            return True
        for sst in self._sstables:
            if sst.has_term(term, field=field):
                return True
        return False

    def _lookup_lsm(self, term: str, field: Optional[str] = None) -> List[int]:
        result = list(self.memtable.get(term, field=field))
        for sst in self._sstables:
            sst_results = sst.get(term, field=field)
            if sst_results:
                result = self._merge_sorted_int(result, sst_results)
        return result

    def _prefix_search_lsm(self, prefix: str, field: Optional[str] = None) -> List[int]:
        matched: Set[int] = set()
        for term in self.memtable.terms(field=field):
            if term.startswith(prefix):
                matched.update(self.memtable.get(term, field=field))
        for sst in self._sstables:
            matched.update(sst.prefix_search(prefix, field=field))
        return sorted(matched)

    def _boolean_search_lsm(self, query: str) -> List[int]:
        tokens = query.lower().split()
        operators = {"and", "or", "not"}
        if not tokens:
            return []
        result = None
        current_operator = "and"
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in operators:
                current_operator = token
                i += 1
                continue
            if self._has_term_lsm(token, field=None):
                doc_ids = self._lookup_lsm(token, field=None)
            else:
                doc_ids = self._prefix_search_lsm(token, field=None)
            if result is None:
                result = doc_ids
            else:
                if current_operator == "and":
                    result = self._merge_and(result, doc_ids)
                elif current_operator == "or":
                    result = self._merge_or(result, doc_ids)
                elif current_operator == "not":
                    result = self._merge_not(result, doc_ids)
            current_operator = "and"
            i += 1
        return result if result else []

    @staticmethod
    def _merge_sorted_int(a: List[int], b: List[int]) -> List[int]:
        result: List[int] = []
        i = j = 0
        while i < len(a) and j < len(b):
            if a[i] == b[j]:
                result.append(a[i])
                i += 1
                j += 1
            elif a[i] < b[j]:
                result.append(a[i])
                i += 1
            else:
                result.append(b[j])
                j += 1
        result.extend(a[i:])
        result.extend(b[j:])
        return result

    # ------------------------------------------------------------------
    # 既有辅助方法
    # ------------------------------------------------------------------

    def remove_document(self, doc_id: int):
        if doc_id < 0 or doc_id >= len(self.document_metadata):
            return

        if self.use_lsm:
            # LSM 模式下不真正删除，仅标记 metadata 为 None
            self.document_metadata[doc_id] = None
            if doc_id < self.document_count:
                self.document_count = doc_id
            return

        for term in list(self.index.keys()):
            if doc_id in self.index[term]:
                self.index[term].remove(doc_id)
                if not self.index[term]:
                    del self.index[term]

        for field in self.field_indices:
            for term in list(self.field_indices[field].keys()):
                if doc_id in self.field_indices[field][term]:
                    self.field_indices[field][term].remove(doc_id)
                    if not self.field_indices[field][term]:
                        del self.field_indices[field][term]

        self.document_metadata[doc_id] = None
        self.document_count -= 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "document_count": self.document_count,
            "unique_terms": self.get_unique_term_count(),
            "build_time": self.build_time,
            "field_stats": {
                field: self.get_field_unique_term_count(field)
                for field in (self.field_indices.keys() if not self.use_lsm else self._default_fields)
            },
            "use_lsm": self.use_lsm,
            "sstable_count": len(self._sstables) if self.use_lsm else 0,
            "memtable_size": self.memtable.size if self.use_lsm else 0,
        }


def create_inverted_index(documents: List[Dict[str, Any]], fields: List[str] = None) -> InvertedIndex:
    index = InvertedIndex()
    index.build_from_documents(documents, fields)
    return index


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness — 倒排索引模块")
    print("=" * 80)

    sample_docs = [
        {
            "id": "shadcn_ui",
            "name": "shadcn/ui",
            "tags": ["react", "tailwind", "ui", "components", "modern"],
            "components": ["button", "card", "dialog", "input", "table"],
            "domain": ["frontend", "dashboard", "saas"],
            "tech": "React + Tailwind",
        },
        {
            "id": "ant_design",
            "name": "Ant Design",
            "tags": ["react", "ui", "components", "enterprise"],
            "components": ["button", "table", "form", "modal", "select"],
            "domain": ["frontend", "enterprise", "admin"],
            "tech": "React",
        },
        {
            "id": "mui",
            "name": "Material UI",
            "tags": ["react", "material", "ui", "components"],
            "components": ["button", "card", "dialog", "app-bar"],
            "domain": ["frontend", "mobile", "desktop"],
            "tech": "React",
        },
        {
            "id": "element_plus",
            "name": "Element Plus",
            "tags": ["vue", "ui", "components", "enterprise"],
            "components": ["button", "table", "form", "dialog"],
            "domain": ["frontend", "enterprise", "admin"],
            "tech": "Vue 3",
        },
        {
            "id": "naive_ui",
            "name": "Naive UI",
            "tags": ["vue", "ui", "components", "modern"],
            "components": ["button", "card", "dialog", "input"],
            "domain": ["frontend", "dashboard", "saas"],
            "tech": "Vue 3",
        },
    ]

    index = InvertedIndex()
    index.build_from_documents(sample_docs)

    stats = index.get_stats()
    print(f"\n📊 索引统计:")
    print(f"  文档数量: {stats['document_count']}")
    print(f"  唯一词数: {stats['unique_terms']}")
    print(f"  构建时间: {stats['build_time']:.4f}s")
    print(f"  字段统计: {stats['field_stats']}")

    print("\n🔍 测试关键词搜索:")
    test_queries = ["button", "react", "enterprise", "vue", "card"]
    for query in test_queries:
        results = index.search(query)
        doc_names = [sample_docs[i]["name"] for i in results]
        print(f"  '{query}' → {doc_names}")

    print("\n🔍 测试布尔查询:")
    test_boolean = [
        "react and button",
        "enterprise or admin",
        "button not table",
        "vue and modern",
    ]
    for query in test_boolean:
        results = index.boolean_search(query)
        doc_names = [sample_docs[i]["name"] for i in results]
        print(f"  '{query}' → {doc_names}")

    print("\n🔍 测试字段搜索:")
    field_results = index.search("button", fields=["components"])
    doc_names = [sample_docs[i]["name"] for i in field_results]
    print(f"  components:button → {doc_names}")

    print("\n🔍 测试前缀搜索:")
    prefix_results = index.search("but")
    doc_names = [sample_docs[i]["name"] for i in prefix_results]
    print(f"  'but*' → {doc_names}")

    print("\n✅ 倒排索引模块测试完成")
