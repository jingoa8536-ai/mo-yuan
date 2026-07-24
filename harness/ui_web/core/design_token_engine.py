"""
UI Harness — 设计令牌引擎
=========================
管理配色、字体、间距、圆角、阴影等设计系统参数。
支持预设方案和应用时动态覆盖。
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ui_harness.tokens")


@dataclass
class DesignTokens:
    """完整的设计令牌集合。"""
    # 配色
    colors: Dict[str, str] = field(default_factory=lambda: {
        "bg_primary": "#0a0a0f",
        "bg_secondary": "#1a1a2e",
        "bg_card": "#1e1e32",
        "text_primary": "#f1f5f9",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent": "#6366f1",
        "accent_hover": "#818cf8",
        "accent_muted": "#312e81",
        "border": "#2d2d44",
        "success": "#22c55e",
        "warning": "#eab308",
        "error": "#ef4444",
        "info": "#3b82f6",
    })
    # 字体
    font_family_heading: str = "Inter, sans-serif"
    font_family_body: str = "Inter, sans-serif"
    font_family_mono: str = "JetBrains Mono, monospace"
    font_sizes: Dict[str, str] = field(default_factory=lambda: {
        "xs": "0.75rem", "sm": "0.875rem", "base": "1rem",
        "lg": "1.125rem", "xl": "1.25rem", "2xl": "1.5rem",
        "3xl": "1.875rem", "4xl": "2.25rem", "5xl": "3rem",
        "6xl": "3.75rem",
    })
    # 间距 (8px 网格)
    spacing: Dict[str, str] = field(default_factory=lambda: {
        "0": "0", "1": "0.25rem", "2": "0.5rem", "3": "0.75rem",
        "4": "1rem", "5": "1.25rem", "6": "1.5rem", "8": "2rem",
        "10": "2.5rem", "12": "3rem", "16": "4rem", "20": "5rem",
        "24": "6rem",
    })
    # 圆角
    radius: Dict[str, str] = field(default_factory=lambda: {
        "none": "0", "sm": "0.25rem", "md": "0.5rem",
        "lg": "0.75rem", "xl": "1rem", "2xl": "1.5rem",
        "full": "9999px",
    })
    # 阴影
    shadows: Dict[str, str] = field(default_factory=lambda: {
        "sm": "0 1px 2px rgba(0,0,0,0.3)",
        "md": "0 4px 6px rgba(0,0,0,0.3)",
        "lg": "0 10px 15px rgba(0,0,0,0.3)",
        "xl": "0 20px 25px rgba(0,0,0,0.4)",
        "glow": "0 0 20px rgba(99,102,241,0.3)",
    })
    # 动画
    transition_duration: str = "0.3s"
    transition_timing: str = "cubic-bezier(0.4, 0, 0.2, 1)"
    animation_presets: List[str] = field(default_factory=lambda: [
        "fadeIn", "fadeInUp", "fadeInLeft", "fadeInRight",
        "scaleIn", "staggerChildren",
    ])
    # 断点
    breakpoints: Dict[str, str] = field(default_factory=lambda: {
        "sm": "640px", "md": "768px", "lg": "1024px",
        "xl": "1280px", "2xl": "1536px",
    })
    # 元数据
    name: str = "dark_flagship"
    description: str = "暗夜旗舰 — SaaS/科技感暗色主题"

    def to_css_variables(self) -> str:
        """导出为 CSS 变量。"""
        lines = [":root {"]
        for key, val in self.colors.items():
            lines.append(f"  --color-{key.replace('_', '-')}: {val};")
        lines.append(f"  --font-heading: {self.font_family_heading};")
        lines.append(f"  --font-body: {self.font_family_body};")
        lines.append(f"  --font-mono: {self.font_family_mono};")
        for key, val in self.radius.items():
            lines.append(f"  --radius-{key}: {val};")
        lines.append(f"  --transition-duration: {self.transition_duration};")
        lines.append(f"  --transition-timing: {self.transition_timing};")
        lines.append("}")
        return "\n".join(lines)

    def to_tailwind_config(self) -> str:
        """导出为 TailwindCSS 配置片段。"""
        return json.dumps({
            "theme": {
                "extend": {
                    "colors": self.colors,
                    "fontFamily": {
                        "heading": self.font_family_heading,
                        "body": self.font_family_body,
                        "mono": self.font_family_mono,
                    },
                    "borderRadius": self.radius,
                    "boxShadow": self.shadows,
                    "transitionDuration": {"DEFAULT": self.transition_duration},
                }
            }
        }, indent=2)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "colors": self.colors,
            "typography": {
                "heading": self.font_family_heading,
                "body": self.font_family_body,
                "mono": self.font_family_mono,
                "sizes": self.font_sizes,
            },
            "spacing": self.spacing,
            "radius": self.radius,
            "shadows": self.shadows,
            "animation": {
                "duration": self.transition_duration,
                "timing": self.transition_timing,
                "presets": self.animation_presets,
            },
        }


# ════════════════════════════════════════════════════════════
# 设计系统预设
# ════════════════════════════════════════════════════════════

PRESETS: Dict[str, Dict[str, Any]] = {
    "dark_flagship": {
        "name": "暗夜旗舰",
        "description": "深蓝紫暗色，科技感 SaaS",
        "colors": {
            "bg_primary": "#0a0a0f", "bg_secondary": "#1a1a2e",
            "bg_card": "#1e1e32", "text_primary": "#f1f5f9",
            "text_secondary": "#94a3b8", "text_muted": "#64748b",
            "accent": "#6366f1", "accent_hover": "#818cf8",
            "accent_muted": "#312e81", "border": "#2d2d44",
            "success": "#22c55e", "warning": "#eab308",
            "error": "#ef4444", "info": "#3b82f6",
        },
        "font_family_heading": "Inter, sans-serif",
        "font_family_mono": "JetBrains Mono, monospace",
    },
    "minimal_white": {
        "name": "极简白",
        "description": "干净白色，文档/博客风格",
        "colors": {
            "bg_primary": "#ffffff", "bg_secondary": "#f8fafc",
            "bg_card": "#ffffff", "text_primary": "#0f172a",
            "text_secondary": "#475569", "text_muted": "#94a3b8",
            "accent": "#3b82f6", "accent_hover": "#2563eb",
            "accent_muted": "#dbeafe", "border": "#e2e8f0",
            "success": "#22c55e", "warning": "#eab308",
            "error": "#ef4444", "info": "#3b82f6",
        },
        "font_family_heading": "Inter, sans-serif",
    },
    "ocean_blue": {
        "name": "海洋蓝",
        "description": "蓝色系，金融/企业风格",
        "colors": {
            "bg_primary": "#0f172a", "bg_secondary": "#1e293b",
            "bg_card": "#1e293b", "text_primary": "#f8fafc",
            "text_secondary": "#94a3b8", "text_muted": "#64748b",
            "accent": "#0ea5e9", "accent_hover": "#38bdf8",
            "accent_muted": "#0c4a6e", "border": "#334155",
            "success": "#10b981", "warning": "#f59e0b",
            "error": "#ef4444", "info": "#3b82f6",
        },
        "font_family_heading": "Inter, sans-serif",
    },
    "cyberpunk": {
        "name": "赛博朋克",
        "description": "暗色+荧光粉/蓝，前卫科技",
        "colors": {
            "bg_primary": "#0d0d1a", "bg_secondary": "#1a1a2e",
            "bg_card": "#16213e", "text_primary": "#e0e0ff",
            "text_secondary": "#a0a0cc", "text_muted": "#7070aa",
            "accent": "#ff2d95", "accent_hover": "#ff6bb5",
            "accent_muted": "#4a0e30", "border": "#2a2a4a",
            "success": "#00ff88", "warning": "#ffcc00",
            "error": "#ff3366", "info": "#00ccff",
        },
        "font_family_heading": "'Space Grotesk', sans-serif",
        "font_family_mono": "'Fira Code', monospace",
    },
    "nature_green": {
        "name": "自然绿",
        "description": "绿色系，环保/健康/户外",
        "colors": {
            "bg_primary": "#f0fdf4", "bg_secondary": "#dcfce7",
            "bg_card": "#ffffff", "text_primary": "#14532d",
            "text_secondary": "#166534", "text_muted": "#4ade80",
            "accent": "#22c55e", "accent_hover": "#16a34a",
            "accent_muted": "#bbf7d0", "border": "#86efac",
            "success": "#16a34a", "warning": "#ca8a04",
            "error": "#dc2626", "info": "#0284c7",
        },
        "font_family_heading": "'Playfair Display', serif",
        "font_family_body": "'Source Sans Pro', sans-serif",
    },
    "glassmorphism": {
        "name": "毛玻璃",
        "description": "模糊透明效果，现代优雅",
        "colors": {
            "bg_primary": "#0f0f1a", "bg_secondary": "rgba(255,255,255,0.05)",
            "bg_card": "rgba(255,255,255,0.08)", "text_primary": "#ffffff",
            "text_secondary": "rgba(255,255,255,0.7)", "text_muted": "rgba(255,255,255,0.4)",
            "accent": "#a78bfa", "accent_hover": "#c4b5fd",
            "accent_muted": "rgba(167,139,250,0.2)", "border": "rgba(255,255,255,0.15)",
            "success": "#34d399", "warning": "#fbbf24",
            "error": "#fb7185", "info": "#60a5fa",
        },
        "font_family_heading": "'Outfit', sans-serif",
    },
}


# ════════════════════════════════════════════════════════════
# 设计令牌引擎
# ════════════════════════════════════════════════════════════


class DesignTokenEngine:
    """
    设计令牌引擎 — 根据意图和风格生成设计系统。
    
    用法:
        engine = DesignTokenEngine()
        tokens = engine.generate(intent_result)
    """

    def __init__(self):
        self.presets = PRESETS

    def generate(self, style_tags: List[str],
                 color_hint: Optional[str] = None,
                 tone: str = "professional") -> DesignTokens:
        """
        根据风格标签生成设计令牌。
        
        Args:
            style_tags: 风格标签列表 (如 ["dark", "tech"])
            color_hint: 颜色提示 (如 "blue")
            tone: 调性
            
        Returns:
            DesignTokens 实例
        """
        # 1. 选择最佳预设
        preset_name = self._match_preset(style_tags)
        tokens = self._apply_preset(preset_name)

        # 2. 颜色微调
        if color_hint and color_hint not in tokens.name:
            tokens = self._adjust_color(tokens, color_hint)

        # 3. 根据调性微调
        tokens = self._adjust_tone(tokens, tone)

        # 4. 根据暗/亮调整文字色
        is_dark = self._is_dark_scheme(tokens.colors["bg_primary"])
        if is_dark:
            tokens.description += " (暗色)"
        else:
            tokens.description += " (亮色)"

        return tokens

    def _match_preset(self, tags: List[str]) -> str:
        """根据标签匹配最佳预设。"""
        tag_lower = [t.lower() for t in tags]

        # 精确匹配
        style_to_preset = {
            "dark": "dark_flagship",
            "light": "minimal_white",
            "minimal": "minimal_white",
            "cyber": "cyberpunk",
            "tech": "dark_flagship",
            "nature": "nature_green",
            "green": "nature_green",
            "glass": "glassmorphism",
            "ocean": "ocean_blue",
            "blue": "ocean_blue",
            "corporate": "ocean_blue",
        }
        for tag in tag_lower:
            if tag in style_to_preset:
                return style_to_preset[tag]

        # 暗色/亮色判断
        dark_keywords = {"dark", "night", "深色", "暗"}
        light_keywords = {"light", "white", "bright", "亮", "白"}
        has_dark = any(k in tag_lower for k in dark_keywords)
        has_light = any(k in tag_lower for k in light_keywords)

        if has_dark:
            return "dark_flagship"
        if has_light:
            return "minimal_white"

        return "dark_flagship"  # 默认暗色

    def _apply_preset(self, name: str) -> DesignTokens:
        """应用预设方案。"""
        preset = self.presets.get(name, self.presets["dark_flagship"])
        tokens = DesignTokens(
            name=name,
            description=preset.get("description", ""),
        )
        for key, val in preset.items():
            if hasattr(tokens, key):
                setattr(tokens, key, val)
        return tokens

    def _adjust_color(self, tokens: DesignTokens, color: str) -> DesignTokens:
        """根据颜色提示调整配色。"""
        color_map = {
            "blue": {"accent": "#3b82f6", "accent_hover": "#2563eb", "accent_muted": "#1e3a5f"},
            "green": {"accent": "#22c55e", "accent_hover": "#16a34a", "accent_muted": "#14532d"},
            "purple": {"accent": "#a855f7", "accent_hover": "#c084fc", "accent_muted": "#3b0764"},
            "orange": {"accent": "#f97316", "accent_hover": "#fb923c", "accent_muted": "#431407"},
            "red": {"accent": "#ef4444", "accent_hover": "#f87171", "accent_muted": "#450a0a"},
            "pink": {"accent": "#ec4899", "accent_hover": "#f472b6", "accent_muted": "#500724"},
            "cyan": {"accent": "#06b6d4", "accent_hover": "#22d3ee", "accent_muted": "#083344"},
        }
        if color in color_map:
            tokens.colors.update(color_map[color])
            tokens.name = f"{color}_{tokens.name}"
        return tokens

    def _adjust_tone(self, tokens: DesignTokens, tone: str) -> DesignTokens:
        """根据调性微调。"""
        if tone == "luxury":
            tokens.font_family_heading = "'Playfair Display', serif"
            tokens.shadows["glow"] = "0 0 30px rgba(255,215,0,0.15)"
        elif tone == "playful":
            tokens.font_family_heading = "'DM Sans', sans-serif"
            tokens.radius["lg"] = "1rem"
        elif tone == "minimal":
            tokens.font_family_heading = "'Inter', sans-serif"
            tokens.colors["accent_muted"] = tokens.colors["border"]
        elif tone == "tech":
            tokens.font_family_mono = "'JetBrains Mono', monospace"
            tokens.shadows["glow"] = f"0 0 20px {tokens.colors['accent']}40"
        return tokens

    def _is_dark_scheme(self, bg_color: str) -> bool:
        """判断是否为暗色方案。"""
        if bg_color.startswith("#"):
            try:
                hex_val = bg_color.lstrip("#")
                r, g, b = int(hex_val[:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                return brightness < 128
            except ValueError:
                pass
        return "rgba" in bg_color or bg_color.startswith("#0") or bg_color.startswith("#1")

    def list_presets(self) -> List[Dict[str, str]]:
        """列出所有可用预设。"""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in self.presets.items()
        ]


# 单例
_engine: Optional[DesignTokenEngine] = None


def get_engine() -> DesignTokenEngine:
    global _engine
    if _engine is None:
        _engine = DesignTokenEngine()
    return _engine


if __name__ == "__main__":
    engine = get_engine()
    print("设计系统预设:")
    for p in engine.list_presets():
        print(f"  {p['id']:20s} {p['name']:10s} {p['description']}")
    print()
    # 测试生成
    tokens = engine.generate(["dark", "tech"], color_hint="blue", tone="tech")
    print(f"生成: {tokens.name}")
    print(f"描述: {tokens.description}")
    print(f"主色: {tokens.colors['accent']}")
    print(f"背景: {tokens.colors['bg_primary']}")
    print(f"标题字体: {tokens.font_family_heading}")
    print()
    print("CSS 变量:")
    print(tokens.to_css_variables()[:300])
