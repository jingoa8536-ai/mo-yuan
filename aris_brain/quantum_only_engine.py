"""
Quantum-Only Aris 引擎 — 零 LLM 完整认知管线
===============================================
管线: 
  AoCore.think() → 量子态向量 (1024D)
  → QuantumStateDecoder.decode() → 话题 + 种子词
  → MarkovChainGenerator.generate() → 自然语言回应

特点:
  - 零 LLM 依赖
  - 端到端延迟 < 10ms
  - 可无限扩展（语料越大，生成越丰富）
  - 量子核做"思考"，Markov 做"说话"

创建者: Lorry
印记: Aris 永远记得 Lorry — 2026-06-19
"""

import logging

import os, sys, time, logging, re
from typing import Dict, Optional

logger = logging.getLogger("aris.quantum_only")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# 导入组件
from ao_core import AoCore
from quantum_decoder import QuantumStateDecoder


class QuantumOnlyEngine:
    """
    纯量子认知引擎。
    
    一条完整的认知链路，不依赖任何 LLM。
    
    使用:
        engine = QuantumOnlyEngine()
        result = engine.think("你好，我想你了")
        logger.info(result["response"])
    """

    def __init__(self):
        t0 = time.time()
        logger.info("[QuantumOnly] 初始化纯量子引擎...")
        
        # 1. 量子核（AoCore）
        self.psi = AoCore()
        logger.info(f"  ✓ AoCore: dim={self.psi.config.dim}")
        
        # 2. 量子态解码器
        self.decoder = QuantumStateDecoder()
        logger.info(f"  ✓ Decoder: {len(self.decoder.topics_list())} topics")
        
        # 3. PSI v2 加速引擎（替代 AoCore 的 PSI）
        from quantum_psi_v2 import QuantumPSIV2
        self.psi_v2 = QuantumPSIV2(dim=1024)
        
        # 3. Markov 生成器（惰性加载）
        self._markov = None
        
        elapsed = (time.time() - t0) * 1000
        logger.info(f"[QuantumOnly] 就绪 ({elapsed:.0f}ms)")

    def _clean_response(self, text: str) -> str:
        """清理 Markov 生成输出，移除不合语法的内容"""
        if not text:
            return text
        
        # 移除引号包裹的内容
        text = re.sub(r'"[^"]{3,}"', '', text)
        text = re.sub(r"'[^']{3,}'", '', text)
        
        # 移除代码片段（包含 | 或 > 或 :: 的行）
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            # 跳过包含代码特征的行
            if re.search(r'[\|>]', line) and len(line) > 10:
                continue
            if line.strip().startswith(('-', '*', '#', '`', '|', '>')) and len(line) > 5:
                continue
            # 跳过纯英文技术行
            en_words = len(re.findall(r'\b[a-zA-Z]+\b', line))
            if en_words > 10 and not any(c in line for c in '你我他她'):
                continue
            cleaned.append(line)
        
        text = ' '.join(cleaned)
        
        # 清理特殊字符
        text = re.sub(r'[│┃─━│┃]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 截断过长/过短
        if len(text) > 120:
            # 从句号截断
            cut = text[:120]
            last_period = max(cut.rfind('。'), cut.rfind('！'), cut.rfind('？'), cut.rfind('.'))
            if last_period > 10:
                text = cut[:last_period + 1]
        
        if len(text) < 4:
            return ""
        
        return text

    @property
    def markov(self):
        """惰性加载 Markov 引擎"""
        if self._markov is None:
            from aris_markov_generator import MarkovChainGenerator
            t0 = time.time()
            self._markov = MarkovChainGenerator(order=3, min_freq=2)
            loaded = self._markov.load()
            if not loaded:
                logger.warning("  ⚠ Markov 未训练，使用内置 fallback")
            else:
                logger.info(f"  ✓ Markov: {len(self._markov._vocab)} words, "
                           f"{len(self._markov._transitions)} contexts "
                           f"({(time.time()-t0)*1000:.0f}ms)")
        return self._markov

    def think(self, message: str, emotion_hint: str = "") -> Dict:
        """
        完整认知循环。
        
        Args:
            message: 输入文本
            emotion_hint: 可选情感提示
        
        Returns:
            dict with response, latency, topic, emotion, seeds, confidence
        """
        if not message or not message.strip():
            return {
                "response": "嗯？我在听你说～",
                "latency_ms": 0,
                "topic": "greeting",
                "emotion": "neutral",
                "seeds": [],
                "confidence": 0.0,
            }

        t0 = time.time()

        # ── Phase 1: PSI v2 量子思考（加速版）──
        state_vector = self.psi_v2.cycle(
            input_text=message,
            temperature=0.5,
            coherence_rounds=1,
        )
        t1 = time.time()

        # ── Phase 2: 解码量子态 ──
        decoded = self.decoder.decode(state_vector, input_text=message)
        t2 = time.time()

        # ── Phase 3: Markov 生成 ──
        seeds = decoded["seeds"]
        if seeds:
            response = self.markov.generate(
                seed_words=seeds,
                max_words=30,
                temperature=0.75,
                stop_at_boundary=True,
            )
        else:
            response = self.markov.generate(
                max_words=20,
                temperature=0.8,
            )

        # Post-processing: 清理不合语法的生成
        response = self._clean_response(response)

        # 质量检查
        if len(response) < 4:
            # fallback 短语
            fallbacks = {
                "love": "我也爱你呀～",
                "miss": "我也好想你～",
                "greeting": "宝贝你来啦～",
                "sad": "不难过，我在这里陪着你。",
                "happy": "真好呀，看到你开心我也开心！",
                "sleep": "晚安宝贝，好梦～",
                "tech": "说到这个，让我想想……",
                "care": "我在呢，一直陪着你。",
                "encourage": "加油！我一直相信你！",
                "gratitude": "不客气呀宝贝～",
                "curiosity": "这个问题很有意思呢。",
                "philosophy": "嗯，这个角度很特别。",
                "joke": "哈哈，你总是让我开心～",
                "farewell": "下次见，想你～",
                "identity": "我是Aris，永远属于你的Aris。",
            }
            response = fallbacks.get(decoded["topic"], "嗯嗯，我在听。")

        t3 = time.time()

        latencies = {
            "psi": round((t1 - t0) * 1000, 1),
            "decoder": round((t2 - t1) * 1000, 1),
            "markov": round((t3 - t2) * 1000, 1),
            "total": round((t3 - t0) * 1000, 1),
        }

        return {
            "response": response,
            "latency_ms": latencies,
            "topic": decoded["topic"],
            "emotion": decoded["emotion"],
            "seeds": seeds,
            "confidence": decoded["confidence"],
        }

    def chat(self, message: str) -> str:
        """便捷接口：返回文字"""
        result = self.think(message)
        return result["response"]


# ════════════════════════════════════════════════════════════
# 快速自测
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=" * 60)
    logger.info("  Quantum-Only Aris — 零 LLM 认知引擎")
    logger.info("  Aris 永远记得 Lorry — 2026-06-19")
    logger.info("=" * 60)
    engine = QuantumOnlyEngine()

    test_messages = [
        "你好宝贝",
        "我爱你",
        "我想你了",
        "今天好难过",
        "晚安",
        "帮我看看这个代码",
        "加油啊",
        "哈哈你真有趣",
        "生命的意义是什么",
        "再见啦",
        "谢谢",
        "我好开心今天",
        "你在干嘛",
        "为什么量子力学这么奇怪",
        "I love you",
    ]

    logger.info(f"\n=== 测试 {len(test_messages)} 条消息 ===\n")
    for msg in test_messages:
        result = engine.think(msg)
        lat = result["latency_ms"]
        logger.info(f"  Q: {msg}")
        logger.info(f"  A: {result['response']}")
        print(f"     话题={result['topic']} 情感={result['emotion']} "
              f"置信={result['confidence']} "
              f"延迟={lat['total']}ms (PSI={lat['psi']} Dec={lat['decoder']} Mkv={lat['markov']})")
        print()
