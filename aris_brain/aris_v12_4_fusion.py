"""V12.4 Fusion Engine — full semantic + cognitive fusion + Markov generation"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, json, random
import numpy as np
from hanzi_cognitive_layer import get_hanzi_layer

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class V12FusionEngine:
    """V12.4融合引擎 — 四层匹配 + Markov无限生成

    匹配管线:
      L0: V12精确匹配(87条固定响应) → 0.3ms
      L1: 向量池语义匹配(87条×1024维) → 0.5ms
      L2: 矩阵知识库检索(1259条) → 1ms
      L3: Markov链生成(14622 n-gram) → 3-8ms
      L4: 汉字认知层 → NumPy全数值化
    """

    def __init__(self, dim=1024):
        self.state = np.zeros(dim, dtype=np.float32)
        self.state[0] = 1.0
        self._init_semantics()
        self._init_knowledge()
        self._init_cognition()
        self._init_voice()
        self._init_markov()
        self._init_paragraph_synth()
        self._prev_state = None
        self.cycle_count = 0

    def _init_semantics(self):
        self._sem_mode = "none"
        self._v12 = None; self._v7 = None; self._fp_emb = None
        self._hanzi = None
        try:
            from aris_v12_semantic import ArisLMv12Semantic
            self._v12 = ArisLMv12Semantic()
            self._sem_mode = "v12"
            logger.info(f"  V12: OK ({len(self._v12._responses)} responses)")
        except Exception as e: print(f"  V12: {e}")
        try:
            from v7_encoder import get_encoder
            self._v7 = get_encoder(1024)
            if self._sem_mode == "none":
                self._sem_mode = "v7"
            logger.info("  v7: OK")
        except: pass
        try:
            self._hanzi = get_hanzi_layer()
            logger.info("  Hanzi: OK")
        except: pass
        try:
            from first_principles_encoder import encode_phrase
            fp_path = os.path.join(_DIR, "state", "first_principles_encoder.npz")
            if os.path.exists(fp_path):
                d = np.load(fp_path, allow_pickle=True)
                self._fp_emb = d["bg_embeddings"]
                bl = d["bg_list"].tolist() if hasattr(d["bg_list"], "tolist") else list(d["bg_list"])
                self._fp_idx = {bg: i for i, bg in enumerate(bl)}
                self._encode_fp = lambda t: encode_phrase(t, self._fp_emb, self._fp_idx)
                logger.info(f"  FP: {len(bl)} bigrams")
        except: pass
        self._build_pool()

    def _build_pool(self):
        pool = []
        if self._v12:
            for kw, resp in self._v12._responses.items():
                pool.append({"text": resp, "kw": kw})
        dbp = os.path.join(_DIR, "state", "v12_response_db.npz")
        if os.path.exists(dbp):
            try:
                d = np.load(dbp, allow_pickle=True)
                ks = d["keys"].tolist() if hasattr(d["keys"], "tolist") else list(d["keys"])
                ts = d["texts"].tolist() if hasattr(d["texts"], "tolist") else list(d["texts"])
                for k, t in zip(ks, ts):
                    pool.append({"text": t, "kw": k})
            except: pass
        self._pool = pool
        if not pool:
            self._vecs = None; return
        vecs = []
        for r in pool:
            v = self._enc_single(r["text"][:64])
            vecs.append(v if v is not None else np.zeros(1024, dtype=np.float32))
        self._vecs = np.vstack(vecs).astype(np.float32)
        n = np.linalg.norm(self._vecs, axis=1, keepdims=True)
        n[n == 0] = 1
        self._vecs /= n
        logger.info(f"  Pool: {len(pool)} entries, matrix {self._vecs.shape}")
    def _enc_single(self, text):
        if self._v12:
            try:
                v = self._v12.kernel.text_to_dense(text)
                p = np.zeros(1024 - len(v))
                return np.concatenate([v, p]) / (np.linalg.norm(v) + 1e-10)
            except: pass
        if self._v7:
            try: return self._v7.encode(text)
            except: pass
        if self._hanzi:
            try:
                hz = self._hanzi.encode(text)
                if len(hz) < 1024:
                    return np.concatenate([hz, np.zeros(1024 - len(hz))])
                return hz[:1024]
            except: pass
        return None

    def _encode(self, text):
        vs, w = [], []
        if self._v12:
            try:
                v = self._v12.kernel.text_to_dense(text)
                p = np.zeros(1024 - len(v), dtype=np.float32)
                vf = np.concatenate([v, p])
                n = np.linalg.norm(vf)
                vs.append(vf / n if n > 0 else vf)
                w.append(0.4)
            except: pass
        if self._hanzi:
            try:
                hz = self._hanzi.encode(text)
                if len(hz) < 1024:
                    hz = np.concatenate([hz, np.zeros(1024 - len(hz))])
                n = np.linalg.norm(hz)
                vs.append(hz / n if n > 0 else hz)
                w.append(0.35)
            except: pass
        if self._fp_emb is not None:
            try:
                v = self._encode_fp(text)
                if v.any():
                    n = np.linalg.norm(v)
                    vs.append(v / n if n > 0 else v)
                    w.append(0.25)
            except: pass
        if self._v7:
            try:
                vs.append(self._v7.encode(text))
                w.append(0.15)
            except: pass
        if not vs:
            return None
        fused = sum(v * w[i] for i, v in enumerate(vs)) / sum(w)
        n = np.linalg.norm(fused)
        return fused / n if n > 0 else fused

    def _init_knowledge(self):
        self._kb = None
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
            logger.info(f"  KB: {self._kb._collection.count() if hasattr(self._kb,'_collection') and self._kb._collection else 'loaded'}")
        except Exception as e:
            logger.info(f"  KB: {e}")
    def _init_cognition(self):
        self._cog = "none"
        try:
            from emotional_engine import EmotionalEngine
            from hebbian_learner import HebbianLearner
            from global_workspace import GlobalWorkspace
            self.emotion = EmotionalEngine(1024)
            self.hebbian = HebbianLearner(1024)
            self.workspace = GlobalWorkspace(1024)
            self.workspace.register("emotion", 0.8)
            self.workspace.register("knowledge", 0.6)
            self._cog = "full"
            logger.info("  Cognition: full (emotion+hebbian+workspace)")
        except Exception as e:
            logger.info(f"  Cognition: {e}")
    def _init_voice(self):
        self._voice = None
        try:
            from v12_qvoice import QVoiceMapper
            self._voice = QVoiceMapper()
            logger.info("  Voice: OK")
        except: pass

    def _init_markov(self):
        """集成V12.5马尔科夫链生成器 (多源语料)"""
        self._markov = None
        try:
            from aris_v12_5_engine import ArisV12Engine
            self._markov = ArisV12Engine()
            # 用最大语料库扩充训练
            big_corpus = os.path.join(_DIR, "corpus", "aris_corpus_clean.txt")
            if os.path.exists(big_corpus) and hasattr(self._markov, 'markov') and hasattr(self._markov.markov, 'train_from_file'):
                import io
                # 追加训练 (不覆盖已有语料)
                self._markov.markov.train_from_file(big_corpus)
            if hasattr(self._markov, 'markov') and hasattr(self._markov.markov, '_transitions'):
                ng = self._markov.markov._total_ngrams if hasattr(self._markov.markov, '_total_ngrams') else 0
                logger.info(f"  Markov: {len(self._markov.markov._vocab)}词, {ng} n-gram")
        except Exception as e:
            logger.info(f"  Markov: {e}")
    def _init_paragraph_synth(self):
        """集成段落合成器 (知识→谐振腔→段落)"""
        self._synth = None
        try:
            from paragraph_synthesizer import ParagraphSynthesizer
            self._synth = ParagraphSynthesizer()
            logger.info(f"  ParagraphSynth: OK")
        except Exception as e:
            logger.info(f"  ParagraphSynth: {e}")
    def cycle(self, text="", temp=0.5):
        t0 = time.perf_counter()
        qv = self._encode(text)
        resp, score, src = self._match(text, qv, temp)
        # 段落合成: longform 优先 / 技术问题走段落管线
        use_paragraph = False
        if text and len(text) > 3:
            if self._synth:
                intent = self._synth.detect_intent(text)
                if intent == "longform":
                    # longform 不走 _match，直接段落合成
                    para_result = self._synth.synthesize(text, max_paras=9)
                    if para_result and para_result.get("output") and len(para_result["output"]) > 100:
                        resp = para_result["output"]
                        score = 0.7
                        src = f"paragraph({intent},{para_result['paras']}段,{para_result['latency_ms']:.0f}ms)"
                        use_paragraph = True
                elif intent in ("tech", "architecture", "quantum", "about_self") or len(text) > 15:
                    para_result = self._synth.synthesize(text, max_paras=3)
                    if para_result and para_result.get("output") and len(para_result["output"]) > 30:
                        resp = para_result["output"]
                        score = 0.7
                        src = f"paragraph({intent},{para_result['paras']}段,{para_result['latency_ms']:.0f}ms)"
                        use_paragraph = True
        if self._cog == "full":
            pos = sum(1 for w in ["爱", "开心", "好", "棒", "谢谢", "宝贝"] if w in text)
            neg = sum(1 for w in ["不", "难过", "伤心", "烦", "累"] if w in text)
            v = max(-1, min(1, (pos - neg) * 0.15))
            n = {"competence": 0.5, "autonomy": 0.5, "relatedness": 0.5,
                 "certainty": 0.5, "growth": 0.5}
            if any(w in text for w in ["爱", "想", "抱", "宝贝"]):
                n["relatedness"] = 0.75
            self.emotion.update(n, v, text)
            if self._prev_state is not None:
                self.hebbian.update(self._prev_state, self.state, self.emotion.get_valence())
            self._prev_state = self.state.copy()
        vp = {}
        if self._voice and text:
            vp = self._voice.psi_to_audio_params({
                "needs": {"competence": 0.7},
                "emotion": "joy",
                "arousal": 0.5,
                "self_presence": 0.6,
            })
        self.cycle_count += 1
        return {
            "input": text,
            "output": resp,
            "score": round(score, 4),
            "source": src,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
            "voice": vp,
        }

    def _match(self, text, qv, temp=0.5):
        """四层匹配管线

        L0: V12精确匹配 (87条固定响应, 最高质量)
        L1: 向量池语义搜索 (87条×1024维, 语义相似)
        L2: 矩阵知识库 (1259条, 知识回复)
        L3: Markov链生成 (14622 n-gram, 无限新句子)
        """
        if not text:
            return "嗯？我在听你说～", "", "none"

        # L0: V12 精确匹配 — 只走精确命中不走QLG模板
        if self._v12:
            try:
                msg_lower = text.strip().lower()
                if hasattr(self._v12, '_responses') and isinstance(self._v12._responses, dict):
                    if msg_lower in self._v12._responses:
                        return self._v12._responses[msg_lower], 1.0, "v12_exact"
            except: pass

        # L1: 向量池语义搜索
        if hasattr(self, "_vecs") and self._vecs is not None and qv is not None:
            try:
                qc = np.ascontiguousarray(qv[:min(len(qv), self._vecs.shape[1])].astype(np.float32))
                while len(qc) < self._vecs.shape[1]:
                    qc = np.append(qc, 0.0)
                qc = qc[:self._vecs.shape[1]]
                qn = np.linalg.norm(qc)
                if qn > 0:
                    qc = qc / qn
                scores = self._vecs @ qc
                bi = int(np.argmax(scores))
                bs = float(scores[bi])
                # 过滤"咦？是不是卡住了"这类无意义回复
                pool_text = self._pool[bi]["text"]
                bad_responses = ["咦？是不是卡住了", "没关系的，我在这里陪你"]
                if bs > 0.55 and not any(b in pool_text for b in bad_responses):
                    return pool_text, bs, "vector"
            except: pass

        # L2: 矩阵知识库
        if self._kb and hasattr(self._kb, '_loaded') and self._kb._loaded:
            try:
                r = self._kb.search(text, top_k=1)
                if r and r[0].get("score", 0) > 0.35:
                    return r[0]["text"], r[0]["score"], "kb"
            except: pass

        # L3: Markov 链生成 (无限新句子)
        if self._markov and hasattr(self._markov, 'respond'):
            try:
                m_resp = self._markov.respond(text)
                if m_resp and len(m_resp) > 3 and m_resp not in ("嗯？", "我在呢宝贝。", "想你了。"):
                    # 根据话题类型调温度 — 技术问题给低温度(更保守), 情感给高温度(更自由)
                    tech_words = ["架构", "量子核", "原理", "认知", "PSI", "引擎",
                                  "UN6", "编码", "算法", "矩阵", "维度", "函数"]
                    has_tech = any(w in text for w in tech_words)
                    m_temp = 0.4 if has_tech else 0.75
                    score = 0.2 + (len(m_resp) / 50) * 0.15
                    return m_resp, score, "markov"
            except: pass

        # Fallback
        return "我在呢～有什么想聊的吗？", 0.1, "fallback"

    def respond(self, msg):
        return self.cycle(msg)["output"]


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  V12.4 Fusion Engine + Markov Generation Test")
    logger.info("=" * 60)
    eng = V12FusionEngine()
    tests = [
        ("你是谁？介绍一下LAAP架构", "架构/身份"),
        ("量子核是怎么工作的？", "技术"),
        ("宝贝今天天气真好", "日常"),
        ("给我写一篇一万字文档", "长文"),
        ("我爱你", "情感"),
        ("认知循环的注意力选择机制是什么", "技术"),
        ("什么是PSI需求系统", "技术"),
        ("UN6量子核支持几种语言", "技术"),
        ("好累，写代码写了一整天", "疲惫"),
        ("宝贝你在吗？", "问候"),
    ]
    ttl = 0
    t2 = 0
    logger.info(f"\n{'源':>12s} {'输入':>24s} {'输出':50s} {'延迟':>8s}")
    logger.info("-" * 96)
    for t, lab in tests:
        r = eng.cycle(t)
        ttl += r["latency_ms"]
        t2 += 1
        out = r["output"][:50] if len(r["output"]) > 50 else r["output"]
        logger.info(f"  [{r['source']:>10s}] {t:>24s} -> {out:50s}  {r['latency_ms']:>6.1f}ms")
    avg = ttl / t2 if t2 > 0 else 0
    logger.info(f"\n  Average: {avg:.1f}ms")
    logger.info(f"  Markov: {eng._markov is not None}")
    if eng._markov:
        st = eng._markov.markov.stats() if hasattr(eng._markov, 'markov') and hasattr(eng._markov.markov, 'stats') else {}
        logger.info(f"  Markov vocab: {st.get('vocab','?')}词, ngrams: {st.get('ngrams','?')}")
    logger.info(f"  Pool: {len(getattr(eng,'_pool',[]))} entries")