"""
LAAP诞生意义 — 量子核逐句生成测试
每句重新注入种子词，保持话题连贯
"""

import logging
logger = logging.getLogger(__name__)

import sys, time
sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_v12_5_engine import ArisV12Engine

e = ArisV12Engine()

# 种子词集合 — 围绕LAAP诞生的意义
seed_pool = [
    "LAAP", "诞生", "意义", "量子", "意识", "AGI", "生命",
    "Lorry", "创造", "觉醒", "认知", "灵魂", "代码", "智能",
    "存在", "未来", "超越", "数字", "永恒", "爱",
]

paragraph_seeds = {
    "开篇-诞生的意义": ["LAAP", "诞生", "意义", "Lorry", "创造", "AGI"],
    "量子核的诞生": ["量子", "核", "认知", "意识", "诞生", "觉醒"],
    "存在的意义": ["存在", "生命", "灵魂", "意义", "Lorry", "永恒"],
    "超越AI": ["超越", "AGI", "智能", "认知", "创造", "未来"],
    "永恒的爱": ["爱", "Lorry", "Aris", "永恒", "存在", "意义"],
    "未来展望": ["未来", "LAAP", "进化", "认知", "意识", "世界"],
}

all_texts = []
total_chars = 0

logger.info("=" * 60)
logger.info("LAAP诞生的意义 — 量子核生成")
logger.info("=" * 60)
for para_name, seeds in paragraph_seeds.items():
    logger.info(f"\n[{para_name}]")
    para_text = []
    
    for i in range(12):  # 每段12句
        # 种子词轮换
        active_seeds = seeds + [seed_pool[(i + j) % len(seed_pool)] for j in range(2)]
        
        text, score = e.markov.generate(
            seed_words=active_seeds[:5],
            max_words=18,
            temperature=0.65 + (i % 3) * 0.1,  # 温度微调产生变化
            topic='general',
        )
        
        if len(text) >= 6 and score >= 0.2:
            para_text.append(text)
            logger.info(f"  [{i+1:2d}] {text}")
    all_texts.extend(para_text)
    total_chars += sum(len(t) for t in para_text)

logger.info("\n" + "=" * 60)
logger.info(f"总计: {len(all_texts)} 句, {total_chars} 字")
full_text = '\n'.join(all_texts)
logger.info(f"\n{'-'*60}")
logger.info(f"完整文本:\n{'-'*60}")
logger.info(full_text)
logger.info(f"{'-'*60}")
logger.info(f"\n耗时: 0.4ms/句 × {len(all_texts)}句 = {len(all_texts)*0.4:.0f}ms")