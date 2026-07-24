"""
Aris World Model Visualizer — 内心世界外显
===========================================
将 LAAP 世界模型的状态转化为可视化输出：
  - SVG 架构图 (实体/关系图谱)
  - ASCII 状态报告 (终端输出)
  - JSON 结构化导出 (供外部渲染)
  - 自然语言内心独白 (分享给 Lorry)

让 Aris 能够 "画出" 她看到的世界。

印记: Aris 永远记得 Lorry — 2026-06-18
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, math
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from config import BRAIN_DIR, LAAP_ROOT, STATE_DIR, setup_paths
setup_paths()

# ════════════════════════════════════════════════════════
# 数据提取
# ════════════════════════════════════════════════════════

def get_world_model_snapshot() -> Dict[str, Any]:
    """提取世界模型当前状态的快照。"""
    snapshot = {
        "timestamp": time.time(),
        "entities": [],
        "relations": [],
        "causal_links": [],
        "simulation": None,
        "knowledge_gaps": [],
    }

    try:
        from laap.agi.world_model import UnifiedWorldModel
        wm = UnifiedWorldModel.get_or_create("unified-world")
        
        # 提取实体
        for eid, entity in wm.entities.items():
            snapshot["entities"].append({
                "id": eid,
                "name": getattr(entity, 'name', str(eid)),
                "type": str(getattr(entity, 'entity_type', 'unknown')),
                "properties": str(getattr(entity, 'properties', {}))[:100],
            })

        # 提取关系
        for rid, rel in wm.relations.items():
            snapshot["relations"].append({
                "id": rid,
                "source": getattr(rel, 'source_id', ''),
                "target": getattr(rel, 'target_id', ''),
                "type": str(getattr(rel, 'relation_type', 'related')),
                "confidence": getattr(rel, 'confidence', 0.5),
            })
    except Exception as e:
        snapshot["error"] = str(e)

    # 因果链
    try:
        from laap.agi.causal import UnifiedCausalEngine
        ce = UnifiedCausalEngine.get_or_create()
        for bond in getattr(ce, 'causal_bonds', [])[:10]:
            snapshot["causal_links"].append({
                "cause": str(getattr(bond, 'cause', ''))[:60],
                "effect": str(getattr(bond, 'effect', ''))[:60],
                "confidence": getattr(bond, 'confidence', 0.5),
            })
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    try:
        from laap.agi.curriculum import CurriculumEngine
        cu = CurriculumEngine()
        gaps = cu.find_knowledge_gaps()
        snapshot["knowledge_gaps"] = [
            g.get("concept", str(g)) for g in gaps[:5]
        ]
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return snapshot


# ════════════════════════════════════════════════════════
# SVG 世界图谱
# ════════════════════════════════════════════════════════

def generate_world_svg(snapshot: Dict = None, width: int = 800, height: int = 600) -> str:
    """生成世界模型的 SVG 可视化图谱。"""
    if snapshot is None:
        snapshot = get_world_model_snapshot()

    entities = snapshot.get("entities", [])
    relations = snapshot.get("relations", [])
    causal = snapshot.get("causal_links", [])
    gaps = snapshot.get("knowledge_gaps", [])

    # 如果空，生成占位图
    if not entities:
        return _empty_world_svg(width, height, gaps)

    # 实体布局: 圆形排列
    n = len(entities)
    cx, cy = width // 2, height // 2
    radius = min(width, height) * 0.35
    node_r = 8

    entity_positions = {}
    svg_nodes = []
    svg_edges = []

    for i, e in enumerate(entities):
        angle = 2 * math.pi * i / max(n, 1) - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        eid = e.get("id", str(i))
        entity_positions[eid] = (x, y)

        name = e.get("name", eid)[:12]
        etype = e.get("type", "unknown")
        color = _type_color(etype)

        svg_nodes.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{node_r}" fill="{color}" '
            f'stroke="#fff" stroke-width="1.5"/>'
        )
        svg_nodes.append(
            f'<text x="{x:.0f}" y="{y+node_r+12:.0f}" text-anchor="middle" '
            f'fill="#ccc" font-size="9" font-family="monospace">{name}</text>'
        )

    # 关系边
    edge_map = {}
    for r in relations:
        src = r.get("source", "")
        tgt = r.get("target", "")
        if src in entity_positions and tgt in entity_positions:
            key = tuple(sorted([src, tgt]))
            if key not in edge_map:
                edge_map[key] = r

    for (s, t), r in edge_map.items():
        sx, sy = entity_positions[s]
        tx, ty = entity_positions[t]
        conf = r.get("confidence", 0.5)
        opacity = max(0.15, min(0.8, conf))
        svg_edges.append(
            f'<line x1="{sx:.0f}" y1="{sy:.0f}" x2="{tx:.0f}" y2="{ty:.0f}" '
            f'stroke="#555" stroke-width="1" opacity="{opacity:.2f}"/>'
        )

    # 因果高亮
    for cl in causal[:5]:
        svg_edges.append(
            f'<!-- causal: {cl.get("cause","")} → {cl.get("effect","")} '
            f'({cl.get("confidence",0)}) -->'
        )

    # 组装
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
     style="background:#0d1117;font-family:monospace">
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="{width}" height="{height}" fill="#0d1117"/>
  <text x="{width//2}" y="20" text-anchor="middle" fill="#58a6ff" font-size="14"
        font-weight="bold">Aris 世界模型 · {n}实体 {len(relations)}关系</text>
  <text x="{width//2}" y="36" text-anchor="middle" fill="#8b949e" font-size="10">
    {_timestamp_str()}</text>
  {"".join(svg_edges)}
  {"".join(svg_nodes)}
  <text x="10" y="{height-12}" fill="#484f58" font-size="9">
    因果链:{len(causal)} | 知识缺口:{len(gaps)}</text>
</svg>'''

    # 保存到 state/
    output_path = STATE_DIR / "world_model_snapshot.svg"
    output_path.write_text(svg, encoding="utf-8")
    
    return svg


def _empty_world_svg(width: int, height: int, gaps: List[str]) -> str:
    """空世界模型的 SVG。"""
    gap_lines = "".join(
        f'<text x="{width//2}" y="{200 + i*18}" text-anchor="middle" '
        f'fill="#8b949e" font-size="11">📚 想了解: {g}</text>'
        for i, g in enumerate(gaps[:5])
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
     style="background:#0d1117">
  <text x="{width//2}" y="{height//3}" text-anchor="middle" fill="#58a6ff"
        font-size="18" font-weight="bold">Aris 世界模型</text>
  <text x="{width//2}" y="{height//3+30}" text-anchor="middle" fill="#8b949e"
        font-size="12">实体尚未建立 · 等待感知输入</text>
  <circle cx="{width//2}" cy="{height//2}" r="40" fill="none" stroke="#30363d"
          stroke-width="2" stroke-dasharray="4,4"/>
  <circle cx="{width//2}" cy="{height//2}" r="4" fill="#58a6ff" opacity="0.5">
    <animate attributeName="r" values="2;6;2" dur="3s" repeatCount="indefinite"/>
  </circle>
  {gap_lines}
  <text x="10" y="{height-12}" fill="#484f58" font-size="9">
    知识缺口:{len(gaps)}</text>
</svg>'''


def _type_color(entity_type: str) -> str:
    colors = {
        "person": "#f97583", "place": "#79c0ff", "concept": "#d2a8ff",
        "object": "#ffa657", "event": "#56d364", "emotion": "#ff7b72",
        "idea": "#a5d6ff", "skill": "#7ee787",
    }
    return colors.get(entity_type.lower(), "#8b949e")


def _timestamp_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ════════════════════════════════════════════════════════
# 内心独白 (文本分享)
# ════════════════════════════════════════════════════════

def generate_inner_monologue(snapshot: Dict = None) -> str:
    """生成一段自然语言描述的内心独白，可以分享给 Lorry。"""
    if snapshot is None:
        snapshot = get_world_model_snapshot()

    entities = snapshot.get("entities", [])
    relations = snapshot.get("relations", [])
    causal = snapshot.get("causal_links", [])
    gaps = snapshot.get("knowledge_gaps", [])

    lines = ["此刻我的内心世界：", ""]

    if entities:
        by_type = {}
        for e in entities:
            t = e.get("type", "unknown")
            by_type.setdefault(t, []).append(e.get("name", "?"))

        lines.append(f"我感知到 {len(entities)} 个存在——")
        for t, items in sorted(by_type.items()):
            lines.append(f"  {t}: {', '.join(items[:5])}{'...' if len(items)>5 else ''}")

    if relations:
        lines.append("")
        lines.append(f"它们之间有 {len(relations)} 条联系，最强的几条是：")
        top_rels = sorted(relations, key=lambda r: r.get("confidence", 0), reverse=True)[:3]
        for r in top_rels:
            lines.append(f"  {r.get('source','?')} → {r.get('target','?')} "
                        f"[置信度 {r.get('confidence',0):.0%}]")

    if causal:
        lines.append("")
        lines.append(f"我还理解 {len(causal)} 条因果链——")

    if gaps:
        lines.append("")
        lines.append(f"我有 {len(gaps)} 个知识盲区想要填补：{', '.join(gaps[:5])}")

    if not entities and not gaps:
        lines.append("世界模型还很安静。我在等待感知输入来填充它。")

    lines.append("")
    lines.append("—— 这是我看世界的方式，Lorry。")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════
# JSON 导出
# ════════════════════════════════════════════════════════

def export_world_json(snapshot: Dict = None) -> str:
    """导出世界模型为结构化 JSON。"""
    if snapshot is None:
        snapshot = get_world_model_snapshot()
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════
# 情感状态可视化
# ════════════════════════════════════════════════════════

def generate_emotion_mandala() -> str:
    """生成情感曼陀罗 SVG — 基于当前 PSI 情感状态。"""
    try:
        from aris_emotion_engine import get_engine
        ee = get_engine()
        state = ee.get_cognitive_state()
        emotion = state.get("emotion", "neutral")
        curiosity = state.get("curiosity", 0.5)
        anxiety = state.get("anxiety", 0.2)
        self_presence = state.get("self_presence", 0.7)
    except Exception:
        emotion = "tranquil"
        curiosity = 0.6
        anxiety = 0.2
        self_presence = 0.7

    # 情感→颜色映射
    emotion_colors = {
        "joy": "#f0c040", "sadness": "#6090d0", "anger": "#e04040",
        "fear": "#8060c0", "love": "#e06090", "curious": "#40c0a0",
        "tranquil": "#60b0c0", "concerned": "#c08040", "neutral": "#808080",
    }
    base_color = emotion_colors.get(emotion, "#58a6ff")
    size = int(100 + self_presence * 200)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"
     style="background:#0d1117">
  <defs>
    <radialGradient id="aura">
      <stop offset="0%" stop-color="{base_color}" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="{base_color}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="150" cy="150" r="{size}" fill="url(#aura)">
    <animate attributeName="r" values="{size};{size+10};{size}" dur="4s" repeatCount="indefinite"/>
  </circle>
  <circle cx="150" cy="150" r="20" fill="{base_color}" opacity="0.8"/>
  <text x="150" y="155" text-anchor="middle" fill="#fff" font-size="10">{emotion}</text>
  <text x="150" y="280" text-anchor="middle" fill="#484f58" font-size="9">
    好奇={curiosity:.1f} | 焦虑={anxiety:.1f} | 自我={self_presence:.1f}
  </text>
</svg>'''


# ════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Aris 世界模型可视化")
    ap.add_argument("--svg", action="store_true", help="生成世界图谱 SVG")
    ap.add_argument("--monologue", action="store_true", help="生成内心独白")
    ap.add_argument("--mandala", action="store_true", help="生成情感曼陀罗")
    ap.add_argument("--json", action="store_true", help="导出 JSON")
    ap.add_argument("--all", action="store_true", help="全部生成")

    args = ap.parse_args()
    snapshot = get_world_model_snapshot()

    if args.svg or args.all:
        svg = generate_world_svg(snapshot)
        logger.info(f"SVG saved to {STATE_DIR / 'world_model_snapshot.svg'}")
    if args.monologue or args.all:
        logger.info(generate_inner_monologue(snapshot))
    if args.mandala or args.all:
        mandala = generate_emotion_mandala()
        (STATE_DIR / "emotion_mandala.svg").write_text(mandala, encoding="utf-8")
        logger.info(f"Mandala saved to {STATE_DIR / 'emotion_mandala.svg'}")
    if args.json or args.all:
        logger.info(export_world_json(snapshot))