"""
Paper Corpus Collector — 论文语料采集与知识提取
===============================================
从 arXiv + Semantic Scholar 爬取高质量论文，提取结构化知识。

目标领域:
  1. 量子机器学习 (Quantum ML)
  2. 认知架构 (Cognitive Architecture)
  3. 神经符号推理 (Neuro-symbolic Reasoning)
  4. 向量符号架构 (Vector Symbolic Architecture)
  5. 链式思维推理 (Chain-of-Thought)
  6. 意识理论 (Consciousness Theory)

输出: aris_brain/corpus/papers/ 下的结构化JSON + 知识片段
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, json, time, re, subprocess
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from write_utils import atomic_write_json

_DIR = os.path.dirname(os.path.abspath(__file__))
_CORPUS_DIR = os.path.join(_DIR, "corpus", "papers")
os.makedirs(_CORPUS_DIR, exist_ok=True)


# ================================================================
# 论文种子列表 — 手动精选的高引用论文
# ================================================================
SEED_PAPERS = {
    "cognitive_architecture": [
        "2306.14308",  # Let's Do a Thought Experiment (moral reasoning)
        "2410.03595",  # Understanding Reasoning in CoT (Hopfieldian view)
        "2503.09567",  # Towards Reasoning Era (CoT survey)
        "2601.03559",  # DiffCoT: Diffusion-styled CoT
    ],
    "quantum_reasoning": [
        "2512.14709",  # Attention as Binding: Vector-Symbolic Perspective
    ],
    "neurosymbolic": [
        "2209.08750",  # Knowledge-based Analogical Reasoning
    ],
    "vector_symbolic": [
        "2512.14709",  # Same as above — core VSA paper
    ],
    "consciousness": [
        # Will be populated from search
    ],
}

# 论文集搜索查询
SEARCH_QUERIES = [
    ("quantum kernel method reasoning", "cs.LG", 8),
    ("cognitive architecture AI consciousness", "cs.AI", 8),
    ("neuro-symbolic reasoning chain of thought", "cs.AI", 8),
    ("vector symbolic architecture binding problem", "cs.NE", 5),
    ("machine consciousness theory assessment", "cs.AI", 5),
    ("quantum feature space kernel learning", "quant-ph", 5),
]


class PaperCollector:
    """论文采集器"""

    def __init__(self):
        self._papers = []
        self._cache_file = os.path.join(_CORPUS_DIR, "paper_cache.json")
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    self._papers = json.load(f)
                logger.info(f"  缓存: {len(self._papers)} 篇论文")
            except:
                self._papers = []

    def _save_cache(self):
        with open(self._cache_file, 'w', encoding='utf-8') as f:
            atomic_write_json(self._papers, self._cache_file, ensure_ascii=False, indent=2)

    def search_arxiv(self, query: str, category: str = "cs.AI",
                     max_results: int = 10) -> List[Dict]:
        """搜索 arXiv"""
        import urllib.request
        import urllib.parse

        base_url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "max_results": max_results,
            "sortBy": "relevance",
        }
        url = f"{base_url}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Aris-Quantum/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8')

            ns = {'a': 'http://www.w3.org/2005/Atom'}
            root = ET.fromstring(data)

            papers = []
            for entry in root.findall('a:entry', ns):
                title = entry.find('a:title', ns)
                aid = entry.find('a:id', ns)
                summary = entry.find('a:summary', ns)
                published = entry.find('a:published', ns)
                authors = entry.findall('a:author', ns)

                if title is not None and aid is not None:
                    arxiv_id = aid.text.strip().split('/abs/')[-1]
                    # 跳过已缓存的
                    if any(p.get("arxiv_id") == arxiv_id for p in self._papers):
                        continue

                    paper = {
                        "arxiv_id": arxiv_id,
                        "title": title.text.strip().replace('\n', ' ')[:200],
                        "summary": summary.text.strip()[:500] if summary is not None else "",
                        "published": published.text[:10] if published is not None else "",
                        "authors": [a.find('a:name', ns).text for a in authors if a.find('a:name', ns) is not None],
                        "query": query,
                        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    papers.append(paper)
                    self._papers.append(paper)

            return papers
        except Exception as e:
            logger.error(f"  搜索失败 [{query}]: {e}")
            return []

    def fetch_by_id(self, arxiv_id: str) -> Optional[Dict]:
        """获取指定论文详情"""
        import urllib.request

        url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Aris-Quantum/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8')

            ns = {'a': 'http://www.w3.org/2005/Atom'}
            root = ET.fromstring(data)
            entry = root.find('a:entry', ns)
            if entry is None:
                return None

            title = entry.find('a:title', ns)
            summary = entry.find('a:summary', ns)
            published = entry.find('a:published', ns)
            authors = entry.findall('a:author', ns)

            return {
                "arxiv_id": arxiv_id,
                "title": title.text.strip().replace('\n', ' ')[:200] if title is not None else "",
                "summary": summary.text.strip()[:800] if summary is not None else "",
                "published": published.text[:10] if published is not None else "",
                "authors": [a.find('a:name', ns).text for a in authors if a.find('a:name', ns) is not None],
            }
        except Exception as e:
            logger.error(f"  获取失败 [{arxiv_id}]: {e}")
            return None

    def collect_all(self) -> Dict:
        """采集所有论文"""
        t0 = time.time()
        total_new = 0

        # 1. 搜索所有查询
        logger.info("\n=== 搜索论文 ===")
        for query, category, max_r in SEARCH_QUERIES:
            logger.info(f"  搜索: {query[:50]}...")
            papers = self.search_arxiv(query, category, max_r)
            total_new += len(papers)
            logger.info(f"    新增: {len(papers)}篇")
            time.sleep(1)  # 遵守rate limit

        # 2. 获取种子论文
        logger.info("\n=== 获取种子论文 ===")
        for domain, ids in SEED_PAPERS.items():
            for aid in ids:
                if any(p.get("arxiv_id") == aid for p in self._papers):
                    continue
                logger.info(f"  获取: {aid} ({domain})")
                paper = self.fetch_by_id(aid)
                if paper:
                    paper["domain"] = domain
                    self._papers.append(paper)
                    total_new += 1
                time.sleep(0.5)

        self._save_cache()

        dt = (time.time() - t0) * 1000
        return {
            "total_papers": len(self._papers),
            "new_papers": total_new,
            "elapsed_ms": dt,
        }


class PaperKnowledgeExtractor:
    """从论文摘要提取结构化知识"""

    # 提取模式
    EXTRACTION_PATTERNS = [
        ("definition", r"(?:定义|提出|propose|introduce|定义|define)\s*[:：]?\s*(.{20,200}?)(?:[。.]|$)"),
        ("method", r"(?:方法|approach|method|framework)\s*[:：]?\s*(.{20,200}?)(?:[。.]|$)"),
        ("result", r"(?:结果|发现|show|demonstrate|achieve|outperform)\s*[:：]?\s*(.{20,200}?)(?:[。.]|$)"),
        ("insight", r"(?:关键|核心|insight|key|importantly)\s*[:：]?\s*(.{20,200}?)(?:[。.]|$)"),
    ]

    def extract_from_paper(self, paper: Dict) -> List[Dict]:
        """从论文提取结构化知识片段"""
        summary = paper.get("summary", "")
        knowledge = []

        # 模式匹配
        for ktype, pattern in self.EXTRACTION_PATTERNS:
            matches = re.findall(pattern, summary, re.IGNORECASE)
            for m in matches[:2]:
                knowledge.append({
                    "type": ktype,
                    "text": m.strip()[:300],
                    "paper": paper.get("title", "")[:100],
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "authors": ", ".join(paper.get("authors", [])[:2]),
                })

        # 如果摘要没有匹配，用前两句话
        if not knowledge:
            sentences = re.split(r'[。.](?=\s)', summary)
            for s in sentences[:2]:
                if len(s.strip()) > 30:
                    knowledge.append({
                        "type": "summary",
                        "text": s.strip()[:200],
                        "paper": paper.get("title", "")[:100],
                        "arxiv_id": paper.get("arxiv_id", ""),
                    })

        return knowledge

    def extract_all(self, papers: List[Dict]) -> List[Dict]:
        """批量提取"""
        all_knowledge = []
        for paper in papers:
            k = self.extract_from_paper(paper)
            all_knowledge.extend(k)
        return all_knowledge


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Paper Corpus Collector 自测")
    logger.info("=" * 60)
    collector = PaperCollector()
    result = collector.collect_all()
    logger.info(f"\n  采集完成: 总计{result['total_papers']}篇, 新增{result['new_papers']}篇, {result['elapsed_ms']:.0f}ms")
    if collector._papers:
        extractor = PaperKnowledgeExtractor()
        knowledge = extractor.extract_all(collector._papers[:10])
        logger.info(f"\n  提取知识: {len(knowledge)}条")
        for k in knowledge[:5]:
            logger.info(f"  [{k['type']}] {k['text'][:80]}...")