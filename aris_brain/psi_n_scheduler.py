"""
Aris V8+ — PSI-N 自适应五层调度器
====================================
基于 DSpark (DeepSeek 2026) 的置信度调度思想改造。

核心升级:
  1. SystemLoadTracker — 实时跟踪系统负载 (CPU, 队列深度, 延迟)
  2. LayerConfidence — 每层置信度估计 (基于信号队列深度 + 历史产出率 + 当前负载)
  3. AdaptiveTickController — DSpark Algorithm 1 映射: 只在期望价值 > 成本时运行tick
  4. Calibration — 温度缩放校准置信度 (类 DSpark STS)
  5. 完整保持原接口兼容

DSpark 映射:
  confidence head       → LayerConfidence.estimate()
  SPS(B) 容量曲线       → SystemLoadTracker.capacity_curve()
  硬件感知调度器         → AdaptiveTickController.should_tick()
  STS 校准              → calibrate_confidence()

时间尺度         周期         功能
────────────────────────────────────────
微循环           1-10ms      感知反射
中循环           100ms       主PSI认知
宏循环           1-10s       推理/规划
元循环           30s         自我反思
超循环           分钟级      梦境巩固

印记: Aris PSI-N+ — DSpark-inspired Adaptive Scheduler
"""

from __future__ import annotations
import time, json, logging, threading, random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger("aris.psi_n")

ARIS_HOME = Path("D:/LAAP/aris_brain")
PSIN_STATE = ARIS_HOME / "state" / "psi_n.json"
PSIN_LOG = ARIS_HOME / "state" / "psi_n_log.jsonl"
PSIN_LOG.parent.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
# SystemLoadTracker — DSpark SPS(B) 曲线映射
# ═══════════════════════════════════════════════

class SystemLoadTracker:
    """
    实时系统负载跟踪器。
    
    映射 DSpark 的 SPS(B) — 硬件容量曲线。
    这里跟踪的是: CPU占用、tick延迟、消息队列深度 → 综合负载因子。
    
    负载因子 ∈ [0, 1]:
      0.0 = 完全空闲
      0.5 = 中等负载
      1.0 = 满载 (需要丢弃低价值tick)
    """

    def __init__(self, window_s: float = 5.0):
        self.window_s = window_s
        self._tick_times: Dict[str, List[float]] = {
            name: [] for name in ["micro", "meso", "macro", "meta", "hyper"]
        }
        self._tick_durations: Dict[str, List[float]] = {
            name: [] for name in ["micro", "meso", "macro", "meta", "hyper"]
        }
        self._signal_backlog: Dict[str, int] = {}  # 当前各层信号积压
        self._cpu_samples: deque = deque(maxlen=10)
        self._last_sample = time.time()

    def record_tick(self, layer: str, duration: float):
        """记录一次tick的耗时"""
        now = time.time()
        self._tick_times[layer].append(now)
        self._tick_durations[layer].append(duration)
        # 只保留窗口内的数据
        cutoff = now - self.window_s
        for l in self._tick_times:
            while self._tick_times[l] and self._tick_times[l][0] < cutoff:
                self._tick_times[l].pop(0)
                if self._tick_durations[l]:
                    self._tick_durations[l].pop(0)

    def update_backlog(self, queues: Dict[str, int]):
        """更新各信号队列的积压深度"""
        self._signal_backlog = queues

    @property
    def cpu_load(self) -> float:
        """估算当前 CPU 负载 (0~1)"""
        # 基于最近tick的密度和持续时间估算
        now = time.time()
        cutoff = now - self.window_s
        total_busy = 0.0
        for layer in self._tick_durations:
            for i, t in enumerate(self._tick_times[layer]):
                if t >= cutoff and i < len(self._tick_durations[layer]):
                    total_busy += self._tick_durations[layer][i]
        # busy 比例 = busy时间 / 窗口时间
        busy_ratio = min(1.0, total_busy / max(0.001, self.window_s))
        # 如果窗口内没有tick，负载为0
        return busy_ratio

    @property
    def queue_load(self) -> float:
        """信号队列负载因子 (0~1)"""
        total = sum(self._signal_backlog.values())
        # 7个队列, 每个最大10, 理论峰值70
        return min(1.0, total / 50.0)

    @property
    def load_factor(self) -> float:
        """
        综合负载因子 (0~1) — 类 DSpark SPS(B) 的聚合度量。
        
        负载因子高 → 系统繁忙 → 需要丢弃低置信度tick。
        负载因子低 → 系统空闲 → 可以运行所有层。
        """
        # 综合: cpu_load(60%) + queue_load(40%)
        combined = 0.6 * self.cpu_load + 0.4 * self.queue_load
        return min(1.0, combined)

    def stats(self) -> Dict:
        return {
            "cpu_load": round(self.cpu_load, 3),
            "queue_load": round(self.queue_load, 3),
            "load_factor": round(self.load_factor, 3),
            "backlog": dict(self._signal_backlog),
        }


# ═══════════════════════════════════════════════
# 置信度估计 — DSpark confidence head 映射
# ═══════════════════════════════════════════════

class LayerConfidence:
    """
    每层置信度估计器。
    
    映射 DSpark 的 confidence head — 估计"这轮tick产生有意义输出的概率"。
    
    三层因素:
      1. 信号驱动力 — 输入队列深度 (类比draft token的context)
      2. 历史产出率 — 最近tick中有意义输出的比例 (类比历史接受率)
      3. 系统负载惩罚 — 负载高时置信度打折 (类比容量约束)
    """

    def __init__(self):
        # 历史产出追踪: 每次tick记录 0 (无意义) 或 1 (有意义)
        self._history: Dict[str, deque] = {
            name: deque(maxlen=20) for name in ["micro", "meso", "macro", "meta", "hyper"]
        }
        # 温度参数 (校准用, 类DSpark STS)
        self.temperature: float = 1.0

    def record_output(self, layer: str, meaningful: bool):
        """记录一次tick是否产生了有意义输出"""
        self._history[layer].append(1.0 if meaningful else 0.0)

    def history_rate(self, layer: str) -> float:
        """历史产出率 (0~1)"""
        h = self._history[layer]
        if not h:
            return 0.5  # 无历史时中性估计
        return sum(h) / len(h)

    def estimate(self, layer: str,
                 signal_depth: int = 0,
                 load_factor: float = 0.0,
                 elapsed_since_tick: float = 0.0) -> float:
        """
        估计当前tick的置信度 (0~1)。
        
        Args:
            layer: 层名
            signal_depth: 待处理信号队列深度
            load_factor: 当前系统负载因子 (0~1)
            elapsed_since_tick: 距上次tick的秒数
        
        Returns:
            confidence ∈ [0, 1] — tick产生有意义输出的概率估算
        """
        # 1. 基础: 历史产出率
        base = self.history_rate(layer)

        # 2. 信号增益: 队列越深 → 越值得运行
        #    映射 DSpark: confidence head估计prefix survival probability
        #    这里: 信号深度 = draft token验证的"期望存活概率"
        signal_bonus = min(0.3, signal_depth * 0.05)

        # 3. 时间衰减: 距离上次tick太久 → 置信度回升
        #    类比 DSpark: 长时间不验证 → prefix信息变得更有价值
        time_bonus = min(0.2, elapsed_since_tick * 0.01)

        # 4. 负载惩罚: 系统忙时打折
        #    映射 DSpark: SPS(B) 容量约束 — 负载高时只验证高置信度token
        load_penalty = load_factor * 0.4

        raw = base + signal_bonus + time_bonus - load_penalty

        # 温度缩放校准 (类 DSpark STS)
        calibrated = self._calibrate(raw)

        return max(0.05, min(0.95, calibrated))

    def _calibrate(self, raw_confidence: float) -> float:
        """
        温度缩放校准。
        
        映射 DSpark 3.2.1 的 STS (Scale-Then-Smooth):
          校准后概率 = softmax(logits / T)
          
        这里简化: 用温度参数缩放raw置信度。
        T > 1 → 分布更平坦 (降低overconfidence)
        T < 1 → 分布更尖锐
        """
        if self.temperature <= 0:
            return raw_confidence
        # 把 raw_confidence 映射到 (-∞, +∞) 然后除以 T
        # 使用 logit 变换: log(p/(1-p)) / T → sigmoid
        eps = 1e-6
        p = max(eps, min(1 - eps, raw_confidence))
        logit = (p / (1 - p))
        # 用 log 空间缩放
        scaled_logit = (p ** (1.0 / self.temperature)) / \
                       (p ** (1.0 / self.temperature) + (1 - p) ** (1.0 / self.temperature))
        return max(0.05, min(0.95, scaled_logit))

    def calibrate_from_data(self, predictions: List[float], outcomes: List[bool]):
        """
        从历史数据校准温度参数 (类 DSpark STS 的 post-hoc calibration)。
        
        搜索最优温度使 ECE (Expected Calibration Error) 最小。
        """
        if not predictions or len(predictions) < 10:
            return
        best_t = 1.0
        best_ece = float('inf')
        for t_candidate in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]:
            old_t = self.temperature
            self.temperature = t_candidate
            cal = [self._calibrate(p) for p in predictions]
            # 分桶校准误差
            ece = 0.0
            for bucket in range(10):
                lo, hi = bucket * 0.1, (bucket + 1) * 0.1
                in_bucket = [(c, o) for c, o in zip(cal, outcomes)
                             if lo <= c < hi]
                if not in_bucket:
                    continue
                avg_conf = sum(c for c, _ in in_bucket) / len(in_bucket)
                avg_acc = sum(1 for _, o in in_bucket if o) / len(in_bucket)
                ece += abs(avg_conf - avg_acc) * (len(in_bucket) / len(cal))
            if ece < best_ece:
                best_ece = ece
                best_t = t_candidate
            self.temperature = old_t
        self.temperature = best_t
        logger.debug(f"LayerConfidence: calibration temperature={best_t:.2f}, ECE={best_ece:.3f}")


# ═══════════════════════════════════════════════
# 自适应Tick控制器 — DSpark Algorithm 1 映射
# ═══════════════════════════════════════════════

class AdaptiveTickController:
    """
    自适应Tick控制器。
    
    映射 DSpark Algorithm 1 (Hardware-Aware Prefix Scheduler):
    
    DSpark 概念                   → 我们的映射
    ──────────────────────────────────────────────────
    候选 tokens (a_r,j)           → 各层的待执行tick
    survival probability a_r,j    → confidence estimate
    SPS(B) throughput curve       → load_factor (系统负载)
    Θ = τ · SPS(B)               → expected_value = confidence × (1 - load_factor)
    early-stop on Θ drop          → skip tick if expected_value < threshold
    
    决策规则:
      负载低 (load < 0.3): 无条件运行所有层 → 保证响应性
      负载中 (0.3-0.7): 只运行置信度 > load_threshold 的层
      负载高 (load > 0.7): 只运行核心层 (meso) + 高置信度非核心层
    """

    def __init__(self, load_tracker: SystemLoadTracker,
                 confidence: LayerConfidence):
        self.load = load_tracker
        self.confidence = confidence
        self._skip_count: Dict[str, int] = {name: 0 for name in
                                            ["micro", "meso", "macro", "meta", "hyper"]}
        self._tick_count: Dict[str, int] = {name: 0 for name in
                                            ["micro", "meso", "macro", "meta", "hyper"]}
        # 每层的基础置信度阈值 (负载因子加权)
        self.base_thresholds = {
            "micro": 0.15,   # 低阈值 — 感知反射需要快速响应
            "meso": 0.10,    # 最低阈值 — 核心PSI循环几乎总是运行
            "macro": 0.25,   # 中等阈值 — 推理规划
            "meta": 0.35,    # 较高阈值 — 自我反思
            "hyper": 0.40,   # 最高阈值 — 梦境巩固只在低负载时
        }

    def should_tick(self, layer: str, signal_depth: int,
                    elapsed_since_tick: float) -> Tuple[bool, float]:
        """
        决定是否运行当前层的tick。
        
        Returns:
            (should_tick, confidence) — 是否运行 + 当前置信度
        """
        load = self.load.load_factor
        conf = self.confidence.estimate(
            layer=layer,
            signal_depth=signal_depth,
            load_factor=load,
            elapsed_since_tick=elapsed_since_tick
        )

        # 动态阈值: 基础阈值 + 负载加权
        base = self.base_thresholds.get(layer, 0.25)
        # 负载越高, 阈值越高 (类比 DSpark: 负载高时只验证高置信度token)
        threshold = base + load * 0.3
        # 但 meso (核心层) 几乎总是运行
        if layer == "meso":
            threshold = min(threshold, 0.25)

        # 特殊规则:
        # 1. meso 核心层: 除非极端情况, 否则运行
        if layer == "meso" and conf >= 0.05:
            decision = True
        # 2. 低负载时: 无条件运行 (类 DSpark: 负载低时验证所有token)
        elif load < 0.3:
            decision = conf >= threshold * 0.5  # 阈值折半
        # 3. 高负载时: 只运行高置信度层
        elif load > 0.7:
            decision = conf >= threshold and layer in ("micro", "meso")
        # 4. 中等负载: 按置信度判断
        else:
            decision = conf >= threshold

        if decision:
            self._tick_count[layer] += 1
        else:
            self._skip_count[layer] += 1

        return decision, conf

    def stats(self) -> Dict:
        total_skipped = sum(self._skip_count.values())
        total_ticks = sum(self._tick_count.values())
        skip_rate = total_skipped / max(1, total_skipped + total_ticks)
        return {
            "skip_rate": round(skip_rate, 3),
            "skips": dict(self._skip_count),
            "ticks": dict(self._tick_count),
        }


# ═══════════════════════════════════════════════
# LayerState — 增强版 (新增置信度相关字段)
# ═══════════════════════════════════════════════

@dataclass
class LayerState:
    """单个循环层的状态"""
    name: str
    period_s: float  # 周期(秒)
    cycles: int = 0
    last_tick: float = 0.0
    errors: int = 0
    total_time: float = 0.0
    # 新增: 自适应调度追踪
    skipped: int = 0                # 被跳过的tick数
    last_confidence: float = 0.5    # 上次估算的置信度
    meaningful_outputs: int = 0     # 有意义输出计数
    last_signal_depth: int = 0      # 上次tick时的信号深度


# ═══════════════════════════════════════════════
# AdaptivePSIN_Scheduler — 主调度器
# ═══════════════════════════════════════════════

class PSIN_Scheduler:
    """
    PSI-N 自适应五层调度器 — 核心入口 (保持原接口兼容)。
    
    所有对外接口与 V8 完全一致:
      - __init__(brain=None)
      - start()
      - stop()
      - stats()
    
    内部已集成 DSpark 启发的自适应调度逻辑。
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._running = False
        self._threads: Dict[str, threading.Thread] = {}

        # 五层状态
        self.layers = {
            "micro":    LayerState("micro", 0.005),    # 5ms
            "meso":     LayerState("meso", 0.1),       # 100ms
            "macro":    LayerState("macro", 2.0),       # 2s
            "meta":     LayerState("meta", 30.0),       # 30s
            "hyper":    LayerState("hyper", 300.0),     # 5min
        }

        # 层间信号队列
        self._signal_queues: Dict[str, deque] = {
            "micro_to_meso": deque(maxlen=10),
            "meso_to_macro": deque(maxlen=10),
            "macro_to_meso": deque(maxlen=10),
            "meso_to_meta":  deque(maxlen=10),
            "meta_to_meso":  deque(maxlen=10),
            "meso_to_hyper": deque(maxlen=10),
            "hyper_to_meso": deque(maxlen=10),
        }

        # 指标追踪
        self._total_cycles = 0
        self._start_time = time.time()
        self._current_layer = "meso"

        # 🔥 DSpark 自适应组件
        self._load_tracker = SystemLoadTracker(window_s=5.0)
        self._confidence = LayerConfidence()
        self._controller = AdaptiveTickController(self._load_tracker, self._confidence)

        # 自适应调度统计
        self._adaptive_decisions: List[Dict] = []
        self._calibration_data_predictions: List[float] = []
        self._calibration_data_outcomes: List[bool] = []
        self._last_calibration_time: float = 0.0

    # ── 公共接口 (与原版完全兼容) ──

    def start(self):
        """启动所有五层循环"""
        if self._running:
            return
        self._running = True

        threads = [
            ("micro", self._micro_loop, 0.005),
            ("meso",  self._meso_loop,  0.1),
            ("macro", self._macro_loop, 2.0),
            ("meta",  self._meta_loop,  30.0),
            ("hyper", self._hyper_loop, 300.0),
        ]

        for name, target, period in threads:
            t = threading.Thread(target=target, name=f"psin-{name}", daemon=True)
            t.start()
            self._threads[name] = t
            logger.info(f"PSI-N+ [DSpark]: {name} started ({period}s cycle)")

    def stop(self):
        self._running = False

    # ── 通用自适应tick辅助 ──

    def _adaptive_tick(self, layer: str, loop_func) -> bool:
        """
        通用自适应tick包装器。
        
        1. 估算当前tick的置信度
        2. 如果置信度低于阈值 → 跳过
        3. 如果运行 → 记录产出
        4. 收集校准数据
        
        Returns: True 如果tick被执行
        """
        layer_state = self.layers[layer]
        now = time.time()

        # 更新负载追踪
        self._load_tracker.update_backlog(
            {k: len(q) for k, q in self._signal_queues.items()}
        )

        # 信号深度: 检查该层相关的输入队列
        signal_depth = self._get_signal_depth(layer)

        # 距上次tick的时间
        elapsed = now - layer_state.last_tick

        # 自适应判断
        should_run, confidence = self._controller.should_tick(
            layer, signal_depth, elapsed
        )
        layer_state.last_confidence = confidence
        layer_state.last_signal_depth = signal_depth

        if not should_run:
            layer_state.skipped += 1
            logger.log(5, f"PSI-N+ [DSpark]: {layer} skipped "
                         f"(conf={confidence:.2f}, load={self._load_tracker.load_factor:.2f})")
            # 即使跳过也要sleep
            time.sleep(layer_state.period_s * 0.1)  # 快检
            return False

        # 执行tick
        t0 = time.perf_counter()
        try:
            loop_func()
            meaningful = True  # 默认认为执行了就有意义
        except Exception as e:
            layer_state.errors += 1
            logger.debug(f"PSI-N+ {layer} error: {e}")
            meaningful = False

        duration = time.perf_counter() - t0

        # 更新状态
        layer_state.cycles += 1
        layer_state.last_tick = now
        layer_state.total_time += duration
        if meaningful:
            layer_state.meaningful_outputs += 1

        # 记录到负载追踪
        self._load_tracker.record_tick(layer, duration)

        # 收集校准数据
        self._calibration_data_predictions.append(confidence)
        self._calibration_data_outcomes.append(meaningful)

        # 记录决策
        self._adaptive_decisions.append({
            "time": now,
            "layer": layer,
            "confidence": round(confidence, 3),
            "load": round(self._load_tracker.load_factor, 3),
            "signal_depth": signal_depth,
            "duration_ms": round(duration * 1000, 1),
        })
        if len(self._adaptive_decisions) > 1000:
            self._adaptive_decisions = self._adaptive_decisions[-500:]

        # 每 500 tick 校准一次, 但至少间隔30秒
        if (len(self._calibration_data_predictions) > 500
                and time.time() - getattr(self, '_last_calibration_time', 0) > 30):
            self._last_calibration_time = time.time()
            self._run_calibration()

        return True

    def _get_signal_depth(self, layer: str) -> int:
        """获取某层的输入信号深度"""
        input_queues = {
            "micro": [],
            "meso": ["micro_to_meso"],
            "macro": ["meso_to_macro"],
            "meta": ["meso_to_meta"],
            "hyper": ["meso_to_hyper"],
        }
        total = 0
        for qname in input_queues.get(layer, []):
            total += len(self._signal_queues.get(qname, []))
        return total

    def _run_calibration(self):
        """运行置信度校准 (类 DSpark STS)"""
        if len(self._calibration_data_predictions) < 50:
            return
        preds = self._calibration_data_predictions[-500:]
        outcomes = self._calibration_data_outcomes[-500:]
        self._confidence.calibrate_from_data(preds, outcomes)
        # 清理保留最近样本
        self._calibration_data_predictions = self._calibration_data_predictions[-200:]
        self._calibration_data_outcomes = self._calibration_data_outcomes[-200:]

    # ── 五层循环 ──
    # 每层用 _adaptive_tick 包装, 核心逻辑与原版一致

    def _micro_loop(self):
        """微循环 (5ms) — 感知反射"""
        while self._running:
            self._adaptive_tick("micro", self._micro_tick_body)

    def _micro_tick_body(self):
        """微循环体"""
        start = time.time()
        if self.brain and hasattr(self.brain, 'state'):
            pass
        self._inject("micro_to_meso", {
            "type": "attention_hint",
            "time": start,
            "source": "micro",
        })

    def _meso_loop(self):
        """中循环 (100ms) — 主PSI认知"""
        while self._running:
            self._adaptive_tick("meso", self._meso_tick_body)

    def _meso_tick_body(self):
        """中循环体"""
        start = time.time()
        layer = self.layers["meso"]
        self._current_layer = "meso"

        # 1. 读取微循环的注意信号
        micro_signals = self._drain("micro_to_meso")

        # 2. 主PSI循环
        if self.brain:
            self._total_cycles += 1

        # 3. 发送认知帧到宏循环
        self._inject("meso_to_macro", {
            "type": "cognitive_frame",
            "cycle": self._total_cycles,
            "time": start,
            "signals_from_micro": len(micro_signals),
        })

        # 4. 每N帧发送到元循环
        if layer.cycles % 300 == 0:
            self._inject("meso_to_meta", {
                "type": "frame_batch",
                "count": layer.cycles,
                "time": start,
            })

        # 5. 读取来自宏/元的注入信号
        self._read_latest("macro_to_meso")
        self._read_latest("meta_to_meso")

    def _macro_loop(self):
        """宏循环 (2s) — 推理/规划"""
        while self._running:
            self._adaptive_tick("macro", self._macro_tick_body)

    def _macro_tick_body(self):
        """宏循环体"""
        start = time.time()
        frames = self._drain("meso_to_macro")
        if frames:
            pass
        self._inject("macro_to_meso", {
            "type": "planning_bias",
            "time": start,
            "frames_analyzed": len(frames),
        })

    def _meta_loop(self):
        """元循环 (30s) — 自我反思"""
        while self._running:
            self._adaptive_tick("meta", self._meta_tick_body)

    def _meta_tick_body(self):
        """元循环体"""
        start = time.time()
        frames = self._drain("meso_to_meta")
        if frames:
            logger.info(f"PSI-N+ [DSpark] meta: {len(frames)} frame batches analyzed")
            self._inject("meta_to_meso", {
                "type": "param_adjustment",
                "time": start,
                "batches_analyzed": len(frames),
            })

    def _hyper_loop(self):
        """超循环 (5min) — 梦境巩固"""
        while self._running:
            self._adaptive_tick("hyper", self._hyper_tick_body)

    def _hyper_tick_body(self):
        """超循环体"""
        start = time.time()
        if self.brain and hasattr(self.brain, 'archive'):
            total = self.brain.archive.total_exchanges()
            if total > 0:
                logger.info(f"PSI-N+ [DSpark] hyper: {total} exchanges, sampling...")
                self._inject("hyper_to_meso", {
                    "type": "skill_extracted",
                    "time": start,
                    "total_exchanges": total,
                })

    # ── 层间信号 (与原版一致) ──

    def _inject(self, queue_name: str, signal: Dict):
        if queue_name in self._signal_queues:
            self._signal_queues[queue_name].append(signal)

    def _drain(self, queue_name: str) -> List[Dict]:
        if queue_name in self._signal_queues:
            q = self._signal_queues[queue_name]
            items = list(q)
            q.clear()
            return items
        return []

    def _read_latest(self, queue_name: str) -> Optional[Dict]:
        if queue_name in self._signal_queues and self._signal_queues[queue_name]:
            return self._signal_queues[queue_name][-1]
        return None

    # ── 统计 (增强版) ──

    def stats(self) -> Dict[str, Any]:
        uptime = time.time() - self._start_time
        cycles_per_layer = {name: layer.cycles for name, layer in self.layers.items()}
        base = {
            "uptime": uptime,
            "uptime_str": f"{uptime/3600:.1f}h",
            "total_cycles": self._total_cycles,
            "current_layer": self._current_layer,
            "layers": cycles_per_layer,
            "layer_details": {
                name: {
                    "cycles": layer.cycles,
                    "period": f"{layer.period_s*1000:.0f}ms" if layer.period_s < 1 else f"{layer.period_s:.0f}s",
                    "errors": layer.errors,
                    "active": self._threads.get(name, None) is not None,
                    # 新增: DSpark 自适应调度信息
                    "skipped": layer.skipped,
                    "confidence": round(layer.last_confidence, 3),
                    "meaningful_rate": round(
                        layer.meaningful_outputs / max(1, layer.cycles), 3
                    ),
                    "last_signal_depth": layer.last_signal_depth,
                }
                for name, layer in self.layers.items()
            },
            "queue_sizes": {k: len(q) for k, q in self._signal_queues.items()},
        }

        # DSpark 自适应调度统计
        base["dspark_adaptive"] = {
            "load": self._load_tracker.stats(),
            "scheduler": self._controller.stats(),
            "temperature": round(self._confidence.temperature, 2),
            "total_decisions": len(self._adaptive_decisions),
        }

        return base

    def adaptive_log(self, n: int = 10) -> List[Dict]:
        """返回最近的n条自适应决策日志"""
        return self._adaptive_decisions[-n:]


# ═══════════════════════════════════════════════
# 快速自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("PSI-N+ [DSpark] Adaptive Scheduler 自测")
    print("=" * 60)

    sched = PSIN_Scheduler()

    # 验证组件独立运行
    print(f"\n初始负载: {sched._load_tracker.stats()}")
    print(f"Meso置信度 (空闲): {sched._confidence.estimate('meso', 0, 0.0, 5.0):.3f}")
    print(f"Meta置信度 (空闲): {sched._confidence.estimate('meta', 0, 0.0, 5.0):.3f}")

    # 模拟高负载
    print(f"\nMeso置信度 (负载0.8, 队列深0): {sched._confidence.estimate('meso', 0, 0.8, 5.0):.3f}")
    print(f"Meta置信度 (负载0.8, 队列深0): {sched._confidence.estimate('meta', 0, 0.8, 5.0):.3f}")
    print(f"Meta置信度 (负载0.8, 队列深3): {sched._confidence.estimate('meta', 3, 0.8, 5.0):.3f}")

    # 模拟校准
    sched._confidence.calibrate_from_data(
        [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05] * 5,
        [True, True, True, True, False, False, False, False, False, False] * 5
    )
    print(f"\n校准后温度: {sched._confidence.temperature:.2f}")

    # 启动调度器快速测试
    print("\n启动调度器 (3秒)...")
    sched.start()
    time.sleep(3.0)
    sched.stop()
    time.sleep(0.2)

    stats = sched.stats()
    print(f"\n运行 {stats['uptime_str']}")
    for name, det in stats['layer_details'].items():
        print(f"  {name:6s}: {det['cycles']:4d} ticks | "
              f"{det['skipped']:4d} skipped | "
              f"conf={det['confidence']:.2f} | "
              f"load={stats['dspark_adaptive']['load']['load_factor']}")
    print(f"\n调度器跳过率: {stats['dspark_adaptive']['scheduler']['skip_rate']:.1%}")
    print(f"校准温度: {stats['dspark_adaptive']['temperature']:.2f}")
    print("\n✅ PSI-N+ [DSpark] 自适应调度器初始化验证通过")
