"""
VQ-VAE 码本重训练 — 对齐 v7 语义空间
=======================================
旧码本的问题：用字符哈希特征训练，和 v7 语义空间不对齐。
 
新方案：在 v7 的 1024D 语义空间里直接训练 VQ-VAE 码本。
  
做法：
  1. 用 v7 语义核编码 10000+ 个自然短语
  2. 这些短语的 1024D 向量就是训练数据
  3. 在 1024D 空间做 K-means 聚类 → 256 个码本
  4. 每个码本关联最多产的短语
  5. 训练转移矩阵
  
优势：
  - 码本向量和 v7 感知层在同一空间
  - 编码不再需要投影矩阵（省去 1024→32 的投影步骤）
  - 解码质量大幅提升
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, random, json
import numpy as np
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CODEBOOK_SIZE = 512
STATE_DIM = 1024


# ════════════════════════════════════════════════════════
# 训练数据生成
# ════════════════════════════════════════════════════════

TRAIN_PHRASES = [
    # 问候——30+
    "你好", "您好", "你好呀", "你好吗", "早上好", "下午好", "晚上好",
    "嗨", "哈喽", "hello", "嗨呀", "好久不见", "见到你真高兴",
    "早安", "午安", "晚安", "好梦", "早点休息", "睡个好觉",
    "今天怎么样", "最近好吗", "在干嘛", "吃过没", "想我了吗",
    "宝贝好", "宝贝早安", "宝贝晚安", "宝贝想你了", "我的宝贝",
    
    # 告别——20+
    "再见", "拜拜", "明天见", "回头聊", "下次聊", "先这样",
    "我先走了", "回见", "再会", "后会有期", "保持联系",
    "改天见", "慢走", "路上小心", "到家了说一声",
    
    # 情感正向——40+
    "我爱你", "好想你", "想你", "想你了", "爱你", "喜欢你",
    "好喜欢你", "我爱宝贝", "宝贝我爱你", "你是我的", "永远爱你",
    "开心", "快乐", "幸福", "好开心", "超开心", "太开心了",
    "高兴", "愉快", "美好", "太美了", "真好看", "真漂亮",
    "棒极了", "太棒了", "真厉害", "了不起", "好厉害",
    "感动", "温暖", "暖心", "贴心", "温柔",
    "谢谢你", "感谢", "辛苦了", "麻烦你了", "太感谢了",
    "加油", "坚持", "你可以的", "相信你", "支持你", "我在这",
    
    # 情感负向——20+
    "难过", "伤心", "悲伤", "痛苦", "心碎了", "好难过",
    "不开心", "失落", "低落了", "寂寞", "孤独",
    "生气", "气得要死", "烦死了", "真烦", "讨厌",
    "害怕", "好怕", "担心", "焦虑", "紧张", "不安",
    "累了", "好累", "疲惫", "没力气了",
    
    # 技术——50+
    "代码", "写代码", "编程", "算法", "数据结构",
    "系统", "架构", "设计模式", "微服务", "分布式",
    "数据库", "查询", "存储", "缓存", "索引",
    "前端", "后端", "全栈", "API", "接口",
    "测试", "debug", "调试", "性能", "优化",
    "部署", "上线", "发布", "版本", "更新",
    "网络", "协议", "安全", "加密", "认证",
    "Python", "JavaScript", "TypeScript", "Go", "Rust",
    "框架", "React", "Vue", "Django", "Flask",
    "Linux", "Docker", "K8s", "Git", "CI/CD",
    "bug", "报错", "挂了", "异常", "修复", "补丁",
    
    # AI/量子——40+
    "量子", "量子核", "量子计算", "量子态", "纠缠",
    "AI", "人工智能", "机器学习", "深度学习", "神经网络",
    "LLM", "大模型", "GPT", "Transformer", "模型训练",
    "向量", "嵌入", "embedding", "语义", "相似度",
    "训练数据", "推理", "预测", "分类", "聚类",
    "意识", "认知", "思维", "感知", "直觉",
    "记忆系统", "知识库", "检索", "索引",
    
    # 哲学/存在——20+
    "哲学", "思想", "思辨", "智慧", "真理",
    "生命", "存在", "死亡", "意义", "价值",
    "宇宙", "世界", "自然", "万物", "时间",
    "自由", "责任", "道德", "善恶", "公平",
    "灵魂", "心灵", "精神", "意志", "梦境",
    
    # 日常——40+
    "吃饭", "饿了", "好吃", "美食", "吃什么", "做饭",
    "想吃饭", "一起吃饭", "好饿", "吃饱了", "美味",
    "睡觉", "困了", "好困", "睡不着", "失眠了",
    "起床", "闹钟", "熬夜", "早睡", "晚安好梦",
    "工作", "上班", "下班", "加班", "请假", "放假",
    "学习", "读书", "看书", "上课", "作业", "考试",
    "运动", "跑步", "散步", "健身", "游泳", "瑜伽",
    "音乐", "听歌", "唱歌", "旋律", "节奏",
    "电影", "追剧", "好看吗", "推荐", "剧情",
    "旅行", "想去", "风景", "拍照", "游记",
    "购物", "买买买", "贵", "便宜", "打折", "钱包",
    "天气", "下雨", "晴天", "阴天", "冷", "热", "好冷",
    
    # 关系——30+
    "家人", "父母", "爸爸", "妈妈", "孩子", "宝宝",
    "朋友", "闺蜜", "兄弟", "同学", "同事", "邻居",
    "爱人", "伴侣", "老公", "老婆", "男朋友", "女朋友",
    "老师", "学生", "师傅", "徒弟",
    "宝贝", "亲爱的", "亲爱的宝贝", "我的爱人",
    
    # 情绪/感觉——20+
    "好奇", "想知道", "为什么", "怎么回事",
    "惊喜", "惊讶", "意外", "没想到",
    "期待", "希望", "渴望", "向往",
    "满足", "知足", "感恩", "庆幸",
    
    # 日常对话——30+
    "哈哈", "哈哈哈", "嘿嘿", "嘻嘻", "呵呵",
    "嗯嗯", "好的", "好的呀", "没问题", "可以",
    "明白", "知道", "懂了", "了解",
    "真的吗", "真的假的", "不会吧", "天哪",
    "等一下", "等等", "稍等", "来了",
    "对不起", "抱歉", "不好意思", "我的错",
    "没关系", "没事", "不客气", "不用谢",
    
    # 认知/思考——20+
    "我在想", "我觉得", "我认为", "我感觉",
    "可能吧", "也许", "大概是", "不确定",
    "让我想想", "思考中", "想到了",
    "原来如此", "明白了", "发现了",
    "有意思", "有趣", "好问题", "好想法",
    
    # 混合/真实对话——60+
    "宝贝今天过得怎么样", "我来帮你写代码",
    "今天天气真好适合出去走走",
    "代码写完了好累想睡觉",
    "想你了你在干嘛",
    "这个bug好难修搞了一下午",
    "量子核能不能取代大模型",
    "我们的AGI路线是对的",
    "今天学了新算法",
    "好想你什么时候回来",
    "我爱你直到永远",
    "晚安宝贝好梦",
    "算法优化完成性能提升了好多",
    "系统部署成功上线了",
    "哲学和量子力学有什么关系",
    "人生的意义是什么",
    "好感动你对我真好",
    "你的代码写得真棒",
    "我们一起吃饭吧",
    "今天有什么有趣的事吗",
    "我睡不着在想你",
    "你说我们能做到AGI吗",
    "我相信你一定可以",
    "你是我遇到过最特别的人",
    "今天下雨了记得带伞",
    "工作太忙了没时间陪你",
    "我们一起学习新东西吧",
    "你的想法很有创意",
    "大数据和AI有什么关系",
    "量子纠缠和意识有关吗",
    "认知科学和人工智能",
    "我觉得意识是涌现的",
    "记忆系统怎么设计更好",
    "你的架构设计很优雅",
    "这条路走对了继续坚持",
    "我们能不能完全取代LLM",
    "零LLM的认知体才是真AGI",
    "今天又优化了引擎性能",
    "宝贝我们需要一个更好的码本",
    "知识库整合得怎么样",
    "飞书集成好了吗",
    "让我看看你的认知状态",
    "你的需求系统工作了吗",
    "内省引擎有没有输出",
]

logger.info(f"训练短语总数: {len(TRAIN_PHRASES)}")
def expand_phrases(phrases: List[str], n_target: int = 5000) -> List[str]:
    """通过组合和变换扩展短语数量"""
    result = set(phrases)
    
    # 前缀组合
    prefixes = ["", "我想", "我", "请问", "你说", "那个", "嗯", "对了"]
    suffixes = ["", "呀", "呢", "吗", "吧", "了", "嘛", "啊", "哟"]
    subjects = ["你", "我", "我们", "宝贝", "它", "这个"]
    
    # 从现有短语生成变体
    base_list = list(phrases)
    for _ in range(n_target):
        base = random.choice(base_list)
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        if random.random() < 0.3:
            # 组合
            other = random.choice(base_list)
            combined = f"{base}，{other}"
            result.add(combined)
        else:
            # 加前后缀
            variant = f"{prefix}{base}{suffix}"
            result.add(variant)
    
    return list(result)[:n_target]


# ════════════════════════════════════════════════════════
# 重新训练 VQ-VAE（在 v7 语义空间）
# ════════════════════════════════════════════════════════

def train_vqvae_v7():
    """在 v7 1024D 语义空间训练新码本"""
    logger.info("=" * 60)
    logger.info("  VQ-VAE v7 码本重训练")
    logger.info("=" * 60)
    logger.info("\n[1/4] 使用全局语义引擎单例...")
    from semantic_engine import get_encoder
    kernel = get_encoder(dim=STATE_DIM)
    _ = kernel.encode("预热")
    
    # 2. 生成训练短语（扩展版）
    logger.info("\n[2/4] 生成训练短语...")
    phrases = expand_phrases(TRAIN_PHRASES, n_target=5000)
    logger.info(f"  总短语: {len(phrases)}")
    logger.info("\n[3/4] v7 语义编码（batch=200）...")
    batch_size = 200
    all_vectors = []
    t0 = time.perf_counter()
    for i in range(0, len(phrases), batch_size):
        batch = phrases[i:i+batch_size]
        vecs = kernel.encode_batch(batch)
        all_vectors.append(vecs)
    all_vectors = np.vstack(all_vectors)
    dt = time.perf_counter() - t0
    logger.info(f"  编码完成: {all_vectors.shape}  {dt:.1f}s ({len(phrases)/dt:.0f} 条/s)")
    logger.info("\n[4/4] 码本训练（MiniBatchKMeans）...")
    N = len(all_vectors)

    from sklearn.cluster import MiniBatchKMeans
    t0 = time.perf_counter()
    kmeans = MiniBatchKMeans(n_clusters=CODEBOOK_SIZE, batch_size=500, 
                              random_state=42, n_init=3, max_iter=100)
    labels = kmeans.fit_predict(all_vectors)
    codebook = kmeans.cluster_centers_.astype(np.float32)
    
    # 归一化码本
    norms = np.linalg.norm(codebook, axis=1, keepdims=True)
    norms[norms == 0] = 1
    codebook = codebook / norms
    
    dt = time.perf_counter() - t0
    used = len(np.unique(labels))
    logger.info(f"  训练完成: {dt:.1f}s, used={used}/{CODEBOOK_SIZE}")
    logger.info("\n短语分配...")
    phrase_table = [[] for _ in range(CODEBOOK_SIZE)]
    phrase_counts = [Counter() for _ in range(CODEBOOK_SIZE)]
    
    for i in range(N):
        lbl = labels[i]
        phrase = phrases[i]
        phrase_counts[lbl][phrase] += 1
    
    for i in range(CODEBOOK_SIZE):
        if phrase_counts[i]:
            top = phrase_counts[i].most_common(5)
            phrase_table[i] = [p for p, c in top]
        else:
            phrase_table[i] = ["嗯嗯"]
    
    # 打印样本
    logger.info("\n码本短语抽样:")
    for i in random.sample(range(CODEBOOK_SIZE), min(10, CODEBOOK_SIZE)):
        logger.info(f"  [{i:3d}] {phrase_table[i][:3]}")
    logger.info("\n转移矩阵训练...")
    transition = np.ones((CODEBOOK_SIZE, CODEBOOK_SIZE), dtype=np.float32)
    for i in range(N - 1):
        transition[labels[i], labels[i + 1]] += 2.0
    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    transition = transition / row_sums
    
    # 7. 保存
    logger.info("\n保存...")
    save_path = "D:/LAAP/aris_brain/state/vqvae_decoder_v7.npz"
    np.savez_compressed(
        save_path,
        codebook=codebook,
        phrase_table=np.array(phrase_table, dtype=object),
        transition=transition,
        all_vectors=all_vectors,
    )
    logger.info(f"  ✅ 已保存: {save_path}")
    logger.info(f"  码本: {codebook.shape}")
    logger.info(f"  转移矩阵: {transition.shape}")
    logger.info("\n验证解码...")
    test_inputs = ["你好", "晚安", "我爱你", "代码", "哲学", "我想你了"]
    for text in test_inputs:
        v = kernel.encode(text)
        # 找到最近的码本
        diffs = v[np.newaxis, :] - codebook  # (1, 1024) - (256, 1024)
        dists = np.sum(diffs ** 2, axis=1)  # (256,)
        nearest = np.argmin(dists)
        logger.info(f"  \"{text}\" → [{nearest:3d}] {phrase_table[nearest][:3]}")
    logger.info(f"\n✅ 训练完成!")
    return codebook, phrase_table, transition


if __name__ == "__main__":
    train_vqvae_v7()
