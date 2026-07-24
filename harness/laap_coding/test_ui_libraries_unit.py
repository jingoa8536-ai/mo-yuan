"""
UI 库单元测试 — 针对新集成库的详细测试用例
使用纯 Python 测试方式，覆盖所有新增库的元数据、组件、样式和渲染功能
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

NEW_LIBRARIES = [
    "ant_design_vue",
    "vant",
    "uni_ui",
    "uview",
    "thor_ui",
    "native_base",
    "react_native_paper",
]

passed = 0
failed = 0
failures = []


def test(name, condition, message=""):
    global passed, failed, failures
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        failures.append(f"❌ {name}: {message}")
        print(f"  ❌ {name}: {message}")


def run_all_tests():
    global passed, failed, failures
    
    print("\n" + "=" * 80)
    print("UI 库单元测试 — 新增库验证")
    print("=" * 80)
    
    print("\n【测试组 1】新增库元数据完整性")
    print("-" * 60)
    for lib_id in NEW_LIBRARIES:
        test(f"库 {lib_id} 存在", lib_id in UI_LIBRARIES, f"不存在于 UI_LIBRARIES")
    
    required_fields = ["name", "tech", "url", "install", "desc", "components", "style", "templates", "tags", "domain", "quality"]
    for lib_id in NEW_LIBRARIES:
        lib = UI_LIBRARIES[lib_id]
        for field in required_fields:
            test(f"{lib['name']} 包含 {field}", field in lib, f"缺少字段: {field}")
    
    for lib_id in NEW_LIBRARIES:
        lib = UI_LIBRARIES[lib_id]
        components = lib.get("components", [])
        test(f"{lib['name']} 组件列表非空", len(components) > 0, "组件列表为空")
        tags = lib.get("tags", [])
        test(f"{lib['name']} 标签列表非空", len(tags) > 0, "标签列表为空")
        domain = lib.get("domain", [])
        test(f"{lib['name']} 领域列表非空", len(domain) > 0, "领域列表为空")
    
    for lib_id in NEW_LIBRARIES:
        lib = UI_LIBRARIES[lib_id]
        url = lib.get("url", "")
        test(f"{lib['name']} URL 格式正确", url.startswith("http"), f"URL: {url}")
    
    print("\n【测试组 2】新增库分类正确性")
    print("-" * 60)
    vue_libs = ["ant_design_vue", "vant", "uni_ui", "uview", "thor_ui"]
    for lib_id in vue_libs:
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 包含 vue 标签", "vue" in lib["tags"], "缺少 vue 标签")
    
    mobile_libs = ["vant", "uni_ui", "uview", "thor_ui", "native_base", "react_native_paper"]
    for lib_id in mobile_libs:
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 包含 mobile 标签", "mobile" in lib["tags"], "缺少 mobile 标签")
    
    cross_platform_libs = ["uni_ui", "uview", "thor_ui", "native_base", "react_native_paper"]
    for lib_id in cross_platform_libs:
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 包含 cross-platform 标签", "cross-platform" in lib["tags"], "缺少 cross-platform 标签")
    
    uni_app_libs = ["uni_ui", "uview", "thor_ui"]
    for lib_id in uni_app_libs:
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 包含 uni-app 标签", "uni-app" in lib["tags"], "缺少 uni-app 标签")
    
    rn_libs = ["native_base", "react_native_paper"]
    for lib_id in rn_libs:
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 包含 react-native 标签", "react-native" in lib["tags"], "缺少 react-native 标签")
    
    print("\n【测试组 3】新增库组件列表")
    print("-" * 60)
    vant = UI_LIBRARIES["vant"]
    mobile_components = ["cell", "picker", "popup", "toast", "loading"]
    for comp in mobile_components:
        test(f"Vant 包含 {comp}", comp in vant["components"], f"缺少移动端组件: {comp}")
    
    uni_ui = UI_LIBRARIES["uni_ui"]
    for comp in uni_ui["components"]:
        test(f"uni-ui 组件 {comp} 使用 uni- 前缀", comp.startswith("uni-"), f"未使用 uni- 前缀")
    
    rn_paper = UI_LIBRARIES["react_native_paper"]
    material_components = ["appbar", "floating-action-button", "icon-button", "text-input"]
    for comp in material_components:
        test(f"React Native Paper 包含 {comp}", comp in rn_paper["components"], f"缺少 Material 组件: {comp}")
    
    ant_vue = UI_LIBRARIES["ant_design_vue"]
    enterprise_components = ["table", "form", "datepicker", "upload", "tree", "menu", "layout"]
    for comp in enterprise_components:
        test(f"Ant Design Vue 包含 {comp}", comp in ant_vue["components"], f"缺少企业级组件: {comp}")
    
    print("\n【测试组 4】新增库样式注册表")
    print("-" * 60)
    for lib_id in NEW_LIBRARIES:
        style = UIStyleRegistry.get_style(lib_id)
        test(f"{UI_LIBRARIES[lib_id]['name']} 样式非空", style != "", "样式为空")
    
    chinese_libs = ["vant", "uni_ui", "uview", "thor_ui"]
    for lib_id in chinese_libs:
        style = UIStyleRegistry.get_style(lib_id)
        test(f"{UI_LIBRARIES[lib_id]['name']} 包含 PingFang 字体", "PingFang" in style, "缺少 PingFang 字体")
    
    english_libs = ["native_base", "react_native_paper"]
    for lib_id in english_libs:
        style = UIStyleRegistry.get_style(lib_id)
        test(f"{UI_LIBRARIES[lib_id]['name']} 包含 Roboto 字体", "Roboto" in style, "缺少 Roboto 字体")
    
    print("\n【测试组 5】新增库组件渲染器")
    print("-" * 60)
    test_cases = [
        ("ant_design_vue", "button", "a-button"),
        ("ant_design_vue", "card", "a-card"),
        ("ant_design_vue", "input", "a-input"),
        ("ant_design_vue", "table", "a-table"),
        ("vant", "button", "van-button"),
        ("vant", "card", "van-card"),
        ("vant", "cell", "van-cell"),
        ("vant", "toast", "van-toast"),
        ("vant", "loading", "van-loading"),
        ("element_plus", "button", "el-button"),
        ("element_plus", "card", "el-card"),
        ("element_plus", "table", "el-table"),
        ("naive_ui", "button", "n-button"),
        ("naive_ui", "card", "n-card"),
        ("naive_ui", "input", "n-input"),
        ("material_ui", "button", "Button"),
        ("material_ui", "card", "Card"),
        ("material_ui", "dialog", "Dialog"),
    ]
    
    for lib_id, component, expected_tag in test_cases:
        result = UIStyleRegistry.render_component(lib_id, component)
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} {component} 渲染包含 {expected_tag}", expected_tag in result, f"渲染结果: {result[:50]}")
        test(f"{lib['name']} {component} 已实现", "not implemented" not in result, "未实现")
    
    print("\n【测试组 6】新增库搜索功能")
    print("-" * 60)
    db = HarnessUIDatabase()
    
    vue_results = db.search_by_tag("vue")
    vue_names = [r["name"] for r in vue_results]
    vue_expected = ["Ant Design Vue", "Vant", "uni-ui", "uView", "ThorUI"]
    for name in vue_expected:
        test(f"按 vue 标签搜索找到 {name}", name in vue_names, "未找到")
    
    mobile_results = db.search_by_tag("mobile")
    mobile_names = [r["name"] for r in mobile_results]
    mobile_expected = ["Vant", "uni-ui", "uView", "ThorUI", "Native Base", "React Native Paper"]
    for name in mobile_expected:
        test(f"按 mobile 标签搜索找到 {name}", name in mobile_names, "未找到")
    
    cross_platform_results = db.search_by_tag("cross-platform")
    cross_platform_names = [r["name"] for r in cross_platform_results]
    cp_expected = ["uni-ui", "uView", "ThorUI", "Native Base", "React Native Paper"]
    for name in cp_expected:
        test(f"按 cross-platform 标签搜索找到 {name}", name in cross_platform_names, "未找到")
    
    rn_results = db.search_by_tag("react-native")
    rn_names = [r["name"] for r in rn_results]
    test("按 react-native 标签搜索找到 Native Base", "Native Base" in rn_names, "未找到")
    test("按 react-native 标签搜索找到 React Native Paper", "React Native Paper" in rn_names, "未找到")
    
    domain_mobile_results = db.search_by_domain("mobile")
    domain_mobile_names = [r["name"] for r in domain_mobile_results]
    for name in mobile_expected:
        test(f"按 mobile 领域搜索找到 {name}", name in domain_mobile_names, "未找到")
    
    button_results = db.search_components("button")
    button_names = [r["library"] for r in button_results]
    button_expected = ["Vant", "uView", "ThorUI", "Native Base", "React Native Paper"]
    for name in button_expected:
        test(f"搜索 button 组件找到 {name}", name in button_names, "未找到")
    
    print("\n【测试组 7】新增库 CDN 链接")
    print("-" * 60)
    cdn_test_cases = [
        ("ant_design_vue", "ant-design-vue"),
        ("vant", "vant"),
    ]
    for lib_id, expected in cdn_test_cases:
        cdn = db.get_cdn_link(lib_id)
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} CDN 链接存在", cdn is not None, "缺少 CDN 链接")
        test(f"{lib['name']} CDN 链接正确", expected in cdn, f"CDN: {cdn}")
    
    print("\n【测试组 8】新增库集成器功能")
    print("-" * 60)
    integrator = HarnessUIIntegrator()
    test_libs = ["ant_design_vue", "vant", "native_base"]
    
    for lib_id in test_libs:
        page = integrator.generate_page(lib_id, "dashboard")
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 页面生成包含库名", lib["name"] in page, "页面不包含库名")
        test(f"{lib['name']} 页面包含生成标记", "Generated page type" in page, "页面缺少生成标记")
    
    status = integrator.status()
    test(f"集成器 UI 库总数为 23", status["total_ui_libraries"] == 23, f"实际: {status['total_ui_libraries']}")
    test(f"集成器总库数为 31", status["total_libraries"] == 31, f"实际: {status['total_libraries']}")
    test(f"集成器组件总数为 206", status["components_available"] == 206, f"实际: {status['components_available']}")
    
    print("\n【测试组 9】新增库索引构建")
    print("-" * 60)
    tag_index = db.build_tag_index()
    test("标签索引包含 uni-app", "uni-app" in tag_index, "缺少 uni-app")
    test("标签索引包含 cross-platform", "cross-platform" in tag_index, "缺少 cross-platform")
    test("标签索引包含 react-native", "react-native" in tag_index, "缺少 react-native")
    test("标签索引包含 mini-program", "mini-program" in tag_index, "缺少 mini-program")
    
    domain_index = db.build_domain_index()
    test("领域索引包含 mobile", "mobile" in domain_index, "缺少 mobile")
    test("领域索引包含 cross-platform", "cross-platform" in domain_index, "缺少 cross-platform")
    
    quality_index = db.build_quality_index()
    test("质量索引包含 maturity", "maturity" in quality_index, "缺少 maturity")
    test("质量索引包含 maintenance", "maintenance" in quality_index, "缺少 maintenance")
    test("质量索引包含 documentation", "documentation" in quality_index, "缺少 documentation")
    
    print("\n【测试组 10】新增库边界情况")
    print("-" * 60)
    for lib_id in NEW_LIBRARIES:
        result = UIStyleRegistry.render_component(lib_id, "nonexistent-component")
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 无效组件返回 not implemented", "not implemented" in result, "无效组件处理不正确")
    
    page = integrator.generate_page("nonexistent-library")
    test("无效库返回 not found", "not found" in page.lower(), "无效库处理不正确")
    
    for lib_id in ["ant_design_vue", "vant"]:
        result = UIStyleRegistry.render_component(lib_id, "button", {})
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 空 props 正常渲染", "not implemented" not in result, "空 props 处理不正确")
    
    print("\n【测试组 11】回归测试 — 现有库不受影响")
    print("-" * 60)
    existing_libs = [
        ("shadcn_ui", "button"),
        ("ant_design", "button"),
        ("material_ui", "button"),
        ("chakra_ui", "button"),
        ("mantine", "button"),
        ("daisyui", "btn"),
    ]
    
    for lib_id, component in existing_libs:
        style = UIStyleRegistry.get_style(lib_id)
        lib = UI_LIBRARIES[lib_id]
        test(f"{lib['name']} 样式仍然非空", style != "", "样式为空")
        
        result = UIStyleRegistry.render_component(lib_id, component)
        test(f"{lib['name']} {component} 渲染仍然正常", "not implemented" not in result, f"{component} 渲染失败")
    
    react_results = db.list_libraries("React")
    test("React 库搜索结果 >= 10", len(react_results) >= 10, f"实际: {len(react_results)}")
    
    vue_results = db.list_libraries("Vue")
    test("Vue 库搜索结果 >= 5", len(vue_results) >= 5, f"实际: {len(vue_results)}")
    
    print("\n" + "=" * 80)
    print(f"测试结果: {passed}/{passed + failed} 通过")
    print("=" * 80)
    
    if failures:
        print("\n失败详情:")
        for failure in failures:
            print(f"  {failure}")
        print(f"\n❌ 共 {failed} 个测试失败")
        return False
    else:
        print("\n🎉 所有测试通过！")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
