"""
style_register.py — 风格注册中心与风格嵌入空间
================================================

Task B1: 风格空间向量化
1. ``StyleRegister`` — 运行时注册新风格描述，供嵌入空间编码使用
2. ``StyleEmbeddingSpace`` — 用 ``EmbeddingProvider`` 编码风格描述，
   与 ``STYLE_SIMILARITY_MAP`` 先验加权融合（0.3 prior + 0.7 embedding）

设计要点
--------
- ``prior_map`` 默认引用 ``matching_engine.STYLE_SIMILARITY_MAP`` 作为冷启动先验
- ``embedding_provider`` 默认使用 ``LocalBGEProvider``（懒加载 + 进程级缓存），
  初始化失败时降级到 ``HashingVectorizer``（无网络/模型依赖）
- 风格 embedding 进程内缓存，避免重复编码
- 风格描述优先从 ``StyleRegister`` 获取，未注册时用风格名本身作为描述
- 未在 ``prior_map`` 中的新风格不再返回 0，而是基于 embedding 余弦相似度计算
"""

from typing import Dict, List, Optional

from .vector_enhancer import (
    EmbeddingProvider,
    EmbeddingProviderError,
    HashingVectorizer,
    LocalBGEProvider,
    _cosine_similarity,
)


# ---------------------------------------------------------------------------
# STYLE_SIMILARITY_MAP 中已知风格的默认描述
# 用于让 EmbeddingProvider 能编码既有风格的语义
# ---------------------------------------------------------------------------

_DEFAULT_STYLE_DESCRIPTIONS: Dict[str, str] = {
    "modern-minimal": (
        "Modern minimal design with clean lines, simple typography, "
        "and ample whitespace"
    ),
    "modern-glossy": (
        "Modern glossy design with reflective surfaces, gradients, "
        "and smooth animations"
    ),
    "modern-standard": (
        "Modern standard design with balanced aesthetics and "
        "conventional layout"
    ),
    "tailwind-semantic": (
        "Tailwind semantic design with utility-first CSS and "
        "semantic class naming"
    ),
    "tailwind-landing": (
        "Tailwind landing page design with marketing-focused layout "
        "and conversion optimization"
    ),
    "enterprise-standard": (
        "Enterprise standard design with professional aesthetics "
        "and business-focused components"
    ),
    "enterprise-meta": (
        "Enterprise meta design with advanced data visualization "
        "and complex interactions"
    ),
    "material-design": (
        "Material design with Google's design system, elevation, "
        "and meaningful motion"
    ),
    "unstyled": (
        "Unstyled design with no default styling, providing maximum "
        "customization freedom"
    ),
    "shadcn-flutter": (
        "shadcn-flutter design with Flutter implementation of "
        "shadcn aesthetic"
    ),
    "shadcn-ui": (
        "shadcn-ui design with modern React components built on "
        "Radix UI and Tailwind CSS"
    ),
}


class StyleRegister:
    """运行时风格注册中心。

    预填 ``STYLE_SIMILARITY_MAP`` 中已知风格的默认描述，并支持运行时
    通过 ``register()`` 注册新风格描述，供 ``StyleEmbeddingSpace`` 编码。
    """

    def __init__(self, default_descriptions: Optional[Dict[str, str]] = None):
        self._descriptions: Dict[str, str] = dict(
            default_descriptions if default_descriptions is not None
            else _DEFAULT_STYLE_DESCRIPTIONS
        )

    def register(self, name: str, description: str) -> None:
        """运行时注册新风格描述。

        - ``name`` 为空时直接忽略（防御性）
        - 同名风格会被覆盖（最后一次注册生效）
        """
        if not name:
            return
        self._descriptions[name] = description

    def get_description(self, name: str) -> Optional[str]:
        """获取风格描述；未注册返回 None。"""
        return self._descriptions.get(name)

    def list_styles(self) -> List[str]:
        """列出所有已注册风格名。"""
        return list(self._descriptions.keys())


class StyleEmbeddingSpace:
    """风格嵌入空间：先验相似度 + embedding 余弦相似度加权融合。

    ``style_similarity(s1, s2) = 0.3 * prior_score + 0.7 * cosine_emb``

    - ``prior_score`` 来自 ``prior_map``（冷启动先验），未命中返回 0.5
    - ``cosine_emb`` 来自 ``embedding_provider`` 对风格描述的编码
    """

    PRIOR_WEIGHT = 0.3
    EMBEDDING_WEIGHT = 0.7
    DEFAULT_PRIOR_SCORE = 0.5  # prior_map 找不到时的中性默认值

    def __init__(
        self,
        prior_map: Optional[Dict[str, Dict[str, float]]] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        style_register: Optional[StyleRegister] = None,
    ):
        # 先验图：默认引用 matching_engine.STYLE_SIMILARITY_MAP（懒导入避免循环依赖）
        if prior_map is None:
            try:
                from .matching_engine import MatchingEngine
                prior_map = MatchingEngine.STYLE_SIMILARITY_MAP
            except Exception:
                prior_map = {}
        self.prior_map: Dict[str, Dict[str, float]] = prior_map or {}

        # 风格注册中心
        self.style_register: StyleRegister = style_register or StyleRegister()

        # Embedding Provider：默认 LocalBGEProvider（懒加载 + 进程级缓存），
        # 初始化失败降级到 HashingVectorizer
        if embedding_provider is not None:
            self.embedding_provider: EmbeddingProvider = embedding_provider
        else:
            self.embedding_provider = self._init_default_provider()

        # 风格 embedding 缓存：style_name -> embedding vector
        self._embedding_cache: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def style_similarity(self, s1: str, s2: str) -> float:
        """计算两个风格的相似度：0.3 * prior + 0.7 * cosine_emb。"""
        if not s1 or not s2:
            return 0.0

        s1_norm = s1.lower().strip()
        s2_norm = s2.lower().strip()

        prior_score = self._lookup_prior(s1_norm, s2_norm)
        cosine_emb = self._compute_cosine(s1_norm, s2_norm)

        return self.PRIOR_WEIGHT * prior_score + self.EMBEDDING_WEIGHT * cosine_emb

    def _get_style_embedding(self, style: str) -> List[float]:
        """获取风格 embedding（带缓存）。

        - 风格描述优先从 ``StyleRegister`` 获取，未注册时用风格名本身
        - 缓存命中直接返回，避免重复编码
        - provider 调用失败时缓存空向量，防止重复失败调用
        """
        if style in self._embedding_cache:
            return self._embedding_cache[style]

        description = self.style_register.get_description(style) or style

        try:
            embeddings = self.embedding_provider.embed([description])
            if embeddings and len(embeddings) > 0:
                vec = list(embeddings[0])
            else:
                vec = []
        except (EmbeddingProviderError, Exception):
            vec = []

        self._embedding_cache[style] = vec
        return vec

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _init_default_provider(self) -> EmbeddingProvider:
        """默认 provider：LocalBGEProvider，失败降级到 HashingVectorizer。"""
        try:
            return LocalBGEProvider()
        except Exception:
            return HashingVectorizer()

    def _lookup_prior(self, s1: str, s2: str) -> float:
        """从 prior_map 查找先验分数；找不到返回 DEFAULT_PRIOR_SCORE。

        支持双向查找：先 ``prior_map[s1][s2]``，再 ``prior_map[s2][s1]``。
        """
        row = self.prior_map.get(s1)
        if row is not None:
            score = row.get(s2)
            if score is not None:
                return float(score)
        # 反向查找
        row_rev = self.prior_map.get(s2)
        if row_rev is not None:
            score = row_rev.get(s1)
            if score is not None:
                return float(score)
        return self.DEFAULT_PRIOR_SCORE

    def _compute_cosine(self, s1: str, s2: str) -> float:
        """计算两个风格描述 embedding 的余弦相似度。"""
        try:
            v1 = self._get_style_embedding(s1)
            v2 = self._get_style_embedding(s2)
            if not v1 or not v2:
                return 0.0
            return self.embedding_provider.similarity(v1, v2)
        except Exception:
            # provider 异常时返回中性值，避免破坏加权
            return self.DEFAULT_PRIOR_SCORE


def get_style_embedding_space(
    prior_map: Optional[Dict[str, Dict[str, float]]] = None,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> StyleEmbeddingSpace:
    """构造 ``StyleEmbeddingSpace`` 实例的工厂函数。"""
    return StyleEmbeddingSpace(
        prior_map=prior_map,
        embedding_provider=embedding_provider,
    )
