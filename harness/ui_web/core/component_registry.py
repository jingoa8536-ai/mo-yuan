"""
UI Harness — 组件注册表
======================
所有组件的元数据注册中心。
每个组件 = 唯一ID + 名称 + 类别 + 标签 + 依赖 + 属性Schema。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("ui_harness.registry")


@dataclass
class ComponentMeta:
    """组件元数据。"""
    id: str                              # 唯一标识 (如 "button_primary")
    name: str                            # 显示名称
    category: str                        # atom / molecule / section / page / three
    description: str = ""
    tags: List[str] = field(default_factory=list)
    variants: List[str] = field(default_factory=list)  # 变体列表
    dependencies: List[str] = field(default_factory=list)  # 依赖的组件ID
    props_schema: Dict[str, Any] = field(default_factory=dict)  # 属性Schema
    design_requirements: Dict[str, Any] = field(default_factory=dict)  # 设计需求
    template_path: Optional[str] = None  # 模板文件路径
    preview: Optional[str] = None        # 预览图路径
    quality_score: float = 95.0          # 质量评分

    def match_tags(self, tags: List[str]) -> float:
        """计算与标签列表的匹配度。"""
        if not tags or not self.tags:
            return 0.0
        self_set = set(t.lower() for t in self.tags)
        query_set = set(t.lower() for t in tags)
        if not query_set:
            return 0.0
        intersection = self_set & query_set
        return len(intersection) / len(query_set)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "tags": self.tags,
            "variants": self.variants,
            "dependencies": self.dependencies,
            "quality_score": self.quality_score,
        }


# ════════════════════════════════════════════════════════════
# 组件注册表
# ════════════════════════════════════════════════════════════


class ComponentRegistry:
    """
    组件注册表 — 所有组件的元数据中心。
    
    用法:
        reg = ComponentRegistry()
        reg.register_all()  # 注册所有内置组件
        comp = reg.find("button_primary")
        results = reg.search(["dark", "hero"])
    """

    def __init__(self):
        self._components: Dict[str, ComponentMeta] = {}
        self._initialized = False

    def register(self, meta: ComponentMeta):
        """注册一个组件。"""
        self._components[meta.id] = meta

    def register_all(self):
        """注册所有内置组件。"""
        if self._initialized:
            return
        self._initialized = True

        # ── 原子组件 ──
        self._register_atoms()
        # ── 分子组件 ──
        self._register_molecules()
        # ── 区块模板 ──
        self._register_sections()
        # ── 3D组件 ──
        self._register_three()
        # ── 整页模板 ──
        self._register_pages()

        logger.info(f"ComponentRegistry: {len(self._components)} 组件已注册")

    def _register_atoms(self):
        atoms = [
            ComponentMeta("button", "Button", "atom", "通用按钮组件",
                tags=["button", "cta", "action", "interactive"],
                variants=["primary", "secondary", "ghost", "outline", "danger", "glass"],
                props_schema={"variant": "string", "size": "sm/md/lg", "disabled": "bool"},
                quality_score=98),
            ComponentMeta("input", "Input", "atom", "通用输入框",
                tags=["input", "form", "text", "search"],
                variants=["text", "email", "password", "search", "textarea", "select", "date", "file"],
                props_schema={"type": "string", "placeholder": "string", "required": "bool"},
                quality_score=96),
            ComponentMeta("typography", "Typography", "atom", "文字排版",
                tags=["text", "heading", "paragraph", "title", "content"],
                variants=["h1", "h2", "h3", "h4", "h5", "h6", "body", "small", "code", "quote"],
                props_schema={"variant": "string", "align": "left/center/right"},
                quality_score=98),
            ComponentMeta("badge", "Badge", "atom", "徽章/标签",
                tags=["badge", "tag", "label", "status"],
                variants=["default", "success", "warning", "error", "info"],
                quality_score=97),
            ComponentMeta("avatar", "Avatar", "atom", "头像",
                tags=["avatar", "profile", "user", "image"],
                variants=["sm", "md", "lg"],
                quality_score=95),
            ComponentMeta("divider", "Divider", "atom", "分割线",
                tags=["divider", "separator", "line"],
                variants=["solid", "dashed", "dotted", "gradient"],
                quality_score=98),
            ComponentMeta("icon", "Icon", "atom", "图标",
                tags=["icon", "svg", "symbol"],
                variants=["lucide", "heroicon"],
                props_schema={"name": "string", "size": "number"},
                quality_score=99),
            ComponentMeta("skeleton", "Skeleton", "atom", "加载骨架屏",
                tags=["loading", "skeleton", "placeholder", "shimmer"],
                variants=["text", "circle", "rect", "card", "table"],
                quality_score=96),
        ]
        for a in atoms:
            self.register(a)

    def _register_molecules(self):
        molecules = [
            ComponentMeta("card", "Card", "molecule", "卡片容器",
                tags=["card", "container", "panel", "box"],
                variants=["default", "hover-scale", "glass", "gradient",
                         "border-accent", "interactive", "padded", "compact",
                         "horizontal", "dashboard", "pricing", "testimonial"],
                dependencies=["typography"],
                quality_score=97),
            ComponentMeta("modal", "Modal", "molecule", "模态框",
                tags=["modal", "dialog", "popup", "overlay"],
                variants=["center", "side", "bottom", "full", "confirm", "form"],
                dependencies=["button", "icon"],
                quality_score=95),
            ComponentMeta("dropdown", "Dropdown", "molecule", "下拉菜单",
                tags=["dropdown", "menu", "select", "popover"],
                variants=["menu", "select", "actions", "user", "notifications"],
                dependencies=["icon"],
                quality_score=96),
            ComponentMeta("tabs", "Tabs", "molecule", "标签页",
                tags=["tabs", "tab", "navigation", "switch"],
                variants=["underline", "pill", "icon", "vertical"],
                quality_score=97),
            ComponentMeta("accordion", "Accordion", "molecule", "手风琴折叠",
                tags=["accordion", "collapse", "expand", "faq"],
                variants=["default", "bordered", "ghost"],
                quality_score=96),
            ComponentMeta("toast", "Toast", "molecule", "通知提示",
                tags=["toast", "notification", "alert", "message"],
                variants=["success", "error", "warning", "info", "loading"],
                dependencies=["icon"],
                quality_score=97),
            ComponentMeta("pagination", "Pagination", "molecule", "分页",
                tags=["pagination", "page", "navigation", "table"],
                variants=["number", "prev-next", "dots", "load-more"],
                quality_score=95),
            ComponentMeta("breadcrumb", "Breadcrumb", "molecule", "面包屑导航",
                tags=["breadcrumb", "navigation", "path"],
                variants=["slash", "arrow", "dot"],
                quality_score=96),
            ComponentMeta("form_group", "FormGroup", "molecule", "表单组",
                tags=["form", "group", "field", "input"],
                dependencies=["input", "typography"],
                quality_score=95),
            ComponentMeta("data_table", "DataTable", "molecule", "数据表格",
                tags=["table", "data", "grid", "list"],
                variants=["default", "sortable", "filterable", "paginated"],
                dependencies=["pagination", "badge"],
                quality_score=93),
            ComponentMeta("tooltip", "Tooltip", "molecule", "提示气泡",
                tags=["tooltip", "hint", "popover", "info"],
                variants=["top", "bottom", "left", "right"],
                quality_score=97),
            ComponentMeta("toggle", "Toggle", "molecule", "开关切换",
                tags=["toggle", "switch", "on-off"],
                variants=["default", "ios-style"],
                quality_score=96),
        ]
        for m in molecules:
            self.register(m)

    def _register_sections(self):
        sections = [
            ComponentMeta("hero_section", "Hero区块", "section", "主视觉区域",
                tags=["hero", "banner", "header", "cover", "intro"],
                variants=[f"template_{i:02d}" for i in range(1, 13)],
                dependencies=["button", "typography", "badge"],
                quality_score=95),
            ComponentMeta("features_section", "特性区块", "section", "功能展示区域",
                tags=["feature", "capability", "grid", "showcase"],
                variants=[f"template_{i:02d}" for i in range(1, 11)],
                dependencies=["card", "typography", "icon"],
                quality_score=96),
            ComponentMeta("pricing_section", "定价区块", "section", "价格展示区域",
                tags=["pricing", "price", "plan", "subscription", "tier"],
                variants=[f"template_{i:02d}" for i in range(1, 9)],
                dependencies=["card", "button", "typography", "toggle"],
                quality_score=95),
            ComponentMeta("cta_section", "CTA区块", "section", "行动号召区域",
                tags=["cta", "call-to-action", "signup", "action"],
                variants=[f"template_{i:02d}" for i in range(1, 7)],
                dependencies=["button", "typography"],
                quality_score=97),
            ComponentMeta("faq_section", "FAQ区块", "section", "常见问题",
                tags=["faq", "question", "help", "accordion"],
                variants=[f"template_{i:02d}" for i in range(1, 6)],
                dependencies=["accordion", "typography"],
                quality_score=96),
            ComponentMeta("testimonials_section", "评价区块", "section", "用户评价",
                tags=["testimonial", "review", "quote", "social-proof"],
                variants=[f"template_{i:02d}" for i in range(1, 8)],
                dependencies=["card", "typography", "avatar"],
                quality_score=95),
            ComponentMeta("footer_section", "页脚区块", "section", "页面底部",
                tags=["footer", "bottom", "links", "copyright"],
                variants=[f"template_{i:02d}" for i in range(1, 7)],
                dependencies=["typography", "icon"],
                quality_score=97),
            ComponentMeta("navbar_section", "导航栏", "section", "顶部导航",
                tags=["navbar", "nav", "menu", "header", "navigation"],
                variants=[f"template_{i:02d}" for i in range(1, 9)],
                dependencies=["button", "icon", "typography"],
                quality_score=96),
            ComponentMeta("stats_section", "统计区块", "section", "数据统计",
                tags=["stats", "statistics", "metrics", "numbers", "achievement"],
                variants=["template_01", "template_02", "template_03"],
                dependencies=["typography"],
                quality_score=95),
            ComponentMeta("gallery_section", "画廊区块", "section", "作品展示",
                tags=["gallery", "showcase", "portfolio", "images", "grid"],
                variants=["template_01", "template_02", "template_03"],
                dependencies=["card", "modal"],
                quality_score=94),
            ComponentMeta("team_section", "团队区块", "section", "团队成员展示",
                tags=["team", "member", "people", "staff", "about"],
                variants=["template_01", "template_02", "template_03"],
                dependencies=["card", "avatar", "typography"],
                quality_score=95),
            ComponentMeta("logos_section", "品牌Logo墙", "section", "合作品牌展示",
                tags=["logo", "brand", "client", "partner", "social-proof"],
                variants=["template_01", "template_02", "template_03"],
                quality_score=96),
            ComponentMeta("contact_section", "联系区块", "section", "联系方式",
                tags=["contact", "form", "reach", "message"],
                variants=["template_01", "template_02"],
                dependencies=["input", "button", "typography"],
                quality_score=95),
        ]
        for s in sections:
            self.register(s)

    def _register_pages(self):
        pages = [
            ComponentMeta("page_landing", "Landing Page", "page", "完整落地页",
                tags=["landing", "page", "full", "marketing", "saas"],
                dependencies=["hero_section", "features_section", "pricing_section",
                             "cta_section", "footer_section", "navbar_section"],
                quality_score=94),
            ComponentMeta("page_dashboard", "仪表盘", "page", "SaaS/管理后台",
                tags=["dashboard", "admin", "data", "analytics"],
                dependencies=["navbar_section", "stats_section", "data_table"],
                quality_score=93),
            ComponentMeta("page_blog", "博客", "page", "博客/文章页",
                tags=["blog", "article", "post", "content"],
                dependencies=["navbar_section", "footer_section"],
                quality_score=94),
            ComponentMeta("page_auth", "登录/注册", "page", "认证页面",
                tags=["auth", "login", "register", "signin", "signup"],
                dependencies=["input", "button", "card", "typography"],
                quality_score=96),
            ComponentMeta("page_portfolio", "作品集", "page", "个人/团队作品集",
                tags=["portfolio", "showcase", "work", "gallery"],
                dependencies=["hero_section", "gallery_section", "contact_section"],
                quality_score=94),
        ]
        for p in pages:
            self.register(p)

    def _register_three(self):
        three_components = [
            ComponentMeta("three_particles", "3D粒子系统", "three", "粒子背景",
                tags=["3d", "particle", "background", "effect"],
                variants=["galaxy", "bokeh", "matrix", "floating"],
                quality_score=94),
            ComponentMeta("three_globe", "3D地球", "three", "3D旋转地球",
                tags=["3d", "globe", "earth", "world", "map"],
                quality_score=93),
            ComponentMeta("three_shapes", "3D浮动几何体", "three", "浮动几何形状",
                tags=["3d", "shape", "floating", "geometric"],
                quality_score=95),
            ComponentMeta("three_wave", "3D波浪表面", "three", "动态波浪",
                tags=["3d", "wave", "surface", "ocean", "water"],
                quality_score=93),
        ]
        for t in three_components:
            self.register(t)

    # ─────────── 查询接口 ───────────

    def find(self, component_id: str) -> Optional[ComponentMeta]:
        """按ID查找组件。"""
        return self._components.get(component_id)

    def search(self, tags: List[str], category: Optional[str] = None,
               top_n: int = 10) -> List[ComponentMeta]:
        """按标签搜索组件。"""
        scored = []
        for comp in self._components.values():
            if category and comp.category != category:
                continue
            score = comp.match_tags(tags)
            if score > 0:
                scored.append((score, comp))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_n]]

    def list_by_category(self, category: str) -> List[ComponentMeta]:
        """按类别列出组件。"""
        return [c for c in self._components.values() if c.category == category]

    def get_dependency_tree(self, component_id: str) -> List[str]:
        """获取组件的完整依赖树。"""
        tree = []
        visited = set()

        def resolve(cid: str):
            if cid in visited:
                return
            visited.add(cid)
            comp = self._components.get(cid)
            if comp:
                for dep in comp.dependencies:
                    resolve(dep)
                tree.append(cid)

        resolve(component_id)
        return tree

    @property
    def count(self) -> int:
        return len(self._components)

    def summary(self) -> dict:
        """返回注册表摘要。"""
        cats = {}
        for c in self._components.values():
            cats.setdefault(c.category, 0)
            cats[c.category] += 1
        return {
            "total": self.count,
            "by_category": cats,
            "initialized": self._initialized,
        }


# 单例
_registry: Optional[ComponentRegistry] = None


def get_registry() -> ComponentRegistry:
    global _registry
    if _registry is None:
        _registry = ComponentRegistry()
        _registry.register_all()
    return _registry


if __name__ == "__main__":
    reg = get_registry()
    print(f"组件注册表: {reg.count} 个组件")
    for cat, count in reg.summary()["by_category"].items():
        print(f"  {cat}: {count}")
    print()
    # 测试搜索
    results = reg.search(["dark", "hero", "landing"])
    print(f"搜索 'dark hero landing': {len(results)} 个结果")
    for c in results[:5]:
        print(f"  [{c.category}] {c.name} ({c.id})")
