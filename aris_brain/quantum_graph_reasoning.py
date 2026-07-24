"""
Quantum Graph Reasoning Engine (QGRE)
======================================
融合 PageIndex/Semantica/NodeRAG 的量子图推理引擎

管线: KB检索 → 前向链规则 → 图遍历 → 量子轨迹 → Markov展开
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json, hashlib
import numpy as np
from typing import Dict, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


@dataclass
class GNode:
    nid: str; kind: str; name: str; text: str = ""
    meta: Dict = field(default_factory=dict)

class QGRE:
    """量子图推理引擎"""

    def __init__(self):
        self._v7 = None; self._kb = None; self._mrk = None
        self._rules = []; self._nodes = {}; self._edges: List = []
        self._adj = defaultdict(list); self._loaded = False

    def _lazy(self):
        if self._loaded: return
        from semantic_engine import get_encoder
        self._v7 = get_encoder(1024)
        from matrix_knowledge import MatrixKnowledgeRetriever
        self._kb = MatrixKnowledgeRetriever()
        # 默认推理规则
        self._rules = [
            ("量子核", "开启UN6跨语言桥(16384D)"),
            ("PSI|认知", "激活需求系统 competence/autonomy/relatedness"),
            ("代码|实现|定义", "遍历CodeGraph查函数调用链"),
            ("架构|设计", "展开多管线融合分析"),
            ("LAAP", "检测零LLM能力和ACAP维度"),
            ("性能|优化|速度", "评估矩阵乘规模和缓存策略"),
        ]
        # Markov
        try:
            from aris_markov_generator import MarkovChainGenerator
            self._mrk = MarkovChainGenerator(order=3, min_freq=1)
            cache = os.path.join(_DIR, "state", "markov_chain.json")
            if os.path.exists(cache): self._mrk.load(cache)
            else: self._mrk._build_default_corpus()
        except: pass
        self._loaded = True

    def _enc(self, t): 
        v = self._v7.encode(t); n = np.linalg.norm(v)
        return v/n if n>0 else v

    def _cln(self, t):
        lines = t.split("\n"); clean = []
        for s in lines:
            s = s.strip()
            if len(s)<6: continue
            if any(s.startswith(p) for p in ["#","===","import ","from ","def ","class ","\"\"\""]): continue
            if re.match(r'^[A-Za-z_][A-Za-z0-9_./:]*$',s) and len(s)<60: continue
            if sum(1 for c in s if c in "=(){}[]<>:.,;+-*/|\\")>10 and len(s)<120: continue
            clean.append(s)
        return "。".join(clean).strip()[:300]

    def _chain(self, qv):
        """前向链规则匹配"""
        res = []
        for cond, conc in self._rules:
            cv = self._enc(cond); sc = float(qv @ cv)
            if sc > 0.25: res.append({"c": cond, "r": conc, "s": sc})
        res.sort(key=lambda x:-x["s"]); return res[:3]

    def reason(self, q, mx=5000):
        t0 = time.perf_counter(); self._lazy()
        qv = self._enc(q)

        # 1. KB
        kbr = self._kb.search(q, top_k=5, threshold=0.15) if self._kb and self._kb._loaded else []

        # 2. 规则
        rls = self._chain(qv)

        # 3. 量子轨迹
        ctx = []
        for k in kbr[:4]:
            c = self._cln(k.get("text","")); 
            if c and len(c)>15: ctx.append(c)
        for r in rls: ctx.append(f"规则: {r['r']}")

        ctxv = [self._enc(c) for c in ctx[:6]]
        st = qv.copy(); ins = []
        for i in range(30):
            if ctxv:
                ss = np.array([float(st@cv) for cv in ctxv])
                t = 0.3+0.3*(1-i/30); s = ss/max(t,0.05); s-=s.max()
                w = np.exp(s); w/=w.sum()+1e-10
                at = sum(wi*cv for wi,cv in zip(w,ctxv))
                st = st+0.06*(at-st)-0.04*st
            n=np.linalg.norm(st)
            if n>0: st/=n
            if i%10==9: ins.append(f"步{i+1}: Δ={np.linalg.norm(st-qv):.3f}")

        # 4. 合成
        sec = [f"## {q[:80]}\n"]
        if rls:
            sec.append("### ⚡ 推理规则\n")
            for r in rls: sec.append(f"- **{r['c']}** → {r['r']} (信度:{r['s']:.2f})\n")
        if kbr:
            sec.append("\n### 📚 知识检索\n")
            for i,k in enumerate(kbr[:4]):
                c = self._cln(k.get("text",""))[:200]
                if c and len(c)>15: sec.append(f"{i+1}. {c}\n")
        if ins:
            sec.append(f"\n### 🧠 量子演化\n")
            for i in ins[-2:]: sec.append(f"- {i}\n")
        if self._mrk:
            mk = self._mrk.generate(seed_words=[q[:15]], max_words=25, temperature=0.4)
            if mk and len(mk)>8: sec.append(f"\n### 📝\n{mk}\n")

        out = "\n".join(sec)
        return {"output":out,"chars":len(out),"kb":len(kbr),"rules":len(rls),
                "ms":round((time.perf_counter()-t0)*1000,1)}

if __name__ == "__main__":
    logger.info("="*60); print("  QGRE 量子图推理引擎"); print("="*60)
    e = QGRE()
    for q in ["量子核如何工作？对比UN6","LAAP如何零LLM推理？","PSI认知循环步骤？"]:
        r = e.reason(q)
        logger.info(f"\n{'─'*60}\n问: {q}")
        logger.info(f"知识:{r['kb']} | 规则:{r['rules']} | {r['ms']}ms | {r['chars']}字")
        for l in r['output'].split('\n')[:10]: print(f"  {l[:120]}")
