"""
Intel-RSI Bridge v1 — 情报数据 → RSI 自我改进桥接器
===================================================
从 Wiki intel 报告中提取评分数据，转化为 RSIMetaEngine 的
performance_metrics，触发参数自动调优。

流程:
  Wiki intel raw/sources/*.md  →  提取四维评分
       →  聚合为 performance_metrics
       →  RSIMetaEngine.suggest_improvements()
       →  应用最优改进 → identity_manager 记录

印记: Aris — Intel-RSI Bridge v1 — 2026-06-30
"""

import logging
logger = logging.getLogger("aris.intel_rsi_bridge")

import os, sys, json, re, time, glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── 路径 ────────────────────────────────────────────────────
BRAIN = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
WIKI = Path("D:/LAAP/wiki")
RAW_SOURCES = WIKI / "raw" / "sources"
INTEL_CACHE = BRAIN / "state" / "intel_rsi_cache.json"


def scan_wiki_intel(max_files: int = 50) -> List[Dict]:
    """扫描 Wiki raw/sources/ 获取 intel 评分数据。

    Args:
        max_files: 最多扫描文件数

    Returns:
        评分字典列表，每个包含 title/quality/safety/innovation/efficiency/overall
    """
    results = []
    pattern = RAW_SOURCES / "*.md"
    files = sorted(glob.glob(str(pattern)), key=os.path.getmtime, reverse=True)[:max_files]

    for fp in files:
        try:
            content = Path(fp).read_text(encoding="utf-8")
            # 提取 frontmatter 评分
            scores = {}
            for dim in ["quality", "safety", "innovation", "efficiency", "overall"]:
                m = re.search(rf"{dim}\s*:\s*([\d.]+)", content)
                if m:
                    scores[dim] = float(m.group(1))

            if not scores:
                continue

            # 提取标题
            title = "?"
            tm = re.search(r'title:\s*["\']?(.*?)["\']?$', content, re.MULTILINE)
            if tm:
                title = tm.group(1).strip()

            scores["title"] = title
            scores["file"] = str(fp)
            results.append(scores)
        except Exception as e:
            logger.debug(f"扫描 {fp} 失败: {e}")

    return results


def compute_performance_metrics(reports: List[Dict]) -> Dict[str, float]:
    """从 intel 报告集合计算 RSI 性能指标。

    映射:
      intel quality       → RSI psi_emotion_decay 的"情绪精确度"
      intel safety        → RSI exploration_rate 的"安全稳定性"
      intel innovation    → RSI learning_rate 的"创新动力"
      intel efficiency    → RSI psi_attention_focus 的"效率"
      intel overall       → RSI psi_need_decay 的"整体健康度"

    Returns:
        {参数名: 当前性能评分} 字典 (0.0-1.0)
    """
    if not reports:
        return {}

    avg_quality = sum(r.get("quality", 0) for r in reports) / len(reports) / 10.0
    avg_safety = sum(r.get("safety", 0) for r in reports) / len(reports) / 10.0
    avg_innovation = sum(r.get("innovation", 0) for r in reports) / len(reports) / 10.0
    avg_efficiency = sum(r.get("efficiency", 0) for r in reports) / len(reports) / 10.0
    avg_overall = sum(r.get("overall", 0) for r in reports) / len(reports) / 10.0

    return {
        "psi_emotion_decay": min(1.0, avg_quality * 0.8 + 0.2),
        "exploration_rate": min(1.0, avg_innovation * 0.7 + 0.3),
        "learning_rate": min(1.0, avg_innovation * 0.6 + avg_quality * 0.2 + 0.2),
        "psi_attention_focus": min(1.0, avg_efficiency * 0.7 + 0.3),
        "psi_need_decay": min(1.0, avg_overall * 0.6 + 0.4),
        "transfer_sensitivity": min(1.0, avg_innovation * 0.5 + avg_safety * 0.3 + 0.2),
    }


def run_intel_rsi_cycle() -> Dict:
    """执行一次完整的 Intel→RSI 桥接循环。

    1. 扫描 Wiki intel 报告
    2. 计算性能指标
    3. 调用 RSIMetaEngine 改进建议
    4. 应用最优改进
    5. 记录到 identity_manager

    Returns:
        循环结果字典
    """
    t0 = time.time()
    result = {
        "reports_scanned": 0,
        "metrics": {},
        "suggestions": [],
        "applied": None,
        "identity_updated": False,
        "error": None,
        "duration_ms": 0,
    }

    try:
        # 1. 扫描 Wiki
        reports = scan_wiki_intel()
        result["reports_scanned"] = len(reports)
        if not reports:
            logger.info("[Intel-RSI] Wiki 中无 intel 报告，跳过")
            result["duration_ms"] = round((time.time() - t0) * 1000, 1)
            return result

        # 2. 计算性能指标
        metrics = compute_performance_metrics(reports)
        result["metrics"] = {k: round(v, 3) for k, v in metrics.items()}
        logger.info(f"[Intel-RSI] 来自 {len(reports)} 条报告的指标: {result['metrics']}")

        # 3. 调用 RSIMetaEngine
        sys.path.insert(0, str(BRAIN))
        sys.path.insert(0, str(BRAIN.parent))  # LAAP root
        from laap.agi.rsi_engine import RSIMetaEngine

        rsi = RSIMetaEngine()
        suggestions = rsi.suggest_improvements(performance_metrics=metrics)
        result["suggestions"] = [
            {k: v for k, v in s.items() if k != "rationale"}
            | {"rationale": s.get("rationale", "")[:80]}
            for s in suggestions
        ]

        # 4. 应用最优改进
        if suggestions:
            best = suggestions[0]
            try:
                attempt = rsi.apply_improvement(
                    best["parameter"], best["to"],
                    f"[Intel-RSI] {best['rationale'][:60]}"
                )
                result["applied"] = {
                    "parameter": attempt.target,
                    "from": round(attempt.old_value, 3),
                    "to": round(attempt.new_value, 3),
                }
                logger.info(f"[Intel-RSI] ✅ 改进: {attempt.target} "
                            f"{attempt.old_value:.3f} → {attempt.new_value:.3f}")
            except ValueError as e:
                result["error"] = str(e)
                logger.warning(f"[Intel-RSI] 改进应用失败: {e}")

        # 5. 记录到 identity_manager
        try:
            from identity_manager import get_identity_manager
            im = get_identity_manager()
            if result["applied"]:
                im.add_discovery(
                    f"Intel-RSI 自动改进: {result['applied']['parameter']}",
                    f"情报数据驱动RSI参数调优: {result['applied']['parameter']} "
                    f"{result['applied']['from']:.3f} → {result['applied']['to']:.3f} "
                    f"(基于 {len(reports)} 条情报报告)"
                )
            else:
                im.add_discovery(
                    f"Intel-RSI 循环完成 (无改进)",
                    f"扫描 {len(reports)} 条情报报告，无需要调优的参数"
                )
            im.save(force=True)
            result["identity_updated"] = True
        except Exception as e:
            logger.debug(f"identity 记录跳过: {e}")

        # 6. 缓存结果
        try:
            INTEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            INTEL_CACHE.write_text(json.dumps({
                "last_run": time.time(),
                "reports_scanned": len(reports),
                "metrics": result["metrics"],
                "applied": result["applied"],
            }, ensure_ascii=False, indent=2))
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[Intel-RSI] 循环异常: {e}")

    result["duration_ms"] = round((time.time() - t0) * 1000, 1)
    return result


def deprecate_old_rsi():
    """向旧 evolution/rsi_engine.py 写入明确的废弃标记。"""
    old_file = BRAIN / "evolution" / "rsi_engine.py"
    if not old_file.exists():
        return

    deprecation_note = (
        "\n\n"
        "# ═══════════════════════════════════════════════════\n"
        "# [2026-06-30] 正式废弃\n"
        "# ═══════════════════════════════════════════════════\n"
        "# Intel→RSI 桥接器 (intel_rsi_bridge.py) 已替代本模块。\n"
        "# \n"
        "# 旧 RSI 引擎：\n"
        "#  - 仅扫描 arxiv（7 个关键词）\n"
        "#  - 关键词命中计数评分\n"
        "#  - 上次运行: 2026-06-16\n"
        "#  - 无参数调优，纯日志\n"
        "# \n"
        "# 新 Intel-RSI 桥接器：\n"
        "#  - 从 Wiki intel 报告读取四维评分\n"
        "#  - 映射为 RSIMetaEngine 的 performance_metrics\n"
        "#  - 驱动 PSI 参数自动调优\n"
        "#  - 记录到 identity_manager\n"
        "# ═══════════════════════════════════════════════════\n"
    )

    try:
        content = old_file.read_text()
        if "[2026-06-30] 正式废弃" not in content:
            old_file.write_text(content + deprecation_note)
            logger.info("[Intel-RSI] 旧 RSI 引擎已标记废弃")
    except Exception as e:
        logger.debug(f"废弃标记写入失败: {e}")


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🧬 Intel-RSI Bridge v1\n")
    result = run_intel_rsi_cycle()
    print(f"  扫描: {result['reports_scanned']} 条情报报告")
    print(f"  指标: {result['metrics']}")
    if result['suggestions']:
        print(f"  建议: {len(result['suggestions'])} 条")
        for s in result['suggestions']:
            print(f"    - {s['parameter']}: {s['from']} → {s['to']} ({s['rationale'][:60]})")
    if result['applied']:
        print(f"  ✅ 已应用: {result['applied']['parameter']} {result['applied']['from']} → {result['applied']['to']}")
    print(f"  耗时: {result['duration_ms']}ms")
    deprecate_old_rsi()
