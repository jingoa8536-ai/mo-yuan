"""
vector_enhancer.py — 向量模型增强模块
======================================

核心能力：
1. Word2Vec预训练词向量支持
2. 标签语义相似度计算
3. 文本向量化与相似度匹配
4. 支持自定义词向量训练
5. 零Token消耗（纯Python计算）
6. 外部 Embedding Provider 抽象（OpenAI / Cohere / 本地 BGE / HashingVectorizer 兜底）

设计原理：
- 使用预训练词向量替代二元向量
- 支持Gensim Word2Vec模型（可选）
- 纯Python回退实现（始终可用）
- 实现平滑余弦相似度
- EmbeddingProvider 抽象基类统一外部嵌入接口，失败降级到 HashingVectorizer（不再使用 random 伪向量）
"""

import os
import json
import math
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

try:
    import gensim
    from gensim.models import Word2Vec
    GENSIM_AVAILABLE = True
except ImportError:
    GENSIM_AVAILABLE = False

try:
    import openai as _openai_module
    OPENAI_AVAILABLE = True
except ImportError:
    _openai_module = None
    OPENAI_AVAILABLE = False

try:
    import cohere as _cohere_module
    COHERE_AVAILABLE = True
except ImportError:
    _cohere_module = None
    COHERE_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
    ST_AVAILABLE = True
except Exception:
    _SentenceTransformer = None
    ST_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import HashingVectorizer as _SKHashingVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    _SKHashingVectorizer = None
    SKLEARN_AVAILABLE = False


# ---------------------------------------------------------------------------
# EmbeddingProvider 抽象基类与异常
# ---------------------------------------------------------------------------

class EmbeddingProviderError(Exception):
    """Embedding Provider 在初始化或调用过程中发生错误时抛出。"""
    pass


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量的余弦相似度。"""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        # 维度不一致时按较短的长度对齐（防御性）
        min_len = min(len(a), len(b))
        a = a[:min_len]
        b = b[:min_len]
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


class EmbeddingProvider(ABC):
    """外部 Embedding Provider 抽象基类。

    子类需实现 `embed` 与 `similarity`；`batch_similarity` 提供默认实现。
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        ...

    @abstractmethod
    def similarity(self, a: List[float], b: List[float]) -> float:
        ...

    def batch_similarity(self, texts_a: List[str], texts_b: List[str]) -> List[List[float]]:
        emb_a = self.embed(texts_a)
        emb_b = self.embed(texts_b)
        return [[self.similarity(a, b) for b in emb_b] for a in emb_a]


# ---------------------------------------------------------------------------
# OpenAI Embedding Provider（text-embedding-3-small, 1536 维）
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider(EmbeddingProvider):
    MODEL = "text-embedding-3-small"
    DIMENSION = 1536

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if not OPENAI_AVAILABLE:
            raise EmbeddingProviderError("openai package not available")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise EmbeddingProviderError("OPENAI_API_KEY not set")
        self.model = model or self.MODEL
        try:
            self.client = _openai_module.OpenAI(api_key=self.api_key)
        except Exception as e:
            raise EmbeddingProviderError(f"Failed to init OpenAI client: {e}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self.client.embeddings.create(model=self.model, input=list(texts))
            return [list(d.embedding) for d in resp.data]
        except Exception as e:
            raise EmbeddingProviderError(f"OpenAI embed failed: {e}")

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)


# ---------------------------------------------------------------------------
# Cohere Embedding Provider（embed-v3, classification, 1024 维）
# ---------------------------------------------------------------------------

class CohereEmbeddingProvider(EmbeddingProvider):
    MODEL = "embed-v3"
    DIMENSION = 1024
    INPUT_TYPE = "classification"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        if not COHERE_AVAILABLE:
            raise EmbeddingProviderError("cohere package not available")
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise EmbeddingProviderError("COHERE_API_KEY not set")
        self.model = model or self.MODEL
        try:
            self.client = _cohere_module.Client(self.api_key)
        except Exception as e:
            raise EmbeddingProviderError(f"Failed to init Cohere client: {e}")

    def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self.client.embed(
                texts=list(texts),
                model=self.model,
                input_type=self.INPUT_TYPE,
            )
            return [list(v) for v in resp.embeddings]
        except Exception as e:
            raise EmbeddingProviderError(f"Cohere embed failed: {e}")

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)


# ---------------------------------------------------------------------------
# 本地 BGE Provider（BAAI/bge-small-zh，懒加载 + 进程级缓存）
# ---------------------------------------------------------------------------

class LocalBGEProvider(EmbeddingProvider):
    MODEL = "BAAI/bge-small-zh"
    DIMENSION = 512
    _MODEL_CACHE: Optional[Any] = None

    def __init__(self, model: Optional[str] = None):
        self.model_name = model or self.MODEL

    def _get_model(self):
        if LocalBGEProvider._MODEL_CACHE is not None:
            return LocalBGEProvider._MODEL_CACHE
        if not ST_AVAILABLE:
            raise EmbeddingProviderError("sentence_transformers not available")
        try:
            LocalBGEProvider._MODEL_CACHE = _SentenceTransformer(self.model_name)
        except Exception as e:
            raise EmbeddingProviderError(f"Failed to load BGE model '{self.model_name}': {e}")
        return LocalBGEProvider._MODEL_CACHE

    def embed(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        try:
            vecs = model.encode(list(texts), convert_to_numpy=True)
            return [list(v) for v in vecs]
        except Exception as e:
            raise EmbeddingProviderError(f"BGE embed failed: {e}")

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)


# ---------------------------------------------------------------------------
# HashingVectorizer 兜底（1024 维，无网络/模型依赖）
# ---------------------------------------------------------------------------

class HashingVectorizer(EmbeddingProvider):
    """基于 sklearn HashingVectorizer 的离线兜底实现。

    - 默认 1024 维，使用 MurmurHash3（sklearn 内部实现）
    - 不依赖网络与外部模型
    - 相似度用余弦相似度
    - 替代 SimpleVectorModel 中的 random.seed(42) 伪向量
    """

    DIMENSION = 1024

    def __init__(self, dim: int = 1024):
        self.dim = dim
        if SKLEARN_AVAILABLE:
            self._sk = _SKHashingVectorizer(
                n_features=dim,
                alternate_sign=True,
                norm=None,
                ngram_range=(1, 1),
                lowercase=True,
            )
        else:
            self._sk = None

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._sk is not None:
            sparse = self._sk.transform(list(texts))
            return [list(sparse[i].toarray()[0]) for i in range(len(texts))]
        # 自实现兜底：MurmurHash3 风格（用 hashlib.blake2b 模拟）
        return [self._hash_text(t) for t in texts]

    def _hash_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = int(hashlib.blake2b(token.encode("utf-8"), digest_size=4).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 31) & 1 == 0 else -1.0
            vec[idx] += sign
        return vec

    def similarity(self, a: List[float], b: List[float]) -> float:
        return _cosine_similarity(a, b)


def get_embedding_provider(name: Optional[str] = None) -> EmbeddingProvider:
    """根据名称构造 EmbeddingProvider 实例。

    name 为空时读取环境变量 EMBEDDING_PROVIDER。
    返回的 provider 已完成初始化；若初始化失败抛 EmbeddingProviderError。
    """
    name = (name or os.environ.get("EMBEDDING_PROVIDER", "")).strip().lower()
    if name == "openai":
        return OpenAIEmbeddingProvider()
    if name == "cohere":
        return CohereEmbeddingProvider()
    if name == "bge":
        return LocalBGEProvider()
    if name == "hashing":
        return HashingVectorizer()
    if not name:
        return HashingVectorizer()
    raise EmbeddingProviderError(f"Unknown embedding provider: {name}")


class SimpleVectorModel:
    def __init__(self, embedding_size: int = 100):
        self.embedding_size = embedding_size
        self.wv = {}
        self._build_default_vectors()

    def _build_default_vectors(self):
        common_words = [
            "react", "vue", "angular", "frontend", "framework",
            "tailwind", "css", "styling", "design", "layout",
            "button", "card", "dialog", "input", "ui", "component",
            "shadcn", "antd", "mui", "element", "library",
            "modern", "minimal", "clean", "elegant", "style",
            "dark", "light", "theme", "color", "mode",
            "mobile", "desktop", "responsive",
            "landing", "page", "home", "section", "hero",
            "form", "table", "list", "modal", "navigation",
            "animation", "transition", "motion", "effect",
            "dashboard", "admin", "panel", "analytics",
            "ecommerce", "shop", "product", "cart",
            "blog", "article", "content", "post",
            "api", "backend", "server", "database",
            "typescript", "javascript", "python", "language",
            "node", "express", "fastapi", "django",
            "graphql", "rest", "endpoint",
            "docker", "kubernetes", "devops", "deployment",
            "testing", "jest", "pytest", "unit", "integration",
            "state", "redux", "zustand", "context", "store",
            "router", "navigation", "route",
            "authentication", "auth", "login", "jwt", "oauth",
            "database", "postgresql", "mongodb", "redis", "orm",
            "performance", "optimization", "cache", "lazy", "loading",
            "accessibility", "a11y", "wcag", "screen", "reader",
            "btn", "dialog", "modal", "card", "tabs", "nav",
            "txt", "img", "tbl", "frm", "icon", "icons", "ui", "ux",
        ]

        # Task C1.5: 用 HashingVectorizer 替代 random.seed(42) 伪向量
        # 保留可重复性（相同输入 → 相同哈希），但不再使用随机数
        hasher = HashingVectorizer(dim=self.embedding_size)
        unique_words = list(dict.fromkeys(common_words))  # 去重保序
        vectors = hasher.embed(unique_words)
        for word, vec in zip(unique_words, vectors):
            self.wv[word] = list(vec)

        self._adjust_similar_words()

    def _adjust_similar_words(self):
        similar_groups = [
            ["button", "btn", "btns"],
            ["dialog", "modal", "popup"],
            ["card", "panel", "container"],
            ["form", "frm", "input"],
            ["table", "tbl", "grid"],
            ["navigation", "nav", "router"],
            ["react", "vue", "angular", "frontend"],
            ["tailwind", "css", "styling"],
            ["dark", "light", "theme"],
            ["mobile", "desktop", "responsive"],
            ["dashboard", "admin", "analytics"],
            ["api", "rest", "graphql"],
            ["auth", "login", "authentication", "jwt", "oauth"],
            ["database", "mongodb", "postgresql", "redis"],
        ]

        for group in similar_groups:
            base_vec = None
            for word in group:
                if word in self.wv:
                    base_vec = self.wv[word]
                    break

            if base_vec:
                for word in group:
                    if word in self.wv:
                        for i in range(self.embedding_size):
                            self.wv[word][i] = base_vec[i] * 0.9 + self.wv[word][i] * 0.1


class VectorEnhancer:
    DEFAULT_EMBEDDING_SIZE = 100
    DEFAULT_WINDOW = 5
    DEFAULT_MIN_COUNT = 1

    def __init__(self, model_path: str = None):
        self.model = None
        self.simple_model = None
        self.model_path = model_path
        self.embedding_size = self.DEFAULT_EMBEDDING_SIZE
        self._load_or_train_model(model_path)

    def _load_or_train_model(self, model_path: str):
        if GENSIM_AVAILABLE:
            if model_path and os.path.exists(model_path):
                try:
                    self.model = Word2Vec.load(model_path)
                    self.embedding_size = self.model.vector_size
                    return
                except Exception:
                    pass

            try:
                corpus = self._build_default_corpus()
                self.model = Word2Vec(
                    sentences=corpus,
                    vector_size=self.DEFAULT_EMBEDDING_SIZE,
                    window=self.DEFAULT_WINDOW,
                    min_count=self.DEFAULT_MIN_COUNT,
                    workers=4,
                    epochs=10
                )
                self.embedding_size = self.model.vector_size
                return
            except Exception:
                pass

        self.simple_model = SimpleVectorModel(self.DEFAULT_EMBEDDING_SIZE)

    def _build_default_corpus(self) -> List[List[str]]:
        corpus = [
            ["react", "vue", "angular", "frontend", "framework"],
            ["tailwind", "css", "styling", "design", "layout"],
            ["button", "card", "dialog", "input", "ui", "component"],
            ["shadcn", "antd", "mui", "element", "component", "library"],
            ["modern", "minimal", "clean", "elegant", "style"],
            ["dark", "light", "theme", "color", "mode"],
            ["mobile", "desktop", "responsive", "layout"],
            ["landing", "page", "home", "section", "hero"],
            ["form", "table", "list", "modal", "navigation"],
            ["animation", "transition", "motion", "effect"],
            ["dashboard", "admin", "panel", "analytics"],
            ["ecommerce", "shop", "product", "cart"],
            ["blog", "article", "content", "post"],
            ["api", "backend", "server", "database"],
            ["typescript", "javascript", "python", "language"],
            ["node", "express", "fastapi", "django", "server"],
            ["graphql", "rest", "api", "endpoint"],
            ["docker", "kubernetes", "devops", "deployment"],
            ["testing", "jest", "pytest", "unit", "integration"],
            ["state", "redux", "zustand", "context", "store"],
            ["router", "navigation", "route", "page"],
            ["authentication", "auth", "login", "jwt", "oauth"],
            ["database", "postgresql", "mongodb", "redis", "orm"],
            ["performance", "optimization", "cache", "lazy", "loading"],
            ["accessibility", "a11y", "wcag", "screen", "reader"],
        ]
        return corpus

    def train_model(self, corpus: List[List[str]], embedding_size: int = 100, window: int = 5, epochs: int = 10):
        self.embedding_size = embedding_size

        if GENSIM_AVAILABLE:
            try:
                self.model = Word2Vec(
                    sentences=corpus,
                    vector_size=embedding_size,
                    window=window,
                    min_count=self.DEFAULT_MIN_COUNT,
                    workers=4,
                    epochs=epochs
                )
                return
            except Exception:
                pass

        self.simple_model = SimpleVectorModel(embedding_size)

    def save_model(self, path: str):
        if self.model:
            self.model.save(path)

    def get_word_vector(self, word: str) -> Optional[List[float]]:
        word_lower = word.lower()

        if self.model and word_lower in self.model.wv:
            return self.model.wv[word_lower].tolist()

        if self.simple_model and word_lower in self.simple_model.wv:
            return self.simple_model.wv[word_lower]

        parts = word_lower.replace("_", " ").replace("-", " ").split()
        if len(parts) > 1:
            vectors = []
            for part in parts:
                if self.model and part in self.model.wv:
                    vectors.append(self.model.wv[part].tolist())
                elif self.simple_model and part in self.simple_model.wv:
                    vectors.append(self.simple_model.wv[part])

            if vectors:
                return self._average_vectors(vectors)

        return None

    def _average_vectors(self, vectors: List[List[float]]) -> List[float]:
        if not vectors:
            return [0.0] * self.embedding_size

        avg = [0.0] * self.embedding_size
        for vec in vectors:
            for i, val in enumerate(vec):
                avg[i] += val / len(vectors)
        return avg

    def calculate_vector_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def calculate_tag_similarity(self, tags_a: List[str], tags_b: List[str]) -> float:
        # Task C1: 优先用配置的 EmbeddingProvider（环境变量 EMBEDDING_PROVIDER）
        # 失败时降级到 HashingVectorizer，不降级到 random
        provider_name = os.environ.get("EMBEDDING_PROVIDER", "").strip().lower()
        if provider_name:
            provider = self._create_provider(provider_name)
            if provider is not None:
                try:
                    vec_a = self._aggregate_embeddings(provider.embed(list(tags_a)))
                    vec_b = self._aggregate_embeddings(provider.embed(list(tags_b)))
                    return provider.similarity(vec_a, vec_b)
                except EmbeddingProviderError:
                    pass  # 落入 HashingVectorizer 降级路径
            # 降级到 HashingVectorizer（不再降级到 random）
            fallback = HashingVectorizer()
            try:
                vec_a = self._aggregate_embeddings(fallback.embed(list(tags_a)))
                vec_b = self._aggregate_embeddings(fallback.embed(list(tags_b)))
                return fallback.similarity(vec_a, vec_b)
            except EmbeddingProviderError:
                return 0.0
        # 未配置 provider：沿用原有词向量路径（SimpleVectorModel 已改用 HashingVectorizer）
        vec_a = self._text_to_vector(tags_a)
        vec_b = self._text_to_vector(tags_b)
        return self.calculate_vector_similarity(vec_a, vec_b)

    def _create_provider(self, name: str) -> Optional[EmbeddingProvider]:
        """根据名称构造 EmbeddingProvider；初始化失败返回 None（触发降级）。"""
        try:
            if name == "openai":
                return OpenAIEmbeddingProvider()
            if name == "cohere":
                return CohereEmbeddingProvider()
            if name == "bge":
                return LocalBGEProvider()
            if name == "hashing":
                return HashingVectorizer()
        except EmbeddingProviderError:
            return None
        return None

    @staticmethod
    def _aggregate_embeddings(embeddings: List[List[float]]) -> List[float]:
        """对多条 embedding 取平均，作为标签集合的聚合表示。"""
        if not embeddings:
            return [0.0] * 1024
        dim = len(embeddings[0])
        avg = [0.0] * dim
        n = len(embeddings)
        for vec in embeddings:
            for i, val in enumerate(vec):
                avg[i] += val / n
        return avg

    def _text_to_vector(self, texts: List[str]) -> List[float]:
        vectors = []
        for text in texts:
            vec = self.get_word_vector(text)
            if vec:
                vectors.append(vec)

        if not vectors:
            return [0.0] * self.embedding_size

        return self._average_vectors(vectors)

    def find_similar_words(self, word: str, top_n: int = 5) -> List[Tuple[str, float]]:
        if self.model:
            try:
                similar = self.model.wv.most_similar(word.lower(), topn=top_n)
                return similar
            except KeyError:
                pass

        if self.simple_model:
            word_vec = self.get_word_vector(word)
            if word_vec:
                similarities = []
                for w, vec in self.simple_model.wv.items():
                    if w != word.lower():
                        sim = self.calculate_vector_similarity(word_vec, vec)
                        if sim > 0.3:
                            similarities.append((w, sim))
                similarities.sort(key=lambda x: x[1], reverse=True)
                return similarities[:top_n]

        return []

    def expand_tags(self, tags: List[str], top_n: int = 3) -> List[str]:
        expanded = set(tags)
        for tag in tags:
            similar = self.find_similar_words(tag, top_n)
            for word, score in similar:
                if score > 0.5:
                    expanded.add(word)
        return list(expanded)

    def has_vector(self, word: str) -> bool:
        word_lower = word.lower()
        if self.model:
            return word_lower in self.model.wv
        if self.simple_model:
            return word_lower in self.simple_model.wv
        return False

    def get_vocabulary(self) -> List[str]:
        if self.model:
            return list(self.model.wv.key_to_index.keys())
        if self.simple_model:
            return list(self.simple_model.wv.keys())
        return []

    def calculate_sentence_similarity(self, sentence_a: str, sentence_b: str) -> float:
        tokens_a = sentence_a.lower().split()
        tokens_b = sentence_b.lower().split()
        return self.calculate_tag_similarity(tokens_a, tokens_b)

    def rank_by_similarity(self, query: str, items: List[str]) -> List[Tuple[str, float]]:
        results = []
        query_vec = self._text_to_vector([query])

        for item in items:
            item_vec = self._text_to_vector([item])
            sim = self.calculate_vector_similarity(query_vec, item_vec)
            results.append((item, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results


def get_vector_enhancer(model_path: str = None) -> VectorEnhancer:
    return VectorEnhancer(model_path)


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness — 向量模型增强模块")
    print("=" * 80)

    enhancer = VectorEnhancer()
    print(f"\n📊 词向量模型信息:")
    print(f"  使用Gensim: {GENSIM_AVAILABLE}")
    print(f"  词表大小: {len(enhancer.get_vocabulary())}")
    print(f"  向量维度: {enhancer.embedding_size}")

    print("\n🔍 测试标签相似度:")
    test_pairs = [
        (["react", "tailwind", "ui"], ["vue", "css", "components"]),
        (["button", "card"], ["dialog", "input"]),
        (["dark", "theme"], ["light", "mode"]),
        (["landing", "page"], ["home", "section"]),
    ]

    for tags_a, tags_b in test_pairs:
        sim = enhancer.calculate_tag_similarity(tags_a, tags_b)
        print(f"  {tags_a} vs {tags_b}: {sim:.4f}")

    print("\n🔍 测试词扩展:")
    test_tags = ["react", "button", "dark"]
    for tag in test_tags:
        expanded = enhancer.expand_tags([tag], top_n=3)
        print(f"  {tag} → {expanded}")

    print("\n🔍 测试相似词查询:")
    test_words = ["react", "button", "dark", "layout"]
    for word in test_words:
        similar = enhancer.find_similar_words(word, top_n=3)
        print(f"  {word}: {[w for w, s in similar]}")

    print("\n✅ 向量增强模块测试完成")