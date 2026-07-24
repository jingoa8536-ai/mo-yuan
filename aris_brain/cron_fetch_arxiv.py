#!/usr/bin/env python3
"""
Cron job: 从arXiv自动抓取论文并扩展论文知识库
每轮从 cs.AI, cs.CL, cs.LG, cs.NE, stat.ML 各抓最新100篇
"""
import sys, os, time, json
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from aris_qre_v3 import PaperKnowledgeBase, ArxivPaperImporter, PaperEntry, KB_DIR, log
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [arXivFetch] %(message)s")
log = logging.getLogger("aris.cron.arxiv")

CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.NE", "stat.ML"]

def normalize_arxiv_id(raw_id: str) -> str:
    """归一化 arxiv ID: 去掉 'arXiv:' 前缀和版本号后缀"""
    rid = raw_id.replace("arXiv:", "").replace("arxiv:", "").strip()
    # 去掉版本号 v1, v2 等
    if rid and rid[-1].isdigit() and "v" in rid:
        parts = rid.rsplit("v", 1)
        if len(parts) == 2 and parts[1].isdigit():
            rid = parts[0]
    return rid


def main():
    t_start = time.time()

    kb = PaperKnowledgeBase()

    # ── 1. 加载已有知识库 ──
    loaded = kb.load()
    if loaded:
        # 重构 _paragraphs 列表 (load 只恢复了向量矩阵和文本, 未恢复 _paragraphs)
        kb._paragraphs = []
        for i, (text, source) in enumerate(zip(kb._para_texts, kb._para_sources)):
            parts = source.split(":", 1)
            paper_id = parts[0] if len(parts) > 0 else ""
            para_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            kb._paragraphs.append({
                "text": text,
                "paper_id": paper_id,
                "para_idx": para_idx,
            })

        # 从 paper_meta.json 恢复 _papers 字典 (用于去重)
        meta_path = KB_DIR / "paper_meta.json"
        n_restored = 0
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for pid, m in meta.items():
                if pid not in kb._papers:
                    # 重构该论文的段落列表
                    paras = [p["text"] for p in kb._paragraphs if p["paper_id"] == pid]
                    entry = PaperEntry(
                        arxiv_id=pid,
                        title=m.get("title", ""),
                        authors=m.get("authors", []),
                        categories=m.get("categories", []),
                        abstract=m.get("abstract", ""),
                        paragraphs=paras,
                        year=m.get("year", 2026),
                        citations=m.get("citations", 0),
                    )
                    kb._papers[pid] = entry
                    n_restored += 1

        existing_ids = set(kb._papers.keys())
        log.info(f"KB加载完成: {len(kb._papers)}篇论文 (恢复{n_restored}), {len(kb._paragraphs)}段落, "
                 f"{'向量就绪' if kb._para_matrix is not None else '无向量'}")
    else:
        existing_ids = set()
        log.info("新建知识库 (无已有数据)")

    # ── 2. 逐类别抓取 ──
    total_new = 0
    total_dup = 0
    total_api = 0
    per_cat_stats = []

    for cat in CATEGORIES:
        t_cat = time.time()
        log.info(f"正在抓取 {cat} ...")
        try:
            entries = ArxivPaperImporter.fetch_by_category(cat, max_results=100)
        except Exception as ex:
            log.error(f"  {cat} 抓取失败: {ex}")
            per_cat_stats.append(f"{cat}: ✗ {ex}")
            continue

        n_api = len(entries)
        total_api += n_api
        n_new = 0
        n_dup = 0

        for e in entries:
            eid = normalize_arxiv_id(e.arxiv_id)
            e.arxiv_id = eid

            if eid in existing_ids:
                n_dup += 1
                continue

            kb.add_paper(e)
            existing_ids.add(eid)
            n_new += 1

        elapsed = time.time() - t_cat
        total_new += n_new
        total_dup += n_dup
        per_cat_stats.append(f"{cat}: API={n_api} 新增={n_new} 重复={n_dup} ({elapsed:.1f}s)")
        log.info(f"  {cat}: API返回{n_api}篇, 新增{n_new}, 重复{n_dup} ({elapsed:.1f}s)")

    # ── 3. 重建索引 & 保存 ──
    if total_new > 0:
        log.info(f"新增{total_new}篇论文, 开始重建向量索引 ({len(kb._paragraphs)}段落)...")
        t_idx = time.time()
        kb.build_index()
        idx_time = time.time() - t_idx
        log.info(f"索引重建完成 ({idx_time:.1f}s)")

        log.info("保存到磁盘...")
        kb.save()
    else:
        log.info("无新论文, 跳过索引重建和保存")
        idx_time = 0

    # ── 4. 报告 ──
    total_time = time.time() - t_start
    n_papers = len(kb._papers)
    n_paras = len(kb._paragraphs)

    print()
    print("=" * 60)
    print("  arXiv 论文抓取报告")
    print("=" * 60)
    for stat in per_cat_stats:
        print(f"  {stat}")
    print()
    print(f"  API总返回:   {total_api} 篇")
    print(f"  本次新增:    {total_new} 篇")
    print(f"  跳过重复:    {total_dup} 篇")
    print(f"  总论文数:    {n_papers} 篇")
    print(f"  总段落数:    {n_paras} 段")
    print(f"  向量索引:    {'已就绪' if kb._para_matrix is not None else '未构建'}")
    if total_new > 0:
        print(f"  索引耗时:    {idx_time:.1f}s")
    print(f"  总耗时:      {total_time:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
