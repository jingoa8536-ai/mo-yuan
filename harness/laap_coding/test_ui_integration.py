"""
UI 库集成验证脚本 — 测试所有新增库的可用性
"""
import sys
sys.path.insert(0, 'core')

from harness_ui_db import (
    HarnessUIDatabase,
    UIStyleRegistry,
    HarnessUIIntegrator,
    UI_LIBRARIES,
    ANIMATION_LIBRARIES,
    ICON_LIBRARIES,
)

def test_ui_database():
    """测试 UI 数据库完整性"""
    print("=" * 80)
    print("1. 测试 UI 数据库完整性")
    print("=" * 80)
    
    db = HarnessUIDatabase()
    
    print(f"\n📦 UI 库总数: {len(UI_LIBRARIES)}")
    print(f"🎬 动画/3D 库总数: {len(ANIMATION_LIBRARIES)}")
    print(f"🎯 图标库总数: {len(ICON_LIBRARIES)}")
    print(f"📊 总库数: {len(UI_LIBRARIES) + len(ANIMATION_LIBRARIES) + len(ICON_LIBRARIES)}")
    
    all_libs = {**UI_LIBRARIES, **ANIMATION_LIBRARIES, **ICON_LIBRARIES}
    
    print("\n📋 所有库清单:")
    print("-" * 80)
    for lib_id, lib in all_libs.items():
        print(f"  {lib['name']:30s} | {lib['tech']:30s} | ⭐ {lib['stars']:10s}")
    
    return True

def test_cdn_links():
    """测试 CDN 链接"""
    print("\n" + "=" * 80)
    print("2. 测试 CDN 链接")
    print("=" * 80)
    
    db = HarnessUIDatabase()
    cdn_libs = ["ant_design", "ant_design_vue", "material_ui", "daisyui", "element_plus", "vant"]
    
    print("\n📡 CDN 链接测试:")
    for lib_id in cdn_libs:
        cdn = db.get_cdn_link(lib_id)
        lib = UI_LIBRARIES.get(lib_id)
        status = "✅" if cdn else "❌"
        print(f"  {status} {lib['name']:25s} | {cdn}")
    
    return True

def test_style_registry():
    """测试样式注册表"""
    print("\n" + "=" * 80)
    print("3. 测试样式注册表")
    print("=" * 80)
    
    registry = UIStyleRegistry()
    
    test_libs = [
        "shadcn_ui", "ant_design", "ant_design_vue", "material_ui",
        "chakra_ui", "mantine", "element_plus", "naive_ui",
        "vant", "daisyui", "native_base", "react_native_paper"
    ]
    
    print("\n🎨 样式获取测试:")
    for lib_id in test_libs:
        style = registry.get_style(lib_id)
        status = "✅" if style else "❌"
        lib = UI_LIBRARIES.get(lib_id) or ANIMATION_LIBRARIES.get(lib_id)
        if lib:
            print(f"  {status} {lib['name']:25s} | 样式长度: {len(style)}")
    
    return True

def test_component_rendering():
    """测试组件渲染器"""
    print("\n" + "=" * 80)
    print("4. 测试组件渲染器")
    print("=" * 80)
    
    registry = UIStyleRegistry()
    
    test_cases = [
        ("shadcn_ui", "button"),
        ("shadcn_ui", "card"),
        ("shadcn_ui", "input"),
        ("ant_design", "button"),
        ("ant_design", "card"),
        ("ant_design", "table"),
        ("ant_design_vue", "button"),
        ("ant_design_vue", "card"),
        ("ant_design_vue", "table"),
        ("material_ui", "button"),
        ("material_ui", "card"),
        ("material_ui", "dialog"),
        ("element_plus", "button"),
        ("element_plus", "card"),
        ("element_plus", "table"),
        ("naive_ui", "button"),
        ("naive_ui", "card"),
        ("naive_ui", "data-table"),
        ("vant", "button"),
        ("vant", "card"),
        ("vant", "toast"),
        ("chakra_ui", "button"),
        ("chakra_ui", "card"),
        ("mantine", "button"),
        ("mantine", "card"),
        ("daisyui", "btn"),
        ("daisyui", "card"),
    ]
    
    print("\n🔧 组件渲染测试:")
    success_count = 0
    for lib_id, component in test_cases:
        result = registry.render_component(lib_id, component)
        lib = UI_LIBRARIES.get(lib_id)
        if "not implemented" not in result:
            status = "✅"
            success_count += 1
        else:
            status = "❌"
        if lib:
            print(f"  {status} {lib['name']:20s} / {component:15s} | 长度: {len(result)}")
    
    print(f"\n📊 渲染成功率: {success_count}/{len(test_cases)} ({success_count/len(test_cases)*100:.1f}%)")
    
    return success_count == len(test_cases)

def test_search_functions():
    """测试搜索功能"""
    print("\n" + "=" * 80)
    print("5. 测试搜索功能")
    print("=" * 80)
    
    db = HarnessUIDatabase()
    
    print("\n🔍 按技术栈搜索 React:")
    react_libs = db.list_libraries("React")
    for lib_id, lib in react_libs.items():
        print(f"  - {lib['name']}")
    
    print("\n🔍 按技术栈搜索 Vue:")
    vue_libs = db.list_libraries("Vue")
    for lib_id, lib in vue_libs.items():
        print(f"  - {lib['name']}")
    
    print("\n🔍 搜索 'button' 组件:")
    button_results = db.search_components("button")
    for result in button_results:
        print(f"  - {result['library']}: {result['components']}")
    
    print("\n🔍 按标签搜索 'mobile':")
    mobile_results = db.search_by_tag("mobile")
    for result in mobile_results:
        print(f"  - {result['name']}")
    
    print("\n🔍 按领域搜索 'dashboard':")
    dashboard_results = db.search_by_domain("dashboard")
    for result in dashboard_results:
        print(f"  - {result['name']}")
    
    return True

def test_index_building():
    """测试索引构建"""
    print("\n" + "=" * 80)
    print("6. 测试索引构建")
    print("=" * 80)
    
    db = HarnessUIDatabase()
    
    tag_index = db.build_tag_index()
    domain_index = db.build_domain_index()
    quality_index = db.build_quality_index()
    
    print(f"\n🏷️  标签索引: {len(tag_index)} 个标签")
    print(f"🌐 领域索引: {len(domain_index)} 个领域")
    print(f"⭐ 质量索引: 成熟度{len(quality_index['maturity'])} / 维护{len(quality_index['maintenance'])} / 文档{len(quality_index['documentation'])}")
    
    return True

def test_integrator():
    """测试集成器"""
    print("\n" + "=" * 80)
    print("7. 测试集成器")
    print("=" * 80)
    
    integrator = HarnessUIIntegrator()
    
    test_libs = ["shadcn_ui", "ant_design", "element_plus", "vant", "material_ui"]
    
    print("\n📄 页面生成测试:")
    for lib_id in test_libs:
        page = integrator.generate_page(lib_id, "dashboard")
        lib = UI_LIBRARIES.get(lib_id)
        status = "✅" if lib['name'] in page else "❌"
        if lib:
            print(f"  {status} {lib['name']:20s} | 页面长度: {len(page)}")
    
    print("\n📊 集成状态:")
    status = integrator.status()
    print(f"  UI 库总数: {status['total_ui_libraries']}")
    print(f"  动画库总数: {status['total_animation_libraries']}")
    print(f"  图标库总数: {status['total_icon_libraries']}")
    print(f"  总库数: {status['total_libraries']}")
    print(f"  可用组件数: {status['components_available']}")
    
    return True

def test_new_libraries():
    """测试新增库的完整性"""
    print("\n" + "=" * 80)
    print("8. 测试新增库的完整性")
    print("=" * 80)
    
    new_libs = [
        "ant_design_vue",
        "vant",
        "uni_ui",
        "uview",
        "thor_ui",
        "native_base",
        "react_native_paper",
    ]
    
    print("\n✨ 新增库测试:")
    all_valid = True
    for lib_id in new_libs:
        lib = UI_LIBRARIES.get(lib_id)
        if lib:
            checks = []
            checks.append("name" in lib)
            checks.append("tech" in lib)
            checks.append("url" in lib)
            checks.append("install" in lib)
            checks.append("components" in lib)
            checks.append(len(lib["components"]) > 0)
            
            status = "✅" if all(checks) else "❌"
            if not all(checks):
                all_valid = False
            
            print(f"  {status} {lib['name']:25s} | 组件数: {len(lib['components'])} | 标签: {lib['tags']}")
        else:
            print(f"  ❌ {lib_id}: 未找到")
            all_valid = False
    
    return all_valid

def main():
    """主测试函数"""
    print("\n" + "=" * 80)
    print("LAAP Harness UI 库集成验证")
    print("=" * 80)
    
    tests = [
        ("UI 数据库完整性", test_ui_database),
        ("CDN 链接", test_cdn_links),
        ("样式注册表", test_style_registry),
        ("组件渲染器", test_component_rendering),
        ("搜索功能", test_search_functions),
        ("索引构建", test_index_building),
        ("集成器", test_integrator),
        ("新增库完整性", test_new_libraries),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n✅ {name}: 通过")
            else:
                failed += 1
                print(f"\n❌ {name}: 失败")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name}: 异常 - {e}")
    
    print("\n" + "=" * 80)
    print(f"测试结果: {passed}/{len(tests)} 通过")
    print("=" * 80)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！")
        sys.exit(0)

if __name__ == "__main__":
    main()
