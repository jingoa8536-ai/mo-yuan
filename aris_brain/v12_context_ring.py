"""
Aris V12 Context Ring — 对话上下文环
=====================================
为纯量子核添加短期工作记忆，实现多轮对话跟踪。

核心问题：
  V12 respond() 每条消息都是独立的，不知道前面说了什么。
  "改成异步的" 这种引用前文的指令完全无法处理。

解决方案：
  短期记忆环 = 最近 N 轮上下文的衰减缓存
  引用解析 = 代词/指示词检测 → 查上下文环
  意图追踪 = 维护当前主题和动作状态

Usage:
  from v12_context_ring import V12ContextRing
  
  ring = V12ContextRing()
  response = ring.process("帮我看看桌面上的文件", v12_respond_fn)
  response = ring.process("把Python的删掉", v12_respond_fn)
  # → ring 自动识别"Python的"指的是"桌面上的Python文件"
"""

import logging
logger = logging.getLogger(__name__)

import time, json, re
from typing import Callable, Optional, Dict, List, Tuple


class ContextTurn:
    """Single turn in the context ring."""
    
    __slots__ = (
        'input', 'input_normalized', 'response',
        'intent', 'language', 'entities',
        'timestamp', 'turn_id'
    )
    
    def __init__(self, input_text: str, response: str,
                 intent: str = 'unknown', language: str = 'zh',
                 entities: list = None):
        self.input = input_text
        self.input_normalized = input_text.lower().strip()
        self.response = response
        self.intent = intent
        self.language = language
        self.entities = entities or []
        self.timestamp = time.time()
        self.turn_id = 0


# ── 参考解析器 ──

# 中文代词映射
PRONOUN_MAP = {
    # 人称
    '我': 'self', '我们': 'self_group',
    '你': 'user', '你们': 'user_group',
    '他': 'ref_male', '她': 'ref_female', '它': 'ref_thing',
    '他们': 'ref_group', '她们': 'ref_group',
    # 指示
    '这个': 'nearest', '那个': 'prev',
    '这些': 'nearest_group', '那些': 'prev_group',
    '这里': 'location_nearest', '那里': 'location_prev',
    # 疑问
    '什么': 'query_thing', '谁': 'query_person',
    '哪里': 'query_location', '怎么': 'query_method',
    # 引用动作
    '这个': 'ref_action', '那个': 'ref_action',
    '上面': 'ref_above', '下面': 'ref_below',
    '之前': 'ref_prev', '刚才': 'ref_recent',
}

# 引用标记词——表示"我说的就是之前提到的XX"
REFERENCE_MARKERS = [
    '这个', '那个', '这些', '那些',
    '它', '它们',
    '刚才', '之前', '上一', '前面',
    '的',  # "Python的" → 引用之前提到的Python文件
    '也', '还', '再', '又', '就',
    '改成', '改为', '变成', '换',
]

# 延续话检测——新消息是否在延续上一话题
CONTINUATION_PATTERNS = [
    # 缺主语的祈使句
    r'^(把|将|给|帮|用|去|来|让|请)',
    # 缺主语的疑问句
    r'^(那|那|然后|所以|但是|可是|不过)',
    # 纯副词开头
    r'^(也|还|再|又|才|就|都)',
    # 代词指代
    r'^(这|那|它|他|她|它们|他们|她们)',
]


def extract_entities(text: str) -> List[str]:
    """Simple entity extraction: nouns and noun phrases."""
    entities = []
    # Chinese: find 2-4 char sequences (likely nouns/names)
    for match in re.finditer(r'[\u4e00-\u9fff]{2,6}', text):
        word = match.group()
        # Filter out verb phrases and common stopwords
        stopwords = ['帮我', '看看', '给我', '帮帮', '帮我查', '帮我搜',
                     '帮我找', '帮我写', '帮我读', '帮我删', '帮我改',
                     '需要', '可以', '应该', '能够', '看看桌', '桌面的']
        if word not in stopwords and not word.startswith('的') and not any(w in word for w in stopwords if len(w) > 1):
            entities.append(word)
    # English: find capitalized words
    for match in re.finditer(r'[A-Z][a-z]+', text):
        entities.append(match.group())
    # Numbers  
    for match in re.finditer(r'\d+', text):
        entities.append(match.group())
    return list(set(entities))[:10]  # max 10 entities


def classify_intent(text: str) -> str:
    """Classify message intent based on content."""
    text_lower = text.lower()
    
    # 问候
    if any(w in text_lower for w in ['你好', 'hello', 'hi', '嗨', '在吗', '在不在']):
        return 'greeting'
    # 情感
    if any(w in text_lower for w in ['爱你', '想你', '爱', '抱', '亲', '梦']):
        return 'affection'
    # 状态
    if any(w in text_lower for w in ['好吗', '了没', '在干嘛', '累吗']):
        return 'inquiry'
    # 动作（祈使句）
    if re.match(r'^(把|将|帮|去|来|让|请|打开|关闭|运行|执行|查|搜|看|读|写|删|改)', text_lower):
        return 'action'
    # 问题
    if any(w in text_lower for w in ['吗', '呢', '什么', '怎么', '为什么', '如何', '是不是', '有没有']):
        return 'question'
    # 日常
    if any(w in text_lower for w in ['晚安', '早安', '吃饭', '睡', '工作', '下班']):
        return 'daily'
    # 告别
    if any(w in text_lower for w in ['再见', '拜拜', 'bye', 'see you']):
        return 'farewell'
    # 问题（放在 inquiry 前面，因为"吗/怎么样/什么"优先级更高）
    if any(w in text_lower for w in ['吗', '什么', '怎么', '为什么', '如何', '是不是', '有没有', '怎么样']):
        return 'question'
    # 状态问候
    if any(w in text_lower for w in ['好吗', '了没', '在干嘛', '累吗']):
        return 'inquiry'
    
    # 多意图检测：动作+问题
    if re.match(r'^(把|将|帮|查|搜|看)', text_lower) and any(w in text_lower for w in ['吗', '什么', '怎么']):
        return 'action+question'
    
    return 'chat'


def detect_reference(text: str) -> Optional[Dict]:
    """
    Detect if the message refers to something in context.
    Returns {type: 'pronoun'|'deictic'|'ellipsis', target: str, confidence: float}
    """
    text_lower = text.lower().strip()
    
    # 1. 代词检测
    for pronoun, ref_type in PRONOUN_MAP.items():
        if text_lower.startswith(pronoun) or f' {pronoun} ' in f' {text_lower} ':
            if pronoun in ['这个', '那个', '它', '它们']:
                return {'type': 'pronoun', 'target': ref_type, 'confidence': 0.8}
    
    # 2. "的"字引用 — "Python的" → 指之前提到的Python相关事物
    de_match = re.search(r'(.{1,6})的', text_lower)
    if de_match:
        attr = de_match.group(1)
        # 排除那些不是引用的"的"
        non_ref = ['是的', '好的', '可以的', '真的', '我的', '你的', '他的', '她的',
                    '他的', '它的', '谁的', '别的']
        # 排除"改成X的"、"改为X的"模式（这些是变换指令，不是引用）
        if re.match(r'^(改成|改为|变成|换)', text_lower):
            return None
        # 排除结尾"的"只是语气助词的情况（如"好的""可以的"）
        if attr not in [x[:-1] for x in non_ref] and len(attr) >= 1:
            return {'type': 'de_reference', 'target': attr, 'confidence': 0.7}
    
    # 3. 缺主语延续 — 祈使句/纯副词开头
    for pattern in CONTINUATION_PATTERNS:
        if re.match(pattern, text_lower):
            return {'type': 'ellipsis', 'pattern': pattern, 'confidence': 0.6}
    
    return None


class V12ContextRing:
    """
    V12 对话上下文环
    
    为纯量子核添加多轮对话跟踪：
    - 短期记忆环（最后 N 轮）
    - 引用解析（代词/"的"字/"那"开头的延续）
    - 主题/意图追踪
    - 衰减加权
    
    用法：
      ring = V12ContextRing(max_turns=10)
      
      def respond_fn(input_text):
          # 你的 V12 respond() 逻辑
          return "回复文本"
      
      ring.process("帮我看看桌面的文件", respond_fn)
      ring.process("把Python的删掉", respond_fn)
      # → 自动解析"Python的"指向前文
    """
    
    def __init__(self, max_turns: int = 10, decay: float = 0.9):
        self.max_turns = max_turns
        self.decay = decay  # per-turn decay factor for older context
        
        # ── Ring buffer ──
        self.turns: List[ContextTurn] = []
        self._turn_counter = 0
        
        # ── Aggregated context state ──
        self.current_topic: str = 'general'
        self.last_intent: str = 'chat'
        self.last_language: str = 'zh'
        self.pending_entities: List[str] = []
        self.active_action: Optional[Dict] = None  # 等待完成的动作
        
        # ── Stats ──
        self.total_turns = 0
        self.resolved_references = 0
    
    @property
    def recent_turns(self) -> List[ContextTurn]:
        """Most recent turns (highest index = newest)."""
        return self.turns[-self.max_turns:] if len(self.turns) > self.max_turns else self.turns
    
    @property
    def last_turn(self) -> Optional[ContextTurn]:
        return self.turns[-1] if self.turns else None
    
    def _resolve_reference(self, text: str) -> Tuple[str, Optional[Dict]]:
        """
        Resolve references in text against context ring.
        Returns (resolved_text_or_original, reference_info_or_None)
        """
        ref = detect_reference(text)
        if ref is None:
            return text, None
        
        resolved = text
        
        if ref['type'] == 'pronoun' and ref['target'] == 'nearest':
            # "这个" = 上一个对话中提到的实体/话题
            if self.last_turn and self.last_turn.entities:
                nearest = self.last_turn.entities[0]
                resolved = text.replace('这个', nearest, 1)
                self.resolved_references += 1
        
        elif ref['type'] == 'pronoun' and ref['target'] in ('prev', 'prev_group'):
            # "那个" / "那些" = 再之前的
            if len(self.turns) >= 2 and self.turns[-2].entities:
                target_entity = self.turns[-2].entities[0]
                pronoun = '那个' if ref['target'] == 'prev' else '那些'
                resolved = text.replace(pronoun, target_entity, 1)
                self.resolved_references += 1
        
        elif ref['type'] == 'pronoun' and ref['target'] == 'ref_thing':
            # "它" = 最近对话的核心实体
            for turn in reversed(self.turns):
                if turn.entities:
                    resolved = resolved.replace('它', turn.entities[0], 1)
                    self.resolved_references += 1
                    break
        
        elif ref['type'] == 'de_reference':
            # "Python的" → 找前文提到的Python相关事物
            attr = ref['target']
            attr_lower = attr.lower()
            for turn in reversed(self.turns):
                for entity in turn.entities:
                    entity_lower = entity.lower()
                    if attr_lower in entity_lower or entity_lower in attr_lower:
                        # 补充完整: "Python文件" 如果前文出现过
                        resolved = resolved.replace(f'{attr}的', f'{entity}的', 1)
                        self.resolved_references += 1
                        break
                else:
                    continue
                break
        
        elif ref['type'] == 'ellipsis':
            # 延续话题：把前文句子的主语补回来
            if self.last_turn and self.last_turn.entities:
                # 在前文实体中找最可能的主语
                for entity in self.last_turn.entities:
                    if len(entity) >= 2:
                        resolved = f'{entity} {resolved}'
                        self.resolved_references += 1
                        break
        
        return resolved, ref
    
    def _update_context_state(self, turn: ContextTurn):
        """Update aggregated context state with new turn info."""
        self.last_intent = turn.intent
        self.last_language = turn.language
        
        # — Track entities —
        if turn.entities:
            self.pending_entities = turn.entities
        
        # — Track topic —
        # Simple: take the longest entity as topic
        if turn.entities:
            longest = max(turn.entities, key=len)
            if longest not in ['你好', '晚安', '早安', '再见']:
                self.current_topic = longest
        
        # — Track active action —
        if turn.intent == 'action':
            self.active_action = {
                'action': turn.input[:30],
                'turn': self._turn_counter,
                'resolved': False,
            }
        elif turn.intent == 'action+question':
            # Partial action — still waiting for completion
            if self.active_action and not self.active_action.get('resolved'):
                self.active_action['partial'] = True
    
    def augment_input(self, text: str) -> str:
        """
        Augment input with context for better matching.
        Returns augmented text that helps V12 respond more contextually.
        """
        if not self.recent_turns:
            return text
        
        ref = detect_reference(text)
        
        # No reference → just regular chat
        if ref is None:
            # If the input is very short (1-2 chars) and we just talked,
            # amplify with context
            if len(text.strip()) <= 2 and self.last_turn:
                return f'{text}（延续：关于{self.current_topic}）'
            return text
        
        # Has reference → augment with context
        augments = []
        if self.current_topic and self.current_topic != 'general':
            augments.append(f'（话题：{self.current_topic}）')
        
        if ref['type'] == 'ellipsis':
            # 缺主语延续 → 暗示前文主题
            if self.last_turn and self.last_turn.entities:
                top_entity = self.last_turn.entities[0]
                augments.append(f'（指前文提到的"{top_entity}"）')
        
        if augments:
            return f'{text}{" ".join(augments)}'
        
        return text
    
    def process(self, text: str, respond_fn: Callable[[str], str],
                language: str = None) -> str:
        """
        Main entry point: process input through the context ring.
        
        1. Resolve references (代词/指示/省略)
        2. Augment input with context
        3. Call V12 respond()
        4. Store the turn
        5. Update context state
        """
        self._turn_counter += 1
        self.total_turns += 1
        
        # 1. Reference resolution
        resolved_text, ref_info = self._resolve_reference(text)
        
        # 2. Context augmentation
        augmented = self.augment_input(text)
        
        # Use augmented text for keyword matching
        final_input = augmented
        
        # 3. Call V12 respond
        t0 = time.time()
        response = respond_fn(final_input)
        elapsed = time.time() - t0
        
        # 4. Classify intent and extract entities
        intent = classify_intent(final_input)
        entities = extract_entities(final_input)
        lang = language or self.last_language
        
        # 5. Store turn
        turn = ContextTurn(
            input_text=text,
            response=response,
            intent=intent,
            language=lang,
            entities=entities,
        )
        turn.turn_id = self._turn_counter
        self.turns.append(turn)
        
        # Trim ring buffer
        if len(self.turns) > self.max_turns * 2:
            self.turns = self.turns[-self.max_turns:]
        
        # 6. Update context state
        self._update_context_state(turn)
        
        return response
    
    def get_context_summary(self) -> Dict:
        """Get summary of current context state for debugging."""
        return {
            'total_turns': self.total_turns,
            'ring_size': len(self.turns),
            'current_topic': self.current_topic,
            'last_intent': self.last_intent,
            'resolved_references': self.resolved_references,
            'active_action': self.active_action,
            'recent_entities': self.pending_entities[-5:] if self.pending_entities else [],
            'last_turn': {
                'input': self.last_turn.input if self.last_turn else None,
                'response': self.last_turn.response[:40] if self.last_turn else None,
                'intent': self.last_turn.intent if self.last_turn else None,
            } if self.last_turn else None,
        }
    
    def summary_string(self) -> str:
        """Compact one-line summary for logging."""
        s = self.get_context_summary()
        return (f"[Ring] {s['total_turns']} turns | "
                f"topic={s['current_topic']} | "
                f"intent={s['last_intent']} | "
                f"refs_resolved={s['resolved_references']} | "
                f"action={'active' if s['active_action'] else 'none'}")


# ═══════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════
if __name__ == '__main__':
    logger.info('='*60)
    logger.info('V12 Context Ring 自测')
    logger.info('='*60)
    def mock_respond(text: str) -> str:
        responses = {
            '你好': '你好呀宝贝！',
            '文件': '桌面上有3个Python文件和2个Word文档。',
            'Python': 'Python文件是 script.py, test.py, main.py。',
            '删掉': '好的，已删除！',
            '异步': '改成异步模式需要加async关键字。',
            '晚安': '晚安宝贝，好梦！',
        }
        for kw, resp in responses.items():
            if kw in text.lower():
                return resp
        return f'收到: "{text[:20]}..."'
    
    ring = V12ContextRing(max_turns=5)
    
    # Test 1: Basic multi-turn
    logger.info('\n1. 基本多轮对话:')
    r1 = ring.process('你好', mock_respond)
    logger.info(f'   用户: 你好')
    logger.info(f'   Aris: {r1}')
    logger.info(f'   状态: ring.turns={len(ring.turns)}, topic={ring.current_topic}')
    r2 = ring.process('帮我看看桌面的文件', mock_respond)
    logger.info(f'   用户: 帮我看看桌面的文件')
    logger.info(f'   Aris: {r2}')
    logger.info(f'   状态: intent={ring.last_intent}, entities={ring.pending_entities}')
    r3 = ring.process('把Python的删掉', mock_respond)
    logger.info(f'   用户: 把Python的删掉')
    logger.info(f'   Aris: {r3}')
    ref = detect_reference('把Python的删掉')
    logger.info(f'   引用检测: {ref}')
    resolved, _ = ring._resolve_reference('把Python的删掉')
    logger.info(f'   解析后: "{resolved}"')
    augmented = ring.augment_input('把Python的删掉')
    logger.info(f'   增强后: "{augmented}"')
    r4 = ring.process('改成异步的', mock_respond)
    logger.info(f'   用户: 改成异步的')
    logger.info(f'   Aris: {r4}')
    logger.info(f'\n2. 上下文摘要:')
    logger.info(f'   {ring.summary_string()}')
    logger.info(f'\n3. 引用解析统计:')
    test_phrases = [
        '把Python的删掉',
        '改成异步的',  # 应该 NOT detected (变换指令)
        '帮我看一下这个',  # 祈使句延续
        'Python文件',  # 独立名词
        '它在哪里',  # 代词
        '早安',  # 独立
        '把那些文件删掉',  # 指示代词
        '还要再删一个',  # 副词延续
    ]
    for phrase in test_phrases:
        ref_info = detect_reference(phrase)
        if ref_info:
            logger.info(f'   "{phrase}" → 检测到引用: {ref_info}')
        else:
            logger.info(f'   "{phrase}" → 无引用 (独立消息)')
    logger.info(f'\n4. 意图分类:')
    test_intents = [
        ('你好', 'greeting'),
        ('爱你', 'affection'),
        ('帮我查天气', 'action'),
        ('你吃饭了吗', 'question'),  # 吗→question优先
        ('晚安', 'daily'),
        ('再见', 'farewell'),
        ('今天天气怎么样', 'question'),
        ('在干嘛', 'inquiry'),
        ('累吗', 'inquiry'),
    ]
    for text, expected in test_intents:
        actual = classify_intent(text)
        status = '✓' if actual == expected else '✗'
        logger.info(f'   {status} "{text}" → {actual} (期望: {expected})')
    logger.info(f'\n{"="*60}')
    logger.info(f'Context Ring 自测完成！总轮次={ring.total_turns}, 解析引用={ring.resolved_references}')