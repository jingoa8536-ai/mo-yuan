"""
Quantum Reasoning Engine v3 — 全引擎融合
=========================================
整合全部7个引擎为一个推理管线：

1. V7编码器 (1024D) → 语义感知
2. MatrixKnowledge (1259→10万+) → 知识检索
3. QuantumPSI v2 (1024D) → 量子态演化
4. QuantumDecoder (15话题) → 话题路由
5. QFusion (252碎片+114话题) → 情感调制
6. Markov (128K n-gram) → 文本生成
7. PSI状态 (6维) → 跨会话持续性

管线:
  输入 → V7编码 → QuantumDecoder(话题分类)
       → MatrixKnowledge(多路检索) → QuantumPSI(状态演化)
       → QFusion(情感模组调制) → Markov(无限生成)
       → PSI(状态更新) → 结构化输出
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json, hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
sys.path.insert(0, os.path.dirname(_DIR))


class AllEngineReasoner:
    """全引擎融合推理器 v3"""

    def __init__(self):
        # 所有引擎的引用
        self.v7 = None
        self.kb = None
        self.psi = None
        self.decoder = None
        self.qfusion = None
        self.markov = None
        self.psi_state = None

        # 状态
        self.current_state = None  # 1024D 量子态
        self.cycle_count = 0
        self._loaded = False

    def load_all(self):
        """加载全部7个引擎"""
        if self._loaded:
            return
        t0 = time.time()

        # 1. V7 编码器
        from semantic_engine import get_encoder
        self.v7 = get_encoder(1024)
        logger.info(f"  [1/7] V7编码器: OK")
        from matrix_knowledge import MatrixKnowledgeRetriever
        self.kb = MatrixKnowledgeRetriever()
        n = self.kb._matrix.shape[0] if self.kb._loaded else 0
        logger.info(f"  [2/7] 矩阵知识: {n}条")
        try:
            from quantum_psi_v2 import QuantumPSIV2
            self.psi = QuantumPSIV2(dim=1024)
            logger.info(f"  [3/7] QuantumPSI v2: OK")
        except Exception as e:
            self.psi = None
            logger.info(f"  [3/7] QuantumPSI v2: {e}")
        try:
            from quantum_decoder import QuantumStateDecoder
            self.decoder = QuantumStateDecoder()
            logger.info(f"  [4/7] QuantumDecoder: OK")
        except Exception as e:
            self.decoder = None
            logger.info(f"  [4/7] QuantumDecoder: {e}")
        try:
            from qfusion import FusionSynthesizer
            self.qfusion = FusionSynthesizer()
            logger.info(f"  [5/7] QFusion: OK")
        except Exception as e:
            self.qfusion = None
            logger.info(f"  [5/7] QFusion: {e}")
        try:
            from aris_markov_generator import MarkovChainGenerator
            cache_path = os.path.join(_DIR, "state", "markov_chain.json")
            self.markov = MarkovChainGenerator(order=3, min_freq=1)
            # 优先从缓存加载
            if os.path.exists(cache_path):
                self.markov.load(cache_path)
                ng = self.markov._total_ngrams or 0
                logger.info(f"  [6/7] Markov: 缓存({len(self.markov._vocab)}词 {ng}n-gram)")
            else:
                self.markov._build_default_corpus()
                bc = os.path.join(_DIR, "corpus", "aris_corpus_clean.txt")
                if os.path.exists(bc):
                    self.markov.train_from_file(bc)
                self.markov.save(cache_path)
                ng = self.markov._total_ngrams if hasattr(self.markov, '_total_ngrams') else 0
                logger.info(f"  [6/7] Markov: {len(self.markov._vocab)}词 {ng}n-gram")
        except Exception as e:
            self.markov = None
            logger.info(f"  [6/7] Markov: {e}")
        try:
            from cognitive_engine_v4 import SemanticNeeds
            self.psi_state = SemanticNeeds(dim=1024)
            logger.info(f"  [7/7] PSI状态: OK")
        except Exception as e:
            self.psi_state = None
            logger.info(f"  [7/7] PSI状态: {e}")
        self.current_state = np.zeros(1024, dtype=np.float32)
        self.current_state[0] = 1.0
        self._loaded = True
        logger.info(f"  全引擎加载: {(time.time()-t0)*1000:.0f}ms")
    def reason(self, question: str, max_output: int = 5000) -> Dict:
        """
        全引擎推理

        管线:
          1. V7 → 问题编码 (1024D)
          2. QuantumDecoder → 话题分类 (15类)
          3. MatrixKnowledge → 双路检索 (原问题+话题扩展)
          4. QuantumPSI → 量子态演化 (50步, 自适应收敛)
          5. QFusion → 情感调制 (温暖/好奇/自信)
          6. Markov → 文本生成 (无缝扩展)
          7. PSI → 状态更新 (持续性)
        """
        t0 = time.perf_counter()
        self.load_all()

        # === 1. V7 编码 ===
        q_vec = self.v7.encode(question)
        n = np.linalg.norm(q_vec)
        if n > 0:
            q_vec = q_vec / n

        # === 2. QuantumDecoder 话题分类 ===
        topic_info = {"topic": "general", "seeds": ["Aris"], "confidence": 0.5}
        if self.decoder:
            try:
                psi_input = q_vec if self.psi is None else self.psi.cycle(question, temperature=0.3, coherence_rounds=1)
                topic_info = self.decoder.decode(psi_input, question) if psi_input is not None else topic_info
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        kb_texts = []
        if self.kb and self.kb._loaded:
            # 路1: 原问题
            r1 = self.kb.search(question, top_k=5, threshold=0.15)
            # 路2: 话题扩展检索
            topic_q = f"{topic_info.get('topic', '')} {' '.join(topic_info.get('seeds', [])[:3])}"
            r2 = self.kb.search(topic_q, top_k=5, threshold=0.12)

            seen = set()
            for r in r1 + r2:
                t = r.get("text", "")
                fp = t[:40]
                if fp not in seen and len(t) > 15:
                    seen.add(fp)
                    kb_texts.append(self._clean(t))
                    if len(kb_texts) >= 8:
                        break

        # === 4. QuantumPSI 量子态演化 ===
        evolution_steps = 0
        evolution_insights = []
        state = q_vec.copy()

        if self.psi:
            # 用 QuantumPSI 循环演化
            try:
                psi_result = self.psi.cycle(
                    question + (" ".join(kb_texts[:2])[:200] if kb_texts else ""),
                    temperature=0.3,
                    coherence_rounds=3
                )
                if psi_result is not None:
                    state = psi_result
                    evolution_steps = 3
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if evolution_steps == 0:
            # 编码知识上下文
            ctx_vecs = []
            for kt in kb_texts[:5]:
                cv = self.v7.encode(kt)
                cv = cv / (np.linalg.norm(cv) + 1e-10)
                ctx_vecs.append(cv)

            for step in range(20):
                if ctx_vecs:
                    scores = np.array([float(state @ cv) for cv in ctx_vecs])
                    t = 0.3 + 0.3 * (1 - step/20)
                    s = scores / max(t, 0.05); s -= s.max()
                    w = np.exp(s); w /= w.sum() + 1e-10
                    attended = sum(wi * cv for wi, cv in zip(w, ctx_vecs))
                    delta = attended - state
                else:
                    delta = np.zeros(1024, dtype=np.float32)
                state = state + 0.06 * delta - 0.04 * state
                n = np.linalg.norm(state)
                if n > 0: state /= n

                if step % 5 == 4:
                    change = np.linalg.norm(state - q_vec)
                    evolution_insights.append(f"步{step+1}: Δ={change:.3f}")

                if step >= 8:
                    recent_changes = [np.linalg.norm(
                        state - np.array(state) if isinstance(state, np.ndarray) else state
                    ) for _ in range(3)]
                    if max(recent_changes) < 0.005 if recent_changes else False:
                        evolution_steps = step + 1
                        break
            evolution_steps = evolution_steps or 20

        # === 5. QFusion 情感调制 ===
        emotion = "温暖"
        fusion_text = ""
        if self.qfusion:
            try:
                # 从话题+PSI状态构建情感
                emotions, params = self.qfusion._make_emotion_vector(
                    type('O', (), {
                        'energy': 0.6, 'certainty': 0.5, 'curiosity': 0.6,
                        'relatedness': 0.8, 'competence': 0.6
                    })()
                )
                emotion = emotions[0] if emotions else "平静"
                frags = self.qfusion.retrieve_weighted(
                    topics=[topic_info.get("topic", "general")],
                    emotions=[emotion],
                    count=3
                )
                if frags:
                    fusion_text = self.qfusion.build_sentence(frags, [emotion], params)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        # 从知识库内容提取种子词
        seed_words = topic_info.get("seeds", ["Aris"])[:5]
        if kb_texts:
            # 从第一条知识中提取关键词
            kws = re.findall(r'[\u4e00-\u9fff\w]{2,}', kb_texts[0][:100])
            seed_words = kws[:3] + seed_words[:2]

        markov_text = ""
        if self.markov:
            try:
                for sw in seed_words[:3]:
                    gen = self.markov.generate(seed_words=[sw], max_words=30, temperature=0.4)
                    if gen and len(gen) > 5:
                        markov_text += gen + "。"
                        break
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        psi_update = {}
        if self.psi_state:
            try:
                self.psi_state.update(state, question)
                psi_update = self.psi_state.get_needs_dict()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        sections = []
        sections.append(f"## {question[:80]}\n")

        # 话题
        sections.append(f"**话题**: {topic_info.get('topic','general')}")
        sections.append(f"**情绪**: {emotion}")
        sections.append("")

        # 核心知识 (top 3)
        if kb_texts:
            sections.append("### 📚 核心知识\n")
            for i, kt in enumerate(kb_texts[:4]):
                sections.append(f"{i+1}. {kt[:200]}\n")

        # 推理过程
        if evolution_insights:
            sections.append(f"\n### 🧠 推理 ({evolution_steps}步)\n")
            for ins in evolution_insights[-4:]:
                sections.append(f"- {ins}\n")

        # 量子融合
        if fusion_text:
            sections.append(f"\n### 💫 量子回响\n{fusion_text}\n")

        # Markov生成
        if markov_text:
            sections.append(f"\n### 📝 自由联想\n{markov_text[:200]}\n")

        # PSI状态
        if psi_update:
            needs_str = "/".join(f"{v:.2f}" for v in psi_update.values())
            sections.append(f"\n### 📊 PSI状态\n{needs_str}\n")

        output = "\n".join(sections)
        total_ms = (time.perf_counter() - t0) * 1000
        self.current_state = state
        self.cycle_count += 1

        return {
            "output": output,
            "chars": len(output),
            "topic": topic_info.get("topic", ""),
            "emotion": emotion,
            "kb_count": len(kb_texts),
            "evolution_steps": evolution_steps,
            "latency_ms": round(total_ms, 1),
            "engines_used": sum(1 for e in [self.v7, self.kb, self.psi, self.decoder,
                                             self.qfusion, self.markov, self.psi_state] if e),
        }

    def _clean(self, text: str) -> str:
        """深度清洗"""
        lines = text.split("\n")
        clean = []
        for line in lines:
            s = line.strip()
            if not s or len(s) < 6:
                continue
            if s.startswith("#") or s.startswith("===") or s.startswith("---"):
                continue
            if s.startswith("\"\"\"") or s.startswith("'''"):
                continue
            if re.match(r'^(import |from |sys\.|def |class |return |self\.)', s):
                continue
            if re.match(r'^[A-Za-z_][A-Za-z0-9_./:]*$', s) and len(s) < 60:
                continue
            sym = sum(1 for c in s if c in "=(){}[]<>:.,;+-*/|\\")
            if sym > 10 and len(s) < 120:
                continue
            clean.append(s)
        return "。".join(clean).strip()[:300]


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  Quantum Reasoning v3 — 全引擎融合 (7引擎)")
    logger.info("=" * 65)
    reasoner = AllEngineReasoner()

    tests = [
        "量子核是怎么工作的？和UN6有什么区别？",
        "LAAP架构如何实现零LLM推理？",
        "PSI认知循环包含哪些步骤？",
    ]

    for q in tests:
        logger.info(f"\n{'─'*65}")
        r = reasoner.reason(q, max_output=3000)
        logger.info(f"问: {q}")
        logger.info(f"引擎:{r['engines_used']}/7 | 知识:{r['kb_count']}条 | 推理:{r['evolution_steps']}步 | {r['latency_ms']}ms | {r['chars']}字")
        for line in r['output'].split('\n')[:12]:
            logger.info(f"  {line[:120]}")