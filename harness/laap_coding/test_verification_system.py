"""
LAAP Harness 验证与质量门控机制验证测试
"""

import tempfile
import os
from core.test_validator import TestValidator
from core.static_analyzer import StaticAnalyzer
from core.security_scanner import SecurityScanner

print('=' * 60)
print('LAAP Harness 验证与质量门控验证')
print('=' * 60)

# 1. 测试验证器验证
print('\n[1/3] 测试验证器验证')
try:
    validator = TestValidator()
    print('  OK 测试验证器初始化成功')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'test_math.py')
        with open(test_file, 'w') as f:
            f.write("""def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")
        
        test_file_pytest = os.path.join(tmpdir, 'test_math_test.py')
        with open(test_file_pytest, 'w') as f:
            f.write("""import test_math

def test_add():
    assert test_math.add(2, 3) == 5
    assert test_math.add(-1, 1) == 0

def test_multiply():
    assert test_math.multiply(2, 3) == 6
    assert test_math.multiply(0, 5) == 0
""")
        
        result = validator.run_pytest(test_file_pytest)
        print('  OK pytest测试运行:', result.passed)
        print('  OK 测试总数:', result.total_tests)
        print('  OK 通过数:', result.passed_tests)
        
        report = validator.generate_report(result)
        print('  OK 报告生成:', len(report) > 0)
    
except Exception as e:
    print('  FAIL 测试验证器验证失败:', e)

# 2. 静态分析器验证
print('\n[2/3] 静态分析器验证')
try:
    analyzer = StaticAnalyzer()
    print('  OK 静态分析器初始化成功')
    
    test_code = """def bad_function():
    x = 1
    y = 2
    z = x + y
    return z

class TooManyMethods:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass
    def method8(self): pass
    def method9(self): pass
    def method10(self): pass
    def method11(self): pass
"""
    
    issues = analyzer.analyze(test_code)
    print('  OK 代码分析:', len(issues), '个问题')
    
    syntax_issues = analyzer.check_syntax(test_code)
    print('  OK 语法检查:', len(syntax_issues), '个语法问题')
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'test.py')
        with open(test_file, 'w') as f:
            f.write(test_code)
        
        file_analysis = analyzer.analyze_file(test_file)
        print('  OK 文件分析:', file_analysis is not None)
        print('  OK 语法验证:', file_analysis.syntax_valid)
        
        flake8_issues = analyzer.run_flake8(test_file)
        print('  OK flake8检查:', len(flake8_issues), '个问题')
        
        report = analyzer.generate_report(file_analysis)
        print('  OK 报告生成:', len(report) > 0)
    
except Exception as e:
    print('  FAIL 静态分析器验证失败:', e)

# 3. 安全扫描器验证
print('\n[3/3] 安全扫描器验证')
try:
    scanner = SecurityScanner()
    print('  OK 安全扫描器初始化成功')
    
    safe_code = """def safe_function(data):
    return data.strip()
"""
    
    unsafe_code = """def unsafe_function(user_input):
    import os
    os.system(user_input)
"""
    
    safe_result = scanner.scan_code(safe_code)
    print('  OK 安全代码扫描:', len(safe_result), '个问题')
    
    unsafe_result = scanner.scan_code(unsafe_code)
    print('  OK 不安全代码扫描:', len(unsafe_result), '个问题')
    if unsafe_result:
        print('    - 漏洞类型:', unsafe_result[0].category)
        print('    - 严重程度:', unsafe_result[0].severity)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, 'test.py')
        with open(test_file, 'w') as f:
            f.write(unsafe_code)
        
        file_scan = scanner.scan_file(test_file)
        print('  OK 文件扫描:', len(file_scan), '个问题')
        
        comprehensive = scanner.comprehensive_scan()
        print('  OK 综合扫描:', comprehensive.passed)
        print('  OK 漏洞总数:', comprehensive.total_vulnerabilities)
        
        report = scanner.generate_report(comprehensive)
        print('  OK 报告生成:', len(report) > 0)
    
except Exception as e:
    print('  FAIL 安全扫描器验证失败:', e)

print('\n' + '=' * 60)
print('验证完成!')
print('=' * 60)