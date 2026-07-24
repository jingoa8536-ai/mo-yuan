"""
test_inverted_index_stress.py — LSM-Tree 写入路径压力测试

覆盖 Task A1.6 验收点：
1. 10 万组件批量入库 < 30 秒（time.perf_counter 计时）
2. WAL 崩溃恢复（写入中模拟崩溃 → recover_from_wal → 验证无重复）
3. 内存峰值 < 500MB（tracemalloc 检测）
4. use_lsm=False 默认路径回归正确性
"""

import os
import sys
import time
import json
import shutil
import tempfile
import tracemalloc

import pytest

# 确保从任意 cwd 运行 pytest 均可导入 core.inverted_index
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.inverted_index import InvertedIndex, WAL, MemTable, SSTable  # noqa: E402


# ---------------------------------------------------------------------------
# 测试数据生成
# ---------------------------------------------------------------------------

def _make_doc(i: int) -> dict:
    """构造第 i 个假组件文档，覆盖 4 个字段。"""
    return {
        "id": f"comp_{i}",
        "name": f"Component {i}",
        "tags": [f"tag_{i % 100}", f"cat_{i % 50}", f"lib_{i % 20}"],
        "components": [f"btn_{i % 30}", f"card_{i % 25}"],
        "domain": [f"d_{i % 10}"],
    }


def _make_docs(n: int):
    return [_make_doc(i) for i in range(n)]


# ---------------------------------------------------------------------------
# 1. 10 万组件批量入库 < 30s + 内存峰值 < 500MB
# ---------------------------------------------------------------------------

def test_bulk_insert_100k_under_30s_and_memory_under_500mb():
    """10 万组件批量入库：耗时 < 30s，内存峰值 < 500MB。

    时间与内存分开测量：tracemalloc 会带来约 10x 的 Python 级别开销，
    因此先在不启用 tracemalloc 的情况下测量耗时，再用 tracemalloc 测量内存峰值。
    """
    docs = _make_docs(100_000)

    # ---- 阶段 1：耗时测量（不启用 tracemalloc，避免其开销干扰计时）----
    tmpdir = tempfile.mkdtemp(prefix="laap_stress_t_")
    try:
        index = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        start = time.perf_counter()
        index.batch_add(docs)
        index.flush()
        elapsed = time.perf_counter() - start

        assert elapsed < 30.0, (
            f"批量入库 10 万组件耗时 {elapsed:.2f}s，超过 30s 阈值"
        )

        # 基本正确性：搜索 tag_0 应返回所有 i % 100 == 0 的文档
        results = index.search("tag_0")
        expected_ids = {i for i in range(100_000) if i % 100 == 0}
        assert set(results) == expected_ids, (
            f"tag_0 搜索结果数量 {len(results)}，预期 {len(expected_ids)}"
        )

        # 验证 document_count 正确
        assert index.document_count == 100_000
        stats = index.get_stats()
        assert stats["use_lsm"] is True
        assert stats["sstable_count"] > 0, "批量入库后应至少有一张 SSTable"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ---- 阶段 2：内存峰值测量（启用 tracemalloc，耗时无关紧要）----
    tmpdir = tempfile.mkdtemp(prefix="laap_stress_m_")
    try:
        index = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        tracemalloc.start()
        index.batch_add(docs)
        index.flush()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        assert peak < 500 * 1024 * 1024, (
            f"内存峰值 {peak_mb:.1f}MB，超过 500MB 阈值"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. WAL 崩溃恢复 —— 写入中模拟崩溃，recover_from_wal 重放，无重复
# ---------------------------------------------------------------------------

def test_wal_crash_recovery_no_duplicates():
    """WAL 崩溃恢复：写入少量文档（不触发 flush），模拟崩溃后重放，无重复 entries。

    使用 50 个文档（50 * 14 = 700 entries < MAX_SIZE=1000），确保不触发 flush，
    MemTable 完全丢失，仅靠 WAL 恢复。
    """
    tmpdir = tempfile.mkdtemp(prefix="laap_crash_")
    try:
        # 阶段 1：写入 50 条文档（每条 fsync），不 flush MemTable（模拟崩溃）
        index_a = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        docs = _make_docs(50)
        for doc in docs:
            index_a.add_document(doc)  # sync=True，确保 WAL 持久化
        # 不调用 flush()，模拟 MemTable 丢失；仅关闭 WAL 句柄
        index_a.wal.close()
        # 50 docs * 14 entries/doc = 700 < 1000，不应触发 flush
        sst_files = [
            f for f in os.listdir(index_a._sstables_dir)
            if f.startswith("sstable_") and f.endswith(".json")
        ]
        assert len(sst_files) == 0, (
            f"模拟崩溃前不应有 SSTable，但发现 {len(sst_files)} 张"
        )

        # 阶段 2：新实例从同一目录恢复
        index_b = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        recovered = index_b.recover_from_wal()
        assert recovered == 50, (
            f"应恢复 50 条文档，实际 {recovered}"
        )

        # 验证 document_count 与 metadata
        assert index_b.document_count == 50
        for i in range(50):
            meta = index_b.get_document(i)
            assert meta is not None, f"doc_id={i} 的 metadata 缺失"
            assert meta["id"] == f"comp_{i}"

        # 验证搜索结果正确
        # tag_0 对应 i % 100 == 0 → 仅 doc_id=0
        results = index_b.search("tag_0")
        assert set(results) == {0}, (
            f"tag_0 搜索结果 {sorted(results)}，预期 [0]"
        )

        # 验证无重复：对若干 term 检查 postings 无重复 doc_id
        sample_terms = ["tag_0", "tag_1", "btn_0", "card_0", "d_0", "cat_0"]
        for term in sample_terms:
            postings = index_b._lookup_lsm(term, field=None)
            if postings:
                assert len(postings) == len(set(postings)), (
                    f"term='{term}' postings 存在重复 doc_id: {postings}"
                )

        # 验证字段索引也可查询
        comp_results = index_b.search("btn_0", fields=["components"])
        expected_comp = {i for i in range(50) if i % 30 == 0}
        assert set(comp_results) == expected_comp, (
            f"components:btn_0 搜索结果数量 {len(comp_results)}，"
            f"预期 {len(expected_comp)}"
        )

        # 阶段 3：恢复后 WAL 应被清空（已 checkpoint）
        assert os.path.getsize(index_b._wal_path) == 0, (
            "recover_from_wal 后 WAL 应被清空"
        )

        # 阶段 4：恢复后继续写入应正常
        index_b.add_document(_make_doc(50))
        assert index_b.document_count == 51
        # doc 50 的 tags 包含 cat_0（50 % 50 == 0）与 tag_50（50 % 100 == 50）
        r2 = index_b.search("cat_0")
        assert 50 in set(r2), "恢复后继续写入的文档应可被搜索"
        r3 = index_b.search("tag_50")
        assert 50 in set(r3), "恢复后继续写入的文档应可被搜索"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_wal_crash_recovery_with_existing_sstables():
    """WAL 崩溃恢复（含已落盘 SSTable）：恢复后 postings 无重复。

    写入 500 文档（会触发多次 flush 产生 SSTable），再崩溃；
    恢复时重放全部 WAL，_lookup_lsm 合并 MemTable + SSTable 时去重。
    """
    tmpdir = tempfile.mkdtemp(prefix="laap_crash_sst_")
    try:
        # 阶段 1：写入 500 条文档（每条 fsync），会触发多次 flush
        index_a = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        docs = _make_docs(500)
        for doc in docs:
            index_a.add_document(doc)
        index_a.wal.close()
        # 此时应有若干 SSTable（500 * 14 = 7000 entries / 1000 = ~7 SSTable）
        sst_files = [
            f for f in os.listdir(index_a._sstables_dir)
            if f.startswith("sstable_") and f.endswith(".json")
        ]
        assert len(sst_files) > 0, "500 文档应已触发至少一次 flush"

        # 阶段 2：新实例从同一目录恢复
        index_b = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        # 新实例应加载已有 SSTable
        assert len(index_b._sstables) == len(sst_files)
        recovered = index_b.recover_from_wal()
        assert recovered == 500, f"应恢复 500 条文档，实际 {recovered}"

        # 验证 document_count
        assert index_b.document_count == 500

        # 验证搜索结果正确且无重复
        # tag_0 对应 i % 100 == 0 → 0, 100, 200, 300, 400
        results = index_b.search("tag_0")
        assert set(results) == {0, 100, 200, 300, 400}, (
            f"tag_0 搜索结果 {sorted(results)}，预期 [0, 100, 200, 300, 400]"
        )

        # 关键验证：即使 WAL 重放的 doc 已在旧 SSTable 中，
        # _lookup_lsm 合并后也不应有重复 doc_id
        sample_terms = ["tag_0", "tag_1", "btn_0", "card_0", "d_0", "cat_0",
                        "tag_2", "btn_1", "lib_0"]
        for term in sample_terms:
            postings = index_b._lookup_lsm(term, field=None)
            if postings:
                assert len(postings) == len(set(postings)), (
                    f"term='{term}' postings 存在重复 doc_id "
                    f"(len={len(postings)}, unique={len(set(postings))})"
                )

        # 恢复后 WAL 应被清空
        assert os.path.getsize(index_b._wal_path) == 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_wal_crash_recovery_with_duplicate_doc_ids():
    """WAL 中同一 doc_id 多次出现时，恢复后取最后一条且无重复 postings。"""
    tmpdir = tempfile.mkdtemp(prefix="laap_dup_")
    try:
        index = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        # 手动向 WAL 写入同一 doc_id 的两条记录（模拟崩溃重试）
        doc_v1 = {
            "id": "comp_0",
            "name": "Component 0",
            "tags": ["tag_0", "cat_0"],
            "components": ["btn_0"],
            "domain": ["d_0"],
        }
        doc_v2 = {
            "id": "comp_0",
            "name": "Component 0 Updated",
            "tags": ["tag_0", "cat_1"],  # cat 改变
            "components": ["btn_1"],
            "domain": ["d_1"],
        }
        index.wal.append({"doc_id": 0, "doc": doc_v1, "fields": ["tags", "name", "components", "domain"]})
        index.wal.append({"doc_id": 0, "doc": doc_v2, "fields": ["tags", "name", "components", "domain"]})
        index.wal.fsync()
        index.wal.close()

        # 新实例恢复
        index2 = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        recovered = index2.recover_from_wal()
        assert recovered == 1, f"去重后应只恢复 1 条，实际 {recovered}"

        # cat_0 应不存在（被 v2 覆盖），cat_1 应存在
        assert not index2._has_term_lsm("cat_0", field=None), "cat_0 应被 v2 覆盖移除"
        cat1_results = index2.search("cat_1")
        assert 0 in set(cat1_results), "cat_1 应可搜索到 doc_id=0"

        # tag_0 在 v1 和 v2 都存在，但 postings 不应有重复
        tag0_postings = index2._lookup_lsm("tag_0", field=None)
        assert tag0_postings.count(0) == 1, (
            f"tag_0 的 postings 中 doc_id=0 出现 {tag0_postings.count(0)} 次，应仅 1 次"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 3. WAL / MemTable / SSTable 单元正确性
# ---------------------------------------------------------------------------

def test_wal_append_and_recover_roundtrip():
    tmpdir = tempfile.mkdtemp(prefix="laap_wal_")
    try:
        wal_path = os.path.join(tmpdir, "wal.log")
        wal = WAL(wal_path)
        records = [
            {"doc_id": 0, "doc": {"name": "a"}, "fields": ["name"]},
            {"doc_id": 1, "doc": {"name": "b"}, "fields": ["name"]},
            {"doc_id": 2, "doc": {"name": "c"}, "fields": ["name"]},
        ]
        for r in records:
            wal.append(r, sync=True)
        wal.close()

        wal2 = WAL(wal_path)
        recovered = wal2.recover()
        assert recovered == records, "WAL recover 应原样返回全部记录"
        wal2.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_wal_recover_skips_corrupt_tail():
    """崩溃中途写入的不完整 JSON 行应被跳过。"""
    tmpdir = tempfile.mkdtemp(prefix="laap_corr_")
    try:
        wal_path = os.path.join(tmpdir, "wal.log")
        with open(wal_path, "wb") as f:
            f.write(b'{"doc_id": 0, "doc": {"name": "a"}}\n')
            f.write(b'{"doc_id": 1, "doc": {"name": "b"}}\n')
            f.write(b'{"doc_id": 2, "doc": {"incomplete"')  # 损坏的末尾行

        wal = WAL(wal_path)
        recovered = wal.recover()
        assert len(recovered) == 2, (
            f"应恢复 2 条完整记录，实际 {len(recovered)}"
        )
        assert recovered[0]["doc_id"] == 0
        assert recovered[1]["doc_id"] == 1
        wal.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_memtable_capacity_and_flush():
    tmpdir = tempfile.mkdtemp(prefix="laap_mem_")
    try:
        mt = MemTable()
        assert mt.MAX_SIZE == 1000
        assert mt.size == 0
        assert not mt.is_full()

        # 添加 999 条
        for i in range(999):
            mt.add(f"term_{i % 50}", i, field=None)
        assert not mt.is_full(), "999 条不应满"

        mt.add("term_trigger", 999, field=None)
        assert mt.is_full(), "1000 条应满"

        # flush 到 SSTable
        sst_path = os.path.join(tmpdir, "sstable_test.json")
        sst = mt.flush_to_sstable(sst_path)
        assert mt.size == 0, "flush 后 MemTable 应清空"

        # 验证 SSTable 可读取
        for i in range(50):
            result = sst.get(f"term_{i}", field=None)
            assert len(result) > 0, f"term_{i} 应在 SSTable 中"

        # 二分查找验证：存在的 term 返回 postings
        r = sst.get("term_0", field=None)
        assert 0 in r and 50 in r and 100 in r
        # 不存在的 term 返回空
        assert sst.get("nonexistent", field=None) == []
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_sstable_binary_search_and_merge():
    tmpdir = tempfile.mkdtemp(prefix="laap_sst_")
    try:
        # 构造两张 SSTable
        path1 = os.path.join(tmpdir, "s1.json")
        path2 = os.path.join(tmpdir, "s2.json")

        mt1 = MemTable()
        mt1.add("alpha", 1, field=None)
        mt1.add("alpha", 3, field=None)
        mt1.add("beta", 5, field=None)
        mt1.flush_to_sstable(path1)

        mt2 = MemTable()
        mt2.add("alpha", 2, field=None)
        mt2.add("alpha", 4, field=None)
        mt2.add("gamma", 6, field=None)
        mt2.flush_to_sstable(path2)

        s1 = SSTable(path1)
        s2 = SSTable(path2)

        # 二分查找
        assert s1.get("alpha", field=None) == [1, 3]
        assert s1.get("beta", field=None) == [5]
        assert s1.get("gamma", field=None) == []
        assert s2.get("alpha", field=None) == [2, 4]
        assert s2.get("gamma", field=None) == [6]

        # 合并
        merged_path = os.path.join(tmpdir, "merged.json")
        merged = s1.merge(s2, merged_path)
        assert merged.get("alpha", field=None) == [1, 2, 3, 4]
        assert merged.get("beta", field=None) == [5]
        assert merged.get("gamma", field=None) == [6]
        # 无重复
        alpha = merged.get("alpha", field=None)
        assert len(alpha) == len(set(alpha)), "合并后不应有重复 doc_id"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 4. use_lsm=False 默认路径回归
# ---------------------------------------------------------------------------

def test_legacy_mode_backward_compatible():
    """use_lsm=False 默认路径应与原 bisect.insort 行为完全一致。"""
    index = InvertedIndex()  # 默认 use_lsm=False
    assert index.use_lsm is False

    docs = _make_docs(100)
    for doc in docs:
        index.add_document(doc)

    # 基本搜索
    results = index.search("tag_0")
    expected = {i for i in range(100) if i % 100 == 0}
    assert set(results) == expected

    # 布尔搜索
    bool_results = index.boolean_search("tag_0 and btn_0")
    # tag_0: i%100==0 → {0}; btn_0: i%30==0 → {0,30,60,90}
    # AND → {0}
    assert set(bool_results) == {0}

    # 字段搜索
    field_results = index.search("btn_0", fields=["components"])
    expected_field = {i for i in range(100) if i % 30 == 0}
    assert set(field_results) == expected_field

    # 前缀搜索
    prefix_results = index.search("tag_")
    # tag_0..tag_99 都匹配 prefix "tag_"
    assert len(prefix_results) == 100, (
        f"前缀 'tag_' 应匹配全部 100 文档，实际 {len(prefix_results)}"
    )


def test_legacy_batch_add_equivalent_to_loop():
    """非 LSM 模式 batch_add 等价于循环 add_document。"""
    index1 = InvertedIndex(use_lsm=False)
    index2 = InvertedIndex(use_lsm=False)

    docs = _make_docs(50)
    for doc in docs:
        index1.add_document(doc)
    index2.batch_add(docs)

    assert index1.document_count == index2.document_count == 50
    # 比较搜索结果
    for term in ["tag_0", "btn_1", "cat_2", "d_3"]:
        assert index1.search(term) == index2.search(term), (
            f"term='{term}' 的搜索结果不一致"
        )


# ---------------------------------------------------------------------------
# 5. LSM 与 legacy 语义等价性
# ---------------------------------------------------------------------------

def test_lsm_and_legacy_produce_same_search_results():
    """同一批文档，LSM 与 legacy 路径应产生相同搜索结果。"""
    docs = _make_docs(200)

    legacy = InvertedIndex(use_lsm=False)
    legacy.batch_add(docs)

    tmpdir = tempfile.mkdtemp(prefix="laap_equiv_")
    try:
        lsm = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        lsm.batch_add(docs)
        lsm.flush()

        test_terms = [
            "tag_0", "tag_1", "btn_0", "card_1", "cat_2", "d_3",
            "nonexistent", "tag_99",
        ]
        for term in test_terms:
            legacy_res = set(legacy.search(term))
            lsm_res = set(lsm.search(term))
            assert legacy_res == lsm_res, (
                f"term='{term}': legacy={sorted(legacy_res)[:5]}... "
                f"lsm={sorted(lsm_res)[:5]}... 不一致"
            )

        # 布尔搜索等价
        for q in ["tag_0 and btn_0", "cat_0 or cat_1", "tag_0 not btn_0"]:
            legacy_b = set(legacy.boolean_search(q))
            lsm_b = set(lsm.boolean_search(q))
            assert legacy_b == lsm_b, (
                f"boolean '{q}': legacy={sorted(legacy_b)[:5]}... "
                f"lsm={sorted(lsm_b)[:5]}... 不一致"
            )

        # 字段搜索等价
        for field in ["tags", "components", "domain"]:
            for term in ["tag_0", "btn_0", "d_0"]:
                lf = set(legacy.search(term, fields=[field]))
                ls = set(lsm.search(term, fields=[field]))
                assert lf == ls, (
                    f"field={field} term={term}: legacy={sorted(lf)[:5]}... "
                    f"lsm={sorted(ls)[:5]}... 不一致"
                )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 6. 持久化跨实例：LSM SSTable 在新实例中可查询
# ---------------------------------------------------------------------------

def test_lsm_persistence_across_instances():
    """LSM 模式下，SSTable 持久化到磁盘，新实例加载后可查询。"""
    tmpdir = tempfile.mkdtemp(prefix="laap_persist_")
    try:
        # 实例 1：写入并 flush
        idx1 = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        idx1.batch_add(_make_docs(300))
        idx1.flush()
        sst_count = len(idx1._sstables)
        assert sst_count > 0
        idx1.wal.close()

        # 实例 2：从同一目录加载，应能查到已有 SSTable
        idx2 = InvertedIndex(use_lsm=True, lsm_dir=tmpdir)
        assert len(idx2._sstables) == sst_count, (
            "新实例应加载已有 SSTable"
        )
        results = idx2.search("tag_0")
        expected = {i for i in range(300) if i % 100 == 0}
        assert set(results) == expected
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
