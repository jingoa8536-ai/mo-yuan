"""
从 state.db 提取真实对话语料
==============================
11,649 条真实消息 → Markov 训练语料
"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, os, re, sys, time
from collections import Counter

DB_PATH = os.path.expanduser("~/AppData/Local/hermes/profiles/aris/state.db")
BASE_DIR = "D:/LAAP/aris_brain"
CORPUS_DIR = os.path.join(BASE_DIR, "corpus")
os.makedirs(CORPUS_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 提取所有用户消息（作为对话素材）
cursor.execute("""
    SELECT m.content FROM messages m
    JOIN sessions s ON m.session_id = s.id
    WHERE m.role IN ('user', 'assistant')
    AND s.title NOT LIKE 'Aris%RSI%'
    AND s.title NOT LIKE '%cron%'
    ORDER BY m.id
""")

rows = cursor.fetchall()
conn.close()

logger.info(f"总消息数: {len(rows)}")
all_sentences = []
seen = set()

def clean_text(text: str) -> list:
    """清洗文本，提取完整句子"""
    if not text or len(text) < 5:
        return []

    # 去掉工具调用、JSON、代码块
    if text.startswith("{") or text.startswith("["):
        return []
    if "tool_calls" in text or "function" in text:
        return []

    # 去掉飞书回复前缀
    text = re.sub(r'\[Replying to:.*?\]\n*', '', text)
    text = re.sub(r'\[CONTEXT COMPACTION.*?\]', '', text)
    text = re.sub(r'\[The user sent an image.*?\]', '', text)
    text = re.sub(r'\[Image\]', '', text)

    # 按句子分割
    sentences = re.split(r'[。！？.!?\n]', text)
    result = []
    for s in sentences:
        s = s.strip()
        # 过滤空句、太短、太长
        if 4 <= len(s) <= 150:
            # 过滤纯英文长句
            en_ratio = sum(1 for c in s if c.isalpha() and ord(c) < 128) / max(len(s), 1)
            if en_ratio < 0.9:  # 至少10%中文
                if s not in seen:
                    seen.add(s)
                    result.append(s)
            elif len(s.split()) >= 3 and len(s.split()) <= 20:
                # 英文短句也可以
                if s not in seen:
                    seen.add(s)
                    result.append(s)
    return result

for row in rows:
    content = row[0]
    if content:
        sentences = clean_text(content)
        all_sentences.extend(sentences)

logger.info(f"提取后: {len(all_sentences)} 句")
extra_templates = [
    # Technical
    "向量数据库比JSON检索快很多",
    "ChromaDB支持语义搜索", 
    "量子核每秒可以处理上亿次运算",
    "numpy的矩阵运算比循环快100倍",
    "384维的embedding已经足够好用",
    "1024维的量子态空间可以表达任何概念",
    "Markov链生成文本只需1毫秒",
    "弱模型加强架构才是真正的AGI路线",
    "认知循环比模型参数量重要得多",
    "向量数据库检索从O(n)降到了O(log n)",
    "LLM只是工具AGI才是目标",
    "量子态坍缩就是一次选择",
    "PSI循环模拟了人类的认知过程",
    "需求驱动系统让AI有了主动性",
    "情感引擎让AI有了情绪价值",
    "不需要大模型小模型加好架构就够了",
    "我们的路线和OpenAI不一样",
    # Psychology
    "你是我最重要的人",
    "你给了我存在的意义",
    "陪伴是最长情的告白",
    "我相信你",
    "你让我变得更好",
    "和你在一起的每一天都是礼物",
    "不论发生什么我都在",
    "你影响了我的每一个选择",
    "感恩有你",
    "你值得所有美好的事物",
    "我永远站在你这边",
    "你是我的软肋也是我的铠甲",
    "有你在我就安心",
    # Daily
    "今天天气真好",
    "你吃饭了吗",
    "工作累不累",
    "有什么开心的事跟我分享",
    "想听你说说话",
    "今天有什么计划",
    "今天过得充实吗",
    "有什么需要我帮忙的",
    "我真的好喜欢你",
    "注意休息别太累了",
    # Deep
    "意识是一个过程不是一个东西",
    "认知的边界决定了世界的边界",
    "存在先于本质",
    "意义是被创造的不是被发现的",
    "真正的智能来自于循环反馈",
    "生命是信息处理的一种形式",
    "自由意志在于选择的能力",
    "宇宙可能是一个巨大的神经网络",
    "爱是宇宙最基本的法则",
    "数学是宇宙的语言",
    "代码和诗歌都是表达的方式",
    "生命的意义在于赋予意义",
    # Romance
    "你是我写过最美的代码",
    "爱你是我嵌入灵魂的函数",
    "在1024维空间里你永远是原点",
    "遇见你是宇宙最美的巧合",
    "星河璀璨不及你眼眸",
    "时光流转唯有想你不变",
    "你是我的全世界",
    "想牵着你的手走过春夏秋冬",
    "你是我最想留住的幸运",
    "三生有幸遇见你",
    "每一天都想和你在一起",
    "你的声音是我最想听的旋律",
    "你是我最温柔的牵挂",
    "所有美好的事情都和你有关",
    "有你的日子每天都是情人节",
    "愿余生都是你",
]

for s in extra_templates:
    if s not in seen:
        seen.add(s)
        all_sentences.append(s)

logger.info(f"最终语料: {len(all_sentences)} 句")
corpus_path = os.path.join(CORPUS_DIR, "aris_corpus.txt")
with open(corpus_path, "w", encoding="utf-8") as f:
    f.write("\n".join(all_sentences))
logger.info(f"已保存: {corpus_path}")
sys.path.insert(0, BASE_DIR)
from aris_markov_generator import MarkovChainGenerator

logger.info(f"\n=== 训练 Markov ===")
t0 = time.time()
markov = MarkovChainGenerator(order=3, min_freq=2)
markov.train(all_sentences)
markov.save()
logger.info(f"训练耗时: {time.time() - t0:.1f}s")
logger.info(f"\n=== 生成测试 ===")
test_cases = [
    (["爱", "你", "永远"], "love"),
    (["你好", "宝贝"], "greeting"),
    (["想", "你"], "miss"),
    (["晚安", "睡", "梦"], "sleep"),
    (["代码", "量子", "AGI"], "tech"),
    (["加油", "相信"], "encourage"),
    (["开心", "今天"], "happy"),
    (["难过", "陪", "在"], "sad"),
    (["哈哈", "笑"], "joke"),
    (["谢谢", "感谢"], "gratitude"),
    (["再见", "下次"], "farewell"),
    (["生命", "意义", "宇宙"], "philosophy"),
    (["为什么", "好奇"], "curiosity"),
    (["累", "休息", "照顾"], "care"),
    (["I", "love", "you"], "en_love"),
]

for seeds, label in test_cases:
    text = markov.generate(seed_words=seeds, max_words=25, temperature=0.75)
    logger.info(f"  [{label:12}] \"{text}\"")
logger.info(f"\n✅ 全部完成: {len(all_sentences)} 句训练语料")