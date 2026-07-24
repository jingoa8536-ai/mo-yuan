"""
game_style_compat.py — 游戏风格兼容性映射系统
=============================================

实现游戏风格与组件之间的关联规则及适配机制，支持：
1. 游戏风格相似度计算
2. 风格适配规则管理
3. 动态风格扩展

游戏风格分类：
- racing-game: 赛车游戏
- sports-game: 体育游戏
- simulation: 模拟游戏
- arcade: 街机游戏
- action: 动作游戏
- rpg: 角色扮演游戏
- strategy: 策略游戏
- godot-native: Godot原生风格
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class GameStyle(Enum):
    RACING = "racing-game"
    SPORTS = "sports-game"
    SIMULATION = "simulation"
    ARCADE = "arcade"
    ACTION = "action"
    RPG = "rpg"
    STRATEGY = "strategy"
    GODOT_NATIVE = "godot-native"


class GameStyleCompatibilityMap:
    DEFAULT_SIMILARITY_MAP = {
        "racing-game": {"racing-game": 1.0, "sports-game": 0.85, "simulation": 0.75, "arcade": 0.7, "action": 0.5, "rpg": 0.3, "strategy": 0.35, "godot-native": 0.9},
        "sports-game": {"racing-game": 0.85, "sports-game": 1.0, "simulation": 0.7, "arcade": 0.75, "action": 0.6, "rpg": 0.35, "strategy": 0.4, "godot-native": 0.85},
        "simulation": {"racing-game": 0.75, "sports-game": 0.7, "simulation": 1.0, "arcade": 0.55, "action": 0.5, "rpg": 0.5, "strategy": 0.65, "godot-native": 0.8},
        "arcade": {"racing-game": 0.7, "sports-game": 0.75, "arcade": 1.0, "action": 0.8, "rpg": 0.6, "strategy": 0.4, "godot-native": 0.8},
        "action": {"racing-game": 0.5, "sports-game": 0.6, "arcade": 0.8, "action": 1.0, "rpg": 0.75, "strategy": 0.45, "godot-native": 0.75},
        "rpg": {"racing-game": 0.3, "sports-game": 0.35, "arcade": 0.6, "action": 0.75, "rpg": 1.0, "strategy": 0.6, "godot-native": 0.7},
        "strategy": {"racing-game": 0.35, "sports-game": 0.4, "arcade": 0.4, "action": 0.45, "rpg": 0.6, "strategy": 1.0, "godot-native": 0.65},
        "godot-native": {"godot-native": 1.0, "racing-game": 0.9, "sports-game": 0.85, "simulation": 0.8, "arcade": 0.8, "action": 0.75, "rpg": 0.7, "strategy": 0.65},
    }

    STYLE_CATEGORIES = {
        "racing-game": {"category": "sports", "subcategory": "racing", "features": ["vehicle_physics", "tracks", "lap_timing", "speed"]},
        "sports-game": {"category": "sports", "subcategory": "general", "features": ["team_management", "match_simulation", "player_stats"]},
        "simulation": {"category": "simulation", "subcategory": "general", "features": ["realistic_physics", "resource_management", "time_progression"]},
        "arcade": {"category": "action", "subcategory": "arcade", "features": ["fast_paced", "simple_controls", "high_score"]},
        "action": {"category": "action", "subcategory": "general", "features": ["combat", "movement", "exploration", "combo_system"]},
        "rpg": {"category": "rpg", "subcategory": "general", "features": ["character_progression", "story", "quests", "inventory"]},
        "strategy": {"category": "strategy", "subcategory": "general", "features": ["resource_management", "tactics", "map_control", "unit_management"]},
        "godot-native": {"category": "engine", "subcategory": "godot", "features": ["godot_nodes", "gdscript", "scene_tree", "physics_3d"]},
    }

    COMPONENT_STYLE_MAPPING = {
        "engine-sound-crossfade": {"primary": "racing-game", "secondary": ["sports-game", "arcade"]},
        "ghost-system": {"primary": "racing-game", "secondary": ["sports-game", "simulation"]},
        "keyframes-pack": {"primary": "racing-game", "secondary": ["arcade", "action"]},
        "vehicle-physics": {"primary": "racing-game", "secondary": ["sports-game", "simulation"]},
        "character-controller": {"primary": "action", "secondary": ["rpg", "arcade"]},
        "combat-system": {"primary": "action", "secondary": ["rpg", "strategy"]},
        "inventory-system": {"primary": "rpg", "secondary": ["action", "strategy"]},
        "quest-system": {"primary": "rpg", "secondary": ["simulation"]},
        "resource-manager": {"primary": "strategy", "secondary": ["simulation", "rpg"]},
        "unit-controller": {"primary": "strategy", "secondary": ["action"]},
        "match-manager": {"primary": "sports-game", "secondary": ["strategy"]},
        "ai-controller": {"primary": "simulation", "secondary": ["strategy", "action"]},
        "racing_game_v1": {"primary": "racing-game", "secondary": ["sports-game", "arcade"]},
        "action_game_core": {"primary": "action", "secondary": ["arcade", "rpg"]},
        "rpg_framework": {"primary": "rpg", "secondary": ["action", "strategy"]},
        "strategy_game_engine": {"primary": "strategy", "secondary": ["simulation", "rpg"]},
        "godot_ai_framework": {"primary": "godot-native", "secondary": ["simulation", "strategy"]},
    }

    def __init__(self, similarity_map: Dict[str, Dict[str, float]] = None):
        self.similarity_map = similarity_map or self.DEFAULT_SIMILARITY_MAP
        self._validate_similarity_map()

    def _validate_similarity_map(self) -> None:
        for style, similarities in self.similarity_map.items():
            for target, score in similarities.items():
                if not (0.0 <= score <= 1.0):
                    raise ValueError(f"相似度分数 {score} 不在 [0, 1] 范围内: {style} -> {target}")
            if similarities.get(style, 0.0) != 1.0:
                raise ValueError(f"风格自相似度必须为 1.0: {style}")

    def get_style_similarity(self, style_a: str, style_b: str) -> float:
        style_a_norm = style_a.lower().strip()
        style_b_norm = style_b.lower().strip()

        if style_a_norm == style_b_norm:
            return 1.0

        if style_a_norm in self.similarity_map:
            score = self.similarity_map[style_a_norm].get(style_b_norm)
            if score is not None:
                return score

        if style_b_norm in self.similarity_map:
            score = self.similarity_map[style_b_norm].get(style_a_norm)
            if score is not None:
                return score

        return 0.5

    def get_style_category(self, style: str) -> Dict[str, Any]:
        return self.STYLE_CATEGORIES.get(style.lower().strip(), {})

    def get_style_features(self, style: str) -> List[str]:
        category_info = self.get_style_category(style)
        return category_info.get("features", [])

    def get_compatible_styles(self, style: str, threshold: float = 0.6) -> List[str]:
        style_norm = style.lower().strip()
        compatible = []

        if style_norm in self.similarity_map:
            for target, score in self.similarity_map[style_norm].items():
                if score >= threshold:
                    compatible.append(target)
        else:
            for target_style in self.STYLE_CATEGORIES.keys():
                if target_style != style_norm:
                    score = self.get_style_similarity(style_norm, target_style)
                    if score >= threshold:
                        compatible.append(target_style)

        return sorted(compatible, key=lambda s: self.get_style_similarity(style_norm, s), reverse=True)

    def get_component_compatible_styles(self, component_id: str) -> Dict[str, Any]:
        return self.COMPONENT_STYLE_MAPPING.get(component_id, {"primary": "", "secondary": []})

    def is_style_compatible(self, style_a: str, style_b: str, threshold: float = 0.6) -> bool:
        return self.get_style_similarity(style_a, style_b) >= threshold

    def add_style(self, style: str, similarities: Dict[str, float], category_info: Dict[str, Any] = None) -> None:
        style_norm = style.lower().strip()

        if style_norm not in similarities:
            similarities[style_norm] = 1.0

        for target, score in list(similarities.items()):
            if not (0.0 <= score <= 1.0):
                raise ValueError(f"相似度分数 {score} 不在 [0, 1] 范围内")

        self.similarity_map[style_norm] = similarities

        if category_info:
            self.STYLE_CATEGORIES[style_norm] = category_info

    def add_component_mapping(self, component_id: str, primary_style: str, secondary_styles: List[str] = None) -> None:
        self.COMPONENT_STYLE_MAPPING[component_id] = {
            "primary": primary_style,
            "secondary": secondary_styles or []
        }

    def get_all_styles(self) -> List[str]:
        return list(self.STYLE_CATEGORIES.keys())

    def get_all_components(self) -> List[str]:
        return list(self.COMPONENT_STYLE_MAPPING.keys())

    def get_similarity_matrix(self) -> Dict[str, Dict[str, float]]:
        return self.similarity_map.copy()

    def calculate_component_style_score(self, component_id: str, query_style: str) -> float:
        mapping = self.get_component_compatible_styles(component_id)
        primary_style = mapping.get("primary", "")
        secondary_styles = mapping.get("secondary", [])

        if not primary_style:
            return 0.5

        primary_score = self.get_style_similarity(primary_style, query_style)

        if secondary_styles:
            secondary_scores = [self.get_style_similarity(s, query_style) for s in secondary_styles]
            avg_secondary = sum(secondary_scores) / len(secondary_scores)
            return 0.7 * primary_score + 0.3 * avg_secondary

        return primary_score


def get_game_style_compatibility_map() -> GameStyleCompatibilityMap:
    return GameStyleCompatibilityMap()


if __name__ == "__main__":
    gscm = GameStyleCompatibilityMap()

    print("=" * 80)
    print("游戏风格兼容性映射系统 — 测试运行")
    print("=" * 80)

    print("\n📊 所有游戏风格:")
    print("-" * 80)
    for style in gscm.get_all_styles():
        category = gscm.get_style_category(style)
        print(f"  {style} -> 分类: {category.get('category')}, 子分类: {category.get('subcategory')}")

    print("\n🔍 风格相似度查询:")
    print("-" * 80)
    test_pairs = [("racing-game", "sports-game"), ("racing-game", "rpg"), ("action", "arcade"), ("simulation", "strategy")]
    for style_a, style_b in test_pairs:
        score = gscm.get_style_similarity(style_a, style_b)
        print(f"  {style_a} ↔ {style_b}: {score:.4f}")

    print("\n📋 racing-game 的兼容风格 (阈值 0.6):")
    print("-" * 80)
    compatible = gscm.get_compatible_styles("racing-game", threshold=0.6)
    for style in compatible:
        score = gscm.get_style_similarity("racing-game", style)
        print(f"  {style}: {score:.4f}")

    print("\n🔧 组件风格匹配:")
    print("-" * 80)
    test_components = ["engine-sound-crossfade", "ghost-system", "character-controller", "combat-system"]
    for comp in test_components:
        mapping = gscm.get_component_compatible_styles(comp)
        score = gscm.calculate_component_style_score(comp, "racing-game")
        print(f"  {comp}:")
        print(f"    主风格: {mapping.get('primary')}")
        print(f"    次风格: {mapping.get('secondary')}")
        print(f"    racing-game 匹配度: {score:.4f}")

    print("\n✅ 游戏风格兼容性映射系统测试完成")
