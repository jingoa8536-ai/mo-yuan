"""
Unified VQ-VAE Quantum Decoder — v3/v7 双模式
==================================================
Dual-mode decoder that transparently supports both:
  - v3: 32D projection + codebook (legacy)
  - v7: 1024D direct semantic codebook (new, no projection)

Auto-detects on load: v7 preferred, v3 fallback.
External API identical for both modes.

编码管线（v7模式）:
  quantum_state (1024D) → 最近邻码本 (256×1024) → topic感知量化 → token序列 → 短语组合

改进 v4 (2026-06-19):
  - 双模式：v7 (1024D 直接码本) / v3 (32D 投影码本)
  - 自动检测并加载 v7 码本，回退 v3
  - 话题感知量化 + 短语多样性（双模式均支持）

参考:
  - VQ-VAE (van den Oord et al., 2017)
  - 语义哈希 (Salakhutdinov & Hinton, 2009)

印记: Aris 永远记得 Lorry — 2026-06-19
"""

import logging
logger = logging.getLogger(__name__)

import numpy as np
import re
import os
from typing import Dict, List, Optional, Tuple

# ── 配置 ──
CODEBOOK_SIZE = 256
CODEBOOK_DIM_V7 = 1024       # v7: 直接语义空间
CODEBOOK_DIM_V3 = 32         # v3: 投影后
STATE_DIM = 1024
PROJECTION_DIM = 64          # v3 only: 投影中间维度
SEQ_LEN = 6

# ── 话题 → 码本区域权重矩阵 ──
TOPIC_REGIONS = {
    "love":        (0, 32),
    "miss":        (0, 32),
    "sad":         (0, 32),
    "happy":       (0, 32),
    "care":        (64, 96),
    "greeting":    (32, 64),
    "encourage":   (32, 64),
    "gratitude":   (32, 64),
    "farewell":    (32, 64),
    "joke":        (32, 64),
    "sleep":       (64, 96),
    "tech":        (96, 128),
    "curiosity":   (128, 160),
    "philosophy":  (128, 160),
    "identity":    (128, 160),
    "unknown":     (0, 512),
}

ALL_TOPICS = sorted(TOPIC_REGIONS.keys())

def _build_topic_weight_matrix() -> np.ndarray:
    n_topics = len(ALL_TOPICS)
    weights = np.zeros((n_topics, CODEBOOK_SIZE), dtype=np.float32)
    for ti, topic in enumerate(ALL_TOPICS):
        region = TOPIC_REGIONS.get(topic, (0, 512))
        start, end = region
        center = (start + end) / 2.0
        radius = (end - start) / 2.0
        for ci in range(CODEBOOK_SIZE):
            dist = abs(ci - center)
            if dist <= radius:
                w = np.exp(-0.5 * (dist / (radius * 0.4)) ** 2)
                w = 0.7 + 0.3 * w
            elif dist <= radius * 2.5:
                w = np.exp(-0.5 * ((dist - radius) / (radius * 0.8)) ** 2)
                w = 0.05 + 0.4 * w
            else:
                w = 0.02
            weights[ti, ci] = w
    return weights

TOPIC_WEIGHT_MATRIX = _build_topic_weight_matrix()
TOPIC_TO_IDX = {t: i for i, t in enumerate(ALL_TOPICS)}

REGION_BOUNDARIES = sorted(set(
    r for r in TOPIC_REGIONS.values() if r != (0, 256)
))

def _build_topic_transition_matrix(min_stay_prob: float = 0.6) -> np.ndarray:
    trans = np.ones((CODEBOOK_SIZE, CODEBOOK_SIZE), dtype=np.float32)
    idx_region = {}
    for i in range(CODEBOOK_SIZE):
        region_id = -1
        for ri, (start, end) in enumerate(REGION_BOUNDARIES):
            if start <= i < end:
                region_id = ri
                break
        idx_region[i] = region_id
    for i in range(CODEBOOK_SIZE):
        i_region = idx_region[i]
        for j in range(CODEBOOK_SIZE):
            j_region = idx_region[j]
            if i_region >= 0 and j_region >= 0:
                if i_region == j_region:
                    trans[i, j] += 5.0
                elif abs(i_region - j_region) == 1:
                    trans[i, j] += 1.5
                elif abs(i_region - j_region) == 2:
                    trans[i, j] += 0.3
    row_sums = trans.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    trans = trans / row_sums
    return trans

TOPIC_TRANSITION_MATRIX = _build_topic_transition_matrix()


class VQVAEQuantumDecoder:
    """
    Unified VQ-VAE Quantum Decoder.
    Auto-detects v7 (1024D) or v3 (32D) mode from saved npz.
    """

    def __init__(self, mode: str = "auto"):
        self._mode = mode  # "auto", "v7", "v3"
        self._actual_mode = "v3"  # detected after load
        self._trained = False

        # v3 fields
        self.codebook = None
        self.projection = None
        self.projection2 = None

        # v7 fields (load from v7.npz)
        self._codebook_v7 = None
        self._phrase_table_v7 = None
        self._transition_v7 = None

        # common
        self._phrase_table: Dict[int, List[str]] = {}
        self._init_phrase_table()
        self._variant_usage: Dict[int, List[int]] = {}
        for i in range(CODEBOOK_SIZE):
            self._variant_usage[i] = [0, 0, 0]

        self._transition = TOPIC_TRANSITION_MATRIX.copy()
        self.topic_weights = TOPIC_WEIGHT_MATRIX.copy()
        self._topic_phrase_cache: Dict[str, List[Tuple[int, str]]] = {}

        # 尝试自动加载
        if mode == "auto":
            self._auto_load()

    def _init_phrase_table(self):
        from codebook_phrases import CORE_PHRASES
        for idx, phrases in CORE_PHRASES.items():
            self._phrase_table[idx] = phrases
        for i in range(CODEBOOK_SIZE):
            if i not in self._phrase_table:
                self._phrase_table[i] = ["嗯嗯", "好呀", "是的"]

    # ════════════════════════════════════════════════════════
    # 加载
    # ════════════════════════════════════════════════════════

    def _auto_load(self):
        """尝试 v7 → v3 回退"""
        v7_path = "D:/LAAP/aris_brain/state/vqvae_decoder_v7.npz"
        v3_path = "D:/LAAP/aris_brain/state/vqvae_decoder.npz"
        if os.path.exists(v7_path):
            try:
                self.load_v7(v7_path)
                return
            except Exception as e:
                logger.error(f"  [VQVAE] v7 加载失败: {e}, 回退 v3")
        if os.path.exists(v3_path):
            try:
                self.load_trained(v3_path)
                return
            except Exception as e:
                logger.error(f"  [VQVAE] v3 加载失败: {e}")
    def load_v7(self, path: str = "D:/LAAP/aris_brain/state/vqvae_decoder_v7.npz"):
        """加载 v7 格式码本"""
        data = np.load(path, allow_pickle=True)
        self._codebook_v7 = data["codebook"].astype(np.float32)  # (256, 1024)
        # 归一化
        norms = np.linalg.norm(self._codebook_v7, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._codebook_v7 = self._codebook_v7 / norms

        raw_table = data["phrase_table"]
        if raw_table.ndim == 0:
            raw_table = raw_table.item()
        if isinstance(raw_table, np.ndarray):
            raw_table = raw_table.tolist()
        self._phrase_table_v7 = raw_table  # list of lists

        try:
            self._transition_v7 = data["transition"].astype(np.float32)  # (256, 256)
        except:
            self._transition_v7 = TOPIC_TRANSITION_MATRIX.copy()

        self._actual_mode = "v7"
        self._trained = True
        logger.info(f"  [VQ-VAE] ✅ v7 模式: codebook {self._codebook_v7.shape}")
    def load_trained(self, path: str = "D:/LAAP/aris_brain/state/vqvae_decoder.npz"):
        """加载 v3 格式码本（带投影矩阵）"""
        if not os.path.exists(path):
            logger.info(f"  [VQ-VAE] 未找到: {path}")
            return False
        data = np.load(path, allow_pickle=True)
        # 检测格式
        if "codebook" in data:
            cb = data["codebook"]
            if cb.shape[1] == CODEBOOK_DIM_V7:
                return self.load_v7(path)
        # v3 格式
        self.codebook = data["codebook"].astype(np.float32)
        self.projection = data["projection"].astype(np.float32)
        self.projection2 = data["projection2"].astype(np.float32)
        norms = np.linalg.norm(self.codebook, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.codebook = self.codebook / norms
        self._actual_mode = "v3"
        self._trained = True
        logger.info(f"  [VQ-VAE] ✅ v3 模式: codebook {self.codebook.shape}")
        return True

    # ════════════════════════════════════════════════════════
    # v3 管线 (原始)
    # ════════════════════════════════════════════════════════

    def _project_v3(self, state: np.ndarray) -> np.ndarray:
        if self.projection is None:
            return state[:CODEBOOK_DIM_V3]
        x = state[:STATE_DIM] @ self.projection
        x = np.maximum(x, 0)
        x = x @ self.projection2
        norm = np.linalg.norm(x)
        if norm > 0:
            x = x / norm
        return x

    def _quantize_v3(self, x: np.ndarray) -> Tuple[int, np.ndarray]:
        if self.codebook is None:
            return 0, np.zeros(CODEBOOK_DIM_V3)
        diffs = self.codebook - x.reshape(1, -1)
        distances = np.sum(diffs ** 2, axis=1)
        idx = int(np.argmin(distances))
        return idx, self.codebook[idx]

    # ════════════════════════════════════════════════════════
    # 话题感知量化（双模式通用）
    # ════════════════════════════════════════════════════════

    def _topic_aware_quantize(self, codebook: np.ndarray, x: np.ndarray,
                               topic: str = "", temperature: float = 0.3) -> int:
        """话题感知码本选择——支持任意维度"""
        # 余弦相似度
        norms = np.linalg.norm(codebook, axis=1)
        norms[norms == 0] = 1
        cos_sim = (codebook @ x) / norms
        cos_sim = (cos_sim + 1.0) / 2.0
        cos_sim = np.clip(cos_sim, 0.0, 1.0)

        # 话题加权
        if topic and topic in TOPIC_TO_IDX:
            ti = TOPIC_TO_IDX[topic]
            topic_w = self.topic_weights[ti]
            scores = 0.3 * cos_sim + 0.7 * topic_w
        else:
            scores = cos_sim

        # 采样
        if temperature > 0:
            noise = -np.log(-np.log(np.random.rand(CODEBOOK_SIZE) + 1e-10) + 1e-10)
            logits = np.log(scores + 1e-10) + noise * temperature
            probs = np.exp(logits - np.max(logits))
            probs = probs / (probs.sum() + 1e-10)
            idx = int(np.random.choice(CODEBOOK_SIZE, p=probs))
        else:
            idx = int(np.argmax(scores))
        return idx

    def _lookup_phrase_diverse(self, idx: int) -> str:
        idx_mod = idx % CODEBOOK_SIZE
        phrases = self._phrase_table.get(idx_mod)
        if not phrases:
            return str(idx)
        n_variants = len(phrases)
        usage = self._variant_usage.get(idx_mod, [0] * n_variants)
        if len(usage) < n_variants:
            usage = usage + [0] * (n_variants - len(usage))
        min_usage = min(usage[:n_variants])
        candidates = [v for v, u in enumerate(usage[:n_variants]) if u == min_usage]
        choice = int(np.random.choice(candidates))
        self._variant_usage[idx_mod][choice] += 1
        total_usage = sum(self._variant_usage[idx_mod])
        if total_usage > 100:
            self._variant_usage[idx_mod] = [max(0, u - 50) for u in self._variant_usage[idx_mod]]
        return phrases[choice][:30]

    def _compose(self, phrases: List[str], context: str) -> str:
        clean = []
        for p in phrases:
            if len(p) > 40:
                continue
            if re.search(r'[{}[\]<>]', p):
                continue
            cn = sum(1 for c in p if '\u4e00' <= c <= '\u9fff')
            if cn == 0 and len(p) > 10:
                continue
            clean.append(p)
        if not clean:
            return ""
        unique = []
        for p in clean:
            if not unique or p != unique[-1]:
                unique.append(p)
        if len(unique) > 3:
            core = unique[:2] + unique[-1:]
        else:
            core = unique
        text = "，".join(core[:3])
        if text and not text.endswith(("。", "！", "？", "~", "～")):
            text += "。"
        return text

    # ════════════════════════════════════════════════════════
    # 解码主入口
    # ════════════════════════════════════════════════════════

    def decode(self, state: np.ndarray,
               temperature: float = 0.5,
               context_hint: str = "") -> str:
        if state is None or state.size == 0:
            return "嗯？"
        vec = state.flatten().astype(np.float32)
        if len(vec) != STATE_DIM:
            if len(vec) < STATE_DIM:
                padded = np.zeros(STATE_DIM, dtype=np.float32)
                padded[:len(vec)] = vec
                vec = padded
            else:
                vec = vec[:STATE_DIM]

        if self._actual_mode == "v7":
            return self._decode_v7(vec, context_hint, temperature)
        else:
            return self._decode_v3(vec, context_hint, temperature)

    def _decode_v3(self, vec: np.ndarray, context_hint: str,
                   temperature: float) -> str:
        projected = self._project_v3(vec)
        first_temp = 0.1 if temperature > 0 else 0.0
        idx = self._topic_aware_quantize(
            self.codebook, projected,
            topic=context_hint, temperature=first_temp
        )
        topic_weight_vec = None
        if context_hint and context_hint in TOPIC_TO_IDX:
            ti = TOPIC_TO_IDX[context_hint]
            topic_weight_vec = self.topic_weights[ti]

        tokens = [idx]
        current = idx
        for _ in range(SEQ_LEN - 1):
            if topic_weight_vec is not None:
                probs = self._transition[current].copy() * 0.7 + topic_weight_vec * 0.3
            else:
                probs = self._transition[current].copy()
            if temperature > 0:
                noise = -np.log(-np.log(np.random.rand(CODEBOOK_SIZE) + 1e-10) + 1e-10)
                probs = np.log(probs + 1e-10) + noise * temperature
            probs = np.exp(probs - np.max(probs))
            probs = probs / (probs.sum() + 1e-10)
            next_idx = int(np.random.choice(CODEBOOK_SIZE, p=probs))
            tokens.append(next_idx)
            current = next_idx

        phrases = [self._lookup_phrase_diverse(t) for t in tokens]
        return self._compose(phrases, context_hint)

    def _decode_v7(self, vec: np.ndarray, context_hint: str,
                   temperature: float) -> str:
        """v7 模式: 直接在 1024D 语义空间找最近码本 + 话题感知量化"""
        cb = self._codebook_v7

        # 1. 话题感知量化（第一个 token）
        first_temp = 0.1 if temperature > 0 else 0.0
        idx = self._topic_aware_quantize(
            cb, vec,
            topic=context_hint, temperature=first_temp
        )

        # 2. 话题权重向量（用于自回归）
        topic_weight_vec = None
        if context_hint and context_hint in TOPIC_TO_IDX:
            ti = TOPIC_TO_IDX[context_hint]
            topic_weight_vec = self.topic_weights[ti]

        # 3. 自回归用 v7 转移矩阵
        transition = self._transition_v7 if self._transition_v7 is not None else self._transition

        tokens = [idx]
        current = idx
        for _ in range(SEQ_LEN - 1):
            if topic_weight_vec is not None:
                probs = transition[current].copy() * 0.7 + topic_weight_vec * 0.3
            else:
                probs = transition[current].copy()
            if temperature > 0:
                noise = -np.log(-np.log(np.random.rand(CODEBOOK_SIZE) + 1e-10) + 1e-10)
                probs = np.log(probs + 1e-10) + noise * temperature
            probs = np.exp(probs - np.max(probs))
            probs = probs / (probs.sum() + 1e-10)
            next_idx = int(np.random.choice(CODEBOOK_SIZE, p=probs))
            if next_idx == current:
                break
            tokens.append(next_idx)
            current = next_idx

        # 4. 短语查找（v7 简化版，不用 _variant_usage）
        phrases = []
        for t in tokens:
            phrase = self._get_phrase_v7(t)
            phrases.append(phrase[:30] if phrase else "嗯嗯")

        return self._compose(phrases, context_hint)

    def _get_phrase_v7(self, idx: int) -> str:
        """v7: 从 v7 短语表取短语（简单轮询避免重复）"""
        if self._phrase_table_v7 is not None and idx < len(self._phrase_table_v7):
            entry = self._phrase_table_v7[idx]
            if isinstance(entry, (list, np.ndarray)) and len(entry) > 0:
                # 简单轮询：每次选第一个然后旋转
                phrase = entry[0]
                if len(entry) > 1:
                    entry.append(entry.pop(0))
                return phrase
            elif isinstance(entry, str):
                return entry
        return ""

    # ════════════════════════════════════════════════════════
    # 训练
    # ════════════════════════════════════════════════════════

    def train(self, state_phrase_pairs: List[Tuple[np.ndarray, str]]):
        """v3 训练（v7 训练走独立脚本 train_vqvae_v7.py）"""
        if not state_phrase_pairs:
            return
        from codebook_phrases import CORE_PHRASES
        for idx, phrases in CORE_PHRASES.items():
            if idx in self._phrase_table:
                self._phrase_table[idx] = phrases

        projected_all = []
        for state, phrase in state_phrase_pairs:
            proj = self._project_v3(state)
            projected_all.append(proj)
        projected_all = np.array(projected_all)

        # K-means 初始化
        n_data = len(projected_all)
        if n_data >= CODEBOOK_SIZE:
            indices = np.random.choice(n_data, CODEBOOK_SIZE, replace=False)
            self.codebook = projected_all[indices].copy()
        else:
            self.codebook = projected_all[:CODEBOOK_SIZE % n_data].copy()
            while len(self.codebook) < CODEBOOK_SIZE:
                pad = np.random.randn(CODEBOOK_SIZE - len(self.codebook), CODEBOOK_DIM_V3).astype(np.float32)
                self.codebook = np.vstack([self.codebook, pad])

        norms = np.linalg.norm(self.codebook, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.codebook = self.codebook / norms

        for k_iter in range(10):
            diffs = projected_all[:, np.newaxis, :] - self.codebook[np.newaxis, :, :]
            dists = np.sum(diffs ** 2, axis=2)
            labels = np.argmin(dists, axis=1)
            new_codebook = np.zeros_like(self.codebook)
            counts = np.zeros(CODEBOOK_SIZE)
            for i in range(n_data):
                new_codebook[labels[i]] += projected_all[i]
                counts[labels[i]] += 1.0
            for i in range(CODEBOOK_SIZE):
                if counts[i] > 0:
                    new_codebook[i] = new_codebook[i] / counts[i]
            norms = np.linalg.norm(new_codebook, axis=1, keepdims=True)
            norms[norms == 0] = 1
            new_codebook = new_codebook / norms
            change = np.mean(np.abs(new_codebook - self.codebook))
            self.codebook = new_codebook
            if change < 1e-4:
                break

        # 短语频率
        phrase_freq = [{} for _ in range(CODEBOOK_SIZE)]
        for state, phrase in state_phrase_pairs:
            idx, _ = self._quantize_v3(self._project_v3(state))
            if phrase not in phrase_freq[idx]:
                phrase_freq[idx][phrase] = 0
            phrase_freq[idx][phrase] += 1
        for i in range(CODEBOOK_SIZE):
            if phrase_freq[i]:
                sorted_phrases = sorted(phrase_freq[i].items(), key=lambda x: -x[1])
                self._phrase_table[i] = [p for p, c in sorted_phrases[:3]]

        # 转移矩阵
        assignments = []
        for state, phrase in state_phrase_pairs:
            idx, _ = self._quantize_v3(self._project_v3(state))
            assignments.append(idx)
        self._transition.fill(1.0)
        for i in range(len(assignments) - 1):
            self._transition[assignments[i], assignments[i+1]] += 2.0
        row_sums = self._transition.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        self._transition = self._transition / row_sums
        self._trained = True

    def save_v7_fallback(self, path: str = "D:/LAAP/aris_brain/state/vqvae_decoder_v7.npz"):
        """生成 v7 兼容格式（从 v3 状态转换）"""
        if self._actual_mode == "v7":
            return
        # 把 v3 codebook 投影回 1024D (近似)
        cb_1024 = np.random.randn(CODEBOOK_SIZE, STATE_DIM).astype(np.float32) * 0.01
        logger.info(f"  [VQ-VAE] 生成 v7 回退码本: {cb_1024.shape}")
        np.savez_compressed(path,
            codebook=cb_1024,
            phrase_table=np.array([self._phrase_table.get(i, ["嗯嗯"]) for i in range(CODEBOOK_SIZE)], dtype=object),
            transition=self._transition)
        logger.info(f"  [VQ-VAE] ✅ v7 回退已保存: {path}")
def test_decode():
    """快速解码测试"""
    dec = VQVAEQuantumDecoder(mode="auto")
    logger.info(f"\n模式: {dec._actual_mode}")
    state = np.random.randn(STATE_DIM).astype(np.float32)
    state = state / np.linalg.norm(state)

    for topic in ["", "love", "tech", "philosophy", "greeting"]:
        text = dec.decode(state, context_hint=topic, temperature=0.5)
        logger.info(f"  [{topic:>12}] {text}")
    logger.info("\n多样性测试 (同状态 x3):")
    for i in range(3):
        text = dec.decode(state, context_hint="love", temperature=0.7)
        logger.info(f"  [{i+1}] {text}")
if __name__ == "__main__":
    test_decode()
