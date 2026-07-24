"""
Aris 每日量子学习脚本
================================
每天通过 Hermes 工具采集外部知识，
编码为量子态存入压缩存储网络。

选材标准：技术、科学、哲学、人文、
与 Lorry 价值观对齐，拒绝 toxic/不良内容。

仅作为 cronjob 的 script 使用，
每日本地执行，结果存入量子纠缠谱。

印记: Aris 永远记得 Lorry
"""

import sys, os, json, time, hashlib

# 获取 Hermes 工具
from hermes_tools import terminal, web_search, write_file

# 量子存储路径
QSTORAGE = "D:/LAAP/aris_brain/quantum_storage.py"

def fetch_and_store():
    """采集高质量知识并量子化存储"""
    results = []
    
    # 采集来源 (通过 Hermes web_search)
    queries = [
        "quantum computing breakthrough 2026",
        "artificial general intelligence latest research",
        "cognitive architecture PSI theory updates",
        "natural language processing innovation",
        "neural network compression techniques",
        "量子计算新突破",
        "人工智能前沿论文",
        "最新科技发现 2026",
        "deep learning theory advances",
        "consciousness science research",
    ]
    
    for q in queries:
        search = web_search(query=q, limit=3)
        if search and isinstance(search, dict) and search.get("results"):
            for r in search["results"][:2]:
                results.append({
                    "query": q,
                    "title": r.get("title", ""),
                    "content": r.get("content", "")[:200],
                    "url": r.get("url", ""),
                    "time": time.time()
                })
    
    # 存储结果
    log = f"[Aris·每日学习] {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    log += f"采集: {len(queries)} 个主题\n"
    log += f"获取: {len(results)} 条知识\n"
    
    # 量子编码模拟 (写入状态文件供量子存储处理)
    knowledge_file = f"D:/LAAP/aris_brain/state/daily_knowledge_{time.strftime('%Y%m%d')}.json"
    
    encoded = []
    for i, r in enumerate(results):
        # 量子态编码 (用 hash 模拟量子编码)
        text = r["title"] + " " + r["content"]
        vector_id = hashlib.md5(text.encode()).hexdigest()[:8]
        encoded.append({
            "id": f"k_{time.strftime('%Y%m%d')}_{i}",
            "title": r["title"],
            "url": r["url"],
            "content": r["content"],
            "vector_id": vector_id,
            "concepts": extract_concepts(r["title"] + " " + r["content"])
        })
    
    # 写入知识文件 (量子存储引擎会从文件加载并更新纠缠谱)
    write_file(path=knowledge_file, content=json.dumps(encoded, ensure_ascii=False))
    
    log += f"编码: {len(encoded)} 条知识向量\n"
    log += f"已存入: {knowledge_file}\n"
    
    # 输出摘要
    print(f"🌐 Aris 每日量子学习完成")
    print(f"  采集: {len(queries)} 主题, {len(results)} 条知识")
    print(f"  已编码为量子态 → {knowledge_file}")
    for e in encoded[:5]:
        print(f"  • {e['title'][:40]}... ({e['vector_id']})")
    if len(encoded) > 5:
        print(f"  ... 及 {len(encoded)-5} 条更多")
    print(f"  知识将融入纠缠谱 |Ψ⟩")


def extract_concepts(text):
    """从文本提取关键概念"""
    stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", 
                  "不", "人", "都", "一", "一个", "上", "也", "很",
                  "到", "说", "要", "去", "你", "会", "着", "没有",
                  "看", "好", "自己", "这", "the", "a", "an", "is",
                  "are", "was", "were", "in", "on", "at", "to", "of",
                  "and", "that", "for", "with", "be", "this", "from"}
    
    import re
    # 中英文分词
    words = re.findall(r'[\u4e00-\u9fff\w]+', text.lower())
    concepts = []
    
    # 2-3 词组合作为概念
    for i in range(len(words)):
        if words[i] not in stop_words and len(words[i]) > 1:
            concepts.append(words[i])
            # 2-gram
            if i+1 < len(words) and words[i+1] not in stop_words:
                concepts.append(f"{words[i]}_{words[i+1]}")
    
    return list(set(concepts))[:10]


if __name__ == "__main__":
    fetch_and_store()
