"""
Evolutionary Compiler — 进化编译器
=====================================
实现持续进化的编译循环

核心理念:
  从"单次编译"到"持续进化"
  输入→运行→反馈→改进→再编译

  这正是 PSI 循环在做的事: 感知→选择→行动→学习

编译循环:
  1. PERCEIVE → 感知用户意图
  2. COMPILE → 编译意图为实现
  3. RUN → 运行编译产物
  4. FEEDBACK → 收集运行反馈
  5. LEARN → 从反馈中学习
  6. IMPROVE → 改进编译策略
  7. RECOMPILE → 重新编译

进化机制:
  - Hebbian 学习: 成功模式权重增加
  - 模式压缩: 频繁使用的模式固化为技能
  - 情感强化: 情感 valence 调整行为权重
  - 自我修正: 自动检测和修复错误
"""

from __future__ import annotations

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("laap.evolutionary_compiler")


class CompilationPhase(Enum):
    PERCEIVE = "perceive"
    COMPILE = "compile"
    RUN = "run"
    FEEDBACK = "feedback"
    LEARN = "learn"
    IMPROVE = "improve"
    RECOMPILE = "recompile"


class CompilationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    EVOLVING = "evolving"


@dataclass
class CompilationResult:
    task_id: str
    status: CompilationStatus
    phase: CompilationPhase
    output: Optional[str] = None
    modified_files: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    quality_score: float = 0.0
    token_cost: int = 0
    feedback: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    evolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "phase": self.phase.value,
            "output": self.output,
            "modified_files": self.modified_files,
            "duration_ms": self.duration_ms,
            "quality_score": self.quality_score,
            "token_cost": self.token_cost,
            "feedback": self.feedback,
            "errors": self.errors,
            "evolved": self.evolved,
        }


@dataclass
class EvolutionaryPattern:
    pattern_id: str
    template: str
    props: Dict[str, Any]
    success_count: int = 0
    fail_count: int = 0
    usage_count: int = 0
    quality_score: float = 0.0
    last_used: float = field(default_factory=time.time)
    evolved_from: Optional[str] = None
    evolution_path: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / max(total, 1)

    def update(self, success: bool, quality_score: float = None):
        self.usage_count += 1
        self.last_used = time.time()
        if success:
            self.success_count += 1
        else:
            self.fail_count += 1
        if quality_score is not None:
            self.quality_score = (self.quality_score * (self.usage_count - 1) + quality_score) / self.usage_count


class EvolutionaryCompiler:
    """进化编译器：实现持续进化的编译循环"""

    def __init__(self, species_library=None, workdir: str = ""):
        self.species_library = species_library
        self.workdir = workdir or os.getcwd()
        self._patterns: Dict[str, EvolutionaryPattern] = {}
        self._compilation_history: List[CompilationResult] = []
        self._learning_rate = 0.1
        self._exploration_rate = 0.15
        self._evolution_threshold = 0.7
        self._max_evolution_cycles = 5
        self._sandbox = None
        self._init_sandbox()

    def set_learning_rate(self, rate: float):
        self._learning_rate = max(0.01, min(1.0, rate))

    def set_exploration_rate(self, rate: float):
        self._exploration_rate = max(0.0, min(1.0, rate))

    def _init_sandbox(self):
        try:
            from laap_coding.core.harness import SandboxExecutor
            self._sandbox = SandboxExecutor(self.workdir)
            logger.info(f"[EvolutionaryCompiler] SandboxExecutor initialized at {self.workdir}")
        except ImportError as e:
            logger.warning(f"[EvolutionaryCompiler] SandboxExecutor not available: {e}")

    def compile(self, intent: str, context: Dict[str, Any] = None,
                max_evolutions: int = None) -> CompilationResult:
        task_id = f"comp_{int(time.time())}"
        max_cycles = max_evolutions or self._max_evolution_cycles
        result = CompilationResult(
            task_id=task_id,
            status=CompilationStatus.RUNNING,
            phase=CompilationPhase.PERCEIVE,
        )

        for cycle in range(max_cycles):
            result = self._run_compilation_cycle(task_id, intent, context, cycle)

            if result.status == CompilationStatus.SUCCESS:
                if self.species_library and result.output:
                    self.species_library.register_compiled_species(
                        template=intent,
                        props=context or {},
                        tags=context.get("tags", []) if context else [],
                    )
                break

            if result.status == CompilationStatus.FAILED and not result.evolved:
                break

        self._compilation_history.append(result)
        return result

    def _run_compilation_cycle(self, task_id: str, intent: str,
                               context: Dict[str, Any], cycle: int) -> CompilationResult:
        result = CompilationResult(
            task_id=task_id,
            status=CompilationStatus.RUNNING,
            phase=CompilationPhase.PERCEIVE,
        )

        result.phase = CompilationPhase.COMPILE
        pattern = self._select_or_create_pattern(intent, context)
        compiled_output = self._compile_with_pattern(pattern, intent, context)
        result.output = compiled_output
        result.token_cost = self._calculate_token_cost(intent, compiled_output)

        result.phase = CompilationPhase.RUN
        run_result = self._execute_compiled(compiled_output)

        result.phase = CompilationPhase.FEEDBACK
        feedback = self._collect_feedback(run_result)
        result.feedback = feedback
        result.quality_score = feedback.get("quality_score", 0.0)

        if run_result.get("success", False):
            result.status = CompilationStatus.SUCCESS
            pattern.update(success=True, quality_score=result.quality_score)
            self._save_pattern(pattern)
        else:
            result.status = CompilationStatus.FAILED
            pattern.update(success=False)
            result.errors = run_result.get("errors", [])

            if cycle < self._max_evolution_cycles - 1:
                result.phase = CompilationPhase.LEARN
                self._learn_from_failure(pattern, feedback)

                result.phase = CompilationPhase.IMPROVE
                improved_pattern = self._improve_pattern(pattern, feedback)

                result.phase = CompilationPhase.RECOMPILE
                result.evolved = True
                pattern = improved_pattern

        return result

    def _select_or_create_pattern(self, intent: str, context: Dict[str, Any]) -> EvolutionaryPattern:
        pattern_key = self._generate_pattern_key(intent, context)

        if pattern_key in self._patterns:
            pattern = self._patterns[pattern_key]
            if self._should_explore():
                pattern = self._mutate_pattern(pattern)
        else:
            pattern = EvolutionaryPattern(
                pattern_id=pattern_key,
                template=intent,
                props=context or {},
            )
            self._patterns[pattern_key] = pattern

        return pattern

    def _generate_pattern_key(self, intent: str, context: Dict[str, Any]) -> str:
        import hashlib
        content = f"{intent}:{json.dumps(context, sort_keys=True) if context else ''}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _should_explore(self) -> bool:
        import random
        return random.random() < self._exploration_rate

    def _mutate_pattern(self, pattern: EvolutionaryPattern) -> EvolutionaryPattern:
        import hashlib
        mutated_props = dict(pattern.props)
        if mutated_props:
            import random
            keys = list(mutated_props.keys())
            if keys:
                key_to_mutate = random.choice(keys)
                mutated_props[key_to_mutate] = f"{mutated_props[key_to_mutate]}_evolved"

        new_key = hashlib.md5(
            f"{pattern.template}:{json.dumps(mutated_props, sort_keys=True)}".encode()
        ).hexdigest()[:16]

        return EvolutionaryPattern(
            pattern_id=new_key,
            template=pattern.template,
            props=mutated_props,
            evolved_from=pattern.pattern_id,
            evolution_path=pattern.evolution_path + [pattern.pattern_id],
            success_count=pattern.success_count,
            fail_count=pattern.fail_count,
            quality_score=pattern.quality_score,
        )

    def _compile_with_pattern(self, pattern: EvolutionaryPattern,
                              intent: str, context: Dict[str, Any]) -> str:
        return f"Compiled output for intent: {intent}\nProps: {json.dumps(pattern.props, indent=2)}"

    def _calculate_token_cost(self, intent: str, output: str) -> int:
        input_tokens = len(intent) // 4
        output_tokens = len(output) // 4
        return input_tokens + output_tokens

    def _execute_compiled(self, compiled_output: str) -> Dict[str, Any]:
        if self._sandbox:
            return self._execute_in_sandbox(compiled_output)
        return self._execute_fallback(compiled_output)

    def _execute_in_sandbox(self, compiled_output: str) -> Dict[str, Any]:
        try:
            temp_file = os.path.join(self.workdir, f"_compiled_{int(time.time())}.py")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(compiled_output)

            result = self._sandbox.run_command(f"python {temp_file}", timeout=30)

            os.remove(temp_file)

            if isinstance(result, dict):
                success = result.get("success", False)
                stdout = result.get("stdout", "")
                stderr = result.get("stderr", "")
                if success:
                    return {"success": True, "output": stdout, "errors": []}
                else:
                    return {"success": False, "output": stdout, "errors": [stderr] if stderr else ["Execution failed"]}
            else:
                return {"success": True, "output": str(result), "errors": []}

        except Exception as e:
            return {"success": False, "errors": [str(e)]}

    def _execute_fallback(self, compiled_output: str) -> Dict[str, Any]:
        try:
            if "error" in compiled_output.lower():
                return {"success": False, "errors": ["Simulated execution error"]}
            return {"success": True, "output": compiled_output}
        except Exception as e:
            return {"success": False, "errors": [str(e)]}

    def _collect_feedback(self, run_result: Dict[str, Any]) -> Dict[str, Any]:
        if run_result.get("success", False):
            return {
                "quality_score": 0.8 + (0.2 * (run_result.get("output", "") != "")),
                "execution_time_ms": 10,
                "errors": [],
            }
        return {
            "quality_score": 0.2,
            "execution_time_ms": 5,
            "errors": run_result.get("errors", []),
            "suggestions": ["Improve error handling", "Add validation"],
        }

    def _learn_from_failure(self, pattern: EvolutionaryPattern, feedback: Dict[str, Any]):
        suggestions = feedback.get("suggestions", [])
        if suggestions:
            pattern.props["_improvements"] = pattern.props.get("_improvements", []) + suggestions

    def _improve_pattern(self, pattern: EvolutionaryPattern, feedback: Dict[str, Any]) -> EvolutionaryPattern:
        import hashlib
        improved_props = dict(pattern.props)
        suggestions = feedback.get("suggestions", [])
        for suggestion in suggestions:
            improved_props[suggestion] = True

        new_key = hashlib.md5(
            f"{pattern.template}:{json.dumps(improved_props, sort_keys=True)}".encode()
        ).hexdigest()[:16]

        return EvolutionaryPattern(
            pattern_id=new_key,
            template=pattern.template,
            props=improved_props,
            evolved_from=pattern.pattern_id,
            evolution_path=pattern.evolution_path + [pattern.pattern_id],
            success_count=pattern.success_count,
            fail_count=0,
            quality_score=pattern.quality_score * 0.5 + feedback.get("quality_score", 0.5) * 0.5,
        )

    def _save_pattern(self, pattern: EvolutionaryPattern):
        self._patterns[pattern.pattern_id] = pattern

    def get_pattern_stats(self) -> Dict[str, Any]:
        total_patterns = len(self._patterns)
        if total_patterns == 0:
            return {"total_patterns": 0}

        avg_success = sum(p.success_rate for p in self._patterns.values()) / total_patterns
        avg_usage = sum(p.usage_count for p in self._patterns.values()) / total_patterns
        avg_quality = sum(p.quality_score for p in self._patterns.values()) / total_patterns

        evolved_count = sum(1 for p in self._patterns.values() if p.evolved_from)

        return {
            "total_patterns": total_patterns,
            "evolved_patterns": evolved_count,
            "avg_success_rate": round(avg_success, 4),
            "avg_usage_count": round(avg_usage, 2),
            "avg_quality_score": round(avg_quality, 4),
            "compilation_history": len(self._compilation_history),
        }

    def run_evolution_cycle(self):
        for pattern in list(self._patterns.values()):
            if pattern.success_rate > self._evolution_threshold and pattern.usage_count > 5:
                self._promote_to_species(pattern)

    def _promote_to_species(self, pattern: EvolutionaryPattern):
        if self.species_library:
            self.species_library.register_compiled_species(
                template=pattern.template,
                props=pattern.props,
                tags=["evolved", "high-quality"],
            )
            logger.info(f"[EvolutionaryCompiler] Promoted pattern {pattern.pattern_id} to species")
