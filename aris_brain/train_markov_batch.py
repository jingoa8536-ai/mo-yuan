"""
Markov Batch Trainer — 高效分批训练
====================================
把 5000 条语料分批训练 Markov, 支持断点续训。
每批 500 条, 10 分钟完成全过程。
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json
from collections import defaultdict, Counter

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

def train_markov_batch(filepath, batch_size=500, order=2):
    """分批训练 Markov, order=2更快"""
    from aris_markov_generator import MarkovChainGenerator
    
    cache = os.path.join(_DIR, "state", "markov_chain.json")
    mg = MarkovChainGenerator(order=order, min_freq=1)
    
    # 加载已有模型
    if os.path.exists(cache):
        mg.load(cache)
        logger.info(f"  已有: {len(mg._vocab)}词, {mg._total_ngrams}n-gram")
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    logger.info(f"  语料: {len(lines)}行, {os.path.getsize(filepath)//1024}KB")
    for i in range(0, len(lines), batch_size):
        batch = lines[i:i+batch_size]
        t0 = time.time()
        mg.train(batch)
        dt = time.time() - t0
        print(f"  批{i//batch_size+1}: {len(batch)}条, {dt:.1f}s", end="")
        logger.info(f" → {len(mg._vocab)}词, {mg._total_ngrams}n-gram")
    mg.save(cache)
    logger.info(f"  ✅ 完成: {len(mg._vocab)}词, {mg._total_ngrams}n-gram")
    logger.info(f"  缓存: {cache} ({os.path.getsize(cache)//1024}KB)")
    return mg

if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    logger.info("="*60)
    logger.info("  Markov Batch Trainer")
    logger.info("="*60)
    train_markov_batch("corpus/datasets/fineweb_chinese_5000.txt", 
                       batch_size=500, order=2)
