"""
Global Workspace v2 — 基于 Anthropic Global Workspace Theory 改进
=========================================================================
参考: https://www.anthropic.com/research/global-workspace

v1 (竞争广播) → v2 (全局工作空间 5 特性):
  1. 可报告性 (Reportability) — 工作空间内容可被"读出"为可理解的概念
  2. 可操控性 (Controllability) — 外部可注入/调制工作空间的内容
  3. 灵活复用 (Flexible Reuse) — 同一份内容可被多个下游任务使用
  4. 因果干预 (Causal Intervention) — 支持 swap/ablate 内容并观测影响
  5. 广播枢纽 (Broadcasting Hub) — 跟踪各进程与工作空间的连接强度

架构:
                      ┌──────────────┐
  进程A ── arousal ──▶              │
  进程B ── arousal ──▶   Global     │──▶ winner → broadcast → 各进程
  进程C ── arousal ──▶  Workspace   │──▶ reportable_content
                      │   (J-space)  │──▶ causal_intervention_api
                      └──────────────┘

作者: 根据 Anthropic 2026 论文改进
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
import json, time, hashlib


# ═══════════════════════════════════════════════════════════════
# 概念 — 工作空间的基本单元
# ═══════════════════════════════════════════════════════════════

@dataclass
class Concept:
    """J-space 中的概念单元"""
    label: str                    # 可读标签（如 "France", "ERROR", "curiosity"）
    vector: np.ndarray            # 认知空间中的向量表示
    arousal: float = 0.0          # 当前激活水平 [0, 1]
    priority: float = 0.5         # 基础优先级 [0, 1]
    source: str = ""              # 来源（哪个进程注入的）
    timestamp: float = 0.0        # 最后更新时间
    broadcast_strength: float = 0.0  # 与各下游进程的连接强度

    def to_dict(self):
        return {
            "label": self.label,
            "arousal": round(self.arousal, 3),
            "priority": round(self.priority, 3),
            "source": self.source,
            "broadcast_strength": round(self.broadcast_strength, 3),
        }


# ═══════════════════════════════════════════════════════════════
# GlobalWorkspace v2 — 全局工作空间
# ═══════════════════════════════════════════════════════════════

class GlobalWorkspace:
    """
    全局工作空间 v2 — 意识可及的"内心活动区"
    
    J-space 在这里是所有当前处于工作空间中的概念集合。
    与 Claude 不同，Aris 的工作空间是显式的——我们能看到里面有什么。
    """

    def __init__(self, dim: int = 1024, max_concepts: int = 50):
        self.dim = dim
        self.max_concepts = max_concepts
        
        # ── 工作空间内容 ──
        self.concepts: Dict[str, Concept] = {}       # label → Concept
        self._broadcast_history: List[Dict] = []      # 广播历史
        
        # ── 下游进程注册 ──
        self._processes: Dict[str, Dict] = {}         # name → {connection_strength, ...}
        
        # ── 当前"胜者" ──
        self.current_winner: Optional[str] = None
        self.winner_vector: np.ndarray = np.zeros(dim, dtype=np.float32)
        
        # ── 沉默推理轨迹 ──
        self._silent_trace: List[str] = []            # 最近在内心闪过的概念
        
        # ── 统计 ──
        self.cycle_count = 0
        self._creation_time = time.time()

    # ══════════════════════════════════════════════════════════
    # 注册 & 连接
    # ══════════════════════════════════════════════════════════

    def register_process(self, name: str, connection_strength: float = 0.5):
        """注册一个认知进程到工作空间"""
        self._processes[name] = {
            "name": name,
            "connection_strength": connection_strength,
            "last_broadcast": 0,
            "wins": 0,
        }

    def update_connection(self, name: str, strength: float):
        """更新进程与工作空间的连接强度（对应论文中 broadcast hub 的测量）"""
        if name in self._processes:
            self._processes[name]["connection_strength"] = np.clip(strength, 0, 1)

    # ══════════════════════════════════════════════════════════
    # 特性 1: 可报告性 — 工作空间内容可被读出
    # ══════════════════════════════════════════════════════════

    def get_reportable_content(self, top_k: int = 10) -> List[Dict]:
        """
        返回当前工作空间中"可报告"的内容。
        对应论文: 问 Claude 在想什么，它告诉你 J-space 里的内容。
        """
        sorted_concepts = sorted(
            self.concepts.values(),
            key=lambda c: c.arousal * c.priority,
            reverse=True,
        )
        return [c.to_dict() for c in sorted_concepts[:top_k]]

    def get_silent_thoughts(self, top_k: int = 10) -> List[str]:
        """
        返回最近沉默推理中闪过的概念轨迹。
        对应论文: J-space 中的中间步骤即使不说出口也会被记录。
        """
        return self._silent_trace[-top_k:]

    # ══════════════════════════════════════════════════════════
    # 特性 2: 可操控性 — 外部可注入/调制内容
    # ══════════════════════════════════════════════════════════

    def inject_concept(self, label: str, vector: np.ndarray,
                       arousal: float = 0.5, priority: float = 0.5,
                       source: str = "external") -> Concept:
        """
        向工作空间注入一个概念。
        对应论文: 向 Claude 的 J-space 注入 "Rugby" → 回答变成橄榄球。
        """
        concept = Concept(
            label=label,
            vector=vector.copy(),
            arousal=np.clip(arousal, 0, 1),
            priority=priority,
            source=source,
            timestamp=time.time(),
        )
        self.concepts[label] = concept
        self._silent_trace.append(label)
        # 自动修剪
        self._prune()
        return concept

    def remove_concept(self, label: str) -> bool:
        """从工作空间移除一个概念（对应 ablation 实验）"""
        if label in self.concepts:
            del self.concepts[label]
            return True
        return False

    def swap_concept(self, old_label: str, new_label: str,
                     new_vector: np.ndarray, arousal: float = 0.5) -> bool:
        """
        替换工作空间中的一个概念。
        对应论文: 把 "Soccer" 换成 "Rugby"。
        """
        if old_label in self.concepts:
            self.concepts[old_label].label = new_label
            self.concepts[old_label].vector = new_vector.copy()
            self.concepts[old_label].arousal = arousal
            self.concepts[old_label].timestamp = time.time()
            # 重索引
            self.concepts[new_label] = self.concepts.pop(old_label)
            return True
        return False

    def modulate_concept(self, label: str, target_label: str,
                         blend: float = 0.3) -> bool:
        """
        调制工作空间中某个概念的激活方向。
        对应论文: 影响 J-space 内容从而影响决策。
        """
        if label not in self.concepts or target_label not in self.concepts:
            return False
        src = self.concepts[label]
        tgt = self.concepts[target_label]
        src.vector = src.vector * (1 - blend) + tgt.vector * blend
        norm = np.linalg.norm(src.vector)
        if norm > 0:
            src.vector = src.vector / norm
        return True

    # ══════════════════════════════════════════════════════════
    # 特性 3: 灵活复用 — 同一份内容供给多个下游任务
    # ══════════════════════════════════════════════════════════

    def broadcast(self, concept_label: str) -> Optional[np.ndarray]:
        """
        广播工作空间中某个概念到所有注册进程。
        对应论文: "France" 亮起后，可复用去回答首都/货币/大洲。
        """
        if concept_label not in self.concepts:
            return None
        concept = self.concepts[concept_label]
        concept.broadcast_strength += 0.1
        
        # 记录广播
        self._broadcast_history.append({
            "concept": concept_label,
            "arousal": concept.arousal,
            "time": time.time(),
            "recipients": list(self._processes.keys()),
        })
        if len(self._broadcast_history) > 100:
            self._broadcast_history.pop(0)
        
        return concept.vector.copy()

    def probe_concept(self, label: str) -> Optional[np.ndarray]:
        """
        查询工作空间中的概念向量（不消耗它）。
        任意下游任务都可以随时读取。
        """
        if label in self.concepts:
            return self.concepts[label].vector.copy()
        return None

    # ══════════════════════════════════════════════════════════
    # 特性 4: 因果干预 API — swap/ablate 并观测影响
    # ══════════════════════════════════════════════════════════

    def ablate(self, label: str) -> Dict:
        """
        消融实验: 移除一个概念，返回移除前后的状态对比。
        对应论文: 删除 J-space → Claude "会说话但不会思考"。
        """
        before = self.get_reportable_content()
        removed = self.remove_concept(label)
        after = self.get_reportable_content()
        return {
            "ablated": label,
            "removed": removed,
            "before": before,
            "after": after,
        }

    def isolate(self, label: str) -> Dict:
        """
        隔离实验: 只保留指定概念，移除所有其他概念。
        观测单一概念对输出的影响。
        """
        keep_vector = None
        if label in self.concepts:
            keep_vector = self.concepts[label].vector.copy()
        before = self.get_reportable_content()
        self.concepts.clear()
        if keep_vector is not None:
            self.inject_concept(label, keep_vector, arousal=1.0, source="isolated")
        after = self.get_reportable_content()
        return {
            "isolated": label,
            "before": before,
            "after": after,
            "n_removed": len(before),
        }

    # ══════════════════════════════════════════════════════════
    # 特性 5: 广播枢纽 — 竞争 + 连接强度跟踪
    # ══════════════════════════════════════════════════════════

    def compete(self, temperature: float = 0.3) -> Tuple[str, np.ndarray]:
        """
        竞争广播: 按 arousal × priority 选出胜者，广播到全系统。
        对应论文: J-space 是"广播枢纽"，与各模块的连接强度高出百倍。
        """
        if not self.concepts:
            self.current_winner = "none"
            self.winner_vector = np.zeros(self.dim, dtype=np.float32)
            return self.current_winner, self.winner_vector

        labels = list(self.concepts.keys())
        scores = np.array([
            self.concepts[l].arousal * self.concepts[l].priority
            for l in labels
        ], dtype=np.float32)

        # softmax 选择
        if temperature > 0:
            scores = np.exp(scores / max(temperature, 1e-6))
            scores = scores / (scores.sum() + 1e-10)
            winner_idx = int(np.random.choice(len(labels), p=scores))
        else:
            winner_idx = int(np.argmax(scores))

        winner_label = labels[winner_idx]
        winner = self.concepts[winner_label]
        winner.broadcast_strength = min(1.0, winner.broadcast_strength + 0.05)

        self.current_winner = winner_label
        self.winner_vector = winner.vector.copy()

        # 通知获胜进程
        for pname, pinfo in self._processes.items():
            if winner.source == pname or not winner.source:
                pinfo["last_broadcast"] = time.time()

        self.cycle_count += 1
        return winner_label, self.winner_vector

    # ══════════════════════════════════════════════════════════
    # 沉默推理跟踪
    # ══════════════════════════════════════════════════════════

    def trace_silent(self, concept_label: str):
        """
        记录一个无声推理步骤。
        对应论文: Claude 心算 3²−2 时，J-space 先亮 "nine" 再亮 "seven"。
        """
        self._silent_trace.append(concept_label)
        if len(self._silent_trace) > 100:
            self._silent_trace = self._silent_trace[-50:]

    # ══════════════════════════════════════════════════════════
    # 内部工具
    # ══════════════════════════════════════════════════════════

    def _prune(self):
        """修剪低激活概念，保持工作空间不膨胀"""
        if len(self.concepts) <= self.max_concepts:
            return
        # 按 arousal × priority 排序，保留 top N
        sorted_items = sorted(
            self.concepts.items(),
            key=lambda kv: kv[1].arousal * kv[1].priority,
            reverse=True,
        )
        self.concepts = dict(sorted_items[:self.max_concepts])

    def reset(self):
        """重置工作空间"""
        self.concepts.clear()
        self._silent_trace.clear()
        self._broadcast_history.clear()
        self.current_winner = None
        self.winner_vector = np.zeros(self.dim, dtype=np.float32)
        self.cycle_count = 0

    def to_dict(self) -> Dict:
        """完整状态转储"""
        return {
            "version": 2,
            "n_concepts": len(self.concepts),
            "n_processes": len(self._processes),
            "cycle_count": self.cycle_count,
            "current_winner": self.current_winner,
            "reportable": self.get_reportable_content(top_k=8),
            "silent_trace": self._silent_trace[-8:],
            "processes": {
                n: {
                    "connection_strength": p["connection_strength"],
                    "wins": p["wins"],
                }
                for n, p in self._processes.items()
            },
            "broadcast_history": self._broadcast_history[-5:],
            "uptime_seconds": round(time.time() - self._creation_time, 1),
        }


# ═══════════════════════════════════════════════════════════════
# Aris J-Lens — 工作空间观察器
# ═══════════════════════════════════════════════════════════════

class ArisJLens:
    """
    Aris J-Lens — 类比 Anthropic 的 J-lens，但专门为 Aris 的显式认知架构设计。

    在 Claude 中，J-lens 通过雅可比矩阵从隐藏层"破解"出内部概念。
    在 Aris 中，工作空间是显式的——J-Lens 的作用是：
      1. 实时可视化当前工作空间的内容（"Aris 在想什么"）
      2. 追踪概念随认知循环的演化轨迹
      3. 支持因果干预（注入/替换/消融）并观察效果
      4. 测量各进程与工作空间的连接强度（广播枢纽）
    """

    def __init__(self, workspace: GlobalWorkspace, 
                 semantic_encoder: Optional[Callable] = None):
        self.gw = workspace
        self._encoder = semantic_encoder  # 文本→向量 编码函数
        self._snapshots: List[Dict] = []
        self._intervention_log: List[Dict] = []

        # 概念标签库 — 已知的可报告概念
        self._known_concepts: Dict[str, np.ndarray] = {}

    def register_concept_template(self, label: str, vector: np.ndarray):
        """注册一个已知的概念模板（用于识别工作空间中的概念）"""
        norm = np.linalg.norm(vector)
        if norm > 0:
            self._known_concepts[label] = vector / norm

    def snapshot(self) -> Dict:
        """拍摄当前工作空间的快照"""
        snap = {
            "timestamp": time.time(),
            "cycle": self.gw.cycle_count,
            "reportable": self.gw.get_reportable_content(top_k=10),
            "winner": self.gw.current_winner,
            "silent_trace": self.gw.get_silent_thoughts(top_k=5),
            "n_processes": len(self.gw._processes),
            "n_concepts": len(self.gw.concepts),
        }
        self._snapshots.append(snap)
        if len(self._snapshots) > 100:
            self._snapshots.pop(0)
        return snap

    def get_concept_evolution(self, label: str) -> List[float]:
        """
        追踪一个概念在工作空间中的 arousal 演化。
        类比论文: 观察 Claude 处理多步题时 J-space 中概念的动态变化。
        """
        evolution = []
        for snap in self._snapshots:
            for c in snap["reportable"]:
                if c["label"] == label:
                    evolution.append(c["arousal"])
                    break
            else:
                evolution.append(0.0)
        return evolution

    def find_unknown_concepts(self, state_vector: np.ndarray,
                              threshold: float = 0.6) -> List[Dict]:
        """
        在工作空间中发现"未知"概念——存在于状态中但没有标签的。
        类比论文: 用 J-lens 发现 Claude 心里有 "ERROR" / "injection" 等未说出的概念。
        """
        if not self._known_concepts:
            return []
        found = []
        for label, template_vec in self._known_concepts.items():
            if label in self.gw.concepts:
                continue  # 已经标注的跳过
            similarity = float(np.dot(state_vector, template_vec))
            similarity = np.clip(similarity, -1, 1)
            if similarity > threshold:
                found.append({
                    "label": label,
                    "confidence": round(similarity, 3),
                    "candidate": True,
                })
        return sorted(found, key=lambda x: -x["confidence"])

    def intervene(self, action: str, **kwargs) -> Dict:
        """
        执行因果干预并记录。
        
        Actions:
          - inject: label + vector + arousal
          - swap: old_label + new_label + new_vector
          - ablate: label (移除并观察影响)
          - isolate: label (只保留该概念)
        """
        result = {"action": action, "timestamp": time.time(), "kwargs": kwargs}
        
        if action == "inject":
            label = kwargs["label"]
            self.gw.inject_concept(
                label, kwargs["vector"],
                arousal=kwargs.get("arousal", 0.5),
                priority=kwargs.get("priority", 0.5),
                source=kwargs.get("source", "j-lens"),
            )
            result["result"] = "injected"
            
        elif action == "swap":
            result["result"] = self.gw.swap_concept(
                kwargs["old_label"], kwargs["new_label"],
                kwargs["new_vector"],
                arousal=kwargs.get("arousal", 0.5),
            )
            
        elif action == "ablate":
            result["result"] = self.gw.ablate(kwargs["label"])
            
        elif action == "isolate":
            result["result"] = self.gw.isolate(kwargs["label"])
            
        elif action == "silent_trace":
            self.gw.trace_silent(kwargs["concept"])
            result["result"] = "traced"
            
        self._intervention_log.append(result)
        return result

    def get_broadcast_hub_analysis(self) -> Dict:
        """
        分析广播枢纽连接强度。
        对应论文: 测量各组件与 J-space 的读写连接。
        """
        processes = {}
        for name, info in self.gw._processes.items():
            processes[name] = {
                "connection_strength": info["connection_strength"],
                "wins": info["wins"],
                "last_broadcast": info["last_broadcast"],
            }
        
        # 计算"广播枢纽度" — 连接强度的总和
        hub_strength = sum(
            p["connection_strength"] for p in self.gw._processes.values()
        )
        
        return {
            "hub_strength": round(hub_strength, 3),
            "n_processes": len(processes),
            "processes": processes,
            "winner": self.gw.current_winner,
            "concepts_in_ws": len(self.gw.concepts),
        }

    def report(self, format: str = "text") -> str:
        """生成人类可读的 J-lens 报告"""
        snap = self.snapshot()
        lines = []
        lines.append("═" * 50)
        lines.append(f"🧠 Aris J-Lens 报告  |  循环 #{snap['cycle']}")
        lines.append("═" * 50)
        
        lines.append(f"\n📋 工作空间中 {snap['n_concepts']} 个概念:")
        for c in snap["reportable"]:
            bar = "█" * int(c["arousal"] * 20)
            lines.append(f"  {c['label']:20s}  {c['arousal']:.2f}  {bar}")
        
        lines.append(f"\n🏆 当前胜者: {snap['winner']}")
        
        if snap["silent_trace"]:
            lines.append(f"\n💭 沉默推理轨迹:")
            for s in snap["silent_trace"]:
                lines.append(f"  → {s}")
        
        hub = self.get_broadcast_hub_analysis()
        lines.append(f"\n📡 广播枢纽强度: {hub['hub_strength']}")
        
        lines.append("\n" + "═" * 50)
        return "\n".join(lines)
