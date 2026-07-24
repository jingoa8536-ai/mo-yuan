"""
测试反馈引擎（Task 8）

验证FR-6的实现：
1. 模式学习器：记录和检索成功/失败模式
2. 经验积累器：积累和查询经验
3. 自修正循环：自动检测和修复错误
4. 质量趋势分析：分析历史任务质量趋势
5. 反馈引擎综合功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.feedback_engine import (
    PatternLearner, ExperienceAccumulator, SelfCorrectionLoop,
    QualityTrendAnalyzer, FeedbackEngine
)


def test_pattern_learner():
    """测试模式学习器"""
    print("=" * 60)
    print("测试1：模式学习器")
    print("=" * 60)

    learner = PatternLearner(r"D:\LAAP")

    test_context = {
        "intent": "create_function",
        "keywords": ["python", "function", "database"],
        "description": "创建数据库查询函数",
        "task_id": "test_task_1",
    }

    learner.learn(test_context, "success", 0.95)
    learner.learn(test_context, "success", 0.88)
    learner.learn(test_context, "failure", 0.3)

    stats = learner.get_pattern_statistics()
    print(f"统计信息: {stats}")
    assert stats["total_patterns"] >= 3
    assert stats["success_patterns"] >= 2
    assert stats["failure_patterns"] >= 1

    success_patterns = learner.get_success_patterns("create_function")
    print(f"成功模式数: {len(success_patterns)}")
    assert len(success_patterns) >= 1

    retrieved = learner.retrieve_patterns({"keywords": ["python", "function"]})
    print(f"检索到的模式数: {len(retrieved)}")
    assert len(retrieved) >= 1

    print("✓ 测试1通过：模式学习器工作正常")


def test_experience_accumulator():
    """测试经验积累器"""
    print("\n" + "=" * 60)
    print("测试2：经验积累器")
    print("=" * 60)

    accumulator = ExperienceAccumulator(r"D:\LAAP")

    experience = {
        "task_id": "test_task_2",
        "intent": "create_class",
        "description": "创建用户服务类",
        "success": True,
        "score": 0.92,
        "duration_ms": 1500.0,
        "issues": [],
        "corrections": [],
    }
    accumulator.accumulate(experience)

    experience2 = {
        "task_id": "test_task_3",
        "intent": "create_class",
        "description": "创建订单服务类",
        "success": False,
        "score": 0.45,
        "duration_ms": 2000.0,
        "issues": [{"message": "测试失败", "type": "test_failure"}],
        "corrections": ["检查测试用例"],
    }
    accumulator.accumulate(experience2)

    stats = accumulator.get_experience_statistics()
    print(f"统计信息: {stats}")
    assert stats["total_experiences"] >= 2
    assert stats["success_count"] >= 1

    recent = accumulator.get_recent_experiences(5)
    print(f"最近经验数: {len(recent)}")
    assert len(recent) >= 1

    query_result = accumulator.query_experiences({"intent": "create_class", "success": True})
    print(f"查询结果数: {len(query_result)}")
    assert len(query_result) >= 1

    common_issues = accumulator.get_common_issues(5)
    print(f"常见问题数: {len(common_issues)}")

    apply_result = accumulator.apply_experience({"intent": "create_class"})
    print(f"经验应用结果: {apply_result}")

    print("✓ 测试2通过：经验积累器工作正常")


def test_self_correction_loop():
    """测试自修正循环"""
    print("\n" + "=" * 60)
    print("测试3：自修正循环")
    print("=" * 60)

    loop = SelfCorrectionLoop()

    issues = [
        {"issue_type": "syntax_error", "message": "语法错误：缺少括号"},
        {"issue_type": "import_error", "message": "导入错误：模块不存在"},
        {"issue_type": "circular_dependency", "message": "循环依赖：A -> B -> A"},
        {"issue_type": "anemic_model", "message": "贫血模型：User类没有行为方法"},
    ]

    for issue in issues:
        fix = loop.correct(issue)
        print(f"问题: {issue['issue_type']}")
        print(f"  修复方案: {fix}")
        assert fix is not None

    analysis = loop.analyze_and_fix(issues)
    print(f"\n分析结果:")
    print(f"  总问题数: {analysis['total_issues']}")
    print(f"  问题类型数: {analysis['issue_types']}")
    print(f"  修复方案数: {len(analysis['corrections'])}")

    assert analysis["total_issues"] == 4
    assert len(analysis["corrections"]) >= 4

    print("✓ 测试3通过：自修正循环工作正常")


def test_quality_trend_analyzer():
    """测试质量趋势分析器"""
    print("\n" + "=" * 60)
    print("测试4：质量趋势分析器")
    print("=" * 60)

    accumulator = ExperienceAccumulator(r"D:\LAAP")
    analyzer = QualityTrendAnalyzer(accumulator)

    for i in range(5):
        accumulator.accumulate({
            "task_id": f"trend_task_{i}",
            "intent": "test_task",
            "description": f"趋势测试任务 {i}",
            "success": i % 2 == 0,
            "score": 0.7 + (i * 0.05),
            "duration_ms": 1000 + (i * 200),
        })

    metric = analyzer.analyze_trend("all")
    print(f"趋势指标:")
    print(f"  任务总数: {metric.total_tasks}")
    print(f"  成功率: {metric.success_rate:.1%}")
    print(f"  平均分数: {metric.avg_score:.2f}")
    print(f"  平均耗时: {metric.avg_duration_ms:.0f}ms")

    assert metric.total_tasks >= 5

    report = analyzer.generate_trend_report()
    print("\n趋势报告:")
    print(report[:300])

    assert "质量趋势报告" in report

    suggestions = analyzer.get_improvement_suggestions()
    print(f"\n改进建议数: {len(suggestions)}")

    print("✓ 测试4通过：质量趋势分析器工作正常")


def test_feedback_engine():
    """测试反馈引擎综合功能"""
    print("\n" + "=" * 60)
    print("测试5：反馈引擎综合功能")
    print("=" * 60)

    engine = FeedbackEngine(r"D:\LAAP")

    context = {
        "task_id": "test_feedback_task",
        "intent": "create_api",
        "keywords": ["api", "rest", "python"],
        "description": "创建REST API服务",
    }

    execution_result = {"duration_ms": 3000.0}
    verification_result = {
        "passed": True,
        "score": 0.85,
        "issues": [],
    }

    feedback_result = engine.process_feedback(context, execution_result, verification_result)
    print(f"反馈处理结果:")
    print(f"  修正: {feedback_result['corrected']}")
    print(f"  学习: {feedback_result['learned']}")
    print(f"  积累: {feedback_result['accumulated']}")

    assert feedback_result["learned"] is True
    assert feedback_result["accumulated"] is True

    stats = engine.get_statistics()
    print(f"\n统计信息:")
    print(f"  模式数: {stats['pattern_stats']['total_patterns']}")
    print(f"  经验数: {stats['experience_stats']['total_experiences']}")

    report = engine.get_quality_report()
    print("\n质量报告:")
    print(report[:200])

    learning = engine.apply_learning(context)
    print(f"\n学习应用:")
    print(f"  找到模式数: {learning['patterns_found']}")
    print(f"  经验应用: {learning['experience_applied']}")

    suggestions = engine.get_improvement_suggestions()
    print(f"\n改进建议: {suggestions}")

    print("✓ 测试5通过：反馈引擎工作正常")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("反馈引擎测试套件")
    print("=" * 60)

    tests = [
        test_pattern_learner,
        test_experience_accumulator,
        test_self_correction_loop,
        test_quality_trend_analyzer,
        test_feedback_engine,
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
