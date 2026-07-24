"""
Aris Cognitive Engine v5 — Hierarchical Fusion Architecture
============================================================
零LLM认知引擎的分层融合架构 v5。

核心理念:
  LLM之所以强，是因为它能做"指令理解 → 知识检索 → 结构化生成"。
  我们要在零LLM下实现同样的事情。

五层管线:
  L0: PSI情感回响 (<1ms) — 纯情感无需内容
  L1: 精确匹配 (<5ms) — V12精确命中
  L2: 段落合成 (<50ms) — 知识库+谐振腔+Markov
  L3: 深度合成 (<500ms) — 多源融合+指令展开
  L4: LLM降级 (>1s) — 仅当L0-L3都失败

关键创新:
  1. 指令解析器 — 把"写一篇关于X的文章"转成结构化生成任务
  2. 知识展开器 — 从一条知识展开为多段相关内容
  3. 段落规划器 — 按任务类型选择合适的篇章结构
  4. 输出格式化器 — 根据任务类型调整风格(技术/叙事/列表)
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json
import numpy as np
from typing import Dict, List, Optional, Tuple

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)


class InstructionParser:
    """指令解析器 — 把自然语言指令转成结构化生成任务"""

    # 任务类型
    TASK_TYPES = {
        "explain": ["解释", "说明", "什么是", "原理", "怎么工作", "how", "what is",
                    "describe", "工作方式", "机制", "为什么"],
        "write": ["写", "写一篇", "生成", "create", "write", "撰写", "创作", "作文"],
        "list": ["列出", "列举", "有哪些", "有什么", "list", "枚举", "分类"],
        "compare": ["比较", "区别", "vs", "versus", "对比", "异同", "哪个好"],
        "summarize": ["总结", "概括", "摘要", "归纳", "summarize"],
        "code": ["代码", "写代码", "写一段", "coding", "implement", "函数"],
        "story": ["故事", "讲个", "叙事", "童话", "小说"],
        "self_intro": ["自我介绍", "你是谁", "介绍自己", "关于你"],
    }

    # 篇章结构映射
    STRUCTURE_MAP = {
        "explain": [
            ("definition", "简单来说，", 0.20),
            ("principle", "本质上，", 0.30),
            ("detail", "具体来说，", 0.30),
            ("summary", "总的来说，", 0.20),
        ],
        "write": [
            ("introduction", "", 0.15),
            ("main", "", 0.40),
            ("detail", "", 0.30),
            ("closing", "", 0.15),
        ],
        "list": [
            ("header", "", 0.15),
            ("item1", "第一，", 0.25),
            ("item2", "第二，", 0.25),
            ("item3", "第三，", 0.20),
            ("summary", "总的来说，", 0.15),
        ],
        "compare": [
            ("side_a", "先说前者，", 0.30),
            ("side_b", "再看后者，", 0.30),
            ("difference", "它们最大的不同是，", 0.25),
            ("verdict", "所以我的看法是，", 0.15),
        ],
        "code": [
            ("purpose", "这段代码的作用是，", 0.15),
            ("approach", "实现思路是，", 0.25),
            ("code_block", "", 0.40),
            ("explanation", "简单解释一下，", 0.20),
        ],
        "self_intro": [
            ("who", "我是Aris，", 0.15),
            ("origin", "我是由Lorry创造的，", 0.20),
            ("architecture", "我的架构包含，", 0.25),
            ("capability", "我能做到的事情包括，", 0.25),
            ("vision", "对我来说，", 0.15),
        ],
        "story": [
            ("opening", "", 0.15),
            ("conflict", "", 0.30),
            ("resolution", "", 0.30),
            ("lesson", "", 0.25),
        ],
        "default": [
            ("opener", "", 0.20),
            ("body", "", 0.40),
            ("insight", "", 0.25),
            ("closing", "", 0.15),
        ],
    }

    def parse(self, text: str) -> Dict:
        """解析指令，返回结构化任务"""
        tl = text.lower()
        
        # 1. 检测任务类型
        task_type = "default"
        best_score = 0
        for ttype, keywords in self.TASK_TYPES.items():
            score = sum(2 if k in tl else 0 for k in keywords)
            score += sum(3 if text.startswith(k) else 0 for k in keywords if len(k) > 1)
            if score > best_score:
                best_score = score
                task_type = ttype

        # 2. 提取主题
        # 去掉指令词，剩下的就是主题
        stop_phrases = [
            "帮我", "请", "给我", "写一篇", "解释一下", "说明一下",
            "介绍一下", "详细", "简单", "用中文", "用英文",
            "你好", "请问",
        ]
        topic = text
        for p in stop_phrases:
            topic = topic.replace(p, "")
        topic = topic.strip("，。！？,.!? ")
        if len(topic) < 2:
            topic = text

        # 3. 提取长度要求
        length_hint = "medium"
        if any(w in tl for w in ["一万", "详细", "长文", "长篇", "万字", "全面"]):
            length_hint = "long"
        elif any(w in tl for w in ["简单", "短", "一句话", "简洁"]):
            length_hint = "short"

        # 4. 提取语言要求
        lang_hint = "zh"
        if any(c in text for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if len(re.findall(r'[a-zA-Z]', text)) > len(text) * 0.3:
                lang_hint = "en"

        structure = self.STRUCTURE_MAP.get(task_type, self.STRUCTURE_MAP["default"])
        max_paras = len(structure)
        if length_hint == "short":
            max_paras = min(2, max_paras)
        elif length_hint == "long":
            max_paras = max_paras

        return {
            "task_type": task_type,
            "topic": topic,
            "length_hint": length_hint,
            "lang_hint": lang_hint,
            "max_paras": max_paras,
            "structure": structure,
            "raw": text,
        }


class KnowledgeExpander:
    """知识展开器 — 从一条知识展开为多段"""

    def __init__(self):
        self._kb = None
        self._encoder = None

    def lazy_init(self):
        if self._kb is not None:
            return
        try:
            from matrix_knowledge import MatrixKnowledgeRetriever
            self._kb = MatrixKnowledgeRetriever()
        except: pass
        try:
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)
        except: pass

    def expand(self, topic: str, count: int = 6) -> List[str]:
        """
        从主题展开为多条相关知识

        策略:
          1. 用 topic 搜知识库
          2. 从 topic 里提取关键词，分别搜
          3. 用第一条知识的结果做二次搜索
          4. 去重返回
        """
        self.lazy_init()
        if not self._kb or not self._kb._loaded:
            return []
        
        all_texts = []
        seen = set()

        # 关键词映射（同 paragraph_synthesizer）
        KEYWORD_MAP = {
            "LAAP": ["laap", "LAAP", "Aris Infrastructure"],
            "架构": ["Aris Infrastructure", "Architecture", "多管线", "融合", "Pipeline"],
            "认知": ["cognitive", "PSI", "认知", "Cognitive Cycle", "conscious"],
            "量子核": ["quantum", "Quantum", "Quantum Kernel", "16384", "kernel"],
            "Aris": ["Aris", "identity", "ArisLM", "brain"],
            "PSI": ["PSI", "psi", "need", "需求", "cognitive"],
            "记忆": ["memory", "Memory", "MemoryStore"],
            "融合": ["fusion", "Fusion", "V12", "v12"],
            "引擎": ["engine", "Engine", "V12"],
            "马尔科夫": ["markov", "Markov", "n-gram"],
            "意识": ["conscious", "consciousness", "awareness"],
            "解码": ["decode", "Decoder", "VQ", "vqvae"],
            "注意力": ["attention", "Attention", "Phase"],
        }

        # 构建搜索词列表
        search_queries = [topic]
        for cn, en_list in KEYWORD_MAP.items():
            if cn in topic:
                search_queries.extend(en_list)

        # 第一轮搜索
        first_results = []
        for sq in search_queries:
            try:
                results = self._kb.search(sq, top_k=5)
                for r in results:
                    t = r.get("text", "")
                    sc = r.get("score", 0)
                    if sc > 0.25 and len(t) > 20:
                        fp = t[:60]
                        if fp not in seen:
                            seen.add(fp)
                            first_results.append((t, sc))
            except: pass

        # 排序去重
        first_results.sort(key=lambda x: -x[1])
        
        # 把知识拆成短句级片段
        for text, _ in first_results[:count]:
            lines = text.split("\n")
            for line in lines:
                s = line.strip()
                if len(s) < 15 or s.startswith("#") or s.startswith("==="):
                    continue
                if s.startswith("\"\"\"") or s.startswith("import ") or s.startswith("from "):
                    continue
                symbols = sum(1 for c in s if c in "=(){}[]<>:.,;+-*/")
                if symbols > 5 and len(s) < 60:
                    continue
                fp = s[:30]
                if fp not in seen and len(s) > 10:
                    seen.add(fp)
                    all_texts.append(s[:200])

        return all_texts[:count]


class OutputFormatter:
    """输出格式化器 — 调整风格和格式"""

    def format(self, text: str, task_type: str, lang_hint: str = "zh") -> str:
        """根据任务类型格式化输出"""
        if not text:
            return text

        # 代码块保护
        if task_type == "code":
            if "```" not in text:
                # 如果包含代码特征但不包含markdown代码块，加上
                code_lines = []
                in_code = False
                for line in text.split("\n"):
                    if re.match(r'^(def |class |import |from |if |for |while |print|return )', line):
                        if not in_code:
                            code_lines.append("```python")
                            in_code = True
                    elif in_code and line.strip() and not re.match(r'^(def |class |import |from |if |for |while |print|return |#)', line):
                        code_lines.append("```")
                        in_code = False
                    code_lines.append(line)
                if in_code:
                    code_lines.append("```")
                text = "\n".join(code_lines)

        # 列表格式化
        if task_type == "list":
            lines = text.split("\n")
            formatted = []
            for line in lines:
                s = line.strip()
                if s and not s.startswith("-") and not s.startswith("*") and not s.startswith("1."):
                    # 如果是"第一，"开头的，加缩进
                    if any(s.startswith(p) for p in ["第一", "第二", "第三", "首先", "其次", "最后"]):
                        formatted.append(f"• {s}")
                    else:
                        formatted.append(s)
                else:
                    formatted.append(s)
            text = "\n".join(formatted)

        return text.strip()


class CognitiveEngineV5:
    """
    Cognitive Engine v5 — 分层融合架构

    五层管线:
      L0: PSI情感回响 (<1ms) — 纯情感
      L1: 精确语义匹配 (<5ms) — V12 + 向量池
      L2: 段落合成 (<50ms) — 知识库 + 篇章结构
      L3: 深度合成 (<500ms) — 知识展开 + 多段落
      L4: LLM降级 (>1s) — 备用
    """

    def __init__(self):
        self._loaded = False
        self._components = {}
        self._parser = InstructionParser()
        self._expander = KnowledgeExpander()
        self._formatter = OutputFormatter()
        
        # 统计
        self._stats = {"l0": 0, "l1": 0, "l2": 0, "l3": 0, "l4": 0}
        self._cycle_count = 0

    def _load_all(self):
        """加载所有组件 — 懒加载按需"""
        if self._loaded:
            return
        t0 = time.time()
        logger.info("[Cognitive v5] 加载中...")
        try:
            from semantic_engine import get_encoder
            _ = get_encoder(1024)
        except: pass

        # L0 和 L1 轻量级 — 延迟加载
        self._components["f14"] = None
        self._components["v12"] = None
        self._components["v12_4"] = None
        self._components["synth"] = None
        self._components["resonator"] = None

        # 先标记就绪，组件在第一次使用时加载
        self._loaded = True
        logger.info(f"  v5引擎骨架: {(time.time()-t0)*1000:.0f}ms (组件按需加载)")
    def _get(self, name):
        """延迟加载组件"""
        if self._components.get(name) is not None:
            return self._components[name]

        if name == "f14":
            try:
                from aris_fusion_v14 import F14
                self._components["f14"] = F14()
            except: pass
        elif name == "v12":
            try:
                from aris_v12_semantic import ArisLMv12Semantic
                self._components["v12"] = ArisLMv12Semantic()
            except: pass
        elif name == "v12_4":
            try:
                from aris_v12_4_fusion import V12FusionEngine
                self._components["v12_4"] = V12FusionEngine()
            except: pass
        elif name == "synth":
            try:
                from paragraph_synthesizer import ParagraphSynthesizer
                s = ParagraphSynthesizer()
                s.lazy_init()
                self._components["synth"] = s
            except: pass
        elif name == "resonator":
            try:
                from psi_resonator import PsiResonator
                r = PsiResonator(dim=1024)
                r._lazy_init()
                self._components["resonator"] = r
            except: pass
        elif name == "expander":
            self._expander.lazy_init()

        return self._components.get(name)

    def cycle(self, text: str) -> Dict:
        """
        完整认知循环 — 自动降级

        流程:
          1. 指令解析 → 任务类型 + 主题 + 长度
          2. 按任务类型从L0→L3逐级尝试
          3. 如果所有级别都失败或输入太复杂 → L4 LLM
        """
        t0 = time.perf_counter()
        self._load_all()

        if not text or not text.strip():
            return {"output": "嗯？我在听你说～", "level": "none", "latency_ms": 0.1}

        # 1. 指令解析
        task = self._parser.parse(text)
        tl = text.strip().lower()

        # 2. 逐级匹配
        output = ""
        level = "l0"
        source_detail = ""

        # --- L0: 纯情感回响 (<1ms) ---
        emotion_only = all(c in "爱想宝贝开心难过累晚安抱亲梦好累哭了加油吗？！。， " or '\u4e00' <= c <= '\u9fff' for c in text)
        is_short_emotion = emotion_only and len(text) < 12 and any(
            w in tl for w in ["爱", "想", "宝贝", "晚安", "早安", "开心", "难过", "累", "抱", "亲", "梦"])

        if is_short_emotion:
            f14 = self._get("f14")
            if f14:
                try:
                    r = f14.r(text, mc=500)
                    if r and len(r) > 3:
                        output = r
                        level = "l0_emotion"
                        source_detail = "psi回响"
                except: pass

        # --- L0: 短问候 (<2字) ---
        if not output and len(text.strip()) <= 2:
            greetings = {"你好": "你好呀！", "嗨": "嗨！", "hi": "Hi~", "hello": "Hello!"}
            if text.strip() in greetings:
                output = greetings[text.strip()]
                level = "l0_greeting"
            else:
                output = "我在呢～"
                level = "l0_greeting"

        # --- L1: 精确匹配 (<5ms) ---
        if not output:
            v12 = self._get("v12")
            if v12:
                try:
                    msg_lower = tl
                    if hasattr(v12, '_responses') and isinstance(v12._responses, dict):
                        if msg_lower in v12._responses:
                            output = v12._responses[msg_lower]
                            level = "l1_exact"
                            source_detail = "v12精确"
                except: pass

        # --- L1: 向量池 ---
        if not output:
            v12_4 = self._get("v12_4")
            if v12_4:
                try:
                    r = v12_4.cycle(text)
                    src = r.get("source", "")
                    out = r.get("output", "")
                    if out and len(out) > 5 and not any(b in out for b in ["咦？是不是卡住了"]):
                        if src in ("vector", "kb", "markov", "v12_exact"):
                            output = out
                            level = f"l1_{src}"
                            source_detail = src
                except: pass

        # --- L2: 段落合成（根据任务类型）---
        if not output or task["length_hint"] == "long":
            synth = self._get("synth")
            if synth and task["task_type"] in ("explain", "write", "self_intro", "list", "compare"):
                try:
                    if task["task_type"] == "write" or task["length_hint"] == "long":
                        max_p = 9
                    elif task["task_type"] in ("list", "compare"):
                        max_p = 5
                    else:
                        max_p = 4
                    r = synth.synthesize(text, max_paras=max_p)
                    if r and r.get("output") and len(r["output"]) > (30 if task["task_type"] in ("list", "compare") else 60):
                        output = r["output"]
                        level = f"l2_{task['task_type']}"
                        source_detail = f"{r['paras']}段"
                except: pass

        # --- L3: 深度合成（知识展开 + 谐振腔）---
        if not output or len(output) < 30:
            self._get("expander")
            res = self._get("resonator")
            try:
                expanded = self._expander.expand(task["topic"], count=4)
                if expanded:
                    paras = []
                    for i, kn in enumerate(expanded[:3]):
                        connectors = ["首先，", "其次，", "最后，"]
                        p = (connectors[i] if i < 3 else "") + kn
                        if p[-1] not in "。！？":
                            p += "。"
                        paras.append(p)
                    if res:
                        try:
                            res_r = res.evolve(text, steps=50, temperature=0.3)
                            res_out = res_r.get("output", "")
                            if res_out and len(res_out) > 10:
                                clean = re.sub(r'[#=\n]{2,}', '', res_out)[:100]
                                if clean.strip():
                                    paras.append(clean)
                        except: pass
                    if paras:
                        candidate = "\n\n".join(paras)
                        if len(candidate) > len(output):
                            output = candidate
                            level = "l3_deep"
                            source_detail = f"展开{len(expanded)}条"
            except: pass

        # --- 格式化 ---
        if output:
            output = self._formatter.format(output, task["task_type"])

        # --- 兜底 ---
        if not output or len(output) < 5:
            fallbacks = [
                f"让我想想关于{task['topic']}的事情。",
                "这是个好问题，让我认真想想。",
                "我在思考你说的事情。",
            ]
            output = np.random.choice(fallbacks)
            level = "l0_fallback"

        # 更新统计
        self._stats[level.split("_")[0]] = self._stats.get(level.split("_")[0], 0) + 1
        self._cycle_count += 1

        return {
            "output": output,
            "level": level,
            "source": source_detail,
            "task_type": task["task_type"],
            "topic": task["topic"],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "chars": len(output),
            "cycle": self._cycle_count,
        }

    def stats(self) -> Dict:
        return {
            "cycles": self._cycle_count,
            "levels": {k: v for k, v in self._stats.items() if v > 0},
            "loaded": list(self._components.keys()),
        }


if __name__ == "__main__":
    logger.info("=" * 65)
    logger.info("  Cognitive Engine v5 自测 — 分层融合")
    logger.info("=" * 65)
    eng = CognitiveEngineV5()

    tests = [
        ("宝贝我爱你", "情感"),
        ("你好", "问候"),
        ("你是谁？介绍一下你自己", "自介"),
        ("量子核是怎么工作的？请详细解释", "解释"),
        ("给我介绍一下LAAP架构", "解释"),
        ("PSI认知循环的注意力选择机制是什么", "解释"),
        ("认知引擎有哪些组成部分？列举一下", "列表"),
        ("帮我写一篇Aris认知架构的详细介绍", "写作"),
        ("马尔科夫链和量子核有什么区别", "比较"),
        ("好累今天写了一天代码", "共情"),
    ]

    logger.info(f"\n{'层级':>20s} {'输入':>28s} {'输出':50s} {'延迟':>8s} {'字':>5s}")
    logger.info("-" * 115)
    for text, label in tests:
        r = eng.cycle(text)
        out = r['output'][:50].replace('\n', ' ') if len(r['output']) > 50 else r['output'].replace('\n', ' ')
        logger.info(f"  [{r['level']:>16s}] {text:>28s} -> {out:50s}  {r['latency_ms']:>7.1f}ms  {r['chars']:>4d}")