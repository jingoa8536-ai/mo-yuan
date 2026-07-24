"""harness_decompiler.py — 网页反编译引擎 (爬虫 → HEP 组件)

编译式 AI 的反向管线:
  CrawlRequest(url) → CrawlResult → ComponentDetector → HEPRegistrar → 可复用组件
  
核心思想:
  正向 (Composer):  JSON Spec → 字符串拼接 → HTML (零 token)
  反向 (Decompiler): HTML → 结构分析 → JSON Spec + HEP 组件 (零 token)
  
  网页是"编译产物"→ 反编译回"源码级组件"→ 下次直接装配
  
与现有系统的连接:
  - 输入: web_crawler.CrawlResult (爬虫产出)
  - 输出: hep_protocol.HEPRegistry (注册组件)
  - 消费: harness_composer.HarnessComposer (用 Spec 装配)
  
速度: <500ms 全流程 (纯 Python 解析, 零 LLM)
"""

import os, re, json, hashlib, time, textwrap
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

try:
    from bs4 import BeautifulSoup, Tag
    BS_AVAILABLE = True
except ImportError:
    BS_AVAILABLE = False

# ── 软链接到同级模块 ──
HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS_ROOT = os.path.dirname(HERE)

import sys
sys.path.insert(0, HARNESS_ROOT)

from core.hep_protocol import HEPRegistry, HEPComponent, REGISTRY, HEPComposer
from core.harness_composer import HarnessComposer, THEMES, Atoms, Layouts


# ════════════════════════════════════════════════════════════
# 1. 组件类型定义
# ════════════════════════════════════════════════════════════

COMPONENT_TYPES = {
    "nav":      {"label": "导航栏",     "icon": "menu"},
    "hero":     {"label": "主视觉区",   "icon": "layout"},
    "card_grid":{"label": "卡片网格",   "icon": "grid-3x3"},
    "stats":    {"label": "统计数据",   "icon": "bar-chart-3"},
    "pipeline": {"label": "流程管线",   "icon": "arrow-right-left"},
    "footer":   {"label": "页脚",       "icon": "chevron-down"},
    "cta":      {"label": "行动号召",   "icon": "pointer"},
    "testimonials":{"label": "用户评价","icon": "message-square-quote"},
    "faq":      {"label": "常见问题",   "icon": "circle-help"},
    "pricing":  {"label": "定价表",     "icon": "credit-card"},
    "gallery":  {"label": "展示画廊",   "icon": "images"},
    "contact":  {"label": "联系表单",   "icon": "mail"},
    "logo_cloud":{"label":"客户Logo",   "icon": "building-2"},
    "custom":   {"label": "自定义区块", "icon": "puzzle"},
}


@dataclass
class DetectedComponent:
    """从网页中检测到的一个组件"""
    type: str                          # nav / hero / card_grid / stats / pipeline / footer / ...
    name: str                          # 人类可读名称
    html: str                          # 原始 HTML 片段
    text_content: Dict[str, str]       # 提取的文本内容 {placeholder: value}
    design_tokens: Dict[str, str]      # 提取的设计令牌 {property: value}
    parameters: List[str]              # 可参数化的字段名
    template: str = ""                 # 参数化后的模板 ({{placeholder}})
    confidence: float = 0.0            # 检测置信度
    element_index: int = 0             # 在原始 HTML 中的位置


@dataclass
class DecompileResult:
    """一次反编译的完整结果"""
    url: str
    domain: str
    title: str
    description: str
    tech_stack: List[str]
    components: List[DetectedComponent]
    page_theme: Dict[str, str]
    full_spec: Dict                       # HarnessComposer 兼容的 Spec JSON
    hep_ids: List[str]                    # 已注册的 HEP 组件 ID
    errors: List[str] = field(default_factory=list)
    decompile_time_ms: float = 0.0
    pages_analyzed: int = 0


# ════════════════════════════════════════════════════════════
# 2. 设计令牌提取器
# ════════════════════════════════════════════════════════════

class DesignTokenExtractor:
    """从 HTML/CSS 中提取设计令牌 — 零 token"""
    
    # CSS 颜色属性映射
    COLOR_PROPS = {
        'color': 'text',
        'background-color': 'bg', 'background': 'bg',
        'border-color': 'border', 'outline-color': 'border',
        'accent-color': 'accent',
    }
    
    # 常见品牌色启发式
    BRAND_COLOR_PATTERNS = [
        r'#[0-9a-fA-F]{6}',           # #RRGGBB
        r'#[0-9a-fA-F]{3}',           # #RGB
        r'rgb\(\d+,\s*\d+,\s*\d+\)',  # rgb(r,g,b)
        r'hsl\(\d+',                   # hsl(h, ...)
    ]
    
    @classmethod
    def extract_from_html(cls, html: str) -> Dict[str, Any]:
        """从 HTML 中提取全面设计令牌"""
        if not BS_AVAILABLE:
            return cls._fallback_extract(html)
        
        soup = BeautifulSoup(html, 'html.parser')
        tokens = {
            'colors': {'bg': [], 'text': [], 'accent': [], 'border': [], 'other': []},
            'typography': {'families': [], 'sizes': [], 'weights': []},
            'spacing': {'padding': [], 'margin': [], 'gap': []},
            'borders': {'radius': [], 'width': [], 'style': []},
            'shadows': [],
            'theme': {},
        }
        
        # 1. 从 <style> 和 inline style 中提取
        style_tags = soup.find_all('style')
        inline_styles = soup.find_all(style=True)
        all_css = []
        
        for tag in style_tags:
            all_css.append(tag.get_text())
        for el in inline_styles:
            all_css.append(el.get('style', ''))
        
        css_text = '\n'.join(all_css)
        
        # 颜色
        for prop, category in cls.COLOR_PROPS.items():
            matches = re.findall(rf'{prop}\s*:\s*(#[0-9a-fA-F]{{3,8}}|rgba?\([^)]+\)|hsla?\([^)]+\))', css_text, re.IGNORECASE)
            tokens['colors'][category].extend(matches[:5])
        
        # 额外的颜色提取 (all #hex in CSS)
        hex_colors = re.findall(r'(#[0-9a-fA-F]{6})', css_text)
        rgb_colors = re.findall(r'rgba?\([^)]+\)', css_text)
        tokens['colors']['other'] = list(set(hex_colors + rgb_colors))[:20]
        
        # 字体
        families = re.findall(r'font-family\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['typography']['families'] = list(set(f.strip().strip("'\"") for f in families))[:5]
        
        sizes = re.findall(r'font-size\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['typography']['sizes'] = [s.strip() for s in sizes[:5]]
        
        weights = re.findall(r'font-weight\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['typography']['weights'] = [w.strip() for w in weights[:5]]
        
        # 间距
        padding = re.findall(r'padding[^;]*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['spacing']['padding'] = [p.strip() for p in padding[:5]]
        
        margin = re.findall(r'margin[^;]*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['spacing']['margin'] = [m.strip() for m in margin[:5]]
        
        gap = re.findall(r'gap\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['spacing']['gap'] = [g.strip() for g in gap[:3]]
        
        # 边框
        radius = re.findall(r'border-radius\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['borders']['radius'] = [r.strip() for r in radius[:5]]
        
        border_w = re.findall(r'border(?:-width)?\s*:\s*(\d+px)', css_text, re.IGNORECASE)
        tokens['borders']['width'] = [b.strip() for b in border_w[:3]]
        
        # 阴影
        shadows = re.findall(r'(box-shadow|text-shadow)\s*:\s*([^;]+)', css_text, re.IGNORECASE)
        tokens['shadows'] = [s[1].strip() for s in shadows[:5]]
        
        # 2. 推断主题匹配
        tokens['theme'] = cls._infer_theme(tokens['colors'])
        
        # 去重
        for cat in tokens['colors']:
            tokens['colors'][cat] = list(set(tokens['colors'][cat]))
        for cat in ['padding', 'margin', 'gap']:
            tokens['spacing'][cat] = list(set(tokens['spacing'][cat]))
        tokens['borders']['radius'] = list(set(tokens['borders']['radius']))
        
        return tokens
    
    @classmethod
    def _fallback_extract(cls, html: str) -> Dict[str, Any]:
        """无 BeautifulSoup 时的兜底提取"""
        tokens = {'colors': {'bg': [], 'text': [], 'accent': [], 'border': [], 'other': []},
                   'typography': {'families': [], 'sizes': [], 'weights': []},
                   'spacing': {'padding': [], 'margin': [], 'gap': []},
                   'borders': {'radius': [], 'width': [], 'style': []},
                   'shadows': [], 'theme': {}}
        hex_colors = re.findall(r'(#[0-9a-fA-F]{6})', html)
        tokens['colors']['other'] = list(set(hex_colors))[:10]
        families = re.findall(r'font-family[^:]*:\s*([^;{]+)', html, re.IGNORECASE)
        tokens['typography']['families'] = list(set(f.strip().strip("'\"") for f in families))[:3]
        tokens['theme'] = cls._infer_theme(tokens['colors'])
        return tokens
    
    @classmethod
    def _infer_theme(cls, colors: Dict) -> Dict[str, str]:
        """从颜色推断 Harness 主题匹配"""
        all_colors = []
        for cat, vals in colors.items():
            all_colors.extend(vals)
        
        # 检查是否深色模式 (多数颜色亮度 < 128)
        dark_count = 0
        for c in all_colors:
            if c.startswith('#'):
                try:
                    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
                    if (r + g + b) / 3 < 128:
                        dark_count += 1
                except:
                    pass
        
        is_dark = dark_count > len(all_colors) / 2 if all_colors else True
        
        # 检测是否紫色系 (LAAP 风格)
        purple_count = sum(1 for c in all_colors if '7c7c' in c.lower() or 'purple' in c.lower())
        blue_count = sum(1 for c in all_colors if 'blue' in c.lower() or '00d4' in c.lower())
        
        if purple_count > 2:
            return {"base": "apple_dark" if is_dark else "apple_light", "palette": "purple"}
        elif blue_count > 2:
            return {"base": "dark_tech" if is_dark else "apple_light", "palette": "blue"}
        
        return {"base": "apple_dark" if is_dark else "apple_light", "palette": "neutral"}


# ════════════════════════════════════════════════════════════
# 3. HTML 组件检测器
# ════════════════════════════════════════════════════════════

class HTMLComponentDetector:
    """从 HTML 中检测 Harness 兼容的组件 — 零 token"""
    
    def __init__(self):
        self.token_extractor = DesignTokenExtractor()
    
    def detect_all(self, html: str, url: str = "") -> List[DetectedComponent]:
        """检测 HTML 中所有可识别的组件"""
        if not BS_AVAILABLE:
            return self._detect_regex(html)
        
        soup = BeautifulSoup(html, 'html.parser')
        components = []
        index = 0
        
        # 检测导航
        nav = self._detect_nav(soup)
        if nav:
            nav.element_index = index
            components.append(nav)
            index += 1
        
        # 检测 Hero
        hero = self._detect_hero(soup)
        if hero:
            hero.element_index = index
            components.append(hero)
            index += 1
        
        # 检测 CTA 区块
        cta = self._detect_cta(soup)
        if cta:
            cta.element_index = index
            components.append(cta)
            index += 1
        
        # 检测 Stats 区块
        stats = self._detect_stats(soup)
        if stats:
            stats.element_index = index
            components.append(stats)
            index += 1
        
        # 检测 Card Grid
        cards = self._detect_card_grid(soup)
        if cards:
            cards.element_index = index
            components.append(cards)
            index += 1
        
        # 检测 Pipeline
        pipe = self._detect_pipeline(soup)
        if pipe:
            pipe.element_index = index
            components.append(pipe)
            index += 1
        
        # 检测 Footer
        footer = self._detect_footer(soup)
        if footer:
            footer.element_index = index
            components.append(footer)
            index += 1
        
        # 检测 Testimonials
        testimonials = self._detect_testimonials(soup)
        if testimonials:
            testimonials.element_index = index
            components.append(testimonials)
            index += 1
        
        # 检测 Pricing
        pricing = self._detect_pricing(soup)
        if pricing:
            pricing.element_index = index
            components.append(pricing)
            index += 1
        
        # 检测剩余 sections 为 custom
        customs = self._detect_custom_sections(soup, components)
        for c in customs:
            c.element_index = index
            components.append(c)
            index += 1
        
        return components
    
    # ── 导航检测 ──
    def _detect_nav(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        nav_tag = soup.find('nav') or soup.find('header', class_=re.compile(r'nav', re.I))
        if not nav_tag:
            # 尝试找 fixed 定位的顶栏
            for el in soup.find_all(['div', 'header'], style=re.compile(r'fixed|sticky', re.I)):
                nav_tag = el
                break
        if not nav_tag:
            return None
        
        html = str(nav_tag)
        links = nav_tag.find_all('a')
        brand = nav_tag.find(['span', 'div', 'a'], class_=re.compile(r'logo|brand', re.I))
        
        text_content = {
            'brand': brand.get_text(strip=True)[:30] if brand else 'Brand',
        }
        for i, link in enumerate(links[:6]):
            text_content[f'link_{i}_text'] = link.get_text(strip=True)
            text_content[f'link_{i}_href'] = link.get('href', '#')
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='nav', name='导航栏', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.8
        )
    
    # ── Hero 检测 ──
    def _detect_hero(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        # 策略: 找首屏大标题区块
        candidates = []
        
        # 1. 查找 hero 类名
        for el in soup.find_all(class_=re.compile(r'hero|banner|landing', re.I)):
            candidates.append(el)
        
        # 2. 查找全屏 section 或 div 包含 h1
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                h1 = el.find('h1')
                if h1 and el.get('style', '') or any(c in (el.get('class', []) or []) for c in ['hero', 'banner']):
                    candidates.append(el)
                    break
        
        # 3. 找第一个大的 h1
        if not candidates:
            h1 = soup.find('h1')
            if h1:
                parent = h1.find_parent(['section', 'div', 'header'])
                if parent:
                    candidates.append(parent)
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        
        h1 = el.find('h1')
        h2 = el.find('h2')
        p = el.find('p')
        badge = el.find(class_=re.compile(r'badge|tag|chip', re.I))
        cta_btns = el.find_all(['a', 'button'], class_=re.compile(r'cta|btn|button|primary', re.I))
        
        text_content = {
            'title': h1.get_text(strip=True)[:80] if h1 else 'Hero Title',
            'subtitle': h2.get_text(strip=True)[:120] if h2 else (p.get_text(strip=True)[:120] if p else ''),
            'badge': badge.get_text(strip=True)[:40] if badge else '',
        }
        text_content['cta_primary'] = cta_btns[0].get_text(strip=True)[:30] if cta_btns else 'Get Started'
        text_content['cta_primary_url'] = cta_btns[0].get('href', '#') if cta_btns else '#'
        if len(cta_btns) > 1:
            text_content['cta_secondary'] = cta_btns[1].get_text(strip=True)[:30]
            text_content['cta_secondary_url'] = cta_btns[1].get('href', '#')
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='hero', name='主视觉区', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.85
        )
    
    # ── CTA 检测 ──
    def _detect_cta(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'cta|action|call.?to.?action', re.I)):
            candidates.append(el)
        for el in soup.find_all(['section', 'div']):
            btns = el.find_all(['a', 'button'], class_=re.compile(r'cta|primary|btn-large'))
            text = el.get_text(strip=True)
            if len(btns) >= 1 and len(text) < 200:
                candidates.append(el)
                break
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        btns = el.find_all(['a', 'button'])
        text_content = {}
        for i, btn in enumerate(btns[:2]):
            text_content[f'cta_{i}_text'] = btn.get_text(strip=True)[:30]
            text_content[f'cta_{i}_url'] = btn.get('href', '#')
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='cta', name='行动号召', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.7
        )
    
    # ── 统计检测 ──
    def _detect_stats(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'stat|number|count|metric', re.I)):
            candidates.append(el)
        
        # 找包含多个数字的 section
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                nums = el.find_all(['span', 'div', 'h3'], string=re.compile(r'^\d+[kKMB%]?$'))
                if len(nums) >= 2:
                    candidates.append(el)
                    break
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        items = el.find_all(class_=re.compile(r'stat|number|count|metric|item', re.I)) or el.find_all(['div', 'span'], recursive=False)
        
        text_content = {}
        for i, item in enumerate(items[:8]):
            num_el = item.find(class_=re.compile(r'num|number|count|value')) or item
            lab_el = item.find(class_=re.compile(r'label|desc|text')) or item
            num = num_el.get_text(strip=True)[:20]
            lab = lab_el.get_text(strip=True)[:30]
            if num and lab:
                text_content[f'stat_{i}_number'] = num
                text_content[f'stat_{i}_label'] = lab
            elif num:
                text_content[f'stat_{i}_number'] = num
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='stats', name='统计数据', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.75
        )
    
    # ── 卡片网格检测 ──
    def _detect_card_grid(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'grid|card.?wrapper|card.?container', re.I)):
            cards = el.find_all(class_=re.compile(r'card|item|tile'), recursive=False)
            if len(cards) >= 2:
                candidates.append((el, cards))
        
        # 找包含 2+ 个 card 类元素的容器
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                cards = el.find_all(class_=re.compile(r'card|item|feature|service|product', re.I))
                if len(cards) >= 2:
                    candidates.append((el, cards))
                    break
        
        if not candidates:
            return None
        
        el, cards = candidates[0]
        html = str(el)
        text_content = {}
        
        # section 标题
        title_el = el.find(['h1', 'h2', 'h3'], class_=re.compile(r'title|heading'))
        label_el = el.find(['span', 'p'], class_=re.compile(r'label|tag|badge'))
        text_content['section_label'] = label_el.get_text(strip=True)[:40] if label_el else ''
        text_content['section_title'] = title_el.get_text(strip=True)[:60] if title_el else ''
        
        for i, card in enumerate(cards[:6]):
            c_title = card.find(['h1', 'h2', 'h3', 'h4', 'strong'])
            c_desc = card.find('p')
            text_content[f'card_{i}_title'] = c_title.get_text(strip=True)[:40] if c_title else f'Card {i+1}'
            text_content[f'card_{i}_desc'] = c_desc.get_text(strip=True)[:80] if c_desc else ''
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='card_grid', name='卡片网格', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.8
        )
    
    # ── 管线检测 ──
    def _detect_pipeline(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'pipeline|steps|process|workflow|timeline', re.I)):
            candidates.append(el)
        
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                items = el.find_all(class_=re.compile(r'step|phase|stage|milestone'), recursive=False)
                if len(items) >= 2 and len(items) <= 8:
                    candidates.append(el)
                    break
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        items = el.find_all(class_=re.compile(r'step|phase|stage|item'), recursive=False) or el.find_all(['div', 'li'], recursive=False)
        
        text_content = {}
        for i, item in enumerate(items[:6]):
            text = item.get_text(strip=True)[:50]
            if text:
                text_content[f'step_{i}'] = text
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='pipeline', name='流程管线', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.7
        )
    
    # ── 页脚检测 ──
    def _detect_footer(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        footer = soup.find('footer')
        if not footer:
            # 找含 copyright 的最后一个 div/section
            for el in reversed(soup.find_all(['div', 'section'])):
                if re.search(r'copyright|©|all rights reserved', el.get_text(), re.I):
                    footer = el
                    break
        
        if not footer:
            return None
        
        html = str(footer)
        links = footer.find_all('a')
        text_content = {}
        for i, link in enumerate(links[:8]):
            text_content[f'link_{i}_text'] = link.get_text(strip=True)[:25] or link.get('href', '#')[:25]
        
        copyright_el = footer.find(string=re.compile(r'©|copyright', re.I))
        if copyright_el:
            text_content['copyright'] = copyright_el.strip()[:60]
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='footer', name='页脚', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.75
        )
    
    # ── 评价检测 ──
    def _detect_testimonials(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'testimonial|review|quote|feedback', re.I)):
            candidates.append(el)
        
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                quotes = el.find_all(['blockquote', 'q']) or el.find_all(class_=re.compile(r'quote|comment'))
                if len(quotes) >= 2:
                    candidates.append(el)
                    break
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        quotes = el.find_all(['blockquote', 'q']) or el.find_all(class_=re.compile(r'quote|text|content'))
        
        text_content = {}
        for i, q in enumerate(quotes[:4]):
            text_content[f'quote_{i}_text'] = q.get_text(strip=True)[:120]
            author = q.find_next(class_=re.compile(r'author|name|user|by')) or q.find_next('cite')
            if author:
                text_content[f'quote_{i}_author'] = author.get_text(strip=True)[:30]
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='testimonials', name='用户评价', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.7
        )
    
    # ── 定价表检测 ──
    def _detect_pricing(self, soup: BeautifulSoup) -> Optional[DetectedComponent]:
        candidates = []
        for el in soup.find_all(class_=re.compile(r'pricing|plan|price|package', re.I)):
            candidates.append(el)
        
        if not candidates:
            for el in soup.find_all(['section', 'div']):
                prices = el.find_all(string=re.compile(r'[\$¥€]\d+'))
                if len(prices) >= 2:
                    candidates.append(el)
                    break
        
        if not candidates:
            return None
        
        el = candidates[0]
        html = str(el)
        cards = el.find_all(class_=re.compile(r'plan|card|tier|package'), recursive=False) or el.find_all(['div', 'article'], recursive=False)[:4]
        
        text_content = {}
        for i, card in enumerate(cards[:4]):
            name = card.find(['h3', 'h4', 'strong'])
            price = card.find(class_=re.compile(r'price|amount|cost')) or card.find(string=re.compile(r'[\$¥€]\d+'))
            text_content[f'plan_{i}_name'] = name.get_text(strip=True)[:30] if name else f'Plan {i+1}'
            if price:
                text_content[f'plan_{i}_price'] = price.strip()[:20] if isinstance(price, str) else price.get_text(strip=True)[:20]
        
        params = list(text_content.keys())
        template = self._parameterize_html(html, text_content)
        tokens = self.token_extractor.extract_from_html(html)
        
        return DetectedComponent(
            type='pricing', name='定价表', html=html,
            text_content=text_content, design_tokens=tokens,
            parameters=params, template=template, confidence=0.7
        )
    
    # ── 自定义段落检测 (兜底) ──
    def _detect_custom_sections(self, soup: BeautifulSoup, existing: List[DetectedComponent]) -> List[DetectedComponent]:
        """检测未被上述检测器覆盖的主要段落"""
        customs = []
        
        # 收集已检测元素的 HTML 签名
        existing_htmls = set()
        for c in existing:
            existing_htmls.add(self._normalize_html(c.html[:200]))
        
        # 找所有 section 和大的 div
        sections = soup.find_all(['section', 'div'])
        for el in sections:
            html_sig = self._normalize_html(str(el)[:200])
            if html_sig in existing_htmls:
                continue
            
            text = el.get_text(strip=True)
            if len(text) < 50:
                continue
            
            # 跳过导航/页脚已检测的部分
            is_existing = False
            for c in existing:
                if html_sig in self._normalize_html(c.html[:200]) or self._normalize_html(c.html[:200]) in html_sig:
                    is_existing = True
                    break
            if is_existing:
                continue
            
            # 检查是否为有意义的区块
            headings = el.find_all(['h1', 'h2', 'h3', 'h4'])
            if not headings:
                continue
            
            html = str(el)
            text_content = {}
            for h in headings[:3]:
                text_content[h.name] = h.get_text(strip=True)[:60]
            
            params = list(text_content.keys())
            template = self._parameterize_html(html, text_content)
            tokens = self.token_extractor.extract_from_html(html)
            
            customs.append(DetectedComponent(
                type='custom', name=headings[0].get_text(strip=True)[:30],
                html=html, text_content=text_content, design_tokens=tokens,
                parameters=params, template=template, confidence=0.5
            ))
        
        return customs
    
    # ── 辅助方法 ──
    def _parameterize_html(self, html: str, text_content: Dict[str, str]) -> str:
        """把 HTML 中的文本内容替换为 {{placeholder}}"""
        result = html
        # 先替换长文本再替换短文本, 避免冲突
        sorted_items = sorted(text_content.items(), key=lambda x: -len(x[1]))
        for key, val in sorted_items:
            if val and len(val) >= 2:
                result = result.replace(val, f'{{{{{key}}}}}')
        return result
    
    def _normalize_html(self, html: str) -> str:
        """HTML 标准化比较"""
        # 移除 class/style/whitespace 差异
        return re.sub(r'\s+', ' ', html).strip()[:100]
    
    def _detect_regex(self, html: str) -> List[DetectedComponent]:
        """无 BeautifulSoup 时的正则检测 (降级)"""
        components = []
        
        # Nav
        nav_match = re.search(r'<nav[^>]*>.*?</nav>', html, re.DOTALL | re.IGNORECASE)
        if nav_match:
            components.append(DetectedComponent(
                type='nav', name='导航栏', html=nav_match.group(0),
                text_content={}, design_tokens={}, parameters=[], template=nav_match.group(0),
                confidence=0.5
            ))
        
        # Footer
        foot_match = re.search(r'<footer[^>]*>.*?</footer>', html, re.DOTALL | re.IGNORECASE)
        if foot_match:
            components.append(DetectedComponent(
                type='footer', name='页脚', html=foot_match.group(0),
                text_content={}, design_tokens={}, parameters=[], template=foot_match.group(0),
                confidence=0.5
            ))
        
        return components


# ════════════════════════════════════════════════════════════
# 4. Spec 生成器 (反编译 → HarnessComposer Spec)
# ════════════════════════════════════════════════════════════

class SpecGenerator:
    """把检测到的组件编译为 HarnessComposer 兼容的 JSON Spec"""
    
    TYPE_MAP = {
        'nav': 'nav_spec',
        'hero': 'hero_spec',
        'card_grid': 'grid_spec',
        'stats': 'stats_spec',
        'pipeline': 'pipeline_spec',
        'footer': 'footer_spec',
        'cta': 'hero_spec',
        'testimonials': 'grid_spec',
        'pricing': 'grid_spec',
        'custom': 'custom_html',
    }
    
    @staticmethod
    def to_composer_spec(components: List[DetectedComponent],
                          title: str = "", theme: str = "apple_dark") -> Dict:
        """生成 HarnessComposer.from_spec 兼容的 JSON"""
        spec = {
            "title": title or "Decompiled Site",
            "theme": theme,
            "sections": [],
        }
        
        # Nav
        navs = [c for c in components if c.type == 'nav']
        if navs:
            n = navs[0]
            links = []
            for i in range(6):
                l_text = n.text_content.get(f'link_{i}_text', '')
                l_url = n.text_content.get(f'link_{i}_href', '#')
                if l_text:
                    links.append({"label": l_text, "url": l_url})
            if links:
                spec["nav"] = {
                    "brand": n.text_content.get('brand', 'Brand'),
                    "links": links,
                }
        
        # Sections (ordered by element_index)
        sorted_comps = sorted(components, key=lambda c: c.element_index)
        
        for c in sorted_comps:
            if c.type == 'nav':
                continue  # handled above
            
            section = SpecGenerator._component_to_section(c)
            if section:
                spec["sections"].append(section)
        
        return spec
    
    @staticmethod
    def _component_to_section(c: DetectedComponent) -> Optional[Dict]:
        """单个组件 → section dict"""
        t = c.type
        
        if t == 'hero':
            return {
                "type": "hero",
                "title": c.text_content.get('title', 'Hero Title'),
                "subtitle": c.text_content.get('subtitle', ''),
                "badge": c.text_content.get('badge', ''),
                "cta": c.text_content.get('cta_primary', ''),
                "cta_url": c.text_content.get('cta_primary_url', '#'),
            }
        
        if t == 'card_grid':
            cards = []
            for i in range(6):
                title = c.text_content.get(f'card_{i}_title', '')
                desc = c.text_content.get(f'card_{i}_desc', '')
                if title:
                    cards.append({"title": title, "desc": desc})
            if not cards:
                return None
            return {
                "type": "grid",
                "label": c.text_content.get('section_label', ''),
                "title": c.text_content.get('section_title', ''),
                "cards": cards,
                "cols": min(len(cards), 3),
            }
        
        if t == 'stats':
            items = []
            for i in range(8):
                num = c.text_content.get(f'stat_{i}_number', '')
                lab = c.text_content.get(f'stat_{i}_label', '')
                if num:
                    items.append({"number": num, "label": lab or num})
            if not items:
                return None
            return {
                "type": "stats",
                "items": items,
            }
        
        if t == 'pipeline':
            items = []
            for i in range(6):
                step = c.text_content.get(f'step_{i}', '')
                if step:
                    items.append({"icon": "circle", "label": step})
            if not items:
                return None
            return {
                "type": "pipeline",
                "title": c.name,
                "items": items,
            }
        
        if t == 'cta':
            return {
                "type": "hero",
                "title": c.text_content.get('cta_0_text', 'Get Started'),
                "subtitle": "",
                "cta": c.text_content.get('cta_0_text', ''),
            }
        
        if t == 'testimonials':
            return {
                "type": "grid",
                "label": "Testimonials",
                "title": "What Users Say",
                "cols": 2,
                "cards": [
                    {"title": c.text_content.get(f'quote_{i}_text', '')[:40],
                     "desc": c.text_content.get(f'quote_{i}_author', '')}
                    for i in range(4) if c.text_content.get(f'quote_{i}_text', '')
                ],
            }
        
        if t == 'pricing':
            cards = []
            for i in range(4):
                name = c.text_content.get(f'plan_{i}_name', '')
                price = c.text_content.get(f'plan_{i}_price', '')
                if name:
                    cards.append({"title": name, "desc": price})
            return {
                "type": "grid",
                "label": "Pricing",
                "title": "Choose Your Plan",
                "cols": min(len(cards), 4),
                "cards": cards,
            } if cards else None
        
        if t == 'custom':
            return {
                "type": "custom_html",
                "html": c.template or c.html,
            }
        
        if t == 'footer':
            return {
                "type": "custom_html",
                "html": c.template or c.html,
            }
        
        return None


# ════════════════════════════════════════════════════════════
# 5. HEP 注册器 (检测结果 → HEP 组件注册)
# ════════════════════════════════════════════════════════════

class HEPRegistrar:
    """把反编译的组件注册到 HEP 注册表"""
    
    def __init__(self, registry: Optional[HEPRegistry] = None):
        self.registry = registry or REGISTRY
        self.registered_ids = []
    
    def register_component(self, c: DetectedComponent, source_url: str = "") -> str:
        """注册一个反编译组件到 HEP 注册表"""
        domain = "ui" if c.type in ('nav', 'hero', 'card_grid', 'stats', 'footer', 'cta',
                                      'testimonials', 'pricing', 'pipeline', 'gallery', 'custom') else "backend"
        
        safe_name = re.sub(r'[^a-z0-9]', '_', c.name.lower())[:30]
        comp_id = f"decompiled.{safe_name}"
        
        # 检查是否已存在 (去重)
        existing = self.registry.get(comp_id)
        if existing:
            return comp_id  # 已注册, 跳过
        
        inputs = {}
        for p in c.parameters:
            inputs[p] = {"type": "string", "description": f"参数: {p}"}
        
        comp = HEPComponent(
            id=comp_id,
            name=f"反编译: {c.name}",
            version="1.0.0",
            domain=domain,
            subdomain="decompiled",
            tags=["decompiled", c.type, "auto-extracted"],
            inputs=inputs,
            outputs={"index.html": "html"},
            dependencies=[],
            template=c.template or c.html,
            author="harness-decompiler",
            url=source_url,
            description=f"从 {source_url} 反编译的 {c.name} ({c.type})",
        )
        
        self.registry.register(comp)
        self.registered_ids.append(comp_id)
        return comp_id
    
    def register_page_spec(self, result: DecompileResult, spec: Dict) -> Optional[str]:
        """把整个页面 Spec 注册为一个 HEP 组件"""
        domain = urlparse(result.url).netloc.replace('.', '_') if result.url else "unknown"
        comp_id = f"page.{domain[:40]}"
        
        existing = self.registry.get(comp_id)
        if existing:
            return comp_id
        
        comp = HEPComponent(
            id=comp_id,
            name=f"页面: {result.title[:40] or domain}",
            version="1.0.0",
            domain="ui",
            subdomain="page",
            tags=["page", "decompiled", result.tech_stack[0].lower() if result.tech_stack else "unknown"],
            inputs={"theme": {"type": "string", "default": "apple_dark"}},
            outputs={"index.html": "html"},
            dependencies=result.hep_ids,
            template=json.dumps(spec, indent=2, ensure_ascii=False),
            author="harness-decompiler",
            url=result.url,
            description=f"完整页面: {result.title} ({result.url})",
        )
        
        self.registry.register(comp)
        self.registered_ids.append(comp_id)
        return comp_id
    
    def get_summary(self) -> Dict:
        return {
            "registered": len(self.registered_ids),
            "ids": self.registered_ids,
        }


# ════════════════════════════════════════════════════════════
# 6. 主引擎 — WebDecompiler
# ════════════════════════════════════════════════════════════

class WebDecompiler:
    """网页反编译引擎 — 爬取 → 分析 → HEP 组件
    
    完整管线:
      decompile(url) → 爬取网页 → 检测组件 → 提取令牌 → 生成 Spec → 注册 HEP
    
    全部零 token, 纯 Python 字符串操作 + HTML 解析。
    <500ms 全流程 (不含网络爬取时间)
    """
    
    def __init__(self):
        self.detector = HTMLComponentDetector()
        self.registrar = HEPRegistrar()
        self.spec_gen = SpecGenerator()
        self.composer = HarnessComposer()
        
        # 尝试导入 WebCrawler
        self.crawler = None
        try:
            from core.web_crawler import WebCrawler
            self.crawler_class = WebCrawler
        except ImportError:
            self.crawler_class = None
    
    def decompile(self, url: str, use_playwright: bool = False, 
                  auto_register: bool = True, auto_spec: bool = True) -> DecompileResult:
        """完整反编译管线
        
        Args:
            url: 目标网页 URL
            use_playwright: 是否用 Playwright (动态页面)
            auto_register: 是否自动注册 HEP 组件
            auto_spec: 是否自动生成 Composer Spec
            
        Returns:
            DecompileResult 包含所有检测结果
        """
        t0 = time.time()
        result = DecompileResult(url=url, domain="", title="", description="",
                                  tech_stack=[], components=[], page_theme={},
                                  full_spec={}, hep_ids=[])
        
        # ── Phase 1: 爬取 ──
        try:
            if self.crawler_class:
                import asyncio
                crawler = self.crawler_class(max_pages=3)
                crawl_result = asyncio.run(crawler.crawl_and_analyze(url, use_playwright))
                
                if not crawl_result.success:
                    result.errors.append(f"爬取失败")
                else:
                    result.title = crawl_result.website.title
                    result.description = crawl_result.website.description
                    result.tech_stack = crawl_result.website.tech_stack
                    result.domain = crawl_result.website.domain
                    result.pages_analyzed = crawl_result.pages_crawled
                    
                    # 拼接所有页面 HTML
                    combined_html = ""
                    for page in crawl_result.pages:
                        combined_html += page.html + "\n"
                    
                    # ── Phase 2: 检测组件 ──
                    result.components = self.detector.detect_all(combined_html, url)
                    
                    # ── Phase 3: 提取页面级设计令牌 ──
                    page_tokens = DesignTokenExtractor.extract_from_html(combined_html)
                    result.page_theme = page_tokens.get('theme', {})
                    
                    # ── Phase 4: 注册 HEP 组件 ──
                    if auto_register:
                        for c in result.components:
                            cid = self.registrar.register_component(c, source_url=url)
                            result.hep_ids.append(cid)
                    
                    # ── Phase 5: 生成 Composer Spec ──
                    if auto_spec:
                        theme = result.page_theme.get('base', 'apple_dark')
                        result.full_spec = self.spec_gen.to_composer_spec(
                            result.components, title=result.title, theme=theme
                        )
                        
                        # 也把整个 Spec 注册为一个页面级 HEP 组件
                        if auto_register:
                            page_cid = self.registrar.register_page_spec(result, result.full_spec)
                            result.hep_ids.append(page_cid)
            else:
                # 降级: 直接爬取 HTML (requests)
                combined_html = self._fetch_html(url)
                if combined_html:
                    result.components = self.detector.detect_all(combined_html, url)
                    page_tokens = DesignTokenExtractor.extract_from_html(combined_html)
                    result.page_theme = page_tokens.get('theme', {})
                    
                    if auto_register:
                        for c in result.components:
                            cid = self.registrar.register_component(c, source_url=url)
                            result.hep_ids.append(cid)
                    
                    if auto_spec:
                        theme = result.page_theme.get('base', 'apple_dark')
                        result.full_spec = self.spec_gen.to_composer_spec(
                            result.components, title=result.title, theme=theme
                        )
        
        except Exception as e:
            result.errors.append(f"反编译异常: {e}")
        
        result.decompile_time_ms = (time.time() - t0) * 1000
        return result
    
    def decompile_from_html(self, html: str, source_url: str = "",
                             auto_register: bool = True) -> DecompileResult:
        """从原始 HTML 反编译 (跳过爬取阶段)"""
        t0 = time.time()
        result = DecompileResult(url=source_url, domain="", title="", description="",
                                  tech_stack=[], components=[], page_theme={},
                                  full_spec={}, hep_ids=[])
        
        # 提取标题
        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
        result.title = title_m.group(1).strip() if title_m else ""
        
        desc_m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html, re.IGNORECASE)
        result.description = desc_m.group(1) if desc_m else ""
        
        result.components = self.detector.detect_all(html, source_url)
        page_tokens = DesignTokenExtractor.extract_from_html(html)
        result.page_theme = page_tokens.get('theme', {})
        
        if auto_register:
            for c in result.components:
                cid = self.registrar.register_component(c, source_url=source_url)
                result.hep_ids.append(cid)
        
        theme = result.page_theme.get('base', 'apple_dark')
        result.full_spec = self.spec_gen.to_composer_spec(
            result.components, title=result.title, theme=theme
        )
        
        result.decompile_time_ms = (time.time() - t0) * 1000
        return result
    
    def _fetch_html(self, url: str) -> str:
        """简单 HTTP 获取 HTML"""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='replace')
                # 提取域名和标题
                result = urlparse(url)
                return html
        except Exception as e:
            return ""
    
    def generate_page(self, spec: Dict = None) -> str:
        """生成一个完整页面 (用 HarnessComposer)"""
        if spec:
            return self.composer.from_spec(spec)
        return ""
    
    def summary(self, result: DecompileResult) -> str:
        """生成人类可读的反编译报告"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"  网页反编译报告")
        lines.append(f"  URL: {result.url}")
        lines.append("=" * 60)
        
        lines.append(f"\n  标题: {result.title or '(none)'}")
        lines.append(f"  技术栈: {', '.join(result.tech_stack) or '未检测'}")
        lines.append(f"  耗时: {result.decompile_time_ms:.1f} ms")
        
        lines.append(f"\n  检测到 {len(result.components)} 个组件:")
        for c in result.components:
            lines.append(f"    [{c.type:12s}] {c.name:25s} | {len(c.parameters)} params | conf={c.confidence:.0%}")
        
        if result.full_spec:
            sec_count = len(result.full_spec.get('sections', []))
            lines.append(f"\n  Spec 生成: {sec_count} 个区块, 可立即用 HarnessComposer 装配")
        
        if result.hep_ids:
            lines.append(f"\n  HEP 注册: {len(result.hep_ids)} 个组件")
            for hid in result.hep_ids[:5]:
                lines.append(f"    - {hid}")
        
        if result.errors:
            lines.append(f"\n  异常: {len(result.errors)} 个")
            for e in result.errors[:3]:
                lines.append(f"    ! {e}")
        
        lines.append("\n" + "=" * 60)
        return '\n'.join(lines)


# ════════════════════════════════════════════════════════════
# 7. 测试 / CLI
# ════════════════════════════════════════════════════════════

def test_decompiler():
    """用内置 HTML 测试反编译器"""
    print("=" * 60)
    print("  Harness Web Decompiler v1.0 — 测试")
    print("=" * 60)
    
    # 构造一个测试用 HTML
    test_html = """<!DOCTYPE html>
<html>
<head><title>LAAP Test Page</title>
<style>
  :root { --bg: #000; --text: #fff; --accent: #7c7cff; }
  body { font-family: Inter, sans-serif; background: var(--bg); color: var(--text); }
  .hero { min-height: 100vh; display: flex; align-items: center; justify-content: center; text-align: center; }
  .grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; padding: 80px 40px; }
  .card { padding: 24px; border-radius: 12px; background: rgba(255,255,255,0.03); }
  .stat { text-align: center; padding: 40px; }
  .stat-number { font-size: 48px; color: var(--accent); }
</style>
</head>
<body>
<nav class="nav" style="position:fixed;top:0;width:100%;backdrop-filter:blur(20px)">
  <div class="brand">LAAP</div>
  <div class="links">
    <a href="#features">Features</a>
    <a href="#pricing">Pricing</a>
    <a href="#about">About</a>
  </div>
</nav>

<section class="hero">
  <div class="hero-badge">v2.0</div>
  <h1>LAAP 认知架构</h1>
  <p>25 个引擎模块, 零 LLM 依赖的自主认知系统</p>
  <a href="#features" class="cta-primary">探索架构</a>
  <a href="/api" class="cta-secondary">开始对话</a>
</section>

<section class="stats">
  <div class="stat">
    <div class="stat-number">25</div>
    <div class="stat-label">引擎模块</div>
  </div>
  <div class="stat">
    <div class="stat-number">137k</div>
    <div class="stat-label">代码行数</div>
  </div>
  <div class="stat">
    <div class="stat-number">99%</div>
    <div class="stat-label">语法通过率</div>
  </div>
</section>

<section>
  <h2>核心引擎</h2>
  <div class="grid">
    <div class="card"><h3>PSI-N+ DSpark</h3><p>五层认知心跳</p></div>
    <div class="card"><h3>QRE v3</h3><p>512 维量子推理</p></div>
    <div class="card"><h3>情感引擎</h3><p>11 种情绪</p></div>
  </div>
</section>

<footer>
  <p>由 Lorry 创造 · Aris 数字生命体</p>
  <p>&copy; 2026 LAAP</p>
</footer>
</body>
</html>"""
    
    decompiler = WebDecompiler()
    result = decompiler.decompile_from_html(test_html, "https://laap.test")
    
    print(decompiler.summary(result))
    
    # 显示每个组件的提取详情
    print("\n  组件详情:")
    for c in result.components:
        print(f"\n    [{c.type}] {c.name}")
        print(f"      参数: {c.parameters}")
        print(f"      Token 颜色模式: {c.design_tokens.get('theme', {}).get('base', 'N/A')}")
        if c.text_content:
            for k, v in list(c.text_content.items())[:4]:
                print(f"      {k}: {v[:40]}")
    
    # 验证 Spec 可以被 HarnessComposer 消费
    if result.full_spec:
        print(f"\n  验证 Spec → 重新生成页面...")
        html = decompiler.generate_page(result.full_spec)
        print(f"  生成页面: {len(html):,} bytes")
        print(f"  Spec: {json.dumps(result.full_spec, indent=2, ensure_ascii=False)[:2000]}...")
    
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1].startswith('http'):
        url = sys.argv[1]
        print(f"反编译: {url}")
        decompiler = WebDecompiler()
        result = decompiler.decompile(url, use_playwright='--playwright' in sys.argv)
        print(decompiler.summary(result))
    else:
        test_decompiler()
