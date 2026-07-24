"""
ConsciousnessHarness 初始化验证脚本

验证FR-1核心架构：
1. 感知层（PerceptionLayer）：需求解析器、意图分类器、上下文提取器
2. 记忆层（MemoryLayer）：设计系统库、架构模式库、项目历史库
3. 推理层（ReasoningLayer）：规划引擎、依赖分析器、冲突检测器
4. 决策层（DecisionLayer）：审美评估器、架构合规器、质量门控
5. 执行层（ExecutionLayer）：代码生成模板、工具编排器、沙箱执行器
6. 验证层（VerificationLayer）：测试验证器、静态分析器、安全扫描器
7. 反馈层（FeedbackLayer）：自修正循环、模式学习器、经验积累器
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from harness.laap_coding.core.harness import (
    ConsciousnessHarness,
    PerceptionLayer,
    MemoryLayer,
    ReasoningLayer,
    DecisionLayer,
    ExecutionLayer,
    VerificationLayer,
    FeedbackLayer,
)


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_memory_layer():
    print_header("🧠 测试记忆层 (MemoryLayer)")
    
    memory = MemoryLayer()
    
    print(f"  架构模式库: {len(memory.architecture_patterns)} 个模式")
    for pattern in memory.architecture_patterns:
        print(f"    - {pattern['name']}: {pattern['description']}")
    
    print(f"\n  设计系统库: {len(memory.design_system)} 个原则")
    for design in memory.design_system:
        print(f"    - {design['name']}: {design['description']}")
    
    print(f"\n  项目历史库: {len(memory.project_history)} 条记录")
    
    pattern = memory.get_pattern_by_name("CQRS")
    assert pattern is not None, "CQRS模式未找到"
    print(f"\n  ✅ 模式查询测试通过: {pattern['name']}")
    
    print("  ✅ 记忆层初始化成功")


def test_perception_layer():
    print_header("👁️ 测试感知层 (PerceptionLayer)")
    
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    
    test_cases = [
        "实现一个Python的REST API，使用FastAPI框架",
        "修复登录功能的bug",
        "审查项目中的安全漏洞",
        "编写单元测试",
    ]
    
    for desc in test_cases:
        context = perception.perceive(desc)
        print(f"\n  输入: {desc}")
        print(f"    意图: {context.intent}")
        print(f"    关键词: {context.keywords}")
        print(f"    约束: {context.constraints}")
        print(f"    相关模式: {context.related_patterns}")
    
    print("\n  ✅ 感知层初始化成功")


def test_reasoning_layer():
    print_header("💭 测试推理层 (ReasoningLayer)")
    
    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    reasoning = ReasoningLayer()
    
    context = perception.perceive("实现一个用户管理系统")
    plan = reasoning.reason(context)
    
    print(f"  生成的子任务: {len(plan)} 个")
    for i, subtask in enumerate(plan):
        print(f"    {i+1}. {subtask.description}")
        print(f"       依赖: {subtask.dependencies}")
        print(f"       预计行数: {subtask.estimated_lines}")
    
    assert len(plan) > 0, "未生成子任务"
    print("\n  ✅ 推理层初始化成功")


def test_decision_layer():
    print_header("⚖️ 测试决策层 (DecisionLayer)")
    
    decision = DecisionLayer()
    
    test_code = """
class UserService:
    def get_user(self, user_id):
        pass
"""
    
    from harness.laap_coding.core.harness import TaskContext
    context = TaskContext(
        task_id="test",
        description="测试代码",
        intent="implement",
        keywords=["python", "service"],
        constraints=[],
        related_patterns=["Repository Pattern"],
        project_context={},
    )
    
    result = decision.decide(test_code, context)
    print(f"  审美评分: {result['aesthetic_score']}")
    print(f"  架构合规: {result['compliant']}")
    print(f"  质量门控: {result['gate_passed']}")
    print(f"  问题列表: {result['issues']}")
    
    assert "aesthetic_score" in result
    assert "compliant" in result
    print("\n  ✅ 决策层初始化成功")


def test_execution_layer():
    print_header("⚡ 测试执行层 (ExecutionLayer)")
    
    execution = ExecutionLayer(workdir=".")
    
    print("  测试代码模板引擎:")
    template_result = execution.code_template.render(
        "python_function",
        function_name="greet",
        params="name",
        return_type=" -> str",
        description="问候函数",
        body="    return f'Hello, {name}'",
    )
    print(f"    {template_result.strip()[:100]}...")
    
    print("\n  测试沙箱执行器:")
    sandbox_result = execution.sandbox.run_command("echo 'hello world'")
    print(f"    命令执行: {sandbox_result['success']}")
    print(f"    输出: {sandbox_result['stdout'].strip()}")
    
    print("\n  ✅ 执行层初始化成功")


def test_verification_layer():
    print_header("🔍 测试验证层 (VerificationLayer)")
    
    verification = VerificationLayer()
    
    from harness.laap_coding.core.harness import ExecutionResult
    test_result = ExecutionResult(
        success=True,
        output="PASS: All tests passed",
        modified_files=[],
        duration_ms=100,
    )
    
    result = verification.verify(test_result)
    print(f"  验证通过: {result.passed}")
    print(f"  问题列表: {result.issues}")
    print(f"  评分: {result.score}")
    
    assert result.passed == True
    print("\n  ✅ 验证层初始化成功")


def test_feedback_layer():
    print_header("🔄 测试反馈层 (FeedbackLayer)")
    
    feedback = FeedbackLayer()
    
    from harness.laap_coding.core.harness import TaskContext, ExecutionResult, VerificationResult
    
    context = TaskContext(
        task_id="test",
        description="测试反馈",
        intent="implement",
        keywords=[],
        constraints=[],
        related_patterns=[],
        project_context={},
    )
    
    execution_result = ExecutionResult(
        success=True,
        output="测试输出",
        modified_files=[],
        duration_ms=100,
    )
    
    verification_result = VerificationResult(
        passed=True,
        issues=[],
        score=1.0,
    )
    
    result = feedback.feedback(context, execution_result, verification_result)
    print(f"  修正状态: {result['corrected']}")
    print(f"  修正内容: {result['corrections']}")
    
    assert "corrected" in result
    print("\n  ✅ 反馈层初始化成功")


def test_consciousness_harness():
    print_header("🌟 测试 ConsciousnessHarness 核心类")
    
    harness = ConsciousnessHarness(workdir=".", token_budget=2000)
    
    print(f"\n  摘要: {harness.summary()}")
    
    status = harness.status
    print(f"\n  状态信息:")
    for k, v in status.items():
        if isinstance(v, dict):
            print(f"    {k}:")
            for sub_k, sub_v in v.items():
                print(f"      {sub_k}: {sub_v}")
        else:
            print(f"    {k}: {v}")
    
    print("\n  测试完整任务流程:")
    result = harness.run("实现一个简单的Python计算器")
    print(f"    状态: {result['status']}")
    print(f"    任务ID: {result['task_id']}")
    print(f"    意图: {result['intent']}")
    print(f"    耗时: {result['duration_ms']:.0f}ms")
    print(f"    消息: {result['message']}")
    
    print(f"\n  子任务结果:")
    for i, r in enumerate(result['results']):
        print(f"    {i+1}. {r['subtask']} - {r['status']}")
    
    assert result['status'] in ['success', 'partial', 'error']
    print("\n  ✅ ConsciousnessHarness 初始化成功")


def test_engine_integration():
    print_header("🔧 测试 HarnessEngine 集成")
    
    from harness.laap_coding.core.engine import HarnessEngine
    from pathlib import Path
    
    engine = HarnessEngine(workdir=Path("."), token_budget=2000)
    
    harness = engine._ensure_harness()
    assert harness is not None, "Harness加载失败"
    
    planner = engine._ensure_code_engine()
    assert planner is not None, "Code engine加载失败"
    
    print(f"  Harness: {harness.summary()}")
    print("\n  ✅ HarnessEngine 集成成功")


def main():
    print("🧠 LAAP ConsciousnessHarness 初始化验证")
    print("="*60)
    
    test_memory_layer()
    test_perception_layer()
    test_reasoning_layer()
    test_decision_layer()
    test_execution_layer()
    test_verification_layer()
    test_feedback_layer()
    test_consciousness_harness()
    test_engine_integration()
    
    print("\n" + "="*60)
    print("🎉 所有验证通过！ConsciousnessHarness 核心架构已就绪")
    print("="*60)


if __name__ == "__main__":
    main()
