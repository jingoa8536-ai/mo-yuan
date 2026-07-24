"""
test_style_embedding.py — StyleEmbeddingSpace 风格嵌入空间测试

覆盖 Task B1 验收点：
1. StyleRegister 注册新风格 neo-brutalism，get_description 返回正确
2. StyleEmbeddingSpace.style_similarity("modern-minimal", "modern-minimal") ≥ 0.8
3. StyleEmbeddingSpace.style_similarity("modern-minimal", "shadcn-ui") ≥ 0.5
4. 新风格 neo-brutalism 与 modern-minimal 相似度 ≥ 0.5（mock provider）
5. 用 unittest.mock.patch mock embedding_provider 验证 0.3 * prior + 0.7 * cosine 公式
6. MatchingEngine 实例化时 style_embedding_space 已初始化
7. MatchingEngine.calculate_style_compatibility 走新路径（mock 验证调用）
8. 与原 STYLE_SIMILARITY_MAP 兼容性：未注册新风格不再返回 0

测试中 mock embedding_provider，避免真实加载 sentence-transformers / BGE 模型。

运行：
    python -m pytest laap_coding/test_style_embedding.py -v -p no:quadrants
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# 确保从任意 cwd 运行 pytest 均可导入 core.style_register / core.matching_engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.vector_enhancer import (  # noqa: E402
    EmbeddingProvider,
    HashingVectorizer,
    _cosine_similarity,
)
from core.style_register import (  # noqa: E402
    StyleRegister,
    StyleEmbeddingSpace,
    get_style_embedding_space,
)
from core.matching_engine import (  # noqa: E402
    MatchingEngine,
    ComponentMeta,
)


# ---------------------------------------------------------------------------
# Mock EmbeddingProvider：基于关键词轴的确定性嵌入
# ---------------------------------------------------------------------------

class MockStyleEmbeddingProvider(EmbeddingProvider):
    """Mock provider：将风格描述中的关键词映射到语义轴向量。

    设计目标（让测试既真实又可验证）：
    - 相同文本 → cosine = 1.0
    - modern-minimal vs shadcn-ui → cosine ≈ 0.52（共享 design + modern 轴）
    - modern-minimal vs neo-brutalism → cosine ≈ 0.58（共享 design + modern 轴）

    关键词到语义轴的映射模拟了真实 embedding 的语义聚类特性。
    """

    DIM = 16

    KEYWORD_AXES = {
        # axis 0: 通用设计词
        "design": 0, "aesthetic": 0, "ui": 0,
        # axis 1: 现代设计（包括 brutalism 作为现代分支）
        "modern": 1, "bold": 1, "raw": 1, "concrete": 1, "contemporary": 1,
        # axis 2: 极简
        "minimal": 2, "clean": 2, "simple": 2, "whitespace": 2,
        # axis 3: glossy
        "glossy": 3, "reflective": 3, "gradient": 3,
        # axis 4: 标准/平衡
        "standard": 4, "balanced": 4, "conventional": 4,
        # axis 5: tailwind
        "tailwind": 5, "utility": 5,
        # axis 6: enterprise
        "enterprise": 6, "professional": 6, "business": 6,
        # axis 7: material
        "material": 7, "google": 7, "elevation": 7,
        # axis 8: shadcn
        "shadcn": 8, "radix": 8,
        # axis 9: borders (brutalism)
        "borders": 9, "thick": 9, "black": 9,
        # axis 10: contrast (brutalism)
        "contrast": 10, "high": 10,
        # axis 11: flutter
        "flutter": 11,
        # axis 12: landing
        "landing": 12, "marketing": 12,
        # axis 13: react/components
        "react": 13, "component": 13, "css": 13,
    }

    def __init__(self):
        self.dim = self.DIM

    def embed(self, texts):
        result = []
        for text in texts:
            vec = [0.0] * self.dim
            t = text.lower()
            for word, idx in self.KEYWORD_AXES.items():
                if word in t:
                    vec[idx] = 1.0
            # 全零兜底：基于 hash 放一个非零位（保持确定性）
            if all(v == 0 for v in vec):
                h = abs(hash(t)) % self.dim
                vec[h] = 1.0
            result.append(vec)
        return result

    def similarity(self, a, b):
        return _cosine_similarity(a, b)


# ---------------------------------------------------------------------------
# 1. StyleRegister 验收
# ---------------------------------------------------------------------------

class TestStyleRegister:
    """StyleRegister 注册与查询验收。"""

    def test_register_new_style(self):
        """注册新风格后 get_description 返回正确描述。"""
        reg = StyleRegister()
        reg.register(
            "neo-brutalism",
            "Bold raw concrete aesthetic with thick black borders and high contrast",
        )
        desc = reg.get_description("neo-brutalism")
        assert desc is not None
        assert "Bold" in desc
        assert "concrete" in desc

    def test_get_description_unknown_returns_none(self):
        """未注册风格返回 None。"""
        reg = StyleRegister()
        assert reg.get_description("nonexistent-style-xyz") is None

    def test_list_styles_includes_registered(self):
        """list_styles 包含已注册风格。"""
        reg = StyleRegister()
        reg.register("neo-brutalism", "Bold raw concrete aesthetic")
        styles = reg.list_styles()
        assert "neo-brutalism" in styles

    def test_list_styles_includes_defaults(self):
        """list_styles 包含预填的 STYLE_SIMILARITY_MAP 已知风格。"""
        reg = StyleRegister()
        styles = reg.list_styles()
        # 已知风格应预填
        assert "modern-minimal" in styles
        assert "shadcn-ui" in styles
        assert "material-design" in styles

    def test_register_overrides_existing(self):
        """同名风格重复注册以后者为准。"""
        reg = StyleRegister()
        reg.register("custom-style", "first description")
        reg.register("custom-style", "second description")
        assert reg.get_description("custom-style") == "second description"

    def test_register_empty_name_ignored(self):
        """空 name 注册被忽略。"""
        reg = StyleRegister()
        reg.register("", "empty name desc")
        assert reg.get_description("") is None


# ---------------------------------------------------------------------------
# 2. StyleEmbeddingSpace 风格相似度验收
# ---------------------------------------------------------------------------

class TestStyleEmbeddingSpaceSimilarity:
    """StyleEmbeddingSpace.style_similarity 验收。"""

    @pytest.fixture
    def embedding_space(self):
        """用 MockStyleEmbeddingProvider 构造 StyleEmbeddingSpace。"""
        prior_map = dict(MatchingEngine.STYLE_SIMILARITY_MAP)
        return StyleEmbeddingSpace(
            prior_map=prior_map,
            embedding_provider=MockStyleEmbeddingProvider(),
        )

    def test_same_style_similarity_above_08(self, embedding_space):
        """同风格相似度 ≥ 0.8（prior=1.0 + cosine=1.0 → 1.0）。"""
        sim = embedding_space.style_similarity("modern-minimal", "modern-minimal")
        assert sim >= 0.8, f"expected >= 0.8, got {sim}"
        # 实际应为 1.0
        assert sim == pytest.approx(1.0, abs=1e-9)

    def test_known_similar_styles_above_05(self, embedding_space):
        """modern-minimal vs shadcn-ui 相似度 ≥ 0.5（prior=0.9）。"""
        sim = embedding_space.style_similarity("modern-minimal", "shadcn-ui")
        assert sim >= 0.5, f"expected >= 0.5, got {sim}"

    def test_neo_brutalism_vs_modern_minimal_above_05(self, embedding_space):
        """新风格 neo-brutalism 与 modern-minimal 相似度 ≥ 0.5（spec 要求）。

        neo-brutalism 未在 STYLE_SIMILARITY_MAP 中，prior=0.5；
        mock embedding 共享 design + modern 轴 → cosine ≈ 0.58；
        综合 0.3*0.5 + 0.7*0.58 ≈ 0.55 ≥ 0.5。
        """
        embedding_space.style_register.register(
            "neo-brutalism",
            "Bold raw concrete aesthetic with thick black borders and high contrast",
        )
        sim = embedding_space.style_similarity("neo-brutalism", "modern-minimal")
        assert sim >= 0.5, f"expected >= 0.5, got {sim}"

    def test_neo_brutalism_vs_modern_minimal_above_03(self, embedding_space):
        """新风格 neo-brutalism 与 modern-minimal 相似度 ≥ 0.3（task 兜底要求）。"""
        embedding_space.style_register.register(
            "neo-brutalism",
            "Bold raw concrete aesthetic with thick black borders and high contrast",
        )
        sim = embedding_space.style_similarity("neo-brutalism", "modern-minimal")
        assert sim >= 0.3, f"expected >= 0.3, got {sim}"

    def test_unregistered_new_style_not_zero(self, embedding_space):
        """未注册的新风格相似度不再返回 0（基于 embedding）。"""
        # "cyberpunk-neon" 完全未注册、不在 prior_map
        sim = embedding_space.style_similarity("cyberpunk-neon", "modern-minimal")
        # prior=0.5（默认），cosine ≥ 0 → 至少 0.3*0.5 = 0.15
        assert sim > 0.0, f"未注册风格不应返回 0，got {sim}"

    def test_empty_style_returns_zero(self, embedding_space):
        """空风格返回 0.0。"""
        assert embedding_space.style_similarity("", "modern-minimal") == 0.0
        assert embedding_space.style_similarity("modern-minimal", "") == 0.0
        assert embedding_space.style_similarity("", "") == 0.0

    def test_symmetric_similarity(self, embedding_space):
        """风格相似度应对称（prior 双向查找 + cosine 对称）。"""
        sim_ab = embedding_space.style_similarity("modern-minimal", "shadcn-ui")
        sim_ba = embedding_space.style_similarity("shadcn-ui", "modern-minimal")
        assert sim_ab == pytest.approx(sim_ba, abs=1e-9)


# ---------------------------------------------------------------------------
# 3. 加权公式验证：0.3 * prior + 0.7 * cosine
# ---------------------------------------------------------------------------

class TestWeightedFormula:
    """验证 style_similarity = 0.3 * prior + 0.7 * cosine 公式。"""

    def test_formula_with_mocked_provider(self):
        """用 mock provider 验证 0.3 * prior + 0.7 * cosine 公式。

        构造已知 prior_map（a-b=0.5）+ mock cosine=0.8，
        期望 style_similarity = 0.3*0.5 + 0.7*0.8 = 0.71。
        """
        prior_map = {
            "a": {"a": 1.0, "b": 0.5},
            "b": {"a": 0.5, "b": 1.0},
        }

        # mock provider：embed 返回固定向量，similarity 返回 0.8
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0, 0.0]]
        mock_provider.similarity.return_value = 0.8

        space = StyleEmbeddingSpace(
            prior_map=prior_map,
            embedding_provider=mock_provider,
        )
        sim = space.style_similarity("a", "b")

        expected = 0.3 * 0.5 + 0.7 * 0.8  # 0.15 + 0.56 = 0.71
        assert sim == pytest.approx(expected, abs=1e-9)

    def test_formula_with_prior_only(self):
        """prior=1.0, cosine=0.0 → style_similarity = 0.3。"""
        prior_map = {"x": {"x": 1.0, "y": 1.0}, "y": {"x": 1.0, "y": 1.0}}

        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0]]
        mock_provider.similarity.return_value = 0.0

        space = StyleEmbeddingSpace(
            prior_map=prior_map,
            embedding_provider=mock_provider,
        )
        sim = space.style_similarity("x", "y")
        assert sim == pytest.approx(0.3 * 1.0 + 0.7 * 0.0, abs=1e-9)

    def test_formula_with_cosine_only(self):
        """prior=0.5（默认）, cosine=1.0 → style_similarity = 0.3*0.5 + 0.7 = 0.85。"""
        # 空 prior_map → 全部走默认 0.5
        prior_map = {}

        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0]]
        mock_provider.similarity.return_value = 1.0

        space = StyleEmbeddingSpace(
            prior_map=prior_map,
            embedding_provider=mock_provider,
        )
        sim = space.style_similarity("foo", "bar")
        expected = 0.3 * 0.5 + 0.7 * 1.0  # 0.15 + 0.7 = 0.85
        assert sim == pytest.approx(expected, abs=1e-9)

    def test_weights_constants(self):
        """权重常量正确：PRIOR_WEIGHT=0.3, EMBEDDING_WEIGHT=0.7。"""
        assert StyleEmbeddingSpace.PRIOR_WEIGHT == 0.3
        assert StyleEmbeddingSpace.EMBEDDING_WEIGHT == 0.7
        # 权重和为 1.0
        assert (
            StyleEmbeddingSpace.PRIOR_WEIGHT + StyleEmbeddingSpace.EMBEDDING_WEIGHT
            == pytest.approx(1.0, abs=1e-9)
        )


# ---------------------------------------------------------------------------
# 4. Embedding 缓存验证
# ---------------------------------------------------------------------------

class TestEmbeddingCache:
    """_get_style_embedding 缓存行为验收。"""

    def test_embedding_cached(self):
        """相同风格的 embedding 被缓存，provider 只调用一次。"""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0, 0.0]]
        mock_provider.similarity.return_value = 0.5

        space = StyleEmbeddingSpace(
            prior_map={},
            embedding_provider=mock_provider,
        )

        # 第一次调用：触发 embed
        v1 = space._get_style_embedding("modern-minimal")
        assert mock_provider.embed.call_count == 1

        # 第二次调用：应命中缓存，不触发 embed
        v2 = space._get_style_embedding("modern-minimal")
        assert mock_provider.embed.call_count == 1  # 仍是 1
        assert v1 == v2

    def test_different_styles_separate_cache(self):
        """不同风格分别缓存。"""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0, 0.0]]
        mock_provider.similarity.return_value = 0.5

        space = StyleEmbeddingSpace(
            prior_map={},
            embedding_provider=mock_provider,
        )

        space._get_style_embedding("modern-minimal")
        space._get_style_embedding("shadcn-ui")
        # 两个不同风格各调用一次 embed
        assert mock_provider.embed.call_count == 2

    def test_unregistered_style_uses_name_as_description(self):
        """未注册风格用风格名本身作为描述传给 provider。"""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.embed.return_value = [[1.0, 0.0]]
        mock_provider.similarity.return_value = 0.5

        space = StyleEmbeddingSpace(
            prior_map={},
            embedding_provider=mock_provider,
        )

        space._get_style_embedding("nonexistent-style-xyz")
        mock_provider.embed.assert_called_once_with(["nonexistent-style-xyz"])


# ---------------------------------------------------------------------------
# 5. 默认 provider 降级路径
# ---------------------------------------------------------------------------

class TestDefaultProviderFallback:
    """StyleEmbeddingSpace 默认 provider 降级路径验收。"""

    def test_default_provider_is_local_bge_or_hashing(self):
        """无 embedding_provider 时默认初始化 LocalBGEProvider 或 HashingVectorizer。"""
        from core.vector_enhancer import LocalBGEProvider
        space = StyleEmbeddingSpace(prior_map={})
        # 应为 LocalBGEProvider 或 HashingVectorizer（取决于环境是否装了 sentence-transformers）
        assert isinstance(
            space.embedding_provider, (LocalBGEProvider, HashingVectorizer)
        )

    def test_local_bge_failure_falls_back_to_hashing(self):
        """LocalBGEProvider 初始化失败时降级到 HashingVectorizer。"""
        # patch LocalBGEProvider 抛异常
        with patch("core.style_register.LocalBGEProvider") as mock_bge:
            mock_bge.side_effect = RuntimeError("model not available")
            space = StyleEmbeddingSpace(prior_map={})
            assert isinstance(space.embedding_provider, HashingVectorizer)

    def test_hashing_vectorizer_usable(self):
        """HashingVectorizer 降级后 style_similarity 仍可调用。"""
        with patch("core.style_register.LocalBGEProvider") as mock_bge:
            mock_bge.side_effect = RuntimeError("model not available")
            space = StyleEmbeddingSpace(prior_map={})
            sim = space.style_similarity("modern-minimal", "shadcn-ui")
            # 不抛异常，返回 [0, 1] 范围
            assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 6. MatchingEngine 集成验收
# ---------------------------------------------------------------------------

class TestMatchingEngineIntegration:
    """MatchingEngine 集成 StyleEmbeddingSpace 验收。"""

    def test_engine_has_style_embedding_space(self):
        """MatchingEngine 实例化后 style_embedding_space 已初始化。"""
        engine = MatchingEngine()
        assert engine.style_embedding_space is not None
        assert isinstance(engine.style_embedding_space, StyleEmbeddingSpace)

    def test_engine_style_embedding_space_uses_style_similarity_map(self):
        """style_embedding_space 的 prior_map 引用自 STYLE_SIMILARITY_MAP。"""
        engine = MatchingEngine()
        # 应包含 STYLE_SIMILARITY_MAP 中的已知风格
        assert "modern-minimal" in engine.style_embedding_space.prior_map
        assert "shadcn-ui" in engine.style_embedding_space.prior_map

    def test_calculate_style_compatibility_uses_new_path(self):
        """calculate_style_compatibility 走 StyleEmbeddingSpace 新路径。"""
        engine = MatchingEngine()
        # mock style_embedding_space.style_similarity 验证调用
        engine.style_embedding_space = MagicMock(spec=StyleEmbeddingSpace)
        engine.style_embedding_space.style_similarity.return_value = 0.77

        component = ComponentMeta("test", {"style": "shadcn-ui"})
        score = engine.calculate_style_compatibility("modern-minimal", component)

        assert score == 0.77
        engine.style_embedding_space.style_similarity.assert_called_once()
        call_args = engine.style_embedding_space.style_similarity.call_args
        # 第一个参数应为 query_style（normalized）
        assert "modern-minimal" in call_args[0][0]

    def test_calculate_style_compatibility_fallback_on_exception(self):
        """style_embedding_space 异常时回退到 STYLE_SIMILARITY_MAP 直查。"""
        engine = MatchingEngine()
        # mock 抛异常
        engine.style_embedding_space = MagicMock(spec=StyleEmbeddingSpace)
        engine.style_embedding_space.style_similarity.side_effect = RuntimeError("fail")

        component = ComponentMeta("test", {"style": "modern-glossy"})
        score = engine.calculate_style_compatibility("modern-minimal", component)
        # 回退到 STYLE_SIMILARITY_MAP["modern-minimal"]["modern-glossy"] = 0.8
        assert score == pytest.approx(0.8, abs=1e-9)

    def test_calculate_style_compatibility_empty_style(self):
        """空风格返回 0.5。"""
        engine = MatchingEngine()
        component = ComponentMeta("test", {"style": ""})
        assert engine.calculate_style_compatibility("modern-minimal", component) == 0.5

        component2 = ComponentMeta("test", {"style": "modern-minimal"})
        assert engine.calculate_style_compatibility("", component2) == 0.5

    def test_unregistered_style_not_zero_in_engine(self):
        """MatchingEngine 中未注册的新风格不再返回 0。"""
        engine = MatchingEngine()
        # 用 mock provider 确保返回非零相似度
        engine.style_embedding_space = StyleEmbeddingSpace(
            prior_map=MatchingEngine.STYLE_SIMILARITY_MAP,
            embedding_provider=MockStyleEmbeddingProvider(),
        )
        component = ComponentMeta("test", {"style": "modern-minimal"})
        score = engine.calculate_style_compatibility("cyberpunk-neon", component)
        # 不再是 0，应基于 embedding 计算
        assert score > 0.0, f"未注册风格不应返回 0，got {score}"

    def test_known_style_pair_returns_weighted_value(self):
        """已知风格对返回加权融合值（非纯 prior，非纯 cosine）。"""
        engine = MatchingEngine()
        # 用 mock provider 隔离
        engine.style_embedding_space = StyleEmbeddingSpace(
            prior_map=MatchingEngine.STYLE_SIMILARITY_MAP,
            embedding_provider=MockStyleEmbeddingProvider(),
        )

        component = ComponentMeta("test", {"style": "shadcn-ui"})
        score = engine.calculate_style_compatibility("modern-minimal", component)

        # prior = 0.9（反向查找 shadcn-ui -> modern-minimal）
        # cosine 由 mock 计算
        expected_prior = 0.9
        # 重新计算 cosine
        v1 = engine.style_embedding_space._get_style_embedding("modern-minimal")
        v2 = engine.style_embedding_space._get_style_embedding("shadcn-ui")
        expected_cosine = _cosine_similarity(v1, v2)
        expected = 0.3 * expected_prior + 0.7 * expected_cosine
        assert score == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# 7. 与原 STYLE_SIMILARITY_MAP 兼容性
# ---------------------------------------------------------------------------

class TestStyleSimilarityMapCompat:
    """验证新路径与原 STYLE_SIMILARITY_MAP 的兼容性。"""

    def test_known_pair_still_high_similarity(self):
        """STYLE_SIMILARITY_MAP 中的高相似度对仍保持高相似度。"""
        space = StyleEmbeddingSpace(
            prior_map=MatchingEngine.STYLE_SIMILARITY_MAP,
            embedding_provider=MockStyleEmbeddingProvider(),
        )
        # shadcn-ui 与 modern-minimal 原 prior = 0.9
        sim = space.style_similarity("shadcn-ui", "modern-minimal")
        assert sim >= 0.5  # 加权后仍应较高

    def test_self_similarity_is_one(self):
        """同风格相似度 = 1.0（prior=1.0 + cosine=1.0）。"""
        space = StyleEmbeddingSpace(
            prior_map=MatchingEngine.STYLE_SIMILARITY_MAP,
            embedding_provider=MockStyleEmbeddingProvider(),
        )
        for style in ("modern-minimal", "shadcn-ui", "material-design", "unstyled"):
            sim = space.style_similarity(style, style)
            assert sim == pytest.approx(1.0, abs=1e-9), \
                f"self-similarity for {style} should be 1.0, got {sim}"

    def test_prior_map_asymmetry_handled(self):
        """STYLE_SIMILARITY_MAP 不对称时双向查找生效。

        STYLE_SIMILARITY_MAP["modern-minimal"]["shadcn-ui"] 不存在，
        但 STYLE_SIMILARITY_MAP["shadcn-ui"]["modern-minimal"] = 0.9。
        """
        space = StyleEmbeddingSpace(
            prior_map=MatchingEngine.STYLE_SIMILARITY_MAP,
            embedding_provider=MockStyleEmbeddingProvider(),
        )
        # 双向都应返回基于 prior=0.9 的加权值
        sim1 = space.style_similarity("modern-minimal", "shadcn-ui")
        sim2 = space.style_similarity("shadcn-ui", "modern-minimal")
        # 对称（prior 双向查找 + cosine 对称）
        assert sim1 == pytest.approx(sim2, abs=1e-9)
        # prior 部分 = 0.9
        prior_part = 0.3 * 0.9  # 0.27
        assert sim1 >= prior_part  # cosine ≥ 0


# ---------------------------------------------------------------------------
# 8. 工厂函数
# ---------------------------------------------------------------------------

class TestGetStyleEmbeddingSpace:
    """get_style_embedding_space 工厂函数验收。"""

    def test_factory_returns_instance(self):
        """工厂函数返回 StyleEmbeddingSpace 实例。"""
        space = get_style_embedding_space(
            prior_map={},
            embedding_provider=MockStyleEmbeddingProvider(),
        )
        assert isinstance(space, StyleEmbeddingSpace)

    def test_factory_passes_provider(self):
        """工厂函数正确传递 embedding_provider。"""
        provider = MockStyleEmbeddingProvider()
        space = get_style_embedding_space(
            prior_map={},
            embedding_provider=provider,
        )
        assert space.embedding_provider is provider


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-p", "no:quadrants"])
