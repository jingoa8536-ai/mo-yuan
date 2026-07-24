import sys
sys.path.insert(0, 'd:\\LAAP\\harness')
from laap_coding.core.page_assembler import PageAssembler

print("=== 页面组装器测试 ===")

assembler = PageAssembler(
    templates_dir='d:\\LAAP\\harness\\laap_coding\\core\\templates',
    database_path='d:\\LAAP\\harness\\laap_coding\\core\\laap_harness_database.json'
)

# 添加组件
assembler.add_component('sections/navbar_template_01', {
    'logo': 'L',
    'brand': 'LAAP Harness',
    'links': [
        {'label': 'Home', 'href': '#home'},
        {'label': 'Components', 'href': '#components'},
        {'label': 'Pricing', 'href': '#pricing'},
        {'label': 'Contact', 'href': '#contact'}
    ]
})

assembler.add_component('sections/hero_template_01', {
    'title': 'Build Amazing Pages',
    'description': 'LAAP Harness makes page assembly easy with minimal tokens',
    'primary_button': 'Get Started',
    'secondary_button': 'Learn More'
})

assembler.add_component('sections/features_template_01', {
    'title': 'Features',
    'items': [
        {'icon': 'Zap', 'title': 'Fast', 'desc': 'Blazing fast rendering'},
        {'icon': 'Shield', 'title': 'Secure', 'desc': 'Enterprise grade security'},
        {'icon': 'Sparkles', 'title': 'Beautiful', 'desc': 'Stunning UI components'}
    ]
})

assembler.add_component('sections/cta_template_01', {
    'title': 'Ready to Start?',
    'description': 'Join thousands of developers building amazing pages',
    'primary_button': 'Get Started',
    'secondary_button': 'Contact Sales'
})

# 验证组件
validation = assembler.validate_components()
print(f"组件验证: {validation}")

# 解析依赖
deps = assembler.resolve_dependencies()
print(f"\n依赖解析结果:")
print(f"  组件数量: {len(deps.get('components', []))}")
print(f"  依赖数量: {len(deps.get('dependencies', []))}")
if deps.get('version_conflicts'):
    print(f"  版本冲突: {deps['version_conflicts']}")
else:
    print(f"  版本冲突: 无")

# 注入主题并生成HTML
assembler.inject_theme('dark_flagship')
html = assembler.generate_html()

# 验证生成结果
print(f"\n生成结果验证:")
print(f"  HTML长度: {len(html)} 字符")
print(f"  包含DOCTYPE: {'<!DOCTYPE html>' in html}")
print(f"  包含主题CSS: {'--accent-primary' in html}")
print(f"  包含组件: {'navbar' in html.lower()}")
print(f"  包含Tailwind: {'tailwind' in html.lower()}")

# 保存生成的页面
output_path = 'd:\\LAAP\\harness\\test_output_page.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✓ 页面已生成并保存到: {output_path}")

# 验证生成的HTML内容
if len(html) > 1000 and '<!DOCTYPE html>' in html and '--accent-primary' in html:
    print("✓ 页面组装测试通过")
else:
    print("✗ 页面组装测试失败")
