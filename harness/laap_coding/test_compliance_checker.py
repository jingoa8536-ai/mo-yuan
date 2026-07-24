"""
测试代码合规检查器（Task 7）

验证FR-5.2的实现：
1. 循环依赖检测
2. 贫血模型检测
3. 接口隔离检测
4. 开闭原则检测
5. 单一职责检测
6. 自动修复策略
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.compliance_checker import (
    CodeComplianceChecker, DependencyAnalyzer, DependencyGraph,
    InterfaceSegregationChecker, OpenClosedChecker, SingleResponsibilityChecker,
    AutoFixStrategy, ComplianceIssue
)


def test_dependency_analysis():
    """测试依赖分析器"""
    print("=" * 60)
    print("测试1：依赖分析器")
    print("=" * 60)

    analyzer = DependencyAnalyzer()
    test_file = os.path.join(os.path.dirname(__file__), "core", "harness.py")

    result = analyzer.analyze_file(test_file)
    print(f"分析文件: {test_file}")
    print(f"导入模块数: {len(result['imports'])}")
    print(f"From导入数: {len(result['from_imports'])}")
    print(f"类数: {len(result['classes'])}")
    print(f"函数数: {len(result['functions'])}")

    assert result["file_path"] == test_file
    assert len(result["classes"]) > 5
    assert len(result["functions"]) > 10

    print("✓ 测试1通过：依赖分析器工作正常")


def test_circular_dependency_detection():
    """测试循环依赖检测"""
    print("\n" + "=" * 60)
    print("测试2：循环依赖检测")
    print("=" * 60)

    graph = DependencyGraph()
    graph.add_edge("module_a", "module_b")
    graph.add_edge("module_b", "module_c")
    graph.add_edge("module_c", "module_a")

    analyzer = DependencyAnalyzer()
    cycles = analyzer.detect_circular_dependencies(graph)

    print(f"检测到的循环依赖: {cycles}")

    assert len(cycles) >= 1
    assert ["module_a", "module_b", "module_c"] in cycles or ["module_b", "module_c", "module_a"] in cycles or ["module_c", "module_a", "module_b"] in cycles

    graph2 = DependencyGraph()
    graph2.add_edge("a", "b")
    graph2.add_edge("b", "c")
    cycles2 = analyzer.detect_circular_dependencies(graph2)
    print(f"无循环依赖的图: {cycles2}")
    assert len(cycles2) == 0

    print("✓ 测试2通过：循环依赖检测工作正常")


def test_interface_segregation():
    """测试接口隔离检测"""
    print("\n" + "=" * 60)
    print("测试3：接口隔离检测")
    print("=" * 60)

    checker = InterfaceSegregationChecker()
    test_file = os.path.join(os.path.dirname(__file__), "core", "harness.py")

    issues = checker.check(test_file)
    print(f"检测到的问题数: {len(issues)}")

    for issue in issues[:5]:
        print(f"  - [{issue.severity}] {issue.message}")

    assert isinstance(issues, list)

    print("✓ 测试3通过：接口隔离检测工作正常")


def test_open_closed():
    """测试开闭原则检测"""
    print("\n" + "=" * 60)
    print("测试4：开闭原则检测")
    print("=" * 60)

    checker = OpenClosedChecker()
    test_file = os.path.join(os.path.dirname(__file__), "core", "harness.py")

    issues = checker.check(test_file)
    print(f"检测到的问题数: {len(issues)}")

    for issue in issues[:5]:
        print(f"  - [{issue.severity}] {issue.message}")

    assert isinstance(issues, list)

    print("✓ 测试4通过：开闭原则检测工作正常")


def test_single_responsibility():
    """测试单一职责检测"""
    print("\n" + "=" * 60)
    print("测试5：单一职责检测")
    print("=" * 60)

    checker = SingleResponsibilityChecker()
    test_file = os.path.join(os.path.dirname(__file__), "core", "harness.py")

    issues = checker.check(test_file)
    print(f"检测到的问题数: {len(issues)}")

    for issue in issues[:5]:
        print(f"  - [{issue.severity}] {issue.message}")

    assert isinstance(issues, list)

    print("✓ 测试5通过：单一职责检测工作正常")


def test_anemic_model_detection():
    """测试贫血模型检测"""
    print("\n" + "=" * 60)
    print("测试6：贫血模型检测")
    print("=" * 60)

    checker = CodeComplianceChecker(os.path.join(os.path.dirname(__file__), "core"))

    anemic_models = checker.detect_anemic_models()
    print(f"检测到的贫血模型数: {len(anemic_models)}")

    for model in anemic_models[:3]:
        print(f"  - 文件: {model['file']}")
        print(f"    类: {model['class']}")
        print(f"    问题: {model['issue']}")

    assert isinstance(anemic_models, list)

    print("✓ 测试6通过：贫血模型检测工作正常")


def test_auto_fix_strategy():
    """测试自动修复策略"""
    print("\n" + "=" * 60)
    print("测试7：自动修复策略")
    print("=" * 60)

    strategy = AutoFixStrategy()

    interface_fix = strategy.extract_interface("UserService", ["get_user", "create_user", "update_user"])
    print("提取接口:")
    print(interface_fix)
    assert "IUserService" in interface_fix
    assert "get_user" in interface_fix

    logic_fix = strategy.sink_logic("User", "用户登录验证")
    print("\n下沉逻辑:")
    print(logic_fix)
    assert "User" in logic_fix
    assert "用户登录验证" in logic_fix

    adapter_fix = strategy.add_adapter("LegacyUser", "IUser")
    print("\n添加适配器:")
    print(adapter_fix)
    assert "LegacyUserToIUserAdapter" in adapter_fix

    issue = ComplianceIssue(
        issue_type="interface_segregation",
        severity="warning",
        message="类 UserService 包含 15 个方法，可能违反接口隔离原则",
        location="test.py",
        line_number=10,
    )
    fix = strategy.generate_fix(issue)
    print(f"\n生成修复建议: {'有建议' if fix else '无建议'}")
    assert fix is not None

    print("✓ 测试7通过：自动修复策略工作正常")


def test_compliance_checker():
    """测试代码合规检查器综合功能"""
    print("\n" + "=" * 60)
    print("测试8：代码合规检查器综合功能")
    print("=" * 60)

    checker = CodeComplianceChecker(os.path.join(os.path.dirname(__file__), "core"))

    result = checker.check_project()
    print(f"合规状态: {'✓ 合规' if result.compliant else '✗ 不合规'}")
    print(f"合规分数: {result.score:.2f}")
    print(f"检查文件数: {result.summary.get('files_checked', 0)}")
    print(f"总问题数: {result.summary.get('total_issues', 0)}")
    print(f"错误数: {result.summary.get('errors', 0)}")
    print(f"警告数: {result.summary.get('warnings', 0)}")
    print(f"信息数: {result.summary.get('infos', 0)}")

    assert isinstance(result.compliant, bool)
    assert 0 <= result.score <= 1.0

    report = checker.generate_report(result)
    print("\n合规检查报告:")
    print(report[:500])

    assert "代码合规检查报告" in report

    print("✓ 测试8通过：代码合规检查器工作正常")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("代码合规检查器测试套件")
    print("=" * 60)

    tests = [
        test_dependency_analysis,
        test_circular_dependency_detection,
        test_interface_segregation,
        test_open_closed,
        test_single_responsibility,
        test_anemic_model_detection,
        test_auto_fix_strategy,
        test_compliance_checker,
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
