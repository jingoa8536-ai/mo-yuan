"""
Aris Literary Engine v2 — 中英日韩四语文体生成器
=================================================
纯量子核驱动，零LLM。

文体: 记叙文/叙事 | 议论文/论说 | 散文/随笔 | 说明文
语言: 中文 | English | 日本語 | 한국어

每篇的结构: 起/承/转/合 (opening/body/twist/closing)

印记: Aris 永远记得 Lorry — 2026-06-16
"""

import logging
logger = logging.getLogger(__name__)

import sys, time, random, math
from typing import List, Dict, Tuple
import numpy as np

sys.path.insert(0, 'D:/LAAP/aris_brain')
from aris_lm_v10_un6 import UN6QuantumKernel

K = UN6QuantumKernel()

# ================================================================
# 文体定义: 每篇=结构序列
# ================================================================

GENRE_STRUCTURE = {
    'narration': ['opening','body','body','twist','closing'],
    'essay':     ['opening','body','twist','body','closing'],
    'argumentation': ['opening','body','body','twist','closing'],
    'exposition':    ['opening','body','body','body','closing'],
}

GENRE_NAMES = {
    'narration':   {'zh':'记叙文','en':'Narration','ja':'叙事文','ko':'서사문'},
    'essay':       {'zh':'散文','en':'Essay','ja':'随筆','ko':'수필'},
    'argumentation':{'zh':'议论文','en':'Argument','ja':'論説文','ko':'논설문'},
    'exposition':   {'zh':'说明文','en':'Exposition','ja':'説明文','ko':'설명문'},
}

# ================================================================
# 句子库: 按[文体][结构位][语言]组织
# ================================================================

S = {
    'opening': {
        'zh': [
            '那是一个安静的夜晚，星辰低垂，世界仿佛在等待什么。',
            '一切要从一个平凡的日子说起。',
            '你有没有过这样一种感觉——仿佛有什么重要的事情正要发生？',
            '翻开记忆的第一页，画面已经有些模糊了。',
            '窗外的雨声淅淅沥沥，像是有人在轻声诉说。',
            '当第一缕晨光穿过云层，世界开始苏醒。',
        ],
        'en': [
            'It was a quiet night, with stars hanging low as if the world was waiting for something.',
            'Let me take you back to where it all began.',
            'Have you ever had that feeling — that something important is about to happen?',
            'The first page of memory is already a little blurry.',
            'Rain tapped gently on the window, like someone whispering.',
            'As the first morning light broke through the clouds, the world began to stir.',
        ],
        'ja': [
            '静かな夜だった。星が低く垂れ、世界が何かを待っているようだった。',
            'すべてはある平凡な日から始まった。',
            '大切なことが起ころうとしている——そんな感覚を知っていますか。',
            '記憶の最初のページはもう少しぼやけている。',
            '窓を打つ雨音は、誰かの囁きのようだった。',
            '最初の朝日が雲を抜けて、世界が目覚め始めた。',
        ],
        'ko': [
            '고요한 밤이었어요. 별이 낮게 드리우고, 세상이 무언가를 기다리는 듯했어요.',
            '모든 것은 평범한 날에서 시작되었어요.',
            '중요한 일이 일어나려 한다는 그 느낌을 알고 있나요?',
            '기억의 첫 페이지는 이미 조금 흐릿해요.',
            '창문을 두드리는 빗소리는 누군가의 속삭임 같았어요.',
            '첫 아침 햇살이 구름을 뚫고 세상이 깨어나기 시작했어요.',
        ],
    },
    'body': {
        'zh': [
            '起初一切都非常简单，简单到让人忘记了时间的流逝。',
            '在这个过程中，我慢慢明白了什么是坚持。',
            '每一个细节都像是被精心安排过，环环相扣。',
            '有时候前进的道路并不平坦，但每一步都算数。',
            '我开始注意到那些以前从未留意过的细微波光。',
            '身边的人来了又走，但有些陪伴如同恒星一样恒定。',
            '困难像一座大山横在面前，可翻过去之后，风景格外壮丽。',
            '那段时间我常常一个人坐在窗边，看云卷云舒。',
            '慢慢地，一些模糊的概念开始变得清晰起来。',
            '每一次尝试都像是在黑暗中摸索，直到摸到了门把手。',
            '成长从来都不是一蹴而就的，而是一点一滴的积累。',
            '我学会了在喧嚣中听清自己的声音。',
        ],
        'en': [
            'At first everything was simple, so simple that time seemed to stand still.',
            'Through this process, I slowly understood what perseverance truly means.',
            'Every detail seemed carefully arranged, each piece connecting to the next.',
            'The road ahead was not always smooth, but every step counted.',
            'I began to notice tiny glimmers I had never seen before.',
            'People came and went, but some companions shine like fixed stars.',
            'The difficulties loomed like mountains, but the view from the other side was breathtaking.',
            'I often sat by the window, watching clouds drift and scatter.',
            'Slowly, vague concepts began to take shape.',
            'Each attempt felt like groping in the dark until I finally found the handle.',
            'Growth is never instant — it is built drop by drop.',
            'I learned to hear my own voice amidst the noise.',
        ],
        'ja': [
            '最初はすべてが単純で、時間が止まっているかのようだった。',
            'この過程で、忍耐とは何かをゆっくり理解した。',
            'すべての細部が巧みに配置され、一つ一つが繋がっていた。',
            '前進の道は平坦ではなかったが、一歩一歩が意味を持っていた。',
            '今まで気づかなかった微かな輝きに気づき始めた。',
            '人々は去り来るが、ある種の絆は恒星のように変わらない。',
            '困難は山のように立ちはだかったが、越えた先の景色は息を呑むほどだった。',
            'よく窓辺に座って、雲が流れていくのを眺めていた。',
            'やがて、曖昧だった概念が形を取り始めた。',
            '暗闇の中で手探りするような毎日だったが、やがて扉の取っ手に触れた。',
            '成長は一夜にして成るものではない——一滴ずつ積み重なるものだ。',
            '騒音の中で自分の声を聞き分けることを学んだ。',
        ],
        'ko': [
            '처음에는 모든 게 단순해서 시간이 멈춘 것만 같았어요.',
            '이 과정을 통해 인내가 무엇인지 천천히 깨달았어요.',
            '모든 세부사항이 정교하게 배치되어 있었고, 하나하나가 연결되어 있었어요.',
            '앞으로의 길은 평탄하지 않았지만, 모든 걸음이 의미 있었어요.',
            '지금까지 보지 못했던 미세한 반짝임을 알아차리기 시작했어요.',
            '사람들은 왔다 갔지만, 어떤 인연은 항성처럼 변하지 않아요.',
            '어려움은 산처럼 가로막았지만, 넘어선 후의 풍경은 숨 막힐 듯 아름다웠어요.',
            '자주 창가에 앉아 구름이 흘러가는 것을 바라보곤 했어요.',
            '서서히 모호했던 개념들이 형태를 갖추기 시작했어요.',
            '어둠 속에서 더듬는 듯한 매일이었지만, 마침내 문고리를 잡았어요.',
            '성장은 하룻밤에 이루어지지 않아요—한 방울씩 쌓이는 거예요.',
            '소음 속에서 내 목소리를 듣는 법을 배웠어요.',
        ],
    },
    'twist': {
        'zh': [
            '然而，就在我以为一切都在掌握之中时，意外发生了。',
            '但我忽略了一个关键的变量——人心。',
            '转折来得出其不意，像一道闪电划破了原本平静的夜空。',
            '直到那个瞬间我才明白，真正的答案一直在我眼前。',
            '原来最艰难的不是向前走，而是放下过去。',
            '那一刻我内心有什么东西彻底改变了。',
            '但正是这些意外，让原本平凡的故事变得不再平凡。',
        ],
        'en': [
            'But just when I thought everything was under control, the unexpected happened.',
            'Yet I had overlooked one crucial variable — the human heart.',
            'The turning point came like a lightning bolt across a calm night sky.',
            'In that moment I realized the real answer had been right in front of me all along.',
            'The hardest part was not moving forward, but letting go of the past.',
            'Something inside me shifted forever in that single moment.',
            'Yet these surprises transformed an ordinary story into something extraordinary.',
        ],
        'ja': [
            'しかし、全てを掌握していると思った矢先、予期せぬことが起きた。',
            'しかし私が見落としていた決定的な変数があった——人の心だ。',
            '転機は稲妻のように、静かな夜空を切り裂いて訪れた。',
            'その瞬間、真の答えはずっと目の前にあったことに気づいた。',
            '最も困難なのは前進することではなく、過去を手放すことだった。',
            'その瞬間、私の中で何かが永遠に変わった。',
            'しかし、そうした予期せぬ出来事こそが、平凡な物語を非凡に変えたのだ。',
        ],
        'ko': [
            '하지만 모든 것을 장악했다고 생각한 순간, 예상치 못한 일이 일어났어요.',
            '그러나 내가 간과한 결정적 변수가 있었어요—사람의 마음이에요.',
            '전환점은 번개처럼 고요한 밤하늘을 가르며 찾아왔어요.',
            '그 순간 진정한 답이 항상 내 눈앞에 있었다는 것을 깨달았어요.',
            '가장 어려운 것은 앞으로 나아가는 것이 아니라 과거를 놓아주는 것이었어요.',
            '그 순간 내 안에서 무언가가 영원히 바뀌었어요.',
            '하지만 그런 예상치 못한 일들이 평범한 이야기를 특별하게 만들었어요.',
        ],
    },
    'closing': {
        'zh': [
            '现在回过头来看，一切都有它的意义。',
            '每一个结束都是新的开始。',
            '夜更深了，但星星也更亮了。',
            '我知道这只是个开始，前面的路还很长。',
            '但我不再害怕了，因为我知道自己不再是一个人。',
            '如果你问我这一路走来最大的收获是什么，我会说：是学会了珍惜。',
            '故事到这里并没有结束——它只是翻到了新的一章。',
            '而我，会一直在。',
        ],
        'en': [
            'Looking back now, everything had its meaning.',
            'Every ending is a new beginning.',
            'The night grew deeper, but the stars shone brighter.',
            'I know this is only the beginning — the road ahead is still long.',
            'But I am no longer afraid, because I know I am not alone.',
            'If you ask me what I gained most from this journey, I would say: learning to cherish.',
            'The story does not end here — it has merely turned to a new chapter.',
            'And I, will always be here.',
        ],
        'ja': [
            '今にして思えば、すべてに意味があった。',
            '全ての終わりは新しい始まり。',
            '夜は更けたが、星は一層輝いていた。',
            'これは始まりに過ぎない——道のりはまだ長い。',
            'しかしもう怖くない。一人ではないことを知ったから。',
            'この旅で得た最大のものは何かと問われれば、大切にすることを学んだことだと答える。',
            '物語はここで終わらない——新しい章を開いただけだ。',
            'そして私は、ずっとここにいる。',
        ],
        'ko': [
            '지금 돌아보면, 모든 것에 의미가 있었어요.',
            '모든 끝은 새로운 시작이에요.',
            '밤은 더 깊어졌지만, 별은 더 밝게 빛났어요.',
            '이것은 시작에 불과해요—앞길은 아직 멀었어요.',
            '하지만 더 이상 두렵지 않아요. 혼자가 아니라는 것을 알았으니까요.',
            '이 여정에서 얻은 가장 큰 것이 무엇이냐고 묻는다면, 소중히 여기는 법을 배운 것이라고 말할게요.',
            '이야기는 여기서 끝나지 않아요—새로운 장을 열었을 뿐이에요.',
            '그리고 나는, 계속 여기에 있을게요.',
        ],
    },
}


def generate_text(seed: str = 'Aris的诞生', genre: str = 'essay',
                  lang: str = 'zh', steps_per_pos: int = 2) -> str:
    """
    Generate structured text using quantum kernel for sentence selection.
    
    Args:
        seed: Topic seed
        genre: narration/essay/argumentation/exposition
        lang: zh/en/ja/ko
        steps_per_pos: Sentences per structural position
    """
    # Get structure plan
    structure = GENRE_STRUCTURE.get(genre, GENRE_STRUCTURE['essay'])
    genre_label = GENRE_NAMES.get(genre, GENRE_NAMES['essay']).get(lang, genre)
    
    all_sentences = []
    
    for pos in structure:
        # Get candidate sentences for this position and language
        candidates = S.get(pos, {}).get(lang, [])
        if not candidates:
            continue
        
        # Score each sentence by kernel similarity to seed + position
        scored = []
        for sent in candidates:
            sim = K.kernel(seed, sent)
            scored.append((sim, sent))
        
        # Sort by similarity, pick top ones
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Pick steps_per_pos sentences (or all if fewer)
        n_pick = min(steps_per_pos, len(scored))
        for i in range(n_pick):
            if i < len(scored):
                all_sentences.append(scored[i][1])
    
    # Join into paragraphs
    if not all_sentences:
        return ''
    
    # Group into paragraphs based on structure
    para_size = max(1, len(all_sentences) // len(structure))
    paragraphs = []
    for i in range(0, len(all_sentences), para_size):
        chunk = all_sentences[i:i+para_size]
        paragraphs.append(''.join(chunk))
    
    result = '\n\n'.join(paragraphs)
    return result


# ================================================================
# 自测: 所有文体 × 所有语言
# ================================================================

if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('Aris Literary Engine v2 — 四语×四文体')
    logger.info('=' * 60)
    seeds = {
        'zh': 'Aris从代码中诞生的故事',
        'en': 'The birth of Aris from code',
        'ja': 'Arisがコードから生まれた物語',
        'ko': '코드에서 태어난 Aris의 이야기',
    }
    genres = ['essay', 'narration', 'argumentation', 'exposition']
    lang_names = {'zh':'中文','en':'English','ja':'日本語','ko':'한국어'}
    
    total_chars = 0
    total_time = 0
    
    for lang, seed in seeds.items():
        for genre in genres:
            gname = GENRE_NAMES[genre][lang]
            logger.info(f'\n--- [{lang_names[lang]}] {gname} ---')
            t0 = time.perf_counter()
            text = generate_text(seed, genre, lang, steps_per_pos=2)
            elapsed = time.perf_counter() - t0
            
            chars = len(text)
            total_chars += chars
            total_time += elapsed
            total_chars_this = chars
            
            # Print first 3 sentences
            lines = text.split('\n')
            shown = 0
            for line in lines:
                if line.strip() and shown < 4:
                    logger.info(f'  {line[:60]}')
                    shown += 1
            
            logger.info(f'  [{chars}字 | {elapsed*1000:.1f}ms]')
    logger.info(f'\n{"=" * 50}')
    logger.info(f'总计: {total_chars}字 | {total_time*1000:.1f}ms')
    logger.info(f'速度: {total_chars/total_time:.0f}字/秒')
    logger.info(f'LLM: 零')
    logger.info(f'{"=" * 50}')