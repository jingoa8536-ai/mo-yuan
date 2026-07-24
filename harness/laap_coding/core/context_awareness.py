"""
context_awareness.py — 上下文感知模块
======================================

核心能力：
1. 用户历史偏好追踪
2. 动态权重调整
3. 上下文感知推荐
4. 会话记忆管理
5. 零Token消耗（纯Python计算）

设计原理：
- 基于用户历史行为计算偏好得分
- 动态调整匹配引擎各维度权重
- 支持短期和长期记忆
- 实现个性化推荐
"""

import os
import json
import time
from typing import Dict, Any, List, Optional


class UserPreference:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tag_preferences: Dict[str, float] = {}
        self.style_preferences: Dict[str, float] = {}
        self.tech_preferences: Dict[str, float] = {}
        self.component_preferences: Dict[str, float] = {}
        self.last_interaction = time.time()
        self.interaction_count = 0

    def record_interaction(self, tags: List[str] = None, style: str = None, tech: str = None, component: str = None):
        if tags:
            for tag in tags:
                self.tag_preferences[tag.lower()] = self.tag_preferences.get(tag.lower(), 0) + 1

        if style:
            self.style_preferences[style.lower()] = self.style_preferences.get(style.lower(), 0) + 1

        if tech:
            self.tech_preferences[tech.lower()] = self.tech_preferences.get(tech.lower(), 0) + 1

        if component:
            self.component_preferences[component.lower()] = self.component_preferences.get(component.lower(), 0) + 1

        self.last_interaction = time.time()
        self.interaction_count += 1

    def get_tag_score(self, tag: str) -> float:
        total = sum(self.tag_preferences.values())
        if total == 0:
            return 0.5
        return self.tag_preferences.get(tag.lower(), 0) / total

    def get_style_score(self, style: str) -> float:
        total = sum(self.style_preferences.values())
        if total == 0:
            return 0.5
        return self.style_preferences.get(style.lower(), 0) / total

    def get_tech_score(self, tech: str) -> float:
        total = sum(self.tech_preferences.values())
        if total == 0:
            return 0.5
        return self.tech_preferences.get(tech.lower(), 0) / total

    def get_top_tags(self, limit: int = 5) -> List[str]:
        sorted_tags = sorted(self.tag_preferences.items(), key=lambda x: x[1], reverse=True)
        return [tag for tag, count in sorted_tags[:limit]]

    def get_top_styles(self, limit: int = 3) -> List[str]:
        sorted_styles = sorted(self.style_preferences.items(), key=lambda x: x[1], reverse=True)
        return [style for style, count in sorted_styles[:limit]]

    def get_top_tech(self, limit: int = 3) -> List[str]:
        sorted_tech = sorted(self.tech_preferences.items(), key=lambda x: x[1], reverse=True)
        return [tech for tech, count in sorted_tech[:limit]]


class ContextAwareness:
    DEFAULT_ALPHA = 0.35
    DEFAULT_BETA = 0.25
    DEFAULT_GAMMA = 0.20
    DEFAULT_DELTA = 0.20

    def __init__(self, preferences_path: str = None):
        self.preferences: Dict[str, UserPreference] = {}
        self.preferences_path = preferences_path
        self.session_context: Dict[str, Any] = {}
        self.global_trends: Dict[str, float] = {}
        self._load_preferences()

    def _load_preferences(self):
        if self.preferences_path and os.path.exists(self.preferences_path):
            try:
                with open(self.preferences_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id, pref_data in data.items():
                        pref = UserPreference(user_id)
                        pref.tag_preferences = pref_data.get("tag_preferences", {})
                        pref.style_preferences = pref_data.get("style_preferences", {})
                        pref.tech_preferences = pref_data.get("tech_preferences", {})
                        pref.component_preferences = pref_data.get("component_preferences", {})
                        pref.last_interaction = pref_data.get("last_interaction", time.time())
                        pref.interaction_count = pref_data.get("interaction_count", 0)
                        self.preferences[user_id] = pref
            except Exception:
                pass

    def _save_preferences(self):
        if self.preferences_path:
            data = {}
            for user_id, pref in self.preferences.items():
                data[user_id] = {
                    "tag_preferences": pref.tag_preferences,
                    "style_preferences": pref.style_preferences,
                    "tech_preferences": pref.tech_preferences,
                    "component_preferences": pref.component_preferences,
                    "last_interaction": pref.last_interaction,
                    "interaction_count": pref.interaction_count,
                }
            with open(self.preferences_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def get_user_preferences(self, user_id: str) -> UserPreference:
        if user_id not in self.preferences:
            self.preferences[user_id] = UserPreference(user_id)
        return self.preferences[user_id]

    def record_user_interaction(self, user_id: str, tags: List[str] = None, style: str = None, tech: str = None, component: str = None):
        pref = self.get_user_preferences(user_id)
        pref.record_interaction(tags, style, tech, component)
        self._update_global_trends(tags, style, tech, component)
        self._save_preferences()

    def _update_global_trends(self, tags: List[str] = None, style: str = None, tech: str = None, component: str = None):
        if tags:
            for tag in tags:
                self.global_trends[tag.lower()] = self.global_trends.get(tag.lower(), 0) + 1

        if style:
            self.global_trends[style.lower()] = self.global_trends.get(style.lower(), 0) + 1

        if tech:
            self.global_trends[tech.lower()] = self.global_trends.get(tech.lower(), 0) + 1

        if component:
            self.global_trends[component.lower()] = self.global_trends.get(component.lower(), 0) + 1

    def get_dynamic_weights(self, user_id: str = None, context: Dict[str, Any] = None) -> Dict[str, float]:
        weights = {
            "alpha": self.DEFAULT_ALPHA,
            "beta": self.DEFAULT_BETA,
            "gamma": self.DEFAULT_GAMMA,
            "delta": self.DEFAULT_DELTA,
        }

        if user_id and user_id in self.preferences:
            pref = self.preferences[user_id]
            interaction_count = pref.interaction_count

            if interaction_count > 0:
                tag_variance = self._calculate_variance(pref.tag_preferences)
                style_variance = self._calculate_variance(pref.style_preferences)
                tech_variance = self._calculate_variance(pref.tech_preferences)

                weights["alpha"] = self.DEFAULT_ALPHA + (0.15 * tag_variance)
                weights["beta"] = self.DEFAULT_BETA + (0.10 * style_variance)
                weights["gamma"] = self.DEFAULT_GAMMA + (0.10 * tech_variance)

                total = sum(weights.values())
                for key in weights:
                    weights[key] /= total

        if context:
            weights = self._adjust_for_context(weights, context)

        return weights

    def _calculate_variance(self, preferences: Dict[str, float]) -> float:
        if not preferences:
            return 0.0

        total = sum(preferences.values())
        if total == 0:
            return 0.0

        proportions = [count / total for count in preferences.values()]
        mean = sum(proportions) / len(proportions)
        variance = sum((p - mean) ** 2 for p in proportions) / len(proportions)
        return min(variance * 10, 1.0)

    def _adjust_for_context(self, weights: Dict[str, float], context: Dict[str, Any]) -> Dict[str, float]:
        context_type = context.get("type", "")

        if context_type == "mobile":
            weights["gamma"] += 0.05
        elif context_type == "enterprise":
            weights["beta"] += 0.05
            weights["delta"] += 0.05
        elif context_type == "landing":
            weights["alpha"] += 0.05
            weights["beta"] += 0.05
        elif context_type == "dashboard":
            weights["alpha"] += 0.05
            weights["gamma"] += 0.05

        total = sum(weights.values())
        for key in weights:
            weights[key] /= total

        return weights

    def get_context_enhanced_intent(self, base_intent: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
        enhanced = base_intent.copy()

        if user_id and user_id in self.preferences:
            pref = self.preferences[user_id]

            top_tags = pref.get_top_tags(3)
            if top_tags:
                existing_tags = enhanced.get("tags", [])
                enhanced["tags"] = list(set(existing_tags + top_tags))

            top_styles = pref.get_top_styles(1)
            if top_styles and not enhanced.get("style"):
                enhanced["style"] = top_styles[0]

            top_tech = pref.get_top_tech(1)
            if top_tech and not enhanced.get("tech"):
                enhanced["tech"] = top_tech[0]

        return enhanced

    def set_session_context(self, user_id: str, context: Dict[str, Any]):
        self.session_context[user_id] = context

    def get_session_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.session_context.get(user_id)

    def clear_session_context(self, user_id: str):
        if user_id in self.session_context:
            del self.session_context[user_id]

    def get_global_trends(self, limit: int = 10) -> List[str]:
        sorted_trends = sorted(self.global_trends.items(), key=lambda x: x[1], reverse=True)
        return [trend for trend, count in sorted_trends[:limit]]

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.preferences:
            return {"user_id": user_id, "interaction_count": 0}

        pref = self.preferences[user_id]
        return {
            "user_id": user_id,
            "interaction_count": pref.interaction_count,
            "last_interaction": pref.last_interaction,
            "top_tags": pref.get_top_tags(5),
            "top_styles": pref.get_top_styles(3),
            "top_tech": pref.get_top_tech(3),
        }

    def reset_user_preferences(self, user_id: str):
        if user_id in self.preferences:
            self.preferences[user_id] = UserPreference(user_id)
            self._save_preferences()


def get_context_awareness(preferences_path: str = None) -> ContextAwareness:
    return ContextAwareness(preferences_path)


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness — 上下文感知模块")
    print("=" * 80)

    context = ContextAwareness()

    print("\n🔍 测试用户交互记录:")
    test_interactions = [
        {"user_id": "user1", "tags": ["react", "tailwind", "ui"], "style": "modern-minimal", "tech": "React + Tailwind"},
        {"user_id": "user1", "tags": ["button", "card"], "style": "modern-minimal"},
        {"user_id": "user1", "tags": ["dashboard", "analytics"], "tech": "React"},
        {"user_id": "user2", "tags": ["vue", "element"], "style": "enterprise-standard", "tech": "Vue 3"},
        {"user_id": "user2", "tags": ["form", "table"], "style": "enterprise-standard"},
    ]

    for interaction in test_interactions:
        context.record_user_interaction(**interaction)
        print(f"  记录: {interaction}")

    print("\n🔍 测试用户偏好获取:")
    pref1 = context.get_user_preferences("user1")
    print(f"  user1 偏好标签: {pref1.get_top_tags(3)}")
    print(f"  user1 偏好风格: {pref1.get_top_styles(2)}")
    print(f"  user1 偏好技术: {pref1.get_top_tech(2)}")

    print("\n🔍 测试动态权重计算:")
    weights1 = context.get_dynamic_weights("user1")
    print(f"  user1 动态权重: {weights1}")

    weights2 = context.get_dynamic_weights("user2")
    print(f"  user2 动态权重: {weights2}")

    weights_default = context.get_dynamic_weights()
    print(f"  默认权重: {weights_default}")

    print("\n🔍 测试上下文增强意图:")
    base_intent = {"tags": ["ui", "components"]}
    enhanced = context.get_context_enhanced_intent(base_intent, "user1")
    print(f"  基础意图: {base_intent}")
    print(f"  增强意图: {enhanced}")

    print("\n🔍 测试全局趋势:")
    trends = context.get_global_trends(5)
    print(f"  全局趋势: {trends}")

    print("\n✅ 上下文感知模块测试完成")