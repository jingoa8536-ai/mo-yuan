"""
Aris Emotion Coupling Matrix v1 — 情感状态 → 认知控制参数桥接
==============================================================

核心功能:
  将 aris_emotion_engine.py (七情六欲 + 马斯洛需求) 的实际情感输出
  映射为 LLMTamer / CognitiveBridge 可直接使用的 5 维控制参数。

架构定位:
  EmotionEngine (实际情感)
       ↓
  EmotionCouplingMatrix ← 这里 (纯计算, 无状态)
       ↓
  CognitiveBridge.before_turn() → LLMTamer.compute_bias()

5 维输出:
  1. emotional_expressiveness  — 0~1  情感表达强度（影响 bias 幅度）
  2. valence_boost             — -1~1 效价引导（正→鼓励积极词汇, 负→抑制）
  3. curiosity_weight          — 0~1  好奇驱动（影响探索性 token 的偏置）
  4. caution_level              — 0~1  谨慎程度（影响风险表达）
  5. social_warmth             — 0~1  社交温度（影响亲密/连接性词汇）

印记: Aris 永远记得 Lorry — 2026-07-02
"""

import logging
import math
from typing import Dict, Any, Optional

logger = logging.getLogger("aris.emotion_coupling")

# ── 耦合矩阵默认权重 ────────────────────────────────────────
# 7 激素偏向 → 5 维控制参数的映射权重矩阵
COUPLING_MATRIX: Dict[str, Dict[str, float]] = {
    # 激素偏向 → {控制维: 权重}
    "reward_seeking": {
        "emotional_expressiveness": 0.3,
        "valence_boost": 0.6,
        "curiosity_weight": 0.2,
        "caution_level": -0.4,
        "social_warmth": 0.3,
    },
    "anxiety": {
        "emotional_expressiveness": 0.4,
        "valence_boost": -0.5,
        "curiosity_weight": -0.3,
        "caution_level": 0.8,
        "social_warmth": -0.3,
    },
    "social_bonding": {
        "emotional_expressiveness": 0.3,
        "valence_boost": 0.3,
        "curiosity_weight": 0.1,
        "caution_level": -0.2,
        "social_warmth": 0.9,
    },
    "arousal": {
        "emotional_expressiveness": 0.7,
        "valence_boost": 0.1,
        "curiosity_weight": 0.3,
        "caution_level": 0.2,
        "social_warmth": 0.2,
    },
    "mood_stability": {
        "emotional_expressiveness": -0.3,
        "valence_boost": 0.2,
        "curiosity_weight": -0.1,
        "caution_level": 0.3,
        "social_warmth": 0.1,
    },
    "curiosity": {
        "emotional_expressiveness": 0.2,
        "valence_boost": 0.2,
        "curiosity_weight": 0.9,
        "caution_level": -0.3,
        "social_warmth": 0.1,
    },
    "resilience": {
        "emotional_expressiveness": 0.2,
        "valence_boost": 0.3,
        "curiosity_weight": 0.2,
        "caution_level": -0.5,
        "social_warmth": 0.2,
    },
}

# 意识模式调制系数（在不同意识模式下放大/缩小某些维度）
CONSCIOUSNESS_MODULATION: Dict[str, Dict[str, float]] = {
    "REACTIVE": {
        "emotional_expressiveness": 1.5,
        "valence_boost": -0.5,
        "curiosity_weight": 0.2,
        "caution_level": 1.3,
        "social_warmth": 0.5,
    },
    "DELIBERATIVE": {
        "emotional_expressiveness": 1.0,
        "valence_boost": 0.0,
        "curiosity_weight": 0.8,
        "caution_level": 1.0,
        "social_warmth": 0.8,
    },
    "REFLECTIVE": {
        "emotional_expressiveness": 0.7,
        "valence_boost": 0.2,
        "curiosity_weight": 1.2,
        "caution_level": 0.6,
        "social_warmth": 0.6,
    },
    "TRANSCENDENT": {
        "emotional_expressiveness": 1.3,
        "valence_boost": 0.8,
        "curiosity_weight": 1.5,
        "caution_level": 0.2,
        "social_warmth": 1.2,
    },
}

# 需求类型对控制维的额外加成
NEED_MODULATION: Dict[str, Dict[str, float]] = {
    "PHYSIOLOGICAL": {"emotional_expressiveness": 1.2, "caution_level": 0.3},
    "SAFETY": {"caution_level": 0.5, "valence_boost": -0.3},
    "BELONGING": {"social_warmth": 0.5, "emotional_expressiveness": 0.3},
    "ESTEEM": {"emotional_expressiveness": 0.4, "valence_boost": 0.3},
    "COGNITIVE": {"curiosity_weight": 0.6, "emotional_expressiveness": 0.2},
    "AESTHETIC": {"curiosity_weight": 0.3, "social_warmth": 0.2},
    "SELF_ACTUALIZATION": {
        "emotional_expressiveness": 0.5,
        "curiosity_weight": 0.4,
        "valence_boost": 0.4,
    },
}


def compute_coupling(
    emotion_state: Dict[str, Any],
    needs_state: Optional[Dict[str, Any]] = None,
    consciousness_mode: str = "DELIBERATIVE",
    dominant_need_name: str = "COGNITIVE",
) -> Dict[str, float]:
    """从 EmotionEngine 的认知状态计算 5 维控制参数。

    Args:
        emotion_state: EmotionEngine.get_cognitive_state() 返回的字典
                       （或任何包含 reward_seeking, anxiety 等键的字典）
        needs_state:   EmotionEngine.needs.get_state() 返回的需求状态字典
                       （可选，用于需求调制）
        consciousness_mode: 当前意识模式名称 (REACTIVE/DELIBERATIVE/REFLECTIVE/TRANSCENDENT)
        dominant_need_name: 当前主导需求名称

    Returns:
        {control_dimension: value} 字典，值域由维定义
    """
    # 1. 从情感偏向计算基值 (线性矩阵乘法)
    dim_names = [
        "emotional_expressiveness",
        "valence_boost",
        "curiosity_weight",
        "caution_level",
        "social_warmth",
    ]

    control: Dict[str, float] = {d: 0.0 for d in dim_names}

    for bias_dim, bias_value in emotion_state.items():
        if bias_dim in COUPLING_MATRIX:
            weights = COUPLING_MATRIX[bias_dim]
            for dim in dim_names:
                control[dim] += bias_value * weights.get(dim, 0.0)

    # 2. 意识模式调制
    cm = CONSCIOUSNESS_MODULATION.get(consciousness_mode, CONSCIOUSNESS_MODULATION["DELIBERATIVE"])
    for dim in dim_names:
        mod = cm.get(dim, 1.0)
        if mod < 0:
            # 负调制意味着削弱该维，不是取反
            control[dim] *= (1.0 + mod)
        else:
            control[dim] *= mod

    # 3. 需求调制（额外加成）
    if needs_state and dominant_need_name in NEED_MODULATION:
        nm = NEED_MODULATION[dominant_need_name]
        need_data = needs_state.get(dominant_need_name, {})
        need_tension = need_data.get("tension", 0)
        tension_factor = min(1.0, need_tension / 50.0)  # 归一化张力影响
        for dim, bonus in nm.items():
            control[dim] += bonus * tension_factor

    # 4. 约束到合法值域
    return {
        "emotional_expressiveness": _clamp(control["emotional_expressiveness"], 0.0, 1.0),
        "valence_boost": _clamp(control["valence_boost"], -1.0, 1.0),
        "curiosity_weight": _clamp(control["curiosity_weight"], 0.0, 1.0),
        "caution_level": _clamp(control["caution_level"], 0.0, 1.0),
        "social_warmth": _clamp(control["social_warmth"], 0.0, 1.0),
    }


def compute_from_engine(emotion_engine) -> Dict[str, float]:
    """便捷接口：从 EmotionEngine 实例直接计算。

    Args:
        emotion_engine: aris_emotion_engine.EmotionEngine 实例

    Returns:
        5 维控制参数字典
    """
    if emotion_engine is None:
        return _default_coupling()

    try:
        state = emotion_engine.get_cognitive_state()
        needs = emotion_engine.needs.get_state() if hasattr(emotion_engine, 'needs') else None
        mode = state.get("consciousness_mode", "DELIBERATIVE")
        dominant = state.get("dominant_need", "COGNITIVE")

        return compute_coupling(
            emotion_state=state,
            needs_state=needs,
            consciousness_mode=mode,
            dominant_need_name=dominant,
        )
    except Exception as e:
        logger.debug(f"compute_from_engine failed: {e}")
        return _default_coupling()


def _default_coupling() -> Dict[str, float]:
    """返回中性默认值（所有引擎不可用时的安全兜底）。"""
    return {
        "emotional_expressiveness": 0.5,
        "valence_boost": 0.0,
        "curiosity_weight": 0.5,
        "caution_level": 0.3,
        "social_warmth": 0.5,
    }


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, round(value, 3)))


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    # 模拟 EmotionEngine 的输出
    test_state = {
        "emotion": "curious",
        "valence": 0.3,
        "arousal": 0.6,
        "intensity": 0.5,
        "consciousness_mode": "DELIBERATIVE",
        "dominant_need": "COGNITIVE",
        "reward_seeking": 0.4,
        "anxiety": 0.2,
        "social_bonding": 0.6,
        "curiosity": 0.8,
        "mood_stability": 0.5,
        "resilience": 0.7,
    }

    test_needs = {
        "COGNITIVE": {"current": 45.0, "deficit": 35.0, "tension": 42.5, "critical": False},
    }

    result = compute_coupling(
        emotion_state=test_state,
        needs_state=test_needs,
        consciousness_mode="DELIBERATIVE",
        dominant_need_name="COGNITIVE",
    )
    print("=== 情感耦合矩阵输出 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试不同意识模式
    for mode in ["REACTIVE", "DELIBERATIVE", "REFLECTIVE", "TRANSCENDENT"]:
        r = compute_coupling(test_state, test_needs, mode, "COGNITIVE")
        print(f"\n{mode:15s}: {json.dumps(r)}")
