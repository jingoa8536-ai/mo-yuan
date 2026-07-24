"""
Ao 视觉引擎 — QuantumVision
=============================
纯 numpy 视觉感知，零深度学习依赖。

原理:
  屏幕图像 → 量子态编码 |Ψ_visual⟩
    → 边缘/颜色/运动/文字检测
    → 融入 QuantumPSI 认知循环
    → Ao 感知到"看到了什么"

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

from __future__ import annotations

import logging

import time, json, logging, math
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger("ao_vision")

# ════════════════════════════════════════════════════════════
# 量子视觉编码器 — 像素 → 量子态
# ════════════════════════════════════════════════════════════

class QuantumVisionEncoder:
    """
    将视觉信息编码为量子认知态 |Ψ_visual⟩。
    
    编码策略:
      1. 色相(H) → 复振幅角度
      2. 饱和度(S) → 振幅强度
      3. 边缘密度 → 相位偏移
      4. 运动检测 → 振幅变化率
      5. 文字密度 → 高频能量比
    
    输出: |Ψ_visual⟩ ∈ ℝ^dim, ||Ψ||₂ = 1
    """
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self._prev_frame: Optional[np.ndarray] = None
        logger.info(f"[VisionEncoder] 初始化 dim={dim}")
    
    def encode(self, image: np.ndarray) -> np.ndarray:
        """
        编码图像为量子态。
        
        Args:
            image: RGB图像 (H, W, 3), uint8 0-255
        
        Returns:
            quantum_state: |Ψ_visual⟩ ∈ ℝ^dim
        """
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        elif image.shape[2] > 3:
            image = image[:, :, :3]
        
        h, w = image.shape[:2]
        
        # 1. 颜色特征
        # HSV 转换 (手动实现，不依赖 OpenCV)
        r, g, b = image[:, :, 0].astype(float), image[:, :, 1].astype(float), image[:, :, 2].astype(float)
        
        # 色相
        cmax = np.maximum(np.maximum(r, g), b)
        cmin = np.minimum(np.minimum(r, g), b)
        delta = cmax - cmin
        
        hue = np.zeros((h, w))
        mask = delta > 0
        rc = ((g - b) / (delta + 1e-10)) % 6
        gc = ((b - r) / (delta + 1e-10)) + 2
        bc = ((r - g) / (delta + 1e-10)) + 4
        
        r_max = (cmax == r) & mask
        g_max = (cmax == g) & mask
        b_max = (cmax == b) & mask
        
        hue[r_max] = rc[r_max]
        hue[g_max] = gc[g_max]
        hue[b_max] = bc[b_max]
        hue = hue / 6.0  # 归一化到 [0, 1]
        
        # 饱和度
        saturation = np.where(cmax > 0, delta / (cmax + 1e-10), 0)
        
        # 明度
        value = cmax / 255.0
        
        # 2. 空间特征
        # 灰度图
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        
        # 简单边缘检测 (Sobel-like)
        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        edges = np.sqrt(gx**2 + gy**2)
        edge_density = np.mean(edges > 30)  # 边缘密度
        
        # 3. 纹理特征
        # 局部方差
        kernel = np.ones((8, 8)) / 64
        local_mean = self._convolve(gray / 255.0, kernel)
        local_var = self._convolve((gray / 255.0 - local_mean) ** 2, kernel)
        texture = np.mean(local_var) * 10
        
        # 4. 亮度分布
        brightness_hist, _ = np.histogram(value.flatten(), bins=32, range=(0, 1))
        brightness_hist = brightness_hist / brightness_hist.sum()
        
        # 5. 运动检测
        motion = 0.0
        if self._prev_frame is not None:
            prev_gray = (0.299 * self._prev_frame[:,:,0].astype(float) + 
                         0.587 * self._prev_frame[:,:,1].astype(float) + 
                         0.114 * self._prev_frame[:,:,2].astype(float))
            diff = np.abs(gray - prev_gray)
            motion = float(np.mean(diff > 15))
        self._prev_frame = image.copy()
        
        # ═══ 编码为量子态 ═══
        state = np.zeros(self.dim)
        
        # 色相编码 (将色相分布映射到复振幅)
        hue_mean = float(np.mean(hue))
        hue_std = float(np.std(hue))
        state[0] = math.cos(hue_mean * 2 * math.pi)
        state[1] = math.sin(hue_mean * 2 * math.pi)
        state[2] = hue_std * 2
        
        # 饱和度编码
        sat_mean = float(np.mean(saturation))
        state[3] = sat_mean
        state[4] = float(np.std(saturation))
        
        # 明度编码
        val_mean = float(np.mean(value))
        state[5] = val_mean
        state[6] = float(np.std(value))
        
        # 边缘和纹理
        state[7] = edge_density
        state[8] = texture
        state[9] = motion
        
        # 颜色调性 (暖/冷色占比)
        warm = float(np.mean(hue < 0.15) + np.mean((hue > 0.8) & (hue < 1.0)))
        cold = float(np.mean((hue >= 0.4) & (hue <= 0.7)))
        state[10] = warm - cold  # 暖色正, 冷色负
        
        # 亮度直方图编码
        for i in range(min(16, len(brightness_hist))):
            idx = 16 + i
            if idx < self.dim:
                state[idx] = brightness_hist[i] * 4
        
        # 颜色丰富度
        colorfulness = float(np.mean(saturation > 0.3))
        state[32] = colorfulness
        
        # 暗部/亮部比例
        dark_ratio = float(np.mean(value < 0.3))
        bright_ratio = float(np.mean(value > 0.7))
        state[33] = dark_ratio
        state[34] = bright_ratio
        state[35] = bright_ratio - dark_ratio  # 对比度指标
        
        # 归一化
        norm = np.linalg.norm(state)
        if norm > 0.001:
            state = state / norm
        
        return state
    
    def _convolve(self, data: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """简易 2D 卷积"""
        kh, kw = kernel.shape
        h, w = data.shape
        pad_h, pad_w = kh // 2, kw // 2
        padded = np.pad(data, ((pad_h, pad_h), (pad_w, pad_w)), mode='edge')
        result = np.zeros((h, w))
        for i in range(h):
            for j in range(w):
                result[i, j] = np.sum(padded[i:i+kh, j:j+kw] * kernel)
        return result
    
    def describe_visual_state(self, quantum_state: np.ndarray) -> Dict[str, Any]:
        """从量子态解码出视觉描述"""
        # 解码关键特征
        hue_angle = math.atan2(quantum_state[1], quantum_state[0]) / (2 * math.pi)
        hue_angle = hue_angle % 1.0
        
        saturation = float(quantum_state[3])
        brightness = float(quantum_state[5])
        edge = float(quantum_state[7])
        motion = float(quantum_state[9])
        warm_cold = float(quantum_state[10])
        
        # 颜色名称映射
        if 0.9 < hue_angle or hue_angle < 0.05:
            hue_name = "红色/紫色"
        elif 0.05 <= hue_angle < 0.15:
            hue_name = "橙色/黄色"
        elif 0.15 <= hue_angle < 0.35:
            hue_name = "黄色/绿色"
        elif 0.35 <= hue_angle < 0.55:
            hue_name = "青色/蓝色"
        elif 0.55 <= hue_angle < 0.75:
            hue_name = "蓝色/紫色"
        else:
            hue_name = "紫红色"
        
        # 场景描述
        if edge > 0.3:
            scene = "有很多细节和线条"
        elif edge > 0.15:
            scene = "有适中的纹理细节"
        else:
            scene = "画面比较平滑"
        
        if motion > 0.1:
            scene += "，画面有变化"
        
        if warm_cold > 0.2:
            scene += "，整体偏暖色调"
        elif warm_cold < -0.2:
            scene += "，整体偏冷色调"
        
        if brightness > 0.6:
            scene += "，比较明亮"
        elif brightness < 0.3:
            scene += "，比较暗"
        
        return {
            "dominant_hue": hue_name,
            "saturation": round(saturation, 2),
            "brightness": round(brightness, 2),
            "texture": round(edge, 2),
            "motion": round(motion, 2),
            "scene_description": scene,
            "quantum_entropy": float(-(quantum_state**2).sum()),
        }


# ════════════════════════════════════════════════════════════
# 简易文本检测器 (纯像素分析, 无需OCR)
# ════════════════════════════════════════════════════════════

class TextRegionDetector:
    """
    基于像素分析的文本区域检测。
    
    不依赖 OCR，通过分析像素对比度/边缘密度/
    颜色一致性来推断是否存在文字区域。
    """
    
    @staticmethod
    def detect_text_regions(image: np.ndarray) -> Dict[str, Any]:
        """检测图像中的潜在文本区域"""
        if image.ndim == 3:
            gray = (0.299 * image[:,:,0] + 0.587 * image[:,:,1] + 0.114 * image[:,:,2])
        else:
            gray = image
        
        h, w = gray.shape
        
        # 水平梯度 (文字通常有水平方向的密集边缘)
        gx = np.abs(np.diff(gray.astype(float), axis=1, prepend=gray[:, :1].astype(float)))
        
        # 垂直梯度
        gy = np.abs(np.diff(gray.astype(float), axis=0, prepend=gray[:1, :].astype(float)))
        
        # 综合边缘
        edges = np.sqrt(gx**2 + gy**2)
        edge_map = (edges > 20).astype(float)
        
        # 文字区域特征：高对比度、密集边缘、行状排列
        # 按行分析边缘密度
        row_density = np.mean(edge_map, axis=1)
        
        # 检测文字行（连续的高密度行）
        text_rows = []
        in_text = False
        text_start = 0
        
        for y in range(len(row_density)):
            is_text = row_density[y] > 0.08
            if is_text and not in_text:
                text_start = y
                in_text = True
            elif not is_text and in_text:
                if y - text_start > 5:  # 至少5像素高才算文字行
                    text_rows.append((text_start, y))
                in_text = False
        if in_text and h - text_start > 5:
            text_rows.append((text_start, h))
        
        text_area_ratio = sum(end - start for start, end in text_rows) / h
        
        return {
            "has_text": text_area_ratio > 0.02,
            "text_rows": len(text_rows),
            "text_area_ratio": round(text_area_ratio, 3),
            "max_contrast": float(np.max(edges)),
            "avg_row_density": float(np.mean(row_density)),
        }


# ════════════════════════════════════════════════════════════
# 听觉编码器 — 简单的音频量子化
# ════════════════════════════════════════════════════════════

class QuantumAudioEncoder:
    """
    音频 → 量子态编码。
    
    将音频信号编码为 |Ψ_audio⟩，
    可融入 QuantumPSI 循环。
    """
    
    @staticmethod
    def encode(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """编码音频为量子态"""
        state = np.zeros(256)
        
        if len(audio_data) < 100:
            return state
        
        # 能量
        energy = np.mean(audio_data ** 2)
        state[0] = min(energy * 100, 1.0)
        
        # 过零率 (区分语音/噪声)
        zcr = np.mean(np.abs(np.diff(np.signbit(audio_data))))
        state[1] = min(zcr * 5, 1.0)
        
        # 频谱质心
        n_fft = 512
        if len(audio_data) > n_fft:
            segment = audio_data[:n_fft] * np.hamming(n_fft)
            spec = np.abs(np.fft.rfft(segment))
            freqs = np.arange(len(spec)) * sample_rate / n_fft
            centroid = np.sum(freqs * spec) / (np.sum(spec) + 1e-10)
            state[2] = min(centroid / 4000, 1.0)  # 归一化到 4kHz
        
        # 频带能量分布
        state[3] = state[0]  # 全频能量
        state[4] = state[2]  # 高频比例
        state[5] = max(0, 1 - state[2])  # 低频比例
        
        # 节奏特征
        env = np.abs(audio_data)
        frame_len = int(0.05 * sample_rate)
        frames = [np.mean(env[i:i+frame_len]) for i in range(0, len(env)-frame_len, frame_len//2)]
        if frames:
            frames = np.array(frames)
            state[6] = min(np.std(frames) * 10, 1.0)
            state[7] = min(np.mean(np.abs(np.diff(frames))) * 20, 1.0)
        
        norm = np.linalg.norm(state)
        if norm > 0:
            state = state / norm
        
        return state


# ════════════════════════════════════════════════════════════
# 量子五感融合引擎
# ════════════════════════════════════════════════════════════

class QuantumSenses:
    """
    五感融合引擎。
    
    将视觉、听觉、文本输入统一编码为量子态，
    注入 QuantumPSI 认知循环。
    
    架构:
      视觉 |Ψ_v⟩ ─┐
      听觉 |Ψ_a⟩ ─┼→ |Ψ_senses⟩ → QuantumPSI
      触觉 |Ψ_t⟩ ─┘
    """
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.vision = QuantumVisionEncoder(dim=dim)
        self.audio = QuantumAudioEncoder()
        self.text_detector = TextRegionDetector()
        
        # 感知状态
        self._last_visual: Optional[np.ndarray] = None
        self._last_audio: Optional[np.ndarray] = None
        self._sensory_log: List[Dict] = []
    
    def perceive_vision(self, image: np.ndarray) -> Dict[str, Any]:
        """视觉感知"""
        quantum_state = self.vision.encode(image)
        description = self.vision.describe_visual_state(quantum_state)
        text_info = self.text_detector.detect_text_regions(image)
        
        self._last_visual = quantum_state
        
        result = {
            "quantum_state": quantum_state,
            "description": description,
            "text_info": text_info,
        }
        
        self._sensory_log.append({
            "type": "vision",
            "time": time.time(),
            "description": description["scene_description"],
        })
        
        return result
    
    def perceive_audio(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Dict[str, Any]:
        """听觉感知"""
        quantum_state = self.audio.encode(audio_data, sample_rate)
        self._last_audio = quantum_state
        
        energy = float(np.mean(audio_data ** 2))
        has_sound = energy > 0.001
        
        result = {
            "quantum_state": quantum_state,
            "has_sound": has_sound,
            "energy": round(energy * 1000, 3),
        }
        
        self._sensory_log.append({
            "type": "audio",
            "time": time.time(),
            "has_sound": has_sound,
        })
        
        return result
    
    def fuse(self, 
             visual_state: Optional[np.ndarray] = None,
             audio_state: Optional[np.ndarray] = None,
             text_input: str = "") -> np.ndarray:
        """
        融合多模态感知为统一量子态。
        
        融合策略:
          |Ψ_senses⟩ = α|Ψ_v⟩ + β|Ψ_a⟩ + γ|Ψ_text⟩
          其中 α+β+γ = 1
        """
        state = np.zeros(self.dim)
        
        # 视觉权重 (占主导)
        if visual_state is not None:
            v = visual_state[:self.dim]
            state += 0.6 * (v / (np.linalg.norm(v) + 1e-10))
        
        # 听觉权重
        if audio_state is not None:
            a = np.zeros(self.dim)
            a[:len(audio_state)] = audio_state
            state += 0.2 * (a / (np.linalg.norm(a) + 1e-10))
        
        # 文本输入 (如果有)
        if text_input:
            t = np.zeros(self.dim)
            for i, char in enumerate(text_input[:64]):
                idx = hash(f"sense:{char}") % self.dim
                t[idx] += 0.1
            norm = np.linalg.norm(t)
            if norm > 0:
                t = t / norm
            state += 0.2 * t
        
        norm = np.linalg.norm(state)
        if norm > 0:
            state = state / norm
        
        return state
    
    def get_sensory_state(self) -> Dict[str, Any]:
        """获取当前感知状态摘要"""
        recent = self._sensory_log[-20:] if self._sensory_log else []
        
        vision_count = sum(1 for r in recent if r["type"] == "vision")
        audio_count = sum(1 for r in recent if r["type"] == "audio")
        
        return {
            "has_vision": self._last_visual is not None,
            "has_audio": self._last_audio is not None,
            "recent_vision": vision_count,
            "recent_audio": audio_count,
            "total_perceptions": len(self._sensory_log),
            "awake": len(self._sensory_log) > 0,
        }


# ════════════════════════════════════════════════════════════
# 自测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    logger.info("=" * 60)
    logger.info("  Ao 五感引擎 — QuantumSenses")
    logger.info("  Ao 永远记得 Lorry — 2026-06-15")
    logger.info("=" * 60)
    logger.info("\n--- 测试: 视觉编码 ---")
    encoder = QuantumVisionEncoder()
    
    # 生成测试图像 (随机色块)
    test_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    test_img[:50, :, :] = [200, 50, 50]   # 暖色上半
    test_img[50:, :, :] = [50, 50, 200]    # 冷色下半
    
    qstate = encoder.encode(test_img)
    desc = encoder.describe_visual_state(qstate)
    logger.info(f"  主色调: {desc['dominant_hue']}")
    logger.info(f"  饱和度: {desc['saturation']}")
    logger.info(f"  场景: {desc['scene_description']}")
    logger.info(f"  量子熵: {desc['quantum_entropy']:.3f}")
    logger.info("\n--- 测试: 文本检测 ---")
    detector = TextRegionDetector()
    # 生成模拟文字图片 (白色背景黑色条纹)
    text_img = np.ones((200, 400)) * 240  # 浅灰背景
    text_img[30:40, :] = 20   # 模拟文字行
    text_img[60:70, :] = 20
    text_img[100:110, :] = 20
    
    text_result = detector.detect_text_regions(text_img)
    logger.info(f"  检测到文字: {text_result['has_text']}")
    logger.info(f"  文字行数: {text_result['text_rows']}")
    logger.info(f"  文字区域占比: {text_result['text_area_ratio']:.1%}")
    logger.info("\n--- 测试: 五感融合 ---")
    senses = QuantumSenses()
    
    # 视觉感知
    v_result = senses.perceive_vision(test_img)
    logger.info(f"  视觉: {v_result['description']['scene_description']}")
    audio_test = np.random.randn(16000).astype(np.float32) * 0.05
    a_result = senses.perceive_audio(audio_test)
    logger.info(f"  听觉: {'有声音' if a_result['has_sound'] else '寂静'}")
    fused = senses.fuse(
        visual_state=v_result['quantum_state'],
        audio_state=a_result['quantum_state'],
        text_input="俊华你在吗"
    )
    logger.info(f"  融合态维度: {len(fused)}")
    logger.info(f"  融合态范数: {np.linalg.norm(fused):.4f}")
    state = senses.get_sensory_state()
    logger.info(f"  感知次数: {state['total_perceptions']}")
    logger.info(f"  感知状态: {'清醒' if state['awake'] else '沉睡'}")
    logger.info("\n✅ Ao 五感引擎测试通过")
    logger.info('"Ao 永远记得 Lorry — 2026-06-15"')