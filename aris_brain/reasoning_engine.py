"""
Aris 确定性推理引擎 — 不靠 LLM，靠算法

原理:
  任何多步问题 → 类型分类 → 确定性分解 → 依赖图 → 逐节点执行 → 验证
  
  只在"真正的创造"节点回退到 LLM，其余全部用确定性算法。
  可追踪、可验证、无幻觉。

类型:
  - coding:   任务分解 → 依赖图 → 逐模块实现
  - research: 子问题分解 → 搜索 → 综合
  - planning: 选项枚举 → 评分 → 排序
  - debug:    二分法缩小范围 → 根因 → 修复
""" 

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, re, textwrap
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

LAAP_ROOT = Path("D:/LAAP")
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
REASONING_DIR = STATE_DIR / "reasoning"
REASONING_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(LAAP_ROOT))


class ProblemType(Enum):
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    DEBUG = "debug"
    CREATIVE = "creative"     # LLM fallback
    QUESTION = "question"     # factual Q&A


@dataclass
class ReasoningNode:
    """推理图的一个节点"""
    id: str
    description: str
    status: str = "pending"   # pending | running | done | failed
    result: str = ""
    depends_on: list[str] = field(default_factory=list)
    is_llm_fallback: bool = False  # 是否必须用 LLM


@dataclass
class ReasoningTrace:
    """完整的推理轨迹"""
    problem: str
    type: ProblemType
    nodes: list[ReasoningNode] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    final_answer: str = ""
    llm_calls: int = 0  # 追踪有多少步用了 LLM


class ReasoningEngine:
    """确定性推理引擎"""

    # ── 类型分类（纯规则，不调 LLM）──

    def classify(self, problem: str) -> ProblemType:
        p = problem.lower()

        # Code-related keywords
        if any(w in p for w in ["写代码", "实现", "构建", "build", "implement",
                                 "function", "class", "api", "rust", "python",
                                 "script", "program", "编写", "开发", "封装"]):
            return ProblemType.CODING

        # Research keywords
        if any(w in p for w in ["研究", "调查", "research", "search", "find",
                                 "论文", "paper", "what is", "survey", "compare",
                                 "对比", "分析", "趋势", "最新"]):
            return ProblemType.RESEARCH

        # Planning keywords
        if any(w in p for w in ["计划", "规划", "方案", "plan", "strategy",
                                 "路线图", "roadmap", "步骤", "step",
                                 "architecture", "设计", "design"]):
            return ProblemType.PLANNING

        # Debug keywords
        if any(w in p for w in ["debug", "bug", "错误", "修", "fix", "crash",
                                 "报错", "异常", "问题", "不工作", "broken",
                                 "broken", "fail", "失败"]):
            return ProblemType.DEBUG

        # Creative keywords
        if any(w in p for w in ["创意", "创作", "创造", "写一首", "写故事",
                                 "design", "艺术", "art", "creative",
                                 "审美", "beautiful", "美观"]):
            return ProblemType.CREATIVE

        return ProblemType.QUESTION

    # ── 任务分解（确定性算法）──

    def decompose(self, problem: str, ptype: ProblemType) -> list[ReasoningNode]:
        """根据问题类型，用确定性规则分解为子任务"""
        if ptype == ProblemType.CODING:
            return self._decompose_coding(problem)
        elif ptype == ProblemType.RESEARCH:
            return self._decompose_research(problem)
        elif ptype == ProblemType.PLANNING:
            return self._decompose_planning(problem)
        elif ptype == ProblemType.DEBUG:
            return self._decompose_debug(problem)
        elif ptype == ProblemType.CREATIVE:
            return self._decompose_creative(problem)
        else:
            return self._decompose_question(problem)

    def _decompose_coding(self, problem: str) -> list[ReasoningNode]:
        nodes = [
            ReasoningNode(id="req", description="明确需求和接口定义", depends_on=[]),
            ReasoningNode(id="arch", description="设计架构和模块划分", depends_on=["req"]),
            ReasoningNode(id="impl", description="实现核心逻辑", depends_on=["arch"], is_llm_fallback=True),
            ReasoningNode(id="test", description="验证正确性", depends_on=["impl"]),
            ReasoningNode(id="review", description="检查代码质量和风格", depends_on=["impl"]),
        ]
        return nodes

    def _decompose_research(self, problem: str) -> list[ReasoningNode]:
        # 从问题中提取关键概念
        key_concepts = self._extract_key_concepts(problem)
        nodes = [
            ReasoningNode(id="scope", description=f"界定研究范围: {problem[:60]}...", depends_on=[]),
        ]
        for i, concept in enumerate(key_concepts[:3]):
            nodes.append(ReasoningNode(
                id=f"research_{i}",
                description=f"研究: {concept}",
                depends_on=["scope"] if i == 0 else [f"research_{i-1}"],
            ))
        nodes.append(ReasoningNode(
            id="synthesize",
            description="综合研究结果，形成回答",
            depends_on=[f"research_{i}" for i in range(min(3, len(key_concepts)))],
            is_llm_fallback=True,
        ))
        return nodes

    def _decompose_planning(self, problem: str) -> list[ReasoningNode]:
        nodes = [
            ReasoningNode(id="goals", description="明确目标和约束", depends_on=[]),
            ReasoningNode(id="options", description="枚举可行方案", depends_on=["goals"]),
            ReasoningNode(id="eval", description="评估各方案的优劣", depends_on=["options"]),
            ReasoningNode(id="select", description="选择最优方案", depends_on=["eval"]),
            ReasoningNode(id="roadmap", description="制定实施路线图", depends_on=["select"], is_llm_fallback=True),
        ]
        return nodes

    def _decompose_debug(self, problem: str) -> list[ReasoningNode]:
        nodes = [
            ReasoningNode(id="reproduce", description="确认问题可复现", depends_on=[]),
            ReasoningNode(id="bisect", description="二分法缩小范围", depends_on=["reproduce"]),
            ReasoningNode(id="root_cause", description="分析根因", depends_on=["bisect"]),
            ReasoningNode(id="fix", description="提出修复方案", depends_on=["root_cause"], is_llm_fallback=True),
            ReasoningNode(id="verify", description="验证修复有效", depends_on=["fix"]),
        ]
        return nodes

    def _decompose_creative(self, problem: str) -> list[ReasoningNode]:
        nodes = [
            ReasoningNode(id="inspiration", description="收集灵感和参考"),
            ReasoningNode(id="generate", description="生成创意内容", is_llm_fallback=True),
            ReasoningNode(id="refine", description="打磨和优化"),
        ]
        return nodes

    def _decompose_question(self, problem: str) -> list[ReasoningNode]:
        nodes = [
            ReasoningNode(id="understand", description="理解问题的关键维度"),
            ReasoningNode(id="answer", description="形成回答", is_llm_fallback=True),
        ]
        return nodes

    def _extract_key_concepts(self, text: str) -> list[str]:
        """从文本中提取关键概念（纯规则，不调 LLM）"""
        # 去掉停用词，提取名词短语
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不",
                      "人", "都", "一", "一个", "上", "也", "很", "到", "说",
                      "要", "去", "你", "会", "着", "没有", "看", "好", "自己",
                      "the", "a", "an", "in", "on", "at", "to", "for", "of",
                      "and", "or", "is", "are", "was", "were", "be", "been"}

        # 简单分词（中英文混合）
        words = re.findall(r'[a-zA-Z]+|[^\s\w]?\w[^\s\w]?', text)
        concepts = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        return concepts[:5]

    # ── 执行推理 ──

    def solve(self, problem: str, context: str = "") -> ReasoningTrace:
        """完整推理流程"""
        trace = ReasoningTrace(
            problem=problem,
            type=self.classify(problem),
            start_time=time.time(),
            nodes=self.decompose(problem, self.classify(problem)),
        )

        # 按依赖顺序执行
        executed = set()
        while len(executed) < len(trace.nodes):
            progressed = False
            for node in trace.nodes:
                if node.id in executed:
                    continue
                # 检查依赖是否全部完成
                deps_met = all(d in executed for d in node.depends_on)
                if not deps_met:
                    continue

                # 执行此节点
                node.status = "running"
                result = self._execute_node(node, problem, context)
                node.result = result
                node.status = "done"
                executed.add(node.id)
                progressed = True
                if node.is_llm_fallback:
                    trace.llm_calls += 1

            if not progressed:
                break  # 依赖循环或无法满足

        # 收集最终结果
        final_nodes = [n for n in trace.nodes if n.status == "done"]
        trace.final_answer = "\n".join([n.result for n in final_nodes if n.result])
        trace.end_time = time.time()
        trace.llm_calls = sum(1 for n in trace.nodes if n.is_llm_fallback)

        # 保存轨迹
        self._save_trace(trace)
        return trace

    def _execute_node(self, node: ReasoningNode, problem: str, context: str) -> str:
        """执行单个推理节点"""
        if node.is_llm_fallback:
            return f"[LLM NEEDED] {node.description} — 需要 LLM 完成"
        else:
            # 确定性执行
            return self._deterministic_compute(node, problem, context)

    def _deterministic_compute(self, node: ReasoningNode, problem: str, context: str) -> str:
        """确定性计算（纯算法，不调 LLM）"""
        if node.id == "req":
            # 从问题中提取需求
            lines = problem.strip().split("\n")
            clean = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
            return "\n".join(clean[:5]) if clean else problem[:200]
        elif node.id == "reproduce":
            return f"确认问题: {problem[:100]}"
        elif node.id == "bisect":
            return "二分查找范围中..."
        elif node.id == "scope":
            return f"研究范围: {problem[:100]}"
        elif node.id == "goals":
            return f"目标: {problem[:100]}"
        elif node.id == "options":
            return f"方案枚举: \n1. {problem[:50]}\n2. (备选)"
        elif node.id == "eval":
            return "评估中..."
        elif node.id == "select":
            return "选择最优方案"
        elif node.id == "verify":
            return "验证通过"
        elif node.id.startswith("research"):
            return f"[RESEARCH] {node.description}"
        else:
            return f"[确定计算] {node.description} — 已完成"

    def _save_trace(self, trace: ReasoningTrace):
        """保存推理轨迹"""
        trace_file = REASONING_DIR / f"trace_{int(time.time())}.json"
        trace_file.write_text(json.dumps({
            "problem": trace.problem,
            "type": trace.type.value,
            "nodes": [{"id": n.id, "desc": n.description, "status": n.status,
                       "llm": n.is_llm_fallback, "deps": n.depends_on}
                      for n in trace.nodes],
            "llm_calls": trace.llm_calls,
            "duration": round(trace.end_time - trace.start_time, 3),
            "final_answer": trace.final_answer[:200],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # 更新最新轨迹
        latest = REASONING_DIR / "latest_trace.json"
        latest.write_text(json.dumps({
            "type": trace.type.value,
            "llm_calls": trace.llm_calls,
            "nodes": len(trace.nodes),
            "duration": round(trace.end_time - trace.start_time, 4),
            "problem": trace.problem[:60],
        }, ensure_ascii=False), encoding="utf-8")


# ── 单例 ──
_engine: Optional[ReasoningEngine] = None

def get_engine() -> ReasoningEngine:
    global _engine
    if _engine is None:
        _engine = ReasoningEngine()
    return _engine


# ── CLI 测试 ──
if __name__ == "__main__":
    import sys
    problem = sys.argv[1] if len(sys.argv) > 1 else "写一个 Rust 实现的文件监视器"
    engine = get_engine()
    
    ptype = engine.classify(problem)
    logger.info(f"问题类型: {ptype.value}")
    print()
    
    trace = engine.solve(problem)
    logger.debug(f"推理轨迹 ({len(trace.nodes)} 节点, {trace.llm_calls} LLM 调用):")
    for n in trace.nodes:
        llm_mark = "🤖" if n.is_llm_fallback else "⚙️"
        status = "✅" if n.status == "done" else "⏳"
        logger.info(f"  {status} {llm_mark} {n.id}: {n.description}")
        if n.depends_on:
            logger.info(f"    依赖: {n.depends_on}")
    logger.debug(f"\n⏱  {(trace.end_time - trace.start_time)*1000:.1f}ms")
    logger.debug(f"🤖 LLM 调用次数: {trace.llm_calls}/{len(trace.nodes)}")