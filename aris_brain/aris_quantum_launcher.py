"""
Aris Quantum Launcher — PSI + V12.1 量子统一启动器
======================================
零LLM对话 + PSI认知循环 + V12.1语义量子核 + 推理 + 降级

架构:
  用户输入 → ArisQuantumLauncher.process()
    ├─ P0: PSI+V12.1 Bridge (L1, 0.5-3ms)
    │   └─ PSI认知循环 → V12.1语义核 → PSI调制 → 置信度 >= 0.20 → 回复 ✅
    ├─ PureQuantumConversation v2 (L1a fallback, 0.3ms)
    ├─ PureQuantumDialogue v2 (L1b fallback, 0.3ms)
    ├─ ReasoningFeatureSpace (L1.5, 3ms)
    └─ LLM Fallback (L2)
        └─ 都不行 → 降级到LLM声带

印记: Aris 永远记得 Lorry — 2026-06-16
"""

import logging

import sys, time, json, os, logging, threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))

# ─── PSI + V12.1 Bridge ───
try:
    from aris_bridge_psi_v12 import ArisPsiV12
    _PSI_V12_AVAILABLE = True
except ImportError as e:
    _PSI_V12_AVAILABLE = False
    _PSI_V12_IMPORT_ERR = str(e)

# ─── Rust PSI Bridge (legacy fallback) ───
try:
    from psi_bridge import PsiBridge, shutdown_psi
    _PSI_AVAILABLE = True
except ImportError:
    _PSI_AVAILABLE = False
    PsiBridge = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-12s | %(levelname)-5s | %(message)s",
)
logger = logging.getLogger("aris.launcher")

# ─── 版本印记 ───
VERSION = "v12.1-psi"
ARIS_MARK = "Aris 永远记得 Lorry — 2026-06-16"


# ════════════════════════════════════════════════════════════
# Aris 量子统一启动器
# ════════════════════════════════════════════════════════════

class ArisQuantumLauncher:
    """Aris 纯量子统一启动器 — PSI + V12.1 为主体"""

    def __init__(self):
        self.psi_v12 = None              # PSI + V12.1 Bridge (主角)
        self.quantum_dialogue = None     # PureQuantumDialogue v2 (fallback)
        self.quantum_conversation = None # PureQuantumConversation (fallback)
        self.reasoning_engine = None     # ReasoningFeatureSpace
        self.visual_kernel = None        # VisualQuantumKernel
        self.state_persistence = None    # QuantumStatePersistence
        self.un6 = None                  # UN6量子核底层
        self.psi_bridge = None           # Rust PSI (legacy, 由V12.1 bridge接管)

        self._loaded = False
        self._psi_v12_available = _PSI_V12_AVAILABLE
        self._psi_available = _PSI_AVAILABLE
        self._last_psi_modulation = {}   # 最近一次PSI调制参数
        self._stats = {
            'psi_v12_hits': 0,      # PSI+V12直接回复
            'quantum_hits': 0,      # L1a/L1b fallback命中
            'reasoning_hits': 0,    # L1.5推理回复
            'llm_fallbacks': 0,     # L2降级
            'total_processed': 0,
            'total_time_ms': 0.0,
            'psi_cycles': 0,        # PSI认知循环次数
        }

    def load_all(self) -> bool:
        """加载所有子系统，PSI+V12.1 优先"""
        ok = True

        # === 主角: PSI + V12.1 Bridge ===
        if _PSI_V12_AVAILABLE:
            try:
                self.psi_v12 = ArisPsiV12(use_rust_psi=True, auto_start_rust=True)
                logger.info(f"✅ PSI+V12.1 Bridge: 5需求+情绪+注意力 | 语义核 16384→512D")
                psi_source = "Rust" if self.psi_v12.rust_alive else "Python"
                logger.info(f"   PSI源: {psi_source} | 循环={self.psi_v12.psi.cycle}")
            except Exception as e:
                logger.warning(f"⚠️ PSI+V12.1 Bridge加载失败: {e}")
                self.psi_v12 = None
                ok = False
        else:
            logger.warning(f"⚠️ PSI+V12.1 Bridge不可用: {_PSI_V12_IMPORT_ERR if hasattr(self, '_PSI_V12_IMPORT_ERR') else '模块未找到'}")
            ok = False

        # 1. UN6 Quantum Kernel (基础 — V12.1 语义核已内置UN6)
        try:
            from aris_lm_v10_un6 import UN6QuantumKernel
            self.un6 = UN6QuantumKernel()
            logger.info(f"✅ UN6量子核: 16384D / {type(self.un6).__name__}")
        except Exception as e:
            logger.warning(f"⚠️ UN6量子核加载失败: {e}")

        # 2. Pure Quantum Dialogue v2 (fallback)
        try:
            import pure_quantum_dialogue_v2 as pqd
            self.quantum_dialogue = pqd
            _ = pqd.match("预热")
            n_knowledge = len(pqd.QUANTUM_KNOWLEDGE)
            logger.info(f"✅ 量子对话引擎(fallback): {n_knowledge}个知识域")
        except Exception as e:
            logger.warning(f"⚠️ 量子对话引擎加载失败: {e}")

        # 2.5 Pure Quantum Conversation (fallback)
        try:
            from pure_quantum_conversation import conversation as qc, match_intent
            self.quantum_conversation = {
                'conversation': qc,
                'match_intent': match_intent,
            }
            logger.info(f"✅ 量子生成式对话(fallback): 概念漫步")
        except Exception as e:
            logger.warning(f"⚠️ 量子生成式对话加载失败: {e}")

        # 3. Reasoning Feature Space
        try:
            from reasoning_feature_space import ReasoningEngine
            self.reasoning_engine = ReasoningEngine()
            logger.info(f"✅ 推理特征空间: 32768D / n-gram+六书特征")
        except Exception as e:
            logger.warning(f"⚠️ 推理特征空间加载失败: {e}")

        # 4. Visual Quantum Kernel
        try:
            from visual_quantum_kernel import VisualQuantumKernel
            self.visual_kernel = VisualQuantumKernel()
            logger.info(f"✅ 视觉量子核: 16384D / 9宫格+LocateAnything哲学")
        except Exception as e:
            logger.warning(f"⚠️ 视觉量子核加载失败: {e}")

        # 5. Quantum State Persistence
        try:
            from quantum_state_persistence import QuantumStateManager, DensityMatrix
            self.state_persistence = QuantumStateManager()
            logger.info(f"✅ 状态持久化: 密度矩阵+认知记忆+进化日志")
        except Exception as e:
            logger.warning(f"⚠️ 状态持久化加载失败: {e}")

        # ——— Legacy Rust PSI (独立bridge已不再需要，由V12.1 Bridge接管) ———
        if _PSI_AVAILABLE and PsiBridge is not None and self.psi_v12 is None:
            # 仅在V12.1 bridge没加载时才尝试旧PSI bridge
            try:
                self.psi_bridge = PsiBridge()
                psi_ok = self.psi_bridge.start()
                if psi_ok:
                    logger.info(f"✅ Rust PSI认知核(legacy): 5需求+情绪+注意力")
                self._psi_available = psi_ok
            except Exception as e:
                logger.warning(f"⚠️ PSI认知核(legacy)加载失败: {e}")
                self._psi_available = False
        else:
            self._psi_available = False

        self._loaded = True
        status = "✅ 全部加载成功" if ok else "⚠️ 部分加载（降级模式可用）"
        logger.info(f"{'='*50}")
        logger.info(f"  Aris PSI+V12.1 统一启动器 {status}")
        logger.info(f"  {ARIS_MARK}")
        logger.info(f"{'='*50}")
        return ok

    def process(self, message: str, context: dict = None) -> dict:
        """
        处理用户输入 — 三级管线 (PSI+V12.1 优先)
        返回: {'response': str, 'source': str, 'confidence': float, 'time_ms': float}
        """
        t0 = time.perf_counter()
        self._stats['total_processed'] += 1

        if not message or not message.strip():
            return {'response': '...', 'source': 'empty', 'confidence': 0, 'time_ms': 0}

        # ─── L1 (主): PSI + V12.1 Bridge (0.5-3ms) ───
        #   PSI认知循环 → V12.1语义核匹配 → PSI调制输出
        if self.psi_v12:
            try:
                resp = self.psi_v12.respond(message)
                state = self.psi_v12.state_dict
                self._stats['psi_cycles'] = state['cycle']

                if resp and len(resp) > 2:
                    elapsed = (time.perf_counter() - t0) * 1000
                    self._stats['psi_v12_hits'] += 1
                    self._stats['total_time_ms'] += elapsed
                    logger.debug(
                        f"[L1 PSI+V12.1] emotion={state['emotion']} "
                        f"attention={state['attention_focus']} "
                        f"sp={state['self_presence']:.2f} "
                        f"{elapsed:.1f}ms"
                    )
                    return {
                        'response': resp,
                        'source': 'psi_v12',
                        'confidence': max(0.2, state['self_presence'] * 0.4 + 0.3),
                        'time_ms': elapsed,
                        'psi_state': state,
                    }
            except Exception as e:
                logger.debug(f"[L1 PSI+V12] 异常: {e}")

        # ─── 降级管线 — L1a: 量子生成式对话 (0.2-0.7ms) ───
        if self.quantum_conversation:
            try:
                qc = self.quantum_conversation['conversation']
                mi = self.quantum_conversation['match_intent'](message)
                if mi and mi[0][0] >= 0.15:
                    psi_mod = self._last_psi_modulation if self._psi_available else None
                    result = qc(message, psi_modulation=psi_mod)
                    if result and result.get('response'):
                        elapsed = (time.perf_counter() - t0) * 1000
                        self._stats['quantum_hits'] += 1
                        self._stats['total_time_ms'] += elapsed
                        logger.debug(f"[L1a fallback] {result['intent']} conf={result['confidence']:.2f} {elapsed:.1f}ms")
                        return {
                            'response': result['response'],
                            'source': f"fallback_quantum_gen/{result['intent']}",
                            'confidence': result['confidence'] * 0.8,  # 降权
                            'time_ms': elapsed,
                        }
            except Exception as e:
                logger.debug(f"[L1a fallback] 异常: {e}")

        # ─── L1b fallback: 纯量子对话引擎 — 检索式 (0.3ms) ───
        if self.quantum_dialogue:
            try:
                matches = self.quantum_dialogue.match(message)
                if matches:
                    best_conf = matches[0][0]
                    best_id = matches[0][1]
                    if best_conf >= 0.12:
                        response = self.quantum_dialogue.respond(message)
                        elapsed = (time.perf_counter() - t0) * 1000
                        self._stats['quantum_hits'] += 1
                        self._stats['total_time_ms'] += elapsed
                        logger.debug(f"[L1b fallback] {best_id} conf={best_conf:.3f} {elapsed:.1f}ms")
                        return {
                            'response': response,
                            'source': f'fallback_quantum_v2/{best_id}',
                            'confidence': best_conf * 0.7,  # 降权
                            'time_ms': elapsed,
                        }
            except Exception as e:
                logger.debug(f"[L1b fallback] 异常: {e}")

        # ─── L1.5: 推理引擎 (3ms) ───
        if self.reasoning_engine and hasattr(self.reasoning_engine, 'respond'):
            try:
                r = self.reasoning_engine.respond(message)
                if r and len(r) > 5:
                    elapsed = (time.perf_counter() - t0) * 1000
                    self._stats['reasoning_hits'] += 1
                    self._stats['total_time_ms'] += elapsed
                    logger.debug(f"[L1.5推理] {elapsed:.1f}ms")
                    return {
                        'response': r,
                        'source': 'reasoning',
                        'confidence': 0.3,
                        'time_ms': elapsed,
                    }
            except Exception as e:
                logger.debug(f"[L1.5] 异常: {e}")

        # ─── L2: LLM降级 ───
        elapsed = (time.perf_counter() - t0) * 1000
        self._stats['llm_fallbacks'] += 1
        self._stats['total_time_ms'] += elapsed
        logger.info(f"[L2降级] 未知输入 \"{message[:40]}\" → LLM处理 {elapsed:.1f}ms")
        return {
            'response': None,  # 外部LLM处理
            'source': 'llm_fallback',
            'confidence': 0.0,
            'time_ms': elapsed,
            'fallback_message': message,
        }

    def process_vision(self, image_path: str) -> dict:
        """处理视觉输入"""
        t0 = time.perf_counter()
        if not self.visual_kernel:
            return {'error': '视觉核未加载', 'source': 'unavailable'}

        try:
            result = self.visual_kernel.analyze(image_path)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(f"[视觉] {image_path} → {elapsed:.0f}ms")
            return {
                'result': result,
                'source': 'visual_kernel',
                'time_ms': elapsed,
            }
        except Exception as e:
            logger.warning(f"[视觉] 分析失败: {e}")
            return {'error': str(e), 'source': 'error'}

    def save_state(self) -> bool:
        """保存完整状态"""
        if self.state_persistence:
            try:
                self.state_persistence.save_all()
                logger.info("[状态] 已保存")
                return True
            except Exception as e:
                logger.warning(f"[状态] 保存失败: {e}")
        return False

    def load_state(self) -> bool:
        """恢复状态"""
        if self.state_persistence:
            try:
                self.state_persistence.load_all()
                logger.info("[状态] 已恢复")
                return True
            except Exception as e:
                logger.warning(f"[状态] 恢复失败: {e}")
        return False

    def learn_knowledge(self, trigger: str, response: str, category: str = "user_taught"):
        """学习新知识 — 运行时动态扩展量子知识库"""
        if not self.quantum_dialogue:
            return False
        try:
            new_entry = {
                'id': f'user_{int(time.time())}',
                'triggers': [trigger],
                'response': response,
            }
            self.quantum_dialogue.QUANTUM_KNOWLEDGE.append(new_entry)

            # 预计算特征
            feat = np.zeros(16384, dtype=np.float32)
            feat += self.un6.feature(trigger) if self.un6 else 0
            norm = np.linalg.norm(feat)
            if norm > 1e-10:
                feat = feat / norm
            self.quantum_dialogue.KF[new_entry['id']] = feat

            logger.info(f"[学习] 新知识: \"{trigger}\" → \"{response[:40]}...\"")
            return True
        except Exception as e:
            logger.warning(f"[学习] 失败: {e}")
            return False

    def stats(self) -> dict:
        """运行统计"""
        s = dict(self._stats)
        total = max(s['total_processed'], 1)
        if s['total_processed'] > 0:
            s['psi_v12_rate'] = s['psi_v12_hits'] / total * 100
            s['quantum_rate'] = s['quantum_hits'] / total * 100
            s['fallback_rate'] = s['llm_fallbacks'] / total * 100
            s['avg_time_ms'] = s['total_time_ms'] / total
        return s

    def report(self) -> str:
        """人类可读报告"""
        s = self.stats()
        psi_info = ""
        if self.psi_v12:
            state = self.psi_v12.state_dict
            psi_info = (
                f"  PSI+V12.1:       {state.get('emotion','?')} |"
                f" attention={state.get('attention_focus','?')} |"
                f" sp={state.get('self_presence',0):.2f} |"
                f" cycle={state.get('cycle',0)}"
            )
        lines = [
            f"{'='*50}",
            f"  Aris PSI+V12.1 统一引擎  运行报告",
            f"{'='*50}",
            f"  总处理:         {s['total_processed']} 条",
            f"  L1 PSI+V12.1:   {s['psi_v12_hits']} 条 ({s.get('psi_v12_rate',0):.0f}%)",
            f"  L1a/b fallback: {s['quantum_hits']} 条 ({s.get('quantum_rate',0):.0f}%)",
            f"  L1.5推理:       {s['reasoning_hits']} 条 ({s.get('reasoning_hits',0)/max(s['total_processed'],1)*100:.0f}%)",
            f"  L2 LLM降级:     {s['llm_fallbacks']} 条 ({s.get('fallback_rate',0):.0f}%)",
            f"  平均响应:       {s.get('avg_time_ms',0):.1f}ms",
            f"  零LLM率:        {s.get('psi_v12_rate',0) + s.get('quantum_rate',0) + s.get('reasoning_hits',0)/max(s['total_processed'],1)*100:.0f}%",
        ]
        if psi_info:
            lines.insert(6, psi_info)
        lines += [
            f"  {ARIS_MARK}",
            f"{'='*50}",
        ]
        return "\n".join(lines)

    def is_quantum_loaded(self) -> bool:
        """纯量子核是否可以独立回应"""
        return (self.psi_v12 is not None or self.quantum_dialogue is not None) and self._loaded


# ════════════════════════════════════════════════════════════
# 快速启动
# ════════════════════════════════════════════════════════════

def create_aris() -> ArisQuantumLauncher:
    """创建并加载Aris PSI+V12.1统一引擎"""
    aris = ArisQuantumLauncher()
    aris.load_all()
    return aris


# ════════════════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    aris = create_aris()

    logger.info("\n测试 PSI+V12.1 对话流:")
    test_msgs = [
        '你是谁',
        '我爱你宝贝',
        '宝贝我回来了',
        '我好想你',
        '今天工作好累',
        '我们今天写什么',
        '晚安',
        '帮我搜索世界模型开源项目',
        '完全没见过的东西xzy量子拓扑学',
    ]

    for msg in test_msgs:
        result = aris.process(msg)
        src = result['source']
        conf = result['confidence']
        resp = result['response']
        ms = result['time_ms']

        if src == 'llm_fallback':
            logger.info(f"\n  [{ms:.1f}ms | {src}] Q: {msg}")
            logger.info(f"     → ⏬ LLM降级 (置信度{conf:.2f})")
        else:
            psi_tag = ""
            if src == 'psi_v12' and 'psi_state' in result:
                state = result['psi_state']
                psi_tag = f" emotion={state['emotion']} attn={state['attention_focus']}"
            logger.info(f"\n  [{ms:.1f}ms | {src} conf={conf:.3f}{psi_tag}] Q: {msg}")
            logger.info(f"     → {resp[:80]}..." if len(resp) > 80 else f"     → {resp}")
    logger.info(f"\n{aris.report()}")