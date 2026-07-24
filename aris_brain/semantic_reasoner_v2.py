"""
Quantum Reasoning Engine v2.1 — 语义内核驱动 + 深度清洗
=========================================================
直接在知识库的向量空间中进行链式推理，不依赖 LLM。
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json
import numpy as np
from typing import Dict, List, Optional, Tuple

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class SemanticReasoner:
    """语义驱动的量子推理引擎 v2.1"""

    def __init__(self):
        self._v7 = None
        self._kb = None
        self._un6 = None
        self._v12 = None
        self._loaded = False

    def _lazy(self):
        if self._loaded:
            return
        from semantic_engine import get_encoder
        self._v7 = get_encoder(1024)
        from matrix_knowledge import MatrixKnowledgeRetriever
        self._kb = MatrixKnowledgeRetriever()
        try:
            from aris_lm_v10_un6 import UN6QuantumKernel
            self._un6 = UN6QuantumKernel()
        except: self._un6 = None
        try:
            from aris_v12_semantic import ArisLMv12Semantic
            self._v12 = ArisLMv12Semantic()
        except: self._v12 = None
        self._loaded = True

    def _encode(self, text: str) -> np.ndarray:
        v = self._v7.encode(text)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def _strip_code(self, text: str) -> str:
        """深度清洗——去除代码行、标题线、路径等"""
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
            # 跳过 import/from/def/class/return/self.
            if re.match(r'^(import |from |sys\.|def |class |return |self\.)', s):
                continue
            # 跳过纯英文标识符或路径
            if re.match(r'^[A-Za-z_][A-Za-z0-9_./:]*$', s) and len(s) < 60:
                continue
            # 符号密集 (代码特征)
            sym_count = sum(1 for c in s if c in "=(){}[]<>:.,;+-*/|\\")
            if sym_count > 10 and len(s) < 120:
                continue
            clean.append(s)
        return "。".join(clean).strip()[:300]

    def decompose(self, question: str, max_sub: int = 3) -> List[Tuple[str, np.ndarray, float]]:
        """语义分解——在知识库中找与问题最相关的多样性概念"""
        self._lazy()
        q_vec = self._encode(question)
        sub_questions = []

        if self._kb and self._kb._loaded:
            results = self._kb.search(question, top_k=10, threshold=0.15)
            seen_fp = set()
            used_vecs = []

            for r in results:
                text = r.get("text", "")[:300]
                score = r.get("score", 0)
                if score < 0.15 or len(text) < 20:
                    continue
                fp = text[:30]
                if fp in seen_fp:
                    continue
                seen_fp.add(fp)

                vec = self._encode(text)
                # 排除高度重叠
                if any(float(vec @ uv) > 0.85 for uv in used_vecs):
                    continue
                used_vecs.append(vec)

                # 生成子问题描述
                keywords = re.findall(r'[\u4e00-\u9fff\w]{2,}', text[:80])
                sub_q = "、".join(keywords[:3]) if keywords else text[:50]
                sub_questions.append((sub_q, vec, max(0.2, score)))
                if len(sub_questions) >= max_sub:
                    break

        if not sub_questions:
            sub_questions.append((question, q_vec, 1.0))

        return sub_questions

    def retrieve_context(self, question: str, existing: List[str] = None,
                         top_k: int = 4) -> List[str]:
        """多样化知识检索——返回不重样的清洗后知识"""
        self._lazy()
        if not self._kb or not self._kb._loaded:
            return []

        results = self._kb.search(question, top_k=top_k + 6, threshold=0.15)
        seen = set()
        if existing:
            seen.update(e[:40] for e in existing)
        contexts = []

        for r in results:
            text = r.get("text", "")
            score = r.get("score", 0)
            fp = text[:40]
            if score < 0.15 or fp in seen or len(text) < 20:
                continue
            seen.add(fp)
            clean = self._strip_code(text)
            if clean and len(clean) > 20:
                contexts.append(clean)
            if len(contexts) >= top_k:
                break
        return contexts

    def reason(self, question: str, max_steps: int = 20, 
               temperature: float = 0.3) -> Dict:
        """量子推理循环——在特征空间中迭代精炼"""
        self._lazy()
        t0 = time.perf_counter()

        q_state = self._encode(question)
        sub_qs = self.decompose(question, max_sub=4)

        # 去重收集所有知识
        all_ctx = set()
        for sq, _, _ in sub_qs:
            ctxs = self.retrieve_context(sq, list(all_ctx), top_k=2)
            all_ctx.update(ctxs)
        ctx_list = list(all_ctx)[:6]

        ctx_vecs = [self._encode(c) for c in ctx_list]

        state = q_state.copy()
        trajectory = [state.copy()]
        insights = []
        alpha, gamma, beta0 = 0.08, 0.05, 0.03

        for step in range(max_steps):
            temp_t = 0.3 + 0.4 * (1 - step / max_steps)
            if ctx_vecs:
                scores = np.array([float(state @ cv) for cv in ctx_vecs])
                scaled = scores / max(temp_t, 0.05)
                scaled -= scaled.max()
                w = np.exp(scaled)
                w /= w.sum() + 1e-10
                attended = sum(wi * cv for wi, cv in zip(w, ctx_vecs))
                delta = attended - state
            else:
                delta = -gamma * state

            beta = beta0 * (1 - step / max_steps)
            noise = np.random.randn(1024).astype(np.float32) * beta
            state = state + alpha * delta - gamma * state + noise
            n = np.linalg.norm(state)
            if n > 0:
                state /= n
            trajectory.append(state.copy())

            if len(trajectory) >= 6:
                recent = trajectory[-5:]
                changes = [np.linalg.norm(recent[i] - recent[i+1]) 
                          for i in range(len(recent)-1)]
                if max(changes) < 0.006:
                    insights.append(f"收敛(步骤{step+1})")
                    break
            if (step+1) % 5 == 0 and step > 0:
                change = np.linalg.norm(state - trajectory[0])
                insights.append(f"步骤{step+1}: Δ={change:.3f}")

        return {
            "trajectory": trajectory,
            "final_state": state,
            "steps_used": step + 1,
            "insights": insights,
            "context_items": len(ctx_list),
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }

    def synthesize(self, question: str, reason_result: Dict,
                   max_chars: int = 3000) -> str:
        """合成最终答案"""
        ctxs = self.retrieve_context(question, top_k=5)
        insights = reason_result.get("insights", [])
        trajectory = reason_result.get("trajectory", [])

        parts = []
        parts.append(f"## {question[:60]}\n")

        # 核心概念
        if ctxs:
            parts.append("### 核心知识\n")
            for i, c in enumerate(ctxs[:3]):
                parts.append(f"{i+1}. {c[:250]}\n")

        # 推理过程
        if insights:
            parts.append("\n### 推理过程\n")
            for ins in insights[-3:]:
                parts.append(f"- {ins}\n")

        # 从轨迹展开分析
        n = len(trajectory)
        if n >= 4:
            parts.append("\n### 分析\n")
            early = trajectory[n//4]
            late = trajectory[-1]

            best_early = max(ctxs, key=lambda c: float(self._encode(c) @ early)) if ctxs else ""
            if best_early:
                parts.append(f"{best_early[:300]}\n")

            best_late = max(ctxs, key=lambda c: float(self._encode(c) @ late)) if ctxs else ""
            if best_late and best_late != best_early:
                parts.append(f"{best_late[:300]}\n")

        if self._v12:
            try:
                r = self._v12.respond(question)
                if r and len(r) > 5:
                    parts.append(f"\n### 语义匹配\n{r}\n")
            except: pass

        return "\n".join(parts)[:max_chars]

    def full_reason(self, question: str, max_chars: int = 3000) -> Dict:
        t0 = time.perf_counter()
        reason_result = self.reason(question)
        output = self.synthesize(question, reason_result, max_chars)
        total = (time.perf_counter() - t0) * 1000
        return {
            "question": question,
            "output": output,
            "chars": len(output),
            "steps": reason_result["steps_used"],
            "context_items": reason_result["context_items"],
            "latency_ms": round(total, 1),
        }


if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  Semantic Quantum Reasoner v2.1")
    logger.info("=" * 65)
    reasoner = SemanticReasoner()

    for q in [
        "量子核是怎么工作的？和UN6有什么区别？",
        "LAAP架构如何实现零LLM的认知推理？",
        "PSI认知循环的五个步骤是什么？",
    ]:
        t0 = time.time()
        r = reasoner.full_reason(q, max_chars=2000)
        logger.info(f"\n{'─'*65}")
        logger.info(f"问: {q}")
        logger.info(f"  步骤:{r['steps']} | 知识:{r['context_items']}条 | {r['latency_ms']}ms | {r['chars']}字")
        for line in r['output'].split('\n')[:10]:
            logger.info(f"  {line[:120]}")