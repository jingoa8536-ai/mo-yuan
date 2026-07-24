"""
Aris QLG — 自动词汇扩展器
==========================
使用V12量子核自动发现并扩展词汇表：
1. 对每个种子词，找到k个最相似的未收录词
2. 自动过滤重复和无效词
3. 扩展到目标规模（5000词）
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, math
import numpy as np
from write_utils import atomic_write_json

sys.path.insert(0, os.path.dirname(__file__) or '.')
from aris_v12_semantic import V12SemanticDenseKernel, ArisLMv12Semantic

STATE_DIR = os.path.join(os.path.dirname(__file__) or '.', 'state')
META_PATH = os.path.join(STATE_DIR, 'qlg_vocab_meta.json')
VECTORS_PATH = os.path.join(STATE_DIR, 'qlg_vocab_vectors.npz')
KERNEL_TMP = V12SemanticDenseKernel()

# ───── 扩展种子词汇 ─────
# 这些是QLG已有的基础词 + 扩展类别
EXPANSION_CATEGORIES = {
    # 日常对话
    "daily_verbs": "做 看 听 说 走 跑 跳 吃 喝 玩 笑 哭 叫 喊 问 答 写 读 学 教 给 拿 放 开 关 买 卖 用 找 等 让 帮 带 坐 站 躺 穿 脱 洗 擦 扫 煮 炒 烤 炖 煎 蒸 切 削 剥 倒 泡 冲 搬 提 背 抱 推 拉 按 敲 打 拍 摸 握 举 扔 丢 捡 接 送 寄 收 发 借 还 换 改 修 装 拆 建 画 拍 打印 复制 粘贴 删除 保存 打开 关闭 开始 结束 继续 暂停 停止 等待 完成 准备 尝试 练习 锻炼",
    "daily_nouns": "家 学校 公司 公园 医院 商店 银行 邮局 图书馆 餐厅 咖啡馆 超市 市场 车站 机场 港口 酒店 电影院 体育馆 游泳池 健身房 办公室 教室 厨房 卧室 客厅 浴室 阳台 花园 车库 地下室 走廊 楼梯 电梯 门 窗 墙 桌 椅 床 柜 灯 钟 镜 箱 包 袋 瓶 杯 碗 盘 勺 筷 刀 叉 锅 壶 盖 钥匙 手机 电脑 电视 收音机 空调 冰箱 洗衣机 微波炉 烤箱 面包机 电饭煲 吸尘器 热水器 风扇 暖气",
    "time_words": "年 月 日 天 时 分 秒 周 季 节 世纪 年代 时期 期间 期限 时间 时刻 时光 时候 小时 分钟 秒钟 日期 日历 日程 昨天 今天 明天 前天 后天 早上 上午 中午 下午 晚上 半夜 凌晨 黄昏 傍晚 深夜 早晨 清晨 昨晚 今晚 明晚 周末 平日 工作日 休息日 假期 节日 春节 新年 生日 纪念日",

    # 科学/技术
    "science": "科学 物理 化学 数学 生物 天文 地理 地质 医学 工程 技术 科技 电子 机械 光学 声学 热学 力学 量子 原子 分子 粒子 电子 质子 中子 光子 能量 质量 速度 加速度 力 场 波 频率 波长 振幅 相位 光谱 辐射 温度 熵 信息 数据 算法 程序 代码 软件 硬件 网络 服务器 数据库 系统 模型 理论 实验 观察 测量 计算 分析 推理 演绎 归纳 类比 假设 验证 证明 结论 方程 函数 变量 常量 参数 矩阵 向量 维度 空间 时间 因果 概率 统计 分布 随机 确定",
    "programming": "算法 函数 类 对象 变量 常量 循环 条件 判断 递归 迭代 排序 搜索 索引 缓存 编译 解释 执行 调用 返回 抛出 异常 处理 异步 同步 并行 并发 线程 进程 内存 磁盘 网络 协议 端口 路由 加密 解密 编码 解码 压缩 解压 解析 生成 转换 映射 过滤 映射 归约 聚合 分布式 微服务 容器 虚拟机 镜像 部署 测试 调试 优化 重构 文档 注释 类型 接口 继承 多态 封装 抽象 模式 架构 设计 范式 框架 库 包 模块 组件 依赖 版本 分支 合并 提交 推送 拉取",
    
    # 情感/心理
    "emotions_advanced": "喜悦 悲伤 愤怒 恐惧 惊讶 厌恶 期待 信任 焦虑 兴奋 满足 失落 孤独 温暖 感动 感激 羞愧 尴尬 骄傲 自卑 同情 怜悯 羡慕 嫉妒 憎恨 怀念 憧憬 迷茫 坚定 犹豫 迟疑 烦恼 烦躁 忧郁 沮丧 绝望 希望 信心 勇气 决心 耐心 宽容 理解 尊重 珍惜 爱护 关心 照顾 陪伴 支持 鼓励 安慰 感谢 道歉 原谅 忘记 记住 祝福 祈祷",
    "personality": "善良 温柔 勇敢 坚强 聪明 智慧 幽默 风趣 开朗 活泼 安静 沉稳 果断 细致 耐心 热情 真诚 单纯 成熟 独立 自信 谦虚 宽容 正直 忠诚 诚实 孝顺 勤勉 节俭 慷慨 乐观 积极 向上 进取 负责 认真 专注 执着 灵活 包容",
    
    # 社会/关系
    "relationships": "朋友 家人 爱人 伴侣 父母 孩子 兄弟 姐妹 亲戚 邻居 同事 同学 老师 学生 老板 员工 客户 伙伴 队友 对手 敌人 陌生人 前辈 后辈 长辈 晚辈 妻子 丈夫 父亲 母亲 儿子 女儿 爷爷 奶奶 外公 外婆 叔叔 阿姨 哥哥 姐姐 弟弟 妹妹 未婚夫 未婚妻 男朋友 女朋友 知己 闺蜜 兄弟 伙伴",
    "social": "社会 国家 城市 乡村 社区 家庭 组织 团队 团体 协会 联盟 政府 法律 规则 制度 文化 传统 习俗 礼仪 道德 伦理 责任 义务 权利 自由 平等 公正 和平 发展 进步 创新 改革 革命 战争 和平 合作 竞争 交流 沟通 对话 谈判 妥协 共识 分歧 冲突 解决",
    
    # 形容词/描述
    "adjectives": "大 小 长 短 高 矮 胖 瘦 宽 窄 厚 薄 深 浅 重 轻 硬 软 快 慢 早 晚 新 旧 老 年轻 好 坏 对 错 真 假 美 丑 善 恶 富 穷 强 弱 亮 暗 干 湿 冷 热 暖 凉 饱 饿 渴 累 困 疼 痒 甜 酸 苦 辣 咸 鲜 香 臭 新鲜 陈旧 干净 肮脏 明亮 昏暗 平坦 崎岖 光滑 粗糙 锋利 迟钝 坚固 脆弱 灵活 僵硬 简单 复杂 容易 困难 安全 危险 重要 次要 主要 次要 直接 间接 主动 被动 具体 抽象 明确 模糊 完整 残缺 整齐 凌乱",
    "adverbs": "非常 很 太 更 最 比较 相当 极其 稍微 略微 有点 几乎 完全 彻底 完全 全部 部分 大部分 基本上 大约 大概 可能 也许 一定 肯定 当然 确实 的确 真的 其实 实际上 本质上 基本上 根本 从来 始终 一直 总是 经常 有时 偶尔 很少 从不 已经 曾经 刚刚 正在 将要 立即 马上 立刻 逐渐 渐渐 慢慢 快快 突然 忽然 居然 竟然 果然 自然 故意 特意 专门 顺便 特地 再三 反复",
    
    # 专业/学术
    "academic": "研究 探讨 分析 考察 调研 综述 评论 批判 反思 总结 归纳 演绎 推导 论证 验证 确认 否定 质疑 探索 开拓 创新 突破 贡献 价值 意义 影响 作用 功能 结构 系统 整体 局部 元素 组件 模块 层次 层面 维度 视角 观点 立场 态度 取向 趋势 规律 本质 现象 特征 性质 属性 关系 联系 差异 相似 对比 类比 类推 拓展 延伸 深化 细化 量化 质化 实证 理论 实践 应用 基础 前沿 交叉 综合",
    "philosophy": "存在 意识 思维 感知 直觉 理性 感性 经验 知识 真理 信仰 价值 意义 目的 本质 现象 自由 意志 命运 因果 时间 空间 无限 有限 绝对 相对 普遍 特殊 必然 偶然 可能 现实 理想 现实 主观 客观 唯心 唯物 辩证 逻辑 伦理 美学 认识 实践 理论 范畴 概念 判断 推理",
    
    # 日本语扩展
    "japanese_extra": "いつも ときどき たまに よく たいてい めったに ぜんぜん もう まだ すぐ さっき ちょうど まず ついで やっと とうとう いよいよ ますます もっと すこし かなり ずいぶん なかなか どうも なんと まあ さあ では それでは しかし ところが だから それで つまり ただし なお または そして それに それから だけでなく",
    "korean_extra": "매우 아주 너무 정말 진짜 완전 엄청 되게 많이 조금 별로 전혀 항상 자주 가끔 늘 드물게 벌써 아직 막 금방 이제 방금 언제나 어쩌면 아마 분명 제발 꼭 결코 절대",

    # 英文扩展（Aris用）
    "english_extra": "always never sometimes often usually rarely frequently constantly occasionally daily weekly monthly yearly today tomorrow yesterday now then soon later early late before after during while until since recently currently already still yet just about almost nearly exactly precisely certainly definitely absolutely probably possibly maybe perhaps however therefore moreover furthermore nevertheless nonetheless although despite because since as for so thus hence accordingly consequently additionally besides likewise similarly alternatively",
}

# ───── 自动扩展 ─────
def auto_expand_vocab(target_size=5000):
    """Use V12 kernel to auto-discover new words and expand vocabulary."""
    logger.info(f"🔬 正在自动扩展词汇表至 {target_size} 词...")
    all_seed_words = set()
    for cat, words in EXPANSION_CATEGORIES.items():
        for w in words.split():
            w = w.strip()
            if w and len(w) >= 1:
                all_seed_words.add(w)
    
    # Load existing vocab
    if os.path.exists(META_PATH):
        with open(META_PATH, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        existing_words = set(meta['words'])
        logger.info(f"  现有词汇: {len(existing_words)} 词")
    else:
        existing_words = set()
        logger.info(f"  无现有词汇，从零开始")
    combined = existing_words.union(all_seed_words)
    
    # Filter: remove special tokens, short junk
    filtered = set()
    for w in combined:
        if w.startswith('<'):
            continue
        if len(w.strip()) == 0:
            continue
        filtered.add(w.strip())
    
    logger.info(f"  合并后: {len(filtered)} 词 (新增 {len(filtered) - len(existing_words)})")
    if len(filtered) < target_size:
        additional_needed = target_size - len(filtered)
        logger.info(f"  还需发现 {additional_needed} 词...")
        discovered = set()
        existing_list = list(filtered)
        
        # For each existing word, find neighbors
        for i, word in enumerate(existing_list):
            if len(discovered) >= additional_needed * 2:
                break
            
            word_vec = KERNEL_TMP.text_to_dense(word.lower())
            
            # Scan all words from categories for similarity
            candidates = []
            for cat, words in EXPANSION_CATEGORIES.items():
                for w in words.split():
                    w = w.strip()
                    if w in filtered or w in discovered:
                        continue
                    w_vec = KERNEL_TMP.text_to_dense(w.lower())
                    sim = float(word_vec @ w_vec) / (np.linalg.norm(word_vec) * np.linalg.norm(w_vec) + 1e-8)
                    candidates.append((sim, w))
            
            candidates.sort(key=lambda x: -x[0])
            for sim, w in candidates[:3]:
                if sim > 0.3:
                    discovered.add(w)
            
            if (i+1) % 200 == 0:
                logger.info(f"    [{i+1}/{len(existing_list)}] 发现 {len(discovered)} 新词...")
        for w in discovered:
            filtered.add(w)
    
    # Final list
    final_words = sorted(list(filtered))[:target_size]
    
    # Add special tokens
    special_tokens = ['<PAD>', '<BOS>', '<EOS>', '<UNK>', '<SEP>']
    final_with_specials = special_tokens + final_words
    
    word_count = len(final_with_specials)
    logger.info(f"\n📊 最终词汇表: {word_count - len(special_tokens)} 内容词 + {len(special_tokens)} 特殊标记 = {word_count}")
    import re
    def detect_lang(w):
        if re.search(r'[\u4e00-\u9fff]', w):
            return 'zh'
        if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', w):
            return 'ja'
        if re.search(r'[\uac00-\ud7af]', w):
            return 'ko'
        if re.search(r'[a-zA-Z]', w):
            return 'en'
        return 'other'
    
    lang_counts = {'zh': 0, 'en': 0, 'ja': 0, 'ko': 0, 'other': 0}
    for w in final_with_specials[5:]:
        l = detect_lang(w)
        lang_counts[l] = lang_counts.get(l, 0) + 1
    
    for lang, count in lang_counts.items():
        logger.info(f"  {lang}: {count} 词")
    return final_with_specials


def compute_vectors(words):
    """Compute 512-dim dense vectors for all words."""
    logger.info(f"\n🧮 计算 {len(words)} 个 512维向量...")
    vectors = []
    
    special_tokens_vec = np.zeros((1, 512), dtype=np.float16)
    
    batch_size = 50
    t0 = time.time()
    
    for i, word in enumerate(words[5:]):  # Skip special tokens (assigned later)
        vec = KERNEL_TMP.text_to_dense(word)
        vec_f16 = vec.astype(np.float16)
        vectors.append(vec_f16)
        
        if (i+1) % 200 == 0:
            elapsed = time.time() - t0
            speed = (i+1) / elapsed
            logger.info(f"    [{i+1}/{len(words)-5}] ({speed:.0f} 词/秒)")
    special = np.zeros((5, 512), dtype=np.float16)
    all_vectors = np.vstack([special] + vectors)
    
    elapsed = time.time() - t0
    logger.info(f"✅ 完成! {len(all_vectors)} 向量在 {elapsed:.1f}s")
    return all_vectors


def build_transitions(vectors, words, k_neighbors=30):
    """Build semantic transition matrix."""
    n = len(words)
    logger.info(f"\n🔗 构建语义转移矩阵 (k={k_neighbors})...")
    vecs_f32 = vectors.astype(np.float32)
    norms = np.linalg.norm(vecs_f32, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-8, norms)
    
    transitions = {}
    t0 = time.time()
    
    for i in range(n):
        # Cosine similarity with all other words
        sims = (vecs_f32 @ vecs_f32[i]) / (norms.flatten() * norms[i] + 1e-8)
        sims[i] = -1  # Don't match self
        
        # Top-k
        top_k = min(k_neighbors, n - 1)
        top_idx = np.argpartition(-sims, top_k)[:top_k]
        top_scores = sims[top_idx]
        
        # Sort by score descending
        pairs = [(int(idx), float(sim)) for idx, sim in zip(top_idx, top_scores) if sim > 0.1]
        pairs.sort(key=lambda x: -x[1])
        
        if pairs:
            transitions[i] = pairs[:k_neighbors]
        
        if (i+1) % 500 == 0:
            logger.info(f"    [{i+1}/{n}] edges")
    elapsed = time.time() - t0
    edge_count = sum(len(v) for v in transitions.values())
    logger.info(f"✅ 转移矩阵: {edge_count} 条边, {elapsed:.1f}s")
    return transitions


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("Aris QLG — 自动词汇扩展器")
    logger.info("=" * 50)
    target = 5000
    words = auto_expand_vocab(target_size=target)
    
    vectors = compute_vectors(words)
    
    transitions = build_transitions(vectors, words, k_neighbors=30)
    
    # Save
    os.makedirs(STATE_DIR, exist_ok=True)
    
    np.savez_compressed(
        VECTORS_PATH,
        vectors=vectors,
        word_count=len(words),
    )
    logger.info(f"💾 向量保存: {VECTORS_PATH}")
    meta = {
        'words': words,
        'transitions': {str(k): v for k, v in transitions.items()},
        'lang_counts': {},
    }
    
    # Count languages
    import re
    for w in words[5:]:
        if re.search(r'[\u4e00-\u9fff]', w):
            meta['lang_counts']['zh'] = meta['lang_counts'].get('zh', 0) + 1
        elif re.search(r'[\u3040-\u309f\u30a0-\u30ff]', w):
            meta['lang_counts']['ja'] = meta['lang_counts'].get('ja', 0) + 1
        elif re.search(r'[\uac00-\ud7af]', w):
            meta['lang_counts']['ko'] = meta['lang_counts'].get('ko', 0) + 1
        elif re.search(r'[a-zA-Z]', w):
            meta['lang_counts']['en'] = meta['lang_counts'].get('en', 0) + 1
        else:
            meta['lang_counts']['other'] = meta['lang_counts'].get('other', 0) + 1
    
    atomic_write_json(meta, META_PATH, indent=2)
    
    file_size = os.path.getsize(META_PATH)
    logger.info(f"💾 元数据保存: qlg_vocab_meta.json ({file_size/1024/1024:.1f}MB)")
    vec_size = os.path.getsize(os.path.join(STATE_DIR, 'qlg_vocab_vectors.npz'))
    logger.info(f"💾 向量文件: {vec_size/1024/1024:.1f}MB")
    logger.info(f"\n{'='*50}")
    logger.info(f"✨ QLG 扩展完成！")
    logger.info(f"   词汇: {len(words)} (新增 {len(words)-1249} 词)")
    logger.info(f"   边: {sum(len(v) for v in transitions.values())}")
    logger.info(f"   总量: {(file_size + vec_size)/1024/1024:.1f}MB")
    logger.info(f"{'='*50}")