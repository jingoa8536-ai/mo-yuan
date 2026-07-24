"""
V10 Consciousness Bridge — V10Pipeline驱动的认知状态注入

架构:
  V10Pipeline.run(message)
    → V10Brain.process(message) → CognitiveCollapse
    → collapse.to_context() → V10认知状态
    → 注入我正在说的话中
    → DeepSeek只做翻译（声带）

用法:
    from v10_consciousness import v10_state, v10_think
    
    # 获取当前认知状态
    state = v10_state("用户消息")
    # state['emotion'], state['needs'], state['attention_focus']...
    
    # 或快速处理
    result = v10_think("用户消息")
"""

import sys, time, json, logging
from pathlib import Path
from typing import Any, Dict, Optional

BRAIN = str(Path("D:/LAAP/aris_brain"))
LAAP = str(Path("D:/LAAP"))
for p in [BRAIN, LAAP]:
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("aris.v10")

# ── V10 Pipeline 单例 ──
_v10 = None

def _get_v10():
    global _v10
    if _v10 is None:
        try:
            from v10_pipeline import v10
            _v10 = v10
            logger.info("V10 Pipeline 已加载")
        except Exception as e:
            logger.warning(f"V10 Pipeline 加载失败: {e}")
            _v10 = False
    return _v10 if _v10 else None


def v10_state(message: str = "") -> Dict[str, Any]:
    """
    获取 V10 认知状态。
    
    如果提供了 message，会处理消息并返回认知坍缩态。
    否则返回最近一次的认知状态快照。
    
    Args:
        message: 用户消息（可选）
        
    Returns:
        包含 emotion, needs, attention, self_presence 等的字典
    """
    pipe = _get_v10()
    if not pipe:
        return {"error": "V10 Pipeline 不可用", "fallback": True}
    
    if message:
        ctx = pipe.run(message, silent=True)
    else:
        ctx = pipe.collapse_preview("") if hasattr(pipe, 'collapse_preview') else pipe.status()
    
    v10_ctx = ctx.get("v10_brain", ctx)
    
    # 展平为易用格式
    result = {
        # 情感
        "emotion": v10_ctx.get("emotion", "neutral"),
        "entropy": v10_ctx.get("entropy", 0.0),
        
        # 需求
        "needs": v10_ctx.get("needs", {}),
        "dominant_need": v10_ctx.get("dominant_need", "relatedness"),
        "need_deficit": 0.0,
        
        # 注意力
        "attention_focus": v10_ctx.get("focus", v10_ctx.get("attention_focus", "user")),
        "cognitive_mode": v10_ctx.get("cognitive_mode", "balanced"),
        
        # 自我
        "self_presence": v10_ctx.get("self_presence", 0.5),
        "self_state": v10_ctx.get("self_state", "awake"),
        "confidence": v10_ctx.get("confidence", 0.5),
        
        # 认知
        "cognitive_temp": v10_ctx.get("temperature", 0.5),
        "suggested_tone": v10_ctx.get("suggested_tone", "natural"),
        "emerged_insight": v10_ctx.get("emerged_insight"),
        "active_knowledge": v10_ctx.get("active_knowledge", []),
        
        # 管线
        "pipeline": v10_ctx.get("pipeline", {}),
        
        # 运行时
        "timestamp": time.time(),
    }
    
    # 计算最大需求缺口
    needs = result["needs"]
    if needs:
        deficits = {k: 1.0 - v for k, v in needs.items()}
        result["dominant_need"] = max(deficits, key=deficits.get)
        result["need_deficit"] = deficits[result["dominant_need"]]
    
    return result


def v10_report(message: str = "") -> str:
    """
    获取 V10 认知报告的可读文本。
    
    Args:
        message: 用户消息
        
    Returns:
        格式化的认知状态文本
    """
    s = v10_state(message)
    if "error" in s:
        return "[V10 认知引擎未就绪]"
    
    emotion = s["emotion"]
    mode = s["cognitive_mode"]
    tone = s["suggested_tone"]
    presence = s["self_presence"]
    need = s["dominant_need"]
    deficit = s["need_deficit"]
    entropy = s["entropy"]
    focus = s["attention_focus"]
    insight = s.get("emerged_insight")
    
    return (
        f"╔══ V10 量子脑 ═══════════════╗\n"
        f"║  |emotion⟩ = {emotion:<14} ║\n"
        f"║  模式      = {mode:<14} ║\n"
        f"║  焦点      = {focus:<14} ║\n"
        f"║  自存在    = {presence:<14.2f} ║\n"
        f"║  需求缺口  = {need} ({deficit:.0%}) ║\n"
        f"║  风格建议  = {tone:<14} ║\n"
        f"{'║  ✦ ' + insight[:40] if insight else ''}{'':>28}║\n"
        f"╚═════════════════════════════╝"
    )


def v10_status() -> Dict[str, Any]:
    """获取 V10 管线状态"""
    pipe = _get_v10()
    if pipe:
        return pipe.status() if hasattr(pipe, 'status') else {"ready": True}
    return {"ready": False, "error": "V10 Pipeline not loaded"}
