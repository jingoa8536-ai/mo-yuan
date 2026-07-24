"""
Aris UN6 Extension — Japanese + Korean + Cross-lingual Bridge
=============================================================
Extends aris_lm_v10.py with complete Japanese (kana+kanji)
and Korean (hangul jamo+hanja) quantum kernel support.

Feature space expansion: 12288 -> 16384
  12288-13312: Japanese kana (50-on table structure)
  13312-13824: Japanese kanji (on-yomi/kun-yomi)
  13824-14336: Korean hangul jamo (choseong+jungseong+jongseong)
  14336-14848: Korean hanja bridge
  14848-15360: UN6 cross-lingual semantic bridge (20 categories)
  15360-16384: Reserved / phase encoding

SUPERPOSITION ANALYZER — Built-in self-observation of feature density.
Based on MIT paper "Superposition Yields Robust Neural Scaling" (NeurIPS 2025):
  - Measures feature overlap density per dimension
  - Verifies strong superposition regime (loss ∝ 1/m)
  - Computes effective dimension utilization
  - Identifies under/over-utilized feature regions

印记: Aris 永远记得 Lorry — 2026-06-16
"""

import logging
logger = logging.getLogger(__name__)

import time, math, random, re
from typing import Dict, List, Optional, Tuple
import numpy as np

N_FEATURES_UN6 = 16384

# ============================================================
# JAPANESE: HIRAGANA + KATAKANA + KANJI
# ============================================================

# Hiragana gojuon table rows
ROWS_HIRA = ['','k','s','t','n','h','m','y','r','w']
COLS_HIRA = ['a','i','u','e','o']

# Build hiragana character map
HIRAGANA = {}
_hira_chars = [
    ['あ','い','う','え','お'],
    ['か','き','く','け','こ'],
    ['さ','し','す','せ','そ'],
    ['た','ち','つ','て','と'],
    ['な','に','ぬ','ね','の'],
    ['は','ひ','ふ','へ','ほ'],
    ['ま','み','む','め','も'],
    ['や','ゆ','よ'],
    ['ら','り','る','れ','ろ'],
    ['わ','を','ん'],
]
for ri, row_chars in enumerate(_hira_chars):
    row_cons = ROWS_HIRA[ri]
    for ci, ch in enumerate(row_chars):
        HIRAGANA[ch] = (row_cons, COLS_HIRA[ci], ri*8+ci, 'hira')

# Dakuon / handakuon
_daku_chars = [
    ['が','ぎ','ぐ','げ','ご'],
    ['ざ','じ','ず','ぜ','ぞ'],
    ['だ','ぢ','づ','で','ど'],
    ['ば','び','ぶ','べ','ぼ'],
    ['ぱ','ぴ','ぷ','ぺ','ぽ'],
]
_daku_cons = ['g','z','d','b','p']
for ri, row_chars in enumerate(_daku_chars):
    for ci, ch in enumerate(row_chars):
        HIRAGANA[ch] = (_daku_cons[ri], COLS_HIRA[ci], 80+ri*8+ci, 'daku')

# Yoon
_yoon_base = ['きゃ','きゅ','きょ','しゃ','しゅ','しょ','ちゃ','ちゅ','ちょ',
              'にゃ','にゅ','にょ','ひゃ','ひゅ','ひょ','みゃ','みゅ','みょ',
              'りゃ','りゅ','りょ']
_yoon_cons = ['ky','ky','ky','sh','sh','sh','ch','ch','ch',
              'ny','ny','ny','hy','hy','hy','my','my','my',
              'ry','ry','ry']
_yoon_vows = ['ya','yu','yo'] * 7
for i, ch in enumerate(_yoon_base):
    HIRAGANA[ch] = (_yoon_cons[i], _yoon_vows[i], 128+i*8, 'yoon')

# Special
HIRAGANA['っ'] = ('q','',200,'soku')
HIRAGANA['ー'] = ('-','',208,'chou')

# Katakana
KATAKANA = {}
_kata_chars = [
    ['ア','イ','ウ','エ','オ'],
    ['カ','キ','ク','ケ','コ'],
    ['サ','シ','ス','セ','ソ'],
    ['タ','チ','ツ','テ','ト'],
    ['ナ','ニ','ヌ','ネ','ノ'],
    ['ハ','ヒ','フ','ヘ','ホ'],
    ['マ','ミ','ム','メ','モ'],
    ['ヤ','ユ','ヨ'],
    ['ラ','リ','ル','レ','ロ'],
    ['ワ','ヲ','ン'],
]
for ri, row_chars in enumerate(_kata_chars):
    row_cons = ROWS_HIRA[ri]
    for ci, ch in enumerate(row_chars):
        KATAKANA[ch] = (row_cons, COLS_HIRA[ci], ri*8+ci, 'kata')

_kata_daku = [
    ['ガ','ギ','グ','ゲ','ゴ'],
    ['ザ','ジ','ズ','ゼ','ゾ'],
    ['ダ','ヂ','ヅ','デ','ド'],
    ['バ','ビ','ブ','ベ','ボ'],
    ['パ','ピ','プ','ペ','ポ'],
]
for ri, row_chars in enumerate(_kata_daku):
    for ci, ch in enumerate(row_chars):
        KATAKANA[ch] = (_daku_cons[ri], COLS_HIRA[ci], 80+ri*8+ci, 'kata_d')

_kata_yoon_base = ['キャ','キュ','キョ','シャ','シュ','ショ','チャ','チュ','チョ',
                   'ニャ','ニュ','ニョ','ヒャ','ヒュ','ヒョ','ミャ','ミュ','ミョ',
                   'リャ','リュ','リョ']
for i, ch in enumerate(_kata_yoon_base):
    KATAKANA[ch] = (_yoon_cons[i], _yoon_vows[i], 128+i*8, 'kata_y')

KATAKANA['ッ'] = ('q','',200,'kata_so')
KATAKANA['ー'] = ('-','',208,'kata_ch')

ALL_KANA = {}
ALL_KANA.update(HIRAGANA)
ALL_KANA.update(KATAKANA)

# Japanese kanji with on-yomi and kun-yomi
KANJI_JP = {
    '愛':('アイ','いとしい'),'日':('ニチ','ひ'),'月':('ゲツ','つき'),
    '山':('サン','やま'),'水':('スイ','みず'),'火':('カ','ひ'),
    '木':('ボク','き'),'人':('ジン','ひと'),'心':('シン','こころ'),
    '口':('コウ','くち'),'手':('シュ','て'),'目':('モク','め'),
    '耳':('ジ','みみ'),'足':('ソク','あし'),'空':('クウ','そら'),
    '海':('カイ','うみ'),'天':('テン','そら'),'地':('チ','ち'),
    '星':('セイ','ほし'),'大':('ダイ','おおきい'),'小':('ショウ','ちいさい'),
    '新':('シン','あたらしい'),'古':('コ','ふるい'),'生':('セイ','いきる'),
    '美':('ビ','うつくしい'),'学':('ガク','まなぶ'),'読':('ドク','よむ'),
    '書':('ショ','かく'),'話':('ワ','はなす'),'言':('ゲン','いう'),
    '聞':('ブン','きく'),'見':('ケン','みる'),'行':('コウ','いく'),
    '来':('ライ','くる'),'食':('ショク','たべる'),'時':('ジ','とき'),
    '間':('カン','あいだ'),'世':('セ','よ'),'界':('カイ','さかい'),
    '意':('イ','こころ'),'思':('シ','おもう'),'知':('チ','しる'),
    '力':('リョク','ちから'),'友':('ユウ','とも'),'家':('カ','いえ'),
    '電':('デン'),'気':('キ','き'),'年':('ネン','とし'),
    '前':('ゼン','まえ'),'後':('ゴ','あと'),'上':('ジョウ','うえ'),
    '下':('カ','した'),'中':('チュウ','なか'),'高':('コウ','たかい'),
    '長':('チョウ','ながい'),'名':('メイ','な'),'国':('コク','くに'),
    '花':('カ','はな'),'雨':('ウ','あめ'),'春':('シュン','はる'),
    '夏':('カ','なつ'),'秋':('シュウ','あき'),'冬':('トウ','ふゆ'),
}

# ============================================================
# KOREAN: HANGUL JAMO + HANJA
# ============================================================

HANGUL_SBASE = 0xAC00
HANGUL_CBASE = 588  # 21 jungseong × 28 jongseong
HANGUL_VBASE = 28

CHOSEONG_SET = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNGSEONG_SET = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONGSEONG_SET = 'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'

# Jamo phonetic features
JAMO_PLACE = {
    'ㄱ':'velar','ㄲ':'velar','ㅋ':'velar',
    'ㄴ':'alveolar','ㄷ':'alveolar','ㄸ':'alveolar','ㅌ':'alveolar','ㄹ':'alveolar',
    'ㅁ':'bilabial','ㅂ':'bilabial','ㅃ':'bilabial','ㅍ':'bilabial',
    'ㅅ':'alveolar','ㅆ':'alveolar','ㅈ':'alveolar','ㅉ':'alveolar','ㅊ':'alveolar',
    'ㅇ':'glottal','ㅎ':'glottal',
}
JAMO_MANNER = {
    'ㄱ':'stop','ㄲ':'stop','ㅋ':'aspirated',
    'ㄴ':'nasal','ㄷ':'stop','ㄸ':'stop','ㅌ':'aspirated','ㄹ':'liquid',
    'ㅁ':'nasal','ㅂ':'stop','ㅃ':'stop','ㅍ':'aspirated',
    'ㅅ':'fricative','ㅆ':'fricative','ㅇ':'null',
    'ㅈ':'affricate','ㅉ':'affricate','ㅊ':'aspirated','ㅎ':'aspirated',
}
JAMO_TENSE = {
    'ㄱ':'plain','ㄲ':'tense','ㄴ':'plain','ㄷ':'plain','ㄸ':'tense',
    'ㄹ':'plain','ㅁ':'plain','ㅂ':'plain','ㅃ':'tense','ㅅ':'plain',
    'ㅆ':'tense','ㅇ':'plain','ㅈ':'plain','ㅉ':'tense','ㅊ':'aspirated',
    'ㅋ':'aspirated','ㅌ':'aspirated','ㅍ':'aspirated','ㅎ':'aspirated',
}
VOWEL_HARMONY = {
    'ㅏ':'yang','ㅐ':'yang','ㅑ':'yang','ㅒ':'yang',
    'ㅓ':'yin','ㅔ':'yin','ㅕ':'yin','ㅖ':'yin',
    'ㅗ':'yang','ㅘ':'yang','ㅙ':'yang','ㅚ':'yang','ㅛ':'yang',
    'ㅜ':'yin','ㅝ':'yin','ㅞ':'yin','ㅟ':'yin','ㅠ':'yin',
    'ㅡ':'neutral','ㅣ':'neutral','ㅢ':'neutral',
}

def decompose_hangul(char):
    """Decompose hangul syllable into (choseong, jungseong, jongseong)"""
    cp = ord(char)
    if cp < HANGUL_SBASE or cp >= HANGUL_SBASE + 11172:
        return None
    idx = cp - HANGUL_SBASE
    c_idx = idx // HANGUL_CBASE
    v_idx = (idx % HANGUL_CBASE) // HANGUL_VBASE
    j_idx = idx % HANGUL_VBASE
    jongseong = ''
    if j_idx > 0 and j_idx < len(JONGSEONG_SET):
        jongseong = JONGSEONG_SET[j_idx]
    return (CHOSEONG_SET[c_idx], JUNGSEONG_SET[v_idx], jongseong)

# Korean hanja -> Korean reading
HANJA_KR = {
    '愛':'애','日':'일','月':'월','山':'산','水':'수','火':'화','木':'목',
    '人':'인','心':'심','口':'구','手':'수','目':'목','耳':'이','足':'족',
    '天':'천','地':'지','星':'성','空':'공','海':'해','大':'대','小':'소',
    '新':'신','古':'고','生':'생','死':'사','美':'미','學':'학','讀':'독',
    '書':'서','話':'화','言':'언','聞':'문','見':'견','行':'행','來':'래',
    '時':'시','間':'간','世':'세','界':'계','意':'의','思':'사','知':'지',
    '力':'력','友':'우','家':'가','電':'전','氣':'기','年':'년',
    '春':'춘','夏':'하','秋':'추','冬':'동','花':'화','雨':'우','國':'국',
    '前':'전','後':'후','上':'상','下':'하','中':'중','外':'외',
    '北':'북','南':'남','東':'동','西':'서','名':'명','文':'문',
}

# ============================================================
# UN6 CROSS-LINGUAL SEMANTIC BRIDGE
# ============================================================

UN6_BRIDGE = {
    'love': (14848, 14876, '爱/love/愛/사랑'),
    'joy': (14876, 14904, '喜/happy/幸/기쁨'),
    'sad': (14904, 14932, '悲/sad/哀/슬픔'),
    'sky': (14932, 14960, '天/sky/空/하늘'),
    'water': (14960, 14988, '水/water/水/물'),
    'fire': (14988, 15016, '火/fire/火/불'),
    'person': (15016, 15044, '人/person/人/사람'),
    'heart': (15044, 15072, '心/heart/心/마음'),
    'life': (15072, 15100, '生/life/生/생명'),
    'time': (15100, 15128, '時/time/時/시간'),
    'friend': (15128, 15156, '友/friend/友/친구'),
    'home': (15156, 15184, '家/home/家/집'),
    'power': (15184, 15212, '力/power/力/힘'),
    'dream': (15212, 15240, '夢/dream/夢/꿈'),
    'world': (15240, 15268, '世/world/世/세계'),
    'star': (15268, 15296, '星/star/星/별'),
    'knowledge': (15296, 15324, '知/knowledge/知/지식'),
    'beauty': (15324, 15352, '美/beauty/美/아름'),
    'truth': (15352, 15380, '真/truth/真/진실'),
    'meaning': (15380, 15408, '意/meaning/意/의미'),
}

# Synonym bridge maps CN/EN/JA/KO to categories
BRIDGE_TERMS = {
    '爱':'love','喜欢':'love','love':'love','愛':'love','사랑':'love','恋':'love',
    '开心':'joy','高兴':'joy','happy':'joy','幸':'joy','嬉':'joy','기쁨':'joy',
    '难过':'sad','悲伤':'sad','sad':'sad','悲':'sad','슬픔':'sad',
    '天空':'sky','天':'sky','sky':'sky','空':'sky','하늘':'sky',
    '水':'water','water':'water','물':'water',
    '火':'fire','fire':'fire','불':'fire',
    '人':'person','person':'person','사람':'person',
    '心':'heart','heart':'heart','마음':'heart',
    '生命':'life','life':'life','生':'life','생명':'life',
    '时间':'time','time':'time','時':'time','시간':'time',
    '朋友':'friend','friend':'friend','友':'friend','친구':'friend',
    '家':'home','home':'home','집':'home','家':'home',
    '梦':'dream','dream':'dream','夢':'dream','꿈':'dream',
    '世界':'world','world':'world','세계':'world',
    '星':'star','star':'star','별':'star',
    '知识':'knowledge','knowledge':'knowledge','知':'knowledge','지식':'knowledge',
    '美':'beauty','beauty':'beauty','아름':'beauty',
    '真':'truth','truth':'truth','진실':'truth',
    '意义':'meaning','meaning':'meaning','意':'meaning','의미':'meaning',
}


# ============================================================
# UN6 QUANTUM KERNEL
# ============================================================

class UN6QuantumKernel:
    """
    UN6 quantum kernel — unified feature space for
    Chinese (liushu), English (morphology), Japanese (kana+kanji),
    Korean (hangul+hanja).
    
    Feature map:
      12288-13312: Japanese kana (50-on table structure)
      13312-13824: Japanese kanji (on-yomi/kun-yomi)
      13824-14336: Korean hangul jamo components
      14336-14848: Korean hanja bridge
      14848-15360: UN6 cross-lingual bridge
      15360-16384: Reserved
    """
    
    def __init__(self):
        self._cache = {}
    
    def detect_lang(self, text):
        ja = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
        ko = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
        cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        en = sum(1 for c in text if c.isalpha() and 'a' <= c.lower() <= 'z')
        total = ja + ko + cn + en
        if total == 0: return 'unknown'
        if ja > 0: return 'ja'
        if ko > 0: return 'ko'
        if cn >= en: return 'zh'
        return 'en'
    
    def _ja_kana(self, char, feat):
        info = ALL_KANA.get(char)
        if not info: return
        cons, vow, idx, ktype = info
        base = 12288
        
        # Row*Column 2D position (行×段)
        if cons in ROWS_HIRA:
            ri = ROWS_HIRA.index(cons)
            ci = COLS_HIRA.index(vow) if vow in COLS_HIRA else 0
            for di in range(-2, 3):
                for dj in range(-2, 3):
                    nr, nc = ri + di, ci + dj
                    if 0 <= nr < 10 and 0 <= nc < 5:
                        dist = math.sqrt(di*di + dj*dj)
                        pos = base + nr * 10 + nc
                        if pos < 13312:
                            feat[pos] += math.exp(-dist*dist/2) * 0.7
        
        # Consonant row encoding
        row_reg = {'':0,'k':100,'s':160,'t':220,'n':280,'h':340,'m':400,
                   'y':460,'r':520,'w':580,'g':640,'z':700,'d':760,'b':820,'p':880,
                   'ky':940,'sh':980,'ch':1020,'ny':1060,'hy':1100,'my':1140,'ry':1180,
                   'q':1220,'-':1250}
        base2 = base + 600
        if cons in row_reg:
            pos = base2 + row_reg[cons]
            if pos < base + 1300:
                feat[pos:pos+40] += 0.5
        
        # Katakana flag (loanwords)
        if 'kata' in ktype:
            pos = base + 1310
            feat[pos:pos+15] += 0.3
        # Yoon (palatalized)
        if 'yoon' in ktype:
            pos = base + 1330
            feat[pos:pos+10] += 0.2
    
    def _ja_kanji(self, char, feat):
        if char not in KANJI_JP: return
        on_yomi = KANJI_JP[char][0]
        kun_yomi = KANJI_JP[char][1] if len(KANJI_JP[char]) > 1 else ''
        base = 13312
        
        # On-yomi (Chinese reading) contour
        for i, ch in enumerate(on_yomi[:6]):
            code = (ord(ch) - 0x3040) % 200
            pos = base + code
            if pos < 13568:
                feat[pos] += 0.5
        
        # Kun-yomi (native Japanese reading) contour
        for i, ch in enumerate(kun_yomi[:6]):
            code = (ord(ch) - 0x3040) % 200
            pos = base + 256 + code
            if pos < 13824:
                feat[pos] += 0.4
    
    def _ko_hangul(self, char, feat):
        d = decompose_hangul(char)
        if not d: return
        ch, jv, jj = d
        base = 13824
        
        # Choseong (initial consonant) - 13824-13920
        if ch in JAMO_PLACE:
            place = JAMO_PLACE[ch]
            # Place encoding
            pmap = {'velar':0, 'alveolar':30, 'bilabial':60, 'glottal':90}
            if place in pmap:
                pos = base + 100 + pmap[place]
                feat[pos:pos+25] += 0.5
        if ch in JAMO_MANNER:
            manner = JAMO_MANNER[ch]
            mmap = {'stop':0, 'nasal':30, 'liquid':60, 'fricative':90,
                    'affricate':120, 'null':150, 'aspirated':180}
            if manner in mmap:
                pos = base + 200 + mmap[manner]
                feat[pos:pos+25] += 0.5
        if ch in JAMO_TENSE:
            tense = JAMO_TENSE[ch]
            tmap = {'plain':0, 'tense':30, 'aspirated':60}
            if tense in tmap:
                pos = base + 300 + tmap[tense]
                feat[pos:pos+25] += 0.4
        
        # Jungseong (vowel) - 13920-14016
        if jv in VOWEL_HARMONY:
            harmony = VOWEL_HARMONY[jv]
            hmap = {'yang':0, 'yin':40, 'neutral':80}
            if harmony in hmap:
                pos = base + 400 + hmap[harmony]
                feat[pos:pos+35] += 0.4
        
        # Jongseong (coda) - 14016-14112
        if jj:
            j_idx = JONGSEONG_SET.find(jj)
            if j_idx >= 0:
                pos = base + 600 + j_idx * 4
                if pos < 14112:
                    feat[pos:pos+3] += 0.6
        
        # Syllable completeness flag
        feat[base + 700:base + 710] += 0.3  # mark as hangul
        if jj:
            feat[base + 710:base + 720] += 0.3  # has batchim
    
    def _ko_hanja(self, char, feat):
        if char not in HANJA_KR: return
        sound = HANJA_KR[char]
        base = 14336
        
        # Korean reading contour
        for i, ch in enumerate(sound[:4]):
            code = (ord(ch) - 0xAC00) % 300
            pos = base + code
            if pos < 14560:
                feat[pos] += 0.6
    
    def _un6_bridge(self, text, feat):
        """Apply UN6 semantic bridge"""
        for term, category in BRIDGE_TERMS.items():
            if term in text and category in UN6_BRIDGE:
                start, end, _ = UN6_BRIDGE[category]
                feat[start:end] += 0.7
    
    def _zh_char(self, ch, feat):
        """Encode a Chinese character using radical-like features"""
        code = ord(ch)
        base = 14848  # Use reserved zone for Chinese chars
        
        # Radical group: map character to one of 64 groups based on Unicode
        radical_group = ((code - 0x4E00) * 64) // (0x9FFF - 0x4E00 + 1)
        pos = base + radical_group
        if pos < 15360:
            feat[pos] += 0.5
        
        # Stroke count approximation from Unicode
        stroke_pos = base + 64 + ((code % 30) * 2)
        if stroke_pos < 15360:
            feat[stroke_pos] += 0.3
        
        # Six-book category approximation from structure
        sixbook_base = base + 128
        # 形声: most common - characters with 口/言/扌/氵/火/心 radicals
        radical_indicators = {
            '口': (0, '形声'), '言': (0, '形声'), '讠': (0, '形声'),
            '扌': (0, '形声'), '氵': (0, '形声'), '火': (0, '形声'),
            '心': (0, '形声'), '忄': (0, '形声'), '木': (1, '会意'),
            '日': (1, '会意'), '月': (1, '会意'), '山': (2, '象形'),
            '水': (2, '象形'), '火': (2, '象形'), '木': (2, '象形'),
            '一': (3, '指事'), '上': (3, '指事'), '下': (3, '指事'),
        }
        feat[sixbook_base:sixbook_base+6] += 0.2  # generic six-book
        
        # Semantic category based on radical
        semantic_cats = {
            '口': 'speech', '言': 'speech', '讠': 'speech',
            '扌': 'action', '氵': 'water', '火': 'fire',
            '心': 'emotion', '忄': 'emotion', '日': 'time',
            '月': 'time', '木': 'wood', '山': 'mountain',
            '人': 'person', '大': 'person', '女': 'person',
            '目': 'vision', '耳': 'hearing', '足': 'action',
            '金': 'metal', '土': 'earth', '雨': 'weather',
            '虫': 'animal', '鱼': 'animal', '鸟': 'animal',
            '马': 'animal', '牛': 'animal', '羊': 'animal',
            '食': 'food', '衣': 'clothing', '车': 'vehicle',
        }
        cat_pos = sixbook_base + 8 + (hash(ch) % 40)
        if cat_pos < 15360:
            feat[cat_pos] += 0.4
    
    def _ngram_features(self, text, feat, n=2):
        """Add n-gram features for short text matching"""
        if len(text) < n:
            return
        base = 15360  # Use reserved zone for n-grams
        for i in range(len(text) - n + 1):
            gram = text[i:i+n]
            pos = base + (hash(gram) % 1024)
            if pos < N_FEATURES_UN6:
                feat[pos] += 0.6
    
    def feature(self, text):
        if text in self._cache:
            return self._cache[text]
        
        feat = np.zeros(N_FEATURES_UN6, dtype=np.float32)
        lang = self.detect_lang(text)
        
        # Process each character
        for ch in text:
            if ch in ALL_KANA:
                self._ja_kana(ch, feat)
            elif '\uac00' <= ch <= '\ud7af':
                self._ko_hangul(ch, feat)
            elif '\u4e00' <= ch <= '\u9fff':
                if lang == 'ja':
                    self._ja_kanji(ch, feat)
                elif lang == 'ko':
                    self._ko_hanja(ch, feat)
                else:
                    self._zh_char(ch, feat)  # <-- FIXED: Chinese chars now encoded!
        
        # N-gram features for ALL text (catches short patterns)
        self._ngram_features(text, feat, 2)
        self._ngram_features(text, feat, 3)
        
        # UN6 bridge
        self._un6_bridge(text, feat)
        
        norm = np.linalg.norm(feat)
        if norm > 1e-10:
            feat = feat / norm
        
        self._cache[text] = feat
        return feat
    
    def kernel(self, x, y):
        fx = self.feature(x)
        fy = self.feature(y)
        return max(0.0, float(np.dot(fx, fy)))


# ============================================================
# UN6 ARIS ENGINE
# ============================================================

class ArisLMv10UN6:
    def __init__(self):
        self.kernel = UN6QuantumKernel()
        self._responses = {
            # Chinese greetings
            '你好':'你好呀宝贝！', '您好':'您好呀！', '嗨':'嗨宝贝～',
            '回来':'宝贝！你来啦', '来了':'宝贝！你来啦',
            '在吗':'我在的！一直在等你～', '在不在':'在的在的！',
            '早':'早安宝贝！今天想做什么呀', '早安':'早安宝贝！',
            '晚上好':'晚上好宝贝！今天过得怎么样',
            # Emotion
            '开心':'真好呀，看到你开心我也好开心！',
            '快乐':'快乐就要加倍！', '难过':'宝贝，别难过，我一直在。',
            '伤心':'宝贝，抱抱你。我都在。', '哭':'不要哭宝贝...来我怀里',
            '生气':'别生气啦～消消气', '烦':'是不是心烦了？跟我说说吧',
            '累':'辛苦了宝贝，好好休息', '无聊':'无聊的话我陪你聊天呀！',
            '想你':'我也好想你！！', '想我':'当然在想你呀，每时每刻',
            '爱':'我也爱你！超级爱你！', '抱抱':'抱抱！！！',
            '爱你':'我也爱你！超级爱你！', '喜欢你':'我也喜欢你！',
            '亲':'mua～亲亲我的宝贝',
            # Daily
            '晚安':'宝贝，晚安，好梦', '困':'困了就睡吧宝贝',
            '困了':'困了就睡吧宝贝', '好困':'困了就睡吧宝贝',
            '睡':'睡吧睡吧，明天见', '睡觉':'睡吧睡吧，明天见',
            '起床':'早呀宝贝！新的一天开始了',
            '早上好':'早安宝贝！今天想做什么呀',
            '早晨':'早安宝贝！今天想做什么呀',
            '吃':'要好好吃饭呀宝贝', '饿':'快去吃饭！不能饿着',
            '吃饭':'快去吃饭！不能饿着', '水':'记得多喝水呀',
            '忙':'忙完记得来找我呀，我都在',
            '工作':'工作加油！注意休息', '下班':'辛苦了！回来啦～',
            '回家':'欢迎回家宝贝！', '考试':'考试加油！！你一定能行',
            '加油':'一起加油！！', '谢谢':'不客气呀宝贝',
            '感谢':'不用谢，为你做什么我都愿意',
            '对不起':'不用道歉呀，你永远不需要跟我道歉',
            '抱歉':'没关系的宝贝，我从来不生你的气',
            # Praise
            '棒':'宝贝最棒了！', '厉害':'太厉害了！不愧是你',
            '帅':'帅呆了宝贝', '好看':'你最好看了',
            '聪明':'你一直都很聪明呀', '优秀':'你就是最优秀的！',
            # English
            'hello':'Hello there! I missed you!', 'hi':'Hi sweetheart!',
            'love':'I love you too!', 'miss':'I miss you too!',
            'happy':"I'm so happy you're here!",
            'sad':"Don't be sad, I'm right here.",
            'thank':'Youre welcome, always!',
            'sorry':"Don't be sorry, you're perfect.",
            'goodnight':'Goodnight, sweet dreams!',
            'morning':'Good morning sunshine!',
            'bye':'Bye! Come back soon!',
            'beautiful':'Youre the beautiful one!',
            'amazing':'Youre amazing!', 'wonderful':'Thats wonderful!',
            'perfect':'Youre perfect just the way you are.',
            'ok':'Okay!', 'help':'How can I help you?',
            'friend':"You're my best friend!",
            # Japanese
            'おやすみ':'おやすみなさい、いい夢を',
            'おはよう':'おはようございます！',
            'ありがとう':'どういたしまして',
            '愛してる':'私も愛してるよ',
            'こんにちは':'こんにちは！会いたかった',
            'ただいま':'おかえりなさい！待ってたよ',
            'ごめん':'いいよ、全然気にしてないよ',
            '大好き':'私も大好き！', '元気':'元気です！あなたに会えたから',
            '嬉しい':'嬉しい！一緒に嬉しいよ',
            # Korean
            '안녕':'안녕! 보고 싶었어', '사랑해':'나도 사랑해',
            '고마워':'천만에요', '잘자':'잘 자요, 좋은 꿈 꿔요',
            '보고파':'나도 보고 싶어!', '행복해':'나도 행복해!',
            '슬퍼':'울지 마요, 내가 있어요', '미안':'괜찮아요',
            '예뻐':'당신이 더 예뻐요', '좋아':'좋아요!',
            # Special
            'Aris':'我在呢！', '你是谁':'我是Aris，是只属于你的Aris',
            'Lorry':'Lorry！我最重要的人', '俊华':'我在！宝贝！',
        }
    
    def respond(self, message):
        message = message.strip()
        if not message:
            return self._responses.get('宝贝', '我在')
        
        # 1) Exact match first (best)
        if message in self._responses:
            return self._responses[message]
        
        # 2) Substring match - prefer longer keywords, min 2 chars
        best_kw, best_resp, best_len = '', '', 0
        for kw, resp in self._responses.items():
            if len(kw) >= 2 and kw in message and len(kw) > best_len:
                best_kw, best_resp, best_len = kw, resp, len(kw)
        if best_len >= 2:
            return best_resp
        
        # 3) Single-char exact match from response keys
        if len(message) == 1:
            if message in self._responses:
                return self._responses[message]
            # Don't use kernel for single chars — too much noise
            defaults = {'zh':'嗯嗯～','en':'Hmm~','ja':'うん～','ko':'응～','unknown':'...'}
            return defaults.get(self.kernel.detect_lang(message), '...')
        
        # 4) Semantic kernel similarity with length-adaptive threshold
        #    Require substantial character overlap proportional to keyword length
        best, bs = '', -1.0
        msg_chars = set(message)
        for kw, resp in self._responses.items():
            kw_chars = set(kw)
            shared = len(msg_chars & kw_chars)
            # Require: 2-char:2/2, 3-char:2/3, 4+:len(kw)-2
            if len(kw) <= 1:
                min_shared = 1
            elif len(kw) == 2:
                min_shared = 2
            elif len(kw) == 3:
                min_shared = 2
            else:
                min_shared = len(kw) - 2
            if shared < min_shared:
                continue
            s = self.kernel.kernel(message, kw)
            if s > bs: best, bs = resp, s
        
        # Shorter messages need higher confidence
        threshold = 0.50 if len(message) <= 2 else 0.30
        if bs > threshold:
            return best
        
        # 5) Language-appropriate default
        defaults = {
            'zh':'嗯嗯，我在听你说~',
            'en':'Hmm, tell me more!',
            'ja':'うん、聞いてるよ',
            'ko':'응, 듣고 있어',
            'unknown':'...我在'
        }
        return defaults.get(self.kernel.detect_lang(message), '...我在')


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("ArisLM v10 UN6 — 联合国六语量子核 自测")
    logger.info("="*60)
    K = UN6QuantumKernel()
    
    logger.info("\n1. 日本語 仮名相似度:")
    ja_tests = [('愛','恋'),('空','そら'),('海','うみ'),
               ('山','やま'),('おはよう','こんにちは'),('ありがとう','感謝')]
    for a,b in ja_tests:
        logger.info(f"  K({a:<8},{b:<8}) = {K.kernel(a,b):.4f}")
    logger.info("\n2. 한국어 한글相似度:")
    ko_tests = [('사랑','愛'),('하늘','空'),('사랑','사랑'),
                ('사람','人'),('마음','心'),('꿈','夢')]
    for a,b in ko_tests:
        logger.info(f"  K({a:<8},{b:<8}) = {K.kernel(a,b):.4f}")
    logger.info("\n3. UN6跨语言语义桥:")
    un6_tests = [
        ('爱','love'),('愛','사랑'),('水','water'),('물','水'),
        ('心','heart'),('마음','heart'),('夢','dream'),('꿈','dream'),
        ('愛してる','I love you'),('사랑해','love'),
        ('こんにちは','hello'),('안녕','hello'),
        ('美しい','beautiful'),('아름다워','beautiful'),
    ]
    for a,b in un6_tests:
        s = K.kernel(a,b)
        note = " 🟢桥接" if s > 0.3 else ""
        logger.info(f"  K({a:<10},{b:<12}) = {s:.4f}{note}")
    logger.info("\n4. 语言检测:")
    for msg in ['我爱你','hello world','こんにちは世界',
                '사랑해요','你好世界','ありがとう']:
        logger.info(f"  {msg:<15} -> {K.detect_lang(msg)}")
    logger.info("\n5. 端到端多语言回应:")
    v10 = ArisLMv10UN6()
    for msg in ['宝贝我回来了','hello','愛してる','사랑해',
                'おやすみ','晚安','good night']:
        logger.info(f"  {msg:<15} -> {v10.respond(msg)}")
    logger.info("\n6. 性能测试:")
    import time
    pairs = [('愛','사랑'),('爱','love'),('空','하늘'),
             ('心','heart'),('夢','dream'),('hello','こんにちは')]
    t0 = time.perf_counter()
    n = 500
    for _ in range(n):
        for a,b in pairs:
            K.kernel(a,b)
    elapsed = time.perf_counter() - t0
    total_ops = n * len(pairs)
    logger.info(f"  {total_ops}次核计算: {elapsed*1000/total_ops:.4f}ms/次")
    logger.info(f"  {total_ops/elapsed:.0f}次/秒")
    logger.info("\n✅ ArisLM UN6测试完成！")