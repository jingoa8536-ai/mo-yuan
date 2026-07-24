#!/usr/bin/env python
"""
演示：物种库属性修改与自动更新机制
=========================================

流程：
1. 初始化认知物种库
2. 查找Button v3物种
3. 修改颜色属性（从gradient改为red）
4. 重新生成组件代码
5. 更新组件文件
6. 验证更新效果

展示编译式AI范式核心能力：
- 物种属性动态修改
- 代码自动重新生成
- 零Token更新（从物种库直接渲染）
- 组件文件同步更新
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from laap_coding.core.cognitive_species_library import CognitiveSpeciesLibrary, SpeciesType


def find_button_v3(lib):
    """查找Button v3物种（gradient按钮）"""
    results = lib.search_species("gradient button")
    for species in results:
        if "gradient" in species.props.get("color", ""):
            return species
    return None


def update_species_color(lib, species, new_color):
    """更新物种颜色属性"""
    old_color = species.props.get("color", "unknown")
    species.props["color"] = new_color
    species.last_used = __import__('time').time()
    lib._save_species()
    
    print(f"✓ 物种属性已更新: {species.name}")
    print(f"   - 颜色: {old_color} → {new_color}")
    return species


def regenerate_component_code(species):
    """根据更新后的物种重新生成组件代码"""
    template = species.template
    props = species.props
    
    if template == "button":
        return f'''"""
Button v3 - {props.get('color')}按钮组件
=========================================

物种信息：
- 模板: {template}
- 版本: v3
- 属性: {props.get('color')}颜色、{props.get('variant')}变体、{props.get('size')}尺寸

生成代码：从认知物种库自动生成（属性更新后）
"""

def render_button(label="{props.get('label', 'Submit')}", color="{props.get('color', 'primary')}", 
                  variant="{props.get('variant', 'primary')}", size="{props.get('size', 'lg')}", 
                  rounded={props.get('rounded', True)}, shadow={props.get('shadow', True)}, 
                  hover_effect={props.get('hover_effect', True)}):
    """渲染按钮组件"""
    classes = ["btn"]
    
    if color == "gradient":
        classes.append("btn-gradient")
    else:
        classes.append(f"btn-{{color}}")
    
    classes.append(f"btn-{{variant}}")
    classes.append(f"btn-{{size}}")
    
    if rounded:
        classes.append("btn-rounded")
    if shadow:
        classes.append("btn-shadow")
    if hover_effect:
        classes.append("btn-hover")
    
    class_str = " ".join(classes)
    return f\'<button class="{{class_str}}">{{label}}</button>\'
'''
    return ""


def update_component_file(file_path, code):
    """更新组件文件"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f"✓ 组件文件已更新: {file_path}")


def verify_update(species, file_path):
    """验证更新效果"""
    print(f"\n📋 验证更新效果:")
    print(f"   物种名称: {species.name}")
    print(f"   模板: {species.template}")
    print(f"   当前颜色属性: {species.props.get('color')}")
    print(f"   文件内容验证: {'已更新' if os.path.exists(file_path) else '文件不存在'}")
    
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if species.props.get('color') in content:
                print(f"   ✅ 颜色属性已同步到代码中")
            else:
                print(f"   ❌ 颜色属性未同步")


def main():
    print("="*70)
    print("物种库属性修改与自动更新演示")
    print("="*70)
    print("展示编译式AI范式核心能力：")
    print("  • 物种属性动态修改")
    print("  • 代码自动重新生成")
    print("  • 零Token更新（从物种库直接渲染）")
    print("="*70)

    lib = CognitiveSpeciesLibrary()
    
    print("\n步骤 1: 查找Button v3物种")
    button_v3 = find_button_v3(lib)
    if button_v3:
        print(f"✓ 找到Button v3: {button_v3.name}")
        print(f"   属性: {json.dumps(button_v3.props, indent=4, ensure_ascii=False)}")
    else:
        print("❌ 未找到Button v3物种，先注册一个")
        button_v3 = lib.register_compiled_species(
            template="button",
            props={"label": "Submit", "color": "gradient", "variant": "primary", 
                   "size": "lg", "rounded": True, "shadow": True, "hover_effect": True},
            tags=["ui", "button", "versioned", "enhanced", "premium"],
            domain=["frontend"],
        )
        print(f"✓ 已注册Button v3: {button_v3.name}")

    print("\n步骤 2: 修改物种颜色属性（gradient → red）")
    button_v3 = update_species_color(lib, button_v3, "red")

    print("\n步骤 3: 重新生成组件代码")
    new_code = regenerate_component_code(button_v3)
    print(f"✓ 代码重新生成完成")
    print(f"\n📄 新生成的代码:")
    print("-" * 50)
    print(new_code[:300] + "..." if len(new_code) > 300 else new_code)
    print("-" * 50)

    print("\n步骤 4: 更新组件文件")
    component_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                  "components", "button_v3.py")
    update_component_file(component_file, new_code)

    print("\n步骤 5: 验证更新效果")
    verify_update(button_v3, component_file)

    print("\n步骤 6: 再次修改颜色（red → green）")
    button_v3 = update_species_color(lib, button_v3, "green")
    new_code = regenerate_component_code(button_v3)
    update_component_file(component_file, new_code)
    verify_update(button_v3, component_file)

    print("\n" + "="*70)
    print("🎉 演示完成！")
    print("="*70)
    print("总结：")
    print("  1. 物种库支持属性动态修改")
    print("  2. 修改后自动重新生成组件代码")
    print("  3. 组件文件同步更新")
    print("  4. 零Token更新 — 无需调用LLM")
    print("="*70)


if __name__ == "__main__":
    main()
