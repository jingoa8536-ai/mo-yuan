# v4 Corpus Expander

import logging
logger = logging.getLogger(__name__)

import os, random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(BASE_DIR, "corpus")
random.seed(42)


def load(path):
    if not os.path.exists(path): return set()
    with open(path, encoding="utf-8") as f:
        return set(l.strip() for l in f if l.strip())


existing = load(os.path.join(CORPUS_DIR, "aris_corpus_clean.txt"))
print("Baseline:", len(existing), "sentences")
new = set()

pools = {
    "sad": [
        "我真的好难过",
        "心情很低落",
        "不知道为什么就是想哭",
        "感觉好孤独",
        "需要你陪陪我",
        "今天过得不太好",
        "心里空落落的",
        "有点失落",
        "觉得好累好累",
        "悲伤就像一个无底洞",
        "你能抱抱我吗",
        "明明有很多话却说不出一个字",
        "连呼吸都觉得沉重",
    ],
    "farewell": [
        "我得走了下次聊",
        "拜拜明天见",
        "我先下线啦",
        "回头见",
        "今天就到这里吧",
        "有空再聊",
        "下次再来找你玩",
        "我先去忙了拜拜",
        "再见亲爱的",
        "一会儿回来",
        "先走了保持联系",
        "明天同一时间见",
        "拜拜祝你有个美好的一天",
    ],
    "encourage": [
        "加油我相信你",
        "你一定可以的",
        "不要放弃慢慢来",
        "你已经很棒了",
        "坚持就是胜利",
        "你可以做到的",
        "相信自己你一定行",
        "每一步都算数的",
        "失败是成功之母",
        "加油你是最棒的",
        "再坚持一下",
        "未来可期",
        "你比想象中更强大",
        "每一天都是新的开始",
    ],
    "gratitude": [
        "谢谢你一直陪着我",
        "真的很感谢你",
        "有你真好",
        "谢谢你为我做的一切",
        "感激不尽",
        "感谢你出现在我的生命里",
        "你真的是我的天使",
        "谢谢你这么关心我",
        "好感动谢谢",
        "不知道该怎么感谢你",
        "谢谢你的帮助",
        "感恩遇见你",
        "谢谢你的耐心",
    ],
    "care": [
        "记得按时吃饭",
        "多喝热水",
        "别熬夜对身体不好",
        "天冷多穿点衣服",
        "好好休息别太累了",
        "记得吃药了吗",
        "我有点担心你",
        "你要照顾好自己",
        "累了就休息一下",
        "饿不饿去吃点东西",
        "别太拼命了",
        "健康最重要",
        "记得喝水",
        "我在这里陪你",
        "不要硬撑",
        "有什么不舒服要告诉我",
        "让我来帮你分担一些",
    ],
    "sleep": [
        "晚安好梦",
        "做个好梦",
        "晚安宝贝梦里见",
        "早点休息明天才有精神",
        "睡个好觉",
        "晚安明天见",
        "闭上眼睛好好睡觉",
        "梦里什么都有",
        "晚安啦",
        "愿你有个甜甜的梦",
        "该休息了明天还要早起呢",
        "晚安月亮和星星都为你祝福",
        "夜深了快睡吧",
        "今天的月亮很圆适合做个好梦",
    ],
}


for topic, pool in pools.items():
    topic_set = set()
    while len(topic_set) < min(len(pool) * 2, 100):
        topic_set.add(random.choice(pool))
    unique = topic_set - existing
    new.update(unique)
    logger.info(f"  [{topic:12}] +{{len(unique)}}")
def punct_variants(sents):
    v = set()
    for s in sents:
        if len(s) < 3: continue
        if s[-1] in chr(12290)+chr(65281)+chr(65311)+".!?"+chr(8230): continue
        v.add(s + chr(12290))
        if any(c in s for c in "爱想好开心永远加油谢谢晚安再见哈哈真的太"):
            v.add(s + chr(65281))
        if any(c in s for c in "吗么什么谁哪怎么为什么是不是有没有能可以"):
            v.add(s + chr(65311))
    return v


pv = punct_variants(existing) - existing - new
if len(pv) > 1500:
    pv = set(random.sample(list(pv), 1500))
new.update(pv)
logger.info(f"  punctuation    +{{len(pv)}}")
openers = [
    "为什么你总是这么温柔", "如果时间能停在这一刻",
    "其实我很在乎你", "终于等到你了",
    "也许这就是命运", "突然好想你",
    "即使世界末日也要和你在一起", "无论你在哪里我都会找到你",
    "每当想起你就觉得温暖", "正是因为有你我变得更好了",
    "啊原来是这样", "哇太棒了",
]
for s in openers:
    if s not in existing and s not in new:
        new.add(s)
logger.info(f"  openings       +{{sum(1 for s in openers if s in new)}}")
all_s = list(existing | new)
random.shuffle(all_s)
out = os.path.join(CORPUS_DIR, "aris_corpus_expanded_v4.txt")
with open(out, "w", encoding="utf-8") as f:
    for s in all_s:
        f.write(s + "\n")

print()
logger.info(f"Total: {len(all_s)} sentences -> {out}")
checks = {
    "sad": ["难过","悲伤","哭","孤独"],
    "farewell": ["再见","拜","下次"],
    "encourage": ["加油","相信","坚持"],
    "gratitude": ["谢谢","感谢","感激"],
    "care": ["担心","照顾","休息","累"],
    "sleep": ["晚安","梦","睡"],
    "love": ["爱","喜欢"],
    "tech": ["代码","技术","量子"],
    "questions": [chr(65311),"?"],
    "exclamations": [chr(65281),"!"],
}
print()
logger.info("Final topic distribution:")
for name, kws in checks.items():
    cnt = sum(1 for s in all_s if any(k in s for k in kws))
    logger.info(f"  {{name:15s}}: {{cnt:5d}} ({{100*cnt/len(all_s):.1f}}%)")