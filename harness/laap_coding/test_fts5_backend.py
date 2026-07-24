"""
test_fts5_backend.py — SQLite FTS5 后端语义等价性测试

覆盖 Task A2.4 验收点：
1. FTS5Backend 基础功能：add_document / search / boolean_search / prefix_search / count
2. 布尔查询 AND/OR/NOT 语义正确
3. 前缀查询 + 字段过滤
4. 与内存 InvertedIndex 语义等价性（同样数据 + 同样查询 = 结果集相同）
"""

import os
import sys

import pytest

# 确保从任意 cwd 运行 pytest 均可导入 core.incremental_updater
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.incremental_updater import FTS5Backend  # noqa: E402
from core.inverted_index import InvertedIndex  # noqa: E402


# ---------------------------------------------------------------------------
# 测试数据：10 个文档
# ---------------------------------------------------------------------------

TEST_DOCS = [
    {"id": "doc_0", "tags": ["button"], "name": "Button"},
    {"id": "doc_1", "tags": ["input"], "name": "Input"},
    {"id": "doc_2", "tags": ["button", "input"], "name": "ButtonInput"},
    {"id": "doc_3", "tags": ["button"], "name": "Btn"},
    {"id": "doc_4", "tags": ["card"], "name": "Card"},
    {"id": "doc_5", "tags": ["button", "card"], "name": "ButtonCard"},
    {"id": "doc_6", "tags": ["input", "form"], "name": "InputForm"},
    {"id": "doc_7", "tags": ["dialog"], "name": "Dialog"},
    {"id": "doc_8", "tags": ["button", "dialog"], "name": "ButtonDialog"},
    {"id": "doc_9", "tags": ["form"], "name": "Form"},
]


def _doc_ids_with_tag(tag: str) -> list:
    """返回 tags 中包含指定 tag 的 doc_id 列表（有序）。"""
    return sorted(doc["id"] for doc in TEST_DOCS if tag in doc["tags"])


def _doc_ids_with_any_tags(*tags: str) -> list:
    """返回 tags 中包含任意一个指定 tag 的 doc_id 列表（有序）。"""
    tag_set = set(tags)
    return sorted(doc["id"] for doc in TEST_DOCS if tag_set & set(doc["tags"]))


def _doc_ids_with_all_tags(*tags: str) -> list:
    """返回 tags 中同时包含全部指定 tag 的 doc_id 列表（有序）。"""
    tag_set = set(tags)
    return sorted(doc["id"] for doc in TEST_DOCS if tag_set.issubset(set(doc["tags"])))


def _doc_ids_with_tag_prefix(prefix: str) -> list:
    """返回 tags 中存在以 prefix 开头的 tag 的 doc_id 列表（有序）。"""
    return sorted(
        doc["id"]
        for doc in TEST_DOCS
        if any(t.startswith(prefix) for t in doc["tags"])
    )


# ---------------------------------------------------------------------------
# Fixture：预填充 10 个文档的 FTS5Backend（仅 tags 字段）
# ---------------------------------------------------------------------------

@pytest.fixture
def fts5_backend(tmp_path):
    db_path = str(tmp_path / "test_fts5.sqlite3")
    backend = FTS5Backend(db_path)
    for doc in TEST_DOCS:
        backend.add_document(doc["id"], {"tags": doc["tags"]})
    yield backend
    backend.close()


# ---------------------------------------------------------------------------
# 1. count() 基础测试
# ---------------------------------------------------------------------------

def test_count_returns_10(fts5_backend):
    """count() 应返回已添加的文档总数（10）。"""
    assert fts5_backend.count() == 10


# ---------------------------------------------------------------------------
# 2. 布尔查询测试
# ---------------------------------------------------------------------------

def test_boolean_search_and(fts5_backend):
    """AND：返回同时包含 'button' 和 'input' 的文档。"""
    result = sorted(fts5_backend.boolean_search(["button", "input"], "AND"))
    expected = _doc_ids_with_all_tags("button", "input")
    assert result == expected, f"AND: got {result}, expected {expected}"


def test_boolean_search_or(fts5_backend):
    """OR：返回包含 'button' 或 'input' 的文档。"""
    result = sorted(fts5_backend.boolean_search(["button", "input"], "OR"))
    expected = _doc_ids_with_any_tags("button", "input")
    assert result == expected, f"OR: got {result}, expected {expected}"


def test_boolean_search_not(fts5_backend):
    """NOT：返回含 'button' 不含 'input' 的文档。"""
    result = sorted(
        fts5_backend.boolean_search(["button"], "NOT", exclude=["input"])
    )
    expected = sorted(
        doc["id"]
        for doc in TEST_DOCS
        if "button" in doc["tags"] and "input" not in doc["tags"]
    )
    assert result == expected, f"NOT: got {result}, expected {expected}"


# ---------------------------------------------------------------------------
# 3. 前缀查询测试
# ---------------------------------------------------------------------------

def test_prefix_search_returns_button_docs(fts5_backend):
    """prefix_search('but') 应返回 tags 中存在以 'but' 开头（即 button）的文档。"""
    result = sorted(fts5_backend.prefix_search("but"))
    expected = _doc_ids_with_tag_prefix("but")
    assert result == expected, f"prefix 'but': got {result}, expected {expected}"


def test_prefix_search_with_field_filter(fts5_backend):
    """prefix_search('but', field='tags') 字段过滤应返回与不带 field 一致的结果。"""
    result = sorted(fts5_backend.prefix_search("but", field="tags"))
    expected = _doc_ids_with_tag_prefix("but")
    assert result == expected, f"prefix 'but' field=tags: got {result}, expected {expected}"


def test_prefix_search_field_filter_excludes_other_fields(tmp_path):
    """字段过滤应只匹配指定字段；其他字段中的同前缀 term 不应被返回。"""
    db_path = str(tmp_path / "field_filter.sqlite3")
    backend = FTS5Backend(db_path)
    try:
        backend.add_document("only_name", {"tags": [], "name": ["button"]})
        backend.add_document("only_tags", {"tags": ["button"], "name": ["card"]})

        # 不限字段：两个文档都应被命中
        all_result = sorted(backend.prefix_search("but"))
        assert all_result == ["only_name", "only_tags"]

        # 仅 tags 字段：只命中 only_tags
        tags_result = sorted(backend.prefix_search("but", field="tags"))
        assert tags_result == ["only_tags"]

        # 仅 name 字段：只命中 only_name
        name_result = sorted(backend.prefix_search("but", field="name"))
        assert name_result == ["only_name"]
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# 4. 通用 search() 测试
# ---------------------------------------------------------------------------

def test_search_single_term(fts5_backend):
    """search('button') 应返回 tags 中包含 button 的文档。"""
    result = sorted(fts5_backend.search("button"))
    expected = _doc_ids_with_tag("button")
    assert result == expected


def test_search_multi_term_and(fts5_backend):
    """search('button input') 多 term 默认 AND 组合。"""
    result = sorted(fts5_backend.search("button input"))
    expected = _doc_ids_with_all_tags("button", "input")
    assert result == expected


def test_search_falls_back_to_prefix(fts5_backend):
    """search('but') 不存在精确 term，应回退到前缀匹配，与 InvertedIndex 一致。"""
    result = sorted(fts5_backend.search("but"))
    expected = _doc_ids_with_tag_prefix("but")
    assert result == expected


def test_search_empty_query_returns_empty(fts5_backend):
    assert fts5_backend.search("") == []
    assert fts5_backend.search("   ") == []


# ---------------------------------------------------------------------------
# 5. 与内存 InvertedIndex 语义等价性测试
# ---------------------------------------------------------------------------

@pytest.fixture
def equiv_pair(tmp_path):
    """构建等价对比 fixture：同样的 10 个文档，分别构建 InvertedIndex 与 FTS5Backend。

    仅使用 tags 字段，避免 name 字段中复合词（如 "ButtonInput"）在两个后端
    间的 token 化差异干扰等价性验证。
    """
    docs_for_index = [
        {"id": doc["id"], "tags": doc["tags"]} for doc in TEST_DOCS
    ]

    index = InvertedIndex()
    index.build_from_documents(docs_for_index, fields=["tags"])

    db_path = str(tmp_path / "equiv.sqlite3")
    backend = FTS5Backend(db_path)
    for doc in docs_for_index:
        backend.add_document(doc["id"], {"tags": doc["tags"]})

    yield index, backend, docs_for_index

    backend.close()


def test_equiv_document_count(equiv_pair):
    index, backend, _ = equiv_pair
    assert backend.count() == index.document_count == len(TEST_DOCS)


def test_equiv_single_term_search(equiv_pair):
    """单 term 搜索：FTS5 与 InvertedIndex 返回相同的 doc_id 集合。"""
    index, backend, docs = equiv_pair
    for term in ["button", "input", "card", "dialog", "form"]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.search(term))
        fts_doc_ids = sorted(backend.search(term))
        assert inv_doc_ids == fts_doc_ids, (
            f"search('{term}'): inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_multi_term_and_search(equiv_pair):
    """多 term AND 搜索：两个后端返回相同的 doc_id 集合。"""
    index, backend, docs = equiv_pair
    for query in ["button input", "button card", "input form", "button dialog"]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.search(query))
        fts_doc_ids = sorted(backend.search(query))
        assert inv_doc_ids == fts_doc_ids, (
            f"search('{query}'): inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_prefix_search(equiv_pair):
    """前缀搜索：FTS5Backend.prefix_search 与 InvertedIndex.search（前缀回退）等价。"""
    index, backend, docs = equiv_pair
    for prefix in ["but", "in", "ca", "di", "fo"]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.search(prefix))
        fts_doc_ids = sorted(backend.prefix_search(prefix))
        assert inv_doc_ids == fts_doc_ids, (
            f"prefix '{prefix}': inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_boolean_and(equiv_pair):
    """布尔 AND：InvertedIndex.boolean_search('a and b') == FTS5Backend.boolean_search([a, b], 'AND')。"""
    index, backend, docs = equiv_pair
    for a, b in [("button", "input"), ("button", "card"), ("input", "form")]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.boolean_search(f"{a} and {b}"))
        fts_doc_ids = sorted(backend.boolean_search([a, b], "AND"))
        assert inv_doc_ids == fts_doc_ids, (
            f"AND {a},{b}: inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_boolean_or(equiv_pair):
    """布尔 OR：两后端返回相同 doc_id 集合。"""
    index, backend, docs = equiv_pair
    for a, b in [("button", "input"), ("card", "dialog"), ("input", "form")]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.boolean_search(f"{a} or {b}"))
        fts_doc_ids = sorted(backend.boolean_search([a, b], "OR"))
        assert inv_doc_ids == fts_doc_ids, (
            f"OR {a},{b}: inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_boolean_not(equiv_pair):
    """布尔 NOT：InvertedIndex 'a not b' == FTS5Backend boolean_search([a], 'NOT', exclude=[b])。"""
    index, backend, docs = equiv_pair
    for a, b in [("button", "input"), ("button", "card"), ("input", "form")]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.boolean_search(f"{a} not {b}"))
        fts_doc_ids = sorted(backend.boolean_search([a], "NOT", exclude=[b]))
        assert inv_doc_ids == fts_doc_ids, (
            f"NOT {a},{b}: inv={inv_doc_ids} fts={fts_doc_ids}"
        )


def test_equiv_field_filtered_search(equiv_pair):
    """字段过滤搜索：InvertedIndex.search(term, fields=['tags']) == FTS5Backend.search(term, fields=['tags'])。"""
    index, backend, docs = equiv_pair
    for term in ["button", "input", "card", "form"]:
        inv_doc_ids = sorted(docs[i]["id"] for i in index.search(term, fields=["tags"]))
        fts_doc_ids = sorted(backend.search(term, fields=["tags"]))
        assert inv_doc_ids == fts_doc_ids, (
            f"field-filtered '{term}': inv={inv_doc_ids} fts={fts_doc_ids}"
        )


# ---------------------------------------------------------------------------
# 6. MatchingEngine FTS5 自动切换阈值测试
# ---------------------------------------------------------------------------

def test_matching_engine_fts5_threshold_constant():
    """MatchingEngine 应暴露 FTS5_THRESHOLD=50000 类属性。"""
    from core.matching_engine import MatchingEngine
    assert MatchingEngine.FTS5_THRESHOLD == 50000


def test_matching_engine_does_not_init_fts5_for_small_db():
    """当前小数据库（< 50000 组件）不应触发 FTS5 后端初始化。"""
    from core.matching_engine import MatchingEngine
    engine = MatchingEngine(use_enhancements=False)
    assert engine.fts5_backend is None
    # 但代码路径应就绪（threshold 字段可读）
    assert engine.FTS5_THRESHOLD == 50000
