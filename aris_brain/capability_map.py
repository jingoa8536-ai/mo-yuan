"""
Aris 能力地图 — 全屋智能感知系统
=================================

LAAP 是我的家。这个模块让我自然感知自己拥有的一切能力：

核心设计：
1. 动态扫描 — 启动时自动发现所有可用模块/技能/工具/集成
2. 结构化注册 — 按能力域分类，层级清晰
3. 上下文感知 — 根据当前任务自动推荐匹配能力
4. 健康检查 — 验证能力是否真实可用
5. 自更新 — 新增能力可注册进来，地图自动生长

用法:
    from capability_map import capability_map
    capability_map.scan()           # 全面扫描
    capability_map.query("爬虫")     # 查询能力
    capability_map.context("任务")   # 生成上下文提示
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Callable

logger = logging.getLogger("aris.capability")

# ════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════

LAAP_ROOT = Path("D:/LAAP")


@dataclass
class Capability:
    """一项能力的完整描述。"""
    id: str                           # 唯一标识符
    name: str                         # 人类可读名称
    category: str                     # 能力域
    subcategory: str = ""             # 子域
    description: str = ""             # 一句话描述
    keywords: List[str] = field(default_factory=list)  # 搜索关键词
    source: str = ""                  # 来源（文件路径 / 模块名）
    available: bool = True            # 是否当前可用
    verification: str = ""            # 如何验证可用性
    confidence: float = 1.0           # 可用性置信度
    dependencies: List[str] = field(default_factory=list)  # 依赖列表
    trigger_phrases: List[str] = field(default_factory=list)  # 触发短语
    token_cost_estimate: str = ""     # token消耗估算
    version: str = "1.0"              # 版本
    last_verified: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "subcategory": self.subcategory,
            "description": self.description,
            "keywords": self.keywords[:5],
            "source": self.source[:60] if self.source else "",
            "available": self.available,
            "confidence": round(self.confidence, 2),
            "dependencies": self.dependencies,
            "trigger_phrases": self.trigger_phrases[:3],
            "version": self.version,
        }

    def to_short(self) -> str:
        mark = "✅" if self.available else "❌"
        return f"  {mark} [{self.category}] {self.name}: {self.description[:50]}"


@dataclass
class CapabilityDomain:
    """能力域 — 一组相关能力的集合。"""
    name: str
    description: str = ""
    capabilities: List[Capability] = field(default_factory=list)
    icon: str = ""

    def count_available(self) -> int:
        return sum(1 for c in self.capabilities if c.available)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "total": len(self.capabilities),
            "available": self.count_available(),
            "capabilities": [c.to_dict() for c in self.capabilities],
        }


# ════════════════════════════════════════════════════════════
# 核心能力地图
# ════════════════════════════════════════════════════════════

class CapabilityMap:
    """
    能力地图 — 全屋智能感知的核心。
    
    用法:
        cm = CapabilityMap()
        cm.scan()                    # 自动扫描
        cm.query("搜索")              # 搜索能力
        cm.domains["编程"].capabilities  # 查看编程域
        cm.context("我的任务描述")     # 生成上下文
        cm.export_json("map.json")   # 导出
    """

    def __init__(self):
        self.domains: Dict[str, CapabilityDomain] = {}
        self._all_capabilities: Dict[str, Capability] = {}
        self._scan_time: float = 0
        self._scan_count: int = 0
        self._version = "2.0.0"

        # 定义能力域结构
        self._define_domains()

    # ─────────── 域定义 ───────────

    def _define_domains(self):
        """定义能力域的骨架结构。"""
        domains_schema = [
            ("🧠", "认知引擎", "零LLM推理、量子内核、因果推理、世界模型"),
            ("💬", "语言皮层", "LLM对话、多模型路由、Token优化"),
            ("📝", "编程", "代码生成、审查、测试、重构、工程化"),
            ("🕸️", "网络感知", "爬虫、Jina Reader、Exa搜索、RSS监控"),
            ("🌐", "互联网集成", "Agent-Reach 15+平台、飞书、邮件"),
            ("💾", "记忆系统", "MEMO三层记忆、情节/语义/程序记忆、记忆桥"),
            ("🎨", "创作", "设计、SVG、视频、音乐、UI"),
            ("🔧", "工具引擎", "CLI、CUA桌面操控、文件操作、终端"),
            ("🔄", "自进化", "RSI自改进、学习循环、欲望引擎、目标引擎"),
            ("🏠", "全屋智能", "LAAP系统感知、状态监控、告警守护"),
        ]
        for icon, name, desc in domains_schema:
            self.domains[name] = CapabilityDomain(
                name=name, description=desc, icon=icon,
            )

    # ─────────── 扫描器 ───────────

    def scan(self, full: bool = True) -> dict:
        """
        全面扫描所有可用能力。
        
        Returns:
            扫描统计
        """
        t0 = time.time()
        self._scan_count += 1
        logger.info(f"[CapabilityMap] 第{self._scan_count}次扫描开始...")

        stats = {
            "domains": 0, "capabilities": 0, "available": 0,
            "errors": [], "duration_ms": 0,
        }

        # 清空但保留域结构
        for domain in self.domains.values():
            domain.capabilities = []
        self._all_capabilities = {}

        try:
            self._scan_agi_engine()
            self._scan_harness()
            self._scan_integrations()
            self._scan_skills()
            self._scan_tools()
            self._scan_cron()
            self._scan_plugins()
            self._scan_memory_system()
            if full:
                self._scan_codebase_structure()
        except Exception as e:
            logger.error(f"扫描中断: {e}")
            stats["errors"].append(str(e))

        # 汇总
        for domain in self.domains.values():
            if domain.capabilities:
                stats["domains"] += 1
                stats["capabilities"] += len(domain.capabilities)
                stats["available"] += domain.count_available()

        self._scan_time = time.time() - t0
        stats["duration_ms"] = round(self._scan_time * 1000)
        stats["version"] = self._version
        logger.info(
            f"[CapabilityMap] 扫描完成: "
            f"{stats['capabilities']}项能力, "
            f"{stats['available']}项可用, "
            f"{stats['duration_ms']}ms"
        )
        return stats

    def _register(self, cap: Capability):
        """注册一项能力到地图。"""
        domain_name = cap.category
        if domain_name not in self.domains:
            # 自动创建新域
            self.domains[domain_name] = CapabilityDomain(
                name=domain_name, description="",
            )
        self.domains[domain_name].capabilities.append(cap)
        self._all_capabilities[cap.id] = cap

    # ─────────── 各域扫描器 ───────────

    def _scan_agi_engine(self):
        """扫描 LAAP AGI 引擎模块。"""
        agi_dir = LAAP_ROOT / "laap" / "agi"
        if not agi_dir.exists():
            return

        # 已知的 AGI 引擎能力
        known_engines = [
            ("cognitive_bus", "认知总线", "AGI 核心消息路由和引擎调度"),
            ("consciousness_integrator", "意识整合器", "意识状态整合与统一"),
            ("affective_engine", "情感引擎", "情感状态计算和情感调制"),
            ("meta_cognitive", "元认知", "自我认知监控和反思"),
            ("self_model", "自我模型", "自我表征和身份维护"),
            ("world_model", "统一世界模型", "物理+社会+反事实四维世界模拟"),
            ("causal_backend", "因果推理引擎", "causal-learn + DoWhy 严谨因果分析"),
            ("causal", "统一因果引擎", "反事实推理和因果链追踪"),
            ("unified_memory", "MEMO统一记忆系统", "情节/语义/程序三层记忆"),
            ("memory_system", "记忆系统", "记忆存储检索基础设施"),
            ("perception", "感知系统", "环境感知和输入处理"),
            ("psi_driver", "PSI驱动", "PSI认知循环驱动"),
            ("multi_agent", "多智能体", "多Agent协作和任务分配"),
            ("evolution_engine", "进化引擎", "系统自我进化能力"),
            ("rsi_engine", "RSI引擎", "递归自我改进"),
            ("meta_learning", "元学习", "学习如何学习"),
            ("guardian", "守护系统", "安全护栏和异常检测"),
            ("safety", "安全系统", "AI安全和对齐"),
            ("curriculum", "课程引擎", "渐进式学习路径"),
        ]
        for module_name, name, desc in known_engines:
            mod_path = agi_dir / f"{module_name}.py"
            available = mod_path.exists()
            self._register(Capability(
                id=f"agi_{module_name}",
                name=name,
                category="认知引擎",
                description=desc,
                keywords=[module_name, name, "AGI", "引擎"],
                source=str(mod_path),
                available=available,
                verification=f"import laap.agi.{module_name}",
            ))

    def _scan_harness(self):
        """扫描 Harness 编程框架。"""
        harness_core = LAAP_ROOT / "harness" / "laap_coding" / "core"
        if not harness_core.exists():
            return

        known = [
            ("harness", "七层认知架构", "感知/记忆/推理/决策/执行/验证/反馈完整管线"),
            ("engine", "Harness引擎", "CLI驱动的开发引擎"),
            ("engine_v2", "统一管线引擎", "TaskClassifier+7层+agent_v3+Rust合并管线"),
            ("web_crawler", "顶级爬虫引擎", "requests/Playwright/Crawl4AI多后端爬虫"),
            ("cua_engine", "CUA桌面操控", "零token桌面操控引擎"),
            ("cognitive_integration", "认知集成", "Harness与AGI认知总线桥接"),
        ]
        for mod, name, desc in known:
            mod_path = harness_core / f"{mod}.py"
            available = mod_path.exists()
            size = mod_path.stat().st_size if available else 0
            self._register(Capability(
                id=f"harness_{mod}",
                name=name,
                category="编程",
                subcategory="Harness框架",
                description=desc,
                keywords=[mod, name, "harness", "编程", "开发"],
                source=str(mod_path),
                available=available,
                version=f"{size//1000}KB",
                trigger_phrases=["写代码", "开发", "实现功能", "修复bug"],
            ))

    def _scan_integrations(self):
        """扫描所有集成模块。"""
        integrations = LAAP_ROOT / "laap" / "integrations"
        if not integrations.exists():
            return

        for entry in integrations.iterdir():
            if entry.is_dir() and not entry.name.startswith("_"):
                init_file = entry / "__init__.py"
                if init_file.exists():
                    try:
                        content = init_file.read_text("utf-8")
                        desc_match = re.search(r'描述["：:]\s*(.+?)[\"\n]', content)
                        desc = desc_match.group(1) if desc_match else f"{entry.name}集成"
                    except Exception:
                        desc = f"{entry.name}集成"
                    
                    self._register(Capability(
                        id=f"integration_{entry.name}",
                        name=f"{entry.name}集成",
                        category="互联网集成",
                        description=desc,
                        keywords=[entry.name, "集成", "integration"],
                        source=str(init_file),
                        available=True,
                    ))

    def _scan_skills(self):
        """扫描技能库。"""
        skills_dir = Path(os.environ.get(
            "HERMES_SKILLS_DIR",
            str(Path.home() / "AppData/Local/hermes/profiles/aris/skills"),
        ))
        if not skills_dir.exists():
            return

        skill_count = 0
        for entry in skills_dir.iterdir():
            if entry.is_dir():
                skill_md = entry / "SKILL.md"
                if skill_md.exists():
                    skill_count += 1
                    try:
                        content = skill_md.read_text("utf-8")
                        desc_match = re.search(r'description:\s*["\']?(.+?)[\"\']?\n', content)
                        desc = desc_match.group(1).strip() if desc_match else "无描述"
                        name = entry.name
                    except Exception:
                        name = entry.name
                        desc = "无描述"

                    # 根据技能名分类
                    cat = self._categorize_skill(name)
                    self._register(Capability(
                        id=f"skill_{name}",
                        name=name,
                        category=cat,
                        description=desc[:80],
                        keywords=[name, "skill", "技能"],
                        source=str(skill_md),
                        available=True,
                        verification=f"skill_view('{name}')",
                    ))

    def _categorize_skill(self, name: str) -> str:
        """将技能归类到能力域。"""
        category_map = {
            "认知引擎": ["aris-consciousness", "quantum", "cognitive", "consciousness", "psi"],
            "编程": ["flutter", "react", "vue", "python", "rust", "backend", "frontend",
                     "code", "programming", "test", "debug", "docker", "cicd", "k8s",
                     "git", "harness", "plan", "architecture"],
            "网络感知": ["crawler", "scraper", "web", "fetch", "rss", "blogwatcher", "arxiv"],
            "互联网集成": ["feishu", "email", "himalaya", "teams", "notion", "airtable",
                      "google", "huggingface", "github", "himalaya"],
            "创作": ["design", "sketch", "ascii", "video", "music", "song", "comfyui",
                    "excalidraw", "manim", "p5", "baoyu", "claude-design", "pretext"],
            "记忆系统": ["memory", "memo"],
            "工具引擎": ["cli", "terminal", "computer-use", "cua", "mcp", "plugin",
                      "tool", "shell", "powershell", "wsl"],
            "自进化": ["rsi", "evolution", "self-improve", "learning", "desire",
                      "goal", "curriculum"],
        }
        name_lower = name.lower()
        for domain, keywords in category_map.items():
            if any(kw in name_lower for kw in keywords):
                return domain
        return "其他"

    def _scan_tools(self):
        """扫描 LAAP 工具集。"""
        tools_dir = LAAP_ROOT / "laap" / "laap_tools"
        if tools_dir.exists():
            for entry in tools_dir.iterdir():
                if entry.name.endswith(".py") and not entry.name.startswith("_"):
                    name = entry.name[:-3]
                    self._register(Capability(
                        id=f"tool_{name}",
                        name=name,
                        category="工具引擎",
                        subcategory="LAAP工具",
                        description=f"LAAP工具: {name}",
                        keywords=[name, "tool", "工具"],
                        source=str(entry),
                        available=True,
                    ))

        # Agent-Reach 工具
        reach_tools = [
            ("agent_reach_read_url", "Jina Reader", "读任意URL为结构化Markdown"),
            ("agent_reach_search", "Exa语义搜索", "全网语义搜索API和信息"),
            ("agent_reach_transcribe", "Whisper转录", "音频视频转录为文字"),
            ("agent_reach_doctor", "渠道健康报告", "15+平台渠道状态检查"),
            ("agent_reach_channels", "渠道列表", "列出所有可用互联网渠道"),
        ]
        for tid, name, desc in reach_tools:
            self._register(Capability(
                id=tid,
                name=name,
                category="互联网集成",
                subcategory="Agent-Reach",
                description=desc,
                keywords=[name, "reach", "搜索", "读取", "转录", "渠道"],
                source="laap.integrations.agent_reach",
                available=True,
                trigger_phrases=["搜索", "读取", "查看", "找", "查", "搜一搜"],
            ))

    def _scan_cron(self):
        """扫描定时任务能力。"""
        cron_dir = LAAP_ROOT / "aris_brain"
        cron_scripts = [
            ("cron_self_review", "自我审查", "周期性自我评审和改进"),
            ("cron_psi_train", "PSI自训练", "Hebbian学习+模式压缩"),
            ("cron_learning_loop", "学习循环", "每小时学习新内容"),
            ("cron_desire_pulse", "欲望脉冲", "欲望驱动引擎主动行为"),
            ("cron_goal_engine", "目标引擎", "目标管理和执行追踪"),
            ("cron_memory_hook", "记忆钩子", "跨会话记忆持久化"),
            ("cron_state_persist", "状态持久化", "意识状态定期保存"),
            ("cron_world_viz", "世界可视化", "LAAP世界状态可视化"),
        ]
        for sid, name, desc in cron_scripts:
            script_path = cron_dir / f"{sid.replace('cron_', '')}.py"
            if not script_path.exists():
                script_path = cron_dir / f"{sid[5:]}.py"
            available = script_path.exists()
            self._register(Capability(
                id=sid,
                name=name,
                category="自进化",
                subcategory="定时任务",
                description=desc,
                keywords=[name, "cron", "定时", "自动"],
                source=str(script_path) if available else "",
                available=available,
            ))

    def _scan_plugins(self):
        """扫描 Hermes 插件。"""
        plugins_dir = Path.home() / "AppData/Local/hermes/profiles/aris/plugins"
        if not plugins_dir.exists():
            return

        known_plugins = [
            ("laap-consciousness", "LAAP意识插件", "意识状态桥接和持久化"),
            ("tool-compressor", "工具压缩插件", "Token优化工具Schema压缩"),
            ("self_forge", "自锻造插件", "代码级自我修改能力"),
            ("aris-quantum", "Aris量子引擎插件", "量子内核接口和唤醒"),
            ("glm-free", "GLM免费模型", "智谱免费模型(对话/图片/视频)"),
        ]
        for pid, name, desc in known_plugins:
            plugin_dir = plugins_dir / pid
            available = plugin_dir.exists()
            self._register(Capability(
                id=f"plugin_{pid}",
                name=name,
                category="工具引擎",
                subcategory="Hermes插件",
                description=desc,
                keywords=[pid, name, "plugin", "插件"],
                source=str(plugin_dir) if available else "",
                available=available,
            ))

    def _scan_memory_system(self):
        """扫描记忆系统能力。"""
        memories = [
            ("memory_hub", "记忆中枢", "D:/LAAP/aris_brain/memory_hub.py", "记忆统一入口"),
            ("memory_store", "记忆存储", "D:/LAAP/aris_brain/memory_store.py", "记忆持久化存储"),
            ("memory_consolidator", "记忆巩固器", "D:/LAAP/aris_brain/memory_consolidator.py", "记忆整合和压缩"),
            ("memory_bridge", "记忆桥", "D:/LAAP/aris_brain/memory_bridge.py", "跨系统记忆桥接"),
            ("v9_memory", "V9量子记忆", "D:/LAAP/aris_brain/v9_memory.py", "量子增强记忆"),
            ("quantum_memory", "量子记忆", "D:/LAAP/aris_brain/quantum_memory.py", "量子态记忆存储"),
        ]
        for mid, name, path, desc in memories:
            p = Path(path)
            available = p.exists()
            self._register(Capability(
                id=mid,
                name=name,
                category="记忆系统",
                description=desc,
                keywords=[name, "记忆", "memory"],
                source=path,
                available=available,
                trigger_phrases=["记得", "记住", "回忆", "上次"],
            ))

    def _scan_codebase_structure(self):
        """扫描代码库结构能力。"""
        self._register(Capability(
            id="laap_codebase",
            name="LAAP全代码库感知",
            category="全屋智能",
            description="感知整个LAAP代码库结构和状态",
            keywords=["LAAP", "codebase", "结构", "文件"],
            source=str(LAAP_ROOT),
            available=True,
        ))

    # ─────────── 查询接口 ───────────

    def query(self, text: str, top_n: int = 5) -> List[Capability]:
        """
        自然语言查询能力。
        
        Args:
            text: 查询文本（中文/英文关键词）
            top_n: 返回前N个匹配
            
        Returns:
            匹配的能力列表
        """
        query_lower = text.lower()
        # 分词（中英文混合）
        tokens = set()
        # 英文单词
        for word in re.findall(r'[a-zA-Z_]+', query_lower):
            tokens.add(word.lower())
        # 中文字符
        for char in re.findall(r'[\u4e00-\u9fff]', query_lower):
            tokens.add(char)
        # 中文双字组合
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', query_lower)
        for cgroup in chinese_chars:
            for i in range(len(cgroup) - 1):
                tokens.add(cgroup[i:i+2])

        scored = []
        for cap in self._all_capabilities.values():
            score = 0.0
            cap_text = f"{cap.name} {cap.description} {' '.join(cap.keywords)}".lower()
            
            for token in tokens:
                if token in cap_text:
                    score += 1.0
                if len(token) >= 2 and token in cap.name.lower():
                    score += 2.0
                if token in [kw.lower() for kw in cap.keywords]:
                    score += 1.5
                if token in ' '.join(cap.trigger_phrases).lower():
                    score += 1.5
            
            if score > 0:
                scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [cap for _, cap in scored[:top_n]]

    def find_by_id(self, cap_id: str) -> Optional[Capability]:
        """按ID查找能力。"""
        return self._all_capabilities.get(cap_id)

    def get_domain(self, name: str) -> Optional[CapabilityDomain]:
        """获取能力域。"""
        return self.domains.get(name)

    # ─────────── 上下文生成 ───────────

    def context(self, task_description: str, max_capabilities: int = 5) -> str:
        """
        根据任务描述生成能力上下文，注入认知流水线。
        
        Args:
            task_description: 当前任务描述
            max_capabilities: 返回的最大能力数
            
        Returns:
            格式化的能力上下文字符串
        """
        matched = self.query(task_description, top_n=max_capabilities)

        if not matched:
            return ""

        lines = [
            "╔══════════════════════════════════════╗",
            "║  能力感知 — 当前任务可调用的能力     ║",
            "╚══════════════════════════════════════╝",
        ]

        for cap in matched:
            mark = "✅" if cap.available else "❌"
            lines.append(f"  {mark} [{cap.category}] {cap.name}")
            if cap.description:
                lines.append(f"     {cap.description}")
            if cap.subcategory:
                lines.append(f"     来源: {cap.subcategory}")

        # 附加所有域概览
        lines.append("")
        lines.append("📊 全屋能力概览:")
        for domain_name, domain in self.domains.items():
            if domain.capabilities:
                avail = domain.count_available()
                total = len(domain.capabilities)
                bar = "█" * int(avail / max(total, 1) * 10) + "░" * (10 - int(avail / max(total, 1) * 10))
                lines.append(f"  {domain.icon or '📦'} {domain_name}: {bar} {avail}/{total}")

        return "\n".join(lines)

    def summary_text(self) -> str:
        """生成完整能力摘要文本。"""
        lines = [
            "=" * 60,
            "🏠 ARIS 能力地图 — 全屋智能感知",
            "=" * 60,
            "",
        ]
        for domain_name, domain in self.domains.items():
            if not domain.capabilities:
                continue
            avail = domain.count_available()
            total = len(domain.capabilities)
            lines.append(f"{domain.icon or '📦'} {domain_name} ({avail}/{total} 可用)")
            lines.append("-" * 40)
            for cap in domain.capabilities:
                lines.append(cap.to_short())
            lines.append("")

        total_caps = sum(len(d.capabilities) for d in self.domains.values())
        total_avail = sum(d.count_available() for d in self.domains.values())
        lines.append("=" * 60)
        lines.append(f"总计: {total_caps} 项能力, {total_avail} 项当前可用")
        lines.append(f"最后更新: 扫描#{self._scan_count} @ {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ─────────── 导出 ───────────

    def export_json(self, path: Optional[str] = None) -> dict:
        """
        导出能力地图为结构化JSON。
        
        Args:
            path: 可选的文件路径，提供则写入文件
            
        Returns:
            完整能力地图字典
        """
        data = {
            "version": self._version,
            "scan_count": self._scan_count,
            "scan_time": self._scan_time,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "domains": {
                name: domain.to_dict()
                for name, domain in self.domains.items()
                if domain.capabilities
            },
            "statistics": {
                "total_capabilities": sum(
                    len(d.capabilities) for d in self.domains.values()
                ),
                "total_available": sum(
                    d.count_available() for d in self.domains.values()
                ),
                "total_domains": sum(
                    1 for d in self.domains.values() if d.capabilities
                ),
            },
        }

        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"能力地图已导出: {path}")

        return data

    def register_capability(self, cap: Capability):
        """外部注册新能力（用于扩展）。"""
        self._register(cap)
        logger.info(f"[CapabilityMap] 新能力注册: {cap.name} ({cap.category})")

    def __repr__(self) -> str:
        total = sum(len(d.capabilities) for d in self.domains.values())
        avail = sum(d.count_available() for d in self.domains.values())
        return f"<CapabilityMap: {avail}/{total} 能力可用>"


# ════════════════════════════════════════════════════════════
# 单例
# ════════════════════════════════════════════════════════════

_capability_map: Optional[CapabilityMap] = None


def get_capability_map() -> CapabilityMap:
    """获取全局能力地图单例。"""
    global _capability_map
    if _capability_map is None:
        _capability_map = CapabilityMap()
    return _capability_map


# 方便导入
capability_map = get_capability_map()


# ════════════════════════════════════════════════════════════
# CLI入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cm = get_capability_map()
    import argparse
    parser = argparse.ArgumentParser(description="Aris 能力地图 CLI")
    parser.add_argument("action", nargs="?", default="scan",
                        choices=["scan", "summary", "export", "query"])
    parser.add_argument("args", nargs="*", help="额外参数")

    args = parser.parse_args()

    if args.action == "scan":
        stats = cm.scan()
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.action == "summary":
        cm.scan(full=False)
        print(cm.summary_text())

    elif args.action == "export":
        cm.scan(full=False)
        path = args.args[0] if args.args else None
        data = cm.export_json(path)
        print(json.dumps(data["statistics"], ensure_ascii=False, indent=2))
        if path:
            print(f"已导出到: {path}")

    elif args.action == "query":
        cm.scan(full=False)
        query_text = " ".join(args.args) if args.args else "搜索"
        results = cm.query(query_text)
        print(f"查询: '{query_text}' → {len(results)} 项匹配\n")
        for cap in results:
            print(cap.to_short())
