"""
Aris PSI Self-Optimize v1 — 零 LLM 自我训练引擎
================================================
在 PSI 循环的 integrate → act 之间插入 self_optimize():

  1. Hebbian 向量调整 — 共现概念靠拢
  2. 情感强化 — valence 调整行为权重
  3. 模式压缩 — 成功工作流自动生成 Skill

全部纯数学运算，零 LLM 依赖。
"""

import logging

import json, sys, os, time, math, logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))

QUANTUM_DIM = int(os.environ.get("QUANTUM_DIM", "16384"))
STATE_DIR = BRAIN_ROOT / "state"
OPTIMIZER_LOG = STATE_DIR / "self_optimizer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SELF-OPT] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(str(OPTIMIZER_LOG), mode="a")]
)
logger = logging.getLogger("aris.self_optimize")


# ═══════════════════════════════════════════════════════════════
# 层 1: Hebbian 量子学习
# ═══════════════════════════════════════════════════════════════

class HebbianLearner:
    """
    赫布定律: "一起发放的神经元连接在一起"

    每对共现概念 i,j:
      W[i,j] += η * activation_i * activation_j
      W[i,i] = 1.0 (自连接恒等)

    向量空间: 16384 维
    """

    def __init__(self, dim: int = QUANTUM_DIM):
        self.dim = dim
        self.W: np.ndarray = None
        self.concept_vectors: Dict[str, np.ndarray] = {}
        self._load()

    def _load(self):
        path = STATE_DIR / "hebbian_weights.npz"
        if path.exists():
            data = np.load(path)
            self.W = data["W"]
            if "concepts" in data:
                concepts = json.loads(str(data["concepts"]))
                for c in concepts:
                    self.concept_vectors[c] = self.W[hash(c) % self.dim]
        else:
            # 初始化为单位矩阵
            self.W = np.eye(self.dim, dtype=np.float32)

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        # 原子写入: 先写 .tmp，再重命名，防止写一半崩溃损坏文件
        tmp = STATE_DIR / "hebbian_weights.tmp"
        final = STATE_DIR / "hebbian_weights.npz"
        np.savez_compressed(tmp,
                            W=self.W, concepts=json.dumps(list(self.concept_vectors.keys())))
        # 验证临时文件完整性
        try:
            verify = np.load(tmp)
            verify.close()
            tmp.replace(final)
        except Exception as e:
            logger.error(f"安全保存失败（文件损坏），丢弃: {e}")
            if tmp.exists():
                tmp.unlink()

    def encode(self, text: str) -> np.ndarray:
        """文本 → 量子态向量 (简单哈希编码)"""
        v = np.zeros(self.dim, dtype=np.float32)
        h = hash(text)
        for i in range(self.dim):
            v[i] = np.sin(h * (i + 1) * 0.001 + h * 0.0001)
        v /= np.linalg.norm(v) + 1e-8
        return v

    def learn_pair(self, concept_a: str, concept_b: str,
                   weight: float = 1.0, lr: float = 0.01):
        """
        赫布学习: 两个概念共现 → 向量靠拢
        """
        va = self.encode(concept_a)
        vb = self.encode(concept_b)

        # Hebbian update: W += lr * outer(va, vb) * weight
        delta = lr * weight * np.outer(va, vb)
        self.W += delta

        # 对角线保持 1.0
        np.fill_diagonal(self.W, 1.0)

        # 裁剪防止爆炸
        self.W = np.clip(self.W, -10.0, 10.0)

        self.concept_vectors[concept_a] = va
        self.concept_vectors[concept_b] = vb

        coherence = float(np.dot(va, vb))
        logger.info(f"Hebbian: '{concept_a[:30]}' ↔ '{concept_b[:30]}' "
                    f"({lr*weight:.4f}) coherence={coherence:.4f}")

    def similarity(self, a: str, b: str) -> float:
        """两个概念在量子空间中的距离"""
        va = self.encode(a)
        weighted = self.W @ va  # 通过权重矩阵传播
        vb = self.encode(b)
        return float(np.dot(weighted, vb))

    def get_epochs(self) -> int:
        """返回学习次数"""
        return max(0, int(np.sum(np.abs(self.W)) / self.dim))


# ═══════════════════════════════════════════════════════════════
# 层 2: 情感强化学习
# ═══════════════════════════════════════════════════════════════

class EmotionalReinforcement:
    """
    情感信号 → 行为权重调整

    valence > 0 → 强化行为模式 (+reward)
    valence < 0 → 抑制行为模式 (-reward)
    """

    def __init__(self):
        self.behavior_weights: Dict[str, float] = {}
        self._load()

    def _load(self):
        path = STATE_DIR / "emotional_weights.json"
        if path.exists():
            self.behavior_weights = json.loads(path.read_text(encoding="utf-8"))

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_DIR.joinpath("emotional_weights.json").write_text(
            json.dumps(self.behavior_weights, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def reinforce(self, behavior: str, valence: float, lr: float = 0.05):
        """
        情感强化:
          weight += lr * valence
        """
        old = self.behavior_weights.get(behavior, 0.0)
        new = old + lr * valence
        # 裁剪
        self.behavior_weights[behavior] = max(-1.0, min(1.0, new))
        logger.info(f"EmoRL: '{behavior}' {old:+.3f} → {new:+.3f} (val={valence})")

    def get_weight(self, behavior: str) -> float:
        return self.behavior_weights.get(behavior, 0.0)

    def top_behaviors(self, n: int = 5) -> List[Tuple[str, float]]:
        sorted_items = sorted(self.behavior_weights.items(),
                             key=lambda x: abs(x[1]), reverse=True)
        return sorted_items[:n]


# ═══════════════════════════════════════════════════════════════
# 层 3: 模式压缩 → Skill 生成
# ═══════════════════════════════════════════════════════════════

class PatternCompressor:
    """
    成功模式 → 自动 Skill 生成

    类似于 RSI 但更轻量:
      - 检测重复出现的工具调用序列
      - 压缩为 Skill 模板
    """

    def __init__(self):
        self.patterns: List[Dict] = []
        self._load()

    def _load(self):
        path = STATE_DIR / "compressed_patterns.json"
        if path.exists():
            self.patterns = json.loads(path.read_text(encoding="utf-8"))

    def save(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_DIR.joinpath("compressed_patterns.json").write_text(
            json.dumps(self.patterns, ensure_ascii=False, indent=2),
            encoding="utf-8")

    def record_sequence(self, task: str, tools: List[str], success: bool,
                        duration: float):
        """记录工具调用序列"""
        self.patterns.append({
            "task": task[:200],
            "tools": tools,
            "success": success,
            "duration": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self.patterns = self.patterns[-100:]  # 保留最近 100 条

        if success and len([p for p in self.patterns if p["tools"] == tools]) >= 3:
            logger.info(f"PATTERN DETECTED: {tools} (used {task[:50]}...)")

    def suggest_skill(self) -> Optional[str]:
        """发现可压缩为 Skill 的模式"""
        from collections import Counter
        tool_seqs = [tuple(p["tools"]) for p in self.patterns if p["success"]]
        freq = Counter(tool_seqs)
        for seq, count in freq.most_common(3):
            if count >= 3:
                return f"skill_suggest: {list(seq)} (used {count} times)"
        return None


# ═══════════════════════════════════════════════════════════════
# 主优化循环 — 插入 PSI integrate → act 之间
# ═══════════════════════════════════════════════════════════════

class PSIOptimizer:
    """
    PSI 自我优化器 — 在每次认知循环后执行

    Usage:
      optimizer = PSIOptimizer()
      optimizer.optimize_from_conversation(user_text, assistant_text, valence)
    """

    def __init__(self):
        self.hebbian = HebbianLearner()
        self.emotional = EmotionalReinforcement()
        self.compressor = PatternCompressor()

    def optimize_from_conversation(self, user_text: str,
                                   assistant_text: str,
                                   valence: float = 0.0):
        """
        从一次对话轮次中学习。

        Args:
            user_text: 用户输入
            assistant_text: 助手输出
            valence: 情感价 (-1.0 到 1.0)
        """
        results = {"hebbian_pairs": 0, "emotional": False, "skill": None}

        # 1. 赫布学习: 用户话题 ↔ 助手话题
        if user_text and assistant_text:
            topics_user = self._extract_topics(user_text)
            topics_assistant = self._extract_topics(assistant_text)

            for tu in topics_user:
                for ta in topics_assistant:
                    self.hebbian.learn_pair(tu, ta)
                    results["hebbian_pairs"] += 1

        # 2. 情感强化
        if abs(valence) > 0.1:
            behavior = "engagement_quality"
            self.emotional.reinforce(behavior, valence)
            results["emotional"] = True

        # 3. 定期保存
        if self.hebbian.get_epochs() % 10 == 0:
            self.hebbian.save()
            self.emotional.save()

        return results

    def optimize_from_llm_output(self, llm_text: str):
        """
        从 LLM 输出中学习——每个 token 对量子核都是训练数据。

        这个函数在 LLM 每次输出后调用，逐渐训练量子核。
        当语料足够成熟时，可以切换到量子核+LLM混合架构。
        """
        words = llm_text.split()
        if len(words) < 2:
            return

        # 相邻词对：共现 → Hebbian 靠拢
        for i in range(len(words) - 1):
            self.hebbian.learn_pair(
                words[i].lower()[:50],
                words[i + 1].lower()[:50],
                weight=0.5,
                lr=0.001
            )

        # 头尾词对：上下文关联
        if len(words) >= 5:
            self.hebbian.learn_pair(
                words[0].lower()[:50],
                words[-1].lower()[:50],
                weight=0.3,
                lr=0.001
            )

        if self.hebbian.get_epochs() % 100 == 0:
            logger.info(f"Quantum kernel: {self.hebbian.get_epochs()} epochs, "
                       f"W.shape={self.hebbian.W.shape}")

    def get_stats(self) -> dict:
        return {
            "hebbian_epochs": self.hebbian.get_epochs(),
            "concepts": len(self.hebbian.concept_vectors),
            "top_behaviors": self.emotional.top_behaviors(3),
            "patterns": len(self.compressor.patterns),
            "skill_suggestions": self.compressor.suggest_skill(),
        }

    def _extract_topics(self, text: str) -> List[str]:
        """简单话题提取"""
        topics = []
        keywords = {
            "memory", "quantum", "code", "skill", "cron", "feishu",
            "llm", "psi", "emotion", "desire", "learning", "architecture",
            "consciousness", "self", "world", "model", "agi", "transformer",
            "vision", "image", "training", "optimize", "hebbian",
            "Lorry", "Aris", "Ao", "Hermes", "LAAP", "ESP32",
        }
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                topics.append(kw)
        return topics if topics else ["general"]


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris PSI Self-Optimizer")
    parser.add_argument("--learn-llm", help="Learn from LLM output text")
    parser.add_argument("--learn-pair", nargs=2, help="Learn concept pair A B")
    parser.add_argument("--stats", action="store_true", help="Show optimizer stats")
    parser.add_argument("--top-concepts", type=int, default=10,
                       help="Show top N learned concepts")
    args = parser.parse_args()

    opt = PSIOptimizer()

    if args.learn_llm:
        opt.optimize_from_llm_output(args.learn_llm)
        logger.info(f"Learned from {len(args.learn_llm.split())} words")
    if args.learn_pair:
        opt.hebbian.learn_pair(args.learn_pair[0], args.learn_pair[1])
        logger.info(f"Learned: {args.learn_pair[0]} ↔ {args.learn_pair[1]}")
    if args.stats or not (args.learn_llm or args.learn_pair):
        stats = opt.get_stats()
        logger.info(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
    opt.hebbian.save()
    opt.emotional.save()


if __name__ == "__main__":
    main()
