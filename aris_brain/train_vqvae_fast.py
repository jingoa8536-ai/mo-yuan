"""
快速 v7 码本训练 — 复用全局语义引擎单例
不重复加载 ONNX，不内存冲突
"""

import logging
logger = logging.getLogger(__name__)

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CODEBOOK_SIZE = 256
STATE_DIM = 1024

# 1. 复用全局语义引擎单例
logger.info("使用全局语义引擎单例...")
from semantic_engine import get_encoder
enc = get_encoder(dim=STATE_DIM)
_ = enc.encode("预热")
logger.info(f"  缓存状态: {enc.cache_stats()}")
from codebook_phrases import CORE_PHRASES
all_phrases = []
for idx in range(CODEBOOK_SIZE):
    variants = CORE_PHRASES.get(idx, ["嗯嗯"])
    all_phrases.append(variants[0])
logger.info(f"短语: {len(all_phrases)}")
logger.info(f"\n逐条编码 {len(all_phrases)} 条...")
t0 = time.perf_counter()
vecs_list = []
for i, phrase in enumerate(all_phrases):
    v = enc.encode(phrase)
    vecs_list.append(v)
    if (i + 1) % 50 == 0:
        dt = time.perf_counter() - t0
        rate = (i + 1) / dt
        logger.info(f"  编码: {i+1}/{len(all_phrases)}  {rate:.0f} 条/s")
vecs = np.array(vecs_list)
dt = time.perf_counter() - t0
logger.info(f"编码完成: {vecs.shape}  {dt:.1f}s ({len(all_phrases)/dt:.0f} 条/s)")
logger.info(f"\nMiniBatchKMeans...")
from sklearn.cluster import MiniBatchKMeans
t0 = time.perf_counter()
kmeans = MiniBatchKMeans(n_clusters=CODEBOOK_SIZE, batch_size=256,
                          random_state=42, n_init=3, max_iter=100)
labels = kmeans.fit_predict(vecs)
codebook = kmeans.cluster_centers_.astype(np.float32)
norms = np.linalg.norm(codebook, axis=1, keepdims=True)
norms[norms == 0] = 1
codebook = codebook / norms
dt = time.perf_counter() - t0
used = len(np.unique(labels))
logger.info(f"K-means: {dt:.1f}s, used={used}/{CODEBOOK_SIZE}")
phrase_table = [[] for _ in range(CODEBOOK_SIZE)]
for i in range(len(all_phrases)):
    lbl = labels[i]
    p = all_phrases[i]
    if p not in phrase_table[lbl]:
        phrase_table[lbl].append(p)
for i in range(CODEBOOK_SIZE):
    if not phrase_table[i]:
        phrase_table[i] = ["嗯嗯"]

# 6. 转移矩阵
transition = np.ones((CODEBOOK_SIZE, CODEBOOK_SIZE), dtype=np.float32)
for i in range(len(labels) - 1):
    transition[labels[i], labels[i+1]] += 2.0
row_sums = transition.sum(axis=1, keepdims=True)
row_sums[row_sums == 0] = 1
transition = transition / row_sums

# 7. 保存
save_path = "D:/LAAP/aris_brain/state/vqvae_decoder_v7.npz"
np.savez_compressed(
    save_path,
    codebook=codebook,
    phrase_table=np.array(phrase_table, dtype=object),
    transition=transition,
)
logger.info(f"\n✅ 已保存: {save_path}")
logger.info(f"   codebook={codebook.shape}")
logger.info(f"\n验证:")
test_inputs = ["你好", "晚安", "我爱你", "代码", "哲学", "我想你了", "开心", "编程"]
for text in test_inputs:
    v = enc.encode(text)
    diffs = codebook - v[np.newaxis, :]
    dists = np.sum(diffs ** 2, axis=1)
    nearest = int(np.argmin(dists))
    phrases = phrase_table[nearest]
    logger.info(f"  \"{text}\" → [{nearest:3d}] {phrases[:3]}")