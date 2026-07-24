"""
测试验证层功能 — Test Verification Layer

实现FR-4验证层测试：
- 测试验证器（TestValidator）测试
- 静态分析器（StaticAnalyzer）测试
- 安全扫描器（SecurityScanner）测试
- 增量交付（IncrementalDelivery）测试
- 验证层（VerificationLayer）完整验证链测试
- 错误恢复模式测试
"""

import os
import sys
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.test_validator import TestValidator
from core.static_analyzer import StaticAnalyzer
from core.security_scanner import SecurityScanner
from core.incremental_delivery import IncrementalDelivery
from core.harness import VerificationLayer, ExecutionResult, SubTask


def print_header(title: str, char: str = "="):
    print(f"\n{char * 60}")
    print(f"  {title}")
    print(char * 60)


def print_result(name: str, passed: bool, details: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {name}")
    if details:
        print(f"       Details: {details}")


def test_test_validator():
    """测试测试验证器"""
    print_header("🔍 测试验证器 (TestValidator)")
    
    validator = TestValidator()
    passed_count = 0
    total_count = 0

    total_count += 1
    result = validator.validate("PASS: All tests passed")
    if result["passed"]:
        passed_count += 1
    print_result("验证通过输出", result["passed"])

    total_count += 1
    result = validator.validate("FAIL: Test failed with error")
    if not result["passed"]:
        passed_count += 1
    print_result("验证失败输出", not result["passed"])

    total_count += 1
    result = validator.validate("")
    if result["passed"]:
        passed_count += 1
    print_result("验证空输出", result["passed"])

    total_count += 1
    result = validator.validate("Generated file successfully")
    if result["passed"]:
        passed_count += 1
    print_result("验证生成输出", result["passed"])

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_static_analyzer():
    """测试静态分析器"""
    print_header("🔍 静态分析器 (StaticAnalyzer)")
    
    analyzer = StaticAnalyzer()
    passed_count = 0
    total_count = 0

    total_count += 1
    issues = analyzer.check_syntax("print('hello')")
    if len(issues) == 0:
        passed_count += 1
    print_result("检查正确语法", len(issues) == 0)

    total_count += 1
    issues = analyzer.check_syntax("def func(")
    if len(issues) > 0:
        passed_count += 1
    print_result("检查语法错误", len(issues) > 0)

    total_count += 1
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def test_func(x):\n    return x * 2\n")
        temp_file = f.name
    
    try:
        issues = analyzer.check_syntax_file(temp_file)
        if len(issues) == 0:
            passed_count += 1
        print_result("检查文件语法", len(issues) == 0)
    finally:
        os.unlink(temp_file)

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_security_scanner():
    """测试安全扫描器"""
    print_header("🔍 安全扫描器 (SecurityScanner)")
    
    scanner = SecurityScanner()
    passed_count = 0
    total_count = 0

    total_count += 1
    issues = scanner.scan_code("password = 'secret123'")
    if len(issues) > 0:
        passed_count += 1
    print_result("检测硬编码密码", len(issues) > 0)

    total_count += 1
    issues = scanner.scan_code("import subprocess; subprocess.run(['ls'])")
    if len(issues) > 0:
        passed_count += 1
    print_result("检测命令执行", len(issues) > 0)

    total_count += 1
    issues = scanner.scan_code("import hashlib; hashlib.md5(b'data')")
    if len(issues) > 0:
        passed_count += 1
    print_result("检测弱加密算法", len(issues) > 0)

    total_count += 1
    issues = scanner.scan_code("def safe_func(x): return x")
    if len(issues) == 0:
        passed_count += 1
    print_result("安全代码无警报", len(issues) == 0)

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_incremental_delivery():
    """测试增量交付约束"""
    print_header("🔍 增量交付约束 (IncrementalDelivery)")
    
    delivery = IncrementalDelivery()
    passed_count = 0
    total_count = 0

    total_count += 1
    valid, msg = delivery.validate_commit_message("feat(harness): add verification layer")
    if valid:
        passed_count += 1
    print_result("验证有效语义化提交", valid)

    total_count += 1
    valid, msg = delivery.validate_commit_message("fix: fix bug")
    if not valid:
        passed_count += 1
    print_result("验证无效提交格式", not valid)

    total_count += 1
    valid, msg = delivery.validate_commit_message("")
    if not valid:
        passed_count += 1
    print_result("验证空提交信息", not valid)

    total_count += 1
    commit_msg = delivery.create_conventional_commit("feat", "test", "add new feature")
    if commit_msg.startswith("feat(test):"):
        passed_count += 1
    print_result("创建语义化提交", commit_msg.startswith("feat(test):"))

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_verification_layer():
    """测试验证层"""
    print_header("🔍 验证层 (VerificationLayer)")
    
    verification = VerificationLayer()
    passed_count = 0
    total_count = 0

    total_count += 1
    exec_result = ExecutionResult(
        success=True,
        output="Generated file successfully",
        modified_files=[],
        duration_ms=100
    )
    result = verification.verify(exec_result)
    if result.passed:
        passed_count += 1
    print_result("验证成功执行结果", result.passed)

    total_count += 1
    exec_result = ExecutionResult(
        success=False,
        output="Error: test failed",
        modified_files=[],
        duration_ms=100,
        error="Test failed"
    )
    result = verification.verify(exec_result)
    if not result.passed:
        passed_count += 1
    print_result("验证失败执行结果", not result.passed)

    total_count += 1
    history = verification.get_verification_history()
    if isinstance(history, list):
        passed_count += 1
    print_result("获取验证历史", isinstance(history, list))

    total_count += 1
    verification.reset_retry_count()
    if verification._current_retry_count == 0:
        passed_count += 1
    print_result("重置重试计数器", verification._current_retry_count == 0)

    total_count += 1
    exec_result = ExecutionResult(
        success=True,
        output="OK",
        modified_files=[],
        duration_ms=100
    )
    chain_result = verification.verify_chain(exec_result)
    if isinstance(chain_result, dict) and "passed" in chain_result:
        passed_count += 1
    print_result("执行验证链", isinstance(chain_result, dict))

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_error_recovery():
    """测试错误恢复模式"""
    print_header("🔍 错误恢复模式 (Error Recovery)")
    
    verification = VerificationLayer()
    passed_count = 0
    total_count = 0

    total_count += 1
    exec_result = ExecutionResult(
        success=False,
        output="FAIL",
        modified_files=[],
        duration_ms=100,
        error="Test failed"
    )
    fix_result = verification.attempt_fix(exec_result)
    if fix_result["retry_count"] == 1:
        passed_count += 1
    print_result("第一次修复尝试", fix_result["retry_count"] == 1)

    total_count += 1
    fix_result = verification.attempt_fix(exec_result)
    if fix_result["retry_count"] == 2:
        passed_count += 1
    print_result("第二次修复尝试", fix_result["retry_count"] == 2)

    total_count += 1
    fix_result = verification.attempt_fix(exec_result)
    if fix_result["retry_count"] == 3:
        passed_count += 1
    print_result("第三次修复尝试", fix_result["retry_count"] == 3)

    total_count += 1
    fix_result = verification.attempt_fix(exec_result)
    if fix_result["action"] == "rollback":
        passed_count += 1
    print_result("达到最大重试次数触发回滚", fix_result["action"] == "rollback")

    total_count += 1
    verification.reset_retry_count()
    fix_result = verification.attempt_fix(exec_result)
    if fix_result["retry_count"] == 1:
        passed_count += 1
    print_result("重置后重新开始计数", fix_result["retry_count"] == 1)

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_verification_with_subtask():
    """测试验证层与子任务集成"""
    print_header("🔍 验证层与子任务集成")
    
    verification = VerificationLayer()
    passed_count = 0
    total_count = 0

    total_count += 1
    subtask = SubTask(
        sub_task_id="test_001",
        parent_task_id="parent_001",
        description="测试子任务",
        files=[],
        estimated_lines=50,
        dependencies=[]
    )
    exec_result = ExecutionResult(
        success=True,
        output="OK",
        modified_files=[],
        duration_ms=100
    )
    chain_result = verification.verify_chain(exec_result, subtask)
    if isinstance(chain_result, dict) and "passed" in chain_result:
        passed_count += 1
    print_result("子任务验证链执行成功", isinstance(chain_result, dict))

    total_count += 1
    steps = chain_result.get("steps", [])
    if len(steps) > 0:
        passed_count += 1
    print_result("验证链包含多个步骤", len(steps) > 0)

    total_count += 1
    reports = chain_result.get("reports", {})
    if isinstance(reports, dict):
        passed_count += 1
    print_result("验证链生成报告", isinstance(reports, dict))

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def test_comprehensive_report():
    """测试综合报告生成"""
    print_header("🔍 综合报告生成")
    
    passed_count = 0
    total_count = 0

    validator = TestValidator()
    test_result = validator.run_pytest("nonexistent_path")
    total_count += 1
    report = validator.generate_report(test_result)
    if "测试验证报告" in report:
        passed_count += 1
    print_result("生成测试报告", "测试验证报告" in report)

    analyzer = StaticAnalyzer()
    analysis_result = analyzer.analyze_project([])
    total_count += 1
    report = analyzer.generate_report(analysis_result)
    if "静态分析报告" in report:
        passed_count += 1
    print_result("生成静态分析报告", "静态分析报告" in report)

    scanner = SecurityScanner()
    scan_result = scanner.comprehensive_scan()
    total_count += 1
    report = scanner.generate_report(scan_result)
    if "安全扫描报告" in report:
        passed_count += 1
    print_result("生成安全扫描报告", "安全扫描报告" in report)

    print(f"\n  测试结果: {passed_count}/{total_count} 通过")
    return passed_count == total_count


def main():
    """主测试入口"""
    print_header("LAAP 验证层测试套件", "=")
    print("实现FR-4：多层验证循环测试")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("测试验证器", test_test_validator),
        ("静态分析器", test_static_analyzer),
        ("安全扫描器", test_security_scanner),
        ("增量交付约束", test_incremental_delivery),
        ("验证层", test_verification_layer),
        ("错误恢复模式", test_error_recovery),
        ("子任务集成", test_verification_with_subtask),
        ("综合报告生成", test_comprehensive_report),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ❌ ERROR - {name}: {e}")
            results.append((name, False))

    print_header("测试总结", "=")
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")

    print(f"\n  总体结果: {passed_count}/{total_count} 通过")

    if passed_count == total_count:
        print("\n  🎉 所有测试通过！验证层功能正常工作。")
        return 0
    else:
        print(f"\n  ⚠️ {total_count - passed_count} 个测试未通过，请检查相关模块。")
        return 1


if __name__ == "__main__":
    sys.exit(main())