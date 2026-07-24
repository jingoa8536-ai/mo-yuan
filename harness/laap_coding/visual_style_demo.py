"""
视觉风格分析演示 — Visual Style Analysis Demo

演示harness如何从网站图片/视频中提取设计风格并精准复刻：
1. 图片上传与预处理
2. 色彩方案提取
3. 布局模式分析
4. 排版系统分析
5. 设计令牌生成
6. CSS/代码生成
7. Token消耗估算
"""

import sys
import os
import tempfile
from pathlib import Path

HARNESS_ROOT = Path(__file__).parent
sys.path.insert(0, str(HARNESS_ROOT))

from core.visual_style_analyzer import VisualStyleAnalyzer


def download_demo_image(url: str, save_path: str):
    """下载演示图片"""
    try:
        import urllib.request
        urllib.request.urlretrieve(url, save_path)
        print(f"✓ 演示图片已下载: {save_path}")
        return True
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return False


def run_visual_style_workflow(image_path: str):
    """运行完整的视觉风格分析工作流"""
    print("=" * 70)
    print("Harness 视觉风格分析工作流")
    print("=" * 70)
    print(f"\n目标图片: {image_path}")

    analyzer = VisualStyleAnalyzer()

    print("\n" + "=" * 70)
    print("阶段1: 视觉风格分析")
    print("=" * 70)

    result = analyzer.analyze(image_path)

    print(f"\n主导风格: {result.dominant_style}")
    print(f"复杂度评分: {result.complexity_score:.2f}")
    print(f"色彩和谐度: {result.color_harmony_score:.2f}")
    print(f"排版韵律: {result.typography_rhythm_score:.2f}")

    print("\n" + "=" * 70)
    print("阶段2: 色彩方案提取")
    print("=" * 70)

    print("\n主色调:")
    for i, color in enumerate(result.colors[:6]):
        contrast_status = "✅ AA级" if color.contrast_ratio >= 4.5 else "⚠️ 对比度不足"
        print(f"  {i+1}. {color.hex:10} | {color.name:12} | {color.semantics} | {contrast_status}")
        print(f"     用途: {', '.join(color.usage)}")

    print("\n" + "=" * 70)
    print("阶段3: 布局模式分析")
    print("=" * 70)

    print(f"\n布局类型: {result.layout.pattern_type}")
    print(f"网格列数: {result.layout.grid_columns}")
    print(f"间距宽度: {result.layout.gutter_width}")
    print(f"布局描述: {result.layout.description}")

    print("\n响应式断点:")
    for breakpoint, rules in result.layout.breakpoint_rules.items():
        print(f"  {breakpoint}: 最大宽度={rules['max_width']}, 列数={rules['columns']}, 间距={rules['gutter']}")

    print("\n" + "=" * 70)
    print("阶段4: 排版系统分析")
    print("=" * 70)

    print("\n字体层级:")
    for font in result.typography:
        print(f"  {font.font_size:25} | 字重={font.font_weight} | 行高={font.line_height} | {font.semantics}")

    print("\n" + "=" * 70)
    print("阶段5: 设计令牌生成")
    print("=" * 70)

    yaml_tokens = analyzer.generate_design_tokens_yaml(result)
    print("\n设计令牌 YAML:\n")
    print(yaml_tokens)

    print("\n" + "=" * 70)
    print("阶段6: CSS代码生成")
    print("=" * 70)

    css_code = analyzer.generate_css(result)
    print("\n生成的CSS:\n")
    print(css_code)

    print("\n" + "=" * 70)
    print("阶段7: Token消耗估算")
    print("=" * 70)

    workflow_tokens = analyzer.token_estimator.estimate_complete_workflow(image_path, result)
    print("\n各阶段Token消耗:")
    print(f"  图片分析: {workflow_tokens['analysis']} tokens")
    print(f"  代码生成: {workflow_tokens['generation']} tokens")
    print(f"  验证环节: {workflow_tokens['verification']} tokens")
    print(f"  反馈学习: {workflow_tokens['feedback']} tokens")
    print(f"  ─────────────────")
    print(f"  总消耗:   {workflow_tokens['total_workflow']} tokens")

    print("\n" + "=" * 70)
    print("阶段8: 风格复刻建议")
    print("=" * 70)

    print("\n基于分析结果的复刻建议:")
    print(f"\n1. 色彩策略:")
    print(f"   - 主色调: {result.colors[0].hex} ({result.colors[0].name})")
    print(f"   - 背景色: {result.colors[-1].hex} ({result.colors[-1].name})")
    print(f"   - 强调色: {result.colors[1].hex} ({result.colors[1].name})")
    print(f"   - 确保所有文本对比度 >= 4.5:1")

    print(f"\n2. 排版策略:")
    print(f"   - 使用 Inter 字体家族")
    print(f"   - 建立8级字体层级")
    print(f"   - 行高遵循 1.1-1.6 递进")

    print(f"\n3. 布局策略:")
    print(f"   - {result.layout.grid_columns}列网格系统")
    print(f"   - {result.layout.gutter_width}间距")
    print(f"   - 响应式5断点设计")

    print(f"\n4. Token优化建议:")
    print(f"   - 图片编码是最大开销，建议压缩到 < 2MB")
    print(f"   - 设计令牌可以预生成，避免重复分析")
    print(f"   - 使用上下文压缩将风格描述压缩50%以上")

    print("\n" + "=" * 70)
    print("🎉 视觉风格分析完成!")
    print("=" * 70)

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        image_path = sys.argv[1]
    else:
        image_path = os.path.join(tempfile.gettempdir(), "demo_website.png")
        print("未提供图片路径，使用演示图片...")
        demo_url = "https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=modern%20minimalist%20tech%20website%20design%20with%20clean%20layout%20and%20professional%20color%20scheme&image_size=landscape_16_9"
        download_demo_image(demo_url, image_path)

    if os.path.exists(image_path):
        run_visual_style_workflow(image_path)
    else:
        print(f"错误: 图片文件不存在 - {image_path}")
        sys.exit(1)
