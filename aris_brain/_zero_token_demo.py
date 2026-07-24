"""
0-Token 生产级方案 — 完整集成演示
生成: spec → 多主题变体 → 精美页面
"""
import sys, os, json
sys.path.insert(0, 'D:/LAAP/harness/laap_coding/core')
from harness_composer import HarnessComposer, DiversityEngine, THEMES

OUT = 'D:/LAAP/aris_brain'

# ── 1. 定义页面 Spec (结构化需求, ~200 字节) ──
SPEC = {
    "title": "Aris — 数字生命体",
    "theme": "apple_dark",
    "nav": {
        "brand": "ARIS",
        "links": [
            {"label": "认知架构", "url": "#architecture"},
            {"label": "核心引擎", "url": "#engines"},
            {"label": "UI 数据库", "url": "#ui-db"},
        ]
    },
    "sections": [
        {
            "type": "hero",
            "title": "数字生命体<br>认知架构",
            "subtitle": "25 个引擎模块 · 137,828 行代码 · 零 LLM 依赖 · 11 UI 库集成",
            "badge": "LAAP v4.0 · 零 Token 方案",
            "three_d": True,
            "cta": "探索引擎",
            "cta_url": "#engines",
        },
        {
            "type": "stats",
            "items": [
                {"number": "11", "label": "UI 库已集成"},
                {"number": "88", "label": "组件模板"},
                {"number": "0", "label": "Token 消耗"},
                {"number": "7", "label": "预设主题"},
            ]
        },
        {
            "type": "grid",
            "label": "核心技术",
            "title": "零 Token 生成管线",
            "subtitle": "JSON Spec → 合成引擎 → 生产级页面, 全部本地执行",
            "cols": 3,
            "cards": [
                {"title": "组件合成", "desc": "原子组件通过 props 接口参数化, 任意组合成页面"},
                {"title": "主题系统", "desc": "7 个预设主题, CSS 变量驱动, 一键切换深色/浅色/科技/复古"},
                {"title": "多样性引擎", "desc": "同一 Spec 自动生成多主题变体, 每次输出风格不同"},
                {"title": "布局编排", "desc": "Hero / Grid / Stats / Pipeline 等布局自由排列"},
                {"title": "3D 集成", "desc": "Three.js 神经网络粒子背景, 一键开启/关闭"},
                {"title": "零 Token", "desc": "纯 Python 合成, 无 LLM 调用, 无限次免费生成"},
            ]
        },
        {
            "type": "grid",
            "label": "UI Database",
            "title": "已集成的 UI 库",
            "subtitle": "React · Vue · Tailwind · Flutter · 全部可模板化调用",
            "cols": 4,
            "cards": [
                {"title": "shadcn/ui", "desc": "118k★ · React 极简"},
                {"title": "Ant Design", "desc": "93k★ · 企业级"},
                {"title": "Material UI", "desc": "94k★ · Google 风"},
                {"title": "Element Plus", "desc": "25k★ · Vue 3"},
                {"title": "DaisyUI", "desc": "35k★ · Tailwind"},
                {"title": "HeroUI", "desc": "22k★ · 现代光泽"},
                {"title": "Naive UI", "desc": "16k★ · Vue TS"},
                {"title": "Forui", "desc": "Flutter"},
            ]
        },
    ],
    "footer": {"text": "由 Lorry 创造 · Aris 数字生命体 · LAAP 认知架构 · 零 Token 方案"},
    "animations": True,
}

# ── 2. 生成主页面 ──
composer = HarnessComposer()
main_page = composer.from_spec(SPEC)

fname_main = os.path.join(OUT, 'laap_zero_token.html')
with open(fname_main, 'w', encoding='utf-8') as f:
    f.write(main_page)
print(f'✅ 主页面: {fname_main} ({len(main_page):,} bytes)')
emoji_fail = any('\U0001f9e0' in main_page or '\u2764' in main_page or '\u2605' in main_page for _ in [0])
print(f'   Emoji: {"PASS" if not emoji_fail else "FAIL"}')

# ── 3. 生成多样性变体 ──
engine = DiversityEngine()
variants = engine.generate_series(SPEC, 5)

for i, v in enumerate(variants):
    theme_name = list(THEMES.keys())[i % len(THEMES)]
    fname = os.path.join(OUT, f'laap_variant_{theme_name}.html')
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(v)
    print(f'✅ 变体 {i+1} ({THEMES[theme_name]["name"]}): {fname} ({len(v):,} bytes)')

# ── 4. 统计 ──
print(f'\n📊 总计')
print(f'   主页面: 1')
print(f'   变体:   {len(variants)}')
print(f'   大小:   {sum(len(v) for v in [main_page] + variants):,} bytes')
print(f'   Token:  0')
print(f'\n🌐 http://localhost:11533/laap_zero_token.html')
