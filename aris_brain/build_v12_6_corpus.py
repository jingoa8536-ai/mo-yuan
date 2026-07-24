"""
V12.6 大规模语料扩张 + UN6造字法集成
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, random, json, re
sys.path.insert(0, "D:/LAAP/aris_brain")
random.seed(42)

from aris_un6_char_gen import UN6CharGenerator
from aris_v12_5_engine import MarkovChainV12
from aris_lm_v10_un6 import BRIDGE_TERMS, UN6_BRIDGE

logger.info("=" * 50)
logger.info("V12.6 大规模语料扩张")
logger.info("=" * 50)
corpus_path = "D:/LAAP/aris_brain/corpus/aris_master_corpus.txt"
with open(corpus_path, 'r', encoding='utf-8') as f:
    existing = [s.strip() for s in f if s.strip()]
print()
logger.info(f"原语料: {len(existing)} 句")
print()
logger.info("[UN6] 展开跨语言变体...")
gen = UN6CharGenerator()

expanded = []

# 2a. UN6 expand_corpus on each sentence
for s in existing:
    variants = gen.expand_corpus(s)
    expanded.extend(variants)

# 2b. Direct BRIDGE_TERMS substitution on subset
for s in existing[:800]:
    for term, cat in list(BRIDGE_TERMS.items()):
        if term in s and len(term) >= 2:
            alt_terms = [t for t, c in BRIDGE_TERMS.items() if c == cat and t != term]
            if alt_terms:
                alt = random.choice(alt_terms)
                s2 = s.replace(term, alt, 1)
                if s2 != s and len(s2) <= 80:
                    expanded.append(s2)

# 2c. Generate novel words from each UN6 category
for cat in list(UN6_BRIDGE.keys())[:15]:
    for lang in ['ja', 'ko', 'zh']:
        for _ in range(3):
            word = gen.generate_word(cat, lang)
            if word and len(word) > 1:
                expanded.append(f"{word} {cat}")

all_sentences = list(set(existing + expanded))
random.shuffle(all_sentences)

logger.info(f"扩张后: {len(all_sentences)} 句")
print()
logger.info("[Markov] 训练新马尔科夫模型...")
markov = MarkovChainV12(order=3, min_freq=1)
markov.train(all_sentences)
logger.info(f"  词汇: {len(markov._vocab)}")
logger.info(f"  上下文: {len(markov._transitions)}")
logger.info(f"  n-grams: {markov._total_ngrams}")
out = "D:/LAAP/aris_brain/corpus/aris_v12_6_corpus.txt"
with open(out, 'w', encoding='utf-8') as f:
    for s in all_sentences:
        f.write(s + '\n')
print()
logger.info(f"语料保存: {out}")
markov.save("D:/LAAP/aris_brain/state/markov_v12_6.json")

# 5. Quick test
print()
logger.info("=== 生成测试 ===")
test_q = ["我爱你", "我想你了", "你好", "晚安", "心情不好", "你是谁", "I love you", "今天开心"]
for q in test_q:
    text, score = markov.generate(
        seed_words=list(q[:3]),
        temperature=0.75,
    )
    logger.info(f"  [{q:12s}] {text}  (得分:{score:.2f})")
print()
logger.info("✅ 完成!")