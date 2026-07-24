#!/usr/bin/env python3
"""
Cron job: 从arXiv自动抓取论文并扩展 PaperKnowledgeBase
类别: cs.AI, cs.CL, cs.LG, cs.NE, stat.ML
每次最多100篇/类别
"""
import sys, os, json, time, logging
from pathlib import Path
from typing import Dict, Set

BASE = Path(__file__).parent
KB_DIR = BASE / "paper_kb"

sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE.parent))

# 直接用导入 — aris_qre_v3 在 BASE 里
from aris_qre_v3 import (
    PaperKnowledgeBase,
    ArxivPaperImporter,
    PaperEntry,
    TripleEncoder,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CRON-arxiv] %(message)s",
)
log = logging.getLogger("cron.arxiv")


def load_existing_ids() -> Set[str]:
    """从 paper_meta.json 读取已有论文 ID 集合"""
    meta_path = KB_DIR / "paper_meta.json"
    if not meta_path.exists():
        log.warning("paper_meta.json 不存在，视为空库")
        return set()
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    ids = set(meta.keys())
    log.info(f"已有知识库: {len(ids)} 篇论文 (来自 paper_meta.json)")
    return ids


def reconstruct_paragraphs(kb: PaperKnowledgeBase):
    """
    从加载的 _para_texts 和 _para_sources 重建 _paragraphs 列表。
    _para_sources 格式: "arxiv_id:para_idx"
    """
    if not kb._para_texts:
        log.info("无已有段落数据")
        return
    for t, s in zip(kb._para_texts, kb._para_sources):
        parts = s.rsplit(":", 1)
        paper_id = parts[0]
        para_idx = int(parts[1]) if len(parts) > 1 else 0
        kb._paragraphs.append({
            "text": t,
            "paper_id": paper_id,
            "para_idx": para_idx,
        })
    # 同时恢复 _papers 字典的 ID 集合(用于去重)
    # 从 _para_sources 提取所有 paper_id
    paper_ids = set()
    for s in kb._para_sources:
        pid = s.rsplit(":", 1)[0]
        paper_ids.add(pid)
    # 从 paper_meta.json 恢复 _papers
    meta_path = KB_DIR / "paper_meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        # 为已存在的论文创建占位 PaperEntry（使 add_paper 能去重）
        for pid, pdata in meta.items():
            if pid not in kb._papers:
                # 创建一个轻量占位，仅用于去重
                placeholder = PaperEntry(
                    arxiv_id=pid,
                    title=pdata.get("title", ""),
                    authors=pdata.get("authors", []),
                    categories=pdata.get("categories", []),
                    abstract=pdata.get("abstract", "")[:200],
                    paragraphs=[],
                    year=pdata.get("year", 2026),
                )
                kb._papers[pid] = placeholder
    log.info(f"重建完成: {len(kb._paragraphs)} 段落, {len(kb._papers)} 篇论文")


def main():
    categories = [
        "cs.AI",
        "cs.CL",
        "cs.LG",
        "cs.NE",
        "stat.ML",
    ]

    total_new = 0
    total_before_papers = 0
    total_before_paras = 0

    # 1. 加载已有知识库
    log.info("=" * 60)
    log.info("加载已有知识库...")
    kb = PaperKnowledgeBase(dim=1024)
    loaded = kb.load()
    if loaded:
        total_before_papers = len(kb._papers)
        total_before_paras = len(kb._para_texts)
        log.info(f"KB 已加载: {total_before_papers} 篇论文(meta), {total_before_paras} 段落(向量)")
        # 重建 _paragraphs 列表
        reconstruct_paragraphs(kb)
        total_before_papers = len(kb._papers)
        total_before_paras = len(kb._paragraphs)
        log.info(f"重建后: {total_before_papers} 篇论文, {total_before_paras} 段落")
    else:
        log.info("知识库为空，将从零构建")

    # 2. 获取已有 ID 集合用于去重
    existing_ids = set(kb._papers.keys())
    log.info(f"去重集合: {len(existing_ids)} 个已存在 ID")

    # 3. 遍历每个类别
    per_cat_stats = {}
    for cat in categories:
        log.info(f"\n--- 类别: {cat} ---")
        try:
            entries = ArxivPaperImporter.fetch_by_category(category=cat, max_results=100)
        except Exception as e:
            log.error(f"  ✗ 抓取失败: {e}")
            per_cat_stats[cat] = {"fetched": 0, "new": 0, "error": str(e)}
            continue

        fetched = len(entries)
        # 去重
        new_entries = [e for e in entries if e.arxiv_id not in existing_ids]
        new_count = len(new_entries)
        dup_count = fetched - new_count
        log.info(f"  获取 {fetched} 篇, 去重后新增 {new_count} 篇 (重复 {dup_count})")

        # 添加新论文
        for entry in new_entries:
            kb.add_paper(entry)
            existing_ids.add(entry.arxiv_id)  # 防止同一类别内重复
            total_new += 1

        per_cat_stats[cat] = {"fetched": fetched, "new": new_count, "duplicates": dup_count}

    # 4. 重建向量索引
    log.info("\n" + "=" * 60)
    log.info("重建向量索引...")
    t0 = time.time()
    kb.build_index()
    build_time = time.time() - t0
    log.info(f"索引重建耗时: {build_time:.1f}s")

    # 5. 保存到磁盘
    log.info("保存知识库...")
    kb.save()

    # 输出统计
    after_papers = len(kb._papers)
    after_paras = len(kb._paragraphs)
    log.info("\n" + "=" * 60)
    log.info("运行完成!")
    log.info("=" * 60)
    log.info(f"每类别统计:")
    for cat, stats in per_cat_stats.items():
        log.info(f"  {cat}: 获取 {stats['fetched']} 篇, 新增 {stats['new']} 篇, 重复 {stats['duplicates']} 篇")
        if "error" in stats:
            log.warning(f"    ⚠ 错误: {stats['error']}")
    log.info(f"\n本轮新增论文: {total_new}")
    log.info(f"知识库总论文: {after_papers}")
    log.info(f"知识库总段落: {after_paras}")
    log.info(f"索引重建耗时: {build_time:.1f}s")

    # 打印 JSON 供 cron 消费
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "categories": per_cat_stats,
        "total_new_papers": total_new,
        "total_papers": after_papers,
        "total_paragraphs": after_paras,
        "build_time_seconds": round(build_time, 1),
    }
    print("\n---CRON_REPORT---")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("---END_REPORT---")


if __name__ == "__main__":
    main()
