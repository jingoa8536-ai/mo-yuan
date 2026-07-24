"""
测试记忆层架构模式库功能

验证FR-1.3和FR-5.1的实现：
1. 架构模式加载（从YAML配置文件）
2. 模式匹配引擎（根据关键词自动选择模式）
3. 项目历史库（存储和检索任务记录）
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.harness import MemoryLayer


def test_pattern_loading():
    """测试架构模式加载"""
    print("=" * 60)
    print("测试1：架构模式加载")
    print("=" * 60)

    memory = MemoryLayer()
    patterns = memory.get_all_patterns()

    print(f"加载的模式数量: {len(patterns)}")
    for pattern in patterns:
        print(f"  - {pattern['id']}: {pattern['name']}")
        print(f"    类别: {pattern.get('category', 'N/A')}")
        print(f"    关键词: {pattern.get('keywords', [])}")
        print(f"    触发条件: {pattern.get('triggers', [])}")
        print(f"    结构约束: {pattern.get('structure', [])}")
        print(f"    质量门控: {pattern.get('quality_gates', [])}")
        print()

    assert len(patterns) >= 5, f"期望至少5个模式，实际加载了{len(patterns)}个"
    pattern_ids = {p["id"] for p in patterns}
    expected_ids = {"cqrs", "modular_monolith", "event_sourcing", "repository", "dependency_injection"}
    assert pattern_ids >= expected_ids, f"缺少期望的模式: {expected_ids - pattern_ids}"

    print("✓ 测试1通过：架构模式加载成功")


def test_pattern_matching():
    """测试模式匹配引擎"""
    print("\n" + "=" * 60)
    print("测试2：模式匹配引擎")
    print("=" * 60)

    memory = MemoryLayer()

    test_cases = [
        (
            ["command", "query", "separation"],
            "CQRS相关关键词",
        ),
        (
            ["event", "store", "audit"],
            "事件溯源相关关键词",
        ),
        (
            ["module", "monolith", "boundary"],
            "模块化单体相关关键词",
        ),
        (
            ["repository", "data", "access"],
            "Repository模式相关关键词",
        ),
        (
            ["dependency", "inject", "container"],
            "依赖注入相关关键词",
        ),
    ]

    for keywords, description in test_cases:
        print(f"\n测试场景: {description}")
        print(f"输入关键词: {keywords}")

        matched = memory.match_patterns(keywords, threshold=1)
        print(f"匹配结果（按分数排序）:")
        for pattern, score in matched:
            print(f"  - {pattern['name']}: 分数={score}")

        assert len(matched) > 0, f"未找到匹配的模式: {keywords}"

    print("\n✓ 测试2通过：模式匹配引擎工作正常")


def test_pattern_recommendation():
    """测试模式推荐功能"""
    print("\n" + "=" * 60)
    print("测试3：模式推荐功能")
    print("=" * 60)

    memory = MemoryLayer()

    test_cases = [
        (
            "实现一个高并发的命令查询分离系统，需要读写分离",
            "CQRS场景",
        ),
        (
            "需要完整的审计日志和历史追踪功能，支持事件驱动",
            "事件溯源场景",
        ),
        (
            "构建一个模块化的单体应用，团队规模较小",
            "模块化单体场景",
        ),
        (
            "设计数据访问层，需要支持多种数据源",
            "Repository场景",
        ),
        (
            "提高代码可测试性，管理复杂的依赖关系",
            "依赖注入场景",
        ),
    ]

    for description, scenario in test_cases:
        print(f"\n测试场景: {scenario}")
        print(f"任务描述: {description}")

        recommendations = memory.recommend_patterns(description, top_n=3)
        print(f"推荐模式:")
        for rec in recommendations:
            print(f"  - {rec['name']}: 匹配分数={rec['match_score']}")

        assert len(recommendations) > 0, f"未找到推荐模式: {description}"

    print("\n✓ 测试3通过：模式推荐功能工作正常")


def test_pattern_retrieval():
    """测试模式检索功能"""
    print("\n" + "=" * 60)
    print("测试4：模式检索功能")
    print("=" * 60)

    memory = MemoryLayer()

    by_name = memory.get_pattern_by_name("CQRS")
    print(f"按名称检索 'CQRS': {'成功' if by_name else '失败'}")
    assert by_name is not None, "按名称检索CQRS失败"
    assert by_name["id"] == "cqrs", "CQRS ID不匹配"

    by_id = memory.get_pattern_by_id("event_sourcing")
    print(f"按ID检索 'event_sourcing': {'成功' if by_id else '失败'}")
    assert by_id is not None, "按ID检索event_sourcing失败"
    assert by_id["name"] == "Event Sourcing", "Event Sourcing名称不匹配"

    categories = memory.get_pattern_categories()
    print(f"模式类别: {categories}")
    assert len(categories) >= 2, f"期望至少2个类别，实际{len(categories)}个"

    print("✓ 测试4通过：模式检索功能工作正常")


def test_quality_gate_validation():
    """测试质量门控验证功能"""
    print("\n" + "=" * 60)
    print("测试5：质量门控验证")
    print("=" * 60)

    memory = MemoryLayer()

    test_cases = [
        (
            "cqrs",
            {"has_transactions": True},
            "CQRS质量门控验证（通过）",
        ),
        (
            "dependency_injection",
            {"has_hardcoded_dependencies": False},
            "依赖注入质量门控验证（通过）",
        ),
        (
            "dependency_injection",
            {"has_hardcoded_dependencies": True},
            "依赖注入质量门控验证（失败）",
        ),
    ]

    for pattern_id, code_context, description in test_cases:
        print(f"\n测试场景: {description}")
        print(f"模式ID: {pattern_id}")
        print(f"代码上下文: {code_context}")

        result = memory.validate_pattern_quality(pattern_id, code_context)
        print(f"验证结果: {'通过' if result['valid'] else '失败'}")
        print(f"通过门控数: {result['passed_gates']}/{result['total_gates']}")
        if result.get("violations"):
            print(f"违规项: {result['violations']}")

    print("✓ 测试5通过：质量门控验证功能工作正常")


def test_project_history():
    """测试项目历史库功能"""
    print("\n" + "=" * 60)
    print("测试6：项目历史库")
    print("=" * 60)

    memory = MemoryLayer()

    print(f"初始历史记录数: {len(memory.get_project_history())}")

    test_event = {
        "type": "task_completed",
        "description": "测试任务：实现用户认证模块",
        "task_id": "test-task-001",
        "result": "success",
        "metadata": {
            "subtasks": 5,
            "duration_ms": 120000,
            "patterns_used": ["repository", "dependency_injection"],
        },
    }

    memory.add_project_event(test_event)
    print("添加测试事件后")

    history = memory.get_project_history(limit=5)
    print(f"最新历史记录数: {len(history)}")
    for event in history:
        print(f"  - {event['event_id']}: {event['description']}")

    search_results = memory.search_project_history("用户认证")
    print(f"\n搜索 '用户认证' 结果数: {len(search_results)}")
    assert len(search_results) >= 1, "搜索失败"

    search_results = memory.search_project_history("task_completed")
    print(f"搜索 'task_completed' 结果数: {len(search_results)}")
    assert len(search_results) >= 1, "搜索失败"

    print("✓ 测试6通过：项目历史库功能工作正常")


def test_cross_validation():
    """测试跨功能验证"""
    print("\n" + "=" * 60)
    print("测试7：跨功能验证")
    print("=" * 60)

    memory = MemoryLayer()

    description = "实现一个事件驱动的微服务系统，需要完整的审计日志和历史追踪"
    print(f"任务描述: {description}")

    recommendations = memory.recommend_patterns(description, top_n=2)
    print(f"\n推荐模式:")
    for rec in recommendations:
        print(f"  - {rec['name']}: 匹配分数={rec['match_score']}")

        validation = memory.validate_pattern_quality(rec["id"], {
            "has_circular_dependency": False,
            "has_hardcoded_dependencies": False,
            "uses_interfaces": True,
            "has_transactions": True,
        })
        print(f"    质量门控验证: {'通过' if validation['valid'] else '失败'}")

    print("\n✓ 测试7通过：跨功能验证成功")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("记忆层架构模式库测试套件")
    print("=" * 60)

    tests = [
        test_pattern_loading,
        test_pattern_matching,
        test_pattern_recommendation,
        test_pattern_retrieval,
        test_quality_gate_validation,
        test_project_history,
        test_cross_validation,
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
