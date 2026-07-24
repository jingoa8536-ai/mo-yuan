"""
项目名称: aris_brain — project_planner.py
模块描述: 项目经理级全生命周期规划引擎
核心设计: 我不是一个简单的"规划器"，而是一个真正的项目经理。
          拿到项目后先调研行业最佳实践，然后询问用户需求细节，
          给出最优方案建议，最后全生命周期跟踪执行。

集成方式:
  - 可在认知循环中注入 project_planner.get_next_action() 作为认知上下文
  - 与 task_supervisor 联动: planning阶段完成后自动创建task
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple


# =============================================================================
# 枚举定义
# =============================================================================

class Phase(str, Enum):
    INITIAL = "initial"               # 刚接到项目
    RESEARCH = "research"             # 调研行业方案
    REQUIREMENTS = "requirements"     # 收集需求
    SOLUTION = "solution"             # 方案设计
    PLANNING = "planning"             # 制定计划
    EXECUTION = "execution"           # 执行中
    REVIEW = "review"                 # 验收
    COMPLETED = "completed"           # 完成

    def __lt__(self, other: "Phase") -> bool:
        order = list(Phase)
        return order.index(self) < order.index(other)

    def __le__(self, other: "Phase") -> bool:
        return self == other or self < other

    def next(self) -> Optional["Phase"]:
        order = list(Phase)
        idx = order.index(self)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class Requirement:
    id: str
    category: str                # 如 "功能", "性能", "安全", "UI/UX"
    description: str
    priority: int                # 1(最高) ~ 5(最低)
    status: str = "pending"      # confirmed / pending / declined

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Requirement":
        return cls(**d)


@dataclass
class Milestone:
    order: int
    name: str
    description: str
    deadline_estimate: str       # 如 "2026-07-15" 或 "Week 2"
    status: str = "pending"      # pending / in_progress / completed / blocked

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Milestone":
        return cls(**d)


@dataclass
class Risk:
    description: str
    probability: int = 3         # 1~5
    impact: int = 3              # 1~5
    mitigation: str = ""
    status: str = "identified"   # identified / mitigated / accepted / realized

    @property
    def score(self) -> int:
        return self.probability * self.impact

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Risk":
        return cls(**d)


@dataclass
class Project:
    id: str
    name: str
    description: str
    phase: Phase = Phase.INITIAL
    industry: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    requirements: List[Requirement] = field(default_factory=list)
    questions_asked: List[str] = field(default_factory=list)
    questions_pending: List[str] = field(default_factory=list)
    research_notes: str = ""
    best_practices: List[str] = field(default_factory=list)
    proposed_solution: str = ""
    milestones: List[Milestone] = field(default_factory=list)
    risks: List[Risk] = field(default_factory=list)
    quality_checklist: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["phase"] = self.phase.value
        d["requirements"] = [r.to_dict() for r in self.requirements]
        d["milestones"] = [m.to_dict() for m in self.milestones]
        d["risks"] = [r.to_dict() for r in self.risks]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        d["phase"] = Phase(d["phase"])
        d["requirements"] = [Requirement.from_dict(r) for r in d.get("requirements", [])]
        d["milestones"] = [Milestone.from_dict(m) for m in d.get("milestones", [])]
        d["risks"] = [Risk.from_dict(r) for r in d.get("risks", [])]
        return cls(**d)


# =============================================================================
# 持久化层
# =============================================================================

STORAGE_DIR = Path(os.environ.get(
    "PROJECT_PLANNER_DIR",
    str(Path.home() / ".hermes" / "project_planner")
))


def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _project_path(project_id: str) -> Path:
    return STORAGE_DIR / f"{project_id}.json"


def save_project(project: Project) -> None:
    """持久化保存项目到 JSON 文件"""
    _ensure_storage()
    project.updated_at = datetime.now().isoformat()
    path = _project_path(project.id)
    path.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(project_id: str) -> Optional[Project]:
    """从 JSON 文件加载项目"""
    path = _project_path(project_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Project.from_dict(data)


def list_projects() -> List[Project]:
    """列出所有已保存的项目"""
    _ensure_storage()
    projects = []
    for f in sorted(STORAGE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            projects.append(Project.from_dict(data))
        except Exception:
            continue
    return projects


def delete_project(project_id: str) -> bool:
    """删除一个项目"""
    path = _project_path(project_id)
    if path.exists():
        path.unlink()
        return True
    return False


# =============================================================================
# 行业调研引擎（web_search 适配器）
# =============================================================================

# 预留的 web_search 接口 — 实际使用时需注入真实搜索函数
_web_search_func = None


def set_web_search(func):
    """注入 web_search 函数。函数签名: func(query: str) -> str"""
    global _web_search_func
    _web_search_func = func


def _try_web_search(query: str) -> str:
    """尝试使用 web_search，如果未注入则返回空字符串"""
    if _web_search_func is not None:
        try:
            return _web_search_func(query)
        except Exception as e:
            return f"[搜索失败: {e}]"
    return ""


# =============================================================================
# 预设问题模板
# =============================================================================

# 每个阶段对应的问题表 — 用于 generate_pending_questions
QUESTION_TEMPLATES = {
    Phase.INITIAL: [
        "项目的核心目标是什么？请用一句话描述。",
        "项目的主要用户或受众是谁？",
        "你有没有参考的竞品、网站或类似项目？",
        "这个项目的期望交付时间是什么时候？",
        "有没有预算范围或者资源限制？",
    ],
    Phase.RESEARCH: [
        "调研中我们发现了一些行业最佳实践，你更偏好哪种技术路线或方案？",
        "项目的核心功能和辅助功能分别是哪些？",
        "你对技术栈有什么偏好或限制吗？",
    ],
    Phase.REQUIREMENTS: [
        "请列出你最看重的3~5个核心功能。",
        "是否需要考虑国际化/多语言？",
        "是否需要移动端适配？",
        "有没有安全合规方面的特殊要求？",
    ],
    Phase.SOLUTION: [
        "对于推荐的方案，你觉得有哪些需要调整的地方？",
        "有没有额外的集成需求（如第三方API、支付、登录等）？",
        "数据量预估有多大？是否需要考虑高并发？",
    ],
    Phase.PLANNING: [
        "你觉得里程碑的时间安排是否合理？",
        "团队中有哪些角色和人员可用？",
        "是否需要外部供应商或外包团队？",
    ],
    Phase.EXECUTION: [
        "当前执行进度如何？有没有遇到阻碍？",
        "需要调整优先级或重新排期吗？",
    ],
    Phase.REVIEW: [
        "验收标准是否清晰？需要补充吗？",
        "有没有需要记录的经验教训？",
    ],
    Phase.COMPLETED: [],
}


# =============================================================================
# 行业调研关键词生成
# =============================================================================

def _generate_research_queries(project: Project) -> List[str]:
    """根据项目信息生成搜索查询词"""
    name = project.name
    industry = project.industry or name
    queries = [
        f"{industry} best practices 2026",
        f"{name} industry trends",
    ]
    if industry:
        queries.append(f"{industry} technology stack recommendation")
        queries.append(f"{industry} common pitfalls")
    queries.append(f"{name} project planning guide")
    return queries


# =============================================================================
# 核心规划引擎
# =============================================================================

class ProjectPlanner:
    """项目经理级全生命周期规划引擎"""

    def __init__(self, storage_dir: Optional[str] = None):
        global STORAGE_DIR
        if storage_dir:
            STORAGE_DIR = Path(storage_dir)
        _ensure_storage()

    # ---------------------------------------------------------------
    # 项目创建
    # ---------------------------------------------------------------

    def new_project(self, name: str, description: str, industry: str = "") -> Project:
        """创建新项目，自动进入 INITIAL 阶段并生成待问问题"""
        project = Project(
            id=uuid.uuid4().hex[:12],
            name=name,
            description=description,
            industry=industry or self._infer_industry(name, description),
            phase=Phase.INITIAL,
        )
        self._init_pending_questions(project)
        save_project(project)
        return project

    def _infer_industry(self, name: str, description: str) -> str:
        """根据项目名称和描述推测行业（简单启发式）"""
        text = (name + " " + description).lower()

        # 常见行业关键词映射
        industry_map = [
            (["网站", "官网", "web", "landing", "landing page"], "互联网/企业官网"),
            (["电商", "商城", "shop", "store", "ecommerce", "购物"], "互联网/电商"),
            (["saas", "订阅", "平台即服务", "云服务"], "互联网/SaaS"),
            (["app", "移动", "ios", "android", "手机", "小程序"], "移动互联网"),
            (["游戏", "game", "gaming", "休闲"], "游戏/娱乐"),
            (["金融", "银行", "支付", "fintech", "理财"], "金融科技"),
            (["教育", "学习", "课程", "培训", "edu", "在线教育"], "教育/在线教育"),
            (["医疗", "健康", "医院", "health", "医药"], "医疗健康"),
            (["AI", "人工智能", "machine learning", "llm", "大模型", "智能"], "人工智能"),
            (["企业", "erp", "crm", "管理", "内部系统", "oa"], "企业服务"),
            (["社交", "社区", "social", "论坛", "bbs", "聊天"], "社交/社区"),
            (["内容", "媒体", "news", "newsletter", "blog", "博客"], "内容/媒体"),
        ]
        for keywords, ind in industry_map:
            if any(kw in text for kw in keywords):
                return ind
        return "通用"

    # ---------------------------------------------------------------
    # 问题管理
    # ---------------------------------------------------------------

    def _init_pending_questions(self, project: Project):
        """根据当前阶段初始化待问问题"""
        templates = QUESTION_TEMPLATES.get(project.phase, [])
        already_asked = set(project.questions_asked)
        project.questions_pending = [q for q in templates if q not in already_asked]
        save_project(project)

    def ask_questions(self, project_id: str) -> List[str]:
        """返回当前需要问用户的问题列表"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        self._init_pending_questions(project)
        return project.questions_pending

    def record_answer(self, project_id: str, question: str, answer: str) -> Project:
        """记录用户的回答，自动推进项目阶段"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        # 将问题从未问列表移到已问列表
        if question in project.questions_pending:
            project.questions_pending.remove(question)
        if question not in project.questions_asked:
            project.questions_asked.append(question)

        # 将回答以需求形式记录
        cat = self._classify_answer(question, answer)
        if cat and answer.strip():
            req = Requirement(
                id=uuid.uuid4().hex[:8],
                category=cat,
                description=f"[问答] {question}\n回答: {answer}",
                priority=2 if cat == "功能" else 3,
            )
            project.requirements.append(req)

        save_project(project)
        self._try_advance_phase(project.id)

        # 重新加载以获取最新状态
        project = load_project(project_id)
        return project

    def _classify_answer(self, question: str, answer: str) -> str:
        """根据问题内容自动分类回答"""
        q = question.lower()
        if any(k in q for k in ["功能", "核心", "做什么", "目标"]):
            return "功能"
        if any(k in q for k in ["用户", "受众", "谁"]):
            return "用户"
        if any(k in q for k in ["预算", "时间", "资源", "工期"]):
            return "约束"
        if any(k in q for k in ["技术", "方案", "偏好", "栈"]):
            return "技术"
        if any(k in q for k in ["安全", "合规", "数据"]):
            return "安全"
        if any(k in q for k in ["集成", "api", "第三方"]):
            return "集成"
        if any(k in q for k in ["移动", "适配", "国际化", "多语言"]):
            return "非功能"
        if any(k in q for k in ["参考", "竞品", "类似"]):
            return "调研"
        return "其他"

    # ---------------------------------------------------------------
    # 行业调研
    # ---------------------------------------------------------------

    def research_industry(self, project_id: str) -> str:
        """自动搜索行业最佳实践，存入 research_notes"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        if project.phase < Phase.RESEARCH:
            project.phase = Phase.RESEARCH
            self._init_pending_questions(project)

        queries = _generate_research_queries(project)
        notes = []
        practices = []

        for query in queries:
            result = _try_web_search(query)
            if result:
                notes.append(f"## 搜索: {query}\n{result}\n")
                # 简单提取可能有用的条目
                for line in result.split("\n"):
                    line = line.strip()
                    if len(line) > 20 and not line.startswith("#"):
                        practices.append(line)

        if not notes:
            # 搜索不可用时，使用内置知识
            builtin = self._builtin_research(project)
            notes.append(builtin["notes"])
            practices.extend(builtin["practices"])

        project.research_notes = "\n".join(notes)
        # 去重并截取前20条最佳实践
        seen = set()
        unique_practices = []
        for p in practices:
            if p not in seen:
                seen.add(p)
                unique_practices.append(p)
        project.best_practices = unique_practices[:20]

        # 自动识别风险
        self._identify_risks(project)

        save_project(project)
        return project.research_notes

    def _builtin_research(self, project: Project) -> dict:
        """内置行业知识库（当 web_search 不可用时的后备方案）"""
        name = project.name.lower()
        industry = project.industry.lower()

        notes = f"## 内置调研 — {project.industry or project.name}\n\n"
        practices = []

        if "网站" in name or "官网" in name or "web" in name or "互联网" in industry:
            notes += (
                "### 企业网站最佳实践 (2026)\n"
                "- 使用 Jamstack 架构 (Next.js/Gatsby + Headless CMS) 获得最佳性能\n"
                "- 确保 Core Web Vitals 达标: LCP < 2.5s, FID < 100ms, CLS < 0.1\n"
                "- 响应式设计 + 移动优先策略\n"
                "- SEO 优化: 语义化 HTML, structured data, sitemap\n"
                "- 无障碍访问 (WCAG 2.1 AA 标准)\n"
                "- 考虑使用 SSR/SSG 提升首屏加载速度\n"
                "- CDN + 图片优化 (WebP, lazy loading)\n"
                "- 安全性: HTTPS, CSP headers, XSS 防护\n"
            )
            practices = [
                "使用 Jamstack 架构提升性能和安全性",
                "确保 Core Web Vitals 达标",
                "移动优先的响应式设计",
                "SEO 最佳实践: 语义化HTML + Structured Data",
                "无障碍访问 WCAG 2.1 AA",
                "SSR/SSG 优化首屏加载",
                "CDN + 图片自动优化",
                "安全防护: HTTPS, CSP, XSS",
            ]
        elif "电商" in industry or "shop" in name or "store" in name:
            notes += (
                "### 电商最佳实践 (2026)\n"
                "- 选择成熟平台 Shopify / WooCommerce / 自建 (根据规模)\n"
                "- 支付集成: 至少支持主流支付方式\n"
                "- 购物车体验优化: 免注册结账, 进度指示器\n"
                "- 商品搜索: Elasticsearch / Meilisearch\n"
                "- 订单管理系统 (OMS) 集成\n"
                "- 库存管理实时同步\n"
                "- 营销工具: 优惠券, 积分, 推荐系统\n"
                "- 移动端转化率优化\n"
                "- 加载速度直接影响转化率: 每慢1秒降低7%转化\n"
            )
            practices = [
                "选择合适的电商平台或框架",
                "多渠道支付集成",
                "免注册结账流程",
                "高性能商品搜索",
                "实时的库存管理",
                "营销自动化工具",
                "移动端转化率优化",
                "页面加载速度优化",
            ]
        elif "saas" in industry or "SaaS" in industry:
            notes += (
                "### SaaS 最佳实践 (2026)\n"
                "- 多租户架构设计\n"
                "- 订阅计费系统 (Stripe / Paddle / Chargebee)\n"
                "- 用户认证: Auth0 / Clerk / 自建\n"
                "- 使用微服务或模块化单体架构\n"
                "- API First 设计原则\n"
                "- 完善的文档和开发者体验\n"
                "- CI/CD 自动化部署\n"
                "- 监控和告警 (Datadog / Sentry)\n"
                "- 数据备份和灾难恢复\n"
            )
            practices = [
                "多租户架构设计",
                "订阅计费与定价模型",
                "安全的用户认证系统",
                "API First 设计",
                "完善的开发者文档",
                "CI/CD 自动化流水线",
                "监控与告警体系",
                "数据备份与灾难恢复",
            ]
        else:
            notes += (
                f"### {project.industry or project.name} 通用建议\n"
                "- 优先明确核心需求和 MVP 范围\n"
                "- 选择成熟稳定的技术栈\n"
                "- 注重可维护性和可扩展性\n"
                "- 尽早建立测试体系\n"
                "- 文档和知识管理\n"
                "- 持续集成和部署\n"
            )
            practices = [
                "明确 MVP 范围",
                "选择成熟技术栈",
                "注重可维护性和可扩展性",
                "建立自动化测试体系",
                "完善的文档和知识管理",
                "CI/CD 自动化",
            ]

        return {"notes": notes, "practices": practices}

    def _identify_risks(self, project: Project):
        """根据项目信息自动识别风险"""
        risks = []

        # 没有明确的痛点的通用风险
        risks.append(Risk(
            description="需求不明确或频繁变更",
            probability=4,
            impact=4,
            mitigation="尽早确认需求文档，建立变更控制流程",
        ))
        risks.append(Risk(
            description="工期估计不足",
            probability=3,
            impact=3,
            mitigation="预留20%缓冲时间，分解任务到天级别",
        ))

        name_lower = project.name.lower()
        if "网站" in name_lower:
            risks.append(Risk(
                description="浏览器兼容性问题",
                probability=3,
                impact=2,
                mitigation="使用 Autoprefixer 和 Polyfill，多浏览器测试",
            ))
            risks.append(Risk(
                description="SEO 效果不达预期",
                probability=3,
                impact=3,
                mitigation="前期做好关键词调研和 SEO 架构设计",
            ))
        elif "电商" in name_lower or "shop" in name_lower:
            risks.append(Risk(
                description="支付流程安全风险",
                probability=2,
                impact=5,
                mitigation="使用 PCI DSS 合规的支付服务商",
            ))
            risks.append(Risk(
                description="高并发下系统崩溃",
                probability=3,
                impact=5,
                mitigation="提前做压力测试，配置自动扩容",
            ))

        # 合并已有风险（去重）
        existing = {r.description for r in project.risks}
        for r in risks:
            if r.description not in existing:
                project.risks.append(r)

    # ---------------------------------------------------------------
    # 方案设计
    # ---------------------------------------------------------------

    def propose_solution(self, project_id: str) -> str:
        """基于 research_notes + requirements 生成最优方案建议"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        if project.phase < Phase.SOLUTION:
            project.phase = Phase.SOLUTION
            self._init_pending_questions(project)

        solution_parts = []

        # 1. 项目概述
        solution_parts.append(f"# 方案建议: {project.name}")
        solution_parts.append(f"> {project.description}")
        solution_parts.append(f"**行业**: {project.industry}  |  **阶段**: {project.phase.value}\n")

        # 2. 需求摘要
        if project.requirements:
            solution_parts.append("## 已收集的需求")
            for req in project.requirements:
                status_icon = "✅" if req.status == "confirmed" else "⏳" if req.status == "pending" else "❌"
                solution_parts.append(f"- {status_icon} **[P{req.priority}] {req.category}**: {req.description}")
            solution_parts.append("")

        # 3. 推荐方案
        solution_parts.append("## 推荐方案")
        solution_parts.append(self._generate_solution(project))
        solution_parts.append("")

        # 4. 技术栈建议
        solution_parts.append("## 技术栈建议")
        for line in self._recommend_tech_stack(project):
            solution_parts.append(f"- {line}")
        solution_parts.append("")

        # 5. 最佳实践
        if project.best_practices:
            solution_parts.append("## 参考的最佳实践")
            for i, bp in enumerate(project.best_practices[:8], 1):
                solution_parts.append(f"{i}. {bp}")
            solution_parts.append("")

        # 6. 风险提示
        if project.risks:
            solution_parts.append("## 风险提示")
            for risk in sorted(project.risks, key=lambda r: r.score, reverse=True)[:5]:
                solution_parts.append(
                    f"- ⚠️ **{risk.description}** (概率:{risk.probability}/5, 影响:{risk.impact}/5, 评分:{risk.score})"
                )
                if risk.mitigation:
                    solution_parts.append(f"  → 缓解: {risk.mitigation}")
            solution_parts.append("")

        project.proposed_solution = "\n".join(solution_parts)
        save_project(project)
        return project.proposed_solution

    def _generate_solution(self, project: Project) -> str:
        """根据需求和行业生成方案描述"""
        name = project.name.lower()
        industry = project.industry.lower()

        if "网站" in name or "官网" in name or "互联网" in industry:
            return (
                "### 企业官网建设方案\n\n"
                "**架构**: Next.js (SSG/SSR) + Headless CMS (Contentful / Strapi / Sanity)\n"
                "**部署**: Vercel / Netlify + CDN\n"
                "**样式**: Tailwind CSS + 组件库 (shadcn/ui)\n"
                "**功能模块**:\n"
                "1. 首页: 品牌展示, 核心价值, CTA\n"
                "2. 关于我们: 团队介绍, 发展历程\n"
                "3. 产品/服务: 分类展示, 详情页\n"
                "4. 博客/资讯: CMS 驱动的动态内容\n"
                "5. 联系我们: 表单 + 地图\n"
                "6. 后台管理: 内容编辑, 数据统计\n\n"
                "**质量目标**: Lighthouse 评分 > 90, 首屏 < 1.5s"
            )
        elif "电商" in industry or "shop" in name:
            return (
                "### 电商平台建设方案\n\n"
                "**架构选项**:\n"
                "- 小型: Shopify / WooCommerce (快速上线)\n"
                "- 中型: Next.js + Medusa.js (开源可定制)\n"
                "- 大型: 微服务架构 (Go/Java + React)\n\n"
                "**核心功能**:\n"
                "1. 商品管理: 分类, SKU, 库存\n"
                "2. 购物车 & 结账: 免注册结账\n"
                "3. 支付: Stripe / PayPal / 支付宝/微信\n"
                "4. 订单管理: 状态追踪, 退款\n"
                "5. 用户系统: 注册, 收藏, 历史\n"
                "6. 搜索: Elasticsearch 全文检索\n"
                "7. 营销: 优惠券, 促销, 推荐"
            )
        elif "saas" in industry:
            return (
                "### SaaS 平台建设方案\n\n"
                "**架构**: Next.js (前端) + Node.js / Go (后端) + PostgreSQL + Redis\n"
                "**多租户**: 数据库行级隔离或 Schema 隔离\n"
                "**认证**: Auth0 / Clerk\n"
                "**支付**: Stripe 订阅管理\n"
                "**部署**: Docker + Kubernetes\n\n"
                "**核心功能**:\n"
                "1. 用户注册/登录 + SSO\n"
                "2. 订阅管理 (免费版/专业版/企业版)\n"
                "3. 核心业务逻辑 (根据具体需求)\n"
                "4. API 网关 + Rate Limiting\n"
                "5. 后台管理面板\n"
                "6. 数据分析与报表"
            )
        else:
            return (
                f"### {project.name} 通用方案\n\n"
                "**推荐架构**: 模块化单体 (适用于大多数中小型项目)\n"
                "**前端**: React / Vue + TypeScript\n"
                "**后端**: Python (FastAPI) / Node.js (Express/Nest)\n"
                "**数据库**: PostgreSQL + Redis (缓存)\n"
                "**部署**: Docker + 云服务器 (AWS / 阿里云 / 腾讯云)\n\n"
                "建议先交付 MVP（最小可行产品），迭代式开发。"
            )

    def _recommend_tech_stack(self, project: Project) -> List[str]:
        """推荐技术栈"""
        name = project.name.lower()
        industry = project.industry.lower()

        if "网站" in name or "官网" in name:
            return [
                "**前端**: Next.js 14, TypeScript, Tailwind CSS",
                "**CMS**: Strapi / Contentful / Sanity",
                "**托管**: Vercel / Netlify (全球CDN)",
                "**分析**: Google Analytics 4 / Plausible",
                "**监控**: Sentry (错误追踪)",
                "**SEO**: next-seo, structured data (JSON-LD)",
            ]
        elif "电商" in industry or "shop" in name:
            return [
                "**前端**: Next.js / Remix (SSR 优化 SEO)",
                "**后端**: Medusa.js / Node.js / Python",
                "**数据库**: PostgreSQL + Redis",
                "**搜索**: Elasticsearch / Meilisearch",
                "**支付**: Stripe + 支付宝/微信支付",
                "**CDN**: Cloudflare / AWS CloudFront",
                "**监控**: Sentry + Datadog",
            ]
        elif "saas" in industry:
            return [
                "**前端**: Next.js 14, TypeScript, Tailwind CSS",
                "**后端**: Node.js (NestJS) / Go / Python (FastAPI)",
                "**数据库**: PostgreSQL + Redis + Elasticsearch",
                "**认证**: Auth0 / Clerk / Firebase Auth",
                "**支付**: Stripe (订阅管理)",
                "**部署**: Docker + Kubernetes (AWS EKS / GKE)",
                "**CI/CD**: GitHub Actions / GitLab CI",
                "**监控**: Datadog / Grafana + Prometheus",
            ]
        else:
            return [
                "**前端**: React / Vue 3 + TypeScript",
                "**后端**: Python (FastAPI/Django) / Node.js",
                "**数据库**: PostgreSQL",
                "**缓存**: Redis",
                "**部署**: Docker + 云服务器",
                "**CI/CD**: GitHub Actions",
            ]

    # ---------------------------------------------------------------
    # 里程碑
    # ---------------------------------------------------------------

    def create_milestones(self, project_id: str) -> List[Milestone]:
        """自动生成里程碑：按阶段分解"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        if project.phase < Phase.PLANNING:
            project.phase = Phase.PLANNING
            self._init_pending_questions(project)

        milestones = self._generate_milestones(project)
        project.milestones = milestones

        # 生成质量检查清单
        project.quality_checklist = self._generate_quality_checklist(project)

        save_project(project)
        return milestones

    def _generate_milestones(self, project: Project) -> List[Milestone]:
        """根据项目和行业生成里程碑"""
        name = project.name.lower()
        industry = project.industry.lower()
        milestones = []

        if "网站" in name or "官网" in name:
            milestones = [
                Milestone(1, "需求确认与设计", "完成需求文档、UI/UX 设计稿", "Week 1-2"),
                Milestone(2, "前端框架搭建", "Next.js 项目初始化，基础布局和路由", "Week 2-3"),
                Milestone(3, "CMS 集成与内容录入", "接入 Headless CMS，创建内容模型", "Week 3-4"),
                Milestone(4, "核心页面开发", "首页、关于、产品、博客、联系页面", "Week 4-6"),
                Milestone(5, "响应式与性能优化", "移动端适配，Lighthouse 优化", "Week 6-7"),
                Milestone(6, "SEO 与无障碍", "结构化数据，WCAG 合规检查", "Week 7-8"),
                Milestone(7, "测试与修复", "全功能测试，跨浏览器测试", "Week 8-9"),
                Milestone(8, "上线部署", "域名配置，CDN，SSL 证书，监控设置", "Week 9-10"),
            ]
        elif "电商" in industry or "shop" in name:
            milestones = [
                Milestone(1, "需求与设计", "需求文档、UX 设计、数据库设计", "Week 1-3"),
                Milestone(2, "基础架构搭建", "项目初始化，认证系统，商品模块", "Week 3-5"),
                Milestone(3, "购物车与结账", "购物车逻辑，支付集成", "Week 5-7"),
                Milestone(4, "订单与库存管理", "订单流程，库存同步", "Week 7-9"),
                Milestone(5, "搜索与营销", "搜索功能，优惠券，推荐", "Week 9-11"),
                Milestone(6, "测试与安全审计", "压力测试，PCI 合规检查", "Week 11-12"),
                Milestone(7, "上线与监控", "部署上线，监控配置", "Week 12-13"),
            ]
        elif "saas" in industry:
            milestones = [
                Milestone(1, "架构设计与原型", "系统架构，数据库设计，原型验证", "Week 1-2"),
                Milestone(2, "核心用户系统", "注册、登录、认证、权限", "Week 2-4"),
                Milestone(3, "订阅与支付", "定价页面，Stripe 订阅集成", "Week 4-6"),
                Milestone(4, "核心业务功能", "主业务逻辑实现", "Week 6-10"),
                Milestone(5, "API 与集成", "REST API，Webhook，第三方集成", "Week 10-12"),
                Milestone(6, "后台与报表", "管理面板，数据分析", "Week 12-14"),
                Milestone(7, "测试与安全", "安全审计，渗透测试", "Week 14-15"),
                Milestone(8, "Beta 发布", "邀请内测，反馈收集", "Week 15-16"),
            ]
        else:
            milestones = [
                Milestone(1, "需求确认", "需求文档评审确认", "Week 1"),
                Milestone(2, "系统设计", "架构设计，技术选型", "Week 2"),
                Milestone(3, "核心功能开发", "MVP 核心功能实现", "Week 3-6"),
                Milestone(4, "测试与修复", "功能测试，Bug 修复", "Week 7-8"),
                Milestone(5, "部署上线", "部署，文档，发布", "Week 9-10"),
            ]

        return milestones

    def _generate_quality_checklist(self, project: Project) -> List[str]:
        """生成质量检查清单"""
        name = project.name.lower()

        base_checks = [
            "代码评审 (Code Review) 完成",
            "单元测试覆盖率 > 80%",
            "集成测试通过",
            "性能测试达标",
            "安全检查: 无已知漏洞依赖",
            "文档完整 (README, API 文档, 部署文档)",
        ]

        if "网站" in name or "官网" in name:
            return base_checks + [
                "Lighthouse 评分 > 90 (Performance, Accessibility, SEO)",
                "Core Web Vitals 达标",
                "响应式设计在主流设备上正常显示",
                "SEO 结构化数据验证通过",
                "无障碍 (WCAG 2.1 AA) 检查通过",
                "所有表单验证和错误提示正常",
                "跨浏览器测试: Chrome, Firefox, Safari, Edge",
                "CDN 配置正确, SSL 证书有效",
            ]
        elif "电商" in name or "shop" in name:
            return base_checks + [
                "支付流程端到端测试通过",
                "购物车逻辑: 增删改查, 数量变更, 优惠码",
                "订单状态流转正常",
                "库存同步实时准确",
                "搜索功能返回正确结果",
                "压力测试: 支持预期并发量",
                "退款流程测试通过",
                "PCI DSS 合规检查",
            ]
        else:
            return base_checks + [
                "核心业务流程端到端测试通过",
                "错误处理和边界情况覆盖",
                "数据备份机制验证",
                "日志和监控配置完成",
            ]

    # ---------------------------------------------------------------
    # 阶段推进
    # ---------------------------------------------------------------

    def advance_phase(self, project_id: str) -> Phase:
        """当当前阶段的条件满足时，自动推进到下一阶段"""
        return self._try_advance_phase(project_id, force=True)

    def _try_advance_phase(self, project_id: str, force: bool = False) -> Phase:
        """尝试推进阶段（内部方法）"""
        project = load_project(project_id)
        if not project:
            raise ValueError(f"项目 '{project_id}' 不存在")

        next_phase = project.phase.next()
        if not next_phase:
            return project.phase

        can_advance = False

        if project.phase == Phase.INITIAL:
            # 至少问过一个问题
            can_advance = len(project.questions_asked) >= 1 or force

        elif project.phase == Phase.RESEARCH:
            # 已有调研笔记
            can_advance = bool(project.research_notes.strip()) or force

        elif project.phase == Phase.REQUIREMENTS:
            # 至少有一个需求被确认
            confirmed = [r for r in project.requirements if r.status == "confirmed"]
            can_advance = len(confirmed) >= 1 or force

        elif project.phase == Phase.SOLUTION:
            # 已有方案建议
            can_advance = bool(project.proposed_solution.strip()) or force

        elif project.phase == Phase.PLANNING:
            # 已有里程碑
            can_advance = len(project.milestones) > 0 or force

        elif project.phase == Phase.EXECUTION:
            # 所有里程碑完成或过半完成
            completed = [m for m in project.milestones if m.status == "completed"]
            can_advance = len(completed) >= len(project.milestones) * 0.5 or force

        elif project.phase == Phase.REVIEW:
            can_advance = force

        if can_advance:
            project.phase = next_phase
            self._init_pending_questions(project)
            save_project(project)

            # 特殊处理: PLANNING 完成后自动触发里程碑创建
            if project.phase == Phase.EXECUTION and not project.milestones:
                self.create_milestones(project_id)

        return project.phase

    # ---------------------------------------------------------------
    # 状态报告
    # ---------------------------------------------------------------

    def get_status(self, project_id: str) -> dict:
        """返回完整的项目状态报告（包含自然语言摘要）"""
        project = load_project(project_id)
        if not project:
            return {"error": f"项目 '{project_id}' 不存在"}

        phase_descriptions = {
            Phase.INITIAL: "📋 项目刚刚创建，正在了解基本需求",
            Phase.RESEARCH: "🔍 正在进行行业调研和最佳实践分析",
            Phase.REQUIREMENTS: "📝 正在收集和确认详细需求",
            Phase.SOLUTION: "🎨 正在基于调研和需求设计最优方案",
            Phase.PLANNING: "📅 正在制定项目计划和里程碑",
            Phase.EXECUTION: "🏗️ 项目正在执行中",
            Phase.REVIEW: "✅ 项目处于验收阶段",
            Phase.COMPLETED: "🎉 项目已完成!",
        }

        confirmed_reqs = [r for r in project.requirements if r.status == "confirmed"]
        pending_reqs = [r for r in project.requirements if r.status == "pending"]
        completed_mils = [m for m in project.milestones if m.status == "completed"]
        total_mils = len(project.milestones)

        # 自然语言摘要
        summary_parts = [
            f"## 📊 项目状态: {project.name}",
            f"**阶段**: {phase_descriptions.get(project.phase, project.phase.value)}",
            f"**行业**: {project.industry}",
            f"**创建时间**: {project.created_at}",
            f"**最后更新**: {project.updated_at}",
            "",
        ]

        # 需求统计
        summary_parts.append(f"**需求**: 已确认 {len(confirmed_reqs)} 个, 待确认 {len(pending_reqs)} 个, 共 {len(project.requirements)} 个")

        # 里程碑进度
        if total_mils > 0:
            progress = len(completed_mils) / total_mils * 100
            bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
            summary_parts.append(f"**里程碑进度**: {bar} {progress:.0f}% ({len(completed_mils)}/{total_mils})")
        else:
            summary_parts.append("**里程碑**: 尚未创建")

        # 风险
        high_risks = [r for r in project.risks if r.score >= 12]
        if high_risks:
            summary_parts.append(f"**高风险项**: {len(high_risks)} 个需关注")
        summary_parts.append(f"**质量检查项**: {len(project.quality_checklist)} 项")

        summary_parts.append("")
        summary_parts.append(f"**下一个建议动作**: {self.get_next_action(project_id)}")

        return {
            "project": project,
            "phase": project.phase,
            "phase_description": phase_descriptions.get(project.phase, ""),
            "requirements_summary": {
                "total": len(project.requirements),
                "confirmed": len(confirmed_reqs),
                "pending": len(pending_reqs),
            },
            "milestones_progress": {
                "total": total_mils,
                "completed": len(completed_mils),
                "percentage": (len(completed_mils) / total_mils * 100) if total_mils > 0 else 0,
            },
            "risks_summary": {
                "total": len(project.risks),
                "high_risk": len(high_risks),
            },
            "summary_text": "\n".join(summary_parts),
        }

    def get_next_action(self, project_id: str) -> str:
        """返回接下来应该做什么的建议"""
        project = load_project(project_id)
        if not project:
            return "项目不存在"

        phase = project.phase

        if phase == Phase.INITIAL:
            if project.questions_pending:
                return f"📋 **回答以下问题**以推进项目:\n" + "\n".join(f"  • {q}" for q in project.questions_pending[:3])
            return "📋 **开始调研行业方案**，调用 research_industry()"

        elif phase == Phase.RESEARCH:
            if not project.research_notes:
                return "🔍 **调用 research_industry()** 进行行业调研"
            if project.questions_pending:
                return f"🔍 **回答调研相关问题**:\n" + "\n".join(f"  • {q}" for q in project.questions_pending[:3])
            return "🎨 **调用 propose_solution()** 生成方案建议"

        elif phase == Phase.REQUIREMENTS:
            if project.questions_pending:
                return f"📝 **回答需求相关问题**:\n" + "\n".join(f"  • {q}" for q in project.questions_pending[:3])
            if not project.proposed_solution:
                return "🎨 **调用 propose_solution()** 基于需求设计方案"
            return "📅 **确认方案后，调用 create_milestones()** 创建里程碑"

        elif phase == Phase.SOLUTION:
            if not project.proposed_solution:
                return "🎨 **调用 propose_solution()** 完成方案设计"
            if not project.milestones:
                return "📅 **调用 create_milestones()** 制定项目计划"
            return "✅ **确认方案和计划**，进入执行阶段"

        elif phase == Phase.PLANNING:
            if not project.milestones:
                return "📅 **调用 create_milestones()** 创建里程碑"
            return "✅ **确认里程碑计划**，调用 advance_phase() 进入执行阶段"

        elif phase == Phase.EXECUTION:
            # 找出下一个待完成的里程碑
            pending_mils = [m for m in project.milestones if m.status != "completed"]
            if pending_mils:
                m = pending_mils[0]
                return f"🏗️ **当前任务**: 完成里程碑 '{m.name}' ({m.deadline_estimate})\n  {m.description}"
            return "✅ **所有里程碑完成!** 调用 advance_phase() 进入验收阶段"

        elif phase == Phase.REVIEW:
            remaining = [c for c in project.quality_checklist if not c.startswith("✅")]
            if remaining:
                return f"✅ **验收检查**: 还有 {len(remaining)} 项待确认"
            return "🎉 **验收通过!** 调用 advance_phase() 完成项目"

        elif phase == Phase.COMPLETED:
            return "🎉 项目已完成! 创建新项目或回顾经验教训。"

        return "状态未知"

    # ---------------------------------------------------------------
    # 任务联动（与 task_supervisor 的接口）
    # ---------------------------------------------------------------

    def get_tasks_for_supervisor(self, project_id: str) -> List[dict]:
        """生成可供 task_supervisor 使用的任务列表"""
        project = load_project(project_id)
        if not project:
            return []

        tasks = []
        for m in project.milestones:
            tasks.append({
                "id": f"{project.id}_milestone_{m.order}",
                "project_id": project.id,
                "project_name": project.name,
                "milestone_name": m.name,
                "description": m.description,
                "deadline": m.deadline_estimate,
                "status": "completed" if m.status == "completed" else "in_progress" if m.status == "in_progress" else "pending",
                "source": "project_planner",
            })

        # 将未完成的质量检查项也作为任务
        for i, check in enumerate(project.quality_checklist):
            if not check.startswith("✅"):
                tasks.append({
                    "id": f"{project.id}_quality_{i}",
                    "project_id": project.id,
                    "project_name": project.name,
                    "milestone_name": "质量检查",
                    "description": check.lstrip("☐ "),
                    "deadline": "",
                    "status": "pending",
                    "source": "project_planner",
                })

        return tasks


# =============================================================================
# 测试函数
# =============================================================================

def test():
    """
    测试演示: 创建一个公司网站项目，走完完整流程。
    运行: python project_planner.py
    """
    import sys

    logger.info("=" * 60)
    logger.info("🧪  ProjectPlanner 测试演示")
    logger.info("=" * 60)
    planner = ProjectPlanner()

    # 1. 创建项目
    logger.info("\n📋 [1] 创建新项目: 公司官网")
    project = planner.new_project(
        name="公司官网",
        description="为一家科技公司建设企业官方网站，展示公司形象、产品和团队",
    )
    logger.info(f"   项目ID: {project.id}")
    logger.info(f"   行业推测: {project.industry}")
    logger.info(f"   当前阶段: {project.phase.value}")
    logger.info(f"   待问问题: {len(project.questions_pending)} 个")
    logger.info("\n📋 [2] 查看需要问用户的问题")
    questions = planner.ask_questions(project.id)
    for i, q in enumerate(questions, 1):
        logger.info(f"   Q{i}. {q}")
    logger.info("\n💬 [3] 模拟用户回答")
    answers = [
        ("项目的核心目标是什么？请用一句话描述。", "建立一个展示公司产品和品牌形象的企业官网，吸引潜在客户"),
        ("项目的主要用户或受众是谁？", "潜在客户、合作伙伴、求职者"),
        ("你有没有参考的竞品、网站或类似项目？", "参考了 Apple, Stripe, Notion 的官网设计"),
        ("这个项目的期望交付时间是什么时候？", "希望在2个月内完成上线"),
        ("有没有预算范围或者资源限制？", "预算10-15万，团队有3个前端和1个设计师"),
    ]
    for question, answer in answers:
        logger.info(f"   [{question[:30]}...]")
        planner.record_answer(project.id, question, answer)

    project = load_project(project.id)
    logger.info(f"   已问问题: {len(project.questions_asked)} 个")
    logger.info(f"   当前需求: {len(project.requirements)} 条")
    logger.info(f"   当前阶段: {project.phase.value}")
    logger.info("\n🔍 [4] 行业调研 (使用内置知识库)")
    research_notes = planner.research_industry(project.id)
    logger.info(f"   调研笔记长度: {len(research_notes)} 字符")
    logger.info(f"   最佳实践条目: {len(project.best_practices)} 条")
    logger.info(f"   识别风险: {len(project.risks)} 项")
    logger.info(f"   当前阶段: {project.phase.value}")
    logger.info("\n🎨 [5] 生成方案建议")
    solution = planner.propose_solution(project.id)
    logger.info(solution[:500] + "\n...(已截断)")
    logger.info("\n📅 [6] 创建里程碑")
    milestones = planner.create_milestones(project.id)
    for m in milestones:
        logger.info(f"   M{m.order}. {m.name} ({m.deadline_estimate})")
    logger.info("\n🔄 [7] 自动推进阶段")
    phase = planner.advance_phase(project.id)
    logger.info(f"   当前阶段: {phase.value}")
    phase = planner.advance_phase(project.id)
    logger.info(f"   推进后阶段: {phase.value}")
    logger.info("\n📊 [8] 项目状态报告")
    status = planner.get_status(project.id)
    logger.info(status["summary_text"])
    logger.info("\n💡 [9] 下一步建议")
    action = planner.get_next_action(project.id)
    logger.info(f"   {action}")
    logger.info("\n💾 [10] 验证持久化")
    loaded = load_project(project.id)
    logger.info(f"   重新加载: {loaded.name} (阶段: {loaded.phase.value})")
    all_projects = list_projects()
    logger.info(f"   已保存项目数: {len(all_projects)}")
    logger.info("\n🔄 [11] 生成 supervisor 任务")
    tasks = planner.get_tasks_for_supervisor(project.id)
    logger.info(f"   生成 {len(tasks)} 个任务")
    logger.info("\n" + "=" * 60)
    logger.info("✅  测试完成!")
    logger.info("=" * 60)
    delete_project(project.id)
    logger.info("  ✅ 测试数据已自动清理")
    return project


# =============================================================================
# CLI 入口
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        projects = list_projects()
        if not projects:
            logger.info("没有已保存的项目。")
        else:
            for p in projects:
                logger.info(f"  [{p.id}] {p.name} — 阶段: {p.phase.value} — 更新: {p.updated_at[:10]}")
    else:
        logger.info("用法:")
        logger.info("  python project_planner.py test   — 运行测试演示")
        logger.info("  python project_planner.py list   — 列出所有项目")
        print()
        logger.info("作为模块导入:")
        logger.info("  from project_planner import ProjectPlanner")
        logger.info('  planner = ProjectPlanner()')
        logger.info('  project = planner.new_project("我的项目", "项目描述")')