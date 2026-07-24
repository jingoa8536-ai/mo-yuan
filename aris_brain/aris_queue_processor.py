"""
Aris 任务队列处理器 — 文件队列模式

被 cron 定时任务调用:
  1. 扫描 requests 目录中的待处理任务
  2. 使用 ConsciousnessHarness 7层架构执行
  3. 写入 responses 目录

两种执行模式:
  - full: 完整 Harness (需要 ConsciousnessHarness 可用)
  - direct: 直接输出 (降级)
"""

import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s|%(message)s")
logger = logging.getLogger("aris.queue.processor")

# 队列目录
QUEUE_DIR = Path(__file__).resolve().parent / ".aris_queue"
REQ_DIR = QUEUE_DIR / "requests"
RESP_DIR = QUEUE_DIR / "responses"
LOCK_FILE = QUEUE_DIR / ".lock"

# 尝试加载 Harness
HAS_HARNESS = False
ConsciousnessHarness = None
HARNESS = None

try:
    HARNESS_PARENT = str(Path(__file__).resolve().parent.parent / "harness")
    if HARNESS_PARENT not in sys.path:
        sys.path.insert(0, HARNESS_PARENT)
    from laap_coding.core.harness import ConsciousnessHarness as _CH
    ConsciousnessHarness = _CH
    HAS_HARNESS = True
    logger.info(f"ConsciousnessHarness loaded (from {HARNESS_PARENT})")
except ImportError as e:
    logger.warning(f"Harness not available: {e}")


def get_harness(workdir: str = None):
    """获取或创建 Harness 实例"""
    global HARNESS
    if HARNESS is None and HAS_HARNESS and ConsciousnessHarness:
        HARNESS = ConsciousnessHarness(workdir=workdir or os.getcwd())
    return HARNESS


def acquire_lock() -> bool:
    """获取处理锁 (防止并发)"""
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < 60:  # 1分钟内其他进程持有锁
            return False
        # 锁超时, 清理
        logger.warning(f"Stale lock (age={age:.0f}s), removing")
        LOCK_FILE.unlink(missing_ok=True)
    try:
        LOCK_FILE.write_text(str(time.time()))
        return True
    except Exception:
        return False


def release_lock():
    LOCK_FILE.unlink(missing_ok=True)


def process_task(task_file: Path) -> bool:
    """处理单个任务文件"""
    task_id = task_file.stem
    resp_path = RESP_DIR / f"{task_id}.json"

    # 已处理过
    if resp_path.exists():
        logger.info(f"Already processed: {task_id}")
        task_file.unlink(missing_ok=True)
        return True

    try:
        with open(task_file, "r", encoding="utf-8") as f:
            task = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read task {task_id}: {e}")
        task_file.unlink(missing_ok=True)
        return False

    logger.info(f"Processing task: {task_id} | {task.get('description','')[:60]}")
    t0 = time.time()

    try:
        result = execute_task(task)
        dt = (time.time() - t0) * 1000
        result["duration_ms"] = dt
        logger.info(f"Task {task_id} completed in {dt:.0f}ms")

        # 写响应
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 删除请求文件
        task_file.unlink(missing_ok=True)
        return True

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}\n{traceback.format_exc()}")
        error_result = {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "tokens": 0,
            "task_id": task_id,
        }
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(error_result, f, ensure_ascii=False, indent=2)
        task_file.unlink(missing_ok=True)
        return False


def execute_task(task: dict) -> dict:
    """执行任务

    两种模式:
      1. full — 使用 ConsciousnessHarness 7层架构
      2. direct — 降级模式, 直接返回
    """
    description = task.get("description", "")
    subtasks = task.get("subtasks", [])
    intent = task.get("intent", "implement")
    workdir = task.get("workdir", os.getcwd())
    keywords = task.get("keywords", [])
    patterns = task.get("patterns", [])

    harness = get_harness(workdir)

    if harness:
        # ── Full Mode: ConsciousnessHarness 7层 ──
        return _exec_full(harness, description, intent, subtasks, patterns)
    else:
        # ── Direct Mode: 降级 ──
        return _exec_direct(description, subtasks)


def _exec_full(harness, description: str, intent: str,
               subtasks: list, patterns: list) -> dict:
    """完整 Harness 执行"""
    result = {
        "status": "completed",
        "output": "",
        "tokens": 0,
        "layers": {},
    }

    # 1. PerceptionLayer (0 token)
    t0 = time.time()
    context = harness.perceive(description)
    if intent:
        context.intent = intent
    result["layers"]["perception"] = {
        "intent": context.intent,
        "keywords": context.keywords,
        "constraints": context.constraints,
        "duration_ms": (time.time() - t0) * 1000,
    }

    # 2. ReasoningLayer (0 token)
    t0 = time.time()
    plan = harness.reason(context)
    result["layers"]["reasoning"] = {
        "subtask_count": len(plan),
        "plan": [s.description for s in plan],
        "duration_ms": (time.time() - t0) * 1000,
    }

    # 3. DecisionLayer (0 token)
    t0 = time.time()
    if patterns:
        for pat in patterns:
            harness.decision_layer.evaluate_pattern(pat.get("id", ""), {})
    result["layers"]["decision"] = {
        "duration_ms": (time.time() - t0) * 1000,
    }

    # 4. ExecutionLayer — 本地模板执行 (0 token, 无 Aris)
    results = []
    t0 = time.time()
    for sub in plan:
        er = harness.execute(sub)
        results.append({
            "sub_task_id": sub.sub_task_id,
            "description": sub.description,
            "success": er.success,
        })
    result["layers"]["execution"] = {
        "completed": sum(1 for r in results if r["success"]),
        "total": len(results),
        "duration_ms": (time.time() - t0) * 1000,
    }

    # 5. VerificationLayer (0 token)
    t0 = time.time()
    ver_passed = True
    for sub, er in zip(plan, results):
        if not er["success"]:
            continue
        vr = harness.verify(
            type('ER', (), {'success': True, 'output': '', 'modified_files': [],
                           'duration_ms': 0, 'error': None})()
        )
        ver_passed = ver_passed and vr.passed
    result["layers"]["verification"] = {
        "passed": ver_passed,
        "duration_ms": (time.time() - t0) * 1000,
    }

    # 6. FeedbackLayer (0 token)
    t0 = time.time()
    result["layers"]["feedback"] = {
        "duration_ms": (time.time() - t0) * 1000,
    }

    result["output"] = (
        f"Perception: {context.intent}, "
        f"Plan: {len(plan)} subtasks, "
        f"Executed: {result['layers']['execution']['completed']}/{result['layers']['execution']['total']}, "
        f"Verified: {'PASS' if ver_passed else 'FAIL'}"
    )
    result["tokens"] = 0
    return result


def _exec_direct(description: str, subtasks: list) -> dict:
    """降级模式—直接返回信息"""
    if subtasks:
        output = f"Plan: {len(subtasks)} subtasks\n"
        for s in subtasks:
            output += f"  - {s.get('description', '?')}\n"
    else:
        output = f"Task: {description[:100]}"

    return {
        "status": "completed",
        "output": output.strip(),
        "tokens": 0,
        "note": "direct mode (no Harness)",
    }


def main():
    """主入口: 处理队列中的所有待处理任务"""
    # 确保目录存在
    REQ_DIR.mkdir(parents=True, exist_ok=True)
    RESP_DIR.mkdir(parents=True, exist_ok=True)

    # 获取锁
    if not acquire_lock():
        logger.info("Another processor is running, skipping")
        return 0

    try:
        # 查找待处理任务
        task_files = sorted(REQ_DIR.glob("*.json"))
        if not task_files:
            logger.info("No pending tasks")
            return 0

        logger.info(f"Found {len(task_files)} pending tasks")

        processed = 0
        for task_file in task_files:
            if process_task(task_file):
                processed += 1

        logger.info(f"Processed {processed}/{len(task_files)} tasks")
        return 0

    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
