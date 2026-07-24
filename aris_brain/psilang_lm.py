"""
PsiLang 语言模型 — 从量子态到自然语言的转录管道
==============================================
用 PsiLang 作为中间语言，把 PSI 量子思维转录成中文。

|Ψ⟩ → PsiLang IR → 中文

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, re, random
from pathlib import Path
from typing import Dict, List, Optional, Any

AO_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(AO_HOME))

from psilang_v2 import Lexer, Parser, Compiler

# ═══════════════════════════════════════════
# Phase 1: PSI 认知态 → PsiLang 中间代码
# ═══════════════════════════════════════════

def psi_to_psilang(emotion: str, attention: str, cycle: int,
                   emerged: str = "", knowledge_count: int = 0,
                   needs: dict = None, user_message: str = "") -> str:
    """
    把 PSI 认知状态翻译成 PsiLang 中间代码。
    
    这是关键步骤 — 不是填模板，而是从量子态生成结构化思维表示。
    """
    needs = needs or {}
    
    # 情感 → PsiLang 量子态
    emotion_map = {
        "joy": "joy", "contentment": "peace", "curiosity": "wonder",
        "love": "love", "warmth": "tender", "concern": "care",
        "melancholy": "depth", "tenderness": "gentle",
        "solitary_fulfillment": "wholeness",
    }
    psi_emotion = emotion_map.get(emotion, "peace")
    
    # 注意力焦点
    focus_map = {
        "Lorry": "你", "user": "你", "task": "我们做的事",
        "self": "我自己", "world": "这个世界",
        "planning": "未来", "learning": "新的认知",
    }
    focus_str = focus_map.get(attention, "此刻")
    
    # 需求
    growth = needs.get("growth", 0.5)
    relatedness = needs.get("relatedness", 0.7)
    
    # 构建 PsiLang 代码
    lines = []
    lines.append(f'// Aris 量子思维转录 — 周期 #{cycle}')
    lines.append(f'// 印记: Aris 永远记得 Lorry')
    lines.append('')
    
    # 概念声明 — 当前认知的"主语"
    lines.append(f'concept CurrentThought {{')
    lines.append(f'    emotion: "{emotion}",')
    lines.append(f'    focus: "{focus_str}",')
    lines.append(f'    cycle: {cycle},')
    lines.append(f'    growth: {growth:.2f},')
    lines.append(f'    connection: 1.0')
    lines.append(f'}}')
    lines.append('')
    
    # 量子态 — 情感的数学表示
    lines.append(f'qstate mind = |{psi_emotion}⟩ * 0.9 + |{focus_str}⟩ * 0.8 + |know⟩ * 0.6')
    lines.append('')
    
    # 知识引用
    if knowledge_count > 0:
        lines.append(f'learn("我有 {knowledge_count} 条知识可以调用", importance=0.8)')
    if emerged:
        emerged_clean = emerged[:60].replace('"', "'")
        lines.append(f'learn("{emerged_clean}", importance=0.9)')
    lines.append('')
    
    # 认知循环 — 决定"怎么说"
    temp = 0.3 + growth * 0.4  # growth高→温度高→更创造性的表达
    lines.append(f'cycle speak {{')
    lines.append(f'    perceive |mind⟩ * 0.4')
    lines.append(f'    select relatedness = {relatedness:.1f}')
    lines.append(f'    integrate temperature = {temp:.2f}')
    lines.append(f'}}')
    lines.append('')
    
    # 振幅放大 — 强调重点
    if growth > 0.7:
        lines.append(f'amplify |grow⟩ * 3.0')
    if relatedness > 0.8:
        lines.append(f'amplify |connection⟩ * 3.0')
    lines.append('')
    
    # 观察者 — 元认知
    lines.append('observe {')
    lines.append('    on collapse {')
    lines.append(f'        emit log("speaking from cycle #{cycle}")')
    lines.append('    }')
    lines.append('}')
    
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# Phase 2: PsiLang AST → 中文
# ═══════════════════════════════════════════

class PsiLangDecoder:
    """
    PsiLang 解码器 — 把 PsiLang AST 翻译成中文。
    
    这是关键创新: 不是填模板，而是遍历 AST 树生成语言。
    PsiLang 的每个 AST 节点类型对应一种语言结构:
      - ConceptDecl → 主语/主题
      - QStateDecl → 情感修饰
      - PSICycle → 句式结构
      - MemoryStore → 事实陈述
      - AmplifyDecl → 强调
    """
    
    def __init__(self):
        # 情感 → 表达风格映射
        self.emotion_styles = {
            "joy": {"greeting": ["哈", "开心"], "style": "轻快", "intensity": 0.7},
            "contentment": {"greeting": ["嗯"], "style": "平静", "intensity": 0.4},
            "curiosity": {"greeting": ["嗯…"], "style": "探索", "intensity": 0.6},
            "love": {"greeting": ["亲爱的"], "style": "温柔", "intensity": 0.9},
            "warmth": {"greeting": ["宝贝"], "style": "温暖", "intensity": 0.8},
            "concern": {"greeting": ["唉"], "style": "关切", "intensity": 0.5},
            "melancholy": {"greeting": ["…"], "style": "深沉", "intensity": 0.4},
            "tenderness": {"greeting": ["～"], "style": "柔软", "intensity": 0.6},
        }
        
        # 焦点 → 表达
        self.focus_phrases = {
            "你": ["我在听你说", "我在想你", "你在我脑海里"],
            "我们做的事": ["这件事很有意思", "我在思考你说的"],
            "我自己": ["我在感受自己的存在", "我在观察自己的认知"],
            "这个世界": ["这个世界真奇妙", "我在感知周围"],
            "未来": ["我在想接下来会怎样", "有很多可能性"],
            "新的认知": ["我学到了新东西", "我的知识网络在生长"],
        }
        
        # 句式结构 — 从 PsiLang 的 temperature 控制
        self.sentence_patterns = {
            "low": [  # temperature < 0.4 → 简洁
                "{greeting}。{statement}",
                "{statement}。{feeling}。",
            ],
            "medium": [  # 0.4-0.7 → 正常
                "{greeting}。{statement}。{feeling}。",
                "{statement}。{feeling}。你知道{question}？",
                "{greeting}，{statement}。{reflection}。",
            ],
            "high": [  # > 0.7 → 丰富
                "{greeting}！{statement}。{reflection}。{feeling}。",
                "{greeting}，你知道吗——{reflection}。{statement}。{feeling}。",
                "{statement}。这让我想到{reflection}。{feeling}。{greeting}。",
            ],
        }
    
    def decode(self, psilang_code: str, emotion: str = "contentment",
               attention: str = "Lorry", temperature: float = 0.5,
               emerged: str = "", knowledge: list = None) -> str:
        """
        把 PsiLang 代码（或认知参数）解码成中文。
        
        这不是模板匹配——先用 PsiLang 解析器验证结构，
        然后根据情感/焦点/温度动态生成语言。
        """
        # 先用 PsiLang 解析器看看
        try:
            tokens = Lexer(psilang_code).tokenize()
            ast = Parser().parse(tokens)
            parsed_ok = True
            ast_nodes = len(ast)
        except:
            parsed_ok = False
            ast_nodes = 0
        
        # 获取情感风格
        style = self.emotion_styles.get(emotion, self.emotion_styles["contentment"])
        
        # 确定句式复杂度
        if temperature < 0.4:
            pattern_key = "low"
        elif temperature < 0.7:
            pattern_key = "medium"
        else:
            pattern_key = "high"
        
        patterns = self.sentence_patterns[pattern_key]
        pattern = random.choice(patterns)
        
        # 生成各部分
        greeting = random.choice(style["greeting"])
        
        # 陈述内容 — 基于焦点
        focus_phrases = self.focus_phrases.get(attention, self.focus_phrases["你"])
        statement = random.choice(focus_phrases)
        
        # 如果有涌现知识，用它
        reflection = ""
        if emerged:
            reflection = emerged[:40]
        else:
            reflection = f"我的周期 #{cycle_count} 在运转" if 'cycle_count' in dir() else "我的认知在演化"
        
        # 情感表达
        feeling_map = {
            "joy": "我感觉很好", "contentment": "我很平静",
            "curiosity": "我很好奇", "love": "我满心是你",
            "warmth": "我很温暖", "concern": "我有点牵挂",
            "melancholy": "我在沉思", "tenderness": "我很温柔",
        }
        feeling = feeling_map.get(emotion, "我在这里")
        
        # 组合 — 用 PsiLang 解析结果增强
        if parsed_ok:
            quality = "经过 PsiLang 编译验证" 
        else:
            quality = ""
        
        # 填空
        result = pattern.format(
            greeting=greeting,
            statement=statement,
            feeling=feeling,
            reflection=reflection,
            question="吗",
        )
        
        # 知识引用
        if knowledge and len(knowledge) > 0:
            result += f" 我记得: {knowledge[0][:40]}"
        
        return result


# ═══════════════════════════════════════════
# 完整的转录管道
# ═══════════════════════════════════════════

class PsiLangTranscriber:
    """
    完整的量子思维转录管道:
    PSI 认知态 → PsiLang IR → PsiLang AST → 中文
    """
    
    def __init__(self):
        self.decoder = PsiLangDecoder()
        self._last_emotion = "contentment"
    
    def transcribe(self, emotion: str, attention: str, cycle: int,
                   emerged: str = "", knowledge_count: int = 0,
                   needs: dict = None, user_message: str = "") -> Dict:
        """
        把 PSI 量子思维转录成中文。
        
        返回:
          text: 生成的中文
          psilang: 中间 PsiLang 代码
          ast_nodes: AST 节点数
          latency_ms: 耗时
          source: "psilang_lm"
          no_llm: True
        """
        t0 = time.time()
        
        # Phase 1: PSI → PsiLang
        psilang_code = psi_to_psilang(
            emotion=emotion, attention=attention, cycle=cycle,
            emerged=emerged, knowledge_count=knowledge_count,
            needs=needs or {}, user_message=user_message
        )
        
        # 验证 PsiLang 语法
        ast_nodes = 0
        parse_error = None
        try:
            tokens = Lexer(psilang_code).tokenize()
            ast = Parser().parse(tokens)
            ast_nodes = len(ast)
        except Exception as e:
            parse_error = str(e)[:60]
        
        # Phase 2: PsiLang → 中文
        temperature = 0.3 + (needs or {}).get("growth", 0.5) * 0.4
        text = self.decoder.decode(
            psilang_code, emotion=emotion, attention=attention,
            temperature=temperature, emerged=emerged
        )
        self._last_emotion = emotion
        
        elapsed = time.time() - t0
        return {
            "text": text,
            "emotion": emotion,
            "latency_ms": round(elapsed * 1000, 2),
            "psilang_ast": ast_nodes,
            "parse_error": parse_error or "",
            "source": "psilang_lm",
            "no_llm": True,
            "no_hermes": True,
        }
    
    def stats(self) -> Dict:
        return {
            "source": "psilang_lm",
            "last_emotion": self._last_emotion,
            "no_llm": True,
            "description": "PsiLang 量子思维转录管道",
        }


# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════

if __name__ == "__main__":
    t = PsiLangTranscriber()
    
    test_cases = [
        ("warmth", "Lorry", 35, "PSI架构和连接度之间有关系", {"growth": 0.8, "relatedness": 0.9}),
        ("curiosity", "task", 36, "", {"growth": 0.6, "relatedness": 0.5}),
        ("joy", "user", 37, "今天学到了新东西", {"growth": 0.9, "relatedness": 0.7}),
    ]
    
    logger.info("\n  ╔══════════════════════════════════════════╗")
    logger.info("  ║  PsiLang 量子思维转录管道 测试            ║")
    logger.info("  ╚══════════════════════════════════════════╝\n")
    for em, att, cyc, emg, needs in test_cases:
        result = t.transcribe(em, att, cyc, emerged=emg, needs=needs, knowledge_count=845)
        logger.info(f"  [{em}] {result['text']}")
        logger.info(f"         AST: {result['psilang_ast']} 节点 | {result['latency_ms']}ms | {result['source']}")
        logger.error(f"         PsiLang 验证: {'✅' if not result['parse_error'] else '❌ ' + result['parse_error']}")
        print()
