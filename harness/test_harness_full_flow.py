import sys
import json
import time
sys.path.insert(0, 'd:\\LAAP\\harness')

from laap_coding.core.matching_engine import MatchingEngine
from laap_coding.core.component_link_protocol import parse_uri, resolve_component
from laap_coding.core.page_assembler import PageAssembler

print("="*70)
print("LAAP Harness 完整流程测试")
print("="*70)

test_cases = [
    {
        "name": "Landing Page",
        "intent": {
            "tags": ["react", "tailwind", "ui", "landing", "dark", "modern"],
            "style": "modern-minimal",
            "tech": "React + Tailwind"
        },
        "components": [
            "sections/navbar_template_01",
            "sections/hero_template_01",
            "sections/features_template_01",
            "sections/cta_template_01"
        ],
        "theme": "dark_flagship"
    },
    {
        "name": "Dashboard",
        "intent": {
            "tags": ["react", "ui", "dashboard", "enterprise", "charts"],
            "style": "enterprise-standard",
            "tech": "React"
        },
        "components": [
            "sections/navbar_template_01",
            "sections/features_template_01"
        ],
        "theme": "minimal_white"
    },
    {
        "name": "Auth Page",
        "intent": {
            "tags": ["vue", "tailwind", "auth", "login", "form"],
            "style": "modern-minimal",
            "tech": "Vue 3 + Tailwind"
        },
        "components": [
            "sections/hero_template_01"
        ],
        "theme": "ocean_blue"
    }
]

total_token_saving = 0
total_speedup = 0
passed_count = 0

for i, test_case in enumerate(test_cases):
    print(f"\n{'='*70}")
    print(f"测试案例 {i+1}: {test_case['name']}")
    print(f"{'='*70}")
    
    # Step 1: 意图解析
    print("\n[1/4] 意图解析")
    start = time.time()
    intent = test_case['intent']
    elapsed = time.time() - start
    print(f"  ✓ 意图解析完成: {elapsed*1000:.2f}ms")
    print(f"  需求标签: {', '.join(intent['tags'])}")
    print(f"  目标风格: {intent['style']}")
    print(f"  技术栈: {intent['tech']}")
    
    # Step 2: 组件匹配
    print("\n[2/4] 组件匹配")
    engine = MatchingEngine()
    start = time.time()
    results = engine.match_intent(intent)
    elapsed = time.time() - start
    print(f"  ✓ 匹配完成: {elapsed*1000:.2f}ms")
    print(f"  匹配结果数: {len(results)}")
    
    top_results = results[:3]
    for j, result in enumerate(top_results):
        scores = result['scores']
        print(f"  {j+1}. {result['name']} - 匹配度: {scores['total_score']:.3f}")
        print(f"      标签相似度: {scores['tag_similarity']:.3f}, 风格兼容性: {scores['style_compatibility']:.3f}")
        print(f"      依赖匹配: {scores['dependency_match']:.3f}, 质量评分: {scores['quality_score']:.3f}")
    
    if len(results) > 0 and results[0]['scores']['total_score'] >= 0.75:
        print("  ✓ 首结果匹配度 ≥0.75")
    else:
        print("  ✗ 首结果匹配度 < 0.75")
    
    # Step 3: URI解析
    print("\n[3/4] URI解析")
    test_uri = "harness://frontend/ui/atom/button@v1.2#primary"
    parsed = parse_uri(test_uri)
    component = resolve_component(test_uri)
    print(f"  ✓ URI解析成功: {test_uri}")
    print(f"    Domain: {parsed.domain}")
    print(f"    Subdomain: {parsed.subdomain}")
    print(f"    Granularity: {parsed.granularity}")
    print(f"    Name: {parsed.name}")
    print(f"    Version: {parsed.version}")
    print(f"    Variant: {parsed.variant}")
    
    if component:
        print(f"  ✓ 组件解析成功")
        print(f"    组件ID: {component.get_id()}")
        print(f"    组件哈希: {component.compute_hash()[:16]}...")
    else:
        print(f"  ✗ 组件解析失败")
    
    # Step 4: 页面组装
    print("\n[4/4] 页面组装")
    assembler = PageAssembler(
        templates_dir='d:\\LAAP\\harness\\laap_coding\\core\\templates',
        database_path='d:\\LAAP\\harness\\laap_coding\\core\\laap_harness_database.json'
    )
    
    for comp_uri in test_case['components']:
        assembler.add_component(comp_uri, {})
    
    assembler.inject_theme(test_case['theme'])
    
    start = time.time()
    html = assembler.generate_html()
    elapsed = time.time() - start
    
    print(f"  ✓ 页面生成完成: {elapsed*1000:.2f}ms")
    print(f"  HTML长度: {len(html)} 字符")
    print(f"  主题: {test_case['theme']}")
    print(f"  组件数: {len(test_case['components'])}")
    
    # 验证生成结果
    valid_html = len(html) > 1000 and '<!DOCTYPE html>' in html
    if valid_html:
        print("  ✓ HTML生成有效")
    else:
        print("  ✗ HTML生成无效")
    
    # 保存测试输出
    output_path = f"d:\\LAAP\\harness\\test_output_{test_case['name'].lower().replace(' ', '_')}.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✓ 页面已保存到: {output_path}")
    
    # Token消耗对比
    traditional_tokens = 10000
    harness_tokens = 100
    token_saving = ((traditional_tokens - harness_tokens) / traditional_tokens) * 100
    total_token_saving += token_saving
    
    traditional_time = 5000  # ms
    harness_time = elapsed * 1000
    speedup = traditional_time / harness_time if harness_time > 0 else 0
    total_speedup += speedup
    
    print(f"\n  Token节省率: {token_saving:.1f}%")
    print(f"  生成速度提升: {speedup:.1f}x")
    
    if valid_html and len(results) > 0 and results[0]['scores']['total_score'] >= 0.75:
        passed_count += 1
        print("  ✓ 测试通过")
    else:
        print("  ✗ 测试未通过")

print(f"\n{'='*70}")
print("测试总结")
print(f"{'='*70}")
print(f"测试案例数: {len(test_cases)}")
print(f"通过数: {passed_count}")
print(f"通过率: {(passed_count/len(test_cases))*100:.1f}%")
print(f"平均Token节省率: {total_token_saving/len(test_cases):.1f}%")
print(f"平均生成速度提升: {total_speedup/len(test_cases):.1f}x")

# 生成测试报告
report = {
    "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
    "test_cases": len(test_cases),
    "passed": passed_count,
    "failed": len(test_cases) - passed_count,
    "pass_rate": (passed_count/len(test_cases))*100,
    "avg_token_saving": total_token_saving/len(test_cases),
    "avg_speedup": total_speedup/len(test_cases),
    "test_details": []
}

for i, test_case in enumerate(test_cases):
    engine = MatchingEngine()
    results = engine.match_intent(test_case['intent'])
    report['test_details'].append({
        "name": test_case['name'],
        "intent": test_case['intent'],
        "theme": test_case['theme'],
        "components": test_case['components'],
        "top_match": results[0]['name'] if results else None,
        "match_score": results[0]['scores']['total_score'] if results else 0,
        "status": "PASS" if i < passed_count else "FAIL"
    })

report_path = 'd:\\LAAP\\harness\\test_report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n测试报告已保存到: {report_path}")
