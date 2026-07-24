"""
Skill Extractor — 从技术文章中提取知识并生成结构化技能文件
================================================================

专门从技术文章/博客中提取知识点、代码片段和最佳实践，生成符合 Hermes Agent
规范的 SKILL.md 文件。

与 AutoLearner 不同，这个引擎专注于 "你给一篇文章 URL，我提取精华存入技能库" 的场景。

核心流程:
  URL → fetch → parse(html→text) → analyze(类型/概念/代码/最佳实践/架构决策)
  → generate SKILL.md → preview / save

依赖:
  - requests / curl (网页获取)
  - trafilatura (HTML→Markdown 提取)
  - beautifulsoup4 (HTML 解析)
  - re, json, hashlib

使用示例:
  >>> from skill_extractor import SkillExtractor
  >>> se = SkillExtractor()
  >>> result = se.analyze_article("https://example.com/blog/post")
  >>> print(se.preview(result))
  >>> path = se.save_as_skill(result, category="software-development")
"""

import logging
logger = logging.getLogger(__name__)

import os
import re
import json
import hashlib
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


# ─── 常量 ────────────────────────────────────────────────────────────────────

_HERMES_SKILLS_DIR = os.path.expanduser(
    "~/AppData/Local/hermes/profiles/aris/skills"
)
_MAX_DESC_LEN = 1024
_MAX_NAME_LEN = 64

_ARTICLE_TYPES = {
    "tutorial":    ["tutorial", "guide", "getting started", "how to", "step-by-step", "walkthrough"],
    "opinion":     ["opinion", "thoughts on", "why", "my take", "rant", "perspective"],
    "comparison":  ["vs", "comparison", "alternative", "versus", "benchmark", "evaluation"],
    "reference":   ["reference", "cheat sheet", "handbook", "glossary", "documentation", "api"],
    "case-study":  ["case study", "migration", "real-world", "production", "experience report", "postmortem"],
}

_CODE_LANG_ALIASES = {
    "js": "javascript", "ts": "typescript", "py": "python", "rb": "ruby",
    "sh": "bash", "shell": "bash", "yml": "yaml", "yaml": "yaml",
    "json": "json", "html": "html", "css": "css", "go": "go",
    "rs": "rust", "java": "java", "kt": "kotlin", "swift": "swift",
    "c": "c", "cpp": "cpp", "h": "c", "hpp": "cpp",
    "dockerfile": "dockerfile", "makefile": "makefile", "ps1": "powershell",
    "sql": "sql", "toml": "toml", "xml": "xml", "diff": "diff",
    "md": "markdown", "txt": "text",
}


# ─── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class CodeBlock:
    """提取的代码块"""
    language: str = ""
    purpose: str = ""
    code: str = ""
    line_count: int = 0


@dataclass
class BestPractice:
    """最佳实践条目"""
    principle: str = ""
    description: str = ""
    example: str = ""


@dataclass
class ArchitectureDecision:
    """架构决策"""
    context: str = ""
    decision: str = ""
    rationale: str = ""
    tradeoffs: str = ""


@dataclass
class Concept:
    """关键概念"""
    name: str = ""
    description: str = ""
    category: str = ""  # terminology | pattern | tool | framework


@dataclass
class AnalysisResult:
    """完整分析结果"""
    url: str = ""
    title: str = ""
    article_type: str = ""
    summary: str = ""
    concepts: List[Concept] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    best_practices: List[BestPractice] = field(default_factory=list)
    architecture_decisions: List[ArchitectureDecision] = field(default_factory=list)
    suggested_skill_name: str = ""
    suggested_tags: List[str] = field(default_factory=list)
    raw_text: str = ""
    word_count: int = 0


# ─── Skill Extractor ────────────────────────────────────────────────────────


class SkillExtractor:
    """主引擎 — 从 URL 提取文章并生成技能文件"""

    def __init__(self, skills_dir: str = _HERMES_SKILLS_DIR):
        self.skills_dir = skills_dir
        self._session_skills = {}  # name → path cache for merge detection

    # ── 1. 网页获取 ──────────────────────────────────────────────────────

    def _fetch_url(self, url: str) -> Tuple[str, str]:
        """获取网页内容，返回 (title, text_markdown)。

        优先用 trafilatura，fallback 到 requests+bs4。
        """
        title, text = "", ""

        # 策略 A: trafilatura
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_formatting=True,
                    include_links=True,
                    include_images=False,
                    include_tables=True,
                    output_format="markdown",
                    favor_precision=True,
                )
                if text:
                    title = self._extract_title_via_trafilatura(downloaded) or ""
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        if not text:
            text, title = self._fetch_with_requests_bs4(url)

        if not text:
            raise RuntimeError(f"无法获取网页内容: {url}")

        title = title or self._guess_title_from_url(url)
        return title, text

    def _extract_title_via_trafilatura(self, raw_html: str) -> Optional[str]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_html, "html.parser")
            for sel in ["h1", "title", "meta[property='og:title']", "meta[name='title']"]:
                el = soup.select_one(sel)
                if el:
                    t = el.get("content") or el.get_text(strip=True)
                    if t:
                        return t.strip()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        return None

    def _fetch_with_requests_bs4(self, url: str) -> Tuple[str, str]:
        """Fallback: 用 requests + BeautifulSoup 获取页面内容"""
        try:
            import requests
            from bs4 import BeautifulSoup
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 去除无用标签
            for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                            "noscript", "iframe", "svg", "form", "button"]):
                tag.decompose()

            title = ""
            for sel in ["h1", "title", "meta[property='og:title']"]:
                el = soup.select_one(sel)
                if el:
                    t = el.get("content") or el.get_text(strip=True)
                    if t:
                        title = t.strip()
                        break

            # 提取主体文本 — 优先 article / main / .content / body
            article = (
                soup.find("article") or
                soup.find("main") or
                soup.select_one(".content, .post, .article, .entry-content, .blog-post") or
                soup.find("body")
            )
            if article:
                text = article.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # 清理空白行
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            text = "\n".join(lines)

            return text, title

        except ImportError:
            # 终极 fallback: curl
            return self._fetch_with_curl(url)

    def _fetch_with_curl(self, url: str) -> Tuple[str, str]:
        """终极 fallback: 用 curl 获取原始 HTML"""
        try:
            result = subprocess.run(
                ["curl", "-sSL", "-A",
                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                 url],
                capture_output=True, text=True, timeout=30,
            )
            html = result.stdout
            if not html:
                raise RuntimeError(f"curl 返回空内容: {url}")

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header",
                            "aside", "noscript", "iframe"]):
                tag.decompose()

            title = ""
            for sel in ["h1", "title"]:
                el = soup.select_one(sel)
                if el:
                    t = el.get_text(strip=True)
                    if t:
                        title = t
                        break

            body = soup.find("body")
            text = body.get_text(separator="\n", strip=True) if body else ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            text = "\n".join(lines)
            return text, title or ""

        except Exception as e:
            raise RuntimeError(f"curl 获取页面失败: {e}")

    # ── 2. 内容分析 ──────────────────────────────────────────────────────

    def analyze_article(self, url: str) -> AnalysisResult:
        """主入口：分析一篇技术文章，返回结构化结果。"""
        title, text = self._fetch_url(url)

        if not text:
            raise ValueError(f"未能从 {url} 提取到有效文本内容")

        result = AnalysisResult(
            url=url,
            title=title,
            raw_text=text,
            word_count=len(text.split()),
        )

        # 分析类型
        result.article_type = self._detect_article_type(title, text)

        # 提取关键概念
        result.concepts = self._extract_concepts(title, text)

        # 提取代码块
        result.code_blocks = self._extract_code_blocks(text)

        # 提取最佳实践
        result.best_practices = self._extract_best_practices(text, result.article_type)

        # 提取架构决策
        result.architecture_decisions = self._extract_arch_decisions(text, result.article_type)

        # 生成摘要
        result.summary = self._generate_summary(text, title, result.article_type)

        # 自动命名技能
        result.suggested_skill_name = self._suggest_skill_name(title, result)
        result.suggested_tags = self._suggest_tags(result)

        return result

    def _detect_article_type(self, title: str, text: str) -> str:
        """根据标题和内容检测文章类型。"""
        combined = (title + " " + text[:2000]).lower()

        scores = {}
        for atype, keywords in _ARTICLE_TYPES.items():
            score = sum(1 for kw in keywords if kw in combined)
            scores[atype] = score

        # 没有匹配则默认 tutorial
        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else "tutorial"

    def _extract_concepts(self, title: str, text: str) -> List[Concept]:
        """从文章中提取关键概念和技术名词。

        使用启发式方法：
        - 大写专有名词 (Python, React, Kubernetes...)
        - 重复出现的特殊标记词
        - 标题中出现的核心名词
        """
        concepts = []
        seen = set()

        # 1. 从标题提取核心名词
        title_words = re.findall(r'[A-Z][a-zA-Z0-9+#.-]{2,}', title)
        for w in title_words:
            key = w.lower()
            if key not in seen and len(w) > 2:
                concepts.append(Concept(name=w, category="framework" if len(w) > 4 else "terminology"))
                seen.add(key)

        # 2. 从正文中提取高频技术名词
        # 大写驼峰名词
        tech_pattern = re.findall(
            r'(?<!\w)([A-Z][a-z]{2,}(?:[A-Z][a-z]+)*|'  # CamelCase
            r'[A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)*)',       # ALL-CAPS or KEBAB
            text[:5000]
        )
        # 首句提取（文章开头往往列出核心概念）
        first_lines = text.split("\n")[:20]
        first_text = " ".join(first_lines)

        common_words = {"The", "This", "That", "These", "Those", "What", "How",
                        "Why", "When", "Where", "There", "Also", "However",
                        "Therefore", "Thus", "Here", "First", "Second", "Then",
                        "Next", "Last", "Finally", "But", "And", "Or", "Not",
                        "All", "Some", "Many", "Each", "Every", "Both", "More",
                        "Very", "Just", "Such", "Than", "While", "Which",
                        "With", "Your", "About", "After", "Before", "Between",
                        "Introduction", "Conclusion", "Summary", "Overview",
                        "Example", "Note", "Tip", "Warning", "Important",
                        "Following", "Following:", "Below", "Above", "Table",
                        "Figure", "Chapter", "Section", "Part", "Version"}

        for w in tech_pattern:
            key = w.lower()
            if key not in seen and w not in common_words and len(w) > 2:
                # 判断大致类别
                category = "terminology"
                if w.endswith(("JS", "QL", "ML", "AI", "API", "SDK", "CLI", "UI", "UX")):
                    category = "tool"
                elif len(re.findall(r'[A-Z]', w)) >= 3:
                    category = "framework"
                elif w.lower() in first_text.lower():
                    # 出现在开头的更可能是核心概念
                    category = "pattern"

                concepts.append(Concept(name=w, category=category))
                seen.add(key)

        return concepts[:15]  # 最多 15 个

    def _extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """从 Markdown 文本中提取代码块。"""
        blocks = []

        # 匹配 ```lang ... ``` 代码块
        code_block_pattern = re.compile(
            r'```(\w*)\n(.*?)```',
            re.DOTALL
        )

        for match in code_block_pattern.finditer(text):
            raw_lang = match.group(1).strip()
            code = match.group(2).strip()

            if not code:
                continue

            lang = _CODE_LANG_ALIASES.get(raw_lang.lower(), raw_lang) if raw_lang else "text"
            lines = code.splitlines()
            purpose = self._infer_code_purpose(code, lang, lines)

            blocks.append(CodeBlock(
                language=lang,
                purpose=purpose,
                code=code,
                line_count=len(lines),
            ))

        return blocks

    def _infer_code_purpose(self, code: str, lang: str, lines: List[str]) -> str:
        """根据代码内容推断用途。"""
        first_line = code.split("\n")[0].strip().lower()
        code_lower = code.lower()

        # 注释中的意图
        for comment_char in ["#", "//", "--", ";"]:
            for line in lines[:10]:
                stripped = line.strip()
                if stripped.startswith(comment_char):
                    text = stripped.lstrip(comment_char + " ").lower()
                    if any(kw in text for kw in ["usage", "example", "purpose:", "setup",
                                                  "initialize", "configure", "install"]):
                        return text[:80]

        # 启发式推断
        if any(kw in code_lower for kw in ["import ", "require(", "from "]):
            return "依赖导入 / 模块引入"

        if any(kw in code_lower for kw in ["def ", "function ", "fn "]):
            return "函数 / 方法定义"

        if any(kw in code_lower for kw in ["class "]):
            return "类定义"

        if any(kw in code_lower for kw in ["const ", "let ", "var ", "val ", "var "]):
            return "变量 / 常量声明"

        if any(kw in code_lower for kw in ["if ", "else ", "switch ", "match "]):
            return "条件 / 分支逻辑"

        if any(kw in code_lower for kw in ["for ", "while ", "loop ", "each "]):
            return "循环 / 迭代"

        if any(kw in code_lower for kw in ["return", "=>", "yield"]):
            return "函数返回值 / Lambda 表达式"

        if any(kw in code_lower for kw in ["config", "setting", "option"]):
            return "配置文件 / 设置"

        if any(kw in code_lower for kw in ["http", "fetch", "axios", "request", "get(", "post("]):
            return "HTTP 请求 / API 调用"

        if any(kw in code_lower for kw in ["select ", "from ", "where ", "insert ", "update ", "delete "]):
            return "SQL 查询 / 数据库操作"

        if any(kw in code_lower for kw in [".then(", ".catch(", "async ", "await "]):
            return "异步操作 / Promise"

        if any(kw in code_lower for kw in ["docker", "FROM ", "RUN ", "CMD "]):
            return "Dockerfile / 容器配置"

        if any(kw in code_lower for kw in ["npm ", "yarn ", "pip ", "cargo ", "gem "]):
            return "包管理 / 依赖安装"

        if any(kw in code_lower for kw in ["test", "describe(", "it(", "assert"]):
            return "测试代码"

        return "代码片段"

    def _extract_best_practices(self, text: str, article_type: str) -> List[BestPractice]:
        """从教程类文章中提取最佳实践。"""
        practices = []

        if article_type not in ("tutorial", "reference", "case-study"):
            return practices

        # 启发式：寻找 "best practice" / "recommend" / "should" / "don't" / "avoid"
        patterns = [
            (r'(?:Best practice|best practice)[:\s]+([^.!?\n]{10,120})', ""),
            (r'(?:recommend|recommended|recommendation)[:\s]+([^.!?\n]{10,120})', ""),
            (r'(?:should|should not|shouldn\'t)\s+([^.!?\n]{15,120})', ""),
            (r'(?:avoid|don\'t|do not)\s+([^.!?\n]{15,120})', ""),
            (r'(?:always|never)\s+([^.!?\n]{15,120})', ""),
            (r'(?:prefer|preferred|preferable)\s+([^.!?\n]{15,120})', ""),
            (r'Note[:\s]+([^.!?\n]{15,120})', ""),
            (r'(?:Tip|Tips|Pro tip)[:\s]+([^.!?\n]{15,120})', ""),
        ]

        for pattern, _ in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                sentence = match.group(1).strip()
                if len(sentence) > 15 and sentence not in [p.description for p in practices]:
                    # 尝试提取一个简明的 principle 名称
                    principle = sentence.split(".")[0].split(",")[0][:60]
                    practices.append(BestPractice(
                        principle=principle,
                        description=sentence,
                    ))

        return practices[:10]

    def _extract_arch_decisions(self, text: str, article_type: str) -> List[ArchitectureDecision]:
        """从比较/设计类文章中提取架构决策。"""
        decisions = []

        if article_type not in ("comparison", "case-study", "reference"):
            return decisions

        patterns = [
            r'(?:decision|chose|选择|选型)[^.!?\n]{10,200}',
            r'(?:architecture|architectural decision|架构)[^.!?\n]{10,200}',
            r'(?:migrate|migration|迁移)[^.!?\n]{10,200}',
            r'(?:trade-off|tradeoff|利弊|取舍)[^.!?\n]{10,200}',
            r'(?:replace|replaced|replace .+ with)[^.!?\n]{10,200}',
            r'(?:we switched|we moved|we adopted|we chose)[^.!?\n]{10,200}',
        ]

        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                snippet = match.group(0).strip()
                if snippet not in seen and len(snippet) > 30:
                    decisions.append(ArchitectureDecision(
                        decision=snippet[:150],
                        context="",
                        rationale="",
                        tradeoffs="",
                    ))
                    seen.add(snippet)

        return decisions[:8]

    def _generate_summary(self, text: str, title: str, article_type: str) -> str:
        """生成文章摘要（取前几段）。"""
        # 尝试取正文前 2-3 个非空段落
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 40]
        summary_parts = [title]

        for p in paragraphs[:3]:
            # 去掉代码块
            clean = re.sub(r'```.*?```', '', p, flags=re.DOTALL).strip()
            if clean and len(clean) > 50:
                # 截断到合理长度
                if len(clean) > 300:
                    clean = clean[:297] + "..."
                summary_parts.append(clean)

        return "\n\n".join(summary_parts[:3])

    def _suggest_skill_name(self, title: str, result: AnalysisResult) -> str:
        """从标题中自动生成技能名称。

        规则:
        1. 取标题前 3-5 个关键词
        2. 转小写，连字符分隔
        3. 确保 ≤ 64 字符
        """
        # 去掉常见后缀
        clean_title = title
        for suffix in [" — ", " – ", " | ", " - ", ": ", "："]:
            if suffix in clean_title:
                clean_title = clean_title.split(suffix)[0]

        # 提取关键词
        words = clean_title.split()
        # 去掉停用词
        stop_words = {"the", "a", "an", "in", "of", "to", "for", "and", "or",
                      "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "can",
                      "with", "from", "by", "at", "on", "into", "through",
                      "during", "before", "after", "above", "below",
                      "between", "your", "our", "its", "this", "that",
                      "these", "those", "using", "their", "his", "her"}

        keywords = [w.lower().strip(",.!?;:'\"()[]{}") for w in words
                    if w.lower().strip(",.!?;:'\"()[]{}") not in stop_words
                    and len(w.strip(",.!?;:'\"()[]{}")) > 1]

        # 最多取 5 个有效词
        name_parts = keywords[:5]
        if not name_parts:
            name_parts = ["extracted", "from", "article"]

        name = "-".join(name_parts)

        # 确保 ≤ 64 字符
        if len(name) > _MAX_NAME_LEN:
            # 逐步减少单词数
            while len(name) > _MAX_NAME_LEN and len(name_parts) > 2:
                name_parts = name_parts[:-1]
                name = "-".join(name_parts)

        return name[:_MAX_NAME_LEN].rstrip("-")

    def _suggest_tags(self, result: AnalysisResult) -> List[str]:
        """基于分析结果推荐标签。"""
        tags = set()

        tags.add(result.article_type)

        # 从概念中提取标签
        for c in result.concepts[:5]:
            tag = c.name.lower().strip()
            if len(tag) > 2 and len(tag) < 30:
                tags.add(tag)

        # 代码语言
        for cb in result.code_blocks[:3]:
            if cb.language and cb.language != "text":
                tags.add(cb.language)

        return sorted(tags)[:10]

    # ── 3. 重复检测与合并 ────────────────────────────────────────────────

    def _find_existing_skill(self, name: str) -> Optional[str]:
        """检查已有技能是否与提取的名字重复，返回路径或 None。"""
        if name in self._session_skills:
            return self._session_skills[name]

        # 搜索 skills 目录
        if os.path.isdir(self.skills_dir):
            for root, dirs, files in os.walk(self.skills_dir):
                for d in dirs:
                    if d == name or d.startswith(name) or name.startswith(d):
                        skill_path = os.path.join(root, d, "SKILL.md")
                        if os.path.isfile(skill_path):
                            self._session_skills[name] = skill_path
                            return skill_path

        return None

    # ── 4. SKILL.md 生成 ─────────────────────────────────────────────────

    def generate_skill_md(self, result: AnalysisResult) -> str:
        """从分析结果生成完整的 SKILL.md 内容。"""
        now = datetime.now().strftime("%Y-%m-%d")
        name = result.suggested_skill_name
        desc = f"Use when extracting knowledge from {result.title}. " \
               f"{self._summarize_article_type(result.article_type)}."

        if len(desc) > _MAX_DESC_LEN:
            desc = desc[:_MAX_DESC_LEN - 3] + "..."

        tags = result.suggested_tags[:8]
        sources = [result.url]

        lines = [
            "---",
            f"name: {name}",
            f"description: \"{desc}\"",
            f"version: 1.0.0",
            f"author: Skill Extractor (auto-generated)",
            f"source: {result.url}",
            f"extracted: {now}",
            f"license: MIT",
            f"platforms: [linux, macos, windows]",
            f"metadata:",
            f"  hermes:",
            f"    tags: [{', '.join(tags)}]",
            f"    source_url: {result.url}",
            "---",
            "",
            f"# {result.title}",
            "",
        ]

        # 文章信息
        lines += [
            f"> **来源:** [{result.url}]({result.url})",
            f"> **类型:** {result.article_type}",
            f"> **词数:** {result.word_count}",
            f"> **提取时间:** {now}",
            "",
        ]

        # 摘要
        if result.summary:
            lines += ["## 概述", "", result.summary, ""]

        # 关键概念
        if result.concepts:
            lines += ["## 关键概念", ""]
            for c in result.concepts:
                lines.append(f"- **{c.name}** ({c.category}): {c.description}" if c.description
                             else f"- **{c.name}** ({c.category})")
            lines.append("")

        # 代码示例
        if result.code_blocks:
            lines += ["## 代码示例", ""]
            for i, cb in enumerate(result.code_blocks, 1):
                header = f"### {i}. {cb.purpose}" if cb.purpose else f"### {i}. 代码片段"
                lines.append(header)
                lines.append("")
                lines.append(f"- **语言:** {cb.language}")
                lines.append(f"- **行数:** {cb.line_count}")
                lines.append("")
                lines.append(f"```{cb.language}")
                lines.append(cb.code)
                lines.append("```")
                lines.append("")

        # 最佳实践
        if result.best_practices:
            lines += ["## 最佳实践", ""]
            for i, bp in enumerate(result.best_practices, 1):
                lines.append(f"### {i}. {bp.principle}")
                lines.append("")
                lines.append(bp.description)
                lines.append("")
                if bp.example:
                    lines.append(f"> **示例:** {bp.example}")
                    lines.append("")

        # 架构决策
        if result.architecture_decisions:
            lines += ["## 架构决策", ""]
            for i, ad in enumerate(result.architecture_decisions, 1):
                lines.append(f"### 决策 {i}")
                lines.append("")
                lines.append(ad.decision)
                lines.append("")

        # 引用来源
        lines += ["## 来源", ""]
        for src in sources:
            lines.append(f"- [{src}]({src})")

        lines.append("")

        return "\n".join(lines)

    def _summarize_article_type(self, article_type: str) -> str:
        summaries = {
            "tutorial": "教程类 — 包含分步指南和可复用的代码模板",
            "opinion": "观点类 — 包含技术权衡和思考视角",
            "comparison": "对比类 — 包含方案选型和架构决策",
            "reference": "参考类 — 包含技术参考和速查表",
            "case-study": "案例研究 — 包含真实世界经验教训和最佳实践",
        }
        return summaries.get(article_type, f"{article_type} 类型内容")

    # ── 5. 预览 ──────────────────────────────────────────────────────────

    def preview(self, result: AnalysisResult) -> str:
        """生成分析结果预览(控制台友好格式)。"""
        lines = [
            "=" * 72,
            f"📄 文章分析预览",
            "=" * 72,
            f"",
            f"  标题:    {result.title}",
            f"  来源:    {result.url}",
            f"  类型:    {result.article_type.upper()}",
            f"  词数:    {result.word_count}",
            f"  建议名:  {result.suggested_skill_name}",
            f"  标签:    {', '.join(result.suggested_tags)}",
            "",
        ]

        # 摘要
        if result.summary:
            short_summary = result.summary[:300].replace("\n", " ")
            lines += [
                f"  📝 摘要预览:",
                f"     {short_summary}...",
                "",
            ]

        # 概念
        if result.concepts:
            lines.append(f"  🔑 关键概念 ({len(result.concepts)}):")
            for c in result.concepts[:8]:
                lines.append(f"     - {c.name} [{c.category}]")
            if len(result.concepts) > 8:
                lines.append(f"     ... 还有 {len(result.concepts) - 8} 个")
            lines.append("")

        # 代码块
        if result.code_blocks:
            lines.append(f"  💻 代码示例 ({len(result.code_blocks)}):")
            for i, cb in enumerate(result.code_blocks[:5], 1):
                preview_code = cb.code[:60].replace("\n", " ")
                lines.append(f"     {i}. [{cb.language}] {cb.purpose}")
                lines.append(f"        {preview_code}{'...' if len(cb.code) > 60 else ''}")
            if len(result.code_blocks) > 5:
                lines.append(f"     ... 还有 {len(result.code_blocks) - 5} 个")
            lines.append("")

        # 最佳实践
        if result.best_practices:
            lines.append(f"  ✅ 最佳实践 ({len(result.best_practices)}):")
            for i, bp in enumerate(result.best_practices[:5], 1):
                lines.append(f"     {i}. {bp.principle}")
            if len(result.best_practices) > 5:
                lines.append(f"     ... 还有 {len(result.best_practices) - 5} 条")
            lines.append("")

        # 架构决策
        if result.architecture_decisions:
            lines.append(f"  🏗️  架构决策 ({len(result.architecture_decisions)}):")
            for i, ad in enumerate(result.architecture_decisions[:4], 1):
                lines.append(f"     {i}. {ad.decision[:80]}...")
            lines.append("")

        lines += [
            "=" * 72,
            f"💾 生成的 SKILL.md 预览 (前 30 行):",
            "=" * 72,
            "",
        ]

        # 生成并截取前 30 行
        skill_md = self.generate_skill_md(result)
        md_lines = skill_md.splitlines()[:30]
        lines += md_lines
        if len(skill_md.splitlines()) > 30:
            lines.append("...")
            lines.append(f"[共 {len(skill_md.splitlines())} 行, {len(skill_md)} 字符]")

        lines.append("")
        return "\n".join(lines)

    # ── 6. 保存技能 ──────────────────────────────────────────────────────

    def save_as_skill(self, result: AnalysisResult, category: str = "software-development") -> str:
        """将分析结果保存为技能文件。返回文件路径。

        如果已有同名技能，尝试 merge 而不是覆盖。
        """
        name = result.suggested_skill_name
        skill_md = self.generate_skill_md(result)

        # 检测已有技能
        existing = self._find_existing_skill(name)
        if existing:
            return self._merge_with_existing(result, existing, skill_md)

        # 创建新技能
        target_dir = os.path.join(self.skills_dir, category, name)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, "SKILL.md")

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(skill_md)

        self._session_skills[name] = target_path
        return target_path

    def _merge_with_existing(self, result: AnalysisResult, existing_path: str,
                              new_content: str) -> str:
        """合并新提取的内容到已有技能中。"""
        # 读取现有内容
        with open(existing_path, "r", encoding="utf-8") as f:
            existing_content = f.read()

        # 分析现有技能结构
        # 在 # 关键概念 / ## 代码示例 等章节后追加新内容
        merged = existing_content.rstrip()

        # 追加代码块
        if result.code_blocks:
            merged += "\n\n## 从文章追加的内容\n\n"
            merged += f"> **追加来源:** [{result.url}]({result.url})\n\n"

            if result.concepts:
                merged += "### 追加概念\n\n"
                for c in result.concepts:
                    merged += f"- **{c.name}** ({c.category}): {c.description}\n" if c.description \
                              else f"- **{c.name}** ({c.category})\n"
                merged += "\n"

            if result.code_blocks:
                merged += "### 追加代码\n\n"
                for i, cb in enumerate(result.code_blocks, 1):
                    merged += f"```{cb.language}\n"
                    merged += f"// {cb.purpose}\n" if cb.purpose else ""
                    merged += cb.code + "\n"
                    merged += "```\n\n"

            if result.best_practices:
                merged += "### 追加最佳实践\n\n"
                for bp in result.best_practices:
                    merged += f"- **{bp.principle}:** {bp.description}\n"
                merged += "\n"

            # 更新 frontmatter 中的 source_url
            merged = re.sub(
                r'(source_url:\s*).*',
                lambda m: m.group(1) + result.url,
                merged,
            )

        with open(existing_path, "w", encoding="utf-8") as f:
            f.write(merged)

        return existing_path

    # ── 7. 批量处理 ──────────────────────────────────────────────────────

    def batch_analyze(self, urls: List[str]) -> List[AnalysisResult]:
        """批量分析多个 URL。"""
        results = []
        for url in urls:
            try:
                logger.info(f"  🔄 正在分析: {url}")
                result = self.analyze_article(url)
                results.append(result)
                logger.info(f"     ✅ 完成: {result.title[:50]}...")
            except Exception as e:
                logger.error(f"     ❌ 失败: {e}")
                results.append(AnalysisResult(
                    url=url,
                    title=f"[提取失败] {url}",
                ))
        return results

    def batch_preview(self, urls: List[str]) -> str:
        """批量预览多个 URL 的分析结果。"""
        lines = []
        results = self.batch_analyze(urls)
        for i, (url, result) in enumerate(zip(urls, results), 1):
            lines.append(f"\n{'─' * 60}")
            lines.append(f"  #{i}  {result.title}")
            lines.append(f"      {url}")
            lines.append(f"      类型: {result.article_type} | "
                         f"概念: {len(result.concepts)} | "
                         f"代码: {len(result.code_blocks)} | "
                         f"最佳实践: {len(result.best_practices)}")
            lines.append(f"      建议技能名: {result.suggested_skill_name}")

        lines.append(f"\n{'=' * 60}")
        lines.append(f"共 {len(results)} 篇文章分析完成")
        return "\n".join(lines)

    # ── 辅助 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _guess_title_from_url(url: str) -> str:
        """从 URL 推断标题。"""
        path = urlparse(url).path
        parts = [p for p in path.split("/") if p and not p.startswith(("?", "#"))]
        if parts:
            last = parts[-1].replace("-", " ").replace("_", " ")
            # 去掉文件扩展名
            last = re.sub(r'\.[a-z]+$', '', last)
            return last.title() if last else url
        return url


# ── CLI ─────────────────────────────────────────────────────────────────────


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Skill Extractor — 从技术文章中提取知识生成结构化技能文件"
    )
    parser.add_argument("url", nargs="*", help="要分析的文章 URL")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="仅预览，不保存")
    parser.add_argument("--save", "-s", action="store_true",
                        help="保存为技能文件")
    parser.add_argument("--category", "-c", default="software-development",
                        help="技能分类 (默认: software-development)")
    parser.add_argument("--batch", "-b", nargs="*",
                        help="批量分析多个 URL")
    parser.add_argument("--file", "-f",
                        help="从文件读取 URL 列表 (每行一个)")

    args = parser.parse_args()

    se = SkillExtractor()

    # 收集 URLs
    urls = []
    if args.file:
        with open(args.file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    if args.batch:
        urls.extend(args.batch)
    if args.url:
        urls.extend(args.url)

    if not urls:
        parser.print_help()
        logger.info("\n⚠️  请提供至少一个 URL")
        sys.exit(1)

    if len(urls) > 1 or args.batch:
        # 批量模式
        results = se.batch_analyze(urls)
        if args.save:
            for r in results:
                if r.title and not r.title.startswith("[提取失败"):
                    path = se.save_as_skill(r, args.category)
                    logger.info(f"  💾 已保存: {path}")
        else:
            logger.info(se.batch_preview(urls))
    else:
        # 单篇模式
        url = urls[0]
        try:
            result = se.analyze_article(url)
            if args.preview or not args.save:
                logger.info(se.preview(result))
            if args.save:
                path = se.save_as_skill(result, args.category)
                logger.info(f"\n💾 技能已保存到: {path}")
        except Exception as e:
            logger.error(f"❌ 分析失败: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
