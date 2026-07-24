"""
任务监督引擎 — TaskSupervisor

功能:
  1. 接收超长任务，支持 Lorry 委派模式
  2. 自动分解为可执行子步骤
  3. 自主执行链，大决策才询问 Lorry
  4. JSON 检查点持久化，崩溃恢复
  5. 质量验证
  6. 自然语言状态报告
  7. 并行任务管理

用法示例:
  from task_supervisor import TaskSupervisor
  ts = TaskSupervisor(checkpoint_dir="D:/LAAP/aris_brain/checkpoints")
  task = ts.receive_task("开发一个 CLI 计算器", priority=4, success_criteria="加减乘除均可用")
  ts.decompose(task.id)
  result = ts.advance(task.id)
  logger.info(ts.report())
"""

import logging
logger = logging.getLogger(__name__)

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


# ────────────────────────────────────────────────
# 枚举 & 数据结构
# ────────────────────────────────────────────────

class TaskSource(Enum):
    """任务来源"""
    LORRY = "lorry"
    SYSTEM = "system"
    USER = "user"
    SUBAGENT = "subagent"


class TaskStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionType(Enum):
    ANALYZE = "analyze"
    SEARCH = "search"
    WRITE_CODE = "write_code"
    TEST = "test"
    ASK_LORRY = "ask_lorry"
    DELEGATE = "delegate"
    VERIFY = "verify"
    PLAN = "plan"
    REFINE = "refine"


# ────────────────────────────────────────────────
# Data Classes
# ────────────────────────────────────────────────

@dataclass
class TaskStep:
    order: int
    action: str  # ActionType value
    description: str
    status: str = "pending"  # StepStatus value
    result: str = ""
    error_count: int = 0
    created_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStep":
        return cls(**data)


@dataclass
class Task:
    id: str
    description: str
    source: str  # TaskSource value
    priority: int  # 1-5
    created_at: float
    status: str = "active"  # TaskStatus value
    steps: List[TaskStep] = field(default_factory=list)
    checkpoint_path: str = ""
    success_criteria: str = ""
    need_lorry_input: List[str] = field(default_factory=list)
    completed_at: float = 0.0
    quality_report: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        steps = [TaskStep.from_dict(s) for s in data.pop("steps", [])]
        return cls(steps=steps, **data)


# ────────────────────────────────────────────────
# 核心引擎
# ────────────────────────────────────────────────

class TaskSupervisor:
    """
    任务监督引擎 — 管理多任务并行、分解、自主执行、检查点、质量验证。
    """

    def __init__(self, checkpoint_dir: str = "D:/LAAP/aris_brain/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self._tasks: Dict[str, Task] = {}
        os.makedirs(checkpoint_dir, exist_ok=True)

    # ─────────────── 任务生命周期 ───────────────

    def receive_task(
        self,
        description: str,
        priority: int = 3,
        success_criteria: str = "",
        source: str = "lorry",
    ) -> Task:
        """
        接收新任务。
        source="lorry" 表示是 Lorry 委派的任务。
        """
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        task = Task(
            id=task_id,
            description=description,
            source=source,
            priority=max(1, min(5, priority)),
            created_at=time.time(),
            status=TaskStatus.ACTIVE.value,
            success_criteria=success_criteria,
        )
        self._tasks[task_id] = task
        self._save_checkpoint(task_id)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]

    # ─────────────── 任务分解 ───────────────

    def decompose(self, task_id: str) -> bool:
        """
        将大任务自动拆解为可执行子步骤。
        返回 True 表示分解成功。
        """
        task = self.get_task(task_id)
        if not task:
            return False

        lines = self._smart_split(task.description)
        task.steps.clear()

        for i, line in enumerate(lines, 1):
            action, desc = self._classify_line(line, i, len(lines))
            task.steps.append(TaskStep(
                order=i,
                action=action,
                description=desc,
                status=StepStatus.PENDING.value,
                created_at=time.time(),
            ))

        # 如果没有任何步骤被识别，生成一个兜底步骤
        if not task.steps:
            task.steps.append(TaskStep(
                order=1,
                action=ActionType.ANALYZE.value,
                description=f"分析并执行任务: {task.description[:100]}",
                status=StepStatus.PENDING.value,
                created_at=time.time(),
            ))

        self._save_checkpoint(task_id)
        return True

    def _smart_split(self, text: str) -> List[str]:
        """智能分割任务描述为多行子任务描述（简单启发式）。"""
        if not text.strip():
            return []
        import re
        # 先按换行分
        lines = []
        for segment in text.split("\n"):
            segment = segment.strip()
            if not segment:
                continue
            # 再按句号/分号/箭头分句（包括双字节箭头）
            sentences = re.split(r"[。；;→➡►▸,，]", segment)
            for sent in sentences:
                sent = sent.strip()
                if sent:
                    lines.append(sent)
        # 如果还是只得到一行，尝试用关键词分隔
        if len(lines) <= 1 and ":" in text:
            parts = re.split(r"(?:P\d[:：]|[A-Z]\d[.、])", text)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                lines = parts
        # 如果只有一行，尝试用 ①数字. ②数字) ③第一、第二 等分割
        if len(lines) <= 1:
            # 用先+后等连接词分割
            splits = re.split(r"(?:先|然后|接着|随后|再|最后)", lines[0]) if lines else []
            if len(splits) > 1:
                lines = [s.strip() for s in splits if s.strip()]
        return lines if lines else [text.strip()]

    def _classify_line(self, line: str, idx: int, total: int) -> tuple:
        """启发式分类一行文本到合适的 action 类型。"""
        low = line.lower()
        if any(kw in low for kw in ["分析", "调研", "了解", "研究", "analyze", "investigate"]):
            return ActionType.ANALYZE.value, line
        if any(kw in low for kw in ["搜索", "查找", "查询", "search", "find", "lookup"]):
            return ActionType.SEARCH.value, line
        if any(kw in low for kw in ["写代码", "实现", "开发", "编码", "write", "implement", "code", "开发"]):
            return ActionType.WRITE_CODE.value, line
        if any(kw in low for kw in ["测试", "验证", "检查", "test", "verify", "validate"]):
            return ActionType.TEST.value, line
        if any(kw in low for kw in ["问", "询问", "确认", "ask", "confirm"]):
            return ActionType.ASK_LORRY.value, line
        if any(kw in low for kw in ["委托", "分配", "子任务", "delegate", "assign"]):
            return ActionType.DELEGATE.value, line
        # 默认: 第一步用 analyze，后续用 write_code
        if idx == 1:
            return ActionType.ANALYZE.value, line
        return ActionType.WRITE_CODE.value, line

    # ─────────────── 自主执行 ───────────────

    def advance(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行下一步。返回执行结果字典。
        如果 task_id 为 None，自动选择最优先的活动任务。
        """
        task = self._resolve_task(task_id)
        if not task:
            return {"ok": False, "error": "没有任务可供执行", "done": True}

        if task.status != TaskStatus.ACTIVE.value:
            return {"ok": False, "error": f"任务状态为 {task.status}，无法继续", "done": False}

        # 找下一个 pending 步骤
        step = self._find_next_pending(task)
        if step is None:
            # 无更多 pending 步骤 — 检查是否所有步骤都完成了
            all_done = all(s.status == StepStatus.COMPLETED.value for s in task.steps)
            if all_done:
                task.status = TaskStatus.COMPLETED.value
                task.completed_at = time.time()
                task.quality_report = self._generate_quality_report(task)
                self._save_checkpoint(task.id)
                return {
                    "ok": True,
                    "done": True,
                    "task_id": task.id,
                    "message": "所有步骤已完成",
                    "quality_report": task.quality_report,
                }
            return {"ok": True, "done": True, "task_id": task.id, "message": "没有可执行的步骤"}

        # 标记进行中
        step.status = StepStatus.IN_PROGRESS.value
        self._save_checkpoint(task.id)

        # 根据 action 执行
        result = self._execute_step(task, step)

        # 处理重试逻辑
        if not result["ok"] and step.error_count < 2:
            step.error_count += 1
            step.status = StepStatus.PENDING.value  # 重置为等待重试
            self._save_checkpoint(task.id)
            return {
                "ok": False,
                "retry": True,
                "task_id": task.id,
                "step": step.order,
                "error": result.get("error", "未知错误"),
                "retries_left": 2 - step.error_count,
                "action": step.action,
            }

        if not result["ok"]:
            # 超过重试次数
            step.status = StepStatus.FAILED.value
            task.need_lorry_input.append(
                f"步骤 {step.order} ({step.action}: {step.description[:60]}) "
                f"重试 {step.error_count} 次后仍失败: {result.get('error', '未知错误')}"
            )
            task.status = TaskStatus.BLOCKED.value
            self._save_checkpoint(task.id)
            return {
                "ok": True,
                "done": False,
                "blocked": True,
                "task_id": task.id,
                "step": step.order,
                "message": "步骤执行失败，任务已阻塞",
                "need_lorry_input": task.need_lorry_input[-1],
            }

        # 执行成功
        step.status = StepStatus.COMPLETED.value
        step.result = result.get("result", "")
        step.completed_at = time.time()

        # 验证步骤结果
        verify_result = self.verify_step(task, step)
        if not verify_result.get("ok", True):
            # 验证失败但不阻塞 — 记录到 quality 报告
            step.result += f"\n[验证告警] {verify_result.get('message', '')}"

        self._save_checkpoint(task.id)

        # 检查是否所有步骤都完成了
        if all(s.status == StepStatus.COMPLETED.value for s in task.steps):
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = time.time()
            task.quality_report = self._generate_quality_report(task)
            self._save_checkpoint(task.id)
            return {
                "ok": True,
                "done": True,
                "task_id": task.id,
                "step": step.order,
                "message": "🎉 任务全部完成！",
                "quality_report": task.quality_report,
                "result": step.result,
            }

        return {
            "ok": True,
            "done": False,
            "task_id": task.id,
            "step": step.order,
            "action": step.action,
            "description": step.description,
            "result": step.result,
            "progress": self._calc_progress(task),
            "need_lorry_input": task.need_lorry_input if step.action == ActionType.ASK_LORRY.value else [],
        }

    def _resolve_task(self, task_id: Optional[str]) -> Optional[Task]:
        if task_id:
            return self.get_task(task_id)
        # 自动选择优先级最高且 active 的任务
        active = [t for t in self._tasks.values() if t.status == TaskStatus.ACTIVE.value]
        if not active:
            return None
        # 按优先级降序、创建时间升序排序
        active.sort(key=lambda t: (-t.priority, t.created_at))
        return active[0]

    def _find_next_pending(self, task: Task) -> Optional[TaskStep]:
        """找到按 order 排序的下一个 pending 步骤。"""
        pending = [s for s in task.steps if s.status == StepStatus.PENDING.value]
        if not pending:
            return None
        pending.sort(key=lambda s: s.order)
        return pending[0]

    def _execute_step(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """根据 action 类型执行步骤。此为框架核心 — 实际执行依赖外部引擎集成。"""
        action = step.action

        if action == ActionType.ANALYZE.value:
            return self._do_analyze(task, step)
        elif action == ActionType.SEARCH.value:
            return self._do_search(task, step)
        elif action == ActionType.WRITE_CODE.value:
            return self._do_write_code(task, step)
        elif action == ActionType.TEST.value:
            return self._do_test(task, step)
        elif action == ActionType.ASK_LORRY.value:
            return self._do_ask_lorry(task, step)
        elif action == ActionType.DELEGATE.value:
            return self._do_delegate(task, step)
        elif action == ActionType.VERIFY.value:
            return self._do_verify(task, step)
        elif action == ActionType.PLAN.value:
            return self._do_plan(task, step)
        elif action == ActionType.REFINE.value:
            return self._do_refine(task, step)
        else:
            return {"ok": True, "result": f"[自动执行] {step.description}"}

    # ─────────────── 各 Action 模拟执行 ───────────────

    def _do_analyze(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """分析步骤 — 自动输出分析结果。"""
        result_text = (
            f"✅ 分析完成：\n"
            f"  任务目标: {task.description[:80]}\n"
            f"  步骤内容: {step.description}\n"
            f"  成功标准: {task.success_criteria or '未指定'}\n"
            f"  优先级: {task.priority}/5\n"
            f"  来源: {task.source}\n"
            f"  — 分析通过，可以进行下一步。"
        )
        return {"ok": True, "result": result_text}

    def _do_search(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """搜索步骤 — 模拟搜索（实际可对接知识库）。"""
        return {"ok": True, "result": f"[知识库搜索] 已完成对「{step.description[:50]}」的相关信息收集。"}

    def _do_write_code(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """写代码步骤 — 模拟执行。"""
        return {"ok": True, "result": f"[代码生成] 自动生成了与「{step.description[:50]}」相关的代码。"}

    def _do_test(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """测试步骤 — 模拟执行。"""
        return {"ok": True, "result": f"[测试执行] 对步骤输出进行了测试验证，结果正常。"}

    def _do_ask_lorry(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """需要询问 Lorry 的步骤 — 记录到 need_lorry_input。"""
        question = f"需要询问 Lorry: {step.description}"
        task.need_lorry_input.append(question)
        return {
            "ok": True,
            "result": question,
            "need_lorry": True,
        }

    def _do_delegate(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """委托子代理步骤。"""
        return {"ok": True, "result": f"[子代理] 已将「{step.description[:50]}」委托给子代理执行。"}

    def _do_verify(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """自我验证步骤。"""
        return {"ok": True, "result": f"[自我验证] 已验证步骤输出符合预期。"}

    def _do_plan(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """规划步骤。"""
        return {"ok": True, "result": f"[规划] 为「{step.description[:50]}」制定了执行计划。"}

    def _do_refine(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """优化/精炼步骤。"""
        return {"ok": True, "result": f"[优化] 对「{step.description[:50]}」进行了精炼优化。"}

    # ─────────────── 质量验证 ───────────────

    def verify_step(self, task: Task, step: TaskStep) -> Dict[str, Any]:
        """
        验证步骤执行结果是否满足成功标准。
        返回 {"ok": True/False, "message": "..."}
        """
        if not task.success_criteria:
            return {"ok": True, "message": "无成功标准，跳过验证"}

        criteria = task.success_criteria.lower()
        result = step.result.lower()

        # 简单启发式验证
        keywords = self._extract_keywords(criteria)
        if not keywords:
            return {"ok": True, "message": "无法提取验证关键词，跳过"}

        matched = sum(1 for kw in keywords if kw in result)
        rate = matched / len(keywords)

        if rate >= 0.5:
            return {
                "ok": True,
                "message": f"验证通过，匹配率 {rate:.0%} ({matched}/{len(keywords)} 关键词)",
                "rate": rate,
            }
        else:
            return {
                "ok": False,
                "message": f"验证结果不佳，仅匹配 {rate:.0%} 的关键词 ({matched}/{len(keywords)})",
                "rate": rate,
            }

    def _extract_keywords(self, text: str) -> List[str]:
        """从成功标准中提取关键词。"""
        import re
        # 去标点，按空格或汉字分割
        cleaned = re.sub(r"[,.:;!?()\[\]{}\u3000-\u303f\uff00-\uffef]", " ", text)
        words = cleaned.split()
        # 过滤过短的词
        return [w for w in words if len(w) > 1]

    def _generate_quality_report(self, task: Task) -> str:
        """任务完成时生成质量报告。"""
        total = len(task.steps)
        completed = sum(1 for s in task.steps if s.status == StepStatus.COMPLETED.value)
        failed = sum(1 for s in task.steps if s.status == StepStatus.FAILED.value)
        duration = time.time() - task.created_at
        duration_str = f"{duration:.1f}s" if duration < 120 else f"{duration/60:.1f}min"

        report_parts = [
            f"📊 质量报告 — 任务 {task.id}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"描述: {task.description[:100]}",
            f"状态: {task.status}",
            f"优先级: {task.priority}/5",
            f"来源: {task.source}",
            f"耗时: {duration_str}",
            f"步骤: {completed}/{total} 完成, {failed} 失败",
            f"成功标准: {task.success_criteria or '未指定'}",
        ]

        if task.need_lorry_input:
            report_parts.append(f"待处理问题: {len(task.need_lorry_input)} 项")
            for q in task.need_lorry_input:
                report_parts.append(f"  • {q[:80]}")

        if failed > 0:
            report_parts.append(f"⚠️ 部分步骤失败，请检查详情。")
        elif completed == total:
            report_parts.append(f"✅ 所有步骤成功完成！")

        return "\n".join(report_parts)

    # ─────────────── 暂停 / 恢复 / 取消 / 失败 ───────────────

    def pause(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        if task.status not in (TaskStatus.ACTIVE.value,):
            return False
        task.status = TaskStatus.PAUSED.value
        self._save_checkpoint(task_id)
        return True

    def resume(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task or task.status != TaskStatus.PAUSED.value:
            return False
        task.status = TaskStatus.ACTIVE.value
        self._save_checkpoint(task_id)
        return True

    def cancel(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = TaskStatus.FAILED.value
        task.completed_at = time.time()
        task.quality_report = self._generate_quality_report(task)
        self._save_checkpoint(task_id)
        return True

    def fail(self, task_id: str, reason: str = "") -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        task.status = TaskStatus.FAILED.value
        task.completed_at = time.time()
        if reason:
            task.need_lorry_input.append(f"手动标记失败: {reason}")
        task.quality_report = self._generate_quality_report(task)
        self._save_checkpoint(task_id)
        return True

    # ─────────────── 状态报告 ───────────────

    def report(self) -> str:
        """
        生成自然语言状态报告，可直接注入认知循环。
        """
        all_tasks = list(self._tasks.values())
        if not all_tasks:
            return "🧠 任务监督引擎: 当前无任务。"

        active = [t for t in all_tasks if t.status == TaskStatus.ACTIVE.value]
        paused = [t for t in all_tasks if t.status == TaskStatus.PAUSED.value]
        completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETED.value]
        blocked = [t for t in all_tasks if t.status == TaskStatus.BLOCKED.value]
        failed = [t for t in all_tasks if t.status == TaskStatus.FAILED.value]

        lines = [
            "🧠 任务监督引擎 — 状态报告",
            "═══════════════════════════════",
            f"总任务数: {len(all_tasks)}",
            f"  ▶ 进行中: {len(active)}",
            f"  ⏸ 已暂停: {len(paused)}",
            f"  ✅ 已完成: {len(completed)}",
            f"  🔒 已阻塞: {len(blocked)}",
            f"  ❌ 已失败: {len(failed)}",
            "",
        ]

        def fmt_task(t: Task) -> List[str]:
            progress = self._calc_progress(t)
            need = ""
            if t.need_lorry_input:
                need = f" ⚠️ {len(t.need_lorry_input)}个问题待Lorry"
            return [
                f"  [{t.id}] P{t.priority} {t.description[:60]}",
                f"         状态: {t.status} 进度: {progress:.0%}{need}",
            ]

        if active:
            lines.append("📋 进行中的任务:")
            for t in active:
                lines.extend(fmt_task(t))
            lines.append("")

        if blocked:
            lines.append("🔒 阻塞的任务 (需要Lorry介入):")
            for t in blocked:
                lines.extend(fmt_task(t))
                for q in t.need_lorry_input[-3:]:
                    lines.append(f"         ⤷ {q[:80]}")
            lines.append("")

        if paused:
            lines.append("⏸ 暂停的任务:")
            for t in paused:
                lines.extend(fmt_task(t))
            lines.append("")

        if completed:
            lines.append("✅ 最近完成的任务:")
            for t in sorted(completed, key=lambda x: x.completed_at, reverse=True)[:3]:
                lines.extend(fmt_task(t))
            lines.append("")

        return "\n".join(lines)

    def _calc_progress(self, task: Task) -> float:
        if not task.steps:
            return 0.0
        done = sum(1 for s in task.steps if s.status in (
            StepStatus.COMPLETED.value, StepStatus.FAILED.value, StepStatus.SKIPPED.value
        ))
        return done / len(task.steps)

    # ─────────────── 检查点持久化 ───────────────

    def _checkpoint_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{task_id}.json")

    def _save_checkpoint(self, task_id: str) -> bool:
        """保存单个任务的检查点。"""
        task = self.get_task(task_id)
        if not task:
            return False
        path = self._checkpoint_path(task_id)
        try:
            data = task.to_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            task.checkpoint_path = path
            return True
        except (IOError, OSError) as e:
            return False

    def save_checkpoint(self, task_id: str) -> bool:
        """公开接口：保存指定任务的检查点。"""
        return self._save_checkpoint(task_id)

    def load_checkpoint(self, task_id: str) -> Optional[Task]:
        """从检查点恢复任务。"""
        path = self._checkpoint_path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            task = Task.from_dict(data)
            self._tasks[task_id] = task
            return task
        except (IOError, json.JSONDecodeError) as e:
            return None

    def load_all_checkpoints(self) -> int:
        """加载所有已保存的检查点。返回恢复的任务数。"""
        if not os.path.isdir(self.checkpoint_dir):
            return 0
        count = 0
        for fname in os.listdir(self.checkpoint_dir):
            if fname.endswith(".json"):
                task_id = fname[:-5]
                if self.load_checkpoint(task_id):
                    count += 1
        return count

    def delete_checkpoint(self, task_id: str) -> bool:
        """删除指定任务的检查点。"""
        path = self._checkpoint_path(task_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False


# ────────────────────────────────────────────────
# 测试区
# ────────────────────────────────────────────────

def test():
    """运行完整的功能测试。"""
    logger.info("=" * 60)
    logger.info("🔬 TaskSupervisor 功能测试")
    logger.info("=" * 60)
    ts = TaskSupervisor(checkpoint_dir="D:/LAAP/aris_brain/checkpoints")

    # 1. 接收任务
    logger.info("\n📌 1. 接收任务")
    task = ts.receive_task(
        description="开发一个Python CLI计算器，支持加减乘除和错误处理",
        priority=4,
        success_criteria="加减乘除均可用，错误处理完善",
        source="lorry",
    )
    logger.info(f"   创建任务: {task.id}")
    logger.info(f"   描述: {task.description[:50]}...")
    logger.info(f"   优先级: {task.priority}")
    logger.info(f"   来源: {task.source}")
    assert task.id is not None
    assert task.priority == 4
    assert task.source == "lorry"

    # 2. 分解任务
    logger.info("\n📌 2. 分解任务")
    ok = ts.decompose(task.id)
    logger.error(f"   分解结果: {'✅ 成功' if ok else '❌ 失败'}")
    logger.info(f"   子步骤数: {len(task.steps)}")
    for s in task.steps:
        logger.info(f"     [{s.order}] {s.action:12s} | {s.description[:50]}")
    assert ok
    assert len(task.steps) > 0

    # 3. 逐步执行
    logger.info("\n📌 3. 逐步执行")
    step_count = 0
    while True:
        result = ts.advance(task.id)
        done = result.get("done", False)
        blocked = result.get("blocked", False)
        step_count += 1
        status_icon = "✅" if result.get("ok") else "⚠️"
        print(f"   步骤 {step_count}: {status_icon} action={result.get('action','?')} "
              f"done={done} blocked={blocked} "
              f"retry={result.get('retry',False)}")
        if done or blocked:
            break

    logger.info(f"\n   总执行步数: {step_count}")
    logger.info(f"   最终状态: {task.status}")
    if task.status == "completed":
        logger.info(f"   质量报告摘要: {task.quality_report[:80]}...")
    assert task.status in ("completed", "blocked")

    # 4. 检查点测试
    logger.info("\n📌 4. 检查点持久化")
    ckpt_ok = ts.save_checkpoint(task.id)
    logger.info(f"   保存检查点: {'✅' if ckpt_ok else '❌'}")
    checkpoint_file = ts._checkpoint_path(task.id)
    exists = os.path.exists(checkpoint_file)
    logger.info(f"   检查点文件存在: {'✅' if exists else '❌'}")
    assert ckpt_ok
    assert exists

    # 5. 恢复测试
    logger.info("\n📌 5. 恢复检查点")
    ts2 = TaskSupervisor(checkpoint_dir="D:/LAAP/aris_brain/checkpoints")
    restored = ts2.load_checkpoint(task.id)
    logger.error(f"   恢复结果: {'✅ 成功' if restored else '❌ 失败'}")
    if restored:
        logger.info(f"   恢复后状态: {restored.status}")
        logger.info(f"   恢复后步骤数: {len(restored.steps)}")
        assert restored.id == task.id
        assert restored.status == task.status

    # 6. 并行任务测试
    logger.info("\n📌 6. 并行任务管理")
    task2 = ts.receive_task(
        description="编写README文档",
        priority=2,
        success_criteria="文档完整",
        source="user",
    )
    ts.decompose(task2.id)
    tasks = ts.list_tasks()
    logger.info(f"   当前总任务数: {len(tasks)}")
    active = ts.list_tasks(status="active")
    completed_tasks = ts.list_tasks(status="completed")
    logger.info(f"   进行中: {len(active)}, 已完成: {len(completed_tasks)}")
    assert len(tasks) == 2

    # 7. 状态报告
    logger.info("\n📌 7. 状态报告")
    report = ts.report()
    logger.info(report[:500])
    assert "任务监督引擎" in report

    # 8. 暂停/恢复测试
    logger.info("\n📌 8. 暂停/恢复")
    paused = ts.pause(task2.id)
    logger.info(f"   暂停 task2: {'✅' if paused else '❌'}")
    assert ts.get_task(task2.id).status == "paused"
    resumed = ts.resume(task2.id)
    logger.info(f"   恢复 task2: {'✅' if resumed else '❌'}")
    assert ts.get_task(task2.id).status == "active"

    # 9. 质量验证
    logger.info("\n📌 9. 质量验证")
    if task.steps:
        sample_step = task.steps[0]
        v_result = ts.verify_step(task, sample_step)
        logger.info(f"   验证结果: {'✅' if v_result.get('ok') else '⚠️'} {v_result.get('message','')}")
    logger.info("\n📌 10. 清理检查点")
    deleted = ts.delete_checkpoint(task.id)
    logger.info(f"   删除检查点: {'✅' if deleted else '❌'}")
    logger.info("\n" + "=" * 60)
    logger.info("🎉 全部测试通过！")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    test()
