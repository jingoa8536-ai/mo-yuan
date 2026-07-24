"""
test_external_embedding.py — ExternalEmbeddingProvider 抽象测试

覆盖 Task C1.6 验收点：
1. HashingVectorizer.embed 返回固定维度（1024）
2. HashingVectorizer.similarity 对相同文本返回 1.0
3. button vs btn 用 HashingVectorizer 相似度 < 0.7（哈希特性，预期行为）
4. 用 OpenAI mock 验证 button vs btn 相似度 >= 0.7
5. OpenAIEmbeddingProvider 调用 client.embeddings.create 参数正确
6. 降级路径：OpenAIEmbeddingProvider 抛异常 → 降级到 HashingVectorizer
7. 不实际调用 OpenAI/Cohere/BGE API（避免网络依赖）

运行：
    python -m pytest laap_coding/test_external_embedding.py -v -p no:quadrants
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# 确保从任意 cwd 运行 pytest 均可导入 core.vector_enhancer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.vector_enhancer import (  # noqa: E402
    EmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
    CohereEmbeddingProvider,
    LocalBGEProvider,
    HashingVectorizer,
    SimpleVectorModel,
    VectorEnhancer,
    get_embedding_provider,
)


# ---------------------------------------------------------------------------
# 辅助：构造 mock OpenAI embedding（让 button 与 btn 高度相似）
# ---------------------------------------------------------------------------

def _make_mock_openai_embedding(text: str, dim: int = 1536) -> list:
    """构造 mock embedding：button/btn 设计为高度相似（>= 0.7）。"""
    vec = [0.0] * dim
    t = text.lower().strip()
    if t in ("button", "btn"):
        # 共享主方向，btn 仅做轻微扰动 → 余弦相似度 > 0.99
        vec[0] = 1.0
        if t == "btn":
            vec[1] = 0.05
    elif t == "":
        return vec
    else:
        # 其他文本：基于字符和确定性地放置一个非零位
        h = abs(hash(t)) % dim
        vec[h] = 1.0
    return vec


def _build_mock_openai_response(texts):
    """构造类似 openai SDK 的 embeddings.create 返回对象。"""
    resp = MagicMock()
    resp.data = [MagicMock(embedding=_make_mock_openai_embedding(t)) for t in texts]
    return resp


# ---------------------------------------------------------------------------
# 1. HashingVectorizer 基础行为
# ---------------------------------------------------------------------------

class TestHashingVectorizer:
    """HashingVectorizer 兜底实现验收。"""

    def test_embed_returns_fixed_dimension_1024(self):
        """embed 返回固定 1024 维向量。"""
        hv = HashingVectorizer()
        emb = hv.embed(["button", "btn", "dialog"])
        assert len(emb) == 3
        for vec in emb:
            assert len(vec) == 1024

    def test_embed_default_dim_is_1024(self):
        """默认 DIMENSION = 1024。"""
        assert HashingVectorizer.DIMENSION == 1024
        hv = HashingVectorizer()
        assert hv.dim == 1024

    def test_similarity_same_text_is_one(self):
        """相同文本的相似度 = 1.0。"""
        hv = HashingVectorizer()
        emb = hv.embed(["button"])
        sim = hv.similarity(emb[0], emb[0])
        assert sim == pytest.approx(1.0, abs=1e-9)

    def test_similarity_identical_vectors_is_one(self):
        """两个相同向量的相似度 = 1.0。"""
        hv = HashingVectorizer()
        vec = [1.0] + [0.0] * 1023
        assert hv.similarity(vec, vec) == pytest.approx(1.0, abs=1e-9)

    def test_button_vs_btn_similarity_below_07(self):
        """button vs btn 用 HashingVectorizer 相似度 < 0.7（哈希特性，预期）。

        不同 token 哈希到不同位置，无重叠时余弦为 0。
        """
        hv = HashingVectorizer()
        emb = hv.embed(["button", "btn"])
        sim = hv.similarity(emb[0], emb[1])
        assert sim < 0.7

    def test_embed_empty_list_returns_empty(self):
        """空输入返回空列表。"""
        hv = HashingVectorizer()
        assert hv.embed([]) == []

    def test_similarity_zero_vector_returns_zero(self):
        """零向量相似度 = 0.0。"""
        hv = HashingVectorizer()
        zero = [0.0] * 1024
        assert hv.similarity(zero, zero) == 0.0

    def test_embed_is_deterministic(self):
        """相同输入产生相同输出（可重复性）。"""
        hv = HashingVectorizer()
        a1 = hv.embed(["button"])[0]
        a2 = hv.embed(["button"])[0]
        assert a1 == a2

    def test_batch_similarity_shape(self):
        """batch_similarity 返回正确形状的矩阵。"""
        hv = HashingVectorizer()
        matrix = hv.batch_similarity(["button", "card"], ["button", "card"])
        assert len(matrix) == 2
        assert all(len(row) == 2 for row in matrix)
        # 对角自相似 = 1.0（相同文本）
        assert matrix[0][0] == pytest.approx(1.0, abs=1e-9)
        assert matrix[1][1] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 2. EmbeddingProvider 抽象基类
# ---------------------------------------------------------------------------

class TestEmbeddingProviderAbstract:
    """EmbeddingProvider 抽象基类验收。"""

    def test_cannot_instantiate_abstract(self):
        """抽象基类不能直接实例化。"""
        with pytest.raises(TypeError):
            EmbeddingProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_abstract_methods(self):
        """子类必须实现 embed 与 similarity。"""

        class Incomplete(EmbeddingProvider):
            def embed(self, texts):
                return []

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_batch_similarity_default_impl(self):
        """batch_similarity 默认实现基于 embed + similarity。"""

        class Dummy(EmbeddingProvider):
            def embed(self, texts):
                # "a" → [1,0]，其他 → [0,1]
                return [[1.0, 0.0] if t == "a" else [0.0, 1.0] for t in texts]

            def similarity(self, a, b):
                return 1.0 if a == b else 0.5

        d = Dummy()
        m = d.batch_similarity(["a", "b"], ["a", "b"])
        # m[0][0] = sim(a, a) = 1.0；m[0][1] = sim(a, b) = 0.5
        # m[1][0] = sim(b, a) = 0.5；m[1][1] = sim(b, b) = 1.0
        assert m == [[1.0, 0.5], [0.5, 1.0]]


# ---------------------------------------------------------------------------
# 3. OpenAIEmbeddingProvider（mock，不调用真实 API）
# ---------------------------------------------------------------------------

class TestOpenAIEmbeddingProvider:
    """OpenAIEmbeddingProvider 验收（mock client，无网络）。"""

    def test_init_requires_api_key(self):
        """无 API key 时抛 EmbeddingProviderError。"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EmbeddingProviderError):
                OpenAIEmbeddingProvider(api_key=None)

    def test_init_with_explicit_api_key(self):
        """显式传入 api_key 时正常初始化（mock OpenAI 类）。"""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_openai_cls.return_value = MagicMock()
            provider = OpenAIEmbeddingProvider(api_key="fake-key")
            assert provider.model == "text-embedding-3-small"
            assert provider.api_key == "fake-key"
            mock_openai_cls.assert_called_once()

    def test_embed_calls_client_correctly(self):
        """embed 调用 client.embeddings.create，参数正确。"""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.return_value = _build_mock_openai_response(
                ["button", "btn"]
            )

            provider = OpenAIEmbeddingProvider(api_key="fake-key")
            emb = provider.embed(["button", "btn"])

            mock_client.embeddings.create.assert_called_once()
            call_kwargs = mock_client.embeddings.create.call_args
            assert call_kwargs.kwargs["model"] == "text-embedding-3-small"
            assert call_kwargs.kwargs["input"] == ["button", "btn"]
            assert len(emb) == 2
            assert len(emb[0]) == 1536

    def test_button_vs_btn_similarity_above_07(self):
        """mock OpenAI embedding：button vs btn 相似度 >= 0.7。"""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client

            def fake_create(model, input):
                return _build_mock_openai_response(list(input))

            mock_client.embeddings.create.side_effect = fake_create

            provider = OpenAIEmbeddingProvider(api_key="fake-key")
            emb = provider.embed(["button", "btn"])
            sim = provider.similarity(emb[0], emb[1])
            assert sim >= 0.7, f"expected >= 0.7, got {sim}"

    def test_embed_failure_raises_provider_error(self):
        """embed 网络异常时抛 EmbeddingProviderError。"""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.side_effect = RuntimeError("network error")

            provider = OpenAIEmbeddingProvider(api_key="fake-key")
            with pytest.raises(EmbeddingProviderError):
                provider.embed(["button"])

    def test_init_failure_raises_provider_error(self):
        """client 初始化失败时抛 EmbeddingProviderError。"""
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_openai_cls.side_effect = RuntimeError("init failed")
            with pytest.raises(EmbeddingProviderError):
                OpenAIEmbeddingProvider(api_key="fake-key")


# ---------------------------------------------------------------------------
# 4. 降级路径：OpenAI 失败 → HashingVectorizer
# ---------------------------------------------------------------------------

class TestFallbackPath:
    """calculate_tag_similarity 降级路径验收。"""

    def test_fallback_on_init_failure(self, monkeypatch):
        """EMBEDDING_PROVIDER=openai 但无 API key → 降级到 HashingVectorizer。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        enhancer = VectorEnhancer()
        # 不抛异常，降级到 HashingVectorizer 返回 [0, 1]
        sim = enhancer.calculate_tag_similarity(["button"], ["btn"])
        assert 0.0 <= sim <= 1.0

    def test_fallback_on_embed_failure(self, monkeypatch):
        """OpenAI embed 抛异常 → 降级到 HashingVectorizer。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.side_effect = RuntimeError("network down")

            enhancer = VectorEnhancer()
            sim = enhancer.calculate_tag_similarity(["button"], ["btn"])
            # 降级到 HashingVectorizer，button/btn 无哈希重叠 → 0.0
            assert 0.0 <= sim <= 1.0

    def test_fallback_uses_hashing_not_random(self, monkeypatch):
        """降级路径使用 HashingVectorizer，结果确定性（非随机）。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.embeddings.create.side_effect = RuntimeError("fail")

            enhancer = VectorEnhancer()
            sim1 = enhancer.calculate_tag_similarity(["button"], ["button"])
            sim2 = enhancer.calculate_tag_similarity(["button"], ["button"])
            # 相同输入应产生相同结果（HashingVectorizer 确定性）
            assert sim1 == pytest.approx(sim2, abs=1e-9)
            # button vs button 应为 1.0
            assert sim1 == pytest.approx(1.0, abs=1e-9)

    def test_hashing_provider_explicit(self, monkeypatch):
        """EMBEDDING_PROVIDER=hashing 直接使用 HashingVectorizer。"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "hashing")

        enhancer = VectorEnhancer()
        sim = enhancer.calculate_tag_similarity(["button"], ["btn"])
        # HashingVectorizer：button/btn 不同哈希 → 0.0
        assert sim < 0.7

    def test_no_provider_uses_word_vector_path(self, monkeypatch):
        """未配置 EMBEDDING_PROVIDER 时沿用原有词向量路径。"""
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)

        enhancer = VectorEnhancer()
        sim = enhancer.calculate_tag_similarity(["button", "ui"], ["btn", "component"])
        assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 5. SimpleVectorModel 不再使用 random.seed(42)
# ---------------------------------------------------------------------------

class TestSimpleVectorModelNoRandom:
    """验证 SimpleVectorModel 已移除 random.seed(42) 伪向量。"""

    def test_vectors_are_deterministic(self):
        """相同 embedding_size 下，两次构造的向量一致（哈希确定性）。"""
        m1 = SimpleVectorModel(100)
        m2 = SimpleVectorModel(100)
        # 去重后 common_words 顺序固定，向量应一致
        assert m1.wv["button"] == m2.wv["button"]
        assert m1.wv["btn"] == m2.wv["btn"]

    def test_no_random_module_used(self):
        """vector_enhancer 模块不再 import random。"""
        import core.vector_enhancer as ve
        # 模块级不应持有 random 属性
        assert not hasattr(ve, "random")

    def test_vector_dimension_matches_embedding_size(self):
        """向量维度与 embedding_size 一致。"""
        m = SimpleVectorModel(100)
        for word in ("button", "btn", "react"):
            assert len(m.wv[word]) == 100

    def test_similar_words_still_adjusted(self):
        """_adjust_similar_words 仍生效：button 与 btn 经调整后有相似度。"""
        m = SimpleVectorModel(100)
        # 调整后 button/btn 应有非零相似度（共享 base_vec * 0.9）
        from core.vector_enhancer import _cosine_similarity
        sim = _cosine_similarity(m.wv["button"], m.wv["btn"])
        assert sim > 0.0


# ---------------------------------------------------------------------------
# 6. get_embedding_provider 工厂
# ---------------------------------------------------------------------------

class TestGetEmbeddingProvider:
    """工厂函数验收。"""

    def test_hashing_default(self, monkeypatch):
        """无环境变量时返回 HashingVectorizer。"""
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        provider = get_embedding_provider()
        assert isinstance(provider, HashingVectorizer)

    def test_hashing_explicit(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "hashing")
        assert isinstance(get_embedding_provider(), HashingVectorizer)

    def test_unknown_provider_raises(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "unknown_xyz")
        with pytest.raises(EmbeddingProviderError):
            get_embedding_provider()

    def test_openai_without_key_raises(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(EmbeddingProviderError):
            get_embedding_provider()


# ---------------------------------------------------------------------------
# 7. Cohere / BGE 不可用时不影响其他 provider（无网络依赖）
# ---------------------------------------------------------------------------

class TestOtherProvidersNoNetwork:
    """Cohere/BGE 在依赖缺失时抛 EmbeddingProviderError，不触发网络调用。"""

    def test_cohere_init_checks_dependency(self):
        """Cohere 依赖缺失时抛 EmbeddingProviderError（不调用网络）。"""
        try:
            import cohere  # noqa: F401
            cohere_available = True
        except ImportError:
            cohere_available = False

        if cohere_available:
            pytest.skip("cohere installed; skip dependency-missing test")
        with pytest.raises(EmbeddingProviderError):
            CohereEmbeddingProvider(api_key="fake")

    def test_bge_embed_without_model_raises(self):
        """BGE 在 sentence_transformers 不可用时抛 EmbeddingProviderError。"""
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            st_available = True
        except Exception:
            st_available = False

        if st_available:
            pytest.skip("sentence_transformers installed; skip dependency-missing test")
        provider = LocalBGEProvider()
        with pytest.raises(EmbeddingProviderError):
            provider.embed(["button"])
