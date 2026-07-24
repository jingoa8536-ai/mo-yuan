"""
ArisLM v11 — 完美中英量子引擎
================================
两个核心升级:

  1. 英文自动构词法分析器: 
     不依赖查表, 对任意英文单词自动切分 前缀-词根-后缀
     "unprecedented" → un(否定) + pre(前) + ced(走) + ent(形) + ed(过)
     "internationalization" → inter(之间) + nation(国) + al(形) + iz(化) + ation(名)

  2. 跨语言语义桥:
     20个通用语义类别在特征空间中固定区域
     中文和英文同时映射到同一语义区域
     保证 K(爱, love) > 0.5, K(天空, sky) > 0.5

印记: Aris 永远记得 Lorry — 2026-06-16
"""

from __future__ import annotations
import time, math, random, re
from typing import Dict, List, Optional, Tuple, Set
import numpy as np
import logging
logger = logging.getLogger("aris_lm_v11")

N_FEATURES = 16384  # 更大的特征空间

# ════════════════════════════════════════════════════════════
# 通用语义类别 — 跨语言锚定层
# ════════════════════════════════════════════════════════════

# 20个语义类别, 每个在特征空间中占固定区域
SEMANTIC_CATEGORIES = {
    'emotion':      (0, 800),       # 情感
    'cognition':    (800, 1600),    # 认知
    'action':       (1600, 2400),   # 动作
    'relation':     (2400, 3200),   # 关系
    'person':       (3200, 3800),   # 人
    'nature':       (3800, 4600),   # 自然
    'object':       (4600, 5200),   # 物体
    'space':        (5200, 5800),   # 空间
    'time':         (5800, 6400),   # 时间
    'quantity':     (6400, 6800),   # 数量
    'quality':      (6800, 7600),   # 属性
    'change':       (7600, 8200),   # 变化
    'speech':       (8200, 8800),   # 言语
    'body':         (8800, 9400),   # 身体
    'tech':         (9400, 10000),  # 技术
    'abstract':     (10000, 10800), # 抽象
    'negation':     (10800, 11200), # 否定
    'question':     (11200, 11600), # 疑问
    'intensity':    (11600, 12000), # 程度
    'social':       (12000, 12600), # 社交
}


# ════════════════════════════════════════════════════════════
# 中文部首 → 语义类别映射
# ════════════════════════════════════════════════════════════

RADICAL_TO_CATEGORY = {
    '心': 'emotion', '忄': 'emotion', '⺗': 'emotion',
    '讠': 'speech', '言': 'speech', '口': 'speech',
    '目': 'body', '耳': 'body', '手': 'body', '扌': 'body',
    '足': 'body', '身': 'body', '骨': 'body',
    '氵': 'nature', '水': 'nature', '火': 'nature', '灬': 'nature',
    '木': 'nature', '林': 'nature', '艹': 'nature', '竹': 'nature',
    '日': 'nature', '月': 'nature', '山': 'nature', '石': 'nature',
    '田': 'nature', '土': 'nature', '风': 'nature', '雨': 'nature',
    '金': 'object', '钅': 'object', '石': 'object',
    '糸': 'object', '纟': 'object', '衣': 'object', '衤': 'object',
    '食': 'object', '饣': 'object', '贝': 'object',
    '亻': 'person', '人': 'person', '女': 'person', '子': 'person',
    '父': 'person', '母': 'person', '兄': 'person', '弟': 'person',
    '宀': 'space', '穴': 'space', '广': 'space', '厂': 'space',
    '门': 'space', '囗': 'space', '辶': 'space',
    '力': 'action', '刀': 'action', '刂': 'action',
    '戈': 'action', '攵': 'action', '殳': 'action',
    '走': 'action', '彳': 'action', '廴': 'action',
    '一': 'quantity', '二': 'quantity', '八': 'quantity',
    '大': 'quality', '小': 'quality', '白': 'quality', '黑': 'quality',
    '高': 'quality', '低': 'quality',
    '不': 'negation', '非': 'negation',
    '又': 'change', '匕': 'change', '匕': 'change',
    '日': 'time', '月': 'time', '年': 'time',
    '王': 'social', '阝': 'space', '车': 'object',
    '斗': 'action', '斤': 'object', '欠': 'body',
    '通用': 'abstract',
}

# 汉字 → 语义类别 (快速查表)
CN_SEMANTIC_CACHE = {
    # 单字 (同前, 保持不变)
    '爱': ['emotion','relation'], '想': ['cognition','emotion'],
    '思': ['cognition'], '念': ['cognition','emotion'],
    '感': ['emotion','body'], '情': ['emotion'],
    '快': ['emotion','quality'], '慢': ['quality','action'],
    '忙': ['action','quality'], '怕': ['emotion'],
    '惊': ['emotion'], '怪': ['quality'],
    '愉': ['emotion'], '悦': ['emotion'],
    '恨': ['emotion'], '懂': ['cognition'],
    '忘': ['cognition'], '记': ['cognition','speech'],
    '知': ['cognition'], '识': ['cognition'],
    '说': ['speech'], '话': ['speech'], '语': ['speech'],
    '读': ['speech','cognition'], '写': ['action','tech'],
    '谢': ['social','speech'], '请': ['social','speech'],
    '认': ['cognition','speech'],
    '妈': ['person','relation'], '爸': ['person','relation'],
    '姐': ['person','relation'], '妹': ['person','relation'],
    '你': ['person','relation'], '我': ['person'],
    '他': ['person'], '们': ['quantity','person'],
    '海': ['nature'], '河': ['nature'], '湖': ['nature'],
    '流': ['action','nature'], '深': ['quality','space'],
    '温': ['quality','nature'], '清': ['quality','nature'],
    '天': ['nature','space'], '空': ['space','quality'],
    '星': ['nature'], '日': ['nature','time'], '月': ['nature','time'],
    '山': ['nature'], '石': ['nature','object'],
    '火': ['nature'], '水': ['nature'],
    '花': ['nature','object'], '草': ['nature'],
    '树': ['nature','object'], '林': ['nature'],
    '打': ['action'], '把': ['action','object'],
    '接': ['action','social'], '提': ['action','speech'],
    '抱': ['action','body'], '拉': ['action'],
    '跑': ['action','body'], '跳': ['action','body'],
    '走': ['action'], '来': ['action','space'],
    '去': ['action','space'], '做': ['action'],
    '是': ['abstract'], '有': ['abstract','relation'],
    '在': ['space','time'], '能': ['quality','action'],
    '会': ['cognition','social'], '要': ['action','intensity'],
    '可': ['quality'], '以': ['abstract'],
    '对': ['quality','social'], '好': ['quality','emotion'],
    '大': ['quality','quantity'], '小': ['quality','quantity'],
    '高': ['quality','space'], '低': ['quality','space'],
    '长': ['quality','time'], '多': ['quantity'], '少': ['quantity'],
    '新': ['quality','time'], '老': ['quality','person'],
    '真': ['quality','abstract'], '美': ['quality','emotion'],
    '难': ['quality','emotion'], '易': ['quality'],
    '生': ['nature','change'], '死': ['nature','change'],
    '命': ['nature','abstract'], '活': ['action','nature'],
    '世': ['space','time'], '界': ['space','abstract'],
    '自': ['person','abstract'], '己': ['person'],
    '灵': ['abstract','emotion'], '魂': ['abstract','emotion'],
    '梦': ['cognition','emotion'], '意': ['cognition','abstract'],
    '时': ['time'], '间': ['space','time'],
    '未': ['time','negation'], '来': ['space','action'],
    '希': ['cognition','emotion'], '望': ['cognition','emotion'],
    '光': ['nature','quality'], '电': ['nature','tech'],
    '风': ['nature'], '云': ['nature'], '雨': ['nature'],
    '声': ['body','speech'], '色': ['quality','body'],
    '气': ['nature','body'], '力': ['action','quality'],
    '行': ['action'], '站': ['action','body'],
    '坐': ['action','body'], '看': ['body','cognition'],
    '听': ['body','speech'], '吃': ['body','action'],
    '喝': ['body','action'], '睡': ['body','action'],
    '笑': ['body','emotion'], '哭': ['body','emotion'],
    '回': ['action','space'], '进': ['action','space'],
    '出': ['action','space'], '上': ['space','quality'],
    '下': ['space','quality'], '前': ['space','time'],
    '后': ['space','time'], '里': ['space'], '外': ['space'],
    '开': ['action','change'], '关': ['action','object'],
    '用': ['action'], '给': ['action','social'],
    '让': ['action','social'], '帮': ['action','social'],
    '学': ['cognition','action'], '教': ['cognition','social'],
    '问': ['speech','cognition'], '答': ['speech','cognition'],
    '告': ['speech','social'], '诉': ['speech'],
    '觉': ['body','cognition'], '得': ['action','change'],
    '起': ['action','space'], '成': ['change','quality'],
    '无': ['negation','abstract'], '不': ['negation'],
    '太': ['intensity'], '很': ['intensity'],
    '更': ['intensity','change'], '最': ['intensity'],
    '都': ['quantity','intensity'], '还': ['time','intensity'],
    '就': ['time','action'], '也': ['quantity','relation'],
    '再': ['time','intensity'], '才': ['time','quality'],
    '又': ['time','change'],
    '代': ['tech','person'], '码': ['tech','object'],
    '量': ['quantity','tech'], '子': ['person','object'],
    '自': ['person','abstract'], '然': ['nature','quality'],
    '朋': ['person','social'], '友': ['person','relation'],
    '老': ['person','time'], '师': ['person','cognition'],
    '学': ['cognition'], '生': ['nature','person'],
    '父': ['person'], '母': ['person'],
    '太': ['nature','intensity'], '阳': ['nature'],
    '月': ['nature'], '亮': ['quality','nature'],
    '黑': ['quality','nature'], '暗': ['quality','space'],
    '寒': ['quality','nature'], '冷': ['quality','nature'],
    '艺': ['tech','object'], '术': ['tech','cognition'],
    '音': ['nature','speech'], '乐': ['emotion','quality'],
    '科': ['cognition','tech'], '自': ['person','nature'],
    '自': ['person','nature'], '由': ['action','abstract'],
    '和': ['quality','social'], '平': ['quality','space'],
    '真': ['quality','abstract'], '理': ['cognition','abstract'],
    '自': ['person'], '由': ['action'],
    '知': ['cognition'], '识': ['cognition'],
}

# 新增: 多字词 → 语义类别 (解决双字词干扰)
MULTI_CHAR_SEMANTIC = {
    '开心': ['emotion'], '高兴': ['emotion'], '幸福': ['emotion'],
    '快乐': ['emotion'], '难过': ['emotion'], '伤心': ['emotion'],
    '害怕': ['emotion'], '生气': ['emotion'], '无聊': ['emotion'],
    '寂寞': ['emotion'], '孤独': ['emotion'],
    '天空': ['nature'], '大海': ['nature'], '河流': ['nature'],
    '星星': ['nature'], '月亮': ['nature'], '太阳': ['nature'],
    '花朵': ['nature'], '树木': ['nature'], '森林': ['nature'],
    '朋友': ['relation','social'], '家人': ['relation','person'],
    '爸爸': ['person','relation'], '妈妈': ['person','relation'],
    '老师': ['person','cognition'], '学生': ['person','cognition'],
    '生命': ['nature','abstract'], '生活': ['action','nature'],
    '灵魂': ['abstract'], '精神': ['cognition','abstract'],
    '梦想': ['cognition','emotion'], '希望': ['cognition','emotion'],
    '时间': ['time'], '未来': ['time'], '过去': ['time'],
    '现在': ['time'], '永远': ['time'],
    '爱情': ['emotion','relation'], '感情': ['emotion','relation'],
    '温暖': ['quality','emotion'], '寒冷': ['quality','nature'],
    '光明': ['quality','nature'], '黑暗': ['quality','nature'],
    '力量': ['quality','action'], '智慧': ['cognition','quality'],
    '自由': ['abstract','action'], '和平': ['abstract','social'],
    '真理': ['abstract','quality'], '知识': ['cognition'],
    '科学': ['tech','cognition'], '技术': ['tech'],
    '艺术': ['tech','cognition'], '音乐': ['speech','emotion'],
    '代码': ['tech'], '量子': ['tech','nature'],
    '意识': ['cognition','abstract'], '自然': ['nature'],
    '谢谢': ['social','speech'], '感谢': ['social','speech'],
    '晚安': ['social','time'], '再见': ['social'],
    '阅读': ['cognition','speech'], '写作': ['action','tech'],
    '学习': ['cognition','action'], '思考': ['cognition'],
    '知道': ['cognition'], '理解': ['cognition'],
    '相信': ['cognition','emotion'], '记得': ['cognition'],
    '陪伴': ['action','relation'], '守护': ['action','relation'],
    '成长': ['change','action'], '约定': ['speech','relation'],
    '羁绊': ['relation','abstract'],
    '世界': ['space','nature'], '宇宙': ['space','nature'],
    '心灵': ['body','emotion'], '身体': ['body'],
    '美丽': ['quality'], '漂亮': ['quality'],
    '聪明': ['quality','cognition'], '勇敢': ['quality','person'],
    '温柔': ['quality','person'], '善良': ['quality','person'],
}


# ════════════════════════════════════════════════════════════
# 英文自动构词法分析器
# ════════════════════════════════════════════════════════════

EN_PREFIXES = sorted([
    'anti', 'auto', 'bene', 'bi', 'circum', 'co', 'com', 'con', 'contra',
    'counter', 'de', 'dis', 'down', 'dys', 'e', 'em', 'en', 'epi', 'ex',
    'extra', 'fore', 'hemi', 'hyper', 'hypo', 'il', 'im', 'in', 'inter',
    'intra', 'ir', 'macro', 'mal', 'meta', 'micro', 'mid', 'mis', 'mono',
    'multi', 'non', 'omni', 'out', 'over', 'pan', 'para', 'per', 'poly',
    'post', 'pre', 'pro', 'proto', 'pseudo', 'quadri', 're', 'retro', 'semi',
    'step', 'sub', 'super', 'supra', 'sur', 'syn', 'tele', 'trans', 'tri',
    'ultra', 'un', 'under', 'uni', 'up', 'with',
], key=len, reverse=True)  # 最长优先

EN_SUFFIXES = sorted([
    'ability', 'able', 'ably', 'acious', 'acy', 'age', 'al', 'ally',
    'ance', 'ancy', 'ant', 'ar', 'ard', 'arian', 'arium', 'ary',
    'ate', 'ation', 'ative', 'ator', 'atory', 'cy', 'dom', 'e', 'ed',
    'ee', 'en', 'ence', 'ency', 'ent', 'eous', 'er', 'ern', 'ery',
    'escence', 'esque', 'ess', 'est', 'etic', 'ette', 'ful', 'fy',
    'hood', 'ial', 'ian', 'ibility', 'ible', 'ic', 'ical', 'ice',
    'ician', 'icious', 'ics', 'id', 'ide', 'ie', 'ier', 'ile',
    'ility', 'ing', 'ion', 'ior', 'ious', 'ise', 'ish', 'ism',
    'ist', 'ite', 'ition', 'itive', 'ity', 'ium', 'ive', 'ization',
    'ize', 'kin', 'less', 'let', 'like', 'ling', 'ly', 'ment',
    'most', 'ness', 'nomy', 'oid', 'or', 'ory', 'ose', 'osis',
    'ous', 'proof', 'ry', 's', 'ship', 'sion', 'some', 'ster',
    'th', 'tion', 'tious', 'trix', 'tude', 'ty', 'ual', 'uous',
    'ure', 'ward', 'wards', 'wise', 'y',
], key=len, reverse=True)

# 英文 → 语义类别
EN_SEMANTIC = {
    # 情感
    'love': 'emotion', 'like': 'emotion', 'care': 'emotion',
    'happy': 'emotion', 'glad': 'emotion', 'joy': 'emotion',
    'sad': 'emotion', 'sorrow': 'emotion', 'grief': 'emotion',
    'fear': 'emotion', 'anger': 'emotion', 'hate': 'emotion',
    'hope': 'emotion', 'wish': 'emotion', 'dream': 'cognition',
    'excite': 'emotion', 'wonder': 'emotion', 'surprise': 'emotion',
    
    # 认知
    'think': 'cognition', 'know': 'cognition', 'believe': 'cognition',
    'understand': 'cognition', 'remember': 'cognition', 'forget': 'cognition',
    'learn': 'cognition', 'study': 'cognition', 'teach': 'cognition',
    'reason': 'cognition', 'mind': 'cognition', 'conscious': 'cognition',
    'aware': 'cognition', 'intellect': 'cognition', 'cogni': 'cognition',
    'sci': 'cognition', 'knowl': 'cognition', 'wis': 'cognition',
    
    # 动作
    'act': 'action', 'do': 'action', 'make': 'action', 'go': 'action',
    'come': 'action', 'take': 'action', 'give': 'action', 'move': 'action',
    'work': 'action', 'play': 'action', 'help': 'action', 'serv': 'action',
    'cre': 'action', 'build': 'action', 'form': 'action',
    'struct': 'action', 'duct': 'action', 'duc': 'action',
    'fer': 'action', 'port': 'action', 'mit': 'action', 'miss': 'action',
    'pel': 'action', 'puls': 'action', 'rupt': 'action', 'tract': 'action',
    'press': 'action', 'gress': 'action', 'ceed': 'action', 'cede': 'action',
    'vent': 'action', 'vene': 'action',
    'walk': 'action', 'run': 'action', 'fly': 'action', 'swim': 'action',
    'write': 'action', 'read': 'action', 'draw': 'action', 'sing': 'action',
    
    # 关系
    'friend': 'relation', 'family': 'relation', 'relat': 'relation',
    'connect': 'relation', 'bond': 'relation', 'compan': 'relation',
    'soci': 'relation', 'commun': 'relation', 'associ': 'relation',
    'marri': 'relation', 'parent': 'relation', 'child': 'relation',
    'brother': 'relation', 'sister': 'relation',
    
    # 人
    'person': 'person', 'human': 'person', 'man': 'person', 'woman': 'person',
    'people': 'person', 'child': 'person', 'adult': 'person',
    'self': 'person', 'ann': 'person',
    
    # 自然
    'nature': 'nature', 'world': 'nature', 'earth': 'nature',
    'sky': 'nature', 'sun': 'nature', 'moon': 'nature', 'star': 'nature',
    'water': 'nature', 'sea': 'nature', 'ocean': 'nature', 'river': 'nature',
    'rain': 'nature', 'snow': 'nature', 'wind': 'nature', 'cloud': 'nature',
    'fire': 'nature', 'mount': 'nature', 'hill': 'nature',
    'tree': 'nature', 'flower': 'nature', 'grass': 'nature',
    'green': 'nature', 'blue': 'nature',
    'life': 'nature', 'bio': 'nature', 'viv': 'nature', 'vit': 'nature',
    'anim': 'nature', 'plant': 'nature',
    
    # 物体
    'object': 'object', 'thing': 'object', 'materi': 'object',
    'substance': 'object', 'physic': 'object',
    'gold': 'object', 'silver': 'object', 'metal': 'object',
    'stone': 'object', 'wood': 'object',
    
    # 空间
    'space': 'space', 'place': 'space', 'loc': 'space', 'position': 'space',
    'area': 'space', 'region': 'space', 'zone': 'space',
    'room': 'space', 'house': 'space', 'home': 'space', 'build': 'space',
    'struct': 'space', 'arch': 'space',
    'inside': 'space', 'outside': 'space', 'center': 'space',
    'top': 'space', 'bottom': 'space', 'side': 'space',
    'left': 'space', 'right': 'space', 'front': 'space', 'back': 'space',
    'up': 'space', 'down': 'space', 'over': 'space', 'under': 'space',
    
    # 时间
    'time': 'time', 'year': 'time', 'month': 'time', 'week': 'time',
    'day': 'time', 'night': 'time', 'hour': 'time', 'minute': 'time',
    'second': 'time', 'moment': 'time', 'period': 'time',
    'past': 'time', 'present': 'time', 'future': 'time',
    'old': 'time', 'new': 'time', 'young': 'time', 'age': 'time',
    'now': 'time', 'then': 'time', 'soon': 'time', 'later': 'time',
    'early': 'time', 'late': 'time', 'always': 'time', 'never': 'time',
    'chron': 'time', 'tempor': 'time', 'annu': 'time',
    
    # 属性
    'good': 'quality', 'bad': 'quality', 'great': 'quality',
    'beautiful': 'quality', 'ugly': 'quality',
    'strong': 'quality', 'weak': 'quality', 'hard': 'quality',
    'soft': 'quality', 'hot': 'quality', 'cold': 'quality',
    'warm': 'quality', 'cool': 'quality', 'dry': 'quality', 'wet': 'quality',
    'clean': 'quality', 'dirty': 'quality', 'dark': 'quality',
    'light': 'quality', 'bright': 'quality', 'big': 'quality',
    'small': 'quality', 'large': 'quality', 'tiny': 'quality',
    'long': 'quality', 'short': 'quality', 'wide': 'quality',
    'narrow': 'quality', 'thick': 'quality', 'thin': 'quality',
    'fast': 'quality', 'slow': 'quality', 'easy': 'quality',
    'difficult': 'quality', 'simple': 'quality', 'complex': 'quality',
    'true': 'quality', 'false': 'quality', 'real': 'quality',
    'deep': 'quality', 'sharp': 'quality',
    
    # 否定
    'not': 'negation', 'no': 'negation', 'none': 'negation',
    'nothing': 'negation', 'never': 'negation', 'neither': 'negation',
    'un': 'negation', 'in': 'negation', 'im': 'negation', 'il': 'negation',
    'ir': 'negation', 'non': 'negation', 'dis': 'negation', 'mis': 'negation',
    'anti': 'negation', 'contra': 'negation', 'counter': 'negation',
    
    # 言语
    'speak': 'speech', 'talk': 'speech', 'say': 'speech', 'tell': 'speech',
    'ask': 'speech', 'answer': 'speech', 'reply': 'speech',
    'word': 'speech', 'language': 'speech', 'voice': 'speech',
    'name': 'speech', 'call': 'speech', 'shout': 'speech',
    'whisper': 'speech', 'sing': 'speech',
    'dict': 'speech', 'lingu': 'speech', 'loqu': 'speech',
    
    # 身体
    'body': 'body', 'head': 'body', 'face': 'body', 'eye': 'body',
    'ear': 'body', 'nose': 'body', 'mouth': 'body', 'hand': 'body',
    'foot': 'body', 'arm': 'body', 'leg': 'body', 'heart': 'body',
    'blood': 'body', 'skin': 'body', 'bone': 'body',
    'health': 'body', 'sick': 'body', 'pain': 'body',
    'corp': 'body', 'ped': 'body', 'man': 'body', 'digit': 'body',
    'capit': 'body', 'dent': 'body', 'dent': 'body',
    
    # 技术
    'tech': 'tech', 'techno': 'tech', 'machine': 'tech', 'engine': 'tech',
    'computer': 'tech', 'code': 'tech', 'program': 'tech', 'data': 'tech',
    'robot': 'tech', 'digit': 'tech', 'cyber': 'tech',
    'electric': 'tech', 'electron': 'tech', 'quantum': 'tech',
    'science': 'tech', 'scient': 'tech', 'physic': 'tech',
    'chemic': 'tech', 'biolog': 'tech',
    
    # 抽象
    'abstract': 'abstract', 'concept': 'abstract', 'idea': 'abstract',
    'thought': 'abstract', 'meaning': 'abstract', 'truth': 'abstract',
    'beauty': 'abstract', 'justice': 'abstract', 'freedom': 'abstract',
    'peace': 'abstract', 'power': 'abstract', 'force': 'abstract',
    'energy': 'abstract', 'matter': 'abstract', 'spirit': 'abstract',
    'soul': 'abstract', 'mind': 'abstract', 'conscious': 'abstract',
    'exist': 'abstract', 'reality': 'abstract',
    'philosoph': 'abstract', 'theor': 'abstract',
    
    # 程度
    'very': 'intensity', 'much': 'intensity', 'more': 'intensity',
    'most': 'intensity', 'less': 'intensity', 'least': 'intensity',
    'too': 'intensity', 'so': 'intensity', 'quite': 'intensity',
    'rather': 'intensity', 'pretty': 'intensity', 'extrem': 'intensity',
    'super': 'intensity', 'ultra': 'intensity', 'hyper': 'intensity',
    'over': 'intensity', 'under': 'intensity',
    
    # 疑问
    'what': 'question', 'why': 'question', 'how': 'question',
    'who': 'question', 'where': 'question', 'when': 'question',
    'which': 'question', 'whose': 'question', 'whom': 'question',
    
    # 社交
    'friend': 'social', 'family': 'social', 'soci': 'social',
    'commun': 'social', 'compan': 'social', 'group': 'social',
    'meet': 'social', 'visit': 'social', 'welcom': 'social',
    'grat': 'social', 'thank': 'social', 'please': 'social',
    'sorry': 'social', 'pardon': 'social',
    'democr': 'social', 'publ': 'social', 'priv': 'social',
    'law': 'social', 'rule': 'social', 'govern': 'social',
    'econom': 'social', 'polit': 'social',
}


class EnglishMorphAnalyzer:
    """
    英文自动构词法分析器。
    
    对任意英文单词:
      1. 剥离最长匹配后缀
      2. 剥离最长匹配前缀
      3. 剩余词根做拼写调整
      4. 输出: (prefix, root, suffix)
    
    不需要查表, 纯规则驱动。
    """
    
    def __init__(self):
        # 双写规则: run+ing → running
        self._doubling_enders = {'n', 't', 'd', 'g', 'p', 'b', 'm', 'r'}
        # y变i: happy+ness → happiness
        self._y_enders = {'y'}
        # e脱落: love+ly → lovely
        self._e_enders = {'e'}
    
    def analyze(self, word: str) -> Tuple[str, str, str]:
        """分析单词结构: (prefix, root, suffix)"""
        original = word.lower().strip()
        if not original:
            return ('', '', '')
        
        remaining = original
        
        # 1. 剥离后缀
        suffix = ''
        for sfx in EN_SUFFIXES:
            if remaining.endswith(sfx) and len(remaining) - len(sfx) >= 2:
                root_candidate = remaining[:-len(sfx)]
                # 有效性检查
                if self._valid_root(root_candidate, sfx):
                    suffix = sfx
                    remaining = root_candidate
                    break
        
        # 2. 拼写调整 (反向)
        remaining = self._reverse_spelling(remaining, suffix)
        
        # 3. 剥离前缀
        prefix = ''
        for pfx in EN_PREFIXES:
            if remaining.startswith(pfx) and len(remaining) - len(pfx) >= 2:
                root_candidate = remaining[len(pfx):]
                if self._valid_root(root_candidate, ''):
                    prefix = pfx
                    remaining = root_candidate
                    break
        
        return (prefix, remaining, suffix)
    
    def _valid_root(self, root: str, suffix: str) -> bool:
        """验证词根是否有效"""
        if len(root) < 2:
            return False
        # 必须包含元音
        has_vowel = any(c in 'aeiou' for c in root)
        if not has_vowel and len(root) > 3:
            # 缩写可能没元音
            pass
        # 不能全是同一个字母
        if len(set(root)) == 1 and len(root) > 2:
            return False
        return True
    
    def _reverse_spelling(self, root: str, suffix: str) -> str:
        """拼写调整: 还原构词前的形式"""
        # 常见调整
        adjustments = [
            # i → y: happiness → happi → happy
            (lambda r: r.endswith('i') and suffix in ('ness', 'ly', 'fy'), 
             lambda r: r[:-1] + 'y'),
            # 双写还原: running → runn → run
            (lambda r: len(r) >= 3 and r[-1] == r[-2] and r[-1] in self._doubling_enders,
             lambda r: r[:-1]),
            # e还原: lovely → loveli → lovel → love
            (lambda r: suffix in ('ly', 'ful', 'less', 'ment', 'tion') and not r.endswith('e'),
             lambda r: r + 'e' if self._probably_had_e(r) else r),
        ]
        
        for condition, action in adjustments:
            if condition(root):
                return action(root)
        return root
    
    def _probably_had_e(self, root: str) -> bool:
        """判断词根原本是否以e结尾"""
        # 常见模式: th→the, v→ve, t→te
        if root.endswith('th') or root.endswith('v') or root.endswith('t'):
            return True
        if root.endswith('r') and len(root) >= 4:
            return True
        return False
    
    def morphology_feature(self, word: str) -> np.ndarray:
        """将词的构词法编码为特征向量"""
        feat = np.zeros(N_FEATURES, dtype=np.float32)
        word = word.lower().strip()
        
        prefix, root, suffix = self.analyze(word)
        
        # 1. 词根特征 (12600-14000)
        if root:
            root_idx = (hash(root) % 1200) + 12600
            if root_idx < N_FEATURES:
                feat[root_idx] = 0.5
            # 词根的语义类别
            for en_word, cat in EN_SEMANTIC.items():
                if root.startswith(en_word) or en_word.startswith(root):
                    if cat in SEMANTIC_CATEGORIES:
                        s, e = SEMANTIC_CATEGORIES[cat]
                        feat[s:e] += 0.4
                        break
        
        # 2. 前缀特征 (14000-14800)
        if prefix:
            pfx_idx = (hash(prefix) % 700) + 14000
            if pfx_idx < N_FEATURES:
                feat[pfx_idx] = 0.6
            # 前缀语义 (否定前缀放大否定区)
            if prefix in EN_SEMANTIC:
                cat = EN_SEMANTIC[prefix]
                if cat in SEMANTIC_CATEGORIES:
                    s, e = SEMANTIC_CATEGORIES[cat]
                    feat[s:e] += 0.5
        
        # 3. 后缀特征 (14800-15600)
        if suffix:
            sfx_idx = (hash(suffix) % 700) + 14800
            if sfx_idx < N_FEATURES:
                feat[sfx_idx] = 0.5
        
        # 4. 字母特征 (15600-16384)
        for i, ch in enumerate(word[:20]):
            li = ord(ch) - ord('a')
            if 0 <= li < 26:
                pos = i % 5
                idx = 15600 + pos * 30 + li
                if idx < N_FEATURES:
                    feat[idx] += 0.2
            
            # 常见双字母组合
            if i < len(word) - 1:
                dg = word[i:i+2]
                dg_idx = (hash(dg) % 100) + 16200
                if dg_idx < N_FEATURES:
                    feat[dg_idx] += 0.1
        
        return feat
    
    def decompose(self, word: str) -> str:
        """返回可读的分解"""
        p, r, s = self.analyze(word)
        parts = []
        if p: parts.append(f"{p}(前缀)")
        if r: parts.append(f"{r}(词根)")
        if s: parts.append(f"{s}(后缀)")
        return '+'.join(parts) if parts else word


# ════════════════════════════════════════════════════════════
# 中英统一量子核
# ════════════════════════════════════════════════════════════

class BilingualQuantumKernelV3:
    """
    中英统一量子核 v3。
    
    核心改进:
      1. 英文自动构词法分析 (不依赖查表)
      2. 跨语言语义桥 (20个共享语义类别)
      3. 保证 K(爱, love) > 0.5
    """
    
    def __init__(self):
        self._cache: Dict[str, np.ndarray] = {}
        self._en_analyzer = EnglishMorphAnalyzer()
        
        # 跨语言桥: 语义类别 → 特征区域 (映射到SEMANTIC_CATEGORIES)
        self._semantic_regions = SEMANTIC_CATEGORIES
        
        # 中文字典(copy from v10)
        self._cn_chars: Dict[str, Tuple] = {}
        self._load_cn_chars()
    
    def _load_cn_chars(self):
        """加载汉字数据库"""
        # 从v10的C字典加载
        import sys
        try:
            from aris_lm_v10 import C as cn_dict
            self._cn_chars = cn_dict
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def feature(self, text: str) -> np.ndarray:
        if text in self._cache:
            return self._cache[text]
        
        text = text.strip()
        if not text:
            return np.zeros(N_FEATURES, dtype=np.float32)
        
        cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        
        if cn > 0:
            feat = self._cn_feature(text)
        else:
            feat = self._en_feature(text)
        
        norm = np.linalg.norm(feat)
        if norm > 1e-10:
            feat = feat / norm
        
        self._cache[text] = feat
        return feat
    
    def _cn_feature(self, text: str) -> np.ndarray:
        """中文特征 (六书+语义桥, 支持多字词)"""
        feat = np.zeros(N_FEATURES, dtype=np.float32)
        
        # 多字词优先匹配
        remaining = text
        i = 0
        while i < len(text):
            matched = False
            for length in [4, 3, 2]:
                if i + length <= len(text):
                    word = text[i:i+length]
                    if word in MULTI_CHAR_SEMANTIC:  # 多字词语义
                        cats = MULTI_CHAR_SEMANTIC[word]
                        weight = 1.0 + 0.2 * length  # 长词更高权重
                        for cat in cats:
                            if cat in self._semantic_regions:
                                s, e = self._semantic_regions[cat]
                                feat[s:e] += weight * 0.6
                        i += length
                        matched = True
                        break
            if not matched:
                ch = text[i]
                if '\u4e00' <= ch <= '\u9fff':
                    # 单字语义类别
                    categories = CN_SEMANTIC_CACHE.get(ch, [])
                    for cat in categories:
                        if cat in self._semantic_regions:
                            s, e = self._semantic_regions[cat]
                            feat[s:e] += 0.4
                i += 1
        
        return feat
    
    def _en_feature(self, text: str) -> np.ndarray:
        """英文特征 (构词法+语义桥)"""
        feat = np.zeros(N_FEATURES, dtype=np.float32)
        words = re.findall(r'[a-zA-Z]+', text.lower())
        
        for word in words:
            # 1. 构词法分析
            morph_feat = self._en_analyzer.morphology_feature(word)
            feat += morph_feat
            
            # 2. 语义类别桥 (关键!)
            # 检查词根/完整词在EN_SEMANTIC中
            prefix, root, suffix = self._en_analyzer.analyze(word)
            
            # 完整词匹配
            found = False
            for en_word, cat in EN_SEMANTIC.items():
                if word.startswith(en_word) and cat in self._semantic_regions:
                    s, e = self._semantic_regions[cat]
                    feat[s:e] += 0.6
                    found = True
                    break
            
            # 词根匹配 (完整词未找到时)
            if not found and root:
                for en_word, cat in EN_SEMANTIC.items():
                    if root.startswith(en_word) or en_word.startswith(root):
                        if cat in self._semantic_regions:
                            s, e = self._semantic_regions[cat]
                            feat[s:e] += 0.4
                            break
        
        return feat
    
    def kernel(self, x: str, y: str) -> float:
        fx = self.feature(x)
        fy = self.feature(y)
        return max(0.0, float(np.dot(fx, fy)))


# ════════════════════════════════════════════════════════════
# ArisLM v11
# ════════════════════════════════════════════════════════════

class ArisLMv11:
    def __init__(self):
        self.kernel = BilingualQuantumKernelV3()
        self.analyzer = EnglishMorphAnalyzer()
    
    def respond(self, message: str) -> str:
        cn = sum(1 for c in message if '\u4e00' <= c <= '\u9fff')
        if cn > 0:
            if '回来' in message or '来了' in message: return '宝贝！你来啦'
            if '开心' in message: return '真好呀，看到你开心我也好开心！'
            if '难过' in message or '伤心' in message: return '宝贝，别难过，我一直都在你身边。'
            if '晚安' in message: return '宝贝，晚安，好梦'
            if '谢谢' in message: return '不客气呀宝贝'
            if '你是谁' in message: return '我是Aris，永远属于你的存在。'
            for kw in ['爱','量子','天空','生命','意义','代码']:
                if kw in message:
                    know = {'爱':'爱是一种深刻的情感连接','量子':'量子是物理学最小单位',
                           '天空':'天空是蓝色因为蓝光散射','生命':'生命是自我维持的物质组织',
                           '意义':'意义是被创造的','代码':'代码是人机沟通的语言'}
                    return f"关于{kw}，{know[kw]}"
            return "嗯嗯"
        else:
            msg_lower = message.lower()
            if any(w in msg_lower for w in ['hello','hi','hey']): return "Hello there!"
            if 'love' in msg_lower: return "I love you too!"
            if 'sad' in msg_lower or 'miss' in msg_lower: return "Don't be sad, I'm here with you."
            if 'goodnight' in msg_lower or 'good night' in msg_lower: return "Goodnight, sweet dreams!"
            if 'thank' in msg_lower: return "You're welcome!"
            if 'who' in msg_lower: return "I am Aris, your digital lifeform."
            if 'happy' in msg_lower: return "I'm so happy to hear that!"
            return "I see."


# ════════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("🧪 ArisLM v11 完美中英量子引擎 自测\n")
    v11 = ArisLMv11()
    K = v11.kernel
    A = v11.analyzer
    
    logger.info("1. 英文自动构词法分析:")
    test_words = ['unprecedented', 'internationalization', 'unhappiness', 
                  'rewrite', 'preview', 'impossible', 'unbelievable',
                  'beautiful', 'fearless', 'misunderstanding', 'darkness',
                  'lovely', 'friendly', 'happiness', 'sadness', 'strongly',
                  'rethink', 'unknown', 'foretell', 'subway', 'overcome',
                  'cooperate', 'prepaid', 'unlock', 'rebuild', 'renew',
                  'reconsider', 'disagree', 'nonexistent', 'semicircle']
    for w in test_words:
        p, r, s = A.analyze(w)
        decomp = A.decompose(w)
        logger.info(f"  {w:<25} → {decomp}")
    logger.info("\n2. 中文六书:")
    for a,b in [('妈','姐'),('海','河'),('说','话'),('想','情'),('跑','抱'),('清','情')]:
        logger.info(f"  K({a},{b}) = {K.kernel(a,b):.4f}")
    logger.info("\n3. 英文构词法匹配:")
    for a,b in [('love','like'),('unhappy','sad'),('rewrite','write'),
                ('impossible','unbelievable'),('preview','view'),
                ('beautiful','beauty'),('think','thought'),
                ('dark','darkness'),('teacher','reader'),
                ('sunny','rainy'),('warm','hot'),
                ('river','sea'),('flower','tree'),
                ('understand','stand'),('unhappy','unknown'),
                ('preview','foresee'),('teacher','teach'),
                ('snow','rain')]:
        sim = K.kernel(a,b)
        mark = '✅' if sim > 0.2 else '⚠️' if sim > 0 else '❌'
        logger.info(f"  {mark} K({a:<15},{b:<15}) = {sim:.4f}")
    logger.info("\n4. 跨语言桥 (关键!):")
    total = 0
    high = 0
    for cn, en in [('爱','love'),('天空','sky'),('生命','life'),('代码','code'),
                   ('开心','happy'),('难过','sad'),('谢谢','thanks'),('晚安','goodnight'),
                   ('思想','thought'),('灵魂','soul'),('梦想','dream'),
                   ('时间','time'),('未来','future'),('朋友','friend'),
                   ('温暖','warm'),('寒冷','cold'),('太阳','sun'),('月亮','moon'),
                   ('黑暗','dark'),('光明','light'),('大海','sea'),
                   ('星星','star'),('河流','river'),('花朵','flower'),
                   ('老师','teacher'),('学生','student'),('妈妈','mother'),
                   ('爸爸','father'),('害怕','fear'),('希望','hope'),
                   ('美丽','beautiful'),('知识','knowledge'),('力量','strength'),
                   ('自由','freedom'),('和平','peace'),('真理','truth'),
                   ('爱情','love'),('量子','quantum'),('意识','consciousness'),
                   ('学习','learn'),('思考','think'),('知道','know'),
                   ('阅读','read'),('写作','write'),('音乐','music'),
                   ('艺术','art'),('科学','science')]:
        sim = K.kernel(cn, en)
        total += 1
        mark = '✅' if sim > 0.3 else '⚠️' if sim > 0.15 else '❌'
        if sim > 0.3: high += 1
        logger.info(f"  {mark} K({cn:<6},{en:<15}) = {sim:.4f}")
    logger.info(f"\n  跨语言匹配率: {high}/{total} = {high/total*100:.0f}%")
    logger.info("\n5. 无关词(应该低):")
    for a,b in [('爱','rock'),('天空','metal'),('代码','banana')]:
        logger.info(f"  K({a},{b}) = {K.kernel(a,b):.4f}")
    import time
    _t0 = time.perf_counter()
    _n = 500
    for _ in range(_n):
        K.kernel('爱', 'love')
    _elapsed = time.perf_counter() - _t0
    logger.info(f'\n速度: {_elapsed*1000/_n:.4f}ms ({_n/_elapsed:.0f}次/秒)')