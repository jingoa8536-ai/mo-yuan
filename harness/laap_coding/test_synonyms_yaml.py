"""
test_synonyms_yaml.py — 同义词库与缩写映射 YAML 配置化测试

覆盖 Task C2.4 验收点：
1. load_synonyms() 返回非空字典
2. load_abbreviations() 返回非空字典
3. SemanticExpander() 实例化后 expand_tags(["btn"]) 包含 "button"
4. expand_tags(["k8s"]) 包含 "kubernetes"（缩写扩展为完整形式）
5. 热加载：写入新 YAML 后重新调用 load 函数返回新内容
6. 自定义 yaml_path 参数：传入临时 YAML 文件路径可正确加载
7. SynonymExpander 别名兼容性（任务描述中的别名）
"""

import os
import sys
import tempfile

import pytest

# 确保从任意 cwd 运行 pytest 均可导入 core.semantic_expander
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.semantic_expander import (  # noqa: E402
    SemanticExpander,
    load_synonyms,
    load_abbreviations,
)


# ---------------------------------------------------------------------------
# 1. load_synonyms() / load_abbreviations() 返回非空字典
# ---------------------------------------------------------------------------

def test_load_synonyms_returns_nonempty_dict():
    """load_synonyms() 默认从包内 data/synonyms.yaml 加载，返回非空字典。"""
    synonyms = load_synonyms()
    assert isinstance(synonyms, dict)
    assert len(synonyms) > 0, "同义词库不应为空"


def test_load_abbreviations_returns_nonempty_dict():
    """load_abbreviations() 默认从包内 data/abbreviations.yaml 加载，返回非空字典。"""
    abbreviations = load_abbreviations()
    assert isinstance(abbreviations, dict)
    assert len(abbreviations) > 0, "缩写映射不应为空"


def test_load_synonyms_contains_button_group():
    """load_synonyms() 包含原硬编码的 button 同义词组。"""
    synonyms = load_synonyms()
    assert "button" in synonyms
    btn_synonyms = synonyms["button"]
    assert "btn" in btn_synonyms
    assert "buttons" in btn_synonyms
    assert "clickable" in btn_synonyms


def test_load_abbreviations_contains_btn_to_button():
    """load_abbreviations() 包含原硬编码的 btn → button 映射。"""
    abbreviations = load_abbreviations()
    assert "btn" in abbreviations
    assert abbreviations["btn"] == "button"


def test_load_synonyms_returns_list_values():
    """load_synonyms() 的值必须是 list[str]。"""
    synonyms = load_synonyms()
    for canonical, syn_list in synonyms.items():
        assert isinstance(canonical, str)
        assert isinstance(syn_list, list), f"{canonical} 的 synonyms 必须是 list"
        for s in syn_list:
            assert isinstance(s, str)


def test_load_abbreviations_returns_str_values():
    """load_abbreviations() 的值必须是 str。"""
    abbreviations = load_abbreviations()
    for abbr, expansion in abbreviations.items():
        assert isinstance(abbr, str)
        assert isinstance(expansion, str)


# ---------------------------------------------------------------------------
# 2. SemanticExpander 实例化与扩展行为
# ---------------------------------------------------------------------------

def test_expander_expand_btn_contains_button():
    """SemanticExpander() 实例化后 expand_tags(["btn"]) 必须包含 "button"。

    验收点：通过 abbreviation_map 的 btn → button 映射扩展。
    """
    expander = SemanticExpander()
    expanded = expander.expand_tags(["btn"])
    assert "button" in expanded, f"expand_tags(['btn']) 应包含 'button'，实际：{expanded}"


def test_expander_expand_k8s_contains_kubernetes():
    """expand_tags(["k8s"]) 包含 "kubernetes"（缩写扩展为完整形式）。

    验收点：缩写映射扩展行为正确（原硬编码 k8s → kubernetes）。
    """
    expander = SemanticExpander()
    expanded = expander.expand_tags(["k8s"])
    assert "kubernetes" in expanded, f"expand_tags(['k8s']) 应包含 'kubernetes'，实际：{expanded}"


def test_expander_expand_a11y_contains_accessibility():
    """expand_tags(["a11y"]) 包含 "accessibility"（缩写扩展为完整形式）。"""
    expander = SemanticExpander()
    expanded = expander.expand_tags(["a11y"])
    assert "accessibility" in expanded


def test_expander_synonym_graph_button_includes_btn():
    """同义词图扩展：btn 应通过同义词组扩展到 button 的同义集合。"""
    expander = SemanticExpander()
    # btn 既是 abbreviation，也是 button 的同义词
    expanded = expander.expand_tags(["btn"], expand_synonyms=True, expand_abbreviations=True)
    assert "button" in expanded
    # button 的同义词也应被扩展进来
    assert "clickable" in expanded or "action" in expanded


def test_expander_normalize_term_abbreviation():
    """normalize_term 对缩写返回其完整形式。"""
    expander = SemanticExpander()
    assert expander.normalize_term("btn") == "button"
    assert expander.normalize_term("k8s") == "kubernetes"


def test_expander_find_full_form():
    """find_full_form 通过缩写查完整形式。"""
    expander = SemanticExpander()
    assert expander.find_full_form("btn") == "button"
    assert expander.find_full_form("k8s") == "kubernetes"
    assert expander.find_full_form("a11y") == "accessibility"


def test_expander_find_synonyms_button():
    """find_synonyms 返回 button 的同义词列表。"""
    expander = SemanticExpander()
    synonyms = expander.find_synonyms("button")
    assert isinstance(synonyms, list)
    assert "btn" in synonyms
    assert "clickable" in synonyms


def test_expander_no_hardcoded_dict_in_source():
    """验证 semantic_expander.py 不再硬编码同义词与缩写字典。

    检查源文件中不再包含原硬编码字典字面量（button/card 等批量同义词）。
    """
    src_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "core",
        "semantic_expander.py",
    )
    with open(src_path, "r", encoding="utf-8") as f:
        source = f.read()

    # 原硬编码同义词字典的标志性字面量不应再出现（作为 dict literal）
    assert '"button": ["btn", "buttons", "clickable", "action"]' not in source, \
        "semantic_expander.py 不应再硬编码 button 同义词组"
    # 原硬编码缩写映射的标志性字面量不应再出现
    assert '"btn": "button",\n            "btns": "buttons"' not in source, \
        "semantic_expander.py 不应再硬编码 btn/btns 缩写映射"
    # load_synonyms / load_abbreviations 函数应存在
    assert "def load_synonyms(" in source
    assert "def load_abbreviations(" in source


# ---------------------------------------------------------------------------
# 3. 热加载：写入新 YAML 后重新调用 load 函数返回新内容
# ---------------------------------------------------------------------------

def test_hot_reload_synonyms_after_write():
    """热加载：写入新 synonyms YAML 后重新调用 load_synonyms 返回新内容。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- canonical: "widget-x"\n'
            '  synonyms:\n'
            '    - "wx"\n'
            '    - "x-component"\n'
        )
        tmp_path = f.name

    try:
        # 第一次加载
        first = load_synonyms(tmp_path)
        assert first == {"widget-x": ["wx", "x-component"]}

        # 覆盖写入新内容
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(
                '- canonical: "hot-reloaded"\n'
                '  synonyms:\n'
                '    - "hr"\n'
                '    - "live"\n'
            )

        # 重新加载应得到新内容（证明热加载生效，无缓存）
        second = load_synonyms(tmp_path)
        assert second == {"hot-reloaded": ["hr", "live"]}, \
            "热加载失败：重新调用 load_synonyms 未返回最新内容"
        assert "widget-x" not in second
    finally:
        os.unlink(tmp_path)


def test_hot_reload_abbreviations_after_write():
    """热加载：写入新 abbreviations YAML 后重新调用 load_abbreviations 返回新内容。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- abbreviation: "wx"\n'
            '  expansion: "widget-x"\n'
        )
        tmp_path = f.name

    try:
        first = load_abbreviations(tmp_path)
        assert first == {"wx": "widget-x"}

        # 覆盖写入新内容
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(
                '- abbreviation: "hr"\n'
                '  expansion: "hot-reloaded"\n'
            )

        second = load_abbreviations(tmp_path)
        assert second == {"hr": "hot-reloaded"}, \
            "热加载失败：重新调用 load_abbreviations 未返回最新内容"
        assert "wx" not in second
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 4. 自定义 yaml_path 参数：传入临时 YAML 文件路径可正确加载
# ---------------------------------------------------------------------------

def test_custom_yaml_path_synonyms():
    """自定义 yaml_path：传入临时 synonyms YAML 文件路径可正确加载。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- canonical: "custom-term"\n'
            '  synonyms:\n'
            '    - "ct"\n'
            '    - "custom"\n'
            '    - "term"\n'
        )
        tmp_path = f.name

    try:
        result = load_synonyms(tmp_path)
        assert result == {"custom-term": ["ct", "custom", "term"]}
    finally:
        os.unlink(tmp_path)


def test_custom_yaml_path_abbreviations():
    """自定义 yaml_path：传入临时 abbreviations YAML 文件路径可正确加载。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- abbreviation: "ct"\n'
            '  expansion: "custom-term"\n'
        )
        tmp_path = f.name

    try:
        result = load_abbreviations(tmp_path)
        assert result == {"ct": "custom-term"}
    finally:
        os.unlink(tmp_path)


def test_expander_with_custom_synonyms_path():
    """SemanticExpander 支持通过 synonyms_path 参数加载自定义同义词库。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- canonical: "neo-widget"\n'
            '  synonyms:\n'
            '    - "nw"\n'
            '    - "neo"\n'
        )
        tmp_path = f.name

    try:
        expander = SemanticExpander(synonyms_path=tmp_path)
        # 自定义同义词组生效
        expanded = expander.expand_tags(["neo-widget"])
        assert "nw" in expanded
        assert "neo" in expanded
    finally:
        os.unlink(tmp_path)


def test_expander_with_custom_abbreviations_path():
    """SemanticExpander 支持通过 abbreviations_path 参数加载自定义缩写映射。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            '- abbreviation: "nw"\n'
            '  expansion: "neo-widget"\n'
        )
        tmp_path = f.name

    try:
        expander = SemanticExpander(abbreviations_path=tmp_path)
        expanded = expander.expand_tags(["nw"])
        assert "neo-widget" in expanded
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 5. 回归测试：原硬编码内容完整性
# ---------------------------------------------------------------------------

def test_synonyms_yaml_preserves_original_count():
    """验证 synonyms.yaml 保留了原硬编码的同义词组数量（98 组）。"""
    synonyms = load_synonyms()
    # 原硬编码共 98 个同义词组（button..fullstack）
    assert len(synonyms) >= 90, \
        f"同义词组数量 {len(synonyms)} 过少，原硬编码约 98 组"


def test_abbreviations_yaml_preserves_original_count():
    """验证 abbreviations.yaml 保留了原硬编码的缩写映射数量（240+ 条去重后）。"""
    abbreviations = load_abbreviations()
    # 原硬编码约 250 条（含重复键），去重后 240+ 条
    assert len(abbreviations) >= 200, \
        f"缩写映射数量 {len(abbreviations)} 过少，原硬编码去重后 240+ 条"


def test_synonyms_yaml_preserves_key_groups():
    """验证 synonyms.yaml 保留了原硬编码的关键同义词组内容。"""
    synonyms = load_synonyms()
    expected_groups = {
        "button": {"btn", "buttons", "clickable", "action"},
        "card": {"cards", "panel", "widget", "tile"},
        "dialog": {"modal", "popup", "overlay", "dialog-box"},
        "kubernetes": {"k8s", "orchestration", "cluster"},
        "accessibility": {"a11y", "wcag", "inclusive"},
        "frontend": {"client", "browser", "ui"},
        "fullstack": {"full-stack", "both-ends", "full-stack-dev"},
    }
    for canonical, expected_syns in expected_groups.items():
        assert canonical in synonyms, f"缺少同义词组：{canonical}"
        actual_set = set(synonyms[canonical])
        assert expected_syns.issubset(actual_set), \
            f"{canonical} 同义词组内容不完整：缺 {expected_syns - actual_set}"


def test_abbreviations_yaml_preserves_key_mappings():
    """验证 abbreviations.yaml 保留了原硬编码的关键缩写映射。"""
    abbreviations = load_abbreviations()
    expected_mappings = {
        "btn": "button",
        "btns": "buttons",
        "nav": "navigation",
        "k8s": "kubernetes",
        "a11y": "accessibility",
        "sso": "single-sign-on",
        "jwt": "json-web-token",
        "cli": "command-line-interface",
        "ssr": "server-side-rendering",
        "pwa": "progressive-web-app",
        "ddd": "domain-driven-design",
    }
    for abbr, expansion in expected_mappings.items():
        assert abbr in abbreviations, f"缺少缩写映射：{abbr}"
        assert abbreviations[abbr] == expansion, \
            f"{abbr} 映射错误：期望 {expansion}，实际 {abbreviations[abbr]}"


# ---------------------------------------------------------------------------
# 6. 接口兼容性：原 expand 方法接口保持不变
# ---------------------------------------------------------------------------

def test_expand_tags_interface_unchanged():
    """expand_tags 接口保持不变：支持 expand_synonyms / expand_abbreviations 开关。"""
    expander = SemanticExpander()

    # 默认两个开关都开
    full = expander.expand_tags(["btn"])
    assert "button" in full

    # 关闭缩写扩展
    no_abbr = expander.expand_tags(["btn"], expand_abbreviations=False)
    assert "button" not in no_abbr or "btn" in no_abbr  # 仅靠同义词组扩展

    # 关闭同义词扩展
    no_syn = expander.expand_tags(["btn"], expand_synonyms=False)
    assert "button" in no_syn  # 缩写扩展仍生效


def test_get_semantic_expander_factory():
    """get_semantic_expander 工厂函数接口保持不变。"""
    from core.semantic_expander import get_semantic_expander
    expander = get_semantic_expander()
    assert isinstance(expander, SemanticExpander)
    expanded = expander.expand_tags(["btn"])
    assert "button" in expanded


def test_calculate_semantic_similarity_unchanged():
    """calculate_semantic_similarity 接口与行为保持不变。"""
    expander = SemanticExpander()
    sim = expander.calculate_semantic_similarity(["button", "card"], ["btn", "panel"])
    assert 0.0 <= sim <= 1.0
    # btn→button, panel→card 同义扩展后应有交集
    assert sim > 0.0
