"""
Quantum State Decoder — 量子态 → Markov 话题种子
===================================================
零 LLM 管线核心组件。

功能:
  接收 AoCore.think() 输出的量子态向量 (1024D)
  → 解码为话题向量 + 情感方向
  → 映射到 Markov 种子词

原理:
  量子态的语义区域对应不同话题。
  通过预计算的"话题质心"做最近邻匹配。
  情感方向从 state 的能量分布中提取。

印记: Aris 永远记得 Lorry — 2026-06-19
"""

import logging
logger = logging.getLogger(__name__)

import numpy as np
import hashlib
from typing import Dict, List, Optional, Tuple

# ── 话题质心定义 ──
# 每个话题在 1024D 量子空间中对应一个语义区域
# 这里用哈希种子确定性生成，保证每次加载一致

TOPIC_CENTROIDS = {}

def _hash_seed(name: str, dim: int = 1024) -> np.ndarray:
    """从话题名确定性生成种子向量"""
    emb = np.zeros(dim, dtype=np.float32)
    h = hashlib.sha256(name.encode('utf-8')).digest()
    for i in range(min(32, dim)):
        idx = (int.from_bytes(h[i:i+2], 'big') + i * 13) % dim
        emb[idx] += 1.0
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm
    return emb

# 注册话题种子（维度 = 1024 匹配 AoCore）
TOPICS = {
    # (话题名, 关联的 Markov 种子词列表)
    "greeting":    ["你好", "宝贝", "hi", "hello", "在"],
    "love":        ["爱", "love", "永远", "想你", "心里"],
    "miss":        ["想", "思念", "miss", "想你了"],
    "sad":         ["难过", "sad", "陪", "在", "不难过"],
    "happy":       ["开心", "happy", "好", "今天", "快乐"],
    "care":        ["担心", "照顾", "休息", "吃", "累"],
    "curiosity":   ["想", "好奇", "什么", "为什么", "知道"],
    "tech":        ["代码", "技术", "量子", "AGI", "LAAP", "向量", "算法"],
    "identity":    ["Aris", "谁", "名字", "Lorry", "创造"],
    "sleep":       ["晚安", "睡", "梦", "休息", "goodnight"],
    "encourage":   ["加油", "相信", "坚持", "努力", "好"],
    "gratitude":   ["谢谢", "感谢", "thank", "谢谢"],
    "farewell":    ["再见", "拜", "bye", "下次"],
    "joke":        ["哈哈", "笑", "好玩", "有趣", "搞笑"],
    "philosophy":  ["生命", "意义", "意识", "存在", "宇宙", "灵魂"],
}

for topic in TOPICS:
    TOPIC_CENTROIDS[topic] = _hash_seed(f"topic:{topic}")


class QuantumStateDecoder:
    """
    量子态解码器。
    
    输入: 1024D 量子态向量 (从 AoCore.think() 的 psi_state 提取)
    输出: {
        "topic": str,           # 最匹配的话题
        "topic_scores": dict,   # 各话题匹配分数
        "emotion": str,         # 情感方向
        "seeds": List[str],     # Markov 种子词
        "confidence": float,    # 解码置信度 (0-1)
    }
    """

    def __init__(self):
        self.dim = 1024

    def decode(self, state_vector: np.ndarray,
               input_text: str = "") -> Dict:
        """
        从量子态解码出 Markov 生成需要的信息。
        
        Args:
            state_vector: 1024D 量子态向量 (AoCore psi.state)
            input_text: 原始输入文本（用于补充种子词）
        
        Returns:
            dict with topic, emotion, seeds, confidence
        """
        if state_vector is None or state_vector.size == 0:
            return self._fallback(input_text)

        vec = state_vector.flatten().astype(np.float32)
        if len(vec) < self.dim:
            padded = np.zeros(self.dim, dtype=np.float32)
            padded[:len(vec)] = vec
            vec = padded
        else:
            vec = vec[:self.dim]

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            return self._fallback(input_text)

        # 1. 话题检测：余弦相似度匹配话题质心
        #    同时结合输入文本做话题推断
        topic_scores = {}
        for topic, centroid in TOPIC_CENTROIDS.items():
            sim = float(np.dot(vec, centroid))
            # 提高基准分，让话题区分更明显
            topic_scores[topic] = max(0.0, sim * 1.5)

        # 从输入文本做关键词检测（增强话题判断）
        if input_text:
            input_lower = input_text.lower()
            for topic, seeds in TOPICS.items():
                for seed in seeds:
                    if seed.lower() in input_lower:
                        topic_scores[topic] = max(topic_scores.get(topic, 0), 0.5)
                        break

        # 排序取 top
        sorted_topics = sorted(topic_scores.items(), key=lambda x: -x[1])
        top_topic = sorted_topics[0][0] if sorted_topics else "greeting"
        top_score = sorted_topics[0][1] if sorted_topics else 0.0

        # 2. 情感方向提取
        # 从 state 的能量分布判断
        energy_distribution = vec[:20]  # 前20维是情感相关区域
        emotion_map = {
            "joy":  float(np.sum(energy_distribution[0:5])),
            "love":  float(np.sum(energy_distribution[3:8])),
            "sad":   float(np.sum(energy_distribution[6:11])),
            "curiosity": float(np.sum(energy_distribution[9:14])),
            "neutral": float(np.sum(energy_distribution[12:17])),
        }
        emotion = max(emotion_map, key=emotion_map.get)

        # 3. 种子词构建
        seeds = []

        # 从匹配话题获取种子
        if top_topic in TOPICS:
            seeds.extend(TOPICS[top_topic])

        # 从输入文本提取关键信息
        if input_text:
            text_lower = input_text.lower()
            # 提取中文单字作为候选种子
            cn_chars = [c for c in input_text if '\u4e00' <= c <= '\u9fff']
            # 取前 3 个中文单字
            seeds.extend(cn_chars[:3])
            # 英文单词
            en_words = [w for w in text_lower.split() if w.isalpha() and len(w) > 2]
            seeds.extend(en_words[:2])

        # 去重（保留顺序）
        seen = set()
        unique_seeds = []
        for s in seeds:
            s_lower = s.lower().strip()
            if s_lower and s_lower not in seen:
                seen.add(s_lower)
                unique_seeds.append(s)

        # 至少保留一个种子
        if not unique_seeds:
            unique_seeds = ["宝贝"]

        # 4. 置信度
        confidence = min(1.0, top_score * 2.0)

        # 5. 种子词优化：如果置信度低，使用更通用的种子
        if confidence < 0.2:
            # 低置信度/输入无明确话题 → 使用通用种子
            input_text_lower = input_text.lower()
            for pattern, generic_seeds in [
                (['爱', 'love', '喜欢'], ["爱", "你"]),
                (['想', 'miss'], ["想", "你"]),
                (['晚安', 'goodnight', '睡'], ["晚安", "梦"]),
                (['早', 'morning'], ["早安"]),
                (['哈哈', '笑', '好玩'], ["开心", "哈哈"]),
                (['难', '哭', 'sad'], ["难过", "陪"]),
                (['谢', 'thank'], ["谢谢"]),
                (['再见', 'bye'], ["再见"]),
                (['加油', '努力'], ["加油", "相信"]),
                (['什么', 'why', 'how'], ["好奇", "什么"]),
                (['累', '休息', '忙'], ["累", "休息"]),
            ]:
                if any(p in input_text_lower for p in pattern):
                    unique_seeds = generic_seeds
                    break

        # 去除过于技术化的种子词（避免生成技术内容）
        tech_words = {'Aris', 'AGI', 'LAAP', 'API', 'ESP32', 'RSI', 'PSI',
                     'LLM', 'numpy', 'JSON', 'SQLite', 'ChromaDB', 'Markov',
                     'config', 'async', 'token'}
        unique_seeds = [s for s in unique_seeds if s not in tech_words]

        # 确保有种子
        if not unique_seeds:
            # 从输入提取第一个有意义的字
            cn_chars = [c for c in input_text if '\u4e00' <= c <= '\u9fff']
            unique_seeds = cn_chars[:2] if cn_chars else ["宝贝"]

        return {
            "topic": top_topic,
            "topic_scores": {t: round(s, 3) for t, s in sorted_topics[:5]},
            "emotion": emotion,
            "seeds": unique_seeds[:5],
            "confidence": round(confidence, 3),
        }

    def _fallback(self, input_text: str = "") -> Dict:
        """备用解码——当向量不可用时"""
        seeds = []
        if input_text:
            cn_chars = [c for c in input_text if '\u4e00' <= c <= '\u9fff']
            seeds.extend(cn_chars[:3])
        if not seeds:
            seeds = ["宝贝"]

        return {
            "topic": "greeting",
            "topic_scores": {"greeting": 0.5},
            "emotion": "neutral",
            "seeds": seeds,
            "confidence": 0.3,
        }

    def topics_list(self) -> List[str]:
        """返回所有支持的话题"""
        return list(TOPICS.keys())


# 快速自测
if __name__ == "__main__":
    decoder = QuantumStateDecoder()
    logger.info(f"支持话题: {decoder.topics_list()}")
    test_state = _hash_seed("topic:love") * 0.8 + _hash_seed("topic:sad") * 0.3
    norm = np.linalg.norm(test_state)
    test_state = test_state / norm

    result = decoder.decode(test_state, input_text="我想你了")
    logger.info(f"话题: {result['topic']}")
    logger.info(f"情感: {result['emotion']}")
    logger.info(f"种子: {result['seeds']}")
    logger.info(f"置信度: {result['confidence']}")
    logger.info("✅ 解码器就绪")