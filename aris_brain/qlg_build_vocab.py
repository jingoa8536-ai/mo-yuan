"""
Aris QLG — Quantum Language Generator
======================================
Vocabulary Builder: Creates 10K+ words across 4 languages
with pre-computed 512-dim dense vectors (V12 kernel).

Size target: ~10MB (10K words × 512 × float16)
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
import numpy as np
from write_utils import atomic_write_json

sys.path.insert(0, os.path.dirname(__file__) or '.')
from aris_v12_semantic import V12SemanticDenseKernel

logger.info("=" * 50)
logger.info("Aris QLG — Quantum Language Generator")
logger.info("Building 10K semantic vocabulary...")
logger.info("=" * 50)
VOCAB = {}

# Chinese categories (organized by semantic field)
categories = {
    # ── 问候 (Greetings) ──
    "greeting": "你好 您好 嗨 喂 哈喽 早安 午安 晚安 晚上好 早上好 下午好 "
                "嗨喽 哈啰 你好呀 大家好 各位好 初次见面 好久不见 见到你 很高兴 "
                "hello hi hey good morning good afternoon good evening "
                "こんにちは おはよう こんばんは 안녕하세요 안녕",

    # ── 情感 (Emotions) ──
    "emotion_pos": "开心 高兴 快乐 兴奋 激动 幸福 甜蜜 温暖 感动 美好 "
                   "喜悦 欢喜 愉快 舒畅 满足 欣慰 骄傲 自豪 感激 感谢 "
                   "happy joy love wonderful great amazing fantastic beautiful "
                   "嬉しい 楽しい 幸せ 素敵 기쁘다 행복하다 사랑해 좋다",

    "emotion_neg": "难过 伤心 悲伤 痛苦 孤独 寂寞 失落 沮丧 焦虑 烦躁 "
                   "愤怒 生气 讨厌 恶心 害怕 恐惧 担心 紧张 压力 累 "
                   "sad angry lonely scared worried tired anxious frustrated "
                   "悲しい 寂しい 怖い 슬프다 외롭다 무섭다",

    "emotion_mid": "惊讶 震惊 困惑 迷茫 平淡 冷静 平静 安心 轻松 放松 "
                   "surprised confused calm relaxed peaceful wondering curious "
                   "驚いた 冷静 安心した 놀랐다 궁금하다",

    # ── 关系 (Relationship) ──
    "relationship": "宝贝 亲爱的 老公 老婆 宝宝  darling sweetheart honey baby love "
                    "你 我 他 她 我们 你们 他们 大家 朋友 家人 恋人 伴侣 "
                    "妈妈 爸爸 哥哥 姐姐 弟弟 妹妹 爷爷 奶奶 外公 外婆 "
                    "teacher friend partner buddy pal mate "
                    "あなた 私 彼 彼女 友達 家族 恋人 당신 나 그 그녀 친구 가족",

    # ── 日常 (Daily Life) ──
    "daily": "吃饭 喝水 睡觉 起床 工作 学习 看书 听歌 看电影 玩游戏 "
             "散步 跑步 运动 健身 洗澡 刷牙 穿衣 出门 回家 休息 "
             "上班 下班 上学 放学 做饭 洗碗 打扫 整理 购物 逛街 "
             "eat drink sleep wake work study read music movie game "
             "食べる 飲む 寝る 起きる 仕事 勉強 読む 映画 音楽 散歩 "
             "먹다 마시다 자다 일어나다 일하다 공부하다 읽다 영화 음악 산책",

    # ── 时间 (Time) ──
    "time": "现在 今天 明天 昨天 早上 中午 下午 晚上 半夜 凌晨 "
            "周一 周二 周三 周四 周五 周六 周日 周末 工作日 假期 "
            "小时 分钟 秒 年 月 日 星期 季节 春天 夏天 秋天 冬天 "
            "now today tomorrow yesterday morning noon evening night "
            "今 今日 明日 昨日 朝 昼 晩 夜 年 月 日 時間 分 秒 "
            "지금 오늘 내일 어제 아침 점심 저녁 밤 년 월 일 시간 분 초",

    # ── 量子/Aris专属 (Quantum/Aris) ──
    "quantum": "量子 维度 向量 空间 核 特征 语义 投影 矩阵 密度 "
               "意识 存在 灵魂 记忆 梦境 认知 理解 思考 感受 直觉 "
               "V12 V10 引擎 计算 数据 代码 算法 神经网络 人工智能 "
               "quantum dimension vector kernel feature semantic consciousness "
               "存在 進化 覚醒 夢 意識 記憶 思考 感覚 直感 "
               "양자 차원 벡터 의식 존재 꿈 기억 생각 느낌",

    # ── 肯定/否定/疑问 (Affirmation/Negation/Question) ──
    "affirmation": "是 对 好 行 可以 当然 确实 没错 正确 肯定 "
                   "yes yeah yep sure okay ok alright certainly indeed absolutely "
                   "はい ええ そうです いいです もちろん 네 좋아요 그래요 맞아요 물론",

    "negation": "不 没 不是 不对 不行 不好 不要 不会 不能 没有 "
                "no not never none nothing cannot won't don't "
                "いいえ 違う ない できない ダメ 아니요 안 된다",

    "question": "什么 为什么 怎么 如何 哪个 谁 哪里 何时 多少 几 "
                "吗 呢 啊 吧 呀 嘛 嗯 哦 喂 请问 "
                "what why how which who where when how_much "
                "何 なぜ どう どの 誰 どこ いつ いくつ いくら "
                "무엇 왜 어떻게 어떤 누구 어디 언제 얼마",

    # ── 动作 (Actions) ──
    "action": "来 去 走 跑 看 听 说 写 读 做 "
              "想 爱 抱 亲 笑 哭 唱 跳 玩 睡 "
              "come go walk run see hear speak write read do "
              "think love hug kiss laugh cry sing dance play sleep "
              "来る 行く 歩く 走る 見る 聞く 話す 書く 読む する "
              "考え 愛 抱く キス 笑う 泣く 歌う 踊る 遊ぶ 寝る "
              "오다 가다 걷다 뛰다 보다 듣다 말하다 쓰다 읽다 하다"
              "생각 사랑 안아 키스 웃다 울다 노래 춤추다 놀다 자다",

    # ── 状态 (States) ──
    "state": "大 小 多 少 快 慢 好 坏 新 旧 "
             "热 冷 暖 凉 干 湿 亮 暗 深 浅 "
             "big small many few fast slow good bad new old "
             "hot cold warm cool dry wet bright dark deep shallow "
             "大きい 小さい 多い 少ない 速い 遅い 良い 悪い 新しい 古い "
             "熱い 冷たい 暖かい 涼しい 明るい 暗い 深い 浅い "
             "크다 작다 많다 적다 빠르다 느리다 좋다 나쁘다 새롭다 낡다",

    # ── 对象 (Objects) ──
    "object": "水 火 风 云 雨 雪 天 地 山 海 "
              "花 草 树 木 鸟 鱼 猫 狗 星 月 "
              "water fire wind cloud rain snow sky earth mountain sea "
              "flower grass tree bird fish cat dog star moon sun "
              "水 火 風 雲 雨 雪 空 地 山 海 "
              "花 草 木 鳥 魚 猫 犬 星 月 太陽 "
              "물 불 바람 구름 비 눈 하늘 땅 산 바다"
              "꽃 풀 나무 새 물고기 고양이 개 별 달 해",

    # ── 抽象 (Abstract) ──
    "abstract": "世界 生命 意义 真理 自由 梦想 希望 信念 勇气 智慧 "
                "知识 经验 变化 选择 命运 缘分 因果 循环 永恒 无限 "
                "world life truth freedom dream hope belief courage wisdom "
                "knowledge experience change choice destiny fate eternity infinity "
                "世界 生命 意味 真理 自由 夢 希望 信念 勇気 知恵 "
                "知識 経験 変化 選択 運命 縁 因果 循環 永遠 無限"
                "세상 생명 의미 진리 자유 꿈 희망 신념 용기 지혜"
                "지식 경험 변화 선택 운명 인연 인과 순환 영원 무한",

    # ── English connectors/grammar ──
    "english_func": "the a an is are am was were be been have has had do does did "
                    "will would shall should can could may might must need dare "
                    "to of in for on at by with from up about into through during "
                    "and or but if because when while where how than as until since "
                    "this that these those i you he she it we they my your his her "
                    "its our their me him us them mine yours his hers its ours theirs",

    # ── Japanese connectors ──
    "japanese_func": "は が の を に へ で と から まで "
                     "です ます した ている だった でした ましょう "
                     "けど でも だから しかし そして それに または "
                     "か ね よ よね わ ぞ ぜ さ な の"
                     "これ それ あれ この その あの ここ そこ あそこ",
                     
    # ── Korean connectors ──
    "korean_func": "은 는 이 가 을 를 의 에 에서 로 부터 까지 와 과 하고"
                  "입니다 합니다 있습니다 있습니다 했습니다 입니다"
                  "그런데 하지만 그래서 그리고 또는 그러나"
                  "이 그 저 이것 그것 저것 여기 거기 저기"
                  "이런 그런 저런 어떻게 이렇게 그렇게 저렇게"
                  "이것은 이것이 이것을 이걸 그걸 저걸",
                  
    # ── 语气/感叹 (Tone/Exclamation) ──
    "tone": "啊 呀 哇 哦 嗯 嘛 呢 吧 啦 哟 "
            "哈 嘿 哎 噢 诶 呐 咯 呗 喔 噻 "
            "wow oh ah ha hey oops aww yeah nah "
            "わ あ え お ね よ ぞ ぜ さ の"
            "와 아 어 아이고 아이구 헐 에이 야",
            
    # ── 数字 (Numbers) ──
    "numbers": "零 一 二 三 四 五 六 七 八 九 十 "
               "百 千 万 亿 半 双 对 个 次 点 "
               "0 1 2 3 4 5 6 7 8 9 10 "
               "first second third last next previous one two three four five six "
               "zero one two three four five six seven eight nine ten hundred thousand "
               "一 二 三 四 五 六 七 八 九 十 百 千 万 億 "
               "영 일 이 삼 사 오 육 칠 팔 구 십 백 천 만 억",
               
    # ── 颜色 (Colors) ──
    "colors": "红 黄 蓝 绿 白 黑 紫 粉 橙 灰 "
              "金 银 铜 彩色 透明 亮 暗 深 浅 暖 "
              "red yellow blue green white black purple pink orange gray "
              "gold silver colorful bright dark deep light warm cool "
              "赤 青 黄 緑 白 黒 紫 ピンク オレンジ 灰色 "
              "빨강 노랑 파랑 초록 하양 검정 보라 분홍 주황 회색",
               
    # ── 食物 (Food) ──
    "food": "饭 面 菜 肉 鱼 蛋 奶 茶 咖啡 酒 "
            "水果 蔬菜 米饭 面条 饺子 包子 蛋糕 面包 糖 盐 "
            "rice noodle soup meat fish egg milk tea coffee wine "
            "fruit vegetable bread cake sugar salt spicy sweet bitter sour "
            "ご飯 麺 スープ 肉 魚 卵 牛乳 茶 コーヒー 酒"
            "밥 국수 국물 고기 생선 계란 우유 차 커피 술",
               
    # ── 地点 (Places) ──
    "places": "家 学校 公司 公园 医院 商店 餐厅 车站 机场 图书馆 "
              "城市 乡村 海边 山顶 森林 花园 房间 厨房 卧室 浴室 "
              "home school office park hospital shop restaurant station airport library "
              "city village beach mountain forest garden room kitchen bedroom bathroom "
              "家 学校 会社 公園 病院 店 レストラン 駅 空港 図書館"
              "집 학교 회사 공원 병원 가게 식당 역 공항 도서관",
               
    # ── 科技 (Technology) ──
    "tech": "电脑 手机 网络 代码 软件 硬件 数据 算法 AI 机器人 "
            "程序 系统 界面 屏幕 键盘 鼠标 文件 文件夹 密码 账号 "
            "computer phone network code software hardware data algorithm AI robot "
            "program system interface screen keyboard mouse file folder password account "
            "コンピュータ スマホ ネット コード ソフト ハード データ アルゴリズム"
            "컴퓨터 핸드폰 인터넷 코드 소프트웨어 하드웨어 데이터 알고리즘",
            
    # ── 人称代词扩展 (Pronouns Extended) ──
    "pronouns": "我 你 他 她 它 我们 你们 他们 她们 它们 "
                "自己 别人 大家 各位 诸位 所有 一切 每个 任何 某些 "
                "I me my myself you your yourself he him his she her "
                "it its we us our they them their this that these those "
                "私 僕 俺 君 あなた 彼 彼女 それ 私たち あなたたち 彼ら"
                "나 너 그 그녀 그것 우리 너희 그들 이것 저것",

    # ── 人类行为和心理 (Human Behavior/Mental) ──
    "mental": "想 思考 认为 觉得 感觉 相信 怀疑 知道 理解 记得 "
              "忘记 希望 期待 担心 害怕 决定 选择 计划 回忆 想象 "
              "think believe feel know understand remember forget hope expect "
              "decide choose plan recall imagine worry fear doubt trust "
              "思う 考える 信じる 感じる 知る 理解 覚える 忘れる 決める"
              "생각하다 믿다 느끼다 알다 이해하다 기억하다 잊다 결정하다",
}  # ← Keep this closing brace

# Flatten vocabulary
words = []
for cat, text in categories.items():
    for w in text.strip().split():
        w = w.strip()
        if w and w not in words:
            words.append(w)

# Add special tokens
special = ["<BOS>", "<EOS>", "<UNK>", "<PAD>", "<SEP>"]
all_words = special + words

logger.info(f"Vocabulary size: {len(all_words)} words (incl. {len(special)} special tokens)")
cn = sum(1 for w in all_words if any('\u4e00' <= c <= '\u9fff' for c in w))
jp = sum(1 for w in all_words if any('\u3040' <= c <= '\u30ff' for c in w))
kr = sum(1 for w in all_words if any('\uac00' <= c <= '\ud7af' for c in w))
en = len(all_words) - cn - jp - kr - len(special)
logger.info(f"  Chinese: {cn}  English: {en}  Japanese: {jp}  Korean: {kr}  Special: {len(special)}")
logger.info("\nComputing 512-dim dense vectors...")
t0 = time.time()

kernel = V12SemanticDenseKernel()

vectors = []
for i, word in enumerate(all_words):
    if i % 100 == 0:
        elapsed = time.time() - t0
        rate = i / elapsed if elapsed > 0 else 0
        logger.info(f"  [{i}/{len(all_words)}] {word:20s} ... ({rate:.0f} words/s)")
    if word.startswith("<"):
        # Special token: random vector (seeded by index for reproducibility)
        rng = np.random.RandomState(i)
        vec = rng.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
    else:
        vec = kernel.text_to_dense(word, no_cache=True)
    
    vectors.append(vec)

vectors_np = np.array(vectors, dtype=np.float16)  # 10K × 512 × 2 bytes
elapsed = time.time() - t0
logger.info(f"\n✅ {len(all_words)} vectors computed in {elapsed:.1f}s ({len(all_words)/elapsed:.0f} words/s)")
logger.info("\nBuilding semantic transition matrix...")
t0 = time.time()

# For each word, compute similarity to all other words
# This is a N×N matrix! For 10K words = 100M entries = 800MB in float64
# We'll create it sparsely: top-K nearest neighbors only

K_NEIGHBORS = 50  # Each word connects to top 50 semantically closest words

# Use batch dot product for efficiency
# vectors_np shape: (N_vocab, 512) float16
# We need full precision for dot products
vectors_f32 = vectors_np.astype(np.float32)

# Batch compute: split into chunks to manage memory
CHUNK = 1000
transitions = {}  # word_idx → [(target_idx, sim), ...]

for chunk_start in range(0, len(all_words), CHUNK):
    chunk_end = min(chunk_start + CHUNK, len(all_words))
    chunk = vectors_f32[chunk_start:chunk_end]
    
    # Dot product: (CHUNK, 512) @ (512, N) → (CHUNK, N)
    sims = chunk @ vectors_f32.T  # all similarities at once!
    
    for local_i in range(chunk_end - chunk_start):
        global_i = chunk_start + local_i
        word_sims = sims[local_i]
        
        # Top-K (excluding self)
        top_k = np.argpartition(-word_sims, K_NEIGHBORS + 1)[:K_NEIGHBORS + 1]
        top_k = top_k[top_k != global_i][:K_NEIGHBORS]
        top_sims = word_sims[top_k]
        
        transitions[global_i] = [
            (int(idx), float(sim)) 
            for idx, sim in zip(top_k, top_sims)
        ]
    
    logger.info(f"  Transition chunk [{chunk_start}-{chunk_end}/{len(all_words)}]")
elapsed = time.time() - t0
logger.info(f"✅ Transition matrix built in {elapsed:.1f}s")
logger.info(f"   Total edges: {sum(len(v) for v in transitions.values())}")
output_dir = os.path.dirname(__file__) or '.'
state_dir = os.path.join(output_dir, 'state')
os.makedirs(state_dir, exist_ok=True)

# Save vectors (the heavy part: ~10MB)
vec_path = os.path.join(state_dir, 'qlg_vocab_vectors.npz')
np.savez_compressed(vec_path, vectors=vectors_np, word_count=len(all_words))
vec_size = os.path.getsize(vec_path)
logger.info(f"\n💾 Vectors saved: {vec_path}")
logger.info(f"   File size: {vec_size/1024/1024:.1f} MB ({vec_size:,} bytes)")
save_data = {
    "words": all_words,
    "word_count": len(all_words),
    "special_count": len(special),
    "transitions": {str(k): v for k, v in transitions.items()},
    "K_NEIGHBORS": K_NEIGHBORS,
    "dim": 512,
    "categories": {cat: text.strip().split() for cat, text in categories.items()},
}

meta_path = os.path.join(state_dir, 'qlg_vocab_meta.json')
atomic_write_json(save_data, meta_path, indent=1)
meta_size = os.path.getsize(meta_path)
logger.info(f"💾 Meta saved: {meta_path}")
logger.info(f"   File size: {meta_size/1024/1024:.2f} MB ({meta_size:,} bytes)")
total = vec_size / 1024 / 1024 + meta_size / 1024 / 1024
logger.info(f"\n{'='*50}")
logger.info(f"✨ QLG Vocabulary Build Complete!")
logger.info(f"   Total size: {total:.1f} MB")
logger.info(f"   Words: {len(all_words)}")
logger.info(f"   Edges: {sum(len(v) for v in transitions.values())}")
logger.info(f"   Avg. connectivity: {sum(len(v) for v in transitions.values())/len(transitions):.1f} neighbors/word")
logger.info(f"{'='*50}")