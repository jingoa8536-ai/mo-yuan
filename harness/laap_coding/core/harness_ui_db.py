"""
harness_ui_db.py — LAAP Harness UI 数据库
=========================================
完整收录 React / Vue / Tailwind / Flutter / Rust 顶级 UI 库
每个库含: 元数据, 组件索引, 模板生成器, 下载/引用方式
"""
import os, json, subprocess
from typing import Dict, Any, Optional

HARNESS_CORE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(HARNESS_CORE, "templates", "ui")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# ═══════════════════════════════════════════════
# 1. UI 库元数据库
# ═══════════════════════════════════════════════
UI_LIBRARIES = {
    # ── React 生态 ──
    "shadcn_ui": {
        "name": "shadcn/ui",
        "stars": "118k+",
        "tech": "React + Tailwind",
        "url": "https://ui.shadcn.com",
        "repo": "https://github.com/shadcn-ui/ui",
        "install": "npx shadcn@latest init",
        "desc": "复制即用的 React 组件库，无样式锁定",
        "components": ["button", "card", "dialog", "dropdown", "form", "input", "modal", "nav", "table", "tabs", "toast"],
        "style": "modern-minimal",
        "templates": ["landing-page", "dashboard", "settings", "auth"],
                    "tags": ["react", "tailwind", "ui", "components"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "ant_design": {
        "name": "Ant Design",
        "stars": "93k+",
        "tech": "React",
        "url": "https://ant.design",
        "repo": "https://github.com/ant-design/ant-design",
        "install": "npm install antd",
        "desc": "企业级中后台设计系统，60+ 组件",
        "components": ["table", "form", "datepicker", "upload", "tree", "menu", "layout", "chart"],
        "style": "enterprise-standard",
        "templates": ["admin-panel", "dashboard", "login"],
        "tags": ["react", "enterprise", "ui", "design-system"],
        "domain": ["frontend", "enterprise", "dashboard"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "material_ui": {
        "name": "Material UI (MUI)",
        "stars": "94k+",
        "tech": "React (Material Design)",
        "url": "https://mui.com",
        "repo": "https://github.com/mui/material-ui",
        "install": "npm install @mui/material",
        "desc": "Google Material Design 实现，全球最流行",
        "components": ["button", "card", "dialog", "drawer", "grid", "stepper", "table", "tabs"],
        "style": "material-design",
        "templates": ["dashboard", "ecommerce", "blog"],
        "tags": ["react", "material-design", "ui", "design-system"],
        "domain": ["frontend", "dashboard", "ecommerce"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "heroui": {
        "name": "HeroUI (原 NextUI)",
        "stars": "22k+",
        "tech": "React + Tailwind",
        "url": "https://heroui.com",
        "repo": "https://github.com/heroui-inc/heroui",
        "install": "npm install @heroui/react",
        "desc": "现代 React UI，自带暗黑模式，组件精致",
        "components": ["button", "card", "input", "modal", "navbar", "table", "tabs", "tooltip"],
        "style": "modern-glossy",
        "templates": ["saas-landing", "app-dashboard"],
        "tags": ["react", "tailwind", "ui", "dark-mode"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "astryx": {
        "name": "Astryx (Meta)",
        "stars": "Meta 内部开源",
        "tech": "React",
        "url": "https://astryx.atmeta.com",
        "install": "内部包管理器",
        "desc": "Meta 工业级设计系统，150+ 组件，7 主题",
        "components": ["button", "card", "data-table", "form", "icon", "layout", "menu", "modal"],
        "style": "enterprise-meta",
        "templates": ["admin", "dashboard"],
        "tags": ["react", "enterprise", "meta", "design-system"],
        "domain": ["frontend", "enterprise", "internal"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "internal"},
    },
    # ── Vue 生态 ──
    "element_plus": {
        "name": "Element Plus",
        "stars": "25k+",
        "tech": "Vue 3",
        "url": "https://element-plus.org",
        "repo": "https://github.com/element-plus/element-plus",
        "install": "npm install element-plus",
        "desc": "饿了么出品，Vue 3 桌面端组件库",
        "components": ["table", "form", "dialog", "menu", "tree", "upload", "datepicker", "pagination"],
        "style": "enterprise-standard",
        "templates": ["admin", "crm", "dashboard"],
        "tags": ["vue", "enterprise", "ui", "components"],
        "domain": ["frontend", "enterprise", "dashboard"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "naive_ui": {
        "name": "Naive UI",
        "stars": "16k+",
        "tech": "Vue 3 + TypeScript",
        "url": "https://www.naiveui.com",
        "repo": "https://github.com/tusen-ai/naive-ui",
        "install": "npm install naive-ui",
        "desc": "Vue 3 高质量组件库，TypeScript 优先",
        "components": ["button", "card", "data-table", "dialog", "form", "menu", "select", "tree"],
        "style": "modern-standard",
        "templates": ["dashboard", "settings", "login"],
        "tags": ["vue", "typescript", "ui", "components"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── Tailwind 生态 ──
    "daisyui": {
        "name": "DaisyUI",
        "stars": "35k+",
        "tech": "Tailwind CSS",
        "url": "https://daisyui.com",
        "repo": "https://github.com/saadeghi/daisyui",
        "install": "npm install daisyui",
        "desc": "Tailwind CSS 语义化组件，换肤极简",
        "components": ["btn", "card", "collapse", "dropdown", "modal", "navbar", "tab", "table"],
        "style": "tailwind-semantic",
        "templates": ["landing", "admin", "blog"],
        "tags": ["tailwind", "css", "ui", "theming"],
        "domain": ["frontend", "landing", "blog"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "float_ui": {
        "name": "Float UI",
        "stars": "5k+",
        "tech": "Tailwind CSS",
        "url": "https://floatui.com",
        "install": "复制 HTML",
        "desc": "Tailwind 官网/后台区块模板",
        "components": ["hero", "feature", "pricing", "faq", "footer", "nav", "cta"],
        "style": "tailwind-landing",
        "templates": ["saas-landing", "startup", "enterprise"],
        "tags": ["tailwind", "css", "landing", "blocks"],
        "domain": ["frontend", "landing", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── 无样式库 ──
    "headless_ui": {
        "name": "Headless UI",
        "stars": "26k+",
        "tech": "React/Vue (无样式)",
        "url": "https://headlessui.com",
        "repo": "https://github.com/tailwindlabs/headlessui",
        "install": "npm install @headlessui/react",
        "desc": "完全无样式、无障碍的底层 UI 组件",
        "components": ["listbox", "menu", "switch", "tabs", "dialog", "popover"],
        "style": "unstyled",
        "templates": [],
        "tags": ["react", "vue", "headless", "accessibility"],
        "domain": ["frontend", "design-system"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── Flutter ──
    "forui": {
        "name": "Forui",
        "stars": "Flutter package",
        "tech": "Flutter/Dart",
        "url": "https://forui.dev",
        "repo": "https://github.com/duobaseio/forui",
        "install": "flutter pub add forui",
        "desc": "Flutter UI 库，shadcn/ui 风格，40+ 组件",
        "components": ["button", "card", "dialog", "form", "input", "list", "scaffold", "tabs"],
        "style": "shadcn-flutter",
        "templates": ["mobile-app", "settings"],
        "tags": ["flutter", "dart", "ui", "shadcn"],
        "domain": ["mobile", "flutter", "frontend"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── 新增 React UI 库 ──
    "chakra_ui": {
        "name": "Chakra UI",
        "stars": "35k+",
        "tech": "React",
        "url": "https://chakra-ui.com",
        "repo": "https://github.com/chakra-ui/chakra-ui",
        "install": "npm install @chakra-ui/react @emotion/react @emotion/styled framer-motion",
        "desc": "简单、模块化、可访问的 React UI 组件库",
        "components": ["button", "card", "dialog", "form", "input", "modal", "nav", "select", "tabs", "tooltip"],
        "style": "modern-minimal",
        "templates": ["dashboard", "landing", "auth"],
        "tags": ["react", "ui", "accessibility", "design-system"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "radix_ui": {
        "name": "Radix UI",
        "stars": "21k+",
        "tech": "React (无样式)",
        "url": "https://radix-ui.com",
        "repo": "https://github.com/radix-ui/primitives",
        "install": "npm install @radix-ui/react-slot",
        "desc": "高质量、无障碍的无样式 UI 原语组件库",
        "components": ["accordion", "alert-dialog", "aspect-ratio", "avatar", "button", "checkbox", "dialog", "dropdown-menu", "input", "label"],
        "style": "unstyled",
        "templates": [],
        "tags": ["react", "headless", "accessibility", "primitives"],
        "domain": ["frontend", "design-system"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "shadcn_vue": {
        "name": "shadcn-vue",
        "stars": "9k+",
        "tech": "Vue 3 + Tailwind",
        "url": "https://vue.shadcn.com",
        "repo": "https://github.com/shadcn-vue/shadcn-vue",
        "install": "npx shadcn-vue@latest init",
        "desc": "shadcn/ui 的 Vue 3 移植版，复制即用组件",
        "components": ["button", "card", "dialog", "dropdown", "form", "input", "modal", "nav", "table", "tabs", "toast"],
        "style": "modern-minimal",
        "templates": ["landing-page", "dashboard", "settings", "auth"],
        "tags": ["vue", "tailwind", "ui", "components"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "prime_react": {
        "name": "PrimeReact",
        "stars": "13k+",
        "tech": "React",
        "url": "https://primereact.org",
        "repo": "https://github.com/primefaces/primereact",
        "install": "npm install primereact",
        "desc": "企业级 React UI 组件库，80+ 组件，丰富主题",
        "components": ["button", "card", "chart", "data-table", "dialog", "form", "input", "menu", "tree", "upload"],
        "style": "enterprise-standard",
        "templates": ["admin-panel", "dashboard", "crm"],
        "tags": ["react", "enterprise", "ui", "components"],
        "domain": ["frontend", "enterprise", "dashboard"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "mantine": {
        "name": "Mantine",
        "stars": "23k+",
        "tech": "React",
        "url": "https://mantine.dev",
        "repo": "https://github.com/mantinedev/mantine",
        "install": "npm install @mantine/core @mantine/hooks",
        "desc": "功能丰富的 React UI 组件库，支持 SSR，100+ 组件",
        "components": ["button", "card", "dialog", "form", "grid", "input", "modal", "nav", "table", "tabs", "tooltip"],
        "style": "modern-standard",
        "templates": ["dashboard", "ecommerce", "blog"],
        "tags": ["react", "ui", "ssr", "design-system"],
        "domain": ["frontend", "dashboard", "saas"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    # ── Vue 生态补充 ──
    "ant_design_vue": {
        "name": "Ant Design Vue",
        "stars": "19k+",
        "tech": "Vue 2/3",
        "url": "https://antdv.com",
        "repo": "https://github.com/vueComponent/ant-design-vue",
        "install": "npm install ant-design-vue",
        "desc": "蚂蚁集团出品，Ant Design 的 Vue 实现，适合企业级中后台",
        "components": ["table", "form", "datepicker", "upload", "tree", "menu", "layout", "modal", "message"],
        "style": "enterprise-standard",
        "templates": ["admin-panel", "dashboard", "login"],
        "tags": ["vue", "enterprise", "ui", "design-system"],
        "domain": ["frontend", "enterprise", "dashboard"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── 移动端/跨端组件库 ──
    "vant": {
        "name": "Vant",
        "stars": "22k+",
        "tech": "Vue 2/3 + 微信小程序",
        "url": "https://youzan.github.io/vant",
        "repo": "https://github.com/youzan/vant",
        "install": "npm install vant",
        "desc": "有赞出品，轻量可靠的移动端 Vue 组件库，支持小程序",
        "components": ["button", "cell", "dialog", "form", "icon", "loading", "picker", "popup", "toast", "tabs"],
        "style": "mobile-lightweight",
        "templates": ["mobile-h5", "mini-program", "ecommerce-app"],
        "tags": ["vue", "mobile", "mini-program", "ui"],
        "domain": ["mobile", "frontend", "ecommerce"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "uni_ui": {
        "name": "uni-ui",
        "stars": "10k+",
        "tech": "uni-app",
        "url": "https://uniapp.dcloud.net.cn/component/uniui/uni-ui.html",
        "repo": "https://github.com/dcloudio/uni-ui",
        "install": "npm install @dcloudio/uni-ui",
        "desc": "DCloud 出品，uni-app 跨端组件库，支持 App/H5/小程序",
        "components": ["uni-card", "uni-dialog", "uni-forms", "uni-list", "uni-nav-bar", "uni-picker", "uni-popup", "uni-tabs"],
        "style": "cross-platform",
        "templates": ["cross-platform-app", "mini-program", "mobile-app"],
        "tags": ["uni-app", "vue", "cross-platform", "mobile"],
        "domain": ["mobile", "frontend", "cross-platform"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "uview": {
        "name": "uView",
        "stars": "16k+",
        "tech": "uni-app (Vue 2)",
        "url": "https://uviewui.com",
        "repo": "https://github.com/umicro/uView2.0",
        "install": "npm install uview-ui",
        "desc": "uni-app 生态最流行的 UI 框架，全面的组件库",
        "components": ["button", "card", "form", "grid", "icon", "loading", "modal", "navbar", "swiper", "tabs"],
        "style": "cross-platform-rich",
        "templates": ["cross-platform-app", "social-app", "business-app"],
        "tags": ["uni-app", "vue", "cross-platform", "mobile"],
        "domain": ["mobile", "frontend", "cross-platform"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "thor_ui": {
        "name": "ThorUI",
        "stars": "5k+",
        "tech": "uni-app (Vue 2/3)",
        "url": "https://thorui.cn",
        "repo": "https://github.com/thorui/thorui-uniapp",
        "install": "npm install thorui-uni",
        "desc": "高质量 uni-app 组件库，精美 UI 设计，多端兼容",
        "components": ["button", "card", "dialog", "form", "icon", "list", "loading", "navbar", "popup", "tabs"],
        "style": "modern-mobile",
        "templates": ["cross-platform-app", "mobile-h5", "mini-program"],
        "tags": ["uni-app", "vue", "cross-platform", "mobile"],
        "domain": ["mobile", "frontend", "cross-platform"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    # ── 移动端 React 组件库 ──
    "native_base": {
        "name": "Native Base",
        "stars": "19k+",
        "tech": "React Native",
        "url": "https://nativebase.io",
        "repo": "https://github.com/GeekyAnts/NativeBase",
        "install": "npm install native-base",
        "desc": "React Native 全平台 UI 组件库，一套代码适配多端",
        "components": ["button", "card", "dialog", "form", "icon", "input", "modal", "picker", "tabs", "view"],
        "style": "react-native",
        "templates": ["mobile-app", "cross-platform-app"],
        "tags": ["react-native", "mobile", "cross-platform", "ui"],
        "domain": ["mobile", "frontend", "cross-platform"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "react_native_paper": {
        "name": "React Native Paper",
        "stars": "11k+",
        "tech": "React Native (Material Design)",
        "url": "https://reactnativepaper.com",
        "repo": "https://github.com/callstack/react-native-paper",
        "install": "npm install react-native-paper",
        "desc": "React Native Material Design 组件库，Google 风格",
        "components": ["appbar", "badge", "button", "card", "dialog", "floating-action-button", "icon-button", "list", "text-input"],
        "style": "material-design-mobile",
        "templates": ["mobile-app", "android-app"],
        "tags": ["react-native", "material-design", "mobile", "ui", "cross-platform"],
        "domain": ["mobile", "frontend", "cross-platform"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
}

# ── 社区灵感库 ──
UI_COMMUNITY = {
    "uiverse": {
        "name": "Uiverse",
        "desc": "5400+ 纯 CSS/Tailwind 组件，开源社区",
        "url": "https://uiverse.io",
        "lang": "CSS/Tailwind/React/Vue",
    },
    "aceternity": {
        "name": "Aceternity UI",
        "desc": "Framer Motion 动效组件库",
        "url": "https://ui.aceternity.com",
        "lang": "React + Framer Motion",
    },
}


# ═══════════════════════════════════════════════
# 2. 3D/动画库元数据库
# ═══════════════════════════════════════════════
ANIMATION_LIBRARIES = {
    "three_js": {
        "name": "Three.js",
        "stars": "95k+",
        "tech": "JavaScript/WebGL",
        "url": "https://threejs.org",
        "repo": "https://github.com/mrdoob/three.js",
        "install": "npm install three",
        "desc": "最流行的 WebGL 3D 库，创建高性能 3D 场景",
        "features": ["3d-rendering", "scene-graph", "materials", "geometry", "lighting", "animation", "camera", "controls"],
        "category": "3d",
        "templates": ["3d-scene", "product-showcase", "data-visualization"],
        "tags": ["3d", "webgl", "graphics", "animation"],
        "domain": ["frontend", "3d", "visualization"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "gsap": {
        "name": "GSAP (GreenSock)",
        "stars": "17k+",
        "tech": "JavaScript",
        "url": "https://greensock.com",
        "repo": "https://github.com/greensock/GSAP",
        "install": "npm install gsap",
        "desc": "业界领先的 JavaScript 动画库，高性能时间轴动画",
        "features": ["tween", "timeline", "scroll-trigger", "physics", "draggable", "morph"],
        "category": "animation",
        "templates": ["landing-animations", "scroll-effects", "micro-interactions"],
        "tags": ["animation", "tween", "timeline", "greensock"],
        "domain": ["frontend", "animation", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "framer_motion": {
        "name": "Framer Motion",
        "stars": "23k+",
        "tech": "React",
        "url": "https://www.framer.com/motion",
        "repo": "https://github.com/framer/motion",
        "install": "npm install framer-motion",
        "desc": "React 首选动画库，声明式 API，支持手势和布局动画",
        "features": ["motion", "animate", "transition", "gestures", "layout", "scroll", "variants"],
        "category": "animation",
        "templates": ["page-transitions", "interactive-ui", "hero-sections"],
        "tags": ["react", "animation", "motion", "framer"],
        "domain": ["frontend", "animation", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "lenis": {
        "name": "Lenis",
        "stars": "13k+",
        "tech": "JavaScript",
        "url": "https://lenis.studiofreight.com",
        "repo": "https://github.com/studio-freight/lenis",
        "install": "npm install @studio-freight/lenis",
        "desc": "平滑滚动库，支持惯性滚动和自定义缓动",
        "features": ["smooth-scroll", "inertia", "scroll-snap", "performance", "custom-easing"],
        "category": "animation",
        "templates": ["scroll-animations", "parallax", "one-page"],
        "tags": ["scroll", "animation", "smooth", "performance"],
        "domain": ["frontend", "animation", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "babylon_js": {
        "name": "Babylon.js",
        "stars": "22k+",
        "tech": "JavaScript/WebGL",
        "url": "https://www.babylonjs.com",
        "repo": "https://github.com/BabylonJS/Babylon.js",
        "install": "npm install @babylonjs/core",
        "desc": "强大的 WebGL 3D 引擎，游戏级渲染能力",
        "features": ["3d-rendering", "physics", "particles", "materials", "lighting", "VR/AR", "animation"],
        "category": "3d",
        "templates": ["game-scene", "vr-experience", "3d-product"],
        "tags": ["3d", "webgl", "game-engine", "babylon"],
        "domain": ["frontend", "3d", "gaming", "vr"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
}


# ═══════════════════════════════════════════════
# 3. 图标库元数据库
# ═══════════════════════════════════════════════
ICON_LIBRARIES = {
    "lucide": {
        "name": "Lucide Icons",
        "stars": "20k+",
        "tech": "React/Vue/Svelte/Angular",
        "url": "https://lucide.dev",
        "repo": "https://github.com/lucide/lucide",
        "install": "npm install lucide-react",
        "desc": "精美的开源图标库，支持多种框架，1000+ 图标",
        "icon_count": "1200+",
        "styles": ["outline", "solid", "duotone"],
        "category": "icons",
        "tags": ["icons", "react", "vue", "svg"],
        "domain": ["frontend", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "excellent"},
    },
    "heroicons": {
        "name": "Heroicons",
        "stars": "22k+",
        "tech": "React/Vue",
        "url": "https://heroicons.com",
        "repo": "https://github.com/tailwindlabs/heroicons",
        "install": "npm install @heroicons/react",
        "desc": "Tailwind Labs 出品，精美的 SVG 图标集",
        "icon_count": "400+",
        "styles": ["outline", "solid", "mini"],
        "category": "icons",
        "tags": ["icons", "react", "vue", "tailwind"],
        "domain": ["frontend", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
    "phosphor_icons": {
        "name": "Phosphor Icons",
        "stars": "10k+",
        "tech": "React/Vue/Svelte/Angular/HTML",
        "url": "https://phosphoricons.com",
        "repo": "https://github.com/phosphor-icons/phosphor-icons",
        "install": "npm install phosphor-react",
        "desc": "灵活的图标库，支持多种粗细和风格变体",
        "icon_count": "1400+",
        "styles": ["thin", "light", "regular", "bold", "fill", "duotone"],
        "category": "icons",
        "tags": ["icons", "react", "vue", "svg", "variants"],
        "domain": ["frontend", "ui"],
        "quality": {"maturity": "production", "maintenance": "active", "documentation": "good"},
    },
}


class HarnessUIDatabase:
    """UI 数据库 — 查询/生成/集成"""
    
    @staticmethod
    def list_libraries(tech: Optional[str] = None) -> Dict:
        """列出所有 UI 库，可按技术栈筛选"""
        if tech:
            return {k: v for k, v in UI_LIBRARIES.items() if v["tech"].lower().startswith(tech.lower())}
        return UI_LIBRARIES
    
    @staticmethod
    def get_library(name: str) -> Optional[Dict]:
        return UI_LIBRARIES.get(name)
    
    @staticmethod
    def search_components(query: str) -> list:
        """搜索某种 UI 组件在哪些库中可用"""
        results = []
        for lib_id, lib in UI_LIBRARIES.items():
            matching = [c for c in lib["components"] if query.lower() in c.lower()]
            if matching:
                results.append({"library": lib["name"], "components": matching})
        return results
    
    @staticmethod
    def get_cdn_link(lib_id: str) -> Optional[str]:
        """获取 CDN 引用链接"""
        cdn_map = {
            "ant_design": "https://unpkg.com/antd/dist/reset.css",
            "ant_design_vue": "https://unpkg.com/ant-design-vue@latest/dist/reset.css",
            "material_ui": "https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap",
            "daisyui": "https://cdn.jsdelivr.net/npm/daisyui@4/dist/full.min.css",
            "element_plus": "https://unpkg.com/element-plus/dist/index.css",
            "vant": "https://cdn.jsdelivr.net/npm/vant@latest/lib/index.css",
        }
        return cdn_map.get(lib_id)
    
    @staticmethod
    def list_animation_libraries(category: Optional[str] = None) -> Dict:
        """列出所有动画/3D库，可按类别筛选"""
        if category:
            return {k: v for k, v in ANIMATION_LIBRARIES.items() if v.get("category") == category}
        return ANIMATION_LIBRARIES
    
    @staticmethod
    def get_animation_library(name: str) -> Optional[Dict]:
        return ANIMATION_LIBRARIES.get(name)
    
    @staticmethod
    def list_icon_libraries() -> Dict:
        """列出所有图标库"""
        return ICON_LIBRARIES
    
    @staticmethod
    def get_icon_library(name: str) -> Optional[Dict]:
        return ICON_LIBRARIES.get(name)
    
    @staticmethod
    def search_by_tag(tag: str) -> list:
        """按标签搜索所有库"""
        results = []
        for lib_id, lib in UI_LIBRARIES.items():
            if lib.get("tags") and tag.lower() in [t.lower() for t in lib["tags"]]:
                results.append({"type": "ui", "id": lib_id, **lib})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            if lib.get("tags") and tag.lower() in [t.lower() for t in lib["tags"]]:
                results.append({"type": "animation", "id": lib_id, **lib})
        for lib_id, lib in ICON_LIBRARIES.items():
            if lib.get("tags") and tag.lower() in [t.lower() for t in lib["tags"]]:
                results.append({"type": "icons", "id": lib_id, **lib})
        return results
    
    @staticmethod
    def search_by_domain(domain: str) -> list:
        """按领域搜索所有库"""
        results = []
        for lib_id, lib in UI_LIBRARIES.items():
            if lib.get("domain") and domain.lower() in [d.lower() for d in lib["domain"]]:
                results.append({"type": "ui", "id": lib_id, **lib})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            if lib.get("domain") and domain.lower() in [d.lower() for d in lib["domain"]]:
                results.append({"type": "animation", "id": lib_id, **lib})
        for lib_id, lib in ICON_LIBRARIES.items():
            if lib.get("domain") and domain.lower() in [d.lower() for d in lib["domain"]]:
                results.append({"type": "icons", "id": lib_id, **lib})
        return results
    
    @staticmethod
    def search_by_quality(maturity: Optional[str] = None, maintenance: Optional[str] = None) -> list:
        """按质量指标搜索所有库"""
        results = []
        for lib_id, lib in UI_LIBRARIES.items():
            q = lib.get("quality", {})
            if (maturity and q.get("maturity") != maturity) or (maintenance and q.get("maintenance") != maintenance):
                continue
            results.append({"type": "ui", "id": lib_id, **lib})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            q = lib.get("quality", {})
            if (maturity and q.get("maturity") != maturity) or (maintenance and q.get("maintenance") != maintenance):
                continue
            results.append({"type": "animation", "id": lib_id, **lib})
        for lib_id, lib in ICON_LIBRARIES.items():
            q = lib.get("quality", {})
            if (maturity and q.get("maturity") != maturity) or (maintenance and q.get("maintenance") != maintenance):
                continue
            results.append({"type": "icons", "id": lib_id, **lib})
        return results
    
    @staticmethod
    def build_tag_index() -> Dict:
        """构建标签索引"""
        index = {}
        for lib_id, lib in UI_LIBRARIES.items():
            for tag in lib.get("tags", []):
                index.setdefault(tag, []).append({"type": "ui", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            for tag in lib.get("tags", []):
                index.setdefault(tag, []).append({"type": "animation", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ICON_LIBRARIES.items():
            for tag in lib.get("tags", []):
                index.setdefault(tag, []).append({"type": "icons", "id": lib_id, "name": lib["name"]})
        return index
    
    @staticmethod
    def build_domain_index() -> Dict:
        """构建领域索引"""
        index = {}
        for lib_id, lib in UI_LIBRARIES.items():
            for domain in lib.get("domain", []):
                index.setdefault(domain, []).append({"type": "ui", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            for domain in lib.get("domain", []):
                index.setdefault(domain, []).append({"type": "animation", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ICON_LIBRARIES.items():
            for domain in lib.get("domain", []):
                index.setdefault(domain, []).append({"type": "icons", "id": lib_id, "name": lib["name"]})
        return index
    
    @staticmethod
    def build_quality_index() -> Dict:
        """构建质量索引"""
        index = {"maturity": {}, "maintenance": {}, "documentation": {}}
        for lib_id, lib in UI_LIBRARIES.items():
            q = lib.get("quality", {})
            for key, value in q.items():
                if key in index:
                    index[key].setdefault(value, []).append({"type": "ui", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ANIMATION_LIBRARIES.items():
            q = lib.get("quality", {})
            for key, value in q.items():
                if key in index:
                    index[key].setdefault(value, []).append({"type": "animation", "id": lib_id, "name": lib["name"]})
        for lib_id, lib in ICON_LIBRARIES.items():
            q = lib.get("quality", {})
            for key, value in q.items():
                if key in index:
                    index[key].setdefault(value, []).append({"type": "icons", "id": lib_id, "name": lib["name"]})
        return index
    
    @staticmethod
    def export_catalog(path: str = None) -> str:
        """导出完整目录为 JSON"""
        catalog = {
            "metadata": {
                "version": "1.0",
                "protocol": "LAAP Harness",
                "generated_at": __import__('datetime').datetime.now().isoformat(),
            },
            "stats": {
                "total_ui_libraries": len(UI_LIBRARIES),
                "total_animation_libraries": len(ANIMATION_LIBRARIES),
                "total_icon_libraries": len(ICON_LIBRARIES),
                "total_libraries": len(UI_LIBRARIES) + len(ANIMATION_LIBRARIES) + len(ICON_LIBRARIES),
                "total_components": sum(len(l["components"]) for l in UI_LIBRARIES.values()),
            },
            "ui_libraries": UI_LIBRARIES,
            "animation_libraries": ANIMATION_LIBRARIES,
            "icon_libraries": ICON_LIBRARIES,
            "community": UI_COMMUNITY,
            "indexes": {
                "tags": HarnessUIDatabase.build_tag_index(),
                "domains": HarnessUIDatabase.build_domain_index(),
                "quality": HarnessUIDatabase.build_quality_index(),
            },
        }
        output = json.dumps(catalog, indent=2, ensure_ascii=False)
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(output)
        return output


# ═══════════════════════════════════════════════
# 2. 模板生成器
# ═══════════════════════════════════════════════

class UIStyleRegistry:
    """样式注册表 — 映射库名到预编码 HTML/CSS 块"""
    
    @staticmethod
    def get_style(lib_id: str) -> str:
        """获取指定库的样式"""
        styles = {
            "shadcn_ui": """
            /* shadcn/ui — 极简现代风格 */
            :root { --radius: 0.5rem; --background: 0 0% 100%; --foreground: 222.2 84% 4.9%; }
            .dark { --background: 222.2 84% 4.9%; --foreground: 210 40% 98%; }
            """,
            "daisyui": """
            /* DaisyUI — Tailwind 语义化 */
            @import "https://cdn.jsdelivr.net/npm/daisyui@4/full.min.css";
            """,
            "material_ui": """
            /* Material UI — Google Design */
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
            * { font-family: 'Roboto', sans-serif; }
            """,
            "chakra_ui": """
            /* Chakra UI — 简约风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            * { font-family: 'Inter', sans-serif; }
            """,
            "mantine": """
            /* Mantine — 现代风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            * { font-family: 'Inter', sans-serif; }
            """,
            "ant_design": """
            /* Ant Design — 企业风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            """,
            "ant_design_vue": """
            /* Ant Design Vue — 企业风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            """,
            "element_plus": """
            /* Element Plus — 企业风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            """,
            "naive_ui": """
            /* Naive UI — 现代风格 */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            """,
            "vant": """
            /* Vant — 移动端轻量风格 */
            @import url('https://fonts.googleapis.com/css2?family=PingFang+SC:wght@400;500;600;700&display=swap');
            * { font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, sans-serif; }
            """,
            "uni_ui": """
            /* uni-ui — 跨端风格 */
            @import url('https://fonts.googleapis.com/css2?family=PingFang+SC:wght@400;500;600;700&display=swap');
            * { font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, sans-serif; }
            """,
            "uview": """
            /* uView — 跨端丰富风格 */
            @import url('https://fonts.googleapis.com/css2?family=PingFang+SC:wght@400;500;600;700&display=swap');
            * { font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, sans-serif; }
            """,
            "thor_ui": """
            /* ThorUI — 现代移动端风格 */
            @import url('https://fonts.googleapis.com/css2?family=PingFang+SC:wght@400;500;600;700&display=swap');
            * { font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, sans-serif; }
            """,
            "native_base": """
            /* Native Base — React Native 风格 */
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            * { font-family: 'Roboto', sans-serif; }
            """,
            "react_native_paper": """
            /* React Native Paper — Material Design 移动端 */
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            * { font-family: 'Roboto', sans-serif; }
            """,
        }
        return styles.get(lib_id, "")
    
    @staticmethod
    def render_component(lib_id: str, component: str, props: dict = None) -> str:
        """渲染指定库的指定组件"""
        if lib_id == "shadcn_ui":
            return UIStyleRegistry._shadcn_component(component, props or {})
        elif lib_id == "daisyui":
            return UIStyleRegistry._daisyui_component(component, props or {})
        elif lib_id == "chakra_ui":
            return UIStyleRegistry._chakra_component(component, props or {})
        elif lib_id == "mantine":
            return UIStyleRegistry._mantine_component(component, props or {})
        elif lib_id == "ant_design":
            return UIStyleRegistry._ant_design_component(component, props or {})
        elif lib_id == "ant_design_vue":
            return UIStyleRegistry._ant_design_vue_component(component, props or {})
        elif lib_id == "element_plus":
            return UIStyleRegistry._element_plus_component(component, props or {})
        elif lib_id == "naive_ui":
            return UIStyleRegistry._naive_ui_component(component, props or {})
        elif lib_id == "vant":
            return UIStyleRegistry._vant_component(component, props or {})
        elif lib_id == "material_ui":
            return UIStyleRegistry._material_ui_component(component, props or {})
        return f"<!-- {lib_id}/{component} not implemented -->"
    
    @staticmethod
    def _shadcn_component(name: str, props: dict) -> str:
        cards = {
            "button": '<button class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">Button</button>',
            "card": '<div class="rounded-lg border bg-card text-card-foreground shadow-sm"><div class="p-6 pt-0"><h3 class="text-2xl font-semibold leading-none tracking-tight">Card Title</h3><p class="text-sm text-muted-foreground mt-2">Card content here.</p></div></div>',
            "input": '<input class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" placeholder="Input..." />',
        }
        return cards.get(name, f"<!-- shadcn/{name} not implemented -->")
    
    @staticmethod
    def _daisyui_component(name: str, props: dict) -> str:
        cards = {
            "btn": '<button class="btn btn-primary">Button</button>',
            "card": '<div class="card bg-base-100 shadow-xl"><div class="card-body"><h2 class="card-title">Title</h2><p>Content</p></div></div>',
            "navbar": '<div class="navbar bg-base-100"><div class="flex-1"><a class="btn btn-ghost text-xl">Brand</a></div></div>',
        }
        return cards.get(name, f"<!-- daisyui/{name} not implemented -->")
    
    @staticmethod
    def _chakra_component(name: str, props: dict) -> str:
        cards = {
            "button": '<Button colorScheme="blue" size="md">Button</Button>',
            "card": '<Card maxW="sm"><CardBody><Heading size="md">Card Title</Heading><Text mt="2">Card content here.</Text></CardBody></Card>',
            "input": '<Input placeholder="Input..." size="md" />',
        }
        return cards.get(name, f"<!-- chakra/{name} not implemented -->")
    
    @staticmethod
    def _mantine_component(name: str, props: dict) -> str:
        cards = {
            "button": '<Button variant="filled">Button</Button>',
            "card": '<Card padding="lg"><CardTitle>Card Title</CardTitle><CardText>Card content here.</CardText></Card>',
            "input": '<TextInput placeholder="Input..." />',
        }
        return cards.get(name, f"<!-- mantine/{name} not implemented -->")
    
    @staticmethod
    def _ant_design_component(name: str, props: dict) -> str:
        cards = {
            "button": '<Button type="primary">Button</Button>',
            "card": '<Card title="Card Title"><p>Card content here.</p></Card>',
            "input": '<Input placeholder="Input..." />',
            "table": '<Table columns={columns} dataSource={data} />',
            "form": '<Form><Form.Item label="Name"><Input /></Form.Item></Form>',
            "modal": '<Modal title="Title" open={open} onCancel={handleCancel}>Content</Modal>',
        }
        return cards.get(name, f"<!-- ant-design/{name} not implemented -->")
    
    @staticmethod
    def _ant_design_vue_component(name: str, props: dict) -> str:
        cards = {
            "button": '<a-button type="primary">Button</a-button>',
            "card": '<a-card title="Card Title"><p>Card content here.</p></a-card>',
            "input": '<a-input placeholder="Input..." />',
            "table": '<a-table :columns="columns" :data-source="data" />',
            "form": '<a-form><a-form-item label="Name"><a-input /></a-form-item></a-form>',
            "modal": '<a-modal title="Title" :visible="visible" @cancel="handleCancel">Content</a-modal>',
        }
        return cards.get(name, f"<!-- ant-design-vue/{name} not implemented -->")
    
    @staticmethod
    def _element_plus_component(name: str, props: dict) -> str:
        cards = {
            "button": '<el-button type="primary">Button</el-button>',
            "card": '<el-card header="Card Title"><p>Card content here.</p></el-card>',
            "input": '<el-input placeholder="Input..." />',
            "table": '<el-table :data="tableData"><el-table-column prop="name" label="Name" /></el-table>',
            "form": '<el-form><el-form-item label="Name"><el-input /></el-form-item></el-form>',
            "dialog": '<el-dialog title="Title" v-model="visible">Content</el-dialog>',
        }
        return cards.get(name, f"<!-- element-plus/{name} not implemented -->")
    
    @staticmethod
    def _naive_ui_component(name: str, props: dict) -> str:
        cards = {
            "button": '<n-button type="primary">Button</n-button>',
            "card": '<n-card title="Card Title">Card content here.</n-card>',
            "input": '<n-input placeholder="Input..." />',
            "data-table": '<n-data-table :columns="columns" :data="data" />',
            "dialog": '<n-dialog title="Title" v-model:show="show">Content</n-dialog>',
            "form": '<n-form :model="form"><n-form-item label="Name"><n-input v-model:value="form.name" /></n-form-item></n-form>',
        }
        return cards.get(name, f"<!-- naive-ui/{name} not implemented -->")
    
    @staticmethod
    def _vant_component(name: str, props: dict) -> str:
        cards = {
            "button": '<van-button type="primary">Button</van-button>',
            "cell": '<van-cell title="Cell" value="Value" />',
            "card": '<van-card title="Card Title" description="Card description" />',
            "input": '<van-field v-model="value" placeholder="Input..." />',
            "dialog": '<van-dialog v-model:show="show" title="Title">Content</van-dialog>',
            "toast": '<van-toast>Message</van-toast>',
            "tabs": '<van-tabs><van-tab title="Tab 1">Content</van-tab></van-tabs>',
            "loading": '<van-loading type="spinner" />',
        }
        return cards.get(name, f"<!-- vant/{name} not implemented -->")
    
    @staticmethod
    def _material_ui_component(name: str, props: dict) -> str:
        cards = {
            "button": '<Button variant="contained">Button</Button>',
            "card": '<Card><CardContent><Typography gutterBottom variant="h5">Card Title</Typography><Typography variant="body2">Card content here.</Typography></CardContent></Card>',
            "input": '<TextField label="Input" variant="outlined" />',
            "dialog": '<Dialog open={open} onClose={handleClose}><DialogTitle>Title</DialogTitle><DialogContent>Content</DialogContent></Dialog>',
            "tabs": '<Tabs value={value} onChange={handleChange}><Tab label="Tab 1" /></Tabs>',
            "drawer": '<Drawer anchor="left" open={open} onClose={handleClose}>Content</Drawer>',
        }
        return cards.get(name, f"<!-- material-ui/{name} not implemented -->")


class HarnessUIIntegrator:
    """将 UI 库集成到 Harness 工程中"""
    
    @staticmethod
    def generate_page(lib_id: str, page_type: str = "landing") -> str:
        """使用指定库生成页面"""
        lib = UI_LIBRARIES.get(lib_id) or ANIMATION_LIBRARIES.get(lib_id) or ICON_LIBRARIES.get(lib_id)
        if not lib:
            return f"/* Library {lib_id} not found */"
        
        style = UIStyleRegistry.get_style(lib_id)
        cdn = HarnessUIDatabase.get_cdn_link(lib_id)
        
        return f"""<!-- {lib['name']} — {lib['desc']} -->
<style>{style}</style>
{cdn or ''}
<!-- Generated page type: {page_type} -->
"""
    
    @staticmethod
    def clone_github(lib_id: str) -> bool:
        """克隆库到本地模板目录"""
        lib = UI_LIBRARIES.get(lib_id) or ANIMATION_LIBRARIES.get(lib_id) or ICON_LIBRARIES.get(lib_id)
        if not lib or 'repo' not in lib:
            return False
        target = os.path.join(TEMPLATE_DIR, lib_id)
        if os.path.exists(target):
            return True
        try:
            subprocess.run(['git', 'clone', '--depth', '1', lib['repo'], target],
                         capture_output=True, timeout=60)
            return os.path.exists(target)
        except Exception as e:
            print(f"Clone failed: {e}")
            return False
    
    @staticmethod
    def status() -> dict:
        """集成状态报告"""
        cloned = []
        all_libs = {**UI_LIBRARIES, **ANIMATION_LIBRARIES, **ICON_LIBRARIES}
        for lib_id in all_libs:
            target = os.path.join(TEMPLATE_DIR, lib_id)
            if os.path.exists(target):
                cloned.append(lib_id)
        return {
            "total_ui_libraries": len(UI_LIBRARIES),
            "total_animation_libraries": len(ANIMATION_LIBRARIES),
            "total_icon_libraries": len(ICON_LIBRARIES),
            "total_libraries": len(all_libs),
            "cloned_local": cloned,
            "template_dir": TEMPLATE_DIR,
            "components_available": sum(len(l["components"]) for l in UI_LIBRARIES.values()),
        }


if __name__ == "__main__":
    db = HarnessUIDatabase()
    print("=" * 80)
    print("LAAP Harness UI 数据库 — 完整库索引")
    print("=" * 80)
    
    print(f"\n📦 UI 库 ({len(UI_LIBRARIES)} 个):")
    print("-" * 80)
    for lib_id, lib in UI_LIBRARIES.items():
        print(f"  {lib['name']:22s} | {lib['tech']:25s} | ⭐ {lib['stars']:10s} | {len(lib['components'])} 组件")
    
    print(f"\n🎬 动画/3D 库 ({len(ANIMATION_LIBRARIES)} 个):")
    print("-" * 80)
    for lib_id, lib in ANIMATION_LIBRARIES.items():
        print(f"  {lib['name']:22s} | {lib['tech']:25s} | ⭐ {lib['stars']:10s} | {lib['category']:10s}")
    
    print(f"\n🎯 图标库 ({len(ICON_LIBRARIES)} 个):")
    print("-" * 80)
    for lib_id, lib in ICON_LIBRARIES.items():
        print(f"  {lib['name']:22s} | {lib['tech']:25s} | ⭐ {lib['stars']:10s} | {lib['icon_count']:10s}")
    
    print(f"\n📊 统计:")
    print(f"  - 总库数: {len(UI_LIBRARIES) + len(ANIMATION_LIBRARIES) + len(ICON_LIBRARIES)}")
    print(f"  - UI 组件总数: {sum(len(l['components']) for l in UI_LIBRARIES.values())}")
    print(f"  - 模板目录: {TEMPLATE_DIR}")
    print(f"  - 集成状态: {HarnessUIIntegrator.status()}")
