"""
matching_engine.py — LAAP Harness 匹配引擎（增强版）
===================================================

集成所有优化模块的增强版匹配引擎：
1. 向量模型增强 — Word2Vec预训练词向量提升语义理解
2. 语义扩展 — 同义词扩展和缩写识别
3. 性能优化 — 倒排索引实现 O(log n) 查询
4. 上下文感知 — 用户历史偏好动态调整权重
5. 增量更新 — 数据库增量同步机制

加权组合相似度评分算法：
- TagSimilarity: 标签向量余弦相似度（增强语义）
- StyleCompatibility: 风格兼容性评分
- DependencyMatch: 依赖图匹配度评分
- QualityScore: 质量评分
- MatchScore = α×TagSimilarity + β×StyleCompatibility + γ×DependencyMatch + δ×QualityScore
"""

import os
import json
import math
import time
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

HARNESS_CORE = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(HARNESS_CORE, "laap_harness_database.json")


class MatchThreshold(Enum):
    PERFECT = 0.90
    GOOD = 0.75
    AVAILABLE = 0.60


class MatchLevel(Enum):
    PERFECT = "完美匹配"
    GOOD = "良好匹配"
    AVAILABLE = "可用匹配"
    POOR = "较差匹配"


class MatchingStrategy(Enum):
    EXACT = "精确匹配"
    FUZZY = "模糊匹配"
    COMBINED = "组合匹配"
    DEGRADATION = "降级匹配"


class ComponentMeta:
    def __init__(self, component_id: str, data: Dict[str, Any]):
        self.id = component_id
        self.name = data.get("name", "")
        self.type = data.get("type", "")
        self.tags = data.get("tags", [])
        self.style = data.get("style", "")
        self.domain = data.get("domain", [])
        self.quality = data.get("quality", {})
        self.components = data.get("components", [])
        self.tech = data.get("tech", "")
        self.raw = data

    def get_all_features(self) -> List[str]:
        features = []
        features.extend(self.tags)
        features.extend(self.domain)
        features.extend(self.components)
        if self.style:
            features.append(self.style)
        if self.tech:
            features.append(self.tech)
        return features


class MatchingEngine:
    ALPHA = 0.35
    BETA = 0.25
    GAMMA = 0.20
    DELTA = 0.20

    # 超过此组件数阈值时自动切换到 SQLite FTS5 后端
    FTS5_THRESHOLD = 50000

    STYLE_SIMILARITY_MAP = {
        "modern-minimal": {"modern-minimal": 1.0, "modern-glossy": 0.8, "modern-standard": 0.75, "tailwind-semantic": 0.7},
        "modern-glossy": {"modern-minimal": 0.8, "modern-glossy": 1.0, "modern-standard": 0.85, "tailwind-semantic": 0.6},
        "modern-standard": {"modern-minimal": 0.75, "modern-glossy": 0.85, "modern-standard": 1.0, "tailwind-semantic": 0.7},
        "tailwind-semantic": {"modern-minimal": 0.7, "modern-glossy": 0.6, "modern-standard": 0.7, "tailwind-semantic": 1.0},
        "tailwind-landing": {"modern-minimal": 0.6, "modern-glossy": 0.5, "modern-standard": 0.55, "tailwind-semantic": 0.9},
        "enterprise-standard": {"enterprise-standard": 1.0, "enterprise-meta": 0.9, "modern-standard": 0.6},
        "enterprise-meta": {"enterprise-standard": 0.9, "enterprise-meta": 1.0, "modern-standard": 0.55},
        "material-design": {"material-design": 1.0, "modern-standard": 0.6, "modern-minimal": 0.5},
        "unstyled": {"unstyled": 1.0, "shadcn-flutter": 0.8},
        "shadcn-flutter": {"unstyled": 0.8, "shadcn-flutter": 1.0, "modern-minimal": 0.7},
        "shadcn-ui": {"shadcn-ui": 1.0, "modern-minimal": 0.9, "modern-standard": 0.85, "tailwind-semantic": 0.8},
        "racing-game": {"racing-game": 1.0, "sports-game": 0.85, "simulation": 0.75, "arcade": 0.7, "action": 0.5},
        "sports-game": {"racing-game": 0.85, "sports-game": 1.0, "simulation": 0.7, "arcade": 0.75, "action": 0.6},
        "simulation": {"racing-game": 0.75, "sports-game": 0.7, "simulation": 1.0, "strategy": 0.65, "rpg": 0.5},
        "arcade": {"racing-game": 0.7, "sports-game": 0.75, "arcade": 1.0, "action": 0.8, "rpg": 0.6},
        "action": {"racing-game": 0.5, "sports-game": 0.6, "arcade": 0.8, "action": 1.0, "rpg": 0.75},
        "rpg": {"arcade": 0.6, "action": 0.75, "rpg": 1.0, "strategy": 0.6, "simulation": 0.5},
        "strategy": {"simulation": 0.65, "rpg": 0.6, "strategy": 1.0, "action": 0.45, "sports-game": 0.35},
        "godot-native": {"godot-native": 1.0, "racing-game": 0.9, "sports-game": 0.85, "arcade": 0.8, "action": 0.75},
    }

    QUALITY_SCORE_MAP = {
        "maturity": {"production": 1.0, "beta": 0.7, "alpha": 0.4, "experimental": 0.2},
        "maintenance": {"active": 1.0, "stable": 0.8, "slow": 0.5, "abandoned": 0.2},
        "documentation": {"excellent": 1.0, "good": 0.8, "fair": 0.5, "poor": 0.2, "internal": 0.3},
    }

    def __init__(self, database_path: str = None, use_enhancements: bool = True):
        self.db_path = database_path or DATABASE_PATH
        self.database = self._load_database()
        self.all_components = self._build_component_registry()
        self.current_strategy = MatchingStrategy.COMBINED
        self.shadcn_bridge = None
        self.shadcn_components = {}
        self.use_enhancements = use_enhancements
        self.vector_enhancer = None
        self.semantic_expander = None
        self.inverted_index = None
        self.context_awareness = None
        self.incremental_updater = None
        # FTS5 后端（大规模数据场景自动启用）
        self.fts5_backend = None
        # Task B1: 风格嵌入空间（先验 + embedding 加权融合）
        # STYLE_SIMILARITY_MAP 降级为冷启动先验，不再作为唯一来源
        self.style_embedding_space = None
        self._init_enhancements()
        self._init_style_embedding_space()
        self._maybe_init_fts5_backend()

    def _init_enhancements(self):
        if not self.use_enhancements:
            return

        try:
            from .vector_enhancer import get_vector_enhancer
            self.vector_enhancer = get_vector_enhancer()
        except ImportError:
            pass

        try:
            from .semantic_expander import get_semantic_expander
            self.semantic_expander = get_semantic_expander()
        except ImportError:
            pass

        try:
            from .inverted_index import create_inverted_index
            docs = [comp.raw for comp in self.all_components]
            self.inverted_index = create_inverted_index(docs)
        except ImportError:
            pass

        try:
            from .context_awareness import get_context_awareness
            self.context_awareness = get_context_awareness()
        except ImportError:
            pass

        try:
            from .incremental_updater import get_incremental_updater
            self.incremental_updater = get_incremental_updater()
        except ImportError:
            pass

    def _maybe_init_fts5_backend(self) -> None:
        """若组件数超过 FTS5_THRESHOLD，自动切换到 SQLite FTS5 后端。

        当前数据库规模小（< 50000），不会触发自动切换；但代码路径需就绪，
        以便在数据库扩展到大体量时无缝启用 FTS5 查询。
        """
        if len(self.all_components) <= self.FTS5_THRESHOLD:
            return
        try:
            from .incremental_updater import FTS5Backend
            fts5_path = os.path.join(HARNESS_CORE, "fts5_backend.sqlite3")
            self.fts5_backend = FTS5Backend(fts5_path)
            for comp in self.all_components:
                self.fts5_backend.add_document(comp.id, {
                    "tags": comp.tags or [],
                    "name": [comp.name] if comp.name else [],
                    "components": comp.components or [],
                    "domain": comp.domain or [],
                })
        except Exception:
            # FTS5 不可用时静默回退到内存倒排索引
            self.fts5_backend = None

    def _init_style_embedding_space(self) -> None:
        """Task B1: 初始化风格嵌入空间。

        - prior_map 用 ``STYLE_SIMILARITY_MAP`` 作为冷启动先验
        - embedding_provider 默认 ``LocalBGEProvider``，失败降级到 ``HashingVectorizer``
        - 初始化失败时 ``style_embedding_space`` 保持 None，
          ``calculate_style_compatibility`` 会回退到原 STYLE_SIMILARITY_MAP 直查
        """
        try:
            from .style_register import StyleEmbeddingSpace
            self.style_embedding_space = StyleEmbeddingSpace(
                prior_map=self.STYLE_SIMILARITY_MAP,
            )
        except Exception:
            self.style_embedding_space = None

    def set_shadcn_bridge(self, bridge) -> None:
        self.shadcn_bridge = bridge

    def sync_shadcn_components(self) -> int:
        if not self.shadcn_bridge:
            return 0

        try:
            components = self.shadcn_bridge.integrator.list_components()
            for comp in components:
                name = comp.get("name", comp) if isinstance(comp, dict) else comp
                self.shadcn_components[name] = comp
            return len(self.shadcn_components)
        except Exception:
            return 0

    def _build_component_registry(self) -> List[ComponentMeta]:
        registry = []
        for lib_id, data in self.database.get("ui_libraries", {}).items():
            registry.append(ComponentMeta(lib_id, {"type": "ui", **data}))
        for lib_id, data in self.database.get("animation_libraries", {}).items():
            registry.append(ComponentMeta(lib_id, {"type": "animation", **data}))
        for lib_id, data in self.database.get("icon_libraries", {}).items():
            registry.append(ComponentMeta(lib_id, {"type": "icons", **data}))
        for lib_id, data in self.database.get("game_libraries", {}).items():
            registry.append(ComponentMeta(lib_id, {"type": "game", **data}))
        return registry

    def _load_database(self) -> Dict[str, Any]:
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _cosine_similarity(self, vec_a: List[str], vec_b: List[str]) -> float:
        if not vec_a or not vec_b:
            return 0.0

        all_features = set(vec_a + vec_b)
        dict_a = {f: 1 for f in vec_a}
        dict_b = {f: 1 for f in vec_b}

        dot_product = sum(dict_a.get(f, 0) * dict_b.get(f, 0) for f in all_features)
        norm_a = math.sqrt(sum(v * v for v in dict_a.values()))
        norm_b = math.sqrt(sum(v * v for v in dict_b.values()))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _expand_tags(self, tags: List[str]) -> List[str]:
        if not self.semantic_expander:
            return tags
        expanded = set(tags)
        for tag in tags:
            expanded.update(self.semantic_expander.expand_tags(tag))
        return list(expanded)

    def calculate_tag_similarity(self, query_tags: List[str], component: ComponentMeta) -> float:
        expanded_query = self._expand_tags(query_tags)
        expanded_component = self._expand_tags(component.tags)

        if self.vector_enhancer:
            try:
                return self.vector_enhancer.calculate_tag_similarity(expanded_query, expanded_component)
            except Exception:
                pass

        return self._cosine_similarity(expanded_query, expanded_component)

    def calculate_style_compatibility(self, query_style: str, component: ComponentMeta) -> float:
        if not query_style or not component.style:
            return 0.5

        query_style_norm = self._normalize_term(query_style)
        component_style_norm = self._normalize_term(component.style)

        # Task B1: 优先走 StyleEmbeddingSpace（0.3 prior + 0.7 embedding）
        # STYLE_SIMILARITY_MAP 降级为冷启动先验，不再作为唯一来源
        if self.style_embedding_space is not None:
            try:
                return self.style_embedding_space.style_similarity(
                    query_style_norm, component_style_norm
                )
            except Exception:
                pass  # 落入下面的兜底路径

        # 兜底：直接查 STYLE_SIMILARITY_MAP（冷启动先验）
        style_map = self.STYLE_SIMILARITY_MAP.get(query_style_norm, {})
        score = style_map.get(component_style_norm)
        if score is not None:
            return score

        # 反向查找（STYLE_SIMILARITY_MAP 不对称时）
        style_map_rev = self.STYLE_SIMILARITY_MAP.get(component_style_norm, {})
        score_rev = style_map_rev.get(query_style_norm)
        if score_rev is not None:
            return score_rev

        # 最终兜底：未注册新风格返回中性值 0.5（不再返回 0）
        return 0.5

    def _normalize_term(self, term: str) -> str:
        if not term:
            return term
        if self.semantic_expander:
            try:
                return self.semantic_expander.normalize_term(term)
            except Exception:
                pass
        return term.lower().strip()

    def calculate_dependency_match(self, query_tech: str, component: ComponentMeta) -> float:
        if not query_tech:
            return 0.5

        query_lower = query_tech.lower()
        component_tech_lower = component.tech.lower() if component.tech else ""

        if query_lower in component_tech_lower or component_tech_lower in query_lower:
            return 1.0

        query_techs = [t.strip().lower() for t in query_lower.replace("+", " ").replace("/", " ").split()]
        component_techs = [t.strip().lower() for t in component_tech_lower.replace("+", " ").replace("/", " ").split()]

        if self.semantic_expander:
            try:
                query_techs_expanded = []
                for tech in query_techs:
                    query_techs_expanded.extend(self.semantic_expander.expand_tags(tech))
                comp_techs_expanded = []
                for tech in component_techs:
                    comp_techs_expanded.extend(self.semantic_expander.expand_tags(tech))

                common = set(query_techs_expanded) & set(comp_techs_expanded)
                if common:
                    return 0.5 + 0.5 * (len(common) / max(len(query_techs_expanded), len(comp_techs_expanded)))
            except Exception:
                pass

        common = set(query_techs) & set(component_techs)
        if common:
            return 0.5 + 0.5 * (len(common) / max(len(query_techs), len(component_techs)))

        return 0.0

    def calculate_quality_score(self, component: ComponentMeta) -> float:
        quality = component.quality or {}
        scores = []

        maturity = quality.get("maturity", "")
        scores.append(self.QUALITY_SCORE_MAP["maturity"].get(maturity, 0.5))

        maintenance = quality.get("maintenance", "")
        scores.append(self.QUALITY_SCORE_MAP["maintenance"].get(maintenance, 0.5))

        documentation = quality.get("documentation", "")
        scores.append(self.QUALITY_SCORE_MAP["documentation"].get(documentation, 0.5))

        if not scores:
            return 0.5

        return sum(scores) / len(scores)

    def calculate_match_score(self, intent: Dict[str, Any], component: ComponentMeta, weights: Dict[str, float] = None) -> Dict[str, float]:
        tags = intent.get("tags", [])
        style = intent.get("style", "")
        tech = intent.get("tech", "")

        tag_sim = self.calculate_tag_similarity(tags, component)
        style_comp = self.calculate_style_compatibility(style, component)
        dep_match = self.calculate_dependency_match(tech, component)
        quality = self.calculate_quality_score(component)

        w = weights or {
            "alpha": self.ALPHA,
            "beta": self.BETA,
            "gamma": self.GAMMA,
            "delta": self.DELTA,
        }

        total = (
            w["alpha"] * tag_sim
            + w["beta"] * style_comp
            + w["gamma"] * dep_match
            + w["delta"] * quality
        )

        return {
            "tag_similarity": tag_sim,
            "style_compatibility": style_comp,
            "dependency_match": dep_match,
            "quality_score": quality,
            "total_score": total,
        }

    def get_match_level(self, score: float) -> MatchLevel:
        if score >= MatchThreshold.PERFECT.value:
            return MatchLevel.PERFECT
        elif score >= MatchThreshold.GOOD.value:
            return MatchLevel.GOOD
        elif score >= MatchThreshold.AVAILABLE.value:
            return MatchLevel.AVAILABLE
        else:
            return MatchLevel.POOR

    def _filter_candidates(self, intent: Dict[str, Any]) -> List[ComponentMeta]:
        # 优先用 FTS5 后端（大规模数据场景）
        if self.fts5_backend:
            return self._filter_candidates_fts5(intent)

        if not self.inverted_index:
            return self.all_components

        query_terms = []
        query_terms.extend(intent.get("tags", []))
        if intent.get("style"):
            query_terms.append(intent["style"])
        if intent.get("tech"):
            query_terms.append(intent["tech"])

        if not query_terms:
            return self.all_components

        query_str = " ".join(query_terms)
        doc_ids = self.inverted_index.search(query_str)

        candidates = []
        for doc_id in doc_ids:
            doc = self.inverted_index.get_document(doc_id)
            if doc:
                for comp in self.all_components:
                    if comp.id == doc.get("id"):
                        candidates.append(comp)
                        break

        return candidates if candidates else self.all_components

    def _filter_candidates_fts5(self, intent: Dict[str, Any]) -> List[ComponentMeta]:
        """FTS5 后端候选过滤：将 intent 的 tags/style/tech 拼接为查询字符串。"""
        query_terms = []
        query_terms.extend(intent.get("tags", []))
        if intent.get("style"):
            query_terms.append(intent["style"])
        if intent.get("tech"):
            query_terms.append(intent["tech"])

        if not query_terms:
            return self.all_components

        query_str = " ".join(str(t) for t in query_terms)
        doc_ids = self.fts5_backend.search(query_str)
        id_set = set(doc_ids)
        candidates = [comp for comp in self.all_components if comp.id in id_set]
        return candidates if candidates else self.all_components

    def match_intent(self, intent: Dict[str, Any], user_id: str = None, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        results = []
        strategy = self.current_strategy

        weights = None
        if self.context_awareness and user_id:
            weights = self.context_awareness.get_dynamic_weights(user_id, context)

        if self.context_awareness and user_id:
            intent = self.context_awareness.get_context_enhanced_intent(intent, user_id)

        candidates = self._filter_candidates(intent)

        for component in candidates:
            scores = self.calculate_match_score(intent, component, weights)
            level = self.get_match_level(scores["total_score"])

            if strategy == MatchingStrategy.EXACT:
                if scores["total_score"] < MatchThreshold.PERFECT.value:
                    continue
            elif strategy == MatchingStrategy.FUZZY:
                if scores["total_score"] < MatchThreshold.AVAILABLE.value:
                    continue
            elif strategy == MatchingStrategy.DEGRADATION:
                pass

            results.append({
                "component_id": component.id,
                "name": component.name,
                "type": component.type,
                "scores": scores,
                "match_level": level.value,
                "component": component.raw,
            })

        results.sort(key=lambda x: x["scores"]["total_score"], reverse=True)

        if self.context_awareness and user_id:
            tags = intent.get("tags", [])
            style = intent.get("style", "")
            tech = intent.get("tech", "")
            self.context_awareness.record_user_interaction(user_id, tags, style, tech)

        return results

    def search_components(self, query: str) -> List[Dict[str, Any]]:
        if self.fts5_backend:
            doc_ids = self.fts5_backend.search(query)
            id_set = set(doc_ids)
            candidates = [comp for comp in self.all_components if comp.id in id_set]
        elif self.inverted_index:
            doc_ids = self.inverted_index.search(query)
            candidates = []
            for doc_id in doc_ids:
                doc = self.inverted_index.get_document(doc_id)
                if doc:
                    for comp in self.all_components:
                        if comp.id == doc.get("id"):
                            candidates.append(comp)
                            break
        else:
            candidates = self.all_components

        query_lower = query.lower()
        results = []

        for component in candidates:
            match_score = 0.0
            match_reasons = []

            if query_lower in component.name.lower():
                match_score += 0.4
                match_reasons.append("name")

            if component.tags:
                tag_match = any(query_lower in tag.lower() for tag in component.tags)
                if tag_match:
                    match_score += 0.3
                    match_reasons.append("tags")

            if component.components:
                comp_match = any(query_lower in c.lower() for c in component.components)
                if comp_match:
                    match_score += 0.2
                    match_reasons.append("components")

            if component.domain:
                domain_match = any(query_lower in d.lower() for d in component.domain)
                if domain_match:
                    match_score += 0.1
                    match_reasons.append("domain")

            if self.semantic_expander:
                try:
                    query_expanded = set(self.semantic_expander.expand_tags(query_lower))
                    component_features = set([str(f).lower() for f in component.get_all_features()])
                    if query_expanded & component_features:
                        match_score += 0.1
                        match_reasons.append("semantic")
                except Exception:
                    pass

            if match_score > 0:
                results.append({
                    "component_id": component.id,
                    "name": component.name,
                    "type": component.type,
                    "match_score": match_score,
                    "match_reasons": match_reasons,
                    "component": component.raw,
                })

        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results

    def get_matching_strategy(self) -> Dict[str, Any]:
        return {
            "current_strategy": self.current_strategy.value,
            "available_strategies": [s.value for s in MatchingStrategy],
            "weights": {
                "alpha": self.ALPHA,
                "beta": self.BETA,
                "gamma": self.GAMMA,
                "delta": self.DELTA,
            },
            "thresholds": {
                "perfect": MatchThreshold.PERFECT.value,
                "good": MatchThreshold.GOOD.value,
                "available": MatchThreshold.AVAILABLE.value,
            },
            "component_count": len(self.all_components),
            "enhancements": {
                "vector_enhancer": self.vector_enhancer is not None,
                "semantic_expander": self.semantic_expander is not None,
                "inverted_index": self.inverted_index is not None,
                "context_awareness": self.context_awareness is not None,
                "incremental_updater": self.incremental_updater is not None,
                "fts5_backend": self.fts5_backend is not None,
            },
            "fts5_threshold": self.FTS5_THRESHOLD,
        }

    def set_matching_strategy(self, strategy: MatchingStrategy) -> None:
        self.current_strategy = strategy

    def set_weights(self, alpha: float = None, beta: float = None, gamma: float = None, delta: float = None) -> None:
        if alpha is not None:
            self.ALPHA = alpha
        if beta is not None:
            self.BETA = beta
        if gamma is not None:
            self.GAMMA = gamma
        if delta is not None:
            self.DELTA = delta

        total = self.ALPHA + self.BETA + self.GAMMA + self.DELTA
        if total != 1.0:
            self.ALPHA /= total
            self.BETA /= total
            self.GAMMA /= total
            self.DELTA /= total

    def find_best_match(self, intent: Dict[str, Any], user_id: str = None, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        results = self.match_intent(intent, user_id, context)
        return results[0] if results else None

    def find_matches_by_level(self, intent: Dict[str, Any], level: MatchLevel, user_id: str = None, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        results = self.match_intent(intent, user_id, context)
        return [r for r in results if r["match_level"] == level.value]

    def match_shadcn_component(self, intent: Dict[str, Any], user_id: str = None) -> List[Dict[str, Any]]:
        if not self.shadcn_components:
            self.sync_shadcn_components()

        results = []
        query_tags = intent.get("tags", [])
        query_tech = intent.get("tech", "")
        query_style = intent.get("style", "")

        weights = None
        if self.context_awareness and user_id:
            weights = self.context_awareness.get_dynamic_weights(user_id)

        for name, comp in self.shadcn_components.items():
            comp_tags = [name]
            if isinstance(comp, dict):
                comp_tags.extend(comp.get("tags", []))
                comp_tags.extend(comp.get("categories", []))

            expanded_query = self._expand_tags(query_tags)
            expanded_comp = self._expand_tags(comp_tags)

            if self.vector_enhancer:
                try:
                    tag_sim = self.vector_enhancer.calculate_tag_similarity(expanded_query, expanded_comp)
                except Exception:
                    tag_sim = self._cosine_similarity(expanded_query, expanded_comp)
            else:
                tag_sim = self._cosine_similarity(expanded_query, expanded_comp)

            tech_match = 0.5
            if query_tech:
                tech_match = self.calculate_dependency_match(query_tech, ComponentMeta(name, {"tech": "React + Tailwind + shadcn"}))

            style_comp = 0.5
            if query_style:
                style_comp = self.calculate_style_compatibility(query_style, ComponentMeta(name, {"style": "shadcn-ui"}))

            w = weights or {
                "alpha": self.ALPHA,
                "beta": self.BETA,
                "gamma": self.GAMMA,
                "delta": self.DELTA,
            }

            total_score = (
                w["alpha"] * tag_sim
                + w["beta"] * style_comp
                + w["gamma"] * tech_match
                + w["delta"] * 0.9
            )

            level = self.get_match_level(total_score)

            result = {
                "component_id": f"shadcn:{name}",
                "name": name,
                "type": "shadcn-ui",
                "scores": {
                    "tag_similarity": tag_sim,
                    "style_compatibility": style_comp,
                    "dependency_match": tech_match,
                    "quality_score": 0.9,
                    "total_score": total_score,
                },
                "match_level": level.value,
                "component": comp,
                "is_shadcn": True,
            }

            if self.current_strategy == MatchingStrategy.EXACT:
                if total_score >= MatchThreshold.PERFECT.value:
                    results.append(result)
            elif self.current_strategy == MatchingStrategy.FUZZY:
                if total_score >= MatchThreshold.AVAILABLE.value:
                    results.append(result)
            else:
                results.append(result)

        results.sort(key=lambda x: x["scores"]["total_score"], reverse=True)
        return results

    def match_with_shadcn(self, intent: Dict[str, Any], user_id: str = None, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        start_time = time.time()

        regular_results = self.match_intent(intent, user_id, context)

        shadcn_results = []
        if self.shadcn_bridge:
            shadcn_results = self.match_shadcn_component(intent, user_id)

        combined = regular_results + shadcn_results
        combined.sort(key=lambda x: x["scores"]["total_score"], reverse=True)

        elapsed = time.time() - start_time
        if elapsed > 0.5:
            print(f"WARNING: Matching took {elapsed:.2f}s (> 500ms)")

        return combined

    def sync_database(self, source_documents: List[Dict[str, Any]]):
        if self.incremental_updater:
            added, updated, deleted = self.incremental_updater.sync_with_source(source_documents)
            changes = self.incremental_updater.get_latest_changes(len(self.all_components))

            if self.inverted_index:
                self.incremental_updater.update_index(self.inverted_index, changes)

            self.database = self._load_database()
            self.all_components = self._build_component_registry()

            return {"added": added, "updated": updated, "deleted": deleted}
        else:
            self.database = {"ui_libraries": {}}
            for doc in source_documents:
                doc_id = doc.get("id", str(time.time()))
                self.database["ui_libraries"][doc_id] = doc
            self.all_components = self._build_component_registry()

            if self.inverted_index:
                docs = [comp.raw for comp in self.all_components]
                self.inverted_index.build_from_documents(docs)

            return {"added": len(source_documents), "updated": 0, "deleted": 0}

    def get_index_stats(self) -> Dict[str, Any]:
        if self.inverted_index:
            return self.inverted_index.get_stats()
        return {"document_count": len(self.all_components)}


def get_matching_engine(database_path: str = None, use_enhancements: bool = True) -> MatchingEngine:
    return MatchingEngine(database_path, use_enhancements)


if __name__ == "__main__":
    engine = MatchingEngine(use_enhancements=True)
    print("=" * 80)
    print("LAAP Harness 匹配引擎（增强版）— 测试运行")
    print("=" * 80)

    print("\n📊 匹配策略配置:")
    print("-" * 80)
    config = engine.get_matching_strategy()
    for key, value in config.items():
        print(f"  {key}: {value}")

    print("\n🔍 测试搜索: 'button'")
    print("-" * 80)
    search_results = engine.search_components("button")
    for i, result in enumerate(search_results[:5], 1):
        print(f"  {i}. {result['name']} ({result['type']}) — 匹配度: {result['match_score']:.2f}")
        print(f"     原因: {', '.join(result['match_reasons'])}")

    print("\n🎯 测试意图匹配: React + Tailwind + 现代风格")
    print("-" * 80)
    intent = {
        "tags": ["react", "tailwind", "ui", "components"],
        "style": "modern-minimal",
        "tech": "React + Tailwind",
    }
    match_results = engine.match_intent(intent)
    for i, result in enumerate(match_results[:5], 1):
        scores = result["scores"]
        print(f"  {i}. {result['name']} ({result['type']})")
        print(f"     综合评分: {scores['total_score']:.4f} [{result['match_level']}]")
        print(f"     - 标签相似度: {scores['tag_similarity']:.4f}")
        print(f"     - 风格兼容性: {scores['style_compatibility']:.4f}")
        print(f"     - 依赖匹配度: {scores['dependency_match']:.4f}")
        print(f"     - 质量评分: {scores['quality_score']:.4f}")

    print("\n🎯 测试上下文感知匹配 (user_id: test_user)")
    print("-" * 80)
    engine.context_awareness.record_user_interaction("test_user", ["react", "tailwind"], "modern-minimal", "React + Tailwind")
    match_results_context = engine.match_intent(intent, user_id="test_user")
    for i, result in enumerate(match_results_context[:3], 1):
        scores = result["scores"]
        print(f"  {i}. {result['name']} ({result['type']})")
        print(f"     综合评分: {scores['total_score']:.4f} [{result['match_level']}]")

    print("\n🎯 测试倒排索引搜索:")
    print("-" * 80)
    if engine.inverted_index:
        stats = engine.get_index_stats()
        print(f"  索引统计: {stats}")
        boolean_results = engine.inverted_index.boolean_search("react and button")
        print(f"  布尔查询 'react and button': {len(boolean_results)} 个结果")

    print("\n✅ 增强版匹配引擎测试完成")