import sys
sys.path.insert(0, 'd:\\LAAP\\harness')
from laap_coding.core.component_link_protocol import parse_uri, resolve_component, validate_uri

# 测试URI解析
test_uris = [
    "harness://frontend/ui/atom/button@v1.2#primary",
    "harness://frontend/ui/molecule/card@v2.0#glass",
    "harness://frontend/ui/section/hero@v1.0",
    "harness://frontend/animation/3d/three_js@v0.160",
    "harness://frontend/ui/atom/input",
]

print("=== URI解析测试 ===")
for uri in test_uris:
    result = parse_uri(uri)
    valid = validate_uri(uri)
    print(f"\nURI: {uri}")
    print(f"  有效: {valid}")
    if result:
        print(f"  domain: {result.domain}")
        print(f"  subdomain: {result.subdomain}")
        print(f"  granularity: {result.granularity}")
        print(f"  name: {result.name}")
        print(f"  version: {result.version}")
        print(f"  variant: {result.variant}")

print("\n=== 组件解析测试 ===")
uri = "harness://frontend/ui/atom/button@v1.2#primary"
component = resolve_component(uri)
if component:
    print(f"组件ID: {component.get_id()}")
    print(f"版本: {component.get_version()}")
    print(f"哈希: {component.compute_hash()[:16]}...")
    props = {"variant": "primary", "size": "md"}
    validation = component.validate_props(props)
    print(f"属性验证: {validation}")
    rendered = component.render(props, {"theme": "dark"})
    print(f"渲染结果: {rendered[:100]}...")
else:
    print("组件解析失败")

# 测试URI解析成功率
success_count = 0
for uri in test_uris:
    if validate_uri(uri):
        success_count += 1
success_rate = (success_count / len(test_uris)) * 100
print(f"\nURI解析成功率: {success_rate}%")
if success_rate >= 99:
    print("✓ URI解析成功率 ≥99%")
else:
    print("✗ URI解析成功率 < 99%")
