"""
Full pipeline verification: IntentMapper → HarnessComposer → HTML
"""
import sys, os
sys.path.insert(0, 'D:/LAAP/harness/laap_coding/core')

from intent_mapper import IntentMapper
from harness_composer import HarnessComposer

mapper = IntentMapper(enable_hep=False)

# Test 1: Dark SaaS with 3D
spec1 = mapper.parse("暗色 SaaS 落地页带 3D 粒子背景，品牌叫灵镜科技，标题叫重塑云端生产力")
print("=== Test 1: Dark SaaS ===")
print(f"  Brand: {spec1.get('brand', 'N/A')}")
print(f"  Theme: {spec1.get('theme', 'N/A')}")
print(f"  Title: {spec1.get('title', 'N/A')}")
print(f"  Sections: {[s['type'] for s in spec1.get('sections', [])]}")
print(f"  3D: {any(s.get('three_d') for s in spec1.get('sections', []))}")
print(f"  Nav: {'nav' in spec1}")
print()

# Test 2: Glassmorphism portfolio with animations
spec2 = mapper.parse("玻璃拟态设计师作品集，带交互动效")
print("=== Test 2: Glassmorphism Portfolio ===")
print(f"  Theme: {spec2.get('theme', 'N/A')}")
print(f"  Brand: {spec2.get('brand', 'N/A')}")
print(f"  Sections: {[s['type'] for s in spec2.get('sections', [])]}")
print()

# Test 3: Retro terminal hacker theme
spec3 = mapper.parse("复古终端黑客风格落地页，标题叫终端之下")
print("=== Test 3: Retro Terminal ===")
print(f"  Theme: {spec3.get('theme', 'N/A')}")
print(f"  Title: {spec3.get('title', 'N/A')}")
print(f"  Sections: {[s['type'] for s in spec3.get('sections', [])]}")
print()

# Test 4: 不指定风格，默认 apple_dark
spec4 = mapper.parse("科技公司首页，AI 产品")
print("=== Test 4: Default Style ===")
print(f"  Theme: {spec4.get('theme', 'N/A')}")
print(f"  Sections: {[s['type'] for s in spec4.get('sections', [])]}")
print()

# Test 5: 浅色
spec5 = mapper.parse("浅色博客内容站")
print("=== Test 5: Light Blog ===")
print(f"  Theme: {spec5.get('theme', 'N/A')}")
print(f"  Sections: {[s['type'] for s in spec5.get('sections', [])]}")
print()

# Generate real page
c = HarnessComposer(spec1.get('theme', 'apple_dark'))
html = c.from_spec(spec1)

out = 'D:/LAAP/aris_brain/intent_mapper_full_test.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print("=== Page Generation ===")
print(f"  Size: {len(html):,} bytes")
print(f"  SVG icons: {html.count('<svg')}")
print(f"  Three.js: {'three.module.js' in html}")
print(f"  Nav: {'<nav' in html}")
print(f"  Footer: {'<footer' in html}")
print(f"  Output: {out}")
print(f"  Zero token: YES")
