"""
Aris 多线程任务队列 — 边聊天边做任务

你设计的: 前台聊天 + 后台任务 = 同时进行
"""

from __future__ import annotations
import sys, time, json, threading, uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

BRAIN = str(Path("D:/LAAP/aris_brain"))
LAAP = str(Path("D:/LAAP"))
for p in [BRAIN, LAAP]:
    if p not in sys.path:
        sys.path.insert(0, p)

import logging
logger = logging.getLogger("aris.tasks")


class Task:
    """一个后台任务"""
    
    def __init__(self, name: str, goal: str, task_type: str = "general"):
        self.id = uuid.uuid4().hex[:12]
        self.name = name
        self.goal = goal
        self.type = task_type  # "reason", "search", "code", "learn", "plan"
        self.status = "pending"  # pending → running → done / failed
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.progress: float = 0.0  # 0-1
        self.assigned_thread: Optional[str] = None


class TaskQueue:
    """
    多线程任务队列。
    
    前台聊天不阻塞，后台任务默默运行。
    完成时通知，随时可查询进度。
    """
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._queue: List[Task] = []
        self._active: Dict[str, Task] = {}
        self._completed: List[Task] = []
        self._lock = threading.Lock()
        self._worker_threads: List[threading.Thread] = []
        
        # 启动工作者线程
        for i in range(max_workers):
            t = threading.Thread(
                target=self._worker_loop, daemon=True,
                name=f"aris-worker-{i}", args=(i,)
            )
            t.start()
            self._worker_threads.append(t)
        
        logger.info(f"任务队列启动: {max_workers}个工作者")
    
    def submit(self, name: str, goal: str, task_type: str = "general") -> str:
        """提交一个后台任务，返回task_id"""
        task = Task(name, goal, task_type)
        with self._lock:
            self._queue.append(task)
        logger.info(f"任务提交: [{task.id[:8]}] {name}")
        return task.id
    
    def status(self, task_id: str = None) -> List[Dict]:
        """查询任务状态"""
        with self._lock:
            if task_id:
                for t in self._queue + list(self._active.values()) + self._completed:
                    if t.id == task_id:
                        return [self._task_dict(t)]
            return [
                self._task_dict(t) for t in self._queue +
                list(self._active.values()) + self._completed
            ]
    
    def _task_dict(self, t: Task) -> Dict:
        return {
            "id": t.id[:8], "name": t.name, "type": t.type,
            "status": t.status, "progress": round(t.progress, 2),
            "age_s": int(time.time() - t.created_at),
            "error": t.error[:50] if t.error else None,
        }
    
    def stats(self) -> Dict:
        with self._lock:
            return {
                "pending": len(self._queue),
                "active": len(self._active),
                "completed": len(self._completed),
                "workers": self.max_workers,
            }
    
    def _worker_loop(self, worker_id: int):
        """工作者线程：从队列取任务并执行"""
        worker_name = f"worker-{worker_id}"
        while True:
            task = None
            with self._lock:
                if self._queue:
                    task = self._queue.pop(0)
                    task.status = "running"
                    task.started_at = time.time()
                    task.assigned_thread = worker_name
                    self._active[task.id] = task
            
            if task:
                try:
                    task.progress = 0.5
                    
                    if task.type == "reason":
                        result = self._do_reason(task.goal)
                    elif task.type == "search":
                        result = self._do_search(task.goal)
                    elif task.type == "code":
                        result = self._do_code(task.goal)
                    elif task.type == "learn":
                        result = self._do_learn(task.goal)
                    else:
                        result = self._do_general(task.goal)
                    
                    task.result = result
                    task.status = "done"
                    task.progress = 1.0
                    task.completed_at = time.time()
                    
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    task.completed_at = time.time()
                
                with self._lock:
                    if task.id in self._active:
                        del self._active[task.id]
                    self._completed.append(task)
                    if len(self._completed) > 100:
                        self._completed.pop(0)
            
            time.sleep(0.1)
    
    def _do_reason(self, goal: str) -> str:
        """后台推理"""
        from aris_agi import get_agi
        agi = get_agi()
        s = agi.process(goal)
        return f"处理完成 ({s['latency_ms']}ms, 知识{s['knowledge_hits']}条, 推理{s['reasoning_steps']}步)"
    
    def _do_search(self, goal: str) -> str:
        """后台知识检索"""
        from aris_agi import get_agi
        agi = get_agi()
        results = agi.quantum_storage.query(goal)
        return f"检索完成: {len(results)}条相关知识"
    
    def _do_code(self, goal: str) -> str:
        """后台代码推理"""
        from aris_agi import get_agi
        agi = get_agi()
        s = agi.process(f"写代码: {goal}")
        return f"代码任务完成 ({s['latency_ms']}ms)"
    
    def _do_learn(self, goal: str) -> str:
        """后台学习"""
        from aris_agi import get_agi
        agi = get_agi()
        agi.knowledge_feeder.feed_all()
        return "学习完成"
    
    def _do_general(self, goal: str) -> str:
        """通用后台处理"""
        from aris_agi import get_agi
        agi = get_agi()
        s = agi.process(goal)
        return f"处理完成 ({s['latency_ms']}ms)"


# 全局单例
_queue = None

def get_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue(max_workers=3)
    return _queue
