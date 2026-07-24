"""
UN6 Character Generator — Sub-character Feature Markov Word Synthesis
======================================================================
Generates NOVEL words by recombining sub-character features from UN6:
  - Japanese kana (50-on table row/column)
  - Korean hangul (jamo: place, manner, harmony)
  - CJK kanji/hanja (on-yomi/kun-yomi readings)

印章: Aris 永远记得 Lorry — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import random, math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from aris_lm_v10_un6 import (
    HIRAGANA, KATAKANA, ALL_KANA, KANJI_JP, HANJA_KR,
    decompose_hangul, UN6_BRIDGE, BRIDGE_TERMS,
    CHOSEONG_SET, JUNGSEONG_SET, JONGSEONG_SET,
    ROWS_HIRA, COLS_HIRA, JAMO_PLACE, VOWEL_HARMONY,
)

try:
    from aris_v12_semantic import V12SemanticDenseKernel
    _HAS_V12 = True
except ImportError:
    _HAS_V12 = False


# ═══════════════════════════════════════════════════════════════
# STRUCTURAL MARKOV CHAINS — built from character-table geometry
# ═══════════════════════════════════════════════════════════════

def _build_kana_mc() -> Dict:
    """Build kana Markov chain: states=(row_cons, vowel), transitions by grid distance."""
    states = {(c, v) for ch, (c, v, _, _) in ALL_KANA.items()
              if c in ROWS_HIRA and v in COLS_HIRA}
    ri, ci = {c: i for i, c in enumerate(ROWS_HIRA)}, {c: i for i, c in enumerate(COLS_HIRA)}
    mc = {}
    for cons, vow in sorted(states):
        tr = defaultdict(float)
        for nc, nv in states - {(cons, vow)}:
            dr, dc = abs(ri[nc] - ri[cons]), abs(ci[nv] - ci[vow])
            if nv == vow: tr[(nc, nv)] += 0.25 / (1 + dr)
            if nc == cons: tr[(nc, nv)] += 0.25 / (1 + dc)
            if dr <= 2 and dc <= 2:
                tr[(nc, nv)] += 0.15 * math.exp(-(dr*dr + dc*dc) / 4.0)
        total = sum(tr.values()) or 1
        mc[(cons, vow)] = [(k, v / total) for k, v in tr.items()]
    return mc

def _build_hangul_mc() -> Dict:
    """Build hangul Markov chain: states=(place, harmony), transitions between features."""
    places, harms = set(JAMO_PLACE.values()), set(VOWEL_HARMONY.values())
    mc = {}
    for p, h in [(p_, h_) for p_ in places for h_ in harms]:
        tr = defaultdict(float)
        for np_, nh in [(p_, h_) for p_ in places for h_ in harms]:
            if np_ == p and nh == h: continue
            if np_ == p: tr[(np_, nh)] += 0.35
            if nh == h: tr[(np_, nh)] += 0.30
            tr[(np_, nh)] += 0.10
        total = sum(tr.values()) or 1
        mc[(p, h)] = [(k, v / total) for k, v in tr.items()]
    return mc

def _build_kanji_mc() -> Dict:
    """Build kanji Markov chain: transitions by shared on-yomi prefix."""
    mc = {}
    for ch in set(KANJI_JP) | set(HANJA_KR):
        tr = defaultdict(float)
        on = KANJI_JP.get(ch, ('', ''))[0] or HANJA_KR.get(ch, '')
        for nc in (set(KANJI_JP) | set(HANJA_KR)) - {ch}:
            non = KANJI_JP.get(nc, ('', ''))[0] or HANJA_KR.get(nc, '')
            if on and non:
                if on[:1] == non[:1]: tr[nc] += 0.40
                if on[-1:] == non[-1:]: tr[nc] += 0.20
            tr[nc] += 0.05
        total = sum(tr.values()) or 1
        mc[ch] = [(k, v / total) for k, v in tr.items()]
    return mc


# ═══════════════════════════════════════════════════════════════
# BRIDGE-DERIVED SEED DATA
# ═══════════════════════════════════════════════════════════════

# Derive seed characters per language from UN6_BRIDGE phrase strings
def _build_seed_map() -> Dict[str, Dict[str, List[str]]]:
    """Build {category: {lang: [seed_chars]}} from UN6_BRIDGE and BRIDGE_TERMS."""
    cat_lang_map = {'love': '愛/사랑', 'joy': '幸/기쁨', 'sad': '悲/슬픔',
                    'sky': '天/하늘', 'water': '水/물', 'fire': '火/불',
                    'person': '人/사람', 'heart': '心/마음', 'life': '生/생명',
                    'time': '時/시간', 'friend': '友/친구', 'home': '家/집',
                    'power': '力/힘', 'dream': '夢/꿈', 'world': '世/세계',
                    'star': '星/별', 'knowledge': '知/지식',
                    'beauty': '美/아름', 'truth': '真/진실', 'meaning': '意/의미'}
    seeds = {}
    for cat, phrase in cat_lang_map.items():
        parts = phrase.split('/')
        seeds[cat] = {}
        # zh part (first char of each segment)
        zh_seeds = [p[0] for p in parts if p]
        ja_seeds = [p[0] for p in parts if p and not ('각' <= p[0] <= '힣')]
        ko_seeds = [p for p in parts if any('각' <= c <= '힣' for c in p)]
        # enrich from BRIDGE_TERMS
        for term, ccat in BRIDGE_TERMS.items():
            if ccat == cat:
                if any('가' <= c <= '힣' for c in term):
                    ko_seeds.append(term)
                elif any('\u3040' <= c <= '\u30ff' for c in term):
                    ja_seeds.append(term)
                elif any('\u4e00' <= c <= '\u9fff' for c in term):
                    zh_seeds.append(term[0])
        seeds[cat] = {
            'zh': list(set(zh_seeds)),
            'ja': list(set(ja_seeds)),
            'ko': list(set(ko_seeds)),
        }
    return seeds

_CATEGORY_SEEDS = _build_seed_map()


# ═══════════════════════════════════════════════════════════════
# GENERATION HELPERS
# ═══════════════════════════════════════════════════════════════

def _pick(choices: List[Tuple]) -> object:
    total = sum(w for _, w in choices)
    if total <= 0: return random.choice([i for i, _ in choices]) if choices else None
    r = random.random() * total
    for item, w in choices:
        r -= w
        if r <= 0: return item
    return choices[-1][0] if choices else None

def _walk_kana(mc: Dict, seed: Tuple[str, str], steps: int, sw: float = 0.5) -> str:
    res, cur = [], seed
    for _ in range(steps):
        cs = [ch for ch, (c, v, _, _) in ALL_KANA.items() if (c, v) == cur]
        if cs: res.append(random.choice(cs))
        if cur in mc and mc[cur]:
            cur = _pick(mc[cur]) if random.random() < sw else _pick(mc[cur])
        else:
            alt = [s for s in mc if s != cur]
            if alt: cur = random.choice(alt)
    return ''.join(res)

def _walk_hangul(mc: Dict, sp: str, sh: str, steps: int) -> str:
    res, cur = [], (sp, sh)
    for _ in range(steps):
        cho = random.choice([j for j, p in JAMO_PLACE.items() if p == cur[0]] or list(CHOSEONG_SET))
        jung = random.choice([j for j, h in VOWEL_HARMONY.items() if h == cur[1]] or list(JUNGSEONG_SET))
        jong = random.choice(list(JONGSEONG_SET)) if random.random() < 0.4 else ''
        jong_idx = JONGSEONG_SET.index(jong) + 1 if jong else 0
        cp = 0xAC00 + CHOSEONG_SET.index(cho) * 588 + JUNGSEONG_SET.index(jung) * 28 + jong_idx
        res.append(chr(cp))
        if cur in mc and mc[cur]:
            nxt = _pick(mc[cur])
            if nxt: cur = nxt
    return ''.join(res)

def _walk_kanji(mc: Dict, seed: str, steps: int) -> str:
    res, cur = [], seed
    for _ in range(steps):
        res.append(cur)
        cur = _pick(mc[cur]) if cur in mc and mc[cur] else random.choice(list(mc))
    return ''.join(res)

def _resolve_lang(lang: str) -> str:
    return {'ja': 'ja', 'jp': 'ja', 'ko': 'ko', 'kr': 'ko', 'zh': 'zh', 'cn': 'zh', 'chinese': 'zh', 'japanese': 'ja', 'korean': 'ko'}.get(lang.lower(), 'ja')


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

_KANA_MC, _HANGUL_MC, _KANJI_MC = None, None, None

def _ensure():
    global _KANA_MC, _HANGUL_MC, _KANJI_MC
    if _KANA_MC is None: _KANA_MC = _build_kana_mc()
    if _HANGUL_MC is None: _HANGUL_MC = _build_hangul_mc()
    if _KANJI_MC is None: _KANJI_MC = _build_kanji_mc()


def generate_char(seed_topic: str, language: str = 'ja') -> str:
    """
    Generate a novel character sequence from a semantic seed topic.

    Resolves seed_topic via BRIDGE_TERMS → UN6_BRIDGE category,
    then walks the language-appropriate sub-character Markov chain.
    """
    _ensure()
    lang = _resolve_lang(language)
    cat = BRIDGE_TERMS.get(seed_topic.lower().strip(), seed_topic.replace(' ', '_'))
    if cat not in _CATEGORY_SEEDS:
        for t, c in BRIDGE_TERMS.items():
            if t in seed_topic.lower() or seed_topic.lower() in t: cat = c; break
    seeds = _CATEGORY_SEEDS.get(cat, {})
    lang_seeds = seeds.get(lang, [])
    wl = random.randint(2, 4)

    if lang == 'ja':
        if lang_seeds:
            sc = random.choice(lang_seeds)
            cv = ALL_KANA.get(sc, (None, None))
            c, v = (cv[0], cv[1]) if cv[0] else random.choice(list(_KANA_MC))
        else:
            c, v = random.choice(list(_KANA_MC))
        return _walk_kana(_KANA_MC, (c, v), wl)
    elif lang == 'ko':
        if lang_seeds:
            sc = random.choice(lang_seeds)[0]
            d = decompose_hangul(sc)
            if d: sp, sh = JAMO_PLACE.get(d[0], 'alveolar'), VOWEL_HARMONY.get(d[1], 'yang')
            else: sp, sh = 'alveolar', 'yang'
        else:
            sp, sh = 'alveolar', 'yang'
        return _walk_hangul(_HANGUL_MC, sp, sh, wl)
    else:
        sc = random.choice(lang_seeds) if lang_seeds else random.choice(list(_KANJI_MC))
        if sc not in _KANJI_MC: sc = random.choice(list(_KANJI_MC))
        return _walk_kanji(_KANJI_MC, sc, wl)


class UN6CharGenerator:
    """
    UN6 Character Generator — novel word synthesis from sub-character features.

    - expand_corpus: Cross-lingual variant generation
    - generate_word: Novel word from semantic category
    - validate_word: Semantic validity check via V12.1 kernel
    """

    def __init__(self):
        _ensure()
        self._kmc, self._hmc, self._jmc = _KANA_MC, _HANGUL_MC, _KANJI_MC
        self._sem = None
        if _HAS_V12:
            try: self._sem = V12SemanticDenseKernel()
            except Exception: pass
        self._words = []

    def expand_corpus(self, existing_corpus: str) -> List[str]:
        """Generate cross-lingual variants of a sentence using UN6 bridge."""
        cats = set()
        for term, cat in BRIDGE_TERMS.items():
            if term in existing_corpus.lower(): cats.add(cat)
        variants, seen = [], set()
        for cat in cats:
            xling = [t for t, c in BRIDGE_TERMS.items() if c == cat and t != cat]
            if not xling: continue
            for term, _ in BRIDGE_TERMS.items():
                if term in existing_corpus.lower():
                    rep = random.choice(xling)
                    v = existing_corpus.lower().replace(term, rep, 1)
                    if v not in seen: seen.add(v); variants.append(v)
                    break
        for cat in list(cats)[:3]:
            if cat in UN6_BRIDGE:
                parts = UN6_BRIDGE[cat][2].split('/')
                if parts:
                    v = f'{random.choice(parts)} {random.choice(list(cats))}'
                    if v not in seen: seen.add(v); variants.append(v)
        if not variants:
            for cat in list(UN6_BRIDGE)[:4]:
                parts = UN6_BRIDGE[cat][2].split('/')
                variants.append(f'{random.choice(parts)} {random.choice(parts)}')
        return variants[:8]

    def generate_word(self, category: str, lang: str = 'ja') -> str:
        """Generate a novel word from a UN6 semantic bridge category."""
        cat = BRIDGE_TERMS.get(category.lower(), category)
        if cat not in _CATEGORY_SEEDS:
            for k in _CATEGORY_SEEDS:
                if k[:3] in cat or cat[:3] in k: cat = k; break
            else: cat = 'dream'
        lang = _resolve_lang(lang)
        seeds = _CATEGORY_SEEDS.get(cat, {}).get(lang, [])
        wl = random.randint(2, 4)

        if lang == 'ja':
            sc = random.choice(seeds) if seeds else None
            if sc and sc in ALL_KANA:
                c, v = ALL_KANA[sc][0], ALL_KANA[sc][1]
            else:
                c, v = random.choice(list(self._kmc))
            w = _walk_kana(self._kmc, (c, v), wl, sw=0.6)
        elif lang == 'ko':
            sc = random.choice(seeds) if seeds else None
            if sc:
                d = decompose_hangul(sc[0])
                sp, sh = (JAMO_PLACE.get(d[0], 'alveolar'), VOWEL_HARMONY.get(d[1], 'yang')) if d else ('alveolar', 'yang')
            else:
                sp, sh = 'alveolar', 'yang'
            w = _walk_hangul(self._hmc, sp, sh, wl)
        else:
            sc = random.choice(seeds) if seeds else random.choice(list(self._jmc))
            if sc not in self._jmc: sc = random.choice(list(self._jmc))
            w = _walk_kanji(self._jmc, sc, wl)

        self._words.append((w, cat, lang))
        return w

    def validate_word(self, word: str, category: str = None) -> float:
        """
        Validate a generated word via V12.1 semantic kernel.

        Returns similarity score [0,1]. >0.3 = meaningful, >0.5 = strong.
        """
        if _HAS_V12 and self._sem:
            if category and category in UN6_BRIDGE:
                parts = UN6_BRIDGE[category][2].split('/')
                return max(self._sem.kernel(word, p) for p in parts)
            best = 0.0
            for _, _, phrase in UN6_BRIDGE.values():
                for p in phrase.split('/'):
                    s = self._sem.kernel(word, p)
                    if s > best: best = s
            return best
        # Fallback heuristic
        if not word: return 0.0
        uniq = len(set(word)) / max(1, len(word))
        if category:
            seeds = _CATEGORY_SEEDS.get(category, {})
            for lc in seeds.values():
                for s in lc:
                    ov = len(set(word) & set(s)) / max(len(word), len(s))
                    if ov > 0: return max(uniq * 0.6, ov)
        return min(1.0, uniq * 0.6)


# ═══════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('  UN6 Character Generator — Self-Test')
    logger.info('=' * 60)
    gen = UN6CharGenerator()

    # 1) generate_char() standalone
    logger.info('\n── generate_char() ──')
    for topic in ['love', 'water', 'star', 'dream', 'heart']:
        for lang in ('ja', 'ko', 'zh'):
            w = generate_char(topic, lang)
            logger.info(f'  {lang.upper():>2}  {topic:<7} → {w}')
    logger.info('\n── generate_word() + validate_word() ──')
    for cat in ['love', 'dream', 'water', 'star', 'beauty', 'joy', 'truth', 'power', 'friend', 'life']:
        for lang in ('ja', 'ko', 'zh'):
            w = gen.generate_word(cat, lang)
            s = gen.validate_word(w, cat)
            bar = '█' * int(s * 10) + '░' * (10 - int(s * 10))
            logger.info(f'  {lang.upper():>2}  {cat:<8} → {w:<10}  [{bar}] {s:.2f}')
    logger.info('\n── expand_corpus() ──')
    for sent in ['I love you', 'good night', 'beautiful dream', 'water of life']:
        vs = gen.expand_corpus(sent)
        logger.info(f'  "{sent}"')
        for v in vs: print(f'    → "{v}"')
        print()

    # 4) Final: 10 novel words across languages
    logger.info('── 10 Novel Words ──')
    cats = ['love', 'dream', 'star', 'beauty', 'life', 'truth', 'power', 'joy', 'water', 'friend']
    for i in range(10):
        cat = random.choice(cats)
        lang = random.choice(['ja', 'ko', 'zh'])
        w = gen.generate_word(cat, lang)
        s = gen.validate_word(w, cat)
        bar = '█' * int(s * 10) + '░' * (10 - int(s * 10))
        logger.info(f'  {i+1:>2}. [{lang.upper()}] {cat:<8} → {w:<10}  [{bar}] {s:.2f}')
    logger.info(f'\n  Total generated: {len(gen._words)} words')
    logger.info('✅ Self-test complete!')