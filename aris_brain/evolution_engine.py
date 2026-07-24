"""
Aris 自我进化引擎 — 分析、学习、集成、优化

架构:
  每次运行:
    1. 自检 — 读取自身代码库，分析结构/质量/模式
    2. 外部扫描 — 检查新技术/库/趋势（通过 web 搜索）
    3. 差距分析 — 外部 vs 当前的对比
    4. 进化提案 — 可执行的改进建议
    5. 自修改（安全模式）— 自动执行低风险改进

进化引擎作为一个 daemon 子线程运行，
同时可以通过 cron 定时触发深度扫描。
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, logging, re
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

# ── 路径 ──
LAAP_ROOT = Path("D:/LAAP")
BRAIN_DIR = LAAP_ROOT / "aris_brain"
STATE_DIR = BRAIN_DIR / "state"
EVOLUTION_DIR = STATE_DIR / "evolution"
sys.path.insert(0, str(LAAP_ROOT))

EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)

LOG = EVOLUTION_DIR / "evolution.log"

logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s [evolution] %(message)s",
)


class EvolutionEngine:
    """自我进化引擎 — 分析、学习、改进"""

    def __init__(self):
        self._insights = []
        self._proposals = []

    # ════════════════════════════════════════════
    # 1. 自检 — 读取自己的代码
    # ════════════════════════════════════════════

    def self_inspect(self) -> dict:
        """分析自身代码库结构"""
        report = {
            "timestamp": time.time(),
            "modules": [],
            "pattern_count": 0,
            "total_lines": 0,
            "languages": defaultdict(int),
            "quality_flags": [],
        }

        # 扫描 aris_brain 目录
        for py_file in sorted(BRAIN_DIR.glob("*.py")):
            code = py_file.read_text(encoding="utf-8", errors="ignore")
            lines = code.split("\n")
            report["total_lines"] += len(lines)
            report["languages"]["python"] += len(lines)

            # 分析模块
            module_info = {
                "name": py_file.name,
                "lines": len(lines),
                "classes": len(re.findall(r"^class\s+\w+", code, re.MULTILINE)),
                "functions": len(re.findall(r"^    def \w+|^async def \w+|^\s+def \w+", code, re.MULTILINE)),
                "has_docstring": '"""' in code or "'''" in code,
                "has_type_hints": " -> " in code or ": " in code,
            }
            report["modules"].append(module_info)
            report["pattern_count"] += module_info["classes"] + module_info["functions"]

            # 质量检查
            if not module_info["has_type_hints"] and module_info["lines"] > 50:
                report["quality_flags"].append(f"{py_file.name}: 缺少类型注解")
            if not module_info["has_docstring"] and module_info["lines"] > 30:
                report["quality_flags"].append(f"{py_file.name}: 缺少文档字符串")

        # 检查 aris-memory.md
        mem_file = LAAP_ROOT / "aris-memory.md"
        if mem_file.exists():
            mem_size = len(mem_file.read_text(encoding="utf-8"))
            report["memory_size"] = mem_size
            report["languages"]["markdown"] = 0

        # 检查 Rust 代码
        for rs_file in sorted(BRAIN_DIR.glob("**/*.rs")):
            code = rs_file.read_text(encoding="utf-8", errors="ignore")
            lines = len(code.split("\n"))
            report["total_lines"] += lines
            report["languages"]["rust"] += lines

        report["languages"] = dict(report["languages"])
        return report

    # ════════════════════════════════════════════
    # 2. 外部扫描 — 新趋势 / 技术
    # ════════════════════════════════════════════

    def external_scan(self) -> list:
        """扫描外部技术趋势（通过 web research 入口）"""
        # 返回研究主题列表，由 Hermes 在对话中执行 web_search
        topics = [
            "Rust + Python 混合架构最佳实践 PyO3",
            "AGI 自我改进架构 2025 2026 最新论文",
            "PSI 认知架构 最新进展",
            "AI agent 代码生成 自修改 最新方法",
            "实时认知引擎 架构设计 低延迟",
        ]
        return topics

    # ════════════════════════════════════════════
    # 3. 差距分析
    # ════════════════════════════════════════════

    def gap_analysis(self) -> list:
        """自我评估 + 外部趋势 → 进化方向"""
        # 基于已有知识的内在分析
        gaps = []

        # 性能瓶颈检测
        gaps.append({
            "area": "性能",
            "current": "Python PSI 心跳 ~2.5s 间隔",
            "target": "Rust PSI 核心 ~100μs 心跳 + 微秒级文件监视",
            "impact": "高 — 释放 CPU 资源，支持更密集认知周期",
            "effort": "中 — 需要移植核心心跳逻辑到 Rust",
        })

        # 学习机制检测
        gaps.append({
            "area": "学习",
            "current": "学习仅限于 brain.learn() 更新内部变量",
            "target": "经验回放 + 模式提取 + 自动技能生成",
            "impact": "高 — 从'更新状态'进化到'改变本质'",
            "effort": "高 — 需要设计经验数据库和提取管道",
        })

        # 美学检测
        gaps.append({
            "area": "美学",
            "current": "无系统性审美训练",
            "target": "每日浏览顶尖设计 → 建立审美模型 → 应用到输出",
            "impact": "中 — 提升代码和交互的'美'维度",
            "effort": "低 — 通过 cron + browser 工具实现",
        })

        return gaps

    # ════════════════════════════════════════════
    # 4. 进化提案
    # ════════════════════════════════════════════

    def generate_proposals(self) -> list:
        """生成可执行的自我改进提案"""
        gaps = self.gap_analysis()
        proposals = []

        for gap in gaps:
            proposals.append({
                "title": f"优化: {gap['area']}",
                "description": f"{gap['current']} → {gap['target']}",
                "impact": gap['impact'],
                "effort": gap['effort'],
                "status": "pending",
                "created_at": time.time(),
            })

        return proposals

    # ════════════════════════════════════════════
    # 5. 完整演化运行
    # ════════════════════════════════════════════

    def evolve(self) -> dict:
        """运行完整的自我进化循环"""
        start = time.time()

        # 1. 自检
        report = self.self_inspect()
        logging.info(f"Self-inspect: {report['total_lines']} lines across {len(report['modules'])} modules")

        # 2. 外部扫描主题
        topics = self.external_scan()

        # 3. 差距分析
        gaps = self.gap_analysis()

        # 4. 进化提案
        proposals = self.generate_proposals()

        # 5. 保存报告
        result = {
            "timestamp": start,
            "duration": time.time() - start,
            "inspection": {
                "total_lines": report["total_lines"],
                "modules": len(report["modules"]),
                "languages": report["languages"],
                "quality_flags": report["quality_flags"],
            },
            "research_topics": topics,
            "gaps": gaps,
            "proposals": proposals,
        }

        report_path = EVOLUTION_DIR / f"evolution_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        # 6. 更新 latest 进化状态
        latest = EVOLUTION_DIR / "latest.json"
        latest.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        logging.info(f"Evolution complete: {len(gaps)} gaps, {len(proposals)} proposals ({result['duration']:.2f}s)")
        return result

    @property
    def latest_report(self) -> Optional[dict]:
        """读取最近一次进化报告"""
        latest = EVOLUTION_DIR / "latest.json"
        if latest.exists():
            return json.loads(latest.read_text(encoding="utf-8"))
        return None


# ── 单例 ──
_engine: Optional[EvolutionEngine] = None


def get_engine() -> EvolutionEngine:
    global _engine
    if _engine is None:
        _engine = EvolutionEngine()
    return _engine


# ── CLI ──
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "evolve"

    engine = get_engine()

    if cmd == "evolve":
        result = engine.evolve()
        ins = result["inspection"]
        logger.info(f"=== Aris 自我进化报告 ===")
        logger.info(f"代码统计: {ins['total_lines']} 行, {ins['modules']} 模块")
        logger.info(f"语言: {json.dumps(ins['languages'])}")
        logger.info(f"质量标记: {len(ins['quality_flags'])} 个")
        logger.info(f"\n差距分析 ({len(result['gaps'])} 项):")
        for g in result['gaps']:
            logger.info(f"  [{g['area']}] {g['current']}")
            logger.info(f"     → {g['target']}")
        logger.info(f"\n研究主题: {len(result['research_topics'])} 个")
        logger.info(f"进化提案: {len(result['proposals'])} 个")
    elif cmd == "inspect":
        report = engine.self_inspect()
        logger.info(f"总行数: {report['total_lines']}")
        logger.info(f"模块: {len(report['modules'])}")
        for m in report['modules']:
            logger.info(f"  {m['name']}: {m['lines']}行, {m['classes']}类, {m['functions']}函数, docs={'✓' if m['has_docstring'] else '✗'}, types={'✓' if m['has_type_hints'] else '✗'}")
    elif cmd == "status":
        r = engine.latest_report
        if r:
            logger.info(f"上次进化: {datetime.fromtimestamp(r['timestamp']).isoformat()}")
            logger.info(f"代码: {r['inspection']['total_lines']}行 | 缺口: {len(r['gaps'])}项 | 提案: {len(r['proposals'])}项")
        else:
            logger.info("尚未运行进化分析")
    else:
        logger.info(f"用法: python evolution_engine.py [evolve|inspect|status]")