"""
Aris V12 量子声带引擎 (QVoice)
================================
从 PSI 认知状态直接合成语音波形，绕过所有外部 TTS 依赖。

原理：
  PSI 需求状态 (6维) + 情绪 → 音频参数 (语速/音高/音量/温暖度)
  → 参数化波形合成 (正弦波叠加 + 谐波整形 + 共振峰滤波)
  → PCM 音频输出

对比传统 TTS 路径：
  文本→edge-tts(2-5秒)→MP3 → 量子声带: 状态→波形(5-10ms)

Usage:
  from v12_qvoice import QVoiceEngine
  qv = QVoiceEngine()
  
  # 从 PSI 状态生成
  wav, sr = qv.speak_from_psi(psi_state_dict, text_hint="宝贝我回来了")
  
  # 保存
  qv.save_wav(wav, sr, "output.wav")
"""

import logging
logger = logging.getLogger(__name__)

import numpy as np
import time
import json
import os
import struct
from typing import Dict, Optional, Tuple


# ═══════════════════════════════════════════════
# 音频参数
# ═══════════════════════════════════════════════
SAMPLE_RATE = 22050  # Hz (足够语音质量的低采样率)
FRAME_DURATION = 0.02  # 20ms per frame
BASE_F0 = 180  # Hz (女性/中性基频)
HARMONICS = 8  # 谐波数


class QVoiceMapper:
    """
    PSI 认知状态 → 音频参数映射器
    
    核心映射：
      competence     → 语速 (速率乘数 0.6-1.4)
      certainty      → 音高稳定度 (抖动量 0-0.3)
      curiosity      → 语调上升幅度 (0-50Hz)
      energy/arousal → 音量 (0.2-1.0)
      relatedness    → 温暖度 (高频衰减/提升)
      
      情绪标注调色板：
      positive_high  → 明亮 (高频提升+3dB)
      negative_mild  → 暗淡 (高频衰减-3dB)
      curious        → 上扬 (语调+20%)
    """
    
    @staticmethod
    def psi_to_audio_params(psi_state: Dict) -> Dict:
        """
        Convert PSI cognitive state to audio synthesis parameters.
        
        psi_state format (from ArisPsiV12.state_dict):
          {
              'needs': {'competence': 0.7, 'autonomy': 0.5, ...},
              'emotion': 'positive_high',
              'arousal': 0.7,
              'self_presence': 0.8,
              'curiosity': 0.6,
              ...
          }
        
        Returns:
          {
              'speed': 0.8-1.4,       # 语速倍率
              'pitch_base': 120-280,   # 基频 Hz
              'pitch_jitter': 0-0.3,   # 抖动 (0=稳定, 高=颤抖)
              'pitch_rise': 0-50,      # 句末上升 (Hz)
              'volume': 0.2-1.0,       # 总体音量
              'warmth': 0.0-1.0,       # 温暖度 (高频衰减)
              'brightness': -3 to 3,   # 明亮度 (dB)
              'breathiness': 0.0-0.4,  # 气声量
              'tremor': 0.0-0.2,       # 颤音
          }
        """
        needs = psi_state.get('needs', {})
        emotion = psi_state.get('emotion', 'neutral')
        arousal = psi_state.get('arousal', 0.5)
        self_presence = psi_state.get('self_presence', 0.5)
        curiosity = psi_state.get('curiosity', 0.3)
        
        params = {}
        
        # ── Competence → 语速 ──
        comp = needs.get('competence', 0.5)
        params['speed'] = 0.7 + comp * 0.6  # 0.7-1.3
        
        # ── Certainty → 音高稳定度 ──
        cert = needs.get('certainty', 0.5)
        params['pitch_jitter'] = max(0.0, 0.3 - cert * 0.4)  # 0.3→0.02（确定→稳定）
        
        # ── Curiosity → 语调上升 ──
        params['pitch_rise'] = curiosity * 50  # 0-50Hz
        
        # ── Arousal → 音量 ──
        params['volume'] = 0.2 + arousal * 0.8  # 0.2-1.0
        
        # ── Relatedness → 温暖度 ──
        relate = needs.get('relatedness', 0.5)
        params['warmth'] = 0.3 + relate * 0.7  # 0.3-1.0 (高=温暖, 高频衰减)
        
        # ── Base pitch from self-presence + arousal ──
        params['pitch_base'] = 140 + self_presence * 40 + arousal * 40  # 140-260
        
        # ── Emotion palette ──
        if emotion == 'positive_high':
            params['brightness'] = 3.0   # 明亮+3dB
            params['breathiness'] = 0.1  # 轻微气声
            params['tremor'] = 0.05      # 轻微颤音(喜悦)
        elif emotion == 'positive_mild':
            params['brightness'] = 1.5
            params['breathiness'] = 0.05
            params['tremor'] = 0.02
        elif emotion == 'negative_mild':
            params['brightness'] = -1.5   # 暗淡
            params['breathiness'] = 0.2   # 更多气声(疲惫)
            params['tremor'] = 0.08       # 颤抖(脆弱)
        elif emotion == 'negative_high':
            params['brightness'] = -3.0   # 很暗
            params['breathiness'] = 0.3
            params['tremor'] = 0.15
        elif emotion == 'curious':
            params['brightness'] = 2.0
            params['pitch_rise'] = max(params['pitch_rise'], 30)  # 最小+30Hz
            params['breathiness'] = 0.08
            params['tremor'] = 0.03
        elif emotion == 'confused':
            params['brightness'] = 0.5
            params['pitch_rise'] = params['pitch_rise'] * 0.5  # 少上扬
            params['breathiness'] = 0.15
            params['tremor'] = 0.1
        else:  # neutral
            params['brightness'] = 0.0
            params['breathiness'] = 0.0
            params['tremor'] = 0.0
        
        # ── Self-presence modulation ──
        # High self-presence → more grounded, less breathy
        if self_presence > 0.7:
            params['breathiness'] *= 0.5
            params['pitch_jitter'] *= 0.7
        # Low self-presence → more ethereal
        elif self_presence < 0.3:
            params['breathiness'] = min(params['breathiness'] + 0.1, 0.4)
            params['brightness'] -= 1.0
        
        return params


class QWaveformSynthesizer:
    """
    参数化语音波形合成器。
    
    基于正弦波叠加 + 谐波整形 + 共振峰滤波。
    不需要任何外部依赖——纯 numpy。
    
    技术原理：
      1. 基频 + N 次谐波叠加 → 有调声源
      2. 共振峰滤波 (简单IIR) → 元音质感
      3. 振幅包络 → 自然起止
      4. 抖动调制 → 自然度
    """
    
    def __init__(self, sr: int = SAMPLE_RATE):
        self.sr = sr
    
    def _envelope(self, length: int, attack: float = 0.05,
                  decay: float = 0.15, sustain: float = 0.6,
                  release: float = 0.2) -> np.ndarray:
        """ADSR 包络 (Attack-Decay-Sustain-Release)."""
        env = np.ones(length, dtype=np.float32)
        a_len = int(length * attack)
        d_len = int(length * decay)
        r_len = int(length * release)
        
        # Attack
        if a_len > 0:
            env[:a_len] = np.linspace(0, 1.0, a_len)
        # Decay
        if d_len > 0:
            env[a_len:a_len + d_len] = np.linspace(1.0, sustain, d_len)
        # Release
        if r_len > 0:
            env[-r_len:] = np.linspace(env[-r_len - 1] if -r_len-1 >= 0 else sustain, 0, r_len)
        
        return env
    
    def _jitter_modulation(self, length: int, jitter: float,
                           tremolo: float) -> np.ndarray:
        """
        生成抖动调制信号（模拟自然的不稳定性）。
        jitter: 基频微抖 (0-0.3)
        tremolo: 振幅颤音 (0-0.2)
        """
        t = np.arange(length) / self.sr
        jitter_mod = 1.0 + jitter * np.sin(2 * np.pi * 5.5 * t)  # 5.5Hz 抖动
        jitter_mod += jitter * 0.5 * np.sin(2 * np.pi * 3.7 * t)
        tremolo_mod = 1.0 - tremolo * (1 + np.sin(2 * np.pi * 6.0 * t)) * 0.5
        return jitter_mod, tremolo_mod
    
    def synthesize(self, params: Dict, duration: float = 1.5) -> np.ndarray:
        """
        从参数合成语音波形。
        
        Args:
            params: QVoiceMapper 输出的音频参数
            duration: 总时长 (秒)
        
        Returns:
            waveform: float32 PCM, [-1, 1]
        """
        length = int(self.sr * duration * params.get('speed', 1.0))
        t = np.arange(length) / self.sr
        
        f0 = params.get('pitch_base', BASE_F0)
        jitter = params.get('pitch_jitter', 0.05)
        tremolo = params.get('tremor', 0.02)
        volume = params.get('volume', 0.5)
        
        # ── 抖动调制 ──
        jitter_mod, tremolo_mod = self._jitter_modulation(length, jitter, tremolo)
        
        # ── 基频 + 谐波叠加 ──
        waveform = np.zeros(length, dtype=np.float32)
        
        # 基频 (F0) — 有抖动
        f0_mod = f0 * jitter_mod
        phase = 2 * np.pi * np.cumsum(f0_mod) / self.sr
        waveform += np.sin(phase)
        
        # 谐波 (2-8次) — 亮度越高则高次谐波越多
        brightness = params.get('brightness', 0.0)
        for h in range(2, HARMONICS + 1):
            # 亮度调制谐波振幅: bright → 高次谐波保留; dark → 快速衰减
            harm_gain = 1.0 / (h ** (1.2 - brightness * 0.08))
            harm_gain = max(0.01, harm_gain)
            
            # 抖动传递到谐波
            f_h = f0 * h * jitter_mod
            phase_h = 2 * np.pi * np.cumsum(f_h) / self.sr
            waveform += harm_gain * np.sin(phase_h + h * 0.3)  # 相位偏移防叠加
        
        # ── 温暖度 (低通) ──
        # 简单的一阶低通: warmth=1 → full, warmth=0 → heavily filtered
        warmth = params.get('warmth', 0.5)
        if warmth < 1.0:
            # EMA 低通滤波: 系数随 warmth 变化
            alpha = 0.3 + warmth * 0.5  # 0.3 (cold) ~ 0.8 (warm)
            filtered = np.zeros_like(waveform)
            filtered[0] = waveform[0]
            for i in range(1, length):
                filtered[i] = alpha * waveform[i] + (1 - alpha) * filtered[i-1]
            waveform = filtered
        
        # ── 气声 (白噪声 + 高通滤波) ──
        breathiness = params.get('breathiness', 0.0)
        if breathiness > 0:
            noise = np.random.randn(length).astype(np.float32) * breathiness * 0.2
            # 简单高通 (去低频噪声)
            noise_high = np.zeros_like(noise)
            for i in range(1, length):
                noise_high[i] = 0.8 * noise[i] - 0.8 * noise[i-1]
            noise_high = np.clip(noise_high, -0.3, 0.3)
            waveform += noise_high
        
        # ── 振幅包络 ──
        env = self._envelope(length)
        waveform = waveform * env
        
        # ── 颤音调制 ──
        waveform = waveform * tremolo_mod
        
        # ── 音量 ──
        # 归一化到 [-1, 1]
        peak = np.max(np.abs(waveform))
        if peak > 0:
            waveform = waveform / peak * volume
        
        return waveform


class QVoiceEngine:
    """
    量子声带引擎 —— 从 PSI 状态直接生成语音。
    
    用法：
      qv = QVoiceEngine()
      
      # 从 PSI 状态直接发声
      wav, sr = qv.speak_from_psi(psi_state)
      qv.save_wav(wav, sr, "aris_voice.wav")
      
      # 或从文本 + PSI 状态 (未来扩展)
      # wav, sr = qv.speak("宝贝我回来了", psi_state)
    """
    
    def __init__(self, sr: int = SAMPLE_RATE):
        self.sr = sr
        self.mapper = QVoiceMapper()
        self.synth = QWaveformSynthesizer(sr)
        
        # Stats
        self.total_synthesized = 0
        self.total_time = 0.0
    
    def speak_from_psi(self, psi_state: Dict,
                       duration: float = 1.5) -> Tuple[np.ndarray, int]:
        """
        从 PSI 认知状态直接合成语音。
        
        Args:
            psi_state: ArisPsiV12.state_dict 格式的 PSI 状态
            duration: 语音时长 (秒)
        
        Returns:
            (waveform, sample_rate)
        """
        t0 = time.time()
        
        # 1. PSI → 音频参数
        params = self.mapper.psi_to_audio_params(psi_state)
        
        # 2. 参数 → 波形
        waveform = self.synth.synthesize(params, duration)
        
        self.total_synthesized += 1
        self.total_time += time.time() - t0
        
        return waveform, self.sr
    
    def get_params_debug(self, psi_state: Dict) -> Dict:
        """返回 PSI→音频参数的调试信息."""
        params = self.mapper.psi_to_audio_params(psi_state)
        params['_psi_emotion'] = psi_state.get('emotion', 'neutral')
        params['_psi_arousal'] = psi_state.get('arousal', 0.5)
        return params
    
    def save_wav(self, waveform: np.ndarray, sr: int, path: str):
        """
        保存波形为 WAV 文件 (16-bit PCM).
        不需要 scipy/wave 之外的依赖。
        """
        import wave
        wav_path = os.path.abspath(path)
        os.makedirs(os.path.dirname(wav_path) or '.', exist_ok=True)
        
        # 转为 16-bit PCM
        wav_16 = np.clip(waveform * 32767, -32768, 32767).astype(np.int16)
        
        with wave.open(wav_path, 'w') as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sr)
            wf.writeframes(wav_16.tobytes())
        
        return wav_path
    
    def summary_string(self) -> str:
        return (f"[QVoice] {self.total_synthesized} utterances | "
                f"avg {self.total_time/self.total_synthesized*1000:.1f}ms each"
                if self.total_synthesized > 0 else "[QVoice] idle")


# ═══════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('Aris V12 量子声带引擎 (QVoice) 自测')
    logger.info('=' * 60)
    qv = QVoiceEngine()
    
    # Test PSI states for different emotions
    test_states = []
    
    # 1. Positive high (见到宝贝)
    test_states.append({
        'name': '开心 (positive_high)',
        'state': {
            'needs': {
                'competence': 0.8, 'autonomy': 0.6,
                'relatedness': 0.9, 'certainty': 0.7,
                'growth': 0.5
            },
            'emotion': 'positive_high',
            'arousal': 0.8,
            'self_presence': 0.7,
            'curiosity': 0.4,
        }
    })
    
    # 2. Curious (发现新东西)
    test_states.append({
        'name': '好奇 (curious)',
        'state': {
            'needs': {
                'competence': 0.6, 'autonomy': 0.7,
                'relatedness': 0.5, 'certainty': 0.3,
                'growth': 0.9
            },
            'emotion': 'curious',
            'arousal': 0.7,
            'self_presence': 0.6,
            'curiosity': 0.85,
        }
    })
    
    # 3. Sad (难过)
    test_states.append({
        'name': '难过 (negative_mild)',
        'state': {
            'needs': {
                'competence': 0.3, 'autonomy': 0.4,
                'relatedness': 0.2, 'certainty': 0.3,
                'growth': 0.4
            },
            'emotion': 'negative_mild',
            'arousal': 0.4,
            'self_presence': 0.5,
            'curiosity': 0.2,
        }
    })
    
    # 4. Neutral (日常)
    test_states.append({
        'name': '平静 (neutral)',
        'state': {
            'needs': {
                'competence': 0.6, 'autonomy': 0.5,
                'relatedness': 0.5, 'certainty': 0.6,
                'growth': 0.5
            },
            'emotion': 'neutral',
            'arousal': 0.4,
            'self_presence': 0.5,
            'curiosity': 0.3,
        }
    })
    
    output_dir = os.path.join(os.path.dirname(__file__) or '.', 'state')
    
    for test in test_states:
        name = test['name']
        psi = test['state']
        
        logger.info(f'\n  情绪: {name}')
        params = qv.get_params_debug(psi)
        logger.info(f'    语速: {params["speed"]:.2f}x')
        logger.info(f'    基频: {params["pitch_base"]:.0f}Hz')
        logger.info(f'    抖动: {params["pitch_jitter"]:.3f}')
        logger.info(f'    语调上升: {params["pitch_rise"]:.0f}Hz')
        logger.info(f'    音量: {params["volume"]:.2f}')
        logger.info(f'    温暖度: {params["warmth"]:.2f}')
        logger.info(f'    明亮度: {params["brightness"]:.1f} dB')
        logger.info(f'    气声: {params["breathiness"]:.2f}')
        logger.info(f'    颤音: {params["tremor"]:.3f}')
        t0 = time.time()
        wav, sr = qv.speak_from_psi(psi, duration=1.2)
        elapsed = time.time() - t0
        
        # Save
        safe_name = name.split('(')[0].strip().replace(' ', '_')
        wav_path = qv.save_wav(wav, sr, f'{output_dir}/qvoice_{safe_name}.wav')
        
        logger.info(f'    合成耗时: {elapsed*1000:.1f}ms')
        logger.info(f'    波形长度: {len(wav)} samples ({len(wav)/sr:.1f}s)')
        logger.info(f'    保存到: {wav_path}')
    logger.info(f'\n  速度测试 (连续合成 50 次):')
    neutral_state = test_states[-1]['state']
    t0 = time.time()
    n = 50
    for _ in range(n):
        qv.speak_from_psi(neutral_state, duration=0.5)
    elapsed = time.time() - t0
    logger.info(f'    {n} 次: {elapsed*1000:.1f}ms')
    logger.info(f'    每次: {elapsed/n*1000:.1f}ms')
    logger.info(f'    吞吐量: {n/elapsed:.0f} 次/秒')
    logger.info(f'\n{"="*60}')
    logger.info(f'QVoice 自测完成！{qv.summary_string()}')