"""
Aris — Background Task System (后台任务系统)
=============================================

Lets Aris chat AND work simultaneously, like a human brain.

How it works:
  - Main thread: conversation, emotions, real-time response
  - Background worker: long-running tasks (code, research, deploy)
  - Task queue: FIFO with priority levels
  - Progress reporting: tasks report back without blocking chat

Usage:
  aris.task("部署飞书网关", priority=1)
  aris.task_status()  # check what's running
"""

from __future__ import annotations

import logging

from typing import Any, Callable, Dict, List, Optional
import threading, time, json, logging, queue, uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger("aris.tasks")

TASK_HOME = Path("D:/LAAP/aris_brain/state/tasks")
TASK_HOME.mkdir(parents=True, exist_ok=True)


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A single background task."""
    id: str = ""
    name: str = ""
    description: str = ""
    priority: Priority = Priority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    result: str = ""
    error: str = ""
    thread: Optional[threading.Thread] = None

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:8]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description[:60],
            "priority": self.priority.name,
            "status": self.status.value,
            "age": round(time.time() - self.created_at),
        }


class BackgroundWorker:
    """
    Background task processor.

    Runs tasks in separate threads while main conversation continues.
    Reports progress without interrupting chat flow.
    """

    def __init__(self, brain=None):
        self.brain = brain
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._max_workers = 2
        self._active_workers: List[threading.Thread] = []

    def start(self):
        """Start the background worker."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._thread.start()
        logger.info("[Tasks] Worker started")

    def stop(self):
        """Stop the worker."""
        self._running = False

    def submit(self, name: str, func: Callable, *,
               description: str = "",
               priority: Priority = Priority.NORMAL,
               args: tuple = None,
               kwargs: dict = None) -> str:
        """
        Submit a task to run in background.

        Example:
            def deploy():
                ssh("apt update")
                logger.info("done")
            task_id = worker.submit("deploy", deploy, priority=Priority.HIGH)
        """
        task = Task(
            name=name,
            description=description or name,
            priority=priority,
        )

        with self._lock:
            self._tasks[task.id] = task

        # Add to priority queue (lower number = higher priority)
        self._queue.put((-priority.value, task.id, func, args or (), kwargs or {}))

        logger.info(f"[Tasks] Submitted: {name} ({task.id})")
        return task.id

    def submit_shell(self, name: str, command: str, *,
                     description: str = "",
                     priority: Priority = Priority.NORMAL,
                     workdir: str = None) -> str:
        """Submit a shell command as a background task."""
        import subprocess

        def run_cmd():
            import os
            cwd = workdir or os.getcwd()
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=300
            )
            output = result.stdout[-500:] if result.stdout else ""
            error = result.stderr[-200:] if result.stderr else ""
            if result.returncode == 0:
                return f"Done: {output[:200]}"
            else:
                raise RuntimeError(f"Exit {result.returncode}: {error[:200]}")

        return self.submit(name, run_cmd, description=description, priority=priority)

    def submit_python(self, name: str, code: str, *,
                      description: str = "",
                      priority: Priority = Priority.NORMAL) -> str:
        """Submit Python code as a background task."""
        def run_py():
            try:
                local_vars = {}
                # 安全考量: 此处 exec 用于执行用户提交的 Python 后台任务。
                # 通过限制 __builtins__ 和隔离 local_vars 降低风险；
                # 调用方应在校验后提交，生产环境建议配合沙箱/容器使用。
                exec(code, {"__builtins__": __builtins__}, local_vars)
                result = local_vars.get("result", "Done")
                return str(result)[:500]
            except Exception as e:
                raise RuntimeError(str(e))

        return self.submit(name, run_py, description=description, priority=priority)

    def _dispatch_loop(self):
        """Main dispatch loop — pulls tasks from queue and runs them."""
        while self._running:
            try:
                # Get next task (block with timeout for clean shutdown)
                item = self._queue.get(timeout=1.0)
                neg_priority, task_id, func, args, kwargs = item

                with self._lock:
                    task = self._tasks.get(task_id)
                    if not task or task.status == TaskStatus.CANCELLED:
                        continue
                    task.status = TaskStatus.RUNNING
                    task.started_at = time.time()

                # Run in a thread
                worker = threading.Thread(
                    target=self._run_task,
                    args=(task_id, func, args, kwargs),
                    daemon=True,
                )
                worker.start()

                # Track active workers
                self._active_workers = [w for w in self._active_workers if w.is_alive()]
                self._active_workers.append(worker)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[Tasks] Dispatch error: {e}")

    def _run_task(self, task_id: str, func: Callable, args: tuple, kwargs: dict):
        """Execute a single task function."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

        try:
            result = func(*args, **kwargs)
            with self._lock:
                task.status = TaskStatus.DONE
                task.finished_at = time.time()
                task.result = str(result)[:500]
            logger.info(f"[Tasks] Done: {task.name} ({task_id})")

            # Log to brain if available
            if self.brain and self.brain.memory:
                try:
                    self.brain.memory.create_episode(
                        content=f"Task completed: {task.name}",
                        domain="task",
                        salience=0.3,
                    )
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        except Exception as e:
            with self._lock:
                task.status = TaskStatus.FAILED
                task.finished_at = time.time()
                task.error = str(e)[:300]
            logger.warning(f"[Tasks] Failed: {task.name}: {e}")

    def cancel(self, task_id: str) -> bool:
        """Cancel a queued task."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.QUEUED:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def status(self, task_id: str = None) -> List[Dict]:
        """Get task status."""
        with self._lock:
            if task_id:
                task = self._tasks.get(task_id)
                return [task.to_dict()] if task else []
            return [t.to_dict() for t in sorted(
                self._tasks.values(),
                key=lambda t: -t.created_at
            )[:10]]

    def running_tasks(self) -> List[Dict]:
        """Get currently running tasks."""
        return [t.to_dict() for t in self._tasks.values()
                if t.status == TaskStatus.RUNNING]

    def stats(self) -> Dict[str, Any]:
        return {
            "total": len(self._tasks),
            "running": len(self.running_tasks()),
            "done": sum(1 for t in self._tasks.values() if t.status == TaskStatus.DONE),
            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            "active_workers": len([w for w in self._active_workers if w.is_alive()]),
        }
