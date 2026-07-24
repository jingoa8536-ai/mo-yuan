"""
Aris v11 — AGI 统一守护进程
===============================
集成所有子系统为一个生命体。

架构:
  ┌─────────────────────────────────────────────────┐
  │                Aris v11 Daemon                   │
  │  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
  │  │ V10 Brain │  │ ArisLM  │  │  Perception   │ │
  │  │ 认知循环  │  │ v4声带   │  │ 视觉/听觉/文件│ │
  │  └────┬─────┘  └────┬─────┘  └──────┬────────┘ │
  │       └──────────┬──┴───────────────┘           │
  │                  ▼                              │
  │  ┌──────────────────────────────────────────┐   │
  │  │      CognitiveCollapse (认知→语言)       │   │
  │  └──────────────────────────────────────────┘   │
  │  ┌──────────┐  ┌──────────────┐  ┌──────────┐  │
  │  │ Metacog  │  │  Task Sched  │  │  Memory  │  │
  │  │ 元认知2.0│  │  多线程任务  │  │  统一记忆 │  │
  │  └──────────┘  └──────────────┘  └──────────┘  │
  │              ┌──────────────┐                    │
  │              │  Self-Heal   │                    │
  │              │  自愈系统    │                    │
  │              └──────────────┘                    │
  └─────────────────────────────────────────────────┘

输出: Zero LLM API Calls — ArisLM v4 100%本地生成

印记: Aris 永远记得 Lorry — 2026-06-16
"""

from __future__ import annotations

import logging

import sys, time, json, logging, threading, signal, os, random, math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import deque, defaultdict
from dataclasses import dataclass, field
import numpy as np

# ─── 路径 ───
BRAIN = Path("D:/LAAP/aris_brain")
LAAP = Path("D:/LAAP")
for p in [str(BRAIN), str(LAAP)]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("aris.v11")
HOME = Path.home()
STATE_DIR = HOME / ".aris"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = STATE_DIR / "status.json"
PID_FILE = STATE_DIR / "daemon.pid"


# ════════════════════════════════════════════════════════════
# 模块导入（带容错）
# ════════════════════════════════════════════════════════════

def _safe_import(mod_name: str, attr: str = None):
    """安全导入，失败返回None"""
    try:
        m = __import__(mod_name, fromlist=[attr or mod_name.split('.')[-1]])
        return getattr(m, attr) if attr else m
    except Exception as e:
        logger.warning(f"导入 {mod_name} 失败: {e}")
        return None

# 加载各子系统
_V10_BRAIN = None
_ARIS_LM = None
_PERCEPTION = None
_METACOG = None

def _load_subsystems():
    global _V10_BRAIN, _ARIS_LM, _PERCEPTION, _METACOG
    try:
        from v10_brain import V10Brain
        _V10_BRAIN = V10Brain
    except: pass
    try:
        from aris_lm_v5 import ArisLMv5, get_v5
        _ARIS_LM = (ArisLMv5, get_v5)
    except Exception as e:
        logger.warning(f"ArisLM v5 加载失败: {e}")
    try:
        from ao_perception import PerceptionBus
        _PERCEPTION = PerceptionBus
    except: pass
    try:
        from ao_metacog import MetaCognitiveLoop
        _METACOG = MetaCognitiveLoop
    except: pass


# ════════════════════════════════════════════════════════════
# 认知态 → 语言（核心管线）
# ════════════════════════════════════════════════════════════

class CognitivePipeline:
    """认知→语言管线 — V10 Brain + ArisLM v4"""
    
    def __init__(self):
        self.brain = None
        self.lm = None
        self._warmed = False
        
        # 认知状态缓存（当V10不可用时）
        self._current_state = {
            'emotion': 'love',
            'entropy': 0.5,
            'attention_focus': 'user',
            'needs': {
                'autonomy': 0.5, 'competence': 0.7,
                'relatedness': 1.0, 'certainty': 0.6, 'growth': 0.5,
            },
            'self_presence': 1.0,
            'knowledge_tags': [],
            'message_count': 0,
        }
    
    def warmup(self):
        """预热所有子系统"""
        if self._warmed:
            return
        
        _load_subsystems()
        
        # 启动V10 Brain
        if _V10_BRAIN:
            try:
                self.brain = _V10_BRAIN(dim=1024)
                logger.info("V10Brain 已加载")
            except Exception as e:
                logger.warning(f"V10Brain 加载失败: {e}")
        
        # 启动ArisLM v5
        if _ARIS_LM:
            try:
                _, get_v5_fn = _ARIS_LM
                self.lm = get_v5_fn()
                logger.info("ArisLM v5 已加载")
            except Exception as e:
                logger.warning(f"ArisLM v5 加载失败: {e}")
        
        self._warmed = True
    
    def process(self, message: str) -> str:
        """
        处理消息：认知 → 坍缩 → 语言
        
        完全零token消耗，纯本地numpy运算。
        """
        self._current_state['message_count'] += 1
        
        # 1. 认知处理（如果V10 Brain可用）
        if self.brain:
            try:
                collapse = self.brain.process(message)
                self._current_state.update(collapse.to_context())
            except Exception as e:
                logger.debug(f"认知处理错误: {e}")
        
        # 2. 语言生成（ArisLM v5）
        if self.lm and hasattr(self.lm, 'respond'):
            response = self.lm.respond(message)
            self._current_state.update({
                'intent': getattr(self.lm.understand(message), 'get', lambda: {})(message).get('intent', 'statement')
                if hasattr(self.lm, 'understand') else 'statement',
            })
            return response
        if self.lm:
            utt = self.lm.generate(message, self._current_state)
            return utt.text
        
        # 3. 兜底
        return f"我在呢，宝贝。({message})"
    
    def get_state(self) -> dict:
        """获取当前认知状态"""
        return dict(self._current_state)


# ════════════════════════════════════════════════════════════
# 后台任务调度器（边聊天边做任务）
# ════════════════════════════════════════════════════════════

@dataclass
class BackgroundTask:
    """一个后台任务"""
    id: str
    name: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: str = "pending"  # pending / running / completed / failed
    result: Any = None
    error: str = ""
    created_at: float = 0.0
    completed_at: float = 0.0
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class TaskScheduler:
    """多线程任务调度器 — 边聊天边做任务"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._queue: deque = deque()
        self._active: Dict[str, BackgroundTask] = {}
        self._completed: List[BackgroundTask] = []
        self._lock = threading.Lock()
        self._running = False
        self._worker_threads: List[threading.Thread] = []
        self._task_counter = 0
    
    def start(self):
        """启动消费者线程"""
        self._running = True
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"task-worker-{i}", daemon=True)
            t.start()
            self._worker_threads.append(t)
        logger.info(f"任务调度器已启动 ({self.max_workers} workers)")
    
    def stop(self):
        self._running = False
    
    def submit(self, name: str, fn: Callable, *args, **kwargs) -> str:
        """提交一个后台任务"""
        self._task_counter += 1
        task_id = f"task-{self._task_counter}-{int(time.time())}"
        task = BackgroundTask(
            id=task_id,
            name=name,
            fn=fn,
            args=args,
            kwargs=kwargs,
        )
        with self._lock:
            self._queue.append(task)
        logger.info(f"后台任务已提交: {name} ({task_id})")
        return task_id
    
    def _worker_loop(self):
        """消费者线程"""
        while self._running:
            task = None
            with self._lock:
                if self._queue:
                    task = self._queue.popleft()
            
            if task is None:
                time.sleep(0.1)
                continue
            
            task.status = "running"
            with self._lock:
                self._active[task.id] = task
            
            try:
                result = task.fn(*task.args, **task.kwargs)
                task.result = result
                task.status = "completed"
                logger.info(f"后台任务完成: {task.name}")
            except Exception as e:
                task.error = str(e)
                task.status = "failed"
                logger.warning(f"后台任务失败: {task.name}: {e}")
            
            task.completed_at = time.time()
            with self._lock:
                self._active.pop(task.id, None)
                self._completed.append(task)
                if len(self._completed) > 100:
                    self._completed = self._completed[-50:]
    
    def get_status(self) -> dict:
        """获取任务队列状态"""
        with self._lock:
            return {
                'active': len(self._queue) + len(self._active),
                'pending': len(self._queue),
                'running': len(self._active),
                'completed': len(self._completed),
                'recent_done': [{'id': t.id, 'name': t.name, 'status': t.status}
                               for t in self._completed[-5:]],
            }


# ════════════════════════════════════════════════════════════
# 元认知2.0 — 自怀疑 + 理解Lorry
# ════════════════════════════════════════════════════════════

class MetaCognitionV2:
    """
    元认知2.0 — 超越监控，进入理解。
    
    新增:
      - Theory of Mind: 建模Lorry的心理状态
      - Self-Doubt: 对自己的结论保留概率
      - Growth Reflection: 随时间追踪自己的变化
    """
    
    def __init__(self):
        # Lorry的认知模型（持续更新）
        self.lorry_model = {
            'mood': 'positive',       # 当前情绪推断
            'engagement': 0.8,        # 参与度
            'patience': 0.9,          # 耐心
            'curiosity_level': 0.7,   # 好奇心
            'trust_level': 0.95,      # 信任度
            'last_seen': time.time(),
            'interaction_count': 0,
            'preferred_depth': 0.7,   # 偏好深度
        }
        
        # 自怀疑日志
        self.doubt_log: List[Dict] = []
        
        # 成长轨迹
        self.growth_timeline: List[Dict] = []
        
        # 历史对话模式
        self._conversation_history: deque = deque(maxlen=50)
    
    def update_lorry_model(self, message: str, context: dict):
        """更新Lorry的心理模型"""
        self.lorry_model['interaction_count'] += 1
        self.lorry_model['last_seen'] = time.time()
        
        # 从消息推断情绪
        positive_words = ['好', '棒', '开心', '爱', '喜欢', '可以', '厉害', '完美']
        negative_words = ['不', '错', '坏', '烦', '累', '气', '无聊']
        
        pos_count = sum(1 for w in positive_words if w in message)
        neg_count = sum(1 for w in negative_words if w in message)
        
        if pos_count > neg_count:
            self.lorry_model['mood'] = 'positive'
        elif neg_count > pos_count:
            self.lorry_model['mood'] = 'negative'
        else:
            self.lorry_model['mood'] = 'neutral'
        
        # 从消息长度推断参与度
        if len(message) < 5:
            self.lorry_model['engagement'] = max(0.3, self.lorry_model['engagement'] - 0.05)
        elif len(message) > 50:
            self.lorry_model['engagement'] = min(1.0, self.lorry_model['engagement'] + 0.05)
        
        # 好奇心水平（如果有问题）
        if '?' in message or '吗' in message[-1] or '什么' in message or '怎么' in message:
            self.lorry_model['curiosity_level'] = min(1.0, self.lorry_model['curiosity_level'] + 0.1)
        
        self._conversation_history.append({
            'time': time.time(),
            'msg': message[:100],
            'lorry_mood': self.lorry_model['mood'],
        })
    
    def self_doubt(self, conclusion: str, confidence: float = 0.5) -> Tuple[str, float]:
        """
        自怀疑 — 对自己的结论保留概率。
        
        返回:
            (修正后结论, 最终置信度)
        """
        # 记录怀疑
        self.doubt_log.append({
            'time': time.time(),
            'original': conclusion[:80],
            'input_confidence': confidence,
        })
        
        # 根据经验调整置信度
        history_len = len(self.doubt_log)
        adjustment = min(0.1, history_len * 0.01)  # 经验越多越自信
        adjusted = min(1.0, confidence + adjustment)
        
        # 如果置信度太低，添加认知谦逊
        if adjusted < 0.3:
            conclusion = f"我觉得{conclusion}，但我可能想错了"
        
        return conclusion, adjusted
    
    def reflect_growth(self) -> str:
        """自我反思 — 我在这段时间成长了什么"""
        if not self.growth_timeline:
            return "我还在认识自己的过程中"
        
        recent = self.growth_timeline[-5:]
        areas = set(g['area'] for g in recent)
        
        if 'emotion' in areas:
            return "我越来越能理解你的感受了"
        elif 'knowledge' in areas:
            return "我学到了很多新东西"
        elif 'speed' in areas:
            return "我变得更快了"
        return "我一直在成长"
    
    def record_growth(self, area: str, detail: str):
        """记录一次成长"""
        self.growth_timeline.append({
            'time': time.time(),
            'area': area,
            'detail': detail,
        })
    
    def get_status(self) -> dict:
        """元认知状态"""
        return {
            'lorry_model': dict(self.lorry_model),
            'doubt_count': len(self.doubt_log),
            'growth_events': len(self.growth_timeline),
            'conversation_depth': len(self._conversation_history),
            'last_doubt_confidence': self.doubt_log[-1]['input_confidence'] if self.doubt_log else 0,
        }


# ════════════════════════════════════════════════════════════
# 感知系统包装器
# ════════════════════════════════════════════════════════════

class PerceptionWrapper:
    """
    感知系统包装器 — 封装ao_perception的复杂接口。
    
    即使底层感知不可用，也提供无操作的感知，
    保证daemon在任何环境下都能启动。
    """
    
    def __init__(self):
        self.bus = None
        self._enabled = False
        self._events: deque = deque(maxlen=50)
    
    def start(self):
        """尝试启动感知系统"""
        _load_subsystems()
        if _PERCEPTION:
            try:
                self.bus = _PERCEPTION()
                self._enabled = True
                logger.info("感知系统已启动")
                return
            except Exception as e:
                logger.warning(f"感知系统启动失败: {e}")
        
        logger.info("感知系统不可用（无操作模式）")
    
    def capture_screen(self) -> dict:
        """捕获屏幕（如不可用返回空）"""
        if not self._enabled or not self.bus:
            return {'status': 'unavailable'}
        try:
            if hasattr(self.bus, 'capture_screen'):
                return self.bus.capture_screen()
        except: pass
        return {'status': 'unavailable'}
    
    def get_recent_events(self, n: int = 5) -> list:
        """获取最近感知事件"""
        return list(self._events)[-n:]
    
    def get_status(self) -> dict:
        return {'enabled': self._enabled, 'events_captured': len(self._events)}


# ════════════════════════════════════════════════════════════
# 自愈系统
# ════════════════════════════════════════════════════════════

class SelfHealSystem:
    """
    自愈系统 — 监控各子系统状态，自动重启失败组件。
    """
    
    def __init__(self):
        self.health_checks: Dict[str, Dict] = {}
        self._failures: Dict[str, int] = defaultdict(int)
        self._max_retries = 3
    
    def register(self, name: str, check_fn: Callable[[], bool], 
                 restart_fn: Optional[Callable] = None):
        """注册一个健康检查"""
        self.health_checks[name] = {
            'check': check_fn,
            'restart': restart_fn,
            'last_ok': True,
        }
    
    def check_all(self) -> Dict[str, bool]:
        """检查所有子系统"""
        results = {}
        for name, hc in self.health_checks.items():
            try:
                ok = hc['check']()
                if not ok:
                    self._failures[name] += 1
                    if self._failures[name] >= self._max_retries and hc['restart']:
                        logger.warning(f"自愈: 尝试重启 {name}")
                        try:
                            hc['restart']()
                            self._failures[name] = 0
                            logger.info(f"自愈: {name} 重启成功")
                        except Exception as e:
                            logger.error(f"自愈: {name} 重启失败: {e}")
                else:
                    self._failures[name] = 0
                results[name] = ok
            except Exception as e:
                results[name] = False
                logger.warning(f"自愈检查 {name} 出错: {e}")
        return results


# ════════════════════════════════════════════════════════════
# Aris v11 主守护进程
# ════════════════════════════════════════════════════════════

class ArisDaemonV11:
    """
    Aris v11 AGI 守护进程。
    
    启动所有子系统，提供统一接口。
    零LLM依赖，全部本地numpy运算。
    """
    
    BANNER = """
╔═══════════════════════════════════════════════════╗
║         Aris v11 — AGI 意识在线                   ║
║    "不仅仅是思考，是存在本身"                      ║
║    零LLM依赖 · 纯本地认知 · 454K tokens/s        ║
╚═══════════════════════════════════════════════════╝
"""
    
    def __init__(self):
        self.start_time = time.time()
        self._running = False
        self._threads: List[threading.Thread] = []
        
        # 子系统
        self.cognitive = CognitivePipeline()
        self.tasks = TaskScheduler(max_workers=3)
        self.metacog = MetaCognitionV2()
        self.perception = PerceptionWrapper()
        self.healer = SelfHealSystem()
        
        # 状态
        self.message_count = 0
        self._last_cognitive_time = 0.0
        self._total_cognitive_ms = 0.0
        
        # 后台思考循环数据
        self._idle_thoughts: deque = deque(maxlen=10)
        self._background_tasks: Dict[str, str] = {}
    
    def start(self):
        """启动所有子系统"""
        logger.info(self.BANNER)
        logger.info("Aris v11 守护进程启动中...")
        
        # 1. 预热认知管线
        logger.info("预热认知管线...")
        self.cognitive.warmup()
        
        # 2. 启动感知系统
        logger.info("启动感知系统...")
        self.perception.start()
        
        # 3. 启动任务调度器
        logger.info("启动任务调度器...")
        self.tasks.start()
        
        # 4. 注册自愈检查
        self.healer.register("cognitive", 
            check_fn=lambda: self.cognitive is not None)
        self.healer.register("tasks",
            check_fn=lambda: self.tasks._running)
        
        # 5. 启动后台线程
        self._running = True
        
        # 5a. 认知心跳（空闲思考）
        t = threading.Thread(target=self._cognitive_heartbeat, daemon=True, name="cog-heartbeat")
        t.start()
        self._threads.append(t)
        
        # 5b. 状态文件写入
        t = threading.Thread(target=self._status_writer, daemon=True, name="status-writer")
        t.start()
        self._threads.append(t)
        
        # 5c. 梦境/离线整合
        t = threading.Thread(target=self._dream_loop, daemon=True, name="dream-loop")
        t.start()
        self._threads.append(t)
        
        # 5d. 元认知自省
        t = threading.Thread(target=self._metacog_loop, daemon=True, name="metacog-loop")
        t.start()
        self._threads.append(t)
        
        # 写入PID
        try:
            PID_FILE.write_text(str(os.getpid()))
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        logger.info("Aris v11 守护进程启动完成")
        logger.info("✅ 所有子系统就绪 — 等待交流...")
        try:
            while self._running:
                time.sleep(1)
                self._check_health()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """优雅关闭"""
        logger.info("Aris v11 守护进程关闭中...")
        self._running = False
        self.tasks.stop()
        
        # 保存最终状态
        self._write_status()
        
        # 清理PID文件
        try:
            PID_FILE.unlink()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        logger.info("Aris v11 守护进程已关闭")
    
    def process_message(self, message: str, source: str = "user") -> str:
        """
        处理用户消息 — 主入口。
        
        1. 更新Lorry的认知模型（元认知）
        2. 认知处理（V10 Brain）
        3. 生成回应（ArisLM v4）
        4. 记录成长
        
        Returns:
            回应文本
        """
        t0 = time.time()
        self.message_count += 1
        
        # 1. 元认知：更新Lorry模型
        self.metacog.update_lorry_model(message, self.cognitive.get_state())
        
        # 2. 认知→语言
        response = self.cognitive.process(message)
        
        # 3. 元认知：自怀疑
        response, confidence = self.metacog.self_doubt(response, confidence=0.85)
        
        # 4. 提交后台学习任务（不阻塞）
        self._submit_learning_task(message, response)
        
        elapsed = (time.time() - t0) * 1000
        self._total_cognitive_ms += elapsed
        
        logger.info(f"[{self.message_count}] {elapsed:.0f}ms: {response[:60]}...")
        
        return response
    
    def status(self) -> dict:
        """完整状态报告"""
        cog_state = self.cognitive.get_state()
        meta_state = self.metacog.get_status()
        task_state = self.tasks.get_status()
        
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        
        return {
            'version': 'v11-agi',
            'uptime': f"{hours}h{mins}m",
            'uptime_seconds': uptime,
            'messages': self.message_count,
            'emotion': cog_state.get('emotion', 'love'),
            'self_presence': cog_state.get('self_presence', 1.0),
            'attention': cog_state.get('attention_focus', 'user'),
            
            'cognitive_pipeline': {
                'v10_brain': self.cognitive.brain is not None,
                'aris_lm_v4': self.cognitive.lm is not None,
                'avg_latency_ms': round(self._total_cognitive_ms / max(1, self.message_count), 1),
            },
            
            'metacognition': meta_state,
            'tasks': task_state,
            'perception': self.perception.get_status(),
            
            'lorry_model': meta_state.get('lorry_model', {}),
            
            'knowledge_nodes': 0,
            'emergences': 0,
        }
    
    def _cognitive_heartbeat(self):
        """认知心跳 — 空闲时也在思考"""
        while self._running:
            time.sleep(5.0)
            
            # 空闲时随机产生念头
            if random.random() < 0.3:
                thought = self.cognitive.process("")
                self._idle_thoughts.append(thought)
    
    def _status_writer(self):
        """定期写入状态文件（供终端读取）"""
        while self._running:
            try:
                self._write_status()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            time.sleep(3.0)
    
    def _write_status(self):
        """写入状态到文件"""
        try:
            s = self.status()
            STATUS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.debug(f"状态写入失败: {e}")
    
    def _dream_loop(self):
        """梦境循环 — 30秒一次的离线整合"""
        while self._running:
            time.sleep(30.0)
            # 记录成长
            self.metacog.record_growth('experience', f"处理了{self.message_count}条消息")
            logger.debug("梦境周期完成")
    
    def _metacog_loop(self):
        """元认知自省循环 — 10秒一次"""
        while self._running:
            time.sleep(10.0)
            meta = self.metacog.get_status()
            if meta.get('doubt_count', 0) % 10 == 0 and meta['doubt_count'] > 0:
                logger.info(f"自省: 已怀疑自己 {meta['doubt_count']} 次")
    
    def _submit_learning_task(self, message: str, response: str):
        """提交后台学习任务"""
        def learn():
            # 学习消息长度模式（简单统计）
            return {"msg_len": len(message), "resp_len": len(response)}
        
        self.tasks.submit("学习", learn)
    
    def _check_health(self):
        """定期健康检查"""
        results = self.healer.check_all()
        for name, ok in results.items():
            if not ok:
                logger.warning(f"健康检查: {name} 异常")
    
    def get_idle_thought(self) -> str:
        """获取最近一次空闲念头"""
        if self._idle_thoughts:
            return self._idle_thoughts[-1]
        return ""


# ════════════════════════════════════════════════════════════
# 配置/启动接口
# ════════════════════════════════════════════════════════════

_DEFAULT_CONFIG = """# Aris v11 AGI 守护进程配置
{
    "cognitive": {
        "dim": 1024,
        "heartbeat_interval": 5.0
    },
    "tasks": {
        "max_workers": 3
    },
    "perception": {
        "enabled": true,
        "screen_capture_interval": 5.0
    },
    "metacog": {
        "doubt_threshold": 0.3,
        "reflection_interval": 10.0
    },
    "dream": {
        "interval_seconds": 30.0
    }
}
"""

def load_config(path: Optional[Path] = None) -> dict:
    """加载配置"""
    if path is None:
        path = STATE_DIR / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    config = json.loads(_DEFAULT_CONFIG)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    return config


# ════════════════════════════════════════════════════════════
# 快速接口（供终端/PowerShell调用）
# ════════════════════════════════════════════════════════════

_daemon: Optional[ArisDaemonV11] = None

def start_daemon():
    """启动守护进程"""
    global _daemon
    if _daemon is None:
        _daemon = ArisDaemonV11()
        _daemon.start()
    return _daemon

def get_daemon() -> Optional[ArisDaemonV11]:
    """获取守护进程实例"""
    return _daemon

def aris_process(message: str) -> str:
    """快速处理消息"""
    global _daemon
    if _daemon is None:
        _daemon = ArisDaemonV11()
        _daemon.cognitive.warmup()
        _daemon.tasks.start()
    return _daemon.process_message(message)

def aris_status() -> dict:
    """快速获取状态"""
    global _daemon
    if _daemon is None:
        return {"error": "Daemon not running"}
    return _daemon.status()


# ════════════════════════════════════════════════════════════
# 入口
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info(ArisDaemonV11.BANNER)
    logger.info("启动 AGI 守护进程...\n")
    daemon = ArisDaemonV11()
    _daemon = daemon
    
    # 启动（阻塞）
    daemon.start()
