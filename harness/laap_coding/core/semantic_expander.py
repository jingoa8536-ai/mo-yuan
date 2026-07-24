"""
semantic_expander.py — 语义扩展模块
====================================

核心能力：
1. 同义词库管理
2. 标签语义扩展
3. 缩写/简写识别（如 button → btn）
4. 技术术语归一化
5. 上下文感知语义扩展

设计原理：
- 构建领域专用同义词库
- 支持缩写、简写、别名映射
- 实现语义扩展链
- 零Token消耗（纯Python计算）

配置化（Task C2）：
- 同义词库与缩写映射从 YAML 配置热加载
- 默认路径：core/data/synonyms.yaml 与 core/data/abbreviations.yaml
- 支持传入自定义 yaml_path 实现运行时覆盖
"""

import os
import json
from typing import Dict, Any, List, Optional, Set

import yaml


# ---------------------------------------------------------------------------
# YAML 配置默认路径（包内 data 目录）
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_DEFAULT_SYNONYMS_PATH = os.path.join(_DATA_DIR, "synonyms.yaml")
_DEFAULT_ABBREVIATIONS_PATH = os.path.join(_DATA_DIR, "abbreviations.yaml")


def load_synonyms(yaml_path: Optional[str] = None) -> Dict[str, List[str]]:
    """从 YAML 配置热加载同义词库。

    Args:
        yaml_path: YAML 文件路径。为 None 时使用包内默认路径
            ``core/data/synonyms.yaml``。

    Returns:
        Dict[str, List[str]]：``{canonical: [synonym1, synonym2, ...]}``。
        每次调用都重新读取文件，支持运行时热加载。

    YAML 格式::

        - canonical: "button"
          synonyms:
            - "btn"
            - "buttons"
    """
    path = yaml_path if yaml_path is not None else _DEFAULT_SYNONYMS_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    result: Dict[str, List[str]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        canonical = entry.get("canonical")
        if not canonical:
            continue
        synonyms = entry.get("synonyms") or []
        if not isinstance(synonyms, list):
            synonyms = [synonyms]
        result[canonical] = list(synonyms)
    return result


def load_abbreviations(yaml_path: Optional[str] = None) -> Dict[str, str]:
    """从 YAML 配置热加载缩写映射。

    Args:
        yaml_path: YAML 文件路径。为 None 时使用包内默认路径
            ``core/data/abbreviations.yaml``。

    Returns:
        Dict[str, str]：``{abbreviation: expansion}``。
        每次调用都重新读取文件，支持运行时热加载。

    YAML 格式::

        - abbreviation: "btn"
          expansion: "button"
    """
    path = yaml_path if yaml_path is not None else _DEFAULT_ABBREVIATIONS_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    result: Dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        abbr = entry.get("abbreviation")
        if not abbr:
            continue
        expansion = entry.get("expansion")
        if expansion is None:
            continue
        result[abbr] = expansion
    return result


class SemanticExpander:
    def __init__(
        self,
        custom_synonyms: Dict[str, List[str]] = None,
        synonyms_path: Optional[str] = None,
        abbreviations_path: Optional[str] = None,
    ):
        self._synonyms_path = synonyms_path
        self._abbreviations_path = abbreviations_path
        self.synonym_graph = self._build_synonym_graph(custom_synonyms, synonyms_path)
        self.abbreviation_map = self._build_abbreviation_map(abbreviations_path)
        self.term_normalization = self._build_term_normalization()
        self.expansion_cache = {}

    def _build_synonym_graph(
        self,
        custom_synonyms: Optional[Dict[str, List[str]]],
        yaml_path: Optional[str] = None,
    ) -> Dict[str, Set[str]]:
        base_synonyms = load_synonyms(yaml_path)

        graph = {}
        for term, synonyms in base_synonyms.items():
            all_terms = set([term] + list(synonyms))
            for term_in_group in all_terms:
                key = term_in_group.lower()
                if key not in graph:
                    graph[key] = set()
                graph[key].update(all_terms)

        if custom_synonyms:
            for term, synonyms in custom_synonyms.items():
                all_terms = set([term] + list(synonyms))
                for term_in_group in all_terms:
                    key = term_in_group.lower()
                    if key not in graph:
                        graph[key] = set()
                    graph[key].update(all_terms)

        return graph

    def _build_abbreviation_map(self, yaml_path: Optional[str] = None) -> Dict[str, str]:
        return load_abbreviations(yaml_path)

    def _build_term_normalization(self) -> Dict[str, str]:
        return {
            "reactjs": "react",
            "react-js": "react",
            "vuejs": "vue",
            "vue-js": "vue",
            "angularjs": "angular",
            "angular-js": "angular",
            "tailwindcss": "tailwind",
            "tailwind-css": "tailwind",
            "expressjs": "express",
            "express-js": "express",
            "fast-api": "fastapi",
            "postgresql": "postgres",
            "postgre": "postgres",
            "mongo-db": "mongodb",
            "mongo-database": "mongodb",
            "nodejs": "node",
            "node-js": "node",
            "typescript": "ts",
            "javascript": "js",
            "css3": "css",
            "html5": "html",
            "graphql": "gql",
            "kubernetes": "k8s",
            "continuous-integration": "ci",
            "continuous-deployment": "cd",
            "quality-assurance": "qa",
            "content-management-system": "cms",
            "software-as-a-service": "saas",
            "platform-as-a-service": "paas",
            "infrastructure-as-a-service": "iaas",
            "command-line-interface": "cli",
            "graphical-user-interface": "gui",
            "integrated-development-environment": "ide",
            "version-control-system": "vcs",
            "single-sign-on": "sso",
            "json-web-token": "jwt",
            "content-delivery-network": "cdn",
            "domain-name-system": "dns",
            "transmission-control-protocol": "tcp",
            "user-datagram-protocol": "udp",
            "software-development-kit": "sdk",
        }

    def expand_tags(self, tags: List[str], expand_synonyms: bool = True, expand_abbreviations: bool = True) -> List[str]:
        cache_key = tuple(sorted(tags)) + (expand_synonyms, expand_abbreviations)
        if cache_key in self.expansion_cache:
            return self.expansion_cache[cache_key]

        expanded = set(tags)

        for tag in tags:
            tag_lower = tag.lower()

            if expand_abbreviations:
                if tag_lower in self.abbreviation_map:
                    expanded.add(self.abbreviation_map[tag_lower])
                for abbr, full in self.abbreviation_map.items():
                    if tag_lower == full or tag_lower in full:
                        expanded.add(abbr)

            if expand_synonyms:
                if tag_lower in self.synonym_graph:
                    expanded.update(self.synonym_graph[tag_lower])

            if tag_lower in self.term_normalization:
                expanded.add(self.term_normalization[tag_lower])

        result = list(expanded)
        self.expansion_cache[cache_key] = result
        return result

    def normalize_term(self, term: str) -> str:
        term_lower = term.lower()

        if term_lower in self.term_normalization:
            return self.term_normalization[term_lower]

        if term_lower in self.abbreviation_map:
            return self.abbreviation_map[term_lower]

        for abbr, full in self.abbreviation_map.items():
            if term_lower == full:
                return abbr

        return term_lower

    def find_synonyms(self, term: str) -> List[str]:
        term_lower = term.lower()
        if term_lower in self.synonym_graph:
            synonyms = list(self.synonym_graph[term_lower])
            synonyms.remove(term_lower)
            return synonyms
        return []

    def find_abbreviation(self, term: str) -> Optional[str]:
        term_lower = term.lower()
        for abbr, full in self.abbreviation_map.items():
            if term_lower == full.lower():
                return abbr
        return None

    def find_full_form(self, abbreviation: str) -> Optional[str]:
        abbr_lower = abbreviation.lower()
        return self.abbreviation_map.get(abbr_lower)

    def is_abbreviation(self, term: str) -> bool:
        return term.lower() in self.abbreviation_map

    def add_synonyms(self, term: str, synonyms: List[str]):
        all_terms = set([term.lower()] + [s.lower() for s in synonyms])
        for t in all_terms:
            if t not in self.synonym_graph:
                self.synonym_graph[t] = set()
            self.synonym_graph[t].update(all_terms)

        self.expansion_cache.clear()

    def add_abbreviation(self, abbreviation: str, full_form: str):
        self.abbreviation_map[abbreviation.lower()] = full_form.lower()
        self.expansion_cache.clear()

    def calculate_semantic_similarity(self, tags_a: List[str], tags_b: List[str]) -> float:
        expanded_a = set(self.expand_tags(tags_a))
        expanded_b = set(self.expand_tags(tags_b))

        if not expanded_a or not expanded_b:
            return 0.0

        intersection = expanded_a & expanded_b
        union = expanded_a | expanded_b

        return len(intersection) / len(union) if union else 0.0

    def filter_relevant(self, query_tags: List[str], candidate_tags: List[List[str]], threshold: float = 0.3) -> List[int]:
        relevant_indices = []
        for i, tags in enumerate(candidate_tags):
            sim = self.calculate_semantic_similarity(query_tags, tags)
            if sim >= threshold:
                relevant_indices.append(i)
        return relevant_indices


def get_semantic_expander(custom_synonyms: Dict[str, List[str]] = None) -> SemanticExpander:
    return SemanticExpander(custom_synonyms)


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness — 语义扩展模块")
    print("=" * 80)

    expander = SemanticExpander()

    print("\n🔍 测试标签扩展:")
    test_tags = [
        ["btn", "card", "dark"],
        ["react", "tw", "ui"],
        ["api", "auth", "db"],
    ]

    for tags in test_tags:
        expanded = expander.expand_tags(tags)
        print(f"  {tags} → {expanded}")

    print("\n🔍 测试同义词查询:")
    test_terms = ["button", "card", "dialog", "input"]
    for term in test_terms:
        synonyms = expander.find_synonyms(term)
        print(f"  {term}: {synonyms}")

    print("\n🔍 测试缩写识别:")
    test_abbrs = ["btn", "tw", "api", "db"]
    for abbr in test_abbrs:
        full = expander.find_full_form(abbr)
        print(f"  {abbr} → {full}")

    print("\n🔍 测试语义相似度:")
    test_pairs = [
        (["button", "card"], ["btn", "panel"]),
        (["react", "tailwind"], ["vue", "css"]),
        (["api", "auth"], ["authentication", "endpoint"]),
    ]

    for tags_a, tags_b in test_pairs:
        sim = expander.calculate_semantic_similarity(tags_a, tags_b)
        print(f"  {tags_a} vs {tags_b}: {sim:.4f}")

    print("\n✅ 语义扩展模块测试完成")