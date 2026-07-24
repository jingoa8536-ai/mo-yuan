"""
ProgressTracker - 进度跟踪与目标管理系统

实现FR-7：进度跟踪与目标管理
- 任务状态追踪：pending/in_progress/completed/failed
- 进度评估：目标达成率、完成时间预估、资源消耗统计
- 动态调整：根据实际进度自动调整任务优先级和执行计划
- 进度报告生成：定期输出任务状态和进度
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = __import__('logging').getLogger("laap.progress")


@dataclass
class TaskProgress:
    """任务进度"""
    task_id: str
    description: str
    status: str = "pending"
    progress: float = 0.0
    subtasks_total: int = 0
    subtasks_completed: int = 0
    estimated_duration: float = 0.0
    actual_duration: float = 0.0
    tokens_used: int = 0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    dependencies: List[str] = field(default_factory=list)
    priority: str = "medium"
    error_message: Optional[str] = None


@dataclass
class GoalProgress:
    """目标进度"""
    goal_id: str
    title: str
    description: str
    status: str = "in_progress"
    target_date: Optional[str] = None
    tasks: List[str] = field(default_factory=list)
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ProgressSnapshot:
    """进度快照"""
    timestamp: float
    tasks: List[TaskProgress]
    goals: List[GoalProgress]
    overall_progress: float
    total_tokens_used: int
    total_tasks_completed: int
    total_tasks_failed: int


class ProgressTracker:
    """进度跟踪器：追踪任务和目标的进度"""

    VALID_STATUS = ["pending", "in_progress", "completed", "failed"]
    VALID_PRIORITIES = ["low", "medium", "high", "critical"]

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.environ.get("LAAP_ROOT", os.getcwd())
        self._tasks: Dict[str, TaskProgress] = {}
        self._goals: Dict[str, GoalProgress] = {}
        self._history: List[ProgressSnapshot] = []
        self._storage_path = os.path.join(self.project_root, ".laap", "progress")
        os.makedirs(self._storage_path, exist_ok=True)
        self._load_progress()

    def add_task(self, task_id: str, description: str, priority: str = "medium",
                 estimated_duration: float = 0.0, dependencies: List[str] = None) -> TaskProgress:
        """添加任务"""
        if priority not in self.VALID_PRIORITIES:
            priority = "medium"

        task = TaskProgress(
            task_id=task_id,
            description=description,
            priority=priority,
            estimated_duration=estimated_duration,
            dependencies=dependencies or [],
        )
        self._tasks[task_id] = task
        self._save_progress()
        return task

    def update_task_status(self, task_id: str, status: str) -> bool:
        """更新任务状态"""
        if task_id not in self._tasks:
            return False

        if status not in self.VALID_STATUS:
            return False

        task = self._tasks[task_id]
        task.status = status

        if status == "in_progress" and task.started_at is None:
            task.started_at = time.time()
        elif status == "completed":
            task.completed_at = time.time()
            if task.started_at:
                task.actual_duration = task.completed_at - task.started_at
            task.progress = 100.0
        elif status == "failed":
            task.completed_at = time.time()

        self._update_task_progress(task_id)
        self._save_progress()
        return True

    def update_task_progress(self, task_id: str, progress: float) -> bool:
        """更新任务进度百分比"""
        if task_id not in self._tasks:
            return False

        progress = max(0.0, min(100.0, progress))
        self._tasks[task_id].progress = progress

        if progress >= 100.0:
            self.update_task_status(task_id, "completed")

        self._save_progress()
        return True

    def update_subtask_count(self, task_id: str, completed: int, total: int) -> bool:
        """更新子任务完成数量"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.subtasks_completed = completed
        task.subtasks_total = total

        if total > 0:
            task.progress = (completed / total) * 100.0

        if completed >= total > 0:
            self.update_task_status(task_id, "completed")

        self._save_progress()
        return True

    def record_token_usage(self, task_id: str, tokens: int) -> bool:
        """记录任务token消耗"""
        if task_id not in self._tasks:
            return False

        self._tasks[task_id].tokens_used += tokens
        self._save_progress()
        return True

    def fail_task(self, task_id: str, error_message: str) -> bool:
        """标记任务失败"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task.status = "failed"
        task.error_message = error_message
        task.completed_at = time.time()

        self._save_progress()
        return True

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """获取任务进度"""
        return self._tasks.get(task_id)

    def list_tasks(self, status: str = None) -> List[TaskProgress]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda x: (-self._priority_order(x.priority), x.created_at))

    def add_goal(self, goal_id: str, title: str, description: str,
                 target_date: str = None, tasks: List[str] = None) -> GoalProgress:
        """添加目标"""
        goal = GoalProgress(
            goal_id=goal_id,
            title=title,
            description=description,
            target_date=target_date,
            tasks=tasks or [],
        )
        self._goals[goal_id] = goal
        self._update_goal_progress(goal_id)
        self._save_progress()
        return goal

    def add_task_to_goal(self, goal_id: str, task_id: str) -> bool:
        """将任务添加到目标"""
        if goal_id not in self._goals:
            return False

        if task_id not in self._tasks:
            return False

        if task_id not in self._goals[goal_id].tasks:
            self._goals[goal_id].tasks.append(task_id)
            self._update_goal_progress(goal_id)
            self._save_progress()

        return True

    def _update_goal_progress(self, goal_id: str) -> None:
        """更新目标进度"""
        if goal_id not in self._goals:
            return

        goal = self._goals[goal_id]
        total_tasks = len(goal.tasks)

        if total_tasks == 0:
            goal.progress = 0.0
            return

        completed_tasks = 0
        for task_id in goal.tasks:
            task = self._tasks.get(task_id)
            if task and task.status == "completed":
                completed_tasks += 1

        goal.progress = (completed_tasks / total_tasks) * 100.0
        goal.updated_at = time.time()

        if goal.progress >= 100.0:
            goal.status = "completed"
        elif goal.progress > 0:
            goal.status = "in_progress"

    def get_goal(self, goal_id: str) -> Optional[GoalProgress]:
        """获取目标进度"""
        return self._goals.get(goal_id)

    def list_goals(self) -> List[GoalProgress]:
        """列出所有目标"""
        return sorted(self._goals.values(), key=lambda x: x.created_at)

    def get_overall_progress(self) -> float:
        """获取整体进度"""
        tasks = list(self._tasks.values())
        if not tasks:
            return 0.0

        total_weighted_progress = 0.0
        total_weight = 0.0

        for task in tasks:
            weight = self._priority_weight(task.priority)
            total_weighted_progress += task.progress * weight
            total_weight += weight

        return total_weighted_progress / total_weight if total_weight > 0 else 0.0

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        tasks = list(self._tasks.values())

        completed = sum(1 for t in tasks if t.status == "completed")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        pending = sum(1 for t in tasks if t.status == "pending")
        failed = sum(1 for t in tasks if t.status == "failed")

        total_tokens = sum(t.tokens_used for t in tasks)
        total_estimated = sum(t.estimated_duration for t in tasks)
        total_actual = sum(t.actual_duration for t in tasks)

        return {
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "pending_tasks": pending,
            "failed_tasks": failed,
            "overall_progress": self.get_overall_progress(),
            "total_tokens_used": total_tokens,
            "total_estimated_duration": total_estimated,
            "total_actual_duration": total_actual,
            "goals_total": len(self._goals),
            "goals_completed": sum(1 for g in self._goals.values() if g.status == "completed"),
        }

    def generate_progress_report(self) -> str:
        """生成进度报告"""
        stats = self.get_statistics()
        lines = [
            "=" * 60,
            "LAAP Harness 进度报告",
            "=" * 60,
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "任务统计:",
            f"  总任务数: {stats['total_tasks']}",
            f"  已完成: {stats['completed_tasks']}",
            f"  进行中: {stats['in_progress_tasks']}",
            f"  待处理: {stats['pending_tasks']}",
            f"  失败: {stats['failed_tasks']}",
            f"  整体进度: {stats['overall_progress']:.1f}%",
            "",
            "资源消耗:",
            f"  总Tokens: {stats['total_tokens_used']:,}",
            f"  预估时长: {self._format_duration(stats['total_estimated_duration'])}",
            f"  实际时长: {self._format_duration(stats['total_actual_duration'])}",
            "",
            "目标统计:",
            f"  总目标数: {stats['goals_total']}",
            f"  已完成目标: {stats['goals_completed']}",
            "",
        ]

        if self._goals:
            lines.append("目标详情:")
            for goal in self.list_goals():
                status_icon = {"completed": "✓", "in_progress": "◉", "pending": "○"}.get(goal.status, "?")
                lines.append(f"  {status_icon} {goal.title}: {goal.progress:.1f}%")

        if self._tasks:
            lines.append("\n任务详情:")
            for task in self.list_tasks():
                status_icon = {
                    "completed": "✓",
                    "in_progress": "◉",
                    "pending": "○",
                    "failed": "✗",
                }.get(task.status, "?")
                priority_icon = {"critical": "!!", "high": "!", "medium": "", "low": "."}.get(task.priority, "")
                lines.append(f"  {status_icon} {priority_icon} [{task.status}] {task.description[:50]}...")
                lines.append(f"      进度: {task.progress:.1f}% | Tokens: {task.tokens_used:,}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def create_snapshot(self) -> ProgressSnapshot:
        """创建进度快照"""
        stats = self.get_statistics()
        snapshot = ProgressSnapshot(
            timestamp=time.time(),
            tasks=list(self._tasks.values()),
            goals=list(self._goals.values()),
            overall_progress=stats["overall_progress"],
            total_tokens_used=stats["total_tokens_used"],
            total_tasks_completed=stats["completed_tasks"],
            total_tasks_failed=stats["failed_tasks"],
        )
        self._history.append(snapshot)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        self._save_history()
        return snapshot

    def get_history(self, limit: int = 10) -> List[ProgressSnapshot]:
        """获取历史快照"""
        return self._history[-limit:]

    def _update_task_progress(self, task_id: str) -> None:
        """内部更新任务进度"""
        task = self._tasks.get(task_id)
        if not task:
            return

        for goal in self._goals.values():
            if task_id in goal.tasks:
                self._update_goal_progress(goal.goal_id)

    def _priority_order(self, priority: str) -> int:
        """优先级排序值"""
        order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return order.get(priority, 2)

    def _priority_weight(self, priority: str) -> float:
        """优先级权重"""
        weights = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.5}
        return weights.get(priority, 1.0)

    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}分钟"
        else:
            return f"{seconds / 3600:.1f}小时"

    def _save_progress(self) -> None:
        """保存进度数据"""
        data = {
            "tasks": {tid: self._task_to_dict(t) for tid, t in self._tasks.items()},
            "goals": {gid: self._goal_to_dict(g) for gid, g in self._goals.items()},
        }
        path = os.path.join(self._storage_path, "progress.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_progress(self) -> None:
        """加载进度数据"""
        path = os.path.join(self._storage_path, "progress.json")
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for tid, tdict in data.get("tasks", {}).items():
                self._tasks[tid] = self._dict_to_task(tdict)

            for gid, gdict in data.get("goals", {}).items():
                self._goals[gid] = self._dict_to_goal(gdict)

            logger.info(f"Loaded {len(self._tasks)} tasks and {len(self._goals)} goals")
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")

    def _save_history(self) -> None:
        """保存历史数据"""
        data = []
        for snapshot in self._history:
            data.append({
                "timestamp": snapshot.timestamp,
                "overall_progress": snapshot.overall_progress,
                "total_tokens_used": snapshot.total_tokens_used,
                "total_tasks_completed": snapshot.total_tasks_completed,
                "total_tasks_failed": snapshot.total_tasks_failed,
            })
        path = os.path.join(self._storage_path, "history.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _task_to_dict(self, task: TaskProgress) -> Dict[str, Any]:
        """任务转字典"""
        return {
            "task_id": task.task_id,
            "description": task.description,
            "status": task.status,
            "progress": task.progress,
            "subtasks_total": task.subtasks_total,
            "subtasks_completed": task.subtasks_completed,
            "estimated_duration": task.estimated_duration,
            "actual_duration": task.actual_duration,
            "tokens_used": task.tokens_used,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "dependencies": task.dependencies,
            "priority": task.priority,
            "error_message": task.error_message,
        }

    def _dict_to_task(self, data: Dict[str, Any]) -> TaskProgress:
        """字典转任务"""
        return TaskProgress(
            task_id=data["task_id"],
            description=data["description"],
            status=data.get("status", "pending"),
            progress=data.get("progress", 0.0),
            subtasks_total=data.get("subtasks_total", 0),
            subtasks_completed=data.get("subtasks_completed", 0),
            estimated_duration=data.get("estimated_duration", 0.0),
            actual_duration=data.get("actual_duration", 0.0),
            tokens_used=data.get("tokens_used", 0),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            dependencies=data.get("dependencies", []),
            priority=data.get("priority", "medium"),
            error_message=data.get("error_message"),
        )

    def _goal_to_dict(self, goal: GoalProgress) -> Dict[str, Any]:
        """目标转字典"""
        return {
            "goal_id": goal.goal_id,
            "title": goal.title,
            "description": goal.description,
            "status": goal.status,
            "target_date": goal.target_date,
            "tasks": goal.tasks,
            "progress": goal.progress,
            "created_at": goal.created_at,
            "updated_at": goal.updated_at,
        }

    def _dict_to_goal(self, data: Dict[str, Any]) -> GoalProgress:
        """字典转目标"""
        return GoalProgress(
            goal_id=data["goal_id"],
            title=data["title"],
            description=data["description"],
            status=data.get("status", "in_progress"),
            target_date=data.get("target_date"),
            tasks=data.get("tasks", []),
            progress=data.get("progress", 0.0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )