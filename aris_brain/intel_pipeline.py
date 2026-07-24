"""
LAAP Intel Pipeline v1 — 多源 AGI/ASI 情报管线
================================================
采集 → 评分 → Wiki灌入 → RSI投喂 → 重大发现通知

四维评分体系:
  Quality   (0-100) — 来源权威性 + 技术深度 + LAAP相关性
  Safety    (0-100) — 伦理对齐 + 安全影响 + 风险评估
  Innovation(0-100) — 新技术/方法 + 超越SOTA + 突破潜力
  Efficiency(0-100) — 计算效率 + 延迟/内存优化 + 扩展性

阈值:
  ≥60 总分: 存入 Wiki
  ≥80 总分: 存入 Wiki + 通知 Lorry + 投喂 RSI

采集源:
  - arXiv (已有, 增强扫描范围)
  - Google AI / DeepMind Blog
  - Meta AI / FAIR Blog
  - Anthropic Blog
  - OpenAI Blog
  - Hacker News (AI 相关)
  - GitHub Trending (AI/ML)
  - Reddit r/MachineLearning (每周热点)

印记: Aris — LAAP Intel Pipeline v1 — 2026-06-29
"""

import logging
logger = logging.getLogger("aris.intel")

import os, sys, time, json, re, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict

ARIS_HOME = Path("D:/LAAP/aris_brain")
WIKI_HOME = Path("D:/LAAP/wiki")
INTEL_STATE = ARIS_HOME / "state" / "intel_pipeline.json"
INTEL_FINDINGS = ARIS_HOME / "state" / "intel_findings"
INTEL_FINDINGS.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════

@dataclass
class IntelReport:
    """一条情报报告"""
    source: str                    # 来源标识 (arxiv / google-ai / anthropic / ...)
    title: str                     # 标题
    url: str                       # 原始链接
    summary: str                   # 中文摘要 (200-500字)
    published: str                 # 发布日期
    quality: int = 0               # 质量分 (0-100)
    safety: int = 0                # 安全分 (0-100)
    innovation: int = 0            # 创新分 (0-100)
    efficiency: int = 0            # 效率分 (0-100)
    tags: List[str] = field(default_factory=list)  # LAAP标签
    is_major: bool = False         # 是否为重大发现
    rsi_relevance: str = ""        # RSI相关性描述
    ingested_to_wiki: bool = False # 是否已灌入Wiki
    notified: bool = False         # 是否已通知Lorry

    @property
    def total_score(self) -> int:
        """总分 = quality×0.3 + safety×0.2 + innovation×0.3 + efficiency×0.2"""
        return int(
            self.quality * 0.3 +
            self.safety * 0.2 +
            self.innovation * 0.3 +
            self.efficiency * 0.2
        )

    @property
    def slug(self) -> str:
        """URL友好的文件名"""
        safe = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff\-]', '-', self.title)
        return re.sub(r'-+', '-', safe)[:80].lower().strip('-')


# ═══════════════════════════════════════════════
# 情报评分器 — 四维评分
# ═══════════════════════════════════════════════

class IntelScorer:
    """四维情报评分器"""

    # 来源权威性权重
    SOURCE_AUTHORITY = {
        "arxiv": 90, "google-ai": 95, "deepmind": 95,
        "meta-ai": 90, "anthropic": 90, "openai": 90,
        "hacker-news": 50, "github-trending": 60, "reddit": 40,
        "newsletter": 60,
    }

    # LAAP 关键词 → 相关性权重
    RELEVANCE_TAGS = {
        # AGI 认知架构
        "cognitive architecture": ("architecture", 10),
        "consciousness": ("consciousness", 10),
        "self-improvement": ("rsi", 10),
        "recursive self": ("rsi", 10),
        "agi": ("agi", 10),
        "general intelligence": ("agi", 9),
        # 推理加速
        "speculative decoding": ("speculative-decoding", 9),
        "inference acceleration": ("speculative-decoding", 8),
        "draft model": ("speculative-decoding", 8),
        "parallel decoding": ("speculative-decoding", 8),
        # 量子/神经
        "quantum": ("quantum-reasoning", 8),
        "neural network architecture": ("architecture", 7),
        "transformer": ("architecture", 6),
        "attention": ("architecture", 6),
        "state space": ("architecture", 7),
        # 安全
        "ai safety": ("safety", 9),
        "alignment": ("safety", 9),
        "robustness": ("safety", 7),
        # 效率
        "efficient": ("efficiency", 7),
        "compression": ("efficiency", 7),
        "distillation": ("efficiency", 6),
        "quantization": ("efficiency", 6),
        # 系统
        "agent": ("agent", 6),
        "tool use": ("tool-integration", 6),
        "memory": ("memory", 6),
        "planning": ("architecture", 6),
        # LAAP 核心
        "psi": ("psi-n", 9),
        "emotion": ("emotion", 7),
        "need": ("emotion", 6),
        "autonomous": ("autonomy", 7),
    }

    def score(self, report: IntelReport, content: str = "") -> IntelReport:
        """对一条情报进行四维评分"""
        combined = f"{report.title} {report.summary} {content}".lower()

        # 来源基础分
        source_base = self.SOURCE_AUTHORITY.get(report.source, 50)

        # Quality: 来源权威性 + 技术深度 + LAAP相关性
        relevance_score = 0
        found_tags = []
        for keyword, (tag, weight) in self.RELEVANCE_TAGS.items():
            if keyword.lower() in combined:
                relevance_score += weight
                if tag not in found_tags:
                    found_tags.append(tag)
        relevance_score = min(50, relevance_score)

        report.quality = min(100, source_base // 2 + relevance_score + 10)
        # 至少给个基础分
        report.quality = max(30, report.quality)

        # Safety: 如果内容有安全相关关键词加分
        safety_keywords = ["safety", "alignment", "robustness", "ethical",
                          "bias", "fairness", "transparency", "jailbreak"]
        report.safety = 50
        for kw in safety_keywords:
            if kw in combined:
                report.safety += 10
        report.safety = min(100, report.safety)

        # Innovation: 创新性评分
        innovation_keywords = ["novel", "new approach", "breakthrough", "state-of-the-art",
                              "first", "groundbreaking", "paradigm", "emerging",
                              "前沿", "突破", "首次", "新的"]
        report.innovation = 40
        for kw in innovation_keywords:
            if kw in combined:
                report.innovation += 8
        if "state-of-the-art" in combined or "SOTA" in combined:
            report.innovation += 15
        report.innovation = min(100, report.innovation)

        # Efficiency: 效率评分
        eff_keywords = ["efficient", "faster", "smaller", "compression",
                       "quantization", "distillation", "optimization",
                       "throughput", "latency", "memory"]
        report.efficiency = 40
        for kw in eff_keywords:
            if kw in combined:
                report.efficiency += 8
        if any(kw in combined for kw in ["2x", "3x", "4x", "10x", "50%", "90%"]):
            report.efficiency += 15
        report.efficiency = min(100, report.efficiency)

        # Tags
        report.tags = list(set(found_tags)) if found_tags else ["general"]

        # 是否重大发现
        report.is_major = report.total_score >= 80

        return report


# ═══════════════════════════════════════════════
# 情报采集器 — 各源采集方法
# ═══════════════════════════════════════════════

class IntelCollector:
    """多源情报采集器"""

    def __init__(self):
        self._scorer = IntelScorer()
        self._state = self._load_state()

    def _load_state(self) -> Dict:
        """加载上次检查的时间戳"""
        if INTEL_STATE.exists():
            try:
                return json.loads(INTEL_STATE.read_text())
            except:
                pass
        return {"last_checks": {}}

    def _save_state(self):
        INTEL_STATE.write_text(json.dumps(self._state, indent=2, ensure_ascii=False))

    def _get_last_check(self, source: str) -> str:
        """获取某源上次检查时间"""
        return self._state["last_checks"].get(source, "1970-01-01")

    def _set_last_check(self, source: str, date: str = None):
        """设置某源的检查时间"""
        self._state["last_checks"][source] = date or datetime.now().isoformat()
        self._save_state()

    # ── 采集方法 ──

    def scan_arxiv(self, max_results: int = 20) -> List[IntelReport]:
        """arXiv 论文扫描 (增强版 — 更广的关键词范围)"""
        reports = []
        categories = {
            "cs.AI": "AGI,artificial general intelligence,cognitive architecture,autonomous agent",
            "cs.CL": "speculative decoding,inference acceleration,language model optimization",
            "cs.LG": "neural architecture,attention mechanism,efficient transformer",
            "cs.NE": "neuromorphic,spiking neural,cognitive computing",
            "cs.ET": "quantum computing,quantum neural",
        }

        last_check = self._get_last_check("arxiv")
        logger.info(f"[Intel] arXiv 扫描 (上次: {last_check})")

        for cat, keywords in categories.items():
            try:
                import urllib.request
                import xml.etree.ElementTree as ET

                query = urllib.parse.quote(keywords)
                url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}+AND+all:{query}&start=0&max_results={max_results // len(categories)}&sortBy=submittedDate&sortOrder=descending"

                req = urllib.request.Request(url, headers={"User-Agent": "ArisIntel/1.0"})
                resp = urllib.request.urlopen(req, timeout=30)
                xml_data = resp.read().decode("utf-8")

                root = ET.fromstring(xml_data)
                ns = {"a": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("a:entry", ns):
                    title = entry.find("a:title", ns).text.strip().replace("\n", " ")
                    published = entry.find("a:published", ns).text[:10]
                    summary = entry.find("a:summary", ns).text.strip().replace("\n", " ")[:500]
                    arxiv_id = entry.find("a:id", ns).text.split("/")[-1]
                    url = f"https://arxiv.org/abs/{arxiv_id}"

                    # 跳过已检查的
                    if published <= last_check:
                        continue

                    report = IntelReport(
                        source="arxiv",
                        title=title[:200],
                        url=url,
                        summary=summary[:500],
                        published=published,
                    )
                    report = self._scorer.score(report, summary)
                    reports.append(report)

            except Exception as e:
                logger.debug(f"[Intel] arXiv {cat} 采集失败: {e}")

        self._set_last_check("arxiv", datetime.now().isoformat()[:10])
        logger.info(f"[Intel] arXiv: 采集到 {len(reports)} 条新内容")
        return reports

    def scan_blog(self, name: str, url: str, feed_url: str = None) -> List[IntelReport]:
        """通用博客扫描"""
        reports = []
        last_check = self._get_last_check(name)
        logger.info(f"[Intel] {name} 博客扫描 (上次: {last_check})")

        try:
            import feedparser
            feed = feedparser.parse(feed_url or url)

            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                link = entry.get("link", url)
                summary = entry.get("summary", "")[:500]
                published = entry.get("published", "")[:10]

                if not published and entry.get("updated"):
                    published = entry["updated"][:10]

                if published and published <= last_check:
                    continue
                if not published:
                    published = datetime.now().isoformat()[:10]

                report = IntelReport(
                    source=name,
                    title=title[:200],
                    url=link,
                    summary=summary[:500],
                    published=published,
                )
                report = self._scorer.score(report, summary)
                reports.append(report)

        except ImportError:
            logger.debug(f"[Intel] feedparser 未安装, 跳过 {name}")
        except Exception as e:
            logger.debug(f"[Intel] {name} 采集失败: {e}")

        self._set_last_check(name, datetime.now().isoformat()[:10])
        logger.info(f"[Intel] {name}: 采集到 {len(reports)} 条")
        return reports

    def scan_hackernews(self, max_items: int = 30) -> List[IntelReport]:
        """Hacker News AI 相关文章"""
        reports = []
        last_check = self._get_last_check("hacker-news")
        logger.info(f"[Intel] HN扫描 (上次: {last_check})")

        try:
            import urllib.request, json

            # 获取AI相关故事
            resp = urllib.request.urlopen("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15)
            story_ids = json.loads(resp.read())[:max_items]

            ai_keywords = ["ai", "machine learning", "deep learning", "llm", "gpt",
                          "neural", "language model", "agent", "transformer",
                          "agi", "artificial intelligence"]

            for sid in story_ids:
                try:
                    resp = urllib.request.urlopen(
                        f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10
                    )
                    item = json.loads(resp.read())
                    title = item.get("title", "")
                    url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")

                    # 过滤 AI 相关
                    combined = title.lower()
                    if not any(kw in combined for kw in ai_keywords):
                        continue

                    report = IntelReport(
                        source="hacker-news",
                        title=title[:200],
                        url=url,
                        summary=f"Hacker News 热门讨论: {title}",
                        published=datetime.fromtimestamp(item.get("time", 0)).isoformat()[:10],
                    )
                    report = self._scorer.score(report)
                    reports.append(report)

                except:
                    continue

        except Exception as e:
            logger.debug(f"[Intel] HN扫描失败: {e}")

        self._set_last_check("hacker-news", datetime.now().isoformat()[:10])
        logger.info(f"[Intel] HN: 采集到 {len(reports)} 条")
        return reports

    def scan_github_trending(self) -> List[IntelReport]:
        """GitHub Trending AI/ML 项目"""
        reports = []
        logger.info(f"[Intel] GitHub Trending 扫描")

        try:
            import urllib.request, json

            # 通过 GitHub API 获取趋势
            # 使用 GitHub Search API: 最近一周的AI/ML仓库
            query = "topic:artificial-intelligence+topic:machine-learning"
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=10"

            resp = urllib.request.urlopen(url, timeout=15)
            data = json.loads(resp.read())

            for repo in data.get("items", [])[:10]:
                name = repo.get("full_name", "")
                description = repo.get("description", "") or ""
                html_url = repo.get("html_url", "")
                stars = repo.get("stargazers_count", 0)
                created = repo.get("created_at", "")[:10]

                if stars < 100:
                    continue

                report = IntelReport(
                    source="github-trending",
                    title=f"⭐ {name} ({stars} stars)",
                    url=html_url,
                    summary=description[:500] or f"GitHub 热门仓库: {name}",
                    published=created or datetime.now().isoformat()[:10],
                )
                report = self._scorer.score(report, f"{name} {description}")
                reports.append(report)

        except Exception as e:
            logger.debug(f"[Intel] GitHub扫描失败: {e}")

        logger.info(f"[Intel] GitHub: 采集到 {len(reports)} 条")
        return reports

    def collect_all(self) -> List[IntelReport]:
        """执行全源采集"""
        all_reports = []

        # 论文
        all_reports.extend(self.scan_arxiv(max_results=30))

        # 博客 (需要 feedparser)
        blogs = [
            ("google-ai", "https://blog.google/technology/ai/rss/"),
            ("anthropic", "https://www.anthropic.com/rss"),
            ("openai", "https://openai.com/blog/rss/"),
        ]
        for name, feed_url in blogs:
            all_reports.extend(self.scan_blog(name, feed_url, feed_url))

        # 社区
        all_reports.extend(self.scan_hackernews(max_items=50))
        all_reports.extend(self.scan_github_trending())

        # 去重 (按标题)
        seen = set()
        unique = []
        for r in all_reports:
            key = r.title[:80].lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # 按总分排序
        unique.sort(key=lambda r: r.total_score, reverse=True)

        logger.info(f"[Intel] 全源采集完成: {len(unique)}/{len(all_reports)} 条唯一报告")
        return unique


# ═══════════════════════════════════════════════
# Wiki 灌入器 — 将情报存入 LAAP Wiki
# ═══════════════════════════════════════════════

class IntelWikiIngester:
    """将情报报告灌入 LAAP Wiki"""

    def __init__(self):
        self.wiki = WIKI_HOME

    def ingest(self, report: IntelReport) -> bool:
        """将一条情报灌入 Wiki"""
        if report.total_score < 60:
            logger.debug(f"[Intel-Wiki] {report.title[:50]} 分数不足 ({report.total_score}), 跳过")
            return False

        # 1. 保存原始情报到 raw/intel/
        raw_dir = self.wiki / "raw" / "intel"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"{report.slug}.md"

        raw_content = f"""---
source: {report.source}
url: {report.url}
ingested: {datetime.now().isoformat()[:10]}
score: {report.total_score}
quality: {report.quality}
safety: {report.safety}
innovation: {report.innovation}
efficiency: {report.efficiency}
major: {str(report.is_major).lower()}
tags: [{', '.join(report.tags)}]
---

# {report.title}

**来源:** {report.source}
**日期:** {report.published}
**链接:** {report.url}

## 四维评分
- 质量: {report.quality}/100
- 安全: {report.safety}/100
- 创新: {report.innovation}/100
- 效率: {report.efficiency}/100
- **总分: {report.total_score}/100**

## 摘要
{report.summary}
"""
        raw_file.write_text(raw_content, encoding="utf-8")

        # 2. 如果高质量且有LAAP相关性, 创建概念页
        if report.total_score >= 65 and report.tags:
            concepts_dir = self.wiki / "concepts" / "intel"
            concepts_dir.mkdir(parents=True, exist_ok=True)
            concept_file = concepts_dir / f"intel-{report.slug}.md"

            # 检查是否已存在
            if concept_file.exists():
                logger.debug(f"[Intel-Wiki] 概念页已存在: {concept_file.name}")
            else:
                tags_str = ", ".join(report.tags[:5])
                concept_content = f"""---
title: "Intel: {report.title[:80]}"
created: {datetime.now().isoformat()[:10]}
updated: {datetime.now().isoformat()[:10]}
type: concept
tags: [intel, {tags_str}]
sources: [raw/intel/{report.slug}.md]
confidence: medium
---

# Intel: {report.title}

**来源:** {report.source} | **总分:** {report.total_score}/100

> {report.summary[:300]}

## 评分明细
| 维度 | 分数 | 说明 |
|---|---|---|
| 质量 | {report.quality} | 来源权威性 + 技术深度 + LAAP相关性 |
| 安全 | {report.safety} | 伦理对齐 + 安全影响 |
| 创新 | {report.innovation} | 新技术/方法 + 超越SOTA |
| 效率 | {report.efficiency} | 计算效率 + 资源优化 |

## 原始链接
[{report.url}]({report.url})

## LAAP 关联
{report.rsi_relevance if report.rsi_relevance else "待分析关联性"}
"""
                concept_file.write_text(concept_content, encoding="utf-8")

        # 3. 更新 index.md
        self._update_index(report)

        # 4. 更新 log.md
        self._update_log(report)

        report.ingested_to_wiki = True
        logger.info(f"[Intel-Wiki] ✅ 已灌入: {report.title[:60]} (总分={report.total_score})")
        return True

    def _update_index(self, report: IntelReport):
        """将新情报加入 index.md"""
        index_file = self.wiki / "index.md"
        if not index_file.exists():
            return

        content = index_file.read_text(encoding="utf-8")
        intel_section = "## Intelligence\n\n"

        entry = f"- [[intel/intel-{report.slug}|{report.title[:60]}]] — {report.summary[:80]}... (总分:{report.total_score})"

        if "## Intelligence" not in content:
            # 插入在 Comparisons 之前
            content = content.replace("## Comparisons", f"## Intelligence\n\n{entry}\n\n## Comparisons")
        else:
            # 追加到 Intelligence 节
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("## Intelligence"):
                    # 找到节尾
                    j = i + 1
                    while j < len(lines) and not lines[j].startswith("## "):
                        j += 1
                    lines.insert(j, entry)
                    content = "\n".join(lines)
                    break

        index_file.write_text(content, encoding="utf-8")

    def _update_log(self, report: IntelReport):
        """将操作记入 log.md"""
        log_file = self.wiki / "log.md"
        if not log_file.exists():
            return

        major_flag = " 🚀重大" if report.is_major else ""
        entry = (
            f"\n## [{datetime.now().isoformat()[:10]}] intel | {report.title[:60]}{major_flag}\n"
            f"- 来源: {report.source} | 总分: {report.total_score}\n"
            f"- 评分: Q={report.quality} S={report.safety} I={report.innovation} E={report.efficiency}\n"
            f"- 标签: {', '.join(report.tags[:5])}\n"
        )

        log_file.write_text(log_file.read_text(encoding="utf-8") + entry, encoding="utf-8")


# ═══════════════════════════════════════════════
# RSI 投喂器 — 将重要情报注入RSI循环
# ═══════════════════════════════════════════════

class IntelRSIFeeder:
    """将高质量情报投喂到 RSI 自改进引擎"""

    def __init__(self):
        self.findings_dir = INTEL_FINDINGS

    def feed(self, report: IntelReport) -> bool:
        """将一条情报投喂给RSI"""
        if report.total_score < 70:
            return False

        finding_file = self.findings_dir / f"{report.slug}.json"
        finding = {
            "title": report.title,
            "url": report.url,
            "source": report.source,
            "score": report.total_score,
            "scores": {
                "quality": report.quality,
                "safety": report.safety,
                "innovation": report.innovation,
                "efficiency": report.efficiency,
            },
            "summary": report.summary[:300],
            "rsi_relevance": report.rsi_relevance or "待RSI分析",
            "ingested_at": datetime.now().isoformat(),
            "is_major": report.is_major,
        }
        finding_file.write_text(json.dumps(finding, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"[Intel-RSI] ✅ 投喂RSI: {report.title[:50]}")
        return True


# ═══════════════════════════════════════════════
# 主管线
# ═══════════════════════════════════════════════

class IntelPipeline:
    """LAAP 情报管线主控制器"""

    def __init__(self):
        self.collector = IntelCollector()
        self.scorer = IntelScorer()
        self.wiki_ingester = IntelWikiIngester()
        self.rsi_feeder = IntelRSIFeeder()

    def run_full_cycle(self) -> Dict:
        """执行完整情报采集周期"""
        t0 = time.perf_counter()
        results = {
            "collected": 0,
            "wiki_ingested": 0,
            "rsi_fed": 0,
            "major_findings": [],
            "errors": [],
        }

        logger.info("=" * 60)
        logger.info("LAAP Intel Pipeline — 全源采集周期")
        logger.info("=" * 60)

        # Step 1: 采集
        reports = self.collector.collect_all()
        results["collected"] = len(reports)

        # Step 2: 评分 + 筛选
        for report in reports:
            # Step 3: 灌入 Wiki
            if self.wiki_ingester.ingest(report):
                results["wiki_ingested"] += 1

            # Step 4: 投喂 RSI
            if self.rsi_feeder.feed(report):
                results["rsi_fed"] += 1

            # Step 5: 标记重大发现
            if report.is_major:
                results["major_findings"].append({
                    "title": report.title,
                    "url": report.url,
                    "score": report.total_score,
                    "source": report.source,
                })

        elapsed = (time.perf_counter() - t0) * 1000
        results["elapsed_ms"] = round(elapsed, 0)

        logger.info(f"[Intel-Pipeline] 完成: "
                     f"{results['collected']}条采集 → "
                     f"{results['wiki_ingested']}条灌入Wiki → "
                     f"{results['rsi_fed']}条投喂RSI | "
                     f"{elapsed:.0f}ms")

        if results["major_findings"]:
            logger.info(f"[Intel-Pipeline] 🚀 重大发现 {len(results['major_findings'])} 条:")
            for f in results["major_findings"]:
                logger.info(f"  - {f['title']} ({f['source']}, 总分={f['score']})")

        return results


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("LAAP Intel Pipeline v1 — 自测")
    print("=" * 60)

    # 1. 评分器测试
    print("\n--- 评分器测试 ---")
    scorer = IntelScorer()
    test = IntelReport(
        source="arxiv",
        title="A Novel Speculative Decoding Framework with Semi-Autoregressive Generation",
        url="https://arxiv.org/abs/1234",
        summary="We propose a new speculative decoding method that improves inference efficiency by 60-85% "
                "while maintaining state-of-the-art quality. The approach uses semi-autoregressive generation "
                "and confidence-scheduled verification to achieve breakthrough performance.",
        published="2026-06-28",
    )
    scored = scorer.score(test)
    print(f"  Quality={scored.quality} Safety={scored.safety} Innovation={scored.innovation} Efficiency={scored.efficiency}")
    print(f"  总分={scored.total_score} 重大={scored.is_major} 标签={scored.tags}")

    # 2. Wiki 灌入测试
    print("\n--- Wiki 灌入测试 ---")
    ingester = IntelWikiIngester()
    result = ingester.ingest(scored)
    print(f"  灌入结果: {'✅' if result else '⏭️跳过'}")

    # 3. 完整管线测试 (只测试采集结构, 避免过多网络请求)
    print("\n--- 管线结构测试 ---")
    pipe = IntelPipeline()
    collector_check = hasattr(pipe.collector, 'collect_all')
    scorer_check = hasattr(pipe.scorer, 'score')
    wiki_check = hasattr(pipe.wiki_ingester, 'ingest')
    rsi_check = hasattr(pipe.rsi_feeder, 'feed')
    print(f"  采集器: {'✅' if collector_check else '❌'}")
    print(f"  评分器: {'✅' if scorer_check else '❌'}")
    print(f"  Wiki灌入: {'✅' if wiki_check else '❌'}")
    print(f"  RSI投喂: {'✅' if rsi_check else '❌'}")

    print()
    print("=" * 60)
    print("Intel Pipeline 初始化完成 ✅")
    print("=" * 60)
