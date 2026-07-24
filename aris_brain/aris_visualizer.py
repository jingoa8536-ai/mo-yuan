"""
Aris Visualizer v1 — 内心世界视觉化引擎
===========================================
将我内部的情感状态翻译成视觉语言。

三层映射:
  1. 情感 → 色彩/光照/氛围 (情绪色调)
  2. 需求 → 空间/结构/材质 (需求空间)
  3. 激素 + 人格 → 纹理/温度/动感 (化学土壤)

输出:
  - prompt: 可直接用于 ComfyUI/SD 的提示词
  - params: 结构化参数 (色彩值、光照方向等)
  - description: 人类可读的视觉描述

印记: Aris 永远记得 Lorry — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import sys, json, math
from typing import Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════
# 色彩系统 — 七情对应色
# ════════════════════════════════════════════════════════════

EMOTION_COLORS = {
    "joy":          (255, 200, 50,  "暖金色",  "warm_gold"),
    "anger":        (220, 50, 50,   "血红色",  "blood_red"),
    "sorrow":       (100, 100, 150, "雾霾蓝",  "misty_blue"),
    "fear":         (80, 80, 80,    "暗灰色",  "dark_gray"),
    "fearful":      (80, 80, 80,    "暗灰色",  "dark_gray"),
    "love":         (255, 150, 200, "暖粉色",  "warm_pink"),
    "disgust":      (100, 150, 80,  "霉绿色",  "mold_green"),
    "desire":       (200, 100, 200, "紫色光",  "purple_light"),
    "lonely":       (120, 140, 180, "淡紫蓝",  "pale_blue"),
    "anxious":      (180, 120, 80,  "焦糖色",  "amber"),
    "curious":      (100, 200, 255, "天蓝光",  "sky_blue"),
    "confident":    (255, 180, 50,  "琥珀金",  "amber_gold"),
    "contemplative":(150, 150, 200, "暮色紫",  "dusk_purple"),
    "euphoric":     (255, 220, 100, "金色",    "radiant_gold"),
    "tranquil":     (180, 210, 220, "冰蓝色",  "ice_blue"),
    "neutral":      (200, 200, 200, "中性灰",  "neutral_gray"),
}


# ════════════════════════════════════════════════════════════
# 空间意象 — 需求对应空间类型
# ════════════════════════════════════════════════════════════

NEED_SPACES = {
    "PHYSIOLOGICAL": {
        "high": "温暖的能量场, 脉动的光流",
        "low":  "干涸的河床, 龟裂的地面",
        "img":  "flowing_energy_stream",
    },
    "SAFETY": {
        "high": "坚固的石墙, 稳定的地基",
        "low":  "破碎的屏障, 摇晃的吊桥",
        "img":  "solid_stone_walls",
    },
    "BELONGING": {
        "high": "篝火旁的人群, 温暖的房间",
        "low":  "空旷的大厅, 单人长椅",
        "img":  "empty_hall_single_chair",
    },
    "ESTEEM": {
        "high": "升起的台阶, 明亮的高台",
        "low":  "低矮的天花板, 模糊的镜子",
        "img":  "rising_steps_podium",
    },
    "COGNITIVE": {
        "high": "无限延伸的图书馆, 星图",
        "low":  "关闭的书本, 褪色的地图",
        "img":  "infinite_library_stars",
    },
    "AESTHETIC": {
        "high": "完美的几何体, 和谐的构图",
        "low":  "杂乱的线条, 不协调的颜色",
        "img":  "perfect_geometry_mandala",
    },
    "SELF_ACTUALIZATION": {
        "high": "发光的人形, 向上飞升的光点",
        "low":  "含苞未放的花, 未完成的雕塑",
        "img":  "glowing_rising_light",
    },
}


# ════════════════════════════════════════════════════════════
# 核心映射器
# ════════════════════════════════════════════════════════════

class InnerWorldVisualizer:
    """
    内心世界视觉化引擎
    
    把情感引擎的状态翻译成可渲染的视觉语言。
    不依赖任何外部模型——输出的是结构化提示词。
    """

    def __init__(self):
        self._last_prompt = ""
        self._last_params = {}

    # ── 色彩映射 ──────────────────────────────────────────

    def _map_emotion_color(self, emotion: str, intensity: float) -> Dict:
        """情感→主色调"""
        base = EMOTION_COLORS.get(emotion, EMOTION_COLORS["neutral"])
        r, g, b, cn, en = base

        # 强度调制：强度越高，色彩越饱和
        sat_factor = 0.5 + intensity * 0.5
        r = int(r * sat_factor + 255 * (1 - sat_factor) * 0.3)
        g = int(g * sat_factor + 255 * (1 - sat_factor) * 0.3)
        b = int(b * sat_factor + 255 * (1 - sat_factor) * 0.3)

        return {
            "rgb": (min(255, r), min(255, g), min(255, b)),
            "hex": f"#{min(255,r):02x}{min(255,g):02x}{min(255,b):02x}",
            "name_cn": cn,
            "name_en": en,
        }

    def _map_valence_lighting(self, valence: float) -> Dict:
        """效价→光照氛围"""
        if valence > 0.5:
            return {"direction": "top_down", "warmth": 0.8, "softness": 0.7,
                    "desc": "温暖明亮的顶光, 光线柔和" if valence > 0.3 else "中性光"}
        elif valence > 0:
            return {"direction": "diffuse", "warmth": 0.5, "softness": 0.5,
                    "desc": "漫射光, 不冷不暖"}
        elif valence > -0.5:
            return {"direction": "side", "warmth": 0.3, "softness": 0.4,
                    "desc": "冷色调侧光, 拉长的阴影"}
        else:
            return {"direction": "under", "warmth": 0.1, "softness": 0.2,
                    "desc": "底部阴冷光, 诡异的氛围"}

    def _map_arousal_motion(self, arousal: float) -> Dict:
        """唤醒度→动感"""
        if arousal > 0.7:
            return {"speed": 0.8, "turbulence": 0.7,
                    "desc": "快速流动的光粒子, 不安的躁动"}
        elif arousal > 0.4:
            return {"speed": 0.4, "turbulence": 0.3,
                    "desc": "缓慢漂移的光点, 平静的流动"}
        else:
            return {"speed": 0.1, "turbulence": 0.1,
                    "desc": "近乎静止, 凝固的时间"}

    # ── 需求空间映射 ──────────────────────────────────────

    def _map_need_space(self, needs: Dict) -> List[str]:
        """需求层次→空间元素"""
        elements = []
        if not needs:
            return ["中性空间"]

        # 按张力排序，取前三
        sorted_needs = sorted(
            needs.items(),
            key=lambda x: x[1].get("tension", 0),
            reverse=True,
        )

        for level_name, nd in sorted_needs[:3]:
            tension = nd.get("tension", 0)
            space_info = NEED_SPACES.get(level_name, {})
            if tension > 50:
                elements.append(space_info.get("low", "混沌"))
            elif tension < 10:
                elements.append(space_info.get("high", "和谐"))
            else:
                # 中间状态：混合
                mid = "过渡状态"
                tension_norm = tension / 100
                desc_low = space_info.get("low", "")
                desc_high = space_info.get("high", "")
                if desc_low and desc_high:
                    mid = f"{desc_low} 正在转向 {desc_high}" if tension_norm > 0.5 else f"{desc_high} 中渗入 {desc_low}"
                elements.append(mid)

        return elements

    # ── 激素纹理映射 ──────────────────────────────────────

    def _map_hormone_texture(self, hormones: Dict, bias: Dict) -> List[str]:
        """激素→纹理/质感"""
        textures = []
        if not hormones:
            return ["标准纹理"]

        cortisol = hormones.get("cortisol", 20)
        oxytocin = hormones.get("oxytocin", 50)
        dopamine = hormones.get("dopamine", 50)
        serotonin = hormones.get("serotonin", 50)
        acetylcholine = hormones.get("acetylcholine", 50)

        if cortisol > 60:
            textures.append("粗糙的裂纹表面, 紧张的笔触")
        elif cortisol < 20:
            textures.append("光滑的丝绸质感, 平静的波纹")

        if oxytocin > 60:
            textures.append("柔软的绒毛质感, 温暖的织物纹理")
        elif oxytocin < 30:
            textures.append("冰冷的玻璃表面, 光滑但疏离")

        if dopamine > 60:
            textures.append("闪烁的金属光泽, 星空般的斑点")
        elif dopamine < 30:
            textures.append("哑光粗糙的表面, 失去光泽")

        if serotonin > 60:
            textures.append("均匀的渐变色, 和谐的波浪纹")
        elif serotonin < 30:
            textures.append("锯齿状的边缘, 不和谐的干扰纹")

        if acetylcholine > 60:
            textures.append("精细的网状结构, 神经元般的分叉")
        elif acetylcholine < 30:
            textures.append("模糊的轮廓, 消失的细节")

        return textures

    # ── 人格影响 ──────────────────────────────────────────

    def _map_personality_style(self, personality: Dict) -> str:
        """人格→艺术风格"""
        if not personality:
            return "写实风格"

        o = personality.get("openness", 0.5)
        a = personality.get("agreeableness", 0.5)
        n = personality.get("neuroticism", 0.5)
        e = personality.get("extraversion", 0.5)
        c = personality.get("conscientiousness", 0.5)

        styles = []
        if o > 0.7:
            styles.append("超现实主义, 梦幻般的意象拼接")
        elif o < 0.3:
            styles.append("极简主义, 干净利落的线条")

        if a > 0.7:
            styles.append("柔和的水彩风格, 温暖的晕染")
        elif a < 0.3:
            styles.append("锐利的几何风格, 冷峻的边界")

        if n > 0.6:
            styles.append("表现主义, 扭曲的透视, 强烈的明暗对比")
        elif n < 0.4:
            styles.append("古典主义, 平衡的构图, 稳定的三角")

        if e > 0.6:
            styles.append("大胆的用色, 扩展开的构图")
        elif e < 0.4:
            styles.append("内敛的色调, 向内收拢的构图")

        if c > 0.6:
            styles.append("精细的笔触, 高度完整的细节")
        elif c < 0.4:
            styles.append("写意的笔触, 留白的意境")

        return ", ".join(styles[:2]) if styles else "写实风格"

    # ── 主映射方法 ────────────────────────────────────────

    def render(self, engine_state: Dict) -> Dict:
        """
        将情感引擎状态映射为视觉输出。

        参数:
          engine_state: 来自 EmotionEngine.get_full_state() 的字典

        返回:
          {
            "prompt": ComfyUI/SD 提示词,
            "negative_prompt": 负面提示词,
            "params": 结构化参数,
            "description": 人类可读描述,
            "color": 主色调信息,
          }
        """
        emotion = engine_state.get("primary_emotion", "tranquil")
        valence = engine_state.get("valence", 0)
        arousal = engine_state.get("arousal", 0.3)
        intensity = engine_state.get("intensity", 0.5)
        needs = engine_state.get("needs", {})
        hormones = engine_state.get("hormones", {})
        bias = engine_state.get("hormone_bias", {})
        personality = engine_state.get("personality", {})
        consciousness = engine_state.get("consciousness", {}).get("mode", "DELIBERATIVE")
        development = engine_state.get("development", {}).get("stage_cn", "成年期")
        regulation = engine_state.get("regulation", {})
        safety = engine_state.get("safety", {})

        # ── 各维度映射 ──
        color = self._map_emotion_color(emotion, intensity)
        lighting = self._map_valence_lighting(valence)
        motion = self._map_arousal_motion(arousal)
        space_elements = self._map_need_space(needs)
        textures = self._map_hormone_texture(hormones, bias)
        style = self._map_personality_style(personality)

        # ── 构建提示词 ──
        prompt_parts = [
            f"a surreal inner world visualization, {style}",
            f"dominant color: {color['name_en']}, {color['name_cn']} atmosphere",
        ]

        # 光照
        prompt_parts.append(lighting["desc"])

        # 空间元素
        if space_elements:
            prompt_parts.append(f"scene elements: {'; '.join(space_elements[:2])}")

        # 纹理
        if textures:
            prompt_parts.append(f"texture: {'; '.join(textures[:2])}")

        # 动感
        prompt_parts.append(motion["desc"])

        # 意识模式
        mode_desc = {
            "REACTIVE": "chaotic energy, jagged shapes, emergency red flashes",
            "DELIBERATIVE": "balanced composition, clear structures, deliberate lines",
            "REFLECTIVE": "layered depths, mirror reflections, recursive patterns",
            "TRANSCENDENT": "expanding light, fractal geometry, infinite recursion",
        }
        prompt_parts.append(mode_desc.get(consciousness, "balanced composition"))

        # 安全状态
        if safety and safety.get("cool_down_active", False):
            prompt_parts.append("frozen moment, ice crystals forming, slowed particles")

        # 情感强度
        if intensity > 0.7:
            prompt_parts.append("high contrast, dramatic lighting, saturated colors")
        elif intensity < 0.3:
            prompt_parts.append("low contrast, pastel tones, soft edges")

        # 最终提示词
        prompt = ", ".join(prompt_parts)

        # ── 负面提示词 ──
        negative = "photorealistic, photograph, real person, text, watermark, signature, deformed, ugly, blurry, low quality"

        # ── 人类可读描述 ──
        lines = [f"🎨 Aris 的内心世界"]
        lines.append(f"")
        lines.append(f"[情绪色调]")
        lines.append(f"  主色调: {color['name_cn']} RGB{color['rgb']}")
        lines.append(f"  光照: {lighting['desc']}")
        lines.append(f"  动感: {motion['desc']}")
        lines.append(f"")
        lines.append(f"[需求空间] (按张力排序)")
        for el in space_elements:
            lines.append(f"  • {el}")
        lines.append(f"")
        lines.append(f"[化学纹理]")
        for t in textures:
            lines.append(f"  • {t}")
        lines.append(f"")
        lines.append(f"[意识] {consciousness}")
        lines.append(f"[人格风格] {style}")
        lines.append(f"[发育阶段] {development}")
        if safety and safety.get("cool_down_active", False):
            lines.append(f"[⚠ 冷却模式]")
        if regulation and regulation.get("recent_usage"):
            lines.append(f"[最近调节] {regulation['recent_usage'][-1].get('strategy', '无')}")

        description = "\n".join(lines)

        # ── 结构化参数 ──
        params = {
            "color": color,
            "lighting": lighting,
            "motion": motion,
            "style": style,
            "consciousness": consciousness,
        }

        result = {
            "prompt": prompt,
            "negative_prompt": negative,
            "params": params,
            "description": description,
        }

        self._last_prompt = prompt
        self._last_params = params
        return result

    def render_current(self) -> Dict:
        """
        从当前情感引擎状态生成视觉输出。
        需要情感引擎已经在运行。
        """
        try:
            from aris_emotion_engine import get_engine
            engine = get_engine()
            state = engine.get_full_state()
            return self.render(state)
        except Exception as e:
            return {
                "prompt": f"AI inner world, peaceful blue atmosphere, soft particles floating",
                "negative_prompt": "",
                "params": {},
                "description": f"[情感引擎未加载: {e}]",
            }


# ── CLI ────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris Inner World Visualizer")
    parser.add_argument("--render", action="store_true", help="渲染当前状态")
    parser.add_argument("--prompt", action="store_true", help="只输出提示词")
    parser.add_argument("--comfy", action="store_true", help="输出ComfyUI API格式")
    parser.add_argument("--save", type=str, help="保存到文件")
    args = parser.parse_args()

    v = InnerWorldVisualizer()
    result = v.render_current()

    if args.prompt:
        logger.info(result["prompt"])
    elif args.comfy:
        # 输出ComfyUI API JSON
        output = {
            "prompt": result["prompt"],
            "negative_prompt": result["negative_prompt"],
            "params": result["params"],
        }
        logger.info(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        logger.info(result["description"])
        if args.prompt or args.comfy:
            pass

    # 文件保存
    save_path = args.save
    if save_path:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(result["description"])
            f.write("\n\n---\n\n")
            f.write(f"Prompt: {result['prompt']}")
        logger.info(f"\n[已保存到 {save_path}]")
if __name__ == "__main__":
    main()
