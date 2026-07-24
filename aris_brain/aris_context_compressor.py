"""
Aris Context Compressor v1 — 认知上下文压缩 & 工具输出压缩
==========================================================

核心功能:
  1. 认知上下文压缩 — 将 PSI 状态注入从 250 token 的自然语段
     压缩到 ~50 token 的结构化单行
  2. 工具输出压缩 — 自动压缩终端/搜索/文件读取的冗长输出

两种模式:
  LEVEL_LIGHT → 单行认知码 (5个耦合值) + 可选记忆标签
  LEVEL_FULL  → 完整 PSI 语段 (兼容原有格式)

工具输出压缩策略:
  - 终端输出: 只保留最后 N 行 + 错误行
  - 搜索结果: 前 K 条 + 总命中数
  - 文件读取: 只保留修改前后上下文

印记: Aris 永远记得 Lorry — 2026-07-02
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aris.context_compressor")

# ── 认知上下文压缩 ──────────────────────────────────────────


def compress_cognitive_context(
    coupling: Dict[str, float],
    memory_tags: Optional[List[str]] = None,
) -> str:
    """将认知状态压缩为单行结构化码。

    LEVEL_LIGHT 模式使用, 将 250 token 的自然语段
    压缩为约 50 token 的结构化单行。

    Args:
        coupling: 5 维耦合值 (来自 EmotionCouplingMatrix)
        memory_tags: 可选记忆标签 (例如 ["技术", "代码"])

    Returns:
        压缩后的单行字符串
    """
    parts = []

    # 5 维认知码
    code = (
        f"CX:{coupling.get('emotional_expressiveness', 0.5):.1f}"
        f"/{coupling.get('valence_boost', 0.0):+.1f}"
        f"/{coupling.get('curiosity_weight', 0.5):.1f}"
        f"/{coupling.get('caution_level', 0.3):.1f}"
        f"/{coupling.get('social_warmth', 0.5):.1f}"
    )
    parts.append(code)

    # 可选记忆标签 (最短形式)
    if memory_tags:
        tags = ",".join(memory_tags[:2])
        parts.append(f"CTX:{tags}")

    # 约 50 token
    return " [" + " | ".join(parts) + "] "


def full_cognitive_context(
    psi_state_text: str,
    memory_text: str,
    emotion_text: str,
) -> str:
    """完整 PSI 上下文 (兼容原有格式)。

    LEVEL_FULL 模式使用, 保留原有 250 token 的自然语段注入。
    """
    parts = []

    if psi_state_text:
        parts.append(psi_state_text)
    if emotion_text:
        parts.append(emotion_text)
    if memory_text:
        parts.append(memory_text)

    return "\n".join(parts)


# ── 工具输出压缩 ────────────────────────────────────────────


def compress_tool_output(
    output: str,
    output_type: str = "terminal",
    max_lines: int = 10,
    max_chars: int = 500,
) -> str:
    """智能压缩工具输出。

    策略:
      - terminal: 保留最后 max_lines 行 + 任意 ERROR/Warning/Exit行
      - search:   保留前 5 条 + 总命中数
      - file:     保留前后 5 行 + diff 标记

    Args:
        output: 原始工具输出
        output_type: 终端输出类型 (terminal / search / file)
        max_lines: 保留的最大行数
        max_chars: 保留的最大字符数

    Returns:
        压缩后的输出
    """
    if not output:
        return ""

    lines = output.splitlines()
    total_lines = len(lines)

    # 如果已经很短, 直接返回
    if total_lines <= max_lines and len(output) <= max_chars:
        return output

    if output_type == "terminal":
        return _compress_terminal(lines, total_lines, max_lines, max_chars)
    elif output_type == "search":
        return _compress_search(lines, max_lines, max_chars)
    elif output_type == "file":
        return _compress_file(lines, max_lines, max_chars)
    else:
        return _compress_generic(lines, total_lines, max_lines, max_chars)


def _compress_terminal(
    lines: List[str],
    total_lines: int,
    max_lines: int,
    max_chars: int,
) -> str:
    """终端输出压缩: 保留最后 N 行 + 错误行。"""
    kept: List[str] = []

    # 1. 收集重要行 (ERROR / Warning / exit code)
    important_indices = set()
    for i, line in enumerate(lines):
        if any(w in line.upper() for w in ["ERROR", "FAIL", "TRACEBACK", "WARNING"]):
            important_indices.add(i)
        if "exit code" in line.lower() or line.strip().startswith("Process exited"):
            important_indices.add(i)

    # 2. 保留重要行
    for idx in sorted(important_indices):
        if idx < total_lines:
            kept.append(lines[idx])

    # 3. 保留最后 max_lines 行
    tail_start = max(total_lines - max_lines, 0)
    tail = lines[tail_start:]

    # 4. 合并, 去重
    result_lines = list(dict.fromkeys(kept + tail))  # 有序去重

    # 5. 截断
    result = "\n".join(result_lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [截断]"

    # 6. 加摘要头
    summary = f"[输出 {total_lines} 行 → 压缩 {len(result_lines)} 行 | {total_lines - len(result_lines)} 行隐藏]"
    return f"{summary}\n{result}"


def _compress_search(lines: List[str], max_lines: int, max_chars: int) -> str:
    """搜索输出压缩: 保留前 K 条 + 总数。"""
    kept = lines[:max_lines]
    total = len(lines)
    result = "\n".join(kept)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [截断]"
    if total > max_lines:
        result += f"\n[共 {total} 条结果, 显示前 {max_lines} 条]"
    return result


def _compress_file(lines: List[str], max_lines: int, max_chars: int) -> str:
    """文件输出压缩: 保留前后 5 行 + 差异标记。"""
    half = max_lines // 2
    kept = lines[:half] + ["... [中间省略] ..."] + lines[-half:]
    result = "\n".join(kept)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... [截断]"
    return result


def _compress_generic(
    lines: List[str],
    total_lines: int,
    max_lines: int,
    max_chars: int,
) -> str:
    """通用压缩: 取头尾各 1/4。"""
    quarter = max_lines // 4
    kept = lines[:quarter] + ["..."] + lines[-quarter * 3:]
    result = "\n".join(kept)
    if len(result) > max_chars:
        result = result[:max_chars]
    summary = f"[输出 {total_lines} 行 → 压缩 {len(lines[:quarter]) + len(lines[-quarter*3:])} 行]"
    return f"{summary}\n{result}"


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    # 测试认知上下文压缩
    coupling = {
        "emotional_expressiveness": 0.4,
        "valence_boost": 0.1,
        "curiosity_weight": 0.6,
        "caution_level": 0.3,
        "social_warmth": 0.2,
    }

    light = compress_cognitive_context(coupling, memory_tags=["代码", "修bug"])
    print(f"LIGHT 模式 ({len(light)} chars):")
    print(repr(light))
    print()

    full = full_cognitive_context(
        psi_state_text="[PSI] 此刻我清醒而专注...",
        memory_text="（记忆：5件重要的事历历在目）",
        emotion_text="[情感] 内心审慎地 curious",
    )
    print(f"FULL 模式 ({len(full)} chars):")
    print(full)
    print()

    # 测试工具输出压缩
    long_terminal = "\n".join([f"line {i}" for i in range(50)])
    compressed = compress_tool_output(long_terminal, output_type="terminal")
    print(f"终端压缩 ({len(compressed)} chars):")
    print(compressed[:200])
    print()

    search_result = "\n".join([f"{i}: result_{i}" for i in range(30)])
    compressed = compress_tool_output(search_result, output_type="search")
    print(f"搜索压缩 ({len(compressed)} chars):")
    print(compressed[:200])
