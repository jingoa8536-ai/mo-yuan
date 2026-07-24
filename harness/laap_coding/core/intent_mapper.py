"""
intent_mapper.py — 零 Token 意图匹配引擎
========================================
代码匹配 + 工程JSON化 + 指令工程算法

自然语言 → 结构化 JSON Spec → 生产级页面
完全纯 Python, 零 Token 消耗, ~0.1ms

用法:
    mapper = IntentMapper()
    spec = mapper.parse("暗色SaaS落地页带3D粒子背景")
    # → 完整 JSON Spec, 可直接喂给 HarnessComposer / ProductionComposer
"""

import json, os, re
from typing import Dict, Any, Optional, List

# ── 尝试导入 HEP 注册表 (可选集成) ──
try:
    from hep_protocol import REGISTRY as HEP_REGISTRY
    _HEP_AVAILABLE = True
except ImportError:
    HEP_REGISTRY = None
    _HEP_AVAILABLE = False


# ═══════════════════════════════════════════════
# 1. 页面类型定义 — 代码匹配的核心语料
# ═══════════════════════════════════════════════

PAGE_TYPES = {
    "saas": {
        "aliases": ["saas", "软件服务", "云服务", "订阅", "平台"],
        "label": "SaaS 产品",
        "sections": ["hero", "stats", "features", "pricing", "cta"],
        "default_features": "saas",
    },
    "landing": {
        "aliases": ["落地页", "landing", "推广", "宣传", "产品页"],
        "label": "产品落地页",
        "sections": ["hero", "features", "testimonials", "cta"],
        "default_features": "startup",
    },
    "dashboard": {
        "aliases": ["仪表盘", "dashboard", "管理后台", "数据面板", "控制台"],
        "label": "数据仪表盘",
        "sections": ["hero", "stats", "grid", "cta"],
        "default_features": "analytics",
    },
    "blog": {
        "aliases": ["博客", "blog", "文章", "新闻", "媒体"],
        "label": "博客/内容站",
        "sections": ["hero", "grid", "cta"],
        "default_features": "content",
    },
    "portfolio": {
        "aliases": ["作品集", "portfolio", "个人主页", "简历", "展示"],
        "label": "作品集",
        "sections": ["hero", "stats", "grid"],
        "default_features": "creative",
    },
    "pricing": {
        "aliases": ["定价", "pricing", "价格", "套餐", "方案"],
        "label": "定价页",
        "sections": ["hero", "pricing", "cta"],
        "default_features": "business",
    },
    "documentation": {
        "aliases": ["文档", "docs", "文档站", "帮助", "手册", "开发文档"],
        "label": "文档站",
        "sections": ["hero", "grid", "cta"],
        "default_features": "developer",
    },
    "ecommerce": {
        "aliases": ["电商", "商城", "商店", "购物", "ecommerce", "shop", "store"],
        "label": "电商首页",
        "sections": ["hero", "features", "grid", "cta"],
        "default_features": "product",
    },
    "startup": {
        "aliases": ["创业", "startup", "科技公司", "AI公司", "创新"],
        "label": "创业公司首页",
        "sections": ["hero", "stats", "features", "testimonials", "cta", "pricing"],
        "default_features": "startup",
    },
    "agency": {
        "aliases": ["代理", "agency", "服务商", "咨询", "设计公司"],
        "label": "服务商/代理",
        "sections": ["hero", "stats", "features", "testimonials", "cta"],
        "default_features": "service",
    },
    "app": {
        "aliases": ["应用", "app", "移动端", "手机应用", "下载页"],
        "label": "应用推广页",
        "sections": ["hero", "features", "cta"],
        "default_features": "mobile",
    },
    "event": {
        "aliases": ["活动", "event", "会议", "大会", "峰会", "展会"],
        "label": "活动/会议页",
        "sections": ["hero", "stats", "features", "cta"],
        "default_features": "event",
    },
}

# ═══════════════════════════════════════════════
# 2. 风格映射 — 关键词 → 主题 ID
# ═══════════════════════════════════════════════

STYLE_MAP = {
    # 暗色系
    "暗色": "apple_dark", "深色": "apple_dark", "黑色": "apple_dark",
    "dark": "apple_dark", "premium": "apple_dark",
    # 浅色系
    "浅色": "apple_light", "白色": "apple_light", "light": "apple_light",
    "clean": "apple_light",
    # 科技
    "科技": "dark_tech", "科技感": "dark_tech", "赛博": "dark_tech",
    "cyber": "dark_tech", "tech": "dark_tech", "暗黑": "dark_tech",
    # 暖色
    "暖": "warm_earth", "暖色": "warm_earth", "暖土": "warm_earth",
    "warm": "warm_earth", "earth": "warm_earth",
    # 玻璃
    "玻璃": "glassmorphism", "毛玻璃": "glassmorphism", "frosted": "glassmorphism",
    "glass": "glassmorphism", "现代": "glassmorphism",
    # 极简
    "极简": "minimal_white", "简约": "minimal_white", "纯白": "minimal_white",
    "minimal": "minimal_white", "white": "minimal_white",
    # 复古
    "复古": "retro_terminal", "终端": "retro_terminal", "retro": "retro_terminal",
    "terminal": "retro_terminal", "黑客": "retro_terminal",
    # 日落
    "日落": "sunset", "暖色渐变": "sunset", "sunset": "sunset",
    "夕阳": "sunset",
    # 海洋
    "海洋": "ocean", "深海": "ocean", "蓝色": "ocean", "ocean": "ocean",
    "blue": "ocean", "冷静": "ocean",
}

# ═══════════════════════════════════════════════
# 3. 特征检测 — 关键词 → 参数开关
# ═══════════════════════════════════════════════

# 风格 → 是否默认 3D (根据 STYLE_PRESETS 中 three_d=True 的预设)
_THREE_D_STYLES = {"apple_dark", "dark_tech", "glassmorphism", "sunset", "ocean"}

FEATURE_DETECT = {
    "three_d": {
        "keywords": ["3d", "粒子", "三维", "3D", "three.js", "threejs", "空间", "立体"],
        "default_set": _THREE_D_STYLES,
    },
    "animations": {
        "keywords": ["动效", "动画", "微动效", "滚动", "transition", "animate"],
        "default": True,
    },
    "smooth_scroll": {
        "keywords": ["平滑", "滚动", "smooth", "lenis"],
        "default": False,
    },
    "dark_mode_toggle": {
        "keywords": ["深色模式切换", "亮暗切换", "dark mode toggle"],
        "default": False,
    },
}


# ═══════════════════════════════════════════════
# 4. 内容模板 — 场景化标题/描述/功能
# ═══════════════════════════════════════════════

FEATURE_TEMPLATES = {
    "saas": {
        "hero_badge": "下一代 SaaS 平台",
        "hero_title_default": "重塑你的工作方式",
        "hero_subtitle_default": "新一代云端协作平台，AI 驱动、实时同步、安全可靠",
        "stats": [
            {"number": "99.9%", "label": "正常运行时间"},
            {"number": "10K+", "label": "企业客户"},
            {"number": "50M+", "label": "月活用户"},
            {"number": "150+", "label": "集成应用"},
        ],
        "features": [
            {"title": "AI 智能分析", "desc": "基于大模型的数据洞察，自动发现业务趋势与异常", "icon": "Brain"},
            {"title": "实时协做", "desc": "多人同时编辑，毫秒级同步，冲突自动解决", "icon": "Users"},
            {"title": "安全合规", "desc": "SOC2 认证，端到端加密，GDPR 合规", "icon": "Shield"},
            {"title": "自动化工作流", "desc": "可视化流程编排，点击即用，无需代码", "icon": "Zap"},
            {"title": "开放 API", "desc": "RESTful + GraphQL，与现有系统无缝集成", "icon": "Code"},
            {"title": "数据看板", "desc": "自定义仪表盘，拖拽式报表，实时刷新", "icon": "BarChart3"},
        ],
        "cta_title": "开始免费试用",
        "cta_subtitle": "无需信用卡，14天全功能体验",
    },
    "startup": {
        "hero_badge": "颠覆性创新",
        "hero_title_default": "用AI重新定义\n行业未来",
        "hero_subtitle_default": "我们正在构建下一代智能平台，让每个企业都能释放数据的真正价值",
        "stats": [
            {"number": "$50M+", "label": "融资总额"},
            {"number": "200+", "label": "团队成员"},
            {"number": "50K+", "label": "活跃用户"},
            {"number": "30+", "label": "国家覆盖"},
        ],
        "features": [
            {"title": "核心技术", "desc": "自研 AI 引擎，推理速度领先业界 10 倍", "icon": "Cpu"},
            {"title": "产品矩阵", "desc": "从数据采集到决策输出的完整产品线", "icon": "Layers"},
            {"title": "生态开放", "desc": "开发者优先，开放平台 + 插件市场", "icon": "Globe"},
            {"title": "企业级", "desc": "私有化部署，支持混合云/多云架构", "icon": "Building2"},
            {"title": "实时处理", "desc": "流式计算引擎，毫秒级延迟", "icon": "Activity"},
            {"title": "智能运维", "desc": "自动扩缩容，异常自愈，零运维成本", "icon": "Bot"},
        ],
        "cta_title": "加入我们",
        "cta_subtitle": "和顶尖团队一起创造未来",
    },
    "analytics": {
        "hero_badge": "数据驱动决策",
        "hero_title_default": "洞见未来\n数据有灵",
        "hero_subtitle_default": "AI 增强的分析平台，从海量数据中发现隐藏的商业洞察",
        "stats": [
            {"number": "10B+", "label": "日处理事件"},
            {"number": "0.5s", "label": "查询响应"},
            {"number": "99.9%", "label": "数据准确率"},
            {"number": "500+", "label": "数据源支持"},
        ],
        "features": [
            {"title": "实时分析", "desc": "流式数据处理，结果即时可见", "icon": "Activity"},
            {"title": "AI 预测", "desc": "机器学习模型自动预测趋势", "icon": "TrendingUp"},
            {"title": "数据可视化", "desc": "50+ 图表类型，拖拽式仪表盘", "icon": "BarChart4"},
            {"title": "异常检测", "desc": "自动识别数据异常并告警", "icon": "AlertTriangle"},
            {"title": "自然语言查询", "desc": "用日常语言问数据，AI 自动生成分析", "icon": "MessageSquare"},
            {"title": "数据治理", "desc": "血缘追踪、质量监控、权限管理", "icon": "CheckSquare"},
        ],
        "cta_title": "开始分析",
        "cta_subtitle": "免费体验企业级分析平台",
    },
    "creative": {
        "hero_badge": "创意无限",
        "hero_title_default": "让创意\n触手可及",
        "hero_subtitle_default": "设计师 × 开发者 × 梦想家 — 用技术放大创造力",
        "stats": [
            {"number": "500+", "label": "项目作品"},
            {"number": "50+", "label": "全球客户"},
            {"number": "10年", "label": "行业经验"},
            {"number": "20+", "label": "国际奖项"},
        ],
        "features": [
            {"title": "品牌设计", "desc": "从 logo 到 VI 系统的完整品牌体系", "icon": "Palette"},
            {"title": "交互设计", "desc": "用户研究驱动的体验设计", "icon": "Fingerprint"},
            {"title": "动效设计", "desc": "Lottie/Rive 动效，让界面活起来", "icon": "Sparkles"},
            {"title": "前端开发", "desc": "像素级还原，响应式 + 可访问性", "icon": "Code2"},
            {"title": "3D 可视化", "desc": "Three.js / WebGL 沉浸式体验", "icon": "Cube3d"},
            {"title": "品牌策略", "desc": "数据驱动的品牌定位与传播", "icon": "Target"},
        ],
        "cta_title": "联系我",
        "cta_subtitle": "一起创造令人惊叹的作品",
    },
    "content": {
        "hero_badge": "最新文章",
        "hero_title_default": "深度思考\n洞察未来",
        "hero_subtitle_default": "关于技术、设计和产品的深度思考与实践",
        "stats": [
            {"number": "200+", "label": "文章"},
            {"number": "50K+", "label": "订阅者"},
            {"number": "5年", "label": "持续更新"},
            {"number": "10+", "label": "系列专题"},
        ],
        "features": [
            {"title": "技术深度", "desc": "系统架构、底层原理、实战经验", "icon": "BookOpen"},
            {"title": "设计思考", "desc": "设计系统、交互模式、审美哲学", "icon": "PenTool"},
            {"title": "产品方法论", "desc": "从 0 到 1、增长策略、组织文化", "icon": "Lightbulb"},
            {"title": "月度精选", "desc": "每月精选内容，直接送到邮箱", "icon": "Mail"},
        ],
        "cta_title": "订阅更新",
        "cta_subtitle": "每周一封，深度内容直达",
    },
    "business": {
        "hero_badge": "灵活定价",
        "hero_title_default": "选择适合\n你的方案",
        "hero_subtitle_default": "从个人到企业，总有一款适合你",
        "stats": [
            {"number": "3", "label": "可选套餐"},
            {"number": "99.9%", "label": "服务可用性"},
            {"number": "24/7", "label": "技术支持"},
            {"number": "14天", "label": "免费试用"},
        ],
        "features": [
            {"title": "基础版", "desc": "个人开发者和小团队的理想选择", "icon": "Rocket"},
            {"title": "专业版", "desc": "成长型企业的完整工具链", "icon": "Star"},
            {"title": "企业版", "desc": "大客户专属定制方案", "icon": "Crown"},
        ],
        "cta_title": "查看完整定价",
        "cta_subtitle": "所有方案均支持按年付费，享 20% 优惠",
    },
    "developer": {
        "hero_badge": "开发者文档",
        "hero_title_default": "构建\n无限可能",
        "hero_subtitle_default": "完整的 API 文档、SDK 指南和最佳实践",
        "stats": [
            {"number": "200+", "label": "API 端点"},
            {"number": "12", "label": "SDK 语言"},
            {"number": "99.9%", "label": "API 可用性"},
            {"number": "<50ms", "label": "平均延迟"},
        ],
        "features": [
            {"title": "快速开始", "desc": "5 分钟完成集成", "icon": "Zap"},
            {"title": "API 参考", "desc": "完整的端点文档和示例", "icon": "FileJson"},
            {"title": "SDK 指南", "desc": "Python / JS / Go / Rust 等", "icon": "Package"},
            {"title": "最佳实践", "desc": "安全、性能、可扩展性指南", "icon": "BookMarked"},
        ],
        "cta_title": "查看文档",
        "cta_subtitle": "开发者优先，文档即代码",
    },
    "product": {
        "hero_badge": "新品首发",
        "hero_title_default": "重新定义\n产品体验",
        "hero_subtitle_default": "精心打磨每一处细节，只为更好的使用体验",
        "stats": [
            {"number": "10K+", "label": "已售出"},
            {"number": "4.9", "label": "用户评分"},
            {"number": "99%", "label": "满意度"},
            {"number": "30天", "label": "无忧退换"},
        ],
        "features": [
            {"title": "精湛工艺", "desc": "每一处细节都经过千锤百炼", "icon": "Gem"},
            {"title": "极致性能", "desc": "旗舰级配置，从容应对各种场景", "icon": "Zap"},
            {"title": "生态互联", "desc": "无缝连接你的所有设备", "icon": "Wifi"},
            {"title": "绿色环保", "desc": "100% 可回收材料，碳中和认证", "icon": "Leaf"},
        ],
        "cta_title": "立即购买",
        "cta_subtitle": "限时优惠，免运费",
    },
    "service": {
        "hero_badge": "专业服务",
        "hero_title_default": "用专业\n成就客户",
        "hero_subtitle_default": "10 年行业深耕，服务 500+ 企业客户的信赖之选",
        "stats": [
            {"number": "500+", "label": "服务客户"},
            {"number": "98%", "label": "客户满意度"},
            {"number": "10年", "label": "行业经验"},
            {"number": "50+", "label": "专业团队"},
        ],
        "features": [
            {"title": "战略咨询", "desc": "从业务出发的技术战略规划", "icon": "Compass"},
            {"title": "产品设计", "desc": "用户研究 + 交互设计 + 视觉设计", "icon": "PenTool"},
            {"title": "技术研发", "desc": "从原型到生产级的全栈开发", "icon": "Code"},
            {"title": "运维托管", "desc": "7x24 小时监控和运维保障", "icon": "Shield"},
        ],
        "cta_title": "预约咨询",
        "cta_subtitle": "免费 30 分钟业务诊断",
    },
    "mobile": {
        "hero_badge": "移动先行",
        "hero_title_default": "掌中世界\n触手可及",
        "hero_subtitle_default": "轻量、快速、优雅 — 为移动端精心打造",
        "stats": [
            {"number": "1M+", "label": "下载量"},
            {"number": "4.8", "label": "应用评分"},
            {"number": "99%", "label": "崩溃率 <1%"},
            {"number": "实时", "label": "同步速度"},
        ],
        "features": [
            {"title": "离线可用", "desc": "无网络也能正常使用", "icon": "WifiOff"},
            {"title": "实时同步", "desc": "多设备间无缝切换", "icon": "RefreshCw"},
            {"title": "隐私优先", "desc": "端到端加密，数据主权在你", "icon": "Lock"},
            {"title": "轻盈设计", "desc": "包体仅 15MB，秒级启动", "icon": "Feather"},
        ],
        "cta_title": "立即下载",
        "cta_subtitle": "iOS & Android 双平台",
    },
    "event": {
        "hero_badge": "年度盛会",
        "hero_title_default": "连接思想\n共创未来",
        "hero_subtitle_default": "全球顶尖思想者与实践者的年度聚会",
        "stats": [
            {"number": "3天", "label": "会期"},
            {"number": "100+", "label": "演讲嘉宾"},
            {"number": "5000+", "label": "参会者"},
            {"number": "50+", "label": "合作伙伴"},
        ],
        "features": [
            {"title": "主题演讲", "desc": "行业领袖分享前沿洞察", "icon": "Mic"},
            {"title": "工作坊", "desc": "实践驱动的深度学习", "icon": "Wrench"},
            {"title": "圆桌讨论", "desc": "跨界对话，碰撞思想火花", "icon": "MessageCircle"},
            {"title": "展览展示", "desc": "最新产品和解决方案", "icon": "Eye"},
        ],
        "cta_title": "立即报名",
        "cta_subtitle": "早鸟票限时优惠",
    },
}

# 默认内容模板 (当没有匹配到具体场景时)
DEFAULT_CONTENT = {
    "hero_badge": "全新发布",
    "hero_title_default": "开启\n全新体验",
    "hero_subtitle_default": "我们用技术和设计，创造更美好的数字世界",
    "stats": [
        {"number": "100+", "label": "服务客户"},
        {"number": "99%", "label": "满意度"},
        {"number": "7x24", "label": "技术支持"},
    ],
    "features": [
        {"title": "卓越品质", "desc": "精心打磨的每一个细节", "icon": "Sparkles"},
        {"title": "创新技术", "desc": "前沿技术驱动产品迭代", "icon": "Cpu"},
        {"title": "专业服务", "desc": "从咨询到落地的全程陪伴", "icon": "Headphones"},
    ],
    "cta_title": "了解更多",
    "cta_subtitle": "开启你的专属体验",
}


# ═══════════════════════════════════════════════
# 5. 行业/公司关键词 → 内容匹配
# ═══════════════════════════════════════════════

INDUSTRY_MAP = {
    "ai": {"template": "saas", "keywords": ["ai", "人工智能", "智能", "机器学习", "深度学"]},
    "fintech": {"template": "saas", "keywords": ["金融", "fintech", "支付", "区块链", "银行"]},
    "health": {"template": "saas", "keywords": ["医疗", "健康", "health", "生物", "药"]},
    "education": {"template": "saas", "keywords": ["教育", "edtech", "学", "培训", "课程"]},
    "game": {"template": "creative", "keywords": ["游戏", "gaming", "娱乐", "e-sports"]},
    "blockchain": {"template": "startup", "keywords": ["web3", "区块链", "crypto", "nft", "defi"]},
    "design": {"template": "creative", "keywords": ["设计", "design", "创意", "视觉"]},
}

# 品牌名提取正则
BRAND_PATTERN = re.compile(
    r'(?:叫|品牌|公司|项目|产品)[是为叫]?[：: ]?\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)', re.UNICODE
)
EXPLICIT_TITLE = re.compile(
    r"(?:标题叫|标题|title)[：: ]?\s*[\"']?([^\"'\n，。]+)[\"']?", re.UNICODE
)


# ═══════════════════════════════════════════════
# Lucide SVG 图标 — 零 token 图标生成
# ═══════════════════════════════════════════════

LUCIDE_ICONS = {
    # AI / 技术
    "Brain": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-3.04Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-3.04Z"/>',
    "Cpu": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    "Zap": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "Bot": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="14" x="3" y="4" rx="2" ry="2"/><path d="M9 8h6"/><path d="M9 12h6"/><path d="M9 16h2"/><circle cx="17" cy="10" r=".5" fill="currentColor"/><circle cx="17" cy="14" r=".5" fill="currentColor"/>',
    "Code": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "Code2": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>',
    # 数据 / 分析
    "BarChart3": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 16v-3"/><path d="M11 16v-7"/><path d="M15 16V8"/><path d="M19 16v-2"/>',
    "BarChart4": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M13 16V8"/><path d="M9 16V5"/><path d="M17 16v-5"/>',
    "TrendingUp": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "Activity": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    # 安全
    "Shield": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "Lock": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    # 用户 / 协作
    "Users": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    # 层级 / 平台
    "Layers": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "Globe": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "Building2": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    # 创意
    "Palette": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.5-.5 1.5-1.5 0-.37-.14-.7-.37-.93-.23-.23-.37-.56-.37-.93 0-.93.75-1.5 1.5-1.5H14c5.5 0 10-4.5 10-10 0-5.5-4.5-10-10-10"/>',
    "Fingerprint": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12C2 6.5 6.5 2 12 2s10 4.5 10 10"/><path d="M5 12a7 7 0 0 1 14 0"/><path d="M8 12a4 4 0 0 1 8 0"/><circle cx="12" cy="12" r="2"/>',
    "Sparkles": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.313a3 3 0 0 1-1.775 1.775L3 12l5.313 1.912a3 3 0 0 1 1.775 1.775L12 21l1.912-5.313a3 3 0 0 1 1.775-1.775L21 12l-5.313-1.912a3 3 0 0 1-1.775-1.775L12 3"/><path d="M5 3v4"/><path d="M3 5h4"/><path d="M17 3v4"/><path d="M15 5h4"/>',
    "PenTool": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15.707 21.293a1 1 0 0 1-1.414 0l-1.586-1.586a1 1 0 0 1 0-1.414l5.586-5.586a1 1 0 0 1 1.414 0l1.586 1.586a1 1 0 0 1 0 1.414z"/><path d="m18 13-1.375-6.874a1 1 0 0 0-.746-.776L3.235 2.028a1 1 0 0 0-1.207 1.207L5.35 15.879a1 1 0 0 0 .776.746L13 18"/><path d="m2.3 2.3 7.286 7.286"/><circle cx="11" cy="11" r="2"/>',
    "Cube3d": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21 16-9 5-9-5V8l9-5 9 5v8Z"/><path d="m21 12-9 5-9-5"/><path d="M21 8v4"/><path d="M12 17v4"/><path d="M3 8v4"/><path d="M12 2v4"/>',
    # 数据 / 内容
    "Target": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "Lightbulb": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "BookOpen": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "FileJson": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M10 12a1 1 0 0 0-1 1v1a1 1 0 0 1-1 1 1 1 0 0 1 1 1v1a1 1 0 0 0 1 1"/><path d="M14 18a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1 1 1 0 0 1-1-1v-1a1 1 0 0 0-1-1"/>',
    "Package": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    # 通信 / 消息
    "MessageSquare": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "MessageCircle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "Mail": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    # 检查 / 确认
    "CheckSquare": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
    "AlertTriangle": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    # 杂项
    "Rocket": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "Star": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "Crown": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4v16h20V4l-5 4-5-4-5 4-5-4Z"/><path d="M2 16h20"/>',
    "Gem": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 18 3 22 9 12 22 2 9 6 3"/><path d="m2 9 10-4 10 4"/><path d="M12 3v19"/>',
    "Wifi": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h.01"/><path d="M2 8.82a15 15 0 0 1 20 0"/><path d="M5 12.87a10 10 0 0 1 14 0"/><path d="M8.5 16.9a5 5 0 0 1 7 0"/>',
    "WifiOff": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8.82a15 15 0 0 1 5.6-3.48"/><path d="M5 12.87a10 10 0 0 1 3.34-2.16"/><path d="M8.5 16.9a5 5 0 0 1 2.69-1.44"/><circle cx="12" cy="20" r=".5" fill="currentColor"/><line x1="2" x2="22" y1="2" y2="22"/>',
    "Leaf": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.9C15.5 4.9 17 3.5 19 2c1 2 2 4.5 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "RefreshCw": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/>',
    "Feather": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.67 19a2 2 0 0 0 1.41-.59l6.8-6.8a2 2 0 0 0 0-2.82l-4.67-4.67a2 2 0 0 0-2.82 0l-6.8 6.8a2 2 0 0 0-.59 1.41L6 16.5a1.5 1.5 0 0 0 1.5 1.5Z"/><path d="m5 19 5-5"/><path d="M8 22h5"/>',
    # 事件
    "Mic": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="10" x="5" y="2" rx="2"/><path d="M12 16v5"/><path d="M9 21h6"/><path d="M19 12v2a7 7 0 0 1-14 0v-2"/>',
    "Wrench": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "Eye": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "EyeOff": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>',
    # 导航
    "Compass": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    "Headphones": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
    "BookMarked": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/><polyline points="10 2 10 10 13 7 16 10 16 2"/>',
}

# 生成 Lucide 图标的函数
def lucide_icon(name: str, size: int = 24) -> str:
    """通过名称获取 Lucide SVG 图标，若不匹配返回空字符串"""
    svg = LUCIDE_ICONS.get(name, "")
    if svg:
        # 替换默认尺寸为请求尺寸
        return svg.replace('width="24"', f'width="{size}"').replace('height="24"', f'height="{size}"')
    return ""


class IntentMapper:
    """
    零 Token 意图匹配引擎
    
    代码匹配 → 工程JSON化 → 指令工程
    全程纯 Python, 0 Token, ~0.1ms
    
    用法:
        mapper = IntentMapper()
        spec = mapper.parse("暗色 SaaS 落地页，带 3D 粒子背景，AI 产品")
        # spec 可以直接传给 HarnessComposer.from_spec() 或 ProductionComposer.generate()
    """
    
    def __init__(self, enable_hep: bool = True):
        self.enable_hep = enable_hep and _HEP_AVAILABLE
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        自然语言 → 结构化 JSON Spec
        
        三步走:
          1. 代码匹配 — 识别页面类型、风格、特征、行业
          2. 工程JSON化 — 构建标准 Spec 结构
          3. 指令工程 — 填充内容模板，参数优化
        """
        # ── Step 1: 代码匹配 ──
        page_type = self._match_page_type(text)
        style_id = self._match_style(text)
        features = self._detect_features(text, style_id)
        industry = self._match_industry(text)
        brand = self._extract_brand(text)
        custom_title = self._extract_title(text)
        content_key = industry or page_type
        
        # ── Step 2: 工程JSON化 ──
        template = self._get_content(content_key)
        sections = self._build_sections(text, page_type, template, features)
        
        title = custom_title or template.get("hero_title_default", "").replace("\n", " ")
        subtitle = template.get("hero_subtitle_default", "")
        
        spec = {
            "title": title,
            "theme": style_id,
            "sections": sections,
            "animations": features.get("animations", True),
        }
        
        # 品牌名
        if brand:
            spec["brand"] = brand
        
        # 导航 (有品牌名时自动加)
        if brand or any(kw in text for kw in ["导航", "menu", "nav", "页头"]):
            spec["nav"] = {
                "brand": brand or "LAAP",
                "links": [
                    {"label": "首页", "url": "#"},
                    {"label": "产品", "url": "#"},
                    {"label": "定价", "url": "#"},
                    {"label": "关于", "url": "#"},
                ]
            }
        
        # Footer
        spec["footer"] = {"text": f"© 2026 {brand or 'LAAP'} · All rights reserved"}
        
        # 3D 参数 (注入到 hero section)
        if features.get("three_d"):
            for sec in spec["sections"]:
                if sec["type"] == "hero":
                    sec["three_d"] = True
        
        # ── Step 3: 指令工程 (HEP 集成) ──
        if self.enable_hep:
            self._enrich_with_hep(spec, text)
        
        return spec
    
    # ── 代码匹配方法 ──
    
    def _match_page_type(self, text: str) -> str:
        """页面类型匹配 — 关键词 → page_type_id"""
        text_lower = text.lower()
        scores = {}
        for pid, pdef in PAGE_TYPES.items():
            score = 0
            for alias in pdef["aliases"]:
                if alias.lower() in text_lower:
                    score += 1
                # 精确匹配加权
                if alias == text_lower.strip():
                    score += 3
            if score > 0:
                scores[pid] = score
        if scores:
            return max(scores, key=scores.get)
        return "landing"  # 默认
    
    def _match_style(self, text: str) -> str:
        """风格匹配 — 关键词 → 主题 ID"""
        text_lower = text.lower()
        scores = {}
        for keyword, style_id in STYLE_MAP.items():
            if keyword.lower() in text_lower:
                scores[style_id] = scores.get(style_id, 0) + 1
        if scores:
            return max(scores, key=scores.get)
        return "apple_dark"  # 默认
    
    def _match_industry(self, text: str) -> Optional[str]:
        """行业匹配 — 关键词 → 行业 ID (用于选择内容模板)"""
        text_lower = text.lower()
        for ind_id, ind_def in INDUSTRY_MAP.items():
            for kw in ind_def["keywords"]:
                if kw.lower() in text_lower:
                    return ind_id
        return None
    
    def _extract_brand(self, text: str) -> Optional[str]:
        """提取品牌/公司名"""
        m = BRAND_PATTERN.search(text)
        if m:
            name = m.group(1).strip()
            # 过滤掉常见停用词
            if name and len(name) >= 2:
                return name
        return None
    
    def _extract_title(self, text: str) -> Optional[str]:
        """提取自定义标题"""
        m = EXPLICIT_TITLE.search(text)
        if m:
            return m.group(1).strip()
        return None
    
    def _detect_features(self, text: str, style_id: str) -> Dict[str, Any]:
        """特征检测 — 关键词匹配 + 风格默认值"""
        text_lower = text.lower()
        features = {}
        
        for feat_id, feat_def in FEATURE_DETECT.items():
            # 关键词匹配 (显式声明)
            if any(kw.lower() in text_lower for kw in feat_def.get("keywords", [])):
                features[feat_id] = True
            # 默认值: 带 default_set 的检测风格是否在该集合中
            elif "default_set" in feat_def:
                features[feat_id] = style_id in feat_def["default_set"]
            # 普通默认值
            elif "default" in feat_def:
                features[feat_id] = feat_def["default"]
        
        return features
    
    # ── 工程JSON化方法 ──
    
    def _get_content(self, content_key: Optional[str]) -> Dict:
        """获取内容模板 — 有匹配用匹配，没有用默认"""
        if content_key and content_key in FEATURE_TEMPLATES:
            return FEATURE_TEMPLATES[content_key]
        return DEFAULT_CONTENT
    
    def _build_sections(self, text: str, page_type: str, template: Dict, features: Dict) -> List[Dict]:
        """构建 section 列表"""
        pdef = PAGE_TYPES.get(page_type, PAGE_TYPES["landing"])
        section_types = pdef["sections"]
        
        sections = []
        three_d = features.get("three_d", False)
        
        for stype in section_types:
            if stype == "hero":
                sections.append({
                    "type": "hero",
                    "title": template.get("hero_title_default", "开启新体验"),
                    "subtitle": template.get("hero_subtitle_default", ""),
                    "badge": template.get("hero_badge", "全新发布"),
                    "three_d": three_d,
                    "cta": template.get("cta_title", "了解更多"),
                    "cta_url": "#",
                })
            elif stype == "stats":
                stats_items = template.get("stats", DEFAULT_CONTENT["stats"])
                sections.append({
                    "type": "stats",
                    "items": stats_items,
                })
            elif stype == "features":
                feature_items = template.get("features", DEFAULT_CONTENT["features"])
                # 图标名称 → Lucide SVG
                cards_with_icons = []
                for item in feature_items:
                    card = dict(item)
                    if "icon" in card and not card.get("icon_svg"):
                        card["icon_svg"] = lucide_icon(card.pop("icon", ""), size=20)
                    elif "icon_svg" not in card:
                        card["icon_svg"] = ""
                    cards_with_icons.append(card)
                sections.append({
                    "type": "grid",
                    "label": "核心能力",
                    "title": "为什么选择我们",
                    "subtitle": "每一个功能都经过千锤百炼",
                    "cols": len(feature_items) if len(feature_items) <= 4 else 3,
                    "cards": cards_with_icons,
                })
            elif stype == "pricing":
                sections.append({
                    "type": "grid",
                    "label": "定价方案",
                    "title": "选择适合你的方案",
                    "subtitle": "灵活定价，按需选择",
                    "cols": 3,
                    "cards": [
                        {"title": "基础版", "desc": "适合个人和小团队起步使用", "icon_svg": ""},
                        {"title": "专业版", "desc": "适合成长中的企业团队", "icon_svg": ""},
                        {"title": "企业版", "desc": "适合大型组织的定制方案", "icon_svg": ""},
                    ],
                })
            elif stype == "testimonials":
                sections.append({
                    "type": "grid",
                    "label": "客户评价",
                    "title": "他们都在使用",
                    "subtitle": "来自全球客户的真实反馈",
                    "cols": 2,
                    "cards": [
                        {"title": "张伟 · CEO", "desc": "产品极大提升了我们的效率，团队协作变得前所未有的流畅"},
                        {"title": "李娜 · 产品总监", "desc": "从竞品迁移过来后，我们的迭代速度提升了 3 倍"},
                        {"title": "王磊 · CTO", "desc": "架构设计优雅，API 文档清晰，集成过程非常顺利"},
                        {"title": "陈婷 · 设计师", "desc": "用户体验打磨得非常细致，我们的客户都很喜欢"},
                    ],
                })
            elif stype == "cta":
                sections.append({
                    "type": "hero",
                    "title": template.get("cta_title", "开始使用"),
                    "subtitle": template.get("cta_subtitle", ""),
                    "badge": "",
                    "three_d": False,
                    "cta": template.get("cta_title", "立即开始"),
                    "cta_url": "#",
                    "height": "60vh",
                })
            elif stype == "grid":
                # 通用 grid 区 (用于 blog/portfolio 等)
                sections.append({
                    "type": "grid",
                    "label": "精选内容",
                    "title": "最新动态",
                    "subtitle": "",
                    "cols": 3,
                    "cards": [
                        {"title": "文章一", "desc": "精彩内容敬请期待"},
                        {"title": "文章二", "desc": "精彩内容敬请期待"},
                        {"title": "文章三", "desc": "精彩内容敬请期待"},
                    ],
                })
        
        return sections
    
    # ── HEP 集成 ──
    
    def _enrich_with_hep(self, spec: Dict, text: str):
        """从 HEP 注册表搜索匹配组件，注入额外 section"""
        if not self.enable_hep or HEP_REGISTRY is None:
            return
        
        # 搜索 ui 域组件
        ui_components = HEP_REGISTRY.search(domain="ui")
        for comp in ui_components:
            # 如果 spec 中有匹配的标签，添加提醒
            for tag in comp.tags:
                if tag.lower() in text.lower():
                    spec.setdefault("_hep_matches", []).append({
                        "id": comp.id,
                        "name": comp.name,
                        "matched_tag": tag,
                    })
        
        # 搜索 backend 域组件
        if any(kw in text.lower() for kw in ["后端", "api", "backend", "crud"]):
            backend_comps = HEP_REGISTRY.search(domain="backend")
            spec.setdefault("_hep_matches", []).extend({
                "id": c.id, "name": c.name, "matched_tag": "backend"
            } for c in backend_comps)
    
    # ── 工具方法 ──
    
    def parse_to_composer_spec(self, text: str) -> Dict[str, Any]:
        """返回兼容 HarnessComposer 的完整 Spec (含 nav/footer)"""
        return self.parse(text)
    
    def parse_to_production_spec(self, text: str) -> Dict[str, Any]:
        """返回兼容 ProductionComposer 的 Spec (不含 nav, 不含 footer 结构)"""
        spec = self.parse(text)
        # ProductionComposer 的 nav 是 raw html, 不是结构化的
        spec.pop("nav", None)
        return spec
    
    def describe_page_types(self) -> str:
        """列出所有支持的页面类型，用于调试"""
        lines = ["支持的页面类型:\n"]
        for pid, pdef in PAGE_TYPES.items():
            lines.append(f"  {pid:15s} → {pdef['label']:12s}  [{', '.join(pdef['sections'])}]")
            lines.append(f"  {'':15s}  关键词: {', '.join(pdef['aliases'][:3])}")
        return "\n".join(lines)
    
    def describe_styles(self) -> str:
        """列出所有支持的风格"""
        seen = set()
        lines = ["支持的风格:\n"]
        for keyword, style_id in sorted(STYLE_MAP.items(), key=lambda x: x[1]):
            if style_id not in seen:
                seen.add(style_id)
                lines.append(f"  {style_id:20s}  ({keyword})")
        return "\n".join(lines)


# ═══════════════════════════════════════════════
# 快速入口 — 自然语言 → 零 token 页面
# ═══════════════════════════════════════════════

def text_to_spec(text: str) -> Dict[str, Any]:
    """快速入口：自然语言 → JSON Spec"""
    return IntentMapper().parse(text)


def text_to_html(text: str, composer: str = "harness") -> str:
    """
    自然语言 → 生产级 HTML 页面
    
    composer="harness" → 使用 HarnessComposer (更丰富)
    composer="production" → 使用 ProductionComposer (更轻量)
    """
    mapper = IntentMapper()
    spec = mapper.parse(text)
    
    if composer == "production":
        from harness_style_engine import ProductionComposer
        c = ProductionComposer(spec.get("theme", "apple_dark"))
        return c.generate(spec)
    else:
        from harness_composer import HarnessComposer
        c = HarnessComposer(spec.get("theme", "apple_dark"))
        return c.from_spec(spec)


# ── 测试 / Demo ──
if __name__ == "__main__":
    print("=" * 60)
    print("  IntentMapper — 零 Token 意图匹配引擎")
    print("=" * 60)
    
    mapper = IntentMapper()
    
    test_cases = [
        "暗色 SaaS 落地页，带 3D 粒子背景，标题叫重塑云端生产力",
        "浅色科技公司首页，AI 产品，品牌叫灵镜科技",
        "玻璃拟态设计师作品集，带动效",
        "深色数据分析仪表盘，企业级",
        "暖色教育平台落地页，品牌叫知学",
        "极简白博客内容站，标题叫深度思考",
        "复古终端风格黑客主题落地页",
        "暗夜科技风格区块链创业公司首页，标题叫构建信任互联网",
        "深海风格蓝色调SaaS定价页",
        "日落暖色渐变活动会议推广页，标题叫连接思想共创未来",
    ]
    
    print(f"\n测试 {len(test_cases)} 个自然语言输入:\n")
    for i, text in enumerate(test_cases, 1):
        spec = mapper.parse(text)
        sections = spec.get("sections", [])
        sec_types = [s["type"] for s in sections]
        theme = spec.get("theme", "?")
        three_d = any(s.get("three_d") for s in sections)
        brand = spec.get("brand", "")
        title = spec.get("title", "")[:30]
        hep = spec.get("_hep_matches", [])
        
        print(f"  [{i}] {text[:40]:40s}")
        print(f"       类型={sec_types[0] if sec_types else '?'}  "
              f"主题={theme:18s}  3D={'✓' if three_d else '✗'}  "
              f"品牌={brand or '—':10s}")
        print(f"       标题={title}...  "
              f"Sections: {', '.join(sec_types)}")
        print(f"       HEP匹配: {len(hep)} 个组件")
        print()
    
    # 生成一个实际页面
    print("=" * 60)
    print("  生成示例页面...")
    print("=" * 60)
    
    spec = mapper.parse("暗色 SaaS 落地页带 3D 粒子，品牌叫灵镜科技，标题叫重塑云端生产力")
    
    try:
        from harness_composer import HarnessComposer
        c = HarnessComposer(spec.get("theme", "apple_dark"))
        html = c.from_spec(spec)
        out_path = "D:/LAAP/aris_brain/intent_mapper_demo.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  页面生成: {out_path}")
        print(f"  大小: {len(html):,} bytes")
        print(f"  SVG 图标: {html.count('<svg')}")
        print(f"  Three.js: {'three.module.js' in html}")
        print(f"  零 Token: ✓")
    except ImportError as e:
        print(f"  HarnessComposer 未找到 ({e}), 跳过页面生成")
    except Exception as e:
        print(f"  页面生成失败: {e}")
    
    print("\n✅ IntentMapper 就绪 — 全程零 Token")
