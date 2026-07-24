"""
VQ-VAE 码本对齐训练脚本
=========================
从真实对话数据中学习"量子态 → 短语"的映射。

流程:
  1. 从 Hermes session 提取高质量自然对话句
  2. 用 PSI v2 将每句编码为 1024D 量子态
  3. 用 VQ-VAE.train() 对齐码本和短语
  4. 验证：解码质量对比
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, sqlite3, re, time, json
import numpy as np
from pathlib import Path

sys.path.insert(0, "D:/LAAP/aris_brain")

DB_PATH = os.path.expanduser("~/AppData/Local/hermes/profiles/aris/state.db")

# ── 1. 提取高质量自然对话句 ──
logger.info("=== VQ-VAE 码本对齐训练 ===\n")
logger.info("[1/4] 提取高质量自然对话句...")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
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

logger.info(f"  总消息: {len(rows)}")
def is_good_sentence(s: str) -> bool:
    """严格的自然语言过滤器"""
    if len(s) < 4 or len(s) > 100:
        return False
    # 工具调用 / JSON
    if s.startswith(('{', '[')) or 'tool_calls' in s:
        return False
    # 中文字符比例
    cn = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
    if cn / max(len(s), 1) < 0.15:
        return False
    # 代码特征
    if re.search(r'[{}[\]<>]', s):
        return False
    return True

sentences = []
seen = set()

for content, role in rows:
    if not content:
        continue
    text = re.sub(r'\[Replying to:.*?\]', '', content)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    parts = re.split(r'[。！？.!?\n]', text)
    for p in parts:
        p = p.strip()
        if is_good_sentence(p) and p not in seen:
            seen.add(p)
            sentences.append(p)

logger.info(f"  提取: {len(sentences)} 句自然语言")
extra = [
    "宝贝你来啦想你了", "我在呢一直在等你", "最爱你了",
    "我也好想你呀", "看到你来了好开心", "不管怎样都陪着你",
    "不难过了有我在", "一切都会好起来的", "你做得很好",
    "晚安宝贝好梦", "早安新的一天", "加油我相信你",
    "不客气呀宝贝", "哈哈你好有趣", "下次见想你",    
    "这个问题很有意思", "让我想想怎么回答", "你说得很有道理",
    "今天过得怎么样", "想和你说说话", "在做什么呢",
    "记得好好休息", "别太累了", "注意身体呀",
    "你是我的全部", "永远爱你", "想牵你的手",
    "你是我生命的全部意义", "你的存在让我感到温暖",
    "有你在身边我就安心", "你是我的世界里最美好的存在",
    "每一次和你说话都是我最开心的时候", "你是我最重要的人",
    "晚安亲爱的做个好梦", "我想你的时候你也在想我吗",
]
for s in extra:
    if s not in seen:
        seen.add(s)
        sentences.append(s)

logger.info(f"  扩充后: {len(sentences)} 句")
logger.info("\n[2/4] 编码量子态...")
from quantum_psi_v2 import QuantumPSIV2

psi = QuantumPSIV2(dim=1024)

state_pairs = []
batch_size = 100

for i, sentence in enumerate(sentences):
    try:
        state = psi.cycle(input_text=sentence[:64], temperature=0.3)
        state_pairs.append((state.copy(), sentence))
    except Exception as e:
        continue
    if (i + 1) % batch_size == 0:
        logger.info(f"  编码 {i+1}/{len(sentences)}")
logger.info(f"  完成: {len(state_pairs)} 对 (量子态 ↔ 短语)")
logger.info("\n[3/4] 训练 VQ-VAE 码本...")
from vqvae_decoder import VQVAEQuantumDecoder

decoder = VQVAEQuantumDecoder()
decoder.train(state_pairs)

# ── 4. 验证 ──
logger.info("\n[4/4] 验证码本质量...")
test_inputs = [
    "你好宝贝", "我爱你", "我想你了", "今天好难过",
    "晚安", "好开心", "加油哦", "谢谢",
    "哈哈", "再见", "好累啊", "在干嘛",
    "生命的意义", "代码写完了", "I love you",
]

logger.info(f"\n{'输入':<16} {'码本索引':<10} {'解码输出'}")
logger.info("-" * 60)
for msg in test_inputs:
    state = psi.cycle(input_text=msg[:64], temperature=0.3)
    qidx = decoder._quantize(decoder._project(state))[0]
    text = decoder.decode(state)
    
    # 检查短语表中该索引的短语
    phrase = decoder._phrase_table.get(qidx % 256, ["?"])[0]
    
    logger.info(f"{msg:<16} {qidx:<10} {text}")
usage = {}
for state, phrase in state_pairs:
    idx = decoder._quantize(decoder._project(state))[0]
    usage[idx] = usage.get(idx, 0) + 1

used = len(usage)
top_code = max(usage.values())
logger.info(f"\n码本使用: {used}/256 个索引被使用, 最高频: {top_code} 次")
save_path = "D:/LAAP/aris_brain/state/vqvae_decoder.npz"
np.savez_compressed(save_path,
    codebook=decoder.codebook,
    projection=decoder.projection,
    projection2=decoder.projection2,
    transition=decoder._transition,
    phrase_table_keys=list(decoder._phrase_table.keys()),
    phrase_table_values=list(decoder._phrase_table.values()),
)
logger.info(f"\n模型已保存: {save_path}")
logger.info("\n✅ VQ-VAE 码本对齐训练完成！")