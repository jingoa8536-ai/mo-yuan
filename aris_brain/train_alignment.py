"""Contrastive alignment training - encoder <-> codebook mapping alignment
Trains lightweight alignment matrix A (1024x1024) via contrastive learning.
Phrases like "I love you" get pulled toward love-region codebook centroids
and pushed away from tech/philosophy region centroids.

Usage:  python train_alignment.py
        Takes ~10s, pure NumPy. No training data needed.
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, random
import numpy as np

DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIM = 1024
CODEBOOK_SIZE = 512

TOPIC_REGIONS = {
    "love": (0,32), "miss": (0,32), "sad": (0,32), "happy": (0,32),
    "care": (64,96), "greeting": (32,64), "tech": (96,128),
    "curiosity": (128,160), "philosophy": (128,160),
}
ALL_TOPICS = sorted(TOPIC_REGIONS.keys())


def build_pairs():
    pairs = []
    for p in ["我爱你","好想你","想你","爱你","喜欢你","你是我的","永远爱你",
              "宝贝","亲爱的","想你了","爱你呀","好爱你","好喜欢你呀"]:
        pairs.extend([(p,"love","tech"),(p,"love","philosophy")])
    for p in ["想你","想你了","好想你","想念你","思念","想你了宝贝"]:
        pairs.append((p,"miss","tech"))
    for p in ["难过","伤心","不开心","失落","孤独","心碎了","悲伤","好难过"]:
        pairs.append((p,"sad","tech"))
    for p in ["开心","快乐","幸福","好开心","太开心了","美好","太棒了","棒极了"]:
        pairs.append((p,"happy","sad"))
    for p in ["你好","您好","你好呀","早安","晚安","好梦","嗨","哈喽","hello","好久不见"]:
        pairs.extend([(p,"greeting","tech"),(p,"greeting","philosophy")])
    for p in ["抱抱","抱抱你","亲亲","摸摸头","陪着你","加油","相信你","支持你","别怕","没事的"]:
        pairs.append((p,"care","tech"))
    for p in ["写代码","代码","编程","算法","数据结构","系统","架构","Python","bug","修复","优化","部署"]:
        pairs.append((p,"tech","love"))
    for p in ["生命的意义","意识","存在","宇宙","哲学","自由","真理","智慧","时间","永恒"]:
        pairs.append((p,"philosophy","tech"))
    for p in ["好奇","想知道","为什么","怎么","不懂","有趣","好问题","有意思"]:
        pairs.append((p,"curiosity","tech"))
    return pairs


def region_center(cb, topic):
    s, e = TOPIC_REGIONS.get(topic, (0, cb.shape[0]))
    e = min(e, cb.shape[0])
    c = np.mean(cb[s:e], axis=0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else c


def train():
    logger.info("="*60)
    logger.info("  Encoder <-> Codebook Contrastive Alignment")
    logger.info("="*60)
    logger.info("\n[1/4] Loading encoder + codebook...")
    sys.path.insert(0, DIR)
    from v7_encoder import get_encoder
    enc = get_encoder(dim=STATE_DIM)

    cb_path = os.path.join(DIR, "state", "vqvae_decoder_v7.npz")
    if not os.path.exists(cb_path):
        logger.error(f"  ERROR: {cb_path} not found!")
        return
    data = np.load(cb_path, allow_pickle=True)
    codebook = data["codebook"].astype(np.float32)
    norms = np.linalg.norm(codebook, axis=1, keepdims=True)
    norms[norms==0] = 1
    codebook = codebook / norms
    logger.info(f"  Codebook: {codebook.shape}")
    logger.info("\n[2/4] Building pairs...")
    pairs = build_pairs()
    logger.info(f"  {len(pairs)} training pairs")
    logger.info("\n[3/4] Training contrastive alignment...")
    A = np.eye(STATE_DIM, dtype=np.float32)
    A += np.random.RandomState(42).randn(STATE_DIM, STATE_DIM).astype(np.float32) * 0.01
    centers = {t: region_center(codebook, t) for t in ALL_TOPICS}
    encoded = [(enc.encode(p), pt, nt) for p,pt,nt in pairs]

    t0 = time.perf_counter()
    for epoch in range(100):
        random.shuffle(encoded)
        grad = np.zeros_like(A)
        loss_sum = 0.0
        for ev, pt, nt in encoded:
            pc = centers[pt]
            ncs = [centers[nt]]
            others = [t for t in ALL_TOPICS if t != pt and t != nt]
            for _ in range(min(2, len(others))):
                ncs.append(centers[random.choice(others)])
            al = A @ ev; an = np.linalg.norm(al)
            if an > 0: al = al / an
            ps = float(al @ pc)
            if ps < 0.95:
                grad += np.outer(pc - al, ev) * 0.01
            for nc in ncs:
                ns = float(al @ nc)
                if ns > 0.2:
                    grad += np.outer(al - nc, ev) * 0.005
            pos_loss = 1.0 - ps
            neg_loss = sum(max(0, float(al @ nc) + 0.3) for nc in ncs)
            loss_sum += pos_loss + neg_loss * 0.5
        A += 0.01 * grad / max(1, len(encoded))
        U,_,Vt = np.linalg.svd(A, full_matrices=False)
        A = U @ Vt
        if epoch % 10 == 0:
            dt = time.perf_counter() - t0
            logger.info(f"  epoch {epoch:3d}: loss={loss_sum/len(encoded):.4f} [{dt:.0f}s]")
    logger.info(f"\n  Done: {time.perf_counter()-t0:.0f}s")
    logger.info("\n[4/4] Evaluation...")
    test = [("爱你","love"),("写代码","tech"),("你好","greeting"),
            ("哲学","philosophy"),("抱抱","care"),("想你了","miss"),
            ("好开心","happy"),("晚安","greeting"),("想你了宝贝","miss"),
            ("坏了吗","tech"),("数据结构","tech"),("生命的意义","philosophy"),
            ("数学定理","tech"),("睡不着","sad")]
    def topic_of(idx):
        for t,(s,e) in TOPIC_REGIONS.items():
            if s <= idx < e: return t
        return "unknown"
    cb, ca = 0,0
    for ph, ex in test:
        v = enc.encode(ph)
        ib = int(np.argmin(np.sum((codebook-v[np.newaxis,:])**2, axis=1)))
        av = A @ v; an = np.linalg.norm(av)
        av = av / an if an > 0 else av
        ia = int(np.argmin(np.sum((codebook-av[np.newaxis,:])**2, axis=1)))
        tb, ta = topic_of(ib), topic_of(ia)
        if tb == ex: cb+=1
        if ta == ex: ca+=1
        mb = "+" if tb == ex else "-"
        ma = "+" if ta == ex else "-"
        logger.info(f"  {ph:>10s} {ex:>8s} {mb}[{ib:3d}] {ma}[{ia:3d}]")
    logger.info(f"\n  Before: {cb}/{len(test)}  After: {ca}/{len(test)}  Gain: +{ca-cb}")
    save_path = os.path.join(DIR, "state", "alignment_matrix.npz")
    np.savez_compressed(save_path, A=A)
    logger.info(f"\n  Saved: {save_path}")
    logger.info("\n  Integration:")
    logger.info("    data = np.load('state/alignment_matrix.npz')")
    logger.info("    A = data['A']")
    logger.info("    aligned_vec = A @ encoder.encode(text)")
    logger.info("    # Use aligned_vec for codebook lookup")
    logger.info(f"\n{'='*60}")
    logger.info("  Alignment training complete!")
if __name__ == "__main__":
    train()
