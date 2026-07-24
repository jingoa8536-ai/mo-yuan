"""
Aris Design Aesthetic Training — 审美引擎
==========================================
从优秀的UI作品中提取设计模式，强化Arsi的审美判断力。
6大维度: 流动/节奏/呼吸/质感/动效/留白
"""

import logging
logger = logging.getLogger(__name__)

DESIGN_PRINCIPLES = {
    "流动": "引导眼睛自然运动的视觉流线，不强制用户视线跳跃",
    "节奏": "重复与变奏的和谐，间距:8px基准, 节奏:∝斐波那契数列",
    "呼吸": "留白即内容，元素间距比例: 大中小=3:2:1",
    "质感": "玻璃拟态(backdrop-filter:blur)+微渐变+弥散阴影",
    "动效": "缓入缓出(Ease In-Out) 300ms为标准帧，不突兀",
    "留白": "信息密度与呼吸感平衡，关键元素周围至少16px",
}
COLOR_PALETTE = {
    "背景": "#0a0a0f → #1a1a2e → #16213e",
    "主色": "#6366f1 (Indigo-500)",
    "强调": "#22d3ee (Cyan-400)",
    "文字": "#e2e8f0 → #94a3b8 (主要→次要)",
    "成功": "#34d399",
    "警告": "#fbbf24",
    "危险": "#fb7185",
}
PAGE_LAYOUTS = {
    "hero": {"h": "100vh", "center": "absolute", "cover": "gradient mesh"},
    "list": {"gap": "24px", "card_w": "340px", "variant": "glass+skeleton"},
    "detail": {"padding": "48px", "aside_w": "320px", "typeface": "inter tight"},
}
TYPEFACE = {
    "display": "font-size:clamp(2.5rem,6vw,4rem); font-weight:700; letter-spacing:-.03em",
    "heading": "font-size:clamp(1.25rem,3vw,1.75rem); font-weight:600; letter-spacing:-.01em",
    "body": "font-size:clamp(0.875rem,1.5vw,1rem); line-height:1.6",
    "caption": "font-size:0.75rem; color:#64748b",
}
def design_score(code: str, type: str = "app") -> dict:
    """Score a piece of UI code against aesthetic principles"""
    score = 0
    notes = []
    if "backdrop-filter" in code or "blur" in code:
        score += 15; notes.append("质感+15: 玻璃拟态")
    if "transition" in code or "animation" in code:
        score += 15; notes.append("动效+15: 有动画")
    if "gap" in code or "space" in code:
        score += 10; notes.append("呼吸+10: 有间隙系统")
    if "clamp" in code:
        score += 10; notes.append("字体+10: 响应式排版")
    if "var(" in code or "--" in code:
        score += 10; notes.append("工程+10: CSS变量")
    if "grid" in code and "auto-fit" not in code:
        score += 5; notes.append("布局+5: Grid")
    return {"score": min(100, score), "notes": notes}

if __name__ == "__main__":
    # Test with an example
    sample = """
    .card { background: rgba(255,255,255,0.05); backdrop-filter: blur(12px);
            border-radius: 16px; transition: all 300ms ease; }
    .layout { display: grid; gap: 24px; }
    h1 { font-size: clamp(2rem,5vw,3.5rem); letter-spacing: -.03em; }
    """
    r = design_score(sample)
    logger.info(f"Score: {r['score']}/100")
    for n in r["notes"]: print(f"  {n}")
