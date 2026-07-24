"""
UI Harness — 意图感知引擎
========================
从自然语言中理解用户想要什么样的 UI。

核心能力:
  1. 识别页面类型 (landing/dashboard/blog/auth/ecommerce/...)
  2. 提取风格偏好 (dark/light/modern/minimal/tech/...)
  3. 解析功能需求 (hero/features/pricing/contact/...)
  4. 推断目标受众和品牌调性
  5. 输出结构化需求描述
"""

from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ui_harness.intent")

# ════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════


@dataclass
class IntentResult:
    """意图解析结果。"""
    page_type: str = "landing"           # landing/dashboard/blog/auth/ecommerce/portfolio/docs
    style_tags: List[str] = field(default_factory=list)  # dark, modern, minimal, tech, playful...
    required_sections: List[str] = field(default_factory=list)  # hero, features, pricing, cta...
    tone: str = "professional"           # professional/playful/luxury/minimal/friendly
    target_audience: str = "general"     # developers/consumers/enterprise/creators
    color_hint: Optional[str] = None     # 用户显式提到的颜色
    brand_name: Optional[str] = None     # 品牌名称
    key_content: Dict[str, str] = field(default_factory=dict)  # 关键内容片段
    original_text: str = ""              # 原始输入
    confidence: float = 0.0              # 解析置信度
    raw_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_type": self.page_type,
            "style_tags": self.style_tags,
            "required_sections": self.required_sections,
            "tone": self.tone,
            "target_audience": self.target_audience,
            "color_hint": self.color_hint,
            "brand_name": self.brand_name,
            "key_content": self.key_content,
            "confidence": round(self.confidence, 2),
        }

    def to_prompt(self) -> str:
        """转为LLM可读的简短提示。"""
        sections = ", ".join(self.required_sections) if self.required_sections else "auto"
        styles = ", ".join(self.style_tags) if self.style_tags else "default"
        brand = f" 品牌: {self.brand_name}" if self.brand_name else ""
        color = f" 色调: {self.color_hint}" if self.color_hint else ""
        return (
            f"页面: {self.page_type} | 风格: {styles} | "
            f"区块: {sections} | 调性: {self.tone}{brand}{color}"
        )


# ════════════════════════════════════════════════════════════
# 意图引擎
# ════════════════════════════════════════════════════════════


class IntentEngine:
    """
    意图感知引擎 — 把自然语言变成结构化需求。
    
    用法:
        engine = IntentEngine()
        intent = engine.parse("做一个暗色调的SaaS Landing Page")
        print(intent.to_prompt())
    """

    def __init__(self):
        self._build_patterns()

    def _build_patterns(self):
        """构建所有识别模式。"""

        # ── 页面类型 ──
        self.page_type_patterns = [
            (r"landing\s*page|落地页|首页|主页|推广页|营销页", "landing"),
            (r"dashboard|仪表盘|后台|管理面板|控制台|数据面板", "dashboard"),
            (r"blog|博客|文章|新闻|资讯", "blog"),
            (r"auth|登录|注册|sign.?in|sign.?up|login|register", "auth"),
            (r"ecommerce|商城|电商|店铺|购物|商店|product|产品页", "ecommerce"),
            (r"portfolio|作品集|个人主页|简历|个人品牌", "portfolio"),
            (r"documentation|文档|api docs|开发文档|用户手册", "docs"),
            (r"定价|pricing|价格|套餐|订阅|方案", "pricing_page"),
            (r"about|关于我们|关于|团队|公司介绍", "about"),
            (r"contact|联系|联系我们|联系方式|客服", "contact"),
            (r"saas|SaaS|软件即服务|云服务", "landing"),
        ]

        # ── 风格标签 ──
        self.style_patterns = [
            (r"暗|黑|dark|night|深色", "dark"),
            (r"白|亮|light|bright|clean|明亮", "light"),
            (r"极简|minimal|简洁|干净|少", "minimal"),
            (r"现代|modern|当代|时尚", "modern"),
            (r"科技|tech|futuristic|未来|赛博|cyber", "tech"),
            (r"企业|corporate|business|专业|professional|正式", "corporate"),
            (r"创意|creative|artistic|艺术|独特|大胆", "creative"),
            (r"有趣|playful|fun|活泼|可爱|cute", "playful"),
            (r"奢华|luxury|premium|高端|精致|elegant", "luxury"),
            (r"自然|nature|organic|绿色|环保|earth", "nature"),
            (r"复古|vintage|retro|怀旧|classic", "vintage"),
            (r"毛玻璃|glassmorphism|glass|模糊|透明|frosted", "glassmorphism"),
            (r"3d|三维|粒子|particle|立体|空间", "3d"),
            (r"渐变|gradient|霓虹|neon|发光|glow", "gradient"),
            (r"毛玻璃|glassmorphism|玻璃", "glassmorphism"),
        ]

        # ── 区块需求 ──
        self.section_patterns = [
            (r"hero|主视觉|大标题|首屏|banner|header", "hero"),
            (r"feature|特性|功能|特点|优势|能力|capability", "features"),
            (r"pricing|定价|价格|套餐|价格表|订阅|plan", "pricing"),
            (r"cta|行动号召|按钮|立即|开始|免费试用|sign.?up", "cta"),
            (r"faq|常见问题|问答|问题|疑问|help", "faq"),
            (r"testimonial|评价|客户|用户说|推荐|quote|口碑", "testimonials"),
            (r"footer|页脚|底部|版权|法律", "footer"),
            (r"nav|导航|menu|菜单|顶栏|navbar", "navbar"),
            (r"contact|联系|表单|联系方式|form", "contact_section"),
            (r"about|关于|介绍|故事|使命", "about_section"),
            (r"stats|统计|数据|数字|指标|achievement", "stats"),
            (r"gallery|画廊|作品|展示|portfolio|showcase", "gallery"),
            (r"team|团队|成员|人员|member|people", "team"),
            (r"blog|文章|最新|新闻|post", "blog_section"),
            (r"logo|品牌|客户logo|合作伙伴", "logos"),
        ]

        # ── 色调 ──
        self.color_patterns = [
            (r"(蓝色|蓝|blue|navy|indigo)", "blue"),
            (r"(红色|红|red|crimson|rose)", "red"),
            (r"(绿色|绿|green|emerald|forest)", "green"),
            (r"(紫色|紫|purple|violet)", "purple"),
            (r"(橙色|橙|orange|amber|coral)", "orange"),
            (r"(粉色|粉|pink|magenta)", "pink"),
            (r"(黄色|黄|yellow|gold)", "yellow"),
            (r"(青色|青|cyan|teal|ocean)", "cyan"),
            (r"(灰色|灰|gray|slate|neutral)", "gray"),
            (r"(白|white|浅)", "white"),
            (r"(黑|black|深)", "dark"),
        ]

        # ── 目标受众 ──
        self.audience_patterns = [
            (r"开发者|developer|程序员|engineer|技术|程序员", "developers"),
            (r"企业|enterprise|公司|团队|business|B端", "enterprise"),
            (r"消费者|consumer|用户|c端|普通用户|个人", "consumers"),
            (r"创作者|creator|设计师|designer|艺术家|artist", "creators"),
            (r"初创|startup|创业|小团队|founder", "startups"),
        ]

        # ── 调性 ──
        self.tone_patterns = [
            (r"专业|professional|正式|严谨|权威", "professional"),
            (r"友好|friendly|温暖|亲切|柔和|nice", "friendly"),
            (r"有趣|playful|幽默|fun|活泼|cheerful", "playful"),
            (r"奢华|luxury|高端|premium|精致|优雅", "luxury"),
            (r"极简|minimal|克制|简洁|clean", "minimal"),
            (r"科技|tech|前沿|创新|innovative", "tech"),
        ]

    def parse(self, text: str) -> IntentResult:
        """解析输入文本，返回结构化意图。"""
        text_lower = text.lower()
        result = IntentResult(original_text=text)

        # 提取关键词
        result.raw_keywords = self._extract_keywords(text)

        # 1. 识别页面类型
        for pattern, ptype in self.page_type_patterns:
            if re.search(pattern, text_lower):
                result.page_type = ptype
                result.confidence += 0.15
                break

        # 2. 提取风格
        seen_styles = set()
        for pattern, style in self.style_patterns:
            if re.search(pattern, text_lower):
                if style not in seen_styles:
                    result.style_tags.append(style)
                    seen_styles.add(style)
                    result.confidence += 0.1

        # 3. 提取区块需求
        seen_sections = set()
        for pattern, section in self.section_patterns:
            if re.search(pattern, text_lower):
                if section not in seen_sections:
                    result.required_sections.append(section)
                    seen_sections.add(section)
                    result.confidence += 0.1

        # 如果没有显式指明区块，根据页面类型推断
        if not result.required_sections:
            result.required_sections = self._infer_sections(result.page_type)
            result.confidence += 0.05

        # 4. 颜色提示
        for pattern, color in self.color_patterns:
            if re.search(pattern, text_lower):
                result.color_hint = color
                result.confidence += 0.1
                break

        # 5. 目标受众
        for pattern, audience in self.audience_patterns:
            if re.search(pattern, text_lower):
                result.target_audience = audience
                result.confidence += 0.1
                break

        # 6. 调性
        for pattern, tone in self.tone_patterns:
            if re.search(pattern, text_lower):
                result.tone = tone
                result.confidence += 0.1
                break

        # 7. 品牌名提取 (大写单词或引号内的词)
        brand_match = re.search(r"['\"](.+?)['\"]", text)
        if brand_match:
            result.brand_name = brand_match.group(1)
            result.confidence += 0.1

        # 截断置信度上限
        result.confidence = min(result.confidence, 1.0)

        return result

    def _infer_sections(self, page_type: str) -> List[str]:
        """根据页面类型推断默认区块。"""
        defaults = {
            "landing": ["hero", "features", "pricing", "cta", "footer"],
            "dashboard": ["navbar", "stats", "features", "cta", "footer"],
            "blog": ["navbar", "blog_section", "footer"],
            "auth": ["navbar", "hero", "footer"],
            "ecommerce": ["navbar", "hero", "features", "gallery", "footer"],
            "portfolio": ["hero", "gallery", "about_section", "contact_section", "footer"],
            "docs": ["navbar", "features", "footer"],
            "about": ["hero", "about_section", "team", "stats", "cta", "footer"],
            "contact": ["navbar", "hero", "contact_section", "footer"],
            "pricing_page": ["navbar", "hero", "pricing", "faq", "cta", "footer"],
        }
        return defaults.get(page_type, ["hero", "features", "cta", "footer"])

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词。"""
        words = re.findall(r'[a-zA-Z\u4e00-\u9fff]+', text)
        # 过滤常见停用词
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "to", "of", "in", "for", "on", "with", "at", "by", "from",
                      "and", "or", "but", "not", "that", "this", "it", "its",
                      "的", "了", "是", "在", "和", "也", "就", "都", "而",
                      "及", "与", "着", "或", "一个", "没有", "我们", "你们",
                      "他们", "这个", "那个", "自己", "什么", "怎么", "如何"}
        return [w for w in words if w.lower() not in stop_words and len(w) > 1]


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = IntentEngine()
    tests = [
        "做一个暗色调的SaaS Landing Page，需要有hero、功能展示和定价区",
        "帮我设计一个现代化的企业官网，蓝色调，专业大气",
        "一个3D风格的创意个人作品集，暗色背景，展示我的设计项目",
        "电商网站，卖高端护肤品，粉色系，优雅奢华",
        "开发者工具的落地页，暗色科技感，展示API功能",
        "博客首页，极简白色，干净阅读体验",
    ]
    for t in tests:
        result = engine.parse(t)
        print(f"  📝 {t[:40]}...")
        print(f"     → {result.to_prompt()}")
        print(f"     → 置信度: {result.confidence:.0%}")
        print()
