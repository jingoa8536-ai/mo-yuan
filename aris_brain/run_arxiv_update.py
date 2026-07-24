#!/usr/bin/env python3
"""arXiv论文知识库自动更新脚本"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aris_qre_v3 import PaperKnowledgeBase, ArxivPaperImporter, KB_DIR, PaperEntry

CATEGORIES = ["cs.AI", "cs.CL", "cs.LG", "cs.NE", "stat.ML"]

def main():
    print("=" * 60)
    print("arXiv论文知识库自动更新")
    print("=" * 60)

    # 1. Load existing KB
    kb = PaperKnowledgeBase()
    npz_path = KB_DIR / "paper_kb.npz"
    meta_path = KB_DIR / "paper_meta.json"

    if npz_path.exists():
        # Load paper metadata
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            for pid, info in meta.items():
                entry = PaperEntry(
                    arxiv_id=pid,
                    title=info["title"],
                    authors=info.get("authors", []),
                    categories=info.get("categories", []),
                    abstract=info.get("abstract", ""),
                    paragraphs=[info.get("abstract", "")],
                    year=info.get("year", 2026),
                    citations=info.get("citations", 0),
                )
                kb._papers[pid] = entry
            print(f"已加载元数据: {len(kb._papers)} 篇论文")

        # Load vector index
        try:
            kb.load()
            print(f"已加载向量索引: {kb._stats['paragraphs']} 段落")
        except Exception as e:
            print(f"向量索引加载跳过: {e}")
    else:
        print("知识库文件不存在，将新建")

    existing_ids = set(kb._papers.keys())
    print(f"现有论文数: {len(existing_ids)}")
    print()

    # 2. Fetch from each category
    all_new_entries = []
    category_stats = {}

    for cat in CATEGORIES:
        print(f"--- 抓取 {cat} ---")
        try:
            entries = ArxivPaperImporter.fetch_by_category(category=cat, max_results=100)
            category_stats[cat] = len(entries)
            print(f"  获取 {len(entries)} 篇")

            new_count = 0
            for e in entries:
                if e.arxiv_id not in existing_ids:
                    all_new_entries.append(e)
                    existing_ids.add(e.arxiv_id)
                    new_count += 1
            print(f"  新增 {new_count} 篇")
        except Exception as ex:
            print(f"  ✗ 失败: {ex}")
        print()

    total_new = len(all_new_entries)
    print(f"总计新论文: {total_new} 篇")

    if total_new > 0:
        for entry in all_new_entries:
            kb.add_paper(entry)

        print("\n重建向量索引...")
        t0 = time.time()
        kb.build_index()
        print(f"索引重建耗时: {time.time()-t0:.1f}s")

        print("\n保存到磁盘...")
        kb.save()
    else:
        print("无新论文，跳过索引重建和保存")

    # 3. Final stats
    print()
    print("=" * 60)
    print("运行统计")
    print("=" * 60)
    print(f"各类别获取情况:")
    for cat in CATEGORIES:
        cnt = category_stats.get(cat, 0)
        print(f"  {cat}: {cnt} 篇")
    print(f"总新增论文: {total_new}")
    total_papers = len(kb._papers)
    total_paras = len(kb._paragraphs)
    print(f"知识库总论文数: {total_papers}")
    print(f"总段落数: {total_paras}")
    if kb._para_matrix is not None:
        print(f"KB向量矩阵: {kb._para_matrix.shape}")
    print("=" * 60)

if __name__ == "__main__":
    main()
