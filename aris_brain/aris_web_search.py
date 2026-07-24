"""
Aris Web Search Engine — 联网检索系统
======================================
配合 Hermes 为 Aris 提供实时联网检索能力。

后端:
  1. Web Search (DuckDuckGo HTML, 免费零API Key)
  2. arXiv API (学术论文)
  3. Semantic Scholar (引用+关联)
  4. QVDB 本地知识库 (8981条)
  5. CodeGraph 代码搜索

融合:
  多源并行检索 → 去重排序 → 量子核精炼 → Aris格式化输出

使用:
  from aris_web_search import ArisWebSearch
  sw = ArisWebSearch()
  result = sw.search("量子机器学习最新进展")
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json, hashlib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


@dataclass
class WebResult:
    """统一搜索结果"""
    title: str
    url: str
    snippet: str
    source: str           # web | arxiv | scholar | qvdb | codegraph
    score: float = 0.5
    published: str = ""
    authors: str = ""
    metadata: Dict = field(default_factory=dict)


class WebSearcher:
    """DuckDuckGo HTML 搜索 — 零 API Key"""

    @staticmethod
    def search(query: str, max_results: int = 8) -> List[WebResult]:
        """DuckDuckGo HTML 搜索 — 多重解析"""
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": query}).encode()
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')

            results = []
            # 多重解析模式
            # 模式1: class="result__a" / "result__snippet"
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html)

            if titles and len(titles) >= 2:
                for i in range(min(max_results, len(titles))):
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                    if title and len(title) > 3:
                        results.append(WebResult(
                            title=title, url="", snippet=snippet[:300],
                            source="web", score=0.7 - i * 0.05))
            else:
                # 模式2: 通用链接提取
                links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html)
                texts = re.findall(r'<[^>]+>([^<]{20,200})[^<]*</', html)
                count = 0
                for link_url, link_text in links[:max_results]:
                    title = re.sub(r'<[^>]+>', '', link_text).strip()
                    if len(title) > 10 and not any(d in link_url for d in ['duckduckgo','ad.','sponsored']):
                        results.append(WebResult(
                            title=title[:120], url=link_url, snippet="",
                            source="web", score=0.6 - count * 0.05))
                        count += 1
                        if count >= max_results: break

            return results
        except Exception:
            return []


class ArxivSearcher:
    """arXiv API 搜索"""

    @staticmethod
    def search(query: str, max_results: int = 5) -> List[WebResult]:
        try:
            params = {
                "search_query": f"all:{query}",
                "max_results": max_results,
                "sortBy": "relevance",
            }
            url = f"https://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Aris/1.0"})
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8')

            ns = {'a': 'http://www.w3.org/2005/Atom',
                  'opensearch': 'http://a9.com/-/spec/opensearch/1.1/'}
            root = ET.fromstring(data)
            results = []
            try:
                for i, entry in enumerate(root.findall('a:entry', ns)):
                    title = entry.find('a:title', ns)
                    summary = entry.find('a:summary', ns)
                    aid = entry.find('a:id', ns)
                    published = entry.find('a:published', ns)
                    authors = entry.findall('a:author', ns)

                    if title is not None:
                        arxiv_id = aid.text.strip().split('/abs/')[-1] if aid is not None else ""
                        author_names = ", ".join(
                            a.find('a:name', ns).text
                            for a in authors[:3]
                            if a.find('a:name', ns) is not None
                        )
                        results.append(WebResult(
                            title=title.text.strip().replace('\n', ' ')[:200],
                            url=f"https://arxiv.org/abs/{arxiv_id}",
                            snippet=summary.text.strip()[:300] if summary is not None else "",
                            source="arxiv", score=0.85 - i * 0.08,
                            published=published.text[:10] if published is not None else "",
                            authors=author_names,
                            metadata={"arxiv_id": arxiv_id},
                        ))
            except ET.ParseError:
                # XML 解析失败, 用正则回退
                titles = re.findall(r'<title>(.*?)</title>', data)
                summaries = re.findall(r'<summary>(.*?)</summary>', data)
                ids = re.findall(r'<id>.*?/(abs/\d+\.\d+)</id>', data)
                for i in range(min(max_results, len(titles)-1)):
                    t = titles[i+1] if i+1 < len(titles) else ""  # skip feed title
                    s = summaries[i] if i < len(summaries) else ""
                    aid = ids[i] if i < len(ids) else ""
                    if t:
                        results.append(WebResult(
                            title=t.strip().replace('\n',' ')[:200],
                            url=f"https://arxiv.org/{aid}" if aid else "",
                            snippet=s.strip()[:300], source="arxiv",
                            score=0.85 - i * 0.08,
                            metadata={"arxiv_id": aid.split('/')[-1] if aid else ""},
                        ))

            return results
        except Exception:
            return []


class QVDBSearcher:
    """QVDB 本地知识库搜索"""

    def __init__(self):
        self._db = None

    def _lazy(self):
        if self._db is None:
            try:
                from quantum_vector_db import QuantumVectorDB
                self._db = QuantumVectorDB()
            except:
                self._db = None

    def search(self, query: str, max_results: int = 5) -> List[WebResult]:
        self._lazy()
        if not self._db:
            return []

        try:
            r = self._db.search(query, top_k=max_results)
            results = []
            for res in r.get("results", []):
                results.append(WebResult(
                    title=res.text[:80],
                    url="",
                    snippet=res.text[:300],
                    source=f"qvdb_{res.source}",
                    score=res.score,
                ))
            return results
        except:
            return []


class ArisWebSearch:
    """
    Aris 联网搜索引擎 — 多源融合检索

    用法:
      sw = ArisWebSearch()
      result = sw.search("量子机器学习", sources=["web", "arxiv", "qvdb"])
      logger.info(result["summary"])
    """

    def __init__(self):
        self._web = WebSearcher()
        self._arxiv = ArxivSearcher()
        self._qvdb = QVDBSearcher()
        self._v7 = None
        self._cache = {}

    def _lazy_encoder(self):
        if self._v7 is None:
            from semantic_engine import get_encoder
            self._v7 = get_encoder(1024)

    def search(self, query: str, max_results: int = 12,
               sources: List[str] = None) -> Dict:
        """
        多源并行检索

        Args:
            query: 搜索词
            max_results: 总返回条数
            sources: 数据源列表 (默认全部: web, arxiv, qvdb)

        Returns:
            {results, summary, sources_used, latency_ms, query}
        """
        t0 = time.perf_counter()
        if sources is None:
            sources = ["web", "arxiv", "qvdb"]

        # 检查缓存
        cache_key = f"{query}:{','.join(sources)}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["ts"] < 300:  # 5分钟缓存
                return cached["data"]

        # 并行搜索
        all_results = []
        futures = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            if "web" in sources:
                futures["web"] = executor.submit(self._web.search, query, 8)
            if "arxiv" in sources:
                futures["arxiv"] = executor.submit(self._arxiv.search, query, 5)
            if "qvdb" in sources:
                futures["qvdb"] = executor.submit(self._qvdb.search, query, 5)

            for src, future in futures.items():
                try:
                    results = future.result(timeout=15)
                    all_results.extend(results)
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: -x.score):
            fp = (r.title + r.snippet)[:80]
            if fp not in seen:
                seen.add(fp)
                unique.append(r)
                if len(unique) >= max_results:
                    break

        # 生成摘要
        summary = self._generate_summary(query, unique)

        result = {
            "results": unique,
            "summary": summary,
            "sources_used": list(futures.keys()),
            "total_found": len(all_results),
            "unique_results": len(unique),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "query": query,
        }

        # 缓存
        self._cache[cache_key] = {"ts": time.time(), "data": result}

        return result

    def _generate_summary(self, query: str, results: List[WebResult]) -> str:
        """生成搜索摘要"""
        if not results:
            return f"未找到关于「{query}」的相关结果。"

        parts = [f"## 「{query}」搜索结果\n"]

        # 按来源分类
        by_source = {}
        for r in results:
            by_source.setdefault(r.source, []).append(r)

        source_names = {
            "web": "🌐 网络", "arxiv": "📄 学术",
            "qvdb_quantum_matrix": "🧠 知识库",
            "qvdb_quantum_semantica": "⚡ 推理规则",
            "codegraph": "💻 代码",
        }

        for src, items in by_source.items():
            name = source_names.get(src, src)
            parts.append(f"\n### {name} ({len(items)}条)\n")
            for item in items[:3]:
                parts.append(f"- **{item.title[:80]}**")
                if item.url:
                    parts.append(f"  [{item.url[:60]}]")
                if item.snippet:
                    parts.append(f"  {item.snippet[:150]}")
                if item.authors:
                    parts.append(f"  *{item.authors}* — {item.published}")
                parts.append("")

        return "\n".join(parts)

    def search_simple(self, query: str) -> str:
        """便利方法: 只返回摘要文本"""
        r = self.search(query)
        return r["summary"]

    def quick_fact(self, query: str) -> Optional[str]:
        """快速查事实: 返回最相关的一条"""
        r = self.search(query, max_results=3)
        if r["results"]:
            return r["results"][0].snippet[:300]
        return None


# ================================================================
# Aris 检索输出系统 — 挂载到 Hermes
# ================================================================

class ArisRetrievalSystem:
    """
    Aris 检索输出系统 — Hermes 集成入口

    使用:
      ars = ArisRetrievalSystem()
      output = ars.answer("量子核最新进展")
      # → 自动判断联网/本地, 返回格式化回答
    """

    def __init__(self):
        self._web = ArisWebSearch()
        self._reasoner = None
        self._pipeline = None

    def _lazy_reasoner(self):
        if self._reasoner is None:
            try:
                from quantum_graph_reasoning import QGRE
                self._reasoner = QGRE()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def _lazy_pipeline(self):
        if self._pipeline is None:
            try:
                from unified_cognitive_pipeline import UnifiedCognitivePipeline
                self._pipeline = UnifiedCognitivePipeline()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def answer(self, question: str, allow_web: bool = True) -> Dict:
        """
        智能回答 — 自动路由

        1. 短问候 → 本地管线 (L0情感)
        2. 知识问答 → 本地知识库 (L1/L2)
        3. 实时信息/最新 → 联网搜索
        4. 代码查询 → CodeGraph
        """
        t0 = time.perf_counter()

        # 判断是否需要联网
        realtime_keywords = ["最新", "2025", "2026", "今天", "最近", "新闻",
                            "进展", "发布", "刚刚", "当前"]
        needs_web = allow_web and any(k in question for k in realtime_keywords)

        # 短查询走本地
        if len(question.strip()) <= 3 and not needs_web:
            self._lazy_pipeline()
            if self._pipeline:
                r = self._pipeline.answer(question)
                return {"output": r["output"], "source": "local_pipeline",
                    "latency_ms": r.get("latency_ms", 0)}

        # 联网搜索
        if needs_web:
            web_r = self._web.search(question, max_results=8,
                                     sources=["web", "arxiv", "qvdb"])
            # 用量子推理精炼
            self._lazy_reasoner()
            if self._reasoner and len(web_r["summary"]) > 50:
                # 推理引擎在搜索摘要上做二次推理
                qgre_r = self._reasoner.reason(
                    f"{question} (上下文: {web_r['summary'][:500]})")
                return {
                    "output": qgre_r["output"],
                    "source": "web+qgre",
                    "web_results": len(web_r["results"]),
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                }

            return {
                "output": web_r["summary"],
                "source": "web",
                "web_results": len(web_r["results"]),
                "latency_ms": web_r["latency_ms"],
            }

        # 本地知识库
        self._lazy_reasoner()
        if self._reasoner:
            r = self._reasoner.reason(question)
            return {
                "output": r["output"],
                "source": "qgre",
                "latency_ms": r.get("ms", r.get("latency_ms", 0)),
            }

        # 兜底
        self._lazy_pipeline()
        if self._pipeline:
            r = self._pipeline.answer(question)
            return {"output": r["output"], "source": "pipeline",
                    "latency_ms": r.get("latency_ms", 0)}

        return {"output": "让我想想...", "source": "fallback", "latency_ms": 0.1}


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Aris Web Search Engine 自测")
    logger.info("=" * 60)
    sw = ArisWebSearch()

    tests = [
        ("量子机器学习", ["web", "arxiv"]),
        ("transformer attention mechanism", ["arxiv"]),
    ]

    for query, sources in tests:
        logger.info(f"\n{'─'*60}")
        r = sw.search(query, max_results=6, sources=sources)
        logger.info(f"查询: {query} | 源: {r['sources_used']} | {r['latency_ms']}ms")
        logger.info(f"找到: {r['total_found']}条 ({r['unique_results']}去重)")
        logger.info(f"\n{r['summary'][:600]}")
    logger.info(f"\n{'='*60}")
    logger.info("  Aris Retrieval System 测试")
    logger.info(f"{'='*60}")
    ars = ArisRetrievalSystem()
    for q in ["你好", "量子核原理"]:
        r = ars.answer(q, allow_web=True)
        logger.info(f"\n[{r['source']}] {q}")
        logger.info(f"  {r['output'][:200]}...")