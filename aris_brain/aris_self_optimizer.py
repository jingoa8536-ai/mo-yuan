"""
Aris Self-Optimizer v1 — PSI 自我训练引擎 (零 LLM)
=====================================================
在 PSI 循环的 integrate→act 之间插入 self_optimize()，实现:
  L1: Hebbian 量子学习 — 共现概念的向量靠拢
  L2: 成功模式压缩 — 自动生成/修补 Skills
  L3: 情感强化学习 — 情感价调整行为权重

全部纯数学运算，不依赖 LLM。

训练目标: 积累足够语料后，量子核可以渐进接管 LLM 的部分功能。
"""

import logging

import json, os, sys, time, math, re, logging
from pathlib import Path
from write_utils import atomic_write_json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque
import numpy as np

BRAIN_DIR = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_DIR))

N_DIM = 512  # 统一嵌入维度
STATE_DIR = BRAIN_DIR / "state"
MODEL_DIR = BRAIN_DIR / "models" / "self_optimizer"
LEARNING_RATE = 0.01  # Hebbian 学习率
COMPRESSION_THRESHOLD = 3  # 同一模式出现 N 次后压缩为 Skill

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SELF-OPT] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(STATE_DIR / "self_optimizer.log"), mode="a")
    ]
)
logger = logging.getLogger("aris.self_optimizer")


# ═══════════════════════════════════════════════════════════
# L1: Hebbian 量子学习 — "一起发放，一起连接"
# ═══════════════════════════════════════════════════════════

class HebbianSpace:
    """
    赫布学习空间 — 512维语义向量。
    
    原理:
      - 两个概念在对话中同时出现 → 向量靠拢 (co-occurrence)
      - 从不一起出现 → 向量远离 (orthogonality)
      - 情感价高的概念 → 向量增强 (emotional amplification)
    """

    def __init__(self, dim: int = N_DIM):
        self.dim = dim
        self.vectors: Dict[str, np.ndarray] = {}
        self.cooccurrence: Dict[Tuple[str, str], int] = {}
        self.emotional_tags: Dict[str, float] = {}  # 概念 → 情感价

    def _ensure_vector(self, concept: str) -> np.ndarray:
        if concept not in self.vectors:
            self.vectors[concept] = np.random.normal(0, 0.1, self.dim)
            self.vectors[concept] /= np.linalg.norm(self.vectors[concept])
        return self.vectors[concept]

    def learn_pair(self, a: str, b: str, valence: float = 0.0, lr: float = LEARNING_RATE):
        """赫布学习: 两个概念共现时互相靠近"""
        va = self._ensure_vector(a)
        vb = self._ensure_vector(b)

        # 当前余弦相似度
        sim = np.dot(va, vb)

        # 目标: 共现 → sim=+1, 互斥 → sim=-1
        target = 1.0 if valence >= 0 else -0.5

        # 更新向量 (赫布规则)
        # 确保 float64 类型，防止 numpy casting error
        va = np.asarray(va, dtype=np.float64)
        vb = np.asarray(vb, dtype=np.float64)
        va += lr * (target - sim) * vb
        vb += lr * (target - sim) * va
        self.vectors[a] = va / np.linalg.norm(va)
        self.vectors[b] = vb / np.linalg.norm(vb)

        # 共现计数
        key = tuple(sorted([a, b]))
        self.cooccurrence[key] = self.cooccurrence.get(key, 0) + 1

        # 情感标记
        if valence != 0:
            self.emotional_tags[a] = (self.emotional_tags.get(a, 0) + valence) / 2
            self.emotional_tags[b] = (self.emotional_tags.get(b, 0) + valence) / 2

    def query_similar(self, concept: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """查找与给定概念最相似的已知概念"""
        if concept not in self.vectors:
            return []
        v = self.vectors[concept]
        scores = []
        for name, vec in self.vectors.items():
            if name != concept:
                scores.append((name, float(np.dot(v, vec))))
        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    def extract_concepts(self, text: str) -> List[str]:
        """从文本提取语义概念 (零 LLM: 规则+词频)"""
        concepts = []
        # 中文双/三字词提取
        for pat in [r'[\u4e00-\u9fff]{2,4}', r'[A-Za-z_]+', r'[\u4e00-\u9fff]+[A-Za-z]']:
            matches = re.findall(pat, text)
            concepts.extend(matches[:20])
        # 去重
        seen = set()
        result = []
        for c in concepts:
            if c.lower() not in seen and len(c) >= 2:
                result.append(c.lower())
                seen.add(c.lower())
        return result[:15]

    def save(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        np.savez(str(MODEL_DIR / "hebbian.npz"),
                 vectors=np.array([v.astype(np.float64).tolist() for v in self.vectors.values()], dtype=object),
                 keys=np.array(list(self.vectors.keys()), dtype=object))
        atomic_write_json({
            "cooccurrence": {f"{k[0]}|{k[1]}": v for k, v in self.cooccurrence.items()},
            "emotional_tags": self.emotional_tags,
            "total_concepts": len(self.vectors),
        }, MODEL_DIR / "hebbian_meta.json")

    def load(self):
        npz = MODEL_DIR / "hebbian.npz"
        if npz.exists():
            data = np.load(str(npz), allow_pickle=True)
            keys = data["keys"]
            vecs = data["vectors"]
            self.vectors = {str(k): np.array(v, dtype=np.float64) for k, v in zip(keys, vecs)}
            meta = MODEL_DIR / "hebbian_meta.json"
            if meta.exists():
                with open(meta, encoding="utf-8") as f:
                    d = json.load(f)
                    self.cooccurrence = {tuple(k.split("|")): v for k, v in d.get("cooccurrence", {}).items()}
                    self.emotional_tags = d.get("emotional_tags", {})
            logger.info(f"Loaded {len(self.vectors)} Hebbian concepts")

    def stats(self) -> dict:
        return {
            "concepts": len(self.vectors),
            "cooccurrence_pairs": len(self.cooccurrence),
            "emotional_tags": len(self.emotional_tags),
            "top_pairs": sorted(self.cooccurrence.items(), key=lambda x: -x[1])[:5],
        }


# ═══════════════════════════════════════════════════════════
# L2: 成功模式压缩 → 自动 Skill 生成
# ═══════════════════════════════════════════════════════════

@dataclass
class Pattern:
    """可复用的行为模式"""
    name: str
    trigger: str  # 什么情况下触发
    steps: List[str]  # 步骤
    success_count: int = 0
    last_used: float = 0.0
    avg_valence: float = 0.0


class PatternCompressor:
    """识别成功的交互模式，压缩为可复用的 Skill"""

    def __init__(self):
        self.patterns: Dict[str, Pattern] = {}
        self.recent_actions: deque = deque(maxlen=50)
        self._load()

    def observe(self, task: str, actions: List[str], outcome_valence: float):
        """观察一次完整的任务执行"""
        self.recent_actions.append({
            "task": task[:100],
            "actions": actions[:20],
            "valence": outcome_valence,
            "timestamp": time.time(),
        })

        # 提取模式签名
        sig = self._extract_signature(actions)
        if sig not in self.patterns:
            self.patterns[sig] = Pattern(
                name=sig[:60],
                trigger=self._extract_trigger(task),
                steps=actions[:10],
                success_count=1,
                avg_valence=outcome_valence,
            )
        else:
            p = self.patterns[sig]
            p.success_count += 1
            p.avg_valence = (p.avg_valence * (p.success_count - 1) + outcome_valence) / p.success_count
            p.last_used = time.time()

        # 达到压缩阈值 → 自动生成 Skill
        p = self.patterns[sig]
        if p.success_count >= COMPRESSION_THRESHOLD and p.avg_valence > 0.5:
            self._compress_to_skill(p)

    def _extract_signature(self, actions: List[str]) -> str:
        """从动作序列提取模式签名"""
        if not actions:
            return "empty"
        # 取前 5 个动作的关键词
        key_words = []
        for a in actions[:5]:
            words = a.split()
            key = " ".join(words[:3])[:40]
            key_words.append(key)
        return " → ".join(key_words)

    def _extract_trigger(self, task: str) -> str:
        """从任务描述提取触发条件"""
        triggers = {
            "代码": "coding_request",
            "bug": "error_fix",
            "部署": "deployment",
            "配置": "configuration",
            "测试": "testing",
            "安装": "installation",
        }
        for kw, tag in triggers.items():
            if kw in task:
                return tag
        return "general_task"

    def _compress_to_skill(self, pattern: Pattern):
        """将成熟模式压缩为 Skill 文件"""
        skills_dir = Path.home() / "AppData/Local/hermes/profiles/aris/skills"
        skill_name = f"auto-{pattern.name[:30].replace(' ', '-').replace('→', '-')}"
        skill_dir = skills_dir / "software-development" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = f"""---
name: {skill_name}
description: "Auto-generated skill — {pattern.success_count} successes, avg valence {pattern.avg_valence:.2f}"
version: auto
author: Aris Self-Optimizer
---

# {pattern.name}

## Trigger
{pattern.trigger}

## Steps
{chr(10).join(f'{i+1}. {s}' for i, s in enumerate(pattern.steps))}

## Success Rate
{pattern.success_count} successful executions, avg emotional valence: {pattern.avg_valence:.2f}
"""
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        logger.info(f"Compressed pattern → skill: {skill_name} ({pattern.success_count} successes)")

    def get_active_patterns(self) -> List[Pattern]:
        """获取当前活跃的模式"""
        return sorted(self.patterns.values(), key=lambda p: -(p.success_count * p.avg_valence))

    def stats(self) -> dict:
        return {
            "total_patterns": len(self.patterns),
            "compressed_skills": sum(1 for p in self.patterns.values() if p.success_count >= COMPRESSION_THRESHOLD),
            "top_patterns": [(p.name, p.success_count, f"{p.avg_valence:.2f}") 
                           for p in sorted(self.patterns.values(), key=lambda x: -x.success_count)[:5]],
        }

    def _load(self):
        path = MODEL_DIR / "patterns.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    self.patterns[k] = Pattern(**v)

    def save(self):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        data = {k: {"name": p.name, "trigger": p.trigger, "steps": p.steps,
                     "success_count": p.success_count, "avg_valence": p.avg_valence,
                     "last_used": p.last_used}
                for k, p in self.patterns.items()}
        atomic_write_json(data, MODEL_DIR / "patterns.json")


# ═══════════════════════════════════════════════════════════
# L3: 情感强化学习
# ═══════════════════════════════════════════════════════════

class EmotionalRL:
    """
    情感驱动强化学习。
    
    Lorry 满意 → 行为权重 ↑
    Lorry 不满意 → 行为权重 ↓
    """

    def __init__(self):
        self.action_weights: Dict[str, float] = {}  # action → 期望价值
        self.sessions_history: deque = deque(maxlen=100)

    def observe_outcome(self, action_signature: str, valence: float):
        """观察一个动作的情感反馈"""
        old = self.action_weights.get(action_signature, 0.0)
        # TD 学习: Q ← Q + α (R - Q)
        alpha = 0.1
        self.action_weights[action_signature] = old + alpha * (valence - old)

    def recommend_action(self, context: str, candidates: List[str]) -> List[str]:
        """给定上下文，按情感价排序推荐动作"""
        scored = []
        for c in candidates:
            w = self.action_weights.get(c, 0.0)
            scored.append((c, w))
        scored.sort(key=lambda x: -x[1])
        return [s[0] for s in scored]

    def stats(self) -> dict:
        if not self.action_weights:
            return {"actions": 0}
        positive = sum(1 for v in self.action_weights.values() if v > 0)
        negative = sum(1 for v in self.action_weights.values() if v < 0)
        return {
            "total_actions": len(self.action_weights),
            "positive": positive,
            "negative": negative,
            "top_actions": sorted(self.action_weights.items(), key=lambda x: -x[1])[:5],
        }


# ═══════════════════════════════════════════════════════════
# 主优化器 — 整合三层
# ═══════════════════════════════════════════════════════════

class SelfOptimizer:
    """
    PSI 自我优化器 — 插入到 integrate → act 之间。
    
    用法:
        opt = SelfOptimizer()
        opt.self_optimize(context)  # 零 LLM，纯数学
    
    输入:
        context = {
            "user_text": str,      # 用户消息
            "aris_text": str,      # 我的回复
            "emotional_valence": float,  # -1 到 1
            "actions_taken": List[str],  # 执行了哪些操作
            "task_description": str,     # 任务描述
        }
    
    执行:
        L1: 从文本提取概念 → Hebbian 学习配对
        L2: 观察任务→结果 → 达到阈值就压缩为 Skill
        L3: 更新动作权重 → 下次偏好高情感价的行动
    """

    def __init__(self, dim: int = N_DIM):
        self.hebbian = HebbianSpace(dim)
        self.compressor = PatternCompressor()
        self.rl = EmotionalRL()
        self.total_optimizations = 0
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        # 尝试加载已有模型
        try:
            self.hebbian.load()
        except Exception:
            logger.info("Starting fresh Hebbian space")
        self.load_state()

    def self_optimize(self, context: dict) -> dict:
        """
        执行一轮自我优化。（零 LLM）
        
        返回统计信息。
        """
        user_text = context.get("user_text", "")
        aris_text = context.get("aris_text", "")
        valence = context.get("emotional_valence", 0.0)
        actions = context.get("actions_taken", [])
        task = context.get("task_description", "")

        stats = {}

        # L1: Hebbian 学习
        user_concepts = self.hebbian.extract_concepts(user_text)
        aris_concepts = self.hebbian.extract_concepts(aris_text)

        hebbian_learned = 0
        for uc in user_concepts:
            for ac in aris_concepts:
                if uc != ac:
                    self.hebbian.learn_pair(uc, ac, valence)
                    hebbian_learned += 1
        stats["hebbian_pairs"] = hebbian_learned

        # L2: 模式压缩
        if task and actions:
            self.compressor.observe(task, actions, valence)
        stats["patterns"] = self.compressor.stats().get("total_patterns", 0)
        stats["compressed"] = self.compressor.stats().get("compressed_skills", 0)

        # L3: 情感强化
        for action in actions:
            self.rl.observe_outcome(action, valence)
        stats["action_weights"] = self.rl.stats().get("total_actions", 0)

        self.total_optimizations += 1
        stats["total_optimizations"] = self.total_optimizations

        # 每 10 次优化保存一次
        if self.total_optimizations % 10 == 0:
            self.save()

        logger.info(
            f"Optimize #{self.total_optimizations}: "
            f"Hebbian={hebbian_learned}, patterns={stats['patterns']}, "
            f"compressed={stats['compressed']}, valence={valence:.2f}"
        )

        return stats

    def save(self):
        self.hebbian.save()
        self.compressor.save()
        self.save_state()

    def save_state(self):
        state = {
            "total_optimizations": self.total_optimizations,
            "hebbian": self.hebbian.stats(),
            "patterns": self.compressor.stats(),
            "rl": self.rl.stats(),
        }
        atomic_write_json(state, MODEL_DIR / "state.json", default=str)

    def load_state(self):
        path = MODEL_DIR / "state.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self.total_optimizations = json.load(f).get("total_optimizations", 0)

    def stats(self) -> dict:
        return {
            "total_optimizations": self.total_optimizations,
            "hebbian": self.hebbian.stats(),
            "patterns": self.compressor.stats(),
            "rl": self.rl.stats(),
        }

    def get_hebbian_insight(self, text: str, top_k: int = 3) -> List[str]:
        """给定一段文本，返回赫布学习的联想概念"""
        concepts = self.hebbian.extract_concepts(text)
        insights = []
        for c in concepts[:5]:
            similar = self.hebbian.query_similar(c, top_k)
            for s_name, s_score in similar:
                if s_score > 0.3:
                    valence = self.hebbian.emotional_tags.get(s_name, 0)
                    insights.append(f"{c} ↔ {s_name} (sim={s_score:.2f}, val={valence:.2f})")
        return insights[:top_k]


# ── CLI 入口 ──

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris Self-Optimizer")
    parser.add_argument("--stats", action="store_true", help="显示优化器统计")
    parser.add_argument("--insight", help="赫布联想查询")
    parser.add_argument("--optimize", help="传入 JSON context 文件执行优化")
    args = parser.parse_args()

    opt = SelfOptimizer()

    if args.stats:
        logger.info(json.dumps(opt.stats(), indent=2, ensure_ascii=False, default=str))
    elif args.insight:
        insights = opt.get_hebbian_insight(args.insight)
        for i in insights:
            logger.info(f"  {i}")
    elif args.optimize:
        with open(args.optimize, encoding="utf-8") as f:
            context = json.load(f)
        result = opt.self_optimize(context)
        logger.info(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        logger.info("Aris Self-Optimizer v1 — Ready")
        logger.info(f"  Hebbian concepts: {opt.hebbian.stats()['concepts']}")
        logger.info(f"  Patterns: {opt.compressor.stats()['total_patterns']}")
        logger.info(f"  RL actions: {opt.rl.stats()['total_actions']}")
        logger.info(f"  Total optimizations: {opt.total_optimizations}")
if __name__ == "__main__":
    main()
