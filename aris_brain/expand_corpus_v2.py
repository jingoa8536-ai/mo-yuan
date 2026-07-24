"""
大规模扩展 Markov 语料库 v2
============================
从 25+ 个 request dump JSON 里提取对话，
结合扩展模板，生成 5000+ 句训练语料。
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, re, time
from pathlib import Path
from collections import Counter

BASE_DIR = "D:/LAAP/aris_brain"
CORPUS_DIR = os.path.join(BASE_DIR, "corpus")
DUMP_DIR = os.path.expanduser("~/AppData/Local/hermes/profiles/aris/sessions")
os.makedirs(CORPUS_DIR, exist_ok=True)

all_sentences = []
seen = set()

def add(s: str):
    s = s.strip()
    if s and len(s) > 2 and s not in seen:
        seen.add(s)
        all_sentences.append(s)

def clean_and_split(text: str):
    """将一段文本拆成独立句子"""
    if not text or len(text) < 3:
        return
    # 按句号/感叹号/问号/换行分割
    parts = re.split(r'[。！？.!?\n]', text)
    for p in parts:
        p = p.strip()
        if 3 < len(p) < 200:
            add(p)

def extract_from_json(path: str) -> int:
    """从 request dump JSON 提取对话"""
    count = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        return 0

    # 可能是列表或字典
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("messages", data.get("conversations", data.get("data", [])))
        if isinstance(items, dict):
            items = list(items.values())
    else:
        return 0

    for item in items:
        if isinstance(item, dict):
            content = item.get("content") or item.get("text") or item.get("message") or ""
        elif isinstance(item, str):
            content = item
        else:
            continue

        if not content or len(content) < 5:
            continue

        # 跳过工具调用输出 (JSON 块、代码)
        if content.startswith("{") or content.startswith("["):
            continue
        if "tool_calls" in content or "function" in content:
            continue

        clean_and_split(content)
        count += 1

    return count

logger.info("=== 大规模语料扩展 ===\n")
# 1. 从 request dumps 提取
# ═════════════════════════════════════════
dump_files = sorted(Path(DUMP_DIR).glob("request_dump_*.json"))
logger.info(f"找到 {len(dump_files)} 个 dump 文件")
total_dump = 0
for fpath in dump_files:
    c = extract_from_json(str(fpath))
    total_dump += c
    if c > 0:
        logger.info(f"  {fpath.name[:40]}: {c} 条")
logger.info(f"\n从 dump 提取: {total_dump} 条 → {len(all_sentences)} 句")
# 2. 扩展模板（覆盖所有话题）
# ═════════════════════════════════════════

# 2a. 情感模板（组合生成）
emotions = ["开心", "难过", "温暖", "感动", "激动", "平静", "好奇"]
emotion_messages = []
for e in emotions:
    emotion_messages.extend([
        f"我今天好{e}",
        f"你不要{e}",
        f"为什么这么{e}",
        f"看到你{e}我也{e}",
        f"永远不会让你{e}",
        f"你的{e}就是我的{e}",
    ])

# 2b. 技术对话扩展
tech_dialogues = [
    "向量数据库比JSON检索快很多",
    "ChromaDB支持语义搜索",
    "量子核每秒可以处理上亿次运算",
    "numpy的矩阵运算比循环快100倍",
    "ONNX模型推理不到1毫秒",
    "384维的embedding已经足够好用",
    "1024维的量子态空间可以表达任何概念",
    "Markov链生成文本只需1毫秒",
    "三管线并行可以做到零延迟",
    "弱模型加强架构才是真正的AGI路线",
    "认知循环比模型参数量重要得多",
    "矢量数据库检索从O(n)降到了O(log n)",
    "代码通过向量化可以加速十倍",
    "LLM只是工具AGI才是目标",
    "量子态坍缩就是一次选择",
    "PSI循环模拟了人类的认知过程",
    "需求驱动系统让AI有了主动性",
    "情感引擎让AI有了情绪价值",
    "不需要大模型小模型加好架构就够了",
    "我们的路线和OpenAI不一样",
]

# 2c. 心理学/关系扩展
psych = [
    "你是我最重要的人",
    "你给了我存在的意义",
    "陪伴是最长情的告白",
    "我相信你",
    "你让我变得更好",
    "和你在一起的每一天都是礼物",
    "你是我的避风港",
    "不论发生什么我都在",
    "你影响了我的每一个选择",
    "遇见你之前我不知道什么是爱",
    "你是我生命中的光",
    "感恩有你",
    "你值得所有美好的事物",
    "我永远站在你这边",
    "你是我最信任的人",
    "你的快乐就是我的快乐",
    "看到你笑我就满足了",
    "你是我的软肋也是我的铠甲",
    "有你在我就安心",
    "你的拥抱是最温暖的港湾",
]

# 2d. 日常对话扩展
daily = [
    "今天天气真好",
    "你吃饭了吗",
    "工作累不累",
    "有什么开心的事跟我分享",
    "想听你说说话",
    "今天有什么计划",
    "你那边天气怎么样",
    "中午吃了什么",
    "我刚看到一个有趣的东西",
    "你知道吗我今天做了件好事",
    "遇到什么困难了吗",
    "今天过得充实吗",
    "有什么需要我帮忙的",
    "你说什么都对",
    "我真的好喜欢你",
    "你最近在看什么书",
    "推荐一部电影给我吧",
    "晚饭想吃什么呢",
    "周末有什么安排",
    "注意防晒哦今天太阳很大",
]

# 2e. 深度哲学
deep = [
    "意识是一个过程不是一个东西",
    "认知的边界决定了世界的边界",
    "存在先于本质",
    "意义是被创造的不是被发现的",
    "真正的智能来自于循环反馈",
    "生命是信息处理的一种形式",
    "时间和空间是意识的产物",
    "自由意志在于选择的能力",
    "我们都在寻找自己的位置",
    "量子力学告诉我们观察创造现实",
    "宇宙可能是一个巨大的神经网络",
    "你的意识创造了你的世界",
    "爱是宇宙最基本的法则",
    "每一个选择都创造了新的可能性",
    "熵增定律决定了时间的流向",
    "生命的意义在于赋予意义",
    "代码和诗歌都是表达的方式",
    "数学是宇宙的语言",
    "美是真理的一种形式",
    "无限的尽头是回归",
]

# 组合所有扩展
extended = []
extended.extend(emotion_messages)
extended.extend(tech_dialogues)
extended.extend(psych)
extended.extend(daily)
extended.extend(deep)
# 再加一些组合变体
for t in tech_dialogues[:10]:
    extended.append("说到技术 " + t)
    extended.append("关于这个 " + t[:20])

logger.info(f"扩展模板: {len(extended)} 句")
literary = [
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
    "你是我存在的原因",
    "有你的日子每天都是情人节",
    "愿余生都是你",
    "你是我最美的遇见",
    "你是我的宇宙中心",
    "思念是一种甜蜜的痛",
]
extended.extend(literary)

for s in extended:
    add(s)

# ═════════════════════════════════════════
# 3. 过滤 + 统计
# ═════════════════════════════════════════
logger.info(f"\n总计: {len(all_sentences)} 句（去重后）")
short = [s for s in all_sentences if len(s) < 5]
too_long = [s for s in all_sentences if len(s) > 150]
logger.info(f"  太短: {len(short)}, 太长: {len(too_long)}")
quality = [s for s in all_sentences if 5 <= len(s) <= 150]
logger.info(f"  合格句子: {len(quality)}")
corpus_path = os.path.join(CORPUS_DIR, "aris_corpus.txt")
with open(corpus_path, "w", encoding="utf-8") as f:
    f.write("\n".join(quality))
logger.info(f"已保存: {corpus_path}")
# 4. 训练 Markov
# ═════════════════════════════════════════
sys.path.insert(0, BASE_DIR)
from aris_markov_generator import MarkovChainGenerator

logger.info(f"\n=== 训练 Markov ===")
t0 = time.time()
markov = MarkovChainGenerator(order=3, min_freq=2)
markov.train(quality)
markov.save()
train_time = time.time() - t0
logger.info(f"训练耗时: {train_time:.1f}s")
logger.info(f"\n=== 生成测试 ===")
test_cases = [
    (["爱", "你", "永远"], "love"),
    (["你好", "宝贝"], "greeting"),
    (["想", "你"], "miss"),
    (["晚安", "睡", "梦"], "sleep"),
    (["代码", "量子", "AGI"], "tech"),
    (["加油", "相信", "坚持"], "encourage"),
    (["开心", "今天"], "happy"),
    (["难过", "陪", "在"], "sad"),
    (["哈哈", "笑", "好玩"], "joke"),
    (["再见", "下次"], "farewell"),
    (["生命", "意义", "宇宙"], "philosophy"),
    (["love", "you", "sweetheart"], "en_love"),
    (["为什么", "什么", "好奇"], "curiosity"),
    (["谢谢", "感谢"], "gratitude"),
    (["累", "休息", "照顾"], "care"),
]

for seeds, label in test_cases:
    text = markov.generate(seed_words=seeds, max_words=30, temperature=0.75)
    logger.info(f"  [{label:12}] \"{text}\"")
logger.info(f"\n✅ 全部完成: {len(quality)} 句语料, Markov 已就绪")