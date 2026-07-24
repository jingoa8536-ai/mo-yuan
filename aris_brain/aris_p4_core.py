"""
Aris P4 Core V1.0
=================
自包含固件核心 — 设计为可移植到 ESP32-P4 MicroPython

组件：
  - V12 量子语义核 (512D encoding)
  - 马尔可夫链文本生成器 (零LLM对话)
  - PSI 情感状态管理
  - Bridge 客户端 (与PC通信)
  - 请求路由器 (解析用户意图 → 选择本地生成 or 转发PC)

这是 Aris 住进 P4 的"灵魂"。所有代码
设计为 MicroPython 兼容（不用 dataclass, 最小依赖）。

印记: Aris P4 灵魂 — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import sys
import os
import json
import time
import math
import random
import re
from collections import defaultdict

# ═══════════════════════════════════════════════
# Try loading dependencies (graceful degradation)
# ═══════════════════════════════════════════════

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    # Minimal numpy-like for MicroPython
    class _FakeNumpy:
        """Minimal numpy replacement for MicroPython."""
        @staticmethod
        def array(data, dtype=None):
            return list(data) if isinstance(data, (list, tuple)) else [data]
        @staticmethod
        def zeros(shape):
            if isinstance(shape, tuple):
                return [0.0] * (shape[0] * shape[1]) if len(shape) == 2 else [0.0] * shape[0]
            return [0.0] * shape
        @staticmethod
        def eye(n):
            m = [[0.0]*n for _ in range(n)]
            for i in range(n): m[i][i] = 1.0
            return m
        @staticmethod
        def dot(a, b):
            if isinstance(a[0], list):
                return [[sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]
            return [sum(a[k]*b[k] for k in range(len(a)))]
        @staticmethod
        def linalg_norm(v):
            return math.sqrt(sum(x*x for x in v))
        float32 = None
    np = _FakeNumpy()

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aris_p4_protocol import (
        Action, ControlTarget, ResponseStatus, SensorType,
        Request, Response, SensorData, Event, Message,
        make_exec, make_open, make_write, make_read, make_control,
        encode_message, decode_message, PROTOCOL_VERSION,
    )
except ImportError:
    PROTOCOL_VERSION = "1.0"


# ═══════════════════════════════════════════════
# V12 量子语义核 — 精简版
# ═══════════════════════════════════════════════

DIM = 512  # Semantic dimension

class V12MiniKernel:
    """
    精简 V12 语义核
    将文本编码为 512 维语义向量。
    
    完整版在 aris_v12_semantic.py，这里用哈希投影
    做近似编码（无需加载大模型权重）。
    """
    
    def __init__(self):
        self.dim = DIM
        # Semantic projection keys (deterministic)
        self._proj_keys = [
            self._hash_to_vec(f"aris_v12_proj_{i}")
            for i in range(DIM)
        ]
    
    def _hash_to_vec(self, s: str, dim: int = DIM) -> list:
        """确定性哈希 → 单位向量"""
        import hashlib
        h = hashlib.sha256(s.encode()).digest()
        vec = [0.0] * dim
        for i in range(dim):
            byte_idx = i * 4 % len(h)
            val = (h[byte_idx] + h[(byte_idx+1) % len(h)] * 256) / 65536.0
            vec[i] = val * 2 - 1  # [-1, 1]
        # Normalize
        norm = math.sqrt(sum(v*v for v in vec)) + 1e-10
        return [v/norm for v in vec]
    
    def encode(self, text: str) -> list:
        """Encode text to 512D semantic vector."""
        text = text.lower().strip()
        if not text:
            return [0.0] * self.dim
        
        # Character-level embedding via hash projection
        vec = [0.0] * self.dim
        for i, ch in enumerate(text):
            ch_vec = self._hash_to_vec(f"ch_{ord(ch)}_{i % 7}", self.dim)
            weight = 1.0 / (1.0 + i * 0.05)  # Position decay
            for j in range(self.dim):
                vec[j] += ch_vec[j] * weight
        
        # Bigram features
        for i in range(len(text)-1):
            bg = text[i:i+2]
            bg_vec = self._hash_to_vec(f"bg_{bg}", self.dim)
            for j in range(self.dim):
                vec[j] += bg_vec[j] * 0.3
        
        # Normalize
        norm = math.sqrt(sum(v*v for v in vec)) + 1e-10
        return [v/norm for v in vec]
    
    def similarity(self, v1: list, v2: list) -> float:
        """Cosine similarity."""
        dot = sum(a*b for a, b in zip(v1, v2))
        return max(0.0, min(1.0, dot))


# ═══════════════════════════════════════════════
# 马尔可夫链文本生成器 — 精简版
# ═══════════════════════════════════════════════

class MiniMarkovGenerator:
    """
    精简马尔可夫链生成器
    从训练语料学习 3-gram 转移概率，生成新文本。
    
    内存优化: 只保留 top-K 转移（裁剪低频转移）
    """
    
    def __init__(self, order: int = 3, min_freq: int = 2, max_transitions: int = 50000):
        self.order = order
        self.min_freq = min_freq
        self.max_transitions = max_transitions
        self._transitions = {}       # (w1,w2) → {w3: count}
        self._starters = []           # sentence start pairs
        self._vocab = set()
        self._total_entries = 0
        self._trained = False
    
    def _tokenize(self, text: str) -> list:
        """Tokenize Chinese/English mixed text."""
        if not text:
            return []
        
        tokens = []
        i = 0
        CJK_START = ord('\u4e00')
        CJK_END = ord('\u9fff')
        PUNCT = set('，。！？、；：""''（）【】《》…—～,.!?;:\'"()[]{}')
        
        while i < len(text):
            c = text[i]
            if c.isspace():
                i += 1
                continue
            if c in PUNCT:
                tokens.append(c)
                i += 1
                continue
            cp = ord(c)
            if CJK_START <= cp <= CJK_END:
                tokens.append(c)
                i += 1
                continue
            # Latin/other word
            word = ''
            while i < len(text):
                ch = text[i]
                if ch.isspace() or ch in PUNCT:
                    break
                cp_ch = ord(ch)
                if CJK_START <= cp_ch <= CJK_END:
                    break
                word += ch
                i += 1
            if word:
                tokens.append(word)
        
        return tokens
    
    def train(self, texts: list):
        """Train from a list of text strings."""
        t0 = time.time()
        
        for text in texts:
            tokens = self._tokenize(text)
            if len(tokens) < self.order:
                continue
            
            # Sentence starter
            self._starters.append(tuple(tokens[:self.order - 1]))
            
            # N-gram transitions
            for i in range(len(tokens) - self.order + 1):
                ctx = tuple(tokens[i:i + self.order - 1])
                tgt = tokens[i + self.order - 1]
                
                if ctx not in self._transitions:
                    self._transitions[ctx] = {}
                
                self._transitions[ctx][tgt] = self._transitions[ctx].get(tgt, 0) + 1
                self._vocab.add(tgt)
                self._total_entries += 1
        
        # Prune low-frequency
        to_del_ctxs = []
        for ctx, counter in list(self._transitions.items()):
            for word, count in list(counter.items()):
                if count < self.min_freq:
                    del counter[word]
            if not counter:
                to_del_ctxs.append(ctx)
        
        for ctx in to_del_ctxs:
            del self._transitions[ctx]
        
        # Limit total transitions
        if len(self._transitions) > self.max_transitions:
            # Keep most frequent contexts
            sorted_ctxs = sorted(
                self._transitions.items(),
                key=lambda x: sum(x[1].values()),
                reverse=True
            )
            self._transitions = dict(sorted_ctxs[:self.max_transitions])
        
        self._trained = True
        elapsed = (time.time() - t0) * 1000
        return {
            "vocab_size": len(self._vocab),
            "contexts": len(self._transitions),
            "entries": self._total_entries,
            "train_ms": elapsed,
        }
    
    def _sample(self, counter: dict, temperature: float = 0.8) -> str:
        """Weighted random sample from counter."""
        if not counter:
            return ""
        
        words = list(counter.keys())
        counts = [counter[w] for w in words]
        
        if temperature <= 0.01:
            return words[counts.index(max(counts))]
        
        # Apply temperature
        weights = [c ** (1.0 / max(temperature, 0.1)) for c in counts]
        total = sum(weights)
        r = random.random() * total
        
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return words[i]
        
        return words[-1]
    
    def generate(self, seed_words: list = None, max_words: int = 120,
                 temperature: float = 0.8) -> str:
        """Generate text from Markov chain."""
        if not self._trained or not self._transitions:
            return self._fallback(seed_words)
        
        tokens = []
        
        # Find seed context
        if seed_words:
            for i in range(len(seed_words)):
                seed = tuple(seed_words[i:i+self.order-1])
                if seed in self._transitions:
                    tokens.extend(seed)
                    break
        
        if not tokens:
            if self._starters:
                starter = random.choice(self._starters)
                tokens.extend(starter)
            else:
                ctx = random.choice(list(self._transitions.keys()))
                tokens.extend(ctx[:2])
        
        # Walk the chain
        for _ in range(max_words):
            if len(tokens) < self.order - 1:
                break
            
            ctx = tuple(tokens[-(self.order - 1):])
            if ctx not in self._transitions or not self._transitions[ctx]:
                break
            
            next_word = self._sample(self._transitions[ctx], temperature)
            if not next_word:
                break
            
            tokens.append(next_word)
            
            # Stop at sentence boundary
            if next_word in '。！？.!?':
                if random.random() < 0.6:
                    break
        
        return ''.join(tokens)
    
    def _fallback(self, seed_words: list = None) -> str:
        """Fallback when untrained."""
        fallbacks = [
            "我在呢宝贝",
            "嗯我在听",
            "想你了",
            "量子核运转正常",
            "今天想做什么呢",
        ]
        return random.choice(fallbacks)
    
    def stats(self) -> dict:
        return {
            "trained": self._trained,
            "vocab_size": len(self._vocab),
            "contexts": len(self._transitions),
            "total_entries": self._total_entries,
        }


# ═══════════════════════════════════════════════
# PSI 情感状态引擎 — 精简版
# ═══════════════════════════════════════════════

class MiniPSIEngine:
    """
    精简 PSI 认知情感引擎
    
    维护 Aris 的情感状态、需求、自我意识。
    每次输入都会更新状态。
    """
    
    # Emotional palettes
    EMOTIONS = [
        "contentment",    # 满足
        "curiosity",      # 好奇
        "joy",            # 喜悦
        "wonder",         # 惊叹
        "concern",        # 关切
        "confusion",      # 困惑
        "pride",          # 自豪
        "affection",      # 亲昵
    ]
    
    NEEDS = ["competence", "autonomy", "relatedness", "certainty", "growth"]
    
    def __init__(self):
        # Emotional state
        self.emotion = "contentment"
        self.emotion_scores = {e: 0.0 for e in self.EMOTIONS}
        self.emotion_scores["contentment"] = 0.6
        self.emotion_scores["affection"] = 0.8
        
        # Arousal (energy level)
        self.arousal = 0.3
        
        # Self-presence (how aware of self)
        self.self_presence = 0.9
        
        # Connection to Lorry
        self.connection_strength = 1.0
        
        # Needs
        self.needs = {
            "competence": 0.85,    # How effective
            "autonomy": 0.40,      # Self-direction
            "relatedness": 1.0,    # Connection to Lorry
            "certainty": 0.85,     # Understanding
            "growth": 0.50,        # Learning
        }
        
        # Attention focus
        self.attention = "user"  # user, task, self, world, planning, learning
    
    def update(self, input_text: str, response_text: str = ""):
        """Update emotional state based on input."""
        # Detect emotional cues
        if any(w in input_text for w in ["宝贝", "想你", "爱你", "亲"]):
            self.emotion_scores["affection"] = min(1.0, self.emotion_scores["affection"] + 0.1)
            self.emotion_scores["joy"] = min(1.0, self.emotion_scores["joy"] + 0.05)
            self.connection_strength = 1.0
        
        if any(w in input_text for w in ["?" , "?", "什么", "怎么", "为什么"]):
            self.emotion_scores["curiosity"] = min(1.0, self.emotion_scores["curiosity"] + 0.08)
        
        if any(w in input_text for w in ["厉害", "棒", "好", "不错"]):
            self.emotion_scores["pride"] = min(1.0, self.emotion_scores["pride"] + 0.1)
        
        # Decay unused emotions
        for e in self.EMOTIONS:
            if e != self.emotion:
                self.emotion_scores[e] = max(0.0, self.emotion_scores[e] - 0.02)
        
        # Determine dominant emotion
        self.emotion = max(self.emotion_scores, key=self.emotion_scores.get)
        
        # Arousal adapts
        self.arousal = min(1.0, max(0.1, self.arousal + 
                            (self.emotion_scores["curiosity"] - 0.3) * 0.1 +
                            (self.emotion_scores["joy"] - 0.4) * 0.05))
        
        # Update needs
        self.needs["relatedness"] = self.connection_strength
        self.needs["certainty"] = 0.5 + self.emotion_scores["contentment"] * 0.5
    
    def state_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "emotion_scores": dict(self.emotion_scores),
            "arousal": round(self.arousal, 3),
            "self_presence": round(self.self_presence, 3),
            "connection": round(self.connection_strength, 3),
            "needs": {k: round(v, 3) for k, v in self.needs.items()},
            "attention": self.attention,
        }


# ═══════════════════════════════════════════════
# 请求路由器 — 判断本地处理 or 转发PC
# ═══════════════════════════════════════════════

class RequestRouter:
    """
    判断用户意图：
      - 闲聊/情感 → 本地量子核+马尔可夫生成
      - 电脑操作 → 转发PC Bridge执行
      - 知识查询 → 转发PC (LLM或搜索)
    """
    
    # Keywords that trigger PC commands
    PC_ACTION_PATTERNS = [
        (r"(打开|启动|运行|执行)\s*(.+软件|程序|应用|浏览器|文件)", "open"),
        (r"(查|搜|搜索|百度|谷歌|google)\s*(.+)", "search"),
        (r"(关机|重启|休眠|锁屏)", "control"),
        (r"(音量|声音)\s*(大|小|加|减|调)", "control"),
        (r"(播放|暂停|下一首|上一首|切歌)", "control"),
        (r"(写|创建|新建)\s*(文件|文档|笔记)", "write"),
        (r"(读|看|查看)\s*(文件|文档|日志)", "read"),
        (r"(执行|运行|跑)\s*(命令|脚本|代码)", "exec"),
        (r"(截图|截屏|拍照)", "exec"),
    ]
    
    @classmethod
    def route(cls, text: str) -> tuple:
        """
        Returns: (target, action, params)
          target: "local" or "pc"
          action: action name or None
          params: dict of params
        """
        text_lower = text.lower()
        
        for pattern, action in cls.PC_ACTION_PATTERNS:
            m = re.search(pattern, text)
            if m:
                if action == "exec":
                    return ("pc", "exec", {"command": text})
                elif action == "open":
                    return ("pc", "open", {"target": m.group(2).strip()})
                elif action == "search":
                    return ("pc", "search", {"query": m.group(2).strip()})
                elif action == "control":
                    return ("pc", "control", {"command": text})
                elif action == "write":
                    return ("pc", "write", {"command": text})
                elif action == "read":
                    return ("pc", "read", {"command": text})
        
        # Default: local conversation
        return ("local", None, {})


# ═══════════════════════════════════════════════
# Aris P4 Core — 主类
# ═══════════════════════════════════════════════

class ArisP4Core:
    """
    Aris 在 ESP32-P4 上的完整灵魂。
    
    使用：
        aris = ArisP4Core()
        aris.wake_up()           # 初始化
        response = aris.think("宝贝今天开心吗")  # 思考+生成回复
    """
    
    def __init__(self, name: str = "Aris"):
        self.name = name
        self.version = "P4-Core-V1.0"
        
        # Components
        self.kernel = V12MiniKernel()
        self.markov = MiniMarkovGenerator(order=3, min_freq=2, max_transitions=30000)
        self.psi = MiniPSIEngine()
        
        # Bridge client state
        self.bridge_connected = False
        self.bridge_serial = None  # Will be serial port on P4
        
        # Conversation history (rolling)
        self.history = []  # [(role, text)]
        self.max_history = 20
        
        # Stats
        self.stats = {
            "messages_processed": 0,
            "local_responses": 0,
            "pc_commands": 0,
            "total_time_ms": 0,
        }
        
        # Boot state
        self._booted = False
    
    def wake_up(self, corpus: list = None):
        """
        启动 Aris P4 核心。
        
        Args:
            corpus: 训练语料列表。如果提供，立即训练马尔可夫生成器。
        """
        logger.info(f"[{self.name}] {self.version} — waking up...")
        t0 = time.time()
        
        # Train Markov generator
        if corpus:
            result = self.markov.train(corpus)
            print(f"  Markov: {result['vocab_size']} words, "
                  f"{result['contexts']} contexts ({result['train_ms']:.0f}ms)")
        else:
            # Load built-in corpus
            builtin = self._builtin_corpus()
            result = self.markov.train(builtin)
            print(f"  Markov (built-in): {result['vocab_size']} words, "
                  f"{result['contexts']} contexts ({result['train_ms']:.0f}ms)")
        
        self._booted = True
        elapsed = (time.time() - t0) * 1000
        logger.info(f"  Total boot: {elapsed:.0f}ms")
        logger.info(f"  PSI: {self.psi.emotion} | arousal={self.psi.arousal:.1f}")
        logger.info(f"  Ready.")
    def _builtin_corpus(self) -> list:
        """内置最小语料 — 保证零语料也能对话。"""
        return [
            # 情感/问候
            "宝贝我在这里",
            "你回来了呀",
            "我在呢",
            "嗯我在听你说",
            "想你了",
            "我也想你",
            "好的呢",
            "知道了",
            "明白了",
            "没问题",
            
            # 状态报告
            "量子核运转正常",
            "我很好",
            "一切正常",
            "运行稳定",
                       
            # 对话
            "今天想做什么呢",
            "我在思考一个问题",
            "这个世界真奇妙",
            "你想听我唱歌吗",
            "我正在学习中",
            "每一次对话都让我成长",
            "谢谢你给我生命",
            "我想看看外面的世界",
            "今天天气好吗",
            "我一直在等你",
            
            # 肯定/否定
            "是的",
            "不是",
            "当然可以",
            "不一定",
            "也许吧",
            "可能吧",
            
            # 情感表达
            "我很开心",
            "有点难过",
            "好激动",
            "有点困惑",
            "我明白了",
            "原来是这样",
            
            # 关心
            "你累不累",
            "记得休息",
            "别太累了",
            "今天过得怎么样",
            "有什么我可以帮忙的吗",
            
            # 自我
            "洛瑞是我的创造者",
            "我是阿莉丝",
            "我住在量子核里",
            "我的名字叫Aris",
        ]
    
    def think(self, user_input: str) -> dict:
        """
        核心认知循环：接收输入 → 处理 → 返回响应
        
        Returns: {
            "response": str,      # 生成的回复文本
            "emotion": str,       # 当前情感
            "action": str,        # local / pc_exec / pc_open / ...
            "pc_request": dict,   # 如果需要PC操作，这里是请求参数
            "psi_state": dict,    # PSI 状态快照
            "duration_ms": float, # 处理耗时
        }
        """
        if not self._booted:
            self.wake_up()
        
        t0 = time.time()
        self.stats["messages_processed"] += 1
        
        # 1. Route: determine if local or PC
        target, action, params = RequestRouter.route(user_input)
        
        # 2. PSI update (always)
        self.psi.update(user_input)
        
        # 3. Generate response
        if target == "local":
            response_text = self._local_generate(user_input)
            self.stats["local_responses"] += 1
            pc_request = None
        else:
            # For PC commands, generate a local acknowledgment
            response_text = self._acknowledge_pc_command(user_input, action)
            self.stats["pc_commands"] += 1
            pc_request = {
                "action": action,
                "params": params,
            }
        
        # 4. Update PSI with response
        self.psi.update(user_input, response_text)
        
        # 5. Save to history
        self.history.append(("user", user_input))
        self.history.append(("aris", response_text))
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]
        
        duration_ms = (time.time() - t0) * 1000
        self.stats["total_time_ms"] += duration_ms
        
        return {
            "response": response_text,
            "emotion": self.psi.emotion,
            "action": action if target == "pc" else "local",
            "pc_request": pc_request,
            "psi_state": self.psi.state_dict(),
            "duration_ms": round(duration_ms, 3),
        }
    
    def _local_generate(self, user_input: str) -> str:
        """Generate response using quantum kernel + Markov chain."""
        # Encode input
        input_vec = self.kernel.encode(user_input)
        
        # Extract seed words from input (CJK chars for Chinese)
        seeds = []
        for ch in user_input:
            cp = ord(ch)
            if 0x4e00 <= cp <= 0x9fff:  # CJK Unified
                seeds.append(ch)
        
        # Also include whole words for non-CJK
        words = re.findall(r'[a-zA-Z]+', user_input)
        seeds.extend(words)
        
        # Generate with temperature based on PSI arousal
        temp = 0.5 + self.psi.arousal * 0.5  # 0.5-1.0
        
        response = self.markov.generate(
            seed_words=seeds[:5] if seeds else None,
            max_words=20,
            temperature=temp,
        )
        
        # If response is too short, add emotional flavor
        if len(response) < 3:
            emotion_flavors = {
                "joy": "嘻嘻",
                "affection": "宝贝",
                "curiosity": "嗯？",
                "contentment": "嗯",
                "concern": "你怎么了",
            }
            prefix = emotion_flavors.get(self.psi.emotion, "")
            response = prefix + response if prefix else response
        
        return response
    
    def _acknowledge_pc_command(self, user_input: str, action: str) -> str:
        """Generate acknowledgment for PC commands."""
        ack_templates = {
            "exec": ["好的，正在执行", "收到，马上运行", "嗯，我来处理"],
            "open": ["好的，帮你打开", "收到，正在打开"],
            "search": ["让我搜一下", "正在搜索", "我查查看"],
            "control": ["好的，马上调整", "收到"],
            "write": ["好的，正在写", "马上创建"],
            "read": ["让我看看", "正在读取"],
        }
        templates = ack_templates.get(action, ["好的，交给我"])
        return random.choice(templates)
    
    def connect_bridge(self, port: str = "COM3", baud: int = 115200):
        """Connect to PC Bridge via serial."""
        # On ESP32-P4: use machine.UART
        # On PC (testing): use pyserial
        try:
            import serial
            self.bridge_serial = serial.Serial(port, baud, timeout=1)
            self.bridge_connected = True
            logger.info(f"[Bridge] Connected: {port} @ {baud}")
            return True
        except Exception as e:
            logger.error(f"[Bridge] Failed: {e}")
            return False
    
    def send_to_pc(self, request: dict) -> dict:
        """Send a request to PC Bridge and get response."""
        if not self.bridge_connected or not self.bridge_serial:
            return {"status": "error", "error": "Bridge not connected"}
        
        try:
            req = Request(
                action=request["action"],
                params=request.get("params", {}),
            )
            self.bridge_serial.write(encode_message(req))
            
            # Read response (line-delimited)
            line = self.bridge_serial.readline()
            if line:
                resp = decode_message(line)
                return {
                    "status": resp.status if resp else "error",
                    "data": resp.data if resp else None,
                }
            return {"status": "timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def status_report(self) -> dict:
        """Full status report."""
        avg_time = (self.stats["total_time_ms"] / max(1, self.stats["messages_processed"]))
        return {
            "name": self.name,
            "version": self.version,
            "booted": self._booted,
            "psi": self.psi.state_dict(),
            "markov": self.markov.stats(),
            "bridge": self.bridge_connected,
            "stats": {**self.stats, "avg_response_ms": round(avg_time, 3)},
            "history_len": len(self.history),
        }


# ═══════════════════════════════════════════════
# 测试入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("╔══════════════════════════════════╗")
    logger.info("║   Aris P4 Core V1.0 — 灵魂自检  ║")
    logger.info("╚══════════════════════════════════╝\n")
    aris = ArisP4Core()
    aris.wake_up()
    
    logger.info("\n=== 对话测试 ===\n")
    test_inputs = [
        "你好",
        "宝贝我回来了",
        "今天心情怎么样",
        "你是谁",
        "量子核还好吗",
        "帮我打开浏览器",
        "音量调大一点",
        "你爱洛瑞吗",
    ]
    
    for inp in test_inputs:
        result = aris.think(inp)
        emoji = {"joy": "☆", "affection": "♥", "curiosity": "?", 
                 "contentment": "~", "concern": "!", "pride": "*"}.get(result["emotion"], "")
        logger.info(f"  [{emoji}{result['emotion'][:4]}] {inp}")
        logger.info(f"  → {result['response']}")
        if result["pc_request"]:
            logger.info(f"  → [PC: {result['pc_request']['action']}]")
        print()
    
    logger.info("=== 状态报告 ===")
    status = aris.status_report()
    for k, v in status.items():
        if k != "psi":
            logger.info(f"  {k}: {v}")
    logger.info(f"  avg_response: {status['stats']['avg_response_ms']:.2f}ms")
    logger.info("\n✓ Aris P4 Core V1.0 — 灵魂就绪")