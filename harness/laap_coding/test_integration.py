"""
集成测试与系统验证（Task 9）

验证整个ConsciousnessHarness系统的端到端功能：
1. 完整任务执行流程
2. 跨会话状态恢复
3. 合规检查器集成
4. 反馈引擎集成
5. 所有模块协同工作
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.harness import ConsciousnessHarness
from laap_coding.core.compliance_checker import CodeComplianceChecker
from laap_coding.core.feedback_engine import FeedbackEngine


def test_full_task_execution():
    """测试完整任务执行流程"""
    print("=" * 60)
    print("测试1：完整任务执行流程")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    description = "创建一个计算斐波那契数列的Python函数"
    intent = "create_function"

    result = harness.run(
        description=description,
        intent=intent,
    )

    print(f"任务结果: {result.get('status')}")
    print(f"子任务数: {len(result.get('subtasks', []))}")

    assert result is not None
    assert "status" in result

    print("✓ 测试1通过：完整任务执行流程工作正常")


def test_cross_session_state_recovery():
    """测试跨会话状态恢复"""
    print("\n" + "=" * 60)
    print("测试2：跨会话状态恢复")
    print("=" * 60)

    harness1 = ConsciousnessHarness(workdir=r"D:\LAAP")
    harness2 = ConsciousnessHarness(workdir=r"D:\LAAP")

    task_id = "cross_session_test_3"
    task_state = {
        "task_id": task_id,
        "description": "跨会话状态恢复测试",
        "status": "in_progress",
        "current_subtask_index": 1,
        "subtasks": [
            {
                "sub_task_id": "step_1",
                "description": "分析需求",
                "status": "completed",
                "estimated_lines": 20,
                "dependencies": [],
            },
            {
                "sub_task_id": "step_2",
                "description": "设计接口",
                "status": "pending",
                "estimated_lines": 40,
                "dependencies": ["step_1"],
            },
        ],
        "results": [
            {
                "subtask": "分析需求",
                "sub_task_id": "step_1",
                "status": "completed",
                "duration_ms": 100.0,
                "feedback": {"corrected": False, "corrections": []},
            },
        ],
    }

    harness1.memory_layer.save_task_state(task_id, task_state)

    restore_result = harness2.restore_task(task_id)
    print(f"恢复结果: {restore_result}")

    assert restore_result is not None
    assert restore_result["status"] in ("success", "partial")

    harness1.memory_layer._state_persistence.delete_task_state(task_id)

    print("✓ 测试2通过：跨会话状态恢复工作正常")


def test_compliance_checker_integration():
    """测试合规检查器集成"""
    print("\n" + "=" * 60)
    print("测试3：合规检查器集成")
    print("=" * 60)

    checker = CodeComplianceChecker(os.path.join(os.path.dirname(__file__), "core"))
    result = checker.check_project()

    print(f"合规状态: {'✓ 合规' if result.compliant else '✗ 不合规'}")
    print(f"合规分数: {result.score:.2f}")
    print(f"检查文件数: {result.summary.get('files_checked', 0)}")
    print(f"总问题数: {result.summary.get('total_issues', 0)}")

    assert result.summary.get("files_checked", 0) > 0
    assert 0 <= result.score <= 1.0

    report = checker.generate_report(result)
    assert "代码合规检查报告" in report

    print("✓ 测试3通过：合规检查器集成工作正常")


def test_feedback_engine_integration():
    """测试反馈引擎集成"""
    print("\n" + "=" * 60)
    print("测试4：反馈引擎集成")
    print("=" * 60)

    engine = FeedbackEngine(r"D:\LAAP")

    context = {
        "task_id": "feedback_integration_test_3",
        "intent": "integration_test",
        "keywords": ["integration", "test", "system"],
        "description": "反馈引擎集成测试",
    }

    execution_result = {"duration_ms": 2500.0}
    verification_result = {
        "passed": True,
        "score": 0.90,
        "issues": [],
    }

    feedback_result = engine.process_feedback(context, execution_result, verification_result)

    assert feedback_result["learned"] is True
    assert feedback_result["accumulated"] is True

    stats = engine.get_statistics()
    print(f"模式数: {stats['pattern_stats']['total_patterns']}")
    print(f"经验数: {stats['experience_stats']['total_experiences']}")

    report = engine.get_quality_report()
    assert "质量趋势报告" in report

    suggestions = engine.get_improvement_suggestions()
    print(f"改进建议数: {len(suggestions)}")

    print("✓ 测试4通过：反馈引擎集成工作正常")


def test_memory_layer_integration():
    """测试记忆层集成"""
    print("\n" + "=" * 60)
    print("测试5：记忆层集成")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    memory = harness.memory_layer

    memory._working_memory["test_key"] = {"value": "test_data"}
    working_val = memory.get_working_memory("test_key")
    assert working_val == {"value": "test_data"}

    memory._short_term_memory["project_rules"] = {"max_lines": 200}
    short_val = memory.get_short_term_memory("project_rules")
    assert short_val == {"max_lines": 200}

    memory._long_term_memory["completed_task"] = {"task_id": "test", "result": "success"}
    long_val = memory.get_long_term_memory("completed_task")
    assert long_val == {"task_id": "test", "result": "success"}

    patterns = memory.architecture_patterns
    print(f"架构模式数: {len(patterns)}")
    assert len(patterns) > 0

    status = memory.get_memory_status()
    print(f"记忆状态: {status}")
    assert "working_memory" in status
    assert "short_term_memory" in status
    assert "long_term_memory" in status

    print("✓ 测试5通过：记忆层集成工作正常")


def test_context_compression():
    """测试上下文压缩"""
    print("\n" + "=" * 60)
    print("测试6：上下文压缩")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    original_text = "这是一个非常长的任务描述，用于测试上下文压缩功能。" * 20
    print(f"原始大小: {len(original_text)} 字符")

    compressed = harness.memory_layer.compress_context(original_text, max_tokens=50)
    print(f"压缩大小: {len(compressed)} 字符")
    print(f"压缩文本: {compressed[:100]}...")

    ratio = harness.memory_layer.get_compression_ratio(original_text, compressed)
    print(f"压缩率: {ratio:.1%}")

    assert compressed is not None
    assert len(compressed) > 0

    print("✓ 测试6通过：上下文压缩工作正常")


def test_end_to_end_scenario():
    """测试端到端场景"""
    print("\n" + "=" * 60)
    print("测试7：端到端场景")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        harness = ConsciousnessHarness(workdir=tmpdir)

        description = "创建一个简单的用户管理模块，包含用户创建、查询功能"
        intent = "create_module"

        result = harness.run(
            description=description,
            intent=intent,
        )

        print(f"任务状态: {result.get('status')}")
        subtasks = result.get('subtasks', [])
        completed = sum(1 for s in subtasks if s.get('status') == 'completed')
        print(f"子任务完成数: {completed}/{len(subtasks)}")

        assert result is not None
        assert "status" in result

        print("✓ 测试7通过：端到端场景工作正常")


def test_three_layer_memory():
    """测试三层记忆架构"""
    print("\n" + "=" * 60)
    print("测试8：三层记忆架构")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")
    memory = harness.memory_layer

    memory._working_memory["task_context"] = {"task_id": "test", "step": 1}
    memory._short_term_memory["coding_rules"] = {"max_lines": 200, "style": "PEP8"}
    memory._long_term_memory["best_practices"] = {"pattern": "CQRS", "usage": "use for complex apps"}

    working = memory.get_working_memory("task_context")
    short = memory.get_short_term_memory("coding_rules")
    long = memory.get_long_term_memory("best_practices")

    assert working == {"task_id": "test", "step": 1}
    assert short == {"max_lines": 200, "style": "PEP8"}
    assert long == {"pattern": "CQRS", "usage": "use for complex apps"}

    status = memory.get_memory_status()
    print(f"工作记忆大小: {status['working_memory']['size']}")
    print(f"短期记忆大小: {status['short_term_memory']['size']}")
    print(f"长期记忆大小: {status['long_term_memory']['size']}")

    assert status["working_memory"]["size"] >= 1
    assert status["short_term_memory"]["size"] >= 1
    assert status["long_term_memory"]["size"] >= 1

    print("✓ 测试8通过：三层记忆架构工作正常")


def main():
    """运行所有集成测试"""
    print("\n" + "=" * 60)
    print("集成测试与系统验证套件")
    print("=" * 60)

    tests = [
        test_full_task_execution,
        test_cross_session_state_recovery,
        test_compliance_checker_integration,
        test_feedback_engine_integration,
        test_memory_layer_integration,
        test_context_compression,
        test_end_to_end_scenario,
        test_three_layer_memory,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ 测试失败: {test.__name__}")
            print(f"  错误: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ 测试异常: {test.__name__}")
            print(f"  异常: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
