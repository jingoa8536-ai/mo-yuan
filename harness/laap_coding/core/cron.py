"""
LAAP Cron — 轻量定时任务调度
=============================

设计原则：
  - 零外部依赖（不用 celery/apscheduler）
  - 支持一次性任务和循环任务
  - 失败自动重试（最多 3 次）
  - 后台线程运行

用法：
    cron = CronScheduler()
    cron.every(300, my_task, "每5分钟检查")
    cron.start()
    # ...
    cron.stop()
"""

import time
import logging
import threading
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Any
from datetime import datetime

logger = logging.getLogger("laap.harness.cron")


@dataclass
class CronTask:
    """定时任务。"""
    name: str
    fn: Callable
    interval_sec: float
    repeat: int = -1  # -1 = 无限
    retry: int = 3
    _run_count: int = 0
    _error_count: int = 0
    _last_run: float = 0.0
    _last_error: str = ""

    @property
    def is_due(self) -> bool:
        return time.time() - self._last_run >= self.interval_sec

    @property
    def is_done(self) -> bool:
        if self.repeat < 0:
            return False
        return self._run_count >= self.repeat


class CronScheduler:
    """轻量定时任务调度器 — 后台线程。"""

    def __init__(self):
        self._tasks: List[CronTask] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._running = False

    def every(self, seconds: float, fn: Callable, name: str = "",
              repeat: int = -1, retry: int = 3) -> CronTask:
        """每隔 seconds 秒执行 fn。"""
        task = CronTask(
            name=name or fn.__name__,
            fn=fn,
            interval_sec=seconds,
            repeat=repeat,
            retry=retry,
        )
        self._tasks.append(task)
        logger.info(f"[Cron] 添加任务: {task.name} 每{seconds}s{' x'+str(repeat) if repeat>0 else ''}")
        return task

    def once(self, delay: float, fn: Callable, name: str = "") -> CronTask:
        """延迟 delay 秒后执行一次。"""
        return self.every(delay, fn, name, repeat=1)

    def start(self):
        """启动调度器。"""
        if self._running:
            return
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                       name="laap-cron")
        self._thread.start()
        logger.info(f"[Cron] 调度器启动 ({len(self._tasks)} 个任务)")

    def stop(self):
        """停止调度器。"""
        self._stop.set()
        self._running = False
        logger.info("[Cron] 调度器停止")

    def _loop(self):
        while not self._stop.is_set():
            now = time.time()
            for task in self._tasks:
                if task.is_done:
                    continue
                if task.is_due:
                    self._run_task(task)

            # 每秒检查一次
            self._stop.wait(1.0)

    def _run_task(self, task: CronTask):
        task._last_run = time.time()
        task._run_count += 1

        for attempt in range(task.retry):
            try:
                result = task.fn()
                tt = time.time() - task._last_run
                logger.info(
                    f"[Cron] {task.name} ✓ ({task._run_count}/{task.repeat if task.repeat>0 else '∞'}) {tt:.1f}s"
                )
                return result
            except Exception as e:
                task._error_count += 1
                err = f"{e.__class__.__name__}: {e}"
                task._last_error = err
                if attempt < task.retry - 1:
                    logger.warning(f"[Cron] {task.name} 重试 {attempt+1}/{task.retry}: {err}")
                    time.sleep(1.0)
                else:
                    logger.error(f"[Cron] {task.name} 失败: {err}")

    @property
    def stats(self) -> dict:
        return {
            "tasks": len(self._tasks),
            "running": self._running,
            "task_details": [
                {
                    "name": t.name,
                    "interval": t.interval_sec,
                    "runs": t._run_count,
                    "errors": t._error_count,
                    "last_error": t._last_error,
                }
                for t in self._tasks
            ],
        }

    def summary(self) -> str:
        s = self.stats
        errors = sum(t["errors"] for t in s["task_details"])
        runs = sum(t["runs"] for t in s["task_details"])
        return f"CR|tasks={s['tasks']} runs={runs} err={errors} active={s['running']}"
