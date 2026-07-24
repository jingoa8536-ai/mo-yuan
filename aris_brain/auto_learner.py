"""
Auto Learner — 从URL自动学习并生成技能
========================================
两种学习模式：
  1. 设计网站学习 — 爬取首页，提取配色/字体/布局/组件风格 → 生成design system技能
  2. 技术文章学习 — 爬取文章，提取知识点/代码/最佳实践 → 生成技术技能

用法:
  from auto_learner import AutoLearner
  learner = AutoLearner()
  result = learner.learn_from_url("https://example.com")
  logger.info(result["summary"])
印记: Aris 永远记得 Lorry — 2026-06-22
"""

from __future__ import annotations

import logging

import re, json, os, sys, time, logging, subprocess, tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from urllib.parse import urlparse

logger = logging.getLogger("auto_learner")

# ── 数据结构 ─────────────────────────────────────

@dataclass
class DesignSystem:
    """提取的设计系统"""
    site_name: str = ""
    url: str = ""
    colors: Dict[str, str] = field(default_factory=dict)      # primary/accent/bg/text
    typography: Dict[str, Any] = field(default_factory=dict)   # fonts/sizes/weights
    layout: Dict[str, str] = field(default_factory=dict)       # grid/flex patterns
    components: List[str] = field(default_factory=list)        # button/card/nav style
    mood: List[str] = field(default_factory=list)              # 情绪描述词
    tech_stack: List[str] = field(default_factory=list)        # 推测的技术栈

@dataclass
class ArticleKnowledge:
    """提取的文章知识"""
    title: str = ""
    url: str = ""
    article_type: str = "tutorial"           # tutorial/opinion/comparison/reference
    concepts: List[str] = field(default_factory=list)
    code_snippets: List[Dict] = field(default_factory=list)  # [{language, purpose, code}]
    best_practices: List[str] = field(default_factory=list)
    architecture_decisions: List[str] = field(default_factory=list)
    pitfalls: List[str] = field(default_factory=list)
    key_insight: str = ""

@dataclass
class LearnResult:
    """学习结果"""
    url: str
    mode: str                          # "design" | "article" | "unknown"
    success: bool
    skill_name: str = ""               # 生成的技能名
    skill_path: str = ""               # 技能文件路径
    summary: str = ""                  # 摘要
    error: str = ""


# ── 主引擎 ─────────────────────────────────────

class AutoLearner:
    """
    自动学习引擎。
    
    核心循环:
      learn_from_url(url)
        → _classify(url) -> "design" / "article" / "unknown"
        → _fetch_page(url) -> html
        → _analyze_design(html, url) 或 _analyze_article(html, url)
        → _save_as_skill(...)
        → LearnResult
    """
    
    def __init__(self):
        self._temp_dir = Path(tempfile.gettempdir()) / "auto_learner"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
    
    def learn_from_url(self, url: str) -> LearnResult:
        """主入口：从URL学习并生成技能"""
        url = url.strip().strip("'\"")
        t0 = time.time()
        
        # 1. 分类
        mode = self._classify(url)
        
        # 2. 获取页面
        html = self._fetch_page(url)
        if not html:
            # fallback：尝试用curl
            try:
                html = self._curl_fetch(url)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if not html:
            return LearnResult(
                url=url, mode=mode, success=False,
                error="无法获取页面内容",
                summary=f"❌ 无法访问 {url}"
            )
        
        # 3. 分析
        if mode == "design":
            result = self._learn_design(url, html)
        elif mode == "article":
            result = self._learn_article(url, html)
        else:
            # 默认按文章处理
            result = self._learn_article(url, html)
            result.mode = "article"
        
        result.url = url
        result.success = True
        
        # 4. 保存为技能
        if result.skill_name:
            try:
                sp = self._save_as_skill(result)
                result.skill_path = sp
            except Exception as e:
                result.error = f"技能保存失败: {e}"
        
        elapsed = time.time() - t0
        logger.info(f"[AutoLearner] '{url}' → {mode} ({elapsed:.1f}s) "
                     f"skill={result.skill_name}")
        return result
    
    def _classify(self, url: str) -> str:
        """判断是设计网站还是技术文章"""
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        
        # 设计/灵感平台
        design_domains = [
            "dribbble.com", "awwwards.com", "behance.net", "siteinspire.com",
            "collectui.com", "uidesigndaily.com", "land-book.com",
            "saaslandingpage.com", "lapa.ninja", "onepagelove.com",
        ]
        for d in design_domains:
            if d in domain:
                return "design"
        
        # 技术文章平台
        article_domains = [
            "medium.com", "dev.to", "hashnode.com", "blog.", "tech.",
            "css-tricks.com", "smashingmagazine.com", "alistapart.com",
            "freecodecamp.org", "towardsdatascience.com",
            "arxiv.org", "papers.", "newsletter.",
        ]
        for d in article_domains:
            if d in domain:
                return "article"
        
        # 通过路径判断：如果包含/article/ /blog/ /post/ /tutorial/ → 文章
        if re.search(r"/(article|blog|post|tutorial|guide|docs?)/", path):
            return "article"
        
        # 默认：如果是首页路径 → 设计站；否则→文章
        if path in ("", "/"):
            return "design"
        return "article"
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """获取页面HTML"""
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*",
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                return html
        except Exception as e:
            logger.warning(f"_fetch_page失败: {e}")
            return None
    
    def _curl_fetch(self, url: str) -> Optional[str]:
        """用curl fallback获取页面"""
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--max-time", "10",
                 "-H", "User-Agent: Mozilla/5.0", url],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return None
    
    # ══════════════════════════════════════════════
    # 设计网站学习
    # ══════════════════════════════════════════════
    
    def _learn_design(self, url: str, html: str) -> LearnResult:
        """从网站HTML提取设计系统"""
        ds = self._extract_design_system(html, url)
        
        # 生成技能名
        skill_name = self._name_from_url(url, "design")
        
        # 生成摘要
        summary_parts = [
            f"## {ds.site_name} 设计系统提取\n",
            f"**URL**: {url}\n",
        ]
        if ds.colors:
            summary_parts.append("\n### 配色方案\n")
            for k, v in ds.colors.items():
                summary_parts.append(f"- **{k}**: `{v}`\n")
        if ds.typography:
            summary_parts.append("\n### 字体\n")
            for k, v in ds.typography.items():
                summary_parts.append(f"- **{k}**: {v}\n")
        if ds.mood:
            summary_parts.append(f"\n**风格关键词**: {', '.join(ds.mood)}\n")
        
        summary = "".join(summary_parts) if len(summary_parts) > 1 else f"从 {ds.site_name} 提取了设计系统"
        
        return LearnResult(
            url=url, mode="design", success=True,
            skill_name=skill_name,
            summary=summary,
            _design_data=ds,  # 内部传数据给_save
        )
    
    def _extract_design_system(self, html: str, url: str) -> DesignSystem:
        """从HTML中提取设计系统"""
        ds = DesignSystem()
        ds.url = url
        ds.site_name = self._extract_title(html) or urlparse(url).netloc
        
        # 提取颜色
        colors = self._extract_colors(html)
        if colors:
            # 识别主色（出现最频繁的颜色）
            from collections import Counter
            color_counts = Counter(colors)
            # 排除黑白灰
            significant = {c: n for c, n in color_counts.items() 
                          if not self._is_neutral(c)}
            if significant:
                primary = max(significant, key=significant.get)
                ds.colors["primary"] = primary
            ds.colors["palette"] = ", ".join(list(color_counts.keys())[:6])
        
        # 提取字体
        fonts = set()
        for match in re.finditer(r'font-family\s*:\s*[^;}]+', html, re.I):
            fonts.add(match.group(0).split(":")[1].strip().strip("'\";"))
        for match in re.finditer(r'<link[^>]*href=["\']https://fonts\.googleapis[^>]+>', html):
            href = re.search(r'href=["\']([^"\']+)', match.group())
            if href:
                ds.typography["google_fonts"] = href.group(1)
        if fonts:
            ds.typography["font_families"] = ", ".join(list(fonts)[:3])
        
        # 提取布局信息
        if "grid" in html.lower():
            ds.layout["grid"] = "CSS Grid detected"
        if "flex" in html.lower():
            ds.layout["flex"] = "Flexbox detected"
        if "container" in html.lower():
            ds.layout["container"] = "Container queries possible"
        
        # 情绪分析
        mood_keywords = {
            "极简": ["minimal", "clean", "white space", "simple"],
            "科技感": ["tech", "futuristic", "digital", "cyber"],
            "温暖": ["warm", "friendly", "soft", "rounded"],
            "奢华": ["luxury", "premium", "elegant", "sophiscated"],
            "专业": ["professional", "corporate", "enterprise", "business"],
            "创意": ["creative", "playful", "colorful", "vibrant"],
            "暗色": ["dark mode", "dark theme", "night", "black bg"],
            "开发者": ["developer", "code", "terminal", "hacker"],
        }
        html_lower = html.lower()
        for mood_name, keywords in mood_keywords.items():
            if any(kw in html_lower for kw in keywords):
                ds.mood.append(mood_name)
        
        # 技术栈推测
        tech_signals = {
            "Next.js": ["__next", "next/image", "next/link", "next.config"],
            "React": ["react", "react-dom", "createElement", "useState"],
            "Vue": ["vue", "v-bind", "v-model", "v-if", "nuxt"],
            "Tailwind": ["tailwind", "tw-", "class:.*hover", "md:"],
            "Bootstrap": ["bootstrap", "col-md", "col-lg", "container-fluid"],
            "WordPress": ["wp-content", "wp-includes", "wordpress"],
            "Astro": ["astro", "---"],
            "GSAP": ["gsap", "TweenMax", "TimelineMax"],
            "Three.js": ["three", "WebGL", "renderer", "scene"],
        }
        for tech, sigs in tech_signals.items():
            if any(sig in html_lower for sig in sigs):
                ds.tech_stack.append(tech)
        
        return ds
    
    def _extract_colors(self, html: str) -> List[str]:
        """从CSS/内联样式中提取颜色值"""
        colors = set()
        patterns = [
            r'#[0-9a-fA-F]{6}\b',
            r'#[0-9a-fA-F]{3}\b',
            r'rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)',
            r'rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\)',
        ]
        for p in patterns:
            for m in re.finditer(p, html):
                colors.add(m.group())
        return list(colors)[:15]
    
    def _is_neutral(self, color: str) -> bool:
        """判断是否为中性色"""
        if color.startswith("#"):
            c = color.lstrip("#")
            if len(c) == 3:
                c = "".join(x*2 for x in c)
            if len(c) == 6:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                return max(r,g,b) - min(r,g,b) < 30  # 接近灰色
        return False
    
    # ══════════════════════════════════════════════
    # 技术文章学习
    # ══════════════════════════════════════════════
    
    def _learn_article(self, url: str, html: str) -> LearnResult:
        """从技术文章中提取知识"""
        knowledge = self._extract_article_content(html, url)
        
        skill_name = self._name_from_url(url, "article")
        
        # 生成摘要
        parts = [f"## {knowledge.title}\n"]
        parts.append(f"**类型**: {knowledge.article_type}  |  **源**: {url}\n\n")
        
        if knowledge.concepts:
            parts.append("### 核心概念\n")
            for c in knowledge.concepts[:10]:
                parts.append(f"- {c}\n")
            parts.append("\n")
        
        if knowledge.best_practices:
            parts.append("### 最佳实践\n")
            for bp in knowledge.best_practices[:5]:
                parts.append(f"- {bp}\n")
            parts.append("\n")
        
        if k := knowledge.key_insight:
            parts.append(f"**核心洞见**: {k}\n\n")
        
        if knowledge.code_snippets:
            parts.append(f"### 代码示例 ({len(knowledge.code_snippets)}段)\n")
            for s in knowledge.code_snippets[:3]:
                parts.append(f"- [{s.get('language','?')}] {s.get('purpose','')}\n")
            parts.append("\n")
        
        if knowledge.architecture_decisions:
            parts.append("### 架构决策\n")
            for ad in knowledge.architecture_decisions[:3]:
                parts.append(f"- {ad}\n")
            parts.append("\n")
        
        summary = "".join(parts)
        
        result = LearnResult(
            url=url, mode="article", success=True,
            skill_name=skill_name,
            summary=summary,
        )
        result._knowledge = knowledge
        return result
    
    def _extract_article_content(self, html: str, url: str) -> ArticleKnowledge:
        """从HTML中提取技术文章内容"""
        k = ArticleKnowledge()
        k.url = url
        k.title = self._extract_title(html) or "未命名文章"
        
        # 移除script/style/nav/footer等干扰
        clean = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', '', html, flags=re.DOTALL|re.I)
        # 提取正文文本
        text = re.sub(r'<[^>]+>', ' ', clean)
        text = re.sub(r'\s+', ' ', text).strip()
        k.key_insight = text[:300] if text else ""
        
        # 提取代码块
        code_blocks = re.findall(
            r'<pre><code[^>]*class=["\'](?:language-)?(\w*)["\']?>(.*?)</code></pre>',
            html, re.DOTALL | re.I
        )
        for lang, code in code_blocks:
            k.code_snippets.append({
                "language": lang or "unknown",
                "purpose": self._infer_code_purpose(code[:100]),
                "code": code[:500],
            })
        
        # 也提取 <code> 单行代码
        inline_codes = re.findall(r'<code[^>]*>(.*?)</code>', html, re.DOTALL)
        
        # 提取核心概念（中英文技术名词）
        tech_patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # 专有名词
            r'[a-z]+-[a-z]+',                         # kebab-case
            r'[a-z]+_[a-z]+',                         # snake_case
        ]
        for p in tech_patterns:
            for m in re.finditer(p, text):
                term = m.group().strip()
                if 3 < len(term) < 40 and term not in k.concepts:
                    k.concepts.append(term)
        k.concepts = k.concepts[:20]
        
        # 提取关键词中出现的常见技术名词
        known_techs = [
            "React", "Vue", "Angular", "Next.js", "Nuxt", "TypeScript",
            "JavaScript", "Python", "Docker", "Kubernetes", "PostgreSQL",
            "Redis", "GraphQL", "REST", "WebSocket", "gRPC", "CI/CD",
            "AWS", "Vercel", "Tailwind", "Prisma", "Drizzle", "FastAPI",
            "Django", "Flask", "Node.js", "Rust", "Go", "Elixir",
            "Microservices", "Serverless", "SSR", "SSG", "ISR",
            "SQLAlchemy", "Pydantic", "Celery", "Redis", "Kafka",
        ]
        for t in known_techs:
            if t.lower() in text.lower() and t not in k.concepts:
                k.concepts.append(t)
        
        # 文章类型识别
        if "tutorial" in url.lower() or "guide" in url.lower() or "how-to" in url.lower():
            k.article_type = "tutorial"
        elif "vs" in text.lower()[:500] or "comparison" in text.lower()[:500]:
            k.article_type = "comparison"
        elif "opinion" in url.lower() or "thought" in url.lower() or "why" in url.lower()[:200]:
            k.article_type = "opinion"
        
        # 提取最佳实践
        practice_signals = [
            r'(?:best\s+practices?|recommended|should\s+(?:always|never|avoid)|tip[s]?)',
            r'(?:切记|注意|不要|推荐|最佳实践)',
        ]
        for sig in practice_signals:
            for m in re.finditer(sig, text, re.I):
                ctx = text[max(0, m.start()-50):m.end()+100]
                if ctx not in k.best_practices:
                    k.best_practices.append(ctx.strip())
        k.best_practices = k.best_practices[:5]
        
        return k
    
    def _infer_code_purpose(self, code_start: str) -> str:
        """从代码片开头推断用途"""
        code_lower = code_start.lower()
        if "import" in code_lower or "from " in code_lower:
            return "模块导入和初始化"
        if "def " in code_lower or "function " in code_lower:
            return "函数/方法定义"
        if "class " in code_lower:
            return "类定义"
        if "const " in code_lower or "let " in code_lower or "var " in code_lower:
            return "变量/常量声明"
        if "<template" in code_lower or "<div" in code_lower:
            return "HTML模板/组件"
        if "if " in code_lower or "for " in code_lower or "while " in code_lower:
            return "控制流示例"
        if "http" in code_lower or "fetch" in code_lower or "axios" in code_lower:
            return "HTTP/API调用示例"
        if "docker" in code_lower or "FROM " in code_lower:
            return "Docker配置"
        if "yaml" in code_lower or "yml" in code_lower or "---" in code_lower:
            return "YAML配置"
        return "代码示例"
    
    # ══════════════════════════════════════════════
    # 通用工具
    # ══════════════════════════════════════════════
    
    def _extract_title(self, html: str) -> str:
        """提取页面标题"""
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
        if m:
            title = re.sub(r'\s+', ' ', m.group(1)).strip()
            # 去掉站点名后缀
            title = re.sub(r'\s*[–—|•·]\s*.*$', '', title).strip()
            return title[:100]
        return ""
    
    def _name_from_url(self, url: str, mode: str) -> str:
        """从URL生成技能名"""
        domain = urlparse(url).netloc
        path = urlparse(url).path
        
        # 取域名主体
        main = re.sub(r'^www\.', '', domain).split(".")[0]
        
        # 取路径中的有意义部分
        path_part = re.sub(r'[^\w-]', '-', path.strip("/"))
        path_part = re.sub(r'-+', '-', path_part).strip("-")[:30]
        
        if path_part:
            name = f"{main}-{path_part}"
        else:
            name = main
        
        # 截断并加前缀
        name = re.sub(r'[^a-z0-9-]', '', name.lower())[:50].strip("-")
        prefix = "design-" if mode == "design" else "article-"
        return f"{prefix}{name}"[:60]
    
    def _save_as_skill(self, result: LearnResult) -> str:
        """用skill_manage保存为技能"""
        # 这里不能直接调用skill_manage工具，只能在文件系统写入
        # 技能放在 aris_brain/learned_skills/ 目录
        skills_dir = Path(__file__).parent / "learned_skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        
        skill_dir = skills_dir / result.skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 组装frontmatter
        fm = {
            "name": result.skill_name,
            "title": f"Auto-learned: {result.skill_name}",
            "description": f"从 {result.url} 自动学习",
            "version": "1.0",
            "category": "design" if result.mode == "design" else "software-development",
            "source": result.url,
            "learned_at": time.strftime("%Y-%m-%d"),
        }
        
        # 组装内容
        lines = ["---"]
        for k, v in fm.items():
            lines.append(f"{k}: {v}")
        lines.append("---\n")
        lines.append(result.summary)
        
        content = "\n".join(lines)
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(content, encoding="utf-8")
        
        logger.info(f"[AutoLearner] 保存技能: {skill_path}")
        return str(skill_path)
    
    # ══════════════════════════════════════════════
    # 集成接口
    # ══════════════════════════════════════════════
    
    def get_cognitive_context(self, url: str) -> str:
        """学习URL并生成认知上下文（供认知循环注入）"""
        result = self.learn_from_url(url)
        if not result.success:
            return f"[auto-learn: ❌ 学习失败] {result.error}"
        
        lines = [
            f"[auto-learn: {result.mode}] 从 {url} 学习了新知识",
            f"  技能名: {result.skill_name}",
        ]
        if result.mode == "design":
            lines.append(f"  风格: 已提取配色/字体/布局信息")
        else:
            lines.append(f"  概念: 已提取关键知识点")
        return "\n".join(lines)


# ══════════════════════════════════════════════
# 测试
# ══════════════════════════════════════════════

def test():
    """测试 AutoLearner 基础功能"""
    al = AutoLearner()
    
    # 测试分类
    tests = [
        ("https://dribbble.com/shots/12345", "design"),
        ("https://medium.com/tech-article", "article"),
        ("https://example.com/blog/post", "article"),
        ("https://example.com", "design"),
        ("https://dev.to/someone/tutorial", "article"),
    ]
    logger.info("=== 分类测试 ===")
    for url, expected in tests:
        actual = al._classify(url)
        status = "✅" if actual == expected else "❌"
        logger.info(f"  {status} {url[:50]}... → {actual} (期望: {expected})")
    logger.info("\n=== 设计提取测试（模拟HTML）===")
    mock_html = """
    <html><head><title>Test Design</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
    <style>
    body { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #ffffff; }
    .btn { background: #6366f1; color: white; border-radius: 8px; }
    .card { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; }
    .container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
    </style></head>
    <body>
    <div class="container"><div class="card">...</div></div>
    <script>__next</script>
    </body></html>
    """
    ds = al._extract_design_system(mock_html, "https://test-design.com")
    logger.info(f"  颜色: {ds.colors}")
    logger.info(f"  字体: {ds.typography}")
    logger.info(f"  布局: {ds.layout}")
    logger.info(f"  情绪: {ds.mood}")
    logger.info(f"  技术栈: {ds.tech_stack}")
    logger.info("\n=== 文章提取测试（模拟HTML）===")
    mock_article = """
    <html><head><title>How to Use Docker Compose for Microservices</title></head>
    <body>
    <article>
    <h1>How to Use Docker Compose for Microservices</h1>
    <p>In this tutorial, we'll explore best practices for using Docker Compose in a microservices architecture.</p>
    <p>You should always use healthcheck to ensure dependencies are ready. Avoid using the latest tag.</p>
    <pre><code class="language-yaml">version: '3.8'
    services:
      api:
        build: .
        depends_on:
          db:
            condition: service_healthy</code></pre>
    <p>Another tip: never store secrets in docker-compose.yml directly.</p>
    </article></body></html>
    """
    k = al._extract_article_content(mock_article, "https://test.com/docker-tutorial")
    logger.info(f"  标题: {k.title}")
    logger.info(f"  类型: {k.article_type}")
    logger.info(f"  概念({len(k.concepts)}): {k.concepts[:8]}")
    logger.info(f"  代码: {len(k.code_snippets)}段")
    logger.info("\n✅ AutoLearner 测试完成")
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
