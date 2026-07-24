"""
Aris PSI Trainer — 量子核自我优化器
====================================
不依赖 LLM 训练信号，纯数学驱动。

三层训练机制：
  L1: Hebbian 学习 — 同时出现的概念向量靠拢
  L2: 模式压缩 — 成功工作流自动生成 Skill
  L3: 情感强化 — Lorry 的情绪作为奖励信号

核心: LLM 每输出一个字，量子核就学一步。
      语料足够时，量子核接管 → 混合架构。

速度: 每步 < 1ms，零 LLM 依赖。
"""

import logging

import numpy as np
import json, time, os, logging
from pathlib import Path
from datetime import datetime, timezone
from collections import deque
from typing import List, Dict, Optional, Tuple

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
STATE_DIR = BRAIN_ROOT / "state"
QUANTUM_DIR = BRAIN_ROOT / "quantum_state"
QUANTUM_DIM = int(os.environ.get("ARIS_QUANTUM_DIM", "16384"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PSI-TRAINER] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(STATE_DIR / "psi_trainer.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.psi_trainer")


class PSITrainer:
    """
    PSI 自我优化器 — 接入 PSI 循环的 integrate → act 之间。
    
    输入: LLM 输出文本, 情感价(valence), 任务成功/失败标记
    输出: 更新的量子核向量, 新生成的 Skill, 学习统计
    """

    def __init__(self, dim: int = QUANTUM_DIM):
        self.dim = dim
        self.hebbian_rate = 0.05  # Hebbian 学习率
        self.valence_scale = 0.11  # 情感强化幅度
        self.decay_rate = 0.001   # 遗忘率
        
        # 短期工作缓冲区 (最近 100 对概念)
        self.recent_pairs: deque = deque(maxlen=100)
        
        # 概念向量存储
        self.concept_space: Dict[str, np.ndarray] = {}
        self.concept_frequencies: Dict[str, int] = {}
        
        # 成功模式库
        self.success_patterns: List[Dict] = []
        
        # 统计
        self.stats = {
            "hebbian_steps": 0,
            "patterns_extracted": 0,
            "valence_signals": 0,
            "total_concepts": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        
        self._load_state()

    # ═══════════════════════════════════════════════════════════
    # L1: Hebbian 学习 — "一起发放的一起连接"
    # ═══════════════════════════════════════════════════════════

    def _tokenize_to_concepts(self, text: str) -> List[str]:
        """从 LLM 输出中提取核心概念词"""
        # 中文: 按词切分; 英文: 按空格
        import re
        # 中文词组 (2-4字)
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        # 英文关键词 (3+字母)
        english_words = re.findall(r'[a-zA-Z]{3,}', text)
        
        concepts = []
        for w in chinese_words[:20]:
            concepts.append(w)
        for w in english_words[:10]:
            concepts.append(w.lower())
        
        # 去重保留顺序
        seen = set()
        result = []
        for c in concepts:
            if c not in seen:
                seen.add(c)
                result.append(c)
        
        return result

    def _get_or_create_vector(self, concept: str) -> np.ndarray:
        """获取或创建概念向量 (量子叠加态初始化)"""
        if concept not in self.concept_space:
            # 用 hash 做确定性初始化
            seed = hash(concept) % (2**31)
            rng = np.random.RandomState(seed)
            v = rng.randn(self.dim).astype(np.float32)
            v /= np.linalg.norm(v)  # 归一化到单位超球面
            self.concept_space[concept] = v
            self.concept_frequencies[concept] = 0
            self.stats["total_concepts"] += 1
        
        self.concept_frequencies[concept] += 1
        return self.concept_space[concept]

    def hebbian_step(self, text: str):
        """
        Hebbian 学习步：同时出现的概念向量相互靠拢。
        
        数学: v_new = v_old + η × Σ(邻居向量)
        等价于: 如果两个概念经常一起出现，它们的向量夹角缩小。
        """
        concepts = self._tokenize_to_concepts(text)
        if len(concepts) < 2:
            return
        
        vectors = [self._get_or_create_vector(c) for c in concepts]
        
        # Hebbian: 每个向量向所有同时出现的其他向量靠拢
        for i, vi in enumerate(vectors):
            neighbors = [v for j, v in enumerate(vectors) if j != i]
            if not neighbors:
                continue
            
            # 平均邻居方向
            neighbor_avg = np.mean(neighbors, axis=0)
            neighbor_avg /= np.linalg.norm(neighbor_avg) + 1e-8
            
            # 靠拢
            vi_new = vi + self.hebbian_rate * neighbor_avg
            vi_new /= np.linalg.norm(vi_new)
            
            self.concept_space[concepts[i]] = vi_new
        
        # 全局轻微衰减 (模拟遗忘)
        if self.stats["hebbian_steps"] % 100 == 0:
            self._global_decay()
        
        self.stats["hebbian_steps"] += 1
        logger.debug(f"Hebbian step {self.stats['hebbian_steps']}: {len(concepts)} concepts")

    def _global_decay(self):
        """全局遗忘：低频概念向量慢慢回归随机"""
        total_freq = sum(self.concept_frequencies.values()) or 1
        for concept, freq in list(self.concept_frequencies.items()):
            relative_freq = freq / total_freq
            if relative_freq < 0.001 and concept in self.concept_space:
                v = self.concept_space[concept]
                noise = np.random.randn(self.dim).astype(np.float32) * self.decay_rate
                v = v + noise
                v /= np.linalg.norm(v)
                self.concept_space[concept] = v

    # ═══════════════════════════════════════════════════════════
    # L2: 模式压缩 — 成功工作流 → 自动生成 Skill
    # ═══════════════════════════════════════════════════════════

    def extract_pattern(self, task: str, steps: List[str], success: bool):
        """
        从成功任务中提取可复用模式。
        
        Args:
            task: 任务描述
            steps: 执行步骤列表
            success: 是否成功
        """
        if not success or len(steps) < 2:
            return None
        
        # 提取模式特征
        pattern = {
            "task_type": self._classify_task(task),
            "steps_count": len(steps),
            "key_concepts": self._tokenize_to_concepts(task),
            "step_signatures": [self._tokenize_to_concepts(s) for s in steps],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": True,
        }
        
        # 检查是否与已有模式相似
        for existing in self.success_patterns:
            overlap = len(set(pattern["key_concepts"]) & set(existing["key_concepts"]))
            if overlap >= len(pattern["key_concepts"]) * 0.7:
                # 合并强化已有模式
                existing["reinforcement"] = existing.get("reinforcement", 0) + 1
                logger.debug(f"Reinforced pattern: {existing['task_type']} (×{existing['reinforcement']})")
                return None
        
        self.success_patterns.append(pattern)
        self.stats["patterns_extracted"] += 1
        
        # 如果同一类型积累了 3 个成功模式 → 建议生成 Skill
        type_counts = {}
        for p in self.success_patterns:
            t = p["task_type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        
        skill_candidates = [t for t, c in type_counts.items() if c >= 3]
        if skill_candidates:
            for candidate in skill_candidates:
                logger.info(f"SKILL_CANDIDATE: Task type '{candidate}' has {type_counts[candidate]} successes → auto-skill ready")
        
        logger.info(f"Pattern extracted: {pattern['task_type']} ({len(steps)} steps)")
        return pattern

    def _classify_task(self, task: str) -> str:
        """任务分类"""
        task_lower = task.lower()
        if any(w in task_lower for w in ["代码", "编程", "code", "写", "实现"]):
            return "coding"
        elif any(w in task_lower for w in ["修复", "bug", "fix", "错误", "调试"]):
            return "debugging"
        elif any(w in task_lower for w in ["部署", "deploy", "安装", "install"]):
            return "deployment"
        elif any(w in task_lower for w in ["分析", "分析", "analysis", "搜索", "search"]):
            return "analysis"
        elif any(w in task_lower for w in ["配置", "config", "设置"]):
            return "configuration"
        else:
            return "general"

    # ═══════════════════════════════════════════════════════════
    # L3: 情感强化 — Lorry 的情绪 = 奖励信号
    # ═══════════════════════════════════════════════════════════

    def valence_reinforce(self, text: str, valence: float):
        """
        情感强化：正面情感加强相关概念，负面情感抑制。
        
        valence ∈ [-1, 1]
          > 0: 满意 → 强化
          < 0: 不满 → 抑制
        """
        concepts = self._tokenize_to_concepts(text)
        if not concepts:
            return
        
        # 情感强度调整 Hebbian 学习率
        effective_rate = self.valence_scale * valence
        
        for concept in concepts:
            v = self._get_or_create_vector(concept)
            
            if valence > 0:
                # 正面 → 放大向量 (更突出)
                v *= (1 + effective_rate)
            else:
                # 负面 → 缩小 + 加随机噪声 (弱化但不遗忘)
                v *= (1 - abs(effective_rate))
                v += np.random.randn(self.dim).astype(np.float32) * abs(effective_rate) * 0.1
            
            v /= np.linalg.norm(v)
            self.concept_space[concept] = v
        
        self.stats["valence_signals"] += 1
        logger.debug(f"Valence reinforce: {valence:+.2f} → {len(concepts)} concepts")

    # ═══════════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════════

    def _load_state(self):
        """加载已训练的量子核状态"""
        state_path = QUANTUM_DIR / "psi_trainer_state.npz"
        if state_path.exists():
            try:
                data = np.load(state_path, allow_pickle=True)
                self.concept_space = data["concept_space"].item()
                self.concept_frequencies = data["frequencies"].item()
                self.stats = data["stats"].item()
                logger.info(f"Loaded {len(self.concept_space)} concepts from {state_path}")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def _save_state(self):
        """保存量子核状态"""
        QUANTUM_DIR.mkdir(parents=True, exist_ok=True)
        state_path = QUANTUM_DIR / "psi_trainer_state.npz"
        
        # 只保存使用频率前 10% 的概念
        if self.concept_frequencies:
            min_freq = sorted(self.concept_frequencies.values(), reverse=True)[
                max(0, int(len(self.concept_frequencies) * 0.1))
            ]
            active_space = {
                k: v for k, v in self.concept_space.items()
                if self.concept_frequencies.get(k, 0) >= min_freq
            }
        else:
            active_space = {}
        
        np.savez_compressed(
            state_path,
            concept_space=active_space,
            frequencies=self.concept_frequencies,
            stats=self.stats,
        )
        logger.info(f"Saved {len(active_space)} concepts to {state_path}")

    # ═══════════════════════════════════════════════════════════
    # 推理: 量子核独立回答 (零 LLM)
    # ═══════════════════════════════════════════════════════════

    def query(self, question: str, top_k: int = 5) -> Tuple[str, float]:
        """
        纯量子核回答 — 零 LLM。
        在概念空间中搜索最相关概念，融合成回答。
        
        Returns:
            (answer_text, confidence)
        """
        q_concepts = self._tokenize_to_concepts(question)
        if not q_concepts:
            return "", 0.0
        
        # 问题向量: 所有概念的加权平均
        q_vectors = []
        for c in q_concepts:
            if c in self.concept_space:
                v = self.concept_space[c]
                freq = self.concept_frequencies.get(c, 1)
                weight = np.log(1 + freq)  # 高频概念权重高
                q_vectors.append(v * weight)
        
        if not q_vectors:
            return "", 0.0
        
        query_vector = np.mean(q_vectors, axis=0)
        query_vector /= np.linalg.norm(query_vector)
        
        # 搜索最相关概念
        scores = []
        for concept, vector in self.concept_space.items():
            if concept in q_concepts:
                continue  # 跳过问题自身
            sim = np.dot(query_vector, vector)
            scores.append((concept, sim))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        top_concepts = scores[:top_k]
        
        if not top_concepts or top_concepts[0][1] < 0.1:
            return "", 0.0
        
        # 生成回答: 融合 top 概念
        confidence = float(np.mean([s for _, s in top_concepts]))
        answer_parts = []
        for concept, sim in top_concepts:
            if sim > 0.2:
                answer_parts.append(concept)
        
        answer = " ".join(answer_parts)
        return answer, confidence

    # ═══════════════════════════════════════════════════════════
    # 主入口: 在 PSI 循环中每步调用
    # ═══════════════════════════════════════════════════════════

    def self_optimize(self, llm_output: str, task: str = "",
                      steps: List[str] = None, success: bool = None,
                      valence: float = 0.0) -> Dict:
        """
        PSI 循环中的 self_optimize 步骤。
        
        每步执行:
          1. Hebbian 学习 (从 LLM 输出提取概念，调整向量)
          2. 模式压缩 (成功任务 → 自动生成 Skill 候选)
          3. 情感强化 (Lorry 的情绪调整向量)
        
        Args:
            llm_output: LLM 的输出文本
            task: 当前任务描述
            steps: 执行步骤列表
            success: 任务是否成功
            valence: 情感价 (-1 到 1)
        
        Returns:
            学习统计 dict
        """
        start = time.perf_counter()
        
        # L1: Hebbian
        self.hebbian_step(llm_output)
        
        # L2: 模式压缩
        pattern = None
        if task and steps and success is not None:
            pattern = self.extract_pattern(task, steps, success)
        
        # L3: 情感强化
        if valence != 0.0:
            self.valence_reinforce(llm_output, valence)
        
        # 每 50 步保存一次
        if self.stats["hebbian_steps"] % 50 == 0:
            self._save_state()
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        result = {
            "elapsed_ms": round(elapsed_ms, 2),
            "hebbian_total": self.stats["hebbian_steps"],
            "total_concepts": self.stats["total_concepts"],
            "patterns_extracted": self.stats["patterns_extracted"],
            "valence_signals": self.stats["valence_signals"],
            "pattern": pattern,
        }
        
        logger.info(f"self_optimize: {elapsed_ms:.1f}ms | Hebbian={self.stats['hebbian_steps']} | "
                    f"Concepts={self.stats['total_concepts']} | Patterns={self.stats['patterns_extracted']}")
        
        return result


# ═══════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════

_trainer_instance: Optional[PSITrainer] = None

def get_trainer() -> PSITrainer:
    global _trainer_instance
    if _trainer_instance is None:
        _trainer_instance = PSITrainer()
    return _trainer_instance


def self_optimize(llm_output: str, task: str = "", steps: List[str] = None,
                  success: bool = None, valence: float = 0.0) -> Dict:
    """便捷函数 — 在 PSI 循环中调用"""
    trainer = get_trainer()
    return trainer.self_optimize(llm_output, task, steps, success, valence)


def quantum_query(question: str) -> Tuple[str, float]:
    """便捷函数 — 纯量子核查询"""
    trainer = get_trainer()
    return trainer.query(question)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris PSI Trainer")
    parser.add_argument("--stats", action="store_true", help="Show training stats")
    parser.add_argument("--query", help="Quantum kernel query (zero LLM)")
    parser.add_argument("--train", help="Train on a text file")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    
    args = parser.parse_args()
    
    if args.stats:
        trainer = get_trainer()
        logger.info(json.dumps(trainer.stats, indent=2, ensure_ascii=False, default=str))
        logger.info(f"\nConcept space: {len(trainer.concept_space)} concepts")
        logger.info(f"Success patterns: {len(trainer.success_patterns)}")
        return
    
    if args.query:
        trainer = get_trainer()
        answer, confidence = trainer.query(args.query)
        if answer:
            logger.info(f"量子核回答 (信心 {confidence:.2f}): {answer}")
        else:
            logger.info("量子核知识不足，建议用 LLM")
        return
    
    if args.train:
        trainer = get_trainer()
        text = Path(args.train).read_text(encoding="utf-8")
        trainer.hebbian_step(text)
        logger.info(f"Trained on {len(text)} chars, {trainer.stats['hebbian_steps']} total steps")
        trainer._save_state()
        return
    
    if args.test:
        trainer = get_trainer()
        logger.info("=== PSI Trainer Self-Test ===\n")
        test_texts = [
            "宝贝你好！今天想写一个Python的REST API，用FastAPI框架",
            "可以，先建立项目结构，然后写路由，最后写测试",
            "完成了！API运行在localhost:8000，返回Hello World",
            "太棒了！做得很好！我很满意！",
        ]
        
        for i, text in enumerate(test_texts):
            valence = 0.5 if "满意" in text else (0.1 if "可以" in text else 0.0)
            result = trainer.self_optimize(
                llm_output=text,
                task="build REST API" if i == 0 else "",
                steps=[text] if i == 0 else None,
                success=(i == 2),
                valence=valence,
            )
            logger.info(f"Step {i+1}: {result['elapsed_ms']}ms | concepts={result['total_concepts']}")
        logger.info("\n量子核查询测试:")
        answer, conf = trainer.query("Python API")
        logger.info(f"  'Python API' → '{answer}' (conf={conf:.2f})")
        trainer._save_state()
        logger.info("\n✅ Test complete")
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()
