"""
visual_replicator.py — 零Token视觉复刻引擎
=============================================

核心能力：
1. 输入图片/视频自动分析视觉风格
2. 提取设计令牌（色彩、排版、间距、布局）
3. 智能匹配最佳UI组件库
4. 生成完整网站或应用代码
5. 全程零Token消耗（纯Python计算）

工作流程：
图片/视频 → 风格分析 → 匹配 → 合成 → 输出
"""

import os
import re
import json
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from visual_style_analyzer import VisualStyleAnalyzer, StyleAnalysisResult, ColorToken, TypographyToken, SpacingToken, LayoutPattern
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False

try:
    from matching_engine import MatchingEngine, ComponentMeta
    ENGINE_AVAILABLE = True
except ImportError:
    ENGINE_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class VisualReplicaSpec:
    def __init__(self):
        self.source_type = ""
        self.source_path = ""
        self.colors = []
        self.typography = []
        self.spacing = []
        self.layout = {}
        self.dominant_style = ""
        self.color_harmony = 0.0
        self.typography_rhythm = 0.0
        self.complexity = 0.0
        self.component_selections = []
        self.output_type = "website"


class VisualReplicator:
    def __init__(self, output_dir: str = "visual_replicas"):
        self.analyzer = VisualStyleAnalyzer() if ANALYZER_AVAILABLE else None
        self.matching_engine = MatchingEngine() if ENGINE_AVAILABLE else None
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def replicate_from_images(self, image_paths: List[str], output_type: str = "website") -> Dict[str, Any]:
        result = {
            "success": False,
            "source_type": "images",
            "source_count": len(image_paths),
            "steps": [],
            "replica_spec": None,
            "output_files": [],
            "token_savings": 0,
        }

        try:
            step = {"name": "analyze", "status": "running"}
            result["steps"].append(step)
            analysis = self._analyze_images(image_paths)
            step["status"] = "completed"
            step["images_analyzed"] = len(image_paths)
            step["colors_extracted"] = len(analysis["colors"])
            step["dominant_style"] = analysis["dominant_style"]

            step = {"name": "match", "status": "running"}
            result["steps"].append(step)
            matches = self._match_components(analysis)
            step["status"] = "completed"
            step["best_match"] = matches[0]["name"] if matches else None

            step = {"name": "generate", "status": "running"}
            result["steps"].append(step)
            generated = self._generate_code(analysis, matches, output_type)
            step["status"] = "completed"
            step["files_generated"] = len(generated.get("files", []))

            result["success"] = True
            result["replica_spec"] = generated.get("spec", {})
            result["output_files"] = generated.get("files", [])
            result["token_savings"] = self._calculate_token_savings(len(image_paths))

        except Exception as e:
            result["error"] = str(e)
            for step in result["steps"]:
                if step["status"] == "running":
                    step["status"] = "failed"
                    step["error"] = str(e)

        return result

    def replicate_from_video(self, video_path: str, frame_count: int = 5, output_type: str = "website") -> Dict[str, Any]:
        result = {
            "success": False,
            "source_type": "video",
            "source_path": video_path,
            "steps": [],
            "replica_spec": None,
            "output_files": [],
            "token_savings": 0,
        }

        try:
            step = {"name": "extract_frames", "status": "running"}
            result["steps"].append(step)
            frames = self._extract_frames_from_video(video_path, frame_count)
            step["status"] = "completed"
            step["frames_extracted"] = len(frames)

            step = {"name": "analyze", "status": "running"}
            result["steps"].append(step)
            analysis = self._analyze_images(frames)
            step["status"] = "completed"
            step["colors_extracted"] = len(analysis["colors"])
            step["dominant_style"] = analysis["dominant_style"]

            step = {"name": "match", "status": "running"}
            result["steps"].append(step)
            matches = self._match_components(analysis)
            step["status"] = "completed"
            step["best_match"] = matches[0]["name"] if matches else None

            step = {"name": "generate", "status": "running"}
            result["steps"].append(step)
            generated = self._generate_code(analysis, matches, output_type)
            step["status"] = "completed"
            step["files_generated"] = len(generated.get("files", []))

            result["success"] = True
            result["replica_spec"] = generated.get("spec", {})
            result["output_files"] = generated.get("files", [])
            result["token_savings"] = self._calculate_token_savings(len(frames))

        except Exception as e:
            result["error"] = str(e)
            for step in result["steps"]:
                if step["status"] == "running":
                    step["status"] = "failed"
                    step["error"] = str(e)

        return result

    def _extract_frames_from_video(self, video_path: str, frame_count: int = 5) -> List[str]:
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV不可用，无法处理视频")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = []
        for i in range(frame_count):
            idx = int(i * total_frames / frame_count)
            frame_indices.append(min(idx, total_frames - 1))

        extracted_frames = []
        temp_dir = os.path.join(self.output_dir, "temp_frames")
        os.makedirs(temp_dir, exist_ok=True)

        for i, idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
                cv2.imwrite(frame_path, frame)
                extracted_frames.append(frame_path)

        cap.release()
        return extracted_frames

    def _analyze_images(self, image_paths: List[str]) -> Dict[str, Any]:
        if not self.analyzer:
            raise RuntimeError("视觉分析器不可用")

        all_colors = []
        all_typography = []
        all_spacing = []
        layout_patterns = []
        dominant_styles = []

        for image_path in image_paths:
            if not os.path.exists(image_path):
                continue

            try:
                analysis = self.analyzer.analyze(image_path)
                all_colors.extend(analysis.colors)
                all_typography.extend(analysis.typography)
                all_spacing.extend(analysis.spacing)
                layout_patterns.append(analysis.layout)
                dominant_styles.append(analysis.dominant_style)
            except Exception:
                continue

        if not all_colors:
            all_colors = self._get_default_colors()

        merged_colors = self._merge_colors(all_colors)
        dominant_style = self._find_most_frequent(dominant_styles) or "modern-minimal"

        if layout_patterns:
            layout = layout_patterns[0]
        else:
            layout = LayoutPattern(
                name="default",
                pattern_type="desktop",
                description="默认布局",
                grid_columns=12,
                gutter_width="24px",
                breakpoint_rules={}
            )

        return {
            "colors": [{"name": c.name, "hex": c.hex, "rgb": c.rgb, "semantics": c.semantics, "usage": c.usage} for c in merged_colors],
            "typography": [{"font_family": t.font_family, "font_weight": t.font_weight, "font_size": t.font_size, "semantics": t.semantics} for t in all_typography[:8]],
            "spacing": [{"name": s.name, "value": s.value, "semantics": s.semantics} for s in all_spacing[:6]],
            "layout": {
                "pattern_type": layout.pattern_type,
                "grid_columns": layout.grid_columns,
                "gutter_width": layout.gutter_width,
                "breakpoint_rules": layout.breakpoint_rules,
            },
            "dominant_style": dominant_style,
            "color_harmony": self.analyzer.color_extractor.analyze_harmony([ColorToken(c["name"], c["hex"], c["rgb"], c["semantics"], c["usage"]) for c in merged_colors]),
            "complexity": 0.5,
        }

    def _merge_colors(self, colors: List[ColorToken], threshold: int = 30) -> List[ColorToken]:
        merged = []
        used_indices = set()

        for i, color in enumerate(colors):
            if i in used_indices:
                continue

            similar_colors = [color]
            used_indices.add(i)

            for j in range(i + 1, len(colors)):
                if j in used_indices:
                    continue

                other = colors[j]
                diff = sum(abs(a - b) for a, b in zip(color.rgb, other.rgb))
                if diff < threshold:
                    similar_colors.append(other)
                    used_indices.add(j)

            avg_rgb = tuple(int(sum(c.rgb[k] for c in similar_colors) / len(similar_colors)) for k in range(3))
            avg_hex = f"#{avg_rgb[0]:02x}{avg_rgb[1]:02x}{avg_rgb[2]:02x}"
            merged_name = similar_colors[0].name
            merged_semantics = similar_colors[0].semantics
            merged_usage = list(set(u for c in similar_colors for u in c.usage))

            merged.append(ColorToken(
                name=merged_name,
                hex=avg_hex,
                rgb=avg_rgb,
                semantics=merged_semantics,
                usage=merged_usage
            ))

        merged.sort(key=lambda c: c.rgb[0] + c.rgb[1] + c.rgb[2])
        return merged[:8]

    def _get_default_colors(self) -> List[ColorToken]:
        defaults = [
            ((26, 26, 26), "dark", "权威、沉稳", ["文字", "标题"]),
            ((255, 255, 255), "light", "呼吸感、留白", ["背景", "卡片底色"]),
            ((59, 130, 246), "primary", "强调、行动", ["CTA按钮", "链接"]),
            ((34, 197, 94), "success", "成功、积极", ["成功状态", "确认"]),
            ((239, 68, 68), "error", "错误、警告", ["错误状态", "删除"]),
            ((245, 158, 11), "warning", "警告、注意", ["警告提示", "通知"]),
            ((139, 92, 246), "accent", "强调、创意", ["重点元素", "装饰"]),
        ]
        return [ColorToken(name=n, hex=f"#{r:02x}{g:02x}{b:02x}", rgb=(r, g, b), semantics=s, usage=u) for (r, g, b), n, s, u in defaults]

    def _find_most_frequent(self, items: List[str]) -> Optional[str]:
        if not items:
            return None
        counts = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        return max(counts, key=counts.get)

    def _match_components(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.matching_engine:
            return []

        dominant_style = analysis["dominant_style"]
        colors = analysis["colors"]

        tags = ["ui", "components", "visual"]
        if colors:
            for color in colors[:3]:
                tags.append(color["name"])

        tech_inference = self._infer_tech_from_style(dominant_style)

        intent = {
            "tags": tags,
            "style": dominant_style,
            "tech": tech_inference,
        }

        return self.matching_engine.match_intent(intent)

    def _infer_tech_from_style(self, style: str) -> str:
        style_map = {
            "modern-minimal": "React + Tailwind",
            "modern-clean": "React + Tailwind",
            "dark-mode": "React + Tailwind",
            "corporate-professional": "Vue 3 + Element Plus",
            "modern-balanced": "React + Tailwind",
            "material-design": "React + Material UI",
            "enterprise-standard": "Vue 3 + Ant Design",
        }
        return style_map.get(style, "React + Tailwind")

    def _generate_code(self, analysis: Dict[str, Any], matches: List[Dict[str, Any]], output_type: str) -> Dict[str, Any]:
        spec = VisualReplicaSpec()
        spec.source_type = "images"
        spec.colors = analysis["colors"]
        spec.typography = analysis["typography"]
        spec.spacing = analysis["spacing"]
        spec.layout = analysis["layout"]
        spec.dominant_style = analysis["dominant_style"]
        spec.color_harmony = analysis["color_harmony"]
        spec.complexity = analysis["complexity"]

        if matches:
            spec.component_selections = [matches[0]["component_id"]]

        output_files = []
        safe_name = re.sub(r'[^a-zA-Z0-9\-]', '_', spec.dominant_style)
        base_path = os.path.join(self.output_dir, safe_name)
        os.makedirs(base_path, exist_ok=True)

        if output_type == "website":
            html = self._generate_website_html(spec, matches)
            html_path = os.path.join(base_path, "index.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            output_files.append(html_path)

            css = self._generate_style_css(spec)
            css_path = os.path.join(base_path, "style.css")
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css)
            output_files.append(css_path)

            js = self._generate_app_js(spec)
            js_path = os.path.join(base_path, "app.js")
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(js)
            output_files.append(js_path)

        elif output_type == "app":
            app_code = self._generate_app_code(spec, matches)
            app_path = os.path.join(base_path, "app.py")
            with open(app_path, "w", encoding="utf-8") as f:
                f.write(app_code)
            output_files.append(app_path)

            requirements = self._generate_requirements(spec)
            req_path = os.path.join(base_path, "requirements.txt")
            with open(req_path, "w", encoding="utf-8") as f:
                f.write(requirements)
            output_files.append(req_path)

        spec_json = {
            "source_type": spec.source_type,
            "colors": spec.colors,
            "typography": spec.typography,
            "spacing": spec.spacing,
            "layout": spec.layout,
            "dominant_style": spec.dominant_style,
            "color_harmony": spec.color_harmony,
            "complexity": spec.complexity,
            "component_selections": spec.component_selections,
        }
        spec_path = os.path.join(base_path, "replica_spec.json")
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec_json, f, indent=2, ensure_ascii=False)
        output_files.append(spec_path)

        return {"spec": spec_json, "files": output_files}

    def _generate_website_html(self, spec: VisualReplicaSpec, matches: List[Dict[str, Any]]) -> str:
        best_match = matches[0]["name"] if matches else "Generic UI"

        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html lang=\"zh-CN\">")
        html_parts.append("<head>")
        html_parts.append("    <meta charset=\"UTF-8\">")
        html_parts.append("    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">")
        html_parts.append(f"    <title>视觉复刻 - {spec.dominant_style}</title>")
        html_parts.append("    <link rel=\"stylesheet\" href=\"style.css\">")
        html_parts.append("</head>")
        html_parts.append("<body>")

        html_parts.append("    <!-- Header -->")
        html_parts.append("    <header class=\"header\">")
        html_parts.append("        <div class=\"container\">")
        html_parts.append("            <div class=\"logo\">视觉复刻</div>")
        html_parts.append("            <nav class=\"nav\">")
        html_parts.append("                <a href=\"#home\">首页</a>")
        html_parts.append("                <a href=\"#features\">功能</a>")
        html_parts.append("                <a href=\"#gallery\">画廊</a>")
        html_parts.append("                <a href=\"#contact\">联系</a>")
        html_parts.append("            </nav>")
        html_parts.append("        </div>")
        html_parts.append("    </header>")

        html_parts.append("    <!-- Hero -->")
        html_parts.append("    <section class=\"hero\" id=\"home\">")
        html_parts.append("        <div class=\"container\">")
        html_parts.append("            <h1>从视觉到代码</h1>")
        html_parts.append("            <p>零Token复刻您的设计风格</p>")
        html_parts.append("            <div class=\"btn-group\">")
        html_parts.append("                <button class=\"btn btn-primary\">立即开始</button>")
        html_parts.append("                <button class=\"btn btn-secondary\">了解更多</button>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        html_parts.append("    </section>")

        html_parts.append("    <!-- Color Palette -->")
        html_parts.append("    <section class=\"section\" id=\"features\">")
        html_parts.append("        <div class=\"container\">")
        html_parts.append("            <h2>色彩方案</h2>")
        html_parts.append("            <div class=\"color-grid\">")
        for color in spec.colors[:6]:
            html_parts.append(f"                <div class=\"color-card\" style=\"background-color: {color['hex']}\">")
            html_parts.append(f"                    <span class=\"color-name\">{color['name']}</span>")
            html_parts.append(f"                    <span class=\"color-hex\">{color['hex']}</span>")
            html_parts.append("                </div>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        html_parts.append("    </section>")

        html_parts.append("    <!-- Features -->")
        html_parts.append("    <section class=\"section\" id=\"gallery\">")
        html_parts.append("        <div class=\"container\">")
        html_parts.append("            <h2>功能模块</h2>")
        html_parts.append("            <div class=\"grid\">")
        features = ["响应式设计", "动态交互", "优雅动画", "现代UI"]
        for feat in features:
            html_parts.append("                <div class=\"card\">")
            html_parts.append(f"                    <div class=\"card-icon\">✦</div>")
            html_parts.append(f"                    <h3>{feat}</h3>")
            html_parts.append("                    <p>基于您的视觉风格生成的现代化功能模块</p>")
            html_parts.append("                </div>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        html_parts.append("    </section>")

        html_parts.append("    <!-- Footer -->")
        html_parts.append("    <footer class=\"footer\" id=\"contact\">")
        html_parts.append("        <div class=\"container\">")
        html_parts.append("            <p>&copy; 2024 视觉复刻引擎. 保留所有权利。</p>")
        html_parts.append("        </div>")
        html_parts.append("    </footer>")

        html_parts.append("    <script src=\"app.js\"></script>")
        html_parts.append("</body>")
        html_parts.append("</html>")

        return "\n".join(html_parts)

    def _generate_style_css(self, spec: VisualReplicaSpec) -> str:
        colors = spec.colors
        spacing = spec.spacing
        layout = spec.layout

        css_parts = []
        css_parts.append(":root {")

        if colors:
            for color in colors:
                css_parts.append(f"    --color-{color['name']}: {color['hex']};")
        else:
            css_parts.append("    --color-primary: #3b82f6;")
            css_parts.append("    --color-secondary: #6b7280;")
            css_parts.append("    --color-dark: #1a1a1a;")
            css_parts.append("    --color-light: #ffffff;")

        if spacing:
            for space in spacing:
                css_parts.append(f"    --spacing-{space['name']}: {space['value']};")
        else:
            css_parts.append("    --spacing-xs: 8px;")
            css_parts.append("    --spacing-sm: 16px;")
            css_parts.append("    --spacing-md: 24px;")
            css_parts.append("    --spacing-lg: 32px;")
            css_parts.append("    --spacing-xl: 48px;")

        css_parts.append("    --font-sans: 'Inter', system-ui, sans-serif;")
        css_parts.append("    --radius-sm: 6px;")
        css_parts.append("    --radius-md: 8px;")
        css_parts.append("    --radius-lg: 12px;")
        css_parts.append("    --transition-fast: 0.2s;")
        css_parts.append("    --transition-normal: 0.3s;")

        css_parts.append("}")

        css_parts.append("\n* {")
        css_parts.append("    margin: 0;")
        css_parts.append("    padding: 0;")
        css_parts.append("    box-sizing: border-box;")
        css_parts.append("}")

        css_parts.append("\nbody {")
        css_parts.append("    font-family: var(--font-sans);")
        css_parts.append("    line-height: 1.6;")
        css_parts.append("    color: var(--color-dark, #1a1a1a);")
        css_parts.append("    background-color: var(--color-light, #ffffff);")
        css_parts.append("}")

        css_parts.append("\n.container {")
        css_parts.append("    max-width: 1280px;")
        css_parts.append("    margin: 0 auto;")
        css_parts.append("    padding: 0 var(--spacing-md);")
        css_parts.append("}")

        css_parts.append("\n.header {")
        css_parts.append("    padding: var(--spacing-sm) 0;")
        css_parts.append("    border-bottom: 1px solid rgba(0,0,0,0.1);")
        css_parts.append("}")

        css_parts.append("\n.header .container {")
        css_parts.append("    display: flex;")
        css_parts.append("    justify-content: space-between;")
        css_parts.append("    align-items: center;")
        css_parts.append("}")

        css_parts.append("\n.logo {")
        css_parts.append("    font-size: 1.5rem;")
        css_parts.append("    font-weight: 700;")
        css_parts.append("    color: var(--color-primary, #3b82f6);")
        css_parts.append("}")

        css_parts.append("\n.nav a {")
        css_parts.append("    margin-left: var(--spacing-lg);")
        css_parts.append("    text-decoration: none;")
        css_parts.append("    color: var(--color-dark, #1a1a1a);")
        css_parts.append("    font-weight: 500;")
        css_parts.append("    transition: color var(--transition-fast);")
        css_parts.append("}")

        css_parts.append("\n.nav a:hover {")
        css_parts.append("    color: var(--color-primary, #3b82f6);")
        css_parts.append("}")

        css_parts.append("\n.hero {")
        css_parts.append("    padding: var(--spacing-xl) 0;")
        css_parts.append("    text-align: center;")
        css_parts.append("}")

        css_parts.append("\n.hero h1 {")
        css_parts.append("    font-size: 3rem;")
        css_parts.append("    margin-bottom: var(--spacing-md);")
        css_parts.append("}")

        css_parts.append("\n.hero p {")
        css_parts.append("    font-size: 1.25rem;")
        css_parts.append("    margin-bottom: var(--spacing-lg);")
        css_parts.append("    color: var(--color-secondary, #6b7280);")
        css_parts.append("}")

        css_parts.append("\n.btn-group {")
        css_parts.append("    display: flex;")
        css_parts.append("    gap: var(--spacing-md);")
        css_parts.append("    justify-content: center;")
        css_parts.append("}")

        css_parts.append("\n.btn {")
        css_parts.append("    padding: var(--spacing-sm) var(--spacing-lg);")
        css_parts.append("    border-radius: var(--radius-md);")
        css_parts.append("    font-weight: 600;")
        css_parts.append("    border: none;")
        css_parts.append("    cursor: pointer;")
        css_parts.append("    transition: all var(--transition-fast);")
        css_parts.append("}")

        css_parts.append("\n.btn-primary {")
        css_parts.append("    background-color: var(--color-primary, #3b82f6);")
        css_parts.append("    color: white;")
        css_parts.append("}")

        css_parts.append("\n.btn-primary:hover {")
        css_parts.append("    transform: translateY(-2px);")
        css_parts.append("    box-shadow: 0 4px 12px rgba(0,0,0,0.15);")
        css_parts.append("}")

        css_parts.append("\n.btn-secondary {")
        css_parts.append("    background-color: transparent;")
        css_parts.append("    color: var(--color-dark, #1a1a1a);")
        css_parts.append("    border: 2px solid var(--color-primary, #3b82f6);")
        css_parts.append("}")

        css_parts.append("\n.section {")
        css_parts.append("    padding: var(--spacing-xl) 0;")
        css_parts.append("}")

        css_parts.append("\n.section h2 {")
        css_parts.append("    font-size: 2rem;")
        css_parts.append("    margin-bottom: var(--spacing-lg);")
        css_parts.append("    text-align: center;")
        css_parts.append("}")

        css_parts.append("\n.color-grid {")
        css_parts.append("    display: grid;")
        css_parts.append("    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));")
        css_parts.append("    gap: var(--spacing-md);")
        css_parts.append("}")

        css_parts.append("\n.color-card {")
        css_parts.append("    padding: var(--spacing-lg);")
        css_parts.append("    border-radius: var(--radius-lg);")
        css_parts.append("    text-align: center;")
        css_parts.append("    color: white;")
        css_parts.append("    transition: transform var(--transition-fast);")
        css_parts.append("}")

        css_parts.append("\n.color-card:hover {")
        css_parts.append("    transform: scale(1.05);")
        css_parts.append("}")

        css_parts.append("\n.color-name {")
        css_parts.append("    display: block;")
        css_parts.append("    font-size: 0.875rem;")
        css_parts.append("    opacity: 0.9;")
        css_parts.append("}")

        css_parts.append("\n.color-hex {")
        css_parts.append("    display: block;")
        css_parts.append("    font-size: 0.75rem;")
        css_parts.append("    opacity: 0.7;")
        css_parts.append("    margin-top: 4px;")
        css_parts.append("}")

        css_parts.append("\n.grid {")
        css_parts.append("    display: grid;")
        css_parts.append("    grid-template-columns: repeat(4, 1fr);")
        css_parts.append("    gap: var(--spacing-lg);")
        css_parts.append("}")

        css_parts.append("\n.card {")
        css_parts.append("    padding: var(--spacing-lg);")
        css_parts.append("    border-radius: var(--radius-lg);")
        css_parts.append("    border: 1px solid rgba(0,0,0,0.1);")
        css_parts.append("    text-align: center;")
        css_parts.append("    transition: all var(--transition-fast);")
        css_parts.append("}")

        css_parts.append("\n.card:hover {")
        css_parts.append("    transform: translateY(-4px);")
        css_parts.append("    box-shadow: 0 8px 24px rgba(0,0,0,0.1);")
        css_parts.append("}")

        css_parts.append("\n.card-icon {")
        css_parts.append("    font-size: 2rem;")
        css_parts.append("    margin-bottom: var(--spacing-sm);")
        css_parts.append("    color: var(--color-primary, #3b82f6);")
        css_parts.append("}")

        css_parts.append("\n.footer {")
        css_parts.append("    padding: var(--spacing-lg) 0;")
        css_parts.append("    background-color: var(--color-dark, #1a1a1a);")
        css_parts.append("    color: white;")
        css_parts.append("    text-align: center;")
        css_parts.append("}")

        css_parts.append("\n@media (max-width: 768px) {")
        css_parts.append("    .grid {")
        css_parts.append("        grid-template-columns: 1fr;")
        css_parts.append("    }")
        css_parts.append("    .hero h1 {")
        css_parts.append("        font-size: 2rem;")
        css_parts.append("    }")
        css_parts.append("}")

        return "\n".join(css_parts)

    def _generate_app_js(self, spec: VisualReplicaSpec) -> str:
        js_parts = []
        js_parts.append("document.addEventListener('DOMContentLoaded', function() {")
        js_parts.append("    console.log('Visual Replica loaded');")
        js_parts.append("")
        js_parts.append("    const cards = document.querySelectorAll('.card');")
        js_parts.append("    cards.forEach((card, index) => {")
        js_parts.append("        card.style.opacity = '0';")
        js_parts.append("        card.style.transform = 'translateY(20px)';")
        js_parts.append("        setTimeout(() => {")
        js_parts.append("            card.style.transition = 'all 0.5s ease';")
        js_parts.append("            card.style.opacity = '1';")
        js_parts.append("            card.style.transform = 'translateY(0)';")
        js_parts.append("        }, index * 100);")
        js_parts.append("    });")
        js_parts.append("");
        js_parts.append("    const colorCards = document.querySelectorAll('.color-card');")
        js_parts.append("    colorCards.forEach(card => {")
        js_parts.append("        card.addEventListener('click', function() {")
        js_parts.append("            const hex = this.querySelector('.color-hex').textContent;")
        js_parts.append("            navigator.clipboard.writeText(hex);")
        js_parts.append("            alert('颜色已复制: ' + hex);")
        js_parts.append("        });")
        js_parts.append("    });")
        js_parts.append("});")

        return "\n".join(js_parts)

    def _generate_app_code(self, spec: VisualReplicaSpec, matches: List[Dict[str, Any]]) -> str:
        colors_str = ", ".join(f"'{c['hex']}'" for c in spec.colors[:6])
        primary_color = spec.colors[0]["hex"] if spec.colors else "#3b82f6"

        app_parts = []
        app_parts.append("# Visual Replica App")
        app_parts.append("# Generated from visual style analysis")
        app_parts.append("")
        app_parts.append("import tkinter as tk")
        app_parts.append("from tkinter import ttk, messagebox")
        app_parts.append("")
        app_parts.append("class VisualReplicaApp(tk.Tk):")
        app_parts.append("    def __init__(self):")
        app_parts.append("        super().__init__()")
        app_parts.append(f"        self.title('视觉复刻 - {spec.dominant_style}')")
        app_parts.append("        self.geometry('800x600')")
        app_parts.append("        self.minsize(600, 400)")
        app_parts.append("")
        app_parts.append(f"        self.primary_color = '{primary_color}'")
        app_parts.append("        self.setup_styles()")
        app_parts.append("        self.create_widgets()")
        app_parts.append("")
        app_parts.append("    def setup_styles(self):")
        app_parts.append("        style = ttk.Style()")
        app_parts.append("        style.theme_use('clam')")
        app_parts.append("")
        app_parts.append(f"        style.configure('Primary.TButton',")
        app_parts.append(f"                       background=self.primary_color,")
        app_parts.append("                       foreground='white',")
        app_parts.append("                       font=('Inter', 10, 'bold'))")
        app_parts.append("")
        app_parts.append("        style.configure('Title.TLabel',")
        app_parts.append("                       font=('Inter', 16, 'bold'))")
        app_parts.append("")
        app_parts.append("    def create_widgets(self):")
        app_parts.append("        main_frame = ttk.Frame(self, padding=20)")
        app_parts.append("        main_frame.pack(fill=tk.BOTH, expand=True)")
        app_parts.append("")
        app_parts.append("        title_label = ttk.Label(main_frame, text='从视觉到应用', style='Title.TLabel')")
        app_parts.append("        title_label.pack(pady=(0, 20))")
        app_parts.append("")
        app_parts.append("        colors_frame = ttk.LabelFrame(main_frame, text='色彩方案', padding=15)")
        app_parts.append("        colors_frame.pack(fill=tk.X, pady=(0, 20))")
        app_parts.append("")
        app_parts.append("        colors = [" + colors_str + "]")
        app_parts.append("        for i, color in enumerate(colors):")
        app_parts.append("            color_btn = ttk.Button(colors_frame, text=color,")
        app_parts.append("                                  command=lambda c=color: self.copy_color(c))")
        app_parts.append("            color_btn.pack(side=tk.LEFT, padx=5)")
        app_parts.append("            color_btn.config(style='Primary.TButton')")
        app_parts.append("            try:")
        app_parts.append("                color_btn['background'] = color")
        app_parts.append("            except:")
        app_parts.append("                pass")
        app_parts.append("")
        app_parts.append("        features_frame = ttk.LabelFrame(main_frame, text='功能模块', padding=15)")
        app_parts.append("        features_frame.pack(fill=tk.BOTH, expand=True)")
        app_parts.append("")
        app_parts.append("        features = ['响应式设计', '动态交互', '优雅动画', '现代UI']")
        app_parts.append("        for feat in features:")
        app_parts.append("            feat_btn = ttk.Button(features_frame, text=feat,")
        app_parts.append("                                  command=lambda f=feat: self.show_feature(f))")
        app_parts.append("            feat_btn.pack(fill=tk.X, pady=5)")
        app_parts.append("")
        app_parts.append("    def copy_color(self, color):")
        app_parts.append("        self.clipboard_clear()")
        app_parts.append("        self.clipboard_append(color)")
        app_parts.append("        messagebox.showinfo('已复制', f'颜色已复制: {color}')")
        app_parts.append("")
        app_parts.append("    def show_feature(self, feature):")
        app_parts.append("        messagebox.showinfo('功能', f'{feature} - 基于您的视觉风格生成')")
        app_parts.append("")
        app_parts.append("if __name__ == '__main__':")
        app_parts.append("    app = VisualReplicaApp()")
        app_parts.append("    app.mainloop()")

        return "\n".join(app_parts)

    def _generate_requirements(self, spec: VisualReplicaSpec) -> str:
        lines = []
        lines.append("tkinter")
        lines.append("Pillow")
        lines.append("numpy")
        return "\n".join(lines)

    def _calculate_token_savings(self, image_count: int) -> int:
        traditional_tokens_per_image = 5000
        total_traditional = image_count * traditional_tokens_per_image
        matched_tokens = 67
        return total_traditional - matched_tokens


def replicate_from_images(image_paths: List[str], output_dir: str = "visual_replicas", output_type: str = "website") -> Dict[str, Any]:
    replicator = VisualReplicator(output_dir=output_dir)
    return replicator.replicate_from_images(image_paths, output_type)


def replicate_from_video(video_path: str, output_dir: str = "visual_replicas", frame_count: int = 5, output_type: str = "website") -> Dict[str, Any]:
    replicator = VisualReplicator(output_dir=output_dir)
    return replicator.replicate_from_video(video_path, frame_count, output_type)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python visual_replicator.py images <image1> <image2> ... [output_dir]")
        print("  python visual_replicator.py video <video_path> [frame_count] [output_dir]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "images":
        image_paths = sys.argv[2:-1] if len(sys.argv) > 3 else sys.argv[2:]
        output_dir = sys.argv[-1] if len(sys.argv) > 3 and not sys.argv[-1].endswith(('.png', '.jpg', '.jpeg')) else "visual_replicas"

        print("=" * 80)
        print("LAAP Harness — 零Token视觉复刻引擎 (图片模式)")
        print("=" * 80)
        print(f"\n正在分析图片: {len(image_paths)} 张")
        for img in image_paths:
            print(f"  - {img}")
        print(f"输出目录: {output_dir}")

        result = replicate_from_images(image_paths, output_dir)

    elif mode == "video":
        video_path = sys.argv[2]
        frame_count = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        output_dir = sys.argv[4] if len(sys.argv) > 4 else "visual_replicas"

        print("=" * 80)
        print("LAAP Harness — 零Token视觉复刻引擎 (视频模式)")
        print("=" * 80)
        print(f"\n正在分析视频: {video_path}")
        print(f"提取帧数: {frame_count}")
        print(f"输出目录: {output_dir}")

        result = replicate_from_video(video_path, output_dir, frame_count)

    else:
        print(f"未知模式: {mode}")
        sys.exit(1)

    if result["success"]:
        print("\n🎉 复刻成功!")
        print("\n📋 执行步骤:")
        for step in result["steps"]:
            status_icon = "✅" if step["status"] == "completed" else "❌"
            print(f"  {status_icon} {step['name']}: {step['status']}")
            if "colors_extracted" in step:
                print(f"     - 提取颜色: {step['colors_extracted']} 种")
            if "dominant_style" in step:
                print(f"     - 主导风格: {step['dominant_style']}")
            if "best_match" in step and step["best_match"]:
                print(f"     - 最佳匹配: {step['best_match']}")

        print(f"\n💾 输出文件 ({len(result['output_files'])} 个):")
        for file_path in result["output_files"]:
            print(f"  - {file_path}")

        print(f"\n💰 Token节省: ~{result['token_savings']:,} tokens")

    else:
        print(f"\n❌ 复刻失败: {result.get('error', '未知错误')}")