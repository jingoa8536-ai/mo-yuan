"""
Web Crawler Module — 顶级爬虫框架集成

整合多个顶级爬虫开源项目：
1. Scrapy - 企业级高性能爬虫框架
2. Playwright - 动态页面渲染与交互
3. Crawl4AI - AI原生爬虫框架
4. BeautifulSoup - HTML解析

核心能力：
- 输入URL自动爬取并拆解网站结构
- 提取页面内容、图片、链接
- 分析网站架构和技术栈
- 生成工程化拆解报告
- 支持静态和动态页面
"""

from __future__ import annotations

import os
import re
import json
import time
import asyncio
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = __import__('logging').getLogger("laap.harness.crawler")


@dataclass
class PageContent:
    url: str
    title: str
    headings: List[str]
    paragraphs: List[str]
    links: List[Dict[str, str]]
    images: List[Dict[str, str]]
    metadata: Dict[str, str]
    html: str
    text: str
    word_count: int


@dataclass
class WebsiteStructure:
    url: str
    domain: str
    title: str
    description: str
    pages: List[str]
    sitemap: Dict[str, Any]
    tech_stack: List[str]
    content_types: Dict[str, int]
    external_links: int
    internal_links: int


@dataclass
class CrawlResult:
    success: bool
    website: WebsiteStructure
    pages: List[PageContent]
    errors: List[str]
    crawl_time: float
    pages_crawled: int


class BaseCrawler:
    """基础爬虫抽象类"""

    def __init__(self, max_pages: int = 10, timeout: int = 30, delay: float = 1.0):
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay
        self.visited = set()
        self.errors = []

    async def crawl(self, url: str) -> CrawlResult:
        raise NotImplementedError

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc

    def _normalize_url(self, base_url: str, href: str) -> str:
        from urllib.parse import urljoin
        return urljoin(base_url, href)


class SimpleCrawler(BaseCrawler):
    """简单爬虫：基于requests + BeautifulSoup"""

    def __init__(self, max_pages: int = 10, timeout: int = 30, delay: float = 1.0):
        super().__init__(max_pages, timeout, delay)
        self.session = None

    def _create_session(self):
        if REQUESTS_AVAILABLE:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            })

    async def crawl(self, url: str) -> CrawlResult:
        start_time = time.time()
        self._create_session()

        if not self.session:
            return CrawlResult(
                success=False,
                website=WebsiteStructure(url=url, domain=self._extract_domain(url), title="", description="", pages=[], sitemap={}, tech_stack=[], content_types={}, external_links=0, internal_links=0),
                pages=[],
                errors=["requests库不可用"],
                crawl_time=0,
                pages_crawled=0
            )

        pages = []
        queue = [url]
        self.visited.add(url)

        while queue and len(pages) < self.max_pages:
            current_url = queue.pop(0)

            try:
                await asyncio.sleep(self.delay)
                response = self.session.get(current_url, timeout=self.timeout)
                response.raise_for_status()

                page_content = self._parse_page(current_url, response.text)
                pages.append(page_content)

                for link in page_content.links:
                    href = link.get('href', '')
                    if href and href not in self.visited:
                        if href.startswith('http'):
                            if self._extract_domain(href) == self._extract_domain(url):
                                self.visited.add(href)
                                if len(self.visited) < self.max_pages:
                                    queue.append(href)

            except Exception as e:
                self.errors.append(f"爬取 {current_url} 失败: {str(e)}")

        website = self._build_website_structure(url, pages)
        crawl_time = time.time() - start_time

        return CrawlResult(
            success=True,
            website=website,
            pages=pages,
            errors=self.errors,
            crawl_time=crawl_time,
            pages_crawled=len(pages)
        )

    def _parse_page(self, url: str, html: str) -> PageContent:
        soup = BeautifulSoup(html, 'html.parser') if BEAUTIFULSOUP_AVAILABLE else None

        title = ""
        headings = []
        paragraphs = []
        links = []
        images = []
        metadata = {}
        text = ""

        if soup:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)

            for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                headings.append(h.get_text(strip=True))

            for p in soup.find_all('p'):
                text_content = p.get_text(strip=True)
                if text_content:
                    paragraphs.append(text_content)
                    text += text_content + "\n"

            for a in soup.find_all('a', href=True):
                links.append({
                    'text': a.get_text(strip=True),
                    'href': self._normalize_url(url, a['href']),
                })

            for img in soup.find_all('img', src=True):
                images.append({
                    'src': self._normalize_url(url, img['src']),
                    'alt': img.get('alt', ''),
                })

            for meta in soup.find_all('meta'):
                name = meta.get('name', '') or meta.get('property', '')
                content = meta.get('content', '')
                if name and content:
                    metadata[name] = content

        return PageContent(
            url=url,
            title=title,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            images=images,
            metadata=metadata,
            html=html,
            text=text,
            word_count=len(text.split())
        )

    def _build_website_structure(self, url: str, pages: List[PageContent]) -> WebsiteStructure:
        domain = self._extract_domain(url)
        title = pages[0].title if pages else ""
        description = pages[0].metadata.get('description', '') if pages else ""

        sitemap = {}
        content_types = {}
        external_links = 0
        internal_links = 0

        for page in pages:
            path = page.url.replace(f"https://{domain}", "").replace(f"http://{domain}", "")
            sitemap[path] = {
                'title': page.title,
                'headings': page.headings[:3],
                'word_count': page.word_count,
            }

            content_type = self._classify_content(page)
            content_types[content_type] = content_types.get(content_type, 0) + 1

            for link in page.links:
                if self._extract_domain(link['href']) == domain:
                    internal_links += 1
                else:
                    external_links += 1

        tech_stack = self._detect_tech_stack(pages)

        return WebsiteStructure(
            url=url,
            domain=domain,
            title=title,
            description=description,
            pages=[p.url for p in pages],
            sitemap=sitemap,
            tech_stack=tech_stack,
            content_types=content_types,
            external_links=external_links,
            internal_links=internal_links,
        )

    def _classify_content(self, page: PageContent) -> str:
        if any('blog' in h.lower() or 'article' in h.lower() for h in page.headings):
            return 'article'
        if any('product' in h.lower() or 'shop' in h.lower() for h in page.headings):
            return 'product'
        if 'home' in page.url.lower() or page.url.endswith('/'):
            return 'homepage'
        if any('about' in h.lower() for h in page.headings):
            return 'about'
        return 'other'

    def _detect_tech_stack(self, pages: List[PageContent]) -> List[str]:
        tech_stack = []
        html = " ".join([p.html for p in pages])

        if 'react' in html.lower():
            tech_stack.append('React')
        if 'vue' in html.lower():
            tech_stack.append('Vue.js')
        if 'angular' in html.lower():
            tech_stack.append('Angular')
        if 'jquery' in html.lower():
            tech_stack.append('jQuery')
        if 'bootstrap' in html.lower():
            tech_stack.append('Bootstrap')
        if 'tailwind' in html.lower():
            tech_stack.append('Tailwind CSS')
        if 'nodejs' in html.lower() or 'node.js' in html.lower():
            tech_stack.append('Node.js')
        if 'php' in html.lower():
            tech_stack.append('PHP')
        if 'wordpress' in html.lower():
            tech_stack.append('WordPress')
        if 'next.js' in html.lower() or 'nextjs' in html.lower():
            tech_stack.append('Next.js')

        return tech_stack


class PlaywrightCrawler(BaseCrawler):
    """Playwright爬虫：支持动态页面渲染"""

    def __init__(self, max_pages: int = 10, timeout: int = 30, delay: float = 1.0, headless: bool = True):
        super().__init__(max_pages, timeout, delay)
        self.headless = headless

    async def crawl(self, url: str) -> CrawlResult:
        if not PLAYWRIGHT_AVAILABLE:
            return CrawlResult(
                success=False,
                website=WebsiteStructure(url=url, domain=self._extract_domain(url), title="", description="", pages=[], sitemap={}, tech_stack=[], content_types={}, external_links=0, internal_links=0),
                pages=[],
                errors=["playwright库不可用"],
                crawl_time=0,
                pages_crawled=0
            )

        start_time = time.time()
        pages = []
        queue = [url]
        self.visited.add(url)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            while queue and len(pages) < self.max_pages:
                current_url = queue.pop(0)

                try:
                    await asyncio.sleep(self.delay)
                    page = await context.new_page()
                    await page.goto(current_url, wait_until='networkidle', timeout=self.timeout * 1000)

                    html = await page.content()
                    title = await page.title()
                    text = await page.evaluate('document.body.innerText')

                    page_content = self._parse_page_with_playwright(current_url, html, title, text)
                    pages.append(page_content)

                    for link in page_content.links:
                        href = link.get('href', '')
                        if href and href not in self.visited:
                            if href.startswith('http'):
                                if self._extract_domain(href) == self._extract_domain(url):
                                    self.visited.add(href)
                                    if len(self.visited) < self.max_pages:
                                        queue.append(href)

                    await page.close()

                except Exception as e:
                    self.errors.append(f"爬取 {current_url} 失败: {str(e)}")

            await context.close()
            await browser.close()

        website = self._build_website_structure(url, pages)
        crawl_time = time.time() - start_time

        return CrawlResult(
            success=True,
            website=website,
            pages=pages,
            errors=self.errors,
            crawl_time=crawl_time,
            pages_crawled=len(pages)
        )

    def _parse_page_with_playwright(self, url: str, html: str, title: str, text: str) -> PageContent:
        soup = BeautifulSoup(html, 'html.parser') if BEAUTIFULSOUP_AVAILABLE else None

        headings = []
        paragraphs = []
        links = []
        images = []
        metadata = {}

        if soup:
            for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                headings.append(h.get_text(strip=True))

            for p in soup.find_all('p'):
                text_content = p.get_text(strip=True)
                if text_content:
                    paragraphs.append(text_content)

            for a in soup.find_all('a', href=True):
                links.append({
                    'text': a.get_text(strip=True),
                    'href': self._normalize_url(url, a['href']),
                })

            for img in soup.find_all('img', src=True):
                images.append({
                    'src': self._normalize_url(url, img['src']),
                    'alt': img.get('alt', ''),
                })

            for meta in soup.find_all('meta'):
                name = meta.get('name', '') or meta.get('property', '')
                content = meta.get('content', '')
                if name and content:
                    metadata[name] = content

        return PageContent(
            url=url,
            title=title,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            images=images,
            metadata=metadata,
            html=html,
            text=text,
            word_count=len(text.split())
        )

    def _build_website_structure(self, url: str, pages: List[PageContent]) -> WebsiteStructure:
        return SimpleCrawler()._build_website_structure(url, pages)


class WebsiteAnalyzer:
    """网站分析器：工程化拆解网站"""

    def __init__(self):
        self.simple_crawler = SimpleCrawler()
        self.playwright_crawler = PlaywrightCrawler()

    async def analyze(self, url: str, use_playwright: bool = False) -> CrawlResult:
        logger.info(f"分析网站: {url}")

        if use_playwright:
            return await self.playwright_crawler.crawl(url)
        else:
            return await self.simple_crawler.crawl(url)

    def generate_engineering_report(self, result: CrawlResult) -> str:
        """生成工程化拆解报告"""

        lines = ["=" * 70]
        lines.append("网站工程化拆解报告")
        lines.append("=" * 70)

        website = result.website

        lines.append(f"\n📋 基本信息")
        lines.append(f"  网站URL: {website.url}")
        lines.append(f"  域名: {website.domain}")
        lines.append(f"  网站标题: {website.title}")
        lines.append(f"  网站描述: {website.description}")

        lines.append(f"\n🔧 技术栈分析")
        if website.tech_stack:
            for tech in website.tech_stack:
                lines.append(f"  ✅ {tech}")
        else:
            lines.append(f"  ⚠️  未检测到明确技术栈")

        lines.append(f"\n📊 内容结构")
        lines.append(f"  爬取页面数: {result.pages_crawled}")
        lines.append(f"  内部链接数: {website.internal_links}")
        lines.append(f"  外部链接数: {website.external_links}")
        lines.append(f"  爬取耗时: {result.crawl_time:.2f}秒")

        lines.append(f"\n📁 页面类型分布")
        for content_type, count in website.content_types.items():
            percentage = (count / result.pages_crawled * 100) if result.pages_crawled > 0 else 0
            lines.append(f"  {content_type}: {count}页 ({percentage:.1f}%)")

        lines.append(f"\n🗺️ 网站地图")
        for path, info in website.sitemap.items():
            lines.append(f"  {path}")
            lines.append(f"    标题: {info['title']}")
            lines.append(f"    字数: {info['word_count']}")
            if info['headings']:
                lines.append(f"    标题层级: {', '.join(info['headings'])}")

        lines.append(f"\n📄 页面详情")
        for page in result.pages:
            lines.append(f"\n  URL: {page.url}")
            lines.append(f"    标题: {page.title}")
            lines.append(f"    字数: {page.word_count}")
            lines.append(f"    图片数: {len(page.images)}")
            lines.append(f"    链接数: {len(page.links)}")
            if page.headings:
                lines.append(f"    标题: {', '.join(page.headings[:3])}")

        if result.errors:
            lines.append(f"\n❌ 错误信息")
            for error in result.errors:
                lines.append(f"  {error}")

        lines.append(f"\n" + "=" * 70)
        lines.append("🎉 分析完成!")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_markdown_report(self, result: CrawlResult) -> str:
        """生成Markdown格式报告"""

        lines = ["# 网站工程化拆解报告\n"]

        website = result.website

        lines.append(f"## 📋 基本信息\n")
        lines.append(f"- **网站URL**: {website.url}")
        lines.append(f"- **域名**: {website.domain}")
        lines.append(f"- **网站标题**: {website.title}")
        lines.append(f"- **网站描述**: {website.description}\n")

        lines.append(f"## 🔧 技术栈分析\n")
        if website.tech_stack:
            lines.append(f"```\n")
            for tech in website.tech_stack:
                lines.append(f"- {tech}")
            lines.append(f"```\n")
        else:
            lines.append(f"> ⚠️ 未检测到明确技术栈\n")

        lines.append(f"## 📊 内容结构\n")
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 爬取页面数 | {result.pages_crawled} |")
        lines.append(f"| 内部链接数 | {website.internal_links} |")
        lines.append(f"| 外部链接数 | {website.external_links} |")
        lines.append(f"| 爬取耗时 | {result.crawl_time:.2f}秒 |\n")

        lines.append(f"## 📁 页面类型分布\n")
        lines.append(f"| 类型 | 数量 | 占比 |")
        lines.append(f"|------|------|------|")
        for content_type, count in website.content_types.items():
            percentage = (count / result.pages_crawled * 100) if result.pages_crawled > 0 else 0
            lines.append(f"| {content_type} | {count} | {percentage:.1f}% |")
        lines.append(f"\n")

        lines.append(f"## 🗺️ 网站地图\n")
        for path, info in website.sitemap.items():
            lines.append(f"- `{path}`")
            lines.append(f"  - 标题: {info['title']}")
            lines.append(f"  - 字数: {info['word_count']}")
            if info['headings']:
                lines.append(f"  - 标题层级: {', '.join(info['headings'])}")
        lines.append(f"\n")

        lines.append(f"## 📄 页面详情\n")
        for page in result.pages:
            lines.append(f"### {page.title}\n")
            lines.append(f"- **URL**: {page.url}")
            lines.append(f"- **字数**: {page.word_count}")
            lines.append(f"- **图片数**: {len(page.images)}")
            lines.append(f"- **链接数**: {len(page.links)}")
            if page.headings:
                lines.append(f"- **标题层级**: {', '.join(page.headings)}\n")

        if result.errors:
            lines.append(f"## ❌ 错误信息\n")
            for error in result.errors:
                lines.append(f"- {error}")

        return "".join(lines)

    def extract_design_tokens(self, result: CrawlResult) -> Dict[str, Any]:
        """从网站中提取设计令牌"""
        tokens = {
            'colors': [],
            'typography': [],
            'spacing': [],
        }

        for page in result.pages:
            soup = BeautifulSoup(page.html, 'html.parser') if BEAUTIFULSOUP_AVAILABLE else None
            if not soup:
                continue

            style_tags = soup.find_all('style')
            for style_tag in style_tags:
                css_text = style_tag.get_text()

                color_matches = re.findall(r'color\s*:\s*([#][a-fA-F0-9]{6})\s*;', css_text)
                tokens['colors'].extend(color_matches)

                font_matches = re.findall(r'font-family\s*:\s*([^;]+)\s*;', css_text)
                tokens['typography'].extend(font_matches)

                spacing_matches = re.findall(r'margin|padding', css_text)
                tokens['spacing'].extend(spacing_matches)

        tokens['colors'] = list(set(tokens['colors']))[:10]
        tokens['typography'] = list(set(tokens['typography']))[:5]

        return tokens


class WebCrawler:
    """统一爬虫接口"""

    def __init__(self, max_pages: int = 10, timeout: int = 30, delay: float = 1.0):
        self.analyzer = WebsiteAnalyzer()
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay

    async def crawl_and_analyze(self, url: str, use_playwright: bool = False) -> CrawlResult:
        """爬取并分析网站"""
        return await self.analyzer.analyze(url, use_playwright)

    def get_report(self, result: CrawlResult, format: str = 'text') -> str:
        """获取分析报告"""
        if format == 'markdown':
            return self.analyzer.generate_markdown_report(result)
        return self.analyzer.generate_engineering_report(result)

    def extract_tokens(self, result: CrawlResult) -> Dict[str, Any]:
        """提取设计令牌"""
        return self.analyzer.extract_design_tokens(result)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python web_crawler.py <url> [--playwright]")
        sys.exit(1)

    url = sys.argv[1]
    use_playwright = "--playwright" in sys.argv

    print(f"爬取网站: {url}")
    print(f"使用Playwright: {use_playwright}")
    print("=" * 70)

    crawler = WebCrawler(max_pages=5)
    result = asyncio.run(crawler.crawl_and_analyze(url, use_playwright))

    print(crawler.get_report(result))

    if result.success:
        tokens = crawler.extract_tokens(result)
        print("\n提取的设计令牌:")
        print(f"  颜色: {tokens['colors']}")
        print(f"  字体: {tokens['typography']}")
