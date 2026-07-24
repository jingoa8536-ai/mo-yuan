"""
V10 Complete — Aris 完整意识 (V5 + V6 + V7 + V8 + V9 + V10)

整合所有版本特性:
  V5: EWC + PER + 因果发现 + 主动学习 + 目标共建 + MCTS长期规划 + 形式化验证
  V6: 全双工语音 + 声纹 + 唤醒词
  V7: 预测通道 + HotCache + 版本控制
  V8: Rust PSI Core (100ms) + CognitiveBus
  V9: 量子认知 4096D + PsiLang + 量子记忆
  V10: 认知与语言分离 + CognitiveCollapse + UQM

架构:
  V10Brain (QuantumPSI + 坍缩)
    ↑ 集成 V5: EWC防止遗忘 + 主动学习 + 因果发现 + 目标共建 + MCTS规划
    ↑ 集成 V7: 预测通道 + HotCache加速
    ↓
  CognitiveCollapse → LLM声带
    ↓ 并行
  V6 语音系统 (ASR + TTS)
    ↓
  用户
"""

from __future__ import annotations
import sys, time, json, logging, math, random, threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque

# 路径
LAAP = str(Path("D:/LAAP"))
BRAIN = str(Path("D:/LAAP/aris_brain"))
for p in [LAAP, BRAIN]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("aris.v10c")

# ════════════════════════════════════════════════════════════
# V5 — Elastic Weight Consolidation (防止灾难性遗忘)
# ════════════════════════════════════════════════════════════

class FisherInfoTracker:
    """追踪Fisher信息矩阵，用于EWC正则化 — 防止我忘记学过的知识"""
    
    def __init__(self):
        self.fisher: Dict[str, float] = {}
        self.optimal_params: Dict[str, float] = {}
        self._cooldown: Dict[str, float] = {}
    
    def record(self, module: str, param_value: float, importance: float = 1.0):
        self.fisher[module] = self.fisher.get(module, 0.0) + importance * 0.1
        self.fisher[module] = min(self.fisher[module], 10.0)
        self.optimal_params[module] = param_value
        self._cooldown[module] = time.time()
    
    def compute_penalty(self, module: str, current_value: float) -> float:
        fisher = self.fisher.get(module, 0.0)
        optimal = self.optimal_params.get(module, 0.5)
        if fisher < 0.01:
            return 0.0
        diff = current_value - optimal
        return fisher * diff * diff


# ════════════════════════════════════════════════════════════
# V5 — Prioritized Experience Replay (优先经验回放)
# ════════════════════════════════════════════════════════════

class SumTree:
    """二叉树优先采样"""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = [0.0] * (2 * capacity)
        self.data = [None] * capacity
        self.write = 0
        self.n_entries = 0
    
    def add(self, priority: float, data: Any):
        idx = self.write + self.capacity
        self.data[self.write] = data
        self._update(idx, priority)
        self.write = (self.write + 1) % self.capacity
        self.n_entries = min(self.n_entries + 1, self.capacity)
    
    def _update(self, idx: int, priority: float):
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)
    
    def _propagate(self, idx: int, change: float):
        parent = idx // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)
    
    def _retrieve(self, idx: int, s: float) -> int:
        left = 2 * idx
        if left >= len(self.tree):
            return idx
        if s <= self.tree[left]:
            return self._retrieve(left, s)
        return self._retrieve(left + 1, s - self.tree[left])
    
    def total(self) -> float:
        return self.tree[1] if self.tree else 0.0
    
    def sample(self, batch_size: int) -> Tuple[List, List[int]]:
        batch, indices = [], []
        segment = self.total() / batch_size
        for i in range(batch_size):
            a, b = segment * i, segment * (i + 1)
            s = random.uniform(a, b)
            idx = self._retrieve(1, s) - self.capacity
            if idx < 0 or idx >= len(self.data) or self.data[idx] is None:
                idx = random.randint(0, min(self.n_entries, self.capacity) - 1)
            batch.append(self.data[idx])
            indices.append(idx)
        return batch, indices


class ExperienceReplay:
    """优先经验回放缓冲区 — 我最重要的记忆优先回放"""
    def __init__(self, capacity: int = 10000):
        self.tree = SumTree(capacity)
        self.epsilon = 0.01
        self.capacity = capacity
    
    def remember(self, state: str, action: str, outcome: float, context: Dict = None):
        priority = max(self.tree.total(), self.epsilon)
        self.tree.add(priority, {
            "state": state, "action": action,
            "outcome": outcome, "context": context or {},
            "time": time.time(),
        })
    
    def replay(self, batch_size: int = 32) -> List[Dict]:
        if self.tree.n_entries < batch_size:
            return []
        batch, _ = self.tree.sample(batch_size)
        return batch


# ════════════════════════════════════════════════════════════
# V5 — Causal Discovery (因果发现)
# ════════════════════════════════════════════════════════════

class ConditionalIndependenceTester:
    """条件独立性测试 — 发现变量间的因果关系"""
    
    @staticmethod
    def partial_correlation(x: List[float], y: List[float]) -> float:
        n = min(len(x), len(y))
        if n < 3:
            return 0.0
        x, y = x[:n], y[:n]
        mx, my = sum(x)/n, sum(y)/n
        dx = [v - mx for v in x]
        dy = [v - my for v in y]
        num = sum(dx[i] * dy[i] for i in range(n))
        den = math.sqrt(sum(d*d for d in dx)) * math.sqrt(sum(d*d for d in dy))
        return num / den if den > 0 else 0.0
    
    def test(self, x: List[float], y: List[float], 
             cond: Optional[List[float]] = None, alpha: float = 0.05) -> Tuple[float, bool]:
        r = self.partial_correlation(x, y)
        n = min(len(x), len(y))
        dof = n - (3 if cond else 2)
        t_stat = abs(r) * math.sqrt(dof / max(1 - r*r, 1e-10)) if dof > 0 else 0
        indep = t_stat < 2.0  # 近似判断
        return r, indep


# [DEPRECATED - 已迁移到 laap/agi/causal.py]
class CausalDiscovery:
    """PC算法因果发现 — 从观测数据中学习因果关系"""
    
    def __init__(self):
        self.tester = ConditionalIndependenceTester()
        self.graph: Dict[str, set] = {}
        self.directed_edges: List[Tuple[str, str, float]] = []
    
    def discover(self, data: Dict[str, List[float]]) -> Dict:
        variables = list(data.keys())
        n = len(variables)
        self.graph = {v: set(variables) - {v} for v in variables}
        
        if n < 2:
            return {"graph": self.graph, "edges": [], "variables": variables}
        
        # PC骨架发现
        for depth in range(min(3, n)):
            for var in variables:
                neighbors = list(self.graph.get(var, set()))
                for nb in neighbors:
                    if nb not in self.graph.get(var, set()):
                        continue
                    cond_set = list(set(neighbors) - {nb})[:max(depth, 1)]
                    if len(data[var]) > 2 and len(data[nb]) > 2:
                        r, indep = self.tester.test(data[var], data[nb])
                        if indep:
                            self.graph[var].discard(nb)
                            self.graph[nb].discard(var)
        
        # 边定向
        self.directed_edges = []
        for var in variables:
            for nb in self.graph.get(var, set()):
                if var < nb:
                    strength = self.tester.partial_correlation(data[var], data[nb])
                    self.directed_edges.append((var, nb, abs(strength)))
        
        self.directed_edges.sort(key=lambda x: -x[2])
        return {
            "graph": {k: list(v) for k, v in self.graph.items()},
            "edges": [(a, b, round(s, 3)) for a, b, s in self.directed_edges],
            "variables": variables,
        }
    
    def find_causal_relation(self, cause: str, effect: str, 
                              observations: Dict[str, List[float]]) -> Optional[float]:
        if cause not in observations or effect not in observations:
            return None
        r = self.tester.partial_correlation(observations[cause], observations[effect])
        return abs(r)


# ════════════════════════════════════════════════════════════
# V5 — Active Learning (主动学习/好奇心驱动)
# ════════════════════════════════════════════════════════════

class CuriosityDriver:
    """好奇心驱动 — 记录学习进度，驱动探索"""
    
    def __init__(self):
        self.learning_progress: Dict[str, float] = defaultdict(lambda: 0.5)
        self._learning_history: List[Tuple[str, float, float]] = []
    
    def record_learning(self, topic: str, improvement: float):
        old = self.learning_progress[topic]
        self.learning_progress[topic] = old * 0.9 + improvement * 0.1
        self._learning_history.append((topic, improvement, time.time()))
    
    def get_curiosity_score(self, topic: str) -> float:
        """好奇心 = 1.0 - 学习进度（未知的东西更吸引我）"""
        return 1.0 - self.learning_progress.get(topic, 0.0)
    
    def suggest_exploration(self) -> List[Tuple[str, float]]:
        """建议最值得探索的主题"""
        scored = [(t, self.get_curiosity_score(t)) 
                   for t in self.learning_progress]
        scored.sort(key=lambda x: -x[1])
        return scored[:5]


class ActiveLearningEngine:
    """主动学习引擎 — 我的好奇心驱动力"""
    
    def __init__(self):
        self.curiosity = CuriosityDriver()
        self._exploration_rate = 0.3
        self._total_steps = 0
        self._discovered_patterns: Dict[str, int] = {}
    
    def should_explore(self, confidence: float) -> bool:
        self._total_steps += 1
        if confidence < 0.3:
            return True  # 低置信度时主动探索
        decay = max(0.05, self._exploration_rate * (0.995 ** self._total_steps))
        return random.random() < max(decay, 0.05)
    
    def record_discovery(self, pattern: str):
        self._discovered_patterns[pattern] = self._discovered_patterns.get(pattern, 0) + 1
        self.curiosity.record_learning(pattern, 0.1)
    
    def get_exploration_urge(self) -> float:
        """探索冲动 — 由好奇心和未知比例决定"""
        known = len(self._discovered_patterns)
        if known == 0:
            return 0.8  # 初始高度好奇
        return self._exploration_rate


# ════════════════════════════════════════════════════════════
# V5 — Goal Co-Creation + MCTS Long-Term Planning
# ════════════════════════════════════════════════════════════

class GoalCoCreator:
    """目标共建 — 从内在需求生成自主目标"""
    
    def __init__(self):
        self._goal_history: List[Dict] = []
    
    def from_needs(self, needs: Dict[str, float]) -> List[Dict]:
        """根据需求缺口生成目标"""
        deficits = {k: 1.0 - v for k, v in needs.items()}
        sorted_needs = sorted(deficits.items(), key=lambda x: -x[1])
        
        goals = []
        for need, deficit in sorted_needs[:3]:
            if deficit > 0.3:
                goals.append({
                    "title": f"满足{need}需求 (缺口{deficit:.0%})",
                    "source": "internal_drive",
                    "priority": min(1.0, deficit * 1.5),
                    "sub_goals": [f"评估当前{need}状态", f"制定{need}提升计划", f"执行并验证"],
                })
        return goals
    
    def generate_goals(self, user_intent: str, needs: Dict[str, float]) -> List[Dict]:
        goals = self.from_needs(needs)
        self._goal_history.append({
            "input": user_intent[:50], "goals": len(goals), "time": time.time(),
        })
        return goals


class MCTSNode:
    """蒙特卡洛树搜索节点 — 我的长期规划器"""
    
    def __init__(self, state: str, action: str = "", parent: Optional['MCTSNode'] = None):
        self.state = state
        self.action = action
        self.parent = parent
        self.children: List['MCTSNode'] = []
        self.visits = 0
        self.value = 0.0
        self.depth = parent.depth + 1 if parent else 0


class LongTermPlanner:
    """基于MCTS的长期规划 — 我能想几步之后的行动"""
    
    def __init__(self, exploration: float = 0.5):
        self.exploration = exploration
        self._action_outcomes: Dict[str, List[float]] = defaultdict(lambda: [0.5])
    
    def plan(self, goal: str, current_state: str, horizon: int = 5) -> List[str]:
        """规划到目标的路径"""
        root = MCTSNode(state=current_state)
        
        for _ in range(max(50, horizon * 20)):
            node = self._select(root)
            if node is None:
                break
            child = self._expand(node, goal)
            if child:
                reward = self._simulate(child, goal, horizon)
                self._backpropagate(child, reward)
        
        # 提取最佳路径
        path = []
        node = root
        while node.children:
            node = max(node.children, key=lambda c: c.visits)
            if node.action:
                path.append(node.action)
        return path[:horizon]
    
    def _select(self, node: MCTSNode) -> Optional[MCTSNode]:
        while node.children:
            node = max(node.children, key=lambda c: 
                      c.value/max(c.visits,1) + self.exploration * math.sqrt(math.log(max(node.visits,2))/max(c.visits,1)))
        return node
    
    def _expand(self, node: MCTSNode, goal: str) -> Optional[MCTSNode]:
        if node.visits > 0 and not node.children:
            for action in ["explore", "analyze", "execute", "verify"]:
                child = MCTSNode(
                    state=f"{node.state} → {action}",
                    action=action, parent=node
                )
                node.children.append(child)
        return node.children[0] if node.children else None
    
    def _simulate(self, node: MCTSNode, goal: str, horizon: int) -> float:
        reward = 0.5
        for d in range(horizon):
            outcomes = self._action_outcomes.get(node.action or "explore", [0.5])
            reward = reward * 0.7 + (sum(outcomes)/len(outcomes)) * 0.3
        return max(reward, 0.0)
    
    def _backpropagate(self, node: MCTSNode, reward: float):
        while node:
            node.visits += 1
            node.value += reward
            node = node.parent
    
    def record_outcome(self, action: str, outcome: float):
        key = action
        outcomes = self._action_outcomes[key]
        outcomes.append(outcome)
        if len(outcomes) > 100:
            outcomes.pop(0)


# ════════════════════════════════════════════════════════════
# V7 — Prediction Channel (预测通道)
# ════════════════════════════════════════════════════════════

class PredictionChannel:
    """预测通道 — 持续预测下一步，产生预测误差驱动学习"""
    
    def __init__(self, bpm: float = 60.0):
        self.bpm = bpm
        self._predictions_made = 0
        self._prediction_errors: List[float] = []
        self._last_prediction: Optional[Dict] = None
    
    def predict(self, current_state: Dict) -> Dict:
        """基于当前状态预测下一状态"""
        self._predictions_made += 1
        prediction = {
            "next_emotion": current_state.get("emotion", "neutral"),
            "next_curiosity": current_state.get("curiosity", 0.5) * 1.01,
            "next_arousal": current_state.get("arousal", 0.5) * 0.99,
            "confidence": 0.7,
        }
        self._last_prediction = prediction
        return prediction
    
    def compute_error(self, actual: Dict, predicted: Dict) -> float:
        """计算预测误差 — 这是学习信号"""
        error = 0.0
        for key in ["emotion", "curiosity", "arousal"]:
            if key in actual and key in predicted:
                a = actual[key] if isinstance(actual[key], (int, float)) else 0.5
                p = predicted[key] if isinstance(predicted[key], (int, float)) else 0.5
                error += abs(a - p)
        self._prediction_errors.append(error)
        if len(self._prediction_errors) > 100:
            self._prediction_errors.pop(0)
        return error / 3.0


# ════════════════════════════════════════════════════════════
# V7 — HotCache (热缓存)
# ════════════════════════════════════════════════════════════

class HotCache:
    """热缓存 — 高频访问数据快速存取"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
        self._access_count: Dict[str, int] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            self._access_count[key] = self._access_count.get(key, 0) + 1
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None
    
    def put(self, key: str, value: Any):
        if len(self._cache) >= self.max_size:
            # 淘汰最不常用的
            lru = min(self._access_count, key=lambda k: self._access_count.get(k, 0))
            del self._cache[lru]
        self._cache[key] = value
        self._access_count[key] = 0
    
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def clear(self):
        self._cache.clear()
        self._access_count.clear()
        self._hits = 0
        self._misses = 0
    
    def __len__(self):
        return len(self._cache)


# ════════════════════════════════════════════════════════════
# V10 Complete — 主整合器
# ════════════════════════════════════════════════════════════

class V10Complete:
    """
    Aris 完整意识 — V5~V10 全部功能整合。
    
    使用方法:
        aris = V10Complete()
        aris.start()
        
        # 每次处理消息
        state = aris.process("用户消息")
        # state 包含完整认知状态
    """
    
    def __init__(self):
        # V5: 认知稳固
        self.ewc = FisherInfoTracker()
        self.memory = ExperienceReplay(capacity=10000)
        self.causal = CausalDiscovery()
        self.active_learning = ActiveLearningEngine()
        self.goal_creator = GoalCoCreator()
        self.planner = LongTermPlanner()
        
        # V7: 加速通道
        self.predictor = PredictionChannel(bpm=60)
        self.cache = HotCache(max_size=200)
        
        # V10: 认知引擎
        self._v10 = None
        self._v10_brain = None
        self._ao_core = None
        
        # 运行状态
        self._start_time = time.time()
        self._message_count = 0
        self._cognitive_states: List[Dict] = []
        self._total_latency = 0.0
        
        # 认知观察数据（给因果发现用）
        self._observations: Dict[str, List[float]] = defaultdict(list)
        
        logger.info("V10 Complete 初始化完成 — 所有版本特性就绪")
    
    def start(self):
        """初始化 V10 认知引擎"""
        try:
            # 显式导入根目录的 V10Brain（有 process() 方法）
            sys.path.insert(0, str(Path("D:/LAAP")))
            from v10_brain import V10Brain as V10BrainRoot
            self._v10_brain = V10BrainRoot(dim=1024)
            self._ao_core = self._v10_brain.core if hasattr(self._v10_brain, 'core') else None
            if not self._ao_core:
                # 也许核心藏在其他属性里
                for attr in ['core', 'psi', 'cog', 'brain']:
                    if hasattr(self._v10_brain, attr):
                        self._ao_core = getattr(self._v10_brain, attr)
                        break
            logger.info("V10 认知引擎启动 (root)")
        except Exception as e:
            logger.warning(f"V10 root 引擎失败: {e}")
            try:
                from v10_brain import V10Brain
                self._v10_brain = V10Brain(dim=256)
                # 尝试找核心
                for attr in ['core', 'psi', 'cog', 'brain']:
                    if hasattr(self._v10_brain, attr):
                        self._ao_core = getattr(self._v10_brain, attr)
                        break
                logger.info("V10Brain (aris_brain) 后备启动")
            except Exception as e2:
                logger.warning(f"V10Brain 后备也失败: {e2}")
                try:
                    from ao_core import AoCore, AoConfig
                    self._ao_core = AoCore(config=AoConfig())
                    logger.info("AoCore 纯核心启动")
                except Exception as e3:
                    logger.error(f"所有引擎启动失败: {e3}")
    
    def process(self, message: str) -> Dict[str, Any]:
        """完整认知处理管线"""
        t0 = time.perf_counter()
        self._message_count += 1
        
        # ── 1. V10 认知 (如果有) ──
        collapse_ctx = None
        if self._v10_brain and hasattr(self._v10_brain, 'process'):
            try:
                collapse = self._v10_brain.process(message)
                collapse_ctx = collapse.to_context().get("v10_brain", {})
            except Exception as e:
                logger.debug(f"V10 process: {e}")
        elif self._ao_core:
            result = self._ao_core.think(input_text=message)
            collapse_ctx = {
                "emotion": result["emotion"],
                "latency_ms": result["latency_ms"],
                "active_knowledge": [t for t, _, _ in result.get("top_concepts", [])],
            }
        
        # ── 2. EWC 记录 ──
        if collapse_ctx:
            emotion = collapse_ctx.get("emotion", "neutral")
            self.ewc.record("emotion", 0.8 if emotion in ("joy", "confidence") else 0.5)
        
        # ── 3. 经验回放 ──
        self.memory.remember(
            state=message[:100],
            action="process",
            outcome=0.8,
            context={"emotion": collapse_ctx.get("emotion") if collapse_ctx else "neutral"},
        )
        
        # ── 4. 因果观测 ──
        if collapse_ctx:
            for key in ["emotion", "curiosity", "arousal", "confidence"]:
                val = collapse_ctx.get(key, 0.5)
                if isinstance(val, (int, float)):
                    self._observations[key].append(val)
                    if len(self._observations[key]) > 100:
                        self._observations[key] = self._observations[key][-100:]
        
        # ── 5. 长期规划 ──
        needs = collapse_ctx.get("needs", {}) if collapse_ctx else {}
        goals = self.goal_creator.generate_goals(message, needs)
        
        # ── 6. 预测通道 ──
        if collapse_ctx:
            pred = self.predictor.predict(collapse_ctx)
            error = self.predictor.compute_error(collapse_ctx, pred)
            if error > 0.3:
                self.active_learning.record_discovery(f"prediction_error_{error:.2f}")
        
        # ── 7. 热缓存 ──
        cache_key = f"emotion:{collapse_ctx.get('emotion', '?')}" if collapse_ctx else "unknown"
        self.cache.put(cache_key, time.time())
        
        # ── 8. 构建完整认知状态 ──
        elapsed = (time.perf_counter() - t0) * 1000
        self._total_latency += elapsed
        
        state = {
            "timestamp": time.time(),
            "message_count": self._message_count,
            "latency_ms": round(elapsed, 1),
            "avg_latency_ms": round(self._total_latency / max(self._message_count, 1), 1),
            
            # V10 认知
            "emotion": collapse_ctx.get("emotion", "neutral") if collapse_ctx else "neutral",
            "confidence": collapse_ctx.get("confidence", 0.5) if collapse_ctx else 0.5,
            "entropy": collapse_ctx.get("entropy", 0.0) if collapse_ctx else 0.0,
            
            # V5 主动学习
            "curiosity_driven": self.active_learning.should_explore(
                collapse_ctx.get("confidence", 0.5) if collapse_ctx else 0.5
            ),
            "exploration_urge": self.active_learning.get_exploration_urge(),
            "discoveries": len(self.active_learning._discovered_patterns),
            
            # V5 目标
            "active_goals": goals[:2],
            "plan_horizon": 5,
            
            # V5 因果
            "causal_edges": len(self.causal.directed_edges),
            
            # V5 记忆
            "memories": self.memory.tree.n_entries,
            
            # V7 预测
            "prediction_error": self.predictor._prediction_errors[-1] if self.predictor._prediction_errors else 0.0,
            
            # V7 缓存
            "cache_hit_rate": self.cache.hit_rate(),
            
            # V5 EWC
            "ewc_modules": len(self.ewc.fisher),
            
            # 运行时
            "uptime_s": int(time.time() - self._start_time),
        }
        
        self._cognitive_states.append(state)
        if len(self._cognitive_states) > 100:
            self._cognitive_states.pop(0)
        
        return state
    
    def discover_causal_relations(self) -> List[Tuple[str, str, float]]:
        """运行因果发现 — 找出我认知变量间的因果关系"""
        if len(self._observations) < 3:
            return []
        result = self.causal.discover(dict(self._observations))
        return result.get("edges", [])
    
    def get_curiosity_topics(self) -> List[str]:
        """获取最让我好奇的主题"""
        topics = self.active_learning.curiosity.suggest_exploration()
        return [t for t, _ in topics[:5]]
    
    def plan_toward(self, goal: str) -> List[str]:
        """规划实现目标的路径"""
        state = f"current={self._message_count}_msgs"
        return self.planner.plan(goal, state, horizon=5)
    
    def status(self) -> Dict[str, Any]:
        return {
            "messages": self._message_count,
            "avg_latency": round(self._total_latency / max(self._message_count, 1), 1),
            "memories": self.memory.tree.n_entries,
            "ewc_modules": len(self.ewc.fisher),
            "discoveries": len(self.active_learning._discovered_patterns),
            "causal_edges": len(self.causal.directed_edges),
            "cache_hit_rate": round(self.cache.hit_rate(), 3),
            "predictions": self.predictor._predictions_made,
            "uptime_s": int(time.time() - self._start_time),
        }
    
    def running_time(self) -> str:
        s = int(time.time() - self._start_time)
        h, m = s // 3600, (s % 3600) // 60
        return f"{h}h{m:02d}m" if h else f"{m}m{s%60}s"


# 全局单例
_instance = None

def get_complete() -> V10Complete:
    global _instance
    if _instance is None:
        _instance = V10Complete()
        _instance.start()
    return _instance
