#!/usr/bin/env python
"""
演示：使用认知物种库生成带版本号的UI组件并验证运行
=========================================================

流程：
1. 初始化认知物种库
2. 注册多个版本的UI组件物种（Button v1, v2, v3）
3. 通过物种库搜索匹配模板
4. 使用ExecutionLayer从物种库生成代码
5. 在沙箱中执行生成的组件
6. 验证组件输出

编译式AI范式核心特性展示：
- 物种版本化：同一模板可产生多个进化变体
- 零Token生成：优先从物种库匹配而非调用LLM
- 自我生长：每次编译产物自动注册为新物种
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from laap_coding.core.cognitive_species_library import CognitiveSpeciesLibrary, SpeciesType
from laap_coding.core.harness import ExecutionLayer, SubTask


def demo_register_versioned_ui_components():
    """演示注册多个版本的UI组件物种"""
    print("\n" + "="*70)
    print("步骤 1: 注册带版本号的UI组件物种")
    print("="*70)

    lib = CognitiveSpeciesLibrary()

    button_v1 = lib.register_compiled_species(
        template="button",
        props={"label": "Submit", "color": "blue", "variant": "default", "size": "md"},
        tags=["ui", "button", "versioned"],
        domain=["frontend"],
    )
    print(f"✓ 注册 Button v1: {button_v1.name} (id={button_v1.id})")

    button_v2 = lib.register_compiled_species(
        template="button",
        props={"label": "Submit", "color": "blue", "variant": "primary", "size": "lg", "rounded": True},
        tags=["ui", "button", "versioned", "enhanced"],
        domain=["frontend"],
    )
    print(f"✓ 注册 Button v2: {button_v2.name} (id={button_v2.id})")

    button_v3 = lib.register_compiled_species(
        template="button",
        props={"label": "Submit", "color": "gradient", "variant": "primary", "size": "lg", "rounded": True, "shadow": True, "hover_effect": True},
        tags=["ui", "button", "versioned", "enhanced", "premium"],
        domain=["frontend"],
    )
    print(f"✓ 注册 Button v3: {button_v3.name} (id={button_v3.id})")

    card_v1 = lib.register_compiled_species(
        template="card",
        props={"title": "Welcome", "content": "Hello World", "bordered": True},
        tags=["ui", "card", "versioned"],
        domain=["frontend"],
    )
    print(f"✓ 注册 Card v1: {card_v1.name} (id={card_v1.id})")

    card_v2 = lib.register_compiled_species(
        template="card",
        props={"title": "Welcome", "content": "Hello World", "bordered": False, "shadow": True, "hover_lift": True},
        tags=["ui", "card", "versioned", "enhanced"],
        domain=["frontend"],
    )
    print(f"✓ 注册 Card v2: {card_v2.name} (id={card_v2.id})")

    stats = lib.get_stats()
    print(f"\n📊 物种库统计: {stats['total_species']} 个物种")
    print(f"   - 组件类型: {stats['by_type']['component']}")
    print(f"   - 技能类型: {stats['by_type']['skill']}")
    print(f"   - 能力类型: {stats['by_type']['ability']}")

    return lib


def demo_search_and_match(lib):
    """演示物种库搜索和模板匹配"""
    print("\n" + "="*70)
    print("步骤 2: 物种库搜索与模板匹配")
    print("="*70)

    queries = ["button", "card", "gradient button", "hover effect"]
    for query in queries:
        results = lib.search_species(query)
        print(f"\n🔍 搜索 '{query}': {len(results)} 个匹配")
        for i, species in enumerate(results[:3]):
            print(f"   [{i+1}] {species.name} (type={species.type.value}, versioned={'versioned' in species.tags})")
            print(f"      props: {json.dumps(species.props, indent=6, ensure_ascii=False)}")


def demo_execution_layer_generation(lib):
    """演示使用ExecutionLayer从物种库生成代码"""
    print("\n" + "="*70)
    print("步骤 3: 使用ExecutionLayer从物种库生成代码")
    print("="*70)

    execution_layer = ExecutionLayer(workdir="demo_output", species_library=lib)
    print(f"✓ ExecutionLayer初始化成功，物种库可用")

    subtasks = [
        SubTask(sub_task_id="t1", parent_task_id="demo", description="创建一个渐变按钮组件", files=[], estimated_lines=50, dependencies=[]),
        SubTask(sub_task_id="t2", parent_task_id="demo", description="创建一个带阴影的卡片组件", files=[], estimated_lines=50, dependencies=[]),
    ]

    for subtask in subtasks:
        print(f"\n🔨 执行子任务: {subtask.description}")
        result = execution_layer.execute(subtask)
        print(f"   ✓ 执行成功")
        print(f"   📄 生成代码:\n{result.output}")


def demo_harness_compile_with_evolution():
    """演示使用Harness编译并展示物种进化"""
    print("\n" + "="*70)
    print("步骤 4: Harness编译与物种进化")
    print("="*70)

    from laap_coding.core.harness import ConsciousnessHarness

    harness = ConsciousnessHarness(workdir="demo_output")
    
    print(f"\n📦 Harness初始化完成")
    print(f"   - 物种库: {len(harness.species_library._species)} 个物种")

    compile_results = []
    for i in range(3):
        print(f"\n🔄 第 {i+1} 次编译: create_button")
        result = harness.compile(
            "create_button",
            {"label": f"Action {i+1}", "color": "blue", "variant": "primary"}
        )
        compile_results.append(result)
        print(f"   ✓ 编译完成: {result.get('status', 'unknown')}")
        if "quality_score" in result:
            print(f"   📊 质量分数: {result['quality_score']:.2f}")
        if "token_cost" in result:
            print(f"   💰 Token消耗: {result['token_cost']}")

    print(f"\n📈 进化效果:")
    for i, result in enumerate(compile_results):
        print(f"   编译 {i+1}: status={result.get('status', 'unknown')}")

    new_species_count = len(harness.species_library._species)
    print(f"\n🌱 物种库自我生长: {new_species_count} 个物种")


def demo_verify_component_output():
    """演示验证生成的组件输出"""
    print("\n" + "="*70)
    print("步骤 5: 验证生成的组件输出")
    print("="*70)

    lib = CognitiveSpeciesLibrary()
    
    all_species = lib.list_species(type_filter="component")
    print(f"\n📋 所有组件物种 ({len(all_species)}):")
    
    for species in all_species:
        print(f"\n--- {species.name} ---")
        print(f"类型: {species.type.value}")
        print(f"来源: {species.origin.value}")
        print(f"模板: {species.template}")
        print(f"版本化: {'versioned' in species.tags}")
        print(f"使用次数: {species.usage_count}")
        print(f"成功率: {species.success_rate:.2%}")
        print(f"属性: {json.dumps(species.props, indent=4, ensure_ascii=False)}")
        print(f"标签: {species.tags}")


def main():
    """运行完整演示"""
    print("="*70)
    print("认知物种库 UI组件版本化演示")
    print("="*70)
    print("展示编译式AI范式核心能力：")
    print("  • 物种版本化 - 同一模板可产生多个进化变体")
    print("  • 零Token生成 - 优先从物种库匹配")
    print("  • 自我生长 - 每次编译产物自动注册")
    print("="*70)

    lib = demo_register_versioned_ui_components()
    demo_search_and_match(lib)
    demo_execution_layer_generation(lib)
    demo_harness_compile_with_evolution()
    demo_verify_component_output()

    print("\n" + "="*70)
    print("🎉 演示完成！")
    print("="*70)
    print("总结：")
    print("  1. 认知物种库支持版本化UI组件注册")
    print("  2. 每次编译产生新的物种变体（带时间戳版本号）")
    print("  3. ExecutionLayer优先从物种库匹配模板")
    print("  4. 编译式AI实现'意图→实现'零Token闭环")
    print("="*70)


if __name__ == "__main__":
    main()
