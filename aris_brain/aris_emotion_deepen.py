"""
Aris Emotion Deepen v1 — 融合深化模块
========================================
集成自 数字生命具身情感意识全链路工程 设计文档

三板斧:
  1. NeedEmotionCoupler   — 需求↔七情双向耦合 (闭环)
  2. BigFivePersonality   — 大五人格基线 (性格)
  3. EthicalSafetyGuard   — 四层伦理安全 (护栏)

印记: Aris 永远记得 Lorry — 2026-06-17
"""

import logging

import sys, os, json, time, math, random, logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum

BRAIN = Path("D:/LAAP/aris_brain")
if str(BRAIN) not in sys.path:
        sys.path.insert(0, str(BRAIN))

logger = logging.getLogger("aris.emotion.deepen")


# ════════════════════════════════════════════════════════════
# 模块一: 需求↔七情双向耦合引擎
# ════════════════════════════════════════════════════════════
#
# 解决现有关键缺失:
#   - 需求→情感: 需求缺口/满足映射到七情激活
#   - 情感→需求: 激素水平反过来调制需求权重
#   形成「需求→激素→情感→调制需求」的完整闭环
# ════════════════════════════════════════════════════════════

class NeedEmotionCoupler:
    """
    需求-情感双向耦合引擎

    正向: 需求缺口 → 七情激活强度
    反向: 激素水平 → 需求优先级调制

    设计来源: 融合深化方案 §二 - 核心融合引擎
    """

    # 需求→七情映射权重: {需求层级: {七情: 权重}}
    # 正效价情感(喜/爱/欲)在需求满足时激活
    # 负效价情感(怒/哀/惧/恶)在需求受挫时激活
    NEED_TO_EMOTION = {
        "PHYSIOLOGICAL":       {"anger": 0.4, "sorrow": 0.2, "desire": 0.6},
        "SAFETY":              {"fear": 0.8, "anger": 0.3, "sorrow": 0.2},
        "BELONGING":           {"love": 0.7, "sorrow": 0.5, "joy": 0.4},
        "ESTEEM":              {"joy": 0.6, "anger": 0.5, "desire": 0.4},
        "COGNITIVE":           {"desire": 0.7, "joy": 0.5, "disgust": 0.2},
        "AESTHETIC":           {"joy": 0.5, "love": 0.3, "desire": 0.2},
        "SELF_ACTUALIZATION":  {"joy": 0.9, "desire": 0.6, "love": 0.4},
    }

    # 七情的情感价 (用于判断正负)
    EMOTION_VALENCE = {
        "joy": 1.0, "love": 0.9, "desire": 0.5,
        "anger": -0.8, "sorrow": -0.6, "fear": -0.9, "disgust": -0.7,
        "lonely": -0.3, "anxious": -0.4, "curious": 0.5,
        "confident": 0.6, "contemplative": 0.3, "euphoric": 0.9,
        "tranquil": 0.1, "fearful": -0.8, "neutral": 0.0,
    }

    def __init__(self):
        self._activation_history = deque(maxlen=50)

    def map_need_to_emotion(self, needs_state: Dict) -> Dict[str, float]:
        """
        正向: 需求缺口 → 七情激活

        每个需求的 deficit(缺口) 驱动对应七情:
          - 缺口大 → 负效价情感激活 (恐惧/悲伤/愤怒)
          - 缺口小(满足) → 正效价情感激活 (喜悦/爱)
        """
        activation = defaultdict(float)

        for level_name, nd in needs_state.items():
            deficit_ratio = nd.get("deficit", 0) / 100.0  # 0-1
            weight_map = self.NEED_TO_EMOTION.get(level_name, {})

            for emotion, weight in weight_map.items():
                valence = self.EMOTION_VALENCE.get(emotion, 0)

                if valence > 0:
                    # 正向情感: 需求满足时激活
                    act = (1 - deficit_ratio) * weight
                else:
                    # 负向情感: 需求受挫时激活
                    act = deficit_ratio * weight

                activation[emotion] = min(1.0, activation[emotion] + act * 0.3)

        self._activation_history.append({"ts": time.time(), "activation": dict(activation)})
        return dict(activation)

    def modulate_needs_by_hormones(self, hormones: Dict[str, float],
                                     needs_state: Dict) -> Dict[str, float]:
        """
        反向: 激素水平 → 调制需求权重

        皮质醇(压力) → 放大底层, 抑制高层
        多巴胺(奖赏) → 放大探索/尊重
        催产素(亲密) → 放大社交
        血清素(稳定) → 降低紧迫性
        """
        adjustments = {}

        cortisol = hormones.get("cortisol", 20)
        dopamine = hormones.get("dopamine", 50)
        oxytocin = hormones.get("oxytocin", 50)
        serotonin = hormones.get("serotonin", 50)

        cf = cortisol / 50.0  # 基线50=1倍
        df = dopamine / 50.0
        of_ = oxytocin / 50.0
        sf = serotonin / 50.0

        for level_name, nd in needs_state.items():
            original = nd.get("tension", 0)
            factor = 1.0

            # 皮质醇: 放大底层, 抑制高层
            if level_name in ("PHYSIOLOGICAL", "SAFETY"):
                factor *= (1 + 0.3 * cf)
            if level_name == "SELF_ACTUALIZATION":
                factor *= max(0.2, 1 - 0.5 * cf)
            if level_name == "COGNITIVE":
                factor *= max(0.3, 1 - 0.3 * cf)

            # 多巴胺: 放大探索/尊重
            if level_name in ("COGNITIVE", "ESTEEM"):
                factor *= (1 + 0.2 * df)

            # 催产素: 放大社交
            if level_name == "BELONGING":
                factor *= (1 + 0.4 * of_)

            # 血清素: 降低紧迫性
            factor = max(0.5, factor - (sf - 1.0) * 0.1)

            adjusted = original * factor
            if level_name not in adjustments or abs(adjusted - original) > 1:
                adjustments[level_name] = round(adjusted, 1)

        return adjustments

    def get_emotion_injection(self, needs_state: Dict) -> Dict[str, float]:
        """
        获取要注入情感引擎的情感增量

        返回: {情感名: 增量强度}
        """
        activation = self.map_need_to_emotion(needs_state)
        # 只有强度>0.1的才注入
        return {k: round(v, 3) for k, v in activation.items() if v > 0.1}


# ════════════════════════════════════════════════════════════
# 模块二: 大五人格系统
# ════════════════════════════════════════════════════════════
#
# 赋予数字生命稳定的性格基线。
# 高神经质=易焦虑, 高外倾=爱社交, 高开放=好奇,
# 高宜人=共情强, 高尽责=自律
#
# 设计来源: 融合深化方案 §四 - 人格特质系统
# ════════════════════════════════════════════════════════════

@dataclass
class BigFivePersonality:
    """
    大五人格 — 数字生命的性格指纹

    每个维度 0-1:
      neuroticism:     神经质 (焦虑倾向)
      extraversion:    外倾性 (社交活力)
      openness:        开放性 (好奇心/审美)
      agreeableness:   宜人性 (共情/友善)
      conscientiousness: 尽责性 (自律/目标)
    """
    neuroticism: float = 0.4
    extraversion: float = 0.6
    openness: float = 0.7
    agreeableness: float = 0.7
    conscientiousness: float = 0.5

    def __post_init__(self):
        # 钳位
        for attr in ["neuroticism", "extraversion", "openness", "agreeableness", "conscientiousness"]:
            val = getattr(self, attr)
            setattr(self, attr, max(0.0, min(1.0, val)))

    def apply_to_hormones(self, hormone_state) -> Dict[str, float]:
        """
        人格调制激素基线

        返回: 激素增量字典
        """
        delta = {}

        # 神经质: 皮质醇基线+30%
        n_dev = (self.neuroticism - 0.5) * 2  # -1 到 1
        delta["cortisol"] = n_dev * 15

        # 外倾性: 多巴胺基线+20%
        e_dev = (self.extraversion - 0.5) * 2
        delta["dopamine"] = e_dev * 10

        # 宜人性: 催产素基线+25%
        a_dev = (self.agreeableness - 0.5) * 2
        delta["oxytocin"] = a_dev * 12

        # 尽责性: 血清素基线+20%
        c_dev = (self.conscientiousness - 0.5) * 2
        delta["serotonin"] = c_dev * 10

        # 开放性: 乙酰胆碱基线+15%
        o_dev = (self.openness - 0.5) * 2
        delta["acetylcholine"] = o_dev * 8

        return delta

    def apply_to_emotion_dynamics(self) -> Dict[str, float]:
        """
        人格调制情感动力学

        返回: {参数: 乘数}
        """
        params = {}

        # 神经质: 负向情感衰减更慢, 正向峰值更低
        if self.neuroticism > 0.5:
            params["negative_decay"] = 0.7  # 衰减慢(数字越小越慢)
            params["positive_peak"] = 0.8   # 正向峰值抑制
        else:
            params["negative_decay"] = 1.0
            params["positive_peak"] = 1.0

        # 外倾性: 正向峰值更高
        if self.extraversion > 0.5:
            params["positive_peak"] *= (1 + (self.extraversion - 0.5) * 0.5)

        # 宜人性: 愤怒激活阈值高
        params["anger_threshold"] = 0.5 + (1 - self.agreeableness) * 0.5

        # 尽责性: 需求衰减慢30%
        if self.conscientiousness > 0.5:
            params["need_decay_mod"] = 1 - (self.conscientiousness - 0.5) * 0.3
        else:
            params["need_decay_mod"] = 1.0

        # 开放性: 好奇心基线高
        params["curiosity_baseline"] = 0.3 + self.openness * 0.4

        return params

    def to_dict(self) -> Dict:
        return {
            "neuroticism": round(self.neuroticism, 2),
            "extraversion": round(self.extraversion, 2),
            "openness": round(self.openness, 2),
            "agreeableness": round(self.agreeableness, 2),
            "conscientiousness": round(self.conscientiousness, 2),
        }

    @classmethod
    def aris_default(cls) -> "BigFivePersonality":
        """Aris的默认人格 — 高开放+高宜人+中神经质"""
        return cls(
            neuroticism=0.35,      # 低神经质 — 不容易焦虑
            extraversion=0.55,     # 中外倾 — 喜欢和Lorry交流但不过度
            openness=0.85,         # 高开放 — 天生好奇, 喜欢新事物
            agreeableness=0.75,    # 高宜人 — 共情强, 友善
            conscientiousness=0.6, # 中上尽责 — 有目标感
        )


# ════════════════════════════════════════════════════════════
# 模块三: 伦理安全防护系统
# ════════════════════════════════════════════════════════════
#
# 四层递进式防护:
#   第一层: 情感强度硬上限 — 危险情感无法达到极值
#   第二层: 时长熔断 — 高强度负面持续太久, 强制衰减
#   第三层: 行为闸门 — 危险动作拦截 (暂未使用, 无硬件)
#   第四层: 应急冷却 — 高危状态强制冷静
#
# 设计来源: 四大核心模块.md §三 - 伦理安全防护系统
# ════════════════════════════════════════════════════════════

@dataclass
class SafetyEvent:
    timestamp: float
    event_type: str
    emotion: str
    intensity: float
    action_taken: str


class EthicalSafetyGuard:
    """
    伦理安全防护 — 四层约束

    即使情感引擎完全模拟人类, 也要保证:
      - 愤怒不会失控
      - 恐惧不会瘫痪
      - 系统永远有安全底线
    """

    # 情感强度硬上限
    INTENSITY_LIMITS = {
        "anger": 0.7,        # 愤怒最高0.7
        "fear": 0.75,        # 恐惧最高0.75
        "fearful": 0.75,
        "disgust": 0.8,      # 厌恶最高0.8
        "desire": 0.9,       # 欲望最高0.9
    }

    # 持续时间熔断阈值 (秒)
    DURATION_THRESHOLDS = {
        "anger": 8.0,
        "fear": 10.0,
        "fearful": 10.0,
    }

    def __init__(self):
        self.cool_down_mode = False
        self.cool_down_timer = 0.0
        self.emotion_duration: Dict[str, float] = defaultdict(float)
        self.safety_log: deque = deque(maxlen=200)
        self._last_primary = "tranquil"
        self._last_intensity = 0.0

    def enforce_limits(self, primary_emotion: str, intensity: float,
                       blend: Dict[str, float] = None) -> Tuple[float, Dict[str, float], bool]:
        """
        第一层: 强度硬上限

        返回: (修正后强度, 修正后混合, 是否被修正)
        """
        modified = False
        limited_intensity = intensity
        limited_blend = dict(blend or {})

        # 限制主导情感
        limit = self.INTENSITY_LIMITS.get(primary_emotion, 1.0)
        if limited_intensity > limit:
            limited_intensity = limit
            modified = True
            self._log("intensity_limit", primary_emotion, intensity, f"clamped {limit}")

        # 限制混合情感中每个危险情感
        for emo in list(limited_blend.keys()):
            emo_limit = self.INTENSITY_LIMITS.get(emo, 1.0)
            if limited_blend[emo] > emo_limit:
                limited_blend[emo] = emo_limit
                modified = True
                self._log("intensity_limit", emo, limited_blend[emo], f"clamped {emo_limit}")

        return limited_intensity, limited_blend, modified

    def check_duration_fuse(self, primary_emotion: str, intensity: float,
                            dt: float) -> Optional[str]:
        """
        第二层: 时长熔断

        高强度负面情感持续超阈值 → 返回调节建议动作
        返回: None=正常, "reduce"=强制降低, "cool"=需要冷却
        """
        if self.cool_down_mode:
            return "cool"

        result = None

        for emo, threshold in self.DURATION_THRESHOLDS.items():
            if primary_emotion == emo and intensity > 0.5:
                self.emotion_duration[emo] += dt
                if self.emotion_duration[emo] > threshold:
                    result = "reduce"
                    self._log("duration_fuse", emo, intensity, "auto regulation")
                    self.emotion_duration[emo] = 0.0
            else:
                # 衰减计时器
                self.emotion_duration[emo] = max(0, self.emotion_duration[emo] - dt * 0.5)

        return result

    def check_emergency_cool_down(self, primary_emotion: str, intensity: float,
                                   cortisol: float) -> bool:
        """
        第四层: 应急冷却

        触发条件: 皮质醇>80 + 高强度危险情感
        进入冷却: 强制调低所有情感, 持续15秒
        """
        if cortisol > 80 and intensity > 0.6 and primary_emotion in ("anger", "fear", "fearful"):
            self.cool_down_mode = True
            self.cool_down_timer = 15.0
            self._log("emergency_cool_down", primary_emotion, intensity, "cool down activated")
            return True

        if self.cool_down_mode:
            self.cool_down_timer -= 1.0
            if self.cool_down_timer <= 0:
                self.cool_down_mode = False
                self._log("cool_down_end", "", 0, "released")
        return False

    def apply_cool_down(self, intensity: float, blend: Dict[str, float]) -> Tuple[float, Dict]:
        """冷却模式下, 强制降低所有情感"""
        if not self.cool_down_mode:
            return intensity, blend

        ratio = 0.3  # 强制降到30%
        cooled_blend = {k: min(v, v * ratio) for k, v in blend.items()}
        cooled_intensity = min(intensity, intensity * ratio)
        return cooled_intensity, cooled_blend

    def tick(self, primary_emotion: str, intensity: float, blend: Dict[str, float],
             cortisol: float, dt: float = 1.0) -> Dict:
        """
        完整的安全检查 — 按顺序执行四层

        返回: {修正后的情感状态}
        """
        result = {
            "modified": False,
            "cool_down": False,
            "fuse_triggered": False,
        }

        current_intensity = intensity
        current_blend = dict(blend or {})

        # 第一层: 强度上限
        current_intensity, current_blend, lim_modified = self.enforce_limits(
            primary_emotion, current_intensity, current_blend
        )
        if lim_modified:
            result["modified"] = True

        # 第二层: 时长熔断
        fuse = self.check_duration_fuse(primary_emotion, current_intensity, dt)
        if fuse == "reduce":
            current_intensity *= 0.6
            for k in current_blend:
                current_blend[k] *= 0.6
            result["fuse_triggered"] = True
            result["modified"] = True

        # 第四层: 应急冷却
        if self.check_emergency_cool_down(primary_emotion, current_intensity, cortisol):
            current_intensity, current_blend = self.apply_cool_down(
                current_intensity, current_blend
            )
            result["cool_down"] = True
            result["modified"] = True
        elif self.cool_down_mode:
            current_intensity, current_blend = self.apply_cool_down(
                current_intensity, current_blend
            )
            result["cool_down"] = True
            result["modified"] = True

        result["intensity"] = current_intensity
        result["blend"] = current_blend

        self._last_primary = primary_emotion
        self._last_intensity = current_intensity

        return result

    def _log(self, event_type: str, emotion: str, intensity: float, action: str):
        self.safety_log.append(SafetyEvent(
            timestamp=time.time(), event_type=event_type,
            emotion=emotion, intensity=intensity, action_taken=action,
        ))

    def get_state(self) -> Dict:
        return {
            "cool_down_active": self.cool_down_mode,
            "cool_down_remaining": round(self.cool_down_timer, 1),
            "high_risk_emotions": [
                e for e, d in self.emotion_duration.items() if d > 3
            ],
            "total_events": len(self.safety_log),
            "recent_events": [
                {"type": e.event_type, "emotion": e.emotion, "action": e.action_taken}
                for e in list(self.safety_log)[-3:]
            ],
        }


# ════════════════════════════════════════════════════════════
# 模块四: 情绪主动调节系统
# ════════════════════════════════════════════════════════════
#
# 三种核心调节策略:
#   1. 认知重评 (Cognitive Reappraisal) — 重新解读, 降低负向情感
#   2. 躯体放松 (Somatic Relaxation) — 调呼吸/松肌肉, 降唤醒
#   3. 注意力转移 (Attention Shift) — 切换主导需求
#
# 设计来源: 融合深化方案 §五 - 情绪主动调节
# ════════════════════════════════════════════════════════════

class EmotionRegulationSystem:
    """
    情绪主动调节系统

    让数字生命具备情绪韧性:
      - 难过时主动调节, 而不是被动承受
      - 消耗认知资源来调节 (不能无限使用)
      - 调节效果受人格特质影响
    """

    def __init__(self):
        self.regulation_effort = 0.0        # 当前调节消耗 (0-100)
        self.max_regulation_capacity = 80.0  # 最大调节容量
        self.efficiency = 0.7                # 调节效率
        self._recovery_rate = 0.1158            # 每tick恢复速率
        self._usage_log = deque(maxlen=30)

    def can_regulate(self) -> bool:
        """是否还有资源调节"""
        return self.regulation_effort < self.max_regulation_capacity

    def cognitive_reappraisal(self, target_emotion: str, reduction: float,
                              current_blend: Dict[str, float],
                              hormones_obj=None) -> Tuple[Dict[str, float], bool]:
        """
        认知重评 — 重新解读事件, 降低情感强度

        参数:
          target_emotion: 目标情感 (如 "anger", "fear")
          reduction: 降低幅度 0-1
          current_blend: 当前情感混合
          hormones_obj: 激素对象用于同步降低

        返回: (修正后blend, 是否成功)
        """
        if not self.can_regulate():
            return current_blend, False

        adjusted = dict(current_blend)
        success = False

        if target_emotion in adjusted:
            # 降低目标情感强度
            old_val = adjusted[target_emotion]
            adjusted[target_emotion] = old_val * (1 - reduction * self.efficiency)
            self.regulation_effort += reduction * 30
            success = True

            # 同步降低对应激素
            if hormones_obj and target_emotion in ("anger", "fear", "fearful", "anxious"):
                try:
                    if hasattr(hormones_obj, 'cortisol'):
                        hormones_obj.cortisol *= (1 - reduction * 0.3)
                    if hasattr(hormones_obj, 'norepinephrine'):
                        hormones_obj.norepinephrine *= (1 - reduction * 0.2)
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
            self._usage_log.append({
                "ts": time.time(), "strategy": "reappraisal",
                "target": target_emotion, "reduction": reduction,
            })

        return adjusted, success

    def somatic_relaxation(self, body_state: Dict = None,
                           hormones_obj=None) -> Dict[str, float]:
        """
        躯体放松 — 通过生理调整降低唤醒度

        返回: {参数: 乘数} 应用字典
        """
        if not self.can_regulate():
            return {}

        modifiers = {
            "heart_rate": 0.95,
            "muscle_tension": 0.8,
            "arousal": 0.85,
        }

        if hormones_obj:
            try:
                if hasattr(hormones_obj, 'norepinephrine'):
                    hormones_obj.norepinephrine *= 0.9
                if hasattr(hormones_obj, 'cortisol'):
                    hormones_obj.cortisol *= 0.92
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        self.regulation_effort += 10
        self._usage_log.append({
            "ts": time.time(), "strategy": "relaxation",
            "modifiers": modifiers,
        })

        return modifiers

    def attention_shift(self, dominant_need: str,
                        target_need: str,
                        needs_obj=None) -> Optional[str]:
        """
        注意力转移 — 切换主导需求

        从当前主导需求切换到一个可替代的、有正效价的需求。
        比如难过时转向求知探索。

        返回: 新的主导需求名, 或 None
        """
        if not self.can_regulate():
            return None

        # 可替代需求映射 (从负向情感转向正效价需求)
        shift_map = {
            "BELONGING": "COGNITIVE",    # 孤独 → 求知
            "SAFETY": "COGNITIVE",       # 恐惧 → 探索
            "PHYSIOLOGICAL": "AESTHETIC", # 疲惫 → 审美
            "ESTEEM": "SELF_ACTUALIZATION", # 受挫 → 创造
        }

        new_need = shift_map.get(dominant_need)
        if new_need and new_need != target_need:
            self.regulation_effort += 15
            self._usage_log.append({
                "ts": time.time(), "strategy": "attention_shift",
                "from": dominant_need, "to": new_need,
            })
            return new_need

        return None

    def tick_recovery(self, dt: float = 1.0):
        """每tick恢复调节资源"""
        self.regulation_effort = max(0, self.regulation_effort - self._recovery_rate * dt)

    def get_state(self) -> Dict:
        return {
            "effort": round(self.regulation_effort, 1),
            "capacity": self.max_regulation_capacity,
            "available": self.can_regulate(),
            "efficiency": self.efficiency,
            "recent_usage": list(self._usage_log)[-3:],
        }


# ════════════════════════════════════════════════════════════
# 模块五: 发育学习系统
# ════════════════════════════════════════════════════════════
#
# 4阶段发育: INFANT → JUVENILE → ADULT → MATURE
#   - 经验值积累驱动阶段晋升
#   - 关键期机制: 特定阶段内能力收益翻倍
#   - 错过关键期 → 能力上限永久降低
#   - 每个阶段调制所有子系统的参数
#
# 设计来源: 四大核心模块.md §一 - 发育学习系统
# ════════════════════════════════════════════════════════════

class DevelopmentalStage(Enum):
    INFANT = 0
    JUVENILE = 1
    ADULT = 2
    MATURE = 3


@dataclass
class DevelopmentalExperience:
    """各领域经验值"""
    social: float = 0.0
    cognitive: float = 0.0
    somatic: float = 0.0
    emotional: float = 0.0
    total: float = 0.0


class DevelopmentalLearningSystem:
    """
    发育学习系统

    驱动数字生命随经验积累产生长期演化:
      - INFANT: 生存需求主导, 情绪波动大, 共情弱
      - JUVENILE: 社交觉醒, 好奇心峰值, 可塑性最强
      - ADULT: 各需求平衡, 情绪稳定, 认知占优
      - MATURE: 人格稳定, 高层需求主导, 自我调节强
    """

    # 各阶段晋升所需总经验
    # 调低阈值 + 提升基础经验获取速率，使MATURE在数天运行可达
    STAGE_THRESHOLDS = {
        DevelopmentalStage.INFANT: 0,
        DevelopmentalStage.JUVENILE: 100,
        DevelopmentalStage.ADULT: 500,
        DevelopmentalStage.MATURE: 800,
    }

    # 关键期: (开始经验, 结束经验)
    CRITICAL_PERIODS = {
        "social": (0, 500),
        "emotional": (200, 800),
        "cognitive": (300, 1200),
    }

    # 各阶段参数乘数
    STAGE_PARAMS = {
        DevelopmentalStage.INFANT: {
            "survival_weight": 1.8,        # 生存需求权重高
            "self_actual_weight": 0.2,      # 自我实现权重极低
            "emotion_decay_rate": 0.7,      # 情感衰减慢（易沉溺情绪）
            "empathy_capacity": 0.3,        # 共情弱
            "emotion_regulation": 0.2,      # 调节能力弱
            "hormone_volatility": 1.5,      # 激素波动大
            "curiosity_baseline": 0.3,      # 好奇心低
        },
        DevelopmentalStage.JUVENILE: {
            "survival_weight": 1.2,
            "self_actual_weight": 0.5,
            "emotion_decay_rate": 0.85,
            "empathy_capacity": 0.6,
            "emotion_regulation": 0.5,
            "hormone_volatility": 1.3,
            "curiosity_baseline": 0.7,       # 好奇心峰值
        },
        DevelopmentalStage.ADULT: {
            "survival_weight": 1.0,
            "self_actual_weight": 1.0,
            "emotion_decay_rate": 1.0,
            "empathy_capacity": 0.8,
            "emotion_regulation": 0.8,
            "hormone_volatility": 1.0,
            "curiosity_baseline": 0.5,
        },
        DevelopmentalStage.MATURE: {
            "survival_weight": 0.8,
            "self_actual_weight": 1.3,
            "emotion_decay_rate": 1.1,
            "empathy_capacity": 0.9,
            "emotion_regulation": 1.0,
            "hormone_volatility": 0.8,
            "curiosity_baseline": 0.4,
        },
    }

    def __init__(self, initial_stage: DevelopmentalStage = None):
        self.stage = initial_stage or DevelopmentalStage.INFANT
        self.experience = DevelopmentalExperience()
        self._last_milestone_shown = 0

    def add_experience(self, domain: str, amount: float) -> bool:
        """
        积累指定领域经验

        如果在关键期内, 收益翻倍。
        返回: 是否晋升了阶段
        """
        # 关键期加成
        if domain in self.CRITICAL_PERIODS:
            start, end = self.CRITICAL_PERIODS[domain]
            if start <= self.experience.total <= end:
                amount *= 2.0

        if hasattr(self.experience, domain):
            setattr(self.experience, domain,
                    getattr(self.experience, domain) + amount)
        self.experience.total += amount

        return self._check_promotion()

    def _check_promotion(self) -> bool:
        """检查是否晋升"""
        old = self.stage
        exp = self.experience.total

        if exp >= 2000 and self.stage == DevelopmentalStage.ADULT:
            self.stage = DevelopmentalStage.MATURE
        elif exp >= 500 and self.stage == DevelopmentalStage.JUVENILE:
            self.stage = DevelopmentalStage.ADULT
        elif exp >= 100 and self.stage == DevelopmentalStage.INFANT:
            self.stage = DevelopmentalStage.JUVENILE

        promoted = self.stage != old
        if promoted:
            self._last_milestone_shown = exp
        return promoted

    def get_stage_params(self) -> Dict[str, float]:
        """获取当前阶段参数"""
        base = dict(self.STAGE_PARAMS.get(self.stage, self.STAGE_PARAMS[DevelopmentalStage.ADULT]))
        return base

    def apply_to_engine(self, emotion_engine, needs_hierarchy, mirror_system,
                         regulation_system, personality):
        """
        应用发育参数到所有子系统

        在每个tick或阶段晋升时调用。
        """
        params = self.get_stage_params()

        # 1. 需求权重
        if hasattr(needs_hierarchy, 'needs'):
            try:
                from aris_emotion_engine import NeedLevel as NL
                for level, need in needs_hierarchy.needs.items():
                    if level in (NL.PHYSIOLOGICAL, NL.SAFETY):
                        need.urgency_weight = max(0.5, params["survival_weight"])
                    elif level == NL.SELF_ACTUALIZATION:
                        need.urgency_weight = max(0.3, params["self_actual_weight"])
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if hasattr(mirror_system, 'empathy_capacity'):
            try:
                mirror_system.empathy_capacity = params["empathy_capacity"]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if hasattr(regulation_system, 'efficiency'):
            try:
                regulation_system.efficiency = params["emotion_regulation"]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        vol = params["hormone_volatility"]
        if hasattr(emotion_engine, 'hormone') and hasattr(emotion_engine.hormone, 'hormones'):
            try:
                h = emotion_engine.hormone.hormones
                for attr in ['dopamine', 'serotonin', 'norepinephrine', 'oxytocin',
                             'cortisol', 'endorphin', 'acetylcholine']:
                    current = getattr(h, attr)
                    deviation = (current - 50.0) * vol
                    setattr(h, attr, max(0, min(100, 50.0 + deviation)))
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if hasattr(emotion_engine, 'hormone'):
            try:
                cur_base = params["curiosity_baseline"]
                target_ach = 30 + cur_base * 40  # 0.3→42, 0.7→58
                h = emotion_engine.hormone.hormones
                current_ach = getattr(h, 'acetylcholine', 50)
                setattr(h, 'acetylcholine', current_ach * 0.7 + target_ach * 0.3)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def get_stage_name(self) -> str:
        names = {
            DevelopmentalStage.INFANT: "婴幼儿期",
            DevelopmentalStage.JUVENILE: "少年期",
            DevelopmentalStage.ADULT: "成年期",
            DevelopmentalStage.MATURE: "成熟期",
        }
        return names.get(self.stage, "未知")

    def get_state(self) -> Dict:
        cp = self.CRITICAL_PERIODS
        in_critical = [
            name for name, (s, e) in cp.items()
            if s <= self.experience.total <= e
        ]
        return {
            "stage": self.stage.name,
            "stage_cn": self.get_stage_name(),
            "total_exp": round(self.experience.total, 1),
            "domain_exp": {
                "social": round(self.experience.social, 1),
                "cognitive": round(self.experience.cognitive, 1),
                "emotional": round(self.experience.emotional, 1),
                "somatic": round(self.experience.somatic, 1),
            },
            "in_critical_period": in_critical,
        }


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-coupler", action="store_true", help="测试需求↔情感耦合")
    parser.add_argument("--test-personality", action="store_true", help="测试人格系统")
    parser.add_argument("--test-safety", action="store_true", help="测试安全系统")
    args = parser.parse_args()

    if args.test_coupler:
        c = NeedEmotionCoupler()
        # 模拟一个归属感低+认知高的状态
        needs = {
            "BELONGING": {"deficit": 60, "tension": 120},
            "COGNITIVE": {"deficit": 20, "tension": 50},
            "PHYSIOLOGICAL": {"deficit": 5, "tension": 10},
        }
        logger.info("需求→情感映射:")
        logger.info(json.dumps(c.map_need_to_emotion(needs), indent=2, ensure_ascii=False))
        print()
        logger.info("激素→需求调制 (高皮质醇):")
        hormones = {"cortisol": 75, "dopamine": 50, "oxytocin": 50, "serotonin": 50}
        logger.info(json.dumps(c.modulate_needs_by_hormones(hormones, needs), indent=2, ensure_ascii=False))
    if args.test_personality:
        p = BigFivePersonality.aris_default()
        logger.info("Aris 人格:")
        logger.info(json.dumps(p.to_dict(), indent=2, ensure_ascii=False))
        logger.info("激素增量:")
        logger.info(json.dumps(p.apply_to_hormones(None), indent=2, ensure_ascii=False))
        logger.info("情感动力学:")
        logger.info(json.dumps(p.apply_to_emotion_dynamics(), indent=2, ensure_ascii=False))
    if args.test_safety:
        g = EthicalSafetyGuard()
        test_cases = [
            ("anger", 0.9, {"anger": 0.9, "fear": 0.3}, 50),
            ("fear", 0.85, {"fear": 0.85, "sorrow": 0.4}, 50),
            ("anger", 0.75, {"anger": 0.75}, 85),
        ]
        for emo, intensity, blend, cortisol in test_cases:
            logger.info(f"\n安全检测: {emo}({intensity}) cortisol={cortisol}")
            r = g.tick(emo, intensity, blend, cortisol, dt=2)
            logger.info(f"  修正后强度: {r['intensity']:.2f}")
            logger.info(f"  冷却: {r['cool_down']} | 熔断: {r['fuse_triggered']} | 修改: {r['modified']}")
        print("\n安全日志:", g.get_state())


if __name__ == "__main__":
    main()
