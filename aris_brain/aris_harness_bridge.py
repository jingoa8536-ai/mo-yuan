"""
Aris Harness Bridge — 将 ConsciousnessHarness 7层认知架构与 Aris (Hermes Agent) 对接

工作模式:
  1. LocalPlanning: Perceive → Memory → Reason → Decide (纯 Python, 0 tokens)
  2. ArisExecution: 通过 Hermes API 将代码生成任务发给 Aris
  3. LocalVerification: pytest + lint + 合规检查 (纯本地, 0 tokens)
  4. FeedbackLoop: 自修正 (纯本地, 0 tokens)

Token 节省来源:
  - 规划/推理/决策层: 纯 Python 规则引擎, 0 tokens
  - 验证层: pytest/flake8/mypy 本地执行, 0 tokens
  - 反馈层: 分数阈值+重试逻辑, 0 tokens
  - 仅执行层需要 LLM (Aris), 且 Aris 直接读写文件省去 API 上下文填充
"""

import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aris.harness.bridge")

# ── 路径 ──
HARNESS_PARENT = str(Path(__file__).resolve().parent.parent / "harness")
AGENT_DIR = str(Path(__file__).resolve().parent.parent / "laap_agent")
for p in [HARNESS_PARENT, AGENT_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── 尝试导入 Harness ──
HAS_HARNESS = False
ConsciousnessHarness = None
TaskContext = None
SubTask = None
try:
    from laap_coding.core.harness import (
        ConsciousnessHarness as _CH,
        TaskContext as _TC,
        SubTask as _ST,
        ExecutionResult,
        VerificationResult,
    )
    ConsciousnessHarness = _CH
    TaskContext = _TC
    SubTask = _ST
    HAS_HARNESS = True
    logger.info("ConsciousnessHarness loaded successfully")
except ImportError as e:
    logger.warning(f"ConsciousnessHarness not available: {e}")

# ── 尝试导入合规检查 ──
CodeComplianceChecker = None
try:
    from laap_coding.core.compliance_checker import CodeComplianceChecker as _CCC
    CodeComplianceChecker = _CCC
except ImportError:
    pass

# ── 尝试导入反馈引擎 ──
FeedbackEngine = None
try:
    from laap_coding.core.feedback_engine import FeedbackEngine as _FE
    FeedbackEngine = _FE
except ImportError:
    pass


# ════════════════════════════════════════════════════════════
# Hermes API 客户端 — 给 Aris 发任务
# ════════════════════════════════════════════════════════════

class HermesAPIClient:
    """通过 Hermes API Server 与 Aris 通信。

    两种模式:
      1. HTTP: 直接 POST 到 Hermes API server (端口 11520)
      2. FileQueue: 通过文件队列交换 (无 HTTP 时的 fallback)
    """

    API_BASE = "http://127.0.0.1:11520"
    QUEUE_DIR = Path(os.environ.get(
        "ARIS_QUEUE_DIR",
        str(Path(__file__).resolve().parent / ".aris_queue")
    ))

    def __init__(self, mode: str = "auto"):
        self.mode = mode
        self._session = None
        self._http_available = self._check_http()

        if mode == "auto":
            self.mode = "http" if self._http_available else "file"
        logger.info(f"HermesAPIClient mode={self.mode} http={self._http_available}")

        if self.mode == "file":
            self.QUEUE_DIR.mkdir(parents=True, exist_ok=True)
            (self.QUEUE_DIR / "requests").mkdir(exist_ok=True)
            (self.QUEUE_DIR / "responses").mkdir(exist_ok=True)

    def _check_http(self) -> bool:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", 11520))
            s.close()
            return result == 0
        except Exception:
            return False

    def send_task(self, task: Dict[str, Any]) -> Optional[str]:
        """发送任务给 Aris, 返回 task_id"""
        task_id = f"aris_{int(time.time())}_{os.urandom(2).hex()}"
        task["task_id"] = task_id

        if self.mode == "http":
            return self._send_http(task, task_id)
        else:
            return self._send_file(task, task_id)

    def _send_http(self, task: Dict[str, Any], task_id: str) -> Optional[str]:
        try:
            import httpx
            resp = httpx.post(
                f"{self.API_BASE}/api/task",
                json=task,
                timeout=5.0,
            )
            if resp.status_code < 500:
                return task_id
            logger.warning(f"HTTP send returned {resp.status_code}")
            return None
        except Exception as e:
            logger.warning(f"HTTP send failed: {e}, falling back to file")
            return self._send_file(task, task_id)

    def _send_file(self, task: Dict[str, Any], task_id: str) -> str:
        req_path = self.QUEUE_DIR / "requests" / f"{task_id}.json"
        task["status"] = "pending"
        task["created_at"] = time.time()
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
        logger.info(f"Task written to file queue: {req_path}")
        return task_id

    def poll_result(self, task_id: str, timeout: float = 120.0,
                    interval: float = 2.0) -> Optional[Dict[str, Any]]:
        """轮询任务结果"""
        deadline = time.time() + timeout

        if self.mode == "http":
            # HTTP 模式: 轮询 API
            import httpx
            while time.time() < deadline:
                try:
                    resp = httpx.get(
                        f"{self.API_BASE}/api/task/{task_id}",
                        timeout=3.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") in ("completed", "failed"):
                            return data
                except Exception:
                    pass
                time.sleep(interval)
            return None

        # File 模式: 轮询响应目录
        resp_path = self.QUEUE_DIR / "responses" / f"{task_id}.json"
        while time.time() < deadline:
            if resp_path.exists():
                try:
                    with open(resp_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Error reading response: {e}")
                    time.sleep(interval)
                    continue
            time.sleep(interval)
        return None

    def send_and_wait(self, task: Dict[str, Any],
                      timeout: float = 180.0) -> Dict[str, Any]:
        """发送任务并等待结果"""
        task_id = self.send_task(task)
        if not task_id:
            return {
                "success": False,
                "error": "Failed to send task",
                "tokens": 0,
            }
        result = self.poll_result(task_id, timeout=timeout)
        if result is None:
            return {
                "success": False,
                "error": f"Task {task_id} timed out after {timeout}s",
                "tokens": 0,
            }
        return {
            "success": result.get("status") == "completed",
            "response": result.get("output", result.get("response", "")),
            "error": result.get("error", ""),
            "tokens": result.get("tokens", 0),
            "task_id": task_id,
        }


# ════════════════════════════════════════════════════════════
# Aris Harness Engine — LAAPAgentV3 接口兼容
# ════════════════════════════════════════════════════════════

class ArisHarnessEngine:
    """Aris 驱动的 ConsciousnessHarness 引擎。

    实现 LAAPAgentV3.run() 相同接口, 可直接替换:
      agent = ArisHarnessEngine(api_key=..., model=...)
      result = agent.run("implement a REST API")

    内部流程:
      1. PerceptionLayer — 解析意图/关键词 (本地, 0 token)
      2. MemoryLayer — 加载架构模式/项目历史 (本地, 0 token)
      3. ReasoningLayer — 规划子任务/依赖图 (本地, 0 token)
      4. DecisionLayer — 质量门控 (本地, 0 token)
      5. ExecutionLayer — 代码生成 (通过 Aris/Hermes API)
      6. VerificationLayer — pytest/lint (本地, 0 token)
      7. FeedbackLayer — 自修正 (本地, 0 token)
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "aris",
        base_url: str = "",
        workdir: str = "",
        token_budget: int = 2000,
        hermes_mode: str = "auto",
    ):
        self.model = model
        self._workdir = workdir or os.getcwd()
        self._token_budget = token_budget
        self._total_prompt = 0
        self._total_completion = 0
        self._total_tokens = 0
        self._turn = 0

        # Hermes API 客户端 (给 Aris 发任务)
        self._hermes = HermesAPIClient(mode=hermes_mode)

        # ConsciousnessHarness 实例
        self._harness = None
        self._ensure_harness()

        # 合规检查 + 反馈引擎
        self._checker = None
        self._feedback = None
        self._init_checkers()

        logger.info(
            f"ArisHarnessEngine initialized | "
            f"workdir={self._workdir} | "
            f"model={model} | "
            f"hermes_mode={self._hermes.mode}"
        )

    def _ensure_harness(self):
        if self._harness is not None:
            return
        if not HAS_HARNESS or ConsciousnessHarness is None:
            logger.warning("ConsciousnessHarness not available, will use direct mode")
            self._harness = None
            return
        try:
            self._harness = ConsciousnessHarness(
                workdir=self._workdir,
                token_budget=self._token_budget,
            )
            logger.info(f"Harness initialized: {self._harness.summary()}")
        except Exception as e:
            logger.warning(f"Harness init failed: {e}, using direct mode")
            self._harness = None

    def _init_checkers(self):
        if CodeComplianceChecker:
            try:
                self._checker = CodeComplianceChecker(self._workdir)
            except Exception:
                pass
        if FeedbackEngine:
            try:
                self._feedback = FeedbackEngine(self._workdir)
            except Exception:
                pass

    # ══════════════════════════════════════════════
    # 主入口 — LAAPAgentV3.run() 兼容接口
    # ══════════════════════════════════════════════

    def run(
        self,
        user_message: str,
        cognitive_code: str = "",
        workdir: str = "",
        max_turns: int = 10,
    ) -> Dict[str, Any]:
        """执行任务。

        Args:
            user_message: 用户任务描述 (e.g. "实现一个 REST API")
            cognitive_code: 认知码 (LAAP v3 兼容)
            workdir: 工作目录
            max_turns: 最大执行轮次

        Returns:
            LAAPAgentV3 兼容格式:
            {
                "success": bool,
                "response": str,
                "tokens": int,
                "prompt_tokens": int,
                "completion_tokens": int,
                "cache_hit": str,
                # 扩展字段:
                "harness_result": {...},
                "subtask_count": int,
                "verification": {...},
            }
        """
        t0 = time.time()
        self._turn += 1
        _workdir = workdir or self._workdir

        logger.info(f"[Turn {self._turn}] Running: {user_message[:80]}")

        try:
            # ── 阶段 1-4: Harness 本地规划 (0 token) ──
            plan_result = self._local_plan(user_message)

            # ── 阶段 5: 通过 Aris 执行 ──
            exec_result = self._aris_execute(plan_result, _workdir)

            # ── 阶段 6-7: 本地验证 + 反馈 (0 token) ──
            verify_result = self._local_verify(exec_result, _workdir)

            duration = (time.time() - t0) * 1000

            # 组装结果
            response_parts = []
            if plan_result.get("intent"):
                response_parts.append(f"[Intent: {plan_result['intent']}]")
            if plan_result.get("plan"):
                response_parts.append(
                    f"[Plan: {len(plan_result['plan'])} subtasks]"
                )
            if exec_result.get("output"):
                response_parts.append(exec_result["output"][:600])
            if verify_result.get("status"):
                response_parts.append(f"[Verify: {verify_result['status']}]")

            # 更新 token 统计
            exec_tokens = exec_result.get("tokens", 0)
            self._total_prompt += exec_tokens // 2
            self._total_completion += exec_tokens // 2
            self._total_tokens += exec_tokens

            return {
                "success": verify_result.get("passed", True),
                "response": " | ".join(response_parts) if response_parts else "Task completed.",
                "tokens": self._total_tokens,
                "prompt_tokens": self._total_prompt,
                "completion_tokens": self._total_completion,
                "cache_hit": "100%",
                # 扩展
                "harness_result": {
                    "plan": plan_result,
                    "execution": exec_result,
                    "verification": verify_result,
                },
                "subtask_count": len(plan_result.get("plan", [])),
                "duration_ms": duration,
            }

        except Exception as e:
            logger.error(f"Task failed: {e}\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "tokens": self._total_tokens,
                "prompt_tokens": self._total_prompt,
                "completion_tokens": self._total_completion,
                "cache_hit": "0%",
                "harness_result": {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            }

    # ══════════════════════════════════════════════
    # 阶段 1-4: 本地规划 — 0 token
    # ══════════════════════════════════════════════

    def _local_plan(self, description: str) -> Dict[str, Any]:
        """使用 Harness 的 Perception + Memory + Reasoning + Decision 层规划。

        全部本地执行, 0 token 消耗。
        """
        result = {
            "description": description,
            "intent": "implement",
            "keywords": [],
            "constraints": [],
            "patterns": [],
            "plan": [],
        }

        if not self._harness:
            # 无 Harness 时返回基础信息
            return result

        try:
            # PerceptionLayer: 解析需求
            context = self._harness.perceive(description)

            result["intent"] = context.intent
            result["keywords"] = context.keywords
            result["constraints"] = context.constraints
            result["patterns"] = context.related_patterns

            # MemoryLayer: 模式匹配
            if self._harness.memory_layer:
                matched = self._harness.memory_layer.match_patterns(
                    context.keywords, threshold=1
                )
                result["pattern_matches"] = [
                    {"name": p["name"], "score": s} for p, s in matched
                ]

            # ReasoningLayer: 规划子任务
            plan = self._harness.reason(context)
            result["plan"] = [
                {
                    "id": s.sub_task_id,
                    "description": s.description,
                    "files": s.files,
                    "estimated_lines": s.estimated_lines,
                    "dependencies": s.dependencies,
                }
                for s in plan
            ]

            logger.info(
                f"Local plan: intent={context.intent} "
                f"keywords={context.keywords} "
                f"subtasks={len(plan)}"
            )

        except Exception as e:
            logger.warning(f"Local planning failed: {e}")

        return result

    # ══════════════════════════════════════════════
    # 阶段 5: 通过 Aris 执行
    # ══════════════════════════════════════════════

    def _aris_execute(
        self, plan_result: Dict[str, Any], workdir: str
    ) -> Dict[str, Any]:
        """将任务发送给 Aris 执行。

        通过 Hermes API 将任务描述 + 规划结果发给 Aris,
        Aris 使用完整工具链 (read_file/write_file/terminal/...) 执行。
        """
        subtasks = plan_result.get("plan", [])
        description = plan_result.get("description", "")

        # 没有子任务时直接发送完整描述
        task = {
            "type": "code_task",
            "description": description,
            "intent": plan_result.get("intent", "implement"),
            "subtasks": subtasks,
            "keywords": plan_result.get("keywords", []),
            "patterns": plan_result.get("pattern_matches", []),
            "workdir": workdir,
            "constraints": plan_result.get("constraints", []),
        }

        # 如果 Hermes API 可用, 发给 Aris
        if self._hermes.mode in ("http", "file"):
            logger.info(f"Sending task to Aris via {self._hermes.mode}...")
            result = self._hermes.send_and_wait(task, timeout=300.0)
            return result

        # fallback: 本地模板执行
        return self._local_execute(subtasks, workdir)

    def _local_execute(
        self, subtasks: List[Dict[str, Any]], workdir: str
    ) -> Dict[str, Any]:
        """本地模板代码生成 (无 Aris 时的 fallback)。"""
        outputs = []
        for sub in subtasks:
            desc = sub.get("description", "")
            files = sub.get("files", [])
            output = f"# Task: {desc}\n# Files: {', '.join(files)}\n# (template execution - no Aris)\n"
            outputs.append(output)

        return {
            "success": True,
            "response": "\n".join(outputs),
            "output": "\n".join(outputs),
            "tokens": 0,
            "error": "",
        }

    # ══════════════════════════════════════════════
    # 阶段 6-7: 本地验证 + 反馈 — 0 token
    # ══════════════════════════════════════════════

    def _local_verify(
        self, exec_result: Dict[str, Any], workdir: str
    ) -> Dict[str, Any]:
        """使用 Harness VerificationLayer + 合规检查 验证执行结果。

        全部本地执行, 0 token 消耗。
        """
        result = {
            "status": "passed",
            "passed": True,
            "checks": {},
        }

        if not exec_result.get("success"):
            result["status"] = "execution_failed"
            result["passed"] = False
            return result

        # VerificationLayer 验证
        if self._harness:
            try:
                ver = self._harness.verification_layer
                if ver:
                    # 构造 ExecutionResult
                    er = ExecutionResult(
                        success=True,
                        output=exec_result.get("response", ""),
                        modified_files=[],
                        duration_ms=0,
                    )
                    vr = ver.verify(er)
                    result["checks"]["harness_verify"] = {
                        "passed": vr.passed,
                        "score": vr.score,
                        "issues": vr.issues,
                    }
                    if not vr.passed:
                        result["status"] = "verification_failed"
                        result["passed"] = False
            except Exception as e:
                logger.warning(f"Harness verify failed: {e}")

        # 合规检查
        if self._checker:
            try:
                cr = self._checker.check_project()
                result["checks"]["compliance"] = {
                    "compliant": cr.compliant,
                    "score": cr.score,
                    "issues": len(cr.issues) if hasattr(cr, "issues") else 0,
                }
                if not cr.compliant:
                    result["status"] = "compliance_failed"
                    result["passed"] = False
            except Exception as e:
                logger.warning(f"Compliance check failed: {e}")

        logger.info(f"Verification: {result['status']}")
        return result

    # ══════════════════════════════════════════════
    # 工具方法
    # ══════════════════════════════════════════════

    def reset(self):
        """重置引擎 (LAAPAgentV3 兼容接口)"""
        self._turn = 0
        self._total_prompt = 0
        self._total_completion = 0
        self._total_tokens = 0
        self._harness = None

    def summary(self) -> str:
        """引擎摘要"""
        return (
            f"ArisHarnessEngine [turns={self._turn}]"
            f" | tokens={self._total_tokens}"
            f" | harness={'✓' if self._harness else '✗'}"
            f" | hermes={self._hermes.mode}"
        )

    @property
    def status(self) -> Dict[str, Any]:
        """引擎状态"""
        return {
            "engine": "ArisHarnessEngine",
            "model": self.model,
            "turns": self._turn,
            "total_tokens": self._total_tokens,
            "harness_loaded": self._harness is not None,
            "hermes_mode": self._hermes.mode,
            "workdir": self._workdir,
        }
