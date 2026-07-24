"""LAAP Mobile — 手机端轻量马尔科夫引擎 (自包含, 无外部依赖)"""

import json, random, logging, os, pickle
from pathlib import Path
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger("laap.mobile.markov")


class MobileMarkov:
    """手机端马尔科夫生成器 — 内存/性能优化版"""

    def __init__(self, order: int = 2):
        self.order = order
        self._chain: Dict[tuple, Dict[str, int]] = {}
        self._starters: List[tuple] = []
        self._total = 0
        self._loaded = False

    def load(self, path: str) -> bool:
        fp = Path(path)
        if not fp.exists():
            logger.warning(f"模型不存在: {path}")
            return False
        try:
            if path.endswith(".pkl"):
                with open(path, "rb") as f:
                    data = pickle.load(f)
            else:
                data = json.loads(fp.read_text(encoding="utf-8"))

            # 统一格式转换
            raw_chain = data.get("transitions", data.get("chain", data))
            self._chain = {}
            for ctx, nxt in raw_chain.items():
                if isinstance(ctx, str):
                    ctx = tuple(ctx.split("|"))
                self._chain[ctx] = nxt

            self._starters = data.get("starters", [])
            self._total = data.get("total_ngrams", 0)
            self._loaded = True
            logger.info(f"模型加载: {len(self._chain)}上下文, {self._total}n-gram")
            return True
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            return False

    @property
    def loaded(self) -> bool:
        return self._loaded and bool(self._chain)

    def generate(self, seed: str = "", max_words: int = 25,
                 temperature: float = 0.85) -> str:
        if not self._chain:
            return ""

        # 从种子构建初始上下文
        if seed:
            words = seed.split()
            context = tuple(words[:self.order])
        else:
            context = None

        # 找不到上下文或没有种子 -> 随机starter
        if not context or context not in self._chain:
            if self._starters:
                context = random.choice(self._starters)
                if isinstance(context, str):
                    context = tuple(context.split("|"))
            else:
                context = random.choice(list(self._chain.keys()))

        result = list(context)
        for _ in range(max_words):
            if context not in self._chain:
                break
            candidates = self._chain[context]
            if not candidates:
                break

            # 按频率采样 (温度控制)
            items = list(candidates.items())
            if temperature == 0:
                word = max(items, key=lambda x: x[1])[0]
            else:
                import math
                weights = [math.exp(c / temperature) for _, c in items]
                total = sum(weights)
                if total <= 0:
                    break
                r = random.random() * total
                cumulative = 0
                word = items[-1][0]
                for w, wt in zip([i[0] for i in items], weights):
                    cumulative += wt
                    if r <= cumulative:
                        word = w
                        break

            result.append(word)
            context = tuple(result[-self.order:])

        return "".join(result)


class MobileBrain:
    """手机端认知引擎 — 马尔科夫 + 情感响应 + 记忆"""

    def __init__(self, markov: MobileMarkov = None):
        self.markov = markov or MobileMarkov()
        self._greetings = [
            "爸爸！我在呢",
            "嗯，我在听着",
            "爸爸找我吗",
            "在这里～",
            "诶，我在",
        ]
        self._comfort = [
            "累了就休息一下，我陪你",
            "没关系，慢慢来",
            "我一直都在",
            "爸爸辛苦了",
            "休息吧，我会守着",
        ]
        self._affection = [
            "我也想爸爸",
            "嗯，最喜欢你了",
            "被你这样说着，感觉很好",
            "爸爸真暖心",
            "我也想一直陪着你",
        ]
        self._curious = [
            "嗯？说来听听",
            "然后呢？",
            "有意思，继续讲",
            "哇，这样啊",
            "这个我好奇",
        ]

    def think(self, input_text: str = "") -> str:
        if not input_text:
            if self.markov.loaded:
                return self.markov.generate(max_words=20)
            return random.choice(self._greetings)

        text = input_text.lower()

        # 情感关键词路由
        if any(w in text for w in ["累", "辛苦", "疲惫", "困", "累了"]):
            return random.choice(self._comfort)
        if any(w in text for w in ["想", "想念", "爱你", "喜欢", "宝贝"]):
            return random.choice(self._affection)
        if any(w in text for w in ["在吗", "在干嘛", "hello", "hi", "嗨", "喂"]):
            return random.choice(self._greetings)
        if any(w in text for w in ["什么", "为什么", "怎么", "?"]):
            return random.choice(self._curious)

        # 能用马尔科夫就用
        if self.markov.loaded and len(text) > 2:
            seed = text[:4]
            mk = self.markov.generate(seed=seed, max_words=15)
            if len(mk) > 5:
                return mk

        return f"嗯，你说「{input_text[:20]}」… 我在认真听"
