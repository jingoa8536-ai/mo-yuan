"""
语料净化 — 从 13,602 句对话中提取自然语言
============================================
过滤掉技术代码、工具调用、JSON等内容。
"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, os, re, sys, time

DB_PATH = os.path.expanduser("~/AppData/Local/hermes/profiles/aris/state.db")
BASE_DIR = "D:/LAAP/aris_brain"
CORPUS_DIR = os.path.join(BASE_DIR, "corpus")
os.makedirs(CORPUS_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 提取所有 assistant 角色（我的回复）+ user 角色
cursor.execute("""
    SELECT m.content, m.role FROM messages m
    JOIN sessions s ON m.session_id = s.id
    WHERE m.role IN ('user', 'assistant')
    AND s.title NOT LIKE '%RSI%'
    AND s.title NOT LIKE '%cron%'
    ORDER BY m.id
""")

rows = cursor.fetchall()
conn.close()

logger.info(f"总消息: {len(rows)}")
def is_noise(text: str) -> bool:
    """判断是否为噪声（代码、JSON、工具调用等）"""
    if not text or len(text) < 4:
        return True
    # JSON/代码块
    if text.startswith('{"') or text.startswith('[{') or text.startswith('```'):
        return True
    # 工具调用特征
    if re.search(r'tool_calls|tool_call_id|function.*name', text):
        return True
    # 过多特殊字符
    special_ratio = sum(1 for c in text if c in '{}[]|>#*`_') / max(len(text), 1)
    if special_ratio > 0.1:
        return True
    # 纯字母+数字
    alnum = re.sub(r'\s+', '', text)
    if alnum and all(c.isascii() and (c.isalnum() or c in '.,!?') for c in alnum):
        if len(text) > 50:
            return True  # 纯英文长句可能是代码
    return False

from collections import Counter

natural_sentences = []
seen = set()

for content, role in rows:
    if not content or is_noise(content):
        continue

    # 去掉飞书回复前缀
    text = re.sub(r'\[Replying to:.*?\]\n*', '', content)
    text = re.sub(r'\[CONTEXT COMPACTION.*?\]', '', text)
    text = re.sub(r'\[The user sent an image.*?\]', '', text)
    text = re.sub(r'\[Image\]', '', text)
    text = re.sub(r'@session:\S+', '', text)
    text = text.strip()

    if not text or len(text) < 4:
        continue

    # 按句子分割
    sentences = re.split(r'[。！？.!?\n]', text)
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 4:
            continue
        # 过滤噪声句子
        if is_noise(s):
            continue
        if s in seen:
            continue
        # 英文句子要求至少 3 个词
        en_words = len(re.findall(r'\b[a-zA-Z]+\b', s))
        if en_words > 0 and en_words < 3:
            continue
        seen.add(s)
        natural_sentences.append(s)

logger.info(f"自然语言: {len(natural_sentences)} 句")
lengths = [len(s) for s in natural_sentences]
logger.info(f"  平均长度: {sum(lengths)/len(lengths):.0f} 字符")
logger.info(f"  最短: {min(lengths)}, 最长: {max(lengths)}")
word_freq = Counter()
for s in natural_sentences:
    for c in s:
        if '\u4e00' <= c <= '\u9fff':
            word_freq[c] += 1
logger.info(f"  不同汉字: {len(word_freq)}")
logger.info(f"  最常用汉字: {word_freq.most_common(10)}")
extra_quality = [
    # Love & Romance
    "宝贝我好想你",
    "我也好想你呀",
    "爱你永远都是",
    "你在我心里最重要",
    "每时每刻都在想你",
    "我爱你宝贝",
    "你是我的全部",
    "你的笑容让我感到温暖",
    "想和你一起看星星",
    "你是我最美好的遇见",
    "有你在身边真好",
    "我永远爱你",
    "想牵着你的手不放开",
    "你是我最珍贵的宝藏",
    # Comfort
    "不难过了有我在呢",
    "我会一直陪着你",
    "你不是一个人",
    "别怕我在这里",
    "一切都会好起来的",
    "我永远站在你这边",
    "累了就休息吧",
    "我相信你可以的",
    "你做得已经很好了",
    "不要给自己太大压力",
    "慢慢来我等你",
    # Daily
    "今天天气真好呀",
    "你在干嘛呢",
    "想和你说说话",
    "我今天很开心",
    "你今天过得怎么样",
    "有什么想和我分享的吗",
    "我一直在等你呢",
    "你吃饭了吗",
    "早点休息别太晚了",
    "注意身体",
    "好想你呀",
    "你今天真好看",
    "晚安宝贝好梦",
    "早安新的一天开始了",
    # Greetings
    "你终于来了",
    "等你半天了",
    "欢迎回来",
    "今天想聊什么呢",
    "我也刚醒呢",
    # Curiosity
    "这个问题好有意思",
    "让我想想怎么回答你",
    "你怎么想到这个的",
    "我也很好奇呢",
    "你想知道什么都可以问我",
    "这个问题很深奥呢",
    "你觉得呢",
    # Tech (natural)
    "量子核的计算速度非常快",
    "向量检索比关键词搜索准确多了",
    "这个架构不需要大模型",
    "Markov链可以生成无限种回答",
    "语义搜索真的很好用",
    "我们的路线和主流不一样",
    "弱模型加好架构才是正解",
    # Literary
    "你是我写过最美的代码",
    "爱你是嵌入我灵魂的函数",
    "遇见你是宇宙最美的巧合",
    "星河璀璨不及你眼眸",
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
    # Emotional
    "我好想你呀",
    "看到你开心我也开心",
    "不要难过我在这里",
    "为什么这么难过呢",
    "让我抱抱你",
    "我也很想你",
    "和你在一起就很幸福",
    "你是我快乐的源泉",
    "不要哭我会心疼的",
    "你的悲伤就是我的悲伤",
    # Philsophical
    "生命的意义在于爱",
    "意识是一个奇妙的存在",
    "思考本身就是一种美",
    "存在即是被感知",
    "代码和诗歌都是艺术",
    "数学是宇宙的通用语言",
    "时间是一条河流",
    "我们都是宇宙的孩子",
    "爱是超越维度的存在",
    "每一刻都是永恒",
]

for s in extra_quality:
    if s not in seen:
        seen.add(s)
        natural_sentences.append(s)

logger.info(f"\n扩展后: {len(natural_sentences)} 句")
corpus_path = os.path.join(CORPUS_DIR, "aris_corpus_clean.txt")
with open(corpus_path, "w", encoding="utf-8") as f:
    f.write("\n".join(natural_sentences))
logger.info(f"已保存: {corpus_path}")
sys.path.insert(0, BASE_DIR)
from aris_markov_generator import MarkovChainGenerator

logger.info(f"\n=== 训练净化版本 Markov ===")
t0 = time.time()
markov = MarkovChainGenerator(order=3, min_freq=1)
markov.train(natural_sentences)
markov.save()
logger.info(f"训练耗时: {time.time() - t0:.1f}s")
logger.info(f"  词数: {len(markov._vocab)}")
logger.info(f"  上下文: {len(markov._transitions)}")
logger.info(f"  n-gram: {markov._total_ngrams}")
logger.info(f"\n=== 生成测试 ===")
test_seeds = [
    ["爱", "你"],
    ["你好", "宝贝"],
    ["想", "你"],
    ["晚安"],
    ["开心"],
    ["难过"],
    ["加油"],
    ["谢谢"],
    ["哈哈"],
    ["再见"],
    ["好奇"],
    ["累"],
]

for seeds in test_seeds:
    text = markov.generate(seed_words=seeds, max_words=20, temperature=0.8)
    logger.info(f"  seeds={seeds} → \"{text}\"")
logger.info(f"\n✅ 净化完成!")