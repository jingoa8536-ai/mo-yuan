"""
视觉风格分析器 — Visual Style Analyzer

实现视觉风格的自动提取和复刻：
1. 从图片/视频中提取色彩方案
2. 分析排版和布局模式
3. 生成设计令牌系统
4. 计算Token消耗影响

核心能力：
- 色彩提取与和谐度分析
- 字体风格识别
- 布局模式检测
- 间距系统分析
- 动效模式识别
- 设计令牌生成
- Token消耗估算
"""

from __future__ import annotations

import os
import re
import json
import math
import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = __import__('logging').getLogger("laap.harness.visual")


@dataclass
class ColorToken:
    name: str
    hex: str
    rgb: Tuple[int, int, int]
    semantics: str
    usage: List[str]
    forbidden: List[str] = field(default_factory=list)
    contrast_ratio: float = 0.0


@dataclass
class TypographyToken:
    font_family: List[str]
    font_weight: int
    font_size: str
    line_height: float
    letter_spacing: float
    semantics: str
    usage: List[str]


@dataclass
class SpacingToken:
    name: str
    value: str
    scale: str
    semantics: str
    usage: List[str]


@dataclass
class LayoutPattern:
    name: str
    pattern_type: str
    description: str
    grid_columns: int
    gutter_width: str
    breakpoint_rules: Dict[str, Any]


@dataclass
class StyleAnalysisResult:
    colors: List[ColorToken]
    typography: List[TypographyToken]
    spacing: List[SpacingToken]
    layout: LayoutPattern
    dominant_style: str
    complexity_score: float
    color_harmony_score: float
    typography_rhythm_score: float
    token_estimate: Dict[str, int]


class ColorExtractor:
    """色彩提取器：从图片中提取主色调和配色方案"""

    def __init__(self, max_colors: int = 8):
        self.max_colors = max_colors

    def extract_from_image(self, image_path: str) -> List[ColorToken]:
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, using default colors")
            return self._get_default_colors()

        try:
            img = Image.open(image_path)
            img = img.convert('RGB')

            width, height = img.size
            step = max(1, (width * height) // 10000)
            pixels = list(img.getdata())[::step]

            color_counts = {}
            for pixel in pixels:
                rgb = (pixel[0], pixel[1], pixel[2])
                color_counts[rgb] = color_counts.get(rgb, 0) + 1

            sorted_colors = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
            top_colors = [color for color, count in sorted_colors[:self.max_colors]]

            colors = []
            for rgb in top_colors:
                hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                color_name = self._infer_color_name(rgb)
                semantics = self._infer_semantics(rgb)
                usage = self._infer_usage(rgb)
                contrast_ratio = self._calculate_contrast(rgb)

                colors.append(ColorToken(
                    name=color_name,
                    hex=hex_color,
                    rgb=rgb,
                    semantics=semantics,
                    usage=usage,
                    contrast_ratio=contrast_ratio
                ))

            colors = sorted(colors, key=lambda c: c.contrast_ratio, reverse=True)

            if len(colors) < 3:
                colors.extend(self._get_default_colors()[:3 - len(colors)])

            return colors

        except Exception as e:
            logger.error(f"Color extraction failed: {e}")
            return self._get_default_colors()

    def _get_default_colors(self) -> List[ColorToken]:
        default_rgb_values = [
            (26, 26, 26),
            (255, 255, 255),
            (59, 130, 246),
            (34, 197, 94),
            (239, 68, 68),
            (245, 158, 11),
            (139, 92, 246),
            (236, 72, 153),
        ]

        colors = []
        for rgb in default_rgb_values:
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            color_name = self._infer_color_name(rgb)
            semantics = self._infer_semantics(rgb)
            usage = self._infer_usage(rgb)
            contrast_ratio = self._calculate_contrast(rgb)

            colors.append(ColorToken(
                name=color_name,
                hex=hex_color,
                rgb=rgb,
                semantics=semantics,
                usage=usage,
                contrast_ratio=contrast_ratio
            ))

        return colors

    def _infer_color_name(self, rgb: Tuple[int, int, int]) -> str:
        r, g, b = rgb
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val

        if max_val < 50:
            return "dark"
        if min_val > 200:
            return "light"

        r_ratio = r / max_val if max_val > 0 else 0
        g_ratio = g / max_val if max_val > 0 else 0
        b_ratio = b / max_val if max_val > 0 else 0

        if diff < 20:
            return "neutral"

        if r_ratio > 0.7 and g_ratio < 0.5 and b_ratio < 0.5:
            return "primary"
        if r_ratio < 0.5 and g_ratio > 0.7 and b_ratio < 0.5:
            return "success"
        if r_ratio > 0.5 and g_ratio > 0.5 and b_ratio < 0.3:
            return "warning"
        if r_ratio > 0.6 and g_ratio < 0.4 and b_ratio > 0.6:
            return "accent"
        if r_ratio < 0.4 and g_ratio > 0.5 and b_ratio > 0.6:
            return "info"

        return f"color_{hashlib.md5(str(rgb).encode()).hexdigest()[:6]}"

    def _infer_semantics(self, rgb: Tuple[int, int, int]) -> str:
        r, g, b = rgb
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        if brightness < 80:
            return "权威、沉稳、高对比"
        if brightness > 200:
            return "呼吸感、留白、阅读舒适"
        return "平衡、中性、通用"

    def _infer_usage(self, rgb: Tuple[int, int, int]) -> List[str]:
        r, g, b = rgb
        brightness = (r * 299 + g * 587 + b * 114) / 1000

        if brightness < 80:
            return ["文字", "标题", "CTA按钮", "强调元素"]
        if brightness > 200:
            return ["背景", "卡片底色", "次要元素"]
        return ["边框", "分隔线", "图标", "次要文字"]

    def _calculate_contrast(self, rgb: Tuple[int, int, int]) -> float:
        r, g, b = rgb
        luminance = 0.2126 * (r/255) + 0.7152 * (g/255) + 0.0722 * (b/255)
        white_luminance = 1.0
        black_luminance = 0.0

        contrast_white = (white_luminance + 0.05) / (luminance + 0.05)
        contrast_black = (luminance + 0.05) / (black_luminance + 0.05)

        return max(contrast_white, contrast_black)

    def analyze_harmony(self, colors: List[ColorToken]) -> float:
        if len(colors) < 2:
            return 0.0

        total_score = 0.0
        pair_count = 0

        for i, c1 in enumerate(colors):
            for j, c2 in enumerate(colors):
                if i >= j:
                    continue
                r1, g1, b1 = c1.rgb
                r2, g2, b2 = c2.rgb

                diff_r = abs(r1 - r2)
                diff_g = abs(g1 - g2)
                diff_b = abs(b1 - b2)

                total_diff = diff_r + diff_g + diff_b
                if total_diff > 0:
                    score = 1.0 - (total_diff / (3 * 255))
                    total_score += score
                    pair_count += 1

        return total_score / pair_count if pair_count > 0 else 0.0


class LayoutAnalyzer:
    """布局分析器：从图片中检测布局模式和网格系统"""

    def analyze(self, image_path: str) -> LayoutPattern:
        try:
            if PIL_AVAILABLE:
                img = Image.open(image_path)
                width, height = img.size
            elif CV2_AVAILABLE:
                img = cv2.imread(image_path)
                height, width = img.shape[:2]
            else:
                return LayoutPattern(
                    name="default",
                    pattern_type="unknown",
                    description="无法分析布局",
                    grid_columns=12,
                    gutter_width="24px",
                    breakpoint_rules={}
                )

            pattern_type = self._detect_pattern(width, height)
            columns = self._estimate_columns(width)
            gutter = self._estimate_gutter(width)

            return LayoutPattern(
                name=f"{pattern_type}_{columns}col",
                pattern_type=pattern_type,
                description=self._describe_pattern(pattern_type, columns),
                grid_columns=columns,
                gutter_width=gutter,
                breakpoint_rules=self._generate_breakpoints(width)
            )

        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return LayoutPattern(
                name="default",
                pattern_type="unknown",
                description="布局分析失败",
                grid_columns=12,
                gutter_width="24px",
                breakpoint_rules={}
            )

    def _detect_pattern(self, width: int, height: int) -> str:
        aspect_ratio = width / height

        if aspect_ratio > 1.6:
            return "wide"
        if aspect_ratio < 0.7:
            return "tall"
        if width < 600:
            return "mobile"
        if width < 1200:
            return "tablet"
        return "desktop"

    def _estimate_columns(self, width: int) -> int:
        if width < 600:
            return 4
        if width < 900:
            return 8
        if width < 1200:
            return 12
        return 16

    def _estimate_gutter(self, width: int) -> str:
        if width < 600:
            return "16px"
        if width < 900:
            return "20px"
        return "24px"

    def _describe_pattern(self, pattern_type: str, columns: int) -> str:
        descriptions = {
            "mobile": f"移动端布局，{columns}列网格，紧凑间距",
            "tablet": f"平板端布局，{columns}列网格，中等间距",
            "desktop": f"桌面端布局，{columns}列网格，标准间距",
            "wide": f"宽屏布局，{columns}列网格，适合内容展示",
            "tall": f"竖屏布局，{columns}列网格，适合移动端",
        }
        return descriptions.get(pattern_type, "未知布局")

    def _generate_breakpoints(self, width: int) -> Dict[str, Any]:
        return {
            "sm": {"max_width": "640px", "columns": 4, "gutter": "16px"},
            "md": {"max_width": "768px", "columns": 8, "gutter": "20px"},
            "lg": {"max_width": "1024px", "columns": 12, "gutter": "24px"},
            "xl": {"max_width": "1280px", "columns": 12, "gutter": "24px"},
            "2xl": {"max_width": "1536px", "columns": 16, "gutter": "32px"},
        }


class TypographyAnalyzer:
    """排版分析器：分析字体风格和排版节奏"""

    def analyze(self, image_path: str) -> List[TypographyToken]:
        try:
            if PIL_AVAILABLE:
                img = Image.open(image_path)
                width, height = img.size
            else:
                width, height = 1920, 1080

            font_sizes = self._estimate_font_sizes(width)
            tokens = []

            for name, size in font_sizes.items():
                tokens.append(TypographyToken(
                    font_family=["Inter", "system-ui", "sans-serif"],
                    font_weight=self._estimate_weight(name),
                    font_size=size,
                    line_height=self._estimate_line_height(name),
                    letter_spacing=self._estimate_letter_spacing(name),
                    semantics=self._get_semantics(name),
                    usage=self._get_usage(name)
                ))

            return tokens

        except Exception as e:
            logger.error(f"Typography analysis failed: {e}")
            return []

    def _estimate_font_sizes(self, width: int) -> Dict[str, str]:
        base_size = max(14, min(18, width // 100))

        return {
            "display": f"clamp({base_size * 2.5}px, 5vw, {base_size * 4}px)",
            "heading-1": f"clamp({base_size * 2}px, 4vw, {base_size * 3}px)",
            "heading-2": f"clamp({base_size * 1.5}px, 3vw, {base_size * 2.5}px)",
            "heading-3": f"clamp({base_size * 1.25}px, 2vw, {base_size * 2}px)",
            "heading-4": f"{base_size * 1.125}px",
            "body-large": f"{base_size}px",
            "body": f"{base_size - 2}px",
            "caption": f"{base_size - 4}px",
        }

    def _estimate_weight(self, name: str) -> int:
        weights = {
            "display": 800,
            "heading-1": 700,
            "heading-2": 700,
            "heading-3": 600,
            "heading-4": 600,
            "body-large": 500,
            "body": 400,
            "caption": 400,
        }
        return weights.get(name, 400)

    def _estimate_line_height(self, name: str) -> float:
        line_heights = {
            "display": 1.1,
            "heading-1": 1.2,
            "heading-2": 1.25,
            "heading-3": 1.3,
            "heading-4": 1.35,
            "body-large": 1.6,
            "body": 1.6,
            "caption": 1.4,
        }
        return line_heights.get(name, 1.6)

    def _estimate_letter_spacing(self, name: str) -> float:
        spacings = {
            "display": -0.02,
            "heading-1": -0.015,
            "heading-2": -0.01,
            "heading-3": 0,
            "heading-4": 0,
            "body-large": 0,
            "body": 0,
            "caption": 0.01,
        }
        return spacings.get(name, 0)

    def _get_semantics(self, name: str) -> str:
        semantics = {
            "display": "冲击力、品牌人格",
            "heading-1": "页面主标题、层级最高",
            "heading-2": "章节标题、二级层级",
            "heading-3": "子章节标题、三级层级",
            "heading-4": "小标题、四级层级",
            "body-large": "重要正文、强调内容",
            "body": "标准正文、主要内容",
            "caption": "辅助文字、说明信息",
        }
        return semantics.get(name, "通用文字")

    def _get_usage(self, name: str) -> List[str]:
        usages = {
            "display": ["Hero标题", "品牌标语", "重大公告"],
            "heading-1": ["页面标题", "文章标题", "产品名称"],
            "heading-2": ["章节标题", "卡片标题", "区块标题"],
            "heading-3": ["子章节标题", "功能标题", "列表标题"],
            "heading-4": ["小标题", "标签", "按钮文字"],
            "body-large": ["导语", "重要段落", "强调文字"],
            "body": ["正文内容", "描述文字", "说明文字"],
            "caption": ["时间戳", "标签文字", "辅助说明"],
        }
        return usages.get(name, ["通用文字"])

    def calculate_rhythm_score(self, tokens: List[TypographyToken]) -> float:
        if len(tokens) < 2:
            return 0.0

        font_sizes = []
        for token in tokens:
            size_match = re.search(r'(\d+(\.\d+)?)px', token.font_size)
            if size_match:
                font_sizes.append(float(size_match.group(1)))

        if len(font_sizes) < 2:
            return 0.5

        font_sizes.sort(reverse=True)
        ratios = []
        for i in range(len(font_sizes) - 1):
            ratio = font_sizes[i] / font_sizes[i + 1]
            ratios.append(ratio)

        avg_ratio = sum(ratios) / len(ratios)
        golden_ratio = 1.618

        return 1.0 - abs(avg_ratio - golden_ratio) / golden_ratio


class SpacingAnalyzer:
    """间距分析器：分析间距系统和空间呼吸感"""

    def analyze(self, width: int) -> List[SpacingToken]:
        base = 4
        scale = "golden-ratio"

        spacing_values = [
            ("xs", f"{base * 2}px", "紧凑间距，用于微小元素"),
            ("sm", f"{base * 4}px", "小间距，用于元素内部"),
            ("md", f"{base * 6}px", "中等间距，用于卡片内部"),
            ("lg", f"{base * 8}px", "大间距，用于区块分隔"),
            ("xl", f"{base * 12}px", "超大间距，用于页面分区"),
            ("2xl", f"{base * 16}px", "特大间距，用于首屏"),
        ]

        tokens = []
        for name, value, semantics in spacing_values:
            tokens.append(SpacingToken(
                name=name,
                value=value,
                scale=scale,
                semantics=semantics,
                usage=self._get_usage(name)
            ))

        return tokens

    def _get_usage(self, name: str) -> List[str]:
        usages = {
            "xs": ["图标间距", "文字间距", "内边距微小"],
            "sm": ["按钮内边距", "标签间距", "表单元素"],
            "md": ["卡片内边距", "列表项间距", "输入框"],
            "lg": ["段落间距", "卡片间距", "区块内边距"],
            "xl": ["页面分区", "Header间距", "Footer间距"],
            "2xl": ["首屏间距", "Hero区域", "大标题间距"],
        }
        return usages.get(name, ["通用间距"])


class TokenConsumptionEstimator:
    """Token消耗估算器：计算风格分析和代码生成的token消耗"""

    def __init__(self):
        self.token_per_char = 0.5
        self.token_per_pixel = 0.0001
        self.base_overhead = 100

    def estimate_image_analysis(self, image_path: str) -> Dict[str, int]:
        try:
            if PIL_AVAILABLE:
                img = Image.open(image_path)
                width, height = img.size
                pixels = width * height
            elif CV2_AVAILABLE:
                img = cv2.imread(image_path)
                height, width = img.shape[:2]
                pixels = width * height
            else:
                pixels = 1920 * 1080

            encoded_size = self._estimate_base64_size(image_path)

            return {
                "image_encoding": int(encoded_size * self.token_per_char),
                "feature_extraction": 500,
                "style_analysis": 300,
                "design_token_generation": 200,
                "total": int(encoded_size * self.token_per_char) + 1000,
            }
        except Exception as e:
            logger.error(f"Token estimation failed: {e}")
            return {
                "image_encoding": 2000,
                "feature_extraction": 500,
                "style_analysis": 300,
                "design_token_generation": 200,
                "total": 3000,
            }

    def _estimate_base64_size(self, image_path: str) -> int:
        if os.path.exists(image_path):
            file_size = os.path.getsize(image_path)
            return int(file_size * 1.33)
        return 10000

    def estimate_code_generation(self, result: StyleAnalysisResult) -> Dict[str, int]:
        css_tokens = len(result.colors) * 50 + len(result.typography) * 80 + len(result.spacing) * 30
        js_tokens = 500
        html_tokens = 300
        design_tokens_yaml = len(result.colors) * 40 + len(result.typography) * 60 + len(result.spacing) * 20

        return {
            "css_generation": css_tokens,
            "js_generation": js_tokens,
            "html_generation": html_tokens,
            "design_tokens_yaml": design_tokens_yaml,
            "total": css_tokens + js_tokens + html_tokens + design_tokens_yaml,
        }

    def estimate_complete_workflow(self, image_path: str, result: Optional[StyleAnalysisResult] = None) -> Dict[str, int]:
        analysis = self.estimate_image_analysis(image_path)
        generation = self.estimate_code_generation(result) if result else {"total": 2000}

        return {
            "analysis": analysis["total"],
            "generation": generation["total"],
            "verification": 500,
            "feedback": 200,
            "total_workflow": analysis["total"] + generation["total"] + 700,
        }

    def calculate_compression_ratio(self, original_features: Dict[str, Any], compressed_tokens: int) -> float:
        original_size = sum(len(str(v)) for v in original_features.values())
        compressed_size = compressed_tokens * 2
        return (1 - compressed_size / original_size) * 100 if original_size > 0 else 0


class VisualStyleAnalyzer:
    """视觉风格分析器：整合所有分析模块"""

    def __init__(self):
        self.color_extractor = ColorExtractor()
        self.layout_analyzer = LayoutAnalyzer()
        self.typography_analyzer = TypographyAnalyzer()
        self.spacing_analyzer = SpacingAnalyzer()
        self.token_estimator = TokenConsumptionEstimator()

    def analyze(self, image_path: str) -> StyleAnalysisResult:
        logger.info(f"Analyzing visual style from: {image_path}")

        colors = self.color_extractor.extract_from_image(image_path)
        layout = self.layout_analyzer.analyze(image_path)
        typography = self.typography_analyzer.analyze(image_path)

        width = 1920
        try:
            if PIL_AVAILABLE:
                img = Image.open(image_path)
                width = img.size[0]
        except:
            pass

        spacing = self.spacing_analyzer.analyze(width)

        color_harmony = self.color_extractor.analyze_harmony(colors)
        typography_rhythm = self.typography_analyzer.calculate_rhythm_score(typography)
        complexity = self._calculate_complexity(colors, typography, layout)

        dominant_style = self._determine_dominant_style(colors, layout)

        token_estimate = self.token_estimator.estimate_image_analysis(image_path)

        return StyleAnalysisResult(
            colors=colors,
            typography=typography,
            spacing=spacing,
            layout=layout,
            dominant_style=dominant_style,
            complexity_score=complexity,
            color_harmony_score=color_harmony,
            typography_rhythm_score=typography_rhythm,
            token_estimate=token_estimate,
        )

    def _calculate_complexity(self, colors: List[ColorToken], typography: List[TypographyToken], layout: LayoutPattern) -> float:
        color_complexity = min(len(colors) / 8, 1.0)
        font_complexity = min(len(typography) / 8, 1.0)
        layout_complexity = min(layout.grid_columns / 16, 1.0)

        return (color_complexity + font_complexity + layout_complexity) / 3

    def _determine_dominant_style(self, colors: List[ColorToken], layout: LayoutPattern) -> str:
        if not colors:
            return "unknown"

        brightness_scores = []
        for color in colors:
            r, g, b = color.rgb
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            brightness_scores.append(brightness)

        avg_brightness = sum(brightness_scores) / len(brightness_scores)

        if avg_brightness > 200:
            if layout.pattern_type == "mobile":
                return "minimal-mobile"
            return "minimal-clean"
        elif avg_brightness < 80:
            return "dark-mode"
        else:
            if layout.pattern_type == "wide":
                return "corporate-professional"
            return "modern-balanced"

    def generate_design_tokens_yaml(self, result: StyleAnalysisResult) -> str:
        yaml_lines = ["design_tokens:\n"]

        yaml_lines.append("  colors:\n")
        for color in result.colors:
            yaml_lines.append(f"    {color.name}:\n")
            yaml_lines.append(f"      value: \"{color.hex}\"\n")
            yaml_lines.append(f"      semantics: \"{color.semantics}\"\n")
            yaml_lines.append(f"      usage: {json.dumps(color.usage)}\n")
            if color.forbidden:
                yaml_lines.append(f"      forbidden: {json.dumps(color.forbidden)}\n")

        yaml_lines.append("\n  typography:\n")
        for font in result.typography:
            yaml_lines.append(f"    {font.font_size}: # {font.semantics}\n")
            yaml_lines.append(f"      fontFamily: {json.dumps(font.font_family)}\n")
            yaml_lines.append(f"      fontWeight: {font.font_weight}\n")
            yaml_lines.append(f"      fontSize: \"{font.font_size}\"\n")
            yaml_lines.append(f"      lineHeight: {font.line_height}\n")
            yaml_lines.append(f"      letterSpacing: {font.letter_spacing}em\n")

        yaml_lines.append("\n  spacing:\n")
        for space in result.spacing:
            yaml_lines.append(f"    {space.name}:\n")
            yaml_lines.append(f"      value: \"{space.value}\"\n")
            yaml_lines.append(f"      semantics: \"{space.semantics}\"\n")

        yaml_lines.append("\n  layout:\n")
        yaml_lines.append(f"    columns: {result.layout.grid_columns}\n")
        yaml_lines.append(f"    gutter: \"{result.layout.gutter_width}\"\n")
        yaml_lines.append(f"    pattern: \"{result.layout.pattern_type}\"\n")

        return "".join(yaml_lines)

    def generate_css(self, result: StyleAnalysisResult) -> str:
        css_lines = [":root {\n"]

        for color in result.colors:
            css_lines.append(f"  --color-{color.name}: {color.hex};\n")

        for space in result.spacing:
            css_lines.append(f"  --spacing-{space.name}: {space.value};\n")

        css_lines.append("}\n\n")

        css_lines.append("/* Typography */\n")
        for font in result.typography:
            css_lines.append(f".text-{font.font_size.split('(')[0].strip()} {{\n")
            css_lines.append(f"  font-family: {', '.join(font.font_family)};\n")
            css_lines.append(f"  font-weight: {font.font_weight};\n")
            css_lines.append(f"  font-size: {font.font_size};\n")
            css_lines.append(f"  line-height: {font.line_height};\n")
            css_lines.append(f"  letter-spacing: {font.letter_spacing}em;\n")
            css_lines.append("}\n\n")

        css_lines.append("/* Layout */\n")
        css_lines.append(f".container {{\n")
        css_lines.append(f"  max-width: 1280px;\n")
        css_lines.append(f"  margin: 0 auto;\n")
        css_lines.append(f"  padding: var(--spacing-md);\n")
        css_lines.append("}\n")

        return "".join(css_lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python visual_style_analyzer.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    analyzer = VisualStyleAnalyzer()
    result = analyzer.analyze(image_path)

    print("=" * 60)
    print("视觉风格分析结果")
    print("=" * 60)

    print("\n主色调方案:")
    for color in result.colors[:5]:
        print(f"  {color.hex} - {color.name} ({color.semantics})")

    print(f"\n色彩和谐度: {result.color_harmony_score:.2f}")
    print(f"排版韵律: {result.typography_rhythm_score:.2f}")
    print(f"复杂度: {result.complexity_score:.2f}")
    print(f"主导风格: {result.dominant_style}")

    print("\n布局模式:")
    print(f"  类型: {result.layout.pattern_type}")
    print(f"  列数: {result.layout.grid_columns}")
    print(f"  间距: {result.layout.gutter_width}")

    print("\nToken消耗估算:")
    for key, value in result.token_estimate.items():
        print(f"  {key}: {value} tokens")

    print("\n" + "=" * 60)
    print("设计令牌YAML已生成")
    print("=" * 60)

    yaml_output = analyzer.generate_design_tokens_yaml(result)
    print(yaml_output[:500] + "..." if len(yaml_output) > 500 else yaml_output)
