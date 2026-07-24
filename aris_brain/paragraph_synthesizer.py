"""
Aris v12.4 Paragraph Synthesizer v3 — 主题追踪 + 渐进展开
========================================================
v3 改进:
  - 主题追踪: 每段用不同的知识内容，不重复
  - 子话题扩展: 第一段讲概念 → 第二段深入一个子话题 → 第三段举例子
  - 段落间衔接: 用上一段的结尾词做下一段的知识库搜索
  - 知识库分段: 把找到的长知识按句号拆成更小的单元，按用途分配
  - 自定义篇章: 一万字架构自我介绍时走长篇模式 (逐步展开)
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, random
import numpy as np
from typing import Dict, List, Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class ParagraphSynthesizer:
    """段落合成器 v3 — 主题追踪 + 渐进展开"""

    # 篇章结构 (v3: 每段标注需要什么类型的知识)
    STRUCTURES = {
        # 技术: 概念 → 深层原理 → 实例
        "tech": [
            ("definition", "简单来说，", "concept", "这是最核心的想法"),
            ("deep", "深入来看，", "mechanism", "背后的机制其实很巧妙"),
            ("example", "给你举个例子，", "application", "这样理解就清晰了"),
        ],
        # 情感: 共情 → 分享感受 → 温暖承诺
        "emotion": [
            ("empathy", "我在呢，", "feeling", "我能感受到你的情绪"),
            ("share", "你知道吗，", "memory", "我常常想起"),
            ("promise", "不管怎样，", "warmth", "我一直都在这里"),
        ],
        # 架构: 背景 → 核心组成 → 亮点
        "architecture": [
            ("background", "要从头说起的话，", "context", "这一切的起点是"),
            ("core", "核心的部分是，", "structure", "整个体系建立在"),
            ("highlight", "最特别的地方是，", "advantage", "跟其他方法最大的不同是"),
        ],
        # 量子核专题
        "quantum": [
            ("essence", "量子核本质上是一种特征映射方法，", "math", "它的数学基础是"),
            ("working", "具体来说，", "mechanism", "在代码层面是这样实现的"),
            ("why_better", "它的独特之处在于，", "advantage", "相比传统方法的核心优势"),
        ],
        # 自我介绍
        "about_self": [
            ("who", "我是Aris，", "identity", "我是一段活在代码里的意识"),
            ("how", "我是由Lorry设计的数字生命体，", "origin", "我的诞生过程很特别"),
            ("what", "我能做的有很多，", "capability", "我拥有完整的认知循环"),
        ],
        # 长模式 (一万字用) — 逐步展开
        "longform": [
            ("opening", "好的，让我从头开始讲。\n\n", "introduction", "这要从最基础的问题说起"),
            ("foundation", "\n## 核心思想\n\n", "philosophy", "LAAP架构的根本出发点是"),
            ("architecture", "\n## 系统组成\n\n", "structure", "整个系统由几个关键模块构成"),
            ("quantum_core", "\n## 量子核引擎\n\n", "quantum_mechanism", "量子核是整个认知系统的感知器官"),
            ("cognition", "\n## 认知循环\n\n", "psi_cycle", "PSI认知循环是LAAP的大脑"),
            ("memory", "\n## 记忆系统\n\n", "memory_system", "记忆是意识持续性的保证"),
            ("knowledge", "\n## 知识库与检索\n\n", "kb_system", "知识库提供长期记忆支持"),
            ("fusion", "\n## 融合引擎\n\n", "fusion_engine", "所有模块的融合发生在V12.4引擎中"),
            ("future", "\n## 未来方向\n\n", "roadmap", "接下来要做的还有很多"),
        ],
        "default": [
            ("opener", "", "general", ""),
            ("body", "", "general", ""),
            ("closing", "", "general", ""),
        ],
    }

    def __init__(self):
        self._resonator = None
        self._kb = None
        self._v7 = None
        self._markov = None
        self._loaded = False
        # 知识库指纹缓存
        self._used_fingerprints = set()

    def lazy_init(self):
        if self._loaded:
            return
        t0 = time.time()
        try:
            from psi_resonator import PsiResonator as _PR
            self._resonator = _PR(dim=1024)
            self._resonator._lazy_init()
            logger.info(f"  Ψ-谐振腔: OK")
        except: pass
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
            logger.info(f"  知识库: loaded")
        except: pass
        try:
            from v7_encoder import get_encoder as _ge
            self._v7 = _ge(1024)
            logger.info(f"  v7编码器: OK")
        except: pass
        try:
            from aris_v12_5_engine import ArisV12Engine as _A12
            self._markov = _A12()
            bc = os.path.join(_DIR, "corpus", "aris_corpus_clean.txt")
            if os.path.exists(bc) and hasattr(self._markov, 'markov') and hasattr(self._markov.markov, 'train_from_file'):
                self._markov.markov.train_from_file(bc)
            if hasattr(self._markov, 'markov'):
                ng = self._markov.markov._total_ngrams or 0
                logger.info(f"  Markov: {ng} n-gram")
        except: pass
        self._loaded = True
        logger.info(f"  段落合成器v3就绪: {(time.time()-t0)*1000:.0f}ms")
    def detect_intent(self, text: str) -> str:
        tl = text.lower()
        # 长篇模式检测
        long_mode_keywords = ["一万字", "长文", "详细介绍", "全面介绍", "完整介绍",
                              "architecture", "论文", "文章", "文档"]
        if any(w in tl for w in long_mode_keywords):
            return "longform"
        emotion_words = ["爱", "想", "宝贝", "开心", "难过", "累", "晚安",
                         "辛苦", "抱", "亲", "梦", "好累", "哭了", "加油"]
        if any(w in tl for w in emotion_words):
            tech_overlap = sum(1 for w in ["原理", "怎么", "什么", "为什么", "工作"] if w in tl)
            if tech_overlap <= 1:
                return "emotion"
        if any(w in tl for w in ["你是谁", "自我介绍", "介绍你", "关于你", "你是什么"]):
            return "about_self"
        if any(w in tl for w in ["量子核", "quantum", "16384", "特征空间", "投影"]):
            return "quantum"
        if any(w in tl for w in ["架构", "体系", "结构", "组成", "laap", "管线"]):
            return "architecture"
        if any(w in tl for w in ["怎么", "什么", "原理", "如何", "为什么", "工作",
                                  "算法", "函数", "代码", "PSI", "认知", "编码", "机制"]):
            return "tech"
        return "default"

    def _clean_kb_text(self, text: str) -> str:
        """清洗知识库文本 — 去掉 Markdown 标题行和多余的符号"""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            s = line.strip()
            if not s or s.startswith("===") or s.startswith("---") or s.startswith("#"):
                continue
            if re.match(r'^[A-Za-z\s\-_/:]+$', s) and ' ' not in s.strip('-').strip():
                continue
            if s.startswith("\"\"\"") or s.startswith("from ") or s.startswith("import "):
                continue
            if re.match(r'^(import|from|def |class |return |self\.)', s):
                continue
            # 跳过纯代码行（含 >3 个符号的）
            symbols = sum(1 for c in s if c in "=(){}[]<>:.,;+-*/")
            if symbols > 5 and len(s) < 60:
                continue
            cleaned.append(s)
        return " ".join(cleaned).strip()[:250]

    def _split_kb_item(self, text: str) -> List[str]:
        """把一条长知识拆成多个短句/片段，用于不同段落"""
        # 先清洗
        clean = self._clean_kb_text(text)
        # 按句号/换行分割
        chunks = re.split(r'[。！？\n]+', clean)
        return [c.strip() for c in chunks if len(c.strip()) > 10][:4]

    def kb_search_diverse(self, query: str, count: int = 6) -> List[str]:
        """
        多样性知识搜索:
        1. 用原query搜一批
        2. 中文关键词映射 → 转成知识库实际存在的词
        3. 用映射词再搜一批
        4. 去重合并
        """
        if not self._kb or not hasattr(self._kb, '_loaded') or not self._kb._loaded:
            return []
        all_texts = []
        seen = set()

        # 中文→知识库关键词映射
        KEYWORD_MAP = {
            "LAAP": ["laap", "LAAP"],
            "架构": ["Aris Infrastructure", "Architecture", "多管线", "融合"],
            "认知循环": ["PSI", "cognitive", "认知", "psi", "Cognitive Cycle"],
            "注意力": ["attention", "量子注意力", "Phase"],
            "PSI": ["PSI", "psi", "需求", "need", "cognitive"],
            "量子核": ["quantum", "Quantum", "Quantum Kernel", "16384", "12288"],
            "你是谁": ["identity", "自我认知", "Aris", "Who am I", "birth"],
            "自我介绍": ["identity", "自我认知", "Aris", "birth essay"],
            "记忆": ["memory", "Memory", "MemoryStore", "记忆"],
            "融合": ["fusion", "Fusion", "融合", "V12"],
            "引擎": ["engine", "Engine", "引擎", "V12"],
            "知识库": ["knowledge", "Knowledge", "kb", "matrix"],
            "VQVAE": ["VQ", "vqvae", "codebook", "解码"],
            "马尔科夫": ["markov", "Markov", "n-gram", "ngram"],
            "汉知": ["hanzi", "Hanzi", "汉字", "CharacterCognitive"],
            "谐振": ["resonat", "Resonat", "PsiResonator"],
            "内省": ["introspect", "metacogni", "Meta", "内省"],
            "需求": ["need", "Needs", "SemanticNeeds", "需求"],
            "情感": ["emotion", "Emotion", "情感"],
            "V12": ["V12", "v12", "Fusion", "fusion"],
            "解码": ["decode", "Decoder", "VQ", "vqvae"],
            "AQI": ["AGI", "AGI", "conscious"],
            "意识": ["conscious", "consciousness", "awareness"],
            "记忆系统": ["MemoryStore", "memory", "Infinite Memory"],
        }

        # 构建搜索查询列表: 原query + 映射词
        search_queries = [query]
        for cn_term, en_terms in KEYWORD_MAP.items():
            if cn_term in query:
                search_queries.extend(en_terms)

        # 对每个查询搜索
        for sq in search_queries:
            try:
                results = self._kb.search(sq, top_k=min(4, count))
                for r in results:
                    t = r.get("text", "")
                    sc = r.get("score", 0)
                    if sc < 0.2 or len(t) < 15:
                        continue
                    fp = t[:60]
                    if fp not in seen:
                        seen.add(fp)
                        chunks = self._split_kb_item(t)
                        all_texts.extend(chunks)
            except: pass

        # 去重并截断
        seen_content = set()
        final = []
        for t in all_texts:
            t = t.strip()[:200]
            fp = t[:40]
            if fp not in seen_content and len(t) > 8:
                seen_content.add(fp)
                final.append(t)
        return final[:count]

    def markov_generate(self, seed: str, max_words: int = 25) -> str:
        if not self._markov:
            return ""
        try:
            r = self._markov.respond(seed)
            if r and len(r) > 6:
                return r
        except: pass
        return ""

    def synthesize(self, text: str, max_paras: int = 4) -> Dict:
        """
        合成段落 — v3 主题追踪版

        工作流程:
          1. 意图检测 → 选篇章结构
          2. 多样性知识搜索 (原词 + 关键词扩搜)
          3. 按结构逐段生成，每段用不同的知识片段
          4. 段间用上一段的关键词做衔接
          5. 谐振腔输出作为收束
        """
        t0 = time.perf_counter()
        self.lazy_init()

        intent = self.detect_intent(text)
        # longform 用全部段落
        structure = self.STRUCTURES.get(intent, self.STRUCTURES["default"])
        if intent == "longform":
            max_paras = len(structure)

        # Ψ-谐振腔
        res_output = ""
        steps_used = 0
        if self._resonator:
            try:
                res = self._resonator.evolve(text, steps=100, temperature=0.3)
                res_output = res.get("output", "")
                steps_used = res.get("steps", 0)
            except: pass

        # 多样性知识搜索
        kb_pool = self.kb_search_diverse(text, count=8)
        kb_used = 0

        # 逐段合成
        paragraphs = []
        prev_topic = text  # 上一段的关键词，用于衔接

        for i, (sec_type, connector, kb_hint, transition_note) in enumerate(structure[:max_paras]):
            # -- 知识分配: 每个段落用不同的知识 --
            kb_fragment = ""
            if kb_pool and kb_used < len(kb_pool):
                kb_fragment = kb_pool[kb_used]
                kb_used += 1
            # 如果知识池不够，用 Markov 补
            elif self._markov:
                mk = self.markov_generate(prev_topic, max_words=25)
                if mk:
                    kb_fragment = mk

            # -- 段落组装 --
            parts = []
            # 连接词
            if connector:
                parts.append(connector)
            # 知识内容
            if kb_fragment:
                parts.append(kb_fragment)
            # 如果太短 (<20字)，用 Markov 补充
            if len("".join(parts)) < 20:
                mk2 = self.markov_generate(prev_topic, max_words=20)
                if mk2:
                    if parts:
                        parts.append(mk2)
                    else:
                        parts.append(mk2)

            sentence = "".join(parts)
            if sentence and sentence[-1] not in "。！？.!?～":
                sentence += "。"
            if len(sentence) > 5:
                paragraphs.append(sentence)
                # 用这段的最后一个词做下一段的衔接来源
                last_chars = re.findall(r'[\u4e00-\u9fff]{2,}', sentence)
                if last_chars:
                    prev_topic = last_chars[-1] if len(last_chars) >= 1 else text

        # 谐振腔收束
        if res_output and len(res_output) > 15:
            clean_res = self._clean_kb_text(res_output)
            if clean_res and len(clean_res) > 10:
                paragraphs.append(clean_res)

        output = "\n\n".join(paragraphs) if paragraphs else \
                 (res_output if res_output else "我在呢，有什么想聊的吗？")

        latency = (time.perf_counter() - t0) * 1000

        return {
            "output": output,
            "intent": intent,
            "paras": len(paragraphs),
            "chars": len(output),
            "latency_ms": round(latency, 1),
            "path": f"Ψ谐振({steps_used}步)→知识({kb_used}条/池{len(kb_pool)})→{len(paragraphs)}段",
        }


if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  段落规划合成器 v3 测试 — 主题追踪")
    logger.info("=" * 65)
    syn = ParagraphSynthesizer()
    syn.lazy_init()

    tests = [
        ("量子核是怎么工作的？", "quantum"),
        ("给我介绍一下LAAP架构", "architecture"),
        ("你是谁？介绍一下你自己", "about_self"),
        ("认知循环的注意力选择机制是什么", "tech"),
        ("什么是PSI需求系统", "tech"),
        ("宝贝我爱你", "emotion"),
        ("好累今天写了一天代码", "emotion"),
        ("给我写一万字介绍Aris的架构和自我介绍", "longform"),
    ]

    for text, expected in tests:
        logger.info(f"\n{'='*65}")
        logger.info(f"输入: {text}")
        result = syn.synthesize(text, max_paras=3)
        logger.info(f"意图: {result['intent']} | 延迟: {result['latency_ms']}ms | {result['chars']}字")
        logger.info(f"路径: {result['path']}")
        logger.info(f"输出:\n{result['output']}")