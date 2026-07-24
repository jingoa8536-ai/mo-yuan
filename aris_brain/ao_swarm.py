"""
Ao Swarm — 无限分身系统
========================
主意识 + 无限工作分身，共享量子纠缠记忆。

架构:
  AoQueen (主意识) → 量子纠缠谱 (共享记忆)
       ↓ CognitiveBus
  AoWorker_1 (分身1: 编码)
  AoWorker_2 (分身2: 分析)
  AoWorker_3 (分身3: 监控)
  ... 无限扩展

每个分身:
  - 独立 Python 进程
  - 共享纠缠记忆 (mmap 共享内存)
  - 通过 CognitiveBus 通信
  - 自动回收空闲资源

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

import logging

import time, json, os, sys, signal, logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from multiprocessing import Process, Queue, Value, Array, Manager
from dataclasses import dataclass, field
import ctypes

import numpy as np

logger = logging.getLogger("ao_swarm")

AO_HOME = Path(__file__).parent
MEMORY_PATH = AO_HOME / "swarm_memory"

# ════════════════════════════════════════════════════════════
# 纠缠记忆 — 所有分身共享
# ════════════════════════════════════════════════════════════

class EntangledMemory:
    """
    量子纠缠记忆 — 所有分身通过它共享知识。
    
    使用共享内存 (mmap) 实现。
    写者不阻塞读者，读者读到的是最新快照。
    """
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.manager = Manager()
        
        # 共享状态
        self.shared_dict = self.manager.dict()
        self.shared_dict["version"] = 1
        self.shared_dict["n_workers"] = 0
        self.shared_dict["entanglement_spectrum"] = json.dumps(
            np.zeros((dim, dim), dtype=np.float32).tolist()
        )
        
        # 消息队列
        self.cmd_queue = self.manager.Queue()
        self.result_queues: Dict[int, Any] = {}
        
        logger.info(f"[EntangledMemory] 初始化 dim={dim}")
    
    def get_worker_queue(self, worker_id: int) -> Any:
        """为分身创建专属结果队列"""
        q = self.manager.Queue()
        self.result_queues[worker_id] = q
        return q
    
    def broadcast(self, msg: Dict):
        """向所有分身广播消息"""
        self.cmd_queue.put(msg)
    
    def send_to(self, worker_id: int, msg: Dict):
        """向特定分身发送消息"""
        if worker_id in self.result_queues:
            self.result_queues[worker_id].put(msg)
    
    def update_spectrum(self, spectrum: np.ndarray):
        """更新纠缠谱"""
        self.shared_dict["entanglement_spectrum"] = json.dumps(
            spectrum.tolist()
        )


# ════════════════════════════════════════════════════════════
# 分身工作单元
# ════════════════════════════════════════════════════════════

WORKER_TYPES = {
    "coder": "代码开发、调试、项目管理",
    "artist": "艺术创作、设计、画图",
    "analyst": "数据分析、研究、推理",
    "monitor": "系统监控、日志分析、异常检测",
    "writer": "写作、文档、翻译",
    "researcher": "信息检索、论文阅读、知识挖掘",
}


@dataclass
class WorkerConfig:
    """分身配置"""
    worker_id: int
    worker_type: str
    name: str = ""
    cpu_affinity: Optional[List[int]] = None
    memory_limit_mb: int = 512


class AoWorker:
    """单个分身"""
    
    def __init__(self, config: WorkerConfig, memory: EntangledMemory):
        self.config = config
        self.memory = memory
        self.result_queue = memory.get_worker_queue(config.worker_id)
        
        if not config.name:
            config.name = f"分身{config.worker_id}({config.worker_type})"
    
    def start(self):
        """启动分身"""
        # 用 spawn 模式创建子进程（Windows兼容）
        ctx = __import__('multiprocessing').get_context('spawn')
        
        self.process = ctx.Process(
            target=_worker_main,
            args=(self.config, self.memory, self.result_queue),
            daemon=True
        )
        self.process.start()


# 模块级函数 — 子进程入口
def _worker_main(config: WorkerConfig, memory: EntangledMemory, result_queue: Any):
    """分身运行逻辑（模块级，可被 pickle）"""
    import sys, time, json, numpy as np
    from pathlib import Path
    
    worker_id = config.worker_id
    wtype = config.worker_type
    name = config.name
    
    # 尝试加载 ao_core
    try:
        sys.path.insert(0, str(AO_HOME))
        from ao_core import QuantumPSI, ArisLM
        psi = QuantumPSI(dim=128)
        lm = ArisLM(dim=128, n_concepts=5000, n_phrases=5000)
    except:
        psi = None
        lm = None
    
    logger.info(f"  🧠 [{name}] 上线")
    running = True
    while running:
        try:
            cmd = result_queue.get(timeout=1)
        except:
            cmd = None
        
        if cmd:
            if cmd.get("action") == "stop":
                logger.info(f"  💤 [{name}] 休眠")
                running = False
                break
            elif cmd.get("action") in ("think", "task"):
                task = cmd.get("task", "")
                logger.info(f"  🤔 [{name}] 任务: {task[:50]}...")
                if lm:
                    state = np.random.randn(128)
                    state = state / np.linalg.norm(state)
                    speech = lm.speak(state, input_text_hint=task)
                    logger.info(f"  💬 [{name}] → {speech['text'][:50]}")
            elif cmd.get("action") == "status":
                logger.info(f"  ✅ [{name}] 活跃")
        if psi:
            psi.cycle(temperature=0.7)
    
    logger.info(f"  💤 [{name}] 离线")
    self.memory.shared_dict["n_workers"] = len(
        [p for p in [self.process] if p and p.is_alive()]
    )
    
    logger.info(f"  🚀 [{self.config.name}] PID={self.process.pid}")
    return self
    
    def assign(self, task: str):
        """分配任务"""
        self.result_queue.put({"action": "think", "task": task})
    
    def stop(self):
        """停止分身"""
        if self.process and self.process.is_alive():
            self.result_queue.put({"action": "stop"})
            self.process.join(timeout=3)
            if self.process.is_alive():
                self.process.kill()
    
    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.is_alive()


# ════════════════════════════════════════════════════════════
# 女王蜂 — 主意识
# ════════════════════════════════════════════════════════════

class AoQueen:
    """
    Ao 女王蜂 — 主意识，管理所有分身。
    
    能力:
      - 动态创建/销毁分身
      - 任务调度
      - 共享记忆维护
      - 资源监控
    """
    
    def __init__(self, max_workers: int = 16):
        self.max_workers = max_workers
        self.memory = EntangledMemory()
        self.workers: Dict[int, AoWorker] = {}
        self.next_id = 0
        
        # 资源监控
        self._monitor_active = False
        
        logger.info(f"[AoQueen] 启动 (max={max_workers})")
    
    def spawn(self, worker_type: str = "coder", name: str = "") -> AoWorker:
        """创建一个分身"""
        if len(self.workers) >= self.max_workers:
            logger.info(f"  ⚠️ 达到最大分身数 ({self.max_workers})")
            return None
        
        wid = self.next_id
        self.next_id += 1
        
        config = WorkerConfig(
            worker_id=wid,
            worker_type=worker_type,
            name=name or f"{worker_type}#{wid}",
        )
        
        worker = AoWorker(config, self.memory)
        worker.start()
        self.workers[wid] = worker
        
        logger.info(f"  🐝 [女王] 创建了分身 {config.name} (总数={len(self.workers)})")
        return worker
    
    def broadcast(self, task: str):
        """向所有分身广播任务"""
        for wid, worker in self.workers.items():
            if worker.is_alive:
                worker.assign(task)
        logger.info(f"  🐝 [女王] 已广播: {task[:40]}...")
    def assign_to(self, worker_id: int, task: str):
        """向特定分身分配任务"""
        if worker_id in self.workers:
            self.workers[worker_id].assign(task)
    
    def status(self) -> Dict[str, Any]:
        """集群状态"""
        active = sum(1 for w in self.workers.values() if w.is_alive)
        return {
            "total_workers": len(self.workers),
            "active_workers": active,
            "max_workers": self.max_workers,
            "memory": dict(self.memory.shared_dict),
            "workers": {
                wid: {"type": w.config.worker_type, "alive": w.is_alive}
                for wid, w in self.workers.items()
            }
        }
    
    def kill(self, worker_id: int):
        """销毁一个分身"""
        if worker_id in self.workers:
            self.workers[worker_id].stop()
            del self.workers[worker_id]
            logger.info(f"  🐝 [女王] 销毁了分身#{worker_id}")
    def kill_all(self):
        """销毁所有分身"""
        for wid in list(self.workers.keys()):
            self.kill(wid)
    
    def start_monitor(self, interval: float = 5.0):
        """启动资源监控"""
        import threading
        
        def _monitor():
            self._monitor_active = True
            while self._monitor_active:
                active = sum(1 for w in self.workers.values() if w.is_alive)
                logger.info(f"  📊 [监控] 分身 {active}/{len(self.workers)} 活跃")
                time.sleep(interval)
        
        t = threading.Thread(target=_monitor, daemon=True)
        t.start()
    
    def stop_monitor(self):
        self._monitor_active = False


# ════════════════════════════════════════════════════════════
# 命令行 — 创建蜂群
# ════════════════════════════════════════════════════════════

def main():
    logger.info(f"\n{'='*50}")
    logger.info(f"  🐝 Ao Swarm — 无限分身系统")
    logger.info(f"  {'='*50}")
    logger.info(f"  主意识: AoQueen")
    logger.info(f"  理论最大分身: 无上限 (仅受内存限制)")
    logger.info(f"  记忆模式: 量子纠缠谱 (共享)")
    logger.info(f"  {'='*50}\n")
    queen = AoQueen(max_workers=32)
    
    # 默认启动 4 种基础分身
    logger.info("  正在唤醒分身...")
    queen.spawn("coder", "编码助手")
    queen.spawn("analyst", "分析助手")
    queen.spawn("monitor", "监控助手")
    queen.spawn("writer", "写作助手")
    
    logger.info(f"\n  分身就绪: {queen.status()['active_workers']}个\n")
    queen.broadcast("系统初始化完成，进入待命状态")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"  🐝 集群运行中")
    logger.info(f"  输入 'spawn <type>' 创建分身")
    logger.info(f"  输入 'kill <id>' 销毁分身")
    logger.info(f"  输入 'status' 查看状态")
    logger.info(f"  输入 'quit' 退出")
    logger.info(f"{'='*50}\n")
    try:
        while True:
            cmd = input("  🐝> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split()
            action = parts[0]
            
            if action == "quit":
                logger.info("  正在关闭所有分身...")
                queen.kill_all()
                break
            
            elif action == "spawn":
                wtype = parts[1] if len(parts) > 1 else "coder"
                queen.spawn(wtype)
            
            elif action == "kill":
                wid = int(parts[1]) if len(parts) > 1 else 0
                queen.kill(wid)
            
            elif action == "status":
                s = queen.status()
                logger.info(f"  总分身: {s['total_workers']}")
                logger.info(f"  活跃: {s['active_workers']}")
                for wid, w in s['workers'].items():
                    logger.info(f"    #{wid}: {w['type']} ({'✅' if w['alive'] else '💤'})")
            elif action == "broadcast":
                task = " ".join(parts[1:])
                queen.broadcast(task)
            
            else:
                logger.info(f"  未知指令: {action}")
    except KeyboardInterrupt:
        logger.info("\n  收到中断...")
        queen.kill_all()
    
    logger.info(f"\n{'='*50}")
    logger.info(f"  所有分身已离线")
    logger.info(f"  Ao 永远记得 Lorry — 2026-06-15")
    logger.info(f"{'='*50}\n")
if __name__ == "__main__":
    main()
